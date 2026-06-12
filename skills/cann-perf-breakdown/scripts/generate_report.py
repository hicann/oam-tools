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
"""NPU 性能拆解报告生成脚本"""

import logging
import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from _common import validate_file_exists, load_json
from _assets import HTML_CSS, JS_TEMPLATE

logger = logging.getLogger(__name__)


@dataclass
class HtmlRenderCtx:
    """HTML 树渲染过程中保持不变的上下文（降低单函数参数个数）。"""
    operators: list
    total_duration: float
    max_depth: int
    kernel_semantics: dict = None
    kernel_display_fields: list = None


@dataclass
class KernelRenderCtx:
    """单个 kernel 叶节点渲染所需的上下文（降低 helper 参数个数）。"""
    ctx: 'HtmlRenderCtx'
    multiplier: int
    current_depth: int
    display_fields: list


@dataclass
class NodeHeaderInfo:
    """模块节点头部计算所需的输入。"""
    time_info: dict
    kernel_count: int
    multiplier: int
    current_depth: int
    max_depth: int
    is_leaf: bool
    is_kernel_only: bool


@dataclass
class NodeHeaderView:
    """模块节点头部渲染所需的展示字段。"""
    name: str
    count_str: str
    node_class: str
    current_depth: int
    data_category: str
    kernel_count_str: str
    stream_count_str: str
    duration_hover: str
    duration: float
    percentage: str


@dataclass
class ReportMeta:
    """HTML 报告 metadata 区所需字段。"""
    generate_time: str
    total_duration: float
    step_id: object
    kernel_count: int
    raw_ops_path: str
    config_path: str
    architecture_desc: str


@dataclass
class TimelineNodeState:
    """generate_timeline_data.process_node 的递归状态。"""
    multiplier: int = 1
    depth: int = 0
    parent_index: int = -1
    is_auxiliary: bool = False


@dataclass
class _TimelineBuildCtx:
    """generate_timeline_data 递归构建过程中共享的可变状态。"""
    op_dict: dict
    timeline_nodes: list
    node_color_map: dict

    def assign_color(self, path: str) -> str:
        parts = path.split('/')
        key = parts[-1] if len(parts) > 1 else parts[0]
        if key not in self.node_color_map:
            self.node_color_map[key] = TIMELINE_PALETTE[len(self.node_color_map) % len(TIMELINE_PALETTE)]
        return self.node_color_map[key]


def _timeline_process_node(node, parent_path, ctx, state=None):
    """递归构建单个 timeline 节点；返回其在 timeline_nodes 中的索引，无算子返回 -1。"""
    if state is None:
        state = TimelineNodeState()
    name = node.get('name', 'Unknown')
    path = f"{parent_path}/{name}" if parent_path else name
    color = ctx.assign_color(path)

    all_ops_indices = _collect_node_op_indices_all(node)
    all_ops = [ctx.op_dict[i] for i in all_ops_indices if i in ctx.op_dict]
    if not all_ops:
        return -1

    stream_set = {str(op.get('stream_id', '0')) for op in all_ops}
    min_start = min(op.get('start_time_us', 0) for op in all_ops)
    max_end = max(op.get('start_time_us', 0) + op.get('duration_us', 0) for op in all_ops)
    per_stream_ops = _build_per_stream_ops(all_ops_indices, ctx.op_dict)
    current_index = len(ctx.timeline_nodes)
    stream_counts = {sid: len(ops) for sid, ops in per_stream_ops.items()}
    dominant_stream = max(stream_counts.items(), key=lambda x: x[1])[0] if stream_counts else '0'

    ctx.timeline_nodes.append({
        'name': name, 'path': path, 'color': color, 'multiplier': state.multiplier,
        'start': min_start, 'end': max_end, 'duration': max_end - min_start,
        'kernel_count': len(all_ops), 'streams': sorted(stream_set),
        'dominant_stream': dominant_stream, 'per_stream_ops': per_stream_ops,
        'op_indices': all_ops_indices, 'depth': state.depth,
        'parent_index': state.parent_index, 'children_indices': [],
        'has_children': False, 'category': 'auxiliary' if state.is_auxiliary else '',
    })

    child_indices = []
    for child in node.get('children', []):
        child_state = TimelineNodeState(multiplier=state.multiplier, depth=state.depth + 1,
                                        parent_index=current_index, is_auxiliary=state.is_auxiliary)
        child_idx = _timeline_process_node(child, path, ctx, child_state)
        if child_idx >= 0:
            child_indices.append(child_idx)
    ctx.timeline_nodes[current_index]['children_indices'] = child_indices
    ctx.timeline_nodes[current_index]['has_children'] = len(child_indices) > 0
    return current_index


@dataclass
class ReportOptions:
    """报告生成选项（降低 generate_report / generate_html_report 参数个数）。"""
    output_path: str = None
    depth: int = 3
    html: bool = False
    html_output: str = None
    theme: str = 'vscode-dark'
    kernel_display_fields: list = None
    raw_ops_path: str = ''
    config_path: str = ''


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
    required = ['model_name', 'layer_types', 'layer_structure']
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"analysis_config.json 缺少必要字段: {missing}")


def get_duration_by_indices(operators: list, indices: list) -> float:
    total = 0.0
    op_dict = {op['index']: op for op in operators}
    for idx in indices:
        if idx in op_dict:
            total += op_dict[idx].get('duration_us', 0)
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
    
    for _stage_name, stage_info in config.get('stages', {}).items():
        _collect_from_node(stage_info)

    for _layer_type, structure in config.get('layer_structure', {}).items():
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
    
    if field_key in ('input_shapes', 'output_shapes', 'input_data_types',
                     'output_data_types', 'input_formats', 'output_formats'):
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
    indices = list(node.get('op_indices', []))
    for child in node.get('children', []):
        indices.extend(collect_all_op_indices(child))
    return indices


def count_all_kernels(node: dict, operators: list) -> int:
    return len(collect_all_op_indices(node))


def get_node_time_span_info(node: dict, operators: list) -> dict:
    all_op_indices = collect_all_op_indices(node)
    op_dict = {op['index']: op for op in operators}
    
    if not all_op_indices:
        return {'time_span': 0, 'streams': {}, 'stream_info': '', 'stream_hover': '',
                'calculation': '', 'stream_count': 0}
    
    ops = [op_dict[i] for i in all_op_indices if i in op_dict]
    
    if not ops:
        return {'time_span': 0, 'streams': {}, 'stream_info': '', 'stream_hover': '',
                'calculation': '', 'stream_count': 0}
    
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
    stream_hover = '&#10;'.join([f"Stream {sid}: {cnt}"
                                 for sid, cnt in sorted(stream_counts.items(), key=lambda x: -x[1])])
    calculation = (f"{latest_name}({latest_start:.2f}+{latest_duration:.2f}) - "
                   f"{earliest_name}({min_start:.2f}) = {time_span:.2f} us")
    
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
    duration = get_duration_by_indices(operators, node.get('op_indices', []))
    for child in node.get('children', []):
        duration += get_node_total_duration(child, operators)
    return duration


@dataclass
class TimingCtx:
    """collect_timing_tree_lines 递归过程中保持不变的上下文。"""
    operators: list
    total_duration: float
    max_depth: int
    align_col: int


def _timing_kernel_lines(op_indices, ctx, multiplier, new_indent):
    """渲染叶节点 kernel 明细行（时序文本树）。"""
    lines = []
    kernel_details = get_kernel_details_by_indices(ctx.operators, op_indices)
    for i, k in enumerate(kernel_details):
        k_duration = k['duration'] * multiplier
        k_pct = format_percentage(k_duration, ctx.total_duration)
        k_dur_str = f"{format_duration_us(k_duration)} us ({format_duration_ms(k_duration)} ms, {k_pct}%)"
        k_prefix = new_indent + ("└── " if i == len(kernel_details) - 1 else "├── ")
        k_name_padded = k['name'].ljust(ctx.align_col - len(k_prefix))
        lines.append(f"{k_prefix}{k_name_padded}{k_dur_str}")
    return lines


def collect_timing_tree_lines(node: dict, ctx: TimingCtx, multiplier: int,
                              pos: tuple, current_depth: int) -> List[str]:
    indent, is_last = pos
    align_col = ctx.align_col
    name = node.get('name', 'Unknown')
    op_indices = node.get('op_indices', [])
    children = node.get('children', [])

    duration = get_duration_by_indices(ctx.operators, op_indices) * multiplier
    for child in children:
        duration += get_node_total_duration(child, ctx.operators) * multiplier

    count_str = f" (*{multiplier}层)" if multiplier > 1 and current_depth == 1 else ""
    percentage = format_percentage(duration, ctx.total_duration)
    duration_str = f"{format_duration_us(duration)} us ({format_duration_ms(duration)} ms, {percentage}%)"

    lines = []
    if current_depth == 0:
        lines.append(f"{(name + count_str).ljust(align_col)}{duration_str}")
    else:
        full_prefix = indent + ("└── " if is_last else "├── ")
        name_padded = (name + count_str).ljust(align_col - len(full_prefix))
        lines.append(f"{full_prefix}{name_padded}{duration_str}")

    new_indent = indent + ("    " if is_last else "│   ")

    if current_depth >= ctx.max_depth:
        lines.extend(_timing_kernel_lines(op_indices, ctx, multiplier, new_indent))
        return lines

    if op_indices and not children:
        lines.extend(_timing_kernel_lines(op_indices, ctx, multiplier, new_indent))

    for i, child in enumerate(children):
        is_child_last = (i == len(children) - 1)
        lines.extend(collect_timing_tree_lines(child, ctx, multiplier,
                                               (new_indent, is_child_last),
                                               current_depth + 1))
    return lines


def _collect_stage_modules(config, operators, order_start):
    """收集 stages 段的 module / kernel_module 条目。返回 (modules, kernels, next_order)。"""
    modules, kernel_modules = [], []
    order = order_start
    for stage_name, stage_info in config.get('stages', {}).items():
        stage_indices = stage_info.get('stage_indices', [0])
        stage_count = len(stage_indices) if stage_indices else 1
        stage_children = stage_info.get('children', [])
        stage_duration = get_duration_by_indices(operators, stage_info.get('op_indices', []))
        stage_kernels = get_kernels_by_indices(operators, stage_info.get('op_indices', []))
        for child in stage_children:
            child_duration, child_kernels = collect_node_stats(child, operators)
            stage_duration += child_duration
            stage_kernels.extend(child_kernels)
        modules.append({
            'name': stage_info.get('name', stage_name), 'level': 1, 'order': order,
            'count': stage_count, 'kernels_per_pass': len(stage_kernels),
            'total_kernels': len(stage_kernels) * stage_count,
            'total_duration': stage_duration * stage_count,
        })
        order += 1
        for child in stage_children:
            cm, ck = collect_child_modules_with_kernels(child, operators, stage_count, 2, order)
            modules.extend(cm)
            kernel_modules.extend(ck)
            order += len(cm)
    return modules, kernel_modules, order


def _collect_layer_modules(config, operators, order_start):
    """收集 layer_structure 段的 module / kernel_module 条目。"""
    modules, kernel_modules = [], []
    order = order_start
    layer_types = config.get('layer_types', {})
    layer_structure = config.get('layer_structure', {})
    for layer_type, layer_info in layer_types.items():
        structure = layer_structure.get(layer_type, {})
        if not structure:
            continue
        layer_count = len(layer_info.get('layer_indices', []))
        layer_duration = get_node_total_duration(structure, operators)
        layer_kernels = collect_all_kernels(structure, operators)
        modules.append({
            'name': structure.get('name', layer_type), 'level': 1, 'order': order,
            'count': layer_count, 'kernels_per_pass': len(layer_kernels),
            'total_kernels': len(layer_kernels) * layer_count,
            'total_duration': layer_duration * layer_count,
        })
        order += 1
        cm, ck = collect_child_modules_with_kernels(structure, operators, layer_count, 2, order)
        modules.extend(cm)
        kernel_modules.extend(ck)
        order += len(cm)
    return modules, kernel_modules, order


def _collect_aux_modules(config, operators, order_start):
    """收集 runtime_auxiliary 段的 module 条目。"""
    modules = []
    order = order_start
    for aux in config.get('runtime_auxiliary', []) or []:
        aux_duration = get_duration_by_indices(operators, aux.get('op_indices', []))
        aux_kernels = get_kernels_by_indices(operators, aux.get('op_indices', []))
        modules.append({
            'name': aux.get('name', 'runtime_aux'), 'level': 1, 'order': order,
            'count': 1, 'kernels_per_pass': len(aux_kernels),
            'total_kernels': len(aux_kernels), 'total_duration': aux_duration,
        })
        order += 1
    return modules, order


def collect_all_modules(config: dict, operators: list) -> Tuple[list, list]:
    modules = [{
        'name': config.get('model_name', 'Model'), 'level': 0, 'order': 0, 'count': 1,
        'kernels_per_pass': len(operators), 'total_kernels': len(operators),
        'total_duration': sum(op.get('duration_us', 0) for op in operators),
    }]
    kernel_modules = []

    stage_m, stage_k, order = _collect_stage_modules(config, operators, 1)
    modules.extend(stage_m)
    kernel_modules.extend(stage_k)

    layer_m, layer_k, order = _collect_layer_modules(config, operators, order)
    modules.extend(layer_m)
    kernel_modules.extend(layer_k)

    aux_m, _ = _collect_aux_modules(config, operators, order)
    modules.extend(aux_m)

    return modules, kernel_modules


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


def collect_child_modules_with_kernels(node: dict, operators: list, multiplier: int,
                                       level: int, start_order: int) -> Tuple[list, list]:
    modules = []
    kernel_modules = []
    order = start_order
    
    children = node.get('children', [])
    for _i, child in enumerate(children):
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


def _build_timing_temp_lines(config, model_name, model_duration, total_duration):
    """构建时序树的临时行列表（模型行 + stage/layer/aux 节点元组）。"""
    percentage = format_percentage(model_duration, total_duration)
    temp_lines = [(model_name,
                   f"{format_duration_us(model_duration)} us "
                   f"({format_duration_ms(model_duration)} ms, {percentage}%)")]

    for stage_name, stage_info in config.get('stages', {}).items():
        stage_indices = stage_info.get('stage_indices', [0])
        stage_count = len(stage_indices) if stage_indices else 1
        temp_lines.append((stage_info.get('name', stage_name), stage_count, stage_info, False, 'stage'))

    layer_types = config.get('layer_types', {})
    layer_structure = config.get('layer_structure', {})
    layer_items = [(lt, li, layer_structure[lt]) for lt, li in layer_types.items()
                   if layer_structure.get(lt)]
    for idx, (layer_type, layer_info, structure) in enumerate(layer_items):
        layer_count = len(layer_info.get('layer_indices', []))
        is_last_layer = (idx == len(layer_items) - 1)
        temp_lines.append((structure.get('name', layer_type), layer_count, structure, is_last_layer, 'layer'))

    for aux in config.get('runtime_auxiliary', []):
        temp_lines.append((aux.get('name', 'runtime_aux'), 1, aux, False, 'aux'))
    return temp_lines


def _timing_align_col(temp_lines):
    """计算时序树名称列对齐宽度。"""
    max_name_len = 0
    for item in temp_lines:
        if len(item) == 2:
            max_name_len = max(max_name_len, len(item[0]))
        else:
            name, count, _node, _is_last, item_type = item
            count_str = f" (*{count}层)" if count > 1 and item_type in ('layer',) else ""
            instance_str = f" (*{count}实例)" if count > 1 and item_type in ('stage', 'aux') else ""
            max_name_len = max(max_name_len, len(name) + len(count_str) + len(instance_str))
    return max(max_name_len + 2, 40)


def generate_analysis_section(config: dict, operators: list, total_duration: float, max_depth: int = 4) -> str:
    model_name = config.get('model_name', 'Model')
    model_duration = sum(op.get('duration_us', 0) for op in operators)

    temp_lines = _build_timing_temp_lines(config, model_name, model_duration, total_duration)
    align_col = _timing_align_col(temp_lines)

    timing_ctx = TimingCtx(operators=operators, total_duration=total_duration,
                           max_depth=max_depth, align_col=align_col)
    lines = ["## 模型性能分析", "", "```text"]

    for item_idx, item in enumerate(temp_lines):
        if len(item) == 2:
            name_padded = item[0].ljust(align_col)
            lines.append(f"{name_padded}{item[1]}")
        else:
            name, count, node, _is_last, item_type = item
            is_last = (item_idx == len(temp_lines) - 1)
            lines.extend(collect_timing_tree_lines(node, timing_ctx, count, ("", is_last), 1))

    lines.append("```")
    lines.append("")
    return '\n'.join(lines)




def get_html_css() -> str:
    return HTML_CSS


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


def _build_per_stream_ops(all_ops_indices, op_dict):
    """按 stream_id 分组并按 start 排序 op 列表。"""
    per_stream_ops = {}
    for i in all_ops_indices:
        op = op_dict.get(i)
        if not op:
            continue
        sid = str(op.get('stream_id', '0'))
        per_stream_ops.setdefault(sid, []).append({
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
    return per_stream_ops


def generate_timeline_data(config: dict, operators: list, total_duration: float) -> list:
    ctx = _TimelineBuildCtx(
        op_dict={op['index']: op for op in operators},
        timeline_nodes=[],
        node_color_map={},
    )
    model_name = config.get('model_name', 'Model')

    for _stage_name, stage_info in config.get('stages', {}).items():
        stage_indices = stage_info.get('stage_indices', [0])
        stage_count = len(stage_indices) if stage_indices else 1
        _timeline_process_node(stage_info, model_name, ctx,
                               TimelineNodeState(multiplier=stage_count, is_auxiliary=True))

    layer_types = config.get('layer_types', {})
    layer_structure = config.get('layer_structure', {})
    for layer_type, layer_info in layer_types.items():
        structure = layer_structure.get(layer_type, {})
        if not structure:
            continue
        layer_count = len(layer_info.get('layer_indices', []))
        _timeline_process_node(structure, model_name, ctx,
                               TimelineNodeState(multiplier=layer_count))

    for aux in config.get('runtime_auxiliary', []):
        _timeline_process_node(aux, model_name, ctx,
                               TimelineNodeState(multiplier=1, is_auxiliary=True))

    return ctx.timeline_nodes


def _timeline_static_frame():
    """时序图的静态框架 HTML（展开区 + 详情面板 + section 收尾）。"""
    return [
        '<div class="timeline-expand-area" id="timeline-expand-area" style="display:none">',
        '<div class="expand-header">',
        '<button class="expand-close" id="expand-close-btn">收起</button>',
        '<div class="expand-breadcrumb" id="expand-breadcrumb"></div>',
        '<span class="expand-title" id="expand-title">-</span>',
        '</div>',
        '<div class="expand-gantt" id="expand-gantt">',
        '<div class="gantt-header">子节点多流时序图 <span class="gantt-hint">(按时间比例显示)</span></div>',
        '<div class="gantt-container" id="gantt-container"></div>',
        '</div>',
        '<div class="expand-tree" id="expand-tree">',
        '<div class="expand-tree-title">子节点结构 <span class="tree-hint">(点击有子节点的项继续展开)</span></div>',
        '<div class="expand-tree-content" id="tree-content"></div>',
        '</div>',
        '</div>',
        '</div>',
        '<div class="timeline-detail-panel" id="timeline-detail-panel">',
        '<div class="timeline-detail-header">',
        '<span class="timeline-detail-title" id="timeline-detail-title">-</span>',
        '<button class="timeline-detail-close" id="timeline-detail-close">&times;</button>',
        '</div>',
        '<div class="timeline-detail-ops" id="timeline-detail-ops"></div>',
        '</div>',
        '</section>',
    ]


def _build_timeline_bar_data(timeline_nodes):
    """构建供前端 JS 渲染甘特条的 bar_data 列表。"""
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
    return bar_data_json


def _fmt_timeline_dur(us: float) -> str:
    if us >= 1000:
        return f"{us/1000:.1f}ms"
    return f"{us:.1f}us"


def _timeline_overview_item(ni, node):
    """渲染时序图顶层节点概览中的单个 item。"""
    name = node['name']
    multiplier = node.get('multiplier', 1)
    streams = node.get('streams', [])
    count_suffix = f" ×{multiplier}" if multiplier > 1 else ""
    streams_str = ','.join(streams[:4]) + ('...' if len(streams) > 4 else '')
    duration_str = _fmt_timeline_dur(node.get('duration', 0))
    has_children = node.get('has_children', False)
    expand_icon = '▶' if has_children else '─'
    expand_class = 'has-children' if has_children else ''
    color = node.get('color', '#4fc1ff')
    category = node.get('category', '')
    category_attr = f' data-category="{category}"' if category else ''
    return (
        f'<div class="timeline-node-item {expand_class}" data-node-index="{ni}"{category_attr}>'
        f'<span class="node-expand-icon">{expand_icon}</span>'
        f'<span class="node-name" style="border-left:3px solid {color};padding-left:6px">'
        f'{name}{count_suffix}</span>'
        f'<span class="node-streams">Streams: [{streams_str}]</span>'
        f'<span class="node-duration">{duration_str}</span>'
        f'<span class="node-kernels">{node.get("kernel_count", 0)} kernels</span>'
        f'</div>'
    )


def generate_timeline_html(config: dict, operators: list, total_duration: float, max_depth: int) -> tuple:
    timeline_nodes = generate_timeline_data(config, operators, total_duration)

    if not operators or not timeline_nodes:
        return ('<section id="timeline" class="timeline-section"><h2>多流时序图</h2>'
                '<p style="color:var(--text-secondary)">无可用的时序数据</p></section>'), {}

    top_level_nodes = [i for i, node in enumerate(timeline_nodes) if node.get('depth', 0) == 0]

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
        html_parts.append(_timeline_overview_item(ni, node))

    html_parts.append('</div>')
    html_parts.append('</div>')

    html_parts.extend(_timeline_static_frame())

    bar_data_json = _build_timeline_bar_data(timeline_nodes)

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
    return (JS_TEMPLATE
            .replace('@@TOOLTIP_JSON@@', tooltip_json)
            .replace('@@FIELDS_JSON@@', fields_json)
            .replace('@@TL_JSON@@', tl_json)
            .replace('@@DEFAULT_THEME@@', default_theme))




_TOOLTIP_LONG_FIELDS = {'input_shapes', 'output_shapes', 'input_data_types',
                        'output_data_types', 'input_formats', 'output_formats'}


def _tooltip_field_val(all_fields, key):
    """取字段显示值（优先 *_raw），无值返回 None。"""
    raw_key = f'{key}_raw'
    if raw_key in all_fields:
        val = all_fields[raw_key]
        if val is not None and val != '' and val != 'N/A':
            suffix = ' us' if key.endswith('_us') else ''
            return f'{val}{suffix}'
        return None
    val = all_fields.get(key)
    if val is not None and val != '' and val != 'N/A':
        return format_field_display(key, val)
    return None


def _render_tooltip_group(all_fields, title, fields):
    """渲染 tooltip 中的一个字段分组；无内容返回 None。"""
    has_content = any(
        all_fields.get(key) not in (None, '', 'N/A') for key, _ in fields)
    if not has_content:
        return None
    parts = [f'<div class="kernel-tooltip-section">{title}</div>',
             '<div class="kernel-tooltip-group-grid">']
    for key, label in fields:
        display_val = _tooltip_field_val(all_fields, key)
        if display_val is None:
            continue
        if key in _TOOLTIP_LONG_FIELDS:
            parts.append(f'<div class="kernel-tooltip-full">'
                         f'<span class="kernel-tooltip-label">{label}:</span>'
                         f'<span class="kernel-tooltip-value">{display_val}</span></div>')
        else:
            parts.append(f'<div class="kernel-tooltip-label">{label}</div>')
            parts.append(f'<div class="kernel-tooltip-value">{display_val}</div>')
    parts.append('</div>')
    return ''.join(parts)


_TOOLTIP_GROUP_ROWS = [
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
            parts.append(f'<div class="kernel-tooltip-semantic">{semantic}{shape_html}'
                         f'<br/><small>Path: {path}</small>{code_ref_html}</div>')
    
    parts.append('<div class="kernel-tooltip-container">')
    idx_display = all_fields.get('index', idx)
    parts.append('<div class="kernel-tooltip-label">Index:</div>')
    parts.append(f'<div class="kernel-tooltip-value" style="margin-bottom:8px">{idx_display}</div>')
    
    
    for row in _TOOLTIP_GROUP_ROWS:
        row_parts = []
        for group_title, fields in row:
            group_html = _render_tooltip_group(all_fields, group_title, fields)
            if group_html:
                row_parts.append(f'<div class="kernel-tooltip-group">{group_html}</div>')
        if row_parts:
            parts.append('<div class="kernel-tooltip-row">')
            parts.extend(row_parts)
            parts.append('</div>')
    
    parts.append('</div>')
    return ''.join(parts)


def _render_kernel_meta_field(k, field_key, krc, k_shape_semantic):
    """渲染单个 kernel-meta 字段的 span（含 shape_semantic hover）。"""
    label = KERNEL_FIELD_LABELS.get(field_key, field_key)
    value = get_kernel_field_value(k, field_key, krc.multiplier, krc.ctx.total_duration)
    is_default = field_key in krc.display_fields
    style_attr = '' if is_default else ' style="display:none"'
    tip_cls = ''
    tip_attr = ''
    if field_key in ('input_shapes', 'output_shapes') and k_shape_semantic:
        tip_cls = ' shape-semantic-tip'
        if '→' in k_shape_semantic:
            _parts = k_shape_semantic.split('→', 1)
            _tip = _parts[0].strip() if field_key == 'input_shapes' else _parts[1].strip()
        else:
            _tip = k_shape_semantic
        tip_attr = f' data-shape-semantic="{_tip}"'
    return (f'<span class="kernel-meta-item{tip_cls}" data-field="{field_key}"{style_attr}{tip_attr}>'
            f'<span class="kernel-meta-label">{label}:</span>'
            f'<span class="kernel-meta-value">{value}</span></span>')


def _kernel_semantic_html(semantic_info):
    """构建 kernel 名称后的黄色 semantic 包裹块。"""
    k_semantic = semantic_info.get('semantic', '') if semantic_info else ''
    if not k_semantic:
        return ''
    k_expand_btn = ('<span class="semantic-expand-btn"><svg viewBox="0 0 24 24">'
                    '<path d="M7 10l5 5 5-5z"/></svg></span>')
    k_display = k_semantic[:57] + '...' if len(k_semantic) > 60 else k_semantic
    return (f' <span class="node-semantic-wrapper" data-full="{k_semantic}">'
            f'<span class="node-semantic-truncated">{k_display}</span>'
            f'<span class="node-semantic-full">{k_semantic}</span>'
            f'{k_expand_btn}</span>')


_KERNEL_INFO_SVG = (
    '<svg viewBox="0 0 24 24">'
    '<path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16'
    'c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0'
    'C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>')


def _render_one_kernel(k, ki, total_kernels, krc):
    """渲染单个 kernel 叶节点，返回 (html_lines, (idx, tooltip_html))。"""
    ctx = krc.ctx
    multiplier = krc.multiplier
    current_depth = krc.current_depth
    total_duration = ctx.total_duration
    kernel_semantics = ctx.kernel_semantics
    k_duration_total = k['duration'] * multiplier
    k_pct = format_percentage(k_duration_total, total_duration)
    idx = k.get('index', 0)
    semantic_info = kernel_semantics.get(idx) if kernel_semantics else None
    tooltip_html = generate_kernel_tooltip_html(k, semantic_info)
    kernel_seq = f"[{ki+1}/{total_kernels}]"
    kernel_name = k.get('name', 'Unknown')
    k_shape_semantic = semantic_info.get('shape_semantic', '') if semantic_info else ''
    kernel_semantic_html = _kernel_semantic_html(semantic_info)

    lines = [
        f'<li class="tree-node leaf" data-depth="{current_depth + 1}" data-type="kernel">',
        '<div class="node-header">',
        '<span class="node-spacer"></span>',
        f'<span class="node-name">{kernel_seq} {kernel_name}</span>{kernel_semantic_html}',
        f'<span class="kernel-info-btn" data-index="{idx}">{_KERNEL_INFO_SVG}</span>',
        '<span class="node-duration">',
        f'<span class="duration-us">{format_duration_us(k_duration_total)} us</span>',
        f'<span class="duration-pct">({k_pct}%)</span>',
        '</span>',
        '</div>',
        '<div class="kernel-meta">',
    ]
    for field_key in ALL_KERNEL_META_FIELDS:
        lines.append(_render_kernel_meta_field(k, field_key, krc, k_shape_semantic))
    lines.append('</div>')
    lines.append('</li>')
    return lines, (idx, tooltip_html)


def _node_semantic_suffix(node):
    """构建节点名后的 semantic | [code_ref] 展开块；无则返回 ''。"""
    semantic_parts = []
    node_semantic = node.get('semantic', '') or node.get('comment', '')
    if node_semantic:
        semantic_parts.append(node_semantic)
    if node.get('code_ref'):
        semantic_parts.append(f'[{node["code_ref"]}]')
    if not semantic_parts:
        return ''
    full_text = ' | '.join(semantic_parts)
    expand_btn = ('<span class="semantic-expand-btn"><svg viewBox="0 0 24 24">'
                  '<path d="M7 10l5 5 5-5z"/></svg></span>')
    display_text = full_text[:117] + '...' if len(full_text) > 120 else full_text
    return (f' <span class="node-semantic-wrapper" data-full="{full_text}">'
            f'<span class="node-semantic-truncated">{display_text}</span>'
            f'<span class="node-semantic-full">{full_text}</span>'
            f'{expand_btn}</span>')


def _node_header_attrs(info: NodeHeaderInfo):
    """计算模块节点头部的派生属性：(kernel_count_str, stream_count_str, duration_hover, node_class)。"""
    time_info = info.time_info
    kernel_count = info.kernel_count
    if not info.is_leaf and kernel_count > 0:
        kernel_count_str = f'<span class="kernel-count">({kernel_count} kernels)</span>'
        stream_count_str = (f'<span class="stream-count" title="{time_info["stream_hover"]}">'
                            f'({time_info["stream_info"]})</span>')
    else:
        kernel_count_str = ''
        stream_count_str = ''

    duration_hover = time_info['calculation'] if kernel_count > 0 else ''
    if duration_hover and info.multiplier > 1:
        duration_hover = f"{duration_hover} × {info.multiplier} = {time_info['time_span'] * info.multiplier:.2f} us"

    node_class = 'expanded' if info.current_depth < info.max_depth else 'collapsed'
    if info.is_leaf:
        node_class = 'leaf'
    elif info.is_kernel_only:
        node_class += ' kernel-only'
    return kernel_count_str, stream_count_str, duration_hover, node_class


def _module_node_header_html(node, hdr: NodeHeaderView):
    """渲染模块节点的头部 HTML 行列表（<li> 开标签 + node-header）。"""
    category_attr = f' data-category="{hdr.data_category}"' if hdr.data_category else ''
    semantic_suffix = _node_semantic_suffix(node)
    duration_title = f' title="{hdr.duration_hover}"' if hdr.duration_hover else ''
    return [
        f'<li class="tree-node {hdr.node_class}" data-depth="{hdr.current_depth}" data-type="module"{category_attr}>',
        '<div class="node-header">',
        '<span class="node-toggle">▶</span>',
        f'<span class="node-name">{hdr.name}{hdr.count_str} '
        f'{hdr.kernel_count_str}{hdr.stream_count_str}{semantic_suffix}</span>',
        f'<span class="node-duration"{duration_title}>',
        f'<span class="duration-us">{format_duration_us(hdr.duration)} us</span>',
        f'<span class="duration-ms">({format_duration_ms(hdr.duration)} ms)</span>',
        f'<span class="duration-pct">({hdr.percentage}%)</span>',
        '</span>',
        '</div>',
    ]


def render_html_tree_node(node: dict, ctx: HtmlRenderCtx, multiplier: int,
                          current_depth: int, data_category: str = '') -> tuple:
    operators = ctx.operators
    display_fields = ctx.kernel_display_fields or DEFAULT_KERNEL_DISPLAY_FIELDS
    name = node.get('name', 'Unknown')
    op_indices = node.get('op_indices', [])
    children = node.get('children', [])

    has_kernels = bool(op_indices)
    has_children = bool(children)
    is_leaf = not has_kernels and not has_children
    is_kernel_only = has_kernels and not has_children

    time_info = get_node_time_span_info(node, operators)
    duration = get_node_total_duration(node, operators) * multiplier
    kernel_count = count_all_kernels(node, operators)
    percentage = format_percentage(duration, ctx.total_duration)
    count_str = f" (*{multiplier}层)" if multiplier > 1 and current_depth == 1 else ""

    kernel_count_str, stream_count_str, duration_hover, node_class = _node_header_attrs(
        NodeHeaderInfo(time_info=time_info, kernel_count=kernel_count, multiplier=multiplier,
                       current_depth=current_depth, max_depth=ctx.max_depth,
                       is_leaf=is_leaf, is_kernel_only=is_kernel_only))

    html_parts = _module_node_header_html(node, NodeHeaderView(
        name=name, count_str=count_str, node_class=node_class, current_depth=current_depth,
        data_category=data_category, kernel_count_str=kernel_count_str,
        stream_count_str=stream_count_str, duration_hover=duration_hover,
        duration=duration, percentage=percentage))

    tooltip_parts = []

    if has_kernels or has_children:
        html_parts.append('<ul class="tree-children">')

        if has_children:
            for child in children:
                child_html, child_tooltips = render_html_tree_node(
                    child, ctx, multiplier, current_depth + 1)
                html_parts.append(child_html)
                tooltip_parts.extend(child_tooltips)

        if has_kernels:
            kernels = get_kernel_full_details_by_indices(operators, op_indices)
            total_kernels = len(kernels)
            krc = KernelRenderCtx(ctx=ctx, multiplier=multiplier,
                                  current_depth=current_depth, display_fields=display_fields)
            for ki, k in enumerate(kernels):
                lines, tip = _render_one_kernel(k, ki, total_kernels, krc)
                tooltip_parts.append(tip)
                html_parts.extend(lines)

        html_parts.append('</ul>')

    html_parts.append('</li>')
    return '\n'.join(html_parts), tooltip_parts


def _compute_model_span(operators):
    """计算模型整体 duration 与时间跨度说明文本，返回 (model_duration, calculation)。"""
    if not operators:
        return 0, ''
    model_duration = sum(op.get('duration_us', 0) for op in operators)
    earliest_op = min(operators, key=lambda op: op.get('start_time_us', 0))
    latest_op = max(operators, key=lambda op: op.get('start_time_us', 0) + op.get('duration_us', 0))
    min_start = earliest_op.get('start_time_us', 0)
    max_end = latest_op.get('start_time_us', 0) + latest_op.get('duration_us', 0)
    earliest_name = earliest_op.get('normalized_name') or earliest_op.get('type', 'Unknown')
    latest_name = latest_op.get('normalized_name') or latest_op.get('type', 'Unknown')
    latest_start = latest_op.get('start_time_us', 0)
    latest_duration = latest_op.get('duration_us', 0)
    time_span = max_end - min_start
    calculation = (f"{latest_name}({latest_start:.2f}+{latest_duration:.2f}) - "
                   f"{earliest_name}({min_start:.2f}) = {time_span:.2f} us")
    return model_duration, calculation


def _tree_root_header(display_name, model_duration, percentage, duration_hover):
    """渲染分析树根节点（模型层）的头部 HTML 片段。"""
    duration_title = f' title="{duration_hover}"' if duration_hover else ''
    return [
        '<li class="tree-node expanded" data-depth="0" data-type="module">',
        '<div class="node-header">',
        '<span class="node-toggle">▶</span>',
        f'<span class="node-name">{display_name}</span>',
        f'<span class="node-duration"{duration_title}>',
        f'<span class="duration-us">{format_duration_us(model_duration)} us</span>',
        f'<span class="duration-ms">({format_duration_ms(model_duration)} ms)</span>',
        f'<span class="duration-pct">({percentage}%)</span>',
        '</span>',
        '</div>',
        '<ul class="tree-children">',
    ]


def generate_html_tree_section(config: dict, operators: list, total_duration: float,
                               max_depth: int, kernel_display_fields: list = None) -> tuple:
    model_name = config.get('model_name', 'Model')
    display_name, _ = _extract_model_display_name(model_name)
    kernel_semantics = collect_kernel_semantics(config)
    display_fields = kernel_display_fields or DEFAULT_KERNEL_DISPLAY_FIELDS

    model_duration, calculation = _compute_model_span(operators)
    percentage = format_percentage(model_duration, total_duration)

    stages = config.get('stages', {})
    layer_types = config.get('layer_types', {})
    layer_structure = config.get('layer_structure', {})
    runtime_aux = config.get('runtime_auxiliary', [])

    html_parts = ['<section id="analysis">', '<div class="tree">', '<ul class="tree-root">']
    html_parts.extend(_tree_root_header(display_name, model_duration, percentage,
                                        calculation if calculation else ''))

    all_tooltips = []
    tree_ctx = HtmlRenderCtx(operators=operators, total_duration=total_duration,
                             max_depth=max_depth, kernel_semantics=kernel_semantics,
                             kernel_display_fields=display_fields)

    for _stage_name, stage_info in stages.items():
        stage_indices = stage_info.get('stage_indices', [0])
        stage_count = len(stage_indices) if stage_indices else 1
        node_html, node_tooltips = render_html_tree_node(
            stage_info, tree_ctx, stage_count, 1, data_category='auxiliary')
        html_parts.append(node_html)
        all_tooltips.extend(node_tooltips)

    for layer_type, layer_info in layer_types.items():
        structure = layer_structure.get(layer_type, {})
        if not structure:
            continue
        layer_count = len(layer_info.get('layer_indices', []))
        node_html, node_tooltips = render_html_tree_node(structure, tree_ctx, layer_count, 1)
        html_parts.append(node_html)
        all_tooltips.extend(node_tooltips)

    for aux in runtime_aux:
        node_html, node_tooltips = render_html_tree_node(
            aux, tree_ctx, 1, 1, data_category='auxiliary')
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


def _html_metadata_section(meta: ReportMeta):
    """报告 metadata 区 HTML 片段列表。"""
    return [
        '<div class="metadata">',
        '<div class="meta-row">',
        (f'<div class="meta-item"><span class="meta-label">生成时间:</span>'
         f'<span class="meta-value">{meta.generate_time}</span></div>'),
        (f'<div class="meta-item"><span class="meta-label">总耗时:</span>'
         f'<span class="meta-value">{format_duration_us(meta.total_duration)} us '
         f'({format_duration_ms(meta.total_duration)} ms)</span></div>'),
        f'<div class="meta-item"><span class="meta-label">Step:</span>'
        f'<span class="meta-value">{meta.step_id}</span></div>',
        (f'<div class="meta-item"><span class="meta-label">Kernel数量:</span>'
         f'<span class="meta-value">{meta.kernel_count}</span></div>'),
        '</div>',
        '<div class="meta-row">',
        '<div class="meta-item" style="flex-direction: column; align-items: flex-start; gap: 4px;">',
        '<span class="meta-label">数据源:</span>',
        '<div class="meta-datasources">',
        f'<div class="meta-datasource-item">{meta.raw_ops_path}</div>',
        f'<div class="meta-datasource-item">{meta.config_path}</div>',
        '</div>',
        '</div>',
        '</div>',
        '<div class="meta-row">',
        (f'<div class="meta-item"><span class="meta-label">模型简介:</span>'
         f'<span class="meta-value">{meta.architecture_desc}</span></div>'
         if meta.architecture_desc else ''),
        '</div>',
        '</div>',
    ]


_KERNEL_FIELD_CHECKBOXES = [
    ('stream_id', 'Stream', True), ('input_shapes', 'Input Shapes', True),
    ('output_shapes', 'Output Shapes', True), ('start_time_us', 'Start Time', False),
    ('duration_us', 'Duration', False), ('wait_time_us', 'Wait Time', False),
    ('device_id', 'Device', False), ('task_id', 'Task ID', False),
    ('type', 'Type', False), ('op_state', 'OP State', False),
    ('accelerator_core', 'Acc Core', False), ('block_dim', 'Block Dim', False),
    ('input_data_types', 'In DType', False), ('output_data_types', 'Out DType', False),
    ('input_formats', 'In Fmt', False), ('output_formats', 'Out Fmt', False),
]


def _html_controls_section():
    """报告 controls 工具栏 HTML 片段列表（全静态）。"""
    parts = [
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
    ]
    for val, label, checked in _KERNEL_FIELD_CHECKBOXES:
        chk = ' checked' if checked else ''
        parts.append(f'<label><input type="checkbox" value="{val}"{chk}> {label}</label>')
    parts += [
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
    ]
    return parts


def generate_html_report(raw_ops: dict, config: dict, operators: list, total_duration: float,
                         opts: ReportOptions) -> str:
    import datetime
    depth = opts.depth
    theme = opts.theme
    kernel_display_fields = opts.kernel_display_fields
    raw_ops_path = opts.raw_ops_path
    config_path = opts.config_path
    model_name = config.get('model_name', 'Model')
    display_name, architecture_desc = _extract_model_display_name(model_name)
    generate_time = datetime.datetime.now(datetime.timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S')
    kernel_count = raw_ops.get('kernel_count', len(operators))
    step_id = raw_ops.get('step_id', 'N/A')
    
    display_fields = kernel_display_fields or DEFAULT_KERNEL_DISPLAY_FIELDS
    tree_html, tooltip_data = generate_html_tree_section(
        config, operators, total_duration, depth, kernel_display_fields)
    timeline_html, timeline_data = generate_timeline_html(config, operators, total_duration, depth)

    html_parts = [
        '<!DOCTYPE html>',
        '<html lang="zh-CN">',
        '<head>',
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f'<title>{display_name} 性能分析</title>',
        get_html_css(),
        '</head>',
        '<body>',
        f'<h1>{display_name} 性能分析</h1>',
    ]
    html_parts += _html_metadata_section(ReportMeta(
        generate_time=generate_time, total_duration=total_duration, step_id=step_id,
        kernel_count=kernel_count, raw_ops_path=raw_ops_path, config_path=config_path,
        architecture_desc=architecture_desc))
    html_parts += _html_controls_section()
    html_parts += [
        tree_html,
        timeline_html,
        get_html_js(theme, tooltip_data, display_fields, timeline_data),
        '</body>',
        '</html>'
    ]

    return '\n'.join(html_parts)


def generate_report(raw_ops_path: str, config_path: str, opts: ReportOptions = None) -> str:
    if opts is None:
        opts = ReportOptions()
    output_path = opts.output_path
    depth = opts.depth
    html = opts.html
    html_output = opts.html_output
    raw_ops_file = validate_file_exists(raw_ops_path)
    config_file = validate_file_exists(config_path)

    raw_ops = load_json(raw_ops_file)
    config = load_json(config_file)

    validate_raw_ops(raw_ops)
    validate_analysis_config(config)

    operators = raw_ops.get('operators', [])
    total_duration = raw_ops.get('total_duration_us', 1)

    report = None

    if output_path:
        report_parts = []
        report_parts.append(f"# {config.get('model_name', 'Model')} 性能拆解报告")
        report_parts.append("")
        report_parts.append(generate_analysis_section(config, operators, total_duration, depth))
        report = '\n'.join(report_parts)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info("Markdown报告已生成: %s", output_path)

    if html:
        html_opts = ReportOptions(output_path=output_path, depth=depth, html=html,
                                  html_output=html_output, theme=opts.theme,
                                  kernel_display_fields=opts.kernel_display_fields,
                                  raw_ops_path=raw_ops_path, config_path=config_path)
        html_content = generate_html_report(raw_ops, config, operators, total_duration, html_opts)
        if html_output:
            html_path = html_output
        elif output_path:
            html_path = str(Path(output_path).with_suffix('.html'))
        else:
            html_path = 'report.html'
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info("HTML报告已生成: %s", html_path)
    
    if not output_path and not html:
        report_parts = []
        report_parts.append(f"# {config.get('model_name', 'Model')} 性能拆解报告")
        report_parts.append("")
        report_parts.append(generate_analysis_section(config, operators, total_duration, depth))
        report = '\n'.join(report_parts)
    
    return report


def _build_arg_parser():
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
    parser.add_argument('--html', action='store_true', help='生成HTML格式报告')
    parser.add_argument('--html-output', metavar='FILE',
                        help='HTML输出文件路径 (默认: 与-o同名但后缀为.html)')
    parser.add_argument('--theme', choices=['dracula', 'vscode-dark', 'one-dark', 'github-light', 'solarized-light'],
                        default='dracula', help='HTML报告主题风格 (默认: dracula)')
    parser.add_argument('--kernel-fields', metavar='FIELDS',
                        help=('kernel默认显示字段(逗号分隔), 如: input_shapes,'
                              'output_shapes,type,stream_id,start_time_us,duration_us'))
    return parser


def main():
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    args = _build_arg_parser().parse_args()

    raw_ops_path = args.raw_ops_opt or args.raw_ops
    config_path = args.config_opt or args.config
    if not raw_ops_path or not config_path:
        _build_arg_parser().print_help()
        sys.exit(1)

    kernel_display_fields = None
    if args.kernel_fields:
        kernel_display_fields = [f.strip() for f in args.kernel_fields.split(',') if f.strip()]

    try:
        opts = ReportOptions(output_path=args.output, depth=args.depth,
                             html=args.html, html_output=args.html_output,
                             theme=args.theme, kernel_display_fields=kernel_display_fields)
        report = generate_report(raw_ops_path, config_path, opts)
        if not args.output and not args.html:
            logger.info(report)
    except (FileNotFoundError, ValueError) as e:
        logger.error("错误: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("未知错误: %s", e)
        sys.exit(1)


if __name__ == '__main__':
    main()
