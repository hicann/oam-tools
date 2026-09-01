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

# 始终必填 shape_semantic 的算子（与 references/structure_analysis_guide.md §B.5 单源）
# 这些算子无歧义，每个实例都必须填 shape_semantic
SHAPE_SEMANTIC_ALWAYS_REQUIRED = {
    'MatMul', 'MatMulV2', 'QuantBatchMatmulV3', 'GroupedMatmul', 'GemmEx', 'BatchMatMul',
    'FlashAttentionScore', 'FusedInferAttentionScore', 'KvQuantSparseFlashAttention',
    'HcomAllGather', 'HcomReduceScatter', 'HcomAllToAll', 'hcom_allReduce', 'HcomAllReduce',
    'RmsNorm', 'LayerNormV3', 'InplaceAddRmsNorm', 'AddRmsNormDynamicQuant',
    'MlaPrologV3', 'DequantSwigluQuant', 'LightningIndexerQuant', 'MoeGatingTopKHash',
    'RotaryMul',
    'GatherV2', 'GatherV3',
    'MoeDistributeDispatchV2', 'MoeDistributeCombineV2',
    # AddRmsNormX 系列 (前缀匹配)
}

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


def is_shape_always_required(name: str) -> bool:
    if name in SHAPE_SEMANTIC_ALWAYS_REQUIRED:
        return True
    if name.startswith('AddRmsNorm'):
        return True
    return False


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


def check_structure(config):
    issues = []

    # S1: 树节点 schema 完整
    def check_node_schema(node, path):
        if 'name' not in node:
            issues.append(Issue('S1', 'error', path, '节点缺少 name 字段'))
        is_leaf = ('children' not in node or not node['children'])
        has_indices = 'op_indices' in node
        has_branches = 'branches' in node  # Mode B
        if is_leaf and not has_indices and not has_branches:
            issues.append(Issue('S1', 'error', path, '叶节点缺少 op_indices'))

    for sname, sinfo in (config.get('stages') or {}).items():
        walk_tree(sinfo, f'stages/{sname}', check_node_schema)
    for ltype, lstruct in (config.get('layer_structure') or {}).items():
        walk_tree(lstruct, f'layer_structure/{ltype}', check_node_schema)
    for i, aux in enumerate(config.get('runtime_auxiliary') or []):
        walk_tree(aux, f'runtime_auxiliary[{i}]', check_node_schema)

    # S2: layer_types ↔ layer_structure 匹配
    lt_keys = set((config.get('layer_types') or {}).keys())
    ls_keys = set((config.get('layer_structure') or {}).keys())
    for k in lt_keys - ls_keys:
        issues.append(Issue('S2', 'error', f'layer_types/{k}',
                            'layer_types 中存在但 layer_structure 中缺失'))
    for k in ls_keys - lt_keys:
        issues.append(Issue('S2', 'error', f'layer_structure/{k}',
                            'layer_structure 中存在但 layer_types 中缺失'))

    # S3: semantic 必填（除 Cast/Reshape kernel）
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

    for sname, sinfo in (config.get('stages') or {}).items():
        walk_tree(sinfo, f'stages/{sname}', check_semantic)
    for ltype, lstruct in (config.get('layer_structure') or {}).items():
        walk_tree(lstruct, f'layer_structure/{ltype}', check_semantic)
    for i, aux in enumerate(config.get('runtime_auxiliary') or []):
        walk_tree(aux, f'runtime_auxiliary[{i}]', check_semantic)

    # S4: code_ref 必填
    def check_code_ref(node, path):
        if not node.get('code_ref') and 'branches' not in node:
            issues.append(Issue('S4', 'warning', path, '节点缺少 code_ref'))

    for sname, sinfo in (config.get('stages') or {}).items():
        walk_tree(sinfo, f'stages/{sname}', check_code_ref)
    for ltype, lstruct in (config.get('layer_structure') or {}).items():
        walk_tree(lstruct, f'layer_structure/{ltype}', check_code_ref)
    for i, aux in enumerate(config.get('runtime_auxiliary') or []):
        walk_tree(aux, f'runtime_auxiliary[{i}]', check_code_ref)

    # S5: shape_semantic 字段
    # - 始终必填类：每次 kernels[] 登记都需 shape_semantic
    # - 上下文必填类：仅当 AI 已登记到 kernels[]，才检查 shape_semantic 字段存在
    def check_shape_semantic(node, path):
        for ks in node.get('kernels', []) or []:
            kn = ks.get('name', '') or ''
            kn_norm = kn.split('/')[-1] if '/' in kn else kn
            if is_shape_always_required(kn_norm) or is_shape_contextual(kn_norm):
                if not ks.get('shape_semantic'):
                    sev = 'error' if is_shape_always_required(kn_norm) else 'warning'
                    issues.append(Issue('S5', sev,
                                        f'{path}/kernels[index={ks.get("index")}]',
                                        f'{kn_norm} 已登记 kernels[] 但缺 shape_semantic'))

    for sname, sinfo in (config.get('stages') or {}).items():
        walk_tree(sinfo, f'stages/{sname}', check_shape_semantic)
    for ltype, lstruct in (config.get('layer_structure') or {}).items():
        walk_tree(lstruct, f'layer_structure/{ltype}', check_shape_semantic)
    for i, aux in enumerate(config.get('runtime_auxiliary') or []):
        walk_tree(aux, f'runtime_auxiliary[{i}]', check_shape_semantic)

    # S6: layer_indices / stage_indices / instance_indices 列表无重复值
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

    for sname, sinfo in (config.get('stages') or {}).items():
        walk_tree(sinfo, f'stages/{sname}', check_indices_unique)
    for i, aux in enumerate(config.get('runtime_auxiliary') or []):
        walk_tree(aux, f'runtime_auxiliary[{i}]', check_indices_unique)

    # S7: 每个 layer_type 至少 1 个实例
    for ltype, info in (config.get('layer_types') or {}).items():
        if not info.get('layer_indices'):
            issues.append(Issue('S7', 'error', f'layer_types/{ltype}',
                                f'layer_type {ltype} 没有 layer_indices'))

    # S8: runtime_auxiliary 节点不应出现在 layer_structure 子树中（按名字 + op_indices 重叠粗判）
    aux_names = set()
    for i, aux in enumerate(config.get('runtime_auxiliary') or []):
        if isinstance(aux, dict) and aux.get('name'):
            aux_names.add(aux['name'])

    def check_no_dup_aux(node, path):
        if node.get('name') in aux_names:
            issues.append(Issue('S8', 'warning', path,
                                f'节点名 {node["name"]} 同时出现在 runtime_auxiliary'))

    for ltype, lstruct in (config.get('layer_structure') or {}).items():
        walk_tree(lstruct, f'layer_structure/{ltype}', check_no_dup_aux)

    # S9: 同 op_index 不在多个叶节点同时出现（warning）
    op_to_paths = {}
    for op_idx, leaf_path in collect_leaf_op_indices(config):
        op_to_paths.setdefault(op_idx, []).append(leaf_path)
    for op_idx, paths in op_to_paths.items():
        if len(paths) > 1:
            issues.append(Issue('S9', 'warning', f'op_index={op_idx}',
                                f'op_index {op_idx} 在多个叶节点出现: {paths}'))

    return issues


def check_structure_v2(config, base_dirs):
    """Schema-v2 structure well-formedness (V1..V9)."""
    issues = []

    # V-schema: JSON Schema conformance
    try:
        schema = bc.load_schema(bc.SCHEMAS_DIR / 'analysis_config_v2.schema.json')
        for err in bc.validate_json_schema(config, schema):
            issues.append(Issue('V-schema', 'error', '<schema>', err))
    except (FileNotFoundError, bc.SchemaError) as e:
        issues.append(Issue('V-schema', 'warning', '<schema>', f'schema 校验跳过: {e}'))

    arch = config.get('architecture') or {}

    # V1: architecture present
    if not arch:
        issues.append(Issue('V1', 'error', 'architecture', 'schema v2 缺少 architecture 块'))

    # V2: trace_instances identity — no reused (model_layer_index, invocation_index)
    seen = {}
    for index, inst in enumerate(config.get('trace_instances', []) or []):
        key = (inst.get('model_layer_index'), inst.get('invocation_index'))
        # Unknown is an evidence placeholder, not a learned-layer identity. Treating it as
        # a concrete key would force the mapper to invent layer numbers without checkpoint
        # evidence merely to satisfy this uniqueness check.
        if key[0] not in (None, 'unknown'):
            if key in seen:
                issue = Issue('V2', 'error', f'trace_instances/{inst.get("instance_id")}',
                              f'重复的 (model_layer_index, invocation_index)={key}')
                issue['config_paths'] = [f'$.trace_instances[{index}]']
                issue['trace_evidence'] = list(bc.instance_op_indices(inst))
                issue['repair_policy'] = {
                    'owner_artifact': 'analysis_config',
                    'repair_class': 'trace_instance_identity',
                    'allowed_targets': {
                        'analysis_config': [f'$.trace_instances[{index}]'],
                    },
                    'required_evidence': ['candidate_nodes', 'raw_ops_slice'],
                }
                issues.append(issue)
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

    # V4: source_ref validity for architecture.source_of_truth
    for ref in arch.get('source_of_truth', []) or []:
        ok, reason = bc.validate_source_ref(ref, base_dirs)
        if not ok:
            issues.append(Issue('V4', 'error', 'architecture.source_of_truth', reason))

    # V5: node semantic/code_ref in structures/stages/runtime_auxiliary
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

    # V6: reject legacy v1-only fields to avoid ambiguous layer_indices reuse
    for legacy in ('layer_types', 'layer_structure'):
        if legacy in config:
            issues.append(Issue('V6', 'error', legacy,
                                f'schema v2 不允许遗留字段 {legacy!r}（layer_indices 语义歧义）。'
                                f'请改用 architecture.layer_groups + trace_instances'))

    # V7: trace_scope present
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
        sys.stderr.write(f'错误: 文件不存在: {args.config}\n')
        sys.exit(1)
    with open(args.config, 'r', encoding='utf-8') as f:
        config = json.load(f)

    version = bc.detect_schema_version(config)
    base_dirs = args.source_dir or [os.getcwd()]

    if version == 2:
        issues = check_structure_v2(config, base_dirs)
        errors = [i for i in issues if i['severity'] == 'error']
        warnings = [i for i in issues if i['severity'] == 'warning']
        if args.json:
            print(json.dumps({
                'script': 'check_structure.py',
                'config': args.config,
                'schema_version': 2,
                'error_count': len(errors),
                'warning_count': len(warnings),
                'issues': issues,
            }, indent=2, ensure_ascii=False))
        else:
            for sev_label, items in [('ERROR', errors), ('WARNING', warnings)]:
                for it in items:
                    print(f'[{sev_label}] {it["id"]} @ {it["node_path"]}: {it["message"]}')
            print(f'\n汇总(v2): errors={len(errors)}, warnings={len(warnings)}')
        sys.exit(1 if errors else 0)

    issues = check_structure(config)

    if args.mode == 'B':
        # Mode B 不要求 op_indices/kernels（无 raw_ops 可绑定）
        issues = [i for i in issues if i['id'] not in ('S1', 'S5', 'S9')]

    errors = [i for i in issues if i['severity'] == 'error']
    warnings = [i for i in issues if i['severity'] == 'warning']

    if args.json:
        out = {
            'script': 'check_structure.py',
            'config': args.config,
            'mode': args.mode,
            'error_count': len(errors),
            'warning_count': len(warnings),
            'issues': issues,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        for sev_label, items in [('ERROR', errors), ('WARNING', warnings)]:
            for it in items:
                print(f'[{sev_label}] {it["id"]} @ {it["node_path"]}: {it["message"]}')
        print(f'\n汇总: errors={len(errors)}, warnings={len(warnings)}')

    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
