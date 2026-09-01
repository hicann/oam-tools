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
"""NPU 性能拆解报告生成脚本"""

import argparse
import copy
import json
import os
import sys
from pathlib import Path
from typing import Any, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import breakdown_common as bc  # noqa: E402


def iter_layer_sections(config: dict):
    """Yield (name, structure_node, multiplier) for decoder-layer sections.

    v2: derives sections + invocation-count multiplier from trace_instances/structures
        (see breakdown_common.build_v2_report_view) so the observed-execution tree is
        populated instead of empty. Multiplier is the observed invocation count, never
        the learned model-layer count.
    v1: legacy layer_types + layer_structure.
    """
    if config.get('schema_version') == 2:
        for sec in bc.build_v2_report_view(config) or []:
            yield sec['name'], sec['structure'], sec['multiplier']
        return
    layer_types = config.get('layer_types', {})
    layer_structure = config.get('layer_structure', {})
    for layer_type, layer_info in layer_types.items():
        structure = layer_structure.get(layer_type, {})
        if not structure:
            continue
        yield structure.get('name', layer_type), structure, len(layer_info.get('layer_indices', []))


def validate_file_exists(filepath: str) -> Path:
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {filepath}")
    return path


def load_json(filepath: Path) -> dict:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 格式错误: {filepath}: {e}")


def validate_raw_ops(data: dict) -> None:
    required = ['step_id', 'total_duration_us', 'kernel_count', 'operators']
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"raw_ops.json 缺少必要字段: {missing}")

    for i, op in enumerate(data.get('operators', [])):
        op_required = ['index', 'duration_us']
        op_missing = [k for k in op_required if k not in op]
        if op_missing:
            raise ValueError(f"operators[{i}] 缺少必要字段: {op_missing}")


def validate_analysis_config(data: dict) -> None:
    if data.get('schema_version') == 2:
        # `trace_scope` is deliberately absent: it annotates what the capture covered, not
        # what the model is, so a config without it is complete. The no-extrapolation rule
        # below does not depend on it being present.
        required = ['model_name', 'architecture']
    else:
        required = ['model_name', 'layer_types', 'layer_structure']
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"analysis_config.json 缺少必要字段: {missing}")


def get_duration_by_indices(operators: list, indices: list) -> float:
    total = 0.0
    op_dict = {op['index']: op for op in operators}
    for idx in indices:
        if idx in op_dict:
            total += bc.effective_duration_us(op_dict[idx])
    return total


def get_kernels_by_indices(operators: list, indices: list) -> list:
    op_dict = {op['index']: op for op in operators}
    kernels = []
    for idx in indices:
        if idx in op_dict:
            op = op_dict[idx]
            name = op.get('normalized_name') or op.get('type') or op.get('name', 'Unknown')
            kernels.append(name)
    return kernels


def get_kernel_details_by_indices(operators: list, indices: list) -> list:
    op_dict = {op['index']: op for op in operators}
    kernels = []
    for idx in indices:
        if idx in op_dict:
            op = op_dict[idx]
            name = op.get('normalized_name') or op.get('type') or op.get('name', 'Unknown')
            kernels.append({
                'name': name,
                'duration': op.get('duration_us', 0),
                'index': idx
            })
    kernels.sort(key=lambda x: -x['duration'])
    return kernels


def get_kernel_full_details_by_indices(operators: list, indices: list) -> list:
    op_dict = {op['index']: op for op in operators}
    kernels = []
    for idx in indices:
        if idx in op_dict:
            op = op_dict[idx]
            entry = {
                'index': idx,
                'duration': op.get('duration_us', 0),
                'duration_raw': op.get('duration_us_raw', str(op.get('duration_us', 0))),
                'start_time': op.get('start_time_us', 0),
                'start_time_raw': op.get('start_time_us_raw', str(op.get('start_time_us', 0))),
                'stream_id': op.get('stream_id', ''),
                'all_fields': dict(op)
            }
            if 'normalized_name' in op:
                entry['name'] = op.get('normalized_name', 'Unknown')
                entry['original_name'] = op.get('original_name', '')
                entry['task_type'] = op.get('task_type', '')
                entry['input_shapes'] = op.get('input_shapes', '')
                entry['output_shapes'] = op.get('output_shapes', '')
            else:
                entry['name'] = op.get('type', op.get('name', 'Unknown'))
                entry['original_name'] = op.get('name', '')
                entry['task_type'] = op.get('type', '')
                entry['input_shapes'] = op.get('input_shapes', '')
                entry['output_shapes'] = op.get('output_shapes', '')
                entry['input_data_types'] = op.get('input_data_types', '')
                entry['output_data_types'] = op.get('output_data_types', '')
                entry['input_formats'] = op.get('input_formats', '')
                entry['output_formats'] = op.get('output_formats', '')
            kernels.append(entry)
    kernels.sort(key=lambda x: x['start_time'])
    return kernels


def collect_kernel_semantics(config: dict) -> dict:
    semantics = {}

    def _collect_from_node(node: dict, parent_path: str = ''):
        name = node.get('name', '')
        path = f"{parent_path}/{name}" if parent_path else name

        for ks in node.get('kernels', []):
            idx = ks.get('index')
            if idx is not None:
                semantics[idx] = {
                    'semantic': ks.get('semantic', '') or ks.get('comment', ''),
                    'shape_semantic': ks.get('shape_semantic', ''),
                    'code_ref': ks.get('code_ref', ''),
                    'path': path
                }

        for child in node.get('children', []):
            _collect_from_node(child, path)

    for stage_name, stage_info in config.get('stages', {}).items():
        _collect_from_node(stage_info)

    for layer_type, structure in config.get('layer_structure', {}).items():
        _collect_from_node(structure)

    for layer_type, structure in config.get('structures', {}).items():  # v2
        _collect_from_node(structure)

    for aux in config.get('runtime_auxiliary', []):
        _collect_from_node(aux)

    return semantics


def format_field_display(key: str, value) -> str:
    if value is None or value == '' or value == 'N/A':
        return ''

    if isinstance(value, float):
        if '_ratio' in key:
            return f'{value * 100:.1f}%'
        if '_time' in key or key == 'duration_us' or key == 'start_time_us':
            return f'{value:.3f} us'
        if key.endswith('_pct') or key == 'cube_utilization_pct':
            return f'{value:.1f}%'
        return f'{value:.3f}'

    if isinstance(value, int):
        return str(value)

    s = str(value)
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    return s


FIELD_DISPLAY_NAMES = {
    'name': 'Name',
    'type': 'Type',
    'duration_us': 'Duration',
    'start_time_us': 'Start Time',
    'stream_id': 'Stream',
    'device_id': 'Device',
    'task_id': 'Task ID',
    'op_state': 'OP State',
    'accelerator_core': 'Accelerator Core',
    'wait_time_us': 'Wait Time',
    'block_dim': 'Block Dim',
    'mix_block_dim': 'Mix Block Dim',
    'hf32_eligible': 'HF32 Eligible',
    'input_shapes': 'Input Shapes',
    'input_data_types': 'Input Types',
    'input_formats': 'Input Formats',
    'output_shapes': 'Output Shapes',
    'output_data_types': 'Output Types',
    'output_formats': 'Output Formats',
    'context_id': 'Context ID',
    'aicore_time_us': 'AI Core Time',
    'aic_total_cycles': 'AI Core Cycles',
    'aic_mac_time_us': 'MAC Time',
    'aic_mac_ratio': 'MAC Ratio',
    'aic_scalar_time_us': 'Scalar Time',
    'aic_scalar_ratio': 'Scalar Ratio',
    'aic_mte1_time_us': 'MTE1 Time',
    'aic_mte1_ratio': 'MTE1 Ratio',
    'aic_mte2_time_us': 'MTE2 Time',
    'aic_mte2_ratio': 'MTE2 Ratio',
    'aic_fixpipe_time_us': 'FixPipe Time',
    'aic_fixpipe_ratio': 'FixPipe Ratio',
    'aic_icache_miss_rate': 'AI Core ICache Miss',
    'aiv_time_us': 'AI Vector Time',
    'aiv_total_cycles': 'AI Vector Cycles',
    'aiv_vec_time_us': 'Vector Time',
    'aiv_vec_ratio': 'Vector Ratio',
    'aiv_scalar_time_us': 'AIV Scalar Time',
    'aiv_scalar_ratio': 'AIV Scalar Ratio',
    'aiv_mte2_time_us': 'AIV MTE2 Time',
    'aiv_mte2_ratio': 'AIV MTE2 Ratio',
    'aiv_mte3_time_us': 'AIV MTE3 Time',
    'aiv_mte3_ratio': 'AIV MTE3 Ratio',
    'aiv_icache_miss_rate': 'AIV ICache Miss',
    'cube_utilization_pct': 'Cube Utilization',
    'aic_mac_fp16_ratio': 'MAC FP16 Ratio',
    'aic_mac_int8_ratio': 'MAC INT8 Ratio',
    'aic_cube_fops': 'Cube FLOPs',
    'aiv_vec_fp32_ratio': 'Vec FP32 Ratio',
    'aiv_vec_fp16_ratio': 'Vec FP16 Ratio',
    'aiv_vec_int32_ratio': 'Vec INT32 Ratio',
    'aiv_vec_misc_ratio': 'Vec Misc Ratio',
    'aiv_vector_fops': 'Vector FLOPs',
    'model_id': 'Model ID',
}

TOOLTIP_FIELD_ORDER = [
    'name', 'type', 'op_state', 'accelerator_core',
    'duration_us', 'start_time_us', 'wait_time_us',
    'stream_id', 'device_id', 'task_id', 'block_dim', 'mix_block_dim',
    'input_shapes', 'input_data_types', 'input_formats',
    'output_shapes', 'output_data_types', 'output_formats',
    'hf32_eligible', 'context_id',
    'aicore_time_us', 'aic_total_cycles',
    'aic_mac_time_us', 'aic_mac_ratio',
    'aic_scalar_time_us', 'aic_scalar_ratio',
    'aic_mte1_time_us', 'aic_mte1_ratio',
    'aic_mte2_time_us', 'aic_mte2_ratio',
    'aic_fixpipe_time_us', 'aic_fixpipe_ratio',
    'aic_icache_miss_rate',
    'cube_utilization_pct',
    'aic_mac_fp16_ratio', 'aic_mac_int8_ratio', 'aic_cube_fops',
    'aiv_time_us', 'aiv_total_cycles',
    'aiv_vec_time_us', 'aiv_vec_ratio',
    'aiv_scalar_time_us', 'aiv_scalar_ratio',
    'aiv_mte2_time_us', 'aiv_mte2_ratio',
    'aiv_mte3_time_us', 'aiv_mte3_ratio',
    'aiv_icache_miss_rate',
    'aiv_vec_fp32_ratio', 'aiv_vec_fp16_ratio',
    'aiv_vec_int32_ratio', 'aiv_vec_misc_ratio',
    'aiv_vector_fops',
]

DEFAULT_KERNEL_DISPLAY_FIELDS = [
    'stream_id', 'input_shapes', 'output_shapes'
]

KERNEL_FIELD_LABELS = {
    'input_shapes': 'Input',
    'output_shapes': 'Output',
    'type': 'Type',
    'stream_id': 'Stream',
    'device_id': 'Device',
    'task_id': 'Task ID',
    'start_time_us': 'Start',
    'duration_us': 'Duration',
    'wait_time_us': 'Wait',
    'op_state': 'State',
    'accelerator_core': 'Acc Core',
    'block_dim': 'Block Dim',
    'input_data_types': 'In DType',
    'output_data_types': 'Out DType',
    'input_formats': 'In Fmt',
    'output_formats': 'Out Fmt',
}

ALL_KERNEL_META_FIELDS = [
    'stream_id', 'input_shapes', 'output_shapes',
    'start_time_us', 'duration_us', 'wait_time_us',
    'device_id', 'task_id', 'type', 'op_state',
    'accelerator_core', 'block_dim',
    'input_data_types', 'output_data_types', 'input_formats', 'output_formats',
]


def get_kernel_field_value(kernel: dict, field_key: str, multiplier: int, total_duration: float) -> str:
    if field_key == 'duration_us':
        k_duration_raw = kernel.get('duration', 0)
        raw_str = kernel.get('duration_raw', '')
        if raw_str:
            return f'{raw_str} us'
        return f'{format_duration_us(k_duration_raw)} us'

    if field_key == 'start_time_us':
        raw_str = kernel.get('start_time_raw', '')
        if raw_str:
            return f'{raw_str} us'
        return f'{format_duration_us(kernel.get("start_time", 0))} us'

    if field_key == 'type':
        return kernel.get('task_type', '') or kernel.get('all_fields', {}).get('type', 'N/A')

    if field_key in ('input_shapes', 'output_shapes', 'input_data_types', 'output_data_types', 'input_formats', 'output_formats'):
        val = kernel.get(field_key) or kernel.get('all_fields', {}).get(field_key, 'N/A')
        if val and len(str(val)) > 50:
            return str(val)[:47] + '...'
        return str(val) if val else 'N/A'

    if field_key == 'stream_id':
        return str(kernel.get('stream_id', '') or kernel.get('all_fields', {}).get('stream_id', 'N/A'))

    all_fields = kernel.get('all_fields', {})
    if field_key in all_fields:
        val = all_fields[field_key]
        raw_key = f'{field_key}_raw'
        if raw_key in all_fields:
            return str(all_fields[raw_key])
        if val is None:
            return 'N/A'
        return str(format_field_display(field_key, val))

    if field_key in kernel:
        val = kernel[field_key]
        if val is None:
            return 'N/A'
        return str(format_field_display(field_key, val))

    return 'N/A'


def collect_all_op_indices(node: dict) -> list:
    indices = list(node.get('_report_op_indices', node.get('op_indices', [])))
    for child in node.get('children', []):
        indices.extend(collect_all_op_indices(child))
    return indices


def count_all_kernels(node: dict, operators: list) -> int:
    return len(collect_all_op_indices(node))


def get_node_time_span_info(node: dict, operators: list) -> dict:
    all_op_indices = collect_all_op_indices(node)
    op_dict = {op['index']: op for op in operators}

    if not all_op_indices:
        return {'time_span': 0, 'streams': {}, 'stream_info': '', 'stream_hover': '', 'calculation': '', 'stream_count': 0}

    ops = [op_dict[i] for i in all_op_indices if i in op_dict]

    if not ops:
        return {'time_span': 0, 'streams': {}, 'stream_info': '', 'stream_hover': '', 'calculation': '', 'stream_count': 0}

    def get_op_name(op):
        return op.get('normalized_name') or op.get('type') or op.get('name', 'Unknown')

    earliest_op = min(ops, key=lambda op: op.get('start_time_us', 0))
    min_start = earliest_op.get('start_time_us', 0)
    earliest_name = get_op_name(earliest_op)

    max_end = min_start
    latest_op = None
    for op in ops:
        end_time = op.get('start_time_us', 0) + op.get('duration_us', 0)
        if end_time > max_end:
            max_end = end_time
            latest_op = op

    latest_name = get_op_name(latest_op) if latest_op else 'Unknown'
    latest_start = latest_op.get('start_time_us', 0) if latest_op else 0
    latest_duration = latest_op.get('duration_us', 0) if latest_op else 0

    if len(ops) == 1:
        time_span = ops[0].get('duration_us', 0)
    else:
        time_span = round(max_end - min_start, 2)

    stream_counts = {}
    for op in ops:
        sid = op.get('stream_id', 'unknown')
        stream_counts[sid] = stream_counts.get(sid, 0) + 1

    stream_count = len(stream_counts)
    stream_info = f"{stream_count} streams"
    stream_hover = '&#10;'.join([f"Stream {sid}: {cnt}" for sid, cnt in sorted(stream_counts.items(), key=lambda x: -x[1])])
    calculation = f"{latest_name}({latest_start:.2f}+{latest_duration:.2f}) - {earliest_name}({min_start:.2f}) = {time_span:.2f} us"

    return {
        'time_span': time_span,
        'streams': stream_counts,
        'stream_info': stream_info,
        'stream_hover': stream_hover,
        'stream_count': stream_count,
        'calculation': calculation,
    }


def get_unique_kernels(kernels: list) -> list:
    seen = set()
    unique = []
    for k in kernels:
        if k not in seen:
            seen.add(k)
            unique.append(k)
    return unique


def format_duration_us(duration: float) -> str:
    return f"{duration:.2f}"


def format_duration_ms(duration: float) -> str:
    return f"{duration / 1000:.2f}"


def format_percentage(duration: float, total: float) -> str:
    if total == 0:
        return "0.00"
    return f"{duration / total * 100:.2f}"

def get_node_total_duration(node: dict, operators: list) -> float:
    indices = node.get('_report_op_indices', node.get('op_indices', []))
    duration = get_duration_by_indices(operators, indices)
    for child in node.get('children', []):
        duration += get_node_total_duration(child, operators)
    return duration


def get_report_kernel_details(node: dict, operators: list) -> list:
    """Return exact aggregate timing per representative kernel position."""
    groups = node.get('_report_op_groups')
    if groups is None:
        return get_kernel_details_by_indices(operators, node.get('op_indices', []))
    op_dict = {op['index']: op for op in operators}
    details = []
    for group in groups:
        ops = [op_dict[i] for i in group if i in op_dict]
        if not ops:
            continue
        op = ops[0]
        details.append({
            'name': op.get('normalized_name') or op.get('type') or op.get('name', 'Unknown'),
            'duration': sum(bc.effective_duration_us(item) for item in ops),
            'index': op.get('index'),
        })
    details.sort(key=lambda item: -item['duration'])
    return details


def get_report_kernel_full_details(node: dict, operators: list) -> list:
    """Keep one detail row per template position, with exact aggregate duration."""
    groups = node.get('_report_op_groups')
    if groups is None:
        return get_kernel_full_details_by_indices(operators, node.get('op_indices', []))
    op_dict = {op['index']: op for op in operators}
    details = []
    for group in groups:
        present = [i for i in group if i in op_dict]
        if not present:
            continue
        detail = get_kernel_full_details_by_indices(operators, [present[0]])[0]
        detail['duration'] = sum(bc.effective_duration_us(op_dict[i]) for i in present)
        detail['aggregate_count'] = len(present)
        details.append(detail)
    details.sort(key=lambda item: -item['duration'])
    return details


def _count_suffix(multiplier: int, count_label: str) -> str:
    """Multiplier suffix. v1 decoder layers -> '(*N层)'; v2 -> '(×N invocations)'
    so a repeated MTP invocation is never mislabeled as N model layers."""
    if multiplier <= 1:
        return ""
    if count_label == '层':
        return f" (*{multiplier}层)"
    return f" (×{multiplier} {count_label})"


def collect_timing_tree_lines(node: dict, operators: list, total_duration: float, multiplier: int,
                               indent: str, is_last: bool, align_col: int,
                               current_depth: int, max_depth: int,
                               count_label: str = '层') -> List[str]:
    lines = []
    name = node.get('name', 'Unknown')
    op_indices = node.get('op_indices', [])
    children = node.get('children', [])

    is_exact_aggregate = '_report_op_indices' in node
    effective_multiplier = 1 if is_exact_aggregate else multiplier
    own_indices = node.get('_report_op_indices', op_indices)
    duration = get_duration_by_indices(operators, own_indices) * effective_multiplier
    for child in children:
        child_multiplier = 1 if '_report_op_indices' in child else multiplier
        duration += get_node_total_duration(child, operators) * child_multiplier

    count_str = _count_suffix(multiplier, count_label) if current_depth == 1 else ""

    percentage = format_percentage(duration, total_duration)
    duration_str = f"{format_duration_us(duration)} us ({format_duration_ms(duration)} ms, {percentage}%)"

    if current_depth == 0:
        name_padded = (name + count_str).ljust(align_col)
        lines.append(f"{name_padded}{duration_str}")
    else:
        prefix = "└── " if is_last else "├── "
        full_prefix = indent + prefix
        name_padded = (name + count_str).ljust(align_col - len(full_prefix))
        lines.append(f"{full_prefix}{name_padded}{duration_str}")

    new_indent = indent + ("    " if is_last else "│   ")

    if current_depth >= max_depth:
        kernel_details = get_report_kernel_details(node, operators)
        for i, k in enumerate(kernel_details):
            k_duration = k['duration'] * effective_multiplier
            k_pct = format_percentage(k_duration, total_duration)
            k_dur_str = f"{format_duration_us(k_duration)} us ({format_duration_ms(k_duration)} ms, {k_pct}%)"
            k_is_last = (i == len(kernel_details) - 1)
            k_prefix = new_indent + ("└── " if k_is_last else "├── ")
            k_name_padded = k['name'].ljust(align_col - len(k_prefix))
            lines.append(f"{k_prefix}{k_name_padded}{k_dur_str}")
        return lines

    if op_indices and not children:
        kernel_details = get_report_kernel_details(node, operators)
        for i, k in enumerate(kernel_details):
            k_duration = k['duration'] * effective_multiplier
            k_pct = format_percentage(k_duration, total_duration)
            k_dur_str = f"{format_duration_us(k_duration)} us ({format_duration_ms(k_duration)} ms, {k_pct}%)"
            k_is_last = (i == len(kernel_details) - 1)
            k_prefix = new_indent + ("└── " if k_is_last else "├── ")
            k_name_padded = k['name'].ljust(align_col - len(k_prefix))
            lines.append(f"{k_prefix}{k_name_padded}{k_dur_str}")

    for i, child in enumerate(children):
        is_child_last = (i == len(children) - 1)
        lines.extend(collect_timing_tree_lines(child, operators, total_duration, multiplier,
                                               new_indent, is_child_last, align_col,
                                               current_depth + 1, max_depth, count_label))

    return lines


def collect_node_stats(node: dict, operators: list) -> tuple:
    duration = get_duration_by_indices(operators, node.get('op_indices', []))
    kernels = get_kernels_by_indices(operators, node.get('op_indices', []))

    for child in node.get('children', []):
        child_duration, child_kernels = collect_node_stats(child, operators)
        duration += child_duration
        kernels.extend(child_kernels)

    return duration, kernels


def collect_all_kernels(node: dict, operators: list) -> list:
    kernels = get_kernels_by_indices(operators, node.get('op_indices', []))
    for child in node.get('children', []):
        kernels.extend(collect_all_kernels(child, operators))
    return kernels


def collect_child_modules(node: dict, operators: list, multiplier: int) -> list:
    modules = []

    op_indices = node.get('op_indices', [])
    if op_indices:
        duration = get_duration_by_indices(operators, op_indices)
        kernels = get_kernels_by_indices(operators, op_indices)
        modules.append({
            'name': node.get('name', 'Unknown'),
            'count': multiplier,
            'kernels_per_pass': len(kernels),
            'total_kernels': len(kernels) * multiplier,
            'total_duration': duration * multiplier,
        })

    for child in node.get('children', []):
        modules.extend(collect_child_modules(child, operators, multiplier))

    return modules


def collect_child_modules_with_kernels(node: dict, operators: list, multiplier: int, level: int, start_order: int) -> Tuple[list, list]:
    modules = []
    kernel_modules = []
    order = start_order

    children = node.get('children', [])
    for i, child in enumerate(children):
        child_name = child.get('name', 'Unknown')
        child_op_indices = child.get('op_indices', [])
        child_children = child.get('children', [])

        if child_op_indices and not child_children:
            kernel_details = get_kernel_details_by_indices(operators, child_op_indices)
            for kd in kernel_details:
                kernel_modules.append({
                    'module_name': child_name,
                    'kernel_name': kd['name'],
                    'level': level + 1,
                    'duration': kd['duration'] * multiplier,
                    'count': multiplier,
                })

        child_duration = get_duration_by_indices(operators, child_op_indices)
        for sub_child in child_children:
            child_duration += get_node_total_duration(sub_child, operators)

        child_kernels = get_kernels_by_indices(operators, child_op_indices)
        for sub_child in child_children:
            _, sub_kernels = collect_node_stats(sub_child, operators)
            child_kernels.extend(sub_kernels)

        modules.append({
            'name': child_name,
            'level': level,
            'order': order,
            'count': multiplier,
            'kernels_per_pass': len(child_kernels),
            'total_kernels': len(child_kernels) * multiplier,
            'total_duration': child_duration * multiplier,
        })
        order += 1

        sub_modules, sub_kernels = collect_child_modules_with_kernels(child, operators, multiplier, level + 1, order)
        modules.extend(sub_modules)
        kernel_modules.extend(sub_kernels)
        order += len(sub_modules)

    return modules, kernel_modules


def _fmt_layer_span(group: dict) -> str:
    if group.get('model_layer_indices'):
        idxs = group['model_layer_indices']
        if len(idxs) > 6:
            runs = []
            start = previous = idxs[0]
            for index in idxs[1:]:
                if index == previous + 1:
                    previous = index
                    continue
                runs.append((start, previous))
                start = previous = index
            runs.append((start, previous))
            spans = [str(start) if start == end else f"{start}..{end}"
                     for start, end in runs]
            return f"[{', '.join(spans)}] ({len(idxs)} layers)"
        return str(idxs)
    rng = group.get('model_layer_range')
    if rng:
        return f"[{rng[0]}..{rng[1]}] ({rng[1] - rng[0] + 1} layers)"
    return "unknown"


def generate_architecture_section(config: dict) -> str:
    """Schema-v2: global learned architecture, shown SEPARATELY from observed execution.

    MTP/prediction modules are labelled '1 learned layer, N invocations' — never 'N layers'.
    """
    arch = config.get('architecture') or {}
    scope = config.get('trace_scope') or {}
    lines = ["## 全局模型架构（learned architecture）", ""]
    lines.append(f"- num_main_layers: {arch.get('num_main_layers', 'unknown')}")
    lines.append("")
    lines.append("| layer group | 分类 | 模型层号 | 源码证据 |")
    lines.append("|---|---|---|---|")
    for g in arch.get('layer_groups', []):
        lines.append(f"| {g.get('type')} | {g.get('classification', 'unknown')} | "
                     f"{_fmt_layer_span(g)} | `{g.get('source_ref', 'unknown')}` |")
    lines.append("")

    # execution counts derived from trace instances (per learned layer)
    exec_counts = {}
    for inst in config.get('trace_instances', []) or []:
        mli = inst.get('model_layer_index')
        exec_counts[mli] = exec_counts.get(mli, 0) + 1

    pms = arch.get('prediction_modules', []) or []
    if pms:
        lines.append("### 预测模块 / MTP（learned vs invocations）")
        lines.append("")
        lines.append("| 模块 | learned layers | 观测 invocations | 模型层号 |")
        lines.append("|---|---|---|---|")
        for pm in pms:
            learned = pm.get('learned_module_count', 'unknown')
            idxs = pm.get('model_layer_indices', [])
            inv = sum(exec_counts.get(i, 0) for i in idxs)
            lines.append(f"| {pm.get('type')} | {learned} learned layer"
                         f"{'s' if isinstance(learned, int) and learned != 1 else ''} | "
                         f"{inv} invocations | {idxs} |")
        lines.append("")
        lines.append("> 注意：MTP 外层循环多次调用同一个学习到的 decoder layer，"
                     "报告按 “N learned layer(s), M invocations” 计数，**不**表示 M 个模型层。")
        lines.append("")

    # Capture scope. `trace_scope` is optional, so an absent one is reported as unproven
    # rather than skipped -- silence here would read as "full model" to anyone skimming.
    lines.append("## 当前 trace 范围（observed execution）")
    lines.append("")
    if scope:
        lines.append(f"- trace_scope.kind: **{scope.get('kind', 'unknown')}** "
                     f"(confidence: {scope.get('confidence', 'unknown')})")
        if scope.get('rank') is not None:
            lines.append(f"- rank: {scope.get('rank')}")
        if scope.get('pipeline_stage') is not None:
            lines.append(f"- pipeline_stage: {scope.get('pipeline_stage')}")
        par = scope.get('parallelism') or {}
        if par:
            lines.append(f"- parallelism: {par}")
        ev = scope.get('evidence') or []
        if ev:
            lines.append(f"- evidence: {ev}")
    else:
        lines.append("- trace_scope: **未声明**（该字段可选）")

    # Report what was actually observed, so a partial capture is visible even with no
    # `trace_scope` to describe it.
    # Range-based groups declare their layers as [lo, hi], not as an explicit index list.
    # Collecting only `model_layer_indices` dropped every such group from the declared set --
    # a 58-layer MoE stack counted as 0 -- so the coverage line read "已声明模型层: 4" for a
    # 61-layer model and the unobserved list showed 1 layer instead of 55.
    declared_layers = set()
    for group in list(arch.get('layer_groups') or []) + pms:
        declared_layers.update(bc.expand_layer_group_indices(group))
    observed_layers = {inst.get('model_layer_index')
                       for inst in config.get('trace_instances') or []}
    observed_layers.discard(None)
    unobserved = sorted(i for i in declared_layers
                        if isinstance(i, int) and i not in observed_layers)
    if declared_layers:
        lines.append(f"- 已声明模型层: {len(declared_layers)}；本次采集观测到: "
                     f"{len(observed_layers & declared_layers)}")
    if unobserved:
        lines.append(f"- **未采集到的模型层**: {unobserved}")

    if scope.get('kind') != 'full_model' or unobserved:
        lines.append("")
        lines.append("> 性能数据 **仅覆盖本次采集到的范围**。未观测到的层、rank 或 stage "
                     "**不得** 按代表层耗时外推或复制指标；报告中这些节点显示为未采集，"
                     "而不是估算值。")
    lines.append("")
    return '\n'.join(lines)


def generate_analysis_section(config: dict, operators: list, total_duration: float, max_depth: int = 4) -> str:
    model_name = config.get('model_name', 'Model')
    model_duration = sum(bc.effective_duration_us(op) for op in operators)

    temp_lines = []

    percentage = format_percentage(model_duration, total_duration)
    temp_lines.append((model_name, f"{format_duration_us(model_duration)} us ({format_duration_ms(model_duration)} ms, {percentage}%)"))

    stages = config.get('stages', {})
    for stage_name, stage_info in stages.items():
        stage_indices = stage_info.get('stage_indices', [0])
        stage_count = len(stage_indices) if stage_indices else 1
        temp_lines.append((stage_info.get('name', stage_name), stage_count, stage_info, False, 'stage'))

    is_v2 = config.get('schema_version') == 2
    layer_label = 'invocations' if is_v2 else '层'
    for name, structure, count in iter_layer_sections(config):
        temp_lines.append((name, count, structure, False, 'layer'))

    runtime_aux = config.get('runtime_auxiliary', [])
    for aux in runtime_aux:
        temp_lines.append((aux.get('name', 'runtime_aux'), 1, aux, False, 'aux'))

    max_name_len = 0
    for item in temp_lines:
        if len(item) == 2:
            max_name_len = max(max_name_len, len(item[0]))
        else:
            name, count, _node, _is_last, item_type = item
            count_str = _count_suffix(count, layer_label) if item_type == 'layer' else ""
            instance_str = f" (*{count}实例)" if count > 1 and item_type in ('stage', 'aux') else ""
            max_name_len = max(max_name_len, len(name) + len(count_str) + len(instance_str))

    align_col = max(max_name_len + 2, 40)

    lines = ["## 模型性能分析", "", "```text"]

    for item_idx, item in enumerate(temp_lines):
        if len(item) == 2:
            name_padded = item[0].ljust(align_col)
            lines.append(f"{name_padded}{item[1]}")
        else:
            name, count, node, _is_last, item_type = item
            is_last = (item_idx == len(temp_lines) - 1)
            clabel = layer_label if item_type == 'layer' else '实例'
            lines.extend(collect_timing_tree_lines(node, operators, total_duration, count,
                                                     "", is_last, align_col, 1, max_depth, clabel))

    lines.append("```")
    lines.append("")
    return '\n'.join(lines)


def get_html_css() -> str:
    return '''
    <style>
    :root {
        --bg-primary: #1e1e1e;
        --bg-secondary: #252526;
        --bg-tertiary: #2d2d2d;
        --bg-hover: #2d2d2d;
        --text-primary: #d4d4d4;
        --text-secondary: #808080;
        --accent-blue: #4fc1ff;
        --accent-green: #6a9955;
        --accent-orange: #ce9178;
        --border-color: #3c3c3c;
        --button-bg: #0e639c;
        --button-hover: #1177bb;
        --tooltip-bg: #1e1e2e;
        --tooltip-border: #45475a;
    }
    [data-theme="dracula"] {
        --bg-primary: #282a36;
        --bg-secondary: #21222c;
        --bg-tertiary: #343746;
        --bg-hover: #44475a;
        --text-primary: #f8f8f2;
        --text-secondary: #6272a4;
        --accent-blue: #8be9fd;
        --accent-green: #50fa7b;
        --accent-orange: #ffb86c;
        --border-color: #44475a;
        --button-bg: #bd93f9;
        --button-hover: #ff79c6;
        --tooltip-bg: #1d1e26;
        --tooltip-border: #6272a4;
    }
    [data-theme="one-dark"] {
        --bg-primary: #282c34;
        --bg-secondary: #21252b;
        --bg-tertiary: #2c313a;
        --bg-hover: #2c313a;
        --text-primary: #abb2bf;
        --text-secondary: #5c6370;
        --accent-blue: #61afef;
        --accent-green: #98c379;
        --accent-orange: #d19a66;
        --border-color: #181a1f;
        --button-bg: #4d78cc;
        --button-hover: #528bff;
        --tooltip-bg: #21252b;
        --tooltip-border: #5c6370;
    }
    [data-theme="github-light"] {
        --bg-primary: #ffffff;
        --bg-secondary: #f6f8fa;
        --bg-tertiary: #f0f2f5;
        --bg-hover: #eaeef2;
        --text-primary: #1f2328;
        --text-secondary: #656d76;
        --accent-blue: #0969da;
        --accent-green: #1a7f37;
        --accent-orange: #bc4c00;
        --border-color: #d1d9e0;
        --button-bg: #0969da;
        --button-hover: #0550ae;
        --tooltip-bg: #f6f8fa;
        --tooltip-border: #d1d9e0;
    }
    [data-theme="solarized-light"] {
        --bg-primary: #fdf6e3;
        --bg-secondary: #eee8d5;
        --bg-tertiary: #e8e1cc;
        --bg-hover: #e0dac7;
        --text-primary: #073642;
        --text-secondary: #839496;
        --accent-blue: #268bd2;
        --accent-green: #859900;
        --accent-orange: #cb4b16;
        --border-color: #d3cbb7;
        --button-bg: #268bd2;
        --button-hover: #1a6da8;
        --tooltip-bg: #eee8d5;
        --tooltip-border: #839496;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: 'Segoe UI', 'SF Pro Display', -apple-system, sans-serif;
        background: var(--bg-primary);
        color: var(--text-primary);
        line-height: 1.6;
        padding: 40px;
        max-width: 1600px;
        margin: 0 auto;
    }
    h1 { font-size: 28px; margin-bottom: 20px; color: var(--text-primary); border-bottom: 2px solid var(--border-color); padding-bottom: 15px; }
    .gate-banner {
        background: var(--bg-tertiary);
        border-left: 4px solid var(--accent-green);
        padding: 12px 18px;
        border-radius: 6px;
        margin-bottom: 16px;
    }
    .gate-banner-override {
        border-left-color: var(--accent-orange);
        background: rgba(206, 145, 120, 0.10);
    }
    .gate-banner-title {
        font-weight: 600;
        color: var(--accent-blue);
        margin-bottom: 6px;
    }
    .gate-banner ul { margin: 0; padding-left: 20px; }
    .gate-banner li { margin: 3px 0; color: var(--text-primary); }
    .gate-banner-override strong { color: var(--accent-orange); }
    .metadata {
        background: var(--bg-tertiary);
        padding: 15px 20px;
        border-radius: 8px;
        margin-bottom: 20px;
        display: flex;
        flex-direction: column;
        gap: 12px;
    }
    .meta-row { display: flex; flex-wrap: wrap; gap: 25px; }
    .meta-item { display: flex; gap: 8px; align-items: center; }
    .meta-label { color: var(--text-secondary); font-size: 13px; }
    .meta-value { color: var(--text-primary); font-family: 'Consolas', monospace; font-size: 13px; }
    .meta-datasources { display: flex; flex-direction: column; gap: 4px; margin-left: 20px; }
    .meta-datasource-item {
        display: flex;
        gap: 12px;
        align-items: baseline;
        color: var(--text-primary);
        font-family: 'Consolas', monospace;
        font-size: 12px;
    }
    .meta-datasource-item .step-badge {
        background: var(--button-bg);
        color: #fff;
        padding: 1px 6px;
        border-radius: 3px;
        font-size: 11px;
    }
    .kernel-fields-config {
        position: relative;
        display: inline-block;
    }
    .kernel-fields-panel {
        position: absolute;
        top: 100%;
        left: 0;
        background: var(--bg-tertiary);
        border: 1px solid var(--border-color);
        border-radius: 6px;
        padding: 12px;
        min-width: 200px;
        z-index: 1000;
        display: none;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        margin-top: 4px;
    }
    .kernel-fields-panel.visible {
        display: block;
    }
    .kernel-fields-panel label {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 4px 0;
        cursor: pointer;
        font-size: 13px;
        color: var(--text-primary);
    }
    .kernel-fields-panel input[type="checkbox"] {
        cursor: pointer;
    }
    .kernel-fields-actions {
        display: flex;
        gap: 8px;
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px solid var(--border-color);
    }
    .kernel-fields-actions button {
        flex: 1;
        padding: 4px 8px;
        font-size: 11px;
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        color: var(--text-primary);
        border-radius: 3px;
        cursor: pointer;
    }
    .kernel-fields-actions button:hover {
        background: var(--bg-hover);
    }
    .controls {
        background: var(--bg-tertiary);
        padding: 15px 20px;
        border-radius: 8px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 15px;
        flex-wrap: wrap;
    }
    .controls label { display: flex; align-items: center; gap: 8px; color: var(--text-secondary); font-size: 13px; }
    .controls select {
        background: var(--bg-secondary);
        color: var(--text-primary);
        border: 1px solid var(--border-color);
        padding: 6px 12px;
        border-radius: 4px;
        font-size: 13px;
        cursor: pointer;
    }
    .controls button {
        background: var(--button-bg);
        color: #ffffff;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 13px;
        transition: background 0.2s;
    }
    .controls button:hover { background: var(--button-hover); }
    .tree { background: var(--bg-secondary); border-radius: 8px; padding: 20px; position: relative; }
    .tree-root { list-style: none; }
    .tree-children { list-style: none; padding-left: 24px; overflow: hidden; transition: max-height 0.25s ease-out; }
    .tree-node.collapsed > .tree-children { max-height: 0; }
    .tree-node.expanded > .tree-children { max-height: 50000px; }
    .node-header {
        display: flex;
        align-items: center;
        padding: 5px 10px;
        border-radius: 4px;
        cursor: pointer;
        transition: background 0.15s;
        flex-wrap: wrap;
    }
    .node-header:hover { background: var(--bg-hover); }
    .node-toggle {
        width: 16px;
        font-size: 10px;
        color: var(--text-secondary);
        text-align: center;
        flex-shrink: 0;
        transition: transform 0.2s;
    }
    .tree-node.collapsed > .node-header .node-toggle { transform: rotate(0deg); }
    .tree-node.expanded > .node-header .node-toggle { transform: rotate(90deg); }
    .tree-node.leaf > .node-header .node-toggle { visibility: hidden; }
    .tree-node.kernel-only > .node-header .node-toggle { visibility: hidden; }
    .node-name {
        flex: 1;
        margin-left: 8px;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 14px;
        min-width: 150px;
    }
    .node-semantic {
        color: var(--accent-orange);
        font-size: 11px;
        font-style: italic;
        font-weight: normal;
        margin-left: 6px;
    }
    .node-semantic-wrapper {
        display: inline-flex;
        align-items: center;
        color: var(--accent-orange);
        font-size: 11px;
        font-style: italic;
        margin-left: 6px;
    }
    .node-semantic-truncated {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        max-width: 400px;
    }
    .node-semantic-full {
        display: none;
    }
    .node-semantic-wrapper.expanded .node-semantic-truncated {
        display: none;
    }
    .node-semantic-wrapper.expanded .node-semantic-full {
        display: inline;
        white-space: normal;
    }
    .semantic-expand-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        margin-left: 4px;
        flex-shrink: 0;
        user-select: none;
        width: 18px;
        height: 18px;
        border: none;
        border-radius: 3px;
        background: var(--accent-orange);
        padding: 0;
        transition: background 0.15s;
    }
    .semantic-expand-btn svg {
        width: 12px;
        height: 12px;
        fill: var(--bg-primary);
        transition: transform 0.2s;
    }
    .node-semantic-wrapper.expanded .semantic-expand-btn {
        background: var(--accent-blue);
    }
    .node-semantic-wrapper.expanded .semantic-expand-btn svg {
        transform: rotate(180deg);
    }
    .semantic-expand-btn:hover {
        opacity: 0.85;
    }
    .kernel-semantic {
        color: var(--accent-orange);
        font-size: 11px;
        font-style: italic;
        margin-left: 4px;
    }
    .kernel-count, .stream-count {
        color: var(--text-secondary);
        font-size: 11px;
        margin-left: 4px;
    }
    .tree-node.hidden-kernel {
        display: none;
    }
    .kernel-meta {
        color: var(--text-secondary);
        font-size: 11px;
        margin-left: 28px;
        width: calc(100% - 28px);
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 2px 16px;
        font-family: 'Consolas', monospace;
    }
    .kernel-meta-item {
        display: flex;
        align-items: flex-start;
        gap: 4px;
        min-width: 0;
    }
    .kernel-meta-label {
        color: var(--text-secondary);
        flex-shrink: 0;
    }
    .kernel-meta-value {
        color: var(--text-primary);
        word-break: break-all;
        overflow-wrap: break-word;
    }
    .kernel-meta-item.shape-semantic-tip {
        position: relative;
        cursor: help;
    }
    .kernel-meta-item.shape-semantic-tip::after {
        content: attr(data-shape-semantic);
        position: absolute;
        bottom: calc(100% + 5px);
        left: 0;
        background: rgba(20,22,34,0.97);
        color: #e8c77a;
        border: 1px solid rgba(232,199,122,0.35);
        padding: 5px 9px;
        border-radius: 5px;
        font-size: 11px;
        font-family: 'Consolas', monospace;
        white-space: normal;
        max-width: 480px;
        min-width: 180px;
        pointer-events: none;
        opacity: 0;
        transition: opacity 0.15s;
        z-index: 300;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        line-height: 1.5;
    }
    .kernel-meta-item.shape-semantic-tip:hover::after {
        opacity: 1;
    }
    .node-duration {
        text-align: right;
        min-width: 200px;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 12px;
        display: flex;
        justify-content: flex-end;
        gap: 6px;
    }
    .duration-us { color: var(--accent-green); }
    .duration-ms { color: var(--accent-orange); font-size: 11px; }
    .duration-pct { color: var(--accent-blue); font-weight: bold; min-width: 65px; }
    .ratio-cube { color: #e5c07b; font-size: 11px; min-width: 64px; text-align: right; }
    .ratio-vec  { color: #56b6c2; font-size: 11px; min-width: 58px; text-align: right; }
    .ratio-comm { color: #e06c75; font-size: 11px; min-width: 66px; text-align: right; }
    .tree-node[data-type="kernel"] .node-name {
        color: var(--accent-blue);
        font-style: italic;
        font-size: 13px;
        max-width: 200px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .tree-node[data-type="kernel"] .node-duration {
        margin-left: auto;
    }
    .kernel-info-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 18px;
        height: 18px;
        background: var(--accent-blue);
        color: #fff;
        border-radius: 50%;
        cursor: pointer;
        margin-left: 4px;
        flex-shrink: 0;
        user-select: none;
        border-bottom: none;
        padding: 0;
        border: none;
    }
    .kernel-info-btn svg {
        width: 12px;
        height: 12px;
        fill: #fff;
    }
    .kernel-info-btn:hover {
        opacity: 0.8;
    }
    .node-header[title] { cursor: help; }
    .node-spacer { width: 16px; flex-shrink: 0; }
    .tree-node.leaf > .node-header { cursor: pointer; }

    /* Kernel Tooltip Styles */
    .kernel-tooltip {
        position: fixed;
        background: var(--tooltip-bg);
        border: 1px solid var(--tooltip-border);
        border-radius: 8px;
        padding: 12px 16px;
        max-width: 1200px;
        max-height: 80vh;
        overflow-y: auto;
        z-index: 10000;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        font-size: 12px;
        display: none;
    }
    .kernel-tooltip.visible { display: block; }
    .kernel-tooltip-header {
        font-weight: bold;
        font-size: 14px;
        margin-bottom: 8px;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--tooltip-border);
        color: var(--accent-blue);
        word-break: break-all;
    }
    .kernel-tooltip-semantic {
        background: rgba(79, 193, 255, 0.1);
        border-left: 3px solid var(--accent-blue);
        padding: 6px 10px;
        margin-bottom: 10px;
        font-style: italic;
        color: var(--text-secondary);
    }
    .kernel-tooltip-container {
        width: 100%;
    }
    .kernel-tooltip-row {
        display: flex;
        gap: 16px;
        margin-bottom: 8px;
    }
    .kernel-tooltip-row:last-child {
        margin-bottom: 0;
    }
    .kernel-tooltip-group {
        flex: 1;
        min-width: 160px;
    }
    .kernel-tooltip-group-grid {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 2px 8px;
    }
    .kernel-tooltip-label {
        font-weight: 500;
        color: var(--text-secondary);
        white-space: nowrap;
        font-size: 11px;
    }
    .kernel-tooltip-value {
        color: var(--text-primary);
        word-break: break-all;
        font-size: 11px;
    }
    .kernel-tooltip-section {
        font-weight: bold;
        color: var(--accent-orange);
        padding: 6px 0 4px 0;
        font-size: 12px;
        border-bottom: 1px solid var(--tooltip-border);
        margin-bottom: 4px;
    }
    .kernel-tooltip-full {
        grid-column: 1 / -1;
        display: flex;
        gap: 8px;
    }
    .kernel-tooltip-full .kernel-tooltip-label {
        flex-shrink: 0;
        }

    /* Timeline Styles - Module Schematic View */
.timeline-section {
         background: var(--bg-secondary);
         border-radius: 8px;
         padding: 20px;
         margin-top: 20px;
     }
     .timeline-header {
         display: flex;
         justify-content: space-between;
         align-items: center;
         margin-bottom: 15px;
     }
     .timeline-header h2 {
         font-size: 18px;
         color: var(--text-primary);
         margin: 0;
     }
     .timeline-hint {
         font-size: 12px;
         color: var(--text-secondary);
     }
     .timeline-container {
         position: relative;
         overflow-x: auto;
         overflow-y: visible;
     }
     .timeline-overview {
         margin: 16px 0;
     }
     .timeline-overview-title {
         font-size: 14px;
         color: var(--text-primary);
         margin-bottom: 12px;
         font-weight: 500;
     }
     .timeline-overview-list {
         border: 1px solid var(--border-color);
         border-radius: 6px;
         padding: 8px;
         background: var(--bg-tertiary);
     }
     .timeline-node-item {
         display: flex;
         align-items: center;
         padding: 10px 12px;
         margin: 4px 0;
         background: var(--bg-secondary);
         border-radius: 6px;
         cursor: pointer;
         transition: background 0.15s;
     }
     .timeline-node-item:hover {
         background: var(--bg-hover);
     }
     .timeline-node-item.has-children:hover {
         background: rgba(79, 193, 255, 0.1);
     }
     .node-expand-icon {
         width: 20px;
         font-size: 12px;
         color: var(--text-secondary);
         text-align: center;
     }
     .timeline-node-item.has-children .node-expand-icon {
         color: var(--accent-blue);
     }
     .node-name {
         flex: 1;
         font-weight: 500;
         color: var(--text-primary);
     }
     .node-streams {
         font-size: 11px;
         color: var(--text-secondary);
         margin: 0 12px;
         white-space: nowrap;
     }
     .node-duration {
         font-size: 11px;
         color: var(--accent-green);
         margin-right: 12px;
         white-space: nowrap;
     }
     .node-kernels {
         font-size: 11px;
         color: var(--text-secondary);
         white-space: nowrap;
     }
     .timeline-expand-area {
         margin: 16px 0;
         padding: 16px;
         background: var(--bg-tertiary);
         border-radius: 8px;
         border: 2px solid var(--accent-blue);
     }
     .expand-header {
         display: flex;
         align-items: center;
         margin-bottom: 16px;
     }
      .expand-close {
          background: var(--bg-secondary);
          border: 1px solid var(--border-color);
          border-radius: 4px;
          padding: 4px 12px;
          color: var(--text-secondary);
          cursor: pointer;
          font-size: 12px;
          margin-right: 12px;
      }
      .expand-close:hover {
          background: var(--bg-hover);
          color: var(--text-primary);
      }
      .expand-breadcrumb {
          display: flex;
          align-items: center;
          gap: 4px;
          flex: 1;
          min-width: 0;
          overflow-x: auto;
      }
      .breadcrumb-item {
          font-size: 12px;
          color: var(--accent-blue);
          cursor: pointer;
          white-space: nowrap;
          padding: 2px 6px;
          border-radius: 3px;
          transition: background 0.15s;
      }
      .breadcrumb-item:hover {
          background: rgba(79, 193, 255, 0.1);
      }
      .breadcrumb-item.current {
          color: var(--text-primary);
          font-weight: 600;
          cursor: default;
      }
      .breadcrumb-item.current:hover {
          background: transparent;
      }
      .breadcrumb-sep {
          color: var(--text-secondary);
          font-size: 10px;
          flex-shrink: 0;
      }
     .expand-title {
         font-weight: bold;
         color: var(--accent-blue);
         font-size: 14px;
     }
     .expand-gantt {
         margin: 16px 0;
     }
     .gantt-header {
         font-size: 13px;
         color: var(--text-primary);
         margin-bottom: 8px;
     }
     .gantt-hint {
         font-size: 11px;
         color: var(--text-secondary);
     }
     .gantt-container {
         background: var(--bg-secondary);
         border-radius: 6px;
         padding: 12px;
         border: 1px solid var(--border-color);
     }
      .gantt-stream-group {
          margin: 8px 0;
      }
      .gantt-stream-row {
          display: flex;
          align-items: center;
          min-height: 32px;
      }
      .gantt-stream-label {
          width: 90px;
          font-size: 11px;
          color: var(--text-secondary);
          flex-shrink: 0;
      }
      .gantt-bars {
          flex: 1;
          position: relative;
          height: 28px;
          background: rgba(0,0,0,0.15);
          border-radius: 4px;
          overflow: visible;
      }
      .gantt-bar {
          position: absolute;
          height: 20px;
          top: 4px;
          border-radius: 3px;
          cursor: pointer;
          transition: opacity 0.15s, box-shadow 0.15s;
      }
       .gantt-bar:hover {
           opacity: 0.85;
           z-index: 10;
           box-shadow: 0 0 8px rgba(255,255,255,0.4);
       }
       .gantt-bar-secondary {
           height: 16px;
           top: 6px;
       }
      .gantt-bar-arrow {
          position: absolute;
          bottom: -5px;
          left: 50%;
          transform: translateX(-50%);
          width: 0;
          height: 0;
          border-left: 4px solid transparent;
          border-right: 4px solid transparent;
          border-top: 5px solid;
      }
      .gantt-labels-row {
          position: relative;
          min-height: 22px;
          margin-left: 90px;
          margin-top: 2px;
      }
      .gantt-label {
          position: absolute;
          font-size: 10px;
          white-space: nowrap;
          transform: translateX(-50%);
          padding: 1px 5px;
          border-radius: 3px;
          background: var(--bg-tertiary);
      }
      .gantt-label::before {
          content: '';
          position: absolute;
          top: -4px;
          left: 50%;
          transform: translateX(-50%);
          width: 0;
          height: 0;
          border-left: 3px solid transparent;
          border-right: 3px solid transparent;
          border-bottom: 4px solid var(--bg-tertiary);
      }
     .gantt-time-axis {
         display: flex;
         justify-content: space-between;
         margin-top: 8px;
         padding-top: 8px;
         border-top: 1px solid var(--border-color);
         font-size: 10px;
         color: var(--text-secondary);
     }
     .expand-tree {
         margin-top: 16px;
     }
     .expand-tree-title {
         font-size: 13px;
         color: var(--text-primary);
         margin-bottom: 8px;
     }
     .tree-hint {
         font-size: 11px;
         color: var(--text-secondary);
     }
     .expand-tree-content {
         background: var(--bg-secondary);
         border-radius: 6px;
         padding: 8px 12px;
         border: 1px solid var(--border-color);
     }
     .tree-item {
         display: flex;
         align-items: center;
         padding: 6px 8px;
         margin: 2px 0;
         border-radius: 4px;
         cursor: default;
         transition: background 0.15s;
     }
     .tree-item.clickable {
         cursor: pointer;
     }
     .tree-item.clickable:hover {
         background: rgba(79, 193, 255, 0.1);
     }
     .tree-icon {
         width: 20px;
         font-size: 12px;
         color: var(--text-secondary);
         text-align: center;
         flex-shrink: 0;
     }
     .tree-item.clickable .tree-icon {
         color: var(--accent-blue);
     }
     .tree-name {
         flex: 1;
         font-size: 12px;
         color: var(--text-primary);
     }
     .tree-streams {
         font-size: 10px;
         color: var(--text-secondary);
         margin: 0 8px;
         white-space: nowrap;
     }
     .tree-duration {
         font-size: 10px;
         color: var(--accent-green);
         white-space: nowrap;
     }
     .timeline-tooltip {
         position: fixed;
         background: var(--tooltip-bg);
         border: 1px solid var(--tooltip-border);
         border-radius: 6px;
         padding: 10px 12px;
         font-size: 12px;
         z-index: 10000;
         box-shadow: 0 4px 12px rgba(0,0,0,0.4);
         max-width: 400px;
         display: none;
     }
     .timeline-tooltip.visible {
         display: block;
     }
     .timeline-tooltip-title {
         font-weight: bold;
         color: var(--accent-blue);
         margin-bottom: 6px;
     }
     .timeline-tooltip-row {
         display: flex;
         justify-content: space-between;
         gap: 20px;
         margin-bottom: 3px;
         color: var(--text-primary);
     }
     .timeline-tooltip-label {
         color: var(--text-secondary);
     }
     .timeline-tooltip-streams {
         margin-top: 6px;
         padding-top: 6px;
         border-top: 1px solid var(--tooltip-border);
         font-size: 11px;
     }
     .timeline-detail-panel {
         margin-top: 15px;
         background: var(--bg-tertiary);
         border-radius: 6px;
         padding: 15px;
         display: none;
     }
     .timeline-detail-panel.visible {
         display: block;
     }
     .timeline-detail-header {
         display: flex;
         justify-content: space-between;
         align-items: center;
         margin-bottom: 10px;
     }
     .timeline-detail-title {
         font-weight: bold;
         color: var(--accent-blue);
     }
     .timeline-detail-close {
         background: transparent;
         border: none;
         color: var(--text-secondary);
         cursor: pointer;
         font-size: 18px;
         line-height: 1;
     }
     .timeline-detail-close:hover {
         color: var(--text-primary);
     }
      .timeline-detail-ops {
          background: var(--bg-secondary);
          border-radius: 4px;
          padding: 12px;
      }
      .timeline-stream-row {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          padding: 8px 0;
          border-bottom: 1px solid var(--border-color);
          gap: 6px;
      }
      .timeline-stream-row:last-child {
          border-bottom: none;
      }
      .timeline-stream-label {
          width: 100px;
          flex-shrink: 0;
          font-size: 11px;
          font-weight: 500;
          padding: 4px 8px;
          border-radius: 3px;
          text-align: center;
      }
       .timeline-stream-ops {
           flex: 1;
           position: relative;
           height: 26px;
           background: rgba(0,0,0,0.12);
           border-radius: 4px;
       }
       .timeline-detail-bar {
           position: absolute;
           height: 22px;
           top: 2px;
           border-radius: 3px;
           font-size: 9px;
           color: #fff;
           display: flex;
           align-items: center;
           justify-content: center;
           overflow: hidden;
           cursor: pointer;
           transition: opacity 0.15s, box-shadow 0.15s;
       }
       .timeline-detail-bar:hover {
           opacity: 0.85;
           z-index: 10;
           box-shadow: 0 0 6px rgba(255,255,255,0.3);
       }
       .covered-bar {
           background-image: repeating-linear-gradient(
               45deg, transparent, transparent 3px,
               rgba(255,255,255,0.18) 3px, rgba(255,255,255,0.18) 6px
           ) !important;
           opacity: 0.55 !important;
       }
       .covered-badge {
           font-size: 10px;
           background: rgba(255,120,100,0.25);
           color: #ff7864;
           border: 1px solid rgba(255,120,100,0.45);
           border-radius: 3px;
           padding: 0 4px;
           margin-left: 5px;
           vertical-align: middle;
           white-space: nowrap;
       }
     </style>

    '''


TIMELINE_PALETTE = [
    '#4fc1ff', '#6a9955', '#ce9178', '#c586c0', '#569cd6',
    '#dcdcaa', '#e06c75', '#61afef', '#98c379', '#d19a66',
    '#c678dd', '#e5c07b', '#56b6c2', '#be5046', '#7ec699',
    '#f99157', '#cc99cc', '#99cc99', '#6699cc', '#f2777a',
]


def _collect_node_op_indices_all(node: dict) -> list:
    indices = list(node.get('op_indices', []))
    for child in node.get('children', []):
        indices.extend(_collect_node_op_indices_all(child))
    return indices


def _compute_node_time_range(node: dict, operators: list) -> dict:
    all_indices = _collect_node_op_indices_all(node)
    op_dict = {op['index']: op for op in operators}
    ops = [op_dict[i] for i in all_indices if i in op_dict]
    if not ops:
        return {'start': 0, 'end': 0, 'duration': 0, 'streams': {}, 'kernel_count': 0}
    min_start = min(op.get('start_time_us', 0) for op in ops)
    max_end = max(op.get('start_time_us', 0) + op.get('duration_us', 0) for op in ops)
    stream_counts = {}
    for op in ops:
        sid = str(op.get('stream_id', 'unknown'))
        stream_counts[sid] = stream_counts.get(sid, 0) + 1
    return {
        'start': min_start,
        'end': max_end,
        'duration': max_end - min_start,
        'streams': stream_counts,
        'kernel_count': len(ops),
    }


def _materialize_instance_structure(template: dict, representative_ops: list,
                                    target_ops: list, instance_label: str) -> dict:
    """Map a representative structure onto one real trace invocation."""
    base_name = template.get('name', 'ModelLayer')
    fallback = {
        'name': f'{base_name} [{instance_label}]',
        'semantic': template.get('semantic', base_name),
        'code_ref': template.get('code_ref'),
        'op_indices': list(target_ops),
    }

    template_ops = _collect_node_op_indices_all(template)
    if (len(representative_ops) != len(target_ops)
            or set(template_ops) != set(representative_ops)
            or len(set(representative_ops)) != len(representative_ops)):
        return fallback

    op_map = dict(zip(representative_ops, target_ops))
    node = copy.deepcopy(template)

    def remap(current: dict) -> None:
        if current.get('op_indices'):
            current['op_indices'] = [op_map[i] for i in current['op_indices']]
        for child in current.get('children', []) or []:
            remap(child)

    remap(node)
    node['name'] = f'{base_name} [{instance_label}]'
    return node


def generate_timeline_data(config: dict, operators: list, total_duration: float) -> list:
    op_dict = {op['index']: op for op in operators}
    color_idx = 0
    node_color_map = {}
    timeline_nodes = []

    def assign_color(path: str) -> str:
        nonlocal color_idx
        parts = path.split('/')
        key = parts[-1] if len(parts) > 1 else parts[0]
        if key not in node_color_map:
            node_color_map[key] = TIMELINE_PALETTE[color_idx % len(TIMELINE_PALETTE)]
            color_idx += 1
        return node_color_map[key]

    def get_dominant_stream(per_stream_ops: dict) -> str:
        if not per_stream_ops:
            return '0'
        stream_counts = {sid: len(ops) for sid, ops in per_stream_ops.items()}
        return max(stream_counts.items(), key=lambda x: x[1])[0]

    def process_node(node: dict, parent_path: str, multiplier: int = 1, depth: int = 0, parent_index: int = -1, is_auxiliary: bool = False):
        name = node.get('name', 'Unknown')
        path = f"{parent_path}/{name}" if parent_path else name
        color = assign_color(path)
        op_indices = node.get('op_indices', [])
        children = node.get('children', [])

        all_ops_indices = _collect_node_op_indices_all(node)
        all_ops = [op_dict[i] for i in all_ops_indices if i in op_dict]

        if not all_ops:
            return -1

        stream_set = set()
        for op in all_ops:
            stream_set.add(str(op.get('stream_id', '0')))

        min_start = min(op.get('start_time_us', 0) for op in all_ops)
        max_end = max(op.get('start_time_us', 0) + op.get('duration_us', 0) for op in all_ops)

        per_stream_ops = {}
        for i in all_ops_indices:
            op = op_dict.get(i)
            if op:
                sid = str(op.get('stream_id', '0'))
                if sid not in per_stream_ops:
                    per_stream_ops[sid] = []
                per_stream_ops[sid].append({
                    'index': op['index'],
                    'name': op.get('normalized_name') or op.get('type') or op.get('name', 'Unknown'),
                    'original_name': op.get('original_name', op.get('name', '')),
                    'start': op.get('start_time_us', 0),
                    'end': op.get('start_time_us', 0) + op.get('duration_us', 0),
                    'duration': op.get('duration_us', 0),
                    'wait_time': op.get('wait_time_us', 0),
                    'stream_id': sid,
                })

        for sid in per_stream_ops:
            per_stream_ops[sid].sort(key=lambda x: x['start'])

        current_index = len(timeline_nodes)
        dominant_stream = get_dominant_stream(per_stream_ops)

        timeline_nodes.append({
            'name': name,
            'path': path,
            'color': color,
            'multiplier': multiplier,
            'start': min_start,
            'end': max_end,
            'duration': max_end - min_start,
            'kernel_count': len(all_ops),
            'streams': sorted(stream_set),
            'dominant_stream': dominant_stream,
            'per_stream_ops': per_stream_ops,
            'op_indices': all_ops_indices,
            'depth': depth,
            'parent_index': parent_index,
            'children_indices': [],
            'has_children': False,
            'category': 'auxiliary' if is_auxiliary else '',
        })

        child_indices = []
        for child in children:
            child_idx = process_node(child, path, multiplier, depth + 1, current_index, is_auxiliary)
            if child_idx >= 0:
                child_indices.append(child_idx)

        timeline_nodes[current_index]['children_indices'] = child_indices
        timeline_nodes[current_index]['has_children'] = len(child_indices) > 0

        return current_index

    model_name = config.get('model_name', 'Model')

    stages = config.get('stages', {})
    for _stage_name, stage_info in stages.items():
        # A v2 stage already contains the exact op union for all of its instances.
        # It must not be multiplied again in the Timeline.
        stage_multiplier = 1 if config.get('schema_version') == 2 else max(
            len(stage_info.get('stage_indices', [0])), 1)
        process_node(stage_info, model_name, stage_multiplier, depth=0, is_auxiliary=True)

    if config.get('schema_version') == 2:
        structures = config.get('structures') or {}
        instances = config.get('trace_instances') or []
        groups = {}
        for inst in instances:
            group_type = inst.get('layer_group_type') or f"model_layer_{inst.get('model_layer_index')}"
            groups.setdefault(group_type, []).append(inst)

        for inst in instances:
            group_type = inst.get('layer_group_type') or f"model_layer_{inst.get('model_layer_index')}"
            target_ops = bc.instance_op_indices(inst)
            group_instances = groups[group_type]
            representative_id = inst.get('representative_instance_id')
            representative = next(
                (item for item in group_instances
                 if item.get('instance_id') == representative_id),
                group_instances[0],
            )
            template = structures.get(group_type)
            layer_index = inst.get('model_layer_index', 'unknown')
            invocation_index = inst.get('invocation_index', 0)
            instance_id = inst.get('instance_id', f'layer_{layer_index}_invocation_{invocation_index}')
            instance_label = f'{instance_id}; layer {layer_index}; invocation {invocation_index}'
            if template:
                node = _materialize_instance_structure(
                    template,
                    bc.instance_op_indices(representative),
                    target_ops,
                    instance_label,
                )
            else:
                node = {
                    'name': f'{group_type} [{instance_label}]',
                    'semantic': f'observed {group_type}',
                    'op_indices': target_ops,
                }
            process_node(node, model_name, 1, depth=0)
    else:
        for _name, structure, layer_count in iter_layer_sections(config):
            process_node(structure, model_name, layer_count, depth=0)

    runtime_aux = config.get('runtime_auxiliary', [])
    for aux in runtime_aux:
        process_node(aux, model_name, 1, depth=0, is_auxiliary=True)

    if config.get('schema_version') == 2:
        for excluded in config.get('excluded_profiler_ops', []) or []:
            process_node({
                'name': f"excluded_profiler_ops [{excluded.get('reason_code', 'unknown')}]",
                'semantic': excluded.get('evidence', 'profiler-only operation'),
                'op_indices': excluded.get('op_indices', []),
            }, model_name, 1, depth=0, is_auxiliary=True)

    return timeline_nodes


def _validate_timeline_top_level_coverage(timeline_nodes: list, operators: list) -> None:
    """Reject a schema-v2 Timeline that omits or duplicates raw ops at top level."""
    from collections import Counter

    expected = {op['index'] for op in operators}
    references = [
        index
        for node in timeline_nodes if node.get('depth', 0) == 0
        for index in node.get('op_indices', [])
    ]
    counts = Counter(references)
    actual = set(counts)
    missing = sorted(expected - actual)
    duplicate = sorted(index for index, count in counts.items() if count > 1)
    out_of_range = sorted(actual - expected)
    if missing or duplicate or out_of_range:
        raise ValueError(
            'Timeline top-level coverage failed: '
            f'missing={missing}, duplicate={duplicate}, out_of_range={out_of_range}')


def generate_timeline_html(config: dict, operators: list, total_duration: float, max_depth: int) -> tuple:
    timeline_nodes = generate_timeline_data(config, operators, total_duration)

    if config.get('schema_version') == 2:
        _validate_timeline_top_level_coverage(timeline_nodes, operators)

    if not operators or not timeline_nodes:
        return '<section id="timeline" class="timeline-section"><h2>多流时序图</h2><p style="color:var(--text-secondary)">无可用的时序数据</p></section>', {}

    top_level_nodes = [i for i, node in enumerate(timeline_nodes) if node.get('depth', 0) == 0]

    def format_duration_us(us: float) -> str:
        if us >= 1000:
            return f"{us/1000:.1f}ms"
        return f"{us:.1f}us"

    html_parts = [
        '<section id="timeline" class="timeline-section">',
        '<div class="timeline-header">',
        '<h2>多流时序图</h2>',
        '<span class="timeline-hint">点击节点展开子节点多流时序，悬停查看时间信息</span>',
        '</div>',
        '<div class="timeline-container">',
        '<div class="timeline-overview">',
        '<div class="timeline-overview-title">顶层节点概览</div>',
        '<div class="timeline-overview-list">',
    ]

    for ni, node in enumerate(timeline_nodes):
        if node.get('depth', 0) != 0:
            continue
        name = node['name']
        multiplier = node.get('multiplier', 1)
        streams = node.get('streams', [])
        kernel_count = node.get('kernel_count', 0)
        has_children = node.get('has_children', False)
        color = node.get('color', '#4fc1ff')
        duration = node.get('duration', 0)
        category = node.get('category', '')

        count_suffix = f" ×{multiplier}" if multiplier > 1 else ""
        streams_str = ','.join(streams[:4]) + ('...' if len(streams) > 4 else '')
        duration_str = format_duration_us(duration)
        expand_icon = '▶' if has_children else '─'
        expand_class = 'has-children' if has_children else ''
        category_attr = f' data-category="{category}"' if category else ''

        html_parts.append(
            f'<div class="timeline-node-item {expand_class}" data-node-index="{ni}"{category_attr}>'
            f'<span class="node-expand-icon">{expand_icon}</span>'
            f'<span class="node-name" style="border-left:3px solid {color};padding-left:6px">{name}{count_suffix}</span>'
            f'<span class="node-streams">Streams: [{streams_str}]</span>'
            f'<span class="node-duration">{duration_str}</span>'
            f'<span class="node-kernels">{kernel_count} kernels</span>'
            f'</div>'
        )

    html_parts.append('</div>')
    html_parts.append('</div>')

    html_parts.append('<div class="timeline-expand-area" id="timeline-expand-area" style="display:none">')
    html_parts.append('<div class="expand-header">')
    html_parts.append('<button class="expand-close" id="expand-close-btn">收起</button>')
    html_parts.append('<div class="expand-breadcrumb" id="expand-breadcrumb"></div>')
    html_parts.append('<span class="expand-title" id="expand-title">-</span>')
    html_parts.append('</div>')

    html_parts.append('<div class="expand-gantt" id="expand-gantt">')
    html_parts.append('<div class="gantt-header">子节点多流时序图 <span class="gantt-hint">(按时间比例显示)</span></div>')
    html_parts.append('<div class="gantt-container" id="gantt-container"></div>')
    html_parts.append('</div>')

    html_parts.append('<div class="expand-tree" id="expand-tree">')
    html_parts.append('<div class="expand-tree-title">子节点结构 <span class="tree-hint">(点击有子节点的项继续展开)</span></div>')
    html_parts.append('<div class="expand-tree-content" id="tree-content"></div>')
    html_parts.append('</div>')

    html_parts.append('</div>')
    html_parts.append('</div>')

    html_parts.append('<div class="timeline-detail-panel" id="timeline-detail-panel">')
    html_parts.append('<div class="timeline-detail-header">')
    html_parts.append('<span class="timeline-detail-title" id="timeline-detail-title">-</span>')
    html_parts.append('<button class="timeline-detail-close" id="timeline-detail-close">&times;</button>')
    html_parts.append('</div>')
    html_parts.append('<div class="timeline-detail-ops" id="timeline-detail-ops"></div>')
    html_parts.append('</div>')

    html_parts.append('</section>')

    bar_data_json = []
    for ni, node in enumerate(timeline_nodes):
        bar_data_json.append({
            'name': node['name'],
            'path': node['path'],
            'start': node['start'],
            'end': node['end'],
            'duration': node['duration'],
            'color': node['color'],
            'multiplier': node.get('multiplier', 1),
            'kernel_count': node['kernel_count'],
            'streams': node['streams'],
            'dominant_stream': node.get('dominant_stream', node['streams'][0] if node['streams'] else '0'),
            'node_index': ni,
            'per_stream_ops': node['per_stream_ops'],
            'depth': node.get('depth', 0),
            'parent_index': node.get('parent_index', -1),
            'children_indices': node.get('children_indices', []),
            'has_children': node.get('has_children', False),
            'category': node.get('category', ''),
        })

    return '\n'.join(html_parts), {
        'top_level_nodes': top_level_nodes,
        'bar_data': bar_data_json,
    }


def get_html_js(default_theme: str, tooltip_data: dict = None, display_fields: list = None,
                timeline_data: dict = None) -> str:
    import json as _json
    tooltip_json = _json.dumps(tooltip_data or {}, ensure_ascii=False)
    fields_json = _json.dumps(display_fields or DEFAULT_KERNEL_DISPLAY_FIELDS, ensure_ascii=False)
    tl_json = _json.dumps(timeline_data or {}, ensure_ascii=False)
    js_code = """
    <script>
    let currentTooltip = null;
    const tooltipData = """ + tooltip_json + """;
    const defaultFields = """ + fields_json + """;
    const tlData = """ + tl_json + """;

    function showTooltip(el) {
        const idx = el.dataset.index;

        if (currentTooltip && currentTooltip.classList.contains('visible') &&
            currentTooltip.dataset.currentIdx === idx) {
            hideTooltip();
            return;
        }

        if (!tooltipData[idx]) return;

        if (!currentTooltip) {
            currentTooltip = document.createElement('div');
            currentTooltip.className = 'kernel-tooltip';
            document.body.appendChild(currentTooltip);
        }

        currentTooltip.innerHTML = tooltipData[idx];
        currentTooltip.classList.add('visible');
        currentTooltip.dataset.currentIdx = idx;
        currentTooltip.style.left = '';
        currentTooltip.style.top = '';
        currentTooltip.style.right = '';

        const rect = el.getBoundingClientRect();
        currentTooltip.style.position = 'fixed';

        const tooltipEl = currentTooltip;
        const tw = tooltipEl.offsetWidth;
        const th = tooltipEl.offsetHeight;
        const vw = window.innerWidth;
        const vh = window.innerHeight;

        let left = rect.right + 12;
        let top = rect.top;

        if (left + tw > vw - 10) {
            left = Math.max(10, vw - tw - 10);
        }
        if (top + th > vh - 10) {
            top = Math.max(10, vh - th - 10);
        }
        if (top < 10) top = 10;

        currentTooltip.style.left = left + 'px';
        currentTooltip.style.top = top + 'px';
    }

    function hideTooltip() {
        if (currentTooltip) {
            currentTooltip.classList.remove('visible');
        }
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('report-theme', theme);
        document.getElementById('theme-select').value = theme;
    }

    function initTheme() {
        const saved = localStorage.getItem('report-theme') || '""" + default_theme + """';
        applyTheme(saved);
    }

    function toggleKernels(visible) {
        document.querySelectorAll('.tree-node[data-type="kernel"]').forEach(node => {
            if (visible) {
                node.classList.remove('hidden-kernel');
            } else {
                node.classList.add('hidden-kernel');
            }
        });
        if (visible) {
            document.querySelectorAll('.tree-node[data-type="kernel"]').forEach(kernel => {
                let parent = kernel.parentElement;
                while (parent) {
                    if (parent.classList.contains('tree-node') && parent.classList.contains('collapsed')) {
                        parent.classList.remove('collapsed');
                        parent.classList.add('expanded');
                    }
                    parent = parent.parentElement;
                }
            });
        }
    }

    function updateKernelMetaFields() {
        const panel = document.getElementById('kernel-fields-panel');
        const checked = Array.from(panel.querySelectorAll('input:checked')).map(cb => cb.value);
        document.querySelectorAll('.kernel-meta').forEach(meta => {
            meta.querySelectorAll('.kernel-meta-item').forEach(item => {
                const field = item.dataset.field;
                item.style.display = checked.includes(field) ? 'flex' : 'none';
            });
        });
    }

 /* ========== Timeline Logic ========== */
      let tlTooltip = null;
      let currentExpandedNode = null;
      let navHistory = [];

     function formatUs(us) {
         if (us >= 1000) return (us / 1000).toFixed(1) + 'ms';
         return us.toFixed(1) + 'us';
     }

     function initTimelineTooltip() {
         if (!tlTooltip) {
             tlTooltip = document.createElement('div');
             tlTooltip.className = 'timeline-tooltip';
             document.body.appendChild(tlTooltip);
         }
     }

      function showTimelineTooltip(el, barInfo) {
          initTimelineTooltip();
          let streamInfo = '';
          if (barInfo.streams && barInfo.streams.length > 0) {
              streamInfo = '<div class="timeline-tooltip-streams"><span class="timeline-tooltip-label">Streams:</span> ' +
                  barInfo.streams.map(s => 'Stream ' + s).join(', ') + '</div>';
          }
          const countSuffix = barInfo.multiplier > 1 ? ' (×' + barInfo.multiplier + ')' : '';
          const hasChildrenHint = barInfo.has_children ? '点击展开子节点' : '点击查看算子详情';
          tlTooltip.innerHTML =
              '<div class="timeline-tooltip-title">' + barInfo.name + countSuffix + '</div>' +
              '<div class="timeline-tooltip-row"><span class="timeline-tooltip-label">时间:</span> ' +
              formatUs(barInfo.duration) + '</div>' +
              '<div class="timeline-tooltip-row"><span class="timeline-tooltip-label">Kernels:</span> ' +
              barInfo.kernel_count + '</div>' +
              streamInfo +
              '<div style="margin-top:6px;color:var(--text-secondary);font-size:11px">' + hasChildrenHint + '</div>';
          tlTooltip.classList.add('visible');
          const rect = el.getBoundingClientRect();
          const vw = window.innerWidth;
          const vh = window.innerHeight;
          let left = rect.right + 10;
          let top = rect.top;
          if (left + 320 > vw) left = Math.max(10, rect.left - 330);
          if (top + 180 > vh) top = Math.max(10, vh - 190);
          if (top < 10) top = 10;
          tlTooltip.style.left = left + 'px';
          tlTooltip.style.top = top + 'px';
      }

     function hideTimelineTooltip() {
         if (tlTooltip) tlTooltip.classList.remove('visible');
     }

       function showOpsDetail(nodeIndex) {
           if (!tlData.bar_data || !tlData.bar_data[nodeIndex]) return;
           const bar = tlData.bar_data[nodeIndex];
           const panel = document.getElementById('timeline-detail-panel');
           const title = document.getElementById('timeline-detail-title');
           const opsContainer = document.getElementById('timeline-detail-ops');

           const countSuffix = bar.multiplier > 1 ? ' (×' + bar.multiplier + ')' : '';
           title.textContent = bar.name + countSuffix + ' - 算子列表';

           const allOps = [];
           if (bar.per_stream_ops) {
               for (const sid in bar.per_stream_ops) {
                   for (const op of bar.per_stream_ops[sid]) {
                       allOps.push(op);
                   }
               }
           }
           if (allOps.length === 0) {
               opsContainer.innerHTML = '<div style="padding:10px;color:var(--text-secondary)">无算子数据</div>';
               panel.classList.add('visible');
               return;
           }

           const timeMin = Math.min(...allOps.map(o => o.start));
           const timeMax = Math.max(...allOps.map(o => o.end));
           const timeDuration = Math.max(1, timeMax - timeMin);

           const streamColors = {};
           const palette = ['#4fc1ff', '#6a9955', '#ce9178', '#c586c0', '#569cd6', '#dcdcaa', '#e06c75'];
           let ci = 0;
           const sortedSids = Object.keys(bar.per_stream_ops).sort((a, b) => Number(a) - Number(b));
           for (const sid of sortedSids) {
               streamColors[sid] = palette[ci % palette.length];
               ci++;
           }

           // Determine dominant stream (most ops)
           const dominantSid = sortedSids.reduce((a, b) =>
               (bar.per_stream_ops[a].length >= bar.per_stream_ops[b].length ? a : b), sortedSids[0]);
           const dominantOps = (bar.per_stream_ops[dominantSid] || []).map(o => ({
               start: o.start, end: o.end
           }));
           function isCoveredByDominant(op) {
               return dominantOps.some(d => d.start < op.end && d.end > op.start);
           }

           let html = '';
           for (const sid of sortedSids) {
               const ops = bar.per_stream_ops[sid].sort((a, b) => a.start - b.start);
               const color = streamColors[sid];
               const isAux = sid !== dominantSid;
               const coveredCount = isAux ? ops.filter(op => isCoveredByDominant(op)).length : 0;
               const coveredBadge = (isAux && coveredCount > 0)
                   ? '<span class="covered-badge">' + coveredCount + ' covered</span>' : '';
               html += '<div class="timeline-stream-row">';
               html += '<span class="timeline-stream-label" style="background:' + color + '22;color:' + color + ';border:1px solid ' + color + '44">Stream ' + sid + ' (' + ops.length + ')' + coveredBadge + '</span>';
               html += '<div class="timeline-stream-ops">';
               ops.forEach((op, opIndex) => {
                   const leftPct = ((op.start - timeMin) / timeDuration) * 100;
                   const widthPct = Math.max(1, (op.duration / timeDuration) * 100);
                   const shortName = op.name.length > 10 ? op.name.substring(0, 8) + '..' : op.name;
                   const covered = isAux && isCoveredByDominant(op);
                   const coveredTip = covered ? ('\\n⚠ covered by stream ' + dominantSid) : '';
                   const tipText = op.name + '\\n历时: ' + formatUs(op.duration) + '\\nStart: ' + formatUs(op.start) + coveredTip;
                   const showText = widthPct > 6;
                   // Alternating colors: even = full opacity, odd = semi-transparent + top border
                   const isEven = opIndex % 2 === 0;
                   const barAlpha = isEven ? 'ee' : '88';
                   const borderExtra = isEven ? '' : ';border-top:2px solid ' + color + 'cc';
                   const coveredClass = covered ? ' covered-bar' : '';
                   html += '<span class="timeline-detail-bar' + coveredClass + '" style="left:' + leftPct.toFixed(1) + '%;width:' + widthPct.toFixed(1) + '%;background:' + color + barAlpha + borderExtra + '" title="' + tipText + '">' + (showText ? shortName : '') + '</span>';
               });
               html += '</div></div>';
           }
           opsContainer.innerHTML = html;
           panel.classList.add('visible');
           panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
       }

       function renderGantt(parentNode, children) {
           const container = document.getElementById('gantt-container');
           if (!container || !children || children.length === 0) {
               container.innerHTML = '<div style="padding:10px;color:var(--text-secondary)">无子节点数据</div>';
               return;
           }

           const parentStart = parentNode.start;
           const parentDuration = parentNode.duration || 1;
           const allStreams = new Set();
           children.forEach(c => c.streams.forEach(s => allStreams.add(s)));
           const sortedStreams = Array.from(allStreams).sort();

           let html = '';
           sortedStreams.forEach(stream => {
               const barsOnStream = children.filter(c => c.streams.includes(stream));
               if (barsOnStream.length === 0) return;

               html += '<div class="gantt-stream-group">';
               html += '<div class="gantt-stream-row">';
               html += '<span class="gantt-stream-label">Stream ' + stream + '</span>';
               html += '<div class="gantt-bars">';

               barsOnStream.forEach(child => {
                   const leftPct = Math.max(0, (child.start - parentStart) / parentDuration * 100);
                   const widthPct = Math.max(1.5, child.duration / parentDuration * 100);
                   const rightPct = Math.min(100, leftPct + widthPct);
                   const actualWidth = rightPct - leftPct;
                   const centerPct = leftPct + actualWidth / 2;
                   const isDominant = child.dominant_stream === stream;
                   const opacity = isDominant ? '1' : '0.4';
                   const borderStyle = isDominant ? '' : ';border:1px dashed ' + child.color;

                   html += '<div class="gantt-bar' + (isDominant ? '' : ' gantt-bar-secondary') + '" style="left:' + leftPct.toFixed(1) + '%;width:' + actualWidth.toFixed(1) +
                       '%;background:' + child.color + ';opacity:' + opacity + borderStyle + '" data-node-index="' + child.node_index + '" data-center="' + centerPct.toFixed(1) + '" data-color="' + child.color + '">' +
                       (isDominant ? '<div class="gantt-bar-arrow" style="border-top-color:' + child.color + '"></div>' : '') +
                       '</div>';
               });

               html += '</div></div>';

               html += '<div class="gantt-labels-row">';
               barsOnStream.forEach(child => {
                   const leftPct = Math.max(0, (child.start - parentStart) / parentDuration * 100);
                   const widthPct = Math.max(1.5, child.duration / parentDuration * 100);
                   const centerPct = Math.min(98, Math.max(2, leftPct + widthPct / 2));
                   const isDominant = child.dominant_stream === stream;
                   const shortName = child.name.length > 12 ? child.name.substring(0, 10) + '..' : child.name;

                   if (!isDominant) return;
                   html += '<div class="gantt-label" style="left:' + centerPct.toFixed(1) +
                       '%;color:' + child.color + ';border-color:' + child.color + '66" data-center="' + centerPct.toFixed(1) + '">' +
                       shortName + '</div>';
               });
               html += '</div></div>';
           });

           const timeMarkers = [0, 0.25, 0.5, 0.75, 1].map(r => formatUs(parentStart + parentDuration * r));
           html += '<div class="gantt-time-axis">' +
               '<span>' + timeMarkers[0] + '</span>' +
               '<span>' + timeMarkers[1] + '</span>' +
               '<span>' + timeMarkers[2] + '</span>' +
               '<span>' + timeMarkers[3] + '</span>' +
               '<span>' + timeMarkers[4] + '</span></div>';

           container.innerHTML = html;

           layoutLabels(container);

           container.querySelectorAll('.gantt-bar').forEach(bar => {
               const ni = parseInt(bar.dataset.nodeIndex);
               const info = tlData.bar_data ? tlData.bar_data[ni] : null;
               if (!info) return;
               bar.addEventListener('mouseenter', () => showTimelineTooltip(bar, info));
               bar.addEventListener('mouseleave', () => setTimeout(() => { if (!tlTooltip || !tlTooltip.matches(':hover')) hideTimelineTooltip(); }, 150));
               bar.addEventListener('click', (e) => { e.stopPropagation(); hideTimelineTooltip(); showOpsDetail(ni); });
           });
       }

      function layoutLabels(container) {
          container.querySelectorAll('.gantt-labels-row').forEach(row => {
              const labels = Array.from(row.querySelectorAll('.gantt-label'));
              if (labels.length === 0) return;

              labels.sort((a, b) => parseFloat(a.dataset.center) - parseFloat(b.dataset.center));

              const minGap = 10;
              for (let i = 1; i < labels.length; i++) {
                  const prev = labels[i - 1];
                  const curr = labels[i];
                  const prevLeft = parseFloat(prev.style.left);
                  let currLeft = parseFloat(curr.style.left);

                  const prevWidth = prev.offsetWidth;
                  const currWidth = curr.offsetWidth;
                  const threshold = (prevWidth + currWidth) / 2 / row.offsetWidth * 100 + minGap;

                  if (currLeft - prevLeft < threshold) {
                      currLeft = prevLeft + threshold;
                      if (currLeft > 98) currLeft = 98;
                      curr.style.left = currLeft.toFixed(1) + '%';
                  }
              }
          });
      }

      function renderTree(parentNode, children) {
          const container = document.getElementById('tree-content');
          if (!container || !children || children.length === 0) {
              container.innerHTML = '<div style="padding:10px;color:var(--text-secondary)">无子节点</div>';
              return;
          }

          const baseDepth = parentNode.depth;
          let html = '';

          function renderNode(node, depth) {
              const indent = (depth - baseDepth) * 20;
              const hasChildren = node.has_children;
              const icon = hasChildren ? '▶' : '─';
              const clickableClass = hasChildren ? 'clickable' : '';
              const streamsStr = node.streams.slice(0, 3).join(',') + (node.streams.length > 3 ? '..' : '');

              html += '<div class="tree-item ' + clickableClass + '" data-node-index="' + node.node_index + '" style="padding-left:' + indent + 'px">';
              html += '<span class="tree-icon">' + icon + '</span>';
              html += '<span class="tree-name">' + node.name + '</span>';
              html += '<span class="tree-streams">[' + streamsStr + ']</span>';
              html += '<span class="tree-duration">' + formatUs(node.duration) + '</span>';
              html += '</div>';
          }

         children.forEach(child => renderNode(child, child.depth));
         container.innerHTML = html;

         container.querySelectorAll('.tree-item.clickable').forEach(item => {
             const ni = parseInt(item.dataset.nodeIndex);
             item.addEventListener('click', (e) => {
                 e.stopPropagation();
                 showNodeChildren(ni);
             });
             item.addEventListener('mouseenter', () => {
                 const info = tlData.bar_data ? tlData.bar_data[ni] : null;
                 if (info) showTimelineTooltip(item, info);
             });
             item.addEventListener('mouseleave', () => setTimeout(() => { if (!tlTooltip || !tlTooltip.matches(':hover')) hideTimelineTooltip(); }, 150));
         });

         container.querySelectorAll('.tree-item:not(.clickable)').forEach(item => {
             const ni = parseInt(item.dataset.nodeIndex);
             item.addEventListener('click', (e) => {
                 e.stopPropagation();
                 showOpsDetail(ni);
             });
         });
     }

       function showNodeChildren(nodeIndex, addToHistory = true) {
           if (!tlData.bar_data || !tlData.bar_data[nodeIndex]) return;
           const node = tlData.bar_data[nodeIndex];
           const childrenIndices = node.children_indices || [];

           if (childrenIndices.length === 0) {
               showOpsDetail(nodeIndex);
               return;
           }

           if (addToHistory && currentExpandedNode !== null && currentExpandedNode !== nodeIndex) {
               navHistory.push(currentExpandedNode);
           }

           const children = childrenIndices.map(i => tlData.bar_data[i]).filter(c => c);

           const expandArea = document.getElementById('timeline-expand-area');
           const title = document.getElementById('expand-title');

            const countSuffix = node.multiplier > 1 ? ' (×' + node.multiplier + ')' : '';
            title.textContent = node.name + countSuffix + ' - 子节点多流时序';

           renderGantt(node, children);
           renderTree(node, children);
           renderBreadcrumb(nodeIndex);

           currentExpandedNode = nodeIndex;
           expandArea.style.display = 'block';
           expandArea.scrollIntoView({ behavior: 'smooth', block: 'start' });
       }

       function renderBreadcrumb(currentNodeIndex) {
           const bcContainer = document.getElementById('expand-breadcrumb');
           if (!bcContainer) return;

           const pathIndices = [];
           let idx = currentNodeIndex;
           while (idx >= 0 && tlData.bar_data[idx]) {
               pathIndices.unshift(idx);
               idx = tlData.bar_data[idx].parent_index;
           }

           let html = '';
           pathIndices.forEach((ni, i) => {
               const info = tlData.bar_data[ni];
               const isCurrent = (ni === currentNodeIndex);
               const countSuffix = info.multiplier > 1 ? ' ×' + info.multiplier : '';
               const label = info.name + countSuffix;

               if (i > 0) {
                   html += '<span class="breadcrumb-sep">›</span>';
               }
               html += '<span class="breadcrumb-item' + (isCurrent ? ' current' : '') +
                   '" data-node-index="' + ni + '">' + label + '</span>';
           });

           bcContainer.innerHTML = html;

           bcContainer.querySelectorAll('.breadcrumb-item:not(.current)').forEach(item => {
               const ni = parseInt(item.dataset.nodeIndex);
               item.addEventListener('click', (e) => {
                   e.stopPropagation();
                   const targetIdx = navHistory.indexOf(ni);
                   if (targetIdx >= 0) {
                       navHistory = navHistory.slice(0, targetIdx);
                   }
                   showNodeChildren(ni, false);
               });
           });
       }

       function goBackToParent() {
           if (navHistory.length === 0) {
               hideExpandArea();
               return;
           }
           const prevNodeIndex = navHistory.pop();
           showNodeChildren(prevNodeIndex, false);
       }

      function hideExpandArea() {
          const expandArea = document.getElementById('timeline-expand-area');
          if (expandArea) {
              expandArea.style.display = 'none';
              currentExpandedNode = null;
              navHistory = [];
          }
      }

    document.addEventListener('DOMContentLoaded', function() {
        let kernelsVisible = true;
        const kernelBtn = document.getElementById('toggle-kernels-btn');
        kernelBtn.addEventListener('click', () => {
            kernelsVisible = !kernelsVisible;
            toggleKernels(kernelsVisible);
            kernelBtn.textContent = kernelsVisible ? '\u9690\u85cfKernel\u5e8f\u5217' : '\u663e\u793aKernel\u5e8f\u5217';
        });

        let kernelMetaVisible = true;
        const kernelMetaBtn = document.getElementById('toggle-kernel-meta-btn');
        kernelMetaBtn.addEventListener('click', () => {
            kernelMetaVisible = !kernelMetaVisible;
            document.querySelectorAll('.kernel-meta').forEach(el => {
                el.style.display = kernelMetaVisible ? 'grid' : 'none';
            });
            kernelMetaBtn.textContent = kernelMetaVisible ? '\u9690\u85cfKernel\u4fe1\u606f' : '\u663e\u793aKernel\u4fe1\u606f';
        });

        let allExpanded = false;
        const expandBtn = document.getElementById('toggle-expand-btn');
        const depthSelect = document.getElementById('depth-select');
        expandBtn.addEventListener('click', () => {
            allExpanded = !allExpanded;
            if (allExpanded) {
                const maxDepth = parseInt(depthSelect.value);
                document.querySelectorAll('.tree-node').forEach(node => {
                    const depth = parseInt(node.dataset.depth);
                    if (!node.classList.contains('leaf') && !node.classList.contains('kernel-only')) {
                        if (depth < maxDepth) {
                            node.classList.remove('collapsed');
                            node.classList.add('expanded');
                        } else {
                            node.classList.remove('expanded');
                            node.classList.add('collapsed');
                        }
                    }
                });
                expandBtn.textContent = '\u5168\u90e8\u6536\u8d77';
            } else {
                document.querySelectorAll('.tree-node:not(.leaf)').forEach(node => {
                    node.classList.remove('expanded');
                    node.classList.add('collapsed');
                });
                expandBtn.textContent = '\u5168\u90e8\u5c55\u5f00';
            }
        });

        depthSelect.addEventListener('change', () => {
            const maxDepth = parseInt(depthSelect.value);
            document.querySelectorAll('.tree-node').forEach(node => {
                const depth = parseInt(node.dataset.depth);
                if (!node.classList.contains('leaf') && !node.classList.contains('kernel-only')) {
                    if (depth < maxDepth) {
                        node.classList.remove('collapsed');
                        node.classList.add('expanded');
                    } else {
                        node.classList.remove('expanded');
                        node.classList.add('collapsed');
                    }
                }
            });
            if (allExpanded) {
                expandBtn.textContent = '\u5168\u90e8\u6536\u8d77';
            }
        });

        let auxiliaryVisible = false;
        const auxiliaryBtn = document.getElementById('toggle-auxiliary-btn');
        document.querySelectorAll('.tree-node[data-category="auxiliary"]').forEach(node => {
            node.style.display = 'none';
        });
        document.querySelectorAll('.timeline-node-item[data-category="auxiliary"]').forEach(node => {
            node.style.display = 'none';
        });
        auxiliaryBtn.addEventListener('click', () => {
            auxiliaryVisible = !auxiliaryVisible;
            document.querySelectorAll('.tree-node[data-category="auxiliary"]').forEach(node => {
                node.style.display = auxiliaryVisible ? '' : 'none';
            });
            document.querySelectorAll('.timeline-node-item[data-category="auxiliary"]').forEach(node => {
                node.style.display = auxiliaryVisible ? '' : 'none';
            });
            auxiliaryBtn.textContent = auxiliaryVisible ? '\u9690\u85cf\u8f85\u52a9\u5c42\u6b21' : '\u663e\u793a\u8f85\u52a9\u5c42\u6b21';
        });

        const fieldsPanel = document.getElementById('kernel-fields-panel');
        const fieldsBtn = document.getElementById('kernel-fields-btn');

        fieldsPanel.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            cb.checked = defaultFields.includes(cb.value);
        });

        fieldsBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            fieldsPanel.classList.toggle('visible');
        });

        document.addEventListener('click', (e) => {
            if (!e.target.closest('.kernel-fields-config')) {
                fieldsPanel.classList.remove('visible');
            }
        });

        fieldsPanel.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            cb.addEventListener('change', updateKernelMetaFields);
        });

        document.getElementById('fields-select-all').addEventListener('click', (e) => {
            e.stopPropagation();
            fieldsPanel.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = true);
            updateKernelMetaFields();
        });

        document.getElementById('fields-select-none').addEventListener('click', (e) => {
            e.stopPropagation();
            fieldsPanel.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
            updateKernelMetaFields();
        });

        document.getElementById('fields-reset').addEventListener('click', (e) => {
            e.stopPropagation();
            fieldsPanel.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                cb.checked = defaultFields.includes(cb.value);
            });
            updateKernelMetaFields();
        });

        let semanticAllExpanded = false;
        const semanticBtn = document.getElementById('toggle-semantic-btn');

        semanticBtn.addEventListener('click', () => {
            semanticAllExpanded = !semanticAllExpanded;
            document.querySelectorAll('.node-semantic-wrapper').forEach(w => {
                if (semanticAllExpanded) {
                    w.classList.add('expanded');
                } else {
                    const full = w.dataset.full || '';
                    if (full.length > 120) {
                        w.classList.remove('expanded');
                    }
                }
            });
            semanticBtn.textContent = semanticAllExpanded ? '\u6536\u8d77\u5168\u90e8\u8bed\u4e49' : '\u5c55\u5f00\u5168\u90e8\u8bed\u4e49';
        });

        document.getElementById('theme-select').addEventListener('change', function() {
            applyTheme(this.value);
        });

        document.addEventListener('click', function(e) {
            const btn = e.target.closest('.semantic-expand-btn');
            if (!btn) return;
            e.stopPropagation();
            const wrapper = btn.closest('.node-semantic-wrapper');
            if (wrapper) {
                wrapper.classList.toggle('expanded');
            }
        });

        document.querySelectorAll('.tree-node:not(.leaf)').forEach(node => {
            const header = node.querySelector('.node-header');
            header.addEventListener('click', (e) => {
                if (e.target.closest('[data-type="kernel"]')) return;
                if (e.target.closest('.semantic-expand-btn')) return;
                if (e.target.closest('.node-semantic-wrapper')) return;
                if (e.target.closest('.kernel-info-btn')) return;
                node.classList.toggle('collapsed');
                node.classList.toggle('expanded');
            });
        });

        document.addEventListener('click', (e) => {
            if (!e.target.closest('.tree-node[data-type="kernel"]') &&
                !e.target.closest('.kernel-tooltip') &&
                !e.target.closest('.kernel-info-btn')) {
                hideTooltip();
            }
        });

        document.querySelectorAll('.kernel-info-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                showTooltip(btn);
            });
        });

        if (currentTooltip) {
            currentTooltip.addEventListener('mouseleave', hideTooltip);
        }

        initTheme();

/* ========== Timeline Event Listeners ========== */
         document.querySelectorAll('.timeline-node-item').forEach(item => {
             const ni = parseInt(item.dataset.nodeIndex);
             const info = tlData.bar_data ? tlData.bar_data[ni] : null;
             if (!info) return;

             item.addEventListener('mouseenter', () => showTimelineTooltip(item, info));
             item.addEventListener('mouseleave', () => setTimeout(() => { if (!tlTooltip || !tlTooltip.matches(':hover')) hideTimelineTooltip(); }, 150));
             item.addEventListener('click', (e) => {
                 e.stopPropagation();
                 hideTimelineTooltip();
                 if (info.has_children) {
                     showNodeChildren(ni);
                 } else {
                     showOpsDetail(ni);
                 }
             });
         });

         if (tlTooltip) {
             tlTooltip.addEventListener('mouseleave', hideTimelineTooltip);
         }

          const expandCloseBtn = document.getElementById('expand-close-btn');
          if (expandCloseBtn) {
              expandCloseBtn.addEventListener('click', hideExpandArea);
          }

          const detailCloseBtn = document.getElementById('timeline-detail-close');
         if (detailCloseBtn) {
             detailCloseBtn.addEventListener('click', () => {
                 document.getElementById('timeline-detail-panel').classList.remove('visible');
             });
         }

         document.addEventListener('click', (e) => {
             if (!e.target.closest('.timeline-node-item') && !e.target.closest('.timeline-tooltip') &&
                 !e.target.closest('.timeline-expand-area') && !e.target.closest('.timeline-detail-panel')) {
                 hideTimelineTooltip();
             }
         });
    });
    </script>
    """
    return js_code


def generate_kernel_tooltip_html(kernel: dict, semantic_info: dict = None) -> str:
    all_fields = kernel.get('all_fields', {})
    idx = kernel.get('index', '')

    parts = [f'<div class="kernel-tooltip-header">{kernel.get("name", "Unknown")}</div>']

    if semantic_info:
        semantic = semantic_info.get('semantic', '')
        shape_semantic = semantic_info.get('shape_semantic', '')
        path = semantic_info.get('path', '')
        code_ref = semantic_info.get('code_ref', '')
        if semantic or shape_semantic:
            code_ref_html = f'<br/><small>Code: {code_ref}</small>' if code_ref else ''
            shape_html = f'<br/><small class="kernel-shape-semantic">{shape_semantic}</small>' if shape_semantic else ''
            parts.append(f'<div class="kernel-tooltip-semantic">{semantic}{shape_html}<br/><small>Path: {path}</small>{code_ref_html}</div>')

    parts.append('<div class="kernel-tooltip-container">')
    idx_display = all_fields.get('index', idx)
    parts.append(f'<div class="kernel-tooltip-label">Index:</div>')
    parts.append(f'<div class="kernel-tooltip-value" style="margin-bottom:8px">{idx_display}</div>')

    long_fields = {'input_shapes', 'output_shapes', 'input_data_types', 'output_data_types',
                    'input_formats', 'output_formats'}

    def format_field_val(key):
        raw_key = f'{key}_raw'
        display_val = None
        if raw_key in all_fields:
            val = all_fields[raw_key]
            if val is not None and val != '' and val != 'N/A':
                suffix = ' us' if key.endswith('_us') else ''
                display_val = f'{val}{suffix}'
        else:
            val = all_fields.get(key)
            if val is not None and val != '' and val != 'N/A':
                display_val = format_field_display(key, val)
        return display_val

    def render_group(title, fields):
        group_parts = []
        has_content = False
        for key, _ in fields:
            val = all_fields.get(key)
            if val is not None and val != '' and val != 'N/A':
                has_content = True
                break
        if has_content:
            group_parts.append(f'<div class="kernel-tooltip-section">{title}</div>')
            group_parts.append('<div class="kernel-tooltip-group-grid">')
            for key, label in fields:
                display_val = format_field_val(key)
                if display_val is not None:
                    if key in long_fields:
                        group_parts.append(f'<div class="kernel-tooltip-full"><span class="kernel-tooltip-label">{label}:</span><span class="kernel-tooltip-value">{display_val}</span></div>')
                    else:
                        group_parts.append(f'<div class="kernel-tooltip-label">{label}</div>')
                        group_parts.append(f'<div class="kernel-tooltip-value">{display_val}</div>')
            group_parts.append('</div>')
        return ''.join(group_parts) if has_content else None

    group_rows = [
        [
            ('Basic Info & Timing', [
                ('type', 'Type'),
                ('op_state', 'OP State'),
                ('accelerator_core', 'Acc Core'),
                ('duration_us', 'Duration'),
                ('start_time_us', 'Start'),
                ('wait_time_us', 'Wait'),
            ]),
            ('Stream/Device', [
                ('stream_id', 'Stream'),
                ('device_id', 'Device'),
                ('task_id', 'Task ID'),
                ('block_dim', 'Block Dim'),
            ]),
            ('Tensor Info', [
                ('input_shapes', 'Input Shapes'),
                ('input_data_types', 'Input DType'),
                ('input_formats', 'Input Fmt'),
                ('output_shapes', 'Output Shapes'),
                ('output_data_types', 'Output DType'),
                ('output_formats', 'Output Fmt'),
            ]),
        ],
        [
            ('AI Core Metrics', [
                ('aicore_time_us', 'AI Core Time'),
                ('aic_mac_time_us', 'MAC Time'),
                ('aic_mac_ratio', 'MAC Ratio'),
                ('aic_scalar_time_us', 'Scalar Time'),
                ('aic_mte1_time_us', 'MTE1 Time'),
                ('aic_mte2_time_us', 'MTE2 Time'),
                ('aic_fixpipe_time_us', 'FixPipe Time'),
                ('aic_icache_miss_rate', 'ICache Miss'),
                ('cube_utilization_pct', 'Cube Util'),
            ]),
            ('AI Vector Metrics', [
                ('aiv_time_us', 'AI Vector Time'),
                ('aiv_vec_time_us', 'Vector Time'),
                ('aiv_vec_ratio', 'Vec Ratio'),
                ('aiv_scalar_time_us', 'Scalar Time'),
                ('aiv_mte2_time_us', 'MTE2 Time'),
                ('aiv_mte3_time_us', 'MTE3 Time'),
                ('aiv_icache_miss_rate', 'ICache Miss'),
            ]),
            ('Others', [
                ('mix_block_dim', 'Mix Block Dim'),
                ('hf32_eligible', 'HF32 Eligible'),
                ('context_id', 'Context ID'),
                ('aic_total_cycles', 'AI Core Cycles'),
                ('aic_scalar_ratio', 'Scalar Ratio'),
                ('aic_mte1_ratio', 'MTE1 Ratio'),
                ('aic_mte2_ratio', 'MTE2 Ratio'),
                ('aic_fixpipe_ratio', 'FixPipe Ratio'),
                ('aic_mac_fp16_ratio', 'MAC FP16'),
                ('aic_mac_int8_ratio', 'MAC INT8'),
                ('aic_cube_fops', 'Cube FLOPs'),
                ('aiv_total_cycles', 'AIV Cycles'),
                ('aiv_scalar_ratio', 'AIV Scalar Ratio'),
                ('aiv_mte2_ratio', 'AIV MTE2 Ratio'),
                ('aiv_mte3_ratio', 'AIV MTE3 Ratio'),
                ('aiv_vec_fp32_ratio', 'Vec FP32'),
                ('aiv_vec_fp16_ratio', 'Vec FP16'),
                ('aiv_vec_int32_ratio', 'Vec INT32'),
                ('aiv_vec_misc_ratio', 'Vec Misc'),
                ('aiv_vector_fops', 'Vector FLOPs'),
            ]),
        ],
    ]

    for row in group_rows:
        row_parts = []
        for group_title, fields in row:
            group_html = render_group(group_title, fields)
            if group_html:
                row_parts.append(f'<div class="kernel-tooltip-group">{group_html}</div>')
        if row_parts:
            parts.append('<div class="kernel-tooltip-row">')
            parts.extend(row_parts)
            parts.append('</div>')

    parts.append('</div>')
    return ''.join(parts)


def compute_core_ratios(node: dict, operators: list) -> tuple:
    """计算节点的 cube占比 / vector占比 / 未掩盖通信占比。

    分母统一用该节点的 kernel_sum（节点内所有算子 duration 之和）。
    - cube%  = Σ aicore_time_us / kernel_sum
    - vec%   = Σ aiv_time_us    / kernel_sum
    - comm%  = 未被计算掩盖的通信时间 / kernel_sum
               （通信算子区间减去与计算算子区间的重叠部分）
    MIX 算子的 cube 与 vector 时间会同时计入，故 cube%+vec% 可能略超/不足 100%。
    """
    indices = collect_all_op_indices(node)
    op_dict = {op['index']: op for op in operators}
    ops = [op_dict[i] for i in indices if i in op_dict]
    if not ops:
        return 0.0, 0.0, 0.0

    kernel_sum = sum(bc.effective_duration_us(o) for o in ops)
    if kernel_sum <= 0:
        return 0.0, 0.0, 0.0

    cube = sum(o.get('aicore_time_us', 0) or 0 for o in ops)
    vec = sum(o.get('aiv_time_us', 0) or 0 for o in ops)

    def _is_comm(o):
        return str(o.get('accelerator_core', '')).upper() == 'COMMUNICATION'

    comm_iv = [(o.get('start_time_us', 0), o.get('start_time_us', 0) + o.get('duration_us', 0))
               for o in ops if _is_comm(o)]
    comp_iv = [(o.get('start_time_us', 0), o.get('start_time_us', 0) + o.get('duration_us', 0))
               for o in ops if not _is_comm(o)]
    exposed_comm = _exposed_interval(comm_iv, comp_iv)

    return cube / kernel_sum * 100, vec / kernel_sum * 100, exposed_comm / kernel_sum * 100


def _exposed_interval(target_iv: list, mask_iv: list) -> float:
    """返回 target_iv 区间中未被 mask_iv 覆盖的总长度（用于未掩盖通信）。"""
    if not target_iv:
        return 0.0
    # 合并 mask
    mask = sorted(mask_iv)
    merged = []
    for s, e in mask:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    exposed = 0.0
    for ts, te in target_iv:
        cur = ts
        for ms, me in merged:
            if me <= cur:
                continue
            if ms >= te:
                break
            if ms > cur:
                exposed += min(ms, te) - cur
            cur = max(cur, me)
            if cur >= te:
                break
        if cur < te:
            exposed += te - cur
    return exposed


def _model_core_ratios(operators: list) -> tuple:
    """整模型根节点的 cube/vector/未掩盖通信 占比（分母=全部算子 kernel_sum）。"""
    return compute_core_ratios({'op_indices': [op['index'] for op in operators]}, operators)


def render_html_tree_node(node: dict, operators: list, total_duration: float, multiplier: int,
                           current_depth: int, max_depth: int, kernel_semantics: dict = None,
                           kernel_display_fields: list = None, data_category: str = '',
                           count_label: str = '层') -> tuple:
    name = node.get('name', 'Unknown')
    display_fields = kernel_display_fields or DEFAULT_KERNEL_DISPLAY_FIELDS
    op_indices = node.get('op_indices', [])
    children = node.get('children', [])

    has_kernels = bool(op_indices)
    has_children = bool(children)
    is_leaf = not has_kernels and not has_children
    is_kernel_only = has_kernels and not has_children

    time_info = get_node_time_span_info(node, operators)
    is_exact_aggregate = '_report_op_indices' in node
    effective_multiplier = 1 if is_exact_aggregate else multiplier
    duration = get_node_total_duration(node, operators) * effective_multiplier

    kernel_count = count_all_kernels(node, operators)

    percentage = format_percentage(duration, total_duration)
    count_str = _count_suffix(multiplier, count_label) if current_depth == 1 else ""

    if not is_leaf and kernel_count > 0:
        kernel_count_str = f'<span class="kernel-count">({kernel_count} kernels)</span>'
        stream_count_str = f'<span class="stream-count" title="{time_info["stream_hover"]}">({time_info["stream_info"]})</span>'
    else:
        kernel_count_str = ''
        stream_count_str = ''

    duration_hover = time_info['calculation'] if kernel_count > 0 else ''
    if duration_hover and multiplier > 1 and not is_exact_aggregate:
        duration_hover = f"{duration_hover} × {multiplier} = {time_info['time_span'] * multiplier:.2f} us"

    default_expanded = current_depth < max_depth
    node_class = 'expanded' if default_expanded else 'collapsed'
    if is_leaf:
        node_class = 'leaf'
    elif is_kernel_only:
        node_class += ' kernel-only'

    category_attr = f' data-category="{data_category}"' if data_category else ''
    html_parts = [f'<li class="tree-node {node_class}" data-depth="{current_depth}" data-type="module"{category_attr}>']
    html_parts.append(f'<div class="node-header">')
    html_parts.append(f'<span class="node-toggle">▶</span>')
    node_semantic = node.get('semantic', '') or node.get('comment', '')
    node_code_ref = node.get('code_ref', '')
    semantic_parts = []
    if node_semantic:
        semantic_parts.append(node_semantic)
    if node_code_ref:
        semantic_parts.append(f'[{node_code_ref}]')
    if semantic_parts:
        full_text = ' | '.join(semantic_parts)
        expand_btn = '<span class="semantic-expand-btn"><svg viewBox="0 0 24 24"><path d="M7 10l5 5 5-5z"/></svg></span>'
        display_text = full_text[:117] + '...' if len(full_text) > 120 else full_text
        semantic_suffix = (f' <span class="node-semantic-wrapper" data-full="{full_text}">'
                           f'<span class="node-semantic-truncated">{display_text}</span>'
                           f'<span class="node-semantic-full">{full_text}</span>'
                           f'{expand_btn}</span>')
    else:
        semantic_suffix = ''
    html_parts.append(f'<span class="node-name">{name}{count_str} {kernel_count_str}{stream_count_str}{semantic_suffix}</span>')
    duration_title = f' title="{duration_hover}"' if duration_hover else ''
    html_parts.append(f'<span class="node-duration"{duration_title}>')
    html_parts.append(f'<span class="duration-us">{format_duration_us(duration)} us</span>')
    html_parts.append(f'<span class="duration-ms">({format_duration_ms(duration)} ms)</span>')
    html_parts.append(f'<span class="duration-pct">({percentage}%)</span>')
    _cube_pct, _vec_pct, _comm_pct = compute_core_ratios(node, operators)
    html_parts.append(f'<span class="ratio-cube" title="AI Core(cube)时间占比 = Σaicore_time / kernel_sum">cube {_cube_pct:.0f}%</span>')
    html_parts.append(f'<span class="ratio-vec" title="AI Vector时间占比 = Σaiv_time / kernel_sum">vec {_vec_pct:.0f}%</span>')
    html_parts.append(f'<span class="ratio-comm" title="未掩盖通信占比 = 暴露通信时间 / kernel_sum">comm {_comm_pct:.0f}%</span>')
    html_parts.append(f'</span>')
    html_parts.append(f'</div>')

    tooltip_parts = []

    if has_kernels or has_children:
        html_parts.append('<ul class="tree-children">')

        if has_children:
            for child in children:
                child_html, child_tooltips = render_html_tree_node(
                    child, operators, total_duration, multiplier, current_depth + 1, max_depth,
                    kernel_semantics, display_fields)
                html_parts.append(child_html)
                tooltip_parts.extend(child_tooltips)

        if has_kernels:
            kernels = get_report_kernel_full_details(node, operators)
            total_kernels = len(kernels)
            for ki, k in enumerate(kernels):
                k_duration_raw = k['duration']
                k_duration_total = k_duration_raw * effective_multiplier
                k_pct = format_percentage(k_duration_total, total_duration)

                idx = k.get('index', 0)
                semantic_info = kernel_semantics.get(idx) if kernel_semantics else None
                tooltip_html = generate_kernel_tooltip_html(k, semantic_info)
                tooltip_parts.append((idx, tooltip_html))

                kernel_seq = f"[{ki+1}/{total_kernels}]"
                kernel_name = k.get('name', 'Unknown')

                # Build kernel semantic wrapper: yellow area shows semantic text only
                k_semantic = semantic_info.get('semantic', '') if semantic_info else ''
                k_shape_semantic = semantic_info.get('shape_semantic', '') if semantic_info else ''
                k_code_ref = semantic_info.get('code_ref', '') if semantic_info else ''
                if k_semantic:
                    k_expand_btn = '<span class="semantic-expand-btn"><svg viewBox="0 0 24 24"><path d="M7 10l5 5 5-5z"/></svg></span>'
                    k_display = k_semantic[:57] + '...' if len(k_semantic) > 60 else k_semantic
                    kernel_semantic_html = (
                        f' <span class="node-semantic-wrapper" data-full="{k_semantic}">'
                        f'<span class="node-semantic-truncated">{k_display}</span>'
                        f'<span class="node-semantic-full">{k_semantic}</span>'
                        f'{k_expand_btn}</span>'
                    )
                else:
                    kernel_semantic_html = ''

                html_parts.append(f'<li class="tree-node leaf" data-depth="{current_depth + 1}" data-type="kernel">')
                html_parts.append(f'<div class="node-header">')
                html_parts.append(f'<span class="node-spacer"></span>')
                html_parts.append(f'<span class="node-name">{kernel_seq} {kernel_name}</span>{kernel_semantic_html}')
                html_parts.append(f'<span class="kernel-info-btn" data-index="{idx}"><svg viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg></span>')
                html_parts.append(f'<span class="node-duration">')
                html_parts.append(f'<span class="duration-us">{format_duration_us(k_duration_total)} us</span>')
                html_parts.append(f'<span class="duration-pct">({k_pct}%)</span>')
                html_parts.append(f'</span>')
                html_parts.append(f'</div>')

                html_parts.append(f'<div class="kernel-meta">')
                for field_key in ALL_KERNEL_META_FIELDS:
                    label = KERNEL_FIELD_LABELS.get(field_key, field_key)
                    value = get_kernel_field_value(k, field_key, effective_multiplier, total_duration)
                    is_default = field_key in display_fields
                    style_attr = '' if is_default else ' style="display:none"'
                    # Add shape_semantic hover tooltip on Input/Output fields
                    # Split at first → so Input shows input-side, Output shows output-side
                    if field_key in ('input_shapes', 'output_shapes') and k_shape_semantic:
                        tip_cls = ' shape-semantic-tip'
                        _arrow = '→'
                        if _arrow in k_shape_semantic:
                            _parts = k_shape_semantic.split(_arrow, 1)
                            _tip = _parts[0].strip() if field_key == 'input_shapes' else _parts[1].strip()
                        else:
                            _tip = k_shape_semantic
                        tip_attr = f' data-shape-semantic="{_tip}"'
                    else:
                        tip_cls = ''
                        tip_attr = ''
                    html_parts.append(f'<span class="kernel-meta-item{tip_cls}" data-field="{field_key}"{style_attr}{tip_attr}><span class="kernel-meta-label">{label}:</span><span class="kernel-meta-value">{value}</span></span>')
                html_parts.append(f'</div>')
                html_parts.append(f'</li>')

        html_parts.append('</ul>')

    html_parts.append('</li>')
    return '\n'.join(html_parts), tooltip_parts


def generate_html_tree_section(config: dict, operators: list, total_duration: float,
                               max_depth: int, kernel_display_fields: list = None) -> tuple:
    model_name = config.get('model_name', 'Model')
    display_name, _ = _extract_model_display_name(model_name)
    kernel_semantics = collect_kernel_semantics(config)
    display_fields = kernel_display_fields or DEFAULT_KERNEL_DISPLAY_FIELDS

    if operators:
        model_duration = sum(bc.effective_duration_us(op) for op in operators)
        earliest_op = min(operators, key=lambda op: op.get('start_time_us', 0))
        latest_op = max(operators, key=lambda op: op.get('start_time_us', 0) + op.get('duration_us', 0))
        min_start = earliest_op.get('start_time_us', 0)
        max_end = latest_op.get('start_time_us', 0) + latest_op.get('duration_us', 0)
        earliest_name = earliest_op.get('normalized_name') or earliest_op.get('type', 'Unknown')
        latest_name = latest_op.get('normalized_name') or latest_op.get('type', 'Unknown')
        latest_start = latest_op.get('start_time_us', 0)
        latest_duration = latest_op.get('duration_us', 0)
        time_span = max_end - min_start
        calculation = f"{latest_name}({latest_start:.2f}+{latest_duration:.2f}) - {earliest_name}({min_start:.2f}) = {time_span:.2f} us"
    else:
        model_duration = 0
        calculation = ''
    percentage = format_percentage(model_duration, total_duration)

    kernel_count = len(operators)

    stream_counts = {}
    for op in operators:
        sid = op.get('stream_id', 'unknown')
        stream_counts[sid] = stream_counts.get(sid, 0) + 1
    stream_count = len(stream_counts)
    stream_hover = '&#10;'.join([f"Stream {sid}: {cnt}" for sid, cnt in sorted(stream_counts.items(), key=lambda x: -x[1])]) if stream_counts else ''
    stream_info = f"{stream_count} streams" if stream_count > 0 else ''

    stages = config.get('stages', {})
    runtime_aux = config.get('runtime_auxiliary', [])

    html_parts = ['<section id="analysis">', '<div class="tree">', '<ul class="tree-root">']

    duration_hover = calculation if calculation else ''

    html_parts.append(f'<li class="tree-node expanded" data-depth="0" data-type="module">')
    html_parts.append(f'<div class="node-header">')
    html_parts.append(f'<span class="node-toggle">▶</span>')
    html_parts.append(f'<span class="node-name">{display_name}</span>')
    duration_title = f' title="{duration_hover}"' if duration_hover else ''
    html_parts.append(f'<span class="node-duration"{duration_title}>')
    html_parts.append(f'<span class="duration-us">{format_duration_us(model_duration)} us</span>')
    html_parts.append(f'<span class="duration-ms">({format_duration_ms(model_duration)} ms)</span>')
    html_parts.append(f'<span class="duration-pct">({percentage}%)</span>')
    _m_cube, _m_vec, _m_comm = _model_core_ratios(operators)
    html_parts.append(f'<span class="ratio-cube" title="AI Core(cube)时间占比 = Σaicore_time / kernel_sum">cube {_m_cube:.0f}%</span>')
    html_parts.append(f'<span class="ratio-vec" title="AI Vector时间占比 = Σaiv_time / kernel_sum">vec {_m_vec:.0f}%</span>')
    html_parts.append(f'<span class="ratio-comm" title="未掩盖通信占比 = 暴露通信时间 / kernel_sum">comm {_m_comm:.0f}%</span>')
    html_parts.append(f'</span>')
    html_parts.append(f'</div>')
    html_parts.append('<ul class="tree-children">')

    all_tooltips = []

    for stage_name, stage_info in stages.items():
        stage_indices = stage_info.get('stage_indices', [0])
        stage_count = len(stage_indices) if stage_indices else 1
        node_html, node_tooltips = render_html_tree_node(
            stage_info, operators, total_duration, stage_count, 1, max_depth,
            kernel_semantics, display_fields, data_category='auxiliary',
            count_label='实例')
        html_parts.append(node_html)
        all_tooltips.extend(node_tooltips)

    layer_label = 'invocations' if config.get('schema_version') == 2 else '层'
    for name, structure, layer_count in iter_layer_sections(config):
        node_html, node_tooltips = render_html_tree_node(
            structure, operators, total_duration, layer_count, 1, max_depth,
            kernel_semantics, display_fields, count_label=layer_label)
        html_parts.append(node_html)
        all_tooltips.extend(node_tooltips)

    for aux in runtime_aux:
        node_html, node_tooltips = render_html_tree_node(
            aux, operators, total_duration, 1, 1, max_depth,
            kernel_semantics, display_fields, data_category='auxiliary')
        html_parts.append(node_html)
        all_tooltips.extend(node_tooltips)

    html_parts.extend(['</ul>', '</li>', '</ul>', '</div>', '</section>'])

    return '\n'.join(html_parts), dict(all_tooltips)


def _extract_model_display_name(model_name: str) -> tuple:
    base_name = model_name
    architecture_desc = ''
    paren_start = model_name.find('(')
    if paren_start >= 0:
        paren_end = model_name.rfind(')')
        if paren_end > paren_start:
            architecture_desc = model_name[paren_start + 1:paren_end].strip()
            base_name = model_name[:paren_start].strip()
    return base_name, architecture_desc


def _gate_banner_html(gate_banner: list) -> str:
    """Render the validation-gate banner as an HTML block (empty string when there is none)."""
    if not gate_banner:
        return ''
    import html as _html
    lines = []
    for raw in gate_banner:
        text = str(raw).strip()
        # The banner is authored as Markdown; its '##' heading would otherwise render as a
        # bullet that duplicates gate-banner-title.
        if text.startswith('#'):
            continue
        text = text.lstrip('- ').strip()
        if not text:
            continue
        text = _html.escape(text)
        # keep **bold** emphasis from the markdown banner
        while '**' in text:
            text = text.replace('**', '<strong>', 1)
            if '**' in text:
                text = text.replace('**', '</strong>', 1)
            else:
                text += '</strong>'
        lines.append(f'<li>{text}</li>')
    if not lines:
        return ''
    override = any('allow-warnings' in str(b) for b in gate_banner)
    cls = 'gate-banner gate-banner-override' if override else 'gate-banner'
    return (f'<div class="{cls}">'
            f'<div class="gate-banner-title">校验状态</div>'
            f'<ul>{"".join(lines)}</ul></div>')


def generate_html_report(raw_ops: dict, config: dict, operators: list, total_duration: float,
                        depth: int, raw_ops_path: str, config_path: str, theme: str = 'dracula',
                        kernel_display_fields: list = None, gate_banner: list = None) -> str:
    import datetime
    model_name = config.get('model_name', 'Model')
    display_name, architecture_desc = _extract_model_display_name(model_name)
    generate_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    kernel_count = raw_ops.get('kernel_count', len(operators))
    step_id = raw_ops.get('step_id', 'N/A')

    display_fields = kernel_display_fields or DEFAULT_KERNEL_DISPLAY_FIELDS
    tree_html, tooltip_data = generate_html_tree_section(config, operators, total_duration, depth, kernel_display_fields)
    timeline_html, timeline_data = generate_timeline_html(config, operators, total_duration, depth)

    import json as _json
    fields_json = _json.dumps(display_fields, ensure_ascii=False)

    html_parts = [
        '<!DOCTYPE html>',
        # data-theme must be on the tag statically. The CSS defines every palette under
        # [data-theme="..."]; only initTheme() used to set it, so if anything in the 2.6 MB
        # inline script threw before that ran, the page kept just the :root fallbacks and
        # --theme was silently ignored.
        f'<html lang="zh-CN" data-theme="{theme}">',
        '<head>',
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f'<title>{display_name} 性能分析</title>',
        get_html_css(),
        '</head>',
        '<body>',
        f'<h1>{display_name} 性能分析</h1>',
        # The validation gate banner must appear in HTML too. It used to be injected only
        # into the Markdown path, so an --allow-warnings run produced an HTML report that
        # silently hid its own override — the reader had no way to see the run was
        # exploratory. Same failure shape the checks themselves were just corrected for.
        _gate_banner_html(gate_banner),
        '<div class="metadata">',
        '<div class="meta-row">',
        f'<div class="meta-item"><span class="meta-label">生成时间:</span><span class="meta-value">{generate_time}</span></div>',
        f'<div class="meta-item"><span class="meta-label">总耗时:</span><span class="meta-value">{format_duration_us(total_duration)} us ({format_duration_ms(total_duration)} ms)</span></div>',
        f'<div class="meta-item"><span class="meta-label">Step:</span><span class="meta-value">{step_id}</span></div>',
        f'<div class="meta-item"><span class="meta-label">Kernel数量:</span><span class="meta-value">{kernel_count}</span></div>',
        '</div>',
        '<div class="meta-row">',
        '<div class="meta-item" style="flex-direction: column; align-items: flex-start; gap: 4px;">',
        '<span class="meta-label">数据源:</span>',
        '<div class="meta-datasources">',
        f'<div class="meta-datasource-item">{raw_ops_path}</div>',
        f'<div class="meta-datasource-item">{config_path}</div>',
        '</div>',
        '</div>',
        '</div>',
        '<div class="meta-row">',
        f'<div class="meta-item"><span class="meta-label">模型简介:</span><span class="meta-value">{architecture_desc}</span></div>' if architecture_desc else '',
        '</div>',
        '</div>',
        '<div class="controls">',
        '<button id="toggle-expand-btn">全部展开</button>',
        '<select id="depth-select">',
        '<option value="1">1层</option>',
        '<option value="2">2层</option>',
        '<option value="3" selected>3层</option>',
        '<option value="4">4层</option>',
        '<option value="999">全部</option>',
        '</select>',
        '<button id="toggle-auxiliary-btn">显示辅助层次</button>',
        '<button id="toggle-kernels-btn">隐藏Kernel序列</button>',
        '<button id="toggle-kernel-meta-btn">隐藏Kernel信息</button>',
        '<div class="kernel-fields-config">',
        '<button id="kernel-fields-btn">⚙Kernel显示配置</button>',
        '<div class="kernel-fields-panel" id="kernel-fields-panel">',
        '<label><input type="checkbox" value="stream_id" checked> Stream</label>',
        '<label><input type="checkbox" value="input_shapes" checked> Input Shapes</label>',
        '<label><input type="checkbox" value="output_shapes" checked> Output Shapes</label>',
        '<label><input type="checkbox" value="start_time_us"> Start Time</label>',
        '<label><input type="checkbox" value="duration_us"> Duration</label>',
        '<label><input type="checkbox" value="wait_time_us"> Wait Time</label>',
        '<label><input type="checkbox" value="device_id"> Device</label>',
        '<label><input type="checkbox" value="task_id"> Task ID</label>',
        '<label><input type="checkbox" value="type"> Type</label>',
        '<label><input type="checkbox" value="op_state"> OP State</label>',
        '<label><input type="checkbox" value="accelerator_core"> Acc Core</label>',
        '<label><input type="checkbox" value="block_dim"> Block Dim</label>',
        '<label><input type="checkbox" value="input_data_types"> In DType</label>',
        '<label><input type="checkbox" value="output_data_types"> Out DType</label>',
        '<label><input type="checkbox" value="input_formats"> In Fmt</label>',
        '<label><input type="checkbox" value="output_formats"> Out Fmt</label>',
        '<div class="kernel-fields-actions">',
        '<button id="fields-select-all">全选</button>',
        '<button id="fields-select-none">全不选</button>',
        '<button id="fields-reset">默认</button>',
        '</div>',
        '</div>',
        '</div>',
        '<button id="toggle-semantic-btn">展开全部语义</button>',
        '<label>主题风格: <select id="theme-select">',
        '<option value="dracula" selected>Dracula</option>',
        '<option value="vscode-dark">VS Code Dark</option>',
        '<option value="one-dark">One Dark Pro</option>',
        '<option value="github-light">GitHub Light</option>',
        '<option value="solarized-light">Solarized Light</option>',
        '</select></label>',
        '</div>',
        tree_html,
        timeline_html,
        get_html_js(theme, tooltip_data, display_fields, timeline_data),
        '</body>',
        '</html>'
    ]

    return '\n'.join(html_parts)


def _load_validation_gate(validation_report_path, allow_warnings):
    """Return (ok, banner_lines). Report generation requires status=passed unless allow_warnings."""
    if not validation_report_path:
        return True, ["> ⚠ 未提供 validation report（--validation-report）；建议先运行 run_validation.py。", ""]
    try:
        with open(validation_report_path, 'r', encoding='utf-8') as f:
            vr = json.load(f)
    except (OSError, ValueError) as e:
        return False, [f"> validation report 读取失败: {e}"]
    status = vr.get('status')
    banner = [
        "## 校验状态（validation）",
        "",
        f"- status: **{status}**  errors={vr.get('error_count')}  warnings={vr.get('warning_count')}",
    ]
    # surface the exact-coverage breakdown if present
    for chk in vr.get('checks', []):
        if chk.get('name') == 'coverage' and isinstance(chk.get('detail'), dict):
            d = chk['detail']
            banner.append(f"- coverage: total={d.get('total_ops')} model={d.get('model_mapped')} "
                          f"runtime={d.get('runtime_mapped')} excluded={d.get('excluded')} "
                          f"unmapped={d.get('unmapped')} duplicate={d.get('duplicate')} "
                          f"exact={d.get('exact_coverage_pct')}%")
    if vr.get('allow_warnings'):
        banner.append("- ⚠ **--allow-warnings override 已启用**（探索性运行，warning 未阻断）")
    if status == 'exploratory':
        banner.append("- 🚫 **EXPLORATORY / 未验证**：存在 unmapped 算子，映射不完整。"
                      "本报告**不是正式结果**，禁止据此下性能结论。")
    banner.append("")
    # A formal report requires status EXACTLY `passed`. `passed_with_warnings` means someone
    # chose not to act on open warnings, and `exploratory` means the mapping is incomplete;
    # neither may become a report a reader would treat as a result. `--allow-warnings` no
    # longer opens this gate — the flag now only affects standalone run_validation.py triage,
    # and the banner above still records that it was used.
    ok = status == 'passed'
    if not ok and status == 'passed_with_warnings':
        banner.append("- 🚫 **passed_with_warnings 不是正式通过**：请先消除 warning，"
                      "正式报告要求 validation status 精确为 `passed`。")
    return ok, banner


def generate_report(raw_ops_path: str, config_path: str, output_path: str = None,
                    depth: int = 3, html: bool = False, html_output: str = None,
                    theme: str = 'vscode-dark', kernel_display_fields: list = None,
                    validation_report: str = None, allow_warnings: bool = False) -> str:
    raw_ops_file = validate_file_exists(raw_ops_path)
    config_file = validate_file_exists(config_path)

    raw_ops = load_json(raw_ops_file)
    config = load_json(config_file)

    validate_raw_ops(raw_ops)
    validate_analysis_config(config)

    is_v2 = config.get('schema_version') == 2
    gate_ok, gate_banner = _load_validation_gate(validation_report, allow_warnings)
    if not gate_ok:
        raise ValueError(
            "validation 未通过（status != passed）。请修复后重试，或用 --allow-warnings 进行探索性生成。\n"
            + '\n'.join(gate_banner))

    def _prefix_sections():
        parts = ['\n'.join(gate_banner)]
        if is_v2:
            parts.append(generate_architecture_section(config))
        return parts

    operators = raw_ops.get('operators', [])
    total_duration = raw_ops.get('total_duration_us', 1)

    report = None

    if output_path:
        report_parts = []
        report_parts.append(f"# {config.get('model_name', 'Model')} 性能拆解报告")
        report_parts.append("")
        report_parts.extend(_prefix_sections())
        report_parts.append(generate_analysis_section(config, operators, total_duration, depth))
        report = '\n'.join(report_parts)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"Markdown报告已生成: {output_path}")

    if html:
        html_content = generate_html_report(raw_ops, config, operators, total_duration, depth,
                                            raw_ops_path, config_path, theme,
                                            kernel_display_fields=kernel_display_fields,
                                            gate_banner=gate_banner)
        if html_output:
            html_path = html_output
        elif output_path:
            html_path = str(Path(output_path).with_suffix('.html'))
        else:
            html_path = 'report.html'
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"HTML报告已生成: {html_path}")

    if not output_path and not html:
        report_parts = []
        report_parts.append(f"# {config.get('model_name', 'Model')} 性能拆解报告")
        report_parts.append("")
        report_parts.extend(_prefix_sections())
        report_parts.append(generate_analysis_section(config, operators, total_duration, depth))
        report = '\n'.join(report_parts)

    return report


def main():
    parser = argparse.ArgumentParser(
        description='NPU 性能拆解报告生成脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  %(prog)s raw_ops.json analysis_config.json
  %(prog)s raw_ops.json analysis_config.json -o report.md
  %(prog)s -r raw_ops.json -c analysis_config.json -o report.md
  %(prog)s raw_ops.json analysis_config.json -d 3 -o report.md
  %(prog)s raw_ops.json analysis_config.json --html
  %(prog)s raw_ops.json analysis_config.json -o report.md --html
        '''
    )

    parser.add_argument('raw_ops', nargs='?', help='算子序列JSON文件路径')
    parser.add_argument('config', nargs='?', help='模型层次拆解JSON文件路径')

    parser.add_argument('-r', '--raw-ops', dest='raw_ops_opt', metavar='FILE',
                        help='算子序列JSON文件路径')
    parser.add_argument('-c', '--config', dest='config_opt', metavar='FILE',
                        help='模型层次拆解JSON文件路径')
    parser.add_argument('-o', '--output', metavar='FILE',
                        help='Markdown输出报告文件路径 (默认打印到标准输出)')
    parser.add_argument('-d', '--depth', type=int, default=3,
                        help='树状结构展示深度 (默认: 3)')
    parser.add_argument('--html', action='store_true',
                        help='生成HTML格式报告')
    parser.add_argument('--html-output', metavar='FILE',
                        help='HTML输出文件路径 (默认: 与-o同名但后缀为.html)')
    parser.add_argument('--theme', choices=['dracula', 'vscode-dark', 'one-dark', 'github-light', 'solarized-light'],
                        default='dracula',
                        help='HTML报告主题风格 (默认: dracula)')
    parser.add_argument('--kernel-fields', metavar='FIELDS',
                        help='kernel默认显示字段(逗号分隔), 如: input_shapes,output_shapes,type,stream_id,start_time_us,duration_us')
    parser.add_argument('--validation-report', metavar='FILE',
                        help='run_validation.py 输出的 validation report JSON；生成报告要求 status=passed')
    parser.add_argument('--allow-warnings', action='store_true',
                        help='探索性生成：允许 status=passed_with_warnings 时继续（会在报告中显著标注 override）')

    args = parser.parse_args()

    raw_ops_path = args.raw_ops_opt or args.raw_ops
    config_path = args.config_opt or args.config

    if not raw_ops_path or not config_path:
        parser.print_help()
        sys.exit(1)

    kernel_display_fields = None
    if args.kernel_fields:
        kernel_display_fields = [f.strip() for f in args.kernel_fields.split(',') if f.strip()]

    try:
        report = generate_report(raw_ops_path, config_path, args.output, args.depth,
                                 args.html, args.html_output, args.theme,
                                 kernel_display_fields=kernel_display_fields,
                                 validation_report=args.validation_report,
                                 allow_warnings=args.allow_warnings)
        if not args.output and not args.html:
            print(report)
    except FileNotFoundError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"未知错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
