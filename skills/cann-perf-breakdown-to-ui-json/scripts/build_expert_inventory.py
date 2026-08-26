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
"""Emit the MoE expert inventory: every declared expert, and what the capture measured.

The source declares 256 routed experts plus 1 shared expert per MoE layer. A capture almost
never contains 257 separable measurements, for two independent reasons that must not be
conflated:

1. **Expert parallelism.** With `moe_ep_size = N` only `n_routed_experts / N` experts have
   weights resident on the profiled rank. The rest execute on other ranks and appear in this
   capture only as the all-to-all that dispatches tokens to them. They are declared, not
   observed, and their time is unknown rather than zero.

2. **Kernel fusion.** The resident experts run as a single `GroupedMatmul` over a stacked
   weight tensor, with a `group_list` giving each expert's token count. One kernel, one
   duration. Per-expert time is not recoverable from it by any arithmetic the profiler
   supports — splitting the fused duration by token count would fabricate per-expert numbers
   that read as measurements.

So this emits an inventory, not a per-expert breakdown: each expert gets an identity and a
`data_state` saying precisely why it carries no metrics. `measured` belongs only to the fused
group node that actually owns a kernel. A UI can then show all 257 and be honest about which
one figure covers which experts, instead of silently showing 1 of 257 or inventing 257.

Residency is derived from the weight tensor's leading dimension in the GroupedMatmul shapes,
which is the profiled rank's own local expert count — an observation, not a config assumption.
"""
import argparse
import logging
import os
import sys

import breakdown_paths


logger = logging.getLogger(__name__)

#: Kernels whose stacked weight leading dim reveals the rank's local expert count.
GROUPED_OP_TYPES = ("GroupedMatmul", "GroupedMatmulV2", "GroupedMatMul")


def observed_local_experts(rows):
    """Local expert count from the GroupedMatmul weight tensor's leading dimension.

    A stacked expert weight enters as `[local_experts, ...]`. The activation is `[tokens, hidden]`
    and the group_list is 1-D, so the weight is identified as the first input with rank >= 3 —
    which holds for both the plain `[E, K, N]` layout and the fractal-Z quantised
    `[E, K1, N1, k0, n0]` one seen on Ascend W8A8 captures.

    Returns (count, evidence) or (None, reason). Disagreement across kernels is reported rather
    than resolved: it means the layers do not share one EP topology and no single count is right.
    """
    counts = {}
    for row in rows:
        if str(row.get("op_type") or "") not in GROUPED_OP_TYPES:
            continue
        for shape in row.get("input_shapes") or []:
            if isinstance(shape, list) and len(shape) >= 3 and isinstance(shape[0], int):
                counts.setdefault(shape[0], []).append(row.get("op_index"))
                break

    if not counts:
        return None, "no GroupedMatmul kernel carried a stacked expert weight shape"
    if len(counts) > 1:
        return None, (f"GroupedMatmul kernels disagree on local expert count "
                      f"{sorted(counts)}; the layers do not share one EP topology")
    local = next(iter(counts))
    ops = counts.get(local, [])
    return local, (f"leading dim of the stacked expert weight in {len(ops)} GroupedMatmul "
                   f"kernel(s), e.g. op {ops[0]}")


def find_expert_nodes(modules, semantic_key):
    """Performance records for a given expert semantic key, one per MoE-bearing scope."""
    return [m for m in modules if str(m.get("node_id", "")).endswith("/" + semantic_key)]


def manifest_facts(manifest):
    """Flatten the manifest's `facts` list to {key: (value, source_ref)}.

    Stage 1 records each fact with the source line it was read from. Carrying the ref through
    means the inventory can cite where 256 came from rather than asserting it.
    """
    out = {}
    for fact in (manifest or {}).get("facts") or []:
        key = fact.get("key")
        if key is not None and isinstance(fact.get("value"), int):
            out[key] = (fact["value"], fact.get("source_ref"))
    return out


def declared_expert_facts(config, manifest):
    architecture = config.get("architecture") or {}
    facts = manifest_facts(manifest)
    declared = {}
    for key in ("n_routed_experts", "n_shared_experts", "num_experts_per_tok"):
        value, source_ref = facts.get(key, (None, None))
        declared[key] = architecture.get(key) if value is None else value
        declared[f"{key}_source_ref"] = source_ref
    return declared


def routing_facts(declared_routed, rows, ep_rank):
    local, evidence = observed_local_experts(rows)
    ep_size = None
    if declared_routed and local and declared_routed % local == 0:
        ep_size = declared_routed // local
    known_rank = ep_rank is not None
    base = (ep_rank * local) if (known_rank and local) else 0
    return {
        "local": local, "evidence": evidence, "ep_size": ep_size,
        "known_rank": known_rank, "ep_rank": ep_rank, "base": base,
    }


def routed_state(index, routing):
    local, base = routing["local"], routing["base"]
    resident = bool(routing["known_rank"] and local is not None and base <= index < base + local)
    slot = index - base if resident else None
    unresolved = not routing["known_rank"] and local is not None and index < local
    if resident:
        reason = ("Runs inside the fused GroupedMatmul covering all "
                  f"{local} experts resident on this rank (local slot {slot}). The kernel "
                  "reports one duration for the group; per-expert time is not separable from it.")
        return "fused_measured", reason, resident, slot
    if unresolved:
        reason = (f"This capture has {local} resident routed experts, but it does not record "
                  "which expert-parallel rank produced it, so which global indices those are "
                  f"is unknown. Pass --ep-rank to resolve. Listed here as one of the first {local} "
                  "entries only as a placeholder for the resident slot count, not as a claim "
                  "that this expert ran.")
        return "residency_unresolved", reason, resident, slot
    ep_note = f" (moe_ep_size={routing['ep_size']})" if routing["ep_size"] else ""
    reason = ("Weights live on a different expert-parallel rank" + ep_note
              + ". This capture profiles one rank, so this expert's time is unknown; "
                "the all-to-all dispatch is the only trace of it here.")
    return "remote_ep_shard", reason, resident, slot


def routed_experts(count, routing, routed_nodes):
    experts = []
    for index in range(int(count or 0)):
        state, reason, resident, slot = routed_state(index, routing)
        node_ids = [node["node_id"] for node in routed_nodes]
        experts.append({
            "expert_id": f"routed/{index}", "expert_index": index, "kind": "routed",
            "data_state": state, "local_slot": slot,
            "resident_on_profiled_rank": resident,
            "measured_by_node_id": node_ids if state == "fused_measured" else [],
            "time_us": None, "reason": reason,
        })
    return experts


def shared_experts(count, shared_nodes):
    measured = bool(shared_nodes)
    measured_times = [node["time_us"] for node in shared_nodes if node.get("time_us") is not None]
    time_us = round(sum(measured_times), 4) if measured and measured_times else None
    reason = ("Replicated on every rank and executed by its own kernels, so its time is "
              "directly measured rather than fused with the routed group." if measured else
              "Declared in the source but no kernel was attributed to it in this capture.")
    experts = []
    for index in range(int(count or 0)):
        experts.append({
            "expert_id": f"shared/{index}", "expert_index": index, "kind": "shared",
            "data_state": "measured" if measured else "source_only",
            "resident_on_profiled_rank": True,
            "measured_by_node_id": [node["node_id"] for node in shared_nodes],
            "time_us": time_us, "reason": reason,
        })
    return experts


def parallelism_document(declared_routed, routing):
    local, base = routing["local"], routing["base"]
    known_rank, ep_rank = routing["known_rank"], routing["ep_rank"]
    identity_note = (f"Rank {ep_rank} owns global routed experts {base}-{base + local - 1}."
                     if known_rank and local else
                     "The capture does not record ep_rank, so the resident expert COUNT is "
                     "known but their global indices are not. Rank r owns [r*local, "
                     "(r+1)*local); pass --ep-rank to resolve identities.")
    note = (f"{local} of {declared_routed} routed experts have weights on the profiled rank. "
            f"The other {declared_routed - local} execute elsewhere and are declared, not observed."
            if local and declared_routed else
            "Expert residency could not be established from this capture.")
    return {
        "moe_ep_size": routing["ep_size"], "local_routed_experts": local,
        "residency_evidence": routing["evidence"], "ep_rank": ep_rank,
        "ep_rank_source": "--ep-rank" if known_rank else None,
        "resident_expert_indices": [base, base + local - 1] if known_rank and local else None,
        "identity_note": identity_note, "note": note,
    }


def inventory_counts(experts, declared_total):
    states = [expert["data_state"] for expert in experts]
    return {
        "declared_total": declared_total,
        "resident_on_profiled_rank": sum(1 for expert in experts
                                         if expert["resident_on_profiled_rank"]),
        "individually_measured": states.count("measured"),
        "fused_measured": states.count("fused_measured"),
        "residency_unresolved": states.count("residency_unresolved"),
        "remote_ep_shard": states.count("remote_ep_shard"),
    }


def fused_group_nodes(routed_nodes, local):
    return [{
        "node_id": node["node_id"], "time_us": node.get("time_us"),
        "nops": node.get("nops"), "covers_experts": local,
        "note": f"One measurement covering all {local} resident routed experts.",
    } for node in routed_nodes]


def build(config, performance, attribution, manifest=None, ep_rank=None):
    declared = declared_expert_facts(config, manifest)
    routed_count = declared["n_routed_experts"]
    shared_count = declared["n_shared_experts"]
    declared_total = (int(routed_count or 0) + int(shared_count or 0)) or None
    routing = routing_facts(routed_count, attribution.get("rows") or [], ep_rank)
    modules = performance.get("modules") or []
    routed_nodes = find_expert_nodes(modules, "routed_experts")
    shared_nodes = find_expert_nodes(modules, "shared_expert")
    experts = routed_experts(routed_count, routing, routed_nodes)
    experts.extend(shared_experts(shared_count, shared_nodes))
    return {
        "schema_version": 1, "model_id": performance.get("model_id"),
        "report_id": performance.get("report_id"),
        "representative_step": performance.get("representative_step"),
        "declared": declared_document(declared, declared_total),
        "expert_parallelism": parallelism_document(routed_count, routing),
        "measurability": measurability_document(),
        "counts": inventory_counts(experts, declared_total),
        "fused_group_nodes": fused_group_nodes(routed_nodes, routing["local"]),
        "experts": experts,
    }


def declared_document(declared, total):
    return {
        "routed_experts": declared["n_routed_experts"],
        "shared_experts": declared["n_shared_experts"], "total": total,
        "experts_per_token": declared["num_experts_per_tok"],
        "source_refs": {
            key: declared[f"{key}_source_ref"]
            for key in ("n_routed_experts", "n_shared_experts", "num_experts_per_tok")
        },
        "source": "model source via stage 1 AST extraction; never inferred from kernel "
                  "shapes, which only ever show this rank's slice",
    }


def measurability_document():
    return {
        "separable_per_expert": False,
        "reason": "The resident routed experts execute as one GroupedMatmul over a stacked "
                  "weight, with group_list giving per-expert token counts. The profiler "
                  "reports a single duration for that kernel. Dividing it by token share "
                  "would produce per-expert numbers the hardware never measured.",
        "what_would_be_needed": "Per-expert kernels (unfused MoE), or a profiler that emits "
                                "per-group timing inside GroupedMatmul.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--breakdown", required=True)
    parser.add_argument("--config", help="explicit breakdown config path")
    parser.add_argument("--performance", required=True, help="*_perf_data.json")
    parser.add_argument("--attribution", required=True, help="kernel_attribution.json")
    parser.add_argument("--manifest", help="model_manifest.json; defaults to "
                                           "<breakdown>/model_manifest.json")
    parser.add_argument("--ep-rank", type=int,
                        help="expert-parallel rank this capture came from. Resolves WHICH "
                             "global expert indices are resident; without it only the count "
                             "is reported, since the capture does not record the rank.")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    config = breakdown_paths.load_json(
        breakdown_paths.config_or_die(args.breakdown, args.config)
    )
    performance = breakdown_paths.load_json(args.performance)
    attribution = breakdown_paths.load_json(args.attribution)

    manifest_path = args.manifest or os.path.join(args.breakdown, "model_manifest.json")
    manifest = (breakdown_paths.load_json(manifest_path)
                if os.path.exists(manifest_path) else None)

    inventory = build(config, performance, attribution, manifest, args.ep_rank)
    if not inventory["declared"]["total"]:
        logger.info("no MoE experts declared in this model; nothing to inventory")
        return 0

    breakdown_paths.dump_json(inventory, args.out)
    counts = inventory["counts"]
    ep = inventory["expert_parallelism"]
    logger.info("WROTE %s", args.out)
    logger.info("declared %s experts (%s routed + %s shared)",
                counts["declared_total"], inventory["declared"]["routed_experts"],
                inventory["declared"]["shared_experts"])
    logger.info("moe_ep_size %s, %s routed experts resident on the profiled rank",
                ep["moe_ep_size"], ep["local_routed_experts"])
    logger.info("individually measured %s, fused %s, residency unresolved %s, remote %s",
                counts["individually_measured"], counts["fused_measured"],
                counts["residency_unresolved"], counts["remote_ep_shard"])
    if counts["residency_unresolved"]:
        logger.info("NOTE the capture does not record ep_rank; pass --ep-rank to resolve which "
                    "global expert indices are resident")
    return 0


if __name__ == "__main__":
    sys.exit(breakdown_paths.run_cli(main))
