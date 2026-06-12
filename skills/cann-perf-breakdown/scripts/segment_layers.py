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
基于 raw_ops.json 的 normalized_name 序列做粗粒度 layer 边界候选检测。

启发式：找出"周期性"出现的 marker kernel（典型如 InplaceAddRmsNorm / FlashAttentionScore），
其相邻出现间隔的离散系数（CV = std / mean）越小、出现次数越多，越像 layer 边界标记。

输出 outputs/op_segments.json，格式：
{
  "best_marker": <kernel_name>,
  "layer_length_estimate": <int>,
  "confidence": <float, 0–1>,
  "boundaries": [op_index, op_index, ...],   # 每个 layer 的起始索引
  "ranges": [{"layer_idx": 0, "op_range": [start, end], "marker_index": <int>}, ...],
  "candidates": [{ "kernel": ..., "count": ..., "mean": ..., "cv": ... }, ...]
}

confidence < 0.5 时不输出 boundaries（视为不可靠候选）。
"""
import logging
import argparse
import json
import math
import os
import sys
from collections import defaultdict
logger = logging.getLogger(__name__)



def detect_periodic_markers(operators, min_occurrences=4, max_cv=0.4):
    """
    返回按 cv 升序排列的 marker 候选列表。
    每条：(kind, positions, mean, cv)
    """
    positions_by_kind = defaultdict(list)
    for i, op in enumerate(operators):
        # compact 视图中的 repeat 块需展开
        if op.get('repeat'):
            kind = op.get('normalized_name', '')
            count = op.get('count', 0)
            first = op.get('first_index', i)
            for k in range(count):
                positions_by_kind[kind].append(first + k)
        else:
            kind = op.get('normalized_name', '')
            positions_by_kind[kind].append(op.get('index', i))

    candidates = []
    for kind, positions in positions_by_kind.items():
        if len(positions) < min_occurrences:
            continue
        positions.sort()
        intervals = [positions[i + 1] - positions[i] for i in range(len(positions) - 1)]
        if not intervals:
            continue
        mean = sum(intervals) / len(intervals)
        if mean <= 0:
            continue
        var = sum((x - mean) ** 2 for x in intervals) / len(intervals)
        cv = math.sqrt(var) / mean
        if cv > max_cv:
            continue
        candidates.append({
            'kernel': kind,
            'count': len(positions),
            'mean': mean,
            'cv': cv,
            'positions': positions,
        })

    candidates.sort(key=lambda c: (c['cv'], -c['count']))
    return candidates


def confidence_from(cv, count):
    """Confidence = (1 - cv) * saturation(count). 落在 [0, 1]."""
    cv_term = max(0.0, 1.0 - cv / 0.5)  # cv=0 → 1; cv≥0.5 → 0
    count_term = min(1.0, count / 16.0)  # count<4 已被过滤；16+ 满分
    return round(cv_term * count_term, 3)


def build_segments(operators, candidate):
    positions = candidate['positions']
    layer_length = int(round(candidate['mean']))
    ranges = []
    for i, pos in enumerate(positions):
        if i + 1 < len(positions):
            end = positions[i + 1] - 1
        else:
            end = pos + layer_length - 1
        # 起点偏移到 marker 之前一段（典型 marker 在 layer 中部，回退 ~30% layer 长度）
        start = max(0, pos - layer_length // 3)
        ranges.append({
            'layer_idx': i,
            'op_range': [start, end],
            'marker_index': pos,
        })
    return ranges


def _build_segments_result(operators, candidates, min_confidence):
    """根据周期 marker 候选构建 op_segments 结果 dict。"""
    if not candidates:
        return {
            'best_marker': None,
            'layer_length_estimate': None,
            'confidence': 0.0,
            'boundaries': [],
            'ranges': [],
            'candidates': [],
            'note': '未检测到周期性 marker，AI 须按 structure_analysis_guide §A.3.1 全手动定位 layer 边界',
        }
    best = candidates[0]
    confidence = confidence_from(best['cv'], best['count'])
    note_tail = ('boundaries 可作 layer 候选起点，最终边界以源码语义为准。'
                 if confidence >= min_confidence
                 else f'confidence < {min_confidence}，仅供参考，AI 应回退到全手动定位。')
    return {
        'best_marker': best['kernel'],
        'layer_length_estimate': int(round(best['mean'])),
        'confidence': confidence,
        'boundaries': best['positions'] if confidence >= min_confidence else [],
        'ranges': build_segments(operators, best) if confidence >= min_confidence else [],
        'candidates': [
            {'kernel': c['kernel'], 'count': c['count'],
             'mean': round(c['mean'], 2), 'cv': round(c['cv'], 3)}
            for c in candidates[:5]
        ],
        'note': (f'最佳 marker={best["kernel"]}，{best["count"]} 次出现，'
                 f'平均间隔 {best["mean"]:.1f}, CV={best["cv"]:.3f}, confidence={confidence}. '
                 + note_tail),
    }


def main():
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    parser = argparse.ArgumentParser(description='Layer 边界候选检测')
    parser.add_argument('-r', '--raw-ops', dest='raw_ops', required=True,
                        help='raw_ops.json 路径（或 raw_ops.compact.json）')
    parser.add_argument('-o', '--output', default='outputs/op_segments.json',
                        help='输出 op_segments.json 路径')
    parser.add_argument('--min-occurrences', type=int, default=4,
                        help='marker 候选最少出现次数 (default: 4)')
    parser.add_argument('--max-cv', type=float, default=0.4,
                        help='marker 候选最大允许 CV (default: 0.4)')
    parser.add_argument('--min-confidence', type=float, default=0.5,
                        help='最低 confidence 阈值；低于该值不输出 boundaries')
    args = parser.parse_args()

    if not os.path.exists(args.raw_ops):
        logger.error('错误: 文件不存在: %s', args.raw_ops)
        sys.exit(1)

    with open(args.raw_ops, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    operators = raw.get('operators', [])
    if not operators:
        logger.error('错误: raw_ops 无 operators')
        sys.exit(1)

    candidates = detect_periodic_markers(
        operators, min_occurrences=args.min_occurrences, max_cv=args.max_cv)
    result = _build_segments_result(operators, candidates, args.min_confidence)

    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    logger.info('op_segments 已保存到: %s', args.output)
    logger.info('  best_marker: %s', result["best_marker"])
    logger.info('  confidence:  %s', result["confidence"])
    logger.info('  layer count: %s', len(result["boundaries"]))


if __name__ == '__main__':
    main()
