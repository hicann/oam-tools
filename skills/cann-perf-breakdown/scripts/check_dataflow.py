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
"""Compare the AST-derived dataflow against the declared analysis config.

`forward()` IS the dataflow graph. A semantic review that says "the residual paths are
correct" in prose throws away a free, machine-checkable ground truth -- and a valid source
line plus a valid op index is enough to make a wrong conclusion pass. This script closes
that gap: it re-derives the graph from source and compares it with what the config claims.

Checks (each cites the evidence it used, and abstains when the evidence is absent):

  D1 a config structure whose source module performs a residual join must declare a branch
  D2 a declared branch must not invert direction (source on the main path, bypassing nothing)
  D3 a declared branch's bypassed span must correspond to a real skip in the source
  D4 a fork in the source (one value read by 2+ consumers) must not be declared as a chain
  D5 blocking `unsupported` AST with no matching deviation declaration
  D6 a submodule called in the selected profile's method must appear in the structure
  D7 capability-declared joins must exist (only when a capability asserts them)
  D8 every top-level `dataflow` edge endpoint must name a declared node (JSON Schema
     cannot express a cross-reference, so an edge to a typo'd id would otherwise validate
     and then silently vanish from the rendered graph)

Deliberately NOT here: model class names, kernel names, layer counts, family constants. The
comparison is between two graphs. Anything family-specific arrives as an adapter invariant
or a manifest capability, so a Dense model is never failed for lacking MoE branches.
"""
import argparse
import json
import os
import sys
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract_dataflow  # noqa: E402
import breakdown_common as bc  # noqa: E402

#: Producer id the extractor uses for values arriving as forward() arguments. Read from
#: the extractor rather than restated, so the two cannot drift apart.
INPUT_CALL = getattr(extract_dataflow, 'INPUT', -1)


class DataflowInputError(Exception):
    """Raised when a requested inline source file does not exist."""


def _issue(identifier, severity, node_path, message, evidence=None):
    item = {'id': identifier, 'severity': severity, 'check': 'dataflow',
            'node_path': node_path, 'message': message}
    if evidence:
        item['evidence'] = evidence
    return item


def _leaf(ref):
    """Trailing segment of a node reference; branches may use bare names or full ids."""
    return str(ref).rsplit('/', 1)[-1]


def _child_names(structure):
    return [c.get('name') for c in (structure.get('children') or []) if c.get('name')]


def _structure_names(structure):
    """All named nodes below one structure, including nested containers."""
    names = set()

    def walk(node):
        if node.get('name'):
            names.add(node['name'])
        for child in node.get('children') or []:
            walk(child)

    walk(structure)
    return names


def _module_root(symbol):
    """`self.layers[0].mlp` -> `layers`; non-self calls are not submodules."""
    text = str(symbol)
    if not text.startswith('self.'):
        return None
    return text[len('self.'):].split('.', 1)[0].split('[', 1)[0]


def _related_name(name, requirement):
    """Match a capability id to an explicitly named source/config node."""
    left = str(name or '').lower().replace('-', '_')
    right = str(requirement or '').lower().replace('-', '_')
    return bool(left and right and (left == right or left.endswith('_' + right)
                                    or right.endswith('_' + left)))


def _source_ref_covers(source_ref, source_path, lineno, all_source_paths=None):
    """Whether a declared file:range identifies this exact source construct."""
    parsed = bc.parse_source_ref(source_ref)
    if not parsed or not isinstance(lineno, int):
        return False
    declared_file, start, end = parsed
    source_name = os.path.normcase(os.path.normpath(source_path or ''))
    declared_name = os.path.normcase(os.path.normpath(declared_file))
    if os.path.isabs(declared_name):
        matches = [source_name] if source_name == declared_name else []
    else:
        candidates = all_source_paths or [source_path]
        matches = []
        for path in candidates:
            candidate_name = os.path.normcase(os.path.normpath(path))
            if candidate_name == declared_name or candidate_name.endswith(os.sep + declared_name):
                matches.append(candidate_name)
    same_file = len(set(matches)) == 1 and matches[0] == source_name if matches else False
    return same_file and start <= lineno <= end


def _module_tail(symbol):
    """`self.post_attention_layernorm[1]` -> `post_attention_layernorm`.

    Indices and the `self.` prefix are stripped: the config names a template's child once,
    while the source may call it per-index.
    """
    text = str(symbol)
    if text.startswith('self.'):
        text = text[len('self.'):]
    text = text.split('[')[0]
    return text.rsplit('.', 1)[-1]


def _source_merges(module):
    """Merge points in one extracted method, as sets of contributing module tails."""
    merges = []
    for merge in module.get('merges') or []:
        producers = []
        producer_ids = []
        for operand in merge.get('operands') or []:
            source_call = operand.get('from_call')
            if source_call is None:
                continue
            calls = module.get('calls') or []
            if 0 <= source_call < len(calls):
                producers.append(_module_tail(calls[source_call].get('symbol')))
                producer_ids.append(source_call)
        call_id = merge.get('call_id')
        main_source = max(producer_ids) if producer_ids else None
        residual_producers = [
            _module_tail((module.get('calls') or [])[source_call].get('symbol'))
            for source_call in producer_ids if source_call != main_source
        ]
        merges.append({
            'call_id': call_id,
            'kind': merge.get('kind', 'binop_add'),
            'lineno': merge.get('lineno'),
            'operand_count': merge.get('operand_count'),
            'producers': producers,
            'residual_producers': residual_producers,
            'at': _module_tail((module.get('calls') or [{}])[merge['call_id']].get('symbol'))
            if merge.get('call_id') is not None
               and 0 <= merge.get('call_id', -1) < len(module.get('calls') or [])
            else None,
        })
    return merges


def _branch_matches_merge(branch, merge, positions):
    """Match a residual declaration to the exact source join it describes."""
    output = _leaf(branch.get('output'))
    if output != merge.get('at'):
        return False
    inputs = {_leaf(item) for item in branch.get('inputs') or []}
    residual_producers = set(merge.get('residual_producers') or [])
    if residual_producers:
        return residual_producers.issubset(inputs)
    # A fused entry merge can carry a residual from the previous invocation, which the
    # current method has no producer call for. Its declaration must explicitly wrap from a
    # later child back to this join (or use the cross_invocation kind).
    if branch.get('kind') == 'cross_invocation':
        return True
    output_pos = positions.get(output)
    return output_pos is not None and any(
        positions.get(name, -1) > output_pos for name in inputs)


def _parallel_branch_matches_fork(branch, producer_name, consumers):
    """Whether a parallel declaration names this fork rather than an unrelated edge."""
    endpoints = {_leaf(item) for item in branch.get('inputs') or []}
    endpoints.add(_leaf(branch.get('output')))
    source_names = set(consumers)
    if not str(producer_name).startswith('<'):
        source_names.add(producer_name)
    return bool(endpoints & source_names)


def _has_parallel_branch(branches, producer_name, consumers, capability_id):
    for branch in branches:
        if not _parallel_branch_matches_fork(branch, producer_name, consumers):
            continue
        if not capability_id:
            return True
        related_names = [branch.get('name'), branch.get('output')]
        related_names.extend(branch.get('inputs') or [])
        if any(_related_name(name, capability_id) for name in related_names):
            return True
    return False


def _match_structure_to_module(key, structure, modules):
    """Pick the extracted method most likely to be this structure's source.

    Matched on how many of the structure's children appear as called submodules -- not on
    class-name similarity, which is exactly the heuristic that misreads custom naming. A
    structure with no overlap returns None and its checks abstain rather than guess.
    """
    names = {n for n in _child_names(structure)}
    if not names:
        return None, 0
    best, best_score = None, 0
    for module in modules:
        called = {_module_tail(c.get('symbol')) for c in (module.get('calls') or [])}
        score = len(names & called)
        if score > best_score:
            best, best_score = module, score
    return best, best_score


@dataclass
class DataflowState:
    config: dict
    manifest: dict
    modules: list
    structures: dict
    all_source_paths: list
    issues: list = field(default_factory=list)
    matched_structures: list = field(default_factory=list)
    declared_deviations: set = field(default_factory=set)
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class StructureMatch:
    key: str
    structure: dict
    module: dict
    score: int
    order: list
    positions: dict
    branches: list
    source_merges: list
    residual_branches: list
    parallel_branches: list


def _build_state(config, dataflow, manifest, profile):
    modules = list(dataflow.get('modules') or [])
    structures = config.get('structures') or {}
    detail = {
        'source_modules': len(modules),
        'config_structures': len(structures),
        'matched': {},
        'unmatched': [],
        'source_merge_count': sum(len(module.get('merges') or []) for module in modules),
        'profile': profile,
    }
    return DataflowState(
        config=config,
        manifest=manifest or {},
        modules=modules,
        structures=structures,
        all_source_paths=[module.get('source_path', '') for module in modules],
        detail=detail,
    )


def _check_missing_modules(state):
    if state.modules:
        return False
    state.detail['note'] = ('dataflow_source.json 没有可用模块（源码未提供或全部不可解析）：'
                            '跳过源码对比，不据此判定配置正确')
    state.issues.append(_issue(
            'D0', 'warning', '<source>',
            'dataflow_source.json 没有可解析的源码模块；数据流与分支正确性不可验证，'
            '不得将该检查计为通过'))
    return True


def _check_unsupported(state):
    state.declared_deviations = {
        (d.get('source_ref') or '').strip()
        for d in (state.config.get('deviations') or [])
    }
    for module in state.modules:
        for unsupported in module.get('unsupported') or []:
            severity = unsupported.get('severity')
            if severity not in ('data_dependent', 'unparsable'):
                continue
            source_path = module.get('source_path', '')
            lineno = unsupported.get('lineno')
            ref = f"{os.path.basename(source_path)}:{lineno}"
            if any(_source_ref_covers(d, source_path, lineno, state.all_source_paths)
                   for d in state.declared_deviations if d):
                continue
            state.issues.append(_issue(
                'D5', 'error', f"{module.get('class_name')}.{module.get('method')}",
                f"{ref} 的控制流依赖运行期数据（{unsupported.get('severity')}："
                f"{unsupported.get('condition') or unsupported.get('construct')}），"
                f"AST 无法确定实际数据流；必须在 config.deviations 中显式声明所走分支及理由",
                evidence=[ref, unsupported.get('reason', '')]))


def _build_structure_match(key, structure, module, score):
    order = _child_names(structure)
    branches = structure.get('branches') or []
    return StructureMatch(
        key=key,
        structure=structure,
        module=module,
        score=score,
        order=order,
        positions={name: index for index, name in enumerate(order)},
        branches=branches,
        source_merges=_source_merges(module),
        residual_branches=[branch for branch in branches
                           if (branch.get('kind') or 'residual') == 'residual'],
        parallel_branches=[branch for branch in branches if branch.get('kind') == 'parallel'],
    )


def _missing_merges(match):
    available_branches = list(match.residual_branches)
    missing = []
    for merge in match.source_merges:
        matched_index = None
        for index, branch in enumerate(available_branches):
            if _branch_matches_merge(branch, merge, match.positions):
                matched_index = index
                break
        if matched_index is None:
            missing.append(merge)
        else:
            available_branches.pop(matched_index)
    return missing


def _check_source_merges(match, issues):
    missing_merges = _missing_merges(match)
    if missing_merges:
        issues.append(_issue(
            'D1', 'error', f'structures.{match.key}.branches',
            f'源码 {match.module.get("class_name")}.{match.module.get("method")} 有 '
            f'{len(match.source_merges)} 处残差汇合，但配置只覆盖了 '
            f'{len(match.source_merges) - len(missing_merges)} 处；未覆盖行 '
            f'{[merge["lineno"] for merge in missing_merges]}：'
            f'残差是变量传递、不体现在 children 顺序里，下游不允许推导，'
            f'因此架构图会缺失全部残差边',
            evidence=[f'{os.path.basename(match.module.get("source_path", ""))}:{merge["lineno"]}'
                      for merge in missing_merges]))


def _check_residual_input(match, branch, raw_source, called, issues):
    output = _leaf(branch.get('output'))
    source_name = _leaf(raw_source)
    if source_name not in match.positions or output not in match.positions:
        return
    start, end = match.positions[source_name], match.positions[output]
    span = (match.order[start + 1:end] if start < end
            else match.order[start + 1:] + match.order[:end])
    if not span:
        issues.append(_issue(
            'D2', 'error', f'structures.{match.key}.branches',
            f'残差分支 {branch.get("name")} 声明 {source_name}->{output}，'
            f'两者之间没有被绕过的节点：起点取在主路径上（方向反了）'))
    elif called and not (set(span) & called):
        issues.append(_issue(
            'D3', 'warning', f'structures.{match.key}.branches',
            f'残差分支 {branch.get("name")} 声明绕过 {span}，'
            f'但源码 {match.module.get("method")} 未调用其中任何一个子模块：'
            f'该分支可能不是从源码读出的', evidence=sorted(called)[:8]))


def _check_residual_branches(match, issues):
    called = {_module_tail(call.get('symbol')) for call in (match.module.get('calls') or [])}
    for branch in match.branches:
        if (branch.get('kind') or 'residual') != 'residual':
            continue
        for raw_source in branch.get('inputs') or []:
            _check_residual_input(match, branch, raw_source, called, issues)


def _fork_names(fork, calls):
    producer = fork.get('from_call')
    from_input = bool(fork.get('from_input')) or producer == INPUT_CALL
    if not from_input and (producer is None or not (0 <= producer < len(calls))):
        return None
    producer_name = (f'<{fork.get("variable", "input")}>' if from_input
                     else _module_tail(calls[producer].get('symbol')))
    consumers = [_module_tail(calls[index].get('symbol'))
                 for index in fork.get('read_by_calls') or [] if 0 <= index < len(calls)]
    return producer, from_input, producer_name, consumers


def _chained_consumers(consumers, positions):
    ordered = sorted(consumers, key=lambda name: positions[name])
    return [(first, second) for first, second in zip(ordered, ordered[1:])
            if positions[second] == positions[first] + 1]


def _pop_parallel_match(branches, producer_name, consumers):
    for index, branch in enumerate(branches):
        if _parallel_branch_matches_fork(branch, producer_name, consumers):
            branches.pop(index)
            return True
    return False


def _check_fork(match, fork, remaining_parallel, issues):
    calls = match.module.get('calls') or []
    names = _fork_names(fork, calls)
    if names is None:
        return
    producer, from_input, producer_name, consumers = names
    present = [consumer for consumer in consumers if consumer in match.positions]
    if len(present) < 2 or (not from_input and producer_name not in match.positions):
        return
    if _pop_parallel_match(remaining_parallel, producer_name, consumers):
        return
    where = (calls[min(fork.get('read_by_calls') or [0])].get('lineno')
             if from_input else calls[producer].get('lineno'))
    issues.append(_issue(
        'D4', 'warning', f'structures.{match.key}',
        f'源码中 {producer_name} 被 {sorted(set(present))} 并行读取'
        f'（行 {where}），但配置没有为该 fork 单独声明 kind: parallel '
        f'的 branch；相邻链 {_chained_consumers(present, match.positions)} 会被下游渲染为串行',
        evidence=[f'fork from {"input" if from_input else f"call {producer}"}'
                  f' ({fork.get("variable")}): {consumers}']))


def _check_forks(match, issues):
    remaining_parallel = list(match.parallel_branches)
    for fork in match.module.get('forks') or []:
        _check_fork(match, fork, remaining_parallel, issues)


def _check_submodules(match, issues):
    declared_submodules = set(match.module.get('submodules') or {})
    called_submodules = set()
    for call in match.module.get('calls') or []:
        root = _module_root(call.get('symbol'))
        if root in declared_submodules:
            called_submodules.add(root)
    missing_submodules = sorted(called_submodules - _structure_names(match.structure))
    if missing_submodules:
        issues.append(_issue(
            'D6', 'error', f'structures.{match.key}',
            f'源码调用了已声明子模块 {missing_submodules}，但该 structure 中没有对应节点',
            evidence=[f'{match.module.get("class_name")}.{match.module.get("method")}']))


def _check_structures(state):
    for key, structure in state.structures.items():
        module, score = _match_structure_to_module(key, structure, state.modules)
        if module is None or score == 0:
            state.detail['unmatched'].append(key)
            continue
        state.detail['matched'][key] = {
            'class_name': module.get('class_name'),
            'method': module.get('method'),
            'matched_children': score,
        }
        match = _build_structure_match(key, structure, module, score)
        state.matched_structures.append((key, structure, module, score))
        _check_source_merges(match, state.issues)
        _check_residual_branches(match, state.issues)
        _check_forks(match, state.issues)
        _check_submodules(match, state.issues)


def _best_matches(matched_structures):
    best_score_by_module = {}
    for _, _, module, score in matched_structures:
        module_key = id(module)
        best_score_by_module[module_key] = max(score, best_score_by_module.get(module_key, 0))
    return [item for item in matched_structures
            if item[3] == best_score_by_module.get(id(item[2]), 0)]


def _count_invariant_satisfied(invariant, best_matches):
    tokens = [str(token).lower() for token in invariant.get('match_any') or []]
    minimum = invariant.get('min_occurrences', 1)
    for _, structure, module, _ in best_matches:
        source_count = sum(
            any(token in _module_tail(call.get('symbol')).lower() for token in tokens)
            for call in module.get('calls') or [])
        config_count = sum(
            any(token in str(name).lower() for token in tokens)
            for name in _structure_names(structure))
        if source_count >= minimum and config_count >= minimum:
            return True
    return False


def _fork_satisfies_capability(fork, calls, branches, capability_id):
    producer = fork.get('from_call')
    from_input = bool(fork.get('from_input')) or producer == INPUT_CALL
    producer_name = (f'<{fork.get("variable", "input")}>' if from_input
                     else _module_tail(calls[producer].get('symbol'))
                     if isinstance(producer, int) and 0 <= producer < len(calls)
                     else '<unknown>')
    consumers = [_module_tail(calls[index].get('symbol'))
                 for index in fork.get('read_by_calls') or [] if 0 <= index < len(calls)]
    if capability_id and not any(_related_name(name, capability_id) for name in consumers):
        return False
    return _has_parallel_branch(branches, producer_name, consumers, capability_id)


def _parallel_invariant_satisfied(capability_id, best_matches):
    for _, structure, module, _ in best_matches:
        branches = [branch for branch in structure.get('branches') or []
                    if branch.get('kind') == 'parallel']
        calls = module.get('calls') or []
        if any(_fork_satisfies_capability(fork, calls, branches, capability_id)
               for fork in module.get('forks') or []):
            return True
    return False


def _check_invariants(state):
    capabilities = {item.get('id'): item
                    for item in (state.manifest.get('capabilities') or [])}
    declared_invariants = list(state.manifest.get('dataflow_invariants') or [])
    fallback_invariants = [
        {'id': 'shared_expert_parallel', 'requires': 'shared_expert',
         'reason': 'a parallel expert path joining at the combine point'},
        {'id': 'sparse_index_attention_parallel', 'requires': 'sparse_index_attention',
         'reason': 'an indexer side path feeding attention'},
    ]
    best_matches = _best_matches(state.matched_structures)
    for invariant in declared_invariants or fallback_invariants:
        capability_id = invariant.get('requires')
        requirement = invariant.get('reason') or invariant.get('id') or ''
        if capability_id and capability_id not in capabilities:
            continue
        if invariant.get('kind') == 'min_call_occurrences':
            satisfied = _count_invariant_satisfied(invariant, best_matches)
        else:
            satisfied = _parallel_invariant_satisfied(capability_id, best_matches)
        if not satisfied:
            invariant_name = capability_id or invariant.get('id', 'ungated')
            state.issues.append(_issue(
                'D7', 'error', f'dataflow_invariants.{invariant_name}',
                f'manifest 声明数据流约束 `{invariant_name}`（{requirement}），'
                f'但同一源码模块与 structure 中没有对应声明',
                evidence=[(capabilities.get(capability_id) or {}).get(
                    'source_ref', invariant.get('id', 'unknown'))]))


def check_dataflow(config, dataflow, manifest=None, profile=None):
    """Return (issues, detail). Absent evidence never manufactures a failure."""
    state = _build_state(config, dataflow, manifest, profile)
    state.issues.extend(_check_declared_dataflow(config, state.structures, state.detail))
    if _check_missing_modules(state):
        return state.issues, state.detail
    _check_unsupported(state)
    _check_structures(state)
    _check_invariants(state)
    state.detail['declared_deviations'] = len(state.declared_deviations)
    return state.issues, state.detail


def _check_declared_dataflow(config, structures, detail):
    """D8: every endpoint in the top-level `dataflow` block must resolve.

    JSON Schema cannot express "this string must match an id in a sibling array", so an edge
    pointing at a typo validates cleanly and then disappears from the rendered graph -- the
    reader sees a model missing an edge, with nothing reporting it. Absent `dataflow` is not
    checked: that means the top-level edges are undeclared, which D8 has no opinion about
    (and which nothing downstream may read as "the model is a single chain").
    """
    declared = config.get('dataflow') or {}
    if not declared:
        return []
    issues = []
    node_ids = {n.get('id') for n in (declared.get('nodes') or []) if n.get('id')}
    detail['dataflow_nodes'] = len(node_ids)
    detail['dataflow_edges'] = len(declared.get('edges') or [])
    for position, edge in enumerate(declared.get('edges') or []):
        for side in ('source', 'target'):
            endpoint = edge.get(side)
            if endpoint and endpoint not in node_ids:
                issues.append(_issue(
                    'D8', 'error', f'dataflow.edges[{position}].{side}',
                    f'边的 {side} 端点 `{endpoint}` 不在 dataflow.nodes 中；'
                    f'JSON Schema 无法校验交叉引用，这条边会通过校验然后在图里消失',
                    evidence=[edge.get('source_ref', 'unknown')]))
    # A node standing for a structure must name one that exists, for the same reason.
    for position, node in enumerate(declared.get('nodes') or []):
        key = node.get('structure')
        if key and key not in structures and key not in (config.get('stages') or {}):
            issues.append(_issue(
                'D8', 'error', f'dataflow.nodes[{position}].structure',
                f'节点声明代表结构 `{key}`，但 structures/stages 中没有该键',
                evidence=[node.get('source_ref', 'unknown')]))
    return issues


def _parse_args():
    parser = argparse.ArgumentParser(
        description='Compare AST-derived dataflow with the declared analysis config')
    parser.add_argument('-c', '--config', required=True)
    parser.add_argument('-d', '--dataflow',
                        help='dataflow_source.json from extract_dataflow.py')
    parser.add_argument('-s', '--source', action='append',
                        help='model source file; derives the dataflow inline when '
                             '--dataflow is not supplied (repeatable)')
    parser.add_argument('-m', '--manifest', help='model_manifest.json (for capabilities)')
    parser.add_argument('--profile', help='execution profile id being validated')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('-o', '--output')
    return parser.parse_args()


def _load_dataflow(args):
    if args.dataflow:
        with open(args.dataflow, encoding='utf-8') as stream:
            return json.load(stream)
    modules = []
    for path in args.source:
        if not os.path.exists(path):
            raise DataflowInputError(f'错误: 文件不存在: {path}')
        modules.extend(extract_dataflow.extract_file(path))
    return {'schema_version': 2, 'modules': modules}


def _load_manifest(path):
    if path and os.path.exists(path):
        with open(path, encoding='utf-8') as stream:
            return json.load(stream)
    return None


def _build_report(args, config, dataflow, manifest):
    issues, detail = check_dataflow(config, dataflow, manifest, args.profile)
    errors = [item for item in issues if item['severity'] == 'error']
    warnings = [item for item in issues if item['severity'] == 'warning']
    return {
        'script': 'check_dataflow.py',
        'config': args.config,
        'status': 'failed' if errors else ('warning' if warnings else 'passed'),
        'error_count': len(errors),
        'warning_count': len(warnings),
        'detail': detail,
        'issues': issues,
    }


def _emit_report(report, args):
    text = bc.write_json_report(report, args.output)
    if args.output:
        bc.emit(f'dataflow 校验已写入: {args.output}  status={report["status"]} '
                f'errors={report["error_count"]} warnings={report["warning_count"]}')
    elif args.json:
        bc.emit(text)
    else:
        bc.emit(f'status={report["status"]} errors={report["error_count"]} '
                f'warnings={report["warning_count"]}')
        for item in report['issues']:
            bc.emit(f'  [{item["severity"]}] {item["id"]} {item["node_path"]}: {item["message"]}')


def main():
    args = _parse_args()
    if not args.dataflow and not args.source:
        bc.emit_error('错误: 需要 --dataflow 或 --source 之一\n')
        sys.exit(2)
    with open(args.config, encoding='utf-8') as stream:
        config = json.load(stream)
    try:
        dataflow = _load_dataflow(args)
    except DataflowInputError as error:
        bc.emit_error(f'{error}\n')
        sys.exit(2)
    report = _build_report(args, config, dataflow, _load_manifest(args.manifest))
    _emit_report(report, args)
    sys.exit(1 if report['error_count'] else 0)


if __name__ == '__main__':
    main()
