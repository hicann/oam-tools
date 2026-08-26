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
validate_architecture.py — validate a schema-v2 analysis_config's architecture
block, optionally against an extracted model_manifest.json.

Checks (A1..A9):
  A1 main layer count == manifest.num_main_layers (if manifest given)
  A2 layer_groups complete + disjoint + within [0, num_main_layers-1]
  A3 dense/moe classification matches manifest predicates (if manifest given)
  A4 learned prediction-module (MTP) count == manifest.prediction count / config key
  A5 trace instances never introduce a model_layer_index outside declared architecture
     (i.e. MTP invocations are NOT counted as new learned layers)
  A6 every claimed model layer has a source-backed type (source_ref present, not unknown)
  A7 a partial trace (trace_scope.kind != full_model) cannot claim full coverage of
     all main layers unless scope==full_model
  A8 trace_scope.kind==full_model requires evidence for full ownership
  A9 unsupported/ambiguous topology (num_main_layers unknown, empty layer_groups) -> block

--json prints one JSON object. Exit nonzero on any error.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import breakdown_common as bc  # noqa: E402


class Issue(dict):
    def __init__(self, code, severity, path, message):
        super().__init__(id=code, severity=severity, node_path=path, message=message)


def _validate_topology(arch, num_main, issues):
    if num_main == 'unknown' or num_main is None:
        issues.append(Issue('A9', 'error', 'architecture.num_main_layers',
                            'num_main_layers 未知/缺失，拓扑无法验证（阻断）'))
    if not arch.get('layer_groups'):
        issues.append(Issue('A9', 'error', 'architecture.layer_groups',
                            'layer_groups 为空，无法验证层分类（阻断）'))


def _validate_layer_groups(arch, num_main, issues):
    main_indices, duplicate_indices, groups_by_idx = bc.collect_main_layer_indices(arch)
    for idx in sorted(set(duplicate_indices)):
        issues.append(Issue('A2', 'error', f'architecture.layer_groups[idx={idx}]',
                            f'model layer {idx} 出现在多个 layer_group（不互斥）'))
    if isinstance(num_main, int) and num_main > 0:
        expected = set(range(num_main))
        got = set(main_indices)
        missing = sorted(expected - got)
        extra = sorted(got - expected)
        if missing:
            issues.append(Issue('A2', 'error', 'architecture.layer_groups',
                                f'layer_groups 未覆盖主模型层: 缺失 {missing[:20]}'
                                f'{"..." if len(missing) > 20 else ""}'))
        if extra:
            issues.append(Issue('A2', 'error', 'architecture.layer_groups',
                                f'layer_groups 含越界层号 {extra[:20]} (合法范围 0-{num_main-1})'))
    return groups_by_idx


def _validate_group_sources(arch, base_dirs, issues):
    for i, g in enumerate(arch.get('layer_groups', [])):
        ref = g.get('source_ref')
        if not ref or ref == 'unknown':
            issues.append(Issue('A6', 'warning', f'architecture.layer_groups[{i}]',
                                f'layer_group {g.get("type")} 缺少 source_ref（类型无源码证据）'))
        elif base_dirs:
            ok, reason = bc.validate_source_ref(ref, base_dirs)
            if not ok:
                issues.append(Issue('A6', 'error', f'architecture.layer_groups[{i}]', reason))


def _validate_manifest_layer_count(arch, num_main, manifest, issues):
    m_num = manifest.get('num_main_layers')
    confidence = _manifest_confidence(
        manifest, 'num_main_layers', ('num_layers', 'num_hidden_layers', 'n_layer'))
    severity = 'error' if confidence != 'low' else 'info'
    hint = ('' if severity == 'error' else
            '（manifest 为低置信度回退值，不足以否决 config；'
            '该层数尚未被 checkpoint config.json 证实，trace 仅为辅助证据；'
            '本条仅为 info，层数未确认改由评分扣分体现）')
    if isinstance(num_main, int) and isinstance(m_num, int) and num_main != m_num:
        issues.append(Issue('A1', severity, 'architecture.num_main_layers',
                            f'main layer count {num_main} != manifest {m_num}{hint}'))


def _layer_classifications(arch):
    classifications = {}
    for group in arch.get('layer_groups', []):
        for index in bc.expand_layer_group_indices(group):
            classifications[index] = group.get('classification')
    return classifications


def _validate_manifest_classifications(arch, manifest, issues):
    manifest_classes = _layer_classifications(manifest)
    for group in arch.get('layer_groups', []):
        for index in bc.expand_layer_group_indices(group):
            manifest_class = manifest_classes.get(index)
            config_class = group.get('classification')
            if manifest_class and config_class and manifest_class != config_class:
                issues.append(Issue('A3', 'error', f'architecture.layer_groups (layer {index})',
                                    f'layer {index} 分类 {config_class} 与 manifest {manifest_class} 不符'))


def _validate_manifest_prediction_count(arch, manifest, issues):
    manifest_count = sum(_as_int(p.get('learned_module_count'))
                         for p in manifest.get('prediction_modules', []))
    config_count = sum(_as_int(p.get('learned_module_count'))
                       for p in arch.get('prediction_modules', []))
    if manifest_count == config_count:
        return
    unresolved = any(p.get('source_ref') in (None, '', 'unknown')
                     for p in manifest.get('prediction_modules', []))
    confidence = _manifest_confidence(
        manifest, 'prediction_modules', ('num_nextn_predict_layers',))
    severity = 'warning' if (unresolved or confidence == 'low') else 'error'
    hint = ('' if severity == 'error' else
            '（manifest 的 prediction module 缺少已解析的 source_ref 或为低置信度，'
            '请确认该模块在 modeling 源码中真实存在）')
    issues.append(Issue('A4', severity, 'architecture.prediction_modules',
                        f'learned prediction module 数 {config_count} != manifest {manifest_count}'
                        f'{hint}'))


def _validate_prediction_indices(arch, num_main, issues):
    if not isinstance(num_main, int):
        return
    for i, prediction in enumerate(arch.get('prediction_modules', [])):
        for index in prediction.get('model_layer_indices', []):
            if index < num_main:
                issues.append(Issue(
                    'A4', 'error', f'architecture.prediction_modules[{i}]',
                    f'prediction module 层号 {index} 落入主模型层范围 [0,{num_main-1}]，'
                    f'MTP 层必须追加在主层之后'))


def _validate_trace_instances(config, arch, groups_by_idx, issues):
    owner_by_index = dict(groups_by_idx)
    owner_by_index.update(bc.collect_prediction_layer_indices(arch))
    declared = set(owner_by_index)
    for inst in config.get('trace_instances', []):
        mli = inst.get('model_layer_index')
        if mli == 'unknown':
            continue
        if not isinstance(mli, int) or not declared:
            continue
        if mli not in declared:
            issues.append(Issue('A5', 'error', f'trace_instances/{inst.get("instance_id")}',
                                f'trace instance model_layer_index={mli} 不在已声明的模型层集合中'
                                f'（禁止把运行时 invocation 当作新学习层）'))
            continue
        # Membership in the UNION is not attribution. An MTP invocation parked on a layer id
        # that belongs to a MoE group passes the check above while being filed under the wrong
        # module: downstream joins architecture to trace on this index, so the prediction
        # module reports 0 invocations and its whole cost disappears from the report.
        declared_type = inst.get('layer_group_type')
        owner = owner_by_index.get(mli)
        if declared_type and owner and declared_type != owner:
            issues.append(Issue('A5', 'error', f'trace_instances/{inst.get("instance_id")}',
                                f'trace instance 声明 layer_group_type={declared_type}，'
                                f'但 model_layer_index={mli} 在 architecture 中归属 {owner}；'
                                f'MTP/预测模块必须使用其架构层号（追加在主层之后），'
                                f'不得借用主层层号'))


def _observed_main_layers(config, num_main):
    observed_layers = set()
    for instance in config.get('trace_instances', []):
        layer_index = instance.get('model_layer_index')
        if isinstance(layer_index, int) and layer_index < num_main:
            observed_layers.add(layer_index)
    return observed_layers


def _validate_trace_scope(config, num_main, issues):
    scope = config.get('trace_scope') or {}
    kind = scope.get('kind', 'unknown')
    if kind == 'full_model':
        ev = scope.get('evidence') or []
        if not ev:
            issues.append(Issue('A8', 'error', 'trace_scope',
                                'trace_scope.kind=full_model 但无 evidence，无法证明完整模型所有权（阻断）'))
        if isinstance(num_main, int):
            observed_layers = _observed_main_layers(config, num_main)
            if observed_layers and len(observed_layers) < num_main:
                issues.append(Issue('A7', 'error', 'trace_scope',
                                    f'trace_scope.kind=full_model，但仅观测到 {len(observed_layers)}/{num_main} '
                                    f'个主模型层的 invocation，不能声明为完整模型'))


def validate(config: dict, manifest: dict, base_dirs):
    issues = []
    arch = config.get('architecture') or {}
    num_main = arch.get('num_main_layers')
    _validate_topology(arch, num_main, issues)
    groups_by_idx = _validate_layer_groups(arch, num_main, issues)
    _validate_group_sources(arch, base_dirs, issues)
    if manifest:
        _validate_manifest_layer_count(arch, num_main, manifest, issues)
        _validate_manifest_classifications(arch, manifest, issues)
        _validate_manifest_prediction_count(arch, manifest, issues)
    _validate_prediction_indices(arch, num_main, issues)
    _validate_trace_instances(config, arch, groups_by_idx, issues)
    _validate_trace_scope(config, num_main, issues)

    return issues


def _as_int(v):
    return v if isinstance(v, int) else 0


def _manifest_confidence(manifest, field, fact_keys):
    """Lowest confidence among the manifest facts backing `field`.

    Thin wrapper over the shared rule so A1/A4, MT1 and MA1 cannot drift apart.
    """
    return bc.manifest_fact_confidence(manifest, fact_keys)


def run(config_path, manifest_path, base_dirs):
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    version = bc.detect_schema_version(config)
    manifest = None
    if manifest_path:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

    if version != 2:
        issues = [Issue('A0', 'error', '<global>',
                        f'architecture validation 需要 schema v2；检测到 v{version}。'
                        f'请先用 migrate_config.py 迁移（会标记 legacy_unverified）。')]
        return issues, version
    return validate(config, manifest, base_dirs), version


def main():
    parser = argparse.ArgumentParser(description='Architecture validator (schema v2)')
    parser.add_argument('-c', '--config', required=True)
    parser.add_argument('-m', '--manifest', help='model_manifest.json（可选，用于交叉验证）')
    parser.add_argument('--source-dir', action='append', default=[],
                        help='源码根目录，用于校验 source_ref 存在性（可多次）')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    if not os.path.exists(args.config):
        bc.emit_error(f'错误: 文件不存在: {args.config}\n')
        sys.exit(2)

    base_dirs = args.source_dir or [os.getcwd()]
    issues, version = run(args.config, args.manifest, base_dirs)
    errors = [i for i in issues if i['severity'] == 'error']
    warnings = [i for i in issues if i['severity'] == 'warning']

    if args.json:
        bc.emit(json.dumps({
            'script': 'validate_architecture.py',
            'config': args.config,
            'manifest': args.manifest,
            'schema_version': version,
            'error_count': len(errors),
            'warning_count': len(warnings),
            'issues': issues,
        }, indent=2, ensure_ascii=False))
    else:
        for it in issues:
            bc.emit(f'[{it["severity"].upper()}] {it["id"]} @ {it["node_path"]}: {it["message"]}')
        bc.emit(f'\n汇总: errors={len(errors)}, warnings={len(warnings)}')

    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
