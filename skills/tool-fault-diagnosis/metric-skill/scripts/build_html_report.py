#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
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
# ----------------------------------------------------------------------------
"""Initialize and package the shared layered fault report as standalone HTML."""

from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import re
import shutil
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_CANDIDATES = (
    SKILL_ROOT.parent / "template",
    SKILL_ROOT / "template",
)
LOCAL_REF_RE = re.compile(
    r"(?P<prefix>\b(?:src|href)\s*=\s*['\"])(?P<path>(?!data:|https?://|#)[^'\"]+)(?P<suffix>['\"])",
    flags=re.IGNORECASE,
)
CSS_URL_RE = re.compile(
    r"(?P<prefix>\burl\(\s*['\"]?)(?P<path>(?!data:|https?://|#)[^)'\"\s]+)(?P<suffix>['\"]?\s*\))",
    flags=re.IGNORECASE,
)
REQUIRED_MARKERS = (
    'id="environment-title"',
    'id="overview-title"',
    'id="chain-title"',
    'id="map-title"',
    'id="architecture-wires"',
    'id="report-data-template"',
    "<!-- REPORT_TIMELINE_START -->",
    "<!-- REPORT_TIMELINE_END -->",
    "<!-- REPORT_ARCHITECTURE_GRAPH_START -->",
    "<!-- REPORT_ARCHITECTURE_GRAPH_END -->",
)
VISUAL_CONTRACT_MARKERS = (
    '<meta name="design-source" content="Pixso FILE_DATA">',
    '<meta name="design-light-frame" content="248:76871">',
    '<meta name="design-dark-frame" content="248:76134">',
    "font: 14px/22px var(--font-ui);",
    "min-height: 48px;",
    "grid-template-columns: repeat(2, minmax(0, 1fr));",
    "grid-template-columns: var(--timeline-width, minmax(0, 58fr)) minmax(0, 1fr);",
    ".timeline-row:last-child { padding-bottom: calc(6px + var(--timeline-balance, 0px)); }",
    "padding: 14px 14px calc(12px + var(--log-balance, 0px));",
    "function balanceEvidenceColumns() {",
    "function scheduleEvidenceBalance() {",
    '<span class="summary-label">运行场景</span>',
    '<span class="summary-label">发生问题</span>',
    '<span class="summary-label">业务影响</span>',
    "grid-template-columns: 1.25fr repeat(3, minmax(0, 1fr));",
    ".hardware-empty { min-height: 126px;",
    "border-radius: 16px;",
    ".model-layer { min-height: 0;",
    ".component-layer { min-height: 0;",
    ".hardware-layer { min-height: 0; padding: 63px 43px 31px; }",
    ".timeline { box-shadow: inset 0 1px var(--line); }",
    ".remedy-head { min-height: 32px; padding: 4px 0 7px;",
    ".left-column > .panel { min-height: 0; }",
    ".flow-stack > .node + .node { margin-top: 20px; }",
    ".connector { height: 40px;",
    ".map-panel { min-height: 0;",
    '<div class="legend"><span><i></i>调用/任务下发</span><span><i class="error-line"></i>错误上报/影响</span></div>',
    '<marker id="arrow-call"',
    '<marker id="arrow-error"',
    "const directLayerCall = kind === 'call'",
    "const useLeftRail = kind === 'call';",
    "const sourceX = useLeftRail ? source.left : source.right;",
    "const sourceAnchorX = source.cx - sourceLaneOffset;",
    "const sourceAnchorX = source.cx + sourceLaneOffset;",
    'data-report-icon="environment"',
    'data-report-icon="remedy"',
    'data-report-icon="model-layer"',
    'data-report-icon="component-layer"',
    'data-report-icon="hardware-layer"',
    'data-report-icon="device"',
    ".layer-icon { width: 16px; height: 16px; flex: 0 0 16px; object-fit: contain; }",
    ".hardware-layer-icon { filter: invert(1); }",
    'html[data-theme="dark"] .hardware-layer-icon { filter: none; }',
    "const allowedThemes = ['light', 'dark'];",
    "width: 40px;\n      height: 40px;\n      margin-bottom: 12px;",
    "box-shadow: inset 0 0 0 1.5px #f0f0f0;",
    "background: #fafafa;",
    'html[data-theme="dark"] .step-number {',
    "grid-template-columns: 48px 1fr; gap: 12px;",
    ".remedy-head > :first-child { padding-left: 0; }",
    "width: 48px;\n      height: 48px;\n      border-radius: 8px;",
    'data-report-icon="remedy-1-light"',
    'data-report-icon="remedy-2-light"',
    'data-report-icon="remedy-3-light"',
    'data-report-icon="remedy-4-light"',
    'data-report-icon="remedy-1-dark"',
    'data-report-icon="remedy-2-dark"',
    'data-report-icon="remedy-3-dark"',
    'data-report-icon="remedy-4-dark"',
    "border-left: 4px solid var(--red);\n      border-radius: 8px;",
    ".diagnosis strong { display: block; margin-bottom: 3px; color: var(--red); font-size: 14px; line-height: 22px; font-weight: 700; }",
    ".notice { margin-top: 14px; padding: 12px 14px; border-left: 4px solid var(--orange); border-radius: 8px;",
)
TITLE_LAYOUT_MARKERS = (
    ".title-wrap { flex: 0 1 auto; min-width: 0; position: relative;",
    ".title-wrap { width: 272px; height: 28px; min-width: 0; position: relative; overflow: hidden;",
)
TYPOGRAPHY_CONTRACT_MARKERS = (
    '--font-ui: Arial, "Helvetica Neue", Helvetica, "Microsoft YaHei", "PingFang SC", "HarmonyOS Sans SC", "HarmonyHeiTi", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif;',
    '--font-ui: Arial, "Microsoft YaHei", "PingFang SC", "HarmonyOS Sans SC", "HarmonyHeiTi", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif;',
    '--font-ui: "SF Pro Text", "SF Pro Display", "San Francisco", "Helvetica Neue", Helvetica, "Microsoft YaHei", "PingFang SC", "HarmonyOS Sans SC", "HarmonyHeiTi", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;',
    '--font-mono: Consolas, "DejaVu Sans Mono", monospace;',
    '--font-mono: Monaco, "SFMono-Regular", Consolas, "DejaVu Sans Mono", monospace;',
    '--font-mono: "DejaVu Sans Mono", Consolas, Monaco, monospace;',
    '--font-korean: Arial, "Malgun Gothic", "Apple SD Gothic Neo", "HarmonyOS Sans", sans-serif;',
    '--font-korean: "Helvetica Neue", Helvetica, "Apple SD Gothic Neo", "Malgun Gothic", "HarmonyOS Sans", sans-serif;',
    "font: 14px/22px var(--font-ui);",
    "font-synthesis: none;",
    "code, pre { font-family: var(--font-mono); }",
    ":lang(ko) { font-family: var(--font-korean); }",
    "font-family: var(--font-ui);",
    "font-size: 18px;\n      line-height: 26px;\n      font-weight: 700;",
    ".section-title {",
    "font-size: 18px;\n      line-height: 26px;\n      font-weight: 500;",
    ".subhead {",
    'font-family: var(--font-ui);\n      font-size: 16px;\n      line-height: 24px;\n      font-weight: 500;',
    "pre { margin: 0; color: var(--text-2); font-size: 12px; line-height: 22px; font-weight: 400;",
    ".remedy-head { min-height: 32px; padding: 4px 0 7px; color: var(--muted); font-size: 12px; line-height: 20px; font-weight: 600;",
    ".scope-detail {",
    "flex: 1 1 auto;",
    "max-width: 100%;",
    "display: -webkit-box;",
    "overflow-wrap: anywhere;",
    "-webkit-line-clamp: 2;",
    ".node-title { font-size: 14px; line-height: 22px; font-weight: 600; }",
    ".device-data { color: var(--muted); font-size: 12px; line-height: 18px;",
)
REPORT_DATA_TEMPLATE_RE = re.compile(
    r'<script\s+id="report-data-template"\s+type="application/json">(?P<data>.*?)</script>',
    flags=re.DOTALL,
)
IMAGE_TAG_RE = re.compile(r'<img\b(?P<attrs>[^>]*)>')
ICON_NAME_RE = re.compile(r'\bdata-report-icon="(?P<name>[^"]+)"')
IMAGE_SOURCE_RE = re.compile(r'\bsrc="(?P<src>[^"]+)"')
PLACEHOLDER_RE = re.compile(r"{{\s*(?P<path>[A-Za-z0-9_.-]+)\s*}}")
TIMELINE_BLOCK_RE = re.compile(
    r"<!-- REPORT_TIMELINE_START -->.*?<!-- REPORT_TIMELINE_END -->",
    flags=re.DOTALL,
)
ARCHITECTURE_BLOCK_RE = re.compile(
    r"<!-- REPORT_ARCHITECTURE_GRAPH_START -->.*?<!-- REPORT_ARCHITECTURE_GRAPH_END -->",
    flags=re.DOTALL,
)
NODE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,63}$")
LAYER_KINDS = ("model", "component", "hardware")
LAYER_PRESENTATION = {
    "model": ("model-layer", "layer-icon"),
    "component": ("component-layer", "layer-icon"),
    "hardware": ("hardware-layer", "layer-icon hardware-layer-icon"),
}
LAYER_NODE_LIMITS = {"model": 3, "component": 5}
CONFIDENCE_LEVELS = ("HIGH", "MEDIUM", "LOW", "INSUFFICIENT")
CAUSAL_STATUSES = {"root_cause", "fault_source"}
TIMELINE_TIMESTAMP_RE = re.compile(
    r"^(?:时间戳未提供|"
    r"\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:\.\d{1,6})?|"
    r"\d{4}[-/]\d{2}[-/]\d{2}[ T-]\d{2}:\d{2}:\d{2}"
    r"(?:\.\d{1,6})?(?:\.\d{1,6})?)$"
)
COMPONENT_CATALOG = frozenset({
    "Slog", "IDEDD", "SCC", "HCCL", "FMK", "CCU", "DVPP", "Runtime",
    "CCE", "HDC", "DRV", "NET", "HIXI", "DQSFW", "Dlog memory management",
    "Kernel", "Libmedia", "aicpu schedule", "ROS", "HCCP ROCE", "TEFUSION",
    "PROFILING", "Data Preprocess", "User Application", "Task Schedule", "TSDUMP",
    "AICPU", "Low Power", "tsdaemon or aicpu schedule", "FE", "MD", "MB", "ME",
    "IMU", "IMP", "Fmk", "CAMERA", "ASCENDCL", "TEEOS", "ISP", "SIS", "HSM",
    "DSS", "Process Manager Base Platform", "BBOX", "AIVECTOR", "TBE", "FV",
    "PYPTO", "TUNE", "helper", "FFTS", "OP", "UDF", "HICAID", "TSYNC", "AUDIO",
    "TPRT", "ASCENDCKERNEL", "ASYS", "ATRACE", "RTC", "SYSMONITOR", "AML",
    "ADETECT", "unknown",
})
NODE_STATUS_META = {
    "root_cause": ("已证实根因", "root-cause"),
    "fault_source": ("已证实故障源", "fault-source"),
    "direct_trigger": ("直接触发点", "direct-trigger"),
    "candidate": ("候选", "candidate"),
    "propagation": ("传播", "propagation"),
    "affected": ("受影响", "affected"),
    "first_observed": ("首报（非根因）", "first-observed"),
    "observed": ("已观察", "observed"),
    "unknown": ("未知/缺证", "unknown"),
}
NODE_STATUS_STRENGTH = {
    "root_cause": "proven",
    "fault_source": "proven",
    "direct_trigger": "proven",
    "candidate": "candidate",
    "propagation": "proven",
    "affected": "proven",
    "first_observed": "proven",
    "observed": "proven",
    "unknown": "unknown",
}
EDGE_KIND_META = {
    "root_cause": ("已证实根因链", "root-cause"),
    "call": ("调用/任务下发", "call"),
    "identity": ("已证实同一实体/任务", "identity"),
    "propagation": ("已证实传播", "propagation"),
    "candidate": ("候选关系", "candidate"),
    "unknown": ("关系未证实", "unknown"),
}
EDGE_KIND_STRENGTH = {
    "root_cause": "proven",
    "call": "proven",
    "identity": "proven",
    "propagation": "proven",
    "candidate": "candidate",
    "unknown": "unknown",
}
EDGE_VISUAL_META = {
    "call": ("调用/任务下发", "call"),
    "root_cause": ("错误上报/影响", "error"),
    "propagation": ("错误上报/影响", "error"),
}


class ReportBuildError(RuntimeError):
    pass


def find_template_dir() -> Path:
    for candidate in TEMPLATE_CANDIDATES:
        if (candidate / "index.html").is_file():
            return candidate
    searched = ", ".join(str(path) for path in TEMPLATE_CANDIDATES)
    raise ReportBuildError(f"未找到共享报告模板，已检查: {searched}")


def load_embedded_report_data(template: str, source: Path) -> dict[str, object]:
    match = REPORT_DATA_TEMPLATE_RE.search(template)
    if not match:
        raise ReportBuildError(f"空白模板缺少内嵌数据入口: {source}")
    try:
        data = json.loads(match.group("data"))
    except json.JSONDecodeError as exc:
        raise ReportBuildError(f"空白模板内嵌数据入口不是有效 JSON: {source}: {exc}") from exc
    if not isinstance(data, dict):
        raise ReportBuildError(f"空白模板内嵌数据入口必须是 JSON 对象: {source}")
    return data


def initialize_report(destination: Path, force: bool) -> None:
    if destination.exists() and not force:
        raise ReportBuildError(f"目标已存在，请更换目录或添加 --force: {destination}")
    if destination.exists() and not destination.is_dir():
        raise ReportBuildError(f"报告工作目录不是目录: {destination}")
    template = find_template_dir() / "index.html"
    template_text = template.read_text(encoding="utf-8")
    data = load_embedded_report_data(template_text, template)
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template, destination / "index.html")
    (destination / "report-data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"OK initialized editable report in {destination}")


def validate_structure(html: str, source: Path) -> None:
    missing = [marker for marker in REQUIRED_MARKERS if marker not in html]
    if missing:
        raise ReportBuildError(f"{source} 缺少必要报告结构: {', '.join(missing)}")
    if "</html>" not in html.lower():
        raise ReportBuildError(f"{source} 不是完整 HTML 文档")
    missing_visual = [marker for marker in VISUAL_CONTRACT_MARKERS if marker not in html]
    if not any(marker in html for marker in TITLE_LAYOUT_MARKERS):
        missing_visual.append("title-wrap layout")
    if missing_visual:
        raise ReportBuildError(
            f"{source} 改动了 Pixso 画板视觉合同、图例或布线结构，缺少: "
            + ", ".join(missing_visual)
        )
    if 'data-set-theme="mono"' in html or 'html[data-theme="mono"]' in html:
        raise ReportBuildError(f"{source} 不得恢复已移除的黑白主题")
    if "ic_huawei_cloud_archived_item_@2x" in html:
        raise ReportBuildError(f"{source} 修复方案图标不得复用深色画板 PNG")
    missing_typography = [marker for marker in TYPOGRAPHY_CONTRACT_MARKERS if marker not in html]
    if missing_typography:
        raise ReportBuildError(
            f"{source} 改动了 Pixso 字体合同，缺少: "
            + ", ".join(missing_typography)
        )


def load_report_data(data_path: Path) -> object:
    if not data_path.is_file():
        raise ReportBuildError(f"报告数据文件不存在: {data_path}")
    try:
        return json.loads(data_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReportBuildError(f"报告数据不是有效 UTF-8 JSON: {data_path}: {exc}") from exc


def resolve_value(data: object, path: str) -> object:
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise KeyError(path)
    return current


def require_mapping(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ReportBuildError(f"报告字段必须是对象: {path}")
    return value


def require_list(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise ReportBuildError(f"报告字段必须是数组: {path}")
    return value


def require_text(mapping: dict[str, object], key: str, path: str) -> str:
    value = mapping.get(key)
    if value is None or value == "":
        return "未提供"
    if isinstance(value, (dict, list)):
        raise ReportBuildError(f"报告字段必须是标量值: {path}.{key}")
    return str(value)


def require_confidence(data: object) -> str:
    root = require_mapping(data, "report-data")
    diagnosis = require_mapping(root.get("diagnosis"), "diagnosis")
    confidence = require_text(diagnosis, "confidence", "diagnosis")
    if confidence not in CONFIDENCE_LEVELS:
        raise ReportBuildError(
            "diagnosis.confidence 必须是: " + ", ".join(CONFIDENCE_LEVELS)
        )
    return confidence


def prepare_diagnosis_display(data: object, confidence: str) -> None:
    """Normalize legacy diagnosis facts and expose the score used by the header."""
    root = require_mapping(data, "report-data")
    diagnosis = require_mapping(root.get("diagnosis"), "diagnosis")

    score = diagnosis.get("confidence_score")
    if score is not None:
        if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
            raise ReportBuildError("diagnosis.confidence_score 必须是 0-100 的整数")

    facts = diagnosis.get("facts")
    if not isinstance(facts, list):
        raise ReportBuildError("diagnosis.facts 必须是数组")

    fact_records: list[dict[str, object]] = []
    for index, raw_fact in enumerate(facts):
        fact = require_mapping(raw_fact, f"diagnosis.facts.{index}")
        fact_records.append(fact)
        if score is None and require_text(fact, "label", f"diagnosis.facts.{index}") == "可信度":
            value = require_text(fact, "value", f"diagnosis.facts.{index}")
            score_match = re.search(r"(?<!\d)(\d{1,3})\s*/\s*100(?!\d)", value)
            if score_match:
                score = int(score_match.group(1))

    if score is not None:
        diagnosis["confidence_score"] = score
        diagnosis["confidence_display"] = f"可信度 {score}/100 · {confidence}"
    else:
        diagnosis["confidence_display"] = f"可信度 未提供 · {confidence}"

    aliases = {
        "首报": {"首报"},
        "根因主体": {"根因主体", "根因", "故障主体"},
        "源卡证据": {"源卡证据", "证据边界", "源卡"},
        "客户可做": {"客户可做", "客户动作", "客户侧动作", "处置建议"},
    }
    normalized: list[dict[str, str]] = []
    matched = False
    for canonical, accepted in aliases.items():
        value = "未提供"
        for fact in fact_records:
            label = require_text(fact, "label", "diagnosis.facts")
            if label in accepted:
                value = require_text(fact, "value", "diagnosis.facts")
                matched = True
                break
        normalized.append({"label": canonical, "value": value})

    # New producers may provide four values without labels; keep their order.
    if not matched and len(fact_records) == 4:
        normalized = [
            {"label": canonical, "value": require_text(fact, "value", "diagnosis.facts")}
            for canonical, fact in zip(aliases, fact_records)
        ]
    diagnosis["facts"] = normalized


def reject_insufficient_causal_status(status: str, confidence: str, path: str) -> None:
    if confidence == "INSUFFICIENT" and status in CAUSAL_STATUSES:
        raise ReportBuildError(
            f"{path}: diagnosis.confidence=INSUFFICIENT 时不能标记 {status}"
        )


def render_timeline(data: object, confidence: str) -> str:
    root = require_mapping(data, "report-data")
    timeline = require_list(root.get("timeline"), "timeline")
    if not timeline:
        raise ReportBuildError("timeline 至少需要一条已观察事件")

    rendered_rows: list[str] = []
    for index, raw_item in enumerate(timeline):
        item_path = f"timeline.{index}"
        item = require_mapping(raw_item, item_path)
        status = require_text(item, "status", item_path)
        if status not in NODE_STATUS_STRENGTH:
            raise ReportBuildError(f"{item_path}.status 不受支持: {status}")
        strength = require_text(item, "evidence_strength", item_path)
        expected_strength = NODE_STATUS_STRENGTH[status]
        if strength != expected_strength:
            raise ReportBuildError(
                f"{item_path}: status={status} 必须使用 evidence_strength={expected_strength}"
            )
        reject_insufficient_causal_status(status, confidence, item_path)
        timestamp = require_text(item, "time", item_path)
        if not TIMELINE_TIMESTAMP_RE.fullmatch(timestamp):
            raise ReportBuildError(
                f"{item_path}.time 必须是日志时间戳；日志未提供时间时填写“时间戳未提供”"
            )
        source = require_text(item, "source", item_path)
        message = require_text(item, "message", item_path)
        row_class = "timeline-row source" if status in {"root_cause", "fault_source"} else "timeline-row"
        rendered_rows.append(
            '<div class="{}" data-timeline-status="{}" data-evidence-strength="{}">'
            '<div class="timeline-time"><img class="mini-icon" '
            'data-report-icon="clock" alt="">{}</div>'
            '<div class="timeline-event"><span>{}</span><span>{}</span></div></div>'.format(
                row_class,
                html.escape(status, quote=True),
                html.escape(strength, quote=True),
                html.escape(timestamp),
                html.escape(source),
                html.escape(message),
            )
        )
    return "".join(rendered_rows)


def render_architecture(data: object, confidence: str) -> str:
    root = require_mapping(data, "report-data")
    architecture = require_mapping(root.get("architecture"), "architecture")
    layers = require_list(architecture.get("layers"), "architecture.layers")
    edges = require_list(architecture.get("edges"), "architecture.edges")
    note = require_text(architecture, "hardware_note", "architecture")

    seen_layer_kinds: set[str] = set()
    seen_node_ids: set[str] = set()
    node_statuses: dict[str, str] = {}
    layer_records: list[dict[str, object]] = []

    for layer_index, raw_layer in enumerate(layers):
        layer_path = f"architecture.layers.{layer_index}"
        layer = require_mapping(raw_layer, layer_path)
        kind = require_text(layer, "kind", layer_path)
        if kind not in LAYER_KINDS:
            raise ReportBuildError(
                f"{layer_path}.kind 必须是: {', '.join(LAYER_KINDS)}"
            )
        if kind in seen_layer_kinds:
            raise ReportBuildError(f"架构层重复: {kind}")
        seen_layer_kinds.add(kind)

        label = require_text(layer, "label", layer_path)
        if kind == "model" and label not in {"模型层", "框架层"}:
            raise ReportBuildError(f"{layer_path}.label 必须是模型层或框架层")
        if kind == "component" and label != "组件层":
            raise ReportBuildError(f"{layer_path}.label 必须是组件层")
        if kind == "hardware" and label != "硬件层":
            raise ReportBuildError(f"{layer_path}.label 必须是硬件层")
        caption = require_text(layer, "caption", layer_path)
        nodes = require_list(layer.get("nodes"), f"{layer_path}.nodes")
        if kind != "hardware" and not nodes:
            raise ReportBuildError(f"{layer_path}.nodes 不得为空")
        rendered_nodes: list[str] = []
        rendered_node_ids: list[str] = []

        for node_index, raw_node in enumerate(nodes):
            node_path = f"{layer_path}.nodes.{node_index}"
            node = require_mapping(raw_node, node_path)
            node_id = require_text(node, "id", node_path)
            if not NODE_ID_RE.fullmatch(node_id):
                raise ReportBuildError(
                    f"{node_path}.id 必须以字母开头且只含字母、数字、._:-"
                )
            if node_id in seen_node_ids:
                raise ReportBuildError(f"架构节点 ID 重复: {node_id}")
            seen_node_ids.add(node_id)

            status = require_text(node, "status", node_path)
            if status not in NODE_STATUS_META:
                raise ReportBuildError(
                    f"{node_path}.status 不受支持: {status}"
                )
            strength = require_text(node, "evidence_strength", node_path)
            expected_strength = NODE_STATUS_STRENGTH[status]
            if strength != expected_strength:
                raise ReportBuildError(
                    f"{node_path}: status={status} 必须使用 evidence_strength={expected_strength}"
                )
            reject_insufficient_causal_status(status, confidence, node_path)
            if status == "fault_source" and kind != "hardware":
                raise ReportBuildError(f"{node_path}: fault_source 只能用于硬件层")
            if status == "root_cause" and kind != "component":
                raise ReportBuildError(f"{node_path}: root_cause 只能用于组件层")
            if status == "direct_trigger" and kind != "component":
                raise ReportBuildError(f"{node_path}: direct_trigger 只能用于组件层")
            catalog_name = ""
            if kind == "component":
                catalog_name = require_text(node, "catalog_name", node_path)
                if catalog_name not in COMPONENT_CATALOG:
                    raise ReportBuildError(
                        f"{node_path}.catalog_name 不在 CANN 组件目录中；"
                        "无法映射时请使用 unknown"
                    )

            title = require_text(node, "title", node_path)
            if kind == "hardware" and not re.search(r"\b(?:device|rank|npu)\b", title, re.IGNORECASE):
                raise ReportBuildError(
                    f"{node_path}.title 必须是日志明确出现的 Device、rank 或 NPU；"
                    "Host CPU 不得画入硬件层设备卡"
                )
            if kind == "component" and title == catalog_name:
                raise ReportBuildError(
                    f"{node_path}.title 必须填写具体算子、接口或故障动作，"
                    "不能重复 catalog_name"
                )
            detail = require_text(node, "detail", node_path)
            tag = require_text(node, "tag", node_path)
            status_label, _ = NODE_STATUS_META[status]
            node_statuses[node_id] = status
            rendered_node_ids.append(node_id)
            if kind == "hardware":
                device_class = "device source" if status == "fault_source" else "device"
                rendered_nodes.append(
                    '<div class="{}" data-node-id="{}" data-node-status="{}">'
                    '<div class="device-head"><img class="mini-icon" '
                    'data-report-icon="device" alt="">{}</div>'
                    '<div class="device-body"><div class="device-role">{}</div>'
                    '<div class="device-data">{} · {}</div></div></div>'.format(
                        device_class,
                        html.escape(node_id, quote=True),
                        html.escape(status, quote=True),
                        html.escape(title),
                        html.escape(status_label),
                        html.escape(tag),
                        html.escape(detail),
                    )
                )
            else:
                node_class = "node"
                if kind == "component" and status == "root_cause":
                    node_class += " error"
                elif kind == "component" and status == "direct_trigger":
                    node_class += " trigger"
                display_tag = catalog_name if kind == "component" else tag
                tag_style = ""
                if kind == "component" and status == "propagation":
                    tag_style = ' style="color:var(--blue);background:var(--blue-bg)"'
                meta = (
                    f"{status_label} · {tag} · {detail}"
                    if kind == "component"
                    else f"{tag} · {detail}"
                )
                rendered_nodes.append(
                    '<div class="{}" data-node-id="{}" data-node-status="{}">'
                    '<span class="node-tag"{}>{}</span><div class="node-title">{}</div>'
                    '<div class="node-meta">{}</div></div>'.format(
                        node_class,
                        html.escape(node_id, quote=True),
                        html.escape(status, quote=True),
                        tag_style,
                        html.escape(display_tag),
                        html.escape(title),
                        html.escape(meta),
                    )
                )

        limit = LAYER_NODE_LIMITS.get(kind)
        if limit is not None and len(rendered_nodes) > limit:
            raise ReportBuildError(
                f"{layer_path}.nodes 最多允许 {limit} 个，避免改变 index 模板的竖向长条结构"
            )
        layer_records.append({
            "kind": kind,
            "label": label,
            "caption": caption,
            "node_ids": rendered_node_ids,
            "node_html": rendered_nodes,
        })

    missing_layers = sorted(set(LAYER_KINDS) - seen_layer_kinds)
    if missing_layers:
        raise ReportBuildError(
            "architecture.layers 缺少层: " + ", ".join(missing_layers)
        )
    if tuple(record["kind"] for record in layer_records) != LAYER_KINDS:
        raise ReportBuildError("architecture.layers 必须严格按 model、component、hardware 竖向排列")

    visible_edges: list[dict[str, str]] = []
    for edge_index, raw_edge in enumerate(edges):
        edge_path = f"architecture.edges.{edge_index}"
        edge = require_mapping(raw_edge, edge_path)
        source = require_text(edge, "from", edge_path)
        target = require_text(edge, "to", edge_path)
        if source not in seen_node_ids or target not in seen_node_ids:
            raise ReportBuildError(
                f"{edge_path} 引用了不存在的节点: {source} -> {target}"
            )
        if source == target:
            raise ReportBuildError(f"{edge_path} 不允许自连接: {source}")
        kind = require_text(edge, "kind", edge_path)
        if kind not in EDGE_KIND_META:
            raise ReportBuildError(f"{edge_path}.kind 不受支持: {kind}")
        strength = require_text(edge, "evidence_strength", edge_path)
        expected_strength = EDGE_KIND_STRENGTH[kind]
        if strength != expected_strength:
            raise ReportBuildError(
                f"{edge_path}: kind={kind} 必须使用 evidence_strength={expected_strength}"
            )
        if kind == "root_cause" and not {
            node_statuses[source], node_statuses[target]
        }.intersection({"root_cause", "fault_source"}):
            raise ReportBuildError(
                f"{edge_path}: root_cause 连线必须连接已证实根因或故障源节点"
            )
        label = require_text(edge, "label", edge_path)
        visual = EDGE_VISUAL_META.get(kind)
        if visual:
            _, wire_style = visual
            visible_edges.append({
                "source": source,
                "target": target,
                "wire_style": wire_style,
                "semantic": kind,
                "label": label,
            })

    connector_edges: dict[tuple[str, str], dict[str, str]] = {}
    for record in layer_records:
        if record["kind"] == "hardware":
            continue
        node_ids = record["node_ids"]
        for source, target in zip(node_ids, node_ids[1:]):
            matches = [
                edge for edge in visible_edges
                if edge["source"] == source and edge["target"] == target
            ]
            if matches:
                connector_edges[(source, target)] = matches[0]

    rendered_layers: list[str] = []
    for record in layer_records:
        kind = str(record["kind"])
        node_ids = record["node_ids"]
        node_html = record["node_html"]
        if kind == "hardware":
            if node_html:
                devices_class = "devices dense" if len(node_html) > 4 else "devices"
                content_html = (
                    f'<div class="{devices_class}">{"".join(node_html)}</div>'
                    f'<p class="hardware-note">{html.escape(note)}</p>'
                )
            else:
                content_html = (
                    '<div class="hardware-empty">当前日志未提供 NPU Device 执行证据</div>'
                    f'<p class="hardware-note">{html.escape(note)}</p>'
                )
        else:
            stack_parts: list[str] = []
            for index, current_node in enumerate(node_html):
                stack_parts.append(current_node)
                if index >= len(node_html) - 1:
                    continue
                edge = connector_edges.get((node_ids[index], node_ids[index + 1]))
                if edge is None:
                    continue
                connector_class = "connector error-connector" if edge["wire_style"] == "error" else "connector"
                stack_parts.append(
                    '<div class="{}"><span>{}</span></div>'.format(
                        connector_class,
                        html.escape(edge["label"]),
                    )
                )
            content_html = f'<div class="flow-stack">{"".join(stack_parts)}</div>'
        layer_icon, layer_icon_class = LAYER_PRESENTATION[kind]
        rendered_layers.append(
            '<div class="layer {}-layer" data-layer-kind="{}">'
            '<div class="layer-label"><img class="{}" data-report-icon="{}" alt="">{}</div>'
            '<div class="layer-caption">{}</div>{}'
            '</div>'.format(
                html.escape(kind, quote=True),
                html.escape(kind, quote=True),
                html.escape(layer_icon_class, quote=True),
                html.escape(layer_icon, quote=True),
                html.escape(str(record["label"])),
                html.escape(str(record["caption"])),
                content_html,
            )
        )

    rendered_edges = []
    consumed_connectors = {id(edge) for edge in connector_edges.values()}
    for edge in visible_edges:
        if id(edge) in consumed_connectors:
            continue
        rendered_edges.append(
            '<span hidden data-graph-edge data-edge-from="{}" data-edge-to="{}" '
            'data-edge-kind="{}" data-edge-semantic="{}" data-edge-label="{}"></span>'.format(
                html.escape(edge["source"], quote=True),
                html.escape(edge["target"], quote=True),
                html.escape(edge["wire_style"], quote=True),
                html.escape(edge["semantic"], quote=True),
                html.escape(edge["label"], quote=True),
            )
        )

    return "".join(rendered_layers) + '<div hidden>' + "".join(rendered_edges) + "</div>"


def render_report_data(template: str, data: object) -> str:
    missing: set[str] = set()

    if not TIMELINE_BLOCK_RE.search(template):
        raise ReportBuildError("报告模板缺少动态首错预览替换块")
    if not ARCHITECTURE_BLOCK_RE.search(template):
        raise ReportBuildError("报告模板缺少动态架构预览替换块")
    template = REPORT_DATA_TEMPLATE_RE.sub("", template, count=1)
    root = require_mapping(data, "report-data")
    environment = require_mapping(root.get("environment"), "environment")
    environment_items = require_list(environment.get("items"), "environment.items")
    expected_environment_labels = (
        "模型", "vLLM", "CANN Runtime", "OS", "Driver", "Firmware", "芯片"
    )
    if len(environment_items) != len(expected_environment_labels):
        raise ReportBuildError(
            "environment.items 必须严格包含 7 个运行环境字段，且芯片固定在最后"
        )
    for index, (raw_item, expected_label) in enumerate(zip(environment_items, expected_environment_labels)):
        item = require_mapping(raw_item, f"environment.items.{index}")
        if require_text(item, "label", f"environment.items.{index}") != expected_label:
            raise ReportBuildError(
                f"environment.items.{index}.label 必须是 {expected_label}"
            )

    overview = require_mapping(root.get("overview"), "overview")
    for key, expected_label in (
        ("scene", "运行场景"),
        ("incident", "发生问题"),
        ("impact", "业务影响"),
    ):
        item = require_mapping(overview.get(key), f"overview.{key}")
        if require_text(item, "label", f"overview.{key}") != expected_label:
            raise ReportBuildError(f"overview.{key}.label 必须是 {expected_label}")

    remedies = require_list(root.get("remedies"), "remedies")
    if len(remedies) != 4:
        raise ReportBuildError("remedies 必须包含 4 条处置方案")
    allowed_owners = {"客户方", "华为方为主", "华为方"}
    allowed_remedy_layers = {"模型层", "组件层", "硬件层"}
    architecture = require_mapping(root.get("architecture"), "architecture")
    architecture_layers = require_list(architecture.get("layers"), "architecture.layers")
    architecture_component_names: dict[str, set[str]] = {
        "模型层": set(),
        "组件层": set(),
        "硬件层": set(),
    }
    for layer_index, raw_layer in enumerate(architecture_layers):
        layer_path = f"architecture.layers.{layer_index}"
        architecture_layer = require_mapping(raw_layer, layer_path)
        kind = require_text(architecture_layer, "kind", layer_path)
        nodes = require_list(architecture_layer.get("nodes"), f"{layer_path}.nodes")
        for node_index, raw_node in enumerate(nodes):
            node_path = f"{layer_path}.nodes.{node_index}"
            node = require_mapping(raw_node, node_path)
            if kind == "component":
                architecture_component_names["组件层"].add(
                    require_text(node, "catalog_name", node_path)
                )
            elif kind == "model":
                architecture_component_names["模型层"].add(
                    require_text(node, "tag", node_path)
                )
            elif kind == "hardware":
                architecture_component_names["硬件层"].add(
                    require_text(node, "title", node_path)
                )
    timing_pattern = re.compile(
        r"^(?:配套修复|(?:立即|[^/\s]+(?:后|时|期))\s*/\s*[^/\s]+)$"
    )
    for index, raw_remedy in enumerate(remedies):
        remedy_path = f"remedies.{index}"
        remedy = require_mapping(raw_remedy, remedy_path)
        owner = require_text(remedy, "owner", remedy_path)
        if owner not in allowed_owners:
            raise ReportBuildError(
                f"{remedy_path}.owner 只能是客户方、华为方为主或华为方"
            )
        layer = require_text(remedy, "layer", remedy_path)
        if layer not in allowed_remedy_layers:
            raise ReportBuildError(
                f"{remedy_path}.layer 只能是模型层、组件层或硬件层"
            )
        component = require_text(remedy, "component", remedy_path)
        if "\n" in component or "\r" in component or len(component) > 30:
            raise ReportBuildError(
                f"{remedy_path}.component 必须是右侧分层图中的单行短组件名，"
                "不得填写说明句"
            )
        if component not in architecture_component_names[layer]:
            available = "、".join(sorted(architecture_component_names[layer])) or "无"
            raise ReportBuildError(
                f"{remedy_path}.component 必须复用右侧{layer}节点显示的组件名；"
                f"当前可用值: {available}"
            )
        timing = require_text(remedy, "timing", remedy_path)
        if not timing_pattern.fullmatch(timing):
            raise ReportBuildError(
                f"{remedy_path}.timing 必须使用“时效 / 性质”格式"
            )
        timing_detail = require_text(remedy, "timing_detail", remedy_path)
        if re.search(r"尚未(?:执行|验证|修复)", timing_detail):
            raise ReportBuildError(
                f"{remedy_path}.timing_detail 应写代价、验证要求或方案边界"
            )

    confidence = require_confidence(data)
    prepare_diagnosis_display(data, confidence)
    timeline = render_timeline(data, confidence)
    architecture_graph = render_architecture(data, confidence)
    template = TIMELINE_BLOCK_RE.sub(timeline, template, count=1)
    template = ARCHITECTURE_BLOCK_RE.sub(architecture_graph, template, count=1)

    def replace(match: re.Match[str]) -> str:
        path = match.group("path")
        try:
            value = resolve_value(data, path)
        except KeyError:
            missing.add(path)
            return match.group(0)
        if value is None or value == "":
            value = "未提供"
        if isinstance(value, (dict, list)):
            raise ReportBuildError(f"占位字段必须是标量值: {path}")
        return html.escape(str(value), quote=True)

    rendered = PLACEHOLDER_RE.sub(replace, template)
    if missing:
        raise ReportBuildError(f"报告数据缺少字段: {', '.join(sorted(missing))}")
    return rendered


def load_icon_data(html_text: str, source: Path) -> dict[str, str]:
    icons: dict[str, str] = {}
    for tag in IMAGE_TAG_RE.finditer(html_text):
        attrs = tag.group("attrs")
        name_match = ICON_NAME_RE.search(attrs)
        if not name_match:
            continue
        source_match = IMAGE_SOURCE_RE.search(attrs)
        name = name_match.group("name")
        if not source_match or not source_match.group("src").startswith("data:image/"):
            raise ReportBuildError(f"模板图标未内嵌: {name}")
        value = source_match.group("src")
        if name in icons and icons[name] != value:
            raise ReportBuildError(f"同一模板图标键对应多个资源: {name}")
        icons[name] = value
    if not icons:
        raise ReportBuildError(f"模板缺少内嵌图标: {source}")
    return icons


def apply_embedded_icons(html_text: str, icons: dict[str, str]) -> str:
    missing: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        name_match = ICON_NAME_RE.search(attrs)
        if not name_match:
            return match.group(0)
        name = name_match.group("name")
        data_uri = icons.get(name)
        if data_uri is None:
            missing.add(name)
            return match.group(0)
        attrs = re.sub(r'\s+src="[^"]*"', "", attrs)
        return f'<img{attrs} src="{html.escape(data_uri, quote=True)}">'

    rendered = IMAGE_TAG_RE.sub(replace, html_text)
    if missing:
        raise ReportBuildError("模板缺少图标键: " + ", ".join(sorted(missing)))
    return rendered


def validate_no_placeholders(html_text: str, check_semantic: bool = True) -> None:
    if check_semantic:
        unresolved = sorted({match.group("path") for match in PLACEHOLDER_RE.finditer(html_text)})
        if unresolved:
            raise ReportBuildError(
                "报告仍有未填语义字段，请提供 --data 或完成手工替换: "
                + ", ".join(unresolved)
            )
    if ARCHITECTURE_BLOCK_RE.search(html_text):
        raise ReportBuildError("报告仍有未替换的分层图预览")
    if TIMELINE_BLOCK_RE.search(html_text):
        raise ReportBuildError("报告仍有未替换的首错时序预览")


def embed_local_assets(html: str, source: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        relative = match.group("path")
        asset = (source.parent / relative).resolve()
        try:
            asset.relative_to(source.parent.resolve())
        except ValueError as exc:
            raise ReportBuildError(f"拒绝嵌入报告目录外的资源: {relative}") from exc
        if not asset.is_file():
            raise ReportBuildError(f"本地资源不存在: {relative}")
        mime_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(asset.read_bytes()).decode("ascii")
        return f'{match.group("prefix")}data:{mime_type};base64,{encoded}{match.group("suffix")}'

    return CSS_URL_RE.sub(replace, LOCAL_REF_RE.sub(replace, html))


def package_report(source: Path, output: Path, force: bool, data_path: Path | None = None) -> None:
    if source.resolve() == output.resolve():
        raise ReportBuildError("输出文件不能覆盖输入模板；请为 --output 使用独立路径")
    if output.exists() and not force:
        raise ReportBuildError(f"输出已存在，请更换文件名或添加 --force: {output}")
    if not source.is_file():
        raise ReportBuildError(f"报告源文件不存在: {source}")

    html = source.read_text(encoding="utf-8")
    validate_structure(html, source)
    icons = load_icon_data(html, source)
    if data_path is not None:
        html = render_report_data(html, load_report_data(data_path))
    html = apply_embedded_icons(html, icons)
    html = REPORT_DATA_TEMPLATE_RE.sub("", html, count=1)
    validate_no_placeholders(html, check_semantic=data_path is None)
    standalone = embed_local_assets(html, source)
    unresolved = [
        match.group("path")
        for pattern in (LOCAL_REF_RE, CSS_URL_RE)
        for match in pattern.finditer(standalone)
    ]
    if unresolved:
        raise ReportBuildError(f"仍有未内嵌的本地资源: {', '.join(sorted(set(unresolved)))}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(standalone, encoding="utf-8")
    print(f"OK built standalone report: {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="初始化空白分层故障报告，或用结构化数据生成独立 HTML"
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--init", type=Path, metavar="DIR", help="创建可编辑的报告目录")
    action.add_argument("--output", type=Path, metavar="HTML", help="输出独立 HTML")
    parser.add_argument("--input", type=Path, metavar="HTML", help="报告模板或编辑后的 HTML，默认使用内置空白模板")
    parser.add_argument("--data", type=Path, metavar="JSON", help="填充模板语义字段的结构化 JSON")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的目标")
    args = parser.parse_args()
    if args.init and args.input:
        parser.error("--input 只能与 --output 一起使用")
    if args.init and args.data:
        parser.error("--data 只能与 --output 一起使用")
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.init:
            initialize_report(args.init.expanduser().resolve(), args.force)
        else:
            source = (args.input or (find_template_dir() / "index.html")).expanduser().resolve()
            data_path = args.data.expanduser().resolve() if args.data else None
            package_report(source, args.output.expanduser().resolve(), args.force, data_path)
        return 0
    except ReportBuildError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
