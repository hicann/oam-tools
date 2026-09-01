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
"""Apply a validated diagnostic patch to derived artifacts only."""
import argparse
import copy
import hashlib
import json
import os
import sys

import validate_diagnostic_patch as validator


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


def _pointer_parts(pointer):
    if not isinstance(pointer, str) or not pointer.startswith('/') or pointer == '/':
        raise ValueError(f'invalid or root JSON pointer: {pointer!r}')
    return [part.replace('~1', '/').replace('~0', '~')
            for part in pointer[1:].split('/')]


def _parent(document, parts):
    current = document
    for part in parts[:-1]:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise ValueError(f'patch parent does not exist at {part!r}')
    return current, parts[-1]


def _apply_operation(document, operation):
    parts = _pointer_parts(operation['path'])
    parent, key = _parent(document, parts)
    op = operation['op']
    if isinstance(parent, dict):
        if op in ('replace', 'remove') and key not in parent:
            raise ValueError(f'{op} target does not exist: {operation["path"]}')
        if op == 'remove':
            del parent[key]
        else:
            parent[key] = copy.deepcopy(operation['value'])
        return
    if isinstance(parent, list):
        if op == 'add' and key == '-':
            parent.append(copy.deepcopy(operation['value']))
            return
        if not key.isdigit():
            raise ValueError(f'list patch index is not numeric: {operation["path"]}')
        index = int(key)
        if op == 'add':
            if index > len(parent):
                raise ValueError(f'list add index is out of range: {operation["path"]}')
            parent.insert(index, copy.deepcopy(operation['value']))
        elif index >= len(parent):
            raise ValueError(f'list patch index is out of range: {operation["path"]}')
        elif op == 'remove':
            del parent[index]
        else:
            parent[index] = copy.deepcopy(operation['value'])
        return
    raise ValueError(f'patch parent is not a container: {operation["path"]}')


def apply_diagnostic_patch(report_path, request_path, config_path, manifest_path,
                           config_output, manifest_output, receipt_output):
    report = _load(report_path)
    request = _load(request_path)
    issues, detail = validator.validate_diagnostic_patch(report, request_path)
    if issues or not detail.get('applicable'):
        ids = ', '.join(item['id'] for item in issues) or report.get('outcome', 'unknown')
        raise ValueError(f'diagnostic patch is not applicable: {ids}')

    protected_paths = {os.path.realpath(report_path), os.path.realpath(request_path)}
    for collection in ('base_artifacts', 'inputs'):
        for artifact in (request.get(collection) or {}).values():
            if isinstance(artifact, dict) and artifact.get('path'):
                protected_paths.add(os.path.realpath(artifact['path']))
    output_paths = {
        os.path.realpath(config_output), os.path.realpath(manifest_output),
        os.path.realpath(receipt_output),
    }
    if len(output_paths) != 3:
        raise ValueError('diagnostic output paths must be distinct')
    if output_paths & protected_paths:
        raise ValueError('diagnostic output path would overwrite a protected input')

    expected_config = request['base_artifacts']['analysis_config']['sha256']
    expected_manifest = request['base_artifacts']['model_manifest']['sha256']
    if _sha(config_path) != expected_config or _sha(manifest_path) != expected_manifest:
        raise ValueError('provided base config/manifest does not match the diagnostic request')

    config = _load(config_path)
    manifest = _load(manifest_path)
    derived = {'analysis_config': config, 'manifest_hypothesis': manifest}
    for patch in report.get('patches') or []:
        document = derived[patch['target']]
        for operation in patch.get('operations') or []:
            _apply_operation(document, operation)

    _write(config_output, config)
    _write(manifest_output, manifest)
    receipt = {
        'schema_version': 1,
        'status': 'applied',
        'request_sha256': report['request_sha256'],
        'diagnostic_patch': {'path': os.path.realpath(report_path),
                             'sha256': _sha(report_path)},
        'base_artifacts': copy.deepcopy(request['base_artifacts']),
        'derived_artifacts': {
            'analysis_config': {'path': os.path.realpath(config_output),
                                'sha256': _sha(config_output)},
            'manifest_hypothesis': {'path': os.path.realpath(manifest_output),
                                    'sha256': _sha(manifest_output)},
        },
    }
    _write(receipt_output, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description='Apply a controlled diagnostic patch')
    parser.add_argument('-q', '--diagnostic-patch', required=True)
    parser.add_argument('--request', required=True)
    parser.add_argument('-c', '--config', required=True)
    parser.add_argument('-m', '--manifest', required=True)
    parser.add_argument('--config-output', required=True)
    parser.add_argument('--manifest-output', required=True)
    parser.add_argument('--receipt-output', required=True)
    args = parser.parse_args()
    try:
        apply_diagnostic_patch(
            args.diagnostic_patch, args.request, args.config, args.manifest,
            args.config_output, args.manifest_output, args.receipt_output)
    except (OSError, ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f'controlled diagnostic patch applied: {args.receipt_output}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
