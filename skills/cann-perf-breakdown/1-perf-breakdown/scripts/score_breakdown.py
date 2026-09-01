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
"""Deterministically score a schema-v2 model breakdown and emit one JSON report."""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import breakdown_common as bc  # noqa: E402


MIN_TOTAL_SCORE = 95
CORE_MINIMUMS = {
    'architecture_integrity': 22,
    'dataflow_branch_correctness': 27,
    'layer_submodule_boundaries': 18,
}
# Five dimensions, 100 points. `shape_semantic_consistency` and `trace_instance_scope` are
# gone: a missing shape annotation and a single-step capture describe what the inputs
# contained, not whether the decomposition is right, so both awarded points for evidence
# that could not be wrong. Their 20 points moved to the two things that CAN be wrong and
# are now machine-checkable -- dataflow/branch topology (30) and architecture (25).
#
# The per-dimension minimums sum to 91, below the 95 total bar. That ordering matters: if
# they summed above 95 (the draft's 24/29/19/20/5 = 97) the total threshold could never
# bind and would be dead code. Both gates have to be reachable independently.
DIMENSION_MINIMUMS = {
    **CORE_MINIMUMS,
    'kernel_exact_coverage': 20,
    'evidence_traceability': 4,
}

#: The same bars as `DIMENSION_MINIMUMS`, expressed as a fraction of the weight that could
#: actually run. An absolute bar silently conflates two different failures: a check that ran
#: and disagreed with the source, and a check that never ran because its input was not
#: supplied. Only the first is a decomposition error. Scoring the second as a zero made the
#: absolute minimum unreachable for any capture missing an input, which is how gemma, ds3.2
#: and longcat — three captures with identical raw inputs — ended up with different verdicts
#: for reasons that had nothing to do with whether their breakdowns were right.
#:
#: So a dimension is now judged on `earned / runnable_max`: correctness among the checks that
#: had evidence to work with. How much evidence there was is reported separately as
#: `evidence_fraction` (`runnable_max / nominal_max`) and drives the exit conclusion, not the
#: pass/fail of the dimension. The ratios are the old bars over the old maxima (22/25 = 0.88,
#: 27/30 = 0.90, 18/20 = 0.90, 20/20 = 1.00, 4/5 = 0.80), so a capture with complete inputs is
#: held to exactly the standard it was held to before.
DIMENSION_RATIO_MINIMUMS = {
    'architecture_integrity': 0.88,
    'dataflow_branch_correctness': 0.90,
    'layer_submodule_boundaries': 0.90,
    'kernel_exact_coverage': 1.00,
    'evidence_traceability': 0.80,
}

#: Overall correctness bar, as a fraction of runnable weight. 95/100 from `MIN_TOTAL_SCORE`.
MIN_TOTAL_RATIO = MIN_TOTAL_SCORE / 100.0

#: Below this fraction of nominal weight, a capture has too little evidence for the score to
#: mean much even if everything runnable passed: the conclusion degrades to `exploratory`.
MIN_EVIDENCE_FRACTION = 0.55

#: What each provenance tier can be asked to prove.
#:
#: `scalars_bound` — the architecture scalars (num_main_layers and friends) are confirmed by
#: something other than an unbound Python default, so a check that compares them against the
#: capture is answerable. False for tier A, whose source may or may not describe the run.
#: `source_bound` — the source is tied to THIS capture, so `forward()` may be treated as the
#: topology of what ran. `capture_scoped` — step marks exist, so per-step claims are checkable.
TIER_CAPABILITIES = {
    'S0': {'scalars_bound': True, 'source_bound': True, 'capture_scoped': True},
    'S': {'scalars_bound': True, 'source_bound': True, 'capture_scoped': True},
    'A': {'scalars_bound': False, 'source_bound': True, 'capture_scoped': False},
    'B': {'scalars_bound': False, 'source_bound': False, 'capture_scoped': False},
    'C': {'scalars_bound': False, 'source_bound': False, 'capture_scoped': False},
}

#: Highest conclusion each tier may reach, however well it scores. A tier-A capture that
#: passes every runnable check has verified its structure but not its scalars, and saying
#: plain `verified` would overclaim; a tier-B capture has no source to verify structure
#: against at all.
TIER_CEILING = {
    'S0': 'verified',
    'S': 'verified',
    'A': 'verified_unbound_scalars',
    'B': 'structure_unverified',
    'C': 'exploratory',
}

#: Conclusions that mean the breakdown may be converted into a report. Kept in sync with
#: `2-adapt-breakdown-to-ui-json/scripts/breakdown_paths.py:CONVERTIBLE_STATUSES`.
CONVERTIBLE_CONCLUSIONS = ('verified', 'verified_unbound_scalars', 'structure_unverified')

_CONCLUSION_ORDER = ('verified', 'verified_unbound_scalars', 'structure_unverified',
                     'exploratory', 'needs_iteration')


def _cap_conclusion(conclusion, ceiling):
    """The weaker of two conclusions, ordered strongest-first by `_CONCLUSION_ORDER`."""
    order = _CONCLUSION_ORDER
    if conclusion not in order:
        return conclusion
    if ceiling not in order:
        return conclusion
    return order[max(order.index(conclusion), order.index(ceiling))]


def effective_ceiling(tier, caps):
    """The strongest conclusion the evidence actually supports.

    Derived from the capabilities rather than read straight off `TIER_CEILING`, because a
    capability can be promoted by evidence the tier does not account for: a tier-A capture whose
    scalars were confirmed by a runtime record has bound both scalars and structure, and holding
    it to tier A's ceiling would report a gap that the inputs closed. The tier's own ceiling is
    still the floor of this calculation for tiers that cannot reach `verified` structurally.
    """
    if caps.get('scalars_bound') and caps.get('source_bound'):
        derived = 'verified'
    elif caps.get('source_bound'):
        derived = 'verified_unbound_scalars'
    else:
        derived = 'structure_unverified'
    # Tier C is exploratory whatever the capabilities claim: it has no usable capture.
    return derived if tier != 'C' else 'exploratory'


def capture_tier(manifest):
    """This capture's provenance tier, defaulting to the most cautious reading.

    A manifest written before `capture_provenance` existed carries no tier. Treating that as
    tier S would hand every legacy manifest the strongest conclusion available, so an absent
    block reads as tier A: source is present (the manifest was built from it) but nothing
    binds it to the capture.
    """
    provenance = manifest.get('capture_provenance') or {}
    tier = provenance.get('tier')
    return tier if tier in TIER_CAPABILITIES else 'A'

#: What the *inputs* permit as a maximum, keyed by (source, checkpoint_config, trace).
#:
#: This is deliberately a fixed table rather than anything derived from the run: the ceiling
#: describes the evidence that was supplied, so it must not move because a breakdown scored
#: well. Quality and evidence are then reported as two independent numbers
#: (`quality_rate` x `evidence_cap` = `final_score`), which is what lets a complete-input
#: capture and an input-starved one be told apart instead of both landing on a single blended
#: score that reads as a quality verdict.
EVIDENCE_CAP_TABLE = {
    (True, True, True): 100,    # source + checkpoint config + trace
    (True, False, True): 90,    # source + trace, checkpoint config absent
    (True, True, False): 75,    # source + checkpoint config, no trace
    (True, False, False): 65,   # source only
    (False, True, True): 45,    # config + trace, no source
    (False, False, True): 30,   # trace only
    (False, True, False): 25,   # config only
    (False, False, False): 0,   # nothing to reason from
}

#: `evidence_level` values that mean an architecture scalar rests on something other than an
#: unbound Python default: a delivered `config.json` (1), a value printed by a real load (2),
#: or an AST default tied to this capture by a source snapshot ('2S'). Level 4 is explicitly
#: "source default, provably unbound", which is exactly what must NOT count as a checkpoint --
#: treating a Python default as a bound parameter is how an unverifiable layer count reached a
#: perfect score.
CHECKPOINT_BOUND_LEVELS = frozenset({1, 2, '2S', '1', '2s'})

#: Correctness bar for a formal pass, read off `quality_rate` and NOT off `final_score`. A
#: capture whose evidence caps it at 90 can still be a fully correct breakdown, so gating on
#: the product would fail it for something the decomposition had no control over.
MIN_QUALITY_RATE = 0.95


def checkpoint_is_bound(manifest):
    """Whether an instantiation parameter is backed by more than an unbound Python default."""
    checkpoint = ((manifest.get('capture_provenance') or {}).get('checkpoint_config') or {})
    level = checkpoint.get('evidence_level')
    if isinstance(level, str) and level.isdigit():
        level = int(level)
    return level in CHECKPOINT_BOUND_LEVELS


def evidence_inputs(manifest, raw_ops):
    """The three booleans the cap table is keyed on."""
    provenance = manifest.get('capture_provenance') or {}
    model_source = provenance.get('model_source')
    if isinstance(model_source, dict) and 'present' in model_source:
        # An explicit provenance reading wins. Falling back to `source_of_truth` here would
        # make `has_source` un-falsifiable: extract_model_manifest fills that field on every
        # manifest it writes, so a source-less capture would still read as having source and
        # would be capped at 75 instead of 45.
        has_source = bool(model_source.get('present'))
    else:
        has_source = bool(manifest.get('source_of_truth') or manifest.get('facts'))
    has_trace = bool(bc.expand_raw_op_indices(raw_ops or {}))
    return has_source, checkpoint_is_bound(manifest), has_trace


def evidence_cap(manifest, raw_ops):
    """Highest score these inputs may yield, with the reason recorded alongside."""
    has_source, has_checkpoint, has_trace = evidence_inputs(manifest, raw_ops)
    cap = EVIDENCE_CAP_TABLE[(has_source, has_checkpoint, has_trace)]
    present = [name for name, flag in (('源码', has_source),
                                       ('checkpoint config', has_checkpoint),
                                       ('trace', has_trace)) if flag]
    return cap, {
        'has_source': has_source,
        'has_checkpoint_config': has_checkpoint,
        'has_trace': has_trace,
        'cap': cap,
        'reason': (f'输入包含 {"+".join(present)}' if present else '无可用输入')
                  + f'：证据上限 {cap}',
    }


#: Fraction of a check's weight lost per warning. `_quality` used to return only
#: {1.0, 0.6, 0.0}, so any single warning cost 40% of the check and a "27/30" minimum was
#: in practice "zero warnings" -- a threshold that looked graduated but was binary. With a
#: per-warning step the fractional minimums discriminate: one warning on one check is
#: survivable, a pile of them is not.
WARNING_STEP = 0.2
#: A check drowning in warnings still scores above zero -- it ran and reported. Only an
#: `error` (or a missing check) zeroes the weight.
WARNING_FLOOR = 0.4


def _load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _check_map(validation):
    return {c.get('name'): c for c in validation.get('checks', [])}


#: Validation issues that report an architecture scalar the inputs cannot confirm, rather than
#: a structural defect. This score rates whether the decomposition is complete and correct; a
#: fact the supplied files simply do not contain is not a decomposition error. Under the
#: code-first rule the source is the architecture truth and the trace cannot adjudicate a
#: scalar, so these do not reduce a structural dimension. They stay visible as validation
#: warnings and as the `evidence_traceability` deduction.
DATA_AVAILABILITY_ISSUE_IDS = frozenset({'A1', 'MT1', 'MA1', 'SR_EVIDENCE_GAP_FINDING'})


def _structural_status(checks, name, issues=()):
    """A check's status once data-availability issues are set aside.

    A check whose only warnings are unconfirmable-scalar reports is structurally clean, so it
    scores as `passed`. A check carrying any other warning keeps its reported status. Warnings
    are matched from the report's top-level issue list via each issue's `check` field.
    """
    check = checks.get(name) or {}
    status = check.get('status', 'missing')
    if status != 'warning':
        return status
    warnings = [i for i in issues
                if i.get('check') == name and i.get('severity') == 'warning']
    if len(warnings) != (check.get('warning_count') or 0):
        return status  # cannot account for every warning; do not soften the status
    if warnings and all(i.get('id') in DATA_AVAILABILITY_ISSUE_IDS for i in warnings):
        return 'passed'
    return status


def _quality(checks, name, issues=()):
    """Weight factor in [0, 1] for one check, graded by how many warnings it raised.

    A check that passed scores 1.0; an error or a missing check scores 0.0. In between,
    each warning costs WARNING_STEP down to WARNING_FLOOR, so the fractional dimension
    minimums measure something other than "any warning at all". Data-availability
    warnings are excluded upstream by `_structural_status` and cost nothing.
    """
    status = _structural_status(checks, name, issues)
    if status == 'passed':
        return 1.0
    if status != 'warning':
        return 0.0
    counted = [i for i in issues
               if i.get('check') == name and i.get('severity') == 'warning'
               and i.get('id') not in DATA_AVAILABILITY_ISSUE_IDS]
    count = len(counted) or (checks.get(name, {}).get('warning_count') or 1)
    return max(WARNING_FLOOR, 1.0 - WARNING_STEP * count)


def _points(value):
    return int(round(value))


#: Keys holding per-kernel records, not structure-tree nodes. Enriched op_data entries
#: carry a `name` (the kernel name) and never a `code_ref`, so walking into them would
#: inflate the denominator of code_ref_ratio — making `analyze_kernels.py --enrich`
#: LOWER the evidence score it is supposed to support.
_KERNEL_KEYS = ('op_data', 'kernels')


def _walk_nodes(value):
    """Yield structure-tree nodes (things with a `name`), excluding kernel records."""
    if isinstance(value, dict):
        if 'name' in value:
            yield value
        for key, child in value.items():
            if key in _KERNEL_KEYS:
                continue
            yield from _walk_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_nodes(child)


def _coverage_detail(checks):
    detail = checks.get('coverage', {}).get('detail', {})
    return detail if isinstance(detail, dict) else {}


def _dimension(identifier, label, components, evidence, actions):
    """Score one dimension from weighted components, separating "wrong" from "unknown".

    `components` is a list of `(name, weight, quality, runnable)`. A component with
    `runnable=False` is one whose evidence was never supplied: its weight leaves BOTH the
    numerator and the denominator, so it cannot drag the ratio down. A runnable component
    that scored 0 stays in the denominator — that is a check that ran and disagreed.
    """
    nominal_max = sum(weight for _, weight, _, _ in components)
    runnable = [c for c in components if c[3]]
    runnable_max = sum(weight for _, weight, _, _ in runnable)
    earned = sum(weight * quality for _, weight, quality, _ in runnable)
    skipped = [{'component': name, 'weight': weight}
               for name, weight, _, is_runnable in components if not is_runnable]
    ratio = (earned / runnable_max) if runnable_max else 0.0
    minimum_ratio = DIMENSION_RATIO_MINIMUMS[identifier]
    # A dimension with nothing runnable has proven nothing. Calling that `passed` (0/0 = a
    # vacuous 1.0) is the silent-skip defect one level up, so it fails on evidence instead.
    if not runnable_max:
        status = 'unevaluated'
    else:
        status = 'passed' if ratio + 1e-9 >= minimum_ratio else 'failed'
    return {
        'id': identifier,
        'label': label,
        'score': max(0, min(nominal_max, _points(earned))),
        'earned': _points(earned),
        'runnable_max': _points(runnable_max),
        'nominal_max': nominal_max,
        # `max_score` and `minimum_score` keep their old meaning (nominal weight, absolute
        # bar) so a reader comparing two runs across this change is comparing like with like.
        'max_score': nominal_max,
        'minimum_score': DIMENSION_MINIMUMS[identifier],
        'ratio': round(ratio, 4),
        'minimum_ratio': minimum_ratio,
        'evidence_fraction': round(runnable_max / nominal_max, 4) if nominal_max else 0.0,
        'skipped_weights': skipped,
        'status': status,
        'evidence': evidence,
        'actions': actions,
    }


def _review_passed(review, identifier):
    if not review:
        return 0.0
    item = next((item for item in review.get('checks', [])
                 if item.get('id') == identifier), None)
    return 1.0 if item and item.get('status') == 'passed' else 0.0


#: A check status that means the check declined to run, as opposed to running and disagreeing.
#: `missing` covers a check absent from the report entirely — the shape the old code produced
#: when an input was not supplied, and the shape that used to score a silent zero.
_NOT_RUN_STATUSES = frozenset({'missing', 'skipped', 'not_applicable', 'unavailable'})


def _check_ran(checks, name):
    check = checks.get(name)
    if not check:
        return False
    return check.get('status', 'missing') not in _NOT_RUN_STATUSES


def _review_ran(review, identifier):
    """Whether a review item reached a verdict, so its weight belongs in the denominator."""
    if not review:
        return False
    item = next((item for item in review.get('checks', [])
                 if item.get('id') == identifier), None)
    if not item:
        return False
    return item.get('status', 'missing') not in _NOT_RUN_STATUSES


def critique_gate_findings(critique, critique_validation=None):
    """Hard-gate findings derived from an independent critique report.

    Returns a list of `(id, message, evidence)`. Three distinct failures are separated because
    they call for different actions: an absent critique means the round is not finished, an
    unbound one means the critique describes bytes that no longer exist, and a critique with
    error issues means the candidate has a defect to repair.
    """
    if critique is None:
        return [('GATE_CRITIQUE_MISSING',
                 '正式评分必须提供独立批判报告 critique_report.json',
                 'critique report is missing')]

    findings = []
    if critique and critique.get('critique_kind') == 'targeted':
        findings.append((
            'GATE_CRITIQUE_NOT_FINAL',
            'score_breakdown.py 只接受最终十一项完整 critique；targeted critique '
            '仅用于中间修正，不能进入正式评分',
            'critique_kind=targeted'))
        return findings
    if critique_validation is None:
        findings.append((
            'GATE_CRITIQUE_VALIDATION_MISSING',
            '正式评分必须提供 validate_critique.py 生成的 critique_validation.json',
            'critique validation is missing'))
        detail = {}
        validation_issues = []
    else:
        detail = critique_validation.get('detail') or {}
        validation_issues = critique_validation.get('issues') or []
        if critique_validation.get('status') != 'passed':
            findings.append((
                'GATE_CRITIQUE_VALIDATION_FAILED',
                'critique_validation.status 必须为 passed；批判证据尚不可采纳',
                f'status={critique_validation.get("status", "missing")}'))

    # A critique not bound to the current inputs is not a critique of this candidate. Checked
    # before its verdict is read: an unbound report claiming `passed` would otherwise clear a
    # candidate it never examined, which is precisely how a stale review gets reused.
    stale = [issue for issue in validation_issues
             if issue.get('id') in ('CQ_DIGEST_MISMATCH', 'CQ_ARTIFACT_UNBOUND',
                                    'CQ_SOURCE_CHANGED')]
    if stale:
        findings.append((
            'GATE_CRITIQUE_STALE',
            'critique_report 未绑定当前输入哈希：配置或证据已变化，必须重新进行完整批判',
            '; '.join(item.get('message', '') for item in stale[:3])))

    inadmissible = [issue for issue in validation_issues
                    if issue.get('severity') == 'error'
                    and issue.get('id') not in ('CQ_DIGEST_MISMATCH',
                                                'CQ_ARTIFACT_UNBOUND',
                                                'CQ_SOURCE_CHANGED')]
    if inadmissible:
        findings.append((
            'GATE_CRITIQUE_INADMISSIBLE',
            'critique_report 未通过确定性校验（伪造定位符、缺少强制检查项或结论自相矛盾）',
            '; '.join(item.get('id', '') for item in inadmissible[:5])))

    error_issues = [item for item in critique.get('issues') or []
                    if item.get('severity') == 'error']
    if error_issues:
        findings.append((
            'GATE_CRITIQUE_BLOCKING_ISSUES',
            f'批判报告存在 {len(error_issues)} 个 error 问题，必须修正后重新批判',
            ', '.join(item.get('id', '?') for item in error_issues[:6])))

    unresolved = [check.get('id') for check in critique.get('checks') or []
                  if check.get('status') != 'passed']
    if unresolved:
        findings.append((
            'GATE_CRITIQUE_UNRESOLVED_CHECKS',
            f'批判的十一项检查中有 {len(unresolved)} 项未通过（failed 或 unknown）；'
            f'unknown 不计为通过',
            ', '.join(str(item) for item in unresolved[:6])))

    if detail and not detail.get('clears_candidate', False) and not findings:
        findings.append((
            'GATE_CRITIQUE_NOT_CLEARED',
            'critique validation 判定该候选未获通过',
            'clears_candidate=false'))
    return findings


def score_breakdown(validation, config, raw_ops, manifest, critique=None,
                    critique_validation=None):
    checks = _check_map(validation)
    issues = validation.get('issues', []) or []
    coverage = _coverage_detail(checks)
    critique_supplied = critique is not None
    critique_for_score = (critique if critique_validation is not None
                          and critique_validation.get('status') == 'passed' else None)
    tier = capture_tier(manifest)
    caps = dict(TIER_CAPABILITIES[tier])
    # The tier is the default reading; the manifest's own fact confidence overrides it upward.
    # A tier-A capture whose scalars were nonetheless confirmed (a runtime record naming
    # num_hidden_layers, say — evidence level 2) has answered the identity question, and
    # dropping the check because of the tier alone would refuse evidence that was supplied.
    if bc.manifest_fact_confidence(manifest) not in ('low', 'unknown'):
        caps['scalars_bound'] = True

    def validation_component(name, weight, runnable=True):
        return (f'validation:{name}', weight, _quality(checks, name, issues),
                bool(runnable) and _check_ran(checks, name))

    def critique_component(identifier, weight, runnable=True):
        # Admissibility and candidate clearance are deliberately separate. A well-formed
        # critique that found a real defect is admissible and its failed item must reduce the
        # relevant quality dimension. An inadmissible critique stays in the denominator but
        # earns zero, so supplying fabricated evidence can never improve quality.
        return (f'critique:{identifier}', weight,
                _review_passed(critique_for_score, identifier),
                bool(runnable) and critique_supplied
                and _review_ran(critique, identifier))

    # `source_model_identity` asks whether the source describes the model that ran. At tier A
    # nothing can answer that: there is no checkpoint config and no snapshot binding the source
    # to the capture, so the check is unanswerable rather than answered badly. Its 8 points
    # leave the denominator, and the unbound scalars are reported through the tier and the exit
    # conclusion instead of as a silent 8-point hole no amount of correct work could fill.
    architecture_components = [
        validation_component('architecture', 5),
        validation_component('regression', 4),
        critique_component('model_identity_and_variant', 4),
        critique_component('module_inventory_complete', 5),
        critique_component('learned_layer_vs_invocation', 4),
        critique_component('config_instantiation_params', 3),
    ]
    # The dataflow check re-derives the graph from `forward()` and compares it with the config,
    # so it carries the largest single weight here: it is the one input that can mechanically
    # contradict a claimed topology. Where source is bound, an absent dataflow check is a
    # missing input the run should have supplied, and `run_pipeline.py` now always supplies it
    # — so at tier S0/S/A a check that did not run still costs its weight. Only tier B, which
    # has no source at all, may drop these from the denominator.
    dataflow_components = [
        validation_component('dataflow', 9, runnable=not caps['source_bound']
                             or _check_ran(checks, 'dataflow')),
        validation_component('structure', 4),
        validation_component('sublayers', 4),
    ]
    dataflow_components.extend([
        critique_component('forward_call_order', 4),
        critique_component('residual_parallel_skip_topology', 5),
        critique_component('trace_module_attribution', 4),
    ])
    if caps['source_bound']:
        # Restore the hard reading: with source available the dataflow check is obligatory, so
        # its weight stays in the denominator whether or not the check was run.
        dataflow_components[0] = ('validation:dataflow', 9,
                                  _quality(checks, 'dataflow', issues), True)
    boundary_components = [
        validation_component('structure', 3),
        validation_component('coverage', 2),
        validation_component('sublayers', 3),
    ]
    boundary_components.extend([
        critique_component('layer_and_fusion_boundaries', 7),
        critique_component('runtime_vs_model_classification', 5),
    ])

    exact_pct = coverage.get('exact_coverage_pct', 0)
    try:
        exact_pct = max(0.0, min(100.0, float(exact_pct)))
    except (TypeError, ValueError):
        exact_pct = 0.0
    kernel_coverage = 20 * exact_pct / 100.0

    # Shape validation is no longer scored. `shape_semantic` is an annotation layered on the
    # profiler's dims: when absent there is nothing to be wrong about, so the old dimension
    # handed out 10 points for a check that could not fail (see the plan's §2.8). It remains
    # available as a debugging run (`run_validation.py --with-shapes`) and its findings still
    # appear in the validation report; they just no longer buy score.
    #
    # `trace_instance_scope` is gone for the same reason in the other direction: a capture's
    # scope is a property of THIS capture, and awarding points for declaring it rewarded
    # bookkeeping rather than a correct decomposition. `trace_instances` itself is kept in the
    # config and gated by validation, not by score.

    architecture_config = config.get('architecture', {})
    nodes = list(_walk_nodes({
        'structures': config.get('structures', {}),
        'stages': config.get('stages', []),
        'runtime_auxiliary': config.get('runtime_auxiliary', []),
    }))
    code_ref_ratio = (sum(1 for n in nodes if n.get('code_ref')) / len(nodes)) if nodes else 0
    evidence_score = 0
    if architecture_config.get('source_of_truth'):
        evidence_score += 1
    if code_ref_ratio >= 0.9:
        evidence_score += 2
    elif code_ref_ratio >= 0.5:
        evidence_score += 1
    manifest_refs = list(manifest.get('source_of_truth', []))
    manifest_refs += [g.get('source_ref') for g in manifest.get('layer_groups', [])]
    manifest_refs += [p.get('source_ref') for p in manifest.get('prediction_modules', [])]
    if manifest_refs and all(ref and ref != 'unknown' for ref in manifest_refs):
        evidence_score += 1
    # An `evidence_gaps` entry records a file the run could not read (typically the checkpoint
    # `config.json`), not a traceability failure of the decomposition. Every architecture fact
    # still resolves to a source line, which is what this dimension measures. Withholding the
    # point would make an unreachable path indistinguishable from a missing `source_ref`, so the
    # gap is reported in the evidence list instead of deducted.
    manifest_gaps = manifest.get('evidence_gaps') or []
    evidence_score += 1

    # §5.7.1 guardrail. Demoting the manifest/trace check to `info` removed the only thing
    # that ever contradicted `num_main_layers`. Left alone, an unconfirmed layer count -- a
    # Python default arg that the deployed weights may override -- would score full marks for
    # 架构完整性, which is the same defect as the old Shape dimension: points for evidence that
    # cannot be wrong. So the layer count must cost something whenever no checkpoint
    # `config.json` confirmed it. It is a deduction rather than a hard gate because the source
    # remains the architecture truth; the missing file makes the number unproven, not wrong.
    # …with one change since that note was written: the cap now applies only where the tier
    # says the scalar COULD have been bound. At tier A the scalar is unbindable from the
    # supplied inputs, so capping the dimension below its own minimum made the bar unreachable
    # no matter how correct the decomposition was — a permanent fail that said nothing about
    # the breakdown. There, `source_model_identity` leaves the denominator and the conclusion
    # is capped at `verified_unbound_scalars`, which reports the same gap without pretending
    # the structure is wrong. At tier S0/S the input exists, so failing to bind it is a real
    # omission and the original cap still bites.
    layer_confidence = bc.manifest_fact_confidence(manifest)
    layer_unconfirmed = layer_confidence in ('low', 'unknown')
    layer_note = None
    cap_architecture = layer_unconfirmed and caps['scalars_bound']
    if cap_architecture:
        # Capped BELOW the dimension minimum (22), not merely below the maximum. §5.7.1
        # option A makes the checkpoint `config.json` a required Mode A input: with it absent
        # the layer count has no evidence at all, and a shortfall of one or two points would
        # still let the run clear 95 — which is the outcome that option exists to forbid.
        # The architecture cap is applied to the assembled dimension below; only the evidence
        # deduction can be taken here, since it feeds a single component.
        evidence_score = min(evidence_score, DIMENSION_MINIMUMS['evidence_traceability'])
        layer_note = (f'num_main_layers={manifest.get("num_main_layers")} '
                      f'source=python_default, unconfirmed'
                      f'（checkpoint config.json 未绑定，confidence={layer_confidence}）：'
                      f'架构完整性不得达到分项最低分，正式流程需先绑定 checkpoint')

    if layer_unconfirmed and not caps['scalars_bound']:
        # Tier A: the scalar cannot be bound from the supplied inputs. The final critique still
        # evaluates the candidate's architecture, while the evidence tier limits the conclusion.
        layer_note = (f'num_main_layers={manifest.get("num_main_layers")} '
                      f'source=python_default, unconfirmed'
                      f'（capture_tier={tier}：输入不含 checkpoint config.json 或 source_snapshot，'
                      f'该标量无法绑定）：架构语义仍由最终 critique 评价，'
                      f'结论上限为 verified_unbound_scalars，不据此判定拆解错误')

    coverage_components = [
        ('coverage:exact_pct', 15, exact_pct / 100.0, True),
        critique_component('op_coverage_and_duplicate_ownership', 5),
    ]
    evidence_components = [
        ('evidence:refs', 3, evidence_score / 5.0, True),
        critique_component('source_ref_authenticity', 2),
    ]
    semantic_evidence = 'critique_report.json'

    dimensions = [
        _dimension('architecture_integrity', '架构完整性', architecture_components,
                   ['validation:architecture', 'validation:regression', semantic_evidence,
                    'model_manifest.json', f'capture_tier={tier}']
                   + ([layer_note] if layer_note else []),
                   ['按 manifest 和源码修正层数、层类型、MTP learned layer 与 invocation。']
                   + (['绑定 checkpoint config.json 以确认 num_main_layers。']
                      if layer_unconfirmed else [])),
        _dimension('dataflow_branch_correctness', '数据流与分支正确性', dataflow_components,
                   ['validation:dataflow', 'validation:structure', 'validation:sublayers',
                    semantic_evidence, 'structures'],
                   ['恢复源码中的 Q/K/V、残差、MoE/GQA/MLA 分支；确保父节点等于子节点 op union。',
                    '提供 dataflow_source.json（或 --model-source）让分支拓扑可机器核对。']),
        _dimension('layer_submodule_boundaries', 'Layer/子模块边界', boundary_components,
                   ['validation:structure', 'validation:coverage', 'validation:sublayers',
                    semantic_evidence],
                   ['根据源码 anchor 和 op 时序收紧 layer/submodule 边界，消除跨层和重叠归属。']),
        # Kernel coverage and evidence traceability are computed from inputs that are always
        # present when the run got this far (the op list, the config), so both are single
        # always-runnable components: there is no tier at which they cannot be evaluated.
        _dimension('kernel_exact_coverage', 'Kernel 精确覆盖',
                   coverage_components,
                   [f'exact_coverage_pct={exact_pct}',
                    f'total_ops={len(raw_ops.get("operators", []))}'],
                   ['逐个处理 missing/unmapped/duplicate/out_of_range；主计算 Kernel 不得 excluded。']),
        _dimension('evidence_traceability', '证据与可追溯性',
                   evidence_components,
                   [f'code_ref_ratio={code_ref_ratio:.3f}',
                    f'manifest_evidence_gaps={len(manifest_gaps)}']
                   + ([f'证据缺口（不扣分，仅记录）: {manifest_gaps[0]}'] if manifest_gaps else [])
                   + ([layer_note] if layer_note else []),
                   ['为架构事实和结构节点补充真实 source_ref/code_ref，解决 manifest evidence gaps。']),
    ]
    # The architecture cap is applied after the fact so it acts on the dimension as scored,
    # rather than on one component: the cap is a statement about the dimension's total. It is
    # keyed on `cap_architecture`, not on `layer_note` — tier A also carries a note, and capping
    # there would restore the unreachable bar this rework exists to remove.
    if cap_architecture:
        arch = dimensions[0]
        capped = min(arch['earned'], DIMENSION_MINIMUMS['architecture_integrity'] - 1)
        arch['earned'] = arch['score'] = _points(capped)
        arch['ratio'] = round(capped / arch['runnable_max'], 4) if arch['runnable_max'] else 0.0
        arch['status'] = ('passed' if arch['ratio'] + 1e-9 >= arch['minimum_ratio']
                          else 'failed')

    blocking = []

    def block(identifier, dimension, message, evidence):
        blocking.append({'id': identifier, 'dimension': dimension,
                         'message': message, 'evidence': evidence})

    # Data-availability warnings do not block. `passed_with_warnings` whose every warning is an
    # unconfirmable-scalar report describes inputs that lack a fact, not a decomposition that got
    # one wrong; the run is still gated on `error`-severity issues and on every other warning.
    blocking_validation_issues = [
        issue for issue in validation.get('issues', [])
        if issue.get('severity') == 'error'
        or (issue.get('severity') == 'warning'
            and issue.get('id') not in DATA_AVAILABILITY_ISSUE_IDS)
    ]
    # A formal pass is EXACTLY `passed`. `passed_with_warnings` only exists because someone
    # passed --allow-warnings, i.e. chose to not act on open warnings; accepting it here made
    # the override a route to a formal score. Data-availability issues no longer need that
    # loophole: `manifest_trace` reports as `info`, so a partial capture reaches `passed`.
    if validation.get('status') != 'passed' or blocking_validation_issues:
        block('GATE_VALIDATION', 'global', '统一校验状态必须精确为 passed',
              f'status={validation.get("status", "missing")}')
        for index, issue in enumerate(blocking_validation_issues):
            block(f'VALIDATION_{issue.get("id", "ISSUE")}_{index}',
                  issue.get('check', 'global'), issue.get('message', 'validation issue'),
                  issue.get('node_path', '<unknown>'))

    critique_blocking = []
    for identifier, message, evidence in critique_gate_findings(
            critique, critique_validation):
        critique_blocking.append({'id': identifier, 'dimension': 'global',
                                  'message': message, 'evidence': evidence})
    # The final critique is a formal semantic gate, not metadata on an otherwise publishable
    # score. Keep the dedicated projection for diagnostics and merge the same findings into
    # `hard_gates` so every consumer, including older ones that only read `convertible`, blocks.
    blocking.extend(critique_blocking)

    for field in ('unmapped', 'missing', 'duplicate', 'out_of_range'):
        count = coverage.get(field, 0) or 0
        if count:
            block(f'GATE_COVERAGE_{field.upper()}', 'kernel_exact_coverage',
                  f'coverage.{field} 必须为 0', f'{field}={count}')
    raw_total = len(raw_ops.get('operators', []))
    coverage_total = coverage.get('total_ops')
    if coverage_total is None:
        block('GATE_NO_COVERAGE_TOTAL', 'kernel_exact_coverage',
              'coverage 必须提供 total_ops', 'coverage.total_ops is missing')
    elif coverage_total != raw_total:
        block('GATE_INPUT_MISMATCH', 'kernel_exact_coverage',
              '评分输入不属于同一次拆解，raw_ops 数量与 validation coverage 不一致',
              f'raw_ops={raw_total}, coverage.total_ops={coverage_total}')
    if config.get('unmapped_ops'):
        block('GATE_CONFIG_UNMAPPED', 'kernel_exact_coverage',
              'unmapped_ops 必须为空', f'groups={len(config["unmapped_ops"])}')
    if config.get('migration', {}).get('status') == 'legacy_unverified':
        block('GATE_LEGACY_UNVERIFIED', 'architecture_integrity',
              'legacy_unverified 配置必须依据源码重新验证', 'migration.status=legacy_unverified')
    if not architecture_config.get('source_of_truth'):
        block('GATE_NO_SOURCE_TRUTH', 'evidence_traceability',
              'Mode A 精确拆解必须提供 architecture.source_of_truth', 'source_of_truth is empty')
    if not nodes or not any(n.get('code_ref') for n in nodes):
        block('GATE_NO_CODE_REF', 'evidence_traceability',
              '结构树必须至少具有可追溯的 code_ref', 'no structure node has code_ref')

    total = sum(d['score'] for d in dimensions)
    runnable_total = sum(d['runnable_max'] for d in dimensions)
    nominal_total = sum(d['nominal_max'] for d in dimensions)
    # Correctness among what could be checked, and how much could be checked. The two are
    # reported separately on purpose: collapsing them into one number is what made an
    # incomplete capture indistinguishable from a wrong breakdown.
    correctness = (total / runnable_total) if runnable_total else 0.0
    evidence_fraction = (runnable_total / nominal_total) if nominal_total else 0.0
    # The three values the contract requires, kept separate all the way to the output.
    # `quality_rate` is correctness among checkable items; `cap` is what the inputs allow;
    # `final_score` is their product and is a *description*, never a gate.
    quality_rate = correctness
    cap, cap_detail = evidence_cap(manifest, raw_ops)
    final_score = round(quality_rate * cap, 2)

    failed_dimensions = [d['id'] for d in dimensions if d['status'] in ('failed',
                                                                       'unevaluated')]
    core_failed = [d for d in dimensions
                   if d['id'] in CORE_MINIMUMS and d['status'] != 'passed']
    if correctness + 1e-9 < MIN_TOTAL_RATIO and not failed_dimensions:
        deficits = sorted(dimensions, key=lambda d: d['runnable_max'] - d['earned'],
                          reverse=True)
        failed_dimensions = [d['id'] for d in deficits if d['earned'] < d['runnable_max']][:3]
    # Read off `quality_rate`, never off `final_score`. Gating on the product would make a
    # correct breakdown fail for missing a checkpoint config it never controlled.
    correct = (quality_rate + 1e-9 >= MIN_QUALITY_RATE and not core_failed
               and not [d for d in dimensions if d['status'] == 'failed'])
    eligible = correct and not blocking and cap > 0
    # `passed_at_cap` needs all three legs: quality at the bar, every hard gate clear, and a
    # final critique that actually cleared the candidate.
    critique_cleared = bool(
        critique is not None
        and critique_validation is not None
        and critique_validation.get('status') == 'passed'
        and ((critique_validation.get('detail') or {}).get('clears_candidate') is True)
        and not critique_blocking)
    passed_at_cap = bool(eligible and critique_cleared)

    required_actions = []
    for item in blocking:
        required_actions.append(item['message'])
    for dimension in dimensions:
        if dimension['id'] in failed_dimensions:
            required_actions.extend(dimension['actions'])
    required_actions = list(dict.fromkeys(required_actions))

    # The exit conclusion. `needs_iteration` means a check ran and disagreed — there is work to
    # do on the breakdown. Everything else means nothing contradicted the breakdown, and the
    ceiling = effective_ceiling(tier, caps)
    # conclusion then reports how far the evidence went: `verified` (scalars and structure both
    # bound), `verified_unbound_scalars` (structure verified against source, scalars resting on
    # unbound defaults), `structure_unverified` (no source to check topology against),
    # `exploratory` (too little evidence for the number to carry weight). A capture cannot talk
    # its way past its tier, so the tier ceiling is applied last.
    if not eligible:
        conclusion = 'needs_iteration'
    elif evidence_fraction + 1e-9 < MIN_EVIDENCE_FRACTION:
        conclusion = 'exploratory'
    else:
        conclusion = _cap_conclusion('verified', ceiling)

    return {
        'schema_version': 1,
        'status': conclusion,
        # Retained so a consumer written against the two-value status keeps working: it asked
        # "may this be converted", which is exactly what this answers.
        'convertible': conclusion in CONVERTIBLE_CONCLUSIONS,
        'capture_tier': tier,
        'tier_ceiling': ceiling,
        'nominal_tier_ceiling': TIER_CEILING[tier],
        'tier_reason': (manifest.get('capture_provenance') or {}).get('tier_reason'),
        # ---- the three independent values -------------------------------------------------
        # Reported side by side so no consumer has to reconstruct one from another. A capture
        # capped at 90 that passes every runnable check has `quality_rate` 1.0 and
        # `final_score` 90: correct work, honestly-bounded evidence. Collapsing these would
        # make that indistinguishable from a breakdown that got 10% of its checks wrong.
        'quality_rate': round(quality_rate, 4),
        'evidence_cap': cap,
        'final_score': final_score,
        'evidence_cap_detail': cap_detail,
        'minimum_quality_rate': MIN_QUALITY_RATE,
        # True when the critique-independent gates are met: quality at or above the bar, every
        # core dimension passing, and no hard gate blocking. Named `_at_cap` because a pass is
        # always relative to what the evidence could show -- it does not claim 100.
        'passed_at_cap': passed_at_cap,
        'critique_cleared': critique_cleared,
        'critique_gates': {'passed': not critique_blocking,
                           'blocking_issues': critique_blocking},
        'score': total,
        'max_score': 100,
        'minimum_score': MIN_TOTAL_SCORE,
        'runnable_max': _points(runnable_total),
        'nominal_max': nominal_total,
        'correctness_ratio': round(correctness, 4),
        'minimum_correctness_ratio': MIN_TOTAL_RATIO,
        'evidence_fraction': round(evidence_fraction, 4),
        'minimum_evidence_fraction': MIN_EVIDENCE_FRACTION,
        'validation_status': validation.get('status', 'missing'),
        'dimensions': dimensions,
        'failed_dimensions': failed_dimensions,
        'hard_gates': {'passed': not blocking, 'blocking_issues': blocking},
        'required_actions': required_actions,
        'constraints': [
            '不得降低评分阈值或分项阈值',
            '不得删除主计算 Kernel 或扩大 excluded_profiler_ops 来提分',
            '不得为提高 correctness 而把可运行的检查标为 skipped：分母只允许因输入确实缺失而缩小',
            '下一轮从历史最佳配置开始，只修正有证据的问题',
            'analysis_config/raw_ops/model_manifest 任一变化后必须重新完成独立 critique',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description='Score a validated model breakdown')
    parser.add_argument('-v', '--validation-report', required=True)
    parser.add_argument('-c', '--config', required=True)
    parser.add_argument('-r', '--raw-ops', required=True)
    parser.add_argument('-m', '--manifest', required=True)
    parser.add_argument('-q', '--critique-report',
                        help='independent critique report (required for a formal pass)')
    parser.add_argument('--critique-validation',
                        help='output of validate_critique.py for the above')
    parser.add_argument('-o', '--output')
    args = parser.parse_args()

    critique = _load(args.critique_report) if args.critique_report else None
    critique_validation = (_load(args.critique_validation)
                           if args.critique_validation else None)
    report = score_breakdown(_load(args.validation_report), _load(args.config),
                             _load(args.raw_ops), _load(args.manifest), critique,
                             critique_validation)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
        print(f'breakdown score 已写入: {args.output}  status={report["status"]} '
              f'tier={report["capture_tier"]} '
              f'score={report["score"]}/{report["runnable_max"]} '
              f'(nominal {report["max_score"]}) '
              f'correctness={report["correctness_ratio"]:.3f} '
              f'evidence={report["evidence_fraction"]:.3f}')
    else:
        print(text)
    # Exit 0 for any conclusion that may be converted into a report. `exploratory` and
    # `needs_iteration` exit non-zero: the first has too little evidence to publish, the second
    # has open findings.
    sys.exit(0 if report['convertible'] else 1)


if __name__ == '__main__':
    main()
