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
import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, List, Tuple, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import breakdown_common as bc  # noqa: E402


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


def compute_node_metrics(op_indices: List[int], operators: List[dict], multiplier: int = 1) -> dict:
    """
    计算单个节点的四维指标及衍生指标
    """
    empty_result = {
        'wall_ms': 0.0,
        'busy_union_ms': 0.0,
        'kernel_sum_ms': 0.0,
        'total_cost_ms': 0.0,
        'parallelism': '-',
        'bubble_ms': 0.0,
        'kernel_count': 0,
        'diagnosis': '无算子'
    }

    if not op_indices:
        return empty_result

    op_dict = {op['index']: op for op in operators}
    ops = [op_dict[i] for i in op_indices if i in op_dict]

    if not ops:
        return empty_result

    start_times = []
    end_times = []
    intervals = []
    duration_sum = 0.0
    total_cost = 0.0

    for op in ops:
        start = op.get('start_time_us', 0)
        duration = op.get('duration_us', 0)
        wait = op.get('wait_time_us', 0) or 0

        # Wall span and busy union stay based on the real interval: a doubly-reported collective
        # still occupied the device for that time. Only the arithmetic sums skip the duplicate,
        # which is exactly the double-count — the union already merges the identical intervals.
        start_times.append(start)
        end_times.append(start + duration)
        intervals.append((start, start + duration))
        if bc.is_duplicate_record(op):
            continue
        duration_sum += duration
        total_cost += duration + wait

    wall_us = max(end_times) - min(start_times) if start_times else 0
    busy_union_us = merge_intervals(intervals)

    wall_ms = wall_us / 1000 * multiplier
    busy_union_ms = busy_union_us / 1000 * multiplier
    kernel_sum_ms = duration_sum / 1000 * multiplier
    total_cost_ms = total_cost / 1000 * multiplier

    if wall_ms > 0.001:
        parallelism = f"{kernel_sum_ms / wall_ms:.1f}×"
    else:
        parallelism = '-'

    bubble_ms = round(wall_ms - busy_union_ms, 3)

    findings = generate_findings(wall_ms, busy_union_ms, kernel_sum_ms, total_cost_ms)

    return {
        'wall_ms': round(wall_ms, 3),
        'busy_union_ms': round(busy_union_ms, 3),
        'kernel_sum_ms': round(kernel_sum_ms, 3),
        'total_cost_ms': round(total_cost_ms, 3),
        'parallelism': parallelism,
        'bubble_ms': bubble_ms,
        'kernel_count': len(ops) * multiplier,
        'findings': findings,
        'diagnosis': render_findings(findings)
    }


FINDING_CODES = (
    'STREAM_PARALLEL_HIGH', 'STREAM_PARALLEL_MID', 'GAP_BUBBLE', 'WAIT_DOMINANT',
    'UTIL_GOOD', 'UTIL_LOW', 'CLEAN_SEQUENTIAL', 'NORMAL', 'NO_DATA',
)

ADVICE_REFERENCE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'references', 'diagnosis_advice.md')


def load_advice_table(path: str = ADVICE_REFERENCE) -> dict:
    """从 references/diagnosis_advice.md 解析 code -> {advice, next_data, not_applicable}。

    建议文本的唯一来源是该 reference，代码不内联任何建议正文。
    reference 缺失或某 code 缺段时返回空 dict / 跳过该 code，不抛异常 ——
    建议是咨询性质，不得因其缺失影响指标产出。
    """
    table = {}
    if not os.path.isfile(path):
        return table
    current = None
    with open(path, 'r', encoding='utf-8') as fh:
        for raw in fh:
            line = raw.rstrip('\n')
            m = re.match(r'^##\s+code:\s*([A-Z_]+)\s*$', line)
            if m:
                current = m.group(1)
                table[current] = {}
                continue
            if current is None:
                continue
            m = re.match(r'^-\s+\*\*(advice|next_data|not_applicable)\*\*:\s*(.+)$', line)
            if m:
                table[current][m.group(1)] = m.group(2).strip()
    return {k: v for k, v in table.items() if v.get('advice')}


def attach_advice(findings: List[dict], metric_scope: str,
                  advice_table: dict) -> List[dict]:
    """给 findings 挂 L1 建议。aggregate 作用域加 [聚合口径] 前缀（见 reference §聚合作用域）。"""
    out = []
    for f in findings:
        entry = dict(f)
        info = advice_table.get(f.get('code'), {})
        if info.get('advice'):
            prefix = '[聚合口径] ' if metric_scope == 'aggregate' else ''
            entry['advice_l1'] = prefix + info['advice']
            if info.get('next_data'):
                entry['next_data'] = info['next_data']
            if info.get('not_applicable'):
                entry['not_applicable'] = info['not_applicable']
        out.append(entry)
    return out


def generate_findings(wall: float, busy_union: float, kernel_sum: float,
                      total_cost: float) -> List[dict]:
    """结构化诊断 findings。渲染成字符串的结果与 generate_diagnosis 完全一致。

    每项：{code, severity, metrics, text}。code 取 FINDING_CODES 的有限枚举。
    findings 是纯咨询信息，不进任何门禁、不影响 validation / score / 停止条件。
    """
    if wall == 0 and kernel_sum == 0:
        return [{'code': 'NO_DATA', 'severity': 'info', 'metrics': {}, 'text': '无数据'}]

    out = []
    eps = 0.001

    if kernel_sum > wall * 1.5:
        ratio = kernel_sum / wall if wall > eps else 0
        out.append({'code': 'STREAM_PARALLEL_HIGH', 'severity': 'info',
                    'metrics': {'kernel_sum_over_wall': round(ratio, 3)},
                    'text': f"高流并行度（kernel_sum/wall={ratio:.1f}×）"})
    elif kernel_sum > wall * 1.2:
        ratio = kernel_sum / wall if wall > eps else 0
        out.append({'code': 'STREAM_PARALLEL_MID', 'severity': 'info',
                    'metrics': {'kernel_sum_over_wall': round(ratio, 3)},
                    'text': f"中等流并行（kernel_sum/wall={ratio:.1f}×）"})

    if wall > busy_union * 1.5:
        gap_ratio = (wall - busy_union) / wall * 100 if wall > eps else 0
        out.append({'code': 'GAP_BUBBLE', 'severity': 'high' if gap_ratio >= 80 else 'medium',
                    'metrics': {'gap_pct': round(gap_ratio, 1)},
                    'text': f"存在间隙气泡（gap={gap_ratio:.0f}%）"})

    wait_time = total_cost - kernel_sum
    if wait_time > 0.1 and kernel_sum > eps and total_cost > kernel_sum * 1.3:
        wait_ratio = wait_time / kernel_sum * 100
        if wait_ratio < 1000:
            out.append({'code': 'WAIT_DOMINANT', 'severity': 'high',
                        'metrics': {'wait_pct': round(wait_ratio, 1)},
                        'text': f"等待时间显著（wait占比{wait_ratio:.0f}%）"})
        else:
            out.append({'code': 'WAIT_DOMINANT', 'severity': 'high',
                        'metrics': {'wait_pct': round(wait_ratio, 1), 'kernel_sum_ms': kernel_sum},
                        'text': "等待时间显著（kernel极短但wait长）"})
    elif wait_time > kernel_sum * 2 and kernel_sum < 0.1:
        out.append({'code': 'WAIT_DOMINANT', 'severity': 'high',
                    'metrics': {'kernel_sum_ms': kernel_sum, 'wait_ms': round(wait_time, 3)},
                    'text': "等待时间显著（kernel极短但wait长）"})

    if busy_union > 0 and wall > 0:
        utilization = busy_union / wall * 100
        if utilization > 95:
            pass
        elif utilization > 80:
            out.append({'code': 'UTIL_GOOD', 'severity': 'info',
                        'metrics': {'utilization_pct': round(utilization, 1)},
                        'text': f"利用率良好（{utilization:.0f}%）"})
        else:
            out.append({'code': 'UTIL_LOW', 'severity': 'medium' if utilization >= 50 else 'high',
                        'metrics': {'utilization_pct': round(utilization, 1)},
                        'text': f"利用率偏低（{utilization:.0f}%）"})

    if not out:
        if abs(wall - busy_union) < wall * 0.1 and abs(kernel_sum - wall) < wall * 0.1:
            return [{'code': 'CLEAN_SEQUENTIAL', 'severity': 'info', 'metrics': {},
                     'text': '干净顺序执行'}]
        return [{'code': 'NORMAL', 'severity': 'info', 'metrics': {}, 'text': '正常执行'}]

    return out


def render_findings(findings: List[dict]) -> str:
    """findings -> 表格用的单行中文串。"""
    return "；".join(f.get('text', '') for f in findings)


def generate_diagnosis(wall: float, busy_union: float, kernel_sum: float, total_cost: float) -> str:
    """
    根据四指标生成诊断结论（中文）。保留为 render_findings(generate_findings(...)) 的薄封装。

    诊断规则（与 SKILL.md 一致）：
    - kernel_sum > wall × 1.5: 高流并行度
    - kernel_sum > wall × 1.2: 中等流并行
    - wall > busy_union × 1.5: 存在间隙气泡
    - total_cost > kernel_sum × 1.3: 等待时间显著，检查 wait-anchor 热点
    - busy_union/wall 在 80%~95%: 利用率良好
    - busy_union/wall < 80%: 利用率偏低
    - busy_union ≈ wall ≈ kernel_sum（偏差<10%）: 干净顺序执行
    - 其他: 正常执行
    """
    return render_findings(generate_findings(wall, busy_union, kernel_sum, total_cost))


def collect_all_op_indices(node: dict) -> List[int]:
    """
    递归收集节点及其子节点的所有 op_indices
    """
    indices = list(node.get('_report_op_indices', node.get('op_indices', [])))
    for child in node.get('children', []):
        indices.extend(collect_all_op_indices(child))
    return indices


def collect_tree_nodes(node: dict, operators: List[dict], multiplier: int,
                       current_depth: int, max_depth: int,
                       parent_path: str = "") -> List[dict]:
    """
    递归收集树中所有节点及其指标
    """
    results = []
    name = node.get('name', 'Unknown')
    path = f"{parent_path}/{name}" if parent_path else name

    all_op_indices = collect_all_op_indices(node)
    effective_multiplier = 1 if '_report_op_indices' in node else multiplier
    metrics = compute_node_metrics(all_op_indices, operators, effective_multiplier)

    results.append({
        'name': name,
        'path': path,
        'depth': current_depth,
        'multiplier': multiplier,
        **metrics
    })

    if current_depth < max_depth:
        children = node.get('children', [])
        for child in children:
            child_results = collect_tree_nodes(
                child, operators, 1, current_depth + 1, max_depth, path
            )
            results.extend(child_results)

    return results


def iter_layer_sections(config: dict):
    """Yield (name, structure_node, multiplier) for decoder-layer sections.

    v2: derived from trace_instances/structures (invocation-count multiplier).
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


def categorize_nodes(nodes: List[dict], config: dict) -> Tuple[List[dict], List[dict]]:
    """
    将节点分为主要模块（decoder layers）和辅助模块（stages + runtime_auxiliary）
    """
    if config.get('schema_version') == 2:
        layer_type_names = {name for name, _s, _m in iter_layer_sections(config)}
    else:
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
        else:
            if node.get('depth', 0) <= 1:
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
        "|------|---------|---------------|---------------|---------------|--------|-----------|-------|----------|----------|"
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
            f"| {display_name} | {wall:.3f} | {busy:.3f} | {ksum:.3f} | {tcost:.3f} | {parallelism} | {bubble:.3f} | {ratio_pct} | {kcount} | {diag} |"
        )

    lines.append("")
    return "\n".join(lines)


def build_findings_document(model_name: str, step_id: Any, nodes: List[dict],
                            advice_table: dict) -> dict:
    """机器可读的诊断出口 metrics_findings.json。

    advisory_only=True 是契约的一部分：任何下游读到该文件都必须视其为咨询信息，
    不得据此阻断流程或改变评分。
    """
    entries = []
    for node in nodes:
        multiplier = node.get('multiplier', 1) or 1
        scope = 'aggregate' if multiplier > 1 else 'instance'
        findings = attach_advice(node.get('findings', []), scope, advice_table)
        entries.append({
            'path': node.get('path', ''),
            'name': node.get('name', ''),
            'depth': node.get('depth', 0),
            'metric_scope': scope,
            'invocation_count': multiplier,
            'metrics': {
                'wall_ms': node.get('wall_ms', 0),
                'busy_union_ms': node.get('busy_union_ms', 0),
                'kernel_sum_ms': node.get('kernel_sum_ms', 0),
                'total_cost_ms': node.get('total_cost_ms', 0),
                'bubble_ms': node.get('bubble_ms', 0),
                'kernel_count': node.get('kernel_count', 0),
            },
            'findings': findings,
        })
    return {
        'schema_version': 1,
        'advisory_only': True,
        'advisory_note': (
            '诊断与建议为咨询信息，不参与 validation / breakdown_score / hard_gates / '
            '停止条件；聚合作用域的比例不得外推到单实例。'),
        'model_name': model_name,
        'representative_step': step_id,
        'advice_source': os.path.relpath(ADVICE_REFERENCE, os.path.dirname(ADVICE_REFERENCE)),
        'advice_table_loaded': bool(advice_table),
        'nodes': entries,
    }


def generate_advice_section(findings_doc: dict) -> str:
    """报告里的建议段落。按 code 聚类，避免 77 个节点逐条重复同一句建议。"""
    by_code = {}
    for node in findings_doc.get('nodes', []):
        for f in node.get('findings', []):
            code = f.get('code')
            if code in ('NORMAL', 'CLEAN_SEQUENTIAL', 'UTIL_GOOD',
                        'STREAM_PARALLEL_HIGH', 'STREAM_PARALLEL_MID'):
                continue
            # 聚类段落跨 instance/aggregate 混合，作用域前缀只在 per-node JSON 里有意义，
            # 这里剥掉；作用域分布由段落标题的 instance/aggregate 计数表达。
            advice = (f.get('advice_l1') or '').replace('[聚合口径] ', '', 1) or None
            slot = by_code.setdefault(code, {'nodes': [], 'advice': advice,
                                             'next_data': f.get('next_data'),
                                             'not_applicable': f.get('not_applicable'),
                                             'severity': f.get('severity')})
            slot['nodes'].append((node['path'], node['metric_scope']))

    lines = ['## 诊断建议（咨询性质，不影响校验与评分）', '']
    if not by_code:
        lines += ['本 step 未命中任何需要关注的诊断码。', '']
        return "\n".join(lines)

    lines += ['> 建议只指出「下一步该看什么数据」，不断言根因；聚合口径的比例不能外推到单实例。',
              '> 建议文本来源：`references/diagnosis_advice.md`。', '']
    order = ['WAIT_DOMINANT', 'GAP_BUBBLE', 'UTIL_LOW', 'NO_DATA']
    for code in order + [c for c in by_code if c not in order]:
        if code not in by_code:
            continue
        slot = by_code[code]
        agg = sum(1 for _p, s in slot['nodes'] if s == 'aggregate')
        inst = len(slot['nodes']) - agg
        lines.append(f"### {code}（severity={slot['severity']}，命中 {len(slot['nodes'])} 个节点"
                     f"：instance {inst} / aggregate {agg}）")
        lines.append("")
        if slot['advice']:
            lines.append(f"- **建议**：{slot['advice']}")
        if slot['next_data']:
            lines.append(f"- **接下来看**：{slot['next_data']}")
        if slot['not_applicable']:
            lines.append(f"- **不适用于**：{slot['not_applicable']}")
        sample = "、".join(f"`{p}`" for p, _s in slot['nodes'][:5])
        more = f" 等 {len(slot['nodes'])} 个" if len(slot['nodes']) > 5 else ""
        lines.append(f"- **命中节点**：{sample}{more}")
        lines.append("")
    return "\n".join(lines)


def generate_metrics_report(raw_ops: dict, config: dict, operators: List[dict],
                           max_depth: int = 3, findings_out: dict = None) -> str:
    """
    生成完整的指标报告。findings_out 非 None 时，把 findings 文档写回该 dict（供 CLI 落盘）。
    """
    model_name = config.get('model_name', 'Model')
    step_id = raw_ops.get('step_id', 'N/A')
    total_kernels = raw_ops.get('kernel_count', len(operators))

    total_wall_ms = compute_step_wall_ms(operators)

    all_nodes = []

    stages = config.get('stages', {})
    for stage_name, stage_info in stages.items():
        stage_indices = stage_info.get('stage_indices', [0])
        stage_count = len(stage_indices) if stage_indices else 1
        nodes = collect_tree_nodes(stage_info, operators, stage_count, 1, max_depth)
        all_nodes.extend(nodes)

    for _name, structure, layer_count in iter_layer_sections(config):
        nodes = collect_tree_nodes(structure, operators, layer_count, 1, max_depth)
        all_nodes.extend(nodes)

    runtime_aux = config.get('runtime_auxiliary', [])
    for aux in runtime_aux:
        instance_indices = aux.get('instance_indices', [0])
        instance_count = len(instance_indices) if instance_indices else 1
        nodes = collect_tree_nodes(aux, operators, instance_count, 1, max_depth)
        all_nodes.extend(nodes)

    main_nodes, aux_nodes = categorize_nodes(all_nodes, config)

    def dedupe_and_sort(nodes):
        seen = set()
        unique = []
        for n in nodes:
            key = (n.get('path', ''), n.get('depth', 0))
            if key not in seen:
                seen.add(key)
                unique.append(n)
        return sorted(unique, key=lambda x: (x.get('depth', 0), x.get('path', '')))

    main_nodes = dedupe_and_sort(main_nodes)
    aux_nodes = dedupe_and_sort(aux_nodes)

    lines = [
        f"# {model_name} 性能指标分析",
        "",
        f"**Step**: {step_id} | **总Kernel数**: {total_kernels} | **Step wall_ms**: {total_wall_ms:.3f}",
        "",
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
        ""
    ]

    if aux_nodes:
        lines.append(generate_metrics_table(aux_nodes, "辅助模块指标（stages / runtime）", total_wall_ms))

    if main_nodes:
        lines.append(generate_metrics_table(main_nodes, "主要模块指标（decoder layers）", total_wall_ms))

    advice_table = load_advice_table()
    findings_doc = build_findings_document(
        model_name, step_id, aux_nodes + main_nodes, advice_table)
    if findings_out is not None:
        findings_out.clear()
        findings_out.update(findings_doc)
    lines.append("---")
    lines.append("")
    lines.append(generate_advice_section(findings_doc))

    return "\n".join(lines)


def main():
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
    parser.add_argument('--findings-out', metavar='FILE',
                        help='结构化诊断与 L1 建议输出路径（metrics_findings.json，咨询性质）')

    args = parser.parse_args()

    try:
        raw_ops_file = validate_file_exists(args.raw_ops)
        config_file = validate_file_exists(args.config)

        raw_ops = load_json(raw_ops_file)
        config = load_json(config_file)

        operators = raw_ops.get('operators', [])

        findings_doc = {}
        report = generate_metrics_report(raw_ops, config, operators, args.depth,
                                        findings_out=findings_doc)

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"指标报告已生成: {args.output}")
        else:
            print(report)

        if args.findings_out:
            with open(args.findings_out, 'w', encoding='utf-8') as f:
                json.dump(findings_doc, f, ensure_ascii=False, indent=2)
            n = len(findings_doc.get('nodes', []))
            loaded = findings_doc.get('advice_table_loaded')
            print(f"诊断 findings 已生成: {args.findings_out} "
                  f"（{n} 节点，建议表{'已' if loaded else '未'}加载；咨询性质，不影响门禁）")

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
