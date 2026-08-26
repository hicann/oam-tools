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
"""Derive the ground-truth dataflow graph of a module's forward() from its AST.

The point of this script is that forward() *is* the dataflow graph. Asking an AI to
read the source and then attest "the residual paths are correct" throws away a free,
machine-checkable ground truth. Here we recover it deterministically:

  * every statement is reduced to (writes, reads, called submodule)
  * every read is resolved to the *last writer* of that variable
  * a merge (`a + b + c`) records its operand count and each operand's last writer
  * a variable read by 2+ later calls before being overwritten is a fork (parallel branch)
  * a variable written early and read much later is a shortcut, and the number of
    intervening calls is its overlap window

Output is `dataflow_source.json`, consumed by check_dataflow.py.

Scope and honesty: this handles the straight-line `forward()` shape that transformer
decoder layers overwhelmingly use (assignments, tuple assignments, submodule calls,
binary merges). Control flow is classified rather than uniformly rejected, because
"unsupported" is not one thing:

  * `config_gated`   the test reads only construction-time config/flags, so exactly one
                     branch runs for a given deployment. Each branch is extracted as a
                     named variant; a caller states which one its profile selected.
  * `data_dependent` the test reads a tensor//runtime value, so the graph genuinely varies
                     per token. Needs an explicit deviation declaration.
  * `unparsable`     reflection, dynamic dispatch, or a construct this reducer cannot read.

Only the latter two land in `unsupported`. Treating a quantisation-mode `if` as
unsupported made every real model report its main compute as unextractable, which is
what forced callers to hand-declare the very edges this script exists to derive.
"""
import argparse
import ast
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import breakdown_common as bc  # noqa: E402


class _Unsupported(Exception):
    """Raised when a construct would make the derived graph unsound."""


#: Names that mark a branch test as selecting an execution *mode* rather than reading data.
#: These are passed down the call stack as plain booleans by every runner in this family
#: (prefill vs decode, graph-capture vs eager), so a given profile fixes them before the
#: first token. They are recorded as the variant's condition, never silently resolved.
MODE_FLAG_HINTS = ('is_prefill', 'is_decode', 'prefill', 'decode', 'use_aclgraph',
                   'aclgraph', 'is_graph', 'capture', 'warmup', 'training', 'is_train')

#: Attribute reads whose value is fixed when the module is constructed. `self.<name>` set
#: from a config field cannot change between invocations, so a branch on it is one static
#: choice per deployment rather than a fork in the dataflow.
CONFIG_ATTR_HINTS = ('size', 'mode', 'enable', 'enabled', 'use_', 'is_moe', 'n_', 'num_',
                     'quant', 'dtype', 'tp', 'ep', 'pp', 'cp', 'dp', 'experts', 'offload',
                     'streams', 'eplb', 'absorb', 'fused', 'impl', 'backend', 'version')


def _test_kind(test):
    """Classify a branch test as 'config_gated', 'data_dependent' or 'unparsable'.

    The distinction that matters: does this test's value get fixed before the run, or does
    it depend on the tensors flowing through? A quantisation mode or a TP size is the
    former; a value read out of a tensor is the latter.
    """
    names, attributes, calls = [], [], []
    for node in ast.walk(test):
        if isinstance(node, ast.Call):
            calls.append(_attr_path(node.func))
        elif isinstance(node, ast.Attribute):
            path = _attr_path(node)
            if path.startswith('self.'):
                attributes.append(path[len('self.'):])
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id != 'self':
                names.append(node.id)

    # A call inside the test can do anything (`.item()`, `.any()`, a predicate on a tensor),
    # so it is only safe when it is a plain size/shape query on a config-shaped attribute.
    for call in calls:
        tail = call.rsplit('.', 1)[-1]
        if tail not in ('len', 'int', 'bool', 'getattr'):
            return 'data_dependent'

    def _is_config_attr(name):
        low = name.lower()
        return any(hint in low for hint in CONFIG_ATTR_HINTS)

    def _is_mode_flag(name):
        low = name.lower()
        return any(hint in low for hint in MODE_FLAG_HINTS)

    if not names and not attributes:
        return 'config_gated'  # a literal test, e.g. `if True:`
    if all(_is_config_attr(a) or _is_mode_flag(a) for a in attributes) and \
       all(_is_mode_flag(n) for n in names):
        return 'config_gated'
    return 'data_dependent'


def _attr_path(node):
    """Render `self.self_attn[0]` / `self.mlp` as a stable dotted string."""
    if isinstance(node, ast.Attribute):
        base = _attr_path(node.value)
        return f'{base}.{node.attr}' if base else node.attr
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        base = _attr_path(node.value)
        index = node.slice
        if isinstance(index, ast.Constant):
            return f'{base}[{index.value}]'
        if isinstance(index, ast.Name):
            return f'{base}[{index.id}]'
        return f'{base}[?]'
    if isinstance(node, ast.Call):
        return _attr_path(node.func)
    return ''


def _names_read(node):
    """Local variable names read anywhere inside an expression.

    `self` is dropped: it appears in every submodule call (`self.mlps[0](x)`) as the
    base of the callee path, never as a dataflow value, so keeping it would make
    every call look like it reads a shared tensor.
    """
    names = []
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            if child.id == 'self':
                continue
            names.append(child.id)
    return names


#: Producer id for a value that enters forward() as an argument. Call ids are
#: non-negative indices into `calls`, so -1 can never collide with one, and it stays
#: sortable alongside them. Consumers read it as "produced by the caller, upstream of
#: every node in this method".
INPUT = -1


def _parameter_names(func):
    """Names bound by forward()'s signature (excluding `self`).

    Only these get the INPUT producer. A read of some other unwritten name is a global
    or a constant, not a tensor crossing this method's input boundary.
    """
    spec = func.args
    names = []
    for group in (getattr(spec, 'posonlyargs', []), spec.args, spec.kwonlyargs):
        names.extend(argument.arg for argument in group)
    for extra in (spec.vararg, spec.kwarg):
        if extra is not None:
            names.append(extra.arg)
    return {name for name in names if name != 'self'}


def _targets_written(target):
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        written = []
        for element in target.elts:
            written.extend(_targets_written(element))
        return written
    return []


def _call_of(value):
    """The outermost submodule call in an expression, if any."""
    if isinstance(value, ast.Call):
        return value
    return None


def _merge_operands(value):
    """Flatten `a + b + c` into [a, b, c]; return None when not an add-merge."""
    if not isinstance(value, ast.BinOp) or not isinstance(value.op, ast.Add):
        return None
    operands = []

    def flatten(node):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            flatten(node.left)
            flatten(node.right)
        else:
            operands.append(node)

    flatten(value)
    return operands


def _self_attribute_name(target):
    if not isinstance(target, ast.Attribute) or not isinstance(target.value, ast.Name):
        return None
    return target.attr if target.value.id == 'self' else None


def _module_list_argument_size(argument):
    if isinstance(argument, (ast.List, ast.Tuple)):
        return len(argument.elts)
    if not isinstance(argument, (ast.ListComp, ast.GeneratorExp)):
        return None
    iterable = argument.generators[0].iter
    if isinstance(iterable, (ast.List, ast.Tuple)):
        return len(iterable.elts)
    if not isinstance(iterable, ast.Call) or _attr_path(iterable.func) != 'range':
        return None
    if iterable.args and isinstance(iterable.args[0], ast.Constant):
        return iterable.args[0].value
    return None


def _declared_size(value):
    if not isinstance(value, ast.Call) or not _attr_path(value.func).endswith('ModuleList'):
        return 1
    if not value.args:
        return None
    return _module_list_argument_size(value.args[0])


def _submodules(class_node):
    """Map attribute name -> declared size from __init__ (ModuleList length or 1)."""
    declared = {}
    init = next((node for node in class_node.body
                 if isinstance(node, ast.FunctionDef) and node.name == '__init__'), None)
    if init is None:
        return declared
    for node in ast.walk(init):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            attribute = _self_attribute_name(target)
            if attribute:
                declared[attribute] = _declared_size(node.value)
    return declared


class ForwardGraph:
    """Reduce one forward() body to a call sequence plus resolved dataflow edges."""

    def __init__(self, class_name, func):
        self.class_name = class_name
        self.func = func
        self.calls = []           # ordered submodule invocations
        self.merges = []          # add-merges with resolved operands
        self.unsupported = []     # constructs that would make the graph unsound
        self.variants = []        # config-gated branch arms, selected per execution profile
        self.loops = []           # submodule loops (repeated blocks) on the main path
        self.last_writer = {}     # variable -> call id that last wrote it
        self.reads_of = {}        # (variable, writer) -> [call ids that read it]
        self.parameters = _parameter_names(func)
        self.returns = []
        self.forks = []
        self.shortcuts = []

    def build(self):
        for statement in self.func.body:
            self._statement(statement)
        self._mark_forks()
        return self

    def edges(self):
        """Derived edges: (from_call, to_call, via variable, type)."""
        fork_keys = {(f['variable'], f['from_call']) for f in self.forks}
        shortcut_keys = {(s['variable'], s['from_call'], s['to_call'])
                         for s in self.shortcuts}
        merge_ids = {m['call_id'] for m in self.merges}
        derived = []
        for call in self.calls:
            for read in call['reads']:
                source = read.get('from_call')
                variable = read.get('variable')
                if source is None or variable is None:
                    continue
                if (variable, source, call['call_id']) in shortcut_keys:
                    edge_type = 'shortcut'
                elif call['call_id'] in merge_ids:
                    edge_type = 'residual'
                elif (variable, source) in fork_keys:
                    edge_type = 'parallel_branch'
                else:
                    edge_type = 'activation'
                derived.append({
                    'from_call': source,
                    'to_call': call['call_id'],
                    'via': variable,
                    'type': edge_type,
                })
        return derived

    def to_dict(self):
        return {
            'class_name': self.class_name,
            'method': self.func.name,
            'forward_lineno': self.func.lineno,
            'calls': self.calls,
            'edges': self.edges(),
            'merges': self.merges,
            'forks': self.forks,
            'shortcuts': self.shortcuts,
            'returns': self.returns,
            'variants': self.variants,
            'loops': self.loops,
            'unsupported': self.unsupported,
        }

    def _record_reads(self, value, call_id, skip=()):
        """Resolve every name read in `value` to its last writer.

        `call_id is None` means "read by something that is not a call node" (today:
        the return statement). Such a read still needs provenance in the output, but
        it must never enter `reads_of` — those lists are call ids and get sorted.

        A name with no writer that IS a forward() parameter still has a producer: the
        caller. It is filed under the INPUT sentinel so that two submodules reading the
        same input tensor register as a fork. Without this, the most common parallel
        shape in MoE code -- `shared_expert(hidden_states)` beside `gate(hidden_states)`,
        both reading the layer input -- looks like a chain, which is exactly the defect
        the fork check exists to catch. Names that are neither written nor parameters
        (globals, module constants) are left unresolved: they are not tensors on this
        graph's input boundary and inventing a producer for them would fabricate edges.
        """
        resolved = []
        for name in _names_read(value):
            if name in skip:
                continue
            writer = self.last_writer.get(name)
            resolved.append({'variable': name, 'from_call': writer})
            if call_id is None:
                continue
            if writer is not None:
                self.reads_of.setdefault((name, writer), []).append(call_id)
            elif name in self.parameters:
                self.reads_of.setdefault((name, INPUT), []).append(call_id)
        return resolved

    def _record_fused_merge(self, entry, writes, reads_expr, statement):
        """Record a residual join performed *inside* a called submodule.

        The `a + b` form is the minority in production transformer code. The dominant shape
        is a fused norm that both consumes and returns the residual:

            hidden, residual = self.input_layernorm(hidden, past_residual)

        The add happens inside the kernel, so there is no BinOp to find — which is why a
        BinOp-only reducer reports zero merges on a model whose every layer has two
        residuals. The join is still observable: a call that reads a residual-carrying
        variable and writes one is a merge point, and the tensor it carried in is the
        bypassed path. Recording it here is what lets a checker verify residual topology
        without asking anyone to hand-declare it.
        """
        if reads_expr is None:
            return
        read_vars = [r['variable'] for r in entry['reads'] if r.get('variable')]
        carried = [v for v in read_vars if 'residual' in v.lower()]
        produced = [w for w in writes if 'residual' in w.lower()]
        if not carried or not produced:
            return
        operands = [r for r in entry['reads']
                    if r.get('variable') in carried or r.get('variable') in read_vars]
        self.merges.append({
            'call_id': entry['call_id'],
            'lineno': statement.lineno,
            'kind': 'fused_in_call',
            'symbol': entry['symbol'],
            'operand_count': len(operands),
            'operands': operands,
            'carries_in': carried,
            'writes': list(writes),
            'note': '残差在被调用模块内部相加（fused add-norm），源码中没有独立的 `a + b`；'
                    '合并点即该调用本身',
        })

    def _add_call(self, symbol, writes, reads_expr, node, kind='call'):
        call_id = len(self.calls)
        entry = {
            'call_id': call_id,
            'kind': kind,
            'symbol': symbol,
            'lineno': node.lineno,
            'writes': writes,
            'reads': self._record_reads(reads_expr, call_id) if reads_expr is not None else [],
        }
        self.calls.append(entry)
        for name in writes:
            self.last_writer[name] = call_id
        return entry

    def _statement(self, statement):
        if isinstance(statement, (ast.Expr, ast.Pass)) and not _call_of(
                getattr(statement, 'value', None)):
            return
        if isinstance(statement, ast.Return):
            self._returns(statement)
            return
        if isinstance(statement, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
            self._control_flow(statement)
            return
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            self._assign(statement)
            return
        if isinstance(statement, ast.AugAssign):
            self._aug_assign(statement)
            return
        if isinstance(statement, ast.Expr):
            call = _call_of(statement.value)
            if call is not None:
                self._add_call(_attr_path(call.func), [], statement.value, statement)
            return

    def _control_flow(self, statement):
        loop_targets = set()
        if isinstance(statement, ast.For):
            loop_targets = set(_targets_written(statement.target))
        contains_call = any(
            isinstance(node, ast.Call)
            and (_attr_path(node.func).startswith('self.')
                 or _attr_path(node.func).split('[')[0].split('.')[0] in loop_targets)
            for node in ast.walk(statement))
        if not contains_call:
            return

        # A loop over submodules is the repeated-block construct, not a variant: every
        # iteration runs. Extract the body once and record the iteration count separately.
        if isinstance(statement, (ast.For, ast.While)):
            self._loop(statement)
            return
        if not isinstance(statement, ast.If):
            self._record_unsupported_control(statement)
            return

        kind = _test_kind(statement.test)
        condition = ast.unparse(statement.test)
        if kind != 'config_gated':
            self._record_data_dependent_branch(statement, condition)
            return

        self._record_config_variants(statement, condition)

    def _record_unsupported_control(self, statement):
        construct = type(statement).__name__
        self.unsupported.append({
            'lineno': statement.lineno,
            'construct': construct,
            'severity': 'unparsable',
            'reason': f'{construct} 包含 submodule 调用，此 reducer 无法确定其执行语义；'
                      f'需要显式 deviation 声明',
        })

    def _record_data_dependent_branch(self, statement, condition):
        self.unsupported.append({
            'lineno': statement.lineno,
            'construct': 'If',
            'severity': 'data_dependent',
            'condition': condition,
            'reason': f'分支条件 `{condition}` 依赖运行期数据，展开后的数据流图不可靠；'
                      f'需要在 config 中以 deviations 显式声明所走分支',
        })

    def _record_variant_arm(self, statement, branch_id, label, body, condition):
        if not body:
            return
        calls_before = len(self.calls)
        saved_writers = dict(self.last_writer)
        for inner in body:
            self._statement(inner)
        produced = list(range(calls_before, len(self.calls)))
        if not produced:
            self.last_writer = saved_writers
            return
        for call_id in produced:
            self.calls[call_id]['variant'] = {'branch_id': branch_id, 'arm': label}
        self.variants.append({
            'branch_id': branch_id,
            'arm': label,
            'lineno': statement.lineno,
            'condition': condition,
            'selected_by': 'execution_profile',
            'call_ids': produced,
        })
        if label == 'then' and statement.orelse:
            self.last_writer = saved_writers

    def _record_config_variants(self, statement, condition):
        branch_id = len(self.variants)
        for label, body in (('then', statement.body), ('else', statement.orelse)):
            self._record_variant_arm(statement, branch_id, label, body, condition)

    def _loop(self, statement):
        """A `for`/`while` whose body calls submodules: the repeated-block construct.

        Every iteration executes, so the body belongs on the main path. What the graph must
        not claim is a specific iteration count when the bound is dynamic — that is recorded
        as metadata, not as flattened repetition.
        """
        iterable = ast.unparse(statement.iter) if isinstance(statement, ast.For) else \
            ast.unparse(statement.test)
        calls_before = len(self.calls)
        for inner in statement.body:
            self._statement(inner)
        produced = list(range(calls_before, len(self.calls)))
        if not produced:
            return
        for call_id in produced:
            self.calls[call_id]['loop'] = {'loop_id': len(self.loops)}
        self.loops.append({
            'loop_id': len(self.loops),
            'lineno': statement.lineno,
            'construct': type(statement).__name__,
            'iterates_over': iterable,
            'call_ids': produced,
            'note': '循环体每次迭代都执行，属于主路径；迭代次数由运行期决定，'
                    '不在此处展开为固定次数',
        })

    def _assign(self, statement):
        targets = (statement.targets if isinstance(statement, ast.Assign)
                   else [statement.target])
        writes = []
        for target in targets:
            writes.extend(_targets_written(target))
        value = statement.value

        operands = _merge_operands(value)
        if operands is not None and len(operands) >= 2:
            # Resolve operands against the last_writer state BEFORE this merge is added:
            # `h = residual + h + shortcut` reads the h written upstream, not itself.
            call_id = len(self.calls)
            resolved = []
            for operand in operands:
                names = _names_read(operand)
                primary = names[0] if names else None
                writer = self.last_writer.get(primary) if primary else None
                resolved.append({
                    'variable': primary,
                    'from_call': writer,
                    'expression': ast.unparse(operand),
                })
                if primary is not None and writer is not None:
                    self.reads_of.setdefault((primary, writer), []).append(call_id)
            entry = self._add_call('<merge>', writes, None, statement, kind='merge')
            entry['reads'] = resolved
            self.merges.append({
                'call_id': entry['call_id'],
                'lineno': statement.lineno,
                'operand_count': len(operands),
                'operands': resolved,
                'writes': writes,
            })
            return

        call = _call_of(value)
        if call is not None:
            symbol = _attr_path(call.func)
            # `h = self.mlps[0](h)` reads the PREVIOUS writer of h and then rebinds it.
            # _add_call resolves reads before updating last_writer, so in-place rebinding
            # needs no special case — and the read must be kept, it is the activation edge.
            entry = self._add_call(symbol, writes, value, statement)
            self._record_fused_merge(entry, writes, value, statement)
            return

        # Plain rebinding (`x = y`) — propagate provenance without inventing a node.
        names = _names_read(value)
        if len(names) == 1 and writes:
            source = self.last_writer.get(names[0])
            for name in writes:
                if source is None:
                    self.last_writer.pop(name, None)
                else:
                    self.last_writer[name] = source

    def _aug_assign(self, statement):
        """`hidden += residual` is a two-operand merge written in place.

        Reducing it to a plain read would lose the join: the target is both an operand and
        the result, so the residual edge into it disappears and the layer reads as a chain.
        """
        writes = _targets_written(statement.target)
        if not writes or not isinstance(statement.op, ast.Add):
            return
        target_name = writes[0]
        call_id = len(self.calls)
        resolved = []
        for name in [target_name] + _names_read(statement.value):
            writer = self.last_writer.get(name)
            resolved.append({'variable': name, 'from_call': writer,
                             'expression': name if name == target_name
                             else ast.unparse(statement.value)})
            if writer is not None:
                self.reads_of.setdefault((name, writer), []).append(call_id)
        entry = self._add_call('<merge>', writes, None, statement, kind='merge')
        entry['reads'] = resolved
        self.merges.append({
            'call_id': entry['call_id'],
            'lineno': statement.lineno,
            'kind': 'in_place_add',
            'operand_count': len(resolved),
            'operands': resolved,
            'writes': writes,
        })

    def _returns(self, statement):
        """Record what the function hands back.

        `return self.head(x)` is a real submodule invocation and must become a call
        node — dropping it would silently lose the last op of any forward() that
        returns a call directly.
        """
        if statement.value is None:
            self.returns = []
            return
        call = _call_of(statement.value)
        if call is not None:
            entry = self._add_call(_attr_path(call.func), [], statement.value, statement)
            self.returns = [{'variable': None, 'from_call': entry['call_id']}]
            return
        self.returns = self._record_reads(statement.value, None)

    def _mark_forks(self):
        """A value read by 2+ later calls before being overwritten is a fork.

        `from_call` is INPUT when the forked value is a forward() argument: the two
        readers are still parallel consumers of one tensor, which is what a fork means.
        """
        self.forks = []
        for (variable, writer), readers in sorted(self.reads_of.items()):
            unique = sorted(set(readers))
            if len(unique) < 2:
                continue
            self.forks.append({
                'variable': variable,
                'from_call': writer,
                'read_by_calls': unique,
                'branch_count': len(unique),
                'from_input': writer == INPUT,
            })
        # A shortcut is ANY edge whose consumer is far downstream of its producer —
        # not only a forked one. LongCat's `shortcut_mlp_output` (written by self.mlp,
        # read 6 calls later by the three-way merge) has exactly one reader, and it is
        # the ScMoE overlap window: the compute the all-to-all can hide behind.
        self.shortcuts = []
        for (variable, writer), readers in sorted(self.reads_of.items()):
            if writer == INPUT:
                # An overlap window is a span between two calls: work that can hide behind
                # the producer's latency. A method argument is produced before any call in
                # this method, so there is no window here to report.
                continue
            for reader in sorted(set(readers)):
                span = reader - writer
                if span >= 3:
                    self.shortcuts.append({
                        'variable': variable,
                        'from_call': writer,
                        'to_call': reader,
                        'overlap_window_calls': span,
                        'overlapped_calls': list(range(writer + 1, reader)),
                    })


def extract_file(path, class_names=None, forward_name='forward', include_variants=True):
    """Extract one graph per (class, forward-ish method).

    `include_variants` also picks up `forward_absorb` / `forward_w8a8int8` style siblings.
    These are not alternative spellings of `forward` — they are the methods a deployment
    actually runs, selected by config at construction time. Analysing only `forward` reports
    the dispatcher and misses every op in the method that executed.
    """
    with open(path, encoding='utf-8') as stream:
        tree = ast.parse(stream.read(), filename=path)
    modules = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if class_names and node.name not in class_names:
            continue
        methods = []
        for item in node.body:
            if not isinstance(item, ast.FunctionDef):
                continue
            is_variant = include_variants and item.name.startswith(forward_name + '_')
            if item.name == forward_name or is_variant:
                methods.append(item)
        if not methods:
            continue
        submodules = _submodules(node)
        for func in methods:
            graph = ForwardGraph(node.name, func).build().to_dict()
            graph['submodules'] = submodules
            graph['source_path'] = path
            graph['is_primary'] = func.name == forward_name
            modules.append(graph)
    return modules


def main():
    parser = argparse.ArgumentParser(
        description='Derive the ground-truth dataflow graph of forward() from the AST')
    parser.add_argument('-s', '--source', required=True, action='append',
                        help='model source file (repeatable)')
    parser.add_argument('--class', dest='classes', action='append',
                        help='limit extraction to these class names (repeatable)')
    parser.add_argument('--forward-name', default='forward',
                        help='method to analyse (default: forward)')
    parser.add_argument('--no-variants', action='store_true',
                        help='only analyse the exact --forward-name, skipping forward_* siblings')
    parser.add_argument('-o', '--output')
    args = parser.parse_args()

    modules = []
    for path in args.source:
        if not os.path.exists(path):
            bc.emit_error(f'错误: 文件不存在: {path}\n')
            sys.exit(2)
        modules.extend(extract_file(path, args.classes, args.forward_name,
                                    include_variants=not args.no_variants))

    # Report the two severities separately: a config-gated branch is extracted, so counting it
    # as unsupported is what previously made a fully-readable model look unreadable.
    blocking = 0
    for module in modules:
        for unsupported in module['unsupported']:
            if unsupported.get('severity') in ('data_dependent', 'unparsable'):
                blocking += 1
    report = {
        'schema_version': 2,
        'script': 'extract_dataflow.py',
        'forward_name': args.forward_name,
        'module_count': len(modules),
        'blocking_unsupported': blocking,
        'config_gated_variants': sum(len(m['variants']) for m in modules),
        'merge_count': sum(len(m['merges']) for m in modules),
        'modules': modules,
    }
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as stream:
            stream.write(text + '\n')
        bc.emit(f'dataflow 已写入: {args.output}  modules={len(modules)} '
              f'variants={report["config_gated_variants"]} '
              f'merges={report["merge_count"]} blocking={blocking}')
    else:
        bc.emit(text)


if __name__ == '__main__':
    main()
