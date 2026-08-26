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
分析 kernel_details.csv，输出结构化 JSON 统计信息

用法:
  python analyze_kernels.py [-f FILE] [-s STEP] [-o OUTPUT] [-d DETAILS] [-m MD]

选项:
  -f, --file FILE    指定 CSV 文件路径 (默认: kernel_details.csv)
  -s, --step STEP    指定要输出详情的 step ID (默认: 自动选择非 warmup 代表 step)
  -o, --output FILE  输出 operators JSON 文件路径 (默认: kernels.json)
  -d, --details FILE 输出详细 operators JSON 文件路径 (包含 CSV 全部字段)
  -m, --markdown FILE 输出统计摘要 Markdown 文件路径 (不指定则不生成)
  -h, --help         显示帮助信息
"""
import csv
import json
import sys
import argparse
import os
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import breakdown_common as bc  # noqa: E402

REQUIRED_COLUMNS = ['Step Id', 'Name', 'Duration(us)', 'Start Time(us)', 'Stream ID']
MAX_CONSISTENCY_DIFFERENCES = 10

IGNORED_COLUMNS = {'Step Id'}

METRIC_COLUMN_PATTERNS = [
    'duration', 'time', 'cycles', 'ratio', 'utilization',
    'fops', 'rate', 'miss', 'count', 'num', 'dim', 'id'
]

VALUE_COLUMN_PATTERNS = [
    'name', 'type', 'state', 'core', 'shapes', 'formats',
    'eligible', 'formats', 'context'
]

FLOAT_SUFFIXES = ['(us)', '(%)']


def is_metric_column(col_name):
    col_lower = col_name.lower()
    for pattern in METRIC_COLUMN_PATTERNS:
        if pattern in col_lower:
            return True
    return False


def is_value_column(col_name):
    col_lower = col_name.lower()
    for pattern in VALUE_COLUMN_PATTERNS:
        if pattern in col_lower:
            return True
    return False


def parse_column_value(value, col_name, json_key=None):
    value = value.strip().rstrip('\t')
    if not value or value == 'N/A':
        return None

    col_lower = col_name.lower()

    for suffix in FLOAT_SUFFIXES:
        if col_lower.endswith(suffix.lower()) or suffix.lower() in col_lower:
            try:
                return float(value)
            except (ValueError, AttributeError):
                return value

    if is_metric_column(col_name):
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except (ValueError, AttributeError):
            return value

    try:
        if '.' in value:
            fval = float(value)
            return fval if fval != int(fval) else int(fval)
        return int(value)
    except (ValueError, AttributeError):
        pass

    return value


def csv_col_name_to_json_key(col_name):
    key = col_name.lower()
    key = key.replace('(us)', '_us')
    key = key.replace('(%)', '_pct')
    key = key.replace(' ', '_')
    key = key.replace('(', '')
    key = key.replace(')', '')
    return key


class ValidationError(Exception):
    pass


class ConsistencyError(Exception):
    pass


def _step_sort_key(step_id):
    return int(step_id) if str(step_id).isdigit() else str(step_id)


def _kernel_signature(summary):
    return (
        summary['kernel_count'],
        tuple(sorted(summary['kernel_types'].items())),
    )


def choose_representative_step(steps_summary):
    """
    Choose a stable non-warmup step when the caller does not specify -s.

    Policy:
    1. Group steps by kernel_count + exact kernel type distribution.
    2. Use the largest group, preferring groups with more kernels on ties.
    3. Treat the earliest step in that group as warmup only if its kernel_sum is
       a clear outlier versus the later steps.
    4. If warmup is skipped, choose the remaining step whose kernel_sum is
       closest to the later-step median; otherwise choose the earliest stable
       step to keep behavior deterministic and close to user-visible traces.

    This avoids picking first-step warmup/outlier traces such as decode step 10
    when later steps have the same structure but stable duration.
    """
    if not steps_summary:
        return None, 'no steps available'
    if len(steps_summary) == 1:
        return steps_summary[0]['step_id'], 'single step available'

    groups = defaultdict(list)
    for item in steps_summary:
        groups[_kernel_signature(item)].append(item)

    def group_rank(items):
        first_key = _step_sort_key(items[0]['step_id'])
        first_rank = -first_key if isinstance(first_key, int) else 0
        return (len(items), items[0]['kernel_count'], first_rank)

    selected_group = max(groups.values(), key=group_rank)
    ordered = sorted(selected_group, key=lambda x: _step_sort_key(x['step_id']))
    later = ordered[1:]
    skip_earliest = False
    later_median = None
    if later:
        later_durations = sorted(x['total_duration_us'] for x in later)
        later_mid = len(later_durations) // 2
        later_median = (
            later_durations[later_mid]
            if len(later_durations) % 2
            else (later_durations[later_mid - 1] + later_durations[later_mid]) / 2
        )
        first_duration = ordered[0]['total_duration_us']
        if later_median > 0:
            ratio = first_duration / later_median
            skip_earliest = ratio > 1.5 or ratio < 0.67

    candidates = later if skip_earliest else [ordered[0]]

    durations = sorted(x['total_duration_us'] for x in candidates)
    mid = len(durations) // 2
    median = durations[mid] if len(durations) % 2 else (durations[mid - 1] + durations[mid]) / 2
    selected = min(
        candidates,
        key=lambda x: (abs(x['total_duration_us'] - median), _step_sort_key(x['step_id']))
    )

    skipped = ordered[0]['step_id'] if skip_earliest else None
    if skip_earliest:
        reason = (
            f'auto-selected non-warmup step {selected["step_id"]}: '
            f'largest stable kernel signature group size={len(ordered)}, '
            f'skipped earliest warmup/outlier candidate={skipped}, '
            f'duration_us={selected["total_duration_us"]}, '
            f'later_median_us={round(later_median, 1)}'
        )
    else:
        reason = (
            f'auto-selected stable step {selected["step_id"]}: '
            f'largest stable kernel signature group size={len(ordered)}, '
            f'earliest candidate is not a duration outlier, '
            f'duration_us={selected["total_duration_us"]}'
        )
    return selected['step_id'], reason


def mark_duplicate_collective_records(kernels: list) -> int:
    """Flag the second record of each collective that msprof reports twice.

    A collective op appears as two rows with an identical (Start Time, Duration) and
    `Accelerator Core = COMMUNICATION`: one communication record with no Stream/Task ID, and
    one row for the AIV kernel that executes it on a real stream. They are the same device
    work, so summing both counts it twice. On a tp8 LongCat capture this inflated
    `kernel_sum` by 48% and let a single 73 ms all-reduce claim 95% of the step.

    The two rows are kept — both are real profiler output, and dropping one would break
    op-index continuity that every downstream `op_indices` depends on. Instead the second is
    marked `duplicate_of` and excluded from duration totals. The communication record is kept
    as the primary because it carries the collective's name; the AIV row is the duplicate.

    Pairing requires an exact timestamp and duration match, not just a shared type: two
    genuinely concurrent collectives on different streams keep both durations.
    """
    by_key = {}
    for op in kernels:
        if str(op.get('accelerator_core', '')).upper() != 'COMMUNICATION':
            continue
        key = (op.get('start_time_us'), op.get('duration_us'))
        by_key.setdefault(key, []).append(op)

    duplicates = 0
    for group in by_key.values():
        if len(group) < 2:
            continue
        # Prefer the record carrying the collective's name as primary; it is the one without a
        # Stream/Task ID. Fall back to first-seen so the choice is always deterministic.
        primary = group[0]
        for op in group:
            stream_id = op.get('stream_id')
            if not str(stream_id or '').strip() or str(stream_id).upper() == 'N/A':
                primary = op
                break
        for op in group:
            if op is primary:
                continue
            op['duplicate_of'] = primary['index']
            op['duplicate_reason'] = (
                'msprof records one collective twice: a COMMUNICATION entry and the AIV kernel '
                'executing it, with identical start and duration. Counted once in totals.'
            )
            duplicates += 1
    return duplicates


def validate_file(file_path):
    if not os.path.exists(file_path):
        raise ValidationError(f'错误: 文件不存在: {file_path}')
    if not os.path.isfile(file_path):
        raise ValidationError(f'错误: 路径不是文件: {file_path}')
    if not os.access(file_path, os.R_OK):
        raise ValidationError(f'错误: 文件不可读: {file_path}')


def validate_csv_structure(fieldnames):
    missing = [col for col in REQUIRED_COLUMNS if col not in fieldnames]
    if missing:
        raise ValidationError(
            f'错误: CSV 文件缺少必需列\n'
            f'缺少的列: {", ".join(missing)}\n'
            f'当前的列: {", ".join(fieldnames)}'
        )


def get_safe_value(row, key, default=''):
    return row.get(key, default).strip().rstrip('\t')


def parse_float(value):
    try:
        return float(value.strip().rstrip('\t'))
    except (ValueError, AttributeError):
        return 0.0


def extract_kernel_type(name):
    if not name:
        return 'Unknown'

    if '/' in name:
        return name

    if '_' not in name:
        return name

    parts = name.split('_')

    while parts and parts[-1].isdigit():
        parts.pop()

    if not parts:
        return name

    last_part = parts[-1]
    if last_part and last_part[0].isupper() and not last_part.isdigit():
        return last_part

    return '_'.join([p for p in parts if p])


def _add_analysis_args(parser):
    parser.add_argument(
        '-f', '--file',
        default='kernel_details.csv',
        help='指定 CSV 文件路径 (默认: kernel_details.csv)'
    )
    parser.add_argument(
        '-s', '--step',
        type=int,
        default=None,
        help='指定要输出详情的 step ID (默认: 自动选择非 warmup 代表 step)'
    )


def _add_output_args(parser):
    parser.add_argument(
        '-o', '--output',
        default='kernels.json',
        help='输出 operators JSON 文件路径 (默认: kernels.json)'
    )
    parser.add_argument(
        '-d', '--details',
        default=None,
        help='输出详细 operators JSON 文件路径 (包含 CSV 全部字段)'
    )
    parser.add_argument(
        '-m', '--markdown',
        default=None,
        help='输出统计摘要 Markdown 文件路径 (不指定则不生成)'
    )
    parser.add_argument(
        '--compact-out',
        default=None,
        dest='compact_out',
        help='输出 Step 2 投喂用的精简 JSON 路径 (删除 start_time_us/duration_us，连续相同算子折叠)'
    )


def _add_mode_args(parser):
    parser.add_argument(
        '--allow-step-variation',
        action='store_true',
        help='允许 Step 间 Kernel 签名不同，并从最大稳定签名组自动选择代表 Step'
    )
    parser.add_argument(
        '--enrich',
        action='store_true',
        default=False,
        help='enrich 模式：将 raw_ops.json 数据内嵌到 analysis_config.json'
    )
    parser.add_argument(
        '-c', '--config',
        default=None,
        help='[enrich 模式] analysis_config.json 路径'
    )
    parser.add_argument(
        '-r', '--raw-ops',
        default=None,
        dest='raw_ops',
        help='[enrich 模式] raw_ops.json 路径'
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description='分析 kernel_details.csv，输出结构化 JSON 统计信息',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    _add_analysis_args(parser)
    _add_output_args(parser)
    _add_mode_args(parser)
    return parser.parse_args()


def check_consistency(steps_summary):
    if len(steps_summary) <= 1:
        return

    first = steps_summary[0]
    for current in steps_summary[1:]:
        if current['kernel_types'] == first['kernel_types']:
            continue
        diff_kernels = _kernel_type_differences(first, current)
        raise ConsistencyError(
            '错误: 各 Step 的 Kernel 分布不一致\n'
            '差异:\n' + '\n'.join(diff_kernels[:MAX_CONSISTENCY_DIFFERENCES]) +
            (f'\n  ... 还有 {len(diff_kernels) - MAX_CONSISTENCY_DIFFERENCES} 个差异'
             if len(diff_kernels) > MAX_CONSISTENCY_DIFFERENCES else '')
        )


def _kernel_type_differences(first, current):
    differences = []
    all_keys = set(first['kernel_types']) | set(current['kernel_types'])
    for kernel_type in sorted(all_keys):
        first_count = first['kernel_types'].get(kernel_type, 0)
        current_count = current['kernel_types'].get(kernel_type, 0)
        if first_count != current_count:
            differences.append(
                f'  {kernel_type}: Step {first["step_id"]}={first_count}, '
                f'Step {current["step_id"]}={current_count}')
    return differences


def _new_step_data():
    return {
        'kernels': [],
        'kernels_details': [],
        'total_duration': 0.0,
        'kernel_types': defaultdict(int),
        'all_columns': []
    }


def _operator_info(row, row_num, index):
    name = get_safe_value(row, 'Name')
    return {
        'index': index,
        'org_index': row_num - 2,
        'original_name': name,
        'normalized_name': extract_kernel_type(name),
        'duration_us': parse_float(get_safe_value(row, 'Duration(us)')),
        'start_time_us': parse_float(get_safe_value(row, 'Start Time(us)')),
        'stream_id': get_safe_value(row, 'Stream ID'),
        'accelerator_core': (get_safe_value(row, 'Accelerator Core')
                             if 'Accelerator Core' in row else ''),
        'task_type': get_safe_value(row, 'Type') if 'Type' in row else '',
        'input_shapes': (get_safe_value(row, 'Input Shapes').strip('"')
                         if 'Input Shapes' in row else ''),
        'output_shapes': (get_safe_value(row, 'Output Shapes').strip('"')
                          if 'Output Shapes' in row else ''),
    }


def _detail_info(row, all_columns, op_info):
    detail = {'index': op_info['index'], 'org_index': op_info['org_index']}
    for column in all_columns:
        if column in IGNORED_COLUMNS:
            continue
        json_key = csv_col_name_to_json_key(column)
        raw_value = get_safe_value(row, column)
        if raw_value:
            detail[json_key] = parse_column_value(raw_value, column, json_key)
            if json_key in ('start_time_us', 'duration_us'):
                detail[f'{json_key}_raw'] = raw_value
    for key in ('input_shapes', 'output_shapes'):
        if key in detail and isinstance(detail[key], str):
            detail[key] = detail[key].strip('"')
    return detail


def _append_csv_row(steps_data, row, row_num, all_columns):
    step_id = get_safe_value(row, 'Step Id')
    if not step_id:
        return False
    data = steps_data[step_id]
    op_info = _operator_info(row, row_num, len(data['kernels']))
    data['kernels'].append(op_info)
    data['kernels_details'].append(_detail_info(row, all_columns, op_info))
    data['total_duration'] += op_info['duration_us']
    data['kernel_types'][op_info['normalized_name']] += 1
    data['all_columns'] = all_columns
    return True


def _read_step_rows(reader, steps_data, all_columns):
    row_count = 0
    for row_num, row in enumerate(reader, start=2):
        try:
            row_count += int(_append_csv_row(steps_data, row, row_num, all_columns))
        except Exception as error:
            bc.emit_error(f'警告: 第 {row_num} 行数据解析失败: {error}\n')
    return row_count


def _read_steps(csv_file):
    steps_data = defaultdict(_new_step_data)
    try:
        with open(csv_file, 'r', encoding='utf-8') as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None:
                raise ValidationError('错误: CSV 文件为空或格式不正确')
            validate_csv_structure(reader.fieldnames)
            all_columns = [column for column in reader.fieldnames
                           if column not in IGNORED_COLUMNS]
            row_count = _read_step_rows(reader, steps_data, all_columns)
            if row_count == 0:
                raise ValidationError('错误: CSV 文件没有有效数据行')
            return steps_data, all_columns
    except ValidationError:
        raise
    except Exception as error:
        raise ValidationError(f'错误: 解析 CSV 文件失败: {error}') from error


def _mark_step_duplicates(steps_data):
    for data in steps_data.values():
        data['duplicate_collective_count'] = mark_duplicate_collective_records(data['kernels'])
        duplicate_indices = {op['index'] for op in data['kernels'] if 'duplicate_of' in op}
        if not duplicate_indices:
            continue
        data['total_duration'] = sum(
            op['duration_us'] for op in data['kernels'] if op['index'] not in duplicate_indices)
        duplicate_of = {op['index']: op['duplicate_of'] for op in data['kernels']
                        if op['index'] in duplicate_indices}
        for detail in data['kernels_details']:
            if detail['index'] in duplicate_indices:
                detail['duplicate_of'] = duplicate_of[detail['index']]


def _step_summary(step_id, data):
    return {
        'step_id': step_id,
        'total_duration_us': round(data['total_duration'], 1),
        'duplicate_collective_count': data.get('duplicate_collective_count', 0),
        'kernel_count': len(data['kernels']),
        'kernel_types_count': len(data['kernel_types']),
        'kernel_types': dict(sorted(data['kernel_types'].items(), key=lambda item: -item[1])),
    }


def _selected_step_block(step_id, data, selection_reason, details=False):
    block = {
        'step_id': step_id,
        'selection_reason': selection_reason,
        'total_duration_us': round(data['total_duration'], 1),
        'duplicate_collective_count': data.get('duplicate_collective_count', 0),
        'kernel_count': len(data['kernels']),
        'kernel_types_count': len(data['kernel_types']),
        'kernel_types': dict(sorted(data['kernel_types'].items(), key=lambda item: -item[1])),
    }
    if details:
        block['csv_columns'] = data['all_columns']
        block['operators'] = data['kernels_details']
    else:
        block['operators'] = data['kernels']
    return block


def _select_step(result, steps_data, sorted_steps, detail_step_id):
    if detail_step_id is None:
        detail_step_id, reason = choose_representative_step(result['steps_summary'])
        result['selected_step_reason'] = reason
    else:
        result['selected_step_reason'] = f'user-specified step {detail_step_id}'
    if detail_step_id is None:
        return
    step_id = str(detail_step_id)
    if step_id not in steps_data:
        raise ValidationError(
            f'错误: Step {detail_step_id} 不存在\n'
            f'可用的 Step: {", ".join(list(sorted_steps))}')
    data = steps_data[step_id]
    reason = result.get('selected_step_reason', '')
    result['selected_step_operators'] = _selected_step_block(step_id, data, reason)
    result['selected_step_operators_details'] = _selected_step_block(
        step_id, data, reason, details=True)


def analyze_kernels(csv_file, detail_step_id=None, allow_step_variation=False):
    validate_file(csv_file)
    steps_data, all_columns = _read_steps(csv_file)
    _mark_step_duplicates(steps_data)
    sorted_steps = sorted(steps_data, key=lambda value: int(value) if value.isdigit() else value)
    result = {
        'step_count': len(steps_data),
        'steps_summary': [_step_summary(step_id, steps_data[step_id])
                          for step_id in sorted_steps],
        'csv_columns': all_columns,
    }
    if not allow_step_variation:
        check_consistency(result['steps_summary'])
    _select_step(result, steps_data, sorted_steps, detail_step_id)
    return result, sorted_steps


def build_compact_view(operators_block: dict) -> dict:
    """
    将 selected_step_operators 视图压缩为 Step 2 投喂的精简版本：
    - 删除 start_time_us（Step 2 不需要时间）
    - 删除 original_name、duration_us（Step 2 用 normalized_name 即可）
    - 仅保留：index、org_index、normalized_name、stream_id、task_type、input_shapes、output_shapes
    - 连续相同 (normalized_name, stream_id, task_type, input_shapes, output_shapes) 块折叠为：
        {repeat: true, normalized_name, stream_id, task_type, input_shapes, output_shapes,
         first_index, last_index, first_org_index, count}
      非连续或单个不折叠。
    """
    keep_fields = ('index', 'org_index', 'normalized_name', 'stream_id',
                   'task_type', 'input_shapes', 'output_shapes')

    src_ops = operators_block.get('operators', [])
    compact_ops = []

    def signature(op):
        return (
            op.get('normalized_name', ''),
            op.get('stream_id', ''),
            op.get('task_type', ''),
            op.get('input_shapes', ''),
            op.get('output_shapes', ''),
        )

    i = 0
    n = len(src_ops)
    while i < n:
        sig = signature(src_ops[i])
        j = i + 1
        while j < n and signature(src_ops[j]) == sig:
            j += 1
        run_len = j - i
        if run_len >= 3:
            head = src_ops[i]
            tail = src_ops[j - 1]
            compact_ops.append({
                'repeat': True,
                'normalized_name': head.get('normalized_name', ''),
                'stream_id': head.get('stream_id', ''),
                'task_type': head.get('task_type', ''),
                'input_shapes': head.get('input_shapes', ''),
                'output_shapes': head.get('output_shapes', ''),
                'first_index': head.get('index'),
                'last_index': tail.get('index'),
                'first_org_index': head.get('org_index'),
                'count': run_len,
            })
        else:
            for k in range(i, j):
                op = src_ops[k]
                compact_ops.append({f: op.get(f) for f in keep_fields if f in op})
        i = j

    return {
        'step_id': operators_block.get('step_id'),
        'kernel_count': operators_block.get('kernel_count'),
        'kernel_types_count': operators_block.get('kernel_types_count'),
        'kernel_types': operators_block.get('kernel_types', {}),
        'compact_operator_count': len(compact_ops),
        'note': (
            'compact view for Step 2: timing fields removed; consecutive identical '
            'ops folded as {repeat:true,...,count}'
        ),
        'operators': compact_ops,
    }


def generate_markdown(result, csv_file):
    lines = []
    lines.append(f'# Kernel Analysis Summary')
    lines.append(f'')
    lines.append(f'**Source File:** `{os.path.basename(csv_file)}`')
    lines.append(f'')
    lines.append(f'---')
    lines.append(f'')

    lines.append(f'## Overview')
    lines.append(f'')
    lines.append(f'| Step ID | Kernel Count | Kernel Types | Total Duration (us) |')
    lines.append(f'|---------|--------------|--------------|---------------------|')
    for s in result['steps_summary']:
        lines.append(f'| {s["step_id"]} | {s["kernel_count"]} | {s["kernel_types_count"]} | {s["total_duration_us"]} |')
    lines.append(f'')
    if result.get('selected_step_reason'):
        lines.append(f'**Selected step:** {result.get("selected_step_reason")}')
        lines.append(f'')

    lines.append(f'---')
    lines.append(f'')
    lines.append(f'## Kernel Types Distribution')
    lines.append(f'')
    lines.append(f'### Steps {", ".join([s["step_id"] for s in result["steps_summary"]])}')
    lines.append(f'')
    lines.append(f'| Kernel Name | Count |')
    lines.append(f'|-------------|-------|')

    first_types = result['steps_summary'][0]['kernel_types']
    for ktype, count in first_types.items():
        lines.append(f'| {ktype} | {count} |')
    lines.append(f'')

    return '\n'.join(lines)


def _is_empty_value(v) -> bool:
    return v is None or v == '' or str(v).strip().upper() == 'N/A'


def _format_shape_pair(input_shapes: str, output_shapes: str) -> str:
    ins = str(input_shapes).strip('"') if not _is_empty_value(input_shapes) else ''
    outs = str(output_shapes).strip('"') if not _is_empty_value(output_shapes) else ''
    parts = []
    if ins:
        parts.append(f'[{ins}]')
    if outs:
        parts.append(f'[{outs}]')
    return '→'.join(parts) if parts else ''


def _build_op_entry(index, op, semantic_info):
    entry = {
        'index': op.get('index', index),
        'org_index': op.get('org_index', -1),
        'name': op.get('normalized_name') or op.get('name', 'Unknown'),
        'duration_us': op.get('duration_us', 0),
        'stream_id': op.get('stream_id', ''),
        'task_type': op.get('task_type', ''),
        'input_shapes': op.get('input_shapes', ''),
        'output_shapes': op.get('output_shapes', ''),
    }
    shape_raw = _format_shape_pair(entry['input_shapes'], entry['output_shapes'])
    if shape_raw:
        entry['shape_raw'] = shape_raw
    for field in ('semantic', 'shape_semantic', 'code_ref'):
        if field in semantic_info:
            entry[field] = semantic_info[field]
    filtered_entry = {}
    for key, value in entry.items():
        if not _is_empty_value(value) and value != -1:
            filtered_entry[key] = value
    entry = filtered_entry
    if 'index' not in entry:
        entry['index'] = index
    return entry


def _enrich_kernel(kernel, op):
    defaults = {
        'name': op.get('normalized_name') or op.get('name', 'Unknown'),
        'org_index': op.get('org_index', -1),
        'duration_us': op.get('duration_us', 0),
        'input_shapes': op.get('input_shapes', ''),
        'output_shapes': op.get('output_shapes', ''),
    }
    for field, value in defaults.items():
        if field not in kernel:
            kernel[field] = value
    if 'shape_raw' not in kernel:
        shape_raw = _format_shape_pair(op.get('input_shapes', ''), op.get('output_shapes', ''))
        if shape_raw:
            kernel['shape_raw'] = shape_raw


def collect_kernels_semantics(node: dict) -> dict:
    result = {}
    for kernel in node.get('kernels', []):
        index = kernel.get('index')
        if index is None:
            continue
        entry = {field: kernel[field] for field in ('semantic', 'shape_semantic', 'code_ref')
                 if kernel.get(field, '')}
        if entry:
            result[index] = entry
    return result


def _enrich_node(node, op_dict):
    kernel_semantics = collect_kernels_semantics(node)
    if 'op_indices' in node:
        node['op_data'] = [
            _build_op_entry(index, op_dict[index], kernel_semantics.get(index, {}))
            for index in node['op_indices'] if index in op_dict
        ]
    for kernel in node.get('kernels', []):
        index = kernel.get('index')
        op = op_dict.get(index) if index is not None else None
        if op:
            _enrich_kernel(kernel, op)
    for child in node.get('children', []):
        _enrich_node(child, op_dict)
    return node


def enrich_analysis_config(config: dict, operators: list) -> dict:
    import copy
    config = copy.deepcopy(config)
    op_dict = {op['index']: op for op in operators}

    for stage_name, stage_info in config.get('stages', {}).items():
        config['stages'][stage_name] = _enrich_node(stage_info, op_dict)

    for layer_type, structure in config.get('layer_structure', {}).items():
        config['layer_structure'][layer_type] = _enrich_node(structure, op_dict)

    # schema v2 renamed representative layer templates to `structures`.
    for layer_type, structure in config.get('structures', {}).items():
        config['structures'][layer_type] = _enrich_node(structure, op_dict)

    for i, aux in enumerate(config.get('runtime_auxiliary', [])):
        config['runtime_auxiliary'][i] = _enrich_node(aux, op_dict)

    return config


def enrich_main(args):
    config_path = args.config
    raw_ops_path = args.raw_ops
    output_path = args.output if args.output != 'kernels.json' else config_path

    if not os.path.exists(config_path):
        bc.emit_error(f'错误: 配置文件不存在: {config_path}\n')
        return 1
    if not os.path.exists(raw_ops_path):
        bc.emit_error(f'错误: raw_ops 文件不存在: {raw_ops_path}\n')
        return 1

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    with open(raw_ops_path, 'r', encoding='utf-8') as f:
        raw_ops = json.load(f)

    operators = raw_ops.get('operators', [])
    enriched = enrich_analysis_config(config, operators)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False)
    bc.emit(f'Enriched config 已保存到: {output_path}')
    return 0


def main():
    args = parse_args()
    if getattr(args, 'enrich', False):
        return enrich_main(args)

    try:
        result, sorted_steps = analyze_kernels(
            args.file, args.step, allow_step_variation=args.allow_step_variation
        )

        if 'selected_step_operators' in result:
            operators_json = result['selected_step_operators']
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(operators_json, f, indent=2, ensure_ascii=False)
            bc.emit(f'Operators JSON 已保存到: {args.output}')

        if args.details and 'selected_step_operators_details' in result:
            details_json = result['selected_step_operators_details']
            with open(args.details, 'w', encoding='utf-8') as f:
                json.dump(details_json, f, indent=2, ensure_ascii=False)
            bc.emit(f'Details JSON 已保存到: {args.details}')

        if args.compact_out and 'selected_step_operators' in result:
            compact_json = build_compact_view(result['selected_step_operators'])
            with open(args.compact_out, 'w', encoding='utf-8') as f:
                json.dump(compact_json, f, indent=2, ensure_ascii=False)
            src_n = compact_json['kernel_count']
            cmp_n = compact_json['compact_operator_count']
            saved = (1 - cmp_n / src_n) * 100 if src_n else 0
            bc.emit(f'Compact JSON 已保存到: {args.compact_out} '
                  f'(原 {src_n} 算子 → {cmp_n} 条目，折叠率 {saved:.1f}%)')

        if args.markdown:
            markdown_content = generate_markdown(result, args.file)
            with open(args.markdown, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            bc.emit(f'Summary Markdown 已保存到: {args.markdown}')

    except ValidationError as e:
        bc.emit_error(str(e) + '\n')
        sys.exit(1)
    except ConsistencyError as e:
        bc.emit_error(str(e) + '\n')
        sys.exit(1)
    except Exception as e:
        bc.emit_error(f'错误: 未知错误: {e}\n')
        sys.exit(1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
