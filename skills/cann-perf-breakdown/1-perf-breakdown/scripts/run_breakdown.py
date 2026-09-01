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
"""
run_breakdown.py — generic forward-eval driver for the Mode A workflow.

Runs the deterministic parts of the Skill flow on ANY model + trace and stops where
human/AI judgment is required. It NEVER imports the DS3.2 golden builder and NEVER
fabricates a passed result.

Inputs:
  --model-dir DIR         model source (configuration_*.py / modeling_*.py)
  --csv FILE              kernel_details.csv (profiling)
  --trace FILE            optional trace_view.json, for the declared AI Core Freq counter
  --runtime-config FILE   optional runtime YAML (parallel_config); records the capture's
                          parallel layout. It does NOT define the architecture.
  --checkpoint-config FILE optional deployed checkpoint config.json; authoritative for
                           scalar architecture facts and SHA256-bound in the manifest.
  --rank N                optional global rank id (never assumed to equal pipeline stage)
  --pipeline-stage N      optional explicit pipeline stage id
  --out DIR               output directory

Pipeline:
  Source scan  source_index.json + source_scan_receipt.json
  Evidence     manifest, raw_ops, compact ops, dataflow and candidate hints
  Mapping      ai_mapping_request.json + stage context_manifest.json
  Pre-terminal deterministic validation
  Revisions    isolated revision context + targeted critique only
  Final        clean-context eleven-item critique, validation and score
  Publish      metrics only after passed_at_cap

Prints a final JSON status object with the stage reached.
"""
import argparse
import copy
import datetime
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys

import extract_source_index

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)

DEFAULT_MAX_REVISIONS = 4
DEFAULT_STALL_LIMIT = 2
FORMAL_OUTPUT_INTERFACES = {
    'candidate': 'analysis_config.json',
    'final_critique': 'critique_report.json',
    'final_critique_validation': 'critique_validation.json',
    'deterministic_validation': 'validation_report.json',
    'score': 'breakdown_score.json',
}
REVISION_SCOPE_POLICY_SOURCE = 'deterministic_validation_only'


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _candidate_changed_since_last_iteration(history, candidate_path):
    """Whether targeted review has a new semantic candidate to inspect.

    Missing history or a missing snapshot fails open so recovery from old/incomplete run
    directories remains possible. A byte-identical latest snapshot is not a revision and
    must return to the revision state without spending another targeted-review call.
    """
    iterations = (history or {}).get('iterations') or []
    if not iterations:
        return True
    snapshot = iterations[-1].get('config_snapshot')
    if not snapshot or not os.path.exists(snapshot) or not os.path.exists(candidate_path):
        return True
    return _sha256_file(snapshot) != _sha256_file(candidate_path)


def _extraction_stage_matches(receipt_path, stage, identity, artifact_paths):
    try:
        receipt = _read_json(receipt_path)
        recorded = (receipt.get('stages') or {}).get(stage) or {}
        if recorded.get('identity') != identity:
            return False
        expected = recorded.get('artifacts') or []
        current = [{'path': os.path.realpath(path), 'sha256': _sha256_file(path)}
                   for path in artifact_paths]
        return expected == current
    except (OSError, TypeError, ValueError):
        return False


def _record_extraction_stage(receipt_path, stage, identity, artifact_paths):
    try:
        receipt = _read_json(receipt_path)
        if receipt.get('schema_version') != 1 or not isinstance(
                receipt.get('stages'), dict):
            receipt = {'schema_version': 1, 'stages': {}}
    except (OSError, TypeError, ValueError):
        receipt = {'schema_version': 1, 'stages': {}}
    receipt['stages'][stage] = {
        'identity': identity,
        'artifacts': [
            {'path': os.path.realpath(path), 'sha256': _sha256_file(path)}
            for path in artifact_paths
        ],
    }
    _write_json(receipt_path, receipt)


def _indexed_model_sources(index):
    sources = []
    for record in index.get('files') or []:
        root = record.get('root')
        relative = record.get('path')
        if not root or not relative:
            continue
        path = os.path.realpath(os.path.join(root, *relative.replace('\\', '/').split('/')))
        sources.append({'path': path, 'sha256': record.get('sha256')})
    return sorted(sources, key=lambda item: item['path'])


def _mapping_input_artifacts(inputs):
    """Snapshot every existing file exposed to the initial mapping worker."""
    artifacts = {}
    for name, value in inputs.items():
        if isinstance(value, str) and os.path.isfile(value):
            artifacts[name] = {
                'path': os.path.realpath(value),
                'sha256': _sha256_file(value),
            }
        elif isinstance(value, list):
            records = []
            for item in value:
                path = item.get('path') if isinstance(item, dict) else None
                if path and os.path.isfile(path):
                    records.append({
                        'path': os.path.realpath(path),
                        'sha256': _sha256_file(path),
                    })
            if records:
                artifacts[name] = records
    return artifacts


def _mapping_input_artifacts_match(artifacts):
    for value in (artifacts or {}).values():
        records = value if isinstance(value, list) else [value]
        for record in records:
            path = record.get('path') if isinstance(record, dict) else None
            digest = record.get('sha256') if isinstance(record, dict) else None
            if not path or not digest or not os.path.isfile(path):
                return False
            if _sha256_file(path) != digest:
                return False
    return bool(artifacts)


def _mapping_request_matches_current_inputs(request_path, inputs, source_bundle_hash,
                                            source_index_sha256):
    """Validate a mapping request against the final evidence snapshot for this run."""
    try:
        request = _read_json(request_path)
        context = _read_json(request.get('context_manifest'))
        current_artifacts = _mapping_input_artifacts(inputs)
        return bool(
            request.get('source_bundle_hash') == source_bundle_hash
            and context.get('source_bundle_hash') == source_bundle_hash
            and request.get('source_index_sha256') == source_index_sha256
            and context.get('source_index_sha256') == source_index_sha256
            and request.get('inputs') == inputs
            and context.get('inputs') == inputs
            and request.get('input_artifacts') == current_artifacts
            and context.get('input_artifacts') == current_artifacts
            and _mapping_input_artifacts_match(current_artifacts))
    except (OSError, TypeError, ValueError):
        return False


def _record_source_scan_receipt(receipt_path, source_index_path, source_bundle_hash,
                                candidate_path):
    """Record the one full source-reading pass that produced the first candidate."""
    payload = {
        'schema_version': 1,
        'status': 'valid',
        'source_bundle_hash': source_bundle_hash,
        'source_index_sha256': _sha256_file(source_index_path),
        'initial_candidate': os.path.realpath(candidate_path),
        'initial_candidate_sha256': (_sha256_file(candidate_path)
                                     if os.path.exists(candidate_path) else None),
        'recorded_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    _write_json(receipt_path, payload)
    return payload


def _source_receipt_state(receipt_path, source_index_path):
    if not os.path.exists(receipt_path):
        return {'status': 'missing'}
    try:
        with open(receipt_path, encoding='utf-8') as stream:
            receipt = json.load(stream)
        with open(source_index_path, encoding='utf-8') as stream:
            index = json.load(stream)
    except (OSError, ValueError) as error:
        return {'status': 'invalid', 'reason': str(error)}
    if receipt.get('source_bundle_hash') != index.get('source_bundle_hash'):
        return {'status': 'invalidated_source_changed',
                'previous_source_bundle_hash': receipt.get('source_bundle_hash'),
                'current_source_bundle_hash': index.get('source_bundle_hash')}
    return {'status': 'valid', 'source_bundle_hash': index.get('source_bundle_hash')}


def _source_scan_acknowledged(previous_receipt, current_hash, supplied_hash,
                              current_index_sha=None, mapping_index_sha=None):
    """A new mapping must acknowledge both the source bundle and its deterministic index."""
    if (previous_receipt or {}).get('status') == 'valid':
        return True
    return bool(supplied_hash and supplied_hash == current_hash
                and current_index_sha and current_index_sha == mapping_index_sha)


def _source_index_receipt_matches(receipt, source_index_path):
    recorded = (receipt or {}).get('source_index_sha256')
    return bool(recorded and os.path.exists(source_index_path)
                and recorded == _sha256_file(source_index_path))


def _source_identity_changed(receipt, previous_index_hash, current_bundle_hash,
                             current_index_sha):
    if previous_index_hash and previous_index_hash != current_bundle_hash:
        return True
    if (receipt or {}).get('status') != 'valid':
        return False
    return bool(receipt.get('source_bundle_hash') != current_bundle_hash
                or receipt.get('source_index_sha256') != current_index_sha)


def _archive_source_dependent_state(out_dir, previous_hash, current_hash):
    """Move stale candidate state aside so a new source scan cannot consume it."""
    base = os.path.join(out_dir, 'invalidated_source_state',
                        f'{str(previous_hash)[:12]}_to_{str(current_hash)[:12]}')
    archive = base
    suffix = 2
    while os.path.exists(archive):
        archive = f'{base}_{suffix}'
        suffix += 1
    os.makedirs(archive, exist_ok=False)
    names = (
        'contexts', 'iterations', 'iteration_history.json', 'revision_scope.json',
        'revision_request.json', 'targeted_critique_request.json',
        'targeted_critique_report.json', 'targeted_critique_validation.json',
        'critique_request.json', 'critique_report.json', 'critique_validation.json',
        'validation_report.json', 'breakdown_score.json',
    )
    for name in names:
        path = os.path.join(out_dir, name)
        if os.path.exists(path):
            shutil.move(path, os.path.join(archive, name))
    return archive


def _progress_signature(*, deterministic_errors, hard_gates, unmapped, duplicate,
                        out_of_range, targeted_blockers):
    return {
        'deterministic_errors': int(deterministic_errors),
        'hard_gates': int(hard_gates),
        'unmapped': int(unmapped),
        'duplicate': int(duplicate),
        'out_of_range': int(out_of_range),
        'targeted_blockers': int(targeted_blockers),
    }


def _made_semantic_progress(previous, current):
    """Progress is a Pareto improvement in one of the named blocking classes."""
    keys = tuple(_progress_signature(
        deterministic_errors=0, hard_gates=0, unmapped=0, duplicate=0,
        out_of_range=0, targeted_blockers=0))
    return (all(current.get(key, 0) <= previous.get(key, 0) for key in keys)
            and any(current.get(key, 0) < previous.get(key, 0) for key in keys))


def _preterminal_passed(validation_report, targeted_validation, targeted_required):
    if validation_report.get('status') != 'passed':
        return False
    if not targeted_required:
        return True
    return bool(targeted_validation
                and targeted_validation.get('status') == 'passed'
                and (targeted_validation.get('detail') or {}).get('clears_scope') is True)


def _targeted_requires_candidate_revision(targeted_validation):
    """A deterministic conflict cannot be repaired by asking the critic again."""
    return any(item.get('id') == 'TC_DETERMINISTIC_CONFLICT'
               for item in (targeted_validation or {}).get('issues') or [])


def _revision_stop_stage(revision, max_revisions, stall_limit, no_progress):
    if revision >= max_revisions:
        return 'blocked_max_revisions'
    if stall_limit > 0 and no_progress >= stall_limit:
        return 'blocked_no_progress'
    return 'needs_revision'


def _diagnostic_outcome_stage(outcome):
    return {
        'insufficient_external_evidence': 'blocked_missing_external_evidence',
        'tool_defect': 'blocked_tool_defect',
    }.get(outcome)


def _resume_controlled_diagnostic(out, analysis_config, base_manifest):
    """Reuse a validated manifest hypothesis without replaying its one-shot patch."""
    expected_config = os.path.realpath(out('analysis_config.diagnostic.json'))
    if not analysis_config or os.path.realpath(analysis_config) != expected_config:
        return analysis_config, base_manifest
    receipt_path = out('diagnostic_application.json')
    hypothesis_path = out('model_manifest.hypothesis.json')
    if not all(os.path.exists(path) for path in (
            analysis_config, base_manifest, receipt_path, hypothesis_path)):
        return analysis_config, base_manifest
    try:
        receipt = _read_json(receipt_path)
        base = receipt.get('base_artifacts') or {}
        derived = receipt.get('derived_artifacts') or {}
        recorded_manifest = derived.get('manifest_hypothesis') or {}
        base_manifest_binding = base.get('model_manifest') or {}
        valid = (
            receipt.get('status') == 'applied'
            and os.path.realpath(recorded_manifest.get('path', ''))
            == os.path.realpath(hypothesis_path)
            and recorded_manifest.get('sha256') == _sha256_file(hypothesis_path)
            and base_manifest_binding.get('sha256') == _sha256_file(base_manifest)
        )
    except (OSError, TypeError, ValueError):
        valid = False
    return ((analysis_config, hypothesis_path) if valid
            else (analysis_config, base_manifest))


def _semantic_revision_count(history):
    """The baseline candidate is attempt 1; only later attempts consume corrections."""
    return max(0, len(history.get('iterations') or []) - 1)


def _terminal_detail(stage, signature):
    reason = {
        'blocked_no_progress': 'the configured consecutive semantic revisions reduced no blocker class',
        'blocked_max_revisions': 'four semantic revisions completed without clearing all gates',
    }.get(stage, 'candidate still has blocking conditions')
    return {'stage': stage, 'blocking_counts': dict(signature), 'root_cause': reason}


def _persist_terminal_status(history_path, run_identity, stage, signature):
    history = _load_history(history_path, run_identity)
    detail = _terminal_detail(stage, signature)
    history['terminal_status'] = stage
    history['terminal_detail'] = detail
    history['terminated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if history['iterations']:
        history['iterations'][-1]['status'] = stage
    _write_json(history_path, history)
    return detail


def _terminal_history_state(history):
    stage = history.get('terminal_status')
    if stage not in ('blocked_no_progress', 'blocked_max_revisions'):
        return None
    return {'stage': stage, 'detail': history.get('terminal_detail') or {}}


def _revision_metadata(stage, semantic_revision, max_revisions, stall_limit,
                       no_progress, signature):
    blocked = stage in ('blocked_no_progress', 'blocked_max_revisions')
    detail = _terminal_detail(stage, signature)
    return {
        'status': stage,
        'current_revision': semantic_revision,
        'next_revision': None if blocked else semantic_revision + 1,
        'max_revisions': max_revisions,
        'remaining_revisions': max(0, max_revisions - semantic_revision),
        'stall_limit': stall_limit,
        'consecutive_no_progress': no_progress,
        'blocking_counts': detail['blocking_counts'],
        'root_cause': detail['root_cause'],
    }


def run(cmd):
    print('  $', ' '.join(str(c) for c in cmd))
    return subprocess.run(cmd, capture_output=True, text=True)


def _validation_command(py, validation_script, analysis_config, raw, manifest,
                        model_dir, skill_root, output, dataflow=None, profile=None):
    command = [py, validation_script, '-c', analysis_config, '-r', raw,
               '-m', manifest, '--source-dir', model_dir, '--source-dir', skill_root,
               '-o', output]
    if dataflow:
        command += ['--dataflow', dataflow]
    if profile:
        command += ['--profile', profile]
    return command


def main():
    ap = argparse.ArgumentParser(description='Generic Mode A forward-eval driver')
    ap.add_argument('--model-dir', required=True)
    ap.add_argument('--csv', required=True)
    ap.add_argument('--trace', help='trace_view.json, for the declared AI Core Freq counter')
    ap.add_argument('--runtime-config', help='runtime YAML for trace scope')
    ap.add_argument('--checkpoint-config',
                    help='explicit deployed checkpoint config.json; overrides runtime YAML model_path')
    ap.add_argument('--rank', type=int)
    ap.add_argument('--pipeline-stage', type=int,
                    help='explicit pipeline stage id; global --rank is not a stage id')
    ap.add_argument('--profile', help='execution profile id selected by this capture')
    ap.add_argument('--analysis-config',
                    help='AI/human-produced schema-v2 analysis_config.json (enables Steps 8-11)')
    ap.add_argument('--source-bundle-hash',
                    help='acknowledge the source_bundle_hash used to produce --analysis-config; '
                         'required after source drift invalidates a receipt')
    ap.add_argument('--critique-report',
                    help='independent critique_report.json bound to the current inputs. '
                         'Required for the formal pass path.')
    ap.add_argument('--targeted-critique-report',
                    help='scoped critique for an intermediate revision; never scored')
    ap.add_argument('--diagnostic-patch',
                    help='hash-bound controlled diagnostic patch for diagnostic_request.json')
    ap.add_argument('--out', required=True)
    ap.add_argument('--allow-warnings', action='store_true')
    ap.add_argument('--max-revisions', '--max-iterations', dest='max_iterations',
                    type=int, default=DEFAULT_MAX_REVISIONS, metavar='N',
                    help='maximum semantic revisions (default: 4); --max-iterations is a '
                         'deprecated compatibility alias')
    ap.add_argument('--stall-limit', type=int, default=DEFAULT_STALL_LIMIT,
                    help='stop early after N consecutive non-improving rounds; '
                         'default: 2; 0 remains accepted to disable early stop')
    ap.add_argument('--allow-step-variation', action='store_true',
                    help='select the representative step from the largest stable signature group')
    args = ap.parse_args()

    if args.max_iterations < 1:
        ap.error('--max-iterations must be >= 1')

    os.makedirs(args.out, exist_ok=True)
    py = sys.executable

    def sp(name):
        return os.path.join(HERE, name)

    def out(name):
        return os.path.join(args.out, name)

    status = {'stages': {}, 'out_dir': os.path.realpath(args.out)}
    analysis_config = args.analysis_config

    # This deterministic index is the only source-tree-wide read exposed to the decomposition
    # workflow. Later LLM stages receive the index plus bounded snippets, never the source tree.
    source_index = out('source_index.json')
    receipt_path = out('source_scan_receipt.json')
    previous_receipt = None
    if os.path.exists(receipt_path):
        try:
            with open(receipt_path, encoding='utf-8') as stream:
                previous_receipt = json.load(stream)
        except (OSError, ValueError):
            previous_receipt = {'status': 'invalid'}
    previous_index_hash = None
    try:
        if os.path.exists(source_index):
            source_index_payload = _read_json(source_index)
            previous_index_hash = source_index_payload.get('source_bundle_hash')
            verification = extract_source_index.verify_source_index(
                source_index_payload, [args.model_dir])
            receipt_matches = ((previous_receipt or {}).get('status') != 'valid'
                               or _source_index_receipt_matches(
                                   previous_receipt, source_index))
            if verification['matches'] and receipt_matches:
                status['stages']['source_index'] = 'verified_hash_only'
            else:
                source_index_payload = extract_source_index.build_source_index([args.model_dir])
                extract_source_index.write_json(source_index, source_index_payload)
                status['stages']['source_index'] = (
                    'rescanned_source_changed' if not verification['matches']
                    else 'rescanned_index_integrity')
        else:
            source_index_payload = extract_source_index.build_source_index([args.model_dir])
            extract_source_index.write_json(source_index, source_index_payload)
            status['stages']['source_index'] = 'scanned'
    except (OSError, ValueError) as error:
        status['error'] = str(error)
        return _finish(status, 'failed_source_index')
    current_index_sha = _sha256_file(source_index)
    status['source_bundle_hash'] = source_index_payload['source_bundle_hash']
    receipt_index_changed = bool(
        (previous_receipt or {}).get('status') == 'valid'
        and previous_receipt.get('source_index_sha256') != current_index_sha)
    source_changed = _source_identity_changed(
        previous_receipt, previous_index_hash,
        source_index_payload['source_bundle_hash'], current_index_sha)
    if source_changed:
        archive = _archive_source_dependent_state(
            args.out, previous_index_hash,
            source_index_payload['source_bundle_hash'])
        _write_json(receipt_path, {
            'schema_version': 1,
            'status': 'invalidated_source_changed',
            'previous_source_bundle_hash': previous_index_hash,
            'current_source_bundle_hash': source_index_payload['source_bundle_hash'],
            'invalidated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'archived_state': archive,
            'reason': ('source_index_integrity_changed' if receipt_index_changed
                       else 'source_bundle_changed'),
        })
        analysis_config = None
        status['stages']['source_scan_receipt'] = 'invalidated_source_changed'

    mapping_index_sha = None
    mapping_request_path = out('ai_mapping_request.json')
    if os.path.exists(mapping_request_path):
        try:
            previous_mapping = _read_json(mapping_request_path)
            mapping_context_path = previous_mapping.get('context_manifest')
            previous_mapping_context = _read_json(mapping_context_path)
            request_artifacts = previous_mapping.get('input_artifacts') or {}
            context_artifacts = previous_mapping_context.get('input_artifacts') or {}
            if (previous_mapping.get('source_bundle_hash')
                    == source_index_payload['source_bundle_hash']
                    and previous_mapping_context.get('source_bundle_hash')
                    == source_index_payload['source_bundle_hash']
                    and previous_mapping_context.get('source_index_sha256')
                    == previous_mapping.get('source_index_sha256')
                    and request_artifacts == context_artifacts
                    and _mapping_input_artifacts_match(request_artifacts)):
                mapping_index_sha = previous_mapping.get('source_index_sha256')
        except (OSError, ValueError, TypeError):
            mapping_index_sha = None
    acknowledged = _source_scan_acknowledged(
        previous_receipt, source_index_payload['source_bundle_hash'],
        args.source_bundle_hash, current_index_sha, mapping_index_sha)
    if analysis_config and not acknowledged:
        analysis_config = None
        status['stages']['source_scan_receipt'] = 'awaiting_source_bundle_acknowledgement'

    # Step 2: manifest
    manifest = out('model_manifest.json')
    manifest_cmd = [py, sp('extract_model_manifest.py'), '--model-dir', args.model_dir,
                    '--base-dir', SKILL_ROOT, '-o', manifest]
    if args.runtime_config:
        manifest_cmd.extend(['--runtime-config', args.runtime_config])
    if args.checkpoint_config:
        manifest_cmd.extend(['--checkpoint-config', args.checkpoint_config])
    r = run(manifest_cmd)
    status['stages']['manifest'] = 'ok' if r.returncode == 0 else 'error'
    if r.returncode != 0:
        status['error'] = r.stderr[-500:]
        return _finish(status, 'failed_manifest')

    # Step 4: raw ops
    raw = out('raw_ops.json')
    extraction_receipt = out('evidence_extraction_receipt.json')
    raw_artifacts = [raw, out('raw_ops_details.json'), out('raw_ops.compact.json'),
                     out('steps_summary.md')]
    raw_identity = {
        'csv_path': os.path.realpath(args.csv),
        'csv_sha256': _sha256_file(args.csv),
        'extractor_sha256': _sha256_file(sp('analyze_kernels.py')),
        'allow_step_variation': bool(args.allow_step_variation),
    }
    raw_cmd = [py, sp('analyze_kernels.py'), '-f', args.csv, '-o', raw,
               '-d', out('raw_ops_details.json'), '--compact-out', out('raw_ops.compact.json'),
               '-m', out('steps_summary.md')]
    if args.allow_step_variation:
        raw_cmd.append('--allow-step-variation')
    if _extraction_stage_matches(
            extraction_receipt, 'raw_ops', raw_identity, raw_artifacts):
        status['stages']['raw_ops'] = 'verified_hash_only'
    else:
        r = run(raw_cmd)
        status['stages']['raw_ops'] = 'extracted' if r.returncode == 0 else 'error'
        if r.returncode != 0:
            status['error'] = r.stderr[-500:]
            return _finish(status, 'failed_raw_ops')
        if all(os.path.exists(path) for path in raw_artifacts):
            _record_extraction_stage(
                extraction_receipt, 'raw_ops', raw_identity, raw_artifacts)

    # Step 4b: device clock. Non-fatal — a capture without AI Core counters yields a null
    # frequency, and the metrics that divide by it report unavailable rather than assuming one.
    freq_cmd = [py, sp('device_freq.py'), '-d', out('raw_ops_details.json'),
                '-o', out('device_freq.json')]
    if args.trace:
        freq_cmd += ['--trace', args.trace]
    r = run(freq_cmd)
    status['stages']['device_freq'] = (
        (r.stdout.strip().splitlines()[-1] if r.stdout else 'ok') if r.returncode == 0
        else f'unavailable: {(r.stderr or r.stdout)[-200:]}')

    # Step 5: source dataflow. `forward()` IS the dataflow graph, so extracting it here makes
    # the residual/fork topology available as evidence to the mapping step and as a comparison
    # target for validation — instead of asking a reader to assert branch correctness in prose.
    dataflow = out('dataflow_source.json')
    sources = sorted(glob.glob(os.path.join(args.model_dir, '**', 'modeling_*.py'),
                               recursive=True))
    if sources:
        dataflow_identity = {
            'source_bundle_hash': source_index_payload['source_bundle_hash'],
            'extractor_sha256': _sha256_file(sp('extract_dataflow.py')),
        }
        dataflow_cmd = [py, sp('extract_dataflow.py')]
        for source in sources:
            dataflow_cmd.extend(['-s', source])
        dataflow_cmd.extend(['-o', dataflow])
        if _extraction_stage_matches(
                extraction_receipt, 'dataflow', dataflow_identity, [dataflow]):
            status['stages']['dataflow'] = 'verified_hash_only'
        else:
            r = run(dataflow_cmd)
            status['stages']['dataflow'] = 'extracted' if r.returncode == 0 else 'error'
            if r.returncode != 0:
                status['error'] = (r.stderr or r.stdout)[-500:]
                return _finish(status, 'failed_dataflow')
            if os.path.exists(dataflow):
                _record_extraction_stage(
                    extraction_receipt, 'dataflow', dataflow_identity, [dataflow])
    else:
        dataflow = None
        status['stages']['dataflow'] = 'skipped_no_modeling_source'

    # Capture scope remains separate from architecture. Generate it only when the caller
    # supplied runtime ownership evidence; the mapping step can then annotate observed nodes
    # without inferring model structure from rank-local data.
    trace_scope = None
    if args.runtime_config or args.rank is not None or args.pipeline_stage is not None:
        trace_scope = out('trace_scope.json')
        scope_cmd = [py, sp('detect_trace_scope.py'), '-m', manifest, '-o', trace_scope]
        if args.runtime_config:
            scope_cmd.extend(['--yaml', args.runtime_config])
        if args.rank is not None:
            scope_cmd.extend(['--rank', str(args.rank)])
        if args.pipeline_stage is not None:
            scope_cmd.extend(['--pipeline-stage', str(args.pipeline_stage)])
        if args.analysis_config:
            scope_cmd.extend(['-c', args.analysis_config])
        r = run(scope_cmd)
        status['stages']['trace_scope'] = 'ok' if r.returncode == 0 else 'error'
        if r.returncode != 0:
            status['error'] = (r.stderr or r.stdout)[-500:]
            return _finish(status, 'failed_trace_scope')
        if analysis_config:
            analysis_config = _materialize_effective_config(
                analysis_config, trace_scope, out('analysis_config.effective.json'))
            status['stages']['trace_scope_config'] = analysis_config

    # Repeated intervals are useful search hints for the decomposition LLM, but they are not
    # source truth and never become boundaries automatically. Failure is non-fatal because the
    # LLM can still derive boundaries from forward() and the complete op sequence.
    segments = out('op_segments.json')
    r = run([py, sp('segment_layers.py'), '-r', raw, '-o', segments])
    if r.returncode == 0:
        status['stages']['op_segments'] = 'ok_candidate_hint'
    else:
        segments = None
        status['stages']['op_segments'] = f'unavailable: {(r.stderr or r.stdout)[-200:]}'

    # Step 6: AI mapping gate
    mapping_protocol = os.path.join(
        SKILL_ROOT, 'references', 'ai_mapping_protocol.md')
    scoring_protocol = os.path.join(
        SKILL_ROOT, 'references', 'breakdown_scoring.md')
    analysis_config_schema = os.path.join(
        SKILL_ROOT, 'schemas', 'analysis_config_v2.schema.json')
    mapping_inputs = {
        'source_index': source_index,
        'model_sources': _indexed_model_sources(source_index_payload),
        'model_manifest': manifest,
        'raw_ops_compact': out('raw_ops.compact.json'),
        'dataflow_source': dataflow,
        'mapping_protocol': mapping_protocol,
        'scoring_protocol': scoring_protocol,
        'analysis_config_schema': analysis_config_schema,
    }
    if segments and os.path.isfile(segments):
        mapping_inputs['op_segments'] = segments

    if analysis_config and not _mapping_request_matches_current_inputs(
            mapping_request_path, mapping_inputs,
            source_index_payload['source_bundle_hash'], current_index_sha):
        previous_mapping_sha = (
            _sha256_file(mapping_request_path)
            if os.path.isfile(mapping_request_path) else 'missing')
        current_mapping_sha = hashlib.sha256(json.dumps(
            _mapping_input_artifacts(mapping_inputs), sort_keys=True,
            separators=(',', ':')).encode('utf-8')).hexdigest()
        archive = _archive_source_dependent_state(
            args.out, previous_mapping_sha, current_mapping_sha)
        _write_json(receipt_path, {
            'schema_version': 1,
            'status': 'invalidated_mapping_inputs_changed',
            'source_bundle_hash': source_index_payload['source_bundle_hash'],
            'source_index_sha256': current_index_sha,
            'invalidated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'archived_state': archive,
            'reason': 'mapping_input_artifacts_changed',
        })
        analysis_config = None
        status['stages']['source_scan_receipt'] = (
            'invalidated_mapping_inputs_changed')

    history_path = out('iteration_history.json')
    if os.path.exists(history_path):
        run_identity = {'model_dir': os.path.realpath(args.model_dir),
                        'csv': os.path.realpath(args.csv)}
        try:
            terminal = _terminal_history_state(_load_history(history_path, run_identity))
        except ValueError as error:
            status['error'] = str(error)
            return _finish(status, 'failed_iteration_history')
        if terminal:
            status['terminal_detail'] = terminal['detail']
            return _finish(status, terminal['stage'],
                           note='This run already reached a persistent terminal revision state')

    if not analysis_config:
        request = out('ai_mapping_request.json')
        mapping_artifacts = _mapping_input_artifacts(mapping_inputs)
        mapping_context = out(os.path.join(
            'contexts', 'initial_mapping', 'context_manifest.json'))
        _write_json(mapping_context, {
            'schema_version': 1,
            'stage': 'initial_mapping',
            'source_bundle_hash': source_index_payload['source_bundle_hash'],
            'source_index_sha256': current_index_sha,
            'inputs': mapping_inputs,
            'input_artifacts': mapping_artifacts,
            'forbidden_inputs': [
                'iterations/', 'critique_report.json', 'critique_validation.json',
                'validation_report.json', 'revision_request.json', 'report.md',
                'metrics_report.md', '.html', 'ui.json', 'screenshot',
            ],
        })
        with open(request, 'w', encoding='utf-8') as f:
            json.dump({
                'task': 'map every op of the representative step to model/runtime/excluded',
                'protocol': mapping_protocol,
                'scoring_protocol': scoring_protocol,
                'session': {
                    'clean_context_required': True,
                    'fork_turns': 'none',
                    'inherit_history': False,
                },
                'inputs': mapping_inputs,
                'input_artifacts': mapping_artifacts,
                'source_bundle_hash': source_index_payload['source_bundle_hash'],
                'source_index_sha256': current_index_sha,
                'context_manifest': mapping_context,
                'output_expected': out(FORMAL_OUTPUT_INTERFACES['candidate']),
                'rules': [
                    'read only context_manifest.inputs and do not inherit chat history',
                    'every op -> model / runtime_auxiliary / (strictly-allowed) excluded',
                    'unmapped_ops must be empty for a passed result',
                    'MTP = 1 learned layer + N invocations; never N layers',
                    'no pipeline-rank claim without evidence',
                    'after source invalidation, resubmit the candidate with '
                    '--source-bundle-hash equal to this request source_bundle_hash',
                ],
            }, f, indent=2, ensure_ascii=False)
        return _finish(status, 'awaiting_ai_mapping',
                       note=f'AI mapping required. Request written to {request}. '
                            f'Produce analysis_config.json per the protocol, then re-run '
                            f'with --analysis-config.')

    if ((not previous_receipt or previous_receipt.get('status') != 'valid')
            and acknowledged):
        _record_source_scan_receipt(
            receipt_path, source_index, source_index_payload['source_bundle_hash'],
            analysis_config)
        status['stages']['source_scan_receipt'] = 'recorded'

    if analysis_config and not args.diagnostic_patch:
        resumed_config, resumed_manifest = _resume_controlled_diagnostic(
            out, analysis_config, manifest)
        if resumed_manifest != manifest:
            analysis_config, manifest = resumed_config, resumed_manifest
            status['stages']['controlled_diagnosis'] = 'resumed_derived_artifacts'

    if args.diagnostic_patch:
        analysis_config, manifest, diagnostic_stage = _apply_controlled_diagnostic(
            py, sp, out, args.diagnostic_patch, analysis_config, manifest)
        if diagnostic_stage:
            note = ('Correct diagnostic_patch.json against diagnostic_request.json; '
                    'no semantic revision was consumed.'
                    if diagnostic_stage == 'awaiting_controlled_diagnosis'
                    else 'Controlled diagnosis cannot produce an admissible patch from current evidence.')
            return _finish(status, diagnostic_stage, note=note)
        status['stages']['controlled_diagnosis'] = 'applied_to_derived_artifacts'

    status['active_candidate'] = os.path.realpath(analysis_config)
    status['active_manifest'] = os.path.realpath(manifest)

    # The protocol from here is deterministic pre-terminal gates, scoped critique, then final
    # eleven-item critique and scoring.
    return _run_candidate_pipeline(
        args=args, status=status, py=py, analysis_config=analysis_config,
        raw=raw, manifest=manifest, dataflow=dataflow, source_index=source_index,
        source_bundle_hash=source_index_payload['source_bundle_hash'], out=out, sp=sp)

def _read_json(path):
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def _apply_controlled_diagnostic(py, sp, out, diagnostic_patch, analysis_config, manifest):
    request = out('diagnostic_request.json')
    if not os.path.exists(request):
        return None, None, 'failed_diagnostic_request'
    validation_path = out('diagnostic_patch_validation.json')
    result, produced = _run_with_fresh_output([
        py, sp('validate_diagnostic_patch.py'), '-q', diagnostic_patch,
        '--request', request, '-o', validation_path,
    ], validation_path)
    if not produced:
        return None, None, 'failed_diagnostic_patch_validation'
    validation = _read_json(validation_path)
    if result.returncode != 0 or validation.get('status') != 'passed':
        return None, None, 'awaiting_controlled_diagnosis'
    report = _read_json(diagnostic_patch)
    stop_stage = _diagnostic_outcome_stage(report.get('outcome'))
    if stop_stage:
        return None, None, stop_stage

    config_output = out('analysis_config.diagnostic.json')
    manifest_output = out('model_manifest.hypothesis.json')
    receipt_output = out('diagnostic_application.json')
    result = run([
        py, sp('apply_diagnostic_patch.py'), '-q', diagnostic_patch,
        '--request', request, '-c', analysis_config, '-m', manifest,
        '--config-output', config_output, '--manifest-output', manifest_output,
        '--receipt-output', receipt_output,
    ])
    if result.returncode != 0 or not all(os.path.exists(path) for path in (
            config_output, manifest_output, receipt_output)):
        return None, None, 'failed_diagnostic_patch_application'
    return config_output, manifest_output, None


def _publish_formal_candidate(candidate_path, formal_path):
    if os.path.realpath(candidate_path) == os.path.realpath(formal_path):
        return formal_path
    os.makedirs(os.path.dirname(os.path.abspath(formal_path)), exist_ok=True)
    shutil.copy2(candidate_path, formal_path)
    return formal_path


def _blocking_signature(validation, targeted_validation=None, score=None):
    validation_errors = [item for item in validation.get('issues') or []
                         if item.get('severity') == 'error']
    coverage = next((item.get('detail') or {} for item in validation.get('checks') or []
                     if item.get('name') == 'coverage'), {})
    targeted_blockers = 0
    if targeted_validation:
        targeted_blockers = int((targeted_validation.get('detail') or {}).get(
            'blocking_issue_count', 0))
        if not (targeted_validation.get('detail') or {}).get('clears_scope', False):
            targeted_blockers = max(1, targeted_blockers)
    hard_gates = len(((score or {}).get('hard_gates') or {}).get('blocking_issues') or [])
    return _progress_signature(
        deterministic_errors=len(validation_errors),
        hard_gates=hard_gates,
        unmapped=coverage.get('unmapped', 0),
        duplicate=coverage.get('duplicate', 0),
        out_of_range=coverage.get('out_of_range', 0),
        targeted_blockers=targeted_blockers)


def _run_with_fresh_output(command, output_path):
    if os.path.exists(output_path):
        os.unlink(output_path)
    result = run(command)
    return result, os.path.exists(output_path)


def _append_revision_history(history_path, run_identity, analysis_config, validation,
                             signature, iteration_dir, targeted_report=None,
                             targeted_validation=None, final_critique=None, score=None,
                             force_no_progress=False):
    history = _load_history(history_path, run_identity)
    attempt = len(history['iterations']) + 1
    os.makedirs(iteration_dir, exist_ok=True)
    stem = f'iteration_{attempt}'
    config_snapshot = os.path.join(iteration_dir, stem + '_analysis_config.json')
    validation_snapshot = os.path.join(iteration_dir, stem + '_validation_report.json')
    shutil.copy2(analysis_config, config_snapshot)
    validation_path = validation.get('_path')
    if validation_path:
        shutil.copy2(validation_path, validation_snapshot)
    previous = history['iterations'][-1].get('progress_signature') \
        if history['iterations'] else None
    improved = (not force_no_progress
                and (previous is None or _made_semantic_progress(previous, signature)))
    entry = {
        'iteration': attempt,
        'semantic_revision': max(0, attempt - 1),
        'evaluated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'status': 'needs_revision',
        'validation_status': validation.get('status'),
        'progress_signature': signature,
        'blocking_issue_count': signature['hard_gates'] + signature['targeted_blockers'],
        'failed_dimension_count': signature['deterministic_errors'],
        'improved': improved,
        'config_snapshot': config_snapshot,
        'validation_snapshot': validation_snapshot if validation_path else None,
    }
    for key, path in (('targeted_critique_snapshot', targeted_report),
                      ('targeted_validation_snapshot', targeted_validation),
                      ('final_critique_snapshot', final_critique)):
        if path and os.path.exists(path):
            snapshot = os.path.join(iteration_dir, f'{stem}_{key}.json')
            shutil.copy2(path, snapshot)
            entry[key] = snapshot
    if score:
        entry.update({'score': score.get('score'), 'quality_rate': score.get('quality_rate'),
                      'final_score': score.get('final_score'),
                      'passed_at_cap': score.get('passed_at_cap')})
    history['iterations'].append(entry)
    history['best_iteration'] = attempt if improved else history.get('best_iteration')
    history['best_config_snapshot'] = (config_snapshot if improved
                                       else history.get('best_config_snapshot'))
    history['best_score'] = score.get('score') if score and improved else history.get('best_score')
    _write_json(history_path, history)
    no_progress = 0
    for item in reversed(history['iterations']):
        if item.get('improved'):
            break
        no_progress += 1
    return _semantic_revision_count(history), no_progress


def _prepare_revision_and_targeted(py, sp, out, analysis_config, manifest, source_index,
                                   raw, dataflow, issue_paths, revision, prepare_targeted,
                                   trusted_policy_paths=None):
    revision_context = out('revision_request.json')
    revision_manifest = out(os.path.join(
        'contexts', f'revision_{revision}', 'context_manifest.json'))
    command = [py, sp('prepare_revision_context.py'), '-c', analysis_config,
               '--source-index', source_index, '-r', raw,
               '--context-manifest', revision_manifest, '-o', revision_context]
    if dataflow and os.path.exists(dataflow):
        command += ['--dataflow', dataflow]
    for path in issue_paths:
        if path and os.path.exists(path):
            command += ['--issues', path]
    for path in trusted_policy_paths or []:
        if path and os.path.exists(path):
            command += ['--trusted-policy-issues', path]
    result = run(command)
    if result.returncode != 0:
        failure = None
        try:
            failure = _read_json(revision_context).get('status')
        except (OSError, ValueError):
            pass
        if failure == 'needs_controlled_diagnosis':
            blocked = _read_json(revision_context)
            routing_defects = [
                route.get('issue_id', 'UNNAMED_BLOCKER')
                for route in blocked.get('diagnostic_routes') or []
                if route.get('policy_status') == 'missing_from_deterministic_checker'
                and not route.get('allowed_targets')
            ]
            if routing_defects:
                blocked['status'] = 'blocked_tool_defect'
                blocked['diagnostic_reason'] = 'missing_checker_repair_policy'
                blocked['routing_defect_issue_ids'] = routing_defects
                _write_json(revision_context, blocked)
                return False, revision_context, None, 'blocked_tool_defect'
            diagnostic_request = out('diagnostic_request.json')
            diagnostic_manifest = out(os.path.join(
                'contexts', f'controlled_diagnosis_{revision}', 'context_manifest.json'))
            result = run([
                py, sp('prepare_diagnostic_context.py'), '-c', analysis_config,
                '-m', manifest, '--source-index', source_index, '-r', raw,
                '--revision-request', revision_context,
                '--context-manifest', diagnostic_manifest,
                '-o', diagnostic_request,
            ])
            if result.returncode == 0 and os.path.exists(diagnostic_request):
                return False, revision_context, None, 'awaiting_controlled_diagnosis'
            return False, revision_context, None, 'failed_diagnostic_request'
        return False, revision_context, None, failure
    targeted_request = None
    if prepare_targeted:
        targeted_request = out('targeted_critique_request.json')
        targeted_manifest = out(os.path.join(
            'contexts', f'targeted_critique_{revision}', 'context_manifest.json'))
        result = run([
            py, sp('prepare_targeted_critique.py'), '-c', analysis_config,
            '--source-index', source_index, '--revision-context', revision_context,
            '--context-manifest', targeted_manifest,
            '--targeted-output', out('targeted_critique_report.json'),
            '-o', targeted_request])
        if result.returncode != 0:
            failure = None
            try:
                failure = _read_json(targeted_request).get('status')
            except (OSError, ValueError):
                pass
            return False, revision_context, targeted_request, failure
    return True, revision_context, targeted_request, None


def _run_candidate_pipeline(*, args, status, py, analysis_config, raw, manifest,
                            dataflow, source_index, source_bundle_hash, out, sp):
    """Run deterministic gates, scoped revision critique, then one final full critique."""
    checkpoint_config = _checkpoint_config_from_manifest(manifest, args.model_dir)
    validation_path = out(FORMAL_OUTPUT_INTERFACES['deterministic_validation'])
    val_cmd = _validation_command(
        py, sp('run_validation.py'), analysis_config, raw, manifest,
        args.model_dir, SKILL_ROOT, validation_path, dataflow=dataflow,
        profile=args.profile)
    result, produced = _run_with_fresh_output(val_cmd, validation_path)
    if not produced:
        status['error'] = (result.stderr or result.stdout)[-500:]
        return _finish(status, 'failed_validation_runner')
    validation = _read_json(validation_path)
    validation['_path'] = validation_path
    status['stages']['deterministic_preterminal'] = validation.get('status')

    history_path = out('iteration_history.json')
    run_identity = {'model_dir': os.path.realpath(args.model_dir),
                    'csv': os.path.realpath(args.csv)}
    try:
        history = _load_history(history_path, run_identity)
    except ValueError as error:
        status['error'] = str(error)
        return _finish(status, 'failed_iteration_history')
    targeted_required = any(
        item.get('status') == 'needs_revision' or item.get('progress_signature')
        for item in history['iterations'])
    targeted_validation = None
    targeted_validation_path = out('targeted_critique_validation.json')

    if (targeted_required
            and not _candidate_changed_since_last_iteration(history, analysis_config)):
        signature = _blocking_signature(validation)
        revision, no_progress = _append_revision_history(
            history_path, run_identity, analysis_config, validation, signature,
            out('iterations'), force_no_progress=True)
        scope_path = out('revision_scope.json')
        prior_issues = ((_read_json(scope_path).get('issues') or [])
                        if os.path.exists(scope_path) else [])
        _write_revision_scope(
            scope_path, validation.get('issues') or [], prior_issues,
            prior_scope=True)
        final_stage = _revision_stop_stage(
            revision, args.max_iterations, args.stall_limit, no_progress)
        if final_stage in ('blocked_no_progress', 'blocked_max_revisions'):
            status['terminal_detail'] = _persist_terminal_status(
                history_path, run_identity, final_stage, signature)
        ok, request_path, _, failure = _prepare_revision_and_targeted(
            py, sp, out, analysis_config, manifest, source_index, raw, dataflow,
            [scope_path], revision + 1, False,
            trusted_policy_paths=(
                [scope_path] if _revision_scope_has_trusted_policies(scope_path) else []))
        if not ok:
            return _finish(status, failure or 'failed_revision_context')
        request = _read_json(request_path)
        request.update(_revision_metadata(
            final_stage, revision, args.max_iterations, args.stall_limit,
            no_progress, signature))
        request['targeted_critique_suppressed'] = {
            'reason': 'candidate_sha256_unchanged',
            'candidate_sha256': _sha256_file(analysis_config),
        }
        _write_json(request_path, request)
        return _finish(
            status, final_stage,
            note=('Candidate SHA256 is unchanged from the latest evaluated iteration; '
                  f'targeted critique was not started. See: {request_path}'))

    if targeted_required and not args.targeted_critique_report:
        scope_path = out('revision_scope.json')
        prior_issues = ((_read_json(scope_path).get('issues') or [])
                        if os.path.exists(scope_path) else [])
        _write_revision_scope(
            scope_path, validation.get('issues') or [], prior_issues,
            prior_scope=True)
        if _revision_scope_requires_targeted_review(scope_path):
            ok, _, targeted_request, failure = _prepare_revision_and_targeted(
                py, sp, out, analysis_config, manifest, source_index, raw, dataflow,
                [scope_path], len(history['iterations']) + 1, True,
                trusted_policy_paths=(
                    [scope_path] if _revision_scope_has_trusted_policies(scope_path) else []))
            if not ok:
                return _finish(status, failure or 'failed_targeted_critique_request')
            return _finish(
                status, 'awaiting_targeted_critique',
                note=('Targeted critique required for the current revision scope: '
                      f'{targeted_request}'))
        targeted_required = False

    if args.targeted_critique_report:
        targeted_request_path = out('targeted_critique_request.json')
        if not os.path.exists(targeted_request_path):
            scope_path = out('revision_scope.json')
            prior_issues = ((_read_json(scope_path).get('issues') or [])
                            if os.path.exists(scope_path) else [])
            _write_revision_scope(
                scope_path, validation.get('issues') or [], prior_issues,
                prior_scope=True)
            ok, _, targeted_request_path, failure = _prepare_revision_and_targeted(
                py, sp, out, analysis_config, manifest, source_index, raw, dataflow, [scope_path],
                len(history['iterations']) + 1, True,
                trusted_policy_paths=(
                    [scope_path] if _revision_scope_has_trusted_policies(scope_path) else []))
            if not ok:
                return _finish(status, failure or 'failed_targeted_critique_request')
            return _finish(status, 'awaiting_targeted_critique',
                           note=f'Targeted request was missing and was regenerated: '
                                f'{targeted_request_path}')
        command = [
            py, sp('validate_targeted_critique.py'), '-q', args.targeted_critique_report,
            '-c', analysis_config, '--source-index', source_index, '-r', raw,
            '--source-dir', args.model_dir,
            '--request', targeted_request_path,
            '--validation-report', validation_path,
            '-o', targeted_validation_path]
        targeted_result, produced = _run_with_fresh_output(
            command, targeted_validation_path)
        if not produced:
            return _finish(status, 'failed_targeted_critique_validation')
        targeted_validation = _read_json(targeted_validation_path)
        if targeted_result.returncode != 0 or targeted_validation.get('status') != 'passed':
            if not _targeted_requires_candidate_revision(targeted_validation):
                return _finish(
                    status, 'awaiting_targeted_critique',
                    note=('Targeted report is inadmissible; correct it against the current '
                          'request. No semantic revision was consumed.'))
        status['stages']['targeted_critique'] = (
            (targeted_validation.get('detail') or {}).get('clears_scope'))

    if not _preterminal_passed(validation, targeted_validation, targeted_required):
        signature = _blocking_signature(validation, targeted_validation)
        revision, no_progress = _append_revision_history(
            history_path, run_identity, analysis_config, validation, signature,
            out('iterations'), targeted_report=args.targeted_critique_report,
            targeted_validation=targeted_validation_path if targeted_validation else None)
        _write_revision_scope(
            out('revision_scope.json'), validation.get('issues') or [],
            (_read_json(args.targeted_critique_report).get('issues')
             if args.targeted_critique_report else []))
        final_stage = _revision_stop_stage(
            revision, args.max_iterations, args.stall_limit, no_progress)
        terminal_detail = None
        if final_stage in ('blocked_no_progress', 'blocked_max_revisions'):
            terminal_detail = _persist_terminal_status(
                history_path, run_identity, final_stage, signature)
            status['terminal_detail'] = terminal_detail
        ok, request_path, _, failure = _prepare_revision_and_targeted(
            py, sp, out, analysis_config, manifest, source_index, raw, dataflow,
            [validation_path, args.targeted_critique_report], revision + 1, False,
            trusted_policy_paths=[validation_path])
        if not ok:
            return _finish(status, failure or 'failed_revision_context')
        request = _read_json(request_path)
        request.update(_revision_metadata(
            final_stage, revision, args.max_iterations, args.stall_limit,
            no_progress, signature))
        _write_json(request_path, request)
        return _finish(status, final_stage, note=f'See isolated revision context: {request_path}')

    # Only a candidate that passed every pre-terminal deterministic and targeted gate reaches
    # the eleven-item review. A clean run reaches this point once; any later edit changes the
    # candidate digest and validate_critique forces a completely new final report.
    critique_request = out('critique_request.json')
    critique_output = out(FORMAL_OUTPUT_INTERFACES['final_critique'])
    final_context = out(os.path.join('contexts', 'final_critique', 'context_manifest.json'))
    prep_cmd = [
        py, sp('prepare_critique.py'), '-c', analysis_config, '-r', raw, '-m', manifest,
        '--source-index', source_index, '--raw-ops-compact', out('raw_ops.compact.json'),
        '--context-manifest', final_context, '--critique-output', critique_output,
        '-o', critique_request]
    if dataflow and os.path.exists(dataflow):
        prep_cmd += ['--dataflow', dataflow]
    if checkpoint_config:
        prep_cmd += ['--checkpoint-config', checkpoint_config]
    result = run(prep_cmd)
    if result.returncode != 0:
        return _finish(status, 'failed_critique_request')
    if not args.critique_report:
        return _finish(
            status, 'awaiting_final_critique',
            note=f'Use a clean context (fork_turns=none) for {critique_request}')

    critique_validation_path = out(FORMAL_OUTPUT_INTERFACES['final_critique_validation'])
    check_cmd = [
        py, sp('validate_critique.py'), '-q', args.critique_report,
        '-c', analysis_config, '-r', raw, '-m', manifest,
        '--source-dir', args.model_dir, '--source-dir', SKILL_ROOT,
        '--source-index', source_index,
        '--raw-ops-compact', out('raw_ops.compact.json'),
        '--source-snippets', out(os.path.join(
            'contexts', 'final_critique', 'source_snippets.json')),
        '--context-manifest', final_context,
        '-o', critique_validation_path]
    if dataflow and os.path.exists(dataflow):
        check_cmd += ['--dataflow', dataflow]
    if checkpoint_config:
        check_cmd += ['--checkpoint-config', checkpoint_config]
    critique_result, produced = _run_with_fresh_output(
        check_cmd, critique_validation_path)
    if not produced:
        return _finish(status, 'failed_critique_validation')
    critique_validation = _read_json(critique_validation_path)
    if critique_result.returncode != 0 or critique_validation.get('status') != 'passed':
        result = run(prep_cmd)
        if result.returncode != 0:
            return _finish(status, 'failed_critique_request')
        return _finish(status, 'awaiting_final_critique',
                       note='Final critique is stale or inadmissible and must be redone in full')

    score_path = out(FORMAL_OUTPUT_INTERFACES['score'])
    score_result, produced = _run_with_fresh_output([
        py, sp('score_breakdown.py'), '-v', validation_path, '-c', analysis_config,
        '-r', raw, '-m', manifest, '-q', args.critique_report,
        '--critique-validation', critique_validation_path, '-o', score_path], score_path)
    if not produced:
        return _finish(status, 'failed_scoring_runner')
    score = _read_json(score_path)
    status['stages']['final_critique'] = critique_validation.get('status')
    status['stages']['scoring'] = score.get('status')
    status['score'] = score.get('score')
    if not _score_is_publishable(score):
        signature = _blocking_signature(validation, score=score)
        revision, no_progress = _append_revision_history(
            history_path, run_identity, analysis_config, validation, signature,
            out('iterations'), final_critique=args.critique_report, score=score)
        critique_issues = _read_json(args.critique_report).get('issues') or []
        score_blockers = ((score.get('hard_gates') or {}).get('blocking_issues') or [])
        _write_revision_scope(
            out('revision_scope.json'), validation.get('issues') or [],
            critique_issues + score_blockers)
        final_stage = _revision_stop_stage(
            revision, args.max_iterations, args.stall_limit, no_progress)
        if final_stage in ('blocked_no_progress', 'blocked_max_revisions'):
            status['terminal_detail'] = _persist_terminal_status(
                history_path, run_identity, final_stage, signature)
        ok, request_path, _, failure = _prepare_revision_and_targeted(
            py, sp, out, analysis_config, manifest, source_index, raw, dataflow,
            [args.critique_report, validation_path, score_path], revision + 1, False,
            trusted_policy_paths=[validation_path])
        if not ok:
            return _finish(status, failure or 'failed_revision_context')
        request = _read_json(request_path)
        request.update(_revision_metadata(
            final_stage, revision, args.max_iterations, args.stall_limit,
            no_progress, signature))
        _write_json(request_path, request)
        return _finish(status, final_stage, note=f'See isolated revision context: {request_path}')

    analysis_config = _publish_formal_candidate(
        analysis_config, out(FORMAL_OUTPUT_INTERFACES['candidate']))
    _write_json(out('revision_request.json'), {
        'status': 'passed_at_cap',
        'current_revision': _semantic_revision_count(history),
        'next_revision': None, 'quality_rate': score.get('quality_rate'),
        'evidence_cap': score.get('evidence_cap'), 'final_score': score.get('final_score')})
    metrics = run([py, sp('compute_metrics.py'), '-r', out('raw_ops_details.json'),
                   '-c', analysis_config, '-o', out('metrics_report.md'), '-d', '5',
                   '--findings-out', out('metrics_findings.json')])
    if metrics.returncode != 0:
        status['error'] = (metrics.stderr or metrics.stdout)[-1000:]
        return _finish(status, 'failed_metrics_generation')
    status['stages']['metrics'] = 'ok'
    return _finish(status, 'passed_at_cap',
                   note='Stage 1 outputs are ready for cann-perf-breakdown-to-ui-json.')


def _build_handoff(status, stage):
    specs = {
        'awaiting_ai_mapping': (
            'mapping', 'ai_mapping_request.json', '--analysis-config',
            ['--diagnostic-patch', '--targeted-critique-report', '--critique-report']),
        'needs_revision': (
            'revision', 'revision_request.json', '--analysis-config',
            ['--diagnostic-patch', '--targeted-critique-report', '--critique-report']),
        'awaiting_controlled_diagnosis': (
            'diagnosis', 'diagnostic_request.json', '--diagnostic-patch',
            ['--targeted-critique-report', '--critique-report']),
        'awaiting_targeted_critique': (
            'targeted_critique', 'targeted_critique_request.json',
            '--targeted-critique-report', ['--diagnostic-patch', '--critique-report']),
        'awaiting_final_critique': (
            'final_critique', 'critique_request.json', '--critique-report',
            ['--diagnostic-patch']),
    }
    spec = specs.get(stage)
    out_dir = status.get('out_dir')
    if not spec or not out_dir:
        return None
    worker_kind, request_name, response_option, clear_options = spec
    request_path = os.path.join(out_dir, request_name)
    if not os.path.exists(request_path):
        return None
    try:
        request = _read_json(request_path)
    except (OSError, ValueError):
        return None
    output_expected = request.get('output_expected')
    if not output_expected:
        return None
    set_options = {response_option: output_expected}
    active_candidate = status.get('active_candidate')
    if active_candidate and response_option != '--analysis-config':
        set_options['--analysis-config'] = active_candidate
    source_bundle_hash = status.get('source_bundle_hash')
    if source_bundle_hash:
        set_options['--source-bundle-hash'] = source_bundle_hash
    return {
        'worker_kind': worker_kind,
        'request_path': os.path.realpath(request_path),
        'context_manifest': request.get('context_manifest'),
        'output_expected': os.path.realpath(output_expected),
        'response_option': response_option,
        'set_options': set_options,
        'clear_options': clear_options,
        'instructions': (
            'The worker reads the request envelope plus only the files in '
            'context_manifest.inputs. Apply set_options and clear_options before reentry.'),
    }


def _terminal_receipt(status, stage):
    if not (stage == 'passed_at_cap' or stage.startswith('blocked_')
            or stage.startswith('failed_')):
        return None
    out_dir = status.get('out_dir')
    artifacts = {}
    if out_dir:
        for name in set(FORMAL_OUTPUT_INTERFACES.values()) | {
                'iteration_history.json', 'revision_request.json'}:
            path = os.path.join(out_dir, name)
            if os.path.isfile(path):
                artifacts[name] = {
                    'path': os.path.realpath(path),
                    'sha256': _sha256_file(path),
                }
    return {
        'final': stage,
        'out_dir': out_dir,
        'decision_required': (
            stage in ('blocked_tool_defect', 'blocked_missing_external_evidence')
            or stage.startswith('failed_')),
        'artifacts': artifacts,
        'gate_status': dict(status.get('stages') or {}),
        'blocking_counts': ((status.get('terminal_detail') or {})
                            .get('blocking_counts') or {}),
    }


def _finish(status, stage, note=None):
    status['final'] = stage
    if note:
        status['note'] = note
    handoff = _build_handoff(status, stage)
    if handoff:
        status['handoff'] = handoff
    receipt = _terminal_receipt(status, stage)
    if receipt:
        status['terminal_receipt'] = receipt
    print(json.dumps(status, indent=2, ensure_ascii=False))
    # Awaiting states are intentional hand-offs to an LLM, not failures.
    ok = stage in ('completed', 'passed_at_cap', 'awaiting_ai_mapping',
                   'awaiting_final_critique', 'awaiting_targeted_critique',
                   'awaiting_controlled_diagnosis')
    sys.exit(0 if ok else 1)


def _load_history(path, run_identity):
    if not os.path.exists(path):
        return {'schema_version': 1, 'run_identity': run_identity,
                'iterations': [], 'best_iteration': None,
                'best_score': None, 'best_config_snapshot': None}
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if data.get('schema_version') != 1 or not isinstance(data.get('iterations'), list):
        raise ValueError(f'invalid iteration history: {path}')
    if data.get('run_identity') != run_identity:
        raise ValueError(
            f'{path} belongs to a different model/CSV input; use a different --out directory')
    return data


def _write_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


def _write_revision_scope(path, deterministic_issues, untrusted_issues, *,
                          prior_scope=False):
    """Persist current checker issues plus candidate-bound independent review issues."""
    trusted = [copy.deepcopy(issue) for issue in (deterministic_issues or [])]
    for issue in trusted:
        issue['_scope_origin'] = 'deterministic_validation'
    trusted_identities = {_revision_issue_identity(issue) for issue in trusted}
    seen = set(trusted_identities)
    merged = []
    for issue in untrusted_issues or []:
        if prior_scope and issue.get('_scope_origin') != 'independent_review':
            continue
        sanitized = copy.deepcopy(issue)
        sanitized.pop('repair_policy', None)
        sanitized['_scope_origin'] = 'independent_review'
        identity = _revision_issue_identity(sanitized)
        if identity in seen:
            continue
        merged.append(sanitized)
        seen.add(identity)
    merged.extend(trusted)
    _write_json(path, {
        'schema_version': 1,
        'repair_policy_source': REVISION_SCOPE_POLICY_SOURCE,
        'issues': merged,
    })


def _revision_issue_identity(issue):
    """Identify one scoped finding without conflating same-ID findings on other nodes."""
    return (
        issue.get('id'),
        issue.get('node_path'),
        issue.get('check_id') or issue.get('check'),
        issue.get('claim'),
    )


def _revision_scope_has_trusted_policies(path):
    try:
        return _read_json(path).get('repair_policy_source') == REVISION_SCOPE_POLICY_SOURCE
    except (OSError, ValueError):
        return False


def _revision_scope_requires_targeted_review(path):
    """Return whether the regenerated scope still contains a current blocker."""
    try:
        return bool(_read_json(path).get('issues') or [])
    except (OSError, ValueError):
        return True


def _materialize_effective_config(config_path, trace_scope_path, output_path):
    """Bind runtime ownership evidence into the exact config used by all formal gates."""
    with open(config_path, encoding='utf-8') as stream:
        config = json.load(stream)
    with open(trace_scope_path, encoding='utf-8') as stream:
        config['trace_scope'] = json.load(stream)
    _write_json(output_path, config)
    return output_path


def _history_quality(entry):
    """Rank candidates: fewest hard gates, then quality rate, then final score.

    Hard gates come first because they are categorical rather than graduated. A candidate that
    buried main compute in `excluded` is not a slightly-worse version of one that did not, and
    ranking on score first would let it become the base config for the next round -- carrying
    the defect forward under a better number. `quality_rate` outranks `final_score` for the
    matching reason: the rate measures the work, while the score also carries the evidence cap,
    which the decomposition did not control.
    """
    return (-entry.get('blocking_issue_count', 10 ** 9),
            entry.get('quality_rate', -1.0),
            entry.get('final_score', entry.get('score', -1)),
            -entry.get('failed_dimension_count', 10 ** 9))


def _score_is_publishable(score):
    """The formal critique path publishes only an explicit pass at the evidence cap."""
    return score.get('passed_at_cap') is True


def _checkpoint_config_from_manifest(manifest_path, model_dir):
    """Resolve the exact checkpoint config already selected by manifest extraction."""
    try:
        with open(manifest_path, encoding='utf-8') as stream:
            manifest = json.load(stream)
    except (OSError, ValueError):
        manifest = {}
    selected = manifest.get('weights_config')
    if selected is not None:
        if not isinstance(selected, str) or not selected:
            raise ValueError('manifest weights_config must be a non-empty path string')
        selected = os.path.realpath(selected)
        if not os.path.isfile(selected):
            raise ValueError(
                f'manifest-selected checkpoint config.json no longer exists: {selected}')
        expected_digest = manifest.get('weights_config_sha256')
        if not isinstance(expected_digest, str) or len(expected_digest) != 64:
            raise ValueError(
                'manifest-selected checkpoint config.json is missing '
                'weights_config_sha256')
        actual_digest = _sha256_file(selected)
        if actual_digest != expected_digest:
            raise ValueError(
                'checkpoint config.json SHA256 mismatch: '
                f'manifest={expected_digest}, current={actual_digest}, path={selected}')
        return selected
    local = os.path.join(model_dir, 'config.json')
    return os.path.realpath(local) if os.path.isfile(local) else None


if __name__ == '__main__':
    main()
