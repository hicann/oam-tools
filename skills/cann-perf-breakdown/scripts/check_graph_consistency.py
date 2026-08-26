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
from dataclasses import dataclass

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


@dataclass
class GraphContext:
    graph: dict
    config: dict
    model_id: str
    issues: list
    items: list
    architecture: dict
    groups: list
    structure_keys: set
    clusters: list
    expected: list
    main_types: list
    declared_by_type: dict


def _build_context(graph, config, model_id):
    items = list(_walk(graph))
    architecture = config.get('architecture') or {}
    groups = architecture.get('layer_groups') or []
    structure_keys = set((config.get('structures') or {}).keys())
    clusters = _decoder_clusters(items, structure_keys)
    all_groups = list(groups) + list(architecture.get('prediction_modules') or [])
    return GraphContext(
        graph=graph,
        config=config,
        model_id=model_id,
        issues=[],
        items=items,
        architecture=architecture,
        groups=groups,
        structure_keys=structure_keys,
        clusters=clusters,
        expected=[sorted(bc.expand_layer_group_indices(group)) for group in groups],
        main_types=[group.get('type', f'group_{index}')
                    for index, group in enumerate(groups)],
        declared_by_type={group.get('type'): set(bc.expand_layer_group_indices(group))
                          for group in all_groups},
    )


def _check_repeat_counts(context):
    for item, _parent in context.items:
        count = item.get('repeatCount')
        if count is None:
            continue
        indices = _repeat_indices(item)
        if len(indices) != int(count):
            context.issues.append(_issue(
                'G1', 'error', item.get('id', '<graph>'),
                f'repeatCount={count} 与 instanceIndices 长度 {len(indices)} 不一致'))


def _cluster_type(item):
    backend = item.get('backendNodeId') or ''
    return (item.get('structureKey') or backend.rsplit('/', 1)[-1]
            or (item.get('label') or ''))


def _check_cluster_declarations(context):
    if context.declared_by_type:
        drawn_types = set()
        for item, _parent in context.clusters:
            drawn_types.add(_cluster_type(item))
        missing_main = [group_type for group_type in context.main_types
                        if group_type not in drawn_types]
        if missing_main:
            context.issues.append(_issue(
                'G2', 'error', 'architecture.layer_groups',
                f'图中缺少已声明的主干 decoder 分组 {missing_main}'
                f'（已绘制: {sorted(drawn_types)}）：声明存在的分组不能从图中消失'))
        for item, _parent in context.clusters:
            group_type = _cluster_type(item)
            got = sorted(set(item.get('observedInstanceIndices')
                             or _repeat_indices(item)))
            if group_type not in context.declared_by_type:
                context.issues.append(_issue(
                    'G2', 'error', item.get('id', '<graph>'),
                    f'分组 {group_type!r} 未在 architecture 的 layer_groups / '
                    f'prediction_modules 中声明 (已声明: {sorted(context.declared_by_type)})'))
                continue
            stray = sorted(set(got) - context.declared_by_type[group_type])
            if stray:
                context.issues.append(_issue(
                    'G2', 'error', item.get('id', '<graph>'),
                    f'分组 {group_type} 观测到层号 {stray}，但其声明范围是 '
                    f'{sorted(context.declared_by_type[group_type])}：层号归属错组或被伪造'))


def _seen_layer_indices(context):
    seen = {}
    for item, _parent in context.clusters:
        for index in _repeat_indices(item):
            seen.setdefault(index, []).append(item.get('id', '<graph>'))
    return seen


def _declared_only_indices(context):
    indices = set()
    for item, _parent in context.items:
        indices.update(item.get('unobservedInstanceIndices') or [])
        state = item.get('dataState') or ''
        if state == 'source_only' or item.get('declaredNotObserved'):
            indices.update(_repeat_indices(item))
            indices.update(item.get('instanceIndices') or [])
    return indices


def _check_main_layer_coverage(context):
    num_main = context.architecture.get('num_main_layers')
    if not context.clusters or not isinstance(num_main, int) or num_main <= 0:
        return
    seen = _seen_layer_indices(context)
    overlaps = {key: value for key, value in seen.items() if len(value) > 1}
    if overlaps:
        context.issues.append(_issue(
            'G3', 'error', 'architecture.num_main_layers',
            '层号被多个 decoder 分组重复覆盖: '
            + '; '.join(f'layer {key} -> {value}' for key, value in sorted(overlaps.items()))))
    declared_only = _declared_only_indices(context)
    missing = sorted(set(range(num_main)) - set(seen) - declared_only)
    if missing:
        context.issues.append(_issue(
            'G3', 'error', 'architecture.num_main_layers',
            f'图完全未出现层号 {missing}（num_main_layers={num_main}）：'
            '声明存在但未观测的层必须作为 source-only 节点保留，不能从图中消失'))
    elif declared_only:
        detail_note = sorted(declared_only)
        context.issues.append(_issue(
            'G3', 'warning', 'architecture.num_main_layers',
            f'层号 {detail_note[0]}..{detail_note[-1]}（{len(detail_note)} 层）'
            '声明存在但本次采集未观测，已作为 source-only 节点保留（不带指标）'))
    prediction_indices = set()
    for group in context.architecture.get('prediction_modules') or []:
        prediction_indices.update(bc.expand_layer_group_indices(group))
    extra = sorted(index for index in seen
                   if not 0 <= index < num_main and index not in prediction_indices)
    if extra:
        context.issues.append(_issue(
            'G3', 'error', 'architecture.num_main_layers',
            f'图中层号超出 [0,{num_main - 1}]: {extra}'))


def _check_nested_repeats(context):
    for item, parent in context.items:
        if parent is None or not item.get('repeatCount'):
            continue
        mine = _repeat_indices(item)
        theirs = _repeat_indices(parent)
        if mine and theirs and sorted(set(mine)) == sorted(set(theirs)):
            context.issues.append(_issue(
                'G4', 'warning', item.get('id', '<graph>'),
                f'子节点重复了父节点 {parent.get("id", "?")} 的 instanceIndices '
                f'({sorted(set(mine))})，会被读成 {len(mine)}x{len(theirs)} 次调用；'
                '重复语义应只由父节点承担'))


def _check_graph_node_resolution(context):
    known_paths = _config_node_paths(context.config)
    leaf_names = _leaf_names(context.config)
    known_names = {path.rsplit('.', 1)[-1] for path in known_paths} | leaf_names
    cluster_ids = {item.get('id') for item, _parent in context.clusters}
    root_ids = {root.get('id') for root in (context.graph.get('roots') or [])
                if isinstance(root, dict)}
    graph_names = set()
    for item, parent in context.items:
        backend = item.get('backendNodeId')
        if not backend:
            continue
        tail = backend.rsplit('/', 1)[-1]
        graph_names.add(tail)
        if item.get('id') in cluster_ids or (parent is None and item.get('id') in root_ids):
            continue
        if tail not in known_names and tail not in context.structure_keys:
            context.issues.append(_issue(
                'G5', 'error', item.get('id', '<graph>'),
                f'backendNodeId={backend} 在 analysis_config 中找不到对应节点'))

    for name in sorted(leaf_names - graph_names):
        context.issues.append(_issue(
            'G6', 'warning', f'<config leaf {name}>',
            f'config 叶节点 {name} 未出现在图中，报告会丢掉该节点'))


def _leaf_reference(reference):
    return str(reference).rsplit('/', 1)[-1]


def _check_residual_branch(key, branch, order, positions, issues):
    output = _leaf_reference(branch.get('output'))
    for source in (_leaf_reference(item) for item in branch.get('inputs') or []):
        if source not in positions or output not in positions:
            issues.append(_issue(
                'G7', 'error', f'structures.{key}.branches',
                f'残差分支 {branch.get("name")} 的端点 {source}->{output} '
                f'不在 {key} 的 children 顺序里，无法判定绕过范围'))
            continue
        start, end = positions[source], positions[output]
        span = order[start + 1:end] if start < end else order[start + 1:] + order[:end]
        if not span:
            issues.append(_issue(
                'G7', 'error', f'structures.{key}.branches',
                f'残差分支 {branch.get("name")} 声明 {source}->{output}，但两者之间没有'
                f'任何被绕过的节点：残差起点取在主路径上了（方向反了）'))


def _check_residual_branches(context):
    for key, structure in (context.config.get('structures') or {}).items():
        order = [c.get('name') for c in (structure.get('children') or [])]
        positions = {name: index for index, name in enumerate(order) if name}
        for branch in structure.get('branches') or []:
            if (branch.get('kind') or 'residual') != 'residual':
                continue
            _check_residual_branch(key, branch, order, positions, context.issues)


def validate_graph(graph, config, model_id=None):
    context = _build_context(graph, config, model_id)
    _check_repeat_counts(context)
    _check_cluster_declarations(context)
    _check_main_layer_coverage(context)
    _check_nested_repeats(context)
    _check_graph_node_resolution(context)
    _check_residual_branches(context)
    detail = {
        'graph_items': len(context.items),
        'decoder_clusters': len(context.clusters),
        'config_layer_groups': len(context.groups),
        'expected_index_sets': context.expected,
        'actual_index_sets': [sorted(set(_repeat_indices(item)))
                              for item, _parent in context.clusters],
        'config_leaf_nodes': len(_leaf_names(config)),
        'model_id': model_id or (graph.get('metadata') or {}).get('model_id'),
    }
    return context.issues, detail


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
            bc.emit_error(f'错误: 文件不存在: {path}\n')
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
    text = bc.write_json_report(report, args.output)
    if args.output:
        bc.emit(f'graph consistency 已写入: {args.output}  status={report["status"]}')
    elif args.json:
        bc.emit(text)
    else:
        bc.emit(f'status={report["status"]}  '
              f'{len(errors)} error / {len(warnings)} warning')
        for item in issues:
            bc.emit(f'  [{item["severity"].upper()}] {item["id"]} {item["node_path"]}: '
                  f'{item["message"]}')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
