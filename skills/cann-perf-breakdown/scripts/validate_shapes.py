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

SCRIPT_DIR = str(Path(__file__).resolve().parent)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import breakdown_common as bc  # noqa: E402


# ---------------------------------------------------------------------------
# Symbol table: 从 config 字段映射到数值
# ---------------------------------------------------------------------------
SYMBOL_MAP = {
    'hidden': 'hidden_size',
    'ffn': 'intermediate_size',
    'moe_ffn': 'moe_intermediate_size',
    'H_q': 'num_attention_heads',
    'H': 'num_attention_heads',
    'num_heads': 'num_attention_heads',
    'D_rope': 'qk_rope_head_dim',
    'D_nope': 'qk_nope_head_dim',
    'D': 'v_head_dim',
    'v_head_dim': 'v_head_dim',
    'q_rank': 'q_lora_rank',
    'kv_rank': 'kv_lora_rank',
    'E': 'n_routed_experts',
    'topK': 'num_experts_per_tok',
    'vocab': 'vocab_size',
    'H_idx': 'index_n_heads',
    'D_idx': 'index_head_dim',
    'index_topk': 'index_topk',
    'H_k': 'num_key_value_heads',
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


def _append_literal_dims(result, dimension_group, trivial):
    for raw_token in dimension_group.split(','):
        token = raw_token.strip()
        if not re.fullmatch(r'\d+', token):
            continue
        value = int(token)
        if value not in trivial:
            result.append(value)


def extract_literal_dims(shape_sem: str) -> list[int]:
    """Extract nontrivial standalone numeric literals from dimension brackets."""
    result = []
    for match in re.finditer(r'\[([^\]]+)\]', shape_sem):
        _append_literal_dims(result, match.group(1), {1, 2})
    return result


# ---------------------------------------------------------------------------
# Per-kernel validation
# ---------------------------------------------------------------------------

def validate_kernel(kernel: dict, op_data: dict, symbol_table: dict, strict: bool) -> list[tuple]:
    """Return list of (level, message) issues for one kernel."""
    issues = []
    shape_sem = kernel.get('shape_semantic', '')
    if not shape_sem:
        return issues

    idx = kernel.get('index', '?')
    name = op_data.get('name') or kernel.get('name', '?')

    in_shapes = parse_shapes(op_data.get('input_shapes', ''))
    out_shapes = parse_shapes(op_data.get('output_shapes', ''))
    in_dims = all_dims_set(in_shapes)
    out_dims = all_dims_set(out_shapes)
    all_dims = in_dims | out_dims

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
        left_lits = [n for n in extract_literal_dims(f'[{left}]') if n > 1]
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
        kernels = node.get('kernels', [])
        op_data_list = node.get('op_data', [])
        op_data_map = {od.get('index'): od for od in op_data_list}

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

def _validate_shape_pairs(pairs, symbol_table, strict, fail_fast):
    all_issues = []
    for kernel, op_data in pairs:
        issues = validate_kernel(kernel, op_data, symbol_table, strict)
        all_issues.extend(issues)
        if fail_fast and any(l == 'ERROR' for l, _ in issues):
            break
    return all_issues


def _group_shape_issues(all_issues):
    errors = [(l, m) for l, m in all_issues if l == 'ERROR']
    warnings = [(l, m) for l, m in all_issues if l == 'WARNING']
    infos = [(l, m) for l, m in all_issues if l == 'INFO']
    return errors, warnings, infos


def _shape_exit_code(errors, warnings, strict):
    return 1 if errors or (strict and warnings) else 0


def _emit_shape_json(config_path, pairs, all_issues, strict, fail_fast):
    errors, warnings, infos = _group_shape_issues(all_issues)
    sev_map = {'ERROR': 'error', 'WARNING': 'warning', 'INFO': 'info'}
    formatted = [{'id': 'V1', 'severity': sev_map.get(level, 'warning'),
                  'node_path': '<kernel>', 'message': message}
                 for level, message in all_issues]
    bc.emit(json.dumps({
        'script': 'validate_shapes.py',
        'config': config_path,
        'kernels_checked': len(pairs),
        'strict': strict,
        'error_count': len(errors),
        'warning_count': len(warnings),
        'info_count': len(infos),
        'fail_fast': fail_fast,
        'issues': formatted,
    }, ensure_ascii=False, indent=2))
    return _shape_exit_code(errors, warnings, strict)


def _emit_shape_text(pairs, all_issues, strict, fail_fast):
    if not all_issues:
        bc.emit(f'✓ 全部 {len(pairs)} 个 shape_semantic 校验通过，无问题。')
        return 0
    errors, warnings, infos = _group_shape_issues(all_issues)
    if errors:
        bc.emit(f'=== ERROR ({len(errors)}) ===')
        for _, m in errors:
            bc.emit(f'  [ERROR] {m}')
        bc.emit()

    if warnings:
        label = 'ERROR(strict)' if strict else 'WARN'
        bc.emit(f'=== WARNING ({len(warnings)}){" [strict→fail]" if strict else ""} ===')
        for _, m in warnings:
            bc.emit(f'  [{label}]  {m}')
        bc.emit()

    if infos:
        bc.emit(f'=== INFO ({len(infos)}) ===')
        for _, m in infos:
            bc.emit(f'  [INFO]  {m}')
        bc.emit()

    bc.emit(f'共检查 {len(pairs)} 个 kernel，{len(errors)} 个 ERROR，{len(warnings)} 个 WARNING，{len(infos)} 个 INFO。'
          + (' (strict)' if strict else '') + (' (fail-fast)' if fail_fast else ''))
    return _shape_exit_code(errors, warnings, strict)


def _emit_no_shape_pairs(config_path, json_out):
    message = '未找到带 shape_semantic 的 kernel（是否已运行 --enrich？）'
    if json_out:
        bc.emit(json.dumps({
            'script': 'validate_shapes.py',
            'config': config_path,
            'error_count': 1,
            'issues': [{'id': 'V0', 'severity': 'error',
                        'node_path': '<global>', 'message': message}],
        }, ensure_ascii=False, indent=2))
    else:
        bc.emit(message)
    return 1


def run_validation(config_path: str, strict: bool = False,
                   fail_fast: bool = False, json_out: bool = False) -> int:
    config = json.loads(Path(config_path).read_text())
    symbol_table = build_symbol_table(config)
    if not json_out:
        bc.emit(f'模型: {config.get("model_name", "?")}')
        bc.emit(f'符号表: {symbol_table}')
        bc.emit()
    pairs = collect_kernels_with_op_data(config)
    if not pairs:
        return _emit_no_shape_pairs(config_path, json_out)
    all_issues = _validate_shape_pairs(pairs, symbol_table, strict, fail_fast)
    if json_out:
        return _emit_shape_json(config_path, pairs, all_issues, strict, fail_fast)
    return _emit_shape_text(pairs, all_issues, strict, fail_fast)


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
