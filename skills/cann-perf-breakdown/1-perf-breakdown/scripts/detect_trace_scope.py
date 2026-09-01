#!/usr/bin/env python3
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
            if (k in flat and isinstance(flat[k], int)
                    and not isinstance(flat[k], bool) and flat[k] > 0):
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


def detect(yaml_path, rank, config, manifest, pipeline_stage=None):
    evidence = []
    parallelism = {d: 'unknown' for d in PARALLEL_KEYS}
    world_size = None
    flat = {}

    if yaml_path and os.path.exists(yaml_path):
        ydata = parse_yaml_min(yaml_path)
        parallelism, ev, flat = extract_parallelism(ydata)
        evidence.extend(ev)
        world_size = flat.get('world_size')
        if (isinstance(world_size, int) and not isinstance(world_size, bool)
                and world_size > 0):
            parallelism['world_size'] = world_size

    existing_scope = (config or {}).get('trace_scope') or {}
    existing_parallelism = existing_scope.get('parallelism') or {}
    existing_evidence = existing_scope.get('evidence') or []
    preserved = False
    for dimension, value in existing_parallelism.items():
        evidence_pattern = re.compile(
            rf'\b{re.escape(dimension)}\s*=\s*{value}\s+from\s+(?:yaml key|source)\b',
            re.IGNORECASE)
        has_matching_evidence = any(
            evidence_pattern.search(str(item)) for item in existing_evidence)
        if (parallelism.get(dimension) in (None, 'unknown')
                and isinstance(value, int) and not isinstance(value, bool) and value > 0
                and has_matching_evidence):
            parallelism[dimension] = value
            preserved = True
    if preserved:
        for item in existing_evidence:
            if item not in evidence:
                evidence.append(item)

    if pipeline_stage is None:
        for key in PIPELINE_STAGE_KEYS:
            value = flat.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                pipeline_stage = value
                evidence.append(f'pipeline_stage={value} from yaml key {key}')
                break
    elif isinstance(pipeline_stage, int) and not isinstance(pipeline_stage, bool):
        evidence.append(f'pipeline_stage={pipeline_stage} supplied explicitly')

    total_main = None
    if manifest and isinstance(manifest.get('num_main_layers'), int):
        total_main = manifest['num_main_layers']
    elif config:
        nm = (config.get('architecture') or {}).get('num_main_layers')
        if isinstance(nm, int):
            total_main = nm

    observed_layers = set()
    if config:
        for inst in config.get('trace_instances', []):
            mli = inst.get('model_layer_index')
            if (isinstance(mli, int)
                    and (total_main is None or 0 <= mli < total_main)):
                observed_layers.add(mli)

    pp = parallelism.get('pp')
    pp_proven = isinstance(pp, int) and pp > 1

    kind = 'unknown'
    confidence = 'unknown'
    valid_stage = (isinstance(pipeline_stage, int)
                   and not isinstance(pipeline_stage, bool)
                   and pipeline_stage >= 0
                   and (not pp_proven or pipeline_stage < pp))

    if pp_proven and valid_stage:
        kind = 'pipeline_stage_local'
        confidence = 'high'
        evidence.append(f'PP={pp} proven and pipeline_stage={pipeline_stage} explicit')
    elif pp_proven:
        kind = 'unknown'
        confidence = 'low'
        pipeline_stage = None
        if rank is not None:
            evidence.append(
                f'PP={pp}>1 and global rank={rank}, but launcher rank ordering is unknown '
                f'-> cannot assign pipeline stage')
        else:
            evidence.append(f'PP={pp}>1 but pipeline stage unknown -> cannot assign stage')
    else:
        # PP not proven
        sharded = any(isinstance(parallelism.get(d), int) and parallelism[d] > 1
                      for d in ('tp', 'ep', 'cp'))
        if total_main is not None and observed_layers:
            if len(observed_layers) >= total_main:
                # sees all main layers -> a rank holding full layer stack (tensor-sharded)
                kind = 'rank_local' if sharded else 'full_model'
                confidence = 'medium' if sharded else 'low'
                evidence.append(
                    f'observed {len(observed_layers)} main layers == total {total_main}; '
                    f'{"sharded (TP/EP/CP>1) -> rank_local" if sharded else "no sharding evidence"}')
            else:
                # partial layers, no PP proof -> DO NOT claim pipeline rank 0
                kind = 'unknown'
                confidence = 'low'
                evidence.append(
                    f'observed only {len(observed_layers)}/{total_main} main layers and PP not proven '
                    f'-> partial/unknown (NOT assumed pipeline rank 0)')
        else:
            kind = 'unknown'
            confidence = 'unknown'
            if not evidence:
                evidence.append('no parallel config / no observed layers -> unknown')

    return {
        'kind': kind,
        'rank': rank,
        'pipeline_stage': pipeline_stage,
        'parallelism': parallelism,
        'evidence': evidence,
        'confidence': confidence,
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
        print(f'trace_scope 已写入: {args.output}  kind={scope["kind"]} confidence={scope["confidence"]}')
    else:
        print(text)


if __name__ == '__main__':
    main()
