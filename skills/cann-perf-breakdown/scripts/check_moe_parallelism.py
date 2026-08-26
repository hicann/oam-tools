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
"""Validate MoE parallelism claims against trace operator shapes.

Checks (MP1..MP3):
  MP1: ep_size derived from shapes matches declared trace_scope.ep
  MP2: evidence 不得使用 "absence of X ->" 式推断（必须有正向形状证据）
  MP3: num_experts / experts_per_rank 一致性（router、expert_tokens、grouped_matmul）

When MoE operators are present in trace, ep_size is arithmetic, not inference.
"""
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import breakdown_common as bc  # noqa: E402


class Issue:
    def __init__(self, code, severity, path, message):
        self.id = code
        self.severity = severity
        self.node_path = path
        self.message = message

    def to_dict(self):
        return {
            'id': self.id,
            'severity': self.severity,
            'node_path': self.node_path,
            'message': self.message,
        }


def _parse_shape(shape_str):
    """Parse shape string like '1,128' or '16,88,176,16,16' to list of ints.

    If shape_str contains semicolons (multiple tensors), parse only the first one.
    Example: '2816;16,88,176' -> [2816]
    """
    if not shape_str or shape_str == 'N/A':
        return []
    # Handle multiple tensors separated by semicolon
    if ';' in shape_str:
        parts = shape_str.split(';')
        # Try each part until we find one that parses
        for part in parts:
            try:
                return [int(s.strip()) for s in part.split(',') if s.strip()]
            except ValueError:
                continue
        return []
    try:
        return [int(s.strip()) for s in shape_str.split(',') if s.strip()]
    except ValueError:
        return []


def _find_ops(ops, name_pattern, limit=None):
    """Find ops matching normalized_name pattern. Returns list of (index, op)."""
    results = []
    pattern = re.compile(name_pattern, re.IGNORECASE)
    for op in ops:
        if pattern.search(op.get('normalized_name', '')):
            results.append(op)
            if limit and len(results) >= limit:
                break
    return results


def _raw_operators(raw_ops):
    ops = raw_ops.get('operators', [])
    if not ops:
        ops = raw_ops.get('compact_operator_count')
        if not ops:
            ops = raw_ops.get('ops', [])
    if not ops and isinstance(raw_ops, list):
        ops = raw_ops
    return ops


def _claimed_ep(trace_scope):
    claimed = trace_scope.get('ep')
    if claimed is None:
        claimed = trace_scope.get('parallelism', {}).get('ep')
    return claimed


def _router_expert_count(ops, moe_gating):
    for op in ops[:100]:
        if 'MatMul' not in op.get('normalized_name', ''):
            continue
        out_shape = _parse_shape(op.get('output_shapes', ''))
        next_index = ops.index(op) + 1
        next_is_gating = (next_index < len(ops)
                          and 'MoeGating' in ops[next_index].get('normalized_name', ''))
        if len(out_shape) >= 2 and out_shape[-1] >= 64 and next_is_gating:
            return out_shape[-1]
    if moe_gating:
        gating_input = _parse_shape(moe_gating[0].get('input_shapes', ''))
        if len(gating_input) >= 2 and gating_input[-1] > 1:
            return gating_input[-1]
    return None


def _experts_per_rank(compute_tokens, grouped_matmul, issues):
    experts = None
    sources = []
    if compute_tokens:
        out_shape = _parse_shape(compute_tokens[0].get('output_shapes', ''))
        if out_shape:
            experts = out_shape[-1]
            sources.append(f'MoeComputeExpertTokens output={experts}')
    if not grouped_matmul:
        return experts, sources
    input_shape = _parse_shape(grouped_matmul[0].get('input_shapes', ''))
    if not input_shape or len(input_shape) < 3:
        return experts, sources
    grouped_experts = input_shape[0]
    if experts is None:
        return grouped_experts, [f'GroupedMatmul weight[0]={grouped_experts}']
    if grouped_experts != experts:
        issues.append(Issue(
            'MP3', 'error', 'trace_scope.ep',
            f'experts_per_rank 不一致: MoeComputeExpertTokens={experts}, '
            f'GroupedMatmul weight[0]={grouped_experts}').to_dict())
    return experts, sources


def _derive_ep(num_experts, experts_per_rank, issues):
    if not num_experts or not experts_per_rank:
        return None
    if num_experts % experts_per_rank != 0:
        issues.append(Issue(
            'MP3', 'error', 'trace_scope.ep',
            f'num_experts={num_experts} 不能被 experts_per_rank={experts_per_rank} 整除'
        ).to_dict())
        return None
    return num_experts // experts_per_rank


def _check_ep_claim(derived_ep, claimed_ep, num_experts, experts_per_rank, issues):
    if derived_ep is None:
        issues.append(Issue(
            'MP1', 'warning', 'trace_scope.ep',
            f'trace 有 MoE 算子但无法从形状推导 ep_size（num_experts={num_experts}, '
            f'experts_per_rank={experts_per_rank}）').to_dict())
    elif claimed_ep is None or claimed_ep == 'unknown':
        issues.append(Issue(
            'MP1', 'warning', 'trace_scope.ep',
            f'trace 形状推导 ep={derived_ep} (num_experts={num_experts} ÷ '
            f'experts_per_rank={experts_per_rank})，但 trace_scope.ep 未声明').to_dict())
    elif claimed_ep != derived_ep:
        issues.append(Issue(
            'MP1', 'error', 'trace_scope.ep',
            f'trace_scope.ep={claimed_ep} 与形状推导 ep={derived_ep} 不符 '
            f'(num_experts={num_experts} ÷ experts_per_rank={experts_per_rank})').to_dict())


def _check_indirect_evidence(evidence, issues):
    for item in evidence:
        item_lower = item.lower()
        indirect = any(pattern in item_lower for pattern in ['no ', 'absence of', 'without'])
        if indirect and ('→' in item or '->' in item):
            issues.append(Issue(
                'MP2', 'warning', 'trace_scope.evidence',
                f'证据使用 "absence of X ->" 式间接推断，应改用正向形状证据: {item[:100]}'
            ).to_dict())


def check_moe_parallelism(config, raw_ops):
    """Validate MoE ep_size against operator shapes."""
    issues = []
    ops = _raw_operators(raw_ops)
    trace_scope = config.get('trace_scope', {})
    claimed_ep = _claimed_ep(trace_scope)
    evidence = trace_scope.get('evidence', [])
    moe_gating = _find_ops(ops, r'MoeGatingTopK', limit=1)
    moe_init_routing = _find_ops(ops, r'MoeInitRouting', limit=1)
    compute_tokens = _find_ops(ops, r'MoeComputeExpertTokens', limit=1)
    grouped_matmul = _find_ops(ops, r'GroupedMatmul', limit=1)
    has_moe = bool(moe_gating or moe_init_routing or grouped_matmul)
    if not has_moe:
        if claimed_ep not in (None, 'unknown', 1):
            issues.append(Issue(
                'MP1', 'warning', 'trace_scope.ep',
                f'trace 无 MoE 算子，但 ep 声明为 {claimed_ep}（应为 1 或 unknown）').to_dict())
        return issues, {'has_moe': False}
    num_experts = _router_expert_count(ops, moe_gating)
    experts_per_rank, sources = _experts_per_rank(compute_tokens, grouped_matmul, issues)
    derived_ep = _derive_ep(num_experts, experts_per_rank, issues)
    _check_ep_claim(derived_ep, claimed_ep, num_experts, experts_per_rank, issues)
    _check_indirect_evidence(evidence, issues)
    errors = [i for i in issues if i.get('severity') == 'error']
    warnings = [i for i in issues if i.get('severity') == 'warning']
    return issues, {
        'has_moe': has_moe,
        'num_experts': num_experts,
        'experts_per_rank': experts_per_rank,
        'experts_per_rank_sources': sources,
        'derived_ep': derived_ep,
        'claimed_ep': claimed_ep,
        'error_count': len(errors),
        'warning_count': len(warnings),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Validate MoE ep_size via shapes')
    parser.add_argument('-c', '--config', required=True, help='analysis_config_v2.json')
    parser.add_argument('-r', '--raw-ops', required=True, help='raw_ops.json or compact')
    parser.add_argument('-o', '--output')
    args = parser.parse_args()

    with open(args.config, 'r', encoding='utf-8') as f:
        config = json.load(f)
    with open(args.raw_ops, 'r', encoding='utf-8') as f:
        raw_ops = json.load(f)

    issues, detail = check_moe_parallelism(config, raw_ops)

    result = {
        'check': 'moe_parallelism',
        'issues': issues,
        'detail': detail,
    }
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
        bc.emit(f'MoE parallelism check 已写入: {args.output}  '
              f'errors={detail["error_count"]} warnings={detail["warning_count"]}')
    else:
        bc.emit(text)


if __name__ == '__main__':
    main()
