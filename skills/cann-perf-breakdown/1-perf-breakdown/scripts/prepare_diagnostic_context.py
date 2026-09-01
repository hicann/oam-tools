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
"""Prepare a bounded, hash-bound context for controlled diagnostic patches."""
import argparse
import hashlib
import json
import os
import sys

import prepare_revision_context as revision


HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
FORBIDDEN_INPUT_MARKERS = (
    'iterations/', 'critique_report.json', 'critique_validation.json',
    'validation_report.json', '.md', '.html', 'ui.json', 'screenshot',
)
PROTECTED_ARTIFACTS = (
    'raw_ops', 'raw_ops_details', 'raw_ops_compact', 'source_index',
    'model_source', 'validation_report', 'checker_code', 'skill_code',
    'base_model_manifest',
)


def _load(path):
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def _write(path, value):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, sort_keys=True)
        stream.write('\n')


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


def _artifact(path):
    return {'path': os.path.realpath(path), 'sha256': _sha(path)}


def _operator_name(operator, field):
    if field == 'name':
        return str(operator.get('name') or '')
    return str(operator.get('normalized_name') or operator.get('name') or '')


def _selector_matches(operator, selector):
    field = selector.get('field')
    mode = selector.get('match')
    values = [value for value in selector.get('values') or []
              if isinstance(value, str) and value]
    if field not in ('name', 'normalized_name') or mode not in ('exact', 'prefix', 'contains'):
        return False
    candidate = _operator_name(operator, field)
    if mode == 'exact':
        return candidate in values
    if mode == 'prefix':
        return any(candidate.startswith(value) for value in values)
    return any(value in candidate for value in values)


def _selected_raw_ops(raw_ops, routes):
    selectors = [selector for route in routes
                 for selector in route.get('trace_selectors') or []]
    operators = raw_ops.get('operators') or raw_ops.get('ops') or []
    selected = [operator for operator in operators
                if any(_selector_matches(operator, selector) for selector in selectors)]
    return {
        'schema_version': 1,
        'selectors': selectors,
        'op_indices': sorted(operator['index'] for operator in selected
                             if isinstance(operator.get('index'), int)),
        'operators': selected,
    }


def _operator_summary(raw_ops):
    counts = {}
    for operator in raw_ops.get('operators') or raw_ops.get('ops') or []:
        name = _operator_name(operator, 'normalized_name')
        counts[name] = counts.get(name, 0) + 1
    return {'schema_version': 1,
            'operator_counts': [{'name': name, 'count': count}
                                for name, count in sorted(counts.items())]}


def _allowed_targets(routes):
    result = {}
    for route in routes:
        if route.get('mode') != 'bounded_patch':
            continue
        for target, prefixes in (route.get('allowed_targets') or {}).items():
            if target not in ('analysis_config', 'manifest_hypothesis'):
                continue
            bucket = result.setdefault(target, [])
            for prefix in prefixes or []:
                if prefix not in bucket:
                    bucket.append(prefix)
    return result


def _selected_nodes(document, routes, target):
    nodes = []
    seen = set()
    for route in routes:
        for path in (route.get('allowed_targets') or {}).get(target) or []:
            if path in seen:
                continue
            exists, value = revision._resolve(document, path)
            if exists:
                nodes.append({'path': path, 'value': value})
                seen.add(path)
    return {'schema_version': 1, 'nodes': nodes}


def prepare_diagnostic_context(config_path, manifest_path, source_index_path,
                               raw_ops_path, revision_request_path, output_path,
                               context_manifest_path):
    blocked = _load(revision_request_path)
    routes = blocked.get('diagnostic_routes') or []
    issues = blocked.get('blocking_issues') or []
    index = _load(source_index_path)
    raw_ops = _load(raw_ops_path)
    allowed_targets = _allowed_targets(routes)

    context_dir = os.path.dirname(os.path.abspath(context_manifest_path))
    source_snippets_path = os.path.join(context_dir, 'source_snippets.json')
    raw_slice_path = os.path.join(context_dir, 'raw_ops.slice.json')
    raw_summary_path = os.path.join(context_dir, 'raw_ops.summary.json')
    candidate_nodes_path = os.path.join(context_dir, 'candidate_nodes.json')
    manifest_nodes_path = os.path.join(context_dir, 'manifest_nodes.json')
    authorization_path = os.path.join(
        context_dir, 'diagnostic_authorization.json')
    snippets = revision._source_snippets(index, issues)
    raw_slice = _selected_raw_ops(raw_ops, routes)
    _write(source_snippets_path, snippets)
    _write(raw_slice_path, raw_slice)
    _write(raw_summary_path, _operator_summary(raw_ops))
    _write(candidate_nodes_path, _selected_nodes(_load(config_path), routes, 'analysis_config'))
    _write(manifest_nodes_path, _selected_nodes(
        _load(manifest_path), routes, 'manifest_hypothesis'))

    inputs = {
        'candidate_nodes': _artifact(candidate_nodes_path),
        'manifest_nodes': _artifact(manifest_nodes_path),
        'source_index': _artifact(source_index_path),
        'source_snippets': _artifact(source_snippets_path),
        'raw_ops_slice': _artifact(raw_slice_path),
        'raw_ops_summary': _artifact(raw_summary_path),
        'diagnostic_patch_schema': _artifact(os.path.join(
            SKILL_ROOT, 'schemas', 'diagnostic_patch.schema.json')),
    }
    base_artifacts = {
        'analysis_config': _artifact(config_path),
        'model_manifest': _artifact(manifest_path),
        'source_index': _artifact(source_index_path),
        'raw_ops': _artifact(raw_ops_path),
    }
    context = {
        'schema_version': 1,
        'stage': 'controlled_diagnosis',
        'source_bundle_hash': index.get('source_bundle_hash'),
        'inputs': dict(inputs),
        'bindings_not_llm_inputs': {'raw_ops': _artifact(raw_ops_path)},
        'forbidden_inputs': list(FORBIDDEN_INPUT_MARKERS),
        'protected_artifacts': list(PROTECTED_ARTIFACTS),
    }
    request = {
        'schema_version': 1,
        'status': 'awaiting_controlled_diagnosis',
        'task': 'diagnose unresolved ownership and propose only authorized evidence-backed patches',
        'schema': 'schemas/diagnostic_patch.schema.json',
        'output_expected': os.path.join(
            os.path.dirname(os.path.abspath(output_path)), 'diagnostic_patch.json'),
        'session': {'fork_turns': 'none', 'inherit_history': False},
        'inputs': dict(inputs),
        'base_artifacts': base_artifacts,
        'blocking_issues': issues,
        'diagnostic_routes': routes,
        'allowed_targets': allowed_targets,
        'protected_artifacts': list(PROTECTED_ARTIFACTS),
        'context_manifest': os.path.realpath(context_manifest_path),
        'rules': [
            'Read only context_manifest.inputs.',
            'Never patch raw evidence, source/index files, validation output, or Skill/checker code.',
            'Use proposed_patch only when every operation is inside allowed_targets.',
            'Use insufficient_external_evidence when a checkpoint/runtime fact is required.',
            'Use tool_defect when the parser, checker, or routing policy must change.',
        ],
    }
    request['request_sha256'] = _json_sha(request)
    _write(output_path, request)
    authorization = {
        'schema_version': 1,
        'request_sha256': request['request_sha256'],
        'base_artifacts': base_artifacts,
        'blocking_issues': issues,
        'diagnostic_routes': routes,
        'allowed_targets': allowed_targets,
        'output_expected': request['output_expected'],
    }
    _write(authorization_path, authorization)
    context['inputs']['diagnostic_authorization'] = _artifact(
        authorization_path)
    _write(context_manifest_path, context)
    return request


def main():
    parser = argparse.ArgumentParser(description='Prepare controlled diagnostic context')
    parser.add_argument('-c', '--config', required=True)
    parser.add_argument('-m', '--manifest', required=True)
    parser.add_argument('--source-index', required=True)
    parser.add_argument('-r', '--raw-ops', required=True)
    parser.add_argument('--revision-request', required=True)
    parser.add_argument('--context-manifest', required=True)
    parser.add_argument('-o', '--output', required=True)
    args = parser.parse_args()
    prepare_diagnostic_context(
        args.config, args.manifest, args.source_index, args.raw_ops,
        args.revision_request, args.output, args.context_manifest)
    print(f'controlled diagnostic request written: {args.output}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
