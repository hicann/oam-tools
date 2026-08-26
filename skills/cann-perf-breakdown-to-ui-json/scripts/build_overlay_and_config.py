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
"""Emit `architecture_overlay_map.json` and `report-config.js`.

Both are mechanical, but the UI skill only ships model-specific generators for them
(legacy source-overlay builders hardcode one model's source hashes and layer layout;
`build-qwen-hbm-demo.mjs` writes `report-config.js` for one model), so any other model had to
have them hand-written. These derive from the already-emitted facts:

- overlay: every performance node maps to the graph item with the same id. The mapping kind and
  evidence come from that item, not from a guess about what the node is.
- report-config: the runtime path manifest. Filenames are model-specific by design, which is
  exactly why they belong in this file and nowhere else.
"""
import argparse
import json
import logging
import os
import sys

import breakdown_paths


logger = logging.getLogger(__name__)


def jload(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def walk(item, out):
    out.append(item)
    for child in item.get("children") or []:
        walk(child, out)
    return out


def build_overlay(analysis, performance, graph):
    items = {}
    for root in graph.get("roots") or []:
        for item in walk(root, []):
            items[item["id"]] = item

    mappings = []
    for module in performance.get("modules") or []:
        node_id = module["node_id"]
        item = items.get(node_id)
        if item is None:
            # A metric-carrying node with no graph item would render as an unreachable
            # selection; that is a generation defect, not something to skip.
            raise breakdown_paths.ConversionError(
                f"performance node absent from architecture graph: {node_id}"
            )
        refs = item.get("sourceRefs") or []
        mappings.append({
            "backend_node_id": node_id,
            "source_node_ids": [node_id],
            "projected_graph_node_id": node_id,
            "mapping_kind": item.get("mappingKind") or "exact",
            "evidence": [
                f"source: {refs[0]}" if refs else "source: declared analysis structure",
                f"performance scope: {analysis.get('representative_step')}",
            ],
            "review_state": "resolved",
        })

    source_only = [entry.get("structure_node_id")
                   for entry in analysis.get("source_only_structure") or []]
    return {
        "schema_version": "1.0",
        "model_id": analysis["model_id"],
        "report_id": analysis["report_id"],
        "purpose": "bind backend performance nodes to declared source architecture items",
        "id_namespace": analysis.get("id_namespace"),
        "mappings": mappings,
        "source_only_nodes": source_only,
        "validation": {
            "backend_node_count": len(performance.get("modules") or []),
            "mapped_or_classified_backend_node_count": len(mappings),
            "all_backend_nodes_classified":
                len(mappings) == len(performance.get("modules") or []),
        },
    }


def build_report_config(prefix):
    paths = {
        "analysis": f"../{prefix}_analysis_config.json",
        "performance": f"../{prefix}_perf_data.json",
        "timeline": f"../{prefix}_timeline.json",
        "trace": "../trace_view.json",
        "bindings": "./outputs/trace_bindings.json",
        "architecture": "./outputs/model_architecture_graph.json",
        "overlay": "./outputs/architecture_overlay_map.json",
        "hbm": "./outputs/hbm_series.json",
    }
    return ("window.ReportRuntimeConfig = "
            + json.dumps(paths, indent=2, ensure_ascii=False) + ";\n")


#: An empty-but-valid HBM series. The panel is optional; a capture with no HBM CSV needs a
#: schema-valid file so the runtime reports "unavailable" instead of failing to load.
EMPTY_HBM = {
    "schema_version": "1.0",
    "time": {"unit": "us", "origin": "decode_start", "origin_epoch_us": 0},
    "bandwidth": {"unit": "GB/s",
                  "point_fields": ["time_us", "read_gbs", "write_gbs", "phase", "step",
                                   "attributed_label", "window_busy_pct"],
                  "points": []},
    "occupancy": {"unit": "GiB",
                  "point_fields": ["time_us", "hbm_gib", "event", "phase"],
                  "points": []},
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--performance", required=True)
    parser.add_argument("--graph", required=True)
    parser.add_argument("--repo", required=True, help="report repository root")
    parser.add_argument("--file-prefix", help="backend filename prefix; defaults to model_id")
    parser.add_argument("--write-empty-hbm", action="store_true",
                        help="write a schema-valid empty hbm_series.json when absent")
    args = parser.parse_args()

    analysis = jload(args.analysis)
    performance = jload(args.performance)
    overlay = build_overlay(analysis, performance, jload(args.graph))

    outputs = os.path.join(args.repo, "report", "outputs")
    os.makedirs(outputs, exist_ok=True)
    overlay_path = os.path.join(outputs, "architecture_overlay_map.json")
    with open(overlay_path, "w", encoding="utf-8") as handle:
        json.dump(overlay, handle, ensure_ascii=False, indent=1)
        handle.write("\n")

    prefix = args.file_prefix or analysis["model_id"]
    config_path = os.path.join(args.repo, "report", "report-config.js")
    with open(config_path, "w", encoding="utf-8") as handle:
        handle.write(build_report_config(prefix))

    hbm_path = os.path.join(outputs, "hbm_series.json")
    wrote_hbm = False
    if args.write_empty_hbm and not os.path.exists(hbm_path):
        with open(hbm_path, "w", encoding="utf-8") as handle:
            json.dump(EMPTY_HBM, handle, ensure_ascii=False, indent=1)
            handle.write("\n")
        wrote_hbm = True

    logger.info("WROTE %s", overlay_path)
    logger.info("  mappings %s  source_only %s  all classified %s",
                len(overlay["mappings"]), len(overlay["source_only_nodes"]),
                overlay["validation"]["all_backend_nodes_classified"])
    logger.info("WROTE %s  (prefix %s)", config_path, prefix)
    if wrote_hbm:
        logger.info("WROTE %s  (empty: this capture has no HBM samples)", hbm_path)


if __name__ == "__main__":
    sys.exit(breakdown_paths.run_cli(main))
