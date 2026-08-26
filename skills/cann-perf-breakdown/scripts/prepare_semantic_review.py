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
"""Prepare an evidence-bound request/template for AI semantic review."""
import argparse
import datetime
import json
import os

import breakdown_common as bc
from validate_semantic_review import REQUIRED_CHECKS, sha256_file


def main():
    parser = argparse.ArgumentParser(description='Prepare semantic review request')
    parser.add_argument('-c', '--config', required=True)
    parser.add_argument('-r', '--raw-ops', required=True)
    parser.add_argument('-m', '--manifest', required=True)
    parser.add_argument('--dataflow', help='dataflow_source.json to bind into the review')
    parser.add_argument('--source-dir', action='append', default=[])
    parser.add_argument('--review-output', default='semantic_review.json')
    parser.add_argument('-o', '--output', required=True)
    args = parser.parse_args()

    artifacts = {
        'analysis_config': {'path': os.path.realpath(args.config), 'sha256': sha256_file(args.config)},
        'raw_ops': {'path': os.path.realpath(args.raw_ops), 'sha256': sha256_file(args.raw_ops)},
        'model_manifest': {'path': os.path.realpath(args.manifest), 'sha256': sha256_file(args.manifest)},
    }
    if args.dataflow:
        artifacts['dataflow_source'] = {
            'path': os.path.realpath(args.dataflow),
            'sha256': sha256_file(args.dataflow),
        }
    template = {
        'schema_version': 1,
        'status': 'unknown',
        'reviewed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'reviewer': 'AI agent after source-and-trace review',
        'artifacts': artifacts,
        'source_evidence': [],
        'checks': [{'id': identifier, 'status': 'unknown', 'evidence': []}
                   for identifier in REQUIRED_CHECKS],
        'findings': [],
    }
    request = {
        'task': 'review model breakdown semantics against source code and the representative trace',
        'protocol': 'references/semantic_review_protocol.md',
        'schema': 'schemas/semantic_review.schema.json',
        'inputs': {**artifacts, 'source_dirs': [os.path.realpath(p) for p in args.source_dir]},
        'output_expected': os.path.realpath(args.review_output),
        'instructions': [
            'Read the model configuration and every forward path relevant to the traced execution.',
            'Review all nine checks; do not infer passed from 100% kernel coverage.',
            'Use failed or unknown when source/trace evidence is insufficient.',
            'Every passed check needs located evidence; preserve artifact SHA256 values unchanged.',
        ],
        'review_template': template,
    }
    with open(args.output, 'w', encoding='utf-8') as stream:
        json.dump(request, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    bc.emit(f'semantic review request 已写入: {args.output}')


if __name__ == '__main__':
    main()
