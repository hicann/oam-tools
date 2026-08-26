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
"""Bind every normalized Timeline event to one structure node and one raw TraceView event.

Legacy UI builders re-derived ownership from one model's kernel
shapes (RmsNorm layer boundaries, an `mtp_scaffold` stage, hardcoded lm_head node ids), so it
only runs for that model. The attribution this pipeline already produced is stronger evidence:
it comes from the breakdown's declared `op_indices` and instance ranges, verified at 100%
coverage. This joins that attribution to the raw trace instead of guessing it again.

The raw join is by exact (op name, start time, duration) against `X` events; a kernel that
matches no raw event, or matches ambiguously, is an error rather than a silent drop.
"""
import argparse
import json
import logging
import math
import os
import sys
from collections import defaultdict

import breakdown_paths


logger = logging.getLogger(__name__)


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeline", required=True)
    parser.add_argument("--attribution", required=True)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--enrich-trace", metavar="PATH",
                        help="write a copy of the trace with structure facts added to each "
                             "joined X event's args. The repeated-layer pager derives its "
                             "per-layer heat from args.layer_index, so without this the dots "
                             "stay uncolored even though the layers ran.")
    return parser.parse_args()


def index_raw_events(raw_events):
    by_name = defaultdict(list)
    for index, event in enumerate(raw_events):
        if event.get("ph") == "X":
            by_name[event.get("name")].append(index)
    return by_name


def matching_raw_events(row, raw_events, by_name, used):
    start = float(row.get("start_time_us") or 0.0)
    duration = float(row.get("duration_us") or 0.0)
    candidates = []
    for raw_index in by_name.get(row.get("op_name"), []):
        if raw_index in used:
            continue
        raw_event = raw_events[raw_index]
        timestamp_matches = math.isclose(
            float(raw_event.get("ts") or 0.0), start, rel_tol=0.0, abs_tol=1e-3
        )
        duration_matches = math.isclose(
            float(raw_event.get("dur") or 0.0), duration, rel_tol=0.0, abs_tol=1e-3
        )
        if timestamp_matches and duration_matches:
            candidates.append(raw_index)
    return candidates, start, duration


def binding_for(event, row, raw_index):
    return {
        "trace_event_id": event["event_id"],
        "raw_source_event_index": raw_index,
        "timeline_event_id": event["event_id"],
        "op_index": int(event["op_index"]),
        "node_id": event["owner_node_id"],
        "instance_id": event.get("instance_index"),
        "structure_instance_node_id": event.get("structure_instance_node_id"),
        "submodule": event.get("submodule"),
        "relation": "direct_kernel_owner",
        "mapping_method": row.get("attribution_evidence") or "declared_op_indices",
        "confidence": "high",
    }


def bind_events(timeline, rows_by_op, raw_events):
    by_name = index_raw_events(raw_events)
    used = set()
    enrich_by_raw_index = {}
    bindings = []
    unresolved = []
    for event in timeline.get("events") or []:
        op_index = int(event["op_index"])
        row = rows_by_op.get(op_index)
        if row is None:
            unresolved.append((op_index, "no attribution row"))
            continue
        candidates, start, duration = matching_raw_events(row, raw_events, by_name, used)
        if not candidates:
            unresolved.append((
                op_index,
                f"no free raw X event matching name={row.get('op_name')!r}, "
                f"ts={start}, dur={duration}",
            ))
            continue
        if len(candidates) != 1:
            unresolved.append((
                op_index,
                f"ambiguous raw X event match for name={row.get('op_name')!r}, "
                f"ts={start}, dur={duration}: indices {candidates}",
            ))
            continue
        pick = candidates[0]
        used.add(pick)
        enrich_by_raw_index[pick] = {
            "layer_index": event.get("layer_index"),
            "owner_node_id": event["owner_node_id"],
            "submodule": event.get("submodule"),
            "op_index": op_index,
            "op_type": row.get("op_type"),
        }
        bindings.append(binding_for(event, row, pick))

    if unresolved:
        for op_index, reason in unresolved[:10]:
            logger.error("UNRESOLVED op_index=%s: %s", op_index, reason)
        raise breakdown_paths.ConversionError(
            f"{len(unresolved)} Timeline event(s) could not be bound; "
            "a binding must not be invented"
        )
    return bindings, enrich_by_raw_index


def binding_output(timeline, args, bindings):
    return {
        "schema_version": 1,
        "contract": "structure_tree_to_raw_traceview_v1",
        "model_id": timeline["model_id"],
        "report_id": timeline["report_id"],
        "representative_step": timeline.get("representative_step"),
        "sources": {"timeline": os.path.basename(args.timeline),
                    "raw_trace": os.path.basename(args.trace),
                    "attribution": os.path.basename(args.attribution)},
        "bindings": bindings,
        "summary": {
            "timeline_events": len(timeline.get("events") or []),
            "bound_events": len(bindings),
            "direct_events": len(bindings),
            "propagated_events": 0,
            "coverage_pct": round(100.0 * len(bindings)
                                  / max(1, len(timeline.get("events") or [])), 4),
        },
    }


def write_bindings(path, output):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    logger.info("WROTE %s", path)
    logger.info("  bound %s/%s (%s%%)", len(output["bindings"]),
                output["summary"]["timeline_events"], output["summary"]["coverage_pct"])


def enrich_trace(raw, raw_events, facts_by_index, path):
    with_layer = 0
    for raw_index, facts in facts_by_index.items():
        event = raw_events[raw_index]
        merged = dict(event.get("args") or {})
        for key, value in facts.items():
            if value is not None:
                merged[key] = value
        event["args"] = merged
        if facts.get("layer_index") is not None:
            with_layer += 1
    payload = raw_events if isinstance(raw, list) else {**raw, "traceEvents": raw_events}
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    logger.info("WROTE %s", path)
    logger.info("  enriched %s X events, %s carry layer_index", len(facts_by_index), with_layer)
    if not with_layer:
        logger.info("  NOTE no event carries layer_index: the per-layer pager heat will be "
                    "uniform. Check that trace_instances declare model_layer_index.")


def main():
    args = parse_args()
    timeline = load(args.timeline)
    attribution = load(args.attribution)
    raw = load(args.trace)
    raw_events = raw if isinstance(raw, list) else raw.get("traceEvents") or []
    rows_by_op = {int(row["op_index"]): row for row in attribution["rows"]}
    bindings, enrichments = bind_events(timeline, rows_by_op, raw_events)
    output = binding_output(timeline, args, bindings)
    write_bindings(args.out, output)
    if args.enrich_trace:
        enrich_trace(raw, raw_events, enrichments, args.enrich_trace)


if __name__ == "__main__":
    sys.exit(breakdown_paths.run_cli(main))
