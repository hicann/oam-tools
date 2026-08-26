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
"""Deterministically score a schema-v2 model breakdown and emit one JSON report."""
import argparse
import json
import os
import sys
from dataclasses import dataclass

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
#: `cann-perf-breakdown-to-ui-json/scripts/breakdown_paths.py:CONVERTIBLE_STATUSES`.
CONVERTIBLE_CONCLUSIONS = ('verified', 'verified_unbound_scalars', 'structure_unverified')

_CONCLUSION_ORDER = ('verified', 'verified_unbound_scalars', 'structure_unverified',
                     'exploratory', 'needs_iteration')


@dataclass(frozen=True)
class _ScoreComponents:
    checks: dict
    tier: str
    capabilities: dict
    architecture: list
    dataflow: list
    boundaries: list


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
    counted = []
    for issue in issues:
        if (issue.get('check') == name and issue.get('severity') == 'warning'
                and issue.get('id') not in DATA_AVAILABILITY_ISSUE_IDS):
            counted.append(issue)
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


def _semantic_passed(review, identifier):
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


def _semantic_ran(review, identifier):
    """Whether a semantic item reached a verdict, so its weight belongs in the denominator."""
    if not review:
        return False
    item = next((item for item in review.get('checks', [])
                 if item.get('id') == identifier), None)
    if not item:
        return False
    return item.get('status', 'missing') not in _NOT_RUN_STATUSES


#: A semantic-review finding whose only claim is that an architecture scalar could not be
#: confirmed against a checkpoint `config.json`. Under the code-first rule the source is the
#: architecture truth and the trace cannot adjudicate a scalar, so such a finding records an
#: evidence gap — it does not refute any of the nine per-item semantic conclusions. Scoring
#: therefore keeps the per-item verdicts instead of discarding all of them. `error` findings,
#: and warnings on any other check, still void the review: those do contest the review's own
#: conclusions. The unconfirmed scalar remains visible as an `evidence_traceability` deduction
#: and as the architecture/regression `warning` quality factor.
EVIDENCE_GAP_FINDING_CHECKS = frozenset({'source_model_identity'})


def _semantic_items_usable(review, semantic_check):
    """Whether per-item semantic verdicts may be scored despite a non-passed review.

    Returns False unless every issue blocking the review is an evidence-gap finding.
    """
    if not review:
        return False
    if semantic_check.get('status') == 'passed':
        return True
    blocking = [f for f in review.get('findings', [])
                if f.get('severity') in ('error', 'warning')]
    if not blocking:
        return False
    return all(f.get('severity') == 'warning'
               and f.get('check_id') in EVIDENCE_GAP_FINDING_CHECKS
               for f in blocking)


def _validation_component(checks, issues, name, weight, runnable=True):
    return (f'validation:{name}', weight, _quality(checks, name, issues),
            bool(runnable) and _check_ran(checks, name))


def _semantic_component(review, trusted_review, identifier, weight, runnable=True):
    return (f'semantic:{identifier}', weight,
            _semantic_passed(trusted_review, identifier),
            bool(runnable) and review is not None and _semantic_ran(review, identifier))


def _score_components(validation, manifest, semantic_review):
    checks = _check_map(validation)
    issues = validation.get('issues', []) or []
    semantic_for_score = (semantic_review if _semantic_items_usable(
        semantic_review, checks.get('semantic_review', {})) else None)
    tier = capture_tier(manifest)
    caps = dict(TIER_CAPABILITIES[tier])
    if bc.manifest_fact_confidence(manifest) not in ('low', 'unknown'):
        caps['scalars_bound'] = True

    def validation_component(name, weight, runnable=True):
        return _validation_component(checks, issues, name, weight, runnable)

    def semantic_component(identifier, weight, runnable=True):
        return _semantic_component(
            semantic_review, semantic_for_score, identifier, weight, runnable)

    architecture = [
        validation_component('architecture', 5),
        validation_component('regression', 4),
        semantic_component('source_model_identity', 8, runnable=caps['scalars_bound']),
        semantic_component('module_inventory_complete', 8),
    ]
    dataflow = [
        validation_component('dataflow', 9, runnable=not caps['source_bound']
                             or _check_ran(checks, 'dataflow')),
        validation_component('structure', 4),
        validation_component('sublayers', 4),
        semantic_component('dataflow_edges_complete', 4),
        semantic_component('branch_topology_correct', 5),
        semantic_component('residual_paths_correct', 4),
    ]
    if caps['source_bound']:
        dataflow[0] = ('validation:dataflow', 9, _quality(checks, 'dataflow', issues), True)
    boundaries = [
        validation_component('structure', 3),
        validation_component('coverage', 2),
        validation_component('sublayers', 3),
        semantic_component('layer_boundaries_correct', 3),
        semantic_component('tail_stages_correct', 3),
        semantic_component('runtime_nodes_observed', 3),
        semantic_component('code_refs_resolve', 3),
    ]
    return _ScoreComponents(checks, tier, caps, architecture, dataflow, boundaries)


def _normalized_coverage(coverage):
    try:
        return max(0.0, min(100.0, float(coverage.get('exact_coverage_pct', 0))))
    except (TypeError, ValueError):
        return 0.0


def _evidence_details(config, manifest):
    architecture = config.get('architecture', {})
    nodes = list(_walk_nodes({
        'structures': config.get('structures', {}),
        'stages': config.get('stages', []),
        'runtime_auxiliary': config.get('runtime_auxiliary', []),
    }))
    code_ref_ratio = (sum(1 for node in nodes if node.get('code_ref')) / len(nodes)
                      if nodes else 0)
    score = int(bool(architecture.get('source_of_truth')))
    if code_ref_ratio >= 0.9:
        score += 2
    elif code_ref_ratio >= 0.5:
        score += 1
    manifest_refs = list(manifest.get('source_of_truth', []))
    manifest_refs += [group.get('source_ref') for group in manifest.get('layer_groups', [])]
    manifest_refs += [module.get('source_ref')
                      for module in manifest.get('prediction_modules', [])]
    if manifest_refs and all(ref and ref != 'unknown' for ref in manifest_refs):
        score += 1
    gaps = manifest.get('evidence_gaps') or []
    return architecture, nodes, code_ref_ratio, score + 1, gaps


def _layer_guardrail(manifest, tier, caps, evidence_score):
    confidence = bc.manifest_fact_confidence(manifest)
    unconfirmed = confidence in ('low', 'unknown')
    cap_architecture = unconfirmed and caps['scalars_bound']
    note = None
    if cap_architecture:
        evidence_score = min(evidence_score, DIMENSION_MINIMUMS['evidence_traceability'])
        note = (f'num_main_layers={manifest.get("num_main_layers")} '
                f'source=python_default, unconfirmed'
                f'（checkpoint config.json 未绑定，confidence={confidence}）：'
                f'架构完整性不得达到分项最低分，正式流程需先绑定 checkpoint')
    if unconfirmed and not caps['scalars_bound']:
        note = (f'num_main_layers={manifest.get("num_main_layers")} '
                f'source=python_default, unconfirmed'
                f'（capture_tier={tier}：输入不含 checkpoint config.json 或 source_snapshot，'
                f'该标量无法绑定）：source_model_identity 退出分母，'
                f'结论上限为 verified_unbound_scalars，不据此判定拆解错误')
    return unconfirmed, note, cap_architecture, evidence_score


def _build_dimensions(components, evidence, raw_ops, tier, layer):
    architecture_components, dataflow_components, boundary_components = components
    architecture, nodes, code_ref_ratio, evidence_score, manifest_gaps = evidence
    exact_pct, layer_unconfirmed, layer_note, cap_architecture = layer
    dimensions = [
        _dimension('architecture_integrity', '架构完整性', architecture_components,
                   ['validation:architecture', 'validation:regression', 'semantic_review',
                    'model_manifest.json', f'capture_tier={tier}']
                   + ([layer_note] if layer_note else []),
                   ['按 manifest 和源码修正层数、层类型、MTP learned layer 与 invocation。']
                   + (['绑定 checkpoint config.json 以确认 num_main_layers。']
                      if layer_unconfirmed else [])),
        _dimension('dataflow_branch_correctness', '数据流与分支正确性', dataflow_components,
                   ['validation:dataflow', 'validation:structure', 'validation:sublayers',
                    'semantic_review', 'structures'],
                   ['恢复源码中的 Q/K/V、残差、MoE/GQA/MLA 分支；确保父节点等于子节点 op union。',
                    '提供 dataflow_source.json（或 --model-source）让分支拓扑可机器核对。']),
        _dimension('layer_submodule_boundaries', 'Layer/子模块边界', boundary_components,
                   ['validation:structure', 'validation:coverage', 'validation:sublayers',
                    'semantic_review'],
                   ['根据源码 anchor 和 op 时序收紧 layer/submodule 边界，消除跨层和重叠归属。']),
        _dimension('kernel_exact_coverage', 'Kernel 精确覆盖',
                   [('coverage:exact_pct', 20, exact_pct / 100.0, True)],
                   [f'exact_coverage_pct={exact_pct}',
                    f'total_ops={len(raw_ops.get("operators", []))}'],
                   ['逐个处理 missing/unmapped/duplicate/out_of_range；主计算 Kernel 不得 excluded。']),
        _dimension('evidence_traceability', '证据与可追溯性',
                   [('evidence:refs', 5, evidence_score / 5.0, True)],
                   [f'code_ref_ratio={code_ref_ratio:.3f}',
                    f'manifest_evidence_gaps={len(manifest_gaps)}']
                   + ([f'证据缺口（不扣分，仅记录）: {manifest_gaps[0]}'] if manifest_gaps else [])
                   + ([layer_note] if layer_note else []),
                   ['为架构事实和结构节点补充真实 source_ref/code_ref，解决 manifest evidence gaps。']),
    ]
    if cap_architecture:
        arch = dimensions[0]
        capped = min(arch['earned'], DIMENSION_MINIMUMS['architecture_integrity'] - 1)
        arch['earned'] = arch['score'] = _points(capped)
        arch['ratio'] = round(capped / arch['runnable_max'], 4) if arch['runnable_max'] else 0.0
        arch['status'] = ('passed' if arch['ratio'] + 1e-9 >= arch['minimum_ratio']
                          else 'failed')
    return architecture, nodes, dimensions


def _block(blocking, identifier, dimension, message, evidence):
    blocking.append({'id': identifier, 'dimension': dimension,
                     'message': message, 'evidence': evidence})


def _validation_gates(validation, blocking):
    blocking_issues = []
    for issue in validation.get('issues', []):
        is_error = issue.get('severity') == 'error'
        is_blocking_warning = (issue.get('severity') == 'warning'
                               and issue.get('id') not in DATA_AVAILABILITY_ISSUE_IDS)
        if is_error or is_blocking_warning:
            blocking_issues.append(issue)
    if validation.get('status') == 'passed' and not blocking_issues:
        return
    _block(blocking, 'GATE_VALIDATION', 'global',
           '统一校验状态必须精确为 passed',
           f'status={validation.get("status", "missing")}')
    for index, issue in enumerate(blocking_issues):
        _block(blocking, f'VALIDATION_{issue.get("id", "ISSUE")}_{index}',
               issue.get('check', 'global'), issue.get('message', 'validation issue'),
               issue.get('node_path', '<unknown>'))


def _semantic_gates(validation, checks, review, blocking):
    semantic_check = checks.get('semantic_review')
    if review is None:
        _block(blocking, 'GATE_SEMANTIC_REVIEW_MISSING', 'global',
               '正式评分必须提供 semantic_review.json', 'semantic review is missing')
        return
    if not semantic_check or semantic_check.get('status') != 'passed':
        stale = any(issue.get('id') == 'SR_DIGEST_MISMATCH'
                    for issue in validation.get('issues', []))
        items_usable = _semantic_items_usable(review, semantic_check or {})
        all_items_passed = all(item.get('status') == 'passed'
                               for item in review.get('checks', []))
        if stale or not (items_usable and all_items_passed):
            identifier = ('GATE_SEMANTIC_REVIEW_STALE' if stale
                          else 'GATE_SEMANTIC_REVIEW_FAILED')
            message = ('semantic_review 与当前输入版本不一致，必须重新审查' if stale
                       else 'semantic_review 未通过全部源码/Trace 语义检查')
            status = semantic_check.get('status') if semantic_check else 'missing'
            _block(blocking, identifier, 'global', message,
                   f'validation.semantic_review={status}')
        return
    if review.get('status') != 'passed':
        _block(blocking, 'GATE_SEMANTIC_REVIEW_FAILED', 'global',
               'semantic_review.status 必须为 passed',
               f'status={review.get("status", "missing")}')


def _coverage_gates(config, raw_ops, coverage, blocking):
    for field in ('unmapped', 'missing', 'duplicate', 'out_of_range'):
        count = coverage.get(field, 0) or 0
        if count:
            _block(blocking, f'GATE_COVERAGE_{field.upper()}', 'kernel_exact_coverage',
                   f'coverage.{field} 必须为 0', f'{field}={count}')
    raw_total = len(raw_ops.get('operators', []))
    coverage_total = coverage.get('total_ops')
    if coverage_total is None:
        _block(blocking, 'GATE_NO_COVERAGE_TOTAL', 'kernel_exact_coverage',
               'coverage 必须提供 total_ops', 'coverage.total_ops is missing')
    elif coverage_total != raw_total:
        _block(blocking, 'GATE_INPUT_MISMATCH', 'kernel_exact_coverage',
               '评分输入不属于同一次拆解，raw_ops 数量与 validation coverage 不一致',
               f'raw_ops={raw_total}, coverage.total_ops={coverage_total}')
    if config.get('unmapped_ops'):
        _block(blocking, 'GATE_CONFIG_UNMAPPED', 'kernel_exact_coverage',
               'unmapped_ops 必须为空', f'groups={len(config["unmapped_ops"])}')


def _config_gates(config, architecture, nodes, blocking):
    if config.get('migration', {}).get('status') == 'legacy_unverified':
        _block(blocking, 'GATE_LEGACY_UNVERIFIED', 'architecture_integrity',
               'legacy_unverified 配置必须依据源码重新验证',
               'migration.status=legacy_unverified')
    if not architecture.get('source_of_truth'):
        _block(blocking, 'GATE_NO_SOURCE_TRUTH', 'evidence_traceability',
               'Mode A 精确拆解必须提供 architecture.source_of_truth',
               'source_of_truth is empty')
    if not nodes or not any(node.get('code_ref') for node in nodes):
        _block(blocking, 'GATE_NO_CODE_REF', 'evidence_traceability',
               '结构树必须至少具有可追溯的 code_ref', 'no structure node has code_ref')


def _hard_gates(inputs):
    blocking = []
    _validation_gates(inputs['validation'], blocking)
    _semantic_gates(inputs['validation'], inputs['checks'], inputs['semantic_review'], blocking)
    _coverage_gates(inputs['config'], inputs['raw_ops'], inputs['coverage'], blocking)
    _config_gates(inputs['config'], inputs['architecture'], inputs['nodes'], blocking)
    return blocking


def _score_summary(dimensions):
    total = sum(item['score'] for item in dimensions)
    runnable_total = sum(item['runnable_max'] for item in dimensions)
    nominal_total = sum(item['nominal_max'] for item in dimensions)
    correctness = (total / runnable_total) if runnable_total else 0.0
    evidence_fraction = (runnable_total / nominal_total) if nominal_total else 0.0
    return total, runnable_total, nominal_total, correctness, evidence_fraction


def _failed_dimensions(dimensions, correctness):
    failed = [item['id'] for item in dimensions
              if item['status'] in ('failed', 'unevaluated')]
    core_failed = [item for item in dimensions
                   if item['id'] in CORE_MINIMUMS and item['status'] != 'passed']
    if correctness + 1e-9 < MIN_TOTAL_RATIO and not failed:
        deficits = sorted(dimensions,
                          key=lambda item: item['runnable_max'] - item['earned'],
                          reverse=True)
        failed = [item['id'] for item in deficits
                  if item['earned'] < item['runnable_max']][:3]
    correct = (correctness + 1e-9 >= MIN_TOTAL_RATIO and not core_failed
               and not [item for item in dimensions if item['status'] == 'failed'])
    return failed, correct


def _required_actions(blocking, dimensions, failed_dimensions):
    actions = [item['message'] for item in blocking]
    for dimension in dimensions:
        if dimension['id'] in failed_dimensions:
            actions.extend(dimension['actions'])
    return list(dict.fromkeys(actions))


def _score_conclusion(eligible, evidence_fraction, tier, caps):
    ceiling = effective_ceiling(tier, caps)
    if not eligible:
        return 'needs_iteration', ceiling
    if evidence_fraction + 1e-9 < MIN_EVIDENCE_FRACTION:
        return 'exploratory', ceiling
    return _cap_conclusion('verified', ceiling), ceiling


def _score_report(inputs):
    conclusion, ceiling = _score_conclusion(
        inputs['eligible'], inputs['evidence_fraction'], inputs['tier'], inputs['caps'])
    return {
        'schema_version': 1,
        'status': conclusion,
        'convertible': conclusion in CONVERTIBLE_CONCLUSIONS,
        'capture_tier': inputs['tier'],
        'tier_ceiling': ceiling,
        'nominal_tier_ceiling': TIER_CEILING[inputs['tier']],
        'tier_reason': (inputs['manifest'].get('capture_provenance') or {}).get('tier_reason'),
        'score': inputs['total'],
        'max_score': 100,
        'minimum_score': MIN_TOTAL_SCORE,
        'runnable_max': _points(inputs['runnable_total']),
        'nominal_max': inputs['nominal_total'],
        'correctness_ratio': round(inputs['correctness'], 4),
        'minimum_correctness_ratio': MIN_TOTAL_RATIO,
        'evidence_fraction': round(inputs['evidence_fraction'], 4),
        'minimum_evidence_fraction': MIN_EVIDENCE_FRACTION,
        'validation_status': inputs['validation'].get('status', 'missing'),
        'dimensions': inputs['dimensions'],
        'failed_dimensions': inputs['failed_dimensions'],
        'hard_gates': {'passed': not inputs['blocking'],
                       'blocking_issues': inputs['blocking']},
        'required_actions': inputs['required_actions'],
        'constraints': [
            '不得降低评分阈值或分项阈值',
            '不得删除主计算 Kernel 或扩大 excluded_profiler_ops 来提分',
            '不得为提高 correctness 而把可运行的检查标为 skipped：分母只允许因输入确实缺失而缩小',
            '下一轮从历史最佳配置开始，只修正有证据的问题',
            'analysis_config/raw_ops/model_manifest 任一变化后必须重新完成 semantic review',
        ],
    }


def score_breakdown(validation, config, raw_ops, manifest, semantic_review=None):
    components = _score_components(validation, manifest, semantic_review)
    checks = components.checks
    tier = components.tier
    caps = components.capabilities
    coverage = _coverage_detail(checks)

    exact_pct = _normalized_coverage(coverage)
    evidence = _evidence_details(config, manifest)
    layer_unconfirmed, layer_note, cap_architecture, evidence_score = _layer_guardrail(
        manifest, tier, caps, evidence[3])
    evidence = (*evidence[:3], evidence_score, evidence[4])
    architecture_config, nodes, dimensions = _build_dimensions(
        (components.architecture, components.dataflow, components.boundaries),
        evidence, raw_ops, tier,
        (exact_pct, layer_unconfirmed, layer_note, cap_architecture))

    blocking = _hard_gates({
        'validation': validation, 'checks': checks, 'semantic_review': semantic_review,
        'config': config, 'raw_ops': raw_ops, 'coverage': coverage,
        'architecture': architecture_config, 'nodes': nodes,
    })

    total, runnable_total, nominal_total, correctness, evidence_fraction = _score_summary(
        dimensions)
    failed_dimensions, correct = _failed_dimensions(dimensions, correctness)
    required_actions = _required_actions(blocking, dimensions, failed_dimensions)
    return _score_report({
        'eligible': correct and not blocking,
        'evidence_fraction': evidence_fraction,
        'tier': tier,
        'caps': caps,
        'validation': validation,
        'manifest': manifest,
        'total': total,
        'runnable_total': runnable_total,
        'nominal_total': nominal_total,
        'correctness': correctness,
        'dimensions': dimensions,
        'failed_dimensions': failed_dimensions,
        'blocking': blocking,
        'required_actions': required_actions,
    })


def main():
    parser = argparse.ArgumentParser(description='Score a validated model breakdown')
    parser.add_argument('-v', '--validation-report', required=True)
    parser.add_argument('-c', '--config', required=True)
    parser.add_argument('-r', '--raw-ops', required=True)
    parser.add_argument('-m', '--manifest', required=True)
    parser.add_argument('-s', '--semantic-review')
    parser.add_argument('-o', '--output')
    args = parser.parse_args()

    semantic_review = _load(args.semantic_review) if args.semantic_review else None
    report = score_breakdown(_load(args.validation_report), _load(args.config),
                             _load(args.raw_ops), _load(args.manifest), semantic_review)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
        bc.emit(f'breakdown score 已写入: {args.output}  status={report["status"]} '
              f'tier={report["capture_tier"]} '
              f'score={report["score"]}/{report["runnable_max"]} '
              f'(nominal {report["max_score"]}) '
              f'correctness={report["correctness_ratio"]:.3f} '
              f'evidence={report["evidence_fraction"]:.3f}')
    else:
        bc.emit(text)
    # Exit 0 for any conclusion that may be converted into a report. `exploratory` and
    # `needs_iteration` exit non-zero: the first has too little evidence to publish, the second
    # has open findings.
    sys.exit(0 if report['convertible'] else 1)


if __name__ == '__main__':
    main()
