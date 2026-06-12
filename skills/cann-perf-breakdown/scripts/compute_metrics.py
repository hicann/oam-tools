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
NPU 性能指标计算脚本 - Step 4

计算各节点的四维性能指标及衍生指标：
- wall_ms: 实际墙上时钟耗时（含间隙）
- busy_union_ms: 设备实际忙碌时间（合并去重叠）
- kernel_sum_ms: 所有 kernel 时长算术和
- total_cost_ms: 总成本（duration + wait）
- parallelism: 并行度（kernel_sum_ms / wall_ms）
- bubble_ms: 气泡时间（wall_ms - busy_union_ms）
- ratio_pct: 占比（wall_ms / step总wall_ms × 100）

用法:
  python compute_metrics.py -r raw_ops_details.json -c analysis_config.json -o metrics_report.md
"""
import logging
import argparse
import sys
from dataclasses import dataclass
from typing import List, Tuple

from _common import validate_file_exists, load_json

logger = logging.getLogger(__name__)


@dataclass
class TreeWalkCtx:
    """collect_tree_nodes 递归过程中保持不变的上下文。"""
    operators: List[dict]
    max_depth: int



def merge_intervals(intervals: List[Tuple[float, float]]) -> float:
    """
    合并重叠区间，返回总长度
    intervals: [(start, end), ...]
    """
    if not intervals:
        return 0.0
    
    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_intervals[0]]
    
    for start, end in sorted_intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    
    return sum(end - start for start, end in merged)


def _accumulate_op_timing(ops):
    """遍历 ops 累加时间信息，返回 (wall_us, intervals, duration_sum, total_cost)。"""
    start_times, end_times, intervals = [], [], []
    duration_sum = total_cost = 0.0
    for op in ops:
        start = op.get('start_time_us', 0)
        duration = op.get('duration_us', 0)
        wait = op.get('wait_time_us', 0) or 0
        start_times.append(start)
        end_times.append(start + duration)
        intervals.append((start, start + duration))
        duration_sum += duration
        total_cost += duration + wait
    wall_us = max(end_times) - min(start_times) if start_times else 0
    return wall_us, intervals, duration_sum, total_cost


def compute_node_metrics(op_indices: List[int], operators: List[dict], multiplier: int = 1) -> dict:
    """计算单个节点的四维指标及衍生指标。"""
    empty_result = {
        'wall_ms': 0.0, 'busy_union_ms': 0.0, 'kernel_sum_ms': 0.0, 'total_cost_ms': 0.0,
        'parallelism': '-', 'bubble_ms': 0.0, 'kernel_count': 0, 'diagnosis': '无算子'
    }
    if not op_indices:
        return empty_result

    op_dict = {op['index']: op for op in operators}
    ops = [op_dict[i] for i in op_indices if i in op_dict]
    if not ops:
        return empty_result

    wall_us, intervals, duration_sum, total_cost = _accumulate_op_timing(ops)
    busy_union_us = merge_intervals(intervals)

    wall_ms = wall_us / 1000 * multiplier
    busy_union_ms = busy_union_us / 1000 * multiplier
    kernel_sum_ms = duration_sum / 1000 * multiplier
    total_cost_ms = total_cost / 1000 * multiplier

    parallelism = f"{kernel_sum_ms / wall_ms:.1f}×" if wall_ms > 0.001 else '-'
    bubble_ms = round(wall_ms - busy_union_ms, 3)
    diagnosis = generate_diagnosis(wall_ms, busy_union_ms, kernel_sum_ms, total_cost_ms)

    return {
        'wall_ms': round(wall_ms, 3),
        'busy_union_ms': round(busy_union_ms, 3),
        'kernel_sum_ms': round(kernel_sum_ms, 3),
        'total_cost_ms': round(total_cost_ms, 3),
        'parallelism': parallelism,
        'bubble_ms': bubble_ms,
        'kernel_count': len(ops) * multiplier,
        'diagnosis': diagnosis
    }


_DIAG_EPS = 0.001


def _diag_parallelism(wall, kernel_sum):
    if kernel_sum > wall * 1.5:
        ratio = kernel_sum / wall if wall > _DIAG_EPS else 0
        return f"高流并行度（kernel_sum/wall={ratio:.1f}×）"
    if kernel_sum > wall * 1.2:
        ratio = kernel_sum / wall if wall > _DIAG_EPS else 0
        return f"中等流并行（kernel_sum/wall={ratio:.1f}×）"
    return None


def _diag_bubble(wall, busy_union):
    if wall > busy_union * 1.5:
        gap_ratio = (wall - busy_union) / wall * 100 if wall > _DIAG_EPS else 0
        return f"存在间隙气泡（gap={gap_ratio:.0f}%）"
    return None


def _diag_wait(kernel_sum, total_cost):
    wait_time = total_cost - kernel_sum
    if wait_time > 0.1 and kernel_sum > _DIAG_EPS and total_cost > kernel_sum * 1.3:
        wait_ratio = wait_time / kernel_sum * 100
        if wait_ratio < 1000:
            return f"等待时间显著（wait占比{wait_ratio:.0f}%）"
        return "等待时间显著（kernel极短但wait长）"
    if wait_time > kernel_sum * 2 and kernel_sum < 0.1:
        return "等待时间显著（kernel极短但wait长）"
    return None


def _diag_utilization(wall, busy_union):
    if busy_union > 0 and wall > 0:
        utilization = busy_union / wall * 100
        if utilization > 95:
            return None
        if utilization > 80:
            return f"利用率良好（{utilization:.0f}%）"
        return f"利用率偏低（{utilization:.0f}%）"
    return None


def generate_diagnosis(wall: float, busy_union: float, kernel_sum: float, total_cost: float) -> str:
    """根据四指标生成诊断结论（中文）。规则见各 _diag_* 子函数。"""
    if wall == 0 and kernel_sum == 0:
        return "无数据"

    candidate_diagnoses = (
        _diag_parallelism(wall, kernel_sum),
        _diag_bubble(wall, busy_union),
        _diag_wait(kernel_sum, total_cost),
        _diag_utilization(wall, busy_union),
    )
    diagnoses = [d for d in candidate_diagnoses if d]

    if not diagnoses:
        if abs(wall - busy_union) < wall * 0.1 and abs(kernel_sum - wall) < wall * 0.1:
            return "干净顺序执行"
        return "正常执行"

    return "；".join(diagnoses)


def collect_all_op_indices(node: dict) -> List[int]:
    """
    递归收集节点及其子节点的所有 op_indices
    """
    indices = list(node.get('op_indices', []))
    for child in node.get('children', []):
        indices.extend(collect_all_op_indices(child))
    return indices


def collect_tree_nodes(node: dict, ctx: TreeWalkCtx, multiplier: int,
                       current_depth: int, parent_path: str = "") -> List[dict]:
    """
    递归收集树中所有节点及其指标
    """
    results = []
    name = node.get('name', 'Unknown')
    path = f"{parent_path}/{name}" if parent_path else name

    all_op_indices = collect_all_op_indices(node)
    metrics = compute_node_metrics(all_op_indices, ctx.operators, multiplier)

    results.append({
        'name': name,
        'path': path,
        'depth': current_depth,
        'multiplier': multiplier,
        **metrics
    })

    if current_depth < ctx.max_depth:
        children = node.get('children', [])
        for child in children:
            child_results = collect_tree_nodes(
                child, ctx, 1, current_depth + 1, path
            )
            results.extend(child_results)

    return results


def categorize_nodes(nodes: List[dict], config: dict) -> Tuple[List[dict], List[dict]]:
    """
    将节点分为主要模块（layer_structure）和辅助模块（stages + runtime_auxiliary）
    """
    layer_type_names = set(config.get('layer_types', {}).keys())
    stage_names = set()
    for stage_name in config.get('stages', {}).keys():
        stage_names.add(stage_name)
        stage_info = config.get('stages', {}).get(stage_name, {})
        stage_names.add(stage_info.get('name', stage_name))
    
    main_nodes = []
    aux_nodes = []
    
    for node in nodes:
        path = node.get('path', '')
        name = node.get('name', '')
        
        is_main = any(lt in path or lt == name for lt in layer_type_names)
        is_aux = any(s in path or s == name for s in stage_names)
        
        if 'runtime_auxiliary' in path or 'runtime' in name.lower():
            aux_nodes.append(node)
        elif is_main:
            main_nodes.append(node)
        elif is_aux:
            aux_nodes.append(node)
        elif node.get('depth', 0) <= 1:
            aux_nodes.append(node)
    
    return main_nodes, aux_nodes


def compute_step_wall_ms(operators: List[dict]) -> float:
    """
    计算整个 step 的 wall_ms（所有 operators 的时间跨度）
    """
    if not operators:
        return 0.0
    min_start = min(op.get('start_time_us', 0) for op in operators)
    max_end = max(op.get('start_time_us', 0) + op.get('duration_us', 0) for op in operators)
    return (max_end - min_start) / 1000


def generate_metrics_table(nodes: List[dict], title: str, total_wall_ms: float) -> str:
    """
    生成 Markdown 指标表格
    """
    if not nodes:
        return f"### {title}\n\n无数据\n"
    
    lines = [
        f"### {title}",
        "",
        "| 节点 | wall_ms | busy_union_ms | kernel_sum_ms | total_cost_ms | 并行度 | bubble_ms | 占比% | kernel数 | 诊断结论 |",
        ("|------|---------|---------------|---------------|---------------|"
         "--------|-----------|-------|----------|----------|")
    ]
    
    for node in nodes:
        name = node.get('name', 'Unknown')
        depth = node.get('depth', 0)
        multiplier = node.get('multiplier', 1)
        
        indent = "　" * (depth - 1)
        display_name = f"{indent}{name}"
        if multiplier > 1 and depth <= 1:
            display_name = f"{display_name} ×{multiplier}"
        
        wall = node.get('wall_ms', 0)
        busy = node.get('busy_union_ms', 0)
        ksum = node.get('kernel_sum_ms', 0)
        tcost = node.get('total_cost_ms', 0)
        parallelism = node.get('parallelism', '-')
        bubble = node.get('bubble_ms', 0)
        ratio_pct = f"{wall / total_wall_ms * 100:.1f}" if total_wall_ms > 0.001 else '-'
        kcount = node.get('kernel_count', 0)
        diag = node.get('diagnosis', '')
        
        lines.append(
            f"| {display_name} | {wall:.3f} | {busy:.3f} | {ksum:.3f} | {tcost:.3f} "
            f"| {parallelism} | {bubble:.3f} | {ratio_pct} | {kcount} | {diag} |"
        )
    
    lines.append("")
    return "\n".join(lines)


_METRICS_DOC_LINES = [
    "## 指标说明",
    "",
    "### 四维基础指标",
    "",
    "| 指标 | 定义 | 含义 |",
    "|------|------|------|",
    "| wall_ms | 最后kernel结束 - 首个kernel开始 | 实际墙上时钟耗时（含间隙） |",
    "| busy_union_ms | 合并后的设备忙碌时间 | 设备实际利用率（去重叠） |",
    "| kernel_sum_ms | 所有kernel时长的算术和 | 总计算量（忽略重叠） |",
    "| total_cost_ms | Σ(duration + wait) | 完整成本（含等待） |",
    "",
    "### 衍生指标",
    "",
    "| 指标 | 计算 | 含义 |",
    "|------|------|------|",
    "| 并行度 | kernel_sum_ms / wall_ms | 多流并行执行倍数（>1×表示有并行） |",
    "| bubble_ms | wall_ms - busy_union_ms | 设备空闲气泡时间 |",
    "| 占比% | wall_ms / step总wall_ms × 100 | 占整个 step 墙上时钟的比例 |",
    "",
    "## 诊断规则",
    "",
    "| 条件 | 阈值 | 诊断结论 |",
    "|------|------|----------|",
    "| kernel_sum > wall | > 1.5× | 高流并行度（多流重叠执行） |",
    "| kernel_sum > wall | > 1.2× | 中等流并行 |",
    "| wall > busy_union | > 1.5× | 存在间隙气泡 |",
    "| total_cost > kernel_sum | > 1.3× | 等待时间显著，检查 wait-anchor 热点 |",
    "| busy_union / wall | 80%~95% | 利用率良好 |",
    "| busy_union / wall | < 80% | 利用率偏低 |",
    "| busy_union ≈ wall ≈ kernel_sum | 偏差 < 10% | 干净顺序执行 |",
    "| 其他 | — | 正常执行 |",
    "",
    "---",
    "",
]


def _collect_metric_nodes(config, walk_ctx):
    """从 stages / layer_structure / runtime_auxiliary 收集全部带指标的节点。"""
    all_nodes = []
    for _sname, sinfo in config.get('stages', {}).items():
        stage_indices = sinfo.get('stage_indices', [0])
        all_nodes.extend(collect_tree_nodes(sinfo, walk_ctx,
                                            len(stage_indices) if stage_indices else 1, 1))

    layer_types = config.get('layer_types', {})
    layer_structure = config.get('layer_structure', {})
    for layer_type in layer_types.keys():
        structure = layer_structure.get(layer_type, {})
        if not structure:
            continue
        layer_indices = layer_types.get(layer_type, {}).get('layer_indices', [])
        all_nodes.extend(collect_tree_nodes(structure, walk_ctx, len(layer_indices), 1))

    for aux in config.get('runtime_auxiliary', []):
        instance_indices = aux.get('instance_indices', [0])
        all_nodes.extend(collect_tree_nodes(aux, walk_ctx,
                                            len(instance_indices) if instance_indices else 1, 1))
    return all_nodes


def _dedupe_and_sort_nodes(nodes):
    """按 (path, depth) 去重并排序。"""
    seen = set()
    unique = []
    for n in nodes:
        key = (n.get('path', ''), n.get('depth', 0))
        if key not in seen:
            seen.add(key)
            unique.append(n)
    return sorted(unique, key=lambda x: (x.get('depth', 0), x.get('path', '')))


def generate_metrics_report(raw_ops: dict, config: dict, operators: List[dict],
                            max_depth: int = 3) -> str:
    """生成完整的指标报告。"""
    model_name = config.get('model_name', 'Model')
    step_id = raw_ops.get('step_id', 'N/A')
    total_kernels = raw_ops.get('kernel_count', len(operators))
    total_wall_ms = compute_step_wall_ms(operators)

    walk_ctx = TreeWalkCtx(operators=operators, max_depth=max_depth)
    all_nodes = _collect_metric_nodes(config, walk_ctx)
    main_nodes, aux_nodes = categorize_nodes(all_nodes, config)
    main_nodes = _dedupe_and_sort_nodes(main_nodes)
    aux_nodes = _dedupe_and_sort_nodes(aux_nodes)

    lines = [
        f"# {model_name} 性能指标分析",
        "",
        f"**Step**: {step_id} | **总Kernel数**: {total_kernels} | **Step wall_ms**: {total_wall_ms:.3f}",
        "",
    ]
    lines.extend(_METRICS_DOC_LINES)

    if aux_nodes:
        lines.append(generate_metrics_table(aux_nodes, "辅助模块指标（stages / runtime）", total_wall_ms))
    if main_nodes:
        lines.append(generate_metrics_table(main_nodes, "主要模块指标（decoder layers）", total_wall_ms))

    return "\n".join(lines)


def main():
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    parser = argparse.ArgumentParser(
        description='NPU 性能指标计算 - Step 4',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  %(prog)s -r raw_ops_details.json -c analysis_config.json -o metrics_report.md
  %(prog)s -r raw_ops_details.json -c analysis_config.json -o metrics_report.md -d 4
        '''
    )
    
    parser.add_argument('-r', '--raw-ops', required=True, metavar='FILE',
                        help='raw_ops_details.json 文件路径')
    parser.add_argument('-c', '--config', required=True, metavar='FILE',
                        help='analysis_config.json 文件路径')
    parser.add_argument('-o', '--output', metavar='FILE',
                        help='输出 Markdown 文件路径（默认打印到标准输出）')
    parser.add_argument('-d', '--depth', type=int, default=3,
                        help='指标计算深度（默认: 3）')
    
    args = parser.parse_args()
    
    try:
        raw_ops_file = validate_file_exists(args.raw_ops)
        config_file = validate_file_exists(args.config)
        
        raw_ops = load_json(raw_ops_file)
        config = load_json(config_file)
        
        operators = raw_ops.get('operators', [])
        
        report = generate_metrics_report(raw_ops, config, operators, args.depth)
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info("指标报告已生成: %s", args.output)
        else:
            logger.info(report)

    except (FileNotFoundError, ValueError) as e:
        logger.error("错误: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("未知错误: %s", e)
        sys.exit(1)


if __name__ == '__main__':
    main()
