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
"""Prepare a clean, scoped critique request for an intermediate revision."""
import argparse
import hashlib
import json
import os

from prepare_revision_context import FORBIDDEN_INPUT_MARKERS


def _sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(path):
    return {'path': os.path.realpath(path), 'sha256': _sha(path)}


def _load(path):
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def _write(path, value):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, sort_keys=True)
        stream.write('\n')


def _json_sha(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def prepare_targeted_request(config_path, source_index_path, revision_context_path,
                             output_path, context_manifest_path, report_output):
    revision = _load(revision_context_path)
    if revision.get('status') == 'insufficient_targeted_evidence':
        blocked = {
            'schema_version': 1,
            'status': 'insufficient_targeted_evidence',
            'missing_evidence': revision.get('missing_evidence') or [],
        }
        _write(output_path, blocked)
        return blocked
    source_index = _load(source_index_path)
    blocking_items = []
    seen_ids = set()
    for index, issue in enumerate(revision.get('blocking_issues') or []):
        base_identifier = issue.get('id', f'TARGET_{index + 1}')
        identifier = base_identifier
        suffix = 2
        while identifier in seen_ids:
            identifier = f'{base_identifier}#{suffix}'
            suffix += 1
        blocking_items.append({**issue, 'id': identifier})
        seen_ids.add(identifier)
    source_refs = sorted({ref for issue in blocking_items
                          for ref in issue.get('source_evidence') or []})
    snippets_artifact = (revision.get('inputs') or {}).get('source_snippets') or {}
    try:
        snippets = _load(snippets_artifact['path'])
    except (KeyError, OSError, ValueError, TypeError):
        snippets = {}
    expanded_refs = sorted({item.get('source_ref') for item in snippets.get('snippets') or []
                            if item.get('source_ref')})
    if expanded_refs:
        source_refs = expanded_refs
    config_paths = sorted({ref for issue in blocking_items
                           for ref in issue.get('config_paths') or []})
    op_indices = sorted({ref for issue in blocking_items
                         for ref in issue.get('trace_evidence') or []})
    allowed_keys = ('candidate_nodes', 'source_index', 'source_snippets', 'raw_ops_slice')
    inputs = {key: value for key, value in (revision.get('inputs') or {}).items()
              if key in allowed_keys}
    inputs['source_index'] = _artifact(source_index_path)
    candidate_artifact = inputs.get('candidate_nodes') or {}
    raw_slice_artifact = inputs.get('raw_ops_slice') or {}
    try:
        candidate_nodes = _load(candidate_artifact['path'])
    except (KeyError, OSError, ValueError, TypeError):
        candidate_nodes = {}
    try:
        raw_slice = _load(raw_slice_artifact['path'])
    except (KeyError, OSError, ValueError, TypeError):
        raw_slice = {}
    config_paths = sorted(set(config_paths) | {
        item.get('path') for item in candidate_nodes.get('nodes') or [] if item.get('path')})
    op_indices = sorted(set(op_indices) | set(raw_slice.get('op_indices') or []))
    if not (candidate_nodes.get('nodes') and expanded_refs and raw_slice.get('operators')):
        blocked = {
            'schema_version': 1,
            'status': 'insufficient_targeted_evidence',
            'missing_evidence': [
                name for name, present in (
                    ('candidate_nodes', candidate_nodes.get('nodes')),
                    ('source_snippets', expanded_refs),
                    ('raw_ops_slice', raw_slice.get('operators')),
                ) if not present
            ],
        }
        _write(output_path, blocked)
        return blocked
    bindings = revision.get('bindings_not_llm_inputs') or {}
    candidate_sha256 = _sha(config_path)
    scope = {'config_paths': config_paths, 'source_refs': source_refs,
             'op_indices': op_indices}
    check_ids = [item['id'] for item in blocking_items]
    scope_binding = {'scope': scope, 'check_ids': check_ids}
    scope_sha256 = _json_sha(scope_binding)
    report_template = {
        'schema_version': 1,
        'critique_kind': 'targeted',
        'status': 'unknown',
        'candidate_sha256': candidate_sha256,
        'source_bundle_hash': source_index['source_bundle_hash'],
        'scope_sha256': scope_sha256,
        'scope': scope,
        'checks': [{'id': issue['id'],
                    'status': 'unknown', 'evidence': [], 'issue_ids': []}
                   for issue in blocking_items],
        'issues': [],
        'critic': 'independent targeted critique agent',
    }
    report_schema = _load(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'schemas', 'targeted_critique_report.schema.json'))
    authorization_path = os.path.join(
        os.path.dirname(os.path.abspath(context_manifest_path)),
        'targeted_authorization.json')
    authorization = {
        'schema_version': 1,
        'candidate_sha256': candidate_sha256,
        'source_bundle_hash': source_index['source_bundle_hash'],
        'scope': scope,
        'scope_sha256': scope_sha256,
        'check_ids': check_ids,
        'check_contracts': blocking_items,
        'report_schema': report_schema,
        'report_template': report_template,
        'report_binding_instructions': [
            'Set context_manifest_sha256 to the SHA256 of the current '
            'context_manifest.json before writing the report.',
            'Replace every unknown check status with passed or failed and '
            'attach scoped evidence.',
            'Use source_ref and config_path values exactly as listed in '
            'scope; every evidence op index must also be in scope.op_indices.',
            'Set report status to passed only when all checks pass and no '
            'error issue remains.',
            'For invocation, template, or boundary checks, compare the first, '
            'representative, and final scoped invocations; do not inspect only the '
            'representative range.',
            'A targeted conclusion cannot override an unresolved deterministic blocker.',
        ],
    }
    _write(authorization_path, authorization)
    inputs['targeted_authorization'] = _artifact(authorization_path)
    context = {
        'schema_version': 1,
        'stage': 'targeted_critique',
        'source_bundle_hash': source_index['source_bundle_hash'],
        'candidate_sha256': candidate_sha256,
        'inputs': inputs,
        'bindings_not_llm_inputs': bindings,
        'forbidden_inputs': list(FORBIDDEN_INPUT_MARKERS),
    }
    _write(context_manifest_path, context)
    template = dict(report_template)
    template['context_manifest_sha256'] = _sha(context_manifest_path)
    request = {
        'task': 'critique only the declared revision scope',
        'schema': 'schemas/targeted_critique_report.schema.json',
        'session': {'clean_context_required': True, 'fork_turns': 'none'},
        'inputs': inputs,
        'candidate_sha256': candidate_sha256,
        'scope': template['scope'],
        'blocking_items': blocking_items,
        'context_manifest': os.path.realpath(context_manifest_path),
        'bindings_not_llm_inputs': bindings,
        'output_expected': os.path.realpath(report_output),
        'rules': [
            'Use only context_manifest.inputs and review only scope.',
            'Do not read old configs, validations, critiques, revision requests, iteration files, reports, UI artifacts, screenshots, or chat history.',
            'This targeted critique cannot produce passed_at_cap and cannot be used for scoring.',
            'For invocation, template, or boundary checks, compare first, representative, and final scoped invocations and require source-backed reasons for any special template.',
            'Do not mark a blocker passed as a way to override a deterministic validation error; the validator rejects same-ID conflicts.',
        ],
        'critique_template': template,
    }
    _write(output_path, request)
    return request


def main():
    parser = argparse.ArgumentParser(description='Prepare targeted critique request')
    parser.add_argument('-c', '--config', required=True)
    parser.add_argument('--source-index', required=True)
    parser.add_argument('--revision-context', required=True)
    parser.add_argument('--context-manifest', required=True)
    parser.add_argument('--targeted-output', default='targeted_critique_report.json')
    parser.add_argument('-o', '--output', required=True)
    args = parser.parse_args()
    request = prepare_targeted_request(
        args.config, args.source_index, args.revision_context,
        args.output, args.context_manifest, args.targeted_output)
    if request.get('status') == 'insufficient_targeted_evidence':
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
