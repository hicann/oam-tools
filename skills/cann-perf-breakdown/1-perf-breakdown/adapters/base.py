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


def _is_architecture_int(value):
    """JSON booleans are not valid layer/expert counts despite bool subclassing int."""
    return isinstance(value, int) and not isinstance(value, bool)


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
        if isinstance(node, ast.ImportFrom):
            module = node.module or ''
            if 'config' not in module.lower():
                continue
            for alias in node.names:
                if alias.name.endswith('Config'):
                    names.add(alias.name)
    return names


def find_config_class(tree, modeling_tree=None):
    """Return (ClassDef, __init__) for the config class the model actually uses.

    A config module may define several *Config classes for different model variants.
    The one the modeling source imports is the authoritative one; source order is not
    evidence of anything. Falls back to the first class with an __init__ when there is
    no import to go by, which is the single-class case.
    """
    candidates = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name.endswith('Config'):
            init_fn = next((item for item in node.body
                            if isinstance(item, ast.FunctionDef) and item.name == '__init__'),
                           None)
            candidates.append((node, init_fn))
    if not candidates:
        return None, None

    imported = config_classes_imported_by(modeling_tree)
    with_init = [c for c in candidates if c[1] is not None]
    preferred = [c for c in with_init if c[0].name in imported]
    if preferred:
        # Narrowest wins: a subclass overrides its base's defaults, so when both a base
        # and a derived config are imported the derived one carries the real numbers.
        base_names = {b.id for c in preferred for b in c[0].bases if isinstance(b, ast.Name)}
        derived = [c for c in preferred if c[0].name not in base_names]
        return (derived or preferred)[0]
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
    HELPER = ('Moe', 'MLP', 'Mlp', 'Attention', 'Norm', 'Embed', 'Expert', 'Router', 'Gate')
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if node.name.endswith('DecoderLayer'):
                decoder_layers.append((node.name, node.lineno))
            elif node.name.endswith('Block') and not any(h in node.name for h in HELPER):
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


def find_predicate_assignment(tree, target_attr):
    """
    Find `self.<target_attr> = <expr>` and return (source_text_of_expr, lineno) if the
    expression references known predicate config keys. Returns (None, None) if absent.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if (isinstance(tgt, ast.Attribute) and tgt.attr == target_attr):
                    try:
                        src = ast.unparse(node.value)
                    except Exception:
                        src = None
                    return src, node.lineno
    return None, None


def scan_evidence(config_src, modeling_src):
    """Cheap evidence scan (class names + config keys) for adapter selection."""
    ev = {'class_names': set(), 'config_keys': set()}
    for src in (config_src, modeling_src):
        if not src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                ev['class_names'].add(node.name)
            if isinstance(node, ast.FunctionDef) and node.name == '__init__':
                for a in node.args.args + node.args.kwonlyargs:
                    ev['config_keys'].add(a.arg)
    return ev


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

    def deviations(self):
        """Known unsupported/dynamic constructs for this family. Declarative, not fatal."""
        return [dict(item) for item in (self.known_deviations or ())]

    def matches(self, evidence):
        """Return False, or a (confidence, reasons) pair.

        Returning a bare bool is still supported for backwards compatibility and is read as
        `('medium', [])`. Confidence matters because selection by list order silently
        resolves ambiguity: two families whose signatures both fire is a fact about the
        source that the caller must see, not something to settle by whoever is listed first.
        """
        return False

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

    def extract_components(self, modeling_tree, config_defaults, base_dir=None,
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
            if not (isinstance(node, ast.ClassDef) and node.name in wanted):
                continue
            init_fn = next((item for item in node.body
                            if isinstance(item, ast.FunctionDef) and item.name == '__init__'),
                           None)
            if init_fn is None:
                continue
            components = []
            for stmt in ast.walk(init_fn):
                if not isinstance(stmt, ast.Assign):
                    continue
                for target in stmt.targets:
                    if not (isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == 'self'):
                        continue
                    if not isinstance(stmt.value, ast.Call):
                        continue   # plain scalars are config copies, not submodules
                    components.append({
                        'attr': target.attr,
                        'constructor': _callee_name(stmt.value),
                        'source_ref': rel_ref(modeling_path or 'unknown', stmt.lineno,
                                              base_dir),
                    })
            out.append({
                'class_name': node.name,
                'source_ref': rel_ref(modeling_path or 'unknown', node.lineno, base_dir),
                'components': components,
            })
        return out

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
                lowered = attr.lower()
                # Ranked by (rightmost end position, then hint length) -- NOT by dict order.
                # These names are compounds whose head noun comes last:
                # `post_attention_layernorm` is a norm, not an attention, and it contains
                # both hints at equal length, so picking by dict order or by length alone
                # labelled it `attention` and would file a norm's cost under the attention
                # budget. The rightmost match is the head noun; length only breaks ties, so
                # `shared_expert` still beats `expert` on the same ending.
                best = None   # (role, hint, end_position)
                for role, hints in (self.role_hints or {}).items():
                    for hint in hints:
                        index = lowered.rfind(hint)
                        if index < 0:
                            continue
                        rank = (index + len(hint), len(hint))
                        if best is None or rank > (best[2], len(best[1])):
                            best = (role, hint, index + len(hint))
                entry = {'class_name': component_set['class_name'], 'attr': attr,
                         'source_ref': component['source_ref']}
                if best:
                    roles.append(dict(entry, role=best[0], confidence='low',
                                      basis=f'attr 名含 `{best[1]}` → role_hints[{best[0]}]'))
                else:
                    unresolved.append(entry)
        return {'roles': roles, 'unresolved': unresolved}

    # ---- extraction API -------------------------------------------------

    def extract(self, config_tree, modeling_tree, config_defaults, base_dir,
                config_path, modeling_path):
        """
        Return (facts:list[Fact], layer_groups:list[dict], prediction_modules:list[dict],
                num_main_layers, evidence_gaps:list[str]).
        Generic implementation; adapters may override or post-process via `refine`.
        """
        facts = []
        gaps = []

        def ref(lineno, path=config_path):
            return rel_ref(path, lineno, base_dir)

        # --- main layer count ---
        num_main = UNKNOWN
        main_key = None
        for key in self.main_layer_count_keys:
            if key in config_defaults:
                val, lineno = config_defaults[key]
                if _is_architecture_int(val):
                    num_main = val
                    main_key = key
                    facts.append(Fact(key, val, ref(lineno), 'ast_default_arg', 'high'))
                    break
        if num_main == UNKNOWN:
            gaps.append('num_main_layers: 无法从 config 默认参数静态解析')

        # --- prediction / MTP count ---
        pred_count = 0
        pred_key = None
        for key in self.prediction_count_keys:
            if key in config_defaults:
                val, lineno = config_defaults[key]
                if _is_architecture_int(val):
                    pred_count = val
                    pred_key = key
                    facts.append(Fact(key, val, ref(lineno), 'ast_default_arg', 'high'))
                    break

        # --- dense boundary ---
        first_k_dense = None
        for key in self.dense_boundary_keys:
            if key in config_defaults:
                val, lineno = config_defaults[key]
                if _is_architecture_int(val):
                    first_k_dense = val
                    facts.append(Fact(key, val, ref(lineno), 'ast_default_arg', 'high'))
                    break

        # --- moe experts present? ---
        has_moe = False
        moe_key_unbound = False
        for key in self.moe_expert_keys:
            if key in config_defaults:
                val, lineno = config_defaults[key]
                if _is_architecture_int(val) and val > 0:
                    has_moe = True
                    facts.append(Fact(key, val, ref(lineno), 'ast_default_arg', 'high'))
                    break
                if val is None or val is False:
                    # The key exists, so the family declares an expert path; the default just
                    # carries no count for it. Dropping that on the floor is what lets the
                    # dense-only fallback below assert `dense` at high confidence -- the one
                    # combination that makes a wrong classification invisible downstream.
                    # Absent evidence is unknown, not dense.
                    moe_key_unbound = True
                    facts.append(Fact(key, val, ref(lineno), 'ast_default_arg', 'low'))
                    gaps.append(
                        f'{key}: MoE 配置键存在但默认值为 {val}，无法静态判定是否启用 MoE。'
                        f'该层组分类降为 low confidence；需由 checkpoint config.json 或 '
                        f'trace 算子（MoeGatingTopK* / GroupedMatmul）判定')
                    break

        # --- shared experts and routing width ---
        # Only meaningful on an MoE model, so gated on has_moe. These are what let a consumer
        # state the full declared expert population: the routed count alone omits the shared
        # expert, which is not EP-sharded and is therefore the one expert a single-rank capture
        # can measure on its own. `shared_expert` already appears as a capability, but a
        # capability says the path exists -- it does not carry the count.
        if has_moe:
            for key in self.shared_expert_keys:
                if key in config_defaults:
                    val, lineno = config_defaults[key]
                    if _is_architecture_int(val) and val > 0:
                        facts.append(Fact(key, val, ref(lineno), 'ast_default_arg', 'high'))
                        break
            for key in self.experts_per_token_keys:
                if key in config_defaults:
                    val, lineno = config_defaults[key]
                    if _is_architecture_int(val) and val > 0:
                        facts.append(Fact(key, val, ref(lineno), 'ast_default_arg', 'high'))
                        break

        # --- decoder layer classes + range() construction evidence ---
        layer_classes = find_decoder_layer_classes(modeling_tree) if modeling_tree else []
        range_calls = find_range_calls_over_config(
            modeling_tree, set(self.main_layer_count_keys)) if modeling_tree else []
        base_class_name = layer_classes[0][0] if layer_classes else 'DecoderLayer'
        construct_ref = None
        if range_calls:
            construct_ref = rel_ref(modeling_path, range_calls[0]['lineno'], base_dir)
            facts.append(Fact('main_layer_construction', f"range({range_calls[0]['attr']})",
                              construct_ref, 'ast_range_expr', 'high'))
        else:
            gaps.append('main decoder ModuleList range(...) 构造未静态定位')

        # --- build layer groups ---
        # `construct_ref` is the AST-located `range(config.num_hidden_layers)` that builds
        # the decoder ModuleList — the actual evidence for "there are N main layers".
        # Pass it down so whole-range groups cite it instead of reporting source_ref=unknown.
        layer_groups = self.build_layer_groups(
            num_main, first_k_dense, has_moe, base_class_name, config_defaults,
            config_path, modeling_path, base_dir, config_tree, modeling_tree, gaps,
            construct_ref=construct_ref, moe_key_unbound=moe_key_unbound)

        # --- prediction modules ---
        prediction_modules = self.build_prediction_modules(
            num_main, pred_count, pred_key, base_class_name, modeling_tree,
            modeling_path, base_dir, gaps)

        self.refine(facts, layer_groups, prediction_modules, config_defaults,
                    config_tree, modeling_tree, base_dir, config_path, modeling_path, gaps)

        return facts, layer_groups, prediction_modules, num_main, gaps

    def build_layer_groups(self, num_main, first_k_dense, has_moe, base_class_name,
                           config_defaults, config_path, modeling_path, base_dir,
                           config_tree, modeling_tree, gaps, construct_ref=None,
                           moe_key_unbound=False):
        if num_main == UNKNOWN:
            return []
        # dense/moe split
        if has_moe and first_k_dense is not None:
            pred_src, pred_line = (None, None)
            if modeling_tree is not None:
                pred_src, pred_line = find_predicate_assignment(modeling_tree, 'is_moe')
            groups = []
            if first_k_dense > 0:
                groups.append({
                    'type': f'{base_class_name}_dense',
                    'classification': 'dense',
                    'model_layer_indices': list(range(0, first_k_dense)),
                    'predicate': f'layer_idx < first_k_dense_replace ({first_k_dense})',
                    'source_ref': rel_ref(modeling_path, pred_line, base_dir) if pred_line else UNKNOWN,
                    'confidence': 'high' if pred_line else 'medium',
                })
            groups.append({
                'type': f'{base_class_name}_moe',
                'classification': 'moe',
                'model_layer_range': [first_k_dense, num_main - 1],
                'predicate': f'layer_idx >= first_k_dense_replace ({first_k_dense})',
                'source_ref': rel_ref(modeling_path, pred_line, base_dir) if pred_line else UNKNOWN,
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
                'source_ref': construct_ref or UNKNOWN,
                'confidence': 'medium',
            }]
        # dense-only: the group spans every layer, so the ModuleList construction site is
        # exactly the evidence for it — no per-layer predicate needs locating.
        #
        # `construct_ref` proves how many layers there are; it says nothing about whether
        # they are dense. When an MoE key was found but carried no bound value, this branch
        # is a fallback rather than a finding, so it must not inherit high confidence --
        # otherwise A3 enforces `dense` against trace evidence that says otherwise.
        confidence = 'high' if construct_ref else 'medium'
        if moe_key_unbound:
            confidence = 'low'
        return [{
            'type': base_class_name,
            'classification': 'dense',
            'model_layer_range': [0, num_main - 1],
            'predicate': None,
            'source_ref': construct_ref or UNKNOWN,
            'confidence': confidence,
        }]

    def build_prediction_modules(self, num_main, pred_count, pred_key, base_class_name,
                                 modeling_tree, modeling_path, base_dir, gaps):
        if not pred_count:
            return []
        if num_main == UNKNOWN:
            gaps.append('prediction module 层号无法确定（num_main_layers unknown）')
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
        if modeling_tree is not None:
            for node in ast.walk(modeling_tree):
                if isinstance(node, ast.ClassDef) and 'MTP' in node.name.upper():
                    mtp_ref = rel_ref(modeling_path, node.lineno, base_dir)
                    break
        return [{
            'type': f'{base_class_name}_mtp',
            'learned_module_count': pred_count,
            'model_layer_indices': indices,
            'count_config_key': pred_key,
            'source_ref': mtp_ref,
            'confidence': 'high' if mtp_ref != UNKNOWN else 'medium',
        }]

    def refine(self, facts, layer_groups, prediction_modules, config_defaults,
               config_tree, modeling_tree, base_dir, config_path, modeling_path, gaps):
        """Hook for family-specific post-processing. Default: no-op."""
        return


GENERIC = BaseAdapter()
