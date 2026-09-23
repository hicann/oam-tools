#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
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
# ----------------------------------------------------------------------------
"""Seven-stage CANN pipeline. Markdown is the shared skill/retry/resume artifact."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from artifact_contract import (STAGE_FILES, OWNERS, new_artifact, read_artifact,
                               write_artifact, atomic_write, now_iso)

SCRIPT_DIR = Path(__file__).resolve().parent
SKILLS_ROOT = SCRIPT_DIR.parent.parent
STAGE_IDS = tuple(STAGE_FILES)
STATE_VERSION = 2
TERMINAL_OK = ('success', 'skipped')
MANUAL = ('diagnose', 'report')
CHECK_KEYS = ('has_first_error_line', 'has_env_version', 'has_full_timeline', 'has_crash_artifacts',
              'has_repro_input', 'multi_source_agree', 'timeline_consistent', 'no_contradiction',
              'root_cause_localized', 'chain_no_gap', 'alternatives_excluded', 'reproducible',
              'fix_verified', 'regression_checked', 'errcode_documented', 'case_matched',
              'source_code_confirmed')
BUSINESS_FIELDS = {
    'case_lookup': ('status', 'library_path', 'library_sha256', 'query_features', 'matches', 'errors', 'limitations'),
    'detect': ('primary', 'secondary', 'recognition_confidence', 'scenarios', 'materials', 'errors', 'route'),
    'diagnose': ('first_error', 'timeline', 'causal_chain', 'root_cause', 'alternatives',
                 'recommendations', 'checks', 'references'),
    'report': ('conclusion', 'confidence', 'findings', 'recommendations', 'limitations'),
    'confidence': ('final_score', 'level', 'dimensions', 'unmet_critical', 'missing_items',
                   'case_gate', 'case_gate_reason'),
    'promote': ('enabled', 'decision', 'case_gate', 'target', 'case_id', 'mutation_id', 'reason'),
}
SCRIPTS = {'case_lookup': 'orchestrator-skill/scripts/detect_scenario.py',
           'detect': 'orchestrator-skill/scripts/detect_scenario.py',
           'clean': 'eval-skill/scripts/clean.py',
           'confidence': 'eval-skill/scripts/assess_confidence.py',
           'promote': 'eval-skill/scripts/promote_case.py'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def file_hash(path):
    if not path.is_file():
        return None
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def within(path, parent):
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def classify_error(exc=None, returncode=None, stderr=''):
    text = (str(exc or '') + '\n' + stderr).lower()
    if isinstance(exc, MemoryError) or any(x in text for x in
        ('no space left', 'disk full', 'cannot allocate memory', 'out of memory', 'quota exceeded')):
        return 'resource'
    if isinstance(exc, (ValueError, TypeError, KeyError, PermissionError, FileNotFoundError)):
        return 'permanent'
    if any(x in text for x in ('usage:', 'unrecognized arguments', 'not found', 'permission denied')):
        return 'permanent'
    if isinstance(exc, subprocess.TimeoutExpired) or any(x in text for x in
        ('timed out', 'temporarily unavailable', 'connection reset', 'resource busy', 'eagain', 'eintr')):
        return 'transient'
    if isinstance(exc, OSError) and exc.errno in (4, 11, 16):
        return 'transient'
    return 'permanent' if returncode == 2 else 'unknown'


class StepError(Exception):
    def __init__(self, message, category='permanent', code=None):
        super().__init__(message)
        self.category, self.code = category, code


class Blocked(Exception):
    pass


class Plan:
    def __init__(self, path, state_dir):
        self.path, self.state_dir = path.resolve(), state_dir.resolve()
        self.raw = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(self.raw, dict):
            raise ValueError('plan must be an object')
        self.input = self.raw.get('input', {})
        if not isinstance(self.input, dict) or not self.input.get('path'):
            raise ValueError('plan.input.path is required')
        self.source = Path(self.input['path'])
        if not self.source.is_absolute():
            self.source = self.path.parent / self.source
        self.source = self.source.resolve()
        if not self.source.exists():
            raise FileNotFoundError(str(self.source))
        if within(self.source, state_dir):
            raise ValueError('Input must not be inside the pipeline state directory')
        if self.source.is_dir() and (within(self.state_dir, self.source) or within(self.path, self.source)):
            raise ValueError('Plan and pipeline state must be outside the original input directory')
        requested = self.raw.get('pipeline') or self.raw.get('route', {}).get('pipeline_stages')
        if requested and tuple(requested) != STAGE_IDS:
            raise ValueError('plan must use the fixed seven-stage order')
        self.stages = self.raw.get('stages', self.raw.get('stage_params', self.raw.get('parameters', {})))
        lookup = self.raw.get('case_lookup', {})
        self.library = Path(lookup.get('library_path') or SKILLS_ROOT / 'eval-skill/references/cases.md')
        if not self.library.is_absolute():
            self.library = self.path.parent / self.library
        self.library = self.library.resolve()

    def params(self, sid):
        data = self.stages.get(sid, {})
        if not isinstance(data, dict):
            raise ValueError('stage parameters must be objects')
        return dict(data)

    def artifact(self, sid):
        return self.state_dir / 'artifacts' / STAGE_FILES[sid]

    def materials(self):
        paths = [self.source] if self.source.is_file() else sorted(self.source.rglob('*'))
        return [{'path': str(p.resolve()), 'sha256': file_hash(p)} for p in paths
                if p.is_file() and not within(p, self.state_dir) and p.resolve() != self.path]


def blank_stage():
    return {'status': 'pending', 'attempts': 0, 'failures': 0, 'revision': uuid.uuid4().hex,
            'inputs_fingerprint': None, 'artifact_sha256': None, 'last_error': None}


def load_state(path):
    if not path.exists():
        return {'version': STATE_VERSION, 'run_id': uuid.uuid4().hex, 'created_at': now_iso(),
                'stages': {sid: blank_stage() for sid in STAGE_IDS}}
    state = json.loads(path.read_text(encoding='utf-8-sig'))
    if state.get('version') != STATE_VERSION or tuple(state.get('stages', {})) != STAGE_IDS:
        raise ValueError('State schema changed; select a new --state-dir and retain old state for audit')
    return state


def save_state(plan, state):
    state['updated_at'] = now_iso()
    atomic_write(plan.state_dir / 'state.json', json.dumps(state, ensure_ascii=False, indent=2))


def acquire_lock(directory, force=False):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'pipeline.lock'
    payload = {'pid': os.getpid(), 'token': uuid.uuid4().hex,
               'host': os.environ.get('COMPUTERNAME', os.environ.get('HOSTNAME', '')), 'at': now_iso()}
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        old = json.loads(path.read_text(encoding='utf-8'))
        if not force or old.get('host') != payload['host']:
            raise StepError('State lock exists; use --force-unlock only after the process exits', 'conflict')
        pid = int(old.get('pid', 0))
        if pid <= 0:
            raise StepError('Invalid lock owner; review lock before removal', 'conflict')
        if os.name == 'nt':
            result = subprocess.run(['tasklist', '/FI', 'PID eq %s' % pid, '/NH'],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            if str(pid) in result.stdout.decode('utf-8', 'replace') or result.returncode:
                raise StepError('Lock owner is still running or could not be checked', 'conflict')
        else:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                pass
            else:
                raise StepError('Lock owner is still running', 'conflict')
        path.unlink()
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(payload, stream)
        stream.flush()
        os.fsync(stream.fileno())
    return path, payload['token']


def release_lock(lock):
    if lock:
        path, token = lock
        try:
            if json.loads(path.read_text(encoding='utf-8')).get('token') == token:
                path.unlink()
        except (OSError, ValueError):
            pass


def inputs_for(sid, plan, state):
    index = STAGE_IDS.index(sid)
    upstream = [{'stage': other, 'path': str(plan.artifact(other)),
                 'sha256': file_hash(plan.artifact(other))} for other in STAGE_IDS[:index]]
    scripts = [SCRIPT_DIR / 'run_pipeline.py', SCRIPT_DIR / 'artifact_contract.py']
    if sid in SCRIPTS:
        scripts.append(SKILLS_ROOT / SCRIPTS[sid])
    materials = plan.materials()
    parameters = plan.params(sid)
    dependencies = {'input': plan.input, 'revision': state['stages'][sid]['revision'],
                    'scripts': {str(p): file_hash(p) for p in scripts}}
    if sid in ('case_lookup', 'detect'):
        dependencies['case_library'] = {'path': str(plan.library), 'sha256': lookup_library_hash(plan, state)}
    value = {'materials': materials, 'upstream': upstream, 'parameters': parameters,
             'dependencies': dependencies}
    value['fingerprint'] = digest(value)
    return value


def lookup_library_hash(plan, state):
    """A verified publication by this run does not invalidate its own earlier lookup."""
    actual = file_hash(plan.library)
    try:
        lookup, _ = read_artifact(plan.artifact('case_lookup'), 'case_lookup', state['run_id'])
        if lookup['inputs']['dependencies']['revision'] != state['stages']['case_lookup']['revision']:
            return actual
        baseline = lookup['inputs']['dependencies']['case_library']['sha256']
    except (OSError, ValueError, KeyError, TypeError):
        return actual
    receipts = []
    for path in (plan.state_dir / 'mutations').glob('*.json'):
        try:
            receipt = json.loads(path.read_text(encoding='utf-8'))
            if receipt.get('run_id') == state['run_id'] and receipt.get('target') == str(plan.library):
                receipts.append(receipt)
        except (OSError, ValueError):
            continue
    current, seen = actual, set()
    while current != baseline and current not in seen:
        seen.add(current)
        match = next((item for item in receipts if item.get('after_sha256') == current), None)
        if match is None:
            return actual
        current = match['before_sha256']
    return baseline if current == baseline else actual


def read_current(sid, plan, state, inputs):
    return read_artifact(plan.artifact(sid), sid, state['run_id'], inputs['fingerprint'])


def validate_business(sid, data):
    if data['status'] not in TERMINAL_OK:
        raise ValueError('Artifact is not complete')
    if sid not in ('clean', 'promote') and data['status'] == 'skipped':
        raise ValueError('This stage cannot be skipped')
    result = data['result']
    required = BUSINESS_FIELDS.get(sid, ())
    if any(key not in result for key in required):
        raise ValueError('Missing business fields: ' + ', '.join(required))
    if not any(o['kind'] == 'primary_markdown' for o in data['outputs']):
        raise ValueError('A primary Markdown output must be declared')
    if sid == 'case_lookup' and (result['status'] not in ('hit', 'miss', 'unavailable') or
                                 not isinstance(result['matches'], list) or
                                 not isinstance(result['errors'], list)):
        raise ValueError('Invalid case lookup status or candidates')
    if sid == 'detect' and (not isinstance(result['secondary'], list) or
                            not isinstance(result['errors'], list) or
                            tuple(result['route'].get('pipeline_stages', [])) != STAGE_IDS):
        raise ValueError('Classification must retain candidate list and the complete pipeline')
    if sid == 'diagnose':
        if not isinstance(result['checks'], dict) or set(result['checks']) != set(CHECK_KEYS):
            raise ValueError('Diagnosis needs an explicitly reviewed confidence checklist')
        if any(not isinstance(v, dict) or not isinstance(v.get('value'), bool) or
               'evidence' not in v or (v['value'] and not v['evidence']) for v in result['checks'].values()):
            raise ValueError('Every confidence check needs a Boolean and evidence; true checks cannot be unsupported')
        cause = result['root_cause']
        if not isinstance(cause, dict) or not cause.get('description') or cause.get('status') not in ('confirmed', 'hypothesis', 'undetermined'):
            raise ValueError('Root cause needs a description and confirmed/hypothesis/undetermined status')
        if any(not isinstance(result[key], list) for key in ('timeline', 'causal_chain', 'alternatives', 'recommendations', 'references')):
            raise ValueError('Diagnosis evidence, timeline and alternatives must be arrays')
        if not result['references'] or (not result['timeline'] and not data['evidence_gaps']):
            raise ValueError('Reference supplied materials and explain any unavailable timeline')
    if sid == 'report' and (not result['conclusion'] or not result['findings']):
        raise ValueError('Report conclusion and findings must be filled')
    if sid == 'report':
        upstream = next((entry for entry in data['inputs']['upstream'] if entry['stage'] == 'confidence'), None)
        if not upstream or read_artifact(upstream['path'], 'confidence', data['run_id'])[0]['result'] != result['confidence']:
            raise ValueError('Report confidence must exactly preserve the actual confidence.md result')
    if sid == 'confidence' and (not isinstance(result['final_score'], (int, float)) or
                                not 0 <= result['final_score'] <= 100):
        raise ValueError('Invalid confidence score')
    if sid == 'clean' and result.get('applicability') != 'not_applicable':
        if any(key not in result for key in ('mode', 'input_lines', 'kept_lines', 'collapsed_lines', 'files', 'audit_path')):
            raise ValueError('Cleaning result is missing line counts, file mapping or audit path')
        counts = [result[k] for k in ('input_lines', 'kept_lines', 'collapsed_lines')]
        if any(type(n) is not int or n < 0 for n in counts) or counts[0] != counts[1] + counts[2]:
            raise ValueError('Cleaning line counts must reconcile')
        if not result['files'] or not result['audit_path'] or not any(o['kind'] == 'cleaned_log' for o in data['outputs']):
            raise ValueError('Equivalent cleaning needs real logs, source mapping and audit')
    for output in data['outputs']:
        if output['kind'] != 'primary_markdown':
            path = Path(output['path'])
            if not output.get('sha256') or file_hash(path) != output['sha256']:
                raise ValueError('Supporting output is absent or changed: ' + str(path))


def reusable(sid, plan, state):
    stage = state['stages'][sid]
    if stage['status'] not in TERMINAL_OK:
        return False
    try:
        artifact, _ = read_current(sid, plan, state, inputs_for(sid, plan, state))
        validate_business(sid, artifact)
        return file_hash(plan.artifact(sid)) == stage['artifact_sha256']
    except (OSError, ValueError, KeyError, TypeError):
        return False


def invalidate(state, sid):
    for other in STAGE_IDS[STAGE_IDS.index(sid):]:
        previous = state['stages'][other]
        fresh = blank_stage()
        fresh['attempts'] = previous['attempts']
        state['stages'][other] = fresh


def run_command(argv, timeout=600):
    environment = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True, encoding='utf-8', errors='replace',
                            env=environment, timeout=timeout)
    if result.returncode:
        raise StepError(result.stderr.strip() or result.stdout.strip() or str(result.returncode),
                        classify_error(returncode=result.returncode, stderr=result.stderr), result.returncode)
    return result.stdout


def child(sid):
    script = SKILLS_ROOT / SCRIPTS[sid]
    if not script.is_file():
        raise Blocked('Automatic executor unavailable. Complete the same Markdown contract using an equivalent executor.')
    return [sys.executable, str(script)]


def detector(sid, plan):
    argv = child(sid) + ['--input', str(plan.source), '--phase', sid,
                         '--json', '--cases-library', str(plan.library)]
    for key, flag in (('request', '--request'), ('max_bytes', '--max-bytes'), ('max_files', '--max-files')):
        if key in plan.input:
            argv += [flag, str(plan.input[key])]
    argv += ['--level', str(plan.input.get('level', 'DEBUG'))]
    if sid == 'detect':
        argv += ['--case-match', str(plan.artifact('case_lookup'))]
    return json.loads(run_command(argv, plan.params(sid).get('timeout', 600)))


def attach(artifact, path, kind):
    artifact['outputs'].append({'path': str(path.resolve()), 'kind': kind, 'sha256': file_hash(path)})


def prepare_clean_input(plan, artifact, work):
    """Extract supplied ZIP text members with unambiguous archive-to-file mapping."""
    suffixes = {'.log', '.txt', '.out', '.err', '.trace', '.info', '.stack'}
    source = plan.source
    if source.is_file() and source.suffix.lower() == '.zip':
        extracted = work / 'extracted'
        aliases = []
        with zipfile.ZipFile(str(source)) as archive:
            entries = sorted((i for i in archive.infolist() if not i.is_dir()), key=lambda i: i.filename)
            for index, entry in enumerate(entries):
                name = entry.filename.replace('\\', '/')
                parts = PurePosixPath(name)
                if parts.is_absolute() or '..' in parts.parts or ':' in name or ((entry.external_attr >> 16) & 0o170000) == 0o120000:
                    raise StepError('Unsafe ZIP entry; original archive retained: ' + name)
                if parts.suffix.lower() not in suffixes:
                    continue
                target = extracted / ('%04d' % index) / Path(*parts.parts)
                if not within(target, extracted):
                    raise StepError('ZIP entry escapes extraction directory')
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as reader, target.open('wb') as writer:
                    shutil.copyfileobj(reader, writer)
                attach(artifact, target, 'original_archive_member')
                aliases.append({'source': str(target.resolve()), 'archive': str(source),
                                'member': entry.filename, 'member_index': index,
                                'original_ref': source.name + '!' + name + '#' + str(index),
                                'sha256': file_hash(target)})
        return extracted, [Path(a['source']) for a in aliases], aliases
    logs = ([source] if source.is_file() and source.suffix.lower() in suffixes else
            sorted(p for p in source.rglob('*') if p.is_file() and p.suffix.lower() in suffixes) if source.is_dir() else [])
    return source, logs, []


def execute(sid, plan, state, artifact, work):
    if plan.params(sid).get('execution') == 'manual_equivalent':
        raise Blocked('Equivalent manual execution selected. Complete all original business fields and evidence requirements in this Markdown artifact, then --resume.')
    if sid in ('case_lookup', 'detect'):
        artifact['result'] = detector(sid, plan)
        artifact['summary'] = ('Case lookup: ' + str(artifact['result'].get('status')) if sid == 'case_lookup'
                               else 'Scenario: ' + str(artifact['result'].get('primary', 'unknown')))
        artifact['evidence_gaps'] = artifact['result'].get('limitations', artifact['result'].get('missing_materials', []))
        return ''
    if sid == 'clean':
        clean_source, logs, source_aliases = prepare_clean_input(plan, artifact, work)
        if not logs:
            artifact['result'] = {'applicability': 'not_applicable', 'input_files': artifact['inputs']['materials'],
                                  'cleaned_files': [], 'input_lines': 0, 'kept_lines': 0,
                                  'collapsed_lines': 0, 'audit_path': None, 'policy': 'preserve_original',
                                  'reason': 'No supported text logs; supplied binary artifacts remain available.'}
            artifact['summary'] = 'No text log applicable to cleaning; original materials retained for diagnosis.'
            return ''
        output, audit = work / 'cleaned.log', work / 'clean-audit.md'
        result_path = work / 'clean-result.md'
        argv = child(sid) + ['--level', str(plan.params(sid).get('level', 'DEBUG')),
                             '--encoding', str(plan.params(sid).get('encoding', 'utf-8')),
                             '--output', str(output), '--audit-output', str(audit),
                             '--result-output', str(result_path)]
        if plan.params(sid).get('keep_noise', False):
            argv.append('--keep-noise')
        argv += (['--input-dir', str(clean_source), '--merge'] if clean_source.is_dir()
                 else ['--input', str(clean_source)])
        artifact['result'] = {'applicability': 'applicable', 'input_files': [str(p) for p in logs],
                              'cleaned_files': [], 'audit_path': str(audit), 'policy': 'conservative'}
        stdout = run_command(argv, plan.params(sid).get('timeout', 1800))
        if not output.is_file() or not audit.is_file():
            raise StepError('Cleaner did not produce the declared log and audit Markdown')
        attach(artifact, output, 'cleaned_log')
        attach(artifact, audit, 'cleaning_audit')
        child_result, _ = read_artifact(result_path, stage='clean')
        artifact['result'] = child_result['result']
        if source_aliases:
            artifact['result']['source_aliases'] = source_aliases
        artifact['summary'] = child_result['summary']
        return '# Log cleaning\n\n' + stdout
    if sid in MANUAL:
        raise Blocked('Awaiting ' + ('eval-skill diagnosis' if sid == 'diagnose' else 'metric-skill final report') +
                      '. Fill result and Markdown body, set status=success and finished_at, then --resume.')
    if sid == 'confidence':
        diagnosis, _ = read_artifact(plan.artifact('diagnose'))
        checks = diagnosis['result']['checks']
        if any(not isinstance(v if not isinstance(v, dict) else v.get('value'), bool) for v in checks.values()):
            raise StepError('Confidence check values must be Boolean, never strings or implicit truthy values')
        payload = {'meta': diagnosis['result'].get('meta', {}), 'checks': checks}
        checks_path = work / 'checks.json'
        atomic_write(checks_path, json.dumps(payload, ensure_ascii=False, indent=2))
        result = json.loads(run_command(child(sid) + ['--input', str(checks_path), '--json']))
        artifact['result'] = result
        artifact['summary'] = 'Confidence %s/100 (%s); case gate %s.' % (result['final_score'], result['level'], result['case_gate'])
        artifact['evidence_gaps'] = result.get('missing_items', [])
        return '# Confidence assessment\n\n' + artifact['summary']
    if sid == 'promote':
        return promote(plan, state, artifact, work)
    raise ValueError('Unknown stage ' + sid)


def mutation_write(path, data):
    atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2))


def commit_candidate(source, target):
    temporary = target.with_name(target.name + '.tmp-' + uuid.uuid4().hex)
    try:
        with source.open('rb') as input_stream, temporary.open('xb') as output_stream:
            shutil.copyfileobj(input_stream, output_stream)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        os.replace(str(temporary), str(target))
    finally:
        if temporary.exists():
            temporary.unlink()


def promote(plan, state, artifact, work):
    params = plan.params('promote')
    confidence, _ = read_artifact(plan.artifact('confidence'))
    score = confidence['result']
    artifact['result'] = {'enabled': bool(params.get('enabled', False)), 'decision': 'skipped',
                          'case_gate': score['case_gate'], 'target': None, 'case_id': None,
                          'mutation_id': None, 'reason': ''}
    if not params.get('enabled', False) or score['case_gate'] == 'reject':
        artifact['status'] = 'skipped'
        artifact['summary'] = 'Promotion disabled in plan.' if not params.get('enabled', False) else 'Case gate rejects publication.'
        artifact['result']['reason'] = artifact['summary']
        return ''
    if not params.get('cases_dir'):
        raise Blocked('Enabled promotion requires an explicit cases_dir target in the plan.')
    cases_dir = Path(params['cases_dir'])
    if not cases_dir.is_absolute():
        cases_dir = plan.path.parent / cases_dir
    cases_dir = cases_dir.resolve()
    diagnosis, body = read_artifact(plan.artifact('diagnose'))
    operation = digest({'diagnosis': diagnosis['result'], 'confidence': score, 'target': str(cases_dir)})
    receipt_path = plan.state_dir / 'mutations' / (operation + '.json')
    artifact['result']['mutation_id'] = operation
    target = cases_dir / ('cases.md' if score['case_gate'] == 'accept' else 'cases-pending.md')
    artifact['result']['target'] = str(target)
    lock = acquire_lock(cases_dir)
    try:
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
            if file_hash(target) == receipt['after_sha256']:
                receipt['status'] = 'committed'
                mutation_write(receipt_path, receipt)
                artifact['result'].update(decision='already_committed', reason='Existing mutation receipt verified.')
                artifact['result']['case_id'] = receipt.get('case_id')
                artifact['summary'] = 'Verified the prior case publication; no second write.'
                return ''
            raise Blocked('Publication receipt requires reconciliation; refusing a duplicate or uncertain write.')
        # The real promotion script operates on an isolated copy. Only one verified file is committed.
        staging = work / 'cases'
        staging.mkdir(parents=True, exist_ok=True)
        for name in ('cases.md', 'cases-pending.md'):
            source = cases_dir / name
            if source.is_file():
                shutil.copy2(source, staging / name)
        score_path, report_path = work / 'confidence.json', work / 'diagnosis.md'
        atomic_write(score_path, json.dumps(score, ensure_ascii=False))
        # Strip only the machine contract: the legacy script expects the diagnostic Markdown body.
        atomic_write(report_path, body)
        before = file_hash(target)
        try:
            stdout = run_command(child('promote') + ['--report', str(report_path), '--confidence', str(score_path),
                                                     '--cases-dir', str(staging)])
        except StepError as exc:
            if exc.code in (3, 4):
                artifact['result']['reason'] = str(exc)
                raise Blocked('Promotion needs report redaction or duplicate-case review: ' + str(exc)) from exc
            raise
        candidate = staging / target.name
        if not candidate.is_file():
            raise StepError('Promotion script did not produce a candidate case file')
        match = re.search(r'\[DONE\]\s+(P?CASE-\d+)', stdout)
        case_id = match.group(1) if match else None
        receipt = {'mutation_id': operation, 'run_id': state['run_id'], 'target': str(target),
                   'before_sha256': before, 'case_id': case_id,
                   'after_sha256': file_hash(candidate), 'status': 'prepared', 'at': now_iso()}
        mutation_write(receipt_path, receipt)
        if file_hash(target) != before:
            raise Blocked('Case library changed before commit; reconcile the prepared mutation.')
        commit_candidate(candidate, target)
        receipt['status'] = 'committed'
        mutation_write(receipt_path, receipt)
        artifact['result'].update(decision='committed', reason=stdout.strip(), case_id=case_id)
        artifact['summary'] = 'Case publication committed with a durable deduplication receipt.'
        return '# Case publication\n\n' + stdout
    finally:
        release_lock(lock)


def template_body(sid, artifact):
    if sid == 'diagnose':
        return ('# Diagnosis\n\n## 问题摘要\n\nDescribe only facts from supplied materials.\n\n'
                '## 关键证据链\n\nCite source path and line for each causal link.\n\n'
                '## 根因分析\n\nState confirmed root cause, or explicit unresolved hypotheses and evidence gaps.\n\n'
                '## 修复建议\n\nRecord recommendations and existing validation; do not invent verification.\n')
    if sid == 'report':
        return '# Final report\n\nFill the conclusion, confidence, evidence, recommendations and limitations.\n'
    return '# Equivalent execution work item\n\n' + artifact['next_action']


def generate_index(plan, state, stopped_at):
    """Write artifacts-index.md summarizing every stage's artifact, status, causal chain and hits."""
    lines = ['# 产物索引', '',
             '- run_id: ' + state['run_id'], '- state-dir: ' + str(plan.state_dir), '']
    lines.append('## 产物列表')
    lines.append('')
    lines.append('| step | 产物文件 | 状态 | owner_skill | 上游 | 摘要 |')
    lines.append('| --- | --- | --- | --- | --- | --- |')
    causal = []
    for sid in STAGE_IDS:
        stage = state['stages'][sid]
        art_path = plan.artifact(sid)
        fname = STAGE_FILES[sid]
        owner = OWNERS[sid]
        status = stage['status']
        summary = stage.get('summary', '')
        index = STAGE_IDS.index(sid)
        upstream = ', '.join(STAGE_IDS[:index]) if index > 0 else '—'
        exists = 'yes' if art_path.is_file() else 'no'
        lines.append('| {} | `artifacts/{}` ({}) | {} | {} | {} | {} |'.format(
            sid, fname, exists, status, owner, upstream, summary.replace('|', '/')[:80]))
        causal.append((sid, fname, status, [STAGE_IDS[:index]] if index > 0 else []))
    lines.append('')
    lines.append('## 因果链')
    lines.append('')
    lines.append('```text')
    for i, sid in enumerate(STAGE_IDS):
        if i == 0:
            lines.append('{} → {}'.format(STAGE_FILES[sid], STAGE_FILES[STAGE_IDS[i + 1]]))
        elif i < len(STAGE_IDS) - 1:
            lines.append('{} → {}'.format(STAGE_FILES[sid], STAGE_FILES[STAGE_IDS[i + 1]]))
    lines.append('```')
    lines.append('')
    lines.append('## 命中规则与场景识别')
    lines.append('')
    case_match_path = plan.artifact('case_lookup')
    scenario_path = plan.artifact('detect')
    if case_match_path.is_file():
        try:
            cm, _ = read_artifact(case_match_path, 'case_lookup', state['run_id'])
            result = cm.get('result', {})
            lines.append('- 案例库检索: {}'.format(result.get('status', 'unknown')))
            matches = result.get('matches', [])
            if matches:
                for m in matches:
                    lines.append('  - {} ({})'.format(m.get('case_id', '?'), m.get('title', '?')))
            else:
                lines.append('  - 无命中案例')
            lines.append('- 检索特征: {}'.format(json.dumps(result.get('query_features', {}), ensure_ascii=False)[:200]))
        except (OSError, ValueError, KeyError):
            lines.append('- 案例库检索: 读取失败')
    else:
        lines.append('- 案例库检索: 产物未生成')
    if scenario_path.is_file():
        try:
            sc, _ = read_artifact(scenario_path, 'detect', state['run_id'])
            result = sc.get('result', {})
            lines.append('- 主场景: {}'.format(result.get('primary', 'unknown')))
            lines.append('- 竞争场景: {}'.format(', '.join(result.get('secondary', [])) or '无'))
            lines.append('- 识别可信度: {}'.format(result.get('recognition_confidence', 'unknown')))
        except (OSError, ValueError, KeyError):
            lines.append('- 场景识别: 读取失败')
    else:
        lines.append('- 场景识别: 产物未生成')
    lines.append('')
    lines.append('## 诊断结论')
    lines.append('')
    diag_path = plan.artifact('diagnose')
    if diag_path.is_file():
        try:
            dg, _ = read_artifact(diag_path, 'diagnose', state['run_id'])
            result = dg.get('result', {})
            root = result.get('root_cause', {})
            lines.append('- 根因状态: {}'.format(root.get('status', 'unknown')))
            lines.append('- 根因描述: {}'.format(root.get('description', '—')[:200]))
            conf_path = plan.artifact('confidence')
            if conf_path.is_file():
                cf, _ = read_artifact(conf_path, 'confidence', state['run_id'])
                cr = cf.get('result', {})
                lines.append('- 可信度: {}/100 ({})'.format(cr.get('final_score', '?'), cr.get('level', '?')))
                lines.append('- 入库判定: {}'.format(cr.get('case_gate', '?')))
        except (OSError, ValueError, KeyError):
            lines.append('- 诊断结论: 读取失败')
    else:
        lines.append('- 诊断结论: 产物未生成')
    lines.append('')
    if stopped_at:
        lines.append('> 流水线在 **{}** 步停止。使用 `--resume` 恢复。'.format(stopped_at))
    else:
        lines.append('> 流水线已全部完成。')
    index_path = plan.state_dir / 'artifacts-index.md'
    atomic_write(index_path, '\n'.join(lines) + '\n')
    return index_path


def finalize(plan, state, sid, artifact, body):
    artifact['finished_at'] = now_iso()
    write_artifact(plan.artifact(sid), artifact, body)
    stage = state['stages'][sid]
    stage.update(status=artifact['status'], inputs_fingerprint=artifact['inputs']['fingerprint'],
                 artifact_sha256=file_hash(plan.artifact(sid)), last_error=artifact['error'],
                 summary=artifact['summary'])
    save_state(plan, state)


def run_stage(sid, plan, state, args):
    previous = state['stages'][sid]
    inputs = inputs_for(sid, plan, state)
    candidate, body = None, ''
    try:
        candidate, body = read_current(sid, plan, state, inputs)
    except (OSError, ValueError, TypeError, KeyError):
        pass
    if candidate and previous['status'] in ('blocked', 'failed', 'running') and candidate['status'] in TERMINAL_OK:
        try:
            validate_business(sid, candidate)
        except (ValueError, TypeError, KeyError) as exc:
            body += '\n\nValidation: ' + str(exc)
        else:
            previous['attempts'] += 1
            candidate['attempt'] = previous['attempts']
            candidate['next_action'] = 'Validated equivalent executor output; continue the same pipeline.'
            finalize(plan, state, sid, candidate, body)
            return candidate['status']
    if candidate and previous['status'] == 'running' and candidate['status'] == 'running':
        candidate['status'] = 'failed'
        candidate['summary'] = 'Previous execution was interrupted before completion.'
        candidate['error'] = {'class': 'interrupted', 'code': None, 'message': candidate['summary']}
        candidate['next_action'] = 'Resume the same stage with preserved partial evidence.'
        finalize(plan, state, sid, candidate, body)
    if previous['status'] == 'blocked' and candidate and candidate['status'] == 'blocked':
        # Merely checking an unfinished work item does not create another attempt.
        return 'blocked'
    if previous['status'] == 'failed' and previous['last_error'] and \
            previous['last_error']['class'] not in ('transient', 'resource', 'interrupted'):
        return 'failed'
    while True:
        previous['attempts'] += 1
        artifact = new_artifact(sid, state['run_id'], previous['attempts'], inputs, plan.artifact(sid))
        if candidate:
            artifact['result'] = candidate['result']
            artifact['evidence_gaps'] = candidate['evidence_gaps']
        previous['status'] = 'running'
        previous['inputs_fingerprint'] = inputs['fingerprint']
        save_state(plan, state)
        write_artifact(plan.artifact(sid), artifact, body)
        work = plan.state_dir / 'internal' / sid / ('%04d' % previous['attempts'])
        work.mkdir(parents=True, exist_ok=True)
        try:
            body = execute(sid, plan, state, artifact, work) or body
            if artifact['status'] == 'running':
                artifact['status'] = 'success'
            validate_business(sid, artifact)
        except Blocked as exc:
            artifact['status'], artifact['summary'] = 'blocked', str(exc)
            artifact['next_action'] = str(exc)
            artifact['result'] = artifact['result'] or {key: ({} if key in ('checks', 'confidence') else
                [] if key in ('timeline', 'causal_chain', 'alternatives', 'recommendations', 'references',
                              'findings', 'limitations', 'errors') else None) for key in BUSINESS_FIELDS.get(sid, ())}
            if sid == 'diagnose' and not artifact['result'].get('checks'):
                artifact['result']['checks'] = {key: {'value': False, 'evidence': ''} for key in CHECK_KEYS}
            body = body or template_body(sid, artifact)
        except (Exception, KeyboardInterrupt) as exc:
            category = exc.category if isinstance(exc, StepError) else classify_error(exc)
            if isinstance(exc, KeyboardInterrupt):
                category = 'interrupted'
            artifact['status'], artifact['summary'] = 'failed', str(exc) or category
            artifact['error'] = {'class': category, 'code': getattr(exc, 'code', None), 'message': str(exc)}
            artifact['next_action'] = ('Resume the interrupted stage.' if category == 'interrupted' else
                'Retry while the execution resource is recoverable.' if category in ('transient', 'resource')
                else 'Resolve the execution failure and use --restart-from %s; retain the evidence standard.' % sid)
            if category != 'interrupted':
                previous['failures'] += 1
            # Preserve real partial outputs, including cleaning audits, in the failed Markdown record.
            for path in work.rglob('*'):
                if path.is_file() and path.suffix != '.json' and not any(o['path'] == str(path.resolve()) for o in artifact['outputs']):
                    attach(artifact, path, 'partial_output')
        finalize(plan, state, sid, artifact, body)
        if not args.json:
            print('[%s] %s: %s' % (artifact['status'], sid, artifact['summary']), flush=True)
        if artifact['status'] != 'failed':
            return artifact['status']
        error_class = artifact['error']['class']
        retryable = error_class in ('transient', 'resource')
        if not retryable:
            return 'failed'
        time.sleep(min(args.retry_delay * (2 ** (previous['failures'] - 1)), 30))
        candidate = artifact


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--plan', type=Path)
    result.add_argument('--state-dir', type=Path, default=Path('.cann-orchestrator'))
    modes = result.add_mutually_exclusive_group()
    modes.add_argument('--resume', action='store_true')
    modes.add_argument('--restart-from', choices=STAGE_IDS)
    modes.add_argument('--only', choices=STAGE_IDS)
    result.add_argument('--retry-delay', type=float, default=2.0)
    result.add_argument('--dry-run', action='store_true')
    result.add_argument('--status', action='store_true')
    result.add_argument('--json', action='store_true')
    result.add_argument('--force-unlock', action='store_true')
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    if args.retry_delay < 0:
        raise ValueError('Retry values must be nonnegative')
    state_dir = args.state_dir.resolve()
    if args.status:
        if not (state_dir / 'state.json').exists():
            print('No pipeline state exists.', file=sys.stderr)
            return 2
        state = load_state(state_dir / 'state.json')
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    if not args.plan:
        raise ValueError('--plan is required')
    plan = Plan(args.plan, state_dir)
    if args.dry_run:
        print(json.dumps({'pipeline': list(STAGE_IDS), 'state_dir': str(state_dir),
                          'artifacts': {sid: str(plan.artifact(sid)) for sid in STAGE_IDS},
                          'promotion_enabled': bool(plan.params('promote').get('enabled', False)),
                          'manual_stages': list(MANUAL)}, ensure_ascii=False, indent=2))
        return 0
    lock = None
    try:
        lock = acquire_lock(state_dir, args.force_unlock)
        existed = (state_dir / 'state.json').exists()
        state = load_state(state_dir / 'state.json')
        if existed and not (args.resume or args.restart_from or args.only):
            raise StepError('State already exists; use --resume, --restart-from or --only', 'conflict')
        selected = args.only or args.restart_from
        start = STAGE_IDS.index(selected) if selected else 0
        for earlier in STAGE_IDS[:start]:
            if not reusable(earlier, plan, state):
                raise StepError('Predecessor %s is not current; --resume from the earliest invalid stage.' % earlier,
                                'conflict')
        if selected:
            invalidate(state, selected)
        elif args.resume:
            for sid in STAGE_IDS:
                stage = state['stages'][sid]
                inputs = inputs_for(sid, plan, state)
                if stage['status'] in TERMINAL_OK and not reusable(sid, plan, state):
                    invalidate(state, sid)
                    break
                if stage['inputs_fingerprint'] and stage['inputs_fingerprint'] != inputs['fingerprint']:
                    invalidate(state, sid)
                    break
        save_state(plan, state)
        targets = [args.only] if args.only else STAGE_IDS[start:]
        status, stopped = 'success', None
        for sid in targets:
            if reusable(sid, plan, state):
                continue
            status = run_stage(sid, plan, state, args)
            if status not in TERMINAL_OK:
                stopped = sid
                break
        summary = {'ok': status in TERMINAL_OK, 'run_id': state['run_id'], 'stopped_at': stopped,
                   'status': status, 'state_file': str(state_dir / 'state.json'),
                   'stages': {sid: state['stages'][sid]['status'] for sid in STAGE_IDS},
                   'artifact_index': str(plan.state_dir / 'artifacts-index.md'),
                   'next_action': ('Complete the pending Markdown artifact, then --resume.' if status == 'blocked'
                                   else 'Review the failed stage artifact.' if status == 'failed' else '')}
        generate_index(plan, state, stopped)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if status in TERMINAL_OK else 2 if status == 'blocked' else 1
    except StepError as exc:
        print(str(exc), file=sys.stderr)
        return 3 if exc.category == 'conflict' else 1
    finally:
        release_lock(lock)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError) as exc:
        print('%s: %s' % (type(exc).__name__, exc), file=sys.stderr)
        sys.exit(2)
