#!/usr/bin/env python3
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""
detect_trace_scope.py — determine whether a trace is full_model / rank_local /
pipeline_stage_local / unknown, using only provable evidence.

Inputs (any subset):
  --yaml       runtime config YAML (parallel_config: tp/ep/pp/cp sizes, world_size)
  --rank       explicit global rank id (from launcher/env), optional
  --pipeline-stage explicit pipeline stage id, optional
  --config     schema-v2 analysis_config (to read observed layer count)
  --manifest   model_manifest (to know total main layers)

Rules (no guessing):
  - If a PP size > 1 is proven AND a stage id is explicit -> pipeline_stage_local.
    A global rank is never treated as a stage id because rank ordering is launcher-specific.
  - If TP/EP/CP > 1 (sharding) but PP == 1 (or absent) and observed layer set == all main
    layers -> rank_local (rank shares full layer set, sharded tensors).
  - If observed main-layer count < total main layers and PP not proven -> unknown/partial,
    NEVER "pipeline rank 0".
  - If nothing is known -> unknown.

Emits a trace_scope object (matches analysis_config_v2 trace_scope). --json prints it.
"""
import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import breakdown_common as bc  # noqa: E402


def parse_yaml_min(path):
    """Very small YAML reader for flat `key: value` and one-level nested maps.

    Avoids a PyYAML dependency. Only extracts scalar ints/strings we care about.
    """
    data = {}
    stack = [(-1, data)]
    key_re = re.compile(r'^(\s*)([A-Za-z0-9_]+):\s*(.*)$')
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for raw in f:
            line = raw.rstrip('\n')
            if not line.strip() or line.strip().startswith('#'):
                continue
            m = key_re.match(line)
            if not m:
                continue
            indent, key, val = len(m.group(1)), m.group(2), m.group(3)
            # strip inline comments
            val = re.split(r'\s+#', val, 1)[0].strip()
            while stack and stack[-1][0] >= indent:
                stack.pop()
            parent = stack[-1][1]
            if val == '':
                child = {}
                parent[key] = child
                stack.append((indent, child))
            else:
                parent[key] = _coerce(val)
    return data


def _coerce(v):
    v = v.strip().strip('"').strip("'")
    if re.fullmatch(r'-?\d+', v):
        return int(v)
    low = v.lower()
    if low in ('true', 'false'):
        return low == 'true'
    return v


PARALLEL_KEYS = {
    'tp': ['tp_size', 'attn_tp_size', 'tensor_parallel_size', 'dense_tp_size'],
    'ep': ['ep_size', 'moe_ep_size', 'expert_parallel_size'],
    'pp': ['pp_size', 'pipeline_parallel_size', 'pipeline_model_parallel_size', 'num_pp_stages'],
    'cp': ['cp_size', 'context_parallel_size'],
    'dp': ['dp_size', 'data_parallel_size', 'embed_dp_size'],
}

PIPELINE_STAGE_KEYS = ('pipeline_stage', 'pipeline_stage_id', 'pipeline_rank', 'pp_rank')


def extract_parallelism(yaml_data):
    """Return ({dim: int_or_unknown}, evidence:list). PP absent -> 'unknown' (not 1)."""
    result = {}
    evidence = []
    flat = {}

    def flatten(d, prefix=''):
        for k, v in d.items():
            if isinstance(v, dict):
                flatten(v, prefix)
            else:
                flat[k] = v

    flatten(yaml_data)
    for dim, keys in PARALLEL_KEYS.items():
        found = None
        for k in keys:
            if k in flat and isinstance(flat[k], int):
                found = flat[k]
                evidence.append(f'{dim}={found} from yaml key {k}')
                break
        # PP is special: if no PP key present at all, it is UNKNOWN, not 1.
        if found is None:
            result[dim] = 'unknown' if dim == 'pp' else 'unknown'
        else:
            result[dim] = found
    if 'world_size' in flat:
        evidence.append(f'world_size={flat["world_size"]}')
    return result, evidence, flat


@dataclass
class ScopeState:
    rank: int
    pipeline_stage: int
    parallelism: dict = field(default_factory=lambda: {key: 'unknown' for key in PARALLEL_KEYS})
    evidence: list = field(default_factory=list)
    flat: dict = field(default_factory=dict)
    world_size: int = None
    total_main: int = None
    observed_layers: set = field(default_factory=set)
    kind: str = 'unknown'
    confidence: str = 'unknown'


def _load_parallelism(yaml_path, state):
    if not yaml_path or not os.path.exists(yaml_path):
        return
    yaml_data = parse_yaml_min(yaml_path)
    state.parallelism, extracted, state.flat = extract_parallelism(yaml_data)
    state.evidence.extend(extracted)
    state.world_size = state.flat.get('world_size')


def _resolve_pipeline_stage(state):
    if state.pipeline_stage is None:
        for key in PIPELINE_STAGE_KEYS:
            value = state.flat.get(key)
            if isinstance(value, int):
                state.pipeline_stage = value
                state.evidence.append(f'pipeline_stage={value} from yaml key {key}')
                return
    elif isinstance(state.pipeline_stage, int):
        state.evidence.append(f'pipeline_stage={state.pipeline_stage} supplied explicitly')


def _collect_scope_layers(config, manifest, state):
    if manifest and isinstance(manifest.get('num_main_layers'), int):
        state.total_main = manifest['num_main_layers']
    elif config:
        num_main = (config.get('architecture') or {}).get('num_main_layers')
        if isinstance(num_main, int):
            state.total_main = num_main
    if config:
        for instance in config.get('trace_instances', []):
            model_index = instance.get('model_layer_index')
            if isinstance(model_index, int):
                state.observed_layers.add(model_index)


def _classify_without_pipeline(state):
    sharded = any(isinstance(state.parallelism.get(dim), int)
                  and state.parallelism[dim] > 1 for dim in ('tp', 'ep', 'cp'))
    if state.total_main is not None and state.observed_layers:
        observed_count = len(state.observed_layers)
        if observed_count >= state.total_main:
            state.kind = 'rank_local' if sharded else 'full_model'
            state.confidence = 'medium' if sharded else 'low'
            state.evidence.append(
                f'observed {observed_count} main layers == total {state.total_main}; '
                f'{"sharded (TP/EP/CP>1) -> rank_local" if sharded else "no sharding evidence"}')
        else:
            state.confidence = 'low'
            state.evidence.append(
                f'observed only {observed_count}/{state.total_main} main layers and PP not proven '
                f'-> partial/unknown (NOT assumed pipeline rank 0)')
    elif not state.evidence:
        state.evidence.append('no parallel config / no observed layers -> unknown')


def _classify_scope(state):
    pp = state.parallelism.get('pp')
    pp_proven = isinstance(pp, int) and pp > 1
    valid_stage = (isinstance(state.pipeline_stage, int)
                   and state.pipeline_stage >= 0
                   and (not pp_proven or state.pipeline_stage < pp))
    if pp_proven and valid_stage:
        state.kind = 'pipeline_stage_local'
        state.confidence = 'high'
        state.evidence.append(f'PP={pp} proven and pipeline_stage={state.pipeline_stage} explicit')
    elif pp_proven:
        state.confidence = 'low'
        state.pipeline_stage = None
        if state.rank is not None:
            state.evidence.append(
                f'PP={pp}>1 and global rank={state.rank}, but launcher rank ordering is unknown '
                f'-> cannot assign pipeline stage')
        else:
            state.evidence.append(f'PP={pp}>1 but pipeline stage unknown -> cannot assign stage')
    else:
        _classify_without_pipeline(state)


def detect(yaml_path, rank, config, manifest, pipeline_stage=None):
    state = ScopeState(rank=rank, pipeline_stage=pipeline_stage)
    _load_parallelism(yaml_path, state)
    _resolve_pipeline_stage(state)
    _collect_scope_layers(config, manifest, state)
    _classify_scope(state)

    return {
        'kind': state.kind,
        'rank': rank,
        'pipeline_stage': state.pipeline_stage,
        'parallelism': state.parallelism,
        'world_size': state.world_size,
        'evidence': state.evidence,
        'confidence': state.confidence,
    }


def main():
    parser = argparse.ArgumentParser(description='Trace scope / parallel ownership detector')
    parser.add_argument('--yaml', help='runtime config YAML')
    parser.add_argument('--rank', type=int, default=None)
    parser.add_argument('--pipeline-stage', type=int, default=None,
                        help='explicit pipeline stage id; global --rank is not a stage id')
    parser.add_argument('-c', '--config', help='schema-v2 analysis_config.json')
    parser.add_argument('-m', '--manifest', help='model_manifest.json')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('-o', '--output', help='写入 trace_scope JSON')
    args = parser.parse_args()

    config = None
    if args.config and os.path.exists(args.config):
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)
    manifest = None
    if args.manifest and os.path.exists(args.manifest):
        with open(args.manifest, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

    scope = detect(args.yaml, args.rank, config, manifest, args.pipeline_stage)
    text = json.dumps(scope, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
        bc.emit(f'trace_scope 已写入: {args.output}  kind={scope["kind"]} confidence={scope["confidence"]}')
    else:
        bc.emit(text)


if __name__ == '__main__':
    main()
