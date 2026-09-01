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
"""Validate a controlled diagnostic patch against its immutable request."""
import argparse
import copy
import hashlib
import json
import os
import sys

import breakdown_common as bc
import prepare_revision_context as revision


HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)


def _load(path):
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def _sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _json_sha(value):
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _request_sha(request):
    payload = copy.deepcopy(request)
    payload.pop('request_sha256', None)
    return _json_sha(payload)


def _issue(code, message, path='$'):
    return {'id': code, 'severity': 'error', 'node_path': path, 'message': message}


def _pointer_parts(pointer):
    if not isinstance(pointer, str) or not pointer.startswith('/'):
        return None
    return [part.replace('~1', '/').replace('~0', '~')
            for part in pointer[1:].split('/')]


def _path_allowed(pointer, prefixes):
    parts = _pointer_parts(pointer)
    if parts is None:
        return False
    for prefix in prefixes or []:
        allowed = revision._path_parts(prefix)
        if allowed is not None and parts[:len(allowed)] == allowed:
            return True
    return False


def _artifact_values(request, name):
    artifact = (request.get('inputs') or {}).get(name) or {}
    path = artifact.get('path')
    if not path or not os.path.exists(path):
        return None
    return _load(path)


def validate_diagnostic_patch(report, request_path):
    request = _load(request_path)
    schema = bc.load_schema(os.path.join(
        SKILL_ROOT, 'schemas', 'diagnostic_patch.schema.json'))
    schema_errors = bc.validate_json_schema(report, schema)
    issues = [_issue('DP_SCHEMA', error) for error in schema_errors]
    if schema_errors:
        return issues, {'schema_valid': False, 'applicable': False}

    expected_request_sha = _request_sha(request)
    if (request.get('request_sha256') != expected_request_sha
            or report.get('request_sha256') != expected_request_sha):
        issues.append(_issue(
            'DP_REQUEST_STALE', 'diagnostic patch is not bound to the current request',
            '$.request_sha256'))
    if report.get('base_artifacts') != request.get('base_artifacts'):
        issues.append(_issue(
            'DP_BASE_BINDING', 'base artifact bindings differ from the request',
            '$.base_artifacts'))
    for name, artifact in (request.get('base_artifacts') or {}).items():
        path = artifact.get('path') if isinstance(artifact, dict) else None
        digest = artifact.get('sha256') if isinstance(artifact, dict) else None
        if not (path and digest and os.path.exists(path) and _sha(path) == digest):
            issues.append(_issue(
                'DP_BASE_STALE', f'base artifact is missing or stale: {name}',
                f'$.base_artifacts.{name}'))

    expected_ids = sorted(item.get('id') for item in request.get('blocking_issues') or [])
    actual_ids = [item.get('issue_id') for item in report.get('diagnoses') or []]
    if len(actual_ids) != len(set(actual_ids)) or sorted(actual_ids) != expected_ids:
        issues.append(_issue(
            'DP_DIAGNOSIS_SCOPE', 'diagnoses must cover every blocking issue exactly once',
            '$.diagnoses'))

    outcome = report.get('outcome')
    patches = report.get('patches') or []
    if outcome == 'proposed_patch' and not patches:
        issues.append(_issue('DP_PATCH_MISSING', 'proposed_patch requires at least one patch'))
    if outcome != 'proposed_patch' and patches:
        issues.append(_issue(
            'DP_PATCH_FORBIDDEN', f'{outcome} must not contain patches', '$.patches'))

    allowed_targets = request.get('allowed_targets') or {}
    raw_slice = _artifact_values(request, 'raw_ops_slice') or {}
    allowed_ops = set(raw_slice.get('op_indices') or [])
    snippets = _artifact_values(request, 'source_snippets') or {}
    allowed_refs = {item.get('source_ref') for item in snippets.get('snippets') or []}
    input_names = set((request.get('inputs') or {}).keys())
    for patch_index, patch in enumerate(patches):
        target = patch.get('target')
        prefixes = allowed_targets.get(target)
        if not prefixes:
            issues.append(_issue(
                'DP_TARGET_FORBIDDEN', f'target is not authorized: {target}',
                f'$.patches[{patch_index}].target'))
            prefixes = []
        for operation_index, operation in enumerate(patch.get('operations') or []):
            where = f'$.patches[{patch_index}].operations[{operation_index}]'
            if not _path_allowed(operation.get('path'), prefixes):
                issues.append(_issue(
                    'DP_PATH_FORBIDDEN',
                    f'path is outside the checker-authorized prefixes: {operation.get("path")}',
                    where + '.path'))
            if operation.get('op') in ('add', 'replace') and 'value' not in operation:
                issues.append(_issue(
                    'DP_VALUE_MISSING', 'add/replace operation requires value', where))
            evidence_items = operation.get('evidence') or []
            if not evidence_items:
                issues.append(_issue(
                    'DP_EVIDENCE_MISSING', 'every patch operation requires scoped evidence',
                    where + '.evidence'))
            has_scoped_locator = False
            for evidence_index, evidence in enumerate(evidence_items):
                evidence_where = f'{where}.evidence[{evidence_index}]'
                artifact = evidence.get('artifact')
                if artifact not in input_names:
                    issues.append(_issue(
                        'DP_EVIDENCE_ARTIFACT', f'evidence artifact is not an input: {artifact}',
                        evidence_where))
                invalid_ops = sorted(set(evidence.get('op_indices') or []) - allowed_ops)
                if invalid_ops:
                    issues.append(_issue(
                        'DP_EVIDENCE_OUT_OF_SCOPE',
                        f'op indices are outside the diagnostic slice: {invalid_ops[:8]}',
                        evidence_where))
                elif artifact == 'raw_ops_slice' and evidence.get('op_indices'):
                    has_scoped_locator = True
                source_ref = evidence.get('source_ref')
                if source_ref and source_ref not in allowed_refs:
                    issues.append(_issue(
                        'DP_EVIDENCE_OUT_OF_SCOPE',
                        f'source_ref is outside diagnostic snippets: {source_ref}',
                        evidence_where))
                elif artifact == 'source_snippets' and source_ref:
                    has_scoped_locator = True
            if evidence_items and not has_scoped_locator:
                issues.append(_issue(
                    'DP_EVIDENCE_UNSCOPED',
                    'patch operation must cite a selected source_ref or raw op index',
                    where + '.evidence'))

    applicable = bool(outcome == 'proposed_patch' and not issues)
    return issues, {'schema_valid': not schema_errors, 'applicable': applicable,
                    'outcome': outcome, 'patch_count': len(patches)}


def main():
    parser = argparse.ArgumentParser(description='Validate controlled diagnostic patch')
    parser.add_argument('-q', '--diagnostic-patch', required=True)
    parser.add_argument('--request', required=True)
    parser.add_argument('-o', '--output')
    args = parser.parse_args()
    report = _load(args.diagnostic_patch)
    issues, detail = validate_diagnostic_patch(report, args.request)
    result = {'status': 'passed' if not issues else 'failed',
              'error_count': len(issues), 'issues': issues, 'detail': detail,
              'eligible_for_scoring': False}
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as stream:
            stream.write(text + '\n')
    else:
        print(text)
    return 1 if issues else 0


if __name__ == '__main__':
    sys.exit(main())
