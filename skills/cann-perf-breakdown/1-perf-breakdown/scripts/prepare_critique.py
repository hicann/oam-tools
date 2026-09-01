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
"""Prepare a clean-context request for the final eleven-item critique."""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from validate_critique import REQUIRED_CHECKS  # noqa: E402
from prepare_revision_context import FORBIDDEN_INPUT_MARKERS  # noqa: E402


FINAL_CHECK_CONTRACTS = (
    ('model_identity_and_variant',
     'Verify that the manifest, checkpoint config, source, and candidate describe '
     'the same model and variant.'),
    ('module_inventory_complete',
     'Verify that every major module explicitly called by the source is represented '
     'in the candidate.'),
    ('learned_layer_vs_invocation',
     'Distinguish learned model layers from runtime invocations; repeated calls must '
     'not be represented as additional learned layers.'),
    ('config_instantiation_params',
     'Verify instantiated layer, expert, head, and related scalar values against the '
     'checkpoint config rather than unbound Python defaults.'),
    ('forward_call_order',
     'Verify candidate node order against the actual source forward call order.'),
    ('residual_parallel_skip_topology',
     'Verify both residual endpoints, parallel forks and rejoins, and skip paths '
     'against source dataflow.'),
    ('trace_module_attribution',
     'Verify semantic ownership of trace operations, not merely that each operation '
     'has an owner.'),
    ('layer_and_fusion_boundaries',
     'Verify layer boundaries and ownership of cross-layer or fused operations.'),
    ('runtime_vs_model_classification',
     'Verify that main computation is not classified as runtime or excluded and that '
     'runtime nodes occur in the trace.'),
    ('op_coverage_and_duplicate_ownership',
     'Verify complete operation coverage with no duplicate ownership.'),
    ('source_ref_authenticity',
     'Verify every source_ref exists, has valid line bounds, and supports the claimed '
     'construction.'),
)


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


def _indexed_source_snippets(index):
    snippets = []
    for record in index.get('files') or []:
        ranges = []
        for item in record.get('classes') or []:
            for method in ('init', 'forward'):
                if item.get(method):
                    ranges.append((item['qualname'], method,
                                   item[method]['line_start'], item[method]['line_end']))
        for item in record.get('functions') or []:
            if item.get('kind') == 'function':
                ranges.append((item['qualname'], 'function',
                               item['line_start'], item['line_end']))
        if not ranges:
            continue
        path = os.path.join(record['root'], record['path'])
        with open(path, encoding='utf-8') as stream:
            lines = stream.readlines()
        for qualname, kind, start, end in sorted(set(ranges), key=lambda item: item[2:]):
            snippets.append({
                'source_ref': f'{record["path"]}:{start}-{end}',
                'qualname': qualname,
                'kind': kind,
                'file_sha256': record['sha256'],
                'text': ''.join(lines[start - 1:end]),
            })
    return {'schema_version': 1, 'source_bundle_hash': index['source_bundle_hash'],
            'snippets': snippets}


def prepare_request(*, config_path, raw_ops_path, manifest_path, output_path,
                    critique_output, source_index_path=None,
                    raw_ops_compact_path=None, dataflow_path=None,
                    checkpoint_config_path=None, context_manifest_path=None):
    bindings = {
        'analysis_config': _artifact(config_path),
        'raw_ops': _artifact(raw_ops_path),
        'model_manifest': _artifact(manifest_path),
    }
    inputs = {
        'current_candidate': _artifact(config_path),
        'model_manifest': _artifact(manifest_path),
    }
    source_bundle_hash = None
    if source_index_path:
        index = _load(source_index_path)
        source_bundle_hash = index['source_bundle_hash']
        bindings['source_index'] = _artifact(source_index_path)
        inputs['source_index'] = bindings['source_index']
        context_base = os.path.dirname(os.path.abspath(
            context_manifest_path or output_path))
        snippets_path = os.path.join(context_base, 'source_snippets.json')
        _write(snippets_path, _indexed_source_snippets(index))
        inputs['source_snippets'] = _artifact(snippets_path)
        bindings['source_snippets'] = inputs['source_snippets']
    if raw_ops_compact_path and os.path.exists(raw_ops_compact_path):
        inputs['raw_ops_compact'] = _artifact(raw_ops_compact_path)
        bindings['raw_ops_compact'] = inputs['raw_ops_compact']
    for key, path in (('dataflow_source', dataflow_path),
                      ('checkpoint_config', checkpoint_config_path)):
        if path and os.path.exists(path):
            bindings[key] = _artifact(path)
            inputs[key] = bindings[key]

    template = {
        'schema_version': 1,
        'critique_kind': 'full_final',
        'status': 'unknown',
        'critic': 'independent final critique agent',
        'artifacts': bindings,
        'checks': [{'id': identifier, 'status': 'unknown', 'evidence': [],
                    'issue_ids': []} for identifier in REQUIRED_CHECKS],
        'issues': [],
    }
    context_manifest_path = context_manifest_path or os.path.join(
        os.path.dirname(os.path.abspath(output_path)), 'context_manifest.json')
    report_schema = _load(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'schemas', 'critique_report.schema.json'))
    authorization_path = os.path.join(
        os.path.dirname(os.path.abspath(context_manifest_path)),
        'final_authorization.json')
    authorization = {
        'schema_version': 1,
        'check_ids': list(REQUIRED_CHECKS),
        'check_contracts': [
            {'id': identifier, 'requirement': requirement}
            for identifier, requirement in FINAL_CHECK_CONTRACTS
        ],
        'report_schema': report_schema,
        'report_template': template,
        'artifact_bindings': bindings,
        'output_expected': os.path.realpath(critique_output),
        'report_binding_instructions': [
            'Add the current context_manifest.json path and SHA256 as the '
            'context_manifest artifact before writing the report.',
            'Preserve every artifact path and SHA256 from artifact_bindings.',
            'Replace every unknown check status with passed, failed, or unknown and '
            'attach evidence for every passed check.',
            'Set status to failed when any error issue exists or any check fails; '
            'set status to passed only when all eleven checks pass.',
            'Set critiqued_at to the current UTC time when writing the report.',
            'Use only source refs and op indices available in the authorized inputs.',
            'Use config_evidence only for key paths that resolve in an authorized '
            'checkpoint_config artifact; when checkpoint_config is absent, do not '
            'use config_evidence to cite model_manifest or any other artifact.',
        ],
    }
    _write(authorization_path, authorization)
    inputs['final_authorization'] = _artifact(authorization_path)
    context_manifest = {
        'schema_version': 1,
        'stage': 'final_critique',
        'source_bundle_hash': source_bundle_hash,
        'inputs': inputs,
        'forbidden_inputs': list(FORBIDDEN_INPUT_MARKERS),
    }
    _write(context_manifest_path, context_manifest)
    bindings['context_manifest'] = _artifact(context_manifest_path)
    request = {
        'task': 'independently run the final eleven-item critique of the current candidate',
        'protocol': 'references/critique_protocol.md',
        'schema': 'schemas/critique_report.schema.json',
        'session': {
            'clean_context_required': True,
            'fork_turns': 'none',
            'fallback': 'stop at awaiting_final_critique and use a new window',
        },
        'inputs': inputs,
        'bindings_not_llm_inputs': bindings,
        'context_manifest': os.path.realpath(context_manifest_path),
        'required_checks': list(REQUIRED_CHECKS),
        'output_expected': os.path.realpath(critique_output),
        'instructions': [
            'Use only context_manifest.inputs; do not inherit the decomposition conversation.',
            'Do not read prior candidates, critiques, validations, revision requests, iteration artifacts, Markdown, HTML, UI JSON, screenshots, or browser acceptance output.',
            'Complete all eleven checks. This is the only critique eligible for final scoring.',
            'Preserve every artifact SHA256 in critique_template.artifacts.',
        ],
        'critique_template': template,
    }
    _write(output_path, request)
    return request


def main():
    parser = argparse.ArgumentParser(description='Prepare final independent critique request')
    parser.add_argument('-c', '--config', required=True)
    parser.add_argument('-r', '--raw-ops', required=True)
    parser.add_argument('-m', '--manifest', required=True)
    parser.add_argument('--dataflow')
    parser.add_argument('--checkpoint-config')
    parser.add_argument('--op-segments', help='DEPRECATED compatibility input; never exposed')
    parser.add_argument('--source-dir', action='append', default=[],
                        help='DEPRECATED compatibility input; use --source-index')
    parser.add_argument('--source-index')
    parser.add_argument('--raw-ops-compact')
    parser.add_argument('--context-manifest')
    parser.add_argument('--critique-output', default='critique_report.json')
    parser.add_argument('-o', '--output', required=True)
    args = parser.parse_args()
    prepare_request(
        config_path=args.config, raw_ops_path=args.raw_ops, manifest_path=args.manifest,
        output_path=args.output, critique_output=args.critique_output,
        source_index_path=args.source_index,
        raw_ops_compact_path=args.raw_ops_compact, dataflow_path=args.dataflow,
        checkpoint_config_path=args.checkpoint_config,
        context_manifest_path=args.context_manifest)
    print(f'critique request written: {args.output}')


if __name__ == '__main__':
    main()
