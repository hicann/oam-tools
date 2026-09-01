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
"""Compare the AST-derived dataflow against the declared analysis config.

`forward()` IS the dataflow graph. A critique that says "the residual paths are correct" in
prose throws away a free, machine-checkable ground truth -- and a valid source
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
  D10 source-proven activation across distinct top-level owners requires explicit dataflow

Deliberately NOT here: model class names, kernel names, layer counts, family constants. The
comparison is between two graphs. Anything family-specific arrives as an adapter invariant
or a manifest capability, so a Dense model is never failed for lacking MoE branches.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract_dataflow  # noqa: E402
import breakdown_common as bc  # noqa: E402

#: Producer id the extractor uses for values arriving as forward() arguments. Read from
#: the extractor rather than restated, so the two cannot drift apart.
INPUT_CALL = getattr(extract_dataflow, 'INPUT', -1)


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

    def forms(value):
        singular = '_'.join(
            token[:-1] if token.endswith('s') and not token.endswith('ss') else token
            for token in value.split('_'))
        return {value, singular}

    return bool(left and right and any(
        left_form == right_form
        or left_form.endswith('_' + right_form)
        or left_form.startswith(right_form + '_')
        or right_form.endswith('_' + left_form)
        for left_form in forms(left)
        for right_form in forms(right)))


def _iter_branches(node):
    """Yield branch declarations from a structure and every nested container."""
    yield from (node.get('branches') or [])
    for child in node.get('children') or []:
        yield from _iter_branches(child)


def _call_depends_on(calls, consumer_id, producer_id):
    """Whether one extracted call transitively consumes another call's output."""
    producer_variant = (calls[producer_id].get('variant') or {}
                        if 0 <= producer_id < len(calls) else {})
    equivalent_producers = {producer_id}
    if producer_variant.get('branch_id') is not None:
        equivalent_producers.update(
            index for index, call in enumerate(calls)
            if (call.get('variant') or {}).get('branch_id')
            == producer_variant.get('branch_id'))
    pending = [consumer_id]
    seen = set()
    while pending:
        current = pending.pop()
        if current in seen or not (0 <= current < len(calls)):
            continue
        seen.add(current)
        for read in calls[current].get('reads') or []:
            source = read.get('from_call')
            if source in equivalent_producers:
                return True
            if isinstance(source, int) and source >= 0:
                pending.append(source)
    return False


def _variant_memberships(call):
    memberships = call.get('variant_memberships') or []
    if memberships:
        return memberships
    variant = call.get('variant') or {}
    return [variant] if variant.get('branch_id') is not None else []


def _consumers_are_dependency_ordered(calls, consumer_ids):
    """Return true when every distinct consumer pair is ordered by activation flow."""
    for offset, left in enumerate(consumer_ids):
        for right in consumer_ids[offset + 1:]:
            if _calls_mutually_exclusive(calls[left], calls[right]):
                continue
            if not (_call_depends_on(calls, left, right)
                    or _call_depends_on(calls, right, left)):
                return False
    return True


def _calls_mutually_exclusive(left, right):
    """Whether two calls belong to opposite arms of the same config-gated branch."""
    return any(
        left_variant.get('branch_id') is not None
        and left_variant.get('branch_id') == right_variant.get('branch_id')
        and left_variant.get('arm') != right_variant.get('arm')
        for left_variant in _variant_memberships(left)
        for right_variant in _variant_memberships(right))


def _selected_arms_for_profile(config, profile, module, all_source_paths):
    profiles = config.get('execution_profiles') or []
    selected_profile = None
    if isinstance(profile, str):
        selected_profile = next((item for item in profiles
                                 if item.get('id') == profile), None)
    elif isinstance(profile, dict):
        selected_profile = profile
    elif len(profiles) == 1:
        selected_profile = profiles[0]
    if not selected_profile:
        return None

    selected_arms = {}
    for selection in selected_profile.get('selected_variants') or []:
        for variant in module.get('variants') or []:
            same_condition = (not selection.get('condition')
                              or selection.get('condition') == variant.get('condition'))
            if same_condition and _source_ref_covers(
                    selection.get('source_ref'), module.get('source_path', ''),
                    variant.get('lineno'), all_source_paths):
                selected_arms[variant.get('branch_id')] = selection.get('arm')

    # Selecting a nested branch also selects the unique ancestor arm that contains it.
    # The extractor records every call's full membership ancestry, so infer only ancestors
    # whose arm is identical across every call in the explicitly selected variant arm.
    changed = True
    while changed:
        changed = False
        for variant in module.get('variants') or []:
            branch_id = variant.get('branch_id')
            if selected_arms.get(branch_id) != variant.get('arm'):
                continue
            ancestry = {}
            for call_id in variant.get('call_ids') or []:
                calls = module.get('calls') or []
                if not (0 <= call_id < len(calls)):
                    continue
                for membership in _variant_memberships(calls[call_id]):
                    ancestor_id = membership.get('branch_id')
                    if ancestor_id == branch_id:
                        continue
                    ancestry.setdefault(ancestor_id, set()).add(membership.get('arm'))
            for unsupported_id in variant.get('unsupported_ids') or []:
                unsupported_items = module.get('unsupported') or []
                if not (0 <= unsupported_id < len(unsupported_items)):
                    continue
                for membership in _variant_memberships(unsupported_items[unsupported_id]):
                    ancestor_id = membership.get('branch_id')
                    if ancestor_id == branch_id:
                        continue
                    ancestry.setdefault(ancestor_id, set()).add(membership.get('arm'))
            for ancestor_id, arms in ancestry.items():
                if ancestor_id not in selected_arms and len(arms) == 1:
                    selected_arms[ancestor_id] = next(iter(arms))
                    changed = True
    return selected_arms


def _active_for_selected_arms(item, selected_arms):
    if not selected_arms:
        return True
    return all(
        selected_arms.get(membership.get('branch_id'), membership.get('arm'))
        == membership.get('arm')
        for membership in _variant_memberships(item))


def _active_calls_for_profile(config, profile, module, all_source_paths):
    selected_arms = _selected_arms_for_profile(
        config, profile, module, all_source_paths)

    return [call for call in module.get('calls') or []
            if _active_for_selected_arms(call, selected_arms)]


def _module_for_profile(config, profile, module, all_source_paths):
    """Keep call ids stable while removing inactive-arm dataflow evidence."""
    active_calls = _active_calls_for_profile(
        config, profile, module, all_source_paths)
    active_ids = {call.get('call_id') for call in active_calls}
    selected_arms = _selected_arms_for_profile(
        config, profile, module, all_source_paths)
    active_unsupported = [
        item for item in module.get('unsupported') or []
        if _active_for_selected_arms(item, selected_arms)
    ]
    if (len(active_ids) == len(module.get('calls') or [])
            and len(active_unsupported) == len(module.get('unsupported') or [])):
        view = dict(module)
        view['_active_calls'] = active_calls
        return view

    calls = []
    for index, call in enumerate(module.get('calls') or []):
        call_id = call.get('call_id', index)
        if call_id not in active_ids:
            calls.append({'call_id': call_id, 'kind': 'inactive', 'symbol': '',
                          'lineno': call.get('lineno'), 'writes': [], 'reads': []})
            continue
        active_call = dict(call)
        active_call['reads'] = [
            read for read in call.get('reads') or []
            if read.get('from_call') in active_ids or read.get('from_call') in (None, INPUT_CALL)
        ]
        calls.append(active_call)

    merges = []
    for merge in module.get('merges') or []:
        if merge.get('call_id') not in active_ids:
            continue
        active_merge = dict(merge)
        active_merge['operands'] = [
            operand for operand in merge.get('operands') or []
            if operand.get('from_call') in active_ids
            or operand.get('from_call') in (None, INPUT_CALL)
        ]
        active_merge['operand_count'] = len(active_merge['operands'])
        merges.append(active_merge)

    forks = []
    for fork in module.get('forks') or []:
        producer = fork.get('from_call')
        if producer not in active_ids and producer != INPUT_CALL:
            continue
        readers = [call_id for call_id in fork.get('read_by_calls') or []
                   if call_id in active_ids]
        if len(readers) < 2:
            continue
        active_fork = dict(fork)
        active_fork['read_by_calls'] = readers
        active_fork['branch_count'] = len(readers)
        forks.append(active_fork)

    view = dict(module)
    view['calls'] = calls
    view['merges'] = merges
    view['forks'] = forks
    view['unsupported'] = active_unsupported
    view['_active_calls'] = [calls[call_id] for call_id in sorted(active_ids)]
    return view


def _source_ref_names_file(source_ref, source_path, all_source_paths=None):
    """Whether a declared ref resolves to this exact source file (ignoring the line).

    Separated from the line test because the two answer different questions. A ref naming
    *this* file with the wrong line is a checkable false claim; a ref naming a *different*
    file simply cannot be judged against this module, and treating the two alike would fail
    every config whose branches legitimately cite another file's structure.
    """
    parsed = bc.parse_source_ref(source_ref)
    if not parsed:
        return False
    declared_file = parsed[0]
    source_name = os.path.normcase(os.path.normpath(source_path or ''))
    declared_name = os.path.normcase(os.path.normpath(declared_file))
    if os.path.isabs(declared_name):
        matches = [source_name] if source_name == declared_name else []
    else:
        candidates = all_source_paths or [source_path]
        matches = [os.path.normcase(os.path.normpath(path)) for path in candidates
                   if (os.path.normcase(os.path.normpath(path)) == declared_name
                       or os.path.normcase(os.path.normpath(path)).endswith(
                           os.sep + declared_name))]
    # An ambiguous basename resolving to several files identifies none of them.
    return len(set(matches)) == 1 and matches[0] == source_name if matches else False


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
        matches = [os.path.normcase(os.path.normpath(path)) for path in candidates
                   if (os.path.normcase(os.path.normpath(path)) == declared_name
                       or os.path.normcase(os.path.normpath(path)).endswith(
                           os.sep + declared_name))]
    same_file = len(set(matches)) == 1 and matches[0] == source_name if matches else False
    return same_file and start <= lineno <= end


def _source_ref_overlaps(source_ref, source_path, start_lineno, end_lineno,
                         all_source_paths=None):
    """Whether a source range intersects one exact source construct."""
    parsed = bc.parse_source_ref(source_ref)
    if not parsed or not isinstance(start_lineno, int):
        return False
    if not _source_ref_names_file(source_ref, source_path, all_source_paths):
        return False
    _, start, end = parsed
    construct_end = end_lineno if isinstance(end_lineno, int) else start_lineno
    return start <= construct_end and end >= start_lineno


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


def _module_identity(symbol):
    """Return ``(base_name, static_index, is_indexed)`` for one source call.

    Only a literal integer subscript on the final module attribute creates an expanded
    identity. Dynamic subscripts remain folded because the AST does not prove which
    invocation they select. For example, ``self.attn[1]`` becomes ``('attn', 1, True)``
    while ``self.attn[layer_id]`` becomes ``('attn', None, True)``.
    """
    text = str(symbol)
    if text.startswith('self.'):
        text = text[len('self.'):]
    tail = text.rsplit('.', 1)[-1]
    match = re.fullmatch(r'([^\[]+)\[([+-]?[0-9]+)\]', tail)
    if match:
        return match.group(1), int(match.group(2)), True
    if '[' in tail:
        return tail.split('[', 1)[0], None, True
    return tail, None, False


def _source_call_name(symbol):
    """Canonical config-facing name for a source call with a proven static index."""
    base, index, _ = _module_identity(symbol)
    return f'{base}_{index}' if index is not None else base


def _config_name_matches_symbol(config_name, source_symbol, allow_next=False):
    """Match a config node to a source call without inventing index aliases.

    A folded ``attn`` node may represent ``self.attn[0]`` for backward compatibility.
    An expanded ``attn_0`` node only matches when the source itself contains the static
    ``[0]`` identity; ordinary modules whose names happen to end in ``_0`` are untouched.
    """
    declared = _leaf(config_name)
    if allow_next and declared.endswith('_next'):
        declared = declared[:-5]
    base, index, _ = _module_identity(source_symbol)
    return declared == base or (index is not None and declared == f'{base}_{index}')


def _matching_config_name(source_symbol, config_names):
    """Prefer an exact expanded node, then a compatible folded template node."""
    canonical = _source_call_name(source_symbol)
    if canonical in config_names:
        return canonical
    base, _, _ = _module_identity(source_symbol)
    return base if base in config_names else None


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
                producers.append(_source_call_name(calls[source_call].get('symbol')))
                producer_ids.append(source_call)
        call_id = merge.get('call_id')
        main_source = max(producer_ids) if producer_ids else None
        residual_producer_symbols = [
            (module.get('calls') or [])[source_call].get('symbol')
            for source_call in producer_ids if source_call != main_source
        ]
        residual_producers = [
            _source_call_name(symbol) for symbol in residual_producer_symbols
        ]
        at_symbol = ((module.get('calls') or [{}])[merge['call_id']].get('symbol')
                     if merge.get('call_id') is not None
                     and 0 <= merge.get('call_id', -1) < len(module.get('calls') or [])
                     else None)
        merges.append({
            'call_id': call_id,
            'kind': merge.get('kind', 'binop_add'),
            'lineno': merge.get('lineno'),
            'operand_count': merge.get('operand_count'),
            'producer_ids': producer_ids,
            'producers': producers,
            'residual_producers': residual_producers,
            'residual_producer_symbols': residual_producer_symbols,
            'at': _source_call_name(at_symbol) if at_symbol is not None else None,
            'at_symbol': at_symbol,
        })
    return merges


def _branch_matches_merge(branch, merge, positions, source_path=None,
                          all_source_paths=None):
    """Match a residual declaration to the exact source join it describes.

    A declared `source_ref` is treated as a claim about *which* join this is, not as
    decoration. If it does not cover the merge's line, the branch does not describe this
    merge -- otherwise a reference to a line that holds no join at all would still satisfy
    D1, and the residual would be recorded against source the reader cannot check. An
    absent `source_ref` is not penalised here (the evidence dimension owns that); only a
    present-and-wrong one disqualifies the match.
    """
    declared_ref = (branch.get('source_ref') or branch.get('code_ref') or '').strip()
    if declared_ref and _source_ref_names_file(
            declared_ref, source_path, all_source_paths):
        # In a fused add-norm chain the physical owner can be named
        # `input_layernorm_next`, so the endpoint name intentionally differs from the
        # source call. An exact source locator is the unambiguous binding in that case.
        endpoints = {
            _leaf(endpoint)
            for endpoint in [*(branch.get('inputs') or []), branch.get('output')]
            if endpoint
        }
        merge_name = merge.get('at')
        merge_symbol = merge.get('at_symbol') or merge_name
        touches_merge = any(
            _config_name_matches_symbol(endpoint, merge_symbol, allow_next=True)
            for endpoint in endpoints)
        output = _leaf(branch.get('output'))
        targets_merge = _config_name_matches_symbol(
            output, merge_symbol, allow_next=True)
        inputs = {_leaf(item) for item in branch.get('inputs') or []}
        residual_symbols = (merge.get('residual_producer_symbols')
                            or merge.get('residual_producers') or [])
        carries_residual = all(
            any(_config_name_matches_symbol(endpoint, producer, allow_next=True)
                for endpoint in inputs)
            for producer in residual_symbols)
        if merge_symbol == '<merge>':
            return (output in positions and carries_residual
                    and _source_ref_covers(
                        declared_ref, source_path, merge.get('lineno'),
                        all_source_paths))
        return (touches_merge and targets_merge and carries_residual
                and _source_ref_covers(declared_ref, source_path, merge.get('lineno'),
                                       all_source_paths))
    output = _leaf(branch.get('output'))
    merge_symbol = merge.get('at_symbol') or merge.get('at')
    if not _config_name_matches_symbol(output, merge_symbol):
        return False
    inputs = {_leaf(item) for item in branch.get('inputs') or []}
    residual_symbols = (merge.get('residual_producer_symbols')
                        or merge.get('residual_producers') or [])
    if residual_symbols:
        return all(any(_config_name_matches_symbol(endpoint, producer)
                       for endpoint in inputs)
                   for producer in residual_symbols)
    # A fused entry merge can carry a residual from the previous invocation, which the
    # current method has no producer call for. Its declaration must explicitly wrap from a
    # later child back to this join (or use the cross_invocation kind).
    if branch.get('kind') == 'cross_invocation':
        return True
    output_pos = positions.get(output)
    return output_pos is not None and any(
        positions.get(name, -1) > output_pos for name in inputs)


def _parallel_branch_matches_fork(branch, producer_name, consumers,
                                  source_computed=None, calls=None,
                                  consumer_ids=None, source_merges=None,
                                  source_path=None, all_source_paths=None):
    """Whether a parallel declaration names this fork rather than an unrelated edge.

    Two conditions, not one. The branch must touch the fork (an endpoint that is a real
    consumer or the producer), *and* its rejoin must be a value the source actually
    computes. Checking only the first let a declaration pair a genuine consumer with an
    invented rejoin node and clear the fork: the fork was then recorded as declared while
    the place the two paths actually come back together was never identified, which is the
    half of the parallel shape that downstream rendering depends on.

    `source_computed` is the set of module tails the source calls (plus its merge points).
    When it is not supplied the rejoin cannot be judged and only the fork-touch applies, so
    callers without source keep their previous behaviour rather than failing closed.
    """
    inputs = {_leaf(item) for item in branch.get('inputs') or []}
    output = _leaf(branch.get('output')) if branch.get('output') else None
    source_names = set(consumers)
    if not str(producer_name).startswith('<'):
        source_names.add(producer_name)
    endpoints = set(inputs) | ({output} if output else set())
    if not (endpoints & source_names):
        return False
    if source_computed is None:
        return True
    if not output:
        return False
    if calls is not None and consumer_ids is not None:
        if not set(consumers).issubset(inputs) or output in set(consumers):
            return False
        output_ids = [index for index, call in enumerate(calls)
                      if _config_name_matches_symbol(output, call.get('symbol'))]
        if output in source_computed and any(
                all(_call_depends_on(calls, output_id, consumer_id)
                    for consumer_id in consumer_ids)
                for output_id in output_ids):
            return True

        declared_ref = (branch.get('source_ref') or branch.get('code_ref') or '').strip()
        for merge in source_merges or []:
            if merge.get('at_symbol') != '<merge>':
                continue
            if not _source_ref_covers(
                    declared_ref, source_path, merge.get('lineno'), all_source_paths):
                continue
            producer_ids = merge.get('producer_ids') or []
            if all(any(
                    producer_id == consumer_id
                    or _call_depends_on(calls, producer_id, consumer_id)
                    for producer_id in producer_ids)
                    for consumer_id in consumer_ids):
                return True
        return False
    return output in source_computed


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
        symbols = [c.get('symbol') for c in (module.get('calls') or [])]
        score = sum(any(_config_name_matches_symbol(name, symbol, allow_next=True)
                        for symbol in symbols)
                    for name in names)
        if score > best_score:
            best, best_score = module, score
    return best, best_score


def _boundary_residual_edges(config, structure_key):
    """Residual edges that leave one structure through the top-level graph."""
    graph = config.get('dataflow') or {}
    source_ids = {
        node.get('id')
        for node in graph.get('nodes') or []
        if node.get('structure') == structure_key
    }
    return [
        edge
        for edge in graph.get('edges') or []
        if edge.get('kind') == 'residual'
        and edge.get('source') in source_ids
        and edge.get('source_port')
    ]


def _name_words(value):
    """Normalize a source symbol or config name without model-family assumptions."""
    leaf = _module_tail(value)
    snake = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', leaf)
    return tuple(part for part in re.split(r'[^a-zA-Z0-9]+', snake.lower()) if part)


def _top_level_name_matches(symbol, alias):
    source = _name_words(symbol)
    declared = _name_words(alias)
    if not source or not declared:
        return False
    if source == declared:
        return True
    shorter, longer = sorted((source, declared), key=len)
    return len(shorter) >= 2 and (
        longer[:len(shorter)] == shorter or longer[-len(shorter):] == shorter)


def _top_level_owners(config):
    owners = {}
    for collection_name in ('stages', 'structures'):
        for key, node in (config.get(collection_name) or {}).items():
            aliases = {key, node.get('name')}
            aliases.update(_structure_names(node))
            owners[f'{collection_name}.{key}'] = {alias for alias in aliases if alias}
    return owners


def _source_proven_top_level_edges(config, modules):
    """Find source activation edges whose endpoints map to distinct top-level owners."""
    owners = _top_level_owners(config)
    if len(owners) < 2:
        return []

    def owner_for(symbol):
        matches = [owner for owner, aliases in owners.items()
                   if any(_top_level_name_matches(symbol, alias) for alias in aliases)]
        return matches[0] if len(matches) == 1 else None

    proven = []
    for module in modules:
        calls = {call.get('call_id'): call for call in module.get('calls') or []}
        for edge in module.get('edges') or []:
            if edge.get('type') != 'activation':
                continue
            source_call = calls.get(edge.get('from_call'))
            target_call = calls.get(edge.get('to_call'))
            if not source_call or not target_call:
                continue
            source_owner = owner_for(source_call.get('symbol'))
            target_owner = owner_for(target_call.get('symbol'))
            if not source_owner or not target_owner or source_owner == target_owner:
                continue
            proven.append({
                'source_owner': source_owner,
                'target_owner': target_owner,
                'source_ref': (f'{os.path.basename(module.get("source_path", ""))}:'
                               f'{target_call.get("lineno", module.get("forward_lineno"))}'),
            })
    return proven


def check_dataflow(config, dataflow, manifest=None, profile=None,
                   strict_source_match=False):
    """Return (issues, detail). Absent evidence never manufactures a failure."""
    issues = []
    modules = list(dataflow.get('modules') or [])
    all_source_paths = [module.get('source_path', '') for module in modules]
    profile_modules = {
        id(module): _module_for_profile(
            config, profile, module, all_source_paths)
        for module in modules
    }
    structures = config.get('structures') or {}
    manifest = manifest or {}

    detail = {
        'source_modules': len(modules),
        'config_structures': len(structures),
        'matched': {},
        'unmatched': [],
        'source_merge_count': sum(len(m.get('merges') or []) for m in modules),
        'profile': profile,
    }

    # D8 runs BEFORE the no-source early return: it compares the config's `dataflow` block
    # against the config's own nodes and structures, so it needs no source at all. Leaving it
    # below the return meant a broken edge went unreported whenever source was unavailable --
    # exactly the runs where nothing else would catch it either.
    issues.extend(_check_declared_dataflow(config, structures, detail))

    if not modules:
        detail['note'] = ('dataflow_source.json 没有可用模块（源码未提供或全部不可解析）：'
                          '跳过源码对比，不据此判定配置正确')
        issues.append(_issue(
            'D0', 'warning', '<source>',
            'dataflow_source.json 没有可解析的源码模块；数据流与分支正确性不可验证，'
            '不得将该检查计为通过'))
        return issues, detail

    # Whole-model edges have no representation in `children` or structure-local branches.
    # Require the graph only when source proves a dependency across two distinct declared
    # owners; otherwise abstain instead of turning naming uncertainty into failure.
    proven_top_level_edges = (_source_proven_top_level_edges(config, modules)
                              if strict_source_match else [])
    detail['source_proven_top_level_edges'] = len(proven_top_level_edges)
    if proven_top_level_edges and not (config.get('dataflow') or {}).get('edges'):
        issue = _issue(
            'D10', 'error', 'dataflow.edges',
            '源码证明存在跨顶层模块的数据依赖，但候选未声明顶层 dataflow edges；'
            'children 只表示包含关系，下游不得据此猜测模型主干连线',
            evidence=[item['source_ref'] for item in proven_top_level_edges[:8]])
        issue['config_paths'] = ['$.stages', '$.structures']
        issue['repair_policy'] = {
            'owner_artifact': 'analysis_config',
            'repair_class': 'whole_model_dataflow',
            'allowed_targets': {'analysis_config': ['$.dataflow']},
            'required_evidence': [
                'candidate_nodes', 'source_snippets', 'raw_ops_slice',
            ],
        }
        issues.append(issue)

    # ---- D5 blocking unsupported must be declared as a deviation -------------------------
    declared_deviations = {
        (d.get('source_ref') or '').strip()
        for d in (config.get('deviations') or [])
    }
    for module in profile_modules.values():
        for unsupported in module.get('unsupported') or []:
            severity = unsupported.get('severity')
            if severity not in ('data_dependent', 'unparsable'):
                continue  # config_gated arms are extracted, not blocking
            source_path = module.get('source_path', '')
            lineno = unsupported.get('lineno')
            ref = f"{os.path.basename(source_path)}:{lineno}"
            if any(_source_ref_covers(d, source_path, lineno, all_source_paths)
                   for d in declared_deviations if d):
                continue
            issue = _issue(
                'D5', 'error', f"{module.get('class_name')}.{module.get('method')}",
                f"{ref} 的控制流依赖运行期数据（{unsupported.get('severity')}："
                f"{unsupported.get('condition') or unsupported.get('construct')}），"
                f"AST 无法确定实际数据流；必须在 config.deviations 中显式声明所走分支及理由",
                evidence=[ref, unsupported.get('reason', '')])
            issue['repair_policy'] = {
                'owner_artifact': 'analysis_config',
                'repair_class': 'candidate_deviation',
                'allowed_targets': {
                    'analysis_config': ['$.deviations'],
                },
                'required_evidence': [
                    'source_snippets', 'raw_ops_slice', 'candidate_nodes',
                ],
            }
            issues.append(issue)

    # ---- per-structure comparison --------------------------------------------------------
    matched_structures = []
    for key, structure in structures.items():
        source_module, score = _match_structure_to_module(key, structure, modules)
        if source_module is None or score == 0:
            detail['unmatched'].append(key)
            if strict_source_match and any(module.get('calls') for module in modules):
                issues.append(_issue(
                    'D9', 'error', f'structures.{key}',
                    f'structure {key!r} 无法与任何源码 forward 调用图匹配；'
                    f'正式源码校验不能把未解释的候选结构视为通过',
                    evidence=[m.get('class_name', '<unknown>') for m in modules[:8]]))
            continue
        module = profile_modules[id(source_module)]
        detail['matched'][key] = {
            'class_name': module.get('class_name'),
            'method': module.get('method'),
            'matched_children': score,
        }
        matched_structures.append((key, structure, module, score))
        order = _child_names(structure)
        positions = {name: i for i, name in enumerate(order)}
        branches = structure.get('branches') or []
        source_merges = _source_merges(module)
        residual_branches = [branch for branch in branches
                             if (branch.get('kind') or 'residual')
                             in ('residual', 'cross_invocation')]
        parallel_branches = [branch for branch in branches
                             if branch.get('kind') == 'parallel']

        # D1 every source merge needs its own residual declaration. Prefer matching the
        # source merge call to the branch output; only anonymous `<merge>` calls fall back
        # to one-for-one counting.
        available_branches = list(residual_branches)
        missing_merges = []
        module_source_path = module.get('source_path', '')
        for merge in source_merges:
            matched_index = next((index for index, branch in enumerate(available_branches)
                                  if _branch_matches_merge(branch, merge, positions,
                                                           module_source_path,
                                                           all_source_paths)), None)
            if matched_index is None:
                missing_merges.append(merge)
            else:
                available_branches.pop(matched_index)
        boundary_edges = list(_boundary_residual_edges(config, key))
        still_missing = []
        for merge in missing_merges:
            matched_index = next((
                index for index, edge in enumerate(boundary_edges)
                if _config_name_matches_symbol(
                    _leaf(edge.get('source_port')),
                    merge.get('at_symbol') or merge.get('at'))
                and _source_ref_covers(
                    edge.get('source_ref') or edge.get('code_ref'),
                    module_source_path, merge.get('lineno'), all_source_paths)
            ), None)
            if matched_index is None:
                still_missing.append(merge)
            else:
                boundary_edges.pop(matched_index)
        missing_merges = still_missing
        if missing_merges:
            structure_path = bc.json_path('structures', key)
            branches_path = bc.json_path('structures', key, 'branches')
            issue = _issue(
                'D1', 'error', branches_path[2:] if branches_path.startswith('$.')
                else branches_path,
                f'源码 {module.get("class_name")}.{module.get("method")} 有 '
                f'{len(source_merges)} 处残差汇合，但配置只覆盖了 '
                f'{len(source_merges) - len(missing_merges)} 处；未覆盖行 '
                f'{[m["lineno"] for m in missing_merges]}：'
                f'残差是变量传递、不体现在 children 顺序里，下游不允许推导，'
                f'因此架构图会缺失全部残差边',
                evidence=[f'{os.path.basename(module.get("source_path",""))}:{m["lineno"]}'
                          for m in missing_merges])
            issue['config_paths'] = [structure_path]
            issue['repair_policy'] = {
                'owner_artifact': 'analysis_config',
                'repair_class': 'complete_source_dataflow',
                'allowed_targets': {
                    'analysis_config': [branches_path],
                },
                'required_evidence': ['candidate_nodes', 'source_snippets'],
            }
            issues.append(issue)

        # D2/D3 a declared branch must bypass something, and in the source direction.
        for branch in branches:
            if (branch.get('kind') or 'residual') != 'residual':
                continue
            output = _leaf(branch.get('output'))
            for raw_source in branch.get('inputs') or []:
                source_name = _leaf(raw_source)
                if source_name not in positions or output not in positions:
                    continue  # G7/G5 own referential integrity; do not double-report
                i, j = positions[source_name], positions[output]
                span = order[i + 1:j] if i < j else order[i + 1:] + order[:j]
                if not span:
                    issues.append(_issue(
                        'D2', 'error', f'structures.{key}.branches',
                        f'残差分支 {branch.get("name")} 声明 {source_name}->{output}，'
                        f'两者之间没有被绕过的节点：起点取在主路径上（方向反了）'))
                    continue
                # D3 the bypassed span should contain at least one node the source actually
                # computes between the two ends. A span made only of nodes the source never
                # calls means the declaration was invented rather than read.
                called_symbols = [c.get('symbol') for c in (module.get('calls') or [])]
                if called_symbols and not any(
                        _config_name_matches_symbol(name, symbol)
                        for name in span for symbol in called_symbols):
                    issues.append(_issue(
                        'D3', 'warning', f'structures.{key}.branches',
                        f'残差分支 {branch.get("name")} 声明绕过 {span}，'
                        f'但源码 {module.get("method")} 未调用其中任何一个子模块：'
                        f'该分支可能不是从源码读出的',
                        evidence=sorted({_source_call_name(symbol)
                                         for symbol in called_symbols})[:8]))

        # D4 a source fork must not be flattened into a chain in the config.
        # The rejoin a parallel branch names has to be something the source computes, so the
        # set of called tails (plus join points) is collected once and handed to the matcher.
        source_symbols = [call.get('symbol') for call in module.get('calls') or []]
        source_computed = {
            name for name in positions
            if any(_config_name_matches_symbol(name, symbol)
                   for symbol in source_symbols)
        }
        source_computed |= {
            name for name in positions
            if any(_config_name_matches_symbol(
                name, merge.get('at_symbol') or merge.get('at'))
                for merge in source_merges if merge.get('at'))
        }
        remaining_parallel = list(parallel_branches)
        for fork in module.get('forks') or []:
            producer = fork.get('from_call')
            calls = module.get('calls') or []
            # A fork off the method's own input has no producing call: `hidden_states`
            # arrives from the caller and is read by two submodules. That is the canonical
            # shared-expert shape, so it must not be skipped for lacking a producer node --
            # the parallelism is between the consumers either way.
            from_input = bool(fork.get('from_input')) or producer == INPUT_CALL
            if not from_input and (producer is None
                                   or not (0 <= producer < len(calls))):
                continue
            producer_name = (f'<{fork.get("variable", "input")}>' if from_input
                             else _matching_config_name(
                                 calls[producer].get('symbol'), positions))
            consumer_pairs = [
                (call_id, _matching_config_name(
                    calls[call_id].get('symbol'), positions))
                for call_id in fork.get('read_by_calls') or []
                if 0 <= call_id < len(calls)
            ]
            # Config-gated arms may call the same module at two source locations. One
            # structure node represents those mutually-exclusive calls; they are not a fork.
            unique_present = {}
            for call_id, name in consumer_pairs:
                if name is not None and name in positions:
                    unique_present.setdefault(name, call_id)
            if len(unique_present) < 2:
                continue
            compatible_names = {
                left_name
                for left_name, left_id in unique_present.items()
                for right_name, right_id in unique_present.items()
                if left_name != right_name
                and not _calls_mutually_exclusive(calls[left_id], calls[right_id])
            }
            if len(compatible_names) < 2:
                continue
            if not from_input and producer_name not in positions:
                continue
            # A shared control/config input can be read by two modules that are nevertheless
            # ordered by the activation graph (attention -> norm -> MLP). Such a value does
            # not make the modules parallel, so let the activation dependency take priority.
            if _consumers_are_dependency_ordered(
                    calls, list(unique_present.values())):
                continue
            consumers = [name for _, name in consumer_pairs if name in compatible_names]
            present = list(compatible_names)
            # In the source, `present` all read the SAME value, so none of them may be
            # declared as a downstream step of another. Consecutive declaration order is
            # how a fork gets silently serialised (the shared-expert defect).
            ordered = sorted(present, key=lambda n: positions[n])
            chained = [(a, b) for a, b in zip(ordered, ordered[1:])
                       if positions[b] == positions[a] + 1]
            matched_index = next((index for index, branch in enumerate(remaining_parallel)
                                  if _parallel_branch_matches_fork(
                                      branch, producer_name, consumers,
                                      source_computed, calls,
                                      list(unique_present.values()), source_merges,
                                      module_source_path, all_source_paths)), None)
            if matched_index is not None:
                remaining_parallel.pop(matched_index)
            else:
                structure_path = bc.json_path('structures', key)
                branches_path = bc.json_path('structures', key, 'branches')
                where = (calls[min(fork.get('read_by_calls') or [0])].get('lineno')
                         if from_input else calls[producer].get('lineno'))
                issue = _issue(
                    'D4', 'warning', structure_path[2:] if structure_path.startswith('$.')
                    else structure_path,
                    f'源码中 {producer_name} 被 {sorted(set(present))} 并行读取'
                    f'（行 {where}），但配置没有为该 fork 单独声明 kind: parallel '
                    f'的 branch；相邻链 {chained} 会被下游渲染为串行',
                    evidence=[f'fork from {"input" if from_input else f"call {producer}"}'
                              f' ({fork.get("variable")}): {consumers}',
                              f'{os.path.basename(module_source_path)}:{where}'])
                issue['config_paths'] = [structure_path]
                issue['repair_policy'] = {
                    'owner_artifact': 'analysis_config',
                    'repair_class': 'declare_parallel_fork',
                    'allowed_targets': {
                        'analysis_config': [branches_path],
                    },
                    'required_evidence': ['candidate_nodes', 'source_snippets'],
                }
                issues.append(issue)

        # D6 only attributes calls to names declared as submodules in __init__. Helper methods
        # and library calls are deliberately excluded because the AST cannot call them modules.
        declared_submodules = set(module.get('submodules') or {})
        active_calls = module.get('_active_calls') or []
        structure_names = _structure_names(structure)
        fused_submodules = {
            merge.get('at')
            for merge in _source_merges(module)
            if merge.get('kind') == 'fused_in_call' and merge.get('at')
        }
        cross_invocation_names = {
            _leaf(endpoint)
            for branch in _iter_branches(structure)
            if branch.get('kind') == 'cross_invocation'
            for endpoint in [*(branch.get('inputs') or []), branch.get('output')]
            if endpoint
        }
        missing_submodules = set()
        for call in active_calls:
            symbol = call.get('symbol')
            root = _module_root(symbol)
            if root not in declared_submodules:
                continue
            base, index, _ = _module_identity(symbol)
            direct_indexed_root = base == root and index is not None
            represented = (any(_config_name_matches_symbol(name, symbol)
                               for name in structure_names)
                           if direct_indexed_root else root in structure_names)
            fused_alias = (root in fused_submodules and any(
                _config_name_matches_symbol(name, symbol, allow_next=True)
                for name in structure_names | cross_invocation_names))
            if not represented and not fused_alias:
                missing_submodules.add(_source_call_name(symbol)
                                       if direct_indexed_root else root)
        missing_submodules = sorted(missing_submodules)
        if missing_submodules:
            issues.append(_issue(
                'D6', 'error', f'structures.{key}',
                f'源码调用了已声明子模块 {missing_submodules}，但该 structure 中没有对应节点',
                evidence=[f'{module.get("class_name")}.{module.get("method")}']))

    # ---- D7 capability-asserted joins ----------------------------------------------------
    # Only runs for capabilities the manifest actually evidences. A model with no
    # `shared_expert` capability is never asked to have one.
    capabilities = {c.get('id'): c for c in (manifest.get('capabilities') or [])}
    # The requirements come from the manifest's `dataflow_invariants`, which the family
    # adapter declares. They are NOT listed here: a checker carrying its own family table
    # cannot abstain for a family it has never seen, and would have to be edited for every
    # new model. The fallback pair below is retained only for manifests written before
    # adapters emitted invariants.
    declared_invariants = [
        item
        for item in (manifest.get('dataflow_invariants') or [])
    ]
    fallback_invariants = [
        {'id': 'shared_expert_parallel', 'requires': 'shared_expert',
         'reason': 'a parallel expert path joining at the combine point'},
        {'id': 'sparse_index_attention_parallel', 'requires': 'sparse_index_attention',
         'reason': 'an indexer side path feeding attention'},
    ]
    best_score_by_module = {}
    for _, _, module, score in matched_structures:
        module_key = id(module)
        best_score_by_module[module_key] = max(
            score, best_score_by_module.get(module_key, 0))
    best_matches = [item for item in matched_structures
                    if item[3] == best_score_by_module[id(item[2])]]
    for invariant in declared_invariants or fallback_invariants:
        capability_id = invariant.get('requires')
        requirement = invariant.get('reason') or invariant.get('id') or ''
        if capability_id and capability_id not in capabilities:
            continue
        # A source reducer can deliberately leave a nested block unsupported (for example a
        # stream-switch `with` body) while the mapping declares the fork inside its owning
        # layer. Recognise that explicit nested declaration before consulting extracted
        # forks; D5 still requires a deviation for the unsupported source construct, and the
        # critique/source-ref gates still verify the semantic claim independently.
        declared_nested = any(
            branch.get('kind') == 'parallel'
            and _related_name(branch.get('name'), capability_id)
            and all(_leaf(endpoint) in _structure_names(structure)
                    for endpoint in [*(branch.get('inputs') or []),
                                     branch.get('output')]
                    if endpoint)
            and _source_ref_names_file(
                branch.get('source_ref') or branch.get('code_ref'),
                module.get('source_path', ''), all_source_paths)
            and any(
                _source_ref_overlaps(
                    branch.get('source_ref') or branch.get('code_ref'),
                    module.get('source_path', ''), unsupported.get('lineno'),
                    unsupported.get('end_lineno'), all_source_paths)
                and any(_source_ref_covers(
                    deviation, module.get('source_path', ''), unsupported.get('lineno'),
                    all_source_paths) for deviation in declared_deviations if deviation)
                for unsupported in module.get('unsupported') or []
                if unsupported.get('severity') in ('data_dependent', 'unparsable')
                and any(
                    _related_name(_module_tail(site.get('symbol')), capability_id)
                    and _source_ref_covers(
                        branch.get('source_ref') or branch.get('code_ref'),
                        module.get('source_path', ''), site.get('lineno'),
                        all_source_paths)
                    for site in unsupported.get('call_sites') or []))
            for structure in structures.values()
            for module in profile_modules.values()
            for branch in _iter_branches(structure)
        )
        if declared_nested:
            continue
        if invariant.get('kind') == 'min_call_occurrences':
            tokens = [str(token).lower() for token in invariant.get('match_any') or []]
            minimum = invariant.get('min_occurrences', 1)
            satisfied = False
            for _, structure, module, _ in best_matches:
                source_count = sum(
                    1 for call in module.get('calls') or []
                    if any(token in _module_tail(call.get('symbol')).lower()
                           for token in tokens))
                config_count = sum(
                    1 for name in _structure_names(structure)
                    if any(token in str(name).lower() for token in tokens))
                if source_count >= minimum and config_count >= minimum:
                    satisfied = True
                    break
        else:
            satisfied = False
            for _, structure, module, _ in best_matches:
                branches = [branch for branch in _iter_branches(structure)
                            if branch.get('kind') == 'parallel']
                calls = module.get('calls') or []
                invariant_names = _structure_names(structure)
                invariant_computed = {
                    name for name in invariant_names
                    if any(_config_name_matches_symbol(name, call.get('symbol'))
                           for call in calls)
                }
                invariant_computed |= {
                    name for name in invariant_names
                    if any(_config_name_matches_symbol(
                        name, merge.get('at_symbol') or merge.get('at'))
                        for merge in _source_merges(module) if merge.get('at'))
                }
                for fork in module.get('forks') or []:
                    producer = fork.get('from_call')
                    from_input = bool(fork.get('from_input')) or producer == INPUT_CALL
                    producer_name = (f'<{fork.get("variable", "input")}>' if from_input
                                     else _matching_config_name(
                                         calls[producer].get('symbol'), invariant_names)
                                     if isinstance(producer, int) and 0 <= producer < len(calls)
                                     else '<unknown>')
                    consumers = [_matching_config_name(
                                     calls[index].get('symbol'), invariant_names)
                                 for index in fork.get('read_by_calls') or []
                                 if 0 <= index < len(calls)]
                    consumers = [name for name in consumers if name is not None]
                    consumer_ids = [index for index in fork.get('read_by_calls') or []
                                    if 0 <= index < len(calls)]
                    if capability_id and not any(
                            _related_name(name, capability_id) for name in consumers):
                        continue
                    if any(_parallel_branch_matches_fork(
                            branch, producer_name, consumers, invariant_computed,
                            calls, consumer_ids)
                           and (not capability_id or any(
                               _related_name(name, capability_id)
                               for name in [branch.get('name'), branch.get('output'),
                                            *(branch.get('inputs') or [])]))
                           for branch in branches):
                        satisfied = True
                        break
                if satisfied:
                    break
        if not satisfied:
            invariant_name = capability_id or invariant.get('id', 'ungated')
            issues.append(_issue(
                'D7', 'error', f'dataflow_invariants.{invariant_name}',
                f'manifest 声明数据流约束 `{invariant_name}`（{requirement}），'
                f'但同一源码模块与 structure 中没有对应声明',
                evidence=[(capabilities.get(capability_id) or {}).get(
                    'source_ref', invariant.get('id', 'unknown'))]))

    detail['declared_deviations'] = len(declared_deviations)
    return issues, detail


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


def main():
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
    args = parser.parse_args()

    if not args.dataflow and not args.source:
        sys.stderr.write('错误: 需要 --dataflow 或 --source 之一\n')
        sys.exit(2)

    with open(args.config, encoding='utf-8') as stream:
        config = json.load(stream)

    if args.dataflow:
        with open(args.dataflow, encoding='utf-8') as stream:
            dataflow = json.load(stream)
    else:
        modules = []
        for path in args.source:
            if not os.path.exists(path):
                sys.stderr.write(f'错误: 文件不存在: {path}\n')
                sys.exit(2)
            modules.extend(extract_dataflow.extract_file(path))
        dataflow = {'schema_version': 2, 'modules': modules}

    manifest = None
    if args.manifest and os.path.exists(args.manifest):
        with open(args.manifest, encoding='utf-8') as stream:
            manifest = json.load(stream)

    issues, detail = check_dataflow(config, dataflow, manifest, args.profile)
    errors = [i for i in issues if i['severity'] == 'error']
    warnings = [i for i in issues if i['severity'] == 'warning']
    report = {
        'script': 'check_dataflow.py',
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
        print(f'dataflow 校验已写入: {args.output}  status={report["status"]} '
              f'errors={len(errors)} warnings={len(warnings)}')
    elif args.json:
        print(text)
    else:
        print(f'status={report["status"]} errors={len(errors)} warnings={len(warnings)}')
        for item in issues:
            print(f'  [{item["severity"]}] {item["id"]} {item["node_path"]}: {item["message"]}')

    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
