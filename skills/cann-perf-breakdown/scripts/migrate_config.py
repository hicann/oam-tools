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
migrate_config.py — convert a legacy v1 analysis_config.json to schema v2.

The migration is a best-effort structural lift, NOT a re-validation. The result is
marked migration.status = "legacy_unverified" so downstream never treats a migrated
config as if it passed real v2 architecture validation.

What it does:
  - schema_version -> 2
  - moves layer_structure trees into `structures`
  - builds a minimal architecture block from layer_types (indices preserved verbatim,
    classification "unknown", num_main_layers = distinct main layer indices count if
    derivable else "unknown")
  - synthesizes trace_instances from layer_types.layer_indices, marking each
    model_layer_index as "unknown" (legacy layer_indices conflated layer id with
    invocation count, so we MUST NOT assert them as learned layer ids)
  - keeps stages / runtime_auxiliary as-is
  - records evidence gaps

Downstream must re-run extract_model_manifest + validate_architecture to promote a
legacy_unverified config to a trustworthy state.
"""
import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import breakdown_common as bc  # noqa: E402


def _migrate_layer_groups(layer_types):
    groups = []
    all_indices = set()
    for layer_type, info in layer_types.items():
        indices = info.get('layer_indices', []) or []
        all_indices.update(indices)
        groups.append({
            'type': layer_type,
            'classification': 'unknown',
            'model_layer_indices': sorted(indices),
            'source_ref': 'unknown',
        })
    return groups, all_indices


def _migrate_trace_instances(layer_types):
    instances = []
    for layer_type, info in layer_types.items():
        for invocation, _index in enumerate(info.get('layer_indices', []) or []):
            instances.append({
                'instance_id': f'legacy_{layer_type}_iter_{invocation}',
                'model_layer_index': 'unknown',
                'invocation_index': invocation,
                'layer_group_type': layer_type,
            })
    return instances


def migrate(v1: dict) -> dict:
    layer_types = v1.get('layer_types') or {}
    layer_structure = v1.get('layer_structure') or {}
    layer_groups, all_main_indices = _migrate_layer_groups(layer_types)
    num_main = len(all_main_indices) if all_main_indices else 'unknown'
    trace_instances = _migrate_trace_instances(layer_types)
    return {
        'schema_version': 2,
        'model_name': v1.get('model_name', 'unknown'),
        'representative_step': v1.get('representative_step'),
        'notes': v1.get('notes', ''),
        'migration': {
            'status': 'legacy_unverified',
            'source': 'v1 analysis_config.json',
            'note': ('Migrated structurally from legacy v1. layer_indices were ambiguous '
                     '(model layer id vs invocation count) so model_layer_index is "unknown". '
                     'Re-run extract_model_manifest + validate_architecture to verify.'),
        },
        'architecture': {
            'source_of_truth': [],
            'num_main_layers': num_main,
            'layer_groups': layer_groups,
            'prediction_modules': [],
        },
        'trace_scope': {
            'kind': 'unknown',
            'rank': None,
            'pipeline_stage': None,
            'evidence': ['legacy v1 config: trace scope not recorded'],
            'confidence': 'unknown',
        },
        'trace_instances': trace_instances,
        'structures': layer_structure,
        'stages': v1.get('stages', {}),
        'runtime_auxiliary': v1.get('runtime_auxiliary', []),
        'unmapped_ops': [],
    }


def main():
    parser = argparse.ArgumentParser(description='Migrate legacy v1 analysis_config to v2 (legacy_unverified)')
    parser.add_argument('-c', '--config', required=True)
    parser.add_argument('-o', '--output', required=True)
    args = parser.parse_args()

    if not os.path.exists(args.config):
        bc.emit_error(f'错误: 文件不存在: {args.config}\n')
        sys.exit(2)

    with open(args.config, 'r', encoding='utf-8') as f:
        v1 = json.load(f)

    if v1.get('schema_version') == 2:
        bc.emit_error('输入已是 schema v2，无需迁移\n')
        sys.exit(1)

    v2 = migrate(v1)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(v2, f, indent=2, ensure_ascii=False)
        f.write('\n')
    bc.emit(f'已迁移为 v2 (legacy_unverified): {args.output}')
    bc.emit(f'  num_main_layers={v2["architecture"]["num_main_layers"]}  '
          f'trace_instances={len(v2["trace_instances"])}')


if __name__ == '__main__':
    main()
