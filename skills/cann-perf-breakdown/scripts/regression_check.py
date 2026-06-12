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
Step 3 / P8: 与 baseline 做结构等价性回归 (L1–L8)。

L1: top-level keys 集合相等
L2: layer_types 集合 + layer_indices 列表相等
L3: stages keys 与 stage_indices 集合相等
L4: runtime_auxiliary 名字集合相等
L5: 每个 layer_type 的叶节点路径集合 Jaccard ≥ 0.95
L6: 每个叶节点的 op_indices 集合 Jaccard ≥ 0.90
L7: op 总覆盖（union of op_indices）相等
L8: 11 类算子的 shape_semantic 字段存在性 100%
"""
import logging
import argparse
import json
import os
import sys

from _common import is_shape_always_required as is_shape_required

logger = logging.getLogger(__name__)


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / max(len(a | b), 1)


def collect_leaves(layer_struct):
    """返回 {leaf_path: set(op_indices)}"""
    out = {}

    def walk(node, path):
        if not isinstance(node, dict):
            return
        if 'op_indices' in node and node.get('op_indices') is not None:
            out[path] = set(node['op_indices'])
        for child in node.get('children', []) or []:
            cname = child.get('name', '?')
            walk(child, f'{path}/{cname}')

    walk(layer_struct, layer_struct.get('name', 'root'))
    return out


def collect_all_op_indices(config):
    out = set()

    def walk(node):
        if not isinstance(node, dict):
            return
        for idx in node.get('op_indices', []) or []:
            out.add(idx)
        for child in node.get('children', []) or []:
            walk(child)

    for s in (config.get('stages') or {}).values():
        walk(s)
    for ls in (config.get('layer_structure') or {}).values():
        walk(ls)
    for aux in (config.get('runtime_auxiliary') or []):
        walk(aux)
    return out


def collect_kernels_with_shape(config):
    """返回 {(path, op_index): (kernel_name, has_shape_semantic)}"""
    out = {}

    def walk(node, path):
        if not isinstance(node, dict):
            return
        for ks in node.get('kernels', []) or []:
            kn = ks.get('name', '') or ''
            kn = kn.split('/')[-1] if '/' in kn else kn
            idx = ks.get('index')
            if idx is not None:
                out[(path, idx)] = (kn, bool(ks.get('shape_semantic')))
        for child in node.get('children', []) or []:
            walk(child, f'{path}/{child.get("name", "?")}')

    for sname, s in (config.get('stages') or {}).items():
        walk(s, f'stages/{sname}')
    for ltype, ls in (config.get('layer_structure') or {}).items():
        walk(ls, f'layer_structure/{ltype}')
    for i, aux in enumerate(config.get('runtime_auxiliary') or []):
        walk(aux, f'runtime_auxiliary[{i}]')
    return out


def _reg_l1(baseline, new):
    bl_keys, new_keys = set(baseline.keys()), set(new.keys())
    if bl_keys == new_keys:
        return {'id': 'L1', 'pass': True, 'detail': f'top-level keys match: {sorted(bl_keys)}'}
    return {'id': 'L1', 'pass': False,
            'detail': f'baseline only: {sorted(bl_keys - new_keys)}, '
                      f'new only: {sorted(new_keys - bl_keys)}'}


def _reg_l2(bl_lt, new_lt, bl_set, new_set):
    l2_pass = (bl_set == new_set) and all(
        sorted(bl_lt[k].get('layer_indices', [])) == sorted(new_lt[k].get('layer_indices', []))
        for k in bl_set)
    return {'id': 'L2', 'pass': l2_pass,
            'detail': f'baseline layer_types={sorted(bl_set)}, new={sorted(new_set)}'}


def _reg_l3(baseline, new):
    bl_st = set((baseline.get('stages') or {}).keys())
    new_st = set((new.get('stages') or {}).keys())
    return {'id': 'L3', 'pass': bl_st == new_st,
            'detail': f'stages baseline={sorted(bl_st)}, new={sorted(new_st)}'}


def _reg_l4(baseline, new):
    def names(aux_list):
        return {a.get('name') for a in (aux_list or []) if isinstance(a, dict) and a.get('name')}
    bl_aux = names(baseline.get('runtime_auxiliary'))
    new_aux = names(new.get('runtime_auxiliary'))
    return {'id': 'L4', 'pass': bl_aux == new_aux,
            'detail': f'baseline aux={sorted(bl_aux)}, new={sorted(new_aux)}'}


def _reg_l5(baseline, new, common_types, l5_threshold):
    l5_results = []
    for k in common_types:
        bl_paths = set(collect_leaves(baseline['layer_structure'].get(k, {})).keys())
        new_paths = set(collect_leaves(new['layer_structure'].get(k, {})).keys())
        l5_results.append({
            'layer_type': k,
            'jaccard': round(jaccard(bl_paths, new_paths), 3),
            'baseline_only': sorted(list(bl_paths - new_paths))[:10],
            'new_only': sorted(list(new_paths - bl_paths))[:10],
        })
    l5_pass = all(r['jaccard'] >= l5_threshold for r in l5_results) if l5_results else True
    return {'id': 'L5', 'pass': l5_pass, 'threshold': l5_threshold, 'detail': l5_results}


def _reg_l6(baseline, new, common_types, l6_threshold):
    l6_results = []
    for k in common_types:
        bl_leaves = collect_leaves(baseline['layer_structure'].get(k, {}))
        new_leaves = collect_leaves(new['layer_structure'].get(k, {}))
        for path in set(bl_leaves) & set(new_leaves):
            j = jaccard(bl_leaves[path], new_leaves[path])
            if j < l6_threshold:
                l6_results.append({
                    'layer_type': k, 'leaf': path, 'jaccard': round(j, 3),
                    'baseline_only': sorted(list(bl_leaves[path] - new_leaves[path]))[:5],
                    'new_only': sorted(list(new_leaves[path] - bl_leaves[path]))[:5],
                })
    return {'id': 'L6', 'pass': not l6_results, 'threshold': l6_threshold,
            'mismatches': l6_results[:30], 'mismatch_count': len(l6_results)}


def _reg_l7(baseline, new):
    bl_ops = collect_all_op_indices(baseline)
    new_ops = collect_all_op_indices(new)
    return {'id': 'L7', 'pass': bl_ops == new_ops,
            'detail': {
                'baseline_count': len(bl_ops), 'new_count': len(new_ops),
                'missing_in_new': sorted(list(bl_ops - new_ops))[:20],
                'extra_in_new': sorted(list(new_ops - bl_ops))[:20],
            }}


def _reg_l8(new):
    new_kernels = collect_kernels_with_shape(new)
    missing = [(p, idx, kn) for (p, idx), (kn, ok) in new_kernels.items()
               if is_shape_required(kn) and not ok]
    return {'id': 'L8', 'pass': not missing,
            'missing_count': len(missing), 'missing_examples': missing[:10]}


def check_regression(baseline, new, l5_threshold=0.95, l6_threshold=0.90):
    bl_lt = baseline.get('layer_types') or {}
    new_lt = new.get('layer_types') or {}
    bl_set, new_set = set(bl_lt.keys()), set(new_lt.keys())
    common_types = bl_set & new_set
    return [
        _reg_l1(baseline, new),
        _reg_l2(bl_lt, new_lt, bl_set, new_set),
        _reg_l3(baseline, new),
        _reg_l4(baseline, new),
        _reg_l5(baseline, new, common_types, l5_threshold),
        _reg_l6(baseline, new, common_types, l6_threshold),
        _reg_l7(baseline, new),
        _reg_l8(new),
    ]


def _emit_findings(args, findings, hard_fails, soft_fails):
    """按 --json / 文本模式输出 findings。"""
    if args.json:
        logger.info(json.dumps({
            'script': 'regression_check.py',
            'baseline': args.baseline,
            'new': args.new,
            'mode': args.mode,
            'hard_fails': len(hard_fails),
            'soft_fails': len(soft_fails),
            'findings': findings,
        }, indent=2, ensure_ascii=False))
        return
    for f in findings:
        mark = '✓' if f['pass'] else '✗'
        logger.info('[%s] %s', mark, f["id"])
        if not f['pass']:
            logger.info('    detail: %s', json.dumps(f.get("detail", f), ensure_ascii=False)[:500])
    logger.info('\n汇总: hard_fails=%d, soft_fails=%d', len(hard_fails), len(soft_fails))


def _write_regression_report(report_path, args, findings):
    """写 Markdown 回归报告。"""
    lines = [f'# Regression Check: {os.path.basename(args.new)} vs baseline\n',
             f'- Baseline: `{args.baseline}`',
             f'- New:      `{args.new}`',
             f'- Mode:     {args.mode}\n',
             '| 项 | 通过 | 详情 |',
             '|---|---|---|']
    for f in findings:
        mark = '✓' if f['pass'] else '✗'
        detail = json.dumps(f.get('detail', f), ensure_ascii=False)[:200]
        lines.append(f'| {f["id"]} | {mark} | `{detail}` |')
    with open(report_path, 'w', encoding='utf-8') as fp:
        fp.write('\n'.join(lines) + '\n')
    logger.info('\nReport 已保存到: %s', report_path)


def main():
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    parser = argparse.ArgumentParser(description='Regression check L1–L8 vs baseline')
    parser.add_argument('--baseline', required=True, help='baseline analysis_config.json')
    parser.add_argument('--new', required=True, help='new analysis_config.json')
    parser.add_argument('--mode', default='A', choices=['A', 'B'],
                        help='Mode B 跳过 L6/L7/L8（无 op_indices/kernels）')
    parser.add_argument('--report', help='输出 Markdown 报告路径')
    parser.add_argument('--json', action='store_true', help='以 JSON 输出 stdout')
    parser.add_argument('--l5', type=float, default=0.95, help='L5 Jaccard 阈值')
    parser.add_argument('--l6', type=float, default=0.90, help='L6 Jaccard 阈值')
    args = parser.parse_args()

    for p in (args.baseline, args.new):
        if not os.path.exists(p):
            logger.error('错误: 文件不存在: %s', p)
            sys.exit(1)

    with open(args.baseline, 'r', encoding='utf-8') as f:
        baseline = json.load(f)
    with open(args.new, 'r', encoding='utf-8') as f:
        new = json.load(f)

    findings = check_regression(baseline, new, args.l5, args.l6)
    if args.mode == 'B':
        findings = [f for f in findings if f['id'] not in ('L6', 'L7', 'L8')]

    hard_fails = [f for f in findings if not f['pass'] and f['id'] in ('L1', 'L2', 'L3', 'L4', 'L7')]
    soft_fails = [f for f in findings if not f['pass'] and f['id'] in ('L5', 'L6', 'L8')]

    _emit_findings(args, findings, hard_fails, soft_fails)
    if args.report:
        _write_regression_report(args.report, args, findings)

    sys.exit(1 if hard_fails else 0)


if __name__ == '__main__':
    main()
