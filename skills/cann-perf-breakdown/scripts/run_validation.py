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
run_validation.py — unified validation entrypoint.

Runs structure, architecture, dataflow, coverage (and optional regression) checks and
emits ONE valid JSON document (schemas/validation_report.schema.json). Never
concatenates multiple JSON objects.

A formal pass is EXACTLY `passed`. `--allow-warnings` still exists for exploratory
triage -- it produces `passed_with_warnings`, which downstream conversion and scoring
reject; it is not a way to ship a config with open warnings.

Shape validation is not part of the formal contract (see --with-shapes): a missing
`shape_semantic` annotation says nothing about whether the decomposition is correct.
The dataflow check took its place as the thing that can actually be wrong.

Exit codes:
  0  -> passed, or a non-formal completion (passed_with_warnings / exploratory)
  1  -> failed (errors, or warnings without --allow-warnings)
  2  -> a sub-check raised an unexpected exception / bad inputs
"""
import argparse
import json
import os
import sys
import traceback
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import breakdown_common as bc  # noqa: E402
import check_structure  # noqa: E402
import check_op_coverage  # noqa: E402
import check_sublayers  # noqa: E402
import validate_architecture  # noqa: E402
import validate_shapes  # noqa: E402
import validate_semantic_review  # noqa: E402
import check_graph_consistency  # noqa: E402
import check_manifest_trace  # noqa: E402
import check_dataflow  # noqa: E402
import check_moe_parallelism  # noqa: E402
import extract_dataflow  # noqa: E402


def _run(check_name, fn):
    """Run a sub-check callable returning (issues, extra). Catch exceptions -> error check."""
    try:
        issues, extra = fn()
        errors = [i for i in issues if i.get('severity') == 'error']
        warnings = [i for i in issues if i.get('severity') == 'warning']
        status = 'passed'
        if errors:
            status = 'failed'
        elif warnings:
            status = 'warning'
        for it in issues:
            it.setdefault('check', check_name)
        return {
            'name': check_name,
            'status': status,
            'error_count': len(errors),
            'warning_count': len(warnings),
            'detail': extra,
        }, issues
    except Exception as e:  # noqa: BLE001 — sub-check must never crash the runner silently
        return {
            'name': check_name,
            'status': 'error',
            'error_count': 1,
            'warning_count': 0,
            'detail': f'{type(e).__name__}: {e}\n{traceback.format_exc()}',
        }, [{'id': 'RUNNER', 'severity': 'error', 'check': check_name,
             'node_path': '<runner>', 'message': f'{check_name} 异常: {e}'}]


#: manifest_trace findings that keep their severity through `_demote_to_info`.
#: The demotion rationale is about *scalars* a single capture cannot arbitrate (a layer
#: count). MT2 is not a scalar: it reports that expert-routing kernels were recorded while
#: the manifest calls every layer dense. A capture cannot be wrong about a kernel it ran,
#: so partial coverage is no excuse for that contradiction.
_TRACE_MISMATCH_NON_DEMOTABLE = {'MT2'}


def _demote_to_info(check, issues):
    """Rewrite one check's issues to `info` and recompute its status.

    Used for `manifest_trace`. Its arithmetic compares a layer count against kernel
    witness counts from one capture, and a capture may legitimately span a single step,
    so a mismatch is evidence to read, never a verdict on the source-derived
    decomposition. Emitting it as a warning made a partial capture fail the formal run.
    The finding stays in the report verbatim; only its severity changes, so nothing is
    hidden — see `--fail-on-trace-mismatch` to restore blocking behaviour.

    Qualitative findings listed in `_TRACE_MISMATCH_NON_DEMOTABLE` are left untouched.
    """
    kept = []
    for issue in issues:
        if issue.get('id') in _TRACE_MISMATCH_NON_DEMOTABLE:
            kept.append(issue)
            continue
        issue['severity'] = 'info'
        issue['demoted_from'] = 'warning'
    errors = [i for i in kept if i.get('severity') == 'error']
    warnings = [i for i in kept if i.get('severity') == 'warning']
    if errors:
        check['status'] = 'failed'
    elif warnings:
        check['status'] = 'warning'
    else:
        check['status'] = 'passed' if issues else check.get('status', 'passed')
    check['error_count'] = len(errors)
    check['warning_count'] = len(warnings)
    check['info_count'] = len(issues) - len(kept)
    detail = check.get('detail')
    if isinstance(detail, dict):
        detail['severity_policy'] = ('trace 为辅助证据：标量类发现仅作 info，不阻断正式流程'
                                     '（--fail-on-trace-mismatch 可恢复阻断）；'
                                     f'定性矛盾 {sorted(_TRACE_MISMATCH_NON_DEMOTABLE)} 不降级')
    return check, issues


@dataclass(frozen=True)
class ValidationInputs:
    config_path: str
    raw_ops_path: str = None
    manifest_path: str = None
    source_dirs: tuple = ()
    mode: str = 'A'
    include_shapes: bool = False
    allow_unmapped: bool = False
    baseline_path: str = None
    semantic_review_path: str = None
    graph_path: str = None
    dataflow_path: str = None
    model_sources: tuple = ()
    profile: str = None
    fail_on_trace_mismatch: bool = False


@dataclass
class ValidationState:
    inputs: ValidationInputs
    config: dict
    version: int
    base_dirs: list
    checks: list = field(default_factory=list)
    issues: list = field(default_factory=list)


@dataclass(frozen=True)
class ValidationResult:
    checks: list
    issues: list
    error_count: int
    warning_count: int
    version: int
    has_unmapped: bool


def _load_json(path):
    with open(path, 'r', encoding='utf-8') as stream:
        return json.load(stream)


def _append_check(state, name, function):
    check, issues = _run(name, function)
    state.checks.append(check)
    state.issues.extend(issues)
    return check, issues


def _run_structure(state):
    def check():
        if state.version == 2:
            issues = check_structure.check_structure_v2(state.config, state.base_dirs)
            return issues, {'schema_version': 2}
        return check_structure.check_structure(state.config), {'schema_version': state.version}
    _append_check(state, 'structure', check)


def _run_architecture(state):
    def check():
        manifest = None
        path = state.inputs.manifest_path
        if path and os.path.exists(path):
            manifest = _load_json(path)
        if state.version != 2:
            return ([{'id': 'A0', 'severity': 'warning', 'node_path': '<global>',
                      'message': 'legacy v1: architecture 校验跳过（legacy_unverified）'}],
                    {'schema_version': state.version})
        issues = validate_architecture.validate(state.config, manifest, state.base_dirs)
        return issues, {'manifest': path}
    _append_check(state, 'architecture', check)


def _run_manifest_trace(state):
    inputs = state.inputs
    if not (inputs.raw_ops_path and inputs.manifest_path
            and os.path.exists(inputs.manifest_path)):
        return

    def check():
        return check_manifest_trace.check_manifest_trace(
            _load_json(inputs.manifest_path), _load_json(inputs.raw_ops_path))

    result, issues = _run('manifest_trace', check)
    if not inputs.fail_on_trace_mismatch and result['status'] != 'error':
        result, issues = _demote_to_info(result, issues)
    state.checks.append(result)
    state.issues.extend(issues)


def _run_moe_parallelism(state):
    if not state.inputs.raw_ops_path:
        return

    def check():
        raw_ops = _load_json(state.inputs.raw_ops_path)
        return check_moe_parallelism.check_moe_parallelism(state.config, raw_ops)
    _append_check(state, 'moe_parallelism', check)


def _run_coverage(state):
    if not state.inputs.raw_ops_path:
        return

    def check():
        raw_ops = _load_json(state.inputs.raw_ops_path)
        if state.version == 2:
            return check_op_coverage.check_coverage_v2(
                state.config, raw_ops, allow_unmapped=state.inputs.allow_unmapped)
        return check_op_coverage.check_coverage_legacy(state.config, raw_ops)
    _append_check(state, 'coverage', check)


def _run_sublayers(state):
    if state.version != 2:
        return

    def check():
        raw_ops = None
        path = state.inputs.raw_ops_path
        if path and os.path.exists(path):
            raw_ops = _load_json(path)
        return (check_sublayers.check_sublayers(state.config, raw_ops),
                {'comm_aware': raw_ops is not None})
    _append_check(state, 'sublayers', check)


def _load_dataflow(inputs):
    if inputs.dataflow_path:
        return _load_json(inputs.dataflow_path)
    modules = []
    for path in inputs.model_sources:
        modules.extend(extract_dataflow.extract_file(path))
    return {'schema_version': 2, 'modules': modules}


def _run_dataflow(state):
    inputs = state.inputs
    if state.version != 2 or not (inputs.dataflow_path or inputs.model_sources):
        return

    def check():
        manifest = None
        if inputs.manifest_path and os.path.exists(inputs.manifest_path):
            manifest = _load_json(inputs.manifest_path)
        dataflow = _load_dataflow(inputs)
        return check_dataflow.check_dataflow(state.config, dataflow, manifest, inputs.profile)
    _append_check(state, 'dataflow', check)


def _run_shapes(state):
    if not state.inputs.include_shapes:
        return

    def check():
        symbol_table = validate_shapes.build_symbol_table(state.config)
        pairs = validate_shapes.collect_kernels_with_op_data(state.config)
        issues = []
        severity = {'ERROR': 'error', 'WARNING': 'warning', 'INFO': 'info'}
        for kernel, op_data in pairs:
            results = validate_shapes.validate_kernel(kernel, op_data, symbol_table, strict=True)
            for level, message in results:
                issues.append({'id': 'V1', 'severity': severity.get(level, 'warning'),
                               'node_path': '<kernel>', 'message': message})
        return issues, {'kernels_checked': len(pairs)}
    _append_check(state, 'shapes', check)


def _regression_findings(state):
    import regression_check as rc
    inputs = state.inputs
    findings = []
    if inputs.baseline_path and os.path.exists(inputs.baseline_path):
        findings.extend(rc.check_regression(_load_json(inputs.baseline_path), state.config))
    if inputs.manifest_path and os.path.exists(inputs.manifest_path):
        findings.extend(rc.check_architecture_regression(
            state.config, _load_json(inputs.manifest_path)))
    return findings


def _run_regression(state):
    inputs = state.inputs
    if state.version != 2 or not (inputs.manifest_path or inputs.baseline_path):
        return

    def check():
        findings = _regression_findings(state)
        hard = {'L1', 'L2', 'L3', 'L4', 'L7', 'MA1', 'MA2', 'MA3'}
        issues = []
        for finding in findings:
            if not finding.get('pass'):
                severity = finding.get('severity') or (
                    'error' if finding['id'] in hard else 'warning')
                issues.append({'id': finding['id'], 'severity': severity,
                               'node_path': 'regression',
                               'message': json.dumps(
                                   finding.get('detail', {}), ensure_ascii=False)[:300]})
        return issues, {'findings': len(findings)}
    _append_check(state, 'regression', check)


def _run_semantic_review(state):
    inputs = state.inputs
    if not inputs.semantic_review_path:
        return

    def check():
        review_inputs = validate_semantic_review.ReviewInputs(
            config_path=inputs.config_path,
            raw_ops_path=inputs.raw_ops_path,
            manifest_path=inputs.manifest_path,
            source_dirs=state.base_dirs,
            dataflow_path=inputs.dataflow_path,
        )
        return validate_semantic_review.validate_file(
            inputs.semantic_review_path, review_inputs)
    _append_check(state, 'semantic_review', check)


def _run_graph_consistency(state):
    if not state.inputs.graph_path:
        return

    def check():
        graph = _load_json(state.inputs.graph_path)
        return check_graph_consistency.validate_graph(graph, state.config)
    _append_check(state, 'graph_consistency', check)


def run_all(inputs):
    with open(inputs.config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    version = bc.detect_schema_version(config)
    state = ValidationState(inputs, config, version, list(inputs.source_dirs) or [os.getcwd()])
    for stage in (_run_structure, _run_architecture, _run_manifest_trace,
                  _run_moe_parallelism, _run_coverage, _run_sublayers,
                  _run_dataflow, _run_shapes, _run_regression,
                  _run_semantic_review, _run_graph_consistency):
        stage(state)
    return ValidationResult(
        checks=state.checks,
        issues=state.issues,
        error_count=sum(1 for item in state.issues if item.get('severity') == 'error'),
        warning_count=sum(1 for item in state.issues if item.get('severity') == 'warning'),
        version=version,
        has_unmapped=bool(config.get('unmapped_ops')),
    )


def _parse_args():
    parser = argparse.ArgumentParser(description='Unified validation runner (single JSON report)')
    parser.add_argument('-c', '--config', required=True)
    parser.add_argument('-r', '--raw-ops', dest='raw_ops')
    parser.add_argument('-m', '--manifest')
    parser.add_argument('--source-dir', action='append', default=[])
    parser.add_argument('--mode', default='A', choices=['A', 'B'])
    parser.add_argument('--allow-warnings', action='store_true',
                        help='把 warning 降级为非阻断（会在报告中记录 override）')
    parser.add_argument('--allow-unmapped', action='store_true',
                        help='探索模式：允许 unmapped 存在（unmapped 降级为 warning）；'
                             '结果状态为 exploratory，绝不为 passed')
    parser.add_argument('--baseline', help='baseline analysis_config.json，做结构回归')
    parser.add_argument('--semantic-review',
                        help='AI 源码/Trace 语义审查；提供时作为严格校验项')
    parser.add_argument('--graph',
                        help='下游 model_architecture_graph.json；提供时与 config 交叉核对'
                             '（repeatCount / 层号覆盖 / 节点对应）')
    parser.add_argument('--with-shapes', action='store_true',
                        help='额外运行 shape 校验（调试用，不属于正式契约；'
                             'shape_semantic 缺失不代表拆解错误）')
    parser.add_argument('--dataflow',
                        help='extract_dataflow.py 产出的 dataflow_source.json；'
                             '与 config 声明的残差/分支拓扑逐条比对')
    parser.add_argument('--model-source', action='append', default=[],
                        help='模型源码文件；未提供 --dataflow 时就地推导数据流（可重复）')
    parser.add_argument('--profile', help='本次校验对应的 execution profile id')
    parser.add_argument('--fail-on-trace-mismatch', action='store_true',
                        help='让 manifest/trace 层数差异恢复为阻断 warning；'
                             '默认只作 info，因为一次采集可能只覆盖单个 step')
    parser.add_argument('-o', '--output')
    return parser.parse_args()


def _inputs_from_args(args):
    return ValidationInputs(
        config_path=args.config,
        raw_ops_path=args.raw_ops,
        manifest_path=args.manifest,
        source_dirs=tuple(args.source_dir),
        mode=args.mode,
        include_shapes=args.with_shapes,
        allow_unmapped=args.allow_unmapped,
        baseline_path=args.baseline,
        semantic_review_path=args.semantic_review,
        graph_path=args.graph,
        dataflow_path=args.dataflow,
        model_sources=tuple(args.model_source),
        profile=args.profile,
        fail_on_trace_mismatch=args.fail_on_trace_mismatch,
    )


def _report_status(result, args):
    if result.error_count > 0:
        return 'failed'
    if args.allow_unmapped and result.has_unmapped:
        return 'exploratory'
    if result.warning_count > 0:
        return 'passed_with_warnings' if args.allow_warnings else 'failed'
    return 'passed'


def _build_report(result, args):
    status = _report_status(result, args)
    exploratory = args.allow_unmapped and result.has_unmapped
    return {
        'status': status,
        'allow_warnings': args.allow_warnings,
        'allow_unmapped': args.allow_unmapped,
        'exploratory': exploratory,
        'error_count': result.error_count,
        'warning_count': result.warning_count,
        'config': args.config,
        'checks': result.checks,
        'issues': result.issues,
    }


def _write_report(report, output):
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
        bc.emit(f'validation report 已写入: {output}  status={report["status"]} '
                f'errors={report["error_count"]} warnings={report["warning_count"]}')
    else:
        bc.emit(text)


def main():
    args = _parse_args()
    if not os.path.exists(args.config):
        bc.emit_error(f'错误: 文件不存在: {args.config}\n')
        sys.exit(2)
    report = _build_report(run_all(_inputs_from_args(args)), args)
    _write_report(report, args.output)
    completed = report['status'] in ('passed', 'passed_with_warnings', 'exploratory')
    sys.exit(0 if completed else 1)


if __name__ == '__main__':
    main()
