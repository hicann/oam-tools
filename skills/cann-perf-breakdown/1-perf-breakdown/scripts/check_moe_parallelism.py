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
"""Validate MoE parallelism claims against trace operator shapes.

Checks (MP1..MP3):
  MP1: ep_size derived from shapes matches declared trace_scope.ep
  MP2: evidence 不得使用 "absence of X ->" 式推断（必须有正向形状证据）
  MP3: num_experts / experts_per_rank 一致性（router、expert_tokens、grouped_matmul）

When MoE operators are present in trace, ep_size is arithmetic, not inference.
"""
import json
import re


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


def _parse_shapes(shape_str):
    """Parse every tensor in a semicolon-delimited profiler shape field."""
    if not shape_str or shape_str == 'N/A':
        return []
    parsed = []
    for part in shape_str.split(';'):
        shape = _parse_shape(part)
        if shape:
            parsed.append(shape)
    return parsed


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


def _with_ep_repair_policy(issue):
    issue['repair_policy'] = {
        'owner_artifact': 'analysis_config',
        'repair_class': 'candidate_annotation',
        'allowed_targets': {'analysis_config': ['$.trace_scope']},
        'required_evidence': ['candidate_nodes', 'raw_ops_slice'],
        'trace_selectors': [{
            'field': 'normalized_name',
            'match': 'prefix',
            'values': [
                'MoeGatingTopK', 'MoeComputeExpertTokens', 'GroupedMatmul',
            ],
        }],
    }
    return issue


def check_moe_parallelism(config, raw_ops):
    """Validate MoE ep_size against operator shapes.

    Args:
        config: analysis_config_v2.json dict
        raw_ops: raw_ops.json or raw_ops.compact.json dict

    Returns:
        (issues, detail_dict)
    """
    issues = []
    ops = raw_ops.get('operators', [])
    if not ops:
        # compact format wraps in another layer
        ops = raw_ops.get('compact_operator_count')
        if not ops:
            ops = raw_ops.get('ops', [])
    if not ops and isinstance(raw_ops, list):
        ops = raw_ops

    trace_scope = config.get('trace_scope', {})
    claimed_ep = trace_scope.get('ep')  # Try top-level first
    if claimed_ep is None:
        # Try parallelism.ep (nested)
        parallelism = trace_scope.get('parallelism', {})
        claimed_ep = parallelism.get('ep')
    evidence = trace_scope.get('evidence', [])

    # Look for MoE witness kernels
    moe_gating = _find_ops(ops, r'MoeGatingTopK', limit=1)
    moe_init_routing = _find_ops(ops, r'MoeInitRouting', limit=1)
    moe_compute_expert_tokens = _find_ops(ops, r'MoeComputeExpertTokens', limit=1)
    grouped_matmul = _find_ops(ops, r'GroupedMatmul', limit=1)

    has_moe = bool(moe_gating or moe_init_routing or grouped_matmul)

    if not has_moe:
        # No MoE in trace, ep claim is N/A or should be absent
        if claimed_ep not in (None, 'unknown', 1):
            issues.append(Issue(
                'MP1', 'warning', 'trace_scope.ep',
                f'trace 无 MoE 算子，但 ep 声明为 {claimed_ep}（应为 1 或 unknown）'
            ).to_dict())
        return issues, {'has_moe': False}

    # --- Extract shape evidence ---
    num_experts = None
    experts_per_rank = None
    experts_per_rank_sources = []

    # Router projection output dimension = num_experts (global)
    # Look for MatMul in early ops (before layer repeat) with output ~128 or so
    for op in ops[:100]:  # first 100 ops should cover embedding + first layer
        if 'MatMul' in op.get('normalized_name', ''):
            out_shape = _parse_shape(op.get('output_shapes', ''))
            # Router typically: [batch, hidden] x [hidden, num_experts] -> [batch, num_experts]
            # We're looking for output [1, N] or [T, N] where N > hidden_size
            if len(out_shape) >= 2 and out_shape[-1] >= 64:
                # Heuristic: num_experts is typically 64-256 for MoE models
                # and appears as the last dim of router projection output
                # Check if this is followed by MoeGatingTopK (confirms router)
                next_idx = ops.index(op) + 1
                if next_idx < len(ops) and 'MoeGating' in ops[next_idx].get('normalized_name', ''):
                    num_experts = out_shape[-1]
                    break

    # The gating kernel consumes one score per global expert. This is stronger than
    # relying on adjacency to the router MatMul because fused norms or casts may sit
    # between the projection and MoeGatingTopK in the profiler stream.
    if num_experts is None and moe_gating:
        gating_input = _parse_shape(moe_gating[0].get('input_shapes', ''))
        if len(gating_input) >= 2 and gating_input[-1] > 1:
            num_experts = gating_input[-1]

    # MoeComputeExpertTokens output length = experts_per_rank (local)
    if moe_compute_expert_tokens:
        op = moe_compute_expert_tokens[0]
        out_shape = _parse_shape(op.get('output_shapes', ''))
        if out_shape:
            experts_per_rank = out_shape[-1]
            experts_per_rank_sources.append(f'MoeComputeExpertTokens output={experts_per_rank}')

    # GroupedMatmul weight first dimension = experts_per_rank
    if grouped_matmul:
        op = grouped_matmul[0]
        input_shapes = _parse_shapes(op.get('input_shapes', ''))
        # The activation is commonly the first input ([tokens, hidden]). Only a plain rank-3
        # expert weight has experts_per_rank in dimension 0. Higher-rank NZ/fractal layouts
        # expose tiling dimensions (often 16) there, not an expert count.
        rank3_inputs = [shape for shape in input_shapes if len(shape) == 3]
        has_packed_weight = any(len(shape) >= 4 for shape in input_shapes)
        if has_packed_weight:
            weight_shape = None
        elif len(rank3_inputs) > 1 and input_shapes and len(input_shapes[0]) == 3:
            weight_shape = rank3_inputs[1]
        else:
            weight_shape = rank3_inputs[0] if rank3_inputs else None
        if weight_shape:
            gmm_experts = weight_shape[0]
            if experts_per_rank is None:
                experts_per_rank = gmm_experts
                experts_per_rank_sources.append(f'GroupedMatmul weight[0]={gmm_experts}')
            elif gmm_experts != experts_per_rank:
                issues.append(Issue(
                    'MP3', 'error', 'trace_scope.ep',
                    f'experts_per_rank 不一致: MoeComputeExpertTokens={experts_per_rank}, '
                    f'GroupedMatmul weight[0]={gmm_experts}'
                ).to_dict())

    # --- Derive ep_size ---
    derived_ep = None
    if num_experts and experts_per_rank:
        if num_experts % experts_per_rank != 0:
            issues.append(Issue(
                'MP3', 'error', 'trace_scope.ep',
                f'num_experts={num_experts} 不能被 experts_per_rank={experts_per_rank} 整除'
            ).to_dict())
        else:
            derived_ep = num_experts // experts_per_rank

    # MP1: compare derived vs claimed
    positive_ep_evidence = (
        isinstance(claimed_ep, int)
        and any(re.search(
            rf'\bep\s*=\s*{claimed_ep}\s+from\s+(?:yaml key|source)\b',
            str(item), re.IGNORECASE) for item in evidence))
    if derived_ep is not None:
        if claimed_ep is None or claimed_ep == 'unknown':
            issues.append(_with_ep_repair_policy(Issue(
                'MP1', 'warning', 'trace_scope.ep',
                f'trace 形状推导 ep={derived_ep} (num_experts={num_experts} ÷ '
                f'experts_per_rank={experts_per_rank})，但 trace_scope.ep 未声明'
            ).to_dict()))
        elif claimed_ep != derived_ep:
            issues.append(_with_ep_repair_policy(Issue(
                'MP1', 'error', 'trace_scope.ep',
                f'trace_scope.ep={claimed_ep} 与形状推导 ep={derived_ep} 不符 '
                f'(num_experts={num_experts} ÷ experts_per_rank={experts_per_rank})'
            ).to_dict()))
    elif has_moe:
        message = (
            f'trace 有 MoE 算子但无法从形状推导 ep_size（num_experts={num_experts}, '
            f'experts_per_rank={experts_per_rank}）')
        if claimed_ep in (None, 'unknown'):
            issues.append(Issue(
                'MP1', 'info', 'trace_scope.ep',
                f'{message}；保持 unknown，不据此推断并行度'
            ).to_dict())
        elif not positive_ep_evidence:
            issues.append(_with_ep_repair_policy(Issue(
                'MP1', 'warning', 'trace_scope.ep',
                f'{message}，且没有与声明值匹配的正向 runtime/source 证据'
            ).to_dict()))

    # MP2: check for "absence of X ->" style evidence
    for ev in evidence:
        ev_lower = ev.lower()
        # Pattern: "no X" / "absence of" / "without" followed by "→" or "->"
        if any(pattern in ev_lower for pattern in ['no ', 'absence of', 'without']):
            if '→' in ev or '->' in ev:
                issues.append(Issue(
                    'MP2', 'warning', 'trace_scope.evidence',
                    f'证据使用 "absence of X ->" 式间接推断，应改用正向形状证据: {ev[:100]}'
                ).to_dict())

    errors = [i for i in issues if i.get('severity') == 'error']
    warnings = [i for i in issues if i.get('severity') == 'warning']

    return issues, {
        'has_moe': has_moe,
        'num_experts': num_experts,
        'experts_per_rank': experts_per_rank,
        'experts_per_rank_sources': experts_per_rank_sources,
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
        print(f'MoE parallelism check 已写入: {args.output}  '
              f'errors={detail["error_count"]} warnings={detail["warning_count"]}')
    else:
        print(text)


if __name__ == '__main__':
    main()
