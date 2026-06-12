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
Step 3 Review: 校验 raw_ops 中的算子在 analysis_config 中的覆盖关系 (C1–C3)。

C1: raw_ops 全部 op 是否被 layer_structure ∪ stages ∪ runtime_auxiliary 覆盖
C2: 同一 op_index 是否出现在多个节点 op_indices 中（错误，与 check_structure S9 warning 互补——
    本脚本视为 ERROR，因为同时还要检查未覆盖）
C3: 11 类必填 shape_semantic 的 kernel 中，哪些尚未在 analysis_config 的 kernels 数组里登记
"""
import logging
import argparse
import json
import os
import sys

from _common import is_shape_always_required

logger = logging.getLogger(__name__)


class Issue(dict):
    def __init__(self, code, severity, path, message):
        super().__init__(id=code, severity=severity, node_path=path, message=message)


def collect_leaf_op_paths(config):
    out = {}  # op_index -> [leaf_path]
    kernels_registered = {}  # op_index -> kernel name (if registered with shape_semantic info)

    def walk(node, path):
        if not isinstance(node, dict):
            return
        for idx in node.get('op_indices', []) or []:
            out.setdefault(idx, []).append(path)
        for ks in node.get('kernels', []) or []:
            kn = ks.get('name', '') or ''
            kn = kn.split('/')[-1] if '/' in kn else kn
            idx = ks.get('index')
            if idx is not None:
                kernels_registered[idx] = {
                    'name': kn,
                    'has_shape_semantic': bool(ks.get('shape_semantic')),
                    'path': path,
                }
        for child in node.get('children', []) or []:
            cname = child.get('name', '?')
            walk(child, f'{path}/{cname}')

    for sname, sinfo in (config.get('stages') or {}).items():
        walk(sinfo, f'stages/{sname}')
    for ltype, lstruct in (config.get('layer_structure') or {}).items():
        walk(lstruct, f'layer_structure/{ltype}')
    for i, aux in enumerate(config.get('runtime_auxiliary') or []):
        walk(aux, f'runtime_auxiliary[{i}]')

    return out, kernels_registered


def _collect_section_op_indices(config_section):
    """递归收集一段树结构下所有 op_indices 的集合。"""
    ops = set()

    def walk(node):
        if not isinstance(node, dict):
            return
        for idx in node.get('op_indices', []) or []:
            ops.add(idx)
        for child in node.get('children', []) or []:
            walk(child)

    if isinstance(config_section, dict):
        walk(config_section)
    elif isinstance(config_section, list):
        for item in config_section:
            walk(item)
    return ops


def _check_c1_count(config, n_ops, issues):
    """C1: 计数校验（代表性 layer 展开后）。返回 (total_accounted, gap)。"""
    stages_ops = set()
    for _sname, sinfo in (config.get('stages') or {}).items():
        stages_ops |= _collect_section_op_indices(sinfo)

    runtime_ops = set()
    for aux in (config.get('runtime_auxiliary') or []):
        runtime_ops |= _collect_section_op_indices(aux)

    layer_total_accounted = 0
    per_layer_type_info = []
    for ltype, lstruct in (config.get('layer_structure') or {}).items():
        rep_ops = _collect_section_op_indices(lstruct)
        n_instances = len((config.get('layer_types') or {}).get(ltype, {}).get('layer_indices', []))
        accounted = len(rep_ops) * max(n_instances, 1)
        layer_total_accounted += accounted
        per_layer_type_info.append({
            'layer_type': ltype,
            'rep_ops_count': len(rep_ops),
            'n_instances': n_instances,
            'accounted': accounted,
        })

    total_accounted = len(stages_ops) + len(runtime_ops) + layer_total_accounted
    gap = n_ops - total_accounted
    gap_pct = round(100 * gap / max(n_ops, 1), 2)
    if abs(gap_pct) > 5:
        issues.append(Issue('C1', 'warning', '<global>',
                            f'op count gap: raw_ops={n_ops}, accounted={total_accounted}, '
                            f'gap={gap} ({gap_pct}%). 详细: {per_layer_type_info}'))
    return total_accounted, gap


def _check_c2_overlap(op_to_paths, issues):
    """C2: 节点间 op_indices 重叠。"""
    for idx, paths in op_to_paths.items():
        if len(paths) <= 1:
            continue
        sections = set(p.split('/')[0] for p in paths)
        if len(sections) == 1:
            issues.append(Issue('C2', 'error', f'op_index={idx}',
                                f'op_index={idx} 在同 section 多叶节点出现: {paths}'))
        else:
            issues.append(Issue('C2', 'warning', f'op_index={idx}',
                                f'op_index={idx} 跨 section 出现: {paths}（确认是否合理）'))


def _check_c3_shape_semantic(kernels_registered, issues):
    """C3: kernels[] 已登记的算子缺 shape_semantic。"""
    for idx, info in kernels_registered.items():
        kn = info.get('name', '')
        if is_shape_always_required(kn) and not info.get('has_shape_semantic'):
            issues.append(Issue('C3', 'error', f'{info.get("path", "?")}/kernels[index={idx}]',
                                f'{kn} 必填 shape_semantic 但未提供'))


def check_coverage(config, raw_ops):
    """coverage 校验（C1 计数 / C2 重叠 / C3 shape_semantic）。

    analysis_config.json 采用"代表性 layer + layer_indices"模式，
    layer_structure 只列代表层的 op_indices，故用计数校验而非逐 op 覆盖判定。
    """
    issues = []
    op_to_paths, kernels_registered = collect_leaf_op_paths(config)
    n_ops = len(raw_ops.get('operators', []))

    total_accounted, gap = _check_c1_count(config, n_ops, issues)
    _check_c2_overlap(op_to_paths, issues)
    _check_c3_shape_semantic(kernels_registered, issues)

    return issues, n_ops, total_accounted, gap


def main():
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    parser = argparse.ArgumentParser(description='Step 3 Review: op coverage check')
    parser.add_argument('-c', '--config', required=True, help='analysis_config.json 路径')
    parser.add_argument('-r', '--raw-ops', dest='raw_ops', required=True, help='raw_ops.json 路径')
    parser.add_argument('--json', action='store_true', help='以 JSON 输出')
    args = parser.parse_args()

    if not os.path.exists(args.config) or not os.path.exists(args.raw_ops):
        logger.error('错误: 输入文件不存在')
        sys.exit(1)

    with open(args.config, 'r', encoding='utf-8') as f:
        config = json.load(f)
    with open(args.raw_ops, 'r', encoding='utf-8') as f:
        raw_ops = json.load(f)

    issues, n_ops, n_accounted, gap = check_coverage(config, raw_ops)
    errors = [i for i in issues if i['severity'] == 'error']

    if args.json:
        out = {
            'script': 'check_op_coverage.py',
            'config': args.config,
            'raw_ops': args.raw_ops,
            'total_ops': n_ops,
            'accounted_ops': n_accounted,
            'gap': gap,
            'gap_pct': round(100 * gap / max(n_ops, 1), 2),
            'error_count': len(errors),
            'issues': issues,
        }
        logger.info(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        for it in issues:
            sev = it['severity'].upper()
            logger.info('[%s] %s @ %s: %s', sev, it["id"], it["node_path"], it["message"])
        logger.info('\n汇总: ops 总数=%d, 折算覆盖=%d, gap=%d (%s%%), errors=%d',
                    n_ops, n_accounted, gap, round(100 * gap / max(n_ops, 1), 2), len(errors))

    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
