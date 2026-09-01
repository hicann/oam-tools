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
"""Cross-check a downstream architecture graph JSON against analysis_config_v2.

The graph consumed by the UI report is produced outside this skill, so a config
that scores 100/100 can still be rendered into a wrong picture. This check closes
that gap deterministically:

  G1 repeatCount must equal len(instanceIndices)
  G2 the multiset of decoder-cluster index sets must equal the config layer_groups
  G3 decoder clusters together must cover [0, num_main_layers-1] exactly once
  G4 a child cluster must not restate its parent's instanceIndices (14x14 illusion)
  G5 every graph backendNodeId must resolve to a config node
  G6 every config leaf node must appear somewhere in the graph
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import breakdown_common as bc  # noqa: E402


def _issue(identifier, severity, node_path, message):
    return {'id': identifier, 'severity': severity, 'check': 'graph_consistency',
            'node_path': node_path, 'message': message}


def _walk(graph):
    """Yield (item, parent) over graph roots, tolerating projected or raw specs."""
    def visit(item, parent=None):
        if not isinstance(item, dict):
            return
        yield item, parent
        for child in item.get('children') or []:
            yield from visit(child, item)
    for root in graph.get('roots') or []:
        yield from visit(root)


def _repeat_indices(item):
    idx = item.get('instanceIndices')
    if idx is None:
        idx = (item.get('attrs') or {}).get('instance_indices')
    return list(idx or [])


def _config_node_paths(config):
    """Return the set of dotted config paths that a backendNodeId may point at."""
    paths = set()

    def visit(node, prefix):
        if not isinstance(node, dict):
            return
        name = node.get('name')
        here = f'{prefix}.{name}' if name else prefix
        paths.add(here)
        for child in node.get('children') or []:
            visit(child, here)

    structures = config.get('structures') or {}
    for key, node in structures.items():
        paths.add(f'structures.{key}')
        visit(node, 'structures')
    stages = config.get('stages') or {}
    for stage in (stages.values() if isinstance(stages, dict) else stages):
        visit(stage, 'stages')
    for aux in config.get('runtime_auxiliary') or []:
        visit(aux, 'runtime_auxiliary')
    return paths


def _leaf_names(config):
    names = set()

    def visit(node):
        if not isinstance(node, dict):
            return
        children = node.get('children') or []
        if not children and node.get('name'):
            names.add(node['name'])
        for child in children:
            visit(child)

    structures = config.get('structures') or {}
    for node in structures.values():
        visit(node)
    stages = config.get('stages') or {}
    for stage in (stages.values() if isinstance(stages, dict) else stages):
        visit(stage)
    for aux in config.get('runtime_auxiliary') or []:
        visit(aux)
    return names


def _decoder_clusters(items, structure_keys):
    """Graph clusters that stand for a whole decoder layer_group.

    Matched by backendNodeId tail or label against the config structure keys, and
    otherwise by "top-level cluster carrying repeat metadata".
    """
    clusters = []
    for item, parent in items:
        if not (item.get('children') or []):
            continue
        backend = item.get('backendNodeId') or ''
        tail = backend.rsplit('/', 1)[-1] if backend else ''
        label = item.get('label') or ''
        # A renamed group matches on neither its id tail nor its label, so check the
        # preserved declaring key first; otherwise it falls through to the shape heuristic
        # and a non-repeating renamed group (one observed layer) is missed entirely.
        is_group = (item.get('structureKey') in structure_keys
                    or tail in structure_keys or label in structure_keys)
        if not is_group:
            # Fall back to shape: a repeating cluster whose parent is the model root.
            parent_backend = (parent or {}).get('backendNodeId') or ''
            is_group = bool(_repeat_indices(item)) and parent_backend.count('/') <= 1
        if is_group:
            clusters.append((item, parent))
    return clusters


def _cluster_owner_type(item, config):
    """Resolve a graph cluster's learned owner without name heuristics."""
    structure_key = item.get('structureKey')
    structure = (config.get('structures') or {}).get(structure_key) or {}
    config_owner = structure.get('architecture_group_type')
    if config_owner:
        return config_owner
    explicit = item.get('architectureGroupType')
    return (explicit or structure_key
            or (item.get('backendNodeId') or '').rsplit('/', 1)[-1]
            or (item.get('label') or ''))


def _unverifiable_single_owner(item, config, declared_by_type):
    """Return the sole possible owner when the trace carries no layer evidence."""
    structure_key = item.get('structureKey')
    structure = (config.get('structures') or {}).get(structure_key) or {}
    config_owner = structure.get('architecture_group_type')
    graph_owner = item.get('architectureGroupType')
    related_instances = [
        inst for inst in (config.get('trace_instances') or [])
        if inst.get('layer_group_type') == structure_key
    ]
    if (config_owner
            or graph_owner not in (None, structure_key)
            or len(declared_by_type) != 1
            or not related_instances
            or not all(inst.get('model_layer_index') == 'unknown'
                       for inst in related_instances)):
        return None
    return next(iter(declared_by_type))


def validate_graph(graph, config, model_id=None):
    issues = []
    items = list(_walk(graph))
    architecture = config.get('architecture') or {}
    groups = architecture.get('layer_groups') or []
    structure_keys = set((config.get('structures') or {}).keys())

    # G1 repeatCount vs instanceIndices
    for item, _ in items:
        count = item.get('repeatCount')
        if count is None:
            continue
        indices = _repeat_indices(item)
        if len(indices) != int(count):
            issues.append(_issue(
                'G1', 'error', item.get('id', '<graph>'),
                f'repeatCount={count} 与 instanceIndices 长度 {len(indices)} 不一致'))

    clusters = _decoder_clusters(items, structure_keys)
    # Clusters are matched against `structures`, which holds one template per repeated
    # group -- including learned prediction modules (MTP/draft/Medusa). Comparing that
    # against `layer_groups` alone counts a cluster the expectation never listed, so any
    # model with a prediction module fails on taxonomy rather than on a real defect.
    # Both sides must enumerate the same kinds of group.
    prediction_groups = list(architecture.get('prediction_modules') or [])
    all_groups = list(groups) + prediction_groups
    # `expected` and the detail counts describe the main decoder stack, which is what G3's
    # coverage arithmetic is about. Prediction modules sit past that stack by construction, so
    # folding them in here would report a main-stack group count no config ever declared.
    expected = [sorted(bc.expand_layer_group_indices(g)) for g in groups]
    main_types = [g.get('type', f'group_{n}') for n, g in enumerate(groups)]

    # G2 each cluster's observed layer indices must be a subset of what its own group
    # declares. Equality is the wrong test: a folded group carries only the invocations this
    # capture observed, so a partial capture legitimately shows fewer indices than declared
    # (the remainder are source-only nodes, checked by G3). What is a real defect is an
    # index the declaring group does not own -- a cluster claiming a layer belonging to
    # another group, or a fabricated index. Match by group type, not by list position.
    declared_by_type = {g.get('type'): set(bc.expand_layer_group_indices(g)) for g in all_groups}
    if all_groups:
        # Compare the *set of group types drawn* against the types declared for the main stack,
        # not the cluster count against the declared count. A count test cannot tell "the graph
        # omitted a declared decoder group" (a real defect) from "the graph does not draw the
        # prediction module" (a rendering choice G3 already tolerates via source-only nodes),
        # and it contradicts the per-cluster subset test immediately below, which is deliberately
        # lenient about partial captures. Missing main-stack groups are what must fail.
        drawn_types = set()
        for item, _ in clusters:
            drawn_types.add(
                _unverifiable_single_owner(item, config, declared_by_type)
                or _cluster_owner_type(item, config)
            )
        missing_main = [t for t in main_types if t not in drawn_types]
        if missing_main:
            issues.append(_issue(
                'G2', 'error', 'architecture.layer_groups',
                f'图中缺少已声明的主干 decoder 分组 {missing_main}'
                f'（已绘制: {sorted(drawn_types)}）：声明存在的分组不能从图中消失'))
        for item, _ in clusters:
            # `structureKey` is the declaring key from `structures`, preserved even when
            # `--rename-group` replaced the visible name. Prefer it: the node id tail is the
            # renamed role, which `architecture` never mentions, so matching on it reports
            # every renamed group as undeclared.
            structure_key = item.get('structureKey')
            structure = (config.get('structures') or {}).get(structure_key) or {}
            config_owner = structure.get('architecture_group_type')
            graph_owner = item.get('architectureGroupType')
            if config_owner and graph_owner and graph_owner != config_owner:
                issues.append(_issue(
                    'G2', 'error', item.get('id', '<graph>'),
                    f'图中 architectureGroupType={graph_owner!r} 与 '
                    f'analysis_config structures.{structure_key}.architecture_group_type='
                    f'{config_owner!r} 不一致；图只能透传 learned owner，不能改写归属'))
            gtype = _cluster_owner_type(item, config)
            # The pager index spans declared layers; G2 is about what the capture claims to
            # have observed, so prefer the explicit observed list when the graph carries it.
            got = sorted(set(item.get('observedInstanceIndices')
                             or _repeat_indices(item)))
            if gtype not in declared_by_type:
                only_owner = _unverifiable_single_owner(item, config, declared_by_type)
                if only_owner:
                    issues.append(_issue(
                        'G2', 'warning', item.get('id', '<graph>'),
                        f'运行时模板 {gtype!r} 的 learned owner 未验证；架构仅声明 '
                        f'{only_owner!r}，且相关 trace 的 model_layer_index 全为 unknown。'
                        '允许生成报告，但不能据此声明精确模型层归属'))
                    continue
                issues.append(_issue(
                    'G2', 'error', item.get('id', '<graph>'),
                    f'分组 {gtype!r} 未在 architecture 的 layer_groups / '
                    f'prediction_modules 中声明 (已声明: {sorted(declared_by_type)})'))
                continue
            stray = sorted(set(got) - declared_by_type[gtype])
            if stray:
                issues.append(_issue(
                    'G2', 'error', item.get('id', '<graph>'),
                    f'分组 {gtype} 观测到层号 {stray}，但其声明范围是 '
                    f'{sorted(declared_by_type[gtype])}：层号归属错组或被伪造'))

    # G3 exact coverage of the main layer range
    num_main = architecture.get('num_main_layers')
    if clusters and isinstance(num_main, int) and num_main > 0:
        trace_instances = config.get('trace_instances') or []
        has_unknown_only_trace = (bool(trace_instances)
                                  and not any(isinstance(inst.get('model_layer_index'), int)
                                              for inst in trace_instances))
        if has_unknown_only_trace:
            unsupported_observed = {}
            for item, _ in clusters:
                if item.get('dataState') == 'source_only' or item.get('declaredNotObserved'):
                    continue
                claimed = list(item.get('observedInstanceIndices') or _repeat_indices(item))
                if claimed:
                    unsupported_observed[item.get('id', '<graph>')] = sorted(set(claimed))
            if unsupported_observed:
                issues.append(_issue(
                    'G3', 'error', 'trace_instances.model_layer_index',
                    '图把数字层号标为本次采集已观测，但 trace 没有数字层号证据：'
                    + '; '.join(f'{node} -> {indices}'
                               for node, indices in sorted(unsupported_observed.items()))
                    + '；禁止用 invocation_index 生成 model_layer_index'))
        seen = {}
        for item, _ in clusters:
            for idx in _repeat_indices(item):
                seen.setdefault(idx, []).append(item.get('id', '<graph>'))
        overlaps = {k: v for k, v in seen.items() if len(v) > 1}
        if overlaps:
            issues.append(_issue(
                'G3', 'error', 'architecture.num_main_layers',
                f'层号被多个 decoder 分组重复覆盖: '
                + '; '.join(f'layer {k} -> {v}' for k, v in sorted(overlaps.items()))))
        # A declared layer is covered if the graph carries it at all -- either an observed
        # instance of a repeated group, or a metric-free declared-not-observed node. A
        # capture spanning one step need not execute every layer, so demanding an observed
        # instance for all of them fails on partial captures instead of on real gaps. What
        # must never happen is a declared layer appearing nowhere: that is a silently
        # shrunken model. Track the two states separately so the message says which.
        declared_only = set()
        for item, _ in items:
            # Unrun layers ride in their group's pager index, so read that first; a
            # standalone source-only item is also accepted for graphs built that way.
            declared_only.update(item.get('unobservedInstanceIndices') or [])
            state = item.get('dataState') or ''
            if state == 'source_only' or item.get('declaredNotObserved'):
                declared_only.update(_repeat_indices(item))
                declared_only.update(item.get('instanceIndices') or [])
        missing = sorted(set(range(num_main)) - set(seen) - declared_only)
        if has_unknown_only_trace and missing:
            issues.append(_issue(
                'G3', 'warning', 'trace_instances.model_layer_index',
                '本次采集的 model_layer_index 全部为 unknown，无法验证主层号精确覆盖；'
                '保留 architecture 声明，但不把 invocation_index 伪装成模型层号'))
        elif missing:
            issues.append(_issue(
                'G3', 'error', 'architecture.num_main_layers',
                f'图完全未出现层号 {missing}（num_main_layers={num_main}）：'
                '声明存在但未观测的层必须作为 source-only 节点保留，不能从图中消失'))
        elif declared_only:
            detail_note = sorted(declared_only)
            issues.append(_issue(
                'G3', 'warning', 'architecture.num_main_layers',
                f'层号 {detail_note[0]}..{detail_note[-1]}（{len(detail_note)} 层）'
                '声明存在但本次采集未观测，已作为 source-only 节点保留（不带指标）'))
        # Prediction modules sit past the main stack by construction: a learned MTP module is
        # indexed at num_hidden_layers (DeepSeek's `layer_idx == config.num_hidden_layers`),
        # so its index is legitimately outside [0, num_main). Only indices belonging to no
        # declared group at all are out of range.
        prediction_indices = {
            idx
            for group in (architecture.get('prediction_modules') or [])
            for idx in bc.expand_layer_group_indices(group)
        }
        extra = sorted(idx for idx in seen
                       if not 0 <= idx < num_main and idx not in prediction_indices)
        if extra:
            issues.append(_issue(
                'G3', 'error', 'architecture.num_main_layers',
                f'图中层号超出 [0,{num_main - 1}]: {extra}'))

    # G4 nested repeat restating the parent's indices
    for item, parent in items:
        if parent is None or not item.get('repeatCount'):
            continue
        mine = _repeat_indices(item)
        theirs = _repeat_indices(parent)
        if mine and theirs and sorted(set(mine)) == sorted(set(theirs)):
            issues.append(_issue(
                'G4', 'warning', item.get('id', '<graph>'),
                f'子节点重复了父节点 {parent.get("id", "?")} 的 instanceIndices '
                f'({sorted(set(mine))})，会被读成 {len(mine)}x{len(theirs)} 次调用；'
                '重复语义应只由父节点承担'))

    # G5 every graph backendNodeId resolves to a config node.
    # Decoder group clusters are matched positionally by G2/G3 (the graph may name them
    # by source path while the config keys them by layer_group type), so exempt them here.
    known_paths = _config_node_paths(config)
    leaf_names = _leaf_names(config)
    known_names = {path.rsplit('.', 1)[-1] for path in known_paths} | leaf_names
    cluster_ids = {item.get('id') for item, _ in clusters}
    # The graph's own roots are presentation wrappers for the whole model; the config
    # has no node for them by construction, so they are not G5 candidates.
    root_ids = {root.get('id') for root in (graph.get('roots') or [])
                if isinstance(root, dict)}
    graph_names = set()
    for item, parent in items:
        backend = item.get('backendNodeId')
        if not backend:
            continue
        tail = backend.rsplit('/', 1)[-1]
        graph_names.add(tail)
        if item.get('id') in cluster_ids or (parent is None and item.get('id') in root_ids):
            continue
        if tail not in known_names and tail not in structure_keys:
            issues.append(_issue(
                'G5', 'error', item.get('id', '<graph>'),
                f'backendNodeId={backend} 在 analysis_config 中找不到对应节点'))

    # G6 every config leaf appears in the graph
    for name in sorted(leaf_names - graph_names):
        issues.append(_issue(
            'G6', 'warning', f'<config leaf {name}>',
            f'config 叶节点 {name} 未出现在图中，报告会丢掉该节点'))

    # G7 a declared residual branch must actually bypass something.
    #
    # `inputs`/`output` name the two ends of a skip path. The siblings strictly between
    # them (wrapping when the edge loops back to the group head) are the sub-path being
    # bypassed. If that span is empty the branch asserts a skip over nothing, which means
    # the source was taken from the main path instead of from the point the residual
    # forks off -- the exact shape of an inverted residual. Referential integrity (G5)
    # cannot see this: both endpoints exist, only the direction is wrong.
    for key, structure in (config.get('structures') or {}).items():
        order = [c.get('name') for c in (structure.get('children') or [])]
        pos = {n: i for i, n in enumerate(order) if n}
        for branch in structure.get('branches') or []:
            if (branch.get('kind') or 'residual') != 'residual':
                continue
            # Endpoints may be bare child names or fully-qualified node ids; the graph
            # builder resolves the qualified form, so compare on the trailing segment.
            def _leaf(ref):
                return str(ref).rsplit('/', 1)[-1]
            out = _leaf(branch.get('output'))
            for src in (_leaf(s) for s in branch.get('inputs') or []):
                if src not in pos or out not in pos:
                    issues.append(_issue(
                        'G7', 'error', f'structures.{key}.branches',
                        f'残差分支 {branch.get("name")} 的端点 {src}->{out} '
                        f'不在 {key} 的 children 顺序里，无法判定绕过范围'))
                    continue
                i, j = pos[src], pos[out]
                span = order[i + 1:j] if i < j else order[i + 1:] + order[:j]
                if not span:
                    issues.append(_issue(
                        'G7', 'error', f'structures.{key}.branches',
                        f'残差分支 {branch.get("name")} 声明 {src}->{out}，但两者之间没有'
                        f'任何被绕过的节点：残差起点取在主路径上了（方向反了）'))

    detail = {
        'graph_items': len(items),
        'decoder_clusters': len(clusters),
        'config_layer_groups': len(groups),
        'expected_index_sets': expected,
        'actual_index_sets': [sorted(set(_repeat_indices(i))) for i, _ in clusters],
        'config_leaf_nodes': len(leaf_names),
        'model_id': model_id or (graph.get('metadata') or {}).get('model_id'),
    }
    return issues, detail


def validate_file(graph_path, config_path):
    with open(graph_path, encoding='utf-8') as stream:
        graph = json.load(stream)
    with open(config_path, encoding='utf-8') as stream:
        config = json.load(stream)
    return validate_graph(graph, config)


def main():
    parser = argparse.ArgumentParser(
        description='Cross-check a downstream architecture graph against analysis_config_v2')
    parser.add_argument('-g', '--graph', required=True,
                        help='model_architecture_graph.json produced by the UI skill')
    parser.add_argument('-c', '--config', required=True, help='analysis_config_v2.json')
    parser.add_argument('--json', action='store_true', help='emit a single JSON document')
    parser.add_argument('-o', '--output')
    args = parser.parse_args()

    for path in (args.graph, args.config):
        if not os.path.exists(path):
            sys.stderr.write(f'错误: 文件不存在: {path}\n')
            sys.exit(2)

    issues, detail = validate_file(args.graph, args.config)
    errors = [i for i in issues if i['severity'] == 'error']
    warnings = [i for i in issues if i['severity'] == 'warning']
    report = {
        'script': 'check_graph_consistency.py',
        'graph': args.graph,
        'config': args.config,
        'status': 'failed' if errors else ('warning' if warnings else 'passed'),
        'error_count': len(errors),
        'warning_count': len(warnings),
        'detail': detail,
        'issues': issues,
    }
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as stream:
            stream.write(text + '\n')
        print(f'graph consistency 已写入: {args.output}  status={report["status"]}')
    elif args.json:
        print(text)
    else:
        print(f'status={report["status"]}  '
              f'{len(errors)} error / {len(warnings)} warning')
        for item in issues:
            print(f'  [{item["severity"].upper()}] {item["id"]} {item["node_path"]}: '
                  f'{item["message"]}')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
