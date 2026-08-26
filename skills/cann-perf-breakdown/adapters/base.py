# Copyright (c) 2026 Huawei Technologies Co., Ltd.
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
"""Base adapter + generic AST extraction toolkit.

No model code is imported or executed (models may require torch_npu). Everything
here is pure `ast` static analysis over the source text.
"""
import ast
import os
from dataclasses import dataclass, field


@dataclass
class Fact:
    key: str
    value: object
    source_ref: str            # "file.py:line" or "unknown"
    method: str                # extraction_method enum value
    confidence: str            # high | medium | low | unknown

    def as_dict(self):
        return {
            'key': self.key,
            'value': self.value,
            'source_ref': self.source_ref,
            'method': self.method,
            'confidence': self.confidence,
        }


UNKNOWN = 'unknown'


@dataclass(frozen=True)
class ExtractionContext:
    config_tree: object
    modeling_tree: object
    config_defaults: dict
    base_dir: str
    config_path: str
    modeling_path: str

    def ref(self, lineno, path=None):
        return rel_ref(path or self.config_path, lineno, self.base_dir)


@dataclass
class ExtractionState:
    context: ExtractionContext
    facts: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    num_main: object = UNKNOWN
    pred_count: int = 0
    pred_key: str = None
    first_k_dense: int = None
    has_moe: bool = False
    moe_key_unbound: bool = False
    base_class_name: str = 'DecoderLayer'
    construct_ref: str = None
    layer_groups: list = field(default_factory=list)
    prediction_modules: list = field(default_factory=list)


def rel_ref(path, lineno, base=None, end=None):
    """Format a source_ref, made relative to `base` if possible."""
    p = path
    if base:
        try:
            p = os.path.relpath(path, base)
        except ValueError:
            p = path
    if end and end != lineno:
        return f'{p}:{lineno}-{end}'
    return f'{p}:{lineno}'


def _config_names_from_import(node):
    if not isinstance(node, ast.ImportFrom):
        return set()
    if 'config' not in (node.module or '').lower():
        return set()
    return {alias.name for alias in node.names if alias.name.endswith('Config')}


def config_classes_imported_by(modeling_tree):
    """Names imported from a sibling config module by the modeling source.

    LongCat's config file defines both LongcatFlashConfig (num_layers=61, the full
    Flash model) and LongcatFlashNgramConfig (num_layers=28), and the modeling file
    imports ONLY the latter. Picking by source order reads a class the model never
    instantiates, so the layer count is wrong before any other analysis begins.
    """
    if modeling_tree is None:
        return set()
    names = set()
    for node in ast.walk(modeling_tree):
        names.update(_config_names_from_import(node))
    return names


def _config_candidate(node):
    if not isinstance(node, ast.ClassDef) or not node.name.endswith('Config'):
        return None
    init_fn = next((item for item in node.body
                    if isinstance(item, ast.FunctionDef) and item.name == '__init__'), None)
    return node, init_fn


def _most_derived_config(candidates):
    base_names = set()
    for candidate, _init_fn in candidates:
        base_names.update(base.id for base in candidate.bases if isinstance(base, ast.Name))
    derived = [candidate for candidate in candidates if candidate[0].name not in base_names]
    return (derived or candidates)[0]


def find_config_class(tree, modeling_tree=None):
    """Return (ClassDef, __init__) for the config class the model actually uses.

    A config module may define several *Config classes for different model variants.
    The one the modeling source imports is the authoritative one; source order is not
    evidence of anything. Falls back to the first class with an __init__ when there is
    no import to go by, which is the single-class case.
    """
    candidates = []
    for node in ast.walk(tree):
        candidate = _config_candidate(node)
        if candidate is not None:
            candidates.append(candidate)
    if not candidates:
        return None, None

    imported = config_classes_imported_by(modeling_tree)
    with_init = [c for c in candidates if c[1] is not None]
    preferred = [c for c in with_init if c[0].name in imported]
    if preferred:
        # A subclass overrides its base's defaults, so the narrowest imported class wins.
        return _most_derived_config(preferred)
    return with_init[0] if with_init else candidates[0]


def extract_init_defaults(init_fn):
    """Return {arg_name: (literal_value, lineno)} for keyword defaults in an __init__."""
    out = {}
    args = init_fn.args
    defaults = args.defaults
    posargs = args.args
    # defaults align to the tail of posargs
    if defaults:
        offset = len(posargs) - len(defaults)
        for i, default in enumerate(defaults):
            name = posargs[offset + i].arg
            val = literal_or_none(default)
            if val is not None or isinstance(default, ast.Constant):
                out[name] = (val, getattr(default, 'lineno', init_fn.lineno))
    # kwonly
    for kw, default in zip(args.kwonlyargs, args.kw_defaults):
        if default is not None:
            out[kw.arg] = (literal_or_none(default), getattr(default, 'lineno', init_fn.lineno))
    return out


def literal_or_none(node):
    """Best-effort literal evaluation; returns None if not a simple literal."""
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return None


def find_range_calls_over_config(tree, attr_names):
    """
    Find `for <var> in range(... config.<attr> ...)` or `range(self.<attr>)` loops
    used to build ModuleList/ModuleDict of decoder layers.
    Returns list of dicts: {attr, lineno, is_moduledict}.
    """
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.comprehension):
            rng = node.iter
            attr = _range_attr(rng, attr_names)
            if attr:
                results.append({'attr': attr, 'lineno': getattr(rng, 'lineno', 0)})
        if isinstance(node, ast.For):
            attr = _range_attr(node.iter, attr_names)
            if attr:
                results.append({'attr': attr, 'lineno': getattr(node.iter, 'lineno', 0)})
    return results


def _range_attr(call, attr_names):
    """If call is range(<attr>) where attr resolves to one of attr_names, return the attr name."""
    if not isinstance(call, ast.Call):
        return None
    if not (isinstance(call.func, ast.Name) and call.func.id == 'range'):
        return None
    for arg in call.args:
        for sub in ast.walk(arg):
            if isinstance(sub, ast.Attribute) and sub.attr in attr_names:
                return sub.attr
    return None


def find_decoder_layer_classes(tree):
    """Return heuristic layer class names, DecoderLayer-suffixed prioritized over Block.

    A 'Block' can also match unrelated helper classes (e.g. Gemma4SparseMoeBlock),
    so DecoderLayer wins when both exist. Blocks named like MoE/MLP/Attention/Norm
    helpers are excluded from the Block fallback.
    """
    decoder_layers = []
    blocks = []
    helper_names = ('Moe', 'MLP', 'Mlp', 'Attention', 'Norm', 'Embed', 'Expert', 'Router', 'Gate')
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if node.name.endswith('DecoderLayer'):
                decoder_layers.append((node.name, node.lineno))
            elif node.name.endswith('Block') and not any(h in node.name for h in helper_names):
                blocks.append((node.name, node.lineno))
    return decoder_layers if decoder_layers else blocks


def _callee_name(call):
    """Dotted name of a call's callee, e.g. `nn.ModuleList` -> 'nn.ModuleList'."""
    func = call.func
    parts = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
    return '.'.join(reversed(parts)) if parts else UNKNOWN


def _assignment_value(node, target_attr):
    if not isinstance(node, ast.Assign):
        return None
    if not any(isinstance(target, ast.Attribute) and target.attr == target_attr
               for target in node.targets):
        return None
    try:
        source = ast.unparse(node.value)
    except Exception:
        source = None
    return source, node.lineno


def find_predicate_assignment(tree, target_attr):
    """
    Find `self.<target_attr> = <expr>` and return (source_text_of_expr, lineno) if the
    expression references known predicate config keys. Returns (None, None) if absent.
    """
    for node in ast.walk(tree):
        assignment = _assignment_value(node, target_attr)
        if assignment is not None:
            return assignment
    return None, None


def _scan_source_evidence(source, evidence):
    if not source:
        return
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            evidence['class_names'].add(node.name)
        if isinstance(node, ast.FunctionDef) and node.name == '__init__':
            evidence['config_keys'].update(arg.arg for arg in node.args.args)
            evidence['config_keys'].update(arg.arg for arg in node.args.kwonlyargs)


def scan_evidence(config_src, modeling_src):
    """Cheap evidence scan (class names + config keys) for adapter selection."""
    ev = {'class_names': set(), 'config_keys': set()}
    for source in (config_src, modeling_src):
        _scan_source_evidence(source, ev)
    return ev


def _assignment_components(statement, modeling_path, base_dir):
    if not isinstance(statement, ast.Assign) or not isinstance(statement.value, ast.Call):
        return []
    components = []
    for target in statement.targets:
        is_self_attr = (isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == 'self')
        if not is_self_attr:
            continue
        components.append({
            'attr': target.attr,
            'constructor': _callee_name(statement.value),
            'source_ref': rel_ref(modeling_path or UNKNOWN, statement.lineno, base_dir),
        })
    return components


def _class_components(node, modeling_path, base_dir):
    init_fn = next((item for item in node.body
                    if isinstance(item, ast.FunctionDef) and item.name == '__init__'), None)
    if init_fn is None:
        return None
    components = []
    for statement in ast.walk(init_fn):
        components.extend(_assignment_components(statement, modeling_path, base_dir))
    return {
        'class_name': node.name,
        'source_ref': rel_ref(modeling_path or UNKNOWN, node.lineno, base_dir),
        'components': components,
    }


def _role_hint_candidate(lowered, role, hints):
    best = None
    for hint in hints:
        index = lowered.rfind(hint)
        if index < 0:
            continue
        candidate = (index + len(hint), len(hint), role, hint)
        if best is None or candidate[:2] > best[:2]:
            best = candidate
    return best


def _best_role_hint(attribute, role_hints):
    best = None
    lowered = attribute.lower()
    for role, hints in (role_hints or {}).items():
        candidate = _role_hint_candidate(lowered, role, hints)
        if candidate is not None and (best is None or candidate[:2] > best[:2]):
            best = candidate
    return None if best is None else (best[2], best[3])


def _first_integer_default(context, keys):
    for key in keys:
        if key not in context.config_defaults:
            continue
        value, lineno = context.config_defaults[key]
        if isinstance(value, int):
            return key, value, lineno
    return None


def _append_default_fact(state, found, confidence='high'):
    if found is None:
        return
    key, value, lineno = found
    state.facts.append(Fact(key, value, state.context.ref(lineno),
                            'ast_default_arg', confidence))


def _extract_layer_counts(adapter, state):
    main = _first_integer_default(state.context, adapter.main_layer_count_keys)
    if main is None:
        state.gaps.append('num_main_layers: 无法从 config 默认参数静态解析')
    else:
        _key, state.num_main, _line = main
        _append_default_fact(state, main)

    prediction = _first_integer_default(state.context, adapter.prediction_count_keys)
    if prediction is not None:
        state.pred_key, state.pred_count, _line = prediction
        _append_default_fact(state, prediction)

    dense = _first_integer_default(state.context, adapter.dense_boundary_keys)
    if dense is not None:
        _key, state.first_k_dense, _line = dense
        _append_default_fact(state, dense)


def _extract_moe_presence(adapter, state):
    defaults = state.context.config_defaults
    for key in adapter.moe_expert_keys:
        if key not in defaults:
            continue
        value, lineno = defaults[key]
        if isinstance(value, int) and value > 0:
            state.has_moe = True
            _append_default_fact(state, (key, value, lineno))
            return
        if value is None or value is False:
            state.moe_key_unbound = True
            _append_default_fact(state, (key, value, lineno), 'low')
            state.gaps.append(
                f'{key}: MoE 配置键存在但默认值为 {value}，无法静态判定是否启用 MoE。'
                f'该层组分类降为 low confidence；需由 checkpoint config.json 或 '
                f'trace 算子（MoeGatingTopK* / GroupedMatmul）判定')
            return


def _append_first_positive_fact(adapter, state, keys):
    defaults = state.context.config_defaults
    for key in keys:
        if key not in defaults:
            continue
        value, lineno = defaults[key]
        if isinstance(value, int) and value > 0:
            _append_default_fact(state, (key, value, lineno))
            return


def _extract_moe_dimensions(adapter, state):
    if not state.has_moe:
        return
    _append_first_positive_fact(adapter, state, adapter.shared_expert_keys)
    _append_first_positive_fact(adapter, state, adapter.experts_per_token_keys)


def _extract_layer_construction(adapter, state):
    context = state.context
    layer_classes = (find_decoder_layer_classes(context.modeling_tree)
                     if context.modeling_tree else [])
    range_calls = (find_range_calls_over_config(
        context.modeling_tree, set(adapter.main_layer_count_keys))
        if context.modeling_tree else [])
    state.base_class_name = layer_classes[0][0] if layer_classes else 'DecoderLayer'
    if not range_calls:
        state.gaps.append('main decoder ModuleList range(...) 构造未静态定位')
        return
    state.construct_ref = rel_ref(context.modeling_path, range_calls[0]['lineno'],
                                  context.base_dir)
    state.facts.append(Fact('main_layer_construction',
                            f"range({range_calls[0]['attr']})", state.construct_ref,
                            'ast_range_expr', 'high'))


class BaseAdapter:
    """Generic architecture extractor. Family adapters subclass and override hooks.

    Every family-specific constant belongs here rather than in a validator or a reference
    doc. A checker that knows a model family's module names cannot abstain for a family it
    has never seen, so the family knowledge is confined to these subclasses and the rest of
    the pipeline compares graphs.

    The class attributes below default to EMPTY on purpose in the generic base: an unknown
    family has no known config keys, and inheriting DeepSeek's names would make a Qwen model
    silently read as having a dense/MoE boundary it does not have. `main_layer_count_keys`
    is the one exception -- those four spellings cover essentially every HF-style config, and
    without any of them the generic adapter could not extract a layer count at all.
    """

    name = 'generic'

    # config keys this family uses for the main layer count (first match wins)
    main_layer_count_keys = ('num_hidden_layers', 'num_layers', 'n_layer', 'num_layer')
    # config keys for prediction/MTP module counts. Empty in the base: a model with no
    # prediction module must not be searched for one.
    prediction_count_keys = ()
    # dense/moe boundary predicate keys. Empty in the base for the same reason.
    dense_boundary_keys = ()
    moe_expert_keys = ()
    # Shared/always-on experts, which expert parallelism does not shard: every rank holds a
    # copy. Empty in the base for the same reason as above -- inheriting DeepSeek's
    # `n_shared_experts` would make a family without shared experts appear to have one.
    shared_expert_keys = ()
    # Experts activated per token (top-k routing). Empty in the base likewise.
    experts_per_token_keys = ()

    #: Capabilities this family is known to have, asserted only when the evidence scan
    #: confirms them. Validators gate family-specific rules on these, so a Dense model is
    #: never asked to have MoE branches. See `capabilities()`.
    capability_keys = {}

    #: capability_id -> class-name substrings that evidence it. A second evidence channel
    #: for capabilities that live in a module rather than a config value: DeepSeek V3.2's
    #: sparse indexer is declared by `DeepseekIndexerAttention` existing, while its
    #: `index_topk` sits in a separate `DeepseekV3IndexConfig` the main config never
    #: inherits -- so a config-value-only rule would miss it. Class names are matched
    #: against the modeling source, which is the module actually being built.
    capability_class_hints = {}

    #: Known kernel-name aliases per semantic role, as CANDIDATE HINTS for op mapping --
    #: never as a required table. The same semantic has different kernel names across
    #: backends, op-library versions and quantisation modes, so a fixed list would fail the
    #: next version of the same model.
    kernel_anchors = {}

    #: Dataflow shapes this family must exhibit, checked against the AST-derived graph.
    #: Each entry: {'id', 'requires', 'reason'}. `requires` names the capability that gates
    #: the rule (None = ungated). These are DECLARATIVE only -- an adapter states the
    #: constraint and the checker evaluates it; an adapter never edits report output.
    #: Empty means "assert nothing".
    dataflow_invariants = ()

    #: Constructs this family is known to defeat static extraction on, as a list of
    #: {'id', 'reason'}. Recorded so the gap is visible in the manifest rather than
    #: surfacing later as an unexplained checker abstention.
    known_deviations = ()

    @staticmethod
    def matches(evidence):
        """Return False, or a (confidence, reasons) pair.

        Returning a bare bool is still supported for backwards compatibility and is read as
        `('medium', [])`. Confidence matters because selection by list order silently
        resolves ambiguity: two families whose signatures both fire is a fact about the
        source that the caller must see, not something to settle by whoever is listed first.
        """
        return False

    #: Semantic role -> submodule-attribute-name substrings that indicate it. Used by
    #: `infer_roles` to propose a `semantic` for a node. These are CANDIDATES for a human or
    #: AI mapper to confirm against the source, never an authority: a name is a hint about
    #: intent, and a model is free to call its router `gate` or its MLP `feed_forward`.
    role_hints = {
        'attention': ('self_attn', 'attention', 'attn'),
        'mlp': ('mlp', 'feed_forward', 'ffn'),
        'router_gating': ('gate', 'router'),
        'experts': ('experts', 'expert'),
        'shared_expert': ('shared_expert', 'shared_experts'),
        'moe': ('moe_block', 'sparse_moe', 'moe'),
        'norm': ('layernorm', 'layer_norm', 'rmsnorm', 'norm', 'ln_'),
        'embedding': ('embed_tokens', 'embedding', 'wte'),
    }

    @staticmethod
    def extract_components(modeling_tree, config_defaults, base_dir=None,
                           modeling_path=None):
        """Candidate component definitions: the submodules each layer class declares.

        Returns a list of {'class_name', 'source_ref', 'components': [{'attr', 'count',
        'source_ref'}]}. This is a proposal derived from `__init__` assignments, not a
        decomposition -- containment and dataflow are decided against `forward()` (see
        extract_dataflow.py), because `__init__` order says nothing about execution order
        and a declared submodule may never be called.
        """
        if modeling_tree is None:
            return []
        wanted = {name for name, _line in find_decoder_layer_classes(modeling_tree)}
        out = []
        for node in ast.walk(modeling_tree):
            if not isinstance(node, ast.ClassDef) or node.name not in wanted:
                continue
            component_set = _class_components(node, modeling_path, base_dir)
            if component_set is not None:
                out.append(component_set)
        return out

    @staticmethod
    def build_layer_groups(state):
        num_main = state.num_main
        first_k_dense = state.first_k_dense
        has_moe = state.has_moe
        base_class_name = state.base_class_name
        context = state.context
        if num_main == UNKNOWN:
            return []
        # dense/moe split
        if has_moe and first_k_dense is not None:
            pred_src, pred_line = (None, None)
            if context.modeling_tree is not None:
                pred_src, pred_line = find_predicate_assignment(context.modeling_tree, 'is_moe')
            groups = []
            if first_k_dense > 0:
                groups.append({
                    'type': f'{base_class_name}_dense',
                    'classification': 'dense',
                    'model_layer_indices': list(range(0, first_k_dense)),
                    'predicate': f'layer_idx < first_k_dense_replace ({first_k_dense})',
                    'source_ref': context.ref(pred_line, context.modeling_path) if pred_line else UNKNOWN,
                    'confidence': 'high' if pred_line else 'medium',
                })
            groups.append({
                'type': f'{base_class_name}_moe',
                'classification': 'moe',
                'model_layer_range': [first_k_dense, num_main - 1],
                'predicate': f'layer_idx >= first_k_dense_replace ({first_k_dense})',
                'source_ref': context.ref(pred_line, context.modeling_path) if pred_line else UNKNOWN,
                'confidence': 'high' if pred_line else 'medium',
            })
            return groups
        # all-moe
        if has_moe and first_k_dense is None:
            return [{
                'type': f'{base_class_name}_moe',
                'classification': 'moe',
                'model_layer_range': [0, num_main - 1],
                'predicate': 'all layers MoE (no dense boundary key found)',
                'source_ref': state.construct_ref or UNKNOWN,
                'confidence': 'medium',
            }]
        # dense-only: the group spans every layer, so the ModuleList construction site is
        # exactly the evidence for it — no per-layer predicate needs locating.
        #
        # `construct_ref` proves how many layers there are; it says nothing about whether
        # they are dense. When an MoE key was found but carried no bound value, this branch
        # is a fallback rather than a finding, so it must not inherit high confidence --
        # otherwise A3 enforces `dense` against trace evidence that says otherwise.
        confidence = 'high' if state.construct_ref else 'medium'
        if state.moe_key_unbound:
            confidence = 'low'
        return [{
            'type': base_class_name,
            'classification': 'dense',
            'model_layer_range': [0, num_main - 1],
            'predicate': None,
            'source_ref': state.construct_ref or UNKNOWN,
            'confidence': confidence,
        }]

    @staticmethod
    def build_prediction_modules(state):
        num_main = state.num_main
        pred_count = state.pred_count
        pred_key = state.pred_key
        base_class_name = state.base_class_name
        context = state.context
        if not pred_count:
            return []
        if num_main == UNKNOWN:
            state.gaps.append('prediction module 层号无法确定（num_main_layers unknown）')
            return [{
                'type': f'{base_class_name}_mtp',
                'learned_module_count': pred_count,
                'model_layer_indices': [],
                'count_config_key': pred_key,
                'source_ref': UNKNOWN,
                'confidence': 'low',
            }]
        # MTP layers are appended after the main layers: indices [num_main .. num_main+pred_count-1]
        indices = list(range(num_main, num_main + pred_count))
        # locate the MTP construction (ModuleDict keyed str(mtp_start + i))
        mtp_ref = UNKNOWN
        if context.modeling_tree is not None:
            for node in ast.walk(context.modeling_tree):
                if isinstance(node, ast.ClassDef) and 'MTP' in node.name.upper():
                    mtp_ref = context.ref(node.lineno, context.modeling_path)
                    break
        return [{
            'type': f'{base_class_name}_mtp',
            'learned_module_count': pred_count,
            'model_layer_indices': indices,
            'count_config_key': pred_key,
            'source_ref': mtp_ref,
            'confidence': 'high' if mtp_ref != UNKNOWN else 'medium',
        }]

    @staticmethod
    def refine(state):
        """Hook for family-specific post-processing. Default: no-op."""
        return

    def deviations(self):
        """Known unsupported/dynamic constructs for this family. Declarative, not fatal."""
        return [dict(item) for item in (self.known_deviations or ())]

    def capabilities(self, evidence, config_defaults):
        """Capabilities this source actually evidences, as a list of dicts.

        Evidence is a key RESOLVED TO A TRUTHY VALUE, not merely a key that exists. Gemma 4
        declares `num_experts=None, enable_moe_block=False` in its config `__init__`, so
        name-presence alone would assert `moe` for a deployment that has the expert block
        switched off -- and asserting a capability turns on the validation rules that
        require the matching fork/join (check_dataflow D7). A key resolving to
        None/False/0 is the source saying the feature is off; a key absent entirely is
        unknown. Neither is a reason to claim it.

        `config_defaults` is the authority because `extract_model_manifest` has already
        merged the checkpoint config.json over the Python defaults, so a deployment that
        does enable experts is read from its deployed values.
        """
        found = []
        defaults = config_defaults or {}
        for capability_id, required in (self.capability_keys or {}).items():
            hits = []
            for key in required:
                if key not in defaults:
                    continue
                value = defaults[key][0] if isinstance(defaults[key], tuple) else defaults[key]
                if value:
                    hits.append(key)
            if hits:
                line = defaults[hits[0]][1] if isinstance(defaults[hits[0]], tuple) else 1
                found.append({'id': capability_id, 'evidence_keys': sorted(hits),
                              'source_ref': f'config:{hits[0]}:{line}'})

        seen = {item['id'] for item in found}
        classes = set(evidence.get('class_names') or ())
        for capability_id, hints in (self.capability_class_hints or {}).items():
            if capability_id in seen:
                continue
            matched = sorted(name for name in classes
                             if any(hint in name for hint in hints))
            if matched:
                found.append({'id': capability_id, 'evidence_keys': matched[:4],
                              'source_ref': f'class:{matched[0]}'})
        return found

    def infer_roles(self, modeling_tree, base_dir=None, modeling_path=None):
        """Propose semantic roles for declared submodules, each with a source_ref.

        Only names that match a `role_hints` entry are proposed, and every proposal carries
        `confidence: 'low'` plus the hint that fired. A name is evidence of intent, not of
        behaviour -- what a module does is decided by its `forward()`. Anything unmatched is
        returned under 'unresolved' rather than assigned a default role, so a mapper sees
        what still needs deciding instead of inheriting a guess.
        """
        roles, unresolved = [], []
        for component_set in self.extract_components(modeling_tree, {}, base_dir,
                                                     modeling_path):
            for component in component_set['components']:
                attr = component['attr']
                # The rightmost match is the compound name's head noun; length breaks ties.
                best = _best_role_hint(attr, self.role_hints)
                entry = {'class_name': component_set['class_name'], 'attr': attr,
                         'source_ref': component['source_ref']}
                if best:
                    roles.append(dict(entry, role=best[0], confidence='low',
                                      basis=f'attr 名含 `{best[1]}` → role_hints[{best[0]}]'))
                else:
                    unresolved.append(entry)
        return {'roles': roles, 'unresolved': unresolved}

    # ---- extraction API -------------------------------------------------

    def extract(self, context):
        """
        Return (facts:list[Fact], layer_groups:list[dict], prediction_modules:list[dict],
                num_main_layers, evidence_gaps:list[str]).
        Generic implementation; adapters may override or post-process via `refine`.
        """
        state = ExtractionState(context)
        _extract_layer_counts(self, state)
        _extract_moe_presence(self, state)
        _extract_moe_dimensions(self, state)
        _extract_layer_construction(self, state)
        state.layer_groups = self.build_layer_groups(state)
        state.prediction_modules = self.build_prediction_modules(state)
        self.refine(state)
        return (state.facts, state.layer_groups, state.prediction_modules,
                state.num_main, state.gaps)


GENERIC = BaseAdapter()
