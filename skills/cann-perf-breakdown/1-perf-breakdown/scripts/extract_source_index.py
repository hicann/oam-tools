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
"""Build a deterministic, content-addressed index of Python model sources."""
import argparse
import ast
import hashlib
import json
import ntpath
import os


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _range(node):
    return {'line_start': node.lineno, 'line_end': node.end_lineno}


class _Symbols(ast.NodeVisitor):
    def __init__(self):
        self.scope = []
        self.classes = []
        self.functions = []

    def visit_ClassDef(self, node):
        qualname = '.'.join(self.scope + [node.name])
        methods = {item.name: item for item in node.body
                   if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.classes.append({
            'name': node.name,
            'qualname': qualname,
            **_range(node),
            'init': _range(methods['__init__']) if '__init__' in methods else None,
            'forward': _range(methods['forward']) if 'forward' in methods else None,
        })
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def _visit_function(self, node):
        qualname = '.'.join(self.scope + [node.name])
        self.functions.append({
            'name': node.name,
            'qualname': qualname,
            'kind': 'method' if self.scope else 'function',
            **_range(node),
        })
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function


def _source_files(root):
    for directory, dirs, files in os.walk(root):
        dirs[:] = sorted(item for item in dirs if item != '__pycache__' and not item.startswith('.'))
        for name in sorted(files):
            if name.endswith('.py'):
                yield os.path.join(directory, name)


def _relative_posix(path, root):
    relative = os.path.relpath(path, root).replace('\\', '/').replace(os.sep, '/')
    return relative


def _normalized_source_paths(roots):
    records = []
    for root_number, root in enumerate(roots):
        for path in _source_files(root):
            records.append((root_number, root, _relative_posix(path, root), path))
    return sorted(records, key=lambda item: (item[0], item[2]))


def _normalize_indexed_path(relative):
    if not isinstance(relative, str):
        return None
    normalized = relative.replace('\\', '/')
    parts = normalized.split('/')
    if (not normalized or normalized.startswith('/') or ntpath.isabs(normalized)
            or any(part in ('', '.', '..') for part in parts)):
        return None
    return normalized


def _bundle_state(roots):
    bundle = hashlib.sha256()
    files = []
    for root_number, _, relative, path in _normalized_source_paths(roots):
        with open(path, 'rb') as stream:
            digest = _sha256_bytes(stream.read())
        files.append({'root_index': root_number, 'path': relative, 'sha256': digest})
        bundle.update(str(root_number).encode('ascii'))
        bundle.update(b'\0')
        bundle.update(relative.encode('utf-8'))
        bundle.update(b'\0')
        bundle.update(digest.encode('ascii'))
        bundle.update(b'\n')
    return bundle.hexdigest(), files


def verify_source_index(index, source_dirs=None):
    """Rehash indexed roots without parsing source; report any content/list drift."""
    indexed_roots = [os.path.realpath(path) for path in index.get('source_roots') or []]
    roots = (sorted({os.path.realpath(path) for path in source_dirs})
             if source_dirs is not None else indexed_roots)
    current_hash, current_files = _bundle_state(roots)
    indexed_files = []
    metadata_valid = True
    for item in index.get('files') or []:
        root_index = item.get('root_index')
        relative = _normalize_indexed_path(item.get('path'))
        if (not isinstance(root_index, int) or root_index < 0
                or root_index >= len(indexed_roots) or relative is None):
            metadata_valid = False
            continue
        declared_root = os.path.realpath(item.get('root') or '')
        expected_root = indexed_roots[root_index]
        resolved = os.path.realpath(os.path.join(expected_root, *relative.split('/')))
        if (declared_root != expected_root
                or os.path.commonpath((expected_root, resolved)) != expected_root):
            metadata_valid = False
        indexed_files.append({'root_index': root_index, 'path': relative,
                              'sha256': item.get('sha256')})
    indexed_files.sort(key=lambda item: (item['root_index'], item['path']))
    return {
        'matches': (current_hash == index.get('source_bundle_hash')
                    and current_files == indexed_files and roots == indexed_roots
                    and metadata_valid),
        'source_bundle_hash': current_hash,
        'indexed_source_bundle_hash': index.get('source_bundle_hash'),
        'metadata_valid': metadata_valid,
        'files': current_files,
    }


def build_source_index(source_dirs):
    roots = sorted({os.path.realpath(path) for path in source_dirs})
    records = []
    bundle = hashlib.sha256()
    for root_number, root, relative, path in _normalized_source_paths(roots):
        with open(path, 'rb') as stream:
            content = stream.read()
        digest = _sha256_bytes(content)
        try:
            tree = ast.parse(content, filename=relative)
        except (SyntaxError, UnicodeDecodeError) as error:
            raise ValueError(f'cannot parse source {path}: {error}') from error
        symbols = _Symbols()
        symbols.visit(tree)
        record = {
            'path': relative,
            'root': root,
            'root_index': root_number,
            'sha256': digest,
            'classes': sorted(symbols.classes, key=lambda item: (item['line_start'], item['qualname'])),
            'functions': sorted(symbols.functions, key=lambda item: (item['line_start'], item['qualname'])),
        }
        records.append(record)
        bundle.update(str(root_number).encode('ascii'))
        bundle.update(b'\0')
        bundle.update(relative.encode('utf-8'))
        bundle.update(b'\0')
        bundle.update(digest.encode('ascii'))
        bundle.update(b'\n')
    return {
        'schema_version': 1,
        'source_roots': roots,
        'source_bundle_hash': bundle.hexdigest(),
        'files': records,
    }


def write_json(path, value):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, sort_keys=True)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description='Build deterministic model source index')
    parser.add_argument('--source-dir', action='append', required=True)
    parser.add_argument('-o', '--output', required=True)
    args = parser.parse_args()
    write_json(args.output, build_source_index(args.source_dir))
    print(f'source index written: {args.output}')


if __name__ == '__main__':
    main()
