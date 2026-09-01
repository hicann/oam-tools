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
"""Validate a scoped critique. Targeted reports are never formal scoring inputs."""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import breakdown_common as bc  # noqa: E402


def _sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _issue(identifier, message, node_path='<targeted_critique>'):
    return {'id': identifier, 'severity': 'error', 'node_path': node_path, 'message': message}


def _json_sha(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def validate_targeted_report(report, config_path, source_index_path, raw_ops_path, source_dirs,
                             request_path=None, validation_report_path=None):
    schema = bc.load_schema(os.path.join(SKILL_ROOT, 'schemas',
                                        'targeted_critique_report.schema.json'))
    schema_errors = bc.validate_json_schema(report, schema)
    issues = [_issue('TC_SCHEMA', error) for error in schema_errors]
    if schema_errors:
        return issues, {'schema_valid': False, 'clears_scope': False}
    with open(source_index_path, encoding='utf-8') as stream:
        source_index = json.load(stream)
    with open(raw_ops_path, encoding='utf-8') as stream:
        raw_ops = json.load(stream)
    with open(config_path, encoding='utf-8') as stream:
        config = json.load(stream)
    raw_indices = bc.expand_raw_op_indices(raw_ops)
    if report['candidate_sha256'] != _sha(config_path):
        issues.append(_issue('TC_DIGEST_MISMATCH', 'candidate SHA256 is stale',
                             'candidate_sha256'))
    if report['source_bundle_hash'] != source_index['source_bundle_hash']:
        issues.append(_issue('TC_SOURCE_CHANGED', 'source bundle hash is stale',
                             'source_bundle_hash'))
    deterministic_conflicts = []
    if validation_report_path:
        try:
            with open(validation_report_path, encoding='utf-8') as stream:
                validation_report = json.load(stream)
            active_blockers = {
                item.get('id') for item in validation_report.get('issues') or []
                if item.get('severity') == 'error' and item.get('id')
            }
            passed_checks = {
                item.get('id') for item in report.get('checks') or []
                if item.get('status') == 'passed' and item.get('id')
            }
            deterministic_conflicts = sorted(active_blockers & passed_checks)
            if deterministic_conflicts:
                issues.append(_issue(
                    'TC_DETERMINISTIC_CONFLICT',
                    'targeted report marks unresolved deterministic blockers as passed: '
                    f'{deterministic_conflicts}',
                    'checks'))
        except (OSError, TypeError, ValueError) as error:
            issues.append(_issue(
                'TC_VALIDATION_REPORT',
                f'current deterministic validation report is unreadable: {error}',
                'validation_report'))
    if request_path:
        with open(request_path, encoding='utf-8') as stream:
            request = json.load(stream)
        requested_scope = request.get('scope') or {}
        request_inputs = request.get('inputs') or {}
        if request.get('candidate_sha256') != _sha(config_path):
            issues.append(_issue(
                'TC_REQUEST_STALE',
                'targeted request candidate digest does not match the current run',
                'candidate_sha256'))
        if (request_inputs.get('source_index') or {}).get('sha256') != _sha(source_index_path):
            issues.append(_issue(
                'TC_REQUEST_STALE',
                'targeted request source_index does not match the current run',
                'inputs.source_index'))
        raw_binding = ((request.get('bindings_not_llm_inputs') or {}).get('raw_ops') or {})
        if raw_binding.get('sha256') != _sha(raw_ops_path):
            issues.append(_issue(
                'TC_REQUEST_STALE',
                'targeted request raw_ops binding does not match the current run',
                'bindings_not_llm_inputs.raw_ops'))
        actual_scope = report['scope']
        normalized_requested = {
            'config_paths': sorted(requested_scope.get('config_paths') or []),
            'source_refs': sorted(requested_scope.get('source_refs') or []),
            'op_indices': sorted(requested_scope.get('op_indices') or []),
        }
        normalized_actual = {
            'config_paths': sorted(actual_scope.get('config_paths') or []),
            'source_refs': sorted(actual_scope.get('source_refs') or []),
            'op_indices': sorted(actual_scope.get('op_indices') or []),
        }
        if normalized_actual != normalized_requested:
            issues.append(_issue(
                'TC_SCOPE_MISMATCH',
                'targeted report scope differs from targeted_critique_request.json',
                'scope'))
        expected_ids = [item.get('id') for item in request.get('blocking_items') or []]
        actual_ids = [item.get('id') for item in report.get('checks') or []]
        if (len(actual_ids) != len(set(actual_ids))
                or sorted(actual_ids) != sorted(expected_ids)):
            issues.append(_issue(
                'TC_CHECK_SET_MISMATCH',
                'targeted checks must cover every requested blocking item exactly once',
                'checks'))
        scope_binding = {'scope': normalized_requested, 'check_ids': expected_ids}
        if report.get('scope_sha256') != _json_sha(scope_binding):
            issues.append(_issue('TC_SCOPE_DIGEST',
                                 'targeted report is not bound to the requested scope/checks',
                                 'scope_sha256'))
        context_path = request.get('context_manifest')
        if not (context_path and os.path.exists(context_path)):
            issues.append(_issue('TC_CONTEXT_MISSING',
                                 'targeted request context_manifest is missing'))
        else:
            if report.get('context_manifest_sha256') != _sha(context_path):
                issues.append(_issue('TC_CONTEXT_DIGEST',
                                     'targeted context manifest digest mismatch'))
            with open(context_path, encoding='utf-8') as stream:
                context = json.load(stream)
            if context.get('inputs') != request.get('inputs'):
                issues.append(_issue('TC_CONTEXT_INPUTS',
                                     'request inputs differ from context manifest whitelist'))
            if (context.get('bindings_not_llm_inputs')
                    != request.get('bindings_not_llm_inputs')):
                issues.append(_issue(
                    'TC_CONTEXT_INPUTS',
                    'request deterministic bindings differ from context manifest'))
            for name, artifact in (context.get('inputs') or {}).items():
                path = artifact.get('path') if isinstance(artifact, dict) else None
                digest = artifact.get('sha256') if isinstance(artifact, dict) else None
                if not (path and digest and os.path.exists(path) and _sha(path) == digest):
                    issues.append(_issue('TC_CONTEXT_ARTIFACT',
                                         f'context input is missing or stale: {name}',
                                         f'inputs.{name}'))
    for ref in report['scope']['source_refs']:
        ok, reason = bc.validate_source_ref(ref, source_dirs)
        if not ok:
            issues.append(_issue('TC_SOURCE_REF', reason, 'scope.source_refs'))
    invalid_scope_ops = sorted(set(report['scope']['op_indices']) - raw_indices)
    if invalid_scope_ops:
        issues.append(_issue('TC_OP_INDEX',
                             f'out-of-range targeted op indices: {invalid_scope_ops[:8]}',
                             'scope.op_indices'))
    for index, check in enumerate(report['checks']):
        if check['status'] == 'passed' and not check.get('evidence'):
            issues.append(_issue('TC_EVIDENCE_MISSING',
                                 f'{check["id"]} passed without scoped evidence',
                                 f'checks.{index}'))
        for evidence_index, evidence in enumerate(check.get('evidence') or []):
            where = f'checks.{index}.evidence.{evidence_index}'
            if evidence.get('source_ref'):
                ok, reason = bc.validate_source_ref(evidence['source_ref'], source_dirs)
                if not ok:
                    issues.append(_issue('TC_SOURCE_REF', reason, where))
                elif evidence['source_ref'] not in report['scope']['source_refs']:
                    issues.append(_issue('TC_EVIDENCE_OUT_OF_SCOPE',
                                         'source_ref is outside targeted scope', where))
            if evidence.get('config_path'):
                if evidence['config_path'] not in report['scope']['config_paths']:
                    issues.append(_issue('TC_EVIDENCE_OUT_OF_SCOPE',
                                         'config_path is outside targeted scope', where))
                elif not bc.resolve_config_path(config, evidence['config_path']):
                    issues.append(_issue('TC_CONFIG_PATH',
                                         'config_path does not resolve', where))
            invalid = sorted(set(evidence.get('op_indices') or []) - raw_indices)
            if invalid:
                issues.append(_issue('TC_OP_INDEX',
                                     f'out-of-range targeted op indices: {invalid[:8]}', where))
            outside = sorted(set(evidence.get('op_indices') or [])
                             - set(report['scope']['op_indices']))
            if outside:
                issues.append(_issue('TC_EVIDENCE_OUT_OF_SCOPE',
                                     f'op indices outside targeted scope: {outside[:8]}', where))
    errors = [item for item in issues if item['severity'] == 'error']
    blocking = [item for item in report['issues'] if item.get('severity') == 'error']
    unknown = [item for item in report['checks'] if item.get('status') == 'unknown']
    failed = [item for item in report['checks'] if item.get('status') == 'failed']
    detail = {'schema_valid': not schema_errors, 'blocking_issue_count': len(blocking),
              'deterministic_conflicts': deterministic_conflicts,
              'clears_scope': bool(report['status'] == 'passed' and not errors
                                   and not blocking and not unknown and not failed)}
    return issues, detail


def main():
    parser = argparse.ArgumentParser(description='Validate targeted critique report')
    parser.add_argument('-q', '--targeted-critique-report', required=True)
    parser.add_argument('-c', '--config', required=True)
    parser.add_argument('--source-index', required=True)
    parser.add_argument('-r', '--raw-ops', required=True)
    parser.add_argument('--source-dir', action='append', default=[])
    parser.add_argument('--request', help='targeted_critique_request.json to bind the scope')
    parser.add_argument('--validation-report',
                        help='current deterministic validation report for conflict checks')
    parser.add_argument('-o', '--output')
    args = parser.parse_args()
    with open(args.targeted_critique_report, encoding='utf-8') as stream:
        report = json.load(stream)
    issues, detail = validate_targeted_report(
        report, args.config, args.source_index, args.raw_ops, args.source_dir,
        args.request, args.validation_report)
    result = {'status': 'passed' if not issues else 'failed',
              'error_count': len(issues), 'issues': issues, 'detail': detail,
              'eligible_for_scoring': False}
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as stream:
            stream.write(text + '\n')
    else:
        print(text)
    return 1 if issues else 0


if __name__ == '__main__':
    sys.exit(main())
