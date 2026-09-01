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
"""Deterministically verify an independent critique report.

The critique itself is a semantic judgement -- this script does not second-guess it. What it
does check is everything about that judgement that IS mechanical: that the report is bound by
digest to the exact inputs it claims to have read, that all eleven mandatory checks are
present, and that every locator an issue cites actually resolves (source line exists, op index
is in the representative step, config path names a real node).

That division is the whole point of the contract. An unbound or unlocatable critique is
indistinguishable from an opinion, and an opinion cannot block or clear a candidate. A
fabricated `modeling.py:9999` is caught here rather than being taken at face value.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import breakdown_common as bc  # noqa: E402

#: All eleven critique dimensions, in the order `prepare_critique.py` templates them. Kept as
#: the single source of truth: the schema enumerates the same ids, and the preparer imports
#: this tuple rather than restating it, so the two cannot drift.
REQUIRED_CHECKS = (
    'model_identity_and_variant',
    'module_inventory_complete',
    'learned_layer_vs_invocation',
    'config_instantiation_params',
    'forward_call_order',
    'residual_parallel_skip_topology',
    'trace_module_attribution',
    'layer_and_fusion_boundaries',
    'runtime_vs_model_classification',
    'op_coverage_and_duplicate_ownership',
    'source_ref_authenticity',
)

#: Issue categories whose subject is topology or parameter binding. A claim about a residual
#: or an instantiated scalar that cites no locator is unfalsifiable prose, so these categories
#: must carry at least one machine-checkable reference.
LOCATOR_REQUIRED_CATEGORIES = frozenset({
    'dataflow', 'boundaries', 'attribution', 'architecture', 'identity',
})

TOPOLOGY_EVIDENCE_CATEGORIES = frozenset({'dataflow', 'boundaries'})


def _issue(identifier, message, node_path='<critique_report>', severity='error'):
    return {'id': identifier, 'severity': severity, 'node_path': node_path,
            'message': message}


def validate_critique(report, config_path, raw_ops_path, manifest_path, source_dirs,
                      dataflow_path=None, checkpoint_config_path=None,
                      source_index_path=None, raw_ops_compact_path=None,
                      source_snippets_path=None, context_manifest_path=None):
    """Return (issues, detail). An `error` issue here means the critique cannot be used."""
    schema = bc.load_schema(os.path.join(SKILL_ROOT, 'schemas',
                                        'critique_report.schema.json'))
    schema_errors = bc.validate_json_schema(report, schema)
    issues = [_issue('CQ_SCHEMA', error) for error in schema_errors]
    if schema_errors:
        return issues, {'required_checks': list(REQUIRED_CHECKS), 'schema_valid': False}

    with open(config_path, encoding='utf-8') as stream:
        config = json.load(stream)
    with open(raw_ops_path, encoding='utf-8') as stream:
        raw_ops = json.load(stream)
    raw_indices = bc.expand_raw_op_indices(raw_ops)
    checkpoint_config = None
    if checkpoint_config_path and os.path.exists(checkpoint_config_path):
        try:
            with open(checkpoint_config_path, encoding='utf-8') as stream:
                checkpoint_config = json.load(stream)
        except (OSError, ValueError):
            checkpoint_config = None

    detail = {
        'required_checks': list(REQUIRED_CHECKS),
        'schema_valid': True,
        'issue_count': len(report['issues']),
        'error_issue_count': sum(1 for item in report['issues']
                                 if item['severity'] == 'error'),
    }

    # ---- digest binding -----------------------------------------------------------------
    # A critique of bytes that no longer exist says nothing about the bytes that do, so drift
    # in ANY input voids it. This is what stops a stale critique being reused after the
    # candidate was edited -- the failure mode that makes an iteration loop look convergent
    # while nothing is actually being re-examined.
    expected = {
        'analysis_config': config_path,
        'raw_ops': raw_ops_path,
        'model_manifest': manifest_path,
    }
    stale = []
    for name, path in expected.items():
        if report['artifacts'][name]['sha256'] != bc.sha256_file(path):
            stale.append(name)
            issues.append(_issue(
                'CQ_DIGEST_MISMATCH',
                f'{name} SHA256 与当前文件不一致：批判针对的已不是当前候选，'
                f'必须重新进行完整批判',
                f'artifacts.{name}'))

    for name, path in (('dataflow_source', dataflow_path),
                       ('checkpoint_config', checkpoint_config_path)):
        if not (path and os.path.exists(path)):
            detail[f'{name}_binding'] = 'absent'
            continue
        recorded = (report['artifacts'].get(name) or {}).get('sha256')
        if not recorded:
            detail[f'{name}_binding'] = 'unbound'
            issues.append(_issue(
                'CQ_ARTIFACT_UNBOUND',
                f'{name} 已提供给批判器，但报告未记录其 SHA256：'
                f'批判必须绑定其所依据的全部证据，否则证据变化后旧结论会被静默复用',
                f'artifacts.{name}'))
        elif recorded != bc.sha256_file(path):
            detail[f'{name}_binding'] = 'stale'
            stale.append(name)
            issues.append(_issue(
                'CQ_DIGEST_MISMATCH',
                f'{name} SHA256 与当前文件不一致；证据变化后必须重新批判',
                f'artifacts.{name}'))
        else:
            detail[f'{name}_binding'] = 'bound'

    if source_index_path and os.path.exists(source_index_path):
        recorded = (report['artifacts'].get('source_index') or {}).get('sha256')
        if not recorded:
            detail['source_index_binding'] = 'unbound'
            issues.append(_issue(
                'CQ_ARTIFACT_UNBOUND',
                'source_index 已提供给最终批判器，但报告未绑定其 SHA256',
                'artifacts.source_index'))
        elif recorded != bc.sha256_file(source_index_path):
            detail['source_index_binding'] = 'stale'
            stale.append('source_index')
            issues.append(_issue(
                'CQ_SOURCE_CHANGED',
                'source_index SHA256 已变化；receipt 和旧完整批判均失效，必须重新扫描并重新批判',
                'artifacts.source_index'))
        else:
            detail['source_index_binding'] = 'bound'
    else:
        detail['source_index_binding'] = 'absent'

    for name, path in (('raw_ops_compact', raw_ops_compact_path),
                       ('source_snippets', source_snippets_path),
                       ('context_manifest', context_manifest_path)):
        if not (path and os.path.exists(path)):
            detail[f'{name}_binding'] = 'absent'
            continue
        recorded = (report['artifacts'].get(name) or {}).get('sha256')
        if not recorded:
            detail[f'{name}_binding'] = 'unbound'
            issues.append(_issue(
                'CQ_ARTIFACT_UNBOUND',
                f'{name} 已提供给最终批判器，但报告未绑定其 SHA256',
                f'artifacts.{name}'))
        elif recorded != bc.sha256_file(path):
            detail[f'{name}_binding'] = 'stale'
            stale.append(name)
            issues.append(_issue(
                'CQ_DIGEST_MISMATCH',
                f'{name} SHA256 与当前最终批判输入不一致；必须重新进行完整批判',
                f'artifacts.{name}'))
        else:
            detail[f'{name}_binding'] = 'bound'
    detail['stale_artifacts'] = stale

    allowed_source_ranges = None
    if source_snippets_path and os.path.exists(source_snippets_path):
        allowed_source_ranges = []
        try:
            with open(source_snippets_path, encoding='utf-8') as stream:
                snippets_payload = json.load(stream)
            for snippet in snippets_payload.get('snippets') or []:
                parsed = bc.parse_source_ref(snippet.get('source_ref'))
                if parsed:
                    allowed_source_ranges.append(parsed)
        except (OSError, ValueError, TypeError) as error:
            issues.append(_issue(
                'CQ_SOURCE_CONTEXT_INVALID',
                f'source_snippets 无法解析: {error}', 'artifacts.source_snippets'))

    def source_ref_in_context(ref):
        if allowed_source_ranges is None:
            return True
        parsed = bc.parse_source_ref(ref)
        if not parsed:
            return False
        name, start, end = parsed
        return any(name == allowed_name and start >= allowed_start and end <= allowed_end
                   for allowed_name, allowed_start, allowed_end in allowed_source_ranges)

    # ---- mandatory checks present exactly once -------------------------------------------
    ids = [item['id'] for item in report['checks']]
    for identifier in REQUIRED_CHECKS:
        count = ids.count(identifier)
        if count == 0:
            issues.append(_issue('CQ_CHECK_MISSING',
                                 f'缺少强制批判项 {identifier}', 'checks'))
        elif count > 1:
            issues.append(_issue('CQ_CHECK_DUPLICATE',
                                 f'批判项 {identifier} 重复 {count} 次', 'checks'))

    def validate_evidence(items, node_path):
        for index, evidence in enumerate(items or []):
            where = f'{node_path}.evidence.{index}'
            if not evidence.get('explanation', '').strip():
                issues.append(_issue('CQ_EVIDENCE_EXPLANATION',
                                     '证据 explanation 不能为空', where))
            if not [key for key in ('source_ref', 'config_path', 'op_indices')
                    if evidence.get(key)]:
                issues.append(_issue(
                    'CQ_EVIDENCE_LOCATOR',
                    '证据至少需要 source_ref/config_path/op_indices 之一', where))
            if evidence.get('source_ref'):
                ok, reason = bc.validate_source_ref(evidence['source_ref'], source_dirs)
                if not ok:
                    issues.append(_issue('CQ_SOURCE_REF', reason, where))
                elif not source_ref_in_context(evidence['source_ref']):
                    issues.append(_issue(
                        'CQ_SOURCE_OUTSIDE_CONTEXT',
                        'source_ref 不在绑定的 source_snippets 白名单内', where))
            if evidence.get('config_path') and not bc.resolve_config_path(
                    config, evidence['config_path']):
                issues.append(_issue(
                    'CQ_CONFIG_PATH',
                    f'配置路径不存在: {evidence["config_path"]}', where))
            invalid = sorted(set(evidence.get('op_indices') or []) - raw_indices)
            if invalid:
                issues.append(_issue(
                    'CQ_OP_INDEX',
                    f'op_indices 不在当前 raw_ops 中: {invalid[:8]}', where))

    for index, check in enumerate(report['checks']):
        where = f'checks.{index}'
        if check['status'] == 'passed' and not check.get('evidence'):
            issues.append(_issue('CQ_EVIDENCE_MISSING',
                                 f'{check["id"]} 声明 passed 但没有证据', where))
        # A failed check must name the issue it failed on. Otherwise the report says
        # "something is wrong here" with nothing the next round can act on, and the revision
        # request would carry an empty repair direction.
        if check['status'] == 'failed' and not check.get('issue_ids'):
            issues.append(_issue(
                'CQ_FAILED_CHECK_WITHOUT_ISSUE',
                f'{check["id"]} 状态为 failed 但没有关联任何 issue：'
                f'批判必须给出可据以修正的具体问题', where))
        validate_evidence(check.get('evidence'), where)

    # ---- issue well-formedness ------------------------------------------------------------
    issue_ids = [item['id'] for item in report['issues']]
    duplicated = sorted({i for i in issue_ids if issue_ids.count(i) > 1})
    if duplicated:
        issues.append(_issue('CQ_ISSUE_DUPLICATE_ID',
                             f'issue id 重复: {duplicated}', 'issues'))

    links_by_issue = {}
    for check_index, check in enumerate(report['checks']):
        for issue_id in check.get('issue_ids') or []:
            links_by_issue.setdefault(issue_id, []).append(check)
            if issue_id not in issue_ids:
                issues.append(_issue(
                    'CQ_CHECK_ISSUE_LINK',
                    f'批判项 {check["id"]} 引用了不存在的 issue_id: {issue_id}',
                    f'checks.{check_index}.issue_ids'))

    # Every blocking semantic defect must lower exactly one of the eleven scored checks.
    # Otherwise the global gate fires while all quality dimensions still claim full marks,
    # which makes the score contradict the critique it is supposed to summarize.
    for issue_index, item in enumerate(report['issues']):
        if item['severity'] != 'error':
            continue
        linked = [check for check in links_by_issue.get(item['id'], [])
                  if check['status'] == 'failed']
        declared = item.get('check_id')
        if len(linked) != 1 or (declared and linked and linked[0]['id'] != declared):
            issues.append(_issue(
                'CQ_ISSUE_CHECK_LINK',
                f'error issue {item["id"]} 必须被恰好一个 failed check 的 issue_ids 引用'
                + (f'，且与 check_id={declared} 一致' if declared else ''),
                f'issues.{issue_index}'))

    for index, item in enumerate(report['issues']):
        where = f'issues.{index}'
        for field in ('claim', 'expected', 'observed', 'repair'):
            if not str(item.get(field) or '').strip():
                issues.append(_issue(
                    'CQ_ISSUE_INCOMPLETE',
                    f'issue {item["id"]} 的 {field} 为空：'
                    f'必须同时写清候选声称什么、应当是什么、实际发现什么和修正方向', where))
        for ref in item.get('source_evidence') or []:
            ok, reason = bc.validate_source_ref(ref, source_dirs)
            if not ok:
                issues.append(_issue(
                    'CQ_ISSUE_SOURCE_REF',
                    f'issue {item["id"]} 引用的源码位置无效: {reason}', where))
            elif not source_ref_in_context(ref):
                issues.append(_issue(
                    'CQ_SOURCE_OUTSIDE_CONTEXT',
                    f'issue {item["id"]} 的 source_ref 不在绑定的 source_snippets 白名单内',
                    where))
        for path in item.get('config_paths') or []:
            if not bc.resolve_config_path(config, path):
                issues.append(_issue(
                    'CQ_ISSUE_CONFIG_PATH',
                    f'issue {item["id"]} 引用的配置路径不存在: {path}', where))
        invalid = sorted(set(item.get('trace_evidence') or []) - raw_indices)
        if invalid:
            issues.append(_issue(
                'CQ_ISSUE_OP_INDEX',
                f'issue {item["id"]} 引用的 op 索引不在当前 raw_ops 中: {invalid[:8]}',
                where))
        if item['category'] in TOPOLOGY_EVIDENCE_CATEGORIES and not (
                item.get('source_evidence') and item.get('config_paths')):
            issues.append(_issue(
                'CQ_ISSUE_TOPOLOGY_EVIDENCE',
                f'issue {item["id"]} 是拓扑/边界问题，必须同时引用源码位置和候选配置路径',
                where))
        for reference in item.get('config_evidence') or []:
            key_path = reference.rsplit(':', 1)[-1].strip()
            current = checkpoint_config
            resolved = bool(key_path) and isinstance(current, dict)
            for part in key_path.split('.') if resolved else []:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    resolved = False
                    break
            if not resolved:
                issues.append(_issue(
                    'CQ_ISSUE_CONFIG_EVIDENCE',
                    f'issue {item["id"]} 引用的 checkpoint config 键不可解析: '
                    f'{reference}', where))
        if (item['category'] in LOCATOR_REQUIRED_CATEGORIES
                and not (item.get('source_evidence') or item.get('config_paths')
                         or item.get('trace_evidence') or item.get('config_evidence'))):
            issues.append(_issue(
                'CQ_ISSUE_UNLOCATED',
                f'issue {item["id"]}（category={item["category"]}）没有任何定位符：'
                f'拓扑与参数类问题必须给出源码/配置/trace 证据，自由文本不予采纳', where))
        if item.get('check_id') and item['check_id'] not in ids:
            issues.append(_issue(
                'CQ_ISSUE_CHECK',
                f'issue {item["id"]} 引用了不存在的 check_id: {item["check_id"]}', where))

    # ---- status self-consistency ----------------------------------------------------------
    error_issues = [item['id'] for item in report['issues']
                    if item['severity'] == 'error']
    failed_checks = [check['id'] for check in report['checks']
                     if check['status'] == 'failed']
    unknown_checks = [check['id'] for check in report['checks']
                      if check['status'] == 'unknown']
    detail['error_issues'] = error_issues
    detail['failed_checks'] = failed_checks
    detail['unknown_checks'] = unknown_checks
    # Two different questions, kept apart on purpose.
    #
    # This script's `status` answers *admissibility*: is the report well-formed, digest-bound,
    # and are its locators real? A critic that correctly finds a genuine defect produces an
    # admissible report, so reporting `failed` for it would punish the critique for working.
    #
    # `clears_candidate` answers whether the critique lets the candidate proceed. It is false
    # while any error issue, failed check, or `unknown` check remains -- `unknown` never counts
    # as passing, since "I could not tell" is not evidence of correctness. The scoring gate
    # reads this field; nothing downstream should infer either answer from the other.
    # Staleness and inadmissibility count here too: a critique bound to bytes that no longer
    # exist, or one whose locators do not resolve, has not examined this candidate at all and
    # therefore cannot clear it. Reading only the critic's own verdict would let exactly the
    # reuse-after-edit case through.
    detail['clears_candidate'] = bool(
        report['status'] == 'passed'
        and not error_issues and not failed_checks and not unknown_checks
        and not [item for item in issues if item['severity'] == 'error'])

    if report['status'] == 'passed' and (error_issues or failed_checks):
        issues.append(_issue(
            'CQ_STATUS_INCONSISTENT',
            f'总状态为 passed，但存在 error issue {error_issues[:4]} '
            f'或 failed 检查 {failed_checks[:4]}', 'status'))
    if report['status'] == 'failed' and not (error_issues or failed_checks):
        issues.append(_issue(
            'CQ_STATUS_INCONSISTENT',
            '总状态为 failed，但没有任何 error issue 或 failed 检查：'
            '批判结论必须由具体问题支撑', 'status'))

    return issues, detail


def validate_file(report_path, config_path, raw_ops_path, manifest_path, source_dirs,
                  dataflow_path=None, checkpoint_config_path=None,
                  source_index_path=None, raw_ops_compact_path=None,
                  source_snippets_path=None, context_manifest_path=None):
    with open(report_path, encoding='utf-8') as stream:
        report = json.load(stream)
    return validate_critique(report, config_path, raw_ops_path, manifest_path,
                             source_dirs, dataflow_path, checkpoint_config_path,
                             source_index_path, raw_ops_compact_path,
                             source_snippets_path, context_manifest_path)


def main():
    parser = argparse.ArgumentParser(description='Validate an independent critique report')
    parser.add_argument('-q', '--critique-report', required=True)
    parser.add_argument('-c', '--config', required=True)
    parser.add_argument('-r', '--raw-ops', required=True)
    parser.add_argument('-m', '--manifest', required=True)
    parser.add_argument('--dataflow')
    parser.add_argument('--checkpoint-config')
    parser.add_argument('--source-index')
    parser.add_argument('--raw-ops-compact')
    parser.add_argument('--source-snippets')
    parser.add_argument('--context-manifest')
    parser.add_argument('--source-dir', action='append', default=[])
    parser.add_argument('-o', '--output')
    args = parser.parse_args()

    issues, detail = validate_file(
        args.critique_report, args.config, args.raw_ops, args.manifest,
        args.source_dir, args.dataflow, args.checkpoint_config, args.source_index,
        args.raw_ops_compact, args.source_snippets, args.context_manifest)
    errors = [item for item in issues if item['severity'] == 'error']
    result = {
        'status': 'passed' if not errors else 'failed',
        'error_count': len(errors),
        'issues': issues,
        'detail': detail,
    }
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as stream:
            stream.write(text + '\n')
        print(f'critique validation 已写入: {args.output}')
    else:
        print(text)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
