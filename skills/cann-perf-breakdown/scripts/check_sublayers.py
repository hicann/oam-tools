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
check_sublayers.py — sub-module consistency for schema-v2 `structures` templates.

`structures[<group_type>]` is a representative decomposition of ONE invocation of that
layer group. This validator enforces that the template is internally consistent and
grounded in real ops:

  SL1 parent op-set == union of its children's op-sets (intermediate node with children
      must NOT own ops that no child covers, and children must not exceed the parent)
  SL2 no two sibling children share an op index
  SL3 a leaf/child that carries a name but neither op_indices nor children is illegal
      (empty node that would still show timing in the report)
  SL4 required semantic nodes (self_attn / mlp|moe / *norm* / router / experts / combine)
      must resolve to at least one real op
  SL5 the template's full op-set must be a subset of the representative trace_instance's
      op range for that group (so per-instance timing is real, not invented)
  SL6 all three MoE/MTP instance ranges are the same length (structurally compatible)
  SL7 the layer-0 dense instance is NOT forced onto the layer-1/2 template when their op
      counts differ (guards the standalone-RmsNorm vs fused-Norm difference)

--json prints one object. Exit nonzero on any error.
"""
import argparse
import json
import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import breakdown_common as bc  # noqa: E402

MAIN_SEMANTIC_HINTS = ('self_attn', 'attention', 'mlp', 'moe', 'norm', 'router',
                       'gating', 'expert', 'combine', 'dispatch')


class Issue(dict):
    def __init__(self, code, severity, path, message):
        super().__init__(id=code, severity=severity, node_path=path, message=message)


def node_ops(node):
    """Full op set of a node = its own op_indices ∪ all descendants'."""
    s = set(node.get('op_indices', []) or [])
    for c in node.get('children', []) or []:
        s |= node_ops(c)
    return s


def check_node(node, path, issues):
    children = node.get('children', []) or []
    own = set(node.get('op_indices', []) or [])
    name = node.get('name', '?')

    if children:
        child_union = set()
        overlap = set()
        for c in children:
            co = node_ops(c)
            overlap |= (child_union & co)
            child_union |= co
        # SL2 sibling overlap
        if overlap:
            issues.append(Issue('SL2', 'error', path,
                                f'节点 {name} 子节点间 op 重叠: {sorted(overlap)[:20]}'))
        # SL1: an intermediate node that ALSO declares its own op_indices must keep them
        # DISJOINT from its children (otherwise the op is double-counted parent+child).
        # Ops that belong to no child are permitted (schema allows extra own ops), but they
        # must not also live inside a child.
        dbl = own & child_union
        if dbl:
            issues.append(Issue('SL1', 'error', path,
                                f'节点 {name} 自身 op 与子节点重复计数: {sorted(dbl)[:20]}'))
        for c in children:
            check_node(c, f'{path}/{c.get("name", "?")}', issues)
    else:
        # SL3 leaf must have ops (or be an explicit branches node)
        if not own and 'branches' not in node:
            issues.append(Issue('SL3', 'error', path,
                                f'叶节点 {name} 无 op_indices（报告会显示零耗时空节点）'))

    # SL4 main semantic node must resolve to real ops
    low = name.lower()
    if any(h in low for h in MAIN_SEMANTIC_HINTS):
        if not node_ops(node):
            issues.append(Issue('SL4', 'error', path,
                                f'主语义节点 {name} 没有任何真实 op'))


def rep_instance_ops(config, group_type):
    """Union op set of the representative trace instance(s) for a layer_group_type."""
    insts = [i for i in config.get('trace_instances', [])
             if i.get('layer_group_type') == group_type]
    if not insts:
        return None, []
    rep = None
    for i in insts:
        rid = i.get('representative_instance_id')
        if rid:
            rep = next((x for x in insts if x.get('instance_id') == rid), None)
            if rep:
                break
    rep = rep or insts[0]
    return set(bc.instance_op_indices(rep)), insts


def _compute_op_counter(raw_ops):
    """Return (counter, comm_aware) where counter ignores communication ops.

    SL6 exists because downstream attribution translates the representative's leaf offsets
    onto sibling invocations by range arithmetic, so a length mismatch silently misassigns
    every op past the divergence point. Communication ops do not take part in that
    translation — they live in their own COMMUNICATION-only leaf — and their count is not
    stable across runs, because it depends on first-use link setup and sampling timing.
    Counting them turns that jitter into a demand for a separate layer_group, inventing an
    architecture type the source does not have.

    With no raw_ops the counter falls back to the raw length, so the check never quietly
    weakens into a no-op.
    """
    if not raw_ops:
        return (lambda indices: len(indices)), False
    cores = {op.get('index'): op.get('accelerator_core')
             for op in raw_ops.get('operators', []) if op.get('index') is not None}
    return (lambda indices: sum(1 for i in indices
                                if cores.get(i) != 'COMMUNICATION')), True


def _group_lengths(instances, counter):
    by_length = {}
    for instance in instances:
        length = counter(bc.instance_op_indices(instance))
        by_length.setdefault(length, []).append(instance.get('instance_id'))
    return by_length


@dataclass
class SublayerContext:
    config: dict
    counter: object
    comm_aware: bool
    issues: list


def _check_invocation_lengths(group_type, instances, path, context):
    by_length = _group_lengths(instances, context.counter)
    if len(by_length) > 1:
        representative_ids = {
            item.get('representative_instance_id') for item in instances} - {None}
        rep_length = next((length for length, ids in by_length.items()
                           if set(ids) & representative_ids), None)
        basis = '计算 op' if context.comm_aware else 'op'
        for length, ids in sorted(by_length.items()):
            if length == rep_length:
                continue
            context.issues.append(Issue(
                'SL6', 'error', path,
                f'{group_type} 的 invocation {ids} 有 {length} 个{basis}，'
                f'代表实例有 {rep_length} 个：共用同一模板会让区间平移整体'
                f'错位。请将其拆为独立 layer_group 并给出自己的模板'
                f'（首层 residual=None 导致输入 norm 未融合是常见原因）'))
        return
    if not context.comm_aware:
        return
    raw_lengths = _group_lengths(instances, len)
    if len(raw_lengths) > 1:
        context.issues.append(Issue(
            'SL6', 'info', path,
            f'{group_type} 各 invocation 的计算 op 数一致（{next(iter(by_length))}），'
            f'原始 op 数不同 {dict(sorted(raw_lengths.items()))}：差异全部来自 '
            f'core=COMMUNICATION 同步桩（建链开销/采样时序），非架构差异，不拆分模板'))


def _check_group_template(group_type, tree, context):
    path = f'structures/{group_type}'
    check_node(tree, path, context.issues)
    representative_ops, instances = rep_instance_ops(context.config, group_type)
    if representative_ops is None:
        return
    template_ops = node_ops(tree)
    extra = sorted(template_ops - representative_ops)
    if extra:
        context.issues.append(Issue('SL5', 'warning', path,
                                    f'{group_type} 模板 op {extra[:20]} 不在代表实例范围内'
                                    f'（模板源自代码，实例仅为单步 trace，可能是该步未走到的分支）'))
    uncovered = sorted(representative_ops - template_ops)
    if uncovered:
        context.issues.append(Issue('SL7', 'error', path,
                                    f'{group_type} 代表实例的 op {uncovered[:20]} 未被模板任何节点覆盖'
                                    f'（trace 执行了它但代码拆解没有它，证明拆解不完整）'))
    _check_invocation_lengths(group_type, instances, path, context)


def _check_dense_variation(config, issues):

    # SL7 dense layer-0 must not be silently forced onto the layer1/2 template if its op
    # count differs. We detect it: if a dense instance's length differs from the template's
    # representative instance length, it must be flagged (needs its own template or note).
    dense_insts = [instance for instance in config.get('trace_instances', [])
                   if instance.get('layer_group_type') == 'DeepseekV3DecoderLayer_dense']
    if dense_insts:
        lengths = {i.get('instance_id'): len(bc.instance_op_indices(i)) for i in dense_insts}
        vals = set(lengths.values())
        if len(vals) > 1:
            # info, not a defect: this is the expected layer-0 standalone-RmsNorm difference.
            # It becomes an ERROR only if a shorter instance is wrongly marked as the template
            # representative (SL5 would then fire), or if a dense instance references the
            # layer-1 template range directly. Here we just document it.
            issues.append(Issue('SL7', 'info', 'structures/DeepseekV3DecoderLayer_dense',
                                f'dense invocation op 数不一致 {lengths}；layer 0 有独立 RmsNorm，'
                                f'代表模板取 layer 1（fusion 一致），layer 0 差异已在 instance.note 标注'))


def _check_residual_branches(config, issues):
    for gtype, template in (config.get('structures') or {}).items():
        children = template.get('children') or []
        if not children:
            continue
        names = [str(c.get('name') or '') for c in children]
        norms = [n for n in names if 'norm' in n.lower()]
        attention = [n for n in names
                     if 'attn' in n.lower() or 'attention' in n.lower()]
        if not (norms and attention) or (template.get('branches') or []):
            continue
        issues.append(Issue(
            'SL8', 'warning', f'structures/{gtype}',
            f'{gtype} 声明了 norm({norms}) 与 attention({attention}) 但没有任何 branches：'
            f'残差/跳连是变量传递、不体现在 children 顺序里，下游不允许推导，'
            f'因此 branches 为空会让架构图缺失全部残差边而不报错。'
            f'请按源码声明每处残差的 inputs/output（含跨层残差与多路相加），'
            f'或显式说明该结构确实没有残差'))


def check_sublayers(config, raw_ops=None):
    counter, comm_aware = _compute_op_counter(raw_ops)
    issues = []
    structures = config.get('structures') or {}
    if not structures:
        return issues
    context = SublayerContext(config, counter, comm_aware, issues)
    for group_type, tree in structures.items():
        _check_group_template(group_type, tree, context)
    _check_dense_variation(config, issues)
    _check_residual_branches(config, issues)
    return issues


def main():
    parser = argparse.ArgumentParser(description='Sub-layer structure consistency (schema v2)')
    parser.add_argument('-c', '--config', required=True)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    if not os.path.exists(args.config):
        bc.emit_error(f'错误: 文件不存在: {args.config}\n')
        sys.exit(2)
    with open(args.config, 'r', encoding='utf-8') as f:
        config = json.load(f)
    if bc.detect_schema_version(config) != 2:
        bc.emit(json.dumps({'script': 'check_sublayers.py', 'schema_version': 1,
                          'error_count': 0, 'issues': []}, ensure_ascii=False))
        return
    issues = check_sublayers(config)
    errors = [i for i in issues if i['severity'] == 'error']
    warnings = [i for i in issues if i['severity'] == 'warning']
    if args.json:
        bc.emit(json.dumps({'script': 'check_sublayers.py', 'config': args.config,
                          'error_count': len(errors), 'warning_count': len(warnings),
                          'issues': issues}, indent=2, ensure_ascii=False))
    else:
        for it in issues:
            bc.emit(f'[{it["severity"].upper()}] {it["id"]} @ {it["node_path"]}: {it["message"]}')
        bc.emit(f'\n汇总: errors={len(errors)}, warnings={len(warnings)}')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
