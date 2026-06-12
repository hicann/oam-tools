#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
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
import logging
import argparse
import os
from collections import defaultdict

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ['Step Id', 'Name', 'Duration(us)', 'Start Time(us)', 'Stream ID']

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


def _median(values):
    """有序中位数。"""
    s = sorted(values)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


def _should_skip_warmup(ordered):
    """判断最早步是否为 warmup/离群，返回 (skip, later_median)。"""
    later = ordered[1:]
    if not later:
        return False, None
    later_median = _median([x['total_duration_us'] for x in later])
    if later_median > 0:
        ratio = ordered[0]['total_duration_us'] / later_median
        return (ratio > 1.5 or ratio < 0.67), later_median
    return False, later_median


def _repr_step_reason(selected, ordered, skip_earliest, later_median):
    """构建代表步选择理由文本。"""
    if skip_earliest:
        return (f'auto-selected non-warmup step {selected["step_id"]}: '
                f'largest stable kernel signature group size={len(ordered)}, '
                f'skipped earliest warmup/outlier candidate={ordered[0]["step_id"]}, '
                f'duration_us={selected["total_duration_us"]}, '
                f'later_median_us={round(later_median, 1)}')
    return (f'auto-selected stable step {selected["step_id"]}: '
            f'largest stable kernel signature group size={len(ordered)}, '
            f'earliest candidate is not a duration outlier, '
            f'duration_us={selected["total_duration_us"]}')


def choose_representative_step(steps_summary):
    """选择稳定的非预热代表步（调用方未指定 -s 时）。

    策略：按 kernel_count + 类型分布分组，取最大组；若最早步 kernel_sum 明显
    离群则视为 warmup 跳过；在候选中选 duration 最接近中位数者，保持确定性。
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
    skip_earliest, later_median = _should_skip_warmup(ordered)

    candidates = ordered[1:] if skip_earliest else [ordered[0]]
    median = _median([x['total_duration_us'] for x in candidates])
    selected = min(
        candidates,
        key=lambda x: (abs(x['total_duration_us'] - median), _step_sort_key(x['step_id']))
    )
    reason = _repr_step_reason(selected, ordered, skip_earliest, later_median)
    return selected['step_id'], reason


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


def parse_args():
    parser = argparse.ArgumentParser(
        description='分析 kernel_details.csv，输出结构化 JSON 统计信息',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-f', '--file', default='kernel_details.csv',
                        help='指定 CSV 文件路径 (默认: kernel_details.csv)')
    parser.add_argument('-s', '--step', type=int, default=None,
                        help='指定要输出详情的 step ID (默认: 自动选择第一个 step)')
    parser.add_argument('-o', '--output', default='kernels.json',
                        help='输出 operators JSON 文件路径 (默认: kernels.json)')
    parser.add_argument('-d', '--details', default=None,
                        help='输出详细 operators JSON 文件路径 (包含 CSV 全部字段)')
    parser.add_argument('-m', '--markdown', default=None,
                        help='输出统计摘要 Markdown 文件路径 (不指定则不生成)')
    parser.add_argument('--compact-out', default=None, dest='compact_out',
                        help='输出 Step 2 投喂用的精简 JSON 路径 '
                             '(删除 start_time_us/duration_us，连续相同算子折叠)')
    parser.add_argument('--enrich', action='store_true', default=False,
                        help='enrich 模式：将 raw_ops.json 数据内嵌到 analysis_config.json')
    parser.add_argument('-c', '--config', default=None,
                        help='[enrich 模式] analysis_config.json 路径')
    parser.add_argument('-r', '--raw-ops', default=None, dest='raw_ops',
                        help='[enrich 模式] raw_ops.json 路径')
    return parser.parse_args()


def _raise_kernel_mismatch(first_types, first_step, s):
    """构建并抛出两个 step 间 kernel 分布不一致的错误。"""
    diff_kernels = []
    all_keys = set(first_types.keys()) | set(s['kernel_types'].keys())
    for k in sorted(all_keys):
        v1 = first_types.get(k, 0)
        v2 = s['kernel_types'].get(k, 0)
        if v1 != v2:
            diff_kernels.append(f'  {k}: Step {first_step}={v1}, Step {s["step_id"]}={v2}')
    raise ConsistencyError(
        '错误: 各 Step 的 Kernel 分布不一致\n'
        '差异:\n' + '\n'.join(diff_kernels[:10]) +
        (f'\n  ... 还有 {len(diff_kernels) - 10} 个差异' if len(diff_kernels) > 10 else '')
    )


def check_consistency(steps_summary):
    if len(steps_summary) <= 1:
        return

    first_types = None
    first_step = None

    for s in steps_summary:
        if first_types is None:
            first_types = s['kernel_types']
            first_step = s['step_id']
        elif s['kernel_types'] != first_types:
            _raise_kernel_mismatch(first_types, first_step, s)


def _parse_kernel_row(row, row_num, all_columns, step_kernels_len):
    """解析单行 CSV，返回 (step_id, op_info, detail_info)；step_id 为空返回 None。"""
    step_id = get_safe_value(row, 'Step Id')
    if not step_id:
        return None

    name = get_safe_value(row, 'Name')
    kernel_type = extract_kernel_type(name)
    duration = parse_float(get_safe_value(row, 'Duration(us)'))

    op_info = {
        'index': step_kernels_len,
        'org_index': row_num - 2,
        'original_name': name,
        'normalized_name': kernel_type,
        'duration_us': duration,
        'start_time_us': parse_float(get_safe_value(row, 'Start Time(us)')),
        'stream_id': get_safe_value(row, 'Stream ID'),
        'task_type': get_safe_value(row, 'Type') if 'Type' in row else '',
        'input_shapes': get_safe_value(row, 'Input Shapes').strip('"') if 'Input Shapes' in row else '',
        'output_shapes': (get_safe_value(row, 'Output Shapes').strip('"')
                          if 'Output Shapes' in row else '')
    }

    detail_info = {'index': op_info['index'], 'org_index': op_info['org_index']}
    for col in all_columns:
        if col in IGNORED_COLUMNS:
            continue
        json_key = csv_col_name_to_json_key(col)
        raw_value = get_safe_value(row, col)
        if raw_value:
            detail_info[json_key] = parse_column_value(raw_value, col, json_key)
            if json_key in ('start_time_us', 'duration_us'):
                detail_info[f'{json_key}_raw'] = raw_value
    for key in ('input_shapes', 'output_shapes'):
        if key in detail_info and isinstance(detail_info[key], str):
            detail_info[key] = detail_info[key].strip('"')
    return step_id, op_info, detail_info, kernel_type, duration


def _consume_csv_row(row, row_num, all_columns, steps_data):
    """解析并累加单行 CSV 到 steps_data；成功计入返回 True，跳过返回 False。"""
    try:
        step_id = get_safe_value(row, 'Step Id')
        if not step_id:
            return False
        parsed = _parse_kernel_row(row, row_num, all_columns, len(steps_data[step_id]['kernels']))
    except Exception as e:
        logger.warning('警告: 第 %s 行数据解析失败: %s', row_num, e)
        return False
    if parsed is None:
        return False
    step_id, op_info, detail_info, kernel_type, duration = parsed
    sd = steps_data[step_id]
    sd['kernels'].append(op_info)
    sd['kernels_details'].append(detail_info)
    sd['total_duration'] += duration
    sd['kernel_types'][kernel_type] += 1
    sd['all_columns'] = all_columns
    return True


def _read_csv_rows(csv_file, steps_data):
    """打开 CSV，逐行消费，返回 (all_columns, row_count)。"""
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValidationError('错误: CSV 文件为空或格式不正确')
        validate_csv_structure(reader.fieldnames)
        all_columns = [col for col in reader.fieldnames if col not in IGNORED_COLUMNS]
        row_count = 0
        for row_num, row in enumerate(reader, start=2):
            if _consume_csv_row(row, row_num, all_columns, steps_data):
                row_count += 1
    return all_columns, row_count


def _parse_csv(csv_file, steps_data):
    """读取 CSV，填充 steps_data，返回 all_columns。"""
    try:
        all_columns, row_count = _read_csv_rows(csv_file, steps_data)
        if row_count == 0:
            raise ValidationError('错误: CSV 文件没有有效数据行')
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f'错误: 解析 CSV 文件失败: {e}') from e
    return all_columns


def _step_summary_entry(step_id, data):
    """构建单个 step 的 summary 条目。"""
    return {
        'step_id': step_id,
        'total_duration_us': round(data['total_duration'], 1),
        'kernel_count': len(data['kernels']),
        'kernel_types_count': len(data['kernel_types']),
        'kernel_types': dict(sorted(data['kernel_types'].items(), key=lambda x: -x[1]))
    }


def _selected_step_payload(data, str_step_id, reason, *, with_details):
    """构建 selected_step_operators / _details 的公共负载。"""
    payload = {
        'step_id': str_step_id,
        'selection_reason': reason,
        'total_duration_us': round(data['total_duration'], 1),
        'kernel_count': len(data['kernels']),
        'kernel_types_count': len(data['kernel_types']),
        'kernel_types': dict(sorted(data['kernel_types'].items(), key=lambda x: -x[1])),
    }
    if with_details:
        payload['csv_columns'] = data['all_columns']
        payload['operators'] = data['kernels_details']
    else:
        payload['operators'] = data['kernels']
    return payload


def analyze_kernels(csv_file, detail_step_id=None):
    validate_file(csv_file)

    steps_data = defaultdict(lambda: {
        'kernels': [],
        'kernels_details': [],
        'total_duration': 0.0,
        'kernel_types': defaultdict(int),
        'all_columns': []
    })

    all_columns = _parse_csv(csv_file, steps_data)
    sorted_steps = sorted(steps_data.keys(), key=lambda x: int(x) if x.isdigit() else x)

    result = {
        'step_count': len(steps_data),
        'steps_summary': [_step_summary_entry(sid, steps_data[sid]) for sid in sorted_steps],
        'csv_columns': all_columns
    }

    check_consistency(result['steps_summary'])

    if detail_step_id is None:
        detail_step_id, selection_reason = choose_representative_step(result['steps_summary'])
        result['selected_step_reason'] = selection_reason
    else:
        result['selected_step_reason'] = f'user-specified step {detail_step_id}'

    if detail_step_id is not None:
        str_step_id = str(detail_step_id)
        if str_step_id not in steps_data:
            raise ValidationError(
                f'错误: Step {detail_step_id} 不存在\n'
                f'可用的 Step: {", ".join(sorted_steps)}'
            )
        data = steps_data[str_step_id]
        reason = result.get('selected_step_reason', '')
        result['selected_step_operators'] = _selected_step_payload(
            data, str_step_id, reason, with_details=False)
        result['selected_step_operators_details'] = _selected_step_payload(
            data, str_step_id, reason, with_details=True)

    return result, sorted_steps


def _op_signature(op):
    """compact 折叠的判同签名。"""
    return (
        op.get('normalized_name', ''),
        op.get('stream_id', ''),
        op.get('task_type', ''),
        op.get('input_shapes', ''),
        op.get('output_shapes', ''),
    )


def _fold_operators(src_ops, keep_fields):
    """将连续相同签名（≥3）的 op 折叠为 repeat 块，其余原样保留。"""
    compact_ops = []
    i, n = 0, len(src_ops)
    while i < n:
        sig = _op_signature(src_ops[i])
        j = i + 1
        while j < n and _op_signature(src_ops[j]) == sig:
            j += 1
        run_len = j - i
        if run_len >= 3:
            head, tail = src_ops[i], src_ops[j - 1]
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
    return compact_ops


def build_compact_view(operators_block: dict) -> dict:
    """将 selected_step_operators 视图压缩为 Step 2 投喂的精简版本。

    删除时间字段，仅保留 index/org_index/normalized_name/stream_id/task_type/
    input_shapes/output_shapes；连续相同块折叠为 {repeat:true,...,count}。
    """
    keep_fields = ('index', 'org_index', 'normalized_name', 'stream_id',
                   'task_type', 'input_shapes', 'output_shapes')
    compact_ops = _fold_operators(operators_block.get('operators', []), keep_fields)
    return {
        'step_id': operators_block.get('step_id'),
        'kernel_count': operators_block.get('kernel_count'),
        'kernel_types_count': operators_block.get('kernel_types_count'),
        'kernel_types': operators_block.get('kernel_types', {}),
        'compact_operator_count': len(compact_ops),
        'note': ('compact view for Step 2: timing fields removed; '
                 'consecutive identical ops folded as {repeat:true,...,count}'),
        'operators': compact_ops,
    }


def generate_markdown(result, csv_file):
    lines = []
    lines.append('# Kernel Analysis Summary')
    lines.append('')
    lines.append(f'**Source File:** `{os.path.basename(csv_file)}`')
    lines.append('')
    lines.append('---')
    lines.append('')
    
    lines.append('## Overview')
    lines.append('')
    lines.append('| Step ID | Kernel Count | Kernel Types | Total Duration (us) |')
    lines.append('|---------|--------------|--------------|---------------------|')
    for s in result['steps_summary']:
        lines.append(f'| {s["step_id"]} | {s["kernel_count"]} | {s["kernel_types_count"]} | {s["total_duration_us"]} |')
    lines.append('')
    if result.get('selected_step_reason'):
        lines.append(f'**Selected step:** {result.get("selected_step_reason")}')
        lines.append('')
    
    lines.append('---')
    lines.append('')
    lines.append('## Kernel Types Distribution')
    lines.append('')
    lines.append(f'### Steps {", ".join([s["step_id"] for s in result["steps_summary"]])}')
    lines.append('')
    lines.append('| Kernel Name | Count |')
    lines.append('|-------------|-------|')
    
    first_types = result['steps_summary'][0]['kernel_types']
    for ktype, count in first_types.items():
        lines.append(f'| {ktype} | {count} |')
    lines.append('')
    
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


def _build_op_entry(idx, op, kernel_sem):
    """根据 op + 语义信息构建单个 op_data 条目。"""
    entry = {
        'index': op.get('index', idx),
        'org_index': op.get('org_index', -1),
        'name': op.get('normalized_name') or op.get('name', 'Unknown'),
        'duration_us': op.get('duration_us', 0),
        'stream_id': op.get('stream_id', ''),
        'task_type': op.get('task_type', ''),
        'input_shapes': op.get('input_shapes', ''),
        'output_shapes': op.get('output_shapes', ''),
    }
    shape_sem = _format_shape_pair(entry['input_shapes'], entry['output_shapes'])
    if shape_sem:
        entry['shape_raw'] = shape_sem
    sem_info = kernel_sem.get(idx, {})
    for field in ('semantic', 'shape_semantic', 'code_ref'):
        if field in sem_info:
            entry[field] = sem_info[field]
    entry = {k: v for k, v in entry.items() if not _is_empty_value(v) and v != -1}
    if 'index' not in entry:
        entry['index'] = idx
    return entry


def _enrich_op_data(node, op_dict, kernel_sem):
    """为含 op_indices 的节点构建 op_data 列表。"""
    op_data = []
    for idx in node['op_indices']:
        op = op_dict.get(idx)
        if op is None:
            continue
        op_data.append(_build_op_entry(idx, op, kernel_sem))
    node['op_data'] = op_data


def _enrich_kernels(node, op_dict):
    """为 kernels[] 节点补全缺失字段。"""
    for ks in node['kernels']:
        idx = ks.get('index')
        op = op_dict.get(idx) if idx is not None else None
        if not op:
            continue
        ks.setdefault('name', op.get('normalized_name') or op.get('name', 'Unknown'))
        ks.setdefault('org_index', op.get('org_index', -1))
        ks.setdefault('duration_us', op.get('duration_us', 0))
        ks.setdefault('input_shapes', op.get('input_shapes', ''))
        ks.setdefault('output_shapes', op.get('output_shapes', ''))
        if 'shape_raw' not in ks:
            shape_sem = _format_shape_pair(op.get('input_shapes', ''), op.get('output_shapes', ''))
            if shape_sem:
                ks['shape_raw'] = shape_sem


def _kernel_semantic_entry(ks):
    """从 kernel spec 提取非空 semantic/shape_semantic/code_ref 字段。"""
    entry = {}
    for field in ('semantic', 'shape_semantic', 'code_ref'):
        val = ks.get(field, '')
        if val:
            entry[field] = val
    return entry


def _collect_kernels_semantics(node: dict) -> dict:
    """收集节点下各 kernel 的语义信息，按 index 索引。"""
    result = {}
    for ks in node.get('kernels', []):
        idx = ks.get('index')
        if idx is None:
            continue
        entry = _kernel_semantic_entry(ks)
        if entry:
            result[idx] = entry
    return result


def enrich_analysis_config(config: dict, operators: list) -> dict:
    import copy
    config = copy.deepcopy(config)
    op_dict = {op['index']: op for op in operators}

    def enrich_node(node: dict) -> dict:
        kernel_sem = _collect_kernels_semantics(node)

        if 'op_indices' in node:
            _enrich_op_data(node, op_dict, kernel_sem)

        if 'kernels' in node:
            _enrich_kernels(node, op_dict)

        for child in node.get('children', []):
            enrich_node(child)

        return node

    for stage_name, stage_info in config.get('stages', {}).items():
        config['stages'][stage_name] = enrich_node(stage_info)

    for layer_type, structure in config.get('layer_structure', {}).items():
        config['layer_structure'][layer_type] = enrich_node(structure)

    for i, aux in enumerate(config.get('runtime_auxiliary', [])):
        config['runtime_auxiliary'][i] = enrich_node(aux)

    return config


def enrich_main(args):
    config_path = args.config
    raw_ops_path = args.raw_ops
    output_path = args.output if args.output != 'kernels.json' else config_path

    if not os.path.exists(config_path):
        raise ValidationError(f'错误: 配置文件不存在: {config_path}')
    if not os.path.exists(raw_ops_path):
        raise ValidationError(f'错误: raw_ops 文件不存在: {raw_ops_path}')

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    with open(raw_ops_path, 'r', encoding='utf-8') as f:
        raw_ops = json.load(f)

    operators = raw_ops.get('operators', [])
    enriched = enrich_analysis_config(config, operators)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False)
    logger.info('Enriched config 已保存到: %s', output_path)


def main():
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    args = parse_args()
    if getattr(args, 'enrich', False):
        try:
            enrich_main(args)
        except ValidationError as e:
            logger.error(str(e))
            sys.exit(1)
        return

    try:
        result, sorted_steps = analyze_kernels(args.file, args.step)

        if 'selected_step_operators' in result:
            operators_json = result['selected_step_operators']
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(operators_json, f, indent=2, ensure_ascii=False)
            logger.info('Operators JSON 已保存到: %s', args.output)

        if args.details and 'selected_step_operators_details' in result:
            details_json = result['selected_step_operators_details']
            with open(args.details, 'w', encoding='utf-8') as f:
                json.dump(details_json, f, indent=2, ensure_ascii=False)
            logger.info('Details JSON 已保存到: %s', args.details)

        if args.compact_out and 'selected_step_operators' in result:
            compact_json = build_compact_view(result['selected_step_operators'])
            with open(args.compact_out, 'w', encoding='utf-8') as f:
                json.dump(compact_json, f, indent=2, ensure_ascii=False)
            src_n = compact_json['kernel_count']
            cmp_n = compact_json['compact_operator_count']
            saved = (1 - cmp_n / src_n) * 100 if src_n else 0
            logger.info('Compact JSON 已保存到: %s (原 %s 算子 → %s 条目，折叠率 %.1f%%)',
                        args.compact_out, src_n, cmp_n, saved)

        if args.markdown:
            markdown_content = generate_markdown(result, args.file)
            with open(args.markdown, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            logger.info('Summary Markdown 已保存到: %s', args.markdown)

    except ValidationError as e:
        logger.error(str(e))
        sys.exit(1)
    except ConsistencyError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error('错误: 未知错误: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
