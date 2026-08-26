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
"""Validate a source/trace semantic review and its exact artifact bindings."""
import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import breakdown_common as bc  # noqa: E402


REQUIRED_CHECKS = (
    'source_model_identity',
    'module_inventory_complete',
    'dataflow_edges_complete',
    'branch_topology_correct',
    'residual_paths_correct',
    'layer_boundaries_correct',
    'tail_stages_correct',
    'runtime_nodes_observed',
    'code_refs_resolve',
)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _issue(identifier, message, node_path='<semantic_review>', severity='error'):
    return {'id': identifier, 'severity': severity, 'node_path': node_path,
            'message': message}


#: A finding on this check reports an architecture scalar the supplied files cannot confirm,
#: not a defect in the reviewed semantics. Kept in sync with
#: `score_breakdown.EVIDENCE_GAP_FINDING_CHECKS`.
EVIDENCE_GAP_FINDING_CHECKS = frozenset({'source_model_identity'})

#: Checks whose whole subject is the non-chain topology. Prose saying "the residual paths are
#: correct" is unfalsifiable, and a valid source line plus a valid op index is enough to make
#: a wrong conclusion pass every locator test -- neither says anything about whether the edge
#: was actually declared. These three must point at a `branches` entry in the config, which is
#: the only place a residual or parallel path exists downstream.
BRANCH_EVIDENCE_CHECKS = frozenset({
    'dataflow_edges_complete', 'branch_topology_correct', 'residual_paths_correct',
})


@dataclass(frozen=True)
class ReviewInputs:
    config_path: str
    raw_ops_path: str
    manifest_path: str
    source_dirs: list
    dataflow_path: str = None


@dataclass
class ReviewState:
    inputs: ReviewInputs
    issues: list = field(default_factory=list)
    config: dict = field(default_factory=dict)
    raw_indices: set = field(default_factory=set)
    stale: list = field(default_factory=list)
    checks: list = field(default_factory=list)
    check_ids: list = field(default_factory=list)
    dataflow_binding: str = 'absent'
    declared_branches: list = field(default_factory=list)
    blocking_findings: list = field(default_factory=list)
    evidence_gap_findings: list = field(default_factory=list)
    dataflow_contradictions: list = field(default_factory=list)


def _path_parts(path):
    """Split a JSONPath-ish locator into parts, accepting both `a.0` and `a[0]`.

    Bracket indexing is the natural way to write `$.runtime_auxiliary[0]`, so rejecting
    it would report "path does not exist" for a path that does exist — sending a
    reviewer after a phantom defect.
    """
    parts = []
    for segment in path.split('.'):
        head, bracket, rest = segment.partition('[')
        if head:
            parts.append(head)
        while bracket:
            index, closed, remainder = rest.partition(']')
            if not closed:
                return None
            parts.append(index)
            head, bracket, rest = '', *remainder.partition('[')[1:]
    return parts


def _resolve_config_path(config, path):
    if path == '$':
        return True
    if not isinstance(path, str) or not path.startswith('$.'):
        return False
    parts = _path_parts(path[2:])
    if parts is None:
        return False
    current = config
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        if isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
            continue
        return False
    return True


def _config_declares_branches(config):
    """Return the exact config path of every declared non-chain edge.

    Walks the whole tree rather than only top-level structures: `branches` is legal on any
    node, so a nested declaration still counts.
    """
    found = []

    def walk(node, path):
        if isinstance(node, dict):
            for index, branch in enumerate(node.get('branches') or []):
                if isinstance(branch, dict) and branch.get('name'):
                    found.append(f'{path}.branches[{index}]')
            for index, child in enumerate(node.get('children') or []):
                walk(child, f'{path}.children[{index}]')

    for name, structure in (config.get('structures') or {}).items():
        walk(structure, f'$.structures.{name}')
    for name, stage in (config.get('stages') or {}).items():
        walk(stage, f'$.stages.{name}')
    return found


def _schema_issues(review):
    schema = bc.load_schema(os.path.join(SKILL_ROOT, 'schemas', 'semantic_review.schema.json'))
    schema_errors = bc.validate_json_schema(review, schema)
    return [_issue('SR_SCHEMA', error) for error in schema_errors]


def _load_review_state(inputs):
    with open(inputs.config_path, encoding='utf-8') as stream:
        config = json.load(stream)
    with open(inputs.raw_ops_path, encoding='utf-8') as stream:
        raw_ops = json.load(stream)
    return ReviewState(inputs=inputs, config=config,
                       raw_indices=bc.expand_raw_op_indices(raw_ops))


def _validate_artifact_digests(review, state):
    expected = {
        'analysis_config': state.inputs.config_path,
        'raw_ops': state.inputs.raw_ops_path,
        'model_manifest': state.inputs.manifest_path,
    }
    for name, path in expected.items():
        recorded = review['artifacts'][name]['sha256']
        actual = sha256_file(path)
        if recorded != actual:
            state.stale.append(name)
            state.issues.append(_issue(
                'SR_DIGEST_MISMATCH',
                f'{name} SHA256 与当前文件不一致；配置或输入变化后必须重新审查',
                f'artifacts.{name}'))


def _validate_dataflow_binding(review, state):
    dataflow_path = state.inputs.dataflow_path
    if dataflow_path and os.path.exists(dataflow_path):
        recorded = (review['artifacts'].get('dataflow_source') or {}).get('sha256')
        if not recorded:
            state.dataflow_binding = 'unbound'
            state.issues.append(_issue(
                'SR_DATAFLOW_UNBOUND',
                'dataflow_source.json 已提供，但审查未记录其 SHA256：'
                '审查必须绑定它所依据的数据流真值，否则源码变化后旧结论会被静默复用',
                'artifacts.dataflow_source'))
        elif recorded != sha256_file(dataflow_path):
            state.dataflow_binding = 'stale'
            state.stale.append('dataflow_source')
            state.issues.append(_issue(
                'SR_DIGEST_MISMATCH',
                'dataflow_source SHA256 与当前文件不一致；源码或提取器变化后必须重新审查',
                'artifacts.dataflow_source'))
        else:
            state.dataflow_binding = 'bound'


def _validate_required_checks(state):
    for identifier in REQUIRED_CHECKS:
        count = state.check_ids.count(identifier)
        if count == 0:
            state.issues.append(_issue(
                'SR_CHECK_MISSING', f'缺少强制审查项 {identifier}', 'checks'))
        elif count > 1:
            state.issues.append(_issue(
                'SR_CHECK_DUPLICATE', f'审查项 {identifier} 重复 {count} 次', 'checks'))
    for identifier in sorted(set(state.check_ids) - set(REQUIRED_CHECKS)):
        state.issues.append(_issue('SR_CHECK_UNKNOWN', f'未知审查项 {identifier}', 'checks'))


def _validate_evidence(items, node_path, state):
    for index, evidence in enumerate(items):
        evidence_path = f'{node_path}.evidence.{index}'
        if not evidence.get('explanation', '').strip():
            state.issues.append(_issue(
                'SR_EVIDENCE_EXPLANATION', '证据 explanation 不能为空', evidence_path))
        locators = [key for key in ('source_ref', 'config_path', 'op_indices')
                    if evidence.get(key)]
        if not locators:
            state.issues.append(_issue(
                'SR_EVIDENCE_LOCATOR', '证据至少需要 source_ref/config_path/op_indices 之一', evidence_path))
        if evidence.get('source_ref'):
            ok, reason = bc.validate_source_ref(evidence['source_ref'], state.inputs.source_dirs)
            if not ok:
                state.issues.append(_issue('SR_SOURCE_REF', reason, evidence_path))
        config_path = evidence.get('config_path')
        if config_path and not _resolve_config_path(state.config, config_path):
            state.issues.append(_issue(
                'SR_CONFIG_PATH', f'配置路径不存在: {config_path}', evidence_path))
        invalid = sorted(set(evidence.get('op_indices', [])) - state.raw_indices)
        if invalid:
            state.issues.append(_issue(
                'SR_OP_INDEX', f'op_indices 不在当前 raw_ops 中: {invalid}', evidence_path))


def _validate_checks(state):
    for index, check in enumerate(state.checks):
        path = f'checks.{index}'
        if check['status'] != 'passed':
            state.issues.append(_issue(
                'SR_CHECK_NOT_PASSED', f'{check["id"]} 状态为 {check["status"]}', path))
        if check['status'] == 'passed' and not check['evidence']:
            state.issues.append(_issue(
                'SR_EVIDENCE_MISSING', f'{check["id"]} 声明 passed 但没有证据', path))
        _validate_evidence(check['evidence'], path, state)
        if (check['id'] in BRANCH_EVIDENCE_CHECKS and check['status'] == 'passed'
                and state.declared_branches):
            cited = {evidence.get('config_path') for evidence in check['evidence']}
            missing_citations = [item for item in state.declared_branches if item not in cited]
            if missing_citations:
                state.issues.append(_issue(
                    'SR_BRANCH_EVIDENCE',
                    f'{check["id"]} 声明 passed，但未逐条引用全部 branches；'
                    f'缺少 {missing_citations[:4]}（共 {len(missing_citations)} 条），'
                    f'审查必须逐边引用而不是只用一条边替代全部拓扑',
                    path))


def _validate_source_evidence(review, state):
    for index, evidence in enumerate(review['source_evidence']):
        ok, reason = bc.validate_source_ref(evidence['source_ref'], state.inputs.source_dirs)
        if not ok:
            state.issues.append(_issue('SR_SOURCE_REF', reason, f'source_evidence.{index}'))
        if not evidence.get('explanation', '').strip():
            state.issues.append(_issue(
                'SR_EVIDENCE_EXPLANATION', 'source evidence 说明不能为空',
                f'source_evidence.{index}'))


def _validate_findings(review, state):
    for index, finding in enumerate(review['findings']):
        _validate_evidence(finding['evidence'], f'findings.{index}', state)
        if finding['check_id'] not in state.check_ids:
            state.issues.append(_issue(
                'SR_FINDING_CHECK', f'finding 引用了不存在的 check_id: {finding["check_id"]}',
                f'findings.{index}'))
        if finding['severity'] in ('error', 'warning'):
            if (finding['severity'] == 'warning'
                    and finding['check_id'] in EVIDENCE_GAP_FINDING_CHECKS):
                state.evidence_gap_findings.append(finding['id'])
                state.issues.append(_issue(
                    'SR_EVIDENCE_GAP_FINDING',
                    f'证据缺口 finding（不阻断，仅记录）: {finding["message"]}',
                    f'findings.{index}', severity='info'))
                continue
            state.blocking_findings.append(finding['id'])
            state.issues.append(_issue(
                'SR_BLOCKING_FINDING',
                f'{finding["severity"]} finding 阻断正式通过: {finding["message"]}',
                f'findings.{index}'))


def _validate_review_status(review, state):
    if review['status'] != 'passed':
        state.issues.append(_issue(
            'SR_REVIEW_NOT_PASSED', f'语义审查总状态为 {review["status"]}', 'status'))
    elif (any(check['status'] != 'passed' for check in state.checks)
          or state.blocking_findings):
        state.issues.append(_issue(
            'SR_STATUS_INCONSISTENT', '总状态为 passed，但子项或 finding 尚未通过', 'status'))


def _load_json(path):
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def _record_dataflow_contradictions(review, state):
    if not state.dataflow_contradictions or review['status'] != 'passed':
        return
    for item in state.dataflow_contradictions:
        state.issues.append(_issue(
            'SR_DATAFLOW_CONTRADICTION',
            f'审查声明 passed，但 check_dataflow 报出 {item["id"]} error：'
            f'{item["message"]}',
            item.get('node_path', 'checks')))


def _validate_dataflow(review, state):
    dataflow_path = state.inputs.dataflow_path
    if not dataflow_path or not os.path.exists(dataflow_path):
        return
    try:
        import check_dataflow
        dataflow = _load_json(dataflow_path)
        manifest_path = state.inputs.manifest_path
        manifest = (_load_json(manifest_path)
                    if manifest_path and os.path.exists(manifest_path) else None)
        df_issues, _ = check_dataflow.check_dataflow(state.config, dataflow, manifest)
        state.dataflow_contradictions = [
            item for item in df_issues if item.get('severity') == 'error']
        _record_dataflow_contradictions(review, state)
    except (ImportError, OSError, ValueError, KeyError) as error:
        state.issues.append(_issue(
            'SR_DATAFLOW_UNVERIFIED',
            f'无法独立校验数据流（{error}）：不据此判定审查通过',
            'artifacts.dataflow_source', severity='warning'))


def _review_detail(review, state):
    return {
        'required_checks': list(REQUIRED_CHECKS),
        'schema_valid': True,
        'artifact_digests_match': not state.stale,
        'stale_artifacts': state.stale,
        'review_status': review['status'],
        'checks_present': len(set(state.check_ids).intersection(REQUIRED_CHECKS)),
        'blocking_findings': state.blocking_findings,
        'evidence_gap_findings': state.evidence_gap_findings,
        'dataflow_binding': state.dataflow_binding,
        'declared_branches': len(state.declared_branches),
        'dataflow_contradictions': [item['id'] for item in state.dataflow_contradictions],
    }


def validate_review(review, inputs):
    issues = _schema_issues(review)
    if issues:
        return issues, {'required_checks': list(REQUIRED_CHECKS), 'schema_valid': False}
    state = _load_review_state(inputs)
    state.checks = review['checks']
    state.check_ids = [item['id'] for item in state.checks]
    state.declared_branches = _config_declares_branches(state.config)
    _validate_artifact_digests(review, state)
    _validate_dataflow_binding(review, state)
    _validate_required_checks(state)
    _validate_checks(state)
    _validate_source_evidence(review, state)
    _validate_findings(review, state)
    _validate_review_status(review, state)
    _validate_dataflow(review, state)
    return state.issues, _review_detail(review, state)


def validate_file(review_path, inputs):
    with open(review_path, encoding='utf-8') as stream:
        review = json.load(stream)
    return validate_review(review, inputs)


def main():
    parser = argparse.ArgumentParser(description='Validate semantic_review.json')
    parser.add_argument('-s', '--semantic-review', required=True)
    parser.add_argument('-c', '--config', required=True)
    parser.add_argument('-r', '--raw-ops', required=True)
    parser.add_argument('-m', '--manifest', required=True)
    parser.add_argument('--source-dir', action='append', default=[])
    parser.add_argument('-d', '--dataflow',
                        help='dataflow_source.json：绑定其 SHA256 并独立复核 D1-D7')
    parser.add_argument('-o', '--output')
    args = parser.parse_args()
    try:
        inputs = ReviewInputs(
            config_path=args.config,
            raw_ops_path=args.raw_ops,
            manifest_path=args.manifest,
            source_dirs=args.source_dir or [os.getcwd()],
            dataflow_path=args.dataflow,
        )
        issues, detail = validate_file(args.semantic_review, inputs)
        report = {'status': 'passed' if not issues else 'failed',
                  'error_count': len(issues), 'issues': issues, 'detail': detail}
    except (OSError, ValueError) as error:
        report = {'status': 'failed', 'error_count': 1,
                  'issues': [_issue('SR_INPUT', str(error))], 'detail': {}}
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as stream:
            stream.write(text + '\n')
    else:
        bc.emit(text)
    sys.exit(0 if report['status'] == 'passed' else 1)


if __name__ == '__main__':
    main()
