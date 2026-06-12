#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
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
# ----------------------------------------------------------------------------
"""
Step 3 Review: 校验 analysis_config.json 的结构良构性 (S1–S9)。

输出格式与 check_op_coverage.py、validate_shapes.py 统一：
  普通模式：可读文本 + 错误码退出
  --json :  追加单行 JSON 到 stdout，schema 见 schema_doc()
"""
import logging
import argparse
import json
import os
import sys

from _common import is_shape_always_required

logger = logging.getLogger(__name__)


# 始终必填 shape_semantic 的算子（与 references/structure_analysis_guide.md §B.5 单源）
# 这些算子无歧义，每个实例都必须填 shape_semantic
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


def walk_all_sections(config, visit):
    """对 stages / layer_structure / runtime_auxiliary 三段树统一遍历。"""
    for sname, sinfo in (config.get('stages') or {}).items():
        walk_tree(sinfo, f'stages/{sname}', visit)
    for ltype, lstruct in (config.get('layer_structure') or {}).items():
        walk_tree(lstruct, f'layer_structure/{ltype}', visit)
    for i, aux in enumerate(config.get('runtime_auxiliary') or []):
        walk_tree(aux, f'runtime_auxiliary[{i}]', visit)


def _check_s1_schema(config, issues):
    """S1: 树节点 schema 完整。"""
    def visit(node, path):
        if 'name' not in node:
            issues.append(Issue('S1', 'error', path, '节点缺少 name 字段'))
        is_leaf = ('children' not in node or not node['children'])
        if is_leaf and 'op_indices' not in node and 'branches' not in node:
            issues.append(Issue('S1', 'error', path, '叶节点缺少 op_indices'))
    walk_all_sections(config, visit)


def _check_s2_layer_match(config, issues):
    """S2: layer_types ↔ layer_structure 匹配。"""
    lt_keys = set((config.get('layer_types') or {}).keys())
    ls_keys = set((config.get('layer_structure') or {}).keys())
    for k in lt_keys - ls_keys:
        issues.append(Issue('S2', 'error', f'layer_types/{k}',
                            'layer_types 中存在但 layer_structure 中缺失'))
    for k in ls_keys - lt_keys:
        issues.append(Issue('S2', 'error', f'layer_structure/{k}',
                            'layer_structure 中存在但 layer_types 中缺失'))


def _check_s3_semantic(config, issues):
    """S3: semantic 必填（除 SEMANTIC_OPTIONAL kernel）。"""
    def visit(node, path):
        if not node.get('semantic'):
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
    walk_all_sections(config, visit)


def _check_s4_code_ref(config, issues):
    """S4: code_ref 必填。"""
    def visit(node, path):
        if not node.get('code_ref') and 'branches' not in node:
            issues.append(Issue('S4', 'warning', path, '节点缺少 code_ref'))
    walk_all_sections(config, visit)


def _check_s5_shape_semantic(config, issues):
    """S5: shape_semantic 字段（始终必填类 error，上下文必填类 warning）。"""
    def visit(node, path):
        for ks in node.get('kernels', []) or []:
            kn = ks.get('name', '') or ''
            kn_norm = kn.split('/')[-1] if '/' in kn else kn
            if is_shape_always_required(kn_norm) or is_shape_contextual(kn_norm):
                if not ks.get('shape_semantic'):
                    sev = 'error' if is_shape_always_required(kn_norm) else 'warning'
                    issues.append(Issue('S5', sev,
                                        f'{path}/kernels[index={ks.get("index")}]',
                                        f'{kn_norm} 已登记 kernels[] 但缺 shape_semantic'))
    walk_all_sections(config, visit)


def _check_s6_indices_unique(config, issues):
    """S6: layer_indices / stage_indices / instance_indices 列表无重复值。"""
    for ltype, info in (config.get('layer_types') or {}).items():
        idx = info.get('layer_indices', [])
        if len(idx) != len(set(idx)):
            issues.append(Issue('S6', 'error', f'layer_types/{ltype}', 'layer_indices 含重复值'))

    def visit(node, path):
        for fld in ('stage_indices', 'instance_indices'):
            v = node.get(fld)
            if v and len(v) != len(set(v)):
                issues.append(Issue('S6', 'error', path, f'{fld} 含重复值'))
    for sname, sinfo in (config.get('stages') or {}).items():
        walk_tree(sinfo, f'stages/{sname}', visit)
    for i, aux in enumerate(config.get('runtime_auxiliary') or []):
        walk_tree(aux, f'runtime_auxiliary[{i}]', visit)


def _check_s7_instances(config, issues):
    """S7: 每个 layer_type 至少 1 个实例。"""
    for ltype, info in (config.get('layer_types') or {}).items():
        if not info.get('layer_indices'):
            issues.append(Issue('S7', 'error', f'layer_types/{ltype}',
                                f'layer_type {ltype} 没有 layer_indices'))


def _check_s8_no_dup_aux(config, issues):
    """S8: runtime_auxiliary 节点不应出现在 layer_structure 子树中。"""
    aux_names = set()
    for aux in config.get('runtime_auxiliary') or []:
        if isinstance(aux, dict) and aux.get('name'):
            aux_names.add(aux['name'])

    def visit(node, path):
        if node.get('name') in aux_names:
            issues.append(Issue('S8', 'warning', path,
                                f'节点名 {node["name"]} 同时出现在 runtime_auxiliary'))
    for ltype, lstruct in (config.get('layer_structure') or {}).items():
        walk_tree(lstruct, f'layer_structure/{ltype}', visit)


def _check_s9_op_overlap(config, issues):
    """S9: 同 op_index 不在多个叶节点同时出现。"""
    op_to_paths = {}
    for op_idx, leaf_path in collect_leaf_op_indices(config):
        op_to_paths.setdefault(op_idx, []).append(leaf_path)
    for op_idx, paths in op_to_paths.items():
        if len(paths) > 1:
            issues.append(Issue('S9', 'warning', f'op_index={op_idx}',
                                f'op_index {op_idx} 在多个叶节点出现: {paths}'))


def check_structure(config):
    issues = []
    _check_s1_schema(config, issues)
    _check_s2_layer_match(config, issues)
    _check_s3_semantic(config, issues)
    _check_s4_code_ref(config, issues)
    _check_s5_shape_semantic(config, issues)
    _check_s6_indices_unique(config, issues)
    _check_s7_instances(config, issues)
    _check_s8_no_dup_aux(config, issues)
    _check_s9_op_overlap(config, issues)
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
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    parser = argparse.ArgumentParser(description='Step 3 Review: structure well-formedness')
    parser.add_argument('-c', '--config', required=True, help='analysis_config.json 路径')
    parser.add_argument('--json', action='store_true', help='以 JSON 输出（追加到 stdout）')
    parser.add_argument('--mode', default='A', choices=['A', 'B'],
                        help='Mode A 严格校验，Mode B 跳过 op_indices/kernels 必填检查')
    args = parser.parse_args()

    if not os.path.exists(args.config):
        logger.error('错误: 文件不存在: %s', args.config)
        sys.exit(1)
    with open(args.config, 'r', encoding='utf-8') as f:
        config = json.load(f)

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
        logger.info(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        for sev_label, items in [('ERROR', errors), ('WARNING', warnings)]:
            for it in items:
                logger.info('[%s] %s @ %s: %s', sev_label, it["id"], it["node_path"], it["message"])
        logger.info('\n汇总: errors=%d, warnings=%d', len(errors), len(warnings))

    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
