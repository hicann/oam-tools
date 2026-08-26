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
  --rank N                optional global rank id (never assumed to equal pipeline stage)
  --pipeline-stage N      optional explicit pipeline stage id
  --out DIR               output directory

Pipeline:
  Step 2  extract_model_manifest.py   -> {out}/model_manifest.json
  Step 3  validate_architecture.py    (manifest self-consistency; non-blocking here)
  Step 4  analyze_kernels.py          -> {out}/raw_ops.json (+ details + compact)
  Step 4b device_freq.py              -> {out}/device_freq.json (measured AI Core clock)
  Step 5  extract_dataflow.py         -> {out}/dataflow_source.json
  Step 6  (AI) — emits {out}/ai_mapping_request.json and STOPS at awaiting_ai_mapping,
          UNLESS --analysis-config is supplied (an AI/human-produced v2 config), in which
          case it requests a source/trace semantic review. Supply both the config and
          --semantic-review to proceed to:
  Step 8  semantic source/trace review -> {out}/semantic_review.json
  Step 9  run_validation.py            -> {out}/validation_report.json
  Step 10 score_breakdown.py           -> score + iteration request/history
  Step 11 compute_metrics.py -> metrics for the Stage 2 UI conversion skill

Prints a final JSON status object with the stage reached.
"""
import argparse
import datetime
import glob
import importlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
SKILL_ROOT = os.path.dirname(HERE)

bc = importlib.import_module('breakdown_common')


def run(cmd):
    bc.emit('  $', ' '.join(str(c) for c in cmd))
    return subprocess.run(cmd, capture_output=True, text=True)


def _parse_args():
    ap = argparse.ArgumentParser(description='Generic Mode A forward-eval driver')
    ap.add_argument('--model-dir', required=True)
    ap.add_argument('--csv', required=True)
    ap.add_argument('--trace', help='trace_view.json, for the declared AI Core Freq counter')
    ap.add_argument('--runtime-config', help='runtime YAML for trace scope')
    ap.add_argument('--rank', type=int)
    ap.add_argument('--pipeline-stage', type=int,
                    help='explicit pipeline stage id; global --rank is not a stage id')
    ap.add_argument('--analysis-config',
                    help='AI/human-produced schema-v2 analysis_config.json (enables Steps 8-11)')
    ap.add_argument('--semantic-review',
                    help='AI-produced semantic_review.json bound to config/raw_ops/manifest')
    ap.add_argument('--out', required=True)
    ap.add_argument('--allow-warnings', action='store_true')
    ap.add_argument('--max-iterations', type=int, default=10,
                    help='maximum evaluated mapping candidates before stopping (default: 10)')
    ap.add_argument('--stall-limit', type=int, default=0,
                    help='stop early after N consecutive non-improving rounds; '
                         '0 (default) disables early stop so the loop runs to --max-iterations')
    ap.add_argument('--allow-step-variation', action='store_true',
                    help='select the representative step from the largest stable signature group')
    args = ap.parse_args()

    if args.max_iterations < 1:
        ap.error('--max-iterations must be >= 1')
    return args


def _run_manifest_stage(args, status, paths, sp, out):
    paths['manifest'] = out('model_manifest.json')
    process = run([sys.executable, sp('extract_model_manifest.py'),
                   '--model-dir', args.model_dir, '--base-dir', SKILL_ROOT,
                   '-o', paths['manifest']])
    status['stages']['manifest'] = 'ok' if process.returncode == 0 else 'error'
    if process.returncode != 0:
        status['error'] = process.stderr[-500:]
        return _finish(status, 'failed_manifest')
    return None


def _run_raw_ops_stage(args, status, paths, sp, out):
    paths['raw'] = out('raw_ops.json')
    command = [sys.executable, sp('analyze_kernels.py'), '-f', args.csv,
               '-o', paths['raw'], '-d', out('raw_ops_details.json'),
               '--compact-out', out('raw_ops.compact.json'), '-m', out('steps_summary.md')]
    if args.allow_step_variation:
        command.append('--allow-step-variation')
    process = run(command)
    status['stages']['raw_ops'] = 'ok' if process.returncode == 0 else 'error'
    if process.returncode != 0:
        status['error'] = process.stderr[-500:]
        return _finish(status, 'failed_raw_ops')
    return None


def _run_device_freq_stage(args, status, paths, sp, out):
    command = [sys.executable, sp('device_freq.py'), '-d', out('raw_ops_details.json'),
               '-o', out('device_freq.json')]
    if args.trace:
        command += ['--trace', args.trace]
    process = run(command)
    status['stages']['device_freq'] = (
        (process.stdout.strip().splitlines()[-1] if process.stdout else 'ok')
        if process.returncode == 0
        else f'unavailable: {(process.stderr or process.stdout)[-200:]}')


def _run_dataflow_stage(args, status, paths, sp, out):
    paths['dataflow'] = out('dataflow_source.json')
    sources = sorted(glob.glob(os.path.join(args.model_dir, '**', 'modeling_*.py'),
                               recursive=True))
    if not sources:
        paths['dataflow'] = None
        status['stages']['dataflow'] = 'skipped_no_modeling_source'
        return None
    command = [sys.executable, sp('extract_dataflow.py')]
    for source in sources:
        command.extend(['-s', source])
    command.extend(['-o', paths['dataflow']])
    process = run(command)
    status['stages']['dataflow'] = 'ok' if process.returncode == 0 else 'error'
    if process.returncode != 0:
        status['error'] = (process.stderr or process.stdout)[-500:]
        return _finish(status, 'failed_dataflow')
    return None


def _run_trace_scope_stage(args, status, paths, sp, out):
    paths['trace_scope'] = None
    if not (args.runtime_config or args.rank is not None or args.pipeline_stage is not None):
        return None
    paths['trace_scope'] = out('trace_scope.json')
    command = [sys.executable, sp('detect_trace_scope.py'), '-m', paths['manifest'],
               '-o', paths['trace_scope']]
    if args.runtime_config:
        command.extend(['--yaml', args.runtime_config])
    if args.rank is not None:
        command.extend(['--rank', str(args.rank)])
    if args.pipeline_stage is not None:
        command.extend(['--pipeline-stage', str(args.pipeline_stage)])
    if args.analysis_config:
        command.extend(['-c', args.analysis_config])
    process = run(command)
    status['stages']['trace_scope'] = 'ok' if process.returncode == 0 else 'error'
    if process.returncode != 0:
        status['error'] = (process.stderr or process.stdout)[-500:]
        return _finish(status, 'failed_trace_scope')
    if paths['analysis_config']:
        paths['analysis_config'] = _materialize_effective_config(
            paths['analysis_config'], paths['trace_scope'],
            out('analysis_config.effective.json'))
        status['stages']['trace_scope_config'] = paths['analysis_config']
    return None


def _mapping_gate(args, status, paths, out):
    if paths['analysis_config']:
        return None
    request = out('ai_mapping_request.json')
    payload = {
        'task': 'map every op of the representative step to model/runtime/excluded',
        'protocol': 'references/ai_mapping_protocol.md',
        'scoring_protocol': 'references/breakdown_scoring.md',
        'inputs': {
            'model_manifest': paths['manifest'],
            'raw_ops': paths['raw'],
            'raw_ops_compact': out('raw_ops.compact.json'),
            'dataflow_source': paths['dataflow'],
            'trace_scope': paths['trace_scope'],
            'model_source_dir': args.model_dir,
        },
        'output_expected': out('analysis_config_v2.json'),
        'rules': [
            'every op -> model / runtime_auxiliary / (strictly-allowed) excluded',
            'unmapped_ops must be empty for a passed result',
            'MTP = 1 learned layer + N invocations; never N layers',
            'no pipeline-rank claim without evidence',
        ],
    }
    with open(request, 'w', encoding='utf-8') as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False)
    return _finish(status, 'awaiting_ai_mapping',
                   note=f'AI mapping required. Request written to {request}. '
                        f'Produce analysis_config_v2.json per the protocol, then re-run '
                        f'with --analysis-config.')


def _review_request_command(args, paths, sp, out):
    command = [sys.executable, sp('prepare_semantic_review.py'),
               '-c', paths['analysis_config'], '-r', paths['raw'], '-m', paths['manifest'],
               '--source-dir', args.model_dir, '--review-output', out('semantic_review.json'),
               '-o', out('semantic_review_request.json')]
    if paths['dataflow'] and os.path.exists(paths['dataflow']):
        command += ['--dataflow', paths['dataflow']]
    return command


def _request_review(args, status, paths, sp, out):
    process = run(_review_request_command(args, paths, sp, out))
    refresh_reasons = paths.pop('review_refresh_reasons', None)
    refresh = refresh_reasons is not None
    if refresh:
        status['stages']['semantic_review'] = 'refresh_required'
    else:
        status['stages']['semantic_review'] = 'required' if process.returncode == 0 else 'error'
    if process.returncode != 0:
        status['error'] = (process.stderr or process.stdout)[-500:]
        return _finish(status, 'failed_semantic_review_request')
    request = out('semantic_review_request.json')
    if refresh:
        note = (f'Existing semantic review must be refreshed ({", ".join(refresh_reasons)}). '
                f'A request bound to the current artifacts was written to {request}.')
    else:
        note = (f'Source/trace semantic review required. Request written to {request}. '
                f'Produce {out("semantic_review.json")}, then re-run with --semantic-review.')
    return _finish(status, 'awaiting_semantic_review', note=note)


def _review_validation_command(args, paths, sp, out):
    command = [sys.executable, sp('validate_semantic_review.py'),
               '--semantic-review', args.semantic_review, '-c', paths['analysis_config'],
               '-r', paths['raw'], '-m', paths['manifest'], '--source-dir', args.model_dir,
               '--source-dir', SKILL_ROOT, '-o', out('semantic_review_validation.json')]
    if paths['dataflow'] and os.path.exists(paths['dataflow']):
        command += ['--dataflow', paths['dataflow']]
    return command


def _review_refresh_reasons(report):
    refresh_ids = {
        'SR_INPUT', 'SR_SCHEMA', 'SR_DIGEST_MISMATCH', 'SR_CHECK_MISSING',
        'SR_CHECK_DUPLICATE', 'SR_CHECK_UNKNOWN', 'SR_EVIDENCE_EXPLANATION',
        'SR_EVIDENCE_LOCATOR', 'SR_EVIDENCE_MISSING', 'SR_SOURCE_REF',
        'SR_CONFIG_PATH', 'SR_OP_INDEX', 'SR_FINDING_CHECK', 'SR_DATAFLOW_UNBOUND',
    }
    return sorted({issue.get('id') for issue in report.get('issues', [])
                   if issue.get('id') in refresh_ids})


def _semantic_review_gate(args, status, paths, sp, out):
    if not args.semantic_review:
        return _request_review(args, status, paths, sp, out)
    validation_path = out('semantic_review_validation.json')
    run(_review_validation_command(args, paths, sp, out))
    try:
        with open(validation_path, encoding='utf-8') as stream:
            report = json.load(stream)
    except (OSError, ValueError) as error:
        status['error'] = f'cannot read semantic review validation: {error}'
        return _finish(status, 'failed_semantic_review_validation')
    reasons = _review_refresh_reasons(report)
    if reasons:
        paths['review_refresh_reasons'] = reasons
        return _request_review(args, status, paths, sp, out)
    return None


def _prepare_iteration_stage(args, status, paths, sp, out):
    del sp
    paths['history_path'] = out('iteration_history.json')
    identity = {'model_dir': os.path.realpath(args.model_dir),
                'csv': os.path.realpath(args.csv)}
    try:
        paths['history'] = _load_history(paths['history_path'], identity)
    except ValueError as error:
        status['error'] = str(error)
        return _finish(status, 'failed_iteration_history')
    paths['iteration'] = len(paths['history']['iterations']) + 1
    paths['iteration_dir'] = out('iterations')
    os.makedirs(paths['iteration_dir'], exist_ok=True)
    paths['stem'] = f'iteration_{paths["iteration"]}'
    paths['config_snapshot'] = os.path.join(
        paths['iteration_dir'], paths['stem'] + '_analysis_config.json')
    shutil.copy2(paths['analysis_config'], paths['config_snapshot'])
    paths['review_snapshot'] = os.path.join(
        paths['iteration_dir'], paths['stem'] + '_semantic_review.json')
    shutil.copy2(args.semantic_review, paths['review_snapshot'])
    return None


def _validation_command(args, paths, sp, out):
    command = [sys.executable, sp('run_validation.py'), '-c', paths['analysis_config'],
               '-r', paths['raw'], '-m', paths['manifest'], '--source-dir', args.model_dir,
               '--source-dir', SKILL_ROOT, '--semantic-review', args.semantic_review,
               '-o', out('validation_report.json')]
    if paths['dataflow'] and os.path.exists(paths['dataflow']):
        command += ['--dataflow', paths['dataflow']]
    return command


def _run_validation_stage(args, status, paths, sp, out):
    paths['validation_path'] = out('validation_report.json')
    process = run(_validation_command(args, paths, sp, out))
    if args.allow_warnings:
        status['stages']['validation_override'] = (
            '--allow-warnings 不再传递给正式校验：正式通过必须精确为 passed')
    if not os.path.exists(paths['validation_path']):
        status['stages']['validation'] = 'error'
        status['error'] = (process.stderr or process.stdout)[-500:]
        return _finish(status, 'failed_validation_runner')
    with open(paths['validation_path']) as stream:
        paths['validation_report'] = json.load(stream)
    status['stages']['validation'] = paths['validation_report']['status']
    paths['validation_snapshot'] = os.path.join(
        paths['iteration_dir'], paths['stem'] + '_validation_report.json')
    shutil.copy2(paths['validation_path'], paths['validation_snapshot'])
    return None


def _run_scoring_stage(args, status, paths, sp, out):
    paths['score_path'] = out('breakdown_score.json')
    command = [sys.executable, sp('score_breakdown.py'), '-v', paths['validation_path'],
               '-c', paths['analysis_config'], '-r', paths['raw'], '-m', paths['manifest'],
               '--semantic-review', args.semantic_review, '-o', paths['score_path']]
    run(command)
    if not os.path.exists(paths['score_path']):
        status['stages']['scoring'] = 'error'
        return _finish(status, 'failed_scoring_runner')
    with open(paths['score_path'], encoding='utf-8') as stream:
        paths['score'] = json.load(stream)
    status['stages']['scoring'] = paths['score']['status']
    status['score'] = paths['score']['score']
    paths['score_snapshot'] = os.path.join(
        paths['iteration_dir'], paths['stem'] + '_breakdown_score.json')
    shutil.copy2(paths['score_path'], paths['score_snapshot'])
    return None


def _record_iteration(paths):
    score = paths['score']
    history = paths['history']
    candidate_quality = (score['score'], -len(score['hard_gates']['blocking_issues']),
                         -len(score['failed_dimensions']))
    previous_quality = max((_history_quality(item) for item in history['iterations']),
                           default=(-1, float('-inf'), float('-inf')))
    entry = {
        'iteration': paths['iteration'],
        'evaluated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'score': score['score'],
        'minimum_score': score['minimum_score'],
        'score_status': score['status'],
        'validation_status': paths['validation_report']['status'],
        'blocking_issue_count': len(score['hard_gates']['blocking_issues']),
        'failed_dimension_count': len(score['failed_dimensions']),
        'improved': candidate_quality > previous_quality,
        'config_snapshot': paths['config_snapshot'],
        'semantic_review_snapshot': paths['review_snapshot'],
        'validation_snapshot': paths['validation_snapshot'],
        'score_snapshot': paths['score_snapshot'],
    }
    history['iterations'].append(entry)
    best = max(history['iterations'], key=_history_quality)
    history['best_iteration'] = best['iteration']
    history['best_score'] = best['score']
    history['best_config_snapshot'] = best['config_snapshot']
    _write_json(paths['history_path'], history)


def _non_improving_rounds(history):
    count = 0
    for item in reversed(history['iterations']):
        if item['improved']:
            break
        count += 1
    return count


def _iteration_final_stage(args, iteration, no_progress):
    if iteration >= args.max_iterations:
        return 'blocked_max_iterations'
    if args.stall_limit > 0 and no_progress >= args.stall_limit:
        return 'blocked_no_progress'
    return 'needs_iteration'


def _iteration_request(args, paths, final_stage, no_progress, out):
    revision_seed = None
    iteration = paths['iteration']
    history = paths['history']
    score = paths['score']
    if final_stage == 'needs_iteration':
        revision_seed = out(f'analysis_config_iteration_{iteration + 1}.json')
        shutil.copy2(history['best_config_snapshot'], revision_seed)
    return {
        'status': final_stage,
        'current_iteration': iteration,
        'next_iteration': iteration + 1 if final_stage == 'needs_iteration' else None,
        'max_iterations': args.max_iterations,
        'remaining_iterations': max(0, args.max_iterations - iteration),
        'consecutive_non_improving_rounds': no_progress,
        'stall_limit': args.stall_limit,
        'current_score': score['score'],
        'minimum_score': score['minimum_score'],
        'best_iteration': history['best_iteration'],
        'best_score': history['best_score'],
        'base_config_for_revision': revision_seed,
        'immutable_best_snapshot': history['best_config_snapshot'],
        'failed_dimensions': score['failed_dimensions'],
        'blocking_issues': score['hard_gates']['blocking_issues'],
        'validation_issues': paths['validation_report'].get('issues', []),
        'required_actions': score['required_actions'],
        'constraints': score['constraints'],
        'semantic_review_request': out('semantic_review_request.json'),
        'instructions': (
            'Edit base_config_for_revision (never edit immutable_best_snapshot). Fix only '
            'evidence-backed failed items. Then run prepare_semantic_review.py for the '
            'revised config, complete a new source/trace review, and rerun run_breakdown.py '
            'with the revised --analysis-config, new --semantic-review, and the same --out.'),
    }


def _score_gate(args, status, paths, out):
    score = paths['score']
    if _score_is_convertible(score):
        _write_json(out('iteration_request.json'), {
            'status': 'passed', 'current_iteration': paths['iteration'],
            'next_iteration': None, 'current_score': score['score'],
            'minimum_score': score['minimum_score'],
            'message': '评分已达标，不需要下一轮修正。'})
        return None
    no_progress = _non_improving_rounds(paths['history'])
    final_stage = _iteration_final_stage(args, paths['iteration'], no_progress)
    _write_json(out('iteration_request.json'),
                _iteration_request(args, paths, final_stage, no_progress, out))
    return _finish(status, final_stage,
                   note=f'UI conversion skipped: score {score["score"]} '
                        f'is not eligible; see {out("iteration_request.json")}')


def _run_metrics_stage(args, status, paths, sp, out):
    del args
    process = run([sys.executable, sp('compute_metrics.py'),
                   '-r', out('raw_ops_details.json'), '-c', paths['analysis_config'],
                   '-o', out('metrics_report.md'), '-d', '5',
                   '--findings-out', out('metrics_findings.json')])
    if process.returncode != 0:
        status['stages']['metrics'] = 'error'
        status['error'] = (process.stderr or process.stdout)[-1000:]
        return _finish(status, 'failed_metrics_generation')
    status['stages']['metrics'] = 'ok'
    return _finish(status, 'completed',
                   note='Stage 1 outputs are ready for cann-perf-breakdown-to-ui-json.')


def _run_stages(stages, args, status, paths, helpers):
    sp, out = helpers
    for stage in stages:
        result = stage(args, status, paths, sp, out)
        if result is not None:
            return result
    return None


def main():
    args = _parse_args()

    os.makedirs(args.out, exist_ok=True)

    def sp(name):
        return os.path.join(HERE, name)

    def out(name):
        return os.path.join(args.out, name)

    status = {'stages': {}}
    paths = {'analysis_config': args.analysis_config}
    helpers = (sp, out)
    result = _run_stages(
        (_run_manifest_stage, _run_raw_ops_stage), args, status, paths, helpers)
    if result is not None:
        return result
    _run_device_freq_stage(args, status, paths, sp, out)
    result = _run_stages(
        (_run_dataflow_stage, _run_trace_scope_stage), args, status, paths, helpers)
    if result is not None:
        return result
    result = _mapping_gate(args, status, paths, out)
    if result is not None:
        return result
    result = _semantic_review_gate(args, status, paths, sp, out)
    if result is not None:
        return result
    result = _run_stages(
        (_prepare_iteration_stage, _run_validation_stage, _run_scoring_stage),
        args, status, paths, helpers)
    if result is not None:
        return result
    _record_iteration(paths)
    result = _score_gate(args, status, paths, out)
    return result if result is not None else _run_metrics_stage(args, status, paths, sp, out)


def _finish(status, stage, note=None):
    status['final'] = stage
    if note:
        status['note'] = note
    bc.emit(json.dumps(status, indent=2, ensure_ascii=False))
    # awaiting_ai_mapping is an intentional pause, not a failure -> exit 0
    ok = stage in ('completed', 'awaiting_ai_mapping', 'awaiting_semantic_review')
    return 0 if ok else 1


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
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


def _materialize_effective_config(config_path, trace_scope_path, output_path):
    """Bind runtime ownership evidence into the exact config used by all formal gates."""
    with open(config_path, encoding='utf-8') as stream:
        config = json.load(stream)
    with open(trace_scope_path, encoding='utf-8') as stream:
        config['trace_scope'] = json.load(stream)
    _write_json(output_path, config)
    return output_path


def _history_quality(entry):
    """Prefer a higher score; for ties prefer fewer blockers and failed dimensions."""
    return (entry.get('score', -1), -entry.get('blocking_issue_count', 10 ** 9),
            -entry.get('failed_dimension_count', 10 ** 9))


def _score_is_convertible(score):
    """Use the tiered conclusion gate while retaining pre-tier score compatibility."""
    if 'convertible' in score:
        return score['convertible'] is True
    return score.get('status') == 'passed'


if __name__ == '__main__':
    sys.exit(main())
