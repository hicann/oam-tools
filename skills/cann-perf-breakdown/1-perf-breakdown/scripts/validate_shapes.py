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
validate_shapes.py — 检查 analysis_config.json 中 shape_semantic 与实际 tensor shape 的一致性。

使用方式：
  python scripts/validate_shapes.py -c outputs/analysis_config.json
  python scripts/validate_shapes.py -c outputs/analysis_config.json --strict   # ERROR 也报 WARNING
"""

import json
import re
import sys
import argparse
from pathlib import Path


# ---------------------------------------------------------------------------
# Symbol table: 从 config 字段映射到数值
# ---------------------------------------------------------------------------
SYMBOL_MAP = {
    'hidden':        'hidden_size',
    'ffn':           'intermediate_size',
    'moe_ffn':       'moe_intermediate_size',
    'H_q':           'num_attention_heads',
    'H':             'num_attention_heads',
    'num_heads':     'num_attention_heads',
    'D_rope':        'qk_rope_head_dim',
    'D_nope':        'qk_nope_head_dim',
    'D':             'v_head_dim',
    'v_head_dim':    'v_head_dim',
    'q_rank':        'q_lora_rank',
    'kv_rank':       'kv_lora_rank',
    'E':             'n_routed_experts',
    'topK':          'num_experts_per_tok',
    'vocab':         'vocab_size',
    'H_idx':         'index_n_heads',
    'D_idx':         'index_head_dim',
    'index_topk':    'index_topk',
    'H_k':           'num_key_value_heads',
}


def build_symbol_table(config: dict) -> dict:
    # v2 stores config facts under architecture.facts or a top-level "config" block;
    # keep supporting the legacy top-level "config" dict.
    cfg = config.get('config', {})
    if not cfg:
        # try v2 architecture.facts (list of {key,value}) as a fallback source
        facts = (config.get('architecture') or {}).get('facts')
        if isinstance(facts, list):
            cfg = {f.get('key'): f.get('value') for f in facts if isinstance(f, dict)}
    table = {}
    for sym, field in SYMBOL_MAP.items():
        v = cfg.get(field)
        if isinstance(v, bool):
            continue
        if isinstance(v, int):
            table[sym] = v
        elif isinstance(v, str) and v.isdigit():
            table[sym] = int(v)
    return table


# ---------------------------------------------------------------------------
# Shape parsing helpers
# ---------------------------------------------------------------------------

def parse_shapes(shape_str: str) -> list[list[int]]:
    """Parse semicolon-separated shape string into list of dim lists.
    E.g. "4,7168;96,448,16,16" → [[4,7168],[96,448,16,16]]
    """
    if not shape_str or str(shape_str).upper() == 'N/A':
        return []
    result = []
    for part in str(shape_str).split(';'):
        part = part.strip().strip('"')
        if not part:
            continue
        try:
            dims = [int(x) for x in part.split(',') if x.strip()]
            if dims:
                result.append(dims)
        except ValueError:
            pass
    return result


def all_dims_set(shapes: list[list[int]]) -> set[int]:
    """Flat set of all dimension values across all tensors."""
    s = set()
    for dims in shapes:
        s.update(dims)
    return s


# ---------------------------------------------------------------------------
# shape_semantic extraction
# ---------------------------------------------------------------------------

def extract_bracket_tokens(shape_sem: str) -> list[str]:
    """Extract token strings from [...] brackets in shape_semantic."""
    tokens = []
    for m in re.finditer(r'\[([^\]]+)\]', shape_sem):
        for tok in m.group(1).split(','):
            tokens.append(tok.strip())
    return tokens


def extract_explicit_values(shape_sem: str) -> dict[str, int]:
    """Extract 'sym=N' patterns from inside [...] brackets only.
    Patterns outside brackets (e.g. parallelism annotations like "EP=64 ranks") are ignored.
    """
    result = {}
    for bracket_m in re.finditer(r'\[([^\]]+)\]', shape_sem):
        inner = bracket_m.group(1)
        for m in re.finditer(r'([A-Za-z_][A-Za-z0-9_*]*)=(\d+)', inner):
            sym, val = m.group(1), int(m.group(2))
            result[sym] = val
    return result


def extract_literal_dims(shape_sem: str) -> list[int]:
    """Extract standalone numeric literals inside [...] dimension brackets.
    Skips 1 (trivial broadcast scalar) and 2 (trivial pairing).
    """
    TRIVIAL = {1, 2}
    nums = []
    for m in re.finditer(r'\[([^\]]+)\]', shape_sem):
        for tok in m.group(1).split(','):
            tok = tok.strip()
            if re.fullmatch(r'\d+', tok):
                n = int(tok)
                if n not in TRIVIAL:
                    nums.append(n)
    return nums


# ---------------------------------------------------------------------------
# Per-kernel validation
# ---------------------------------------------------------------------------

def validate_kernel(kernel: dict, op_data: dict, symbol_table: dict, strict: bool) -> list[tuple]:
    """Return list of (level, message) issues for one kernel."""
    issues = []
    shape_sem = kernel.get('shape_semantic', '')
    if not shape_sem:
        return issues

    idx   = kernel.get('index', '?')
    name  = op_data.get('name') or kernel.get('name', '?')

    in_shapes  = parse_shapes(op_data.get('input_shapes', ''))
    out_shapes = parse_shapes(op_data.get('output_shapes', ''))
    in_dims    = all_dims_set(in_shapes)
    out_dims   = all_dims_set(out_shapes)
    all_dims   = in_dims | out_dims

    # Distinguish "profiler has no shape info" (absent) from "shape contradicts".
    # If both input and output shapes are absent, we cannot verify literal presence;
    # emit an INFO-level note instead of a spurious contradiction WARNING.
    shapes_absent = (not in_dims) and (not out_dims)

    # 1. Named value cross-check: sym=N in shape_semantic vs config
    explicit = extract_explicit_values(shape_sem)
    for sym, val in explicit.items():
        expected = symbol_table.get(sym)
        if expected is not None and expected != val:
            issues.append(('ERROR',
                f'[{idx}] {name}: shape_semantic 写 {sym}={val}，但 config 中 {sym}={expected}'))
        # Named value should appear somewhere in actual dims
        if shapes_absent:
            issues.append(('INFO',
                f'[{idx}] {name}: profiler 无 shape 信息，无法核对 {sym}={val}（absent，非矛盾）'))
        elif val not in all_dims:
            issues.append(('WARNING',
                f'[{idx}] {name}: shape_semantic 中 {sym}={val} 不出现在实际 tensor dims {sorted(all_dims)} '
                f'(in={op_data.get("input_shapes","")[:50]}, out={op_data.get("output_shapes","")[:50]})'))

    # 2. Resolve symbolic tokens, check literal dims inside [...]
    literal_dims = extract_literal_dims(shape_sem)
    if not shapes_absent:
        for num in set(literal_dims):
            if num not in all_dims:
                issues.append(('WARNING',
                    f'[{idx}] {name}: shape_semantic 中出现字面量 {num}，但不存在于实际 dims {sorted(all_dims)} '
                    f'(in={op_data.get("input_shapes","")[:50]}, out={op_data.get("output_shapes","")[:50]})'))

    # 3. Arrow-split consistency: left of → should relate to inputs, right to outputs
    arrow = '→'
    if arrow in shape_sem:
        left, right = shape_sem.split(arrow, 1)
        left_lits  = [n for n in extract_literal_dims(f'[{left}]')  if n > 1]
        right_lits = [n for n in extract_literal_dims(f'[{right}]') if n > 1]

        # Left-side literals should appear in actual input dims (input side validated
        # independently of output side).
        for num in left_lits:
            if in_dims and num not in in_dims and num not in all_dims:
                issues.append(('WARNING',
                    f'[{idx}] {name}: shape_semantic 输入侧 (→左) 包含 {num}，'
                    f'但实际输入 dims={sorted(in_dims)}'))

        # Right-side literals should appear in actual output dims
        for num in right_lits:
            if out_dims and num not in out_dims and num not in all_dims:
                issues.append(('WARNING',
                    f'[{idx}] {name}: shape_semantic 输出侧 (→右) 包含 {num}，'
                    f'但实际输出 dims={sorted(out_dims)}'))

    return issues


# ---------------------------------------------------------------------------
# Config traversal
# ---------------------------------------------------------------------------

def collect_kernels_with_op_data(config: dict) -> list[tuple]:
    """Yield (kernel_entry, op_data_dict) for all kernels that have shape_semantic."""
    pairs = []

    def visit(node: dict):
        if not isinstance(node, dict):
            return
        kernels   = node.get('kernels', [])
        op_data_list = node.get('op_data', [])
        op_data_map  = {od.get('index'): od for od in op_data_list}

        for k in kernels:
            if k.get('shape_semantic'):
                od = op_data_map.get(k.get('index'), {})
                pairs.append((k, od))

        for child in node.get('children', []):
            visit(child)

    for stage in config.get('stages', {}).values():
        visit(stage)
    for struct in config.get('layer_structure', {}).values():   # v1
        visit(struct)
    for struct in config.get('structures', {}).values():        # v2
        visit(struct)
    for aux in config.get('runtime_auxiliary', []):
        visit(aux)

    return pairs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_validation(config_path: str, strict: bool = False,
                   fail_fast: bool = False, json_out: bool = False) -> int:
    config = json.loads(Path(config_path).read_text())
    symbol_table = build_symbol_table(config)

    if not json_out:
        print(f'模型: {config.get("model_name", "?")}')
        print(f'符号表: {symbol_table}')
        print()

    pairs = collect_kernels_with_op_data(config)
    if not pairs:
        msg = '未找到带 shape_semantic 的 kernel（是否已运行 --enrich？）'
        if json_out:
            print(json.dumps({
                'script': 'validate_shapes.py',
                'config': config_path,
                'error_count': 1,
                'issues': [{'id': 'V0', 'severity': 'error', 'node_path': '<global>', 'message': msg}],
            }, ensure_ascii=False, indent=2))
        else:
            print(msg)
        return 1

    all_issues = []
    for kernel, op_data in pairs:
        issues = validate_kernel(kernel, op_data, symbol_table, strict)
        all_issues.extend(issues)
        if fail_fast and any(l == 'ERROR' for l, _ in issues):
            break

    errors   = [(l, m) for l, m in all_issues if l == 'ERROR']
    warnings = [(l, m) for l, m in all_issues if l == 'WARNING']
    infos    = [(l, m) for l, m in all_issues if l == 'INFO']

    # In --strict mode a WARNING is promoted to a failure exit code.
    def exit_code():
        if errors:
            return 1
        if strict and warnings:
            return 1
        return 0

    sev_map = {'ERROR': 'error', 'WARNING': 'warning', 'INFO': 'info'}

    if json_out:
        formatted_issues = []
        for level, msg in all_issues:
            formatted_issues.append({
                'id': 'V1',
                'severity': sev_map.get(level, 'warning'),
                'node_path': '<kernel>',  # 详情包含在 message 中
                'message': msg,
            })
        print(json.dumps({
            'script': 'validate_shapes.py',
            'config': config_path,
            'kernels_checked': len(pairs),
            'strict': strict,
            'error_count': len(errors),
            'warning_count': len(warnings),
            'info_count': len(infos),
            'fail_fast': fail_fast,
            'issues': formatted_issues,
        }, ensure_ascii=False, indent=2))
        return exit_code()

    if not all_issues:
        print(f'✓ 全部 {len(pairs)} 个 shape_semantic 校验通过，无问题。')
        return 0

    if errors:
        print(f'=== ERROR ({len(errors)}) ===')
        for _, m in errors:
            print(f'  [ERROR] {m}')
        print()

    if warnings:
        label = 'ERROR(strict)' if strict else 'WARN'
        print(f'=== WARNING ({len(warnings)}){" [strict→fail]" if strict else ""} ===')
        for _, m in warnings:
            print(f'  [{label}]  {m}')
        print()

    if infos:
        print(f'=== INFO ({len(infos)}) ===')
        for _, m in infos:
            print(f'  [INFO]  {m}')
        print()

    print(f'共检查 {len(pairs)} 个 kernel，{len(errors)} 个 ERROR，{len(warnings)} 个 WARNING，{len(infos)} 个 INFO。'
          + (' (strict)' if strict else '') + (' (fail-fast)' if fail_fast else ''))
    return exit_code()


def main():
    parser = argparse.ArgumentParser(description='校验 analysis_config.json 中 shape_semantic 的一致性')
    parser.add_argument('-c', '--config', required=True, help='analysis_config.json 路径')
    parser.add_argument('--strict', action='store_true', help='把 WARNING 也视为失败')
    parser.add_argument('--fail-fast', action='store_true', dest='fail_fast',
                        help='遇到首个 ERROR 即退出')
    parser.add_argument('--json', action='store_true', dest='json_out',
                        help='以 JSON 输出结果（与 check_structure / check_op_coverage 一致）')
    args = parser.parse_args()
    sys.exit(run_validation(args.config, strict=args.strict,
                            fail_fast=args.fail_fast, json_out=args.json_out))


if __name__ == '__main__':
    main()
