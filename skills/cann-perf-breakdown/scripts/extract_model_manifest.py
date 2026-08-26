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
extract_model_manifest.py — statically extract architecture ground truth.

Reads a model's configuration + modeling source with Python AST (NEVER imports or
executes model code) and emits model_manifest.json conforming to
schemas/model_manifest.schema.json.

Every fact carries source_ref + extraction method + confidence. Values that cannot
be resolved statically are recorded as "unknown" and listed in evidence_gaps — the
extractor never guesses architecture numbers.

Usage:
  python scripts/extract_model_manifest.py --model-dir models/ds3.2 -o outputs/model_manifest.json
  python scripts/extract_model_manifest.py --config models/ds3.2/models/configuration_deepseek.py \
      --modeling models/ds3.2/models/modeling_deepseek.py -o outputs/model_manifest.json
"""
import argparse
import ast
import json
import os
import re
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import adapters  # noqa: E402
import breakdown_common as bc  # noqa: E402
from adapters.base import (find_config_class, extract_init_defaults, scan_evidence,  # noqa: E402
                           ExtractionContext, UNKNOWN)


@dataclass(frozen=True)
class ManifestInput:
    config_path: str
    modeling_path: str
    model_name: str
    base_dir: str
    model_dir: str = None
    capture_dir: str = None


@dataclass
class ManifestState:
    request: ManifestInput
    config_src: str = ''
    modeling_src: str = ''
    config_tree: object = None
    modeling_tree: object = None
    config_defaults: dict = field(default_factory=dict)
    config_class_name: str = None
    evidence: dict = field(default_factory=dict)
    selection: dict = None
    adapter: object = None
    weights_config_path: str = None
    declared_weights_path: str = None
    weights_values: dict = field(default_factory=dict)
    facts: list = field(default_factory=list)
    layer_groups: list = field(default_factory=list)
    prediction_modules: list = field(default_factory=list)
    num_main: object = UNKNOWN
    gaps: list = field(default_factory=list)
    source_of_truth: list = field(default_factory=list)
    capabilities: list = field(default_factory=list)
    dataflow_invariants: list = field(default_factory=list)


def read(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def _weights_config_from_yaml(path):
    declared = None
    for line in read(path).splitlines():
        stripped = line.strip()
        if not stripped.startswith('model_path:'):
            continue
        value = stripped.split(':', 1)[1].strip().strip('"\'')
        if not value:
            continue
        declared = declared or value
        candidate = os.path.join(value, 'config.json')
        if os.path.isfile(candidate):
            return candidate, value
    return None, declared


def find_weights_config(model_dir):
    """Resolve the checkpoint config.json a runtime YAML points at.

    Python default args describe the family, not the deployed checkpoint: LongCat's
    config.py defaults to the 61-layer Flash while the YAML loads 14-layer Lite
    weights. The checkpoint config.json is the real source of truth, so when it is
    reachable it must win, and when it is not the caller has to know that the numbers
    came from a fallback.

    Returns (config_json_path_or_None, declared_model_path_or_None).
    """
    if not model_dir or not os.path.isdir(model_dir):
        return None, None
    declared = None
    for root, _dirs, files in os.walk(model_dir):
        for filename in sorted(files):
            if not filename.endswith(('.yaml', '.yml')):
                continue
            candidate, yaml_declared = _weights_config_from_yaml(
                os.path.join(root, filename))
            declared = declared or yaml_declared
            if candidate:
                return candidate, yaml_declared
    # A checkpoint vendored next to the source needs no YAML to be authoritative.
    local = os.path.join(model_dir, 'config.json')
    if os.path.isfile(local):
        return local, model_dir
    return None, declared


def find_source_files(model_dir):
    """Locate configuration_*.py and modeling_*.py under a model dir."""
    config_file = None
    modeling_file = None
    for root, _dirs, files in os.walk(model_dir):
        for fn in files:
            if not fn.endswith('.py'):
                continue
            low = fn.lower()
            full = os.path.join(root, fn)
            if ('config' in low) and config_file is None and 'configuration' in low:
                config_file = full
            elif low.startswith('config_') and config_file is None:
                config_file = full
            if low.startswith('modeling_') and modeling_file is None:
                modeling_file = full
    # fallback: any file with a *Config class / *DecoderLayer class
    return config_file, modeling_file


def _analyze_manifest_sources(state):
    request = state.request
    state.config_src = read(request.config_path) if request.config_path else ''
    state.modeling_src = read(request.modeling_path) if request.modeling_path else ''
    state.config_tree = ast.parse(state.config_src) if state.config_src else None
    state.modeling_tree = ast.parse(state.modeling_src) if state.modeling_src else None
    if state.config_tree is not None:
        config_class, init_fn = find_config_class(state.config_tree, state.modeling_tree)
        state.config_class_name = config_class.name if config_class is not None else None
        if init_fn is not None:
            state.config_defaults = extract_init_defaults(init_fn)
    state.evidence = scan_evidence(state.config_src, state.modeling_src)
    state.selection = adapters.resolve_adapter(state.evidence)
    state.adapter = state.selection['adapter']


def _load_manifest_weights(state):
    state.weights_config_path, state.declared_weights_path = find_weights_config(
        state.request.model_dir)
    if not state.weights_config_path:
        return
    try:
        with open(state.weights_config_path, 'r', encoding='utf-8') as file_obj:
            state.weights_values = json.load(file_obj)
    except (OSError, ValueError):
        state.weights_values = {}
    for key, value in state.weights_values.items():
        if isinstance(value, (int, float, bool)) and not isinstance(value, bool):
            state.config_defaults[key] = (value, 1)


def _extract_manifest_architecture(state):
    request = state.request
    context = ExtractionContext(
        config_tree=state.config_tree,
        modeling_tree=state.modeling_tree,
        config_defaults=state.config_defaults,
        base_dir=request.base_dir,
        config_path=request.config_path or UNKNOWN,
        modeling_path=request.modeling_path or UNKNOWN,
    )
    result = state.adapter.extract(context)
    (state.facts, state.layer_groups, state.prediction_modules,
     state.num_main, state.gaps) = result


def _apply_checkpoint_evidence(state):
    request = state.request
    for path in (request.config_path, request.modeling_path):
        if path:
            relative = os.path.relpath(path, request.base_dir) if request.base_dir else path
            state.source_of_truth.append(f'{relative}:1')
    if not state.weights_config_path:
        where = state.declared_weights_path or '未在 YAML 中声明'
        state.gaps.append(f'checkpoint config.json 不可达（model_path={where}）：'
                          f'以下数值来自 Python 默认参数，可能与实际权重不符')
        for fact in state.facts:
            if fact.method == 'ast_default_arg' and fact.confidence == 'high':
                fact.confidence = 'low'
        return
    relative = (os.path.relpath(state.weights_config_path, request.base_dir)
                if request.base_dir else state.weights_config_path)
    state.source_of_truth.append(f'{relative}:1')
    for fact in state.facts:
        if fact.key in state.weights_values:
            fact.source_ref = f'{relative}:1'
            fact.method = 'weights_config_json'
            fact.confidence = 'high'


def _collect_adapter_metadata(state):
    state.capabilities = state.adapter.capabilities(state.evidence, state.config_defaults)
    selection = state.selection
    if selection['confidence'] in ('medium', 'unknown') and selection['name'] != 'generic':
        state.gaps.append(
            f"适配器 `{selection['name']}` 由 config key 签名匹配（confidence="
            f"{selection['confidence']}），未见该族 class 名：{'; '.join(selection['reasons'])}")
    if selection['name'] == 'generic':
        state.gaps.append('未匹配任何族适配器：使用 generic 基类，不假设 MoE 边界/预测模块的 '
                          'config key 拼写；相关数值若缺失属未知而非不存在')
    capability_ids = {capability['id'] for capability in state.capabilities}
    for item in state.adapter.dataflow_invariants or ():
        required = item.get('requires')
        if not required or required in capability_ids:
            state.dataflow_invariants.append(dict(item))


def _manifest_document(state):
    request = state.request
    selection = state.selection
    adapter = state.adapter
    return {
        'schema_version': 1,
        'model_name': request.model_name,
        'adapter': adapter.name,
        'adapter_selection': {
            'name': selection['name'],
            'confidence': selection['confidence'],
            'reasons': selection['reasons'],
            'candidates': [{'adapter': item['adapter'], 'confidence': item['confidence']}
                           for item in selection['candidates']],
        },
        'capabilities': state.capabilities,
        'dataflow_invariants': state.dataflow_invariants,
        'known_deviations': adapter.deviations(),
        'component_candidates': adapter.extract_components(
            state.modeling_tree, state.config_defaults, request.base_dir,
            request.modeling_path or UNKNOWN),
        'role_candidates': adapter.infer_roles(
            state.modeling_tree, request.base_dir, request.modeling_path or UNKNOWN),
        'config_class': state.config_class_name,
        'weights_config': state.weights_config_path,
        'declared_model_path': state.declared_weights_path,
        'source_of_truth': state.source_of_truth,
        'num_main_layers': state.num_main,
        'layer_groups': state.layer_groups,
        'prediction_modules': state.prediction_modules,
        'facts': [fact.as_dict() for fact in state.facts],
        'evidence_gaps': state.gaps,
    }


def _append_capture_provenance(state, manifest):
    request = state.request
    provenance = detect_capture_provenance(
        request.model_dir, request.capture_dir, request.base_dir,
        weights_config_path=state.weights_config_path, modeling_path=request.modeling_path)
    manifest['capture_provenance'] = provenance
    checkpoint = provenance['checkpoint_config']
    if checkpoint.get('evidence_level') == 4:
        state.gaps.append(
            f'checkpoint config.json 不可达且无运行期记录（{checkpoint.get("method")}）：'
            f'num_main_layers={state.num_main} 等标量仅有源码默认值支撑，'
            f'部署时可能被覆盖。结论按 tier={provenance["tier"]} 标注，不据此判定拆解错误')


def build_manifest(request):
    state = ManifestState(request)
    _analyze_manifest_sources(state)
    _load_manifest_weights(state)
    _extract_manifest_architecture(state)
    _apply_checkpoint_evidence(state)
    _collect_adapter_metadata(state)
    manifest = _manifest_document(state)
    _append_capture_provenance(state, manifest)
    return manifest


#: Directories that never hold a capture's own provenance.
_PROVENANCE_SKIP_DIRS = frozenset({
    '.git', '__pycache__', 'node_modules', '.pytest_cache', 'tests', 'fixtures'})

#: Files that record a config value printed by a real load, in preference order. A value
#: transcribed from a run of `Config(**json.load(open('config.json')))` is checkpoint evidence
#: even though the checkpoint itself was not delivered.
_RUNTIME_RECORD_SUFFIXES = ('.md', '.log', '.txt')

#: `key: value` as printed by a loaded config, not `key=value` as written in a def signature.
_RUNTIME_RECORD_RE = re.compile(
    r'\b(num_hidden_layers|num_layers|n_layers)\s*:\s*(\d+)\b')


def _runtime_record_in_file(path, base_dir):
    for lineno, line in enumerate(read(path).splitlines(), 1):
        if 'def ' in line or 'self.' in line or '=' in line.split(':', 1)[0]:
            continue
        match = _RUNTIME_RECORD_RE.search(line)
        if match:
            return {
                'key': match.group(1),
                'value': int(match.group(2)),
                'source_ref': f'{os.path.relpath(path, base_dir)}:{lineno}',
                'method': 'checkpoint_config_via_runtime_record',
                'excerpt': line.strip()[:200],
            }
    return None


def _find_runtime_config_record(search_root, base_dir):
    """Search for a transcript of a real config load: evidence level 2.

    A checkpoint `config.json` that was not shipped with the capture is still the source of
    truth, and a log line showing what it produced carries that truth. LongCat's real layer
    count (14, against an AST default of 56) is only knowable this way. Declaring an evidence
    gap before searching for this would report a value as unconfirmable while its confirmation
    sits in the bundle.
    """
    if not search_root or not os.path.isdir(search_root):
        return None
    for root, dirs, files in os.walk(search_root):
        dirs[:] = [d for d in dirs if d not in _PROVENANCE_SKIP_DIRS]
        for filename in sorted(files):
            if not filename.endswith(_RUNTIME_RECORD_SUFFIXES):
                continue
            record = _runtime_record_in_file(os.path.join(root, filename), base_dir)
            if record:
                return record
    return None


def _locate_provenance_item(roots, name, base_dir, want_dir=False):
    for root in roots:
        for current, dirs, files in os.walk(root):
            dirs[:] = [item for item in dirs if item not in _PROVENANCE_SKIP_DIRS]
            candidates = dirs if want_dir else files
            if name in candidates:
                return os.path.relpath(os.path.join(current, name), base_dir)
    return None


def _is_self_defined_model(modeling_path):
    if not modeling_path or not os.path.isfile(modeling_path):
        return False
    head = read(modeling_path)[:4000].lower()
    markers = ('randomly initialised', 'randomly initialized', 'random weights')
    return any(marker in head for marker in markers)


def _checkpoint_provenance(weights_config_path, modeling_path, base_dir, self_defined,
                           capture_context):
    source_snapshot = capture_context['source_snapshot']
    checkpoint = {'present': bool(weights_config_path)}
    if weights_config_path:
        checkpoint.update(evidence_level=1, source_ref=weights_config_path,
                          method='checkpoint_config_json')
        return checkpoint
    if self_defined:
        checkpoint.update(evidence_level=1, method='self_defined_source_is_truth',
                          source_ref=(os.path.relpath(modeling_path, base_dir)
                                      if modeling_path else None),
                          note='权重随机初始化，不存在可覆盖源码的 checkpoint：源码即架构真值')
        return checkpoint
    record = (_find_runtime_config_record(capture_context['capture_dir'], base_dir)
              or _find_runtime_config_record(capture_context['model_dir'], base_dir))
    if record:
        checkpoint.update(evidence_level=2, **record)
    elif source_snapshot:
        checkpoint.update(evidence_level='2S', method='ast_default_bound_by_snapshot',
                          source_ref=source_snapshot,
                          note='源码快照与本次采集同源，AST 默认值即本次实际值')
    else:
        checkpoint.update(evidence_level=4, method='ast_default_arg_unbound',
                          note='仅有源码默认参数，且无法证明源码与本次 trace 同源：'
                               '部署时可能被 checkpoint 覆盖')
    return checkpoint


def _provenance_tier(self_defined, capture_manifest, source_snapshot, step_marks,
                     modeling_path):
    if self_defined:
        return 'S0', '模型定义在仓库内、权重随机初始化，源码即唯一真值'
    if capture_manifest and source_snapshot and step_marks:
        return 'S', '自采：capture_manifest + source_snapshot + step_marks 齐备'
    if modeling_path:
        return 'A', '第三方交付：有源码但无采集溯源链，源码与 trace 的同源性无法证明'
    return 'B', '无模型源码：拓扑无法核对'


def detect_capture_provenance(model_dir, capture_dir, base_dir,
                              weights_config_path=None, modeling_path=None):
    """Classify how much this capture can prove about itself.

    The tier is NOT a measure of how much data arrived; it is whether the source can be shown
    to describe the run that produced the trace. A self-captured bundle records the msprof
    command, the environment and a `source_snapshot/` of the code as it was at capture time, so
    "the AST default is the deployed value" has evidence. A third-party delivery has source
    that arrived separately, and nothing ties it to that trace.

    That distinction matters more than the presence of a checkpoint `config.json`: qwen7b has
    no config.json either, yet its snapshot makes its AST defaults trustworthy, while ds3.2's
    identical-looking AST default may be overridden by weights nobody delivered.
    """
    roots = [d for d in (capture_dir, model_dir) if d and os.path.isdir(d)]
    capture_manifest = _locate_provenance_item(roots, 'capture_manifest.json', base_dir)
    source_snapshot = _locate_provenance_item(
        roots, 'source_snapshot', base_dir, want_dir=True)
    step_marks = _locate_provenance_item(roots, 'step_marks.json', base_dir)

    # A model defined by the repo's own source with randomly initialised weights has no
    # checkpoint to disagree with: the source IS the architecture, not a default awaiting
    # override. That is the strongest evidence available, not the weakest.
    self_defined = _is_self_defined_model(modeling_path)
    capture_context = {
        'source_snapshot': source_snapshot,
        'capture_dir': capture_dir,
        'model_dir': model_dir,
    }
    checkpoint = _checkpoint_provenance(
        weights_config_path, modeling_path, base_dir, self_defined, capture_context)
    tier, tier_reason = _provenance_tier(
        self_defined, capture_manifest, source_snapshot, step_marks, modeling_path)

    return {
        'tier': tier,
        'tier_reason': tier_reason,
        'capture_manifest': capture_manifest,
        'source_snapshot': source_snapshot,
        'step_marks': step_marks,
        'model_source': {
            'present': bool(modeling_path),
            'path': (os.path.relpath(modeling_path, base_dir)
                     if modeling_path and os.path.exists(modeling_path) else None),
            # Only a snapshot (or a self-defined model) ties source to this trace.
            'bound_to_capture': bool(source_snapshot or self_defined),
        },
        'checkpoint_config': checkpoint,
    }


def main():
    parser = argparse.ArgumentParser(description='Static model architecture manifest extractor (AST only)')
    parser.add_argument('--model-dir', help='模型目录（自动定位 configuration_*.py / modeling_*.py）')
    parser.add_argument('--config', help='configuration 源文件')
    parser.add_argument('--modeling', help='modeling 源文件')
    parser.add_argument('--model-name', default=None)
    parser.add_argument('--base-dir', default=None, help='source_ref 相对根目录（默认当前工作目录）')
    parser.add_argument('--capture-dir',
                        help='采集目录：探测 capture_manifest.json / source_snapshot/ / '
                             'step_marks.json 与运行期 config 记录，用于判定采集溯源档位。'
                             '未提供时仅按 --model-dir 探测')
    parser.add_argument('-o', '--output', help='输出 model_manifest.json（默认打印）')
    args = parser.parse_args()

    config_path = args.config
    modeling_path = args.modeling
    if args.model_dir:
        c, m = find_source_files(args.model_dir)
        config_path = config_path or c
        modeling_path = modeling_path or m

    if not config_path:
        bc.emit_error('错误: 未找到 configuration 源文件（--config 或 --model-dir）\n')
        sys.exit(2)

    base_dir = args.base_dir or os.getcwd()
    model_name = args.model_name or (os.path.basename(os.path.normpath(args.model_dir))
                                     if args.model_dir else 'unknown')

    manifest = build_manifest(ManifestInput(
        config_path=config_path,
        modeling_path=modeling_path,
        model_name=model_name,
        base_dir=base_dir,
        model_dir=args.model_dir,
        capture_dir=args.capture_dir,
    ))

    text = json.dumps(manifest, indent=2, ensure_ascii=False)
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
        bc.emit(f'model_manifest 已生成: {args.output}')
        prov = manifest['capture_provenance']
        bc.emit(f'adapter={manifest["adapter"]}  num_main_layers={manifest["num_main_layers"]}  '
              f'layer_groups={len(manifest["layer_groups"])}  '
              f'prediction_modules={len(manifest["prediction_modules"])}  gaps={len(manifest["evidence_gaps"])}')
        bc.emit(f'tier={prov["tier"]}  '
              f'checkpoint_evidence_level={prov["checkpoint_config"].get("evidence_level")}  '
              f'source_bound_to_capture={prov["model_source"]["bound_to_capture"]}')
    else:
        bc.emit(text)


if __name__ == '__main__':
    main()
