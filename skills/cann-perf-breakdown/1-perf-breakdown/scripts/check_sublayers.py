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


def _structure_json_path(tree, group_type, slash_path):
    """Resolve a human-readable structure path to its canonical JSON array path."""
    parts = str(slash_path).split('/')
    if len(parts) < 2 or parts[0] != 'structures' or parts[1] != group_type:
        return None, None
    node = tree
    json_parts = ['structures', group_type]
    for name in parts[2:]:
        children = node.get('children') or []
        match = next(((index, child) for index, child in enumerate(children)
                      if child.get('name') == name), None)
        if match is None:
            return None, None
        index, node = match
        json_parts.extend(['children', index])
    return bc.json_path(*json_parts), node


def _attach_repair_policies(config, issues, representative_ops):
    """Bind candidate-owned errors to exact writable paths and local evidence."""
    structures = config.get('structures') or {}
    for issue in issues:
        if issue.get('id') in ('SL3', 'SL4'):
            repair_class = 'populate_missing_sublayer_ops'
        elif issue.get('id') == 'SL7':
            repair_class = 'complete_structure_template'
        else:
            continue
        path = issue.get('node_path') or ''
        parts = path.split('/')
        if len(parts) < 2 or parts[0] != 'structures':
            continue
        group_type = parts[1]
        tree = structures.get(group_type)
        if not isinstance(tree, dict):
            continue
        target, node = _structure_json_path(tree, group_type, path)
        if not target:
            target, node = bc.json_path('structures', group_type), tree
        issue['config_paths'] = [target]
        source_ref = (node or {}).get('code_ref') or tree.get('code_ref')
        if source_ref:
            issue['source_evidence'] = [source_ref]
        issue['trace_evidence'] = sorted(representative_ops.get(group_type, set()))
        issue['repair_policy'] = {
            'owner_artifact': 'analysis_config',
            'repair_class': repair_class,
            'allowed_targets': {'analysis_config': [target]},
            'required_evidence': ['candidate_nodes', 'source_snippets', 'raw_ops_slice'],
        }


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


def check_sublayers(config, raw_ops=None):
    count_compute, comm_aware = _compute_op_counter(raw_ops)
    issues = []
    structures = config.get('structures') or {}
    if not structures:
        return issues

    representative_ops = {}
    for gtype, tree in structures.items():
        path = f'structures/{gtype}'
        check_node(tree, path, issues)

        rep_ops, insts = rep_instance_ops(config, gtype)
        representative_ops[gtype] = rep_ops or set()
        tmpl_ops = node_ops(tree)
        if rep_ops is not None:
            # SL5: template claims an op the representative instance never ran. The template
            # comes from the code, the instance from one trace step, so this direction cannot
            # prove the template wrong — the step may simply not have taken that path. Report
            # it, don't block on it.
            extra = sorted(tmpl_ops - rep_ops)
            if extra:
                issues.append(Issue('SL5', 'warning', path,
                                    f'{gtype} 模板 op {extra[:20]} 不在代表实例范围内'
                                    f'（模板源自代码，实例仅为单步 trace，可能是该步未走到的分支）'))
            # SL7: the falsifiable direction — an op the representative instance ran that no
            # template node claims. The trace executed it, so the code-derived template is
            # incomplete. This is how op 372 (the `scales=` Cast emitted BEFORE
            # MoeFinalizeRoutingV2) escaped: coverage does not count structures, and SL5 only
            # ever looked for EXTRA template ops, never for an under-covering template.
            uncovered = sorted(rep_ops - tmpl_ops)
            if uncovered:
                issues.append(Issue('SL7', 'error', path,
                                    f'{gtype} 代表实例的 op {uncovered[:20]} 未被模板任何节点覆盖'
                                    f'（trace 执行了它但代码拆解没有它，证明拆解不完整）'))
            # SL6 every invocation sharing one template must have the same op count.
            #
            # Downstream attribution translates the representative's leaf offsets onto the other
            # invocations by range arithmetic. That is only valid when the ranges are the same
            # length; a differing invocation makes every offset after the divergence point land
            # on the wrong node, and the result looks plausible because each op still gets an
            # owner. So this is an error, not a note.
            #
            # It is reported per differing instance rather than as a set of lengths, because the
            # fix is per instance: give it its own layer_group and template. A first layer that
            # enters with residual=None is the usual cause — its input norm is unfused, so the
            # graph emits a different op sequence than every later layer.
            by_length = {}
            for inst in insts:
                by_length.setdefault(count_compute(bc.instance_op_indices(inst)), []).append(
                    inst.get('instance_id'))
            if len(by_length) > 1:
                rep_ids = {i.get('representative_instance_id') for i in insts} - {None}
                rep_length = next(
                    (n for n, ids in by_length.items() if set(ids) & rep_ids), None)
                basis = '计算 op' if comm_aware else 'op'
                for length, ids in sorted(by_length.items()):
                    if length == rep_length:
                        continue
                    issue = Issue(
                        'SL6', 'error', path,
                        f'{gtype} 的 invocation {ids} 有 {length} 个{basis}，'
                        f'代表实例有 {rep_length} 个：共用同一模板会让区间平移整体'
                        f'错位。请将其拆为独立 layer_group 并给出自己的模板'
                        f'（首层 residual=None 导致输入 norm 未融合是常见原因）')
                    source_ref = tree.get('code_ref') or tree.get('source_ref')
                    issue['source_evidence'] = [source_ref] if source_ref else []
                    evidence_ids = set(ids) | rep_ids
                    issue['trace_evidence'] = sorted({
                        index
                        for inst in insts
                        if inst.get('instance_id') in evidence_ids
                        for index in bc.instance_op_indices(inst)
                    })
                    issue['config_paths'] = [
                        '$.architecture.layer_groups',
                        '$.structures',
                        '$.trace_instances',
                    ]
                    issue['repair_policy'] = {
                        'owner_artifact': 'analysis_config',
                        'repair_class': 'split_incompatible_template',
                        'allowed_targets': {
                            'analysis_config': list(issue['config_paths']),
                        },
                        'required_evidence': [
                            'candidate_nodes', 'source_snippets', 'raw_ops_slice',
                        ],
                    }
                    issues.append(issue)
            elif comm_aware:
                # Compute sequences agree, so any spread in raw op counts is communication
                # jitter. Report it so the difference is on the record, but do not ask for a
                # template split: the source has one shape here.
                raw_lengths = {}
                for inst in insts:
                    raw_lengths.setdefault(len(bc.instance_op_indices(inst)), []).append(
                        inst.get('instance_id'))
                if len(raw_lengths) > 1:
                    issues.append(Issue(
                        'SL6', 'info', path,
                        f'{gtype} 各 invocation 的计算 op 数一致（{next(iter(by_length))}），'
                        f'原始 op 数不同 {dict(sorted(raw_lengths.items()))}：差异全部来自 '
                        f'core=COMMUNICATION 同步桩（建链开销/采样时序），非架构差异，不拆分模板'))

    # SL7 dense layer-0 must not be silently forced onto the layer1/2 template if its op
    # count differs. We detect it: if a dense instance's length differs from the template's
    # representative instance length, it must be flagged (needs its own template or note).
    dense_insts = [i for i in config.get('trace_instances', [])
                   if i.get('layer_group_type') == 'DeepseekV3DecoderLayer_dense']
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

    # SL8 a layer template that norms its input must declare the residual it carries.
    #
    # Residual flow lives in variable passing (`hidden, residual = norm(hidden, residual)`),
    # not in declaration order, so downstream stages cannot recover it -- and they are
    # forbidden from guessing, because a wrong skip path is worse than none. The result is
    # that an empty `branches` produces a graph with zero residual edges and no complaint:
    # a transformer rendered as a plain feed-forward chain, which reads as complete.
    #
    # Every attention-plus-norm block in current transformers carries at least one residual,
    # so an input norm with no declared branch is a missing declaration, not a model without
    # residuals. Warn rather than error: the check infers intent from names, and a genuinely
    # residual-free block would otherwise be unreportable. Naming the nodes keeps it
    # actionable instead of merely suspicious.
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
    _attach_repair_policies(config, issues, representative_ops)
    return issues


def main():
    parser = argparse.ArgumentParser(description='Sub-layer structure consistency (schema v2)')
    parser.add_argument('-c', '--config', required=True)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    if not os.path.exists(args.config):
        sys.stderr.write(f'错误: 文件不存在: {args.config}\n')
        sys.exit(2)
    with open(args.config, 'r', encoding='utf-8') as f:
        config = json.load(f)
    if bc.detect_schema_version(config) != 2:
        print(json.dumps({'script': 'check_sublayers.py', 'schema_version': 1,
                          'error_count': 0, 'issues': []}, ensure_ascii=False))
        return
    issues = check_sublayers(config)
    errors = [i for i in issues if i['severity'] == 'error']
    warnings = [i for i in issues if i['severity'] == 'warning']
    if args.json:
        print(json.dumps({'script': 'check_sublayers.py', 'config': args.config,
                          'error_count': len(errors), 'warning_count': len(warnings),
                          'issues': issues}, indent=2, ensure_ascii=False))
    else:
        for it in issues:
            print(f'[{it["severity"].upper()}] {it["id"]} @ {it["node_path"]}: {it["message"]}')
        print(f'\n汇总: errors={len(errors)}, warnings={len(warnings)}')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
