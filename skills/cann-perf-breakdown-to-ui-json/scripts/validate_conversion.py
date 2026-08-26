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
"""Check a conversion against the UI skill's contract before handing it off.

These are the invariants the report runtime and its validators assume. Catching a
break here names the offending node; catching it downstream only says a count is
wrong. The UI Skill's own validators remain authoritative for the report itself.
"""
import argparse
import glob
import json
import logging
import os
import sys

import breakdown_paths


logger = logging.getLogger(__name__)

# A key must be written even when its value is null, because absence means the pipeline
# forgot to ask while null means the capture did not measure it.
REQUIRED_METRIC_KEYS = ("time_us", "time_pct", "nops", "hbm_mb",
                        "mfu_int8_pct", "mfu_bf16_pct", "metric_scope", "op_ratio",
                        "aicore_time_us", "mac_ratio", "mte2_ratio")
# Counter-aware facts use counter_coverage as their shape marker. Earlier facts legitimately
# predate these fields, so the extended tuple is required only when that marker is present.
COUNTER_METRIC_KEYS = ("aiv_time_us", "aicore_time_pct", "cube_utilization_pct",
                       "aic_total_cycles", "aicore_cycle_time_us", "counter_coverage")
COUNTER_SHAPE_MARKER = "counter_coverage"


def jload(path):
    with open(path) as handle:
        return json.load(handle)


def find_one(out_dir, suffix):
    matches = sorted(glob.glob(os.path.join(out_dir, f"*{suffix}")))
    if not matches:
        raise breakdown_paths.ConversionError(f"no *{suffix} in {out_dir}")
    if len(matches) > 1:
        raise breakdown_paths.ConversionError(f"ambiguous *{suffix} in {out_dir}: {matches}")
    return matches[0]


def collect(node, out, key="node_id"):
    """Depth-first walk collecting every dict that carries `key`."""
    if isinstance(node, dict):
        if key in node:
            out.append(node)
        for value in node.values():
            collect(value, out, key)
    elif isinstance(node, list):
        for item in node:
            collect(item, out, key)
    return out


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="conversion output directory")
    parser.add_argument("--breakdown", help="cross-check kernel conservation")
    parser.add_argument("--attribution", help="kernel_attribution.json")
    parser.add_argument("--config", help="analysis_config_v2.json; required for model outputs")
    return parser.parse_args()


class ConversionValidator:
    """Accumulate independent conversion contract checks."""

    def __init__(self, args):
        self.args = args
        self.analysis = jload(find_one(args.out, "_analysis_config.json"))
        self.performance = jload(find_one(args.out, "_perf_data.json"))
        self.timeline = jload(find_one(args.out, "_timeline.json"))
        graph_path = os.path.join(args.out, "outputs/model_architecture_graph.json")
        self.graph = jload(graph_path) if os.path.exists(graph_path) else None
        self.checks = []
        self.analysis_nodes = [item["node_id"] for item in collect(self.analysis, [])]
        self.perf_nodes = [item["node_id"] for item in collect(self.performance, [])]
        self.analysis_set = set(self.analysis_nodes)
        self.perf_set = set(self.perf_nodes)
        events = self.timeline.get("events") if isinstance(self.timeline, dict) else self.timeline
        self.events = events or []

    @staticmethod
    def carries_counter(row):
        keys = ("aicore_time_us", "aiv_time_us", "aic_total_cycles", "aiv_total_cycles")
        return any(row.get(key) is not None for key in keys)

    def check(self, ok, label, detail=""):
        self.checks.append({"ok": bool(ok), "check": label, "detail": detail})

    def check_identity(self):
        for field in ("model_id", "report_id", "representative_step"):
            values = {
                "analysis": self.analysis.get(field),
                "performance": self.performance.get(field),
                "timeline": self.timeline.get(field),
            }
            identical = len(set(map(repr, values.values()))) == 1
            self.check(identical, f"{field} identical across the three facts",
                       "" if identical else repr(values))

    def check_node_sets(self):
        duplicates = {node for node in self.analysis_nodes
                      if self.analysis_nodes.count(node) > 1}
        self.check(not duplicates, "one analysis definition per node_id",
                   f"duplicated: {sorted(duplicates)}" if duplicates else "")
        duplicates = {node for node in self.perf_nodes if self.perf_nodes.count(node) > 1}
        self.check(not duplicates, "one performance record per node_id",
                   f"duplicated: {sorted(duplicates)}" if duplicates else "")
        orphans = sorted(self.perf_set - self.analysis_set)
        self.check(not orphans, "every performance node exists in analysis",
                   f"missing from analysis: {orphans}" if orphans else "")

    def check_source_only_nodes(self):
        entries = self.analysis.get("source_only_structure") or []
        source_only = [entry.get("structure_node_id") for entry in entries]
        leaked = sorted(set(source_only) & self.perf_set)
        self.check(not leaked, "no source-only node carries metrics",
                   f"present in performance: {leaked}" if leaked else "")
        miskeyed = [entry for entry in entries if "node_id" in entry]
        detail = (f"{len(miskeyed)} entr(ies) use node_id and would enter the backend index"
                  if miskeyed else "")
        self.check(not miskeyed, "source-only entries use structure_node_id, not node_id", detail)
        unreasoned = [entry.get("structure_node_id") for entry in entries
                      if not str(entry.get("reason") or "").strip()]
        self.check(not unreasoned, "every source-only node records a reason",
                   f"missing reason: {unreasoned}" if unreasoned else "")

    def check_metric_shape(self):
        records = collect(self.performance, [])
        counter_aware = any(COUNTER_SHAPE_MARKER in record for record in records)
        required = REQUIRED_METRIC_KEYS + (COUNTER_METRIC_KEYS if counter_aware else ())
        missing = {}
        for record in records:
            absent = [key for key in required if key not in record]
            if absent:
                missing[record["node_id"]] = absent
        label = ("every performance record declares all metric keys"
                 + (" (incl. AI Core counters)" if counter_aware else " (pre-counter facts)"))
        detail = (f"{len(missing)} record(s) incomplete, e.g. "
                  f"{list(missing.items())[:2]}" if missing else "")
        self.check(not missing, label, detail)
        bad_scope = []
        for record in records:
            sampled = record.get("metric_scope") == "sampled_window_context"
            if sampled and record.get("time_us") is not None:
                bad_scope.append(record["node_id"])
        self.check(not bad_scope, "sampled-window nodes report time_us as null",
                   f"{bad_scope}" if bad_scope else "")

    def check_timeline(self):
        owners = [event.get("owner_node_id") for event in self.events
                  if event.get("owner_node_id")]
        unresolved = sorted({owner for owner in owners if owner not in self.analysis_set})
        self.check(not unresolved, "every timeline owner resolves in analysis",
                   f"unresolved: {unresolved[:5]}" if unresolved else "")
        detail = (f"{len(self.events) - len(owners)} event(s) unowned"
                  if len(owners) != len(self.events) else "")
        self.check(len(owners) == len(self.events), "every timeline event has an owner", detail)

    def check_attribution(self):
        path = self.args.attribution
        if not (path and os.path.exists(path)):
            return
        attribution = jload(path)
        attributed = attribution["summary"]["kernels_attributed"]
        compute_events = [event for event in self.events
                          if event.get("mapping_status") != "sample_window_phase_owner"]
        detail = (f"timeline {len(compute_events)} vs attributed {attributed}"
                  if len(compute_events) != attributed else "")
        self.check(len(compute_events) == attributed,
                   "timeline compute events match attributed kernels", detail)
        coverage = attribution["summary"]["coverage_pct"]
        self.check(coverage == 100.0, "kernel attribution coverage is 100%", f"{coverage}%")

    def check_graph_shape(self):
        if self.graph is None:
            return
        self.check(self.graph.get("schema_version") == "model_architecture_graph.v1",
                   "graph declares the v1 contract",
                   f"found {self.graph.get('schema_version')!r}")
        roots = self.graph.get("roots") or []
        root_ids = {root.get("id") if isinstance(root, dict) else root for root in roots}
        self.check(bool(roots), "graph roots are nonempty")
        for required in ("section/source_architecture", "section/runtime_auxiliary"):
            self.check(required in root_ids, f"graph declares {required}")
        edges = self.graph.get("edges") or []
        self.check(bool(edges), "graph declares explicit edges")
        thin = [edge.get("id") for edge in edges
                if not edge.get("tensor") or not (edge.get("provenance") or [])]
        self.check(not thin, "every edge carries tensor metadata and provenance",
                   f"{len(thin)} thin edge(s), e.g. {thin[:3]}" if thin else "")

    def check_graph_mapping(self):
        if self.graph is None:
            return
        items = collect(self.graph, [], key="backendNodeId")
        dangling = sorted({item["backendNodeId"] for item in items
                           if item["backendNodeId"] not in self.analysis_set})
        self.check(not dangling, "every graph backendNodeId resolves in analysis",
                   f"dangling: {dangling[:5]}" if dangling else "")
        heated = [item.get("id") for item in collect(self.graph, [], key="id")
                  if item.get("dataState") == "source_only" and item.get("backendNodeId")]
        self.check(not heated, "source-only graph items carry no backendNodeId",
                   f"{heated[:5]}" if heated else "")

    def check_device_profile(self):
        profile = self.performance.get("device_profile")
        frequency = self.performance.get("aicore_freq_mhz")
        if profile is None:
            self.check(frequency is None, "no device_profile means no clock is claimed",
                       f"freq={frequency!r}")
            return
        self.check(profile.get("aicore_freq_mhz") == frequency,
                   "top-level aicore_freq_mhz matches device_profile",
                   f"{frequency!r} vs {profile.get('aicore_freq_mhz')!r}")
        basis = profile.get("aicore_freq_basis")
        self.check(basis in ("derived", "declared", "unavailable"),
                   "clock basis is a known provenance", repr(basis))
        cross_check = profile.get("cross_check") or {}
        agreement = cross_check.get("agreement")
        self.check(agreement != "mismatch",
                   "declared and derived clocks agree within tolerance",
                   f"agreement={agreement}, delta_pct={cross_check.get('delta_pct')}")

    def check_counter_drift(self):
        frequency = self.performance.get("aicore_freq_mhz")
        if not frequency:
            return
        drift = []
        pairs = (("aicore_time_us", "aicore_cycle_time_us"),
                 ("aiv_time_us", "aiv_cycle_time_us"))
        for module in self.performance.get("modules") or []:
            for time_key, cycle_key in pairs:
                reported, implied = module.get(time_key), module.get(cycle_key)
                if not reported or implied is None:
                    continue
                delta = 100.0 * abs(implied - reported) / reported
                if delta > 1.0:
                    drift.append(f"{module['node_id']}:{time_key} {delta:.2f}%")
        detail = (f"{len(drift)} module-metric(s) off by >1%, e.g. {drift[:3]}"
                  if drift else "")
        self.check(not drift, "cycle-implied time reconciles with reported counter time", detail)

    def check_counter_ranges(self):
        modules = self.performance.get("modules") or []
        bad_ratio = []
        keys = ("mac_ratio", "mte2_ratio", "mte1_ratio", "scalar_ratio",
                "fixpipe_ratio", "vec_ratio", "aiv_mte2_ratio")
        for module in modules:
            for key in keys:
                value = module.get(key)
                if value is not None and not 0.0 <= value <= 1.0:
                    bad_ratio.append(f"{module['node_id']}:{key}={value}")
        self.check(not bad_ratio, "every pipeline ratio lies in [0,1]",
                   f"{len(bad_ratio)} out of range, e.g. {bad_ratio[:3]}"
                   if bad_ratio else "")
        fabricated = []
        for module in modules:
            coverage = (module.get("counter_coverage") or {}).get("kernels_with_counters")
            if coverage == 0 and module.get("aicore_time_us") is not None:
                fabricated.append(module["node_id"])
        self.check(not fabricated, "no counter metric without a counter-bearing kernel",
                   f"{fabricated[:5]}" if fabricated else "")

    def check_duplicate_counters(self):
        path = self.args.attribution
        if not (path and os.path.exists(path)):
            return
        rows = {row["op_index"]: row for row in jload(path)["rows"]}
        both = []
        for index, row in rows.items():
            duplicate_of = row.get("duplicate_of")
            duplicate = rows.get(duplicate_of, {})
            if (duplicate_of is not None and self.carries_counter(row)
                    and self.carries_counter(duplicate)):
                both.append(index)
        detail = (f"{len(both)} pair(s) carry counters on both rows, so counter sums would "
                  f"double-count: op {both[:5]}" if both else "")
        self.check(not both, "a duplicated collective reports counters on one row only", detail)

    def check_inventory_shape(self, inventory):
        declared = inventory.get("declared") or {}
        counts = inventory.get("counts") or {}
        experts = inventory.get("experts") or []
        total = declared.get("total")
        self.check(total == len(experts), f"the inventory lists all {total} declared experts",
                   "" if total == len(experts)
                   else f"declared {total} but listed {len(experts)}")
        bucketed = 0
        for key in ("individually_measured", "fused_measured",
                    "residency_unresolved", "remote_ep_shard"):
            bucketed += counts.get(key) or 0
        detail = "" if bucketed == len(experts) else (
            f"buckets sum to {bucketed}, listed {len(experts)}")
        self.check(bucketed == len(experts),
                   "every expert falls in exactly one data_state bucket", detail)

    def check_inventory_measurements(self, inventory):
        experts = inventory.get("experts") or []
        fabricated = []
        for expert in experts:
            if (expert.get("data_state") != "measured"
                    and expert.get("time_us") is not None):
                fabricated.append(expert["expert_id"])
        self.check(not fabricated,
                   "no per-expert time unless that expert was individually measured",
                   f"{len(fabricated)} fabricated, e.g. {fabricated[:3]}"
                   if fabricated else "")
        dangling_nodes = set()
        for expert in experts:
            for node in expert.get("measured_by_node_id") or []:
                if node not in self.perf_set:
                    dangling_nodes.add(node)
        dangling = sorted(dangling_nodes)
        self.check(not dangling, "every measured_by_node_id resolves in the perf facts",
                   f"dangling: {dangling[:3]}" if dangling else "")

    def check_inventory_residency(self, inventory):
        parallelism = inventory.get("expert_parallelism") or {}
        if parallelism.get("ep_rank") is not None:
            return
        counts = inventory.get("counts") or {}
        valid = (parallelism.get("resident_expert_indices") is None
                 and counts.get("fused_measured") == 0)
        detail = (f"indices={parallelism.get('resident_expert_indices')}, "
                  f"fused_measured={counts.get('fused_measured')}")
        self.check(valid, "without ep_rank, no expert identity is asserted as resident", detail)

    def check_inventory(self):
        matches = glob.glob(os.path.join(self.args.out, "*_expert_inventory.json"))
        config = jload(self.args.config) if self.args.config else None
        architecture = (config or {}).get("architecture") or {}
        declared_experts = sum(int(architecture.get(key) or 0)
                               for key in ("n_routed_experts", "n_shared_experts"))
        if config is not None:
            valid = declared_experts == 0 or len(matches) == 1
            detail = (f"model declares {declared_experts} experts but found "
                      f"{len(matches)} inventory files"
                      if declared_experts and len(matches) != 1 else "")
            self.check(valid, "expert inventory exists when the model declares experts", detail)
        if not matches:
            return
        inventory = jload(sorted(matches)[0])
        self.check_inventory_shape(inventory)
        self.check_inventory_measurements(inventory)
        self.check_inventory_residency(inventory)

    def run_checks(self):
        self.check_identity()
        self.check_node_sets()
        self.check_source_only_nodes()
        self.check_metric_shape()
        self.check_timeline()
        self.check_attribution()
        self.check_graph_shape()
        self.check_graph_mapping()
        self.check_device_profile()
        self.check_counter_drift()
        self.check_counter_ranges()
        self.check_duplicate_counters()
        self.check_inventory()

    def report(self):
        failures = [check for check in self.checks if not check["ok"]]
        for item in self.checks:
            logger.info("%s  %s%s", "PASS" if item["ok"] else "FAIL", item["check"],
                        f"  — {item['detail']}" if item["detail"] else "")
        logger.info("")
        logger.info("%d passed / %d failed", len(self.checks) - len(failures), len(failures))
        if failures:
            logger.info("\nFix the conversion. Do not satisfy a check by generating data the "
                        "capture does not contain.")
            return 1
        logger.info("\nConversion is self-consistent. Hand off to the UI skill's validators, "
                    "which are authoritative for the report.")
        return 0

    def run(self):
        self.run_checks()
        return self.report()


def main():
    return ConversionValidator(parse_args()).run()


if __name__ == "__main__":
    sys.exit(breakdown_paths.run_cli(main))
