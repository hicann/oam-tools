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
"""Emit the three UI backend facts from an attributed breakdown.

Metrics derive from attributed kernels only. Every metric key is written even
when its value is null, because a missing key and a null value are different
claims: the UI renders null as unavailable, never as zero.

The architecture graph is emitted separately by build_graph.py, which needs the
declared `branches` this stage does not consume.
"""
import argparse
import logging
import os
import sys
from collections import Counter, defaultdict

import breakdown_paths


logger = logging.getLogger(__name__)


def numel(shape):
    if not isinstance(shape, list) or not shape:
        return 0
    total = 1
    for dim in shape:
        if not isinstance(dim, int) or dim <= 0:
            return 0
        total *= dim
    return total


def descendants(node_id, children_of):
    """node_id plus every descendant, so aggregate scopes include subtree kernels."""
    out, stack = [node_id], [node_id]
    while stack:
        for child in children_of.get(stack.pop(), []):
            out.append(child)
            stack.append(child)
    return out


def effective_duration_us(row):
    """A kernel's duration for summation, counting a doubly-reported collective once.

    msprof emits one collective as two rows with identical start and duration: the
    COMMUNICATION record and the AIV kernel executing it. The breakdown marks the second with
    `duplicate_of` rather than dropping it, so op indices stay stable. Every sum here must skip
    the marked row or the collective's time is counted twice — on a tp8 capture that inflated
    the step total by 48% and let one all-reduce claim 95% of it.
    """
    if row.get("duplicate_of") is not None:
        return 0.0
    return float(row.get("duration_us") or 0.0)


def counter_sum(rows, field):
    """Sum a counter across rows, or None when no row reported it.

    Null and zero are different claims. A node whose kernels never carried the counter must
    report null (unavailable), not 0.0 (measured idle) — the UI renders those differently and
    a zero would read as a real cube-idle finding.

    Unlike `effective_duration_us`, this deliberately does NOT skip `duplicate_of` rows. The
    duration rule exists because msprof reports a collective's *time* twice; the counters are
    not duplicated the same way. On the DS3.2 capture's 16 duplicate pairs the COMMUNICATION
    primary carries no counters at all and the AIV row carries all of them, so skipping
    duplicates here would discard the collective's measured vector work — 6.9% of the step's
    AIV time — rather than de-duplicate it. Exactly one row per pair carries counters, so a
    plain sum is right. `validate_conversion.py` asserts that precondition.
    """
    values = [r.get(field) for r in rows if r.get(field) is not None]
    return round(sum(values), 4) if values else None


def counter_time_weighted(rows, ratio_field, weight_field):
    """Time-weighted mean of a pipeline ratio.

    A plain mean over kernels lets a 2 us Cast weigh as much as an 84 us MlaPrologV3, which
    misreports where the node's cube time actually went. Weight by the counter time the ratio
    describes: `aic_mac_ratio` is a fraction of `aicore_time_us`, the AIV ratios of `aiv_time_us`.
    Rows missing either field are skipped rather than treated as zero-weight zeros.
    """
    numerator = 0.0
    denominator = 0.0
    for row in rows:
        ratio = row.get(ratio_field)
        weight = row.get(weight_field)
        if ratio is None or weight is None:
            continue
        numerator += float(ratio) * float(weight)
        denominator += float(weight)
    return round(numerator / denominator, 6) if denominator > 0 else None


def _cores(row, prefer_mix):
    """Core count a kernel's cycle counter was accumulated over.

    Mix Block Dim wins for the vector counters on a mixed kernel, where the AIV phase ran on a
    different core count than the cube phase; using Block Dim there is wrong by exactly 2x.
    """
    keys = ("mix_block_dim", "block_dim") if prefer_mix else ("block_dim", "mix_block_dim")
    for key in keys:
        cores = row.get(key)
        if cores:
            try:
                value = float(cores)
            except (TypeError, ValueError):
                continue
            if value > 0:
                return value
    return None


def _cycle_time_us(rows, cycles_key, time_key, freq_mhz, prefer_mix):
    """Elapsed us implied by the cycle counters, summed per kernel.

    The division is per kernel and includes the core count. `aic_total_cycles` is summed over
    every core the kernel occupied, so `cycles / freq` alone yields core-microseconds: on this
    capture's mean Block Dim of ~22 that overstated a node's cube time by ~22x. Only
    `cycles / (freq * cores)` is comparable to the reported `aicore_time(us)`, which is why
    this cannot be computed from an already-aggregated cycle total.
    """
    total = 0.0
    seen = False
    for row in rows:
        cycles = row.get(cycles_key)
        cores = _cores(row, prefer_mix)
        if cycles is None or not cores:
            continue
        reported_time = row.get(time_key)
        if float(cycles) > 0 and reported_time is not None and float(reported_time) > 0:
            observed_freq = float(cycles) / (float(reported_time) * cores)
            if abs(observed_freq - freq_mhz) / freq_mhz > 0.02:
                return None
        total += float(cycles) / (freq_mhz * cores)
        seen = True
    return round(total, 4) if seen else None


def cycle_metrics(rows, freq_mhz):
    """Cycle-derived metrics for a node, all null unless the clock is known.

    Every derived figure divides by the device clock, so computing them against an assumed
    frequency would silently rescale the set. A capture without a verified clock reports the raw
    cycle counts (which need no clock) and nulls the rest.
    """
    metrics = {
        # Raw core-cycle totals: summed across cores and kernels, no clock involved. A
        # scale-free work measure, not a duration.
        "aic_total_cycles": counter_sum(rows, "aic_total_cycles"),
        "aiv_total_cycles": counter_sum(rows, "aiv_total_cycles"),
        "aicore_cycle_time_us": None,
        "aiv_cycle_time_us": None,
    }
    if not freq_mhz:
        return metrics
    metrics["aicore_cycle_time_us"] = _cycle_time_us(
        rows, "aic_total_cycles", "aicore_time_us", freq_mhz, prefer_mix=False)
    metrics["aiv_cycle_time_us"] = _cycle_time_us(
        rows, "aiv_total_cycles", "aiv_time_us", freq_mhz, prefer_mix=True)
    return metrics


def logical_hbm_bytes(rows, dtype_bytes):
    total = 0
    for row in rows:
        shapes = (row.get("input_shapes") or []) + (row.get("output_shapes") or [])
        for shape in shapes:
            total += numel(shape) * dtype_bytes
    return total


def matmul_flops(rows):
    total = 0
    for row in rows:
        if str(row.get("op_type") or "") not in ("MatMulV2", "MatMul", "BatchMatMulV2"):
            continue
        inputs = row.get("input_shapes") or []
        outputs = row.get("output_shapes") or []
        if len(inputs) < 2 or not outputs:
            continue
        weight_shape = inputs[1]
        if isinstance(weight_shape, list) and weight_shape:
            total += 2 * numel(outputs[0]) * weight_shape[-1]
    return total


def counter_coverage(rows):
    present = 0
    for row in rows:
        if row.get("aicore_time_us") is not None or row.get("aiv_time_us") is not None:
            present += 1
    return {
        "kernels_with_counters": present,
        "kernels_total": len(rows),
        "pct": round(100.0 * present / len(rows), 2) if rows else None,
    }


def operation_ratios(rows, time_us):
    op_time = defaultdict(float)
    for row in rows:
        op_time[str(row.get("op_type") or "unknown")] += effective_duration_us(row)
    if time_us <= 0:
        return {}
    return {
        operation: round(100.0 * value / time_us, 2)
        for operation, value in sorted(op_time.items(), key=lambda item: -item[1])
    }


def counter_ratios(rows):
    """Return time-weighted device-pipeline ratios for attributed kernels."""
    return {
        "mac_ratio": counter_time_weighted(rows, "aic_mac_ratio", "aicore_time_us"),
        "mte2_ratio": counter_time_weighted(rows, "aic_mte2_ratio", "aicore_time_us"),
        "mte1_ratio": counter_time_weighted(rows, "aic_mte1_ratio", "aicore_time_us"),
        "scalar_ratio": counter_time_weighted(rows, "aic_scalar_ratio", "aicore_time_us"),
        "fixpipe_ratio": counter_time_weighted(rows, "aic_fixpipe_ratio", "aicore_time_us"),
        "vec_ratio": counter_time_weighted(rows, "aiv_vec_ratio", "aiv_time_us"),
        "aiv_mte2_ratio": counter_time_weighted(rows, "aiv_mte2_ratio", "aiv_time_us"),
        "cube_utilization_pct": counter_time_weighted(
            rows, "cube_utilization_pct", "aicore_time_us"),
    }


def node_metrics(rows, peak_tflops, dtype_bytes, total_time_us, freq_mhz=None):
    """Metrics for one node from the kernels attributed to it (and its subtree)."""
    if not rows:
        return None

    durations = [effective_duration_us(r) for r in rows]
    time_us = sum(durations)

    hbm_bytes = logical_hbm_bytes(rows, dtype_bytes)
    flops = matmul_flops(rows)

    # AI Core counters. The keys are the CSV's own `aic_`/`aiv_` spellings, which is what
    # attribute_kernels carries through; the earlier unprefixed `mac_ratio`/`mte2_ratio`
    # lookups matched nothing and reported every node's cube behaviour as unavailable while
    # the data sat in raw_ops_details.json.
    aicore_time_us = counter_sum(rows, "aicore_time_us")
    aiv_time_us = counter_sum(rows, "aiv_time_us")
    op_ratio = operation_ratios(rows, time_us)

    mfu = None
    if flops > 0 and time_us > 0 and peak_tflops:
        mfu = round(100.0 * (flops / (time_us * 1e-6)) / (peak_tflops * 1e12), 4)

    return {
        "time_us": round(time_us, 4),
        "time_pct": round(100.0 * time_us / total_time_us, 4) if total_time_us else None,
        "nops": len(rows),
        "hbm_mb": round(hbm_bytes / (1024 * 1024), 4) if hbm_bytes else None,
        "gflops": round(flops / 1e9, 6) if flops else 0.0,
        "mfu_bf16_pct": mfu,
        "mfu_int8_pct": None,
        "aicore_time_us": aicore_time_us,
        "aiv_time_us": aiv_time_us,
        # Cube-time share of wall time. Distinguishes a node genuinely busy on the cube from
        # one whose duration is mostly launch gap or waiting.
        "aicore_time_pct": (round(100.0 * aicore_time_us / time_us, 4)
                            if aicore_time_us is not None and time_us > 0 else None),
        # Pipeline ratios, time-weighted (see counter_time_weighted). mac vs mte2 is the
        # compute-bound vs memory-bound read: high mac means the cube is doing math, high
        # mte2 means it is waiting on loads from HBM/L2.
        **counter_ratios(rows),
        **cycle_metrics(rows, freq_mhz),
        "counter_coverage": counter_coverage(rows),
        "op_ratio": op_ratio,
    }


def strip(node):
    """Analysis-config view of a node: identity and semantics, no kernel rows.

    A node the capture never observed is keyed by `structure_node_id` instead of `node_id`,
    for the same reason `source_only_structure` is: the UI runtime builds its backend index
    by scanning for `node_id`, so leaving one here injects a metric-free node into that
    index and the backend-count checks fail. The node still appears in the tree, keeps its
    semantics, and stays selectable -- it just carries no backend identity.
    """
    id_key = "node_id" if node.get("mapped_kernels", 0) else "structure_node_id"
    stripped = {
        id_key: node["node_id"],
        "semantic_key": node["semantic_key"],
        "node_kind": node["node_kind"],
        "metric_scope": node["metric_scope"],
        "name": node["name"],
        "semantic": node["semantic"],
        "code_ref": node["code_ref"],
        "instance_indices": node["instance_indices"],
        # Declared vs observed layers for a repeated group. The graph pager spans the
        # declared set, so it has to survive this hop; dropping it silently shrinks a
        # 58-layer group to the 3 layers this capture happened to run.
        "mapped_kernels": node.get("mapped_kernels", 0),
        "children": [],
    }
    optional_keys = (
        "declared_instance_indices", "unobserved_instance_indices", "invocation_count"
    )
    for key in optional_keys:
        if node.get(key):
            stripped[key] = node[key]
    return stripped


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="explicit breakdown config path")
    parser.add_argument("--breakdown", required=True)
    parser.add_argument("--nodes", required=True)
    parser.add_argument("--attribution", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--report-id", required=True)
    parser.add_argument("--model-name")
    parser.add_argument("--file-prefix", help="output filename prefix; defaults to model-id")
    parser.add_argument("--device-freq",
                        help="device_freq.json from stage 1 device_freq.py. Supplies the "
                             "measured AI Core clock; without it every cycle-derived metric "
                             "is emitted as null rather than against an assumed frequency.")
    parser.add_argument("--peak-bf16-tflops", type=float, default=0.0)
    parser.add_argument("--dtype-bytes", type=int, default=2)
    parser.add_argument("--out", required=True)
    breakdown_paths.add_score_gate_args(parser)
    return parser.parse_args()


def prepare_fact_state(args):
    breakdown_paths.require_convertible_score(
        args.breakdown, args.allow_unscored, "emit_ui_facts.py")
    config = breakdown_paths.load_json(
        breakdown_paths.config_or_die(args.breakdown, args.config)
    )
    index = breakdown_paths.load_json(args.nodes)
    attribution = breakdown_paths.load_json(args.attribution)
    if attribution["summary"]["coverage_pct"] != 100.0:
        raise breakdown_paths.ConversionError(
            f"attribution coverage is {attribution['summary']['coverage_pct']}%; "
            "emit only from a fully attributed breakdown"
        )
    device_profile = (breakdown_paths.load_json(args.device_freq)
                      if args.device_freq else None)
    freq_mhz = (device_profile or {}).get("aicore_freq_mhz")
    nodes = {node["node_id"]: dict(node) for node in index["nodes"]}
    children_of = {node_id: list(node.get("child_ids") or [])
                   for node_id, node in nodes.items()}
    rows_by_node = defaultdict(list)
    for row in attribution["rows"]:
        rows_by_node[row["owner_node_id"]].append(row)
    for node_id, node in nodes.items():
        node["mapped_kernels"] = sum(
            len(rows_by_node.get(child, [])) for child in descendants(node_id, children_of)
        )
    total_time = round(sum(effective_duration_us(row) for row in attribution["rows"]), 4)
    return {
        "config": config, "index": index, "attribution": attribution,
        "device_profile": device_profile, "freq_mhz": freq_mhz, "nodes": nodes,
        "children_of": children_of, "rows_by_node": rows_by_node,
        "total_time_us": total_time, "step": index.get("representative_step"),
        "prefix": args.file_prefix or args.model_id, "namespace": index["id_namespace"],
    }


def nested_node(node_id, state):
    entry = strip(state["nodes"][node_id])
    entry["children"] = [
        nested_node(child, state) for child in state["children_of"].get(node_id, [])
    ]
    return entry


def source_only_records(state):
    records = []
    for node_id, node in state["nodes"].items():
        if node["mapped_kernels"] != 0:
            continue
        declared_unobserved = node.get("declared_not_observed") and node.get("instance_indices")
        if declared_unobserved:
            reason = (f"Declared by the source at model layer index {node['instance_indices'][0]} "
                      f"but not executed in representative step {state['step']} of this capture; "
                      "structure retained, metrics omitted.")
        else:
            reason = ("No kernel attributed to this node inside the representative step "
                      f"({state['step']}) window of this capture.")
        records.append({
            "structure_node_id": node_id, "name": node["name"], "code_ref": node["code_ref"],
            "data_state": "source_only",
            "instance_indices": list(node.get("instance_indices") or []),
            "declared_not_observed": bool(node.get("declared_not_observed")), "reason": reason,
        })
    return records


def analysis_document(args, state):
    config, roots = state["config"], state["index"]["roots"]
    notes = config.get("notes") or []
    analysis = {
        "schema_version": "2.1-ui",
        "model_id": args.model_id,
        "model_name": args.model_name or config.get("model_name") or args.model_id,
        "report_id": args.report_id,
        "id_namespace": state["namespace"], "representative_step": state["step"],
        "architecture": config.get("architecture"),
        "model_flow": list(config.get("model_flow") or []),
        "trace_scope": config.get("trace_scope"),
        "stages": {state["nodes"][node_id]["semantic_key"]: nested_node(node_id, state)
                   for node_id in roots["stages"]},
        "layer_structure": {key: nested_node(node_id, state)
                            for key, node_id in (roots["layer_structure"] or {}).items()},
        "runtime_auxiliary": [nested_node(node_id, state)
                              for node_id in roots["runtime_auxiliary"]],
        "source_only_structure": source_only_records(state),
        "notes": [notes] if isinstance(notes, str) else list(notes),
    }
    if config.get("dataflow") is not None:
        analysis["dataflow"] = config["dataflow"]
    return analysis


def module_records(args, state, source_only_ids):
    modules = []
    for node_id, node in state["nodes"].items():
        if node_id in source_only_ids:
            continue
        subtree = []
        for child in descendants(node_id, state["children_of"]):
            subtree.extend(state["rows_by_node"].get(child, []))
        metrics = node_metrics(subtree, args.peak_bf16_tflops,
                               args.dtype_bytes, state["total_time_us"], state["freq_mhz"])
        if metrics is None:
            continue
        invocation_count = node.get("invocation_count") or len(node["instance_indices"])
        scope_note = None
        if node["instance_indices"]:
            scope_note = ("Metrics aggregate every observed instance of this node across all "
                          f"{invocation_count} invocations (model layer indices "
                          f"{node['instance_indices']}) in representative step {state['step']}.")
        modules.append({
            "node_id": node_id, "module": node["name"],
            "metric_scope": node["metric_scope"], **metrics,
            "instance_indices": node["instance_indices"],
            "invocation_count": node.get("invocation_count"),
            "code_ref": node["code_ref"], "kernel_scope_note": scope_note,
        })
    modules.sort(key=lambda module: -(module["time_us"] or 0))
    return modules


def performance_document(args, state, modules):
    return {
        "schema_version": "2.1-ui",
        "model_id": args.model_id, "report_id": args.report_id,
        "id_namespace": state["namespace"], "representative_step": state["step"],
        "peak_bf16_tflops_assumed": args.peak_bf16_tflops or None,
        "aicore_freq_mhz": state["freq_mhz"], "device_profile": state["device_profile"],
        "total_time_us": state["total_time_us"], "modules": modules,
        "scope_note": "Metrics are representative-step aggregates over attributed "
                      "kernels. HBM figures are logical shape x dtype estimates, "
                      "not measured traffic.",
    }


def timeline_event(row, state):
    start = float(row.get("start_time_us") or 0.0)
    duration = float(row.get("duration_us") or 0.0)
    return {
            "event_id": (f"{state['namespace']}/step/{state['step']}/"
                         f"kernel/{row['op_index']}"),
            "op_index": row["op_index"],
            "name": row.get("op_name"),
            "op_type": row.get("op_type"),
            "device_id": 0,
            "stream_id": row.get("stream_id"),
            "accelerator_core": "ASCEND_HARDWARE",
            "start_time_us_raw": f"{start:.3f}",
            "ts_us": start,
            "duration_us": duration,
            "end_us": start + duration,
            "wait_time_us": 0,
            "owner_node_id": row["owner_node_id"],
            "structure_instance_node_id": row["owner_node_id"],
            "layer_index": row.get("layer_index"),
            "submodule": state["nodes"][row["owner_node_id"]]["semantic_key"],
            "mapping_status": row["attribution_evidence"],
            "trace_join_status": "breakdown_attributed_kernel",
    }


def timeline_document(args, state):
    rows = sorted(state["attribution"]["rows"], key=lambda row: row["op_index"])
    events = [timeline_event(row, state) for row in rows]
    return {
        "schema_version": "1.4",
        "model_id": args.model_id, "report_id": args.report_id,
        "representative_step": state["step"],
        "time_origin_us": min((event["ts_us"] for event in events), default=0),
        "time_unit": "us", "event_count": len(events), "events": events,
        "mapping_summary": {
            "mapped_events": len(events), "unmapped_events": 0, "mapping_coverage_pct": 100,
            "mapping_semantics": "structure node ownership derived from the "
                                 "breakdown's declared op_indices and instance "
                                 "ranges; no name-similarity matching",
        },
        "scope_note": f"Representative step {state['step']} of the source capture.",
    }


def write_facts(args, state, analysis, performance, timeline):
    prefix = state["prefix"]
    breakdown_paths.dump_json(
        analysis, os.path.join(args.out, f"{prefix}_analysis_config.json")
    )
    breakdown_paths.dump_json(
        performance, os.path.join(args.out, f"{prefix}_perf_data.json")
    )
    breakdown_paths.dump_json(
        timeline, os.path.join(args.out, f"{prefix}_timeline.json")
    )
    logger.info("WROTE %s/%s_analysis_config.json", args.out, prefix)
    logger.info("WROTE %s/%s_perf_data.json", args.out, prefix)
    logger.info("WROTE %s/%s_timeline.json", args.out, prefix)
    logger.info("")
    logger.info("backend nodes      %s", len(performance["modules"]))
    logger.info("source-only nodes  %s", len(analysis["source_only_structure"]))
    logger.info("timeline events    %s", len(timeline["events"]))
    logger.info("total_time_us      %s", state["total_time_us"])
    counts = Counter(row["owner_node_id"] for row in state["attribution"]["rows"])
    logger.info("kernels            %s across %s owners", sum(counts.values()), len(counts))


def main():
    args = parse_args()
    state = prepare_fact_state(args)
    analysis = analysis_document(args, state)
    source_only_ids = {
        record["structure_node_id"] for record in analysis["source_only_structure"]
    }
    modules = module_records(args, state, source_only_ids)
    performance = performance_document(args, state, modules)
    timeline = timeline_document(args, state)
    write_facts(args, state, analysis, performance, timeline)
    return 0


if __name__ == "__main__":
    sys.exit(breakdown_paths.run_cli(main))
