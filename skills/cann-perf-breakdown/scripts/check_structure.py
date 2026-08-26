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
Step 3 Review: 校验 analysis_config.json 的结构良构性 (S1–S9)。

输出格式与 check_op_coverage.py、validate_shapes.py 统一：
  普通模式：可读文本 + 错误码退出
  --json :  追加单行 JSON 到 stdout，schema 见 schema_doc()
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import breakdown_common as bc  # noqa: E402

# 仅在已登记到 kernels[] 时才校验 shape_semantic 的算子（语义上下文相关）
# - Add 仅在残差连接语义时
# - ConcatV2/ConcatD 仅在 KV cache 拼接时
# - ScatterNdUpdate 仅在 KV cache 更新时
# 静态脚本无法判定上下文，故仅当 AI 已主动登记时才校验字段存在
SHAPE_SEMANTIC_IF_REGISTERED = {
    'Add', 'ConcatV2', 'ConcatD', 'ScatterNdUpdate',
}

# semantic 免填的算子
SEMANTIC_OPTIONAL = {'Cast', 'Reshape'}


def is_shape_contextual(name: str) -> bool:
    return name in SHAPE_SEMANTIC_IF_REGISTERED


class Issue(dict):
    def __init__(self, code, severity, path, message):
        super().__init__(id=code, severity=severity, node_path=path, message=message)


def walk_tree(node, path, callback):
    if not isinstance(node, dict):
        return
    callback(node, path)
    for child in node.get('children', []) or []:
        cname = child.get('name', '?')
        walk_tree(child, f'{path}/{cname}', callback)


def collect_leaf_op_indices(config):
    """返回 [(op_index, leaf_path)] 列表"""
    out = []

    def visit(node, path):
        # 叶子或带 op_indices 的中间节点
        for idx in node.get('op_indices', []) or []:
            out.append((idx, path))

    for sname, sinfo in (config.get('stages') or {}).items():
        walk_tree(sinfo, f'stages/{sname}', visit)
    for ltype, lstruct in (config.get('layer_structure') or {}).items():
        walk_tree(lstruct, f'layer_structure/{ltype}', visit)
    for i, aux in enumerate(config.get('runtime_auxiliary') or []):
        walk_tree(aux, f'runtime_auxiliary[{i}]', visit)
    return out


def _walk_legacy_trees(config, callback, include_layers=True):
    for name, info in (config.get('stages') or {}).items():
        walk_tree(info, f'stages/{name}', callback)
    if include_layers:
        for layer_type, structure in (config.get('layer_structure') or {}).items():
            walk_tree(structure, f'layer_structure/{layer_type}', callback)
    for index, auxiliary in enumerate(config.get('runtime_auxiliary') or []):
        walk_tree(auxiliary, f'runtime_auxiliary[{index}]', callback)


def _check_legacy_schema(config, issues):
    def check_node_schema(node, path):
        if 'name' not in node:
            issues.append(Issue('S1', 'error', path, '节点缺少 name 字段'))
        is_leaf = ('children' not in node or not node['children'])
        has_indices = 'op_indices' in node
        has_branches = 'branches' in node  # Mode B
        if is_leaf and not has_indices and not has_branches:
            issues.append(Issue('S1', 'error', path, '叶节点缺少 op_indices'))
    _walk_legacy_trees(config, check_node_schema)


def _check_legacy_layer_keys(config, issues):
    lt_keys = set((config.get('layer_types') or {}).keys())
    ls_keys = set((config.get('layer_structure') or {}).keys())
    for k in lt_keys - ls_keys:
        issues.append(Issue('S2', 'error', f'layer_types/{k}',
                            'layer_types 中存在但 layer_structure 中缺失'))
    for k in ls_keys - lt_keys:
        issues.append(Issue('S2', 'error', f'layer_structure/{k}',
                            'layer_structure 中存在但 layer_types 中缺失'))


def _check_legacy_semantics(config, issues):
    def check_semantic(node, path):
        if not node.get('semantic'):
            # 节点（非 kernel）默认必填
            issues.append(Issue('S3', 'error', path, '节点缺少 semantic'))
        for ks in node.get('kernels', []) or []:
            kn = ks.get('name', '') or ''
            kn_norm = kn.split('/')[-1] if '/' in kn else kn
            if kn_norm in SEMANTIC_OPTIONAL:
                continue
            if not ks.get('semantic'):
                issues.append(Issue('S3', 'error',
                                    f'{path}/kernels[index={ks.get("index")}]',
                                    f'kernel {kn_norm} 缺少 semantic'))
    _walk_legacy_trees(config, check_semantic)


def _check_legacy_code_refs(config, issues):
    def check_code_ref(node, path):
        if not node.get('code_ref') and 'branches' not in node:
            issues.append(Issue('S4', 'warning', path, '节点缺少 code_ref'))
    _walk_legacy_trees(config, check_code_ref)


def _check_legacy_shapes(config, issues):
    def check_shape_semantic(node, path):
        for ks in node.get('kernels', []) or []:
            kn = ks.get('name', '') or ''
            kn_norm = kn.split('/')[-1] if '/' in kn else kn
            requires_shape = (bc.is_shape_semantic_required(kn_norm)
                              or is_shape_contextual(kn_norm))
            if requires_shape and not ks.get('shape_semantic'):
                sev = 'error' if bc.is_shape_semantic_required(kn_norm) else 'warning'
                issues.append(Issue('S5', sev,
                                    f'{path}/kernels[index={ks.get("index")}]',
                                    f'{kn_norm} 已登记 kernels[] 但缺 shape_semantic'))
    _walk_legacy_trees(config, check_shape_semantic)


def _check_legacy_indices(config, issues):
    for ltype, info in (config.get('layer_types') or {}).items():
        idx = info.get('layer_indices', [])
        if len(idx) != len(set(idx)):
            issues.append(Issue('S6', 'error', f'layer_types/{ltype}',
                                'layer_indices 含重复值'))

    def check_indices_unique(node, path):
        for fld in ('stage_indices', 'instance_indices'):
            v = node.get(fld)
            if v and len(v) != len(set(v)):
                issues.append(Issue('S6', 'error', path,
                                    f'{fld} 含重复值'))
    _walk_legacy_trees(config, check_indices_unique, include_layers=False)


def _check_legacy_layer_instances(config, issues):
    for ltype, info in (config.get('layer_types') or {}).items():
        if not info.get('layer_indices'):
            issues.append(Issue('S7', 'error', f'layer_types/{ltype}',
                                f'layer_type {ltype} 没有 layer_indices'))


def _check_legacy_aux_duplicates(config, issues):
    aux_names = set()
    for _, aux in enumerate(config.get('runtime_auxiliary') or []):
        if isinstance(aux, dict) and aux.get('name'):
            aux_names.add(aux['name'])

    def check_no_dup_aux(node, path):
        if node.get('name') in aux_names:
            issues.append(Issue('S8', 'warning', path,
                                f'节点名 {node["name"]} 同时出现在 runtime_auxiliary'))

    for ltype, lstruct in (config.get('layer_structure') or {}).items():
        walk_tree(lstruct, f'layer_structure/{ltype}', check_no_dup_aux)


def _check_legacy_leaf_overlap(config, issues):
    op_to_paths = {}
    for op_idx, leaf_path in collect_leaf_op_indices(config):
        op_to_paths.setdefault(op_idx, []).append(leaf_path)
    for op_idx, paths in op_to_paths.items():
        if len(paths) > 1:
            issues.append(Issue('S9', 'warning', f'op_index={op_idx}',
                                f'op_index {op_idx} 在多个叶节点出现: {paths}'))


def check_structure(config):
    issues = []
    _check_legacy_schema(config, issues)
    _check_legacy_layer_keys(config, issues)
    _check_legacy_semantics(config, issues)
    _check_legacy_code_refs(config, issues)
    _check_legacy_shapes(config, issues)
    _check_legacy_indices(config, issues)
    _check_legacy_layer_instances(config, issues)
    _check_legacy_aux_duplicates(config, issues)
    _check_legacy_leaf_overlap(config, issues)
    return issues


def _check_v2_schema(config, issues):
    try:
        schema = bc.load_schema(bc.SCHEMAS_DIR / 'analysis_config_v2.schema.json')
        for err in bc.validate_json_schema(config, schema):
            issues.append(Issue('V-schema', 'error', '<schema>', err))
    except (FileNotFoundError, bc.SchemaError) as e:
        issues.append(Issue('V-schema', 'warning', '<schema>', f'schema 校验跳过: {e}'))


def _check_v2_architecture(config, issues):
    arch = config.get('architecture') or {}
    if not arch:
        issues.append(Issue('V1', 'error', 'architecture', 'schema v2 缺少 architecture 块'))
    return arch


def _check_v2_instances(config, issues):
    seen = {}
    for inst in config.get('trace_instances', []) or []:
        key = (inst.get('model_layer_index'), inst.get('invocation_index'))
        if key in seen:
            issues.append(Issue('V2', 'error', f'trace_instances/{inst.get("instance_id")}',
                                f'重复的 (model_layer_index, invocation_index)={key}'))
        seen[key] = inst.get('instance_id')
        # each instance must carry an op mapping
        if not inst.get('op_indices') and not inst.get('op_range'):
            issues.append(Issue('V2', 'error', f'trace_instances/{inst.get("instance_id")}',
                                'trace instance 缺少 op_indices/op_range'))

    # V3: instance_id uniqueness
    ids = [i.get('instance_id') for i in config.get('trace_instances', []) or []]
    dup_ids = {x for x in ids if ids.count(x) > 1}
    for d in dup_ids:
        issues.append(Issue('V3', 'error', f'trace_instances/{d}', f'instance_id 重复: {d}'))


def _check_v2_source_refs(architecture, base_dirs, issues):
    for ref in architecture.get('source_of_truth', []) or []:
        ok, reason = bc.validate_source_ref(ref, base_dirs)
        if not ok:
            issues.append(Issue('V4', 'error', 'architecture.source_of_truth', reason))


def _check_v2_nodes(config, issues):
    def check_node(node, path):
        if not node.get('semantic') and node.get('name'):
            issues.append(Issue('V5', 'warning', path, f'节点 {node.get("name")} 缺少 semantic'))
        for child in node.get('children', []) or []:
            check_node(child, f'{path}/{child.get("name", "?")}')

    for name, sect in (config.get('structures') or {}).items():
        check_node(sect, f'structures/{name}')
    for name, sect in (config.get('stages') or {}).items():
        check_node(sect, f'stages/{name}')
    for i, aux in enumerate(config.get('runtime_auxiliary') or []):
        check_node(aux, f'runtime_auxiliary[{i}]')


def _check_v2_legacy_fields(config, issues):
    for legacy in ('layer_types', 'layer_structure'):
        if legacy in config:
            issues.append(Issue('V6', 'error', legacy,
                                f'schema v2 不允许遗留字段 {legacy!r}（layer_indices 语义歧义）。'
                                f'请改用 architecture.layer_groups + trace_instances'))


def check_structure_v2(config, base_dirs):
    """Schema-v2 structure well-formedness (V1..V9)."""
    issues = []
    _check_v2_schema(config, issues)
    architecture = _check_v2_architecture(config, issues)
    _check_v2_instances(config, issues)
    _check_v2_source_refs(architecture, base_dirs, issues)
    _check_v2_nodes(config, issues)
    _check_v2_legacy_fields(config, issues)
    if 'trace_scope' not in config:
        issues.append(Issue('V7', 'error', 'trace_scope', 'schema v2 缺少 trace_scope'))
    return issues


def schema_doc():
    return {
        'script': 'check_structure.py',
        'rules': {
            'S1': '树节点 schema 完整：name 必有；叶节点必有 op_indices；中间节点必有 children',
            'S2': 'layer_types 与 layer_structure 中存在的 key 集合一致',
            'S3': '节点 semantic 必填（kernel 中 Cast/Reshape 除外）',
            'S4': '节点 code_ref 推荐填写（warning）',
            'S5': '11 类算子必有 shape_semantic 字段',
            'S6': 'layer_indices/stage_indices/instance_indices 无重复值',
            'S7': '每个 layer_type 至少有 1 个 layer_indices 实例',
            'S8': 'runtime_auxiliary 节点不在 layer_structure 子树中重名（warning）',
            'S9': '同 op_index 不在多个叶节点同时出现（warning）',
        }
    }


def _emit_results(args, issues, context, summary_label):
    errors = [item for item in issues if item['severity'] == 'error']
    warnings = [item for item in issues if item['severity'] == 'warning']
    if args.json:
        report = {
            'script': 'check_structure.py',
            'config': args.config,
            context[0]: context[1],
            'error_count': len(errors),
            'warning_count': len(warnings),
            'issues': issues,
        }
        bc.emit(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for severity, items in [('ERROR', errors), ('WARNING', warnings)]:
            for item in items:
                bc.emit(
                    f'[{severity}] {item["id"]} @ {item["node_path"]}: {item["message"]}')
        bc.emit(f'\n{summary_label}: errors={len(errors)}, warnings={len(warnings)}')
    return 1 if errors else 0


def main():
    parser = argparse.ArgumentParser(description='Step 3 Review: structure well-formedness')
    parser.add_argument('-c', '--config', required=True, help='analysis_config.json 路径')
    parser.add_argument('--json', action='store_true', help='以 JSON 输出（追加到 stdout）')
    parser.add_argument('--mode', default='A', choices=['A', 'B'],
                        help='Mode A 严格校验，Mode B 跳过 op_indices/kernels 必填检查')
    parser.add_argument('--source-dir', action='append', default=[],
                        help='源码根目录，用于 v2 source_ref 校验（可多次）')
    args = parser.parse_args()

    if not os.path.exists(args.config):
        bc.emit_error(f'错误: 文件不存在: {args.config}\n')
        sys.exit(1)
    with open(args.config, 'r', encoding='utf-8') as f:
        config = json.load(f)

    version = bc.detect_schema_version(config)
    base_dirs = args.source_dir or [os.getcwd()]

    if version == 2:
        issues = check_structure_v2(config, base_dirs)
        sys.exit(_emit_results(args, issues, ('schema_version', 2), '汇总(v2)'))

    issues = check_structure(config)

    if args.mode == 'B':
        # Mode B 不要求 op_indices/kernels（无 raw_ops 可绑定）
        issues = [i for i in issues if i['id'] not in ('S1', 'S5', 'S9')]

    sys.exit(_emit_results(args, issues, ('mode', args.mode), '汇总'))


if __name__ == '__main__':
    main()
