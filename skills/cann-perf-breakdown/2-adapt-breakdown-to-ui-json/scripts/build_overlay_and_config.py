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
"""Emit the architecture overlay and Skill 3 runtime/handoff configuration.

Both are mechanical, but the UI skill only ships model-specific generators for them
(`build-source-overlay.mjs` hardcodes one model's source hashes and layer layout;
`build-qwen-hbm-demo.mjs` writes `report-config.js` for one model), so any other model had to
have them hand-written. These derive from the already-emitted facts:

- overlay: every performance node maps to the graph item with the same id. The mapping kind and
  evidence come from that item, not from a guess about what the node is.
- report-config: the runtime path manifest. Filenames are model-specific by design, which is
  exactly why they belong in this file and nowhere else.
"""
import argparse
import json
import os


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
            raise SystemExit(f"performance node absent from architecture graph: {node_id}")
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


def build_handoff(prefix, analysis, performance, graph, model_source=None,
                  extractor_model=None, expert_inventory=None):
    source_of_truth = (analysis.get("architecture") or {}).get("source_of_truth") or []
    model_source = model_source or next(
        (source for source in source_of_truth if isinstance(source, str) and source.strip()), None
    )
    if not model_source:
        raise SystemExit("Skill 3 handoff requires model source provenance")
    generation = analysis.get("generation_provenance") or {}
    extractor_model = (
        extractor_model
        or generation.get("extractorModel")
        or generation.get("extractor_model")
        or "perf-breakdown-skill"
    )
    repeated_layers = any(
        int(item.get("repeatCount") or 0) > 1
        for root in graph.get("roots") or []
        for item in walk(root, [])
    )
    derived_frequency = (performance.get("device_profile") or {}).get("derived") or {}
    has_derived_frequency_range = all(
        isinstance(derived_frequency.get(key), (int, float))
        and derived_frequency[key] > 0
        for key in ("min_mhz", "max_mhz")
    )
    capabilities = {
        "repeatedLayers": repeated_layers,
        "expertInventory": bool(expert_inventory and os.path.isfile(expert_inventory)),
        "aicoreFrequency": has_derived_frequency_range,
    }
    return {
        "schema_version": "ui_report_handoff.v1",
        "model_family": analysis.get("model_name") or analysis["model_id"],
        "skill3_adapter": "generic",
        "inputs": {
            "analysis": f"../{prefix}_analysis_config.json",
            "performance": f"../{prefix}_perf_data.json",
            "timeline": f"../{prefix}_timeline.json",
            "trace": "../trace_view.json",
            "bindings": "./outputs/trace_bindings.json",
            "architecture": "./outputs/model_architecture_graph.json",
            "overlay": "./outputs/architecture_overlay_map.json",
        },
        "optional_inputs": {
            "operator_details": "./outputs/operator_details.json",
            "hbm": "./outputs/hbm_series.json",
            "findings": "./outputs/metrics_findings.json",
            "expert_inventory": "./outputs/expert_inventory.json",
        },
        "capabilities": capabilities,
        "provenance": {
            "skills": ["cann-perf-breakdown", "cann-perf-breakdown-to-ui-json"],
            "modelSource": model_source,
            "extractorModel": extractor_model,
        },
    }


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
    parser.add_argument("--model-source",
                        help="model source provenance; defaults to architecture.source_of_truth")
    parser.add_argument("--extractor-model",
                        help="agent/model that produced the reviewed breakdown")
    parser.add_argument("--expert-inventory",
                        help="generated expert inventory; declares the capability when present")
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

    handoff_path = os.path.join(args.repo, "ui-report-handoff.json")
    handoff = build_handoff(
        prefix, analysis, performance, jload(args.graph), args.model_source,
        args.extractor_model, args.expert_inventory
    )
    with open(handoff_path, "w", encoding="utf-8") as handle:
        json.dump(handoff, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    hbm_path = os.path.join(outputs, "hbm_series.json")
    wrote_hbm = False
    if args.write_empty_hbm and not os.path.exists(hbm_path):
        with open(hbm_path, "w", encoding="utf-8") as handle:
            json.dump(EMPTY_HBM, handle, ensure_ascii=False, indent=1)
            handle.write("\n")
        wrote_hbm = True

    print(f"WROTE {overlay_path}")
    print(f"  mappings {len(overlay['mappings'])}"
          f"  source_only {len(overlay['source_only_nodes'])}"
          f"  all classified {overlay['validation']['all_backend_nodes_classified']}")
    print(f"WROTE {config_path}  (prefix {prefix})")
    print(f"WROTE {handoff_path}  (ui_report_handoff.v1)")
    if wrote_hbm:
        print(f"WROTE {hbm_path}  (empty: this capture has no HBM samples)")


if __name__ == "__main__":
    main()
