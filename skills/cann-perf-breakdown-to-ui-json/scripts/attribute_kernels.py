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
"""Attribute every representative-step kernel to exactly one UI node.

Evidence, in order of authority:

1. A leaf's own `op_indices` — the breakdown already proved these.
2. `trace_instances[].op_range` — a repeated group's representative leaf offsets
   translate to every other invocation by range arithmetic, so all 32 layers
   inherit attribution without a single name comparison.
3. An explicit profile assertion from a rules file, for runs the breakdown folded
   into one leaf that the report needs split.

Never leaf-label similarity. Every kernel is claimed exactly once or the run
fails; a remainder is a defect, not a rounding difference.
"""
import argparse
import collections
import json
import logging
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass

import breakdown_paths


logger = logging.getLogger(__name__)


#: AI Core / AI Vector counter fields carried from the kernel CSV onto every attributed row,
#: so a node's metrics can report measured device behaviour instead of only wall duration.
#: Names are the analyze_kernels JSON keys, kept verbatim rather than renamed: `mac_ratio`
#: without the `aic_` prefix reads as if it covered the vector core too, and the AIV pipeline
#: has its own separate ratios.
COUNTER_FIELDS = (
    "aicore_time_us",
    "aic_total_cycles",
    "aic_mac_time_us", "aic_mac_ratio",
    "aic_mte1_time_us", "aic_mte1_ratio",
    "aic_mte2_time_us", "aic_mte2_ratio",
    "aic_scalar_time_us", "aic_scalar_ratio",
    "aic_fixpipe_time_us", "aic_fixpipe_ratio",
    "aic_icache_miss_rate",
    "aiv_time_us",
    "aiv_total_cycles",
    "aiv_vec_time_us", "aiv_vec_ratio",
    "aiv_mte2_time_us", "aiv_mte2_ratio",
    "aiv_mte3_time_us", "aiv_mte3_ratio",
    "aiv_scalar_time_us", "aiv_scalar_ratio",
    "aiv_icache_miss_rate",
    "cube_utilization_pct",
    "block_dim", "mix_block_dim",
    "wait_time_us",
)


def load_counters(details_path):
    """Map op index -> counter fields from raw_ops_details.json.

    `raw_ops.json` carries only identity and timing; the AI Core counters live in the details
    file. Reading the wrong one is why every node's counter metric emitted as null while the
    data sat on disk. Returns an empty map when the file is absent, so a capture profiled
    without counters still attributes normally and reports those metrics as unavailable.
    """
    if not details_path or not os.path.exists(details_path):
        return {}
    try:
        with open(details_path) as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return {}
    rows = payload.get("operators") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return {}
    counters = {}
    for row in rows:
        index = row.get("index")
        if index is None:
            continue
        # Absent keys are omitted, not written as null: analyze_kernels already drops
        # 'N/A' cells, and a present-but-null key would claim the counter read zero.
        picked = {field: row[field] for field in COUNTER_FIELDS if row.get(field) is not None}
        if picked:
            counters[int(index)] = picked
    return counters


def shape_list(raw):
    """`"1,1,4096;11008,4096"` -> `[[1,1,4096],[11008,4096]]`; drop empty groups."""
    groups = []
    for group in str(raw or "").split(";"):
        group = group.strip()
        if not group:
            continue
        try:
            groups.append([int(part) for part in group.split(",") if part.strip()])
        except ValueError:
            groups.append(group)
    return groups


def canonical_operator_name(name):
    """Remove profiler graph-node ordinals without erasing operator version numbers."""
    value = re.sub(r"_\d+(?=[A-Z])", "", str(name or ""))
    return re.sub(r"_\d+(?=$|/|_)", "", value)


def _shape_signature(raw):
    """Normalize profiler shape text into a hashable, exact comparison value."""
    return tuple(tuple(group) if isinstance(group, list) else (str(group),)
                 for group in shape_list(raw))


def kernel_signature(row):
    """Identity evidence required before positional attribution crosses invocations."""
    return (
        canonical_operator_name(row.get("normalized_name") or row.get("name")),
        str(row.get("task_type") or row.get("type") or ""),
        _shape_signature(row.get("input_shapes")),
        _shape_signature(row.get("output_shapes")),
    )


def align_stream_profiles(representative, instance):
    """Map each representative stream slot to one uniquely matching instance slot."""
    rep = [tuple(profile) for profile in representative]
    current = [tuple(profile) for profile in instance]
    if Counter(rep) != Counter(current):
        return None
    slots = collections.defaultdict(list)
    for slot, profile in enumerate(current):
        slots[profile].append(slot)
    if any(len(matches) != 1 for matches in slots.values()):
        return None
    return [slots[profile][0] for profile in rep]


def align_stream_profile_with_communication_extras(representative, instance):
    """Align one stream while permitting only repeated communication stubs.

    Some collective launches emit a variable number of profiler synchronization rows. A
    longer invocation remains translatable only when every surplus row is explicitly marked
    COMMUNICATION and repeats a communication signature already proved by the representative.
    The returned positions map representative rows into the instance; extras remain separate
    so callers can require one unambiguous declared owner before claiming them.
    """
    rep_signatures = [kernel_signature(row) for row in representative]
    instance_signatures = [kernel_signature(row) for row in instance]
    allowed_extras = {
        signature for row, signature in zip(representative, rep_signatures)
        if row.get("accelerator_core") == "COMMUNICATION"
    }
    positions = []
    extras = []
    rep_position = 0
    for instance_position, (row, signature) in enumerate(
            zip(instance, instance_signatures)):
        if (rep_position < len(rep_signatures)
                and signature == rep_signatures[rep_position]):
            positions.append(instance_position)
            rep_position += 1
            continue
        if (row.get("accelerator_core") == "COMMUNICATION"
                and signature in allowed_extras):
            extras.append(instance_position)
            continue
        return None
    if rep_position != len(rep_signatures):
        return None
    return {"positions": positions, "extras": extras}


class Attributor:
    def __init__(self, kernels, nodes):
        self.kernels = {int(k["index"]): k for k in kernels}
        self.nodes = {n["node_id"]: n for n in nodes}
        self.owner = {}
        self.evidence = {}
        self.conflicts = []

    def claim(self, op_index, node_id, evidence, layer_index=None):
        op_index = int(op_index)
        if op_index not in self.kernels:
            raise breakdown_paths.ConversionError(
                f"op_index {op_index} claimed by {node_id} is not in the "
                f"representative step (have {len(self.kernels)} kernels). "
                "The breakdown and the kernel rows disagree; do not guess."
            )
        if node_id not in self.nodes:
            raise breakdown_paths.ConversionError(
                f"node_id {node_id!r} is absent from the node index. "
                "Fix the namespace derivation rather than inventing an owner."
            )
        previous = self.owner.get(op_index)
        if previous is not None and previous != node_id:
            # Double attribution would double-count the kernel's time.
            self.conflicts.append({
                "op_index": op_index,
                "first": previous,
                "first_evidence": self.evidence[op_index]["kind"],
                "second": node_id,
                "second_evidence": evidence["kind"],
            })
            return
        self.owner[op_index] = node_id
        self.evidence[op_index] = {**evidence, "layer_index": layer_index}

    def unclaimed(self):
        return sorted(set(self.kernels) - set(self.owner))


def declared_leaves(nodes):
    return [n for n in nodes if not n.get("child_ids") and n.get("op_indices")]


def layer_index_by_op(config):
    """Map each op index to the layer it ran in, from the declared instance ranges.

    Translation already stamps a layer index on the invocations it derives, but the
    representative's own ops -- and any group with a single instance -- are claimed directly and
    would otherwise carry none. The UI derives its per-layer heat from this index, so a missing
    one leaves those layers uncolored while their neighbours are shaded: the pager looks broken
    when in fact the layers ran.
    """
    owner = {}
    for inst in config.get("trace_instances") or []:
        layer = inst.get("model_layer_index")
        if layer is None:
            continue
        op_range = inst.get("op_range")
        if isinstance(op_range, list) and len(op_range) == 2:
            for op_index in range(int(op_range[0]), int(op_range[1]) + 1):
                owner.setdefault(op_index, layer)
        for op_index in inst.get("op_indices") or []:
            owner.setdefault(int(op_index), layer)
    return owner


def apply_direct(attributor, nodes, config=None):
    """Stage 1: each leaf's own op_indices."""
    layer_of = layer_index_by_op(config or {})
    for node in declared_leaves(nodes):
        for op_index in node["op_indices"]:
            attributor.claim(op_index, node["node_id"],
                             {"kind": "declared_op_indices"},
                             layer_index=layer_of.get(int(op_index)))


class InstanceRangeTranslator:
    """Translate representative ownership across repeated per-stream invocations."""

    def __init__(self, attributor, config, index, nodes):
        self.attributor = attributor
        self.instances_by_group = {}
        for instance in config.get("trace_instances") or []:
            key = instance.get("layer_group_type")
            self.instances_by_group.setdefault(key, []).append(instance)
        self.node_by_id = {node["node_id"]: node for node in nodes}
        self.group_roots = (index.get("roots") or {}).get("layer_structure") or {}
        self.translated = 0
        self.used_instances = 0
        self.communication_extras = 0

    @staticmethod
    def alignment_detail(representative_profile, instance_profile):
        detail = (f"representative has {len(representative_profile)} stream(s) with sizes "
                  f"{[len(stream) for stream in representative_profile]}, this instance has "
                  f"{len(instance_profile)} with {[len(stream) for stream in instance_profile]}")
        for slot, profiles in enumerate(zip(representative_profile, instance_profile)):
            expected, actual = profiles
            if expected == actual:
                continue
            first = next((index for index, pair in enumerate(zip(expected, actual))
                          if pair[0] != pair[1]), None)
            if first is not None:
                detail = (f"stream slot {slot} position {first}: representative "
                          f"{expected[first]!r} vs {actual[first]!r}")
            break
        return detail

    def signature_of(self, op_index):
        row = self.attributor.kernels.get(int(op_index))
        return kernel_signature(row) if row else None

    def per_stream(self, lower, upper):
        grouped = collections.OrderedDict()
        for op_index in range(lower, upper + 1):
            row = self.attributor.kernels.get(op_index)
            if row is not None:
                grouped.setdefault(str(row.get("stream_id")), []).append(op_index)
        return list(grouped.values())

    def group_context(self, group_key, root_id, instances):
        representative_id = instances[0].get("representative_instance_id")
        representative = next(
            (item for item in instances if item.get("instance_id") == representative_id),
            instances[0],
        )
        op_range = representative.get("op_range")
        if not (isinstance(op_range, list) and len(op_range) == 2):
            raise breakdown_paths.ConversionError(
                f"{group_key}: representative instance has no op_range"
            )
        lower, upper = int(op_range[0]), int(op_range[1])
        streams = self.per_stream(lower, upper)
        slot_of = {}
        for slot, indices in enumerate(streams):
            for position, op_index in enumerate(indices):
                slot_of[op_index] = (slot, position)
        offsets = self.group_offsets(root_id, lower, upper, slot_of)
        return {
            "representative": representative, "lower": lower, "upper": upper,
            "span": upper - lower, "streams": streams, "offsets": offsets,
        }

    def group_offsets(self, root_id, lower, upper, slot_of):
        offsets = []
        for node_id, node in self.node_by_id.items():
            if not node_id.startswith(root_id + "/") or node.get("child_ids"):
                continue
            for raw_index in node.get("op_indices") or []:
                op_index = int(raw_index)
                if lower <= op_index <= upper:
                    offsets.append((slot_of[op_index], node_id))
        return offsets

    def communication_alignment(self, representative_streams, instance_streams):
        candidates = []
        for representative_stream in representative_streams:
            representative_rows = [self.attributor.kernels[i] for i in representative_stream]
            matches = []
            for slot, instance_stream in enumerate(instance_streams):
                instance_rows = [self.attributor.kernels[i] for i in instance_stream]
                match = align_stream_profile_with_communication_extras(
                    representative_rows, instance_rows
                )
                if match is not None:
                    matches.append((slot, match))
            candidates.append(matches)
        if not all(len(matches) == 1 for matches in candidates):
            return None
        slots = [matches[0][0] for matches in candidates]
        if len(set(slots)) != len(slots):
            return None
        matches = [matches[0][1] for matches in candidates]
        return {
            "streams": [instance_streams[slot] for slot in slots],
            "positions": [match["positions"] for match in matches],
            "extras": [match["extras"] for match in matches],
        }

    def align_instance(self, context, instance):
        op_range = instance.get("op_range")
        if not (isinstance(op_range, list) and len(op_range) == 2):
            raise breakdown_paths.ConversionError(
                f"{instance.get('instance_id')}: missing op_range; cannot translate"
            )
        lower, upper = int(op_range[0]), int(op_range[1])
        streams = self.per_stream(lower, upper)
        expected = [[self.signature_of(index) for index in stream]
                    for stream in context["streams"]]
        actual = [[self.signature_of(index) for index in stream] for stream in streams]
        alignment = align_stream_profiles(expected, actual)
        if alignment is not None:
            return {
                "streams": [streams[slot] for slot in alignment],
                "positions": [list(range(len(stream))) for stream in context["streams"]],
                "extras": [[] for _ in context["streams"]],
            }
        if upper - lower != context["span"] and len(context["streams"]) == len(streams):
            result = self.communication_alignment(context["streams"], streams)
            if result is not None:
                return result
        detail = self.alignment_detail(expected, actual)
        raise breakdown_paths.ConversionError(
            f"{instance.get('instance_id')} cannot be aligned with the "
            f"{context['span'] + 1}-op representative per-stream kernel sequence, so a "
            f"positional claim would misattribute. {detail}. Give this group per-instance "
            "op_indices, or split it into its own layer_group."
        )

    def claim_offsets(self, context, instance, alignment):
        layer_index = instance.get("model_layer_index")
        for (slot, position), node_id in context["offsets"]:
            representative_op = context["streams"][slot][position]
            instance_op = alignment["streams"][slot][alignment["positions"][slot][position]]
            self.attributor.claim(
                instance_op, node_id,
                {"kind": "instance_range_translation",
                 "instance_id": instance.get("instance_id"),
                 "representative_op_index": representative_op},
                layer_index=layer_index,
            )
            self.translated += 1

    def matching_extra_owner(self, context, slot, signature):
        owners, representative_ops = set(), set()
        for (offset_slot, position), node_id in context["offsets"]:
            if offset_slot != slot:
                continue
            representative_op = context["streams"][slot][position]
            if self.signature_of(representative_op) == signature:
                owners.add(node_id)
                representative_ops.add(representative_op)
        return owners, sorted(representative_ops)

    def claim_extras(self, context, instance, alignment):
        for slot, extra_positions in enumerate(alignment["extras"]):
            for position in extra_positions:
                op_index = alignment["streams"][slot][position]
                signature = self.signature_of(op_index)
                owners, representative_ops = self.matching_extra_owner(context, slot, signature)
                if len(owners) != 1:
                    raise breakdown_paths.ConversionError(
                        f"{instance.get('instance_id')} has a surplus communication row with "
                        f"signature {signature!r}, but its declared owner is ambiguous "
                        f"({sorted(owners)}). Give this instance explicit op_indices rather "
                        "than guessing."
                    )
                self.attributor.claim(
                    op_index, next(iter(owners)),
                    {"kind": "instance_range_communication_extra",
                     "instance_id": instance.get("instance_id"),
                     "representative_op_indices": representative_ops},
                    layer_index=instance.get("model_layer_index"),
                )
                self.translated += 1
                self.communication_extras += 1

    def translate_group(self, group_key, root_id):
        instances = self.instances_by_group.get(group_key) or []
        if len(instances) < 2:
            return
        context = self.group_context(group_key, root_id, instances)
        if not context["offsets"]:
            return
        for instance in instances:
            if instance.get("instance_id") == context["representative"].get("instance_id"):
                continue
            alignment = self.align_instance(context, instance)
            self.claim_offsets(context, instance, alignment)
            self.claim_extras(context, instance, alignment)
            self.used_instances += 1

    def run(self):
        for group_key, root_id in self.group_roots.items():
            self.translate_group(group_key, root_id)
        return {
            "translated": self.translated, "instances": self.used_instances,
            "communication_extras": self.communication_extras,
        }


def apply_instance_ranges(attributor, config, index, nodes):
    """Translate representative ownership onto every repeated invocation."""
    return InstanceRangeTranslator(attributor, config, index, nodes).run()


class SplitRuleApplier:
    """Validate folded-run split assertions and remap every derived claim."""

    def __init__(self, attributor, nodes):
        self.attributor = attributor
        self.nodes = {node["node_id"]: node for node in nodes}

    @staticmethod
    def targets_for(rule, run):
        source = rule["source_node_id"]
        targets_by_representative_op = {}
        for assignment in rule["assign"]:
            target = assignment["target_node_id"]
            lo, hi = assignment["range"]
            if not (isinstance(lo, int) and isinstance(hi, int)
                    and 0 <= lo < hi <= len(run)):
                raise breakdown_paths.ConversionError(
                    f"{source}: invalid split range {assignment['range']!r} for "
                    f"representative run of length {len(run)}"
                )
            for representative_op_index in run[lo:hi]:
                previous = targets_by_representative_op.get(representative_op_index)
                if previous is not None and previous != target:
                    raise breakdown_paths.ConversionError(
                        f"{source}: representative op {representative_op_index} is assigned "
                        f"to both {previous!r} and {target!r}"
                    )
                targets_by_representative_op[representative_op_index] = target

        missing = sorted(set(run) - set(targets_by_representative_op))
        if missing:
            raise breakdown_paths.ConversionError(
                f"{source}: split rule leaves representative ops unassigned: {missing}. "
                "Every op in a folded run must resolve to one target."
            )
        return targets_by_representative_op

    @staticmethod
    def target_for_claim(source, op_index, representative_ops, targets):
        unknown = sorted(int(index) for index in representative_ops
                         if int(index) not in targets)
        owners = {targets.get(int(index)) for index in representative_ops}
        owners.discard(None)
        if not representative_ops or unknown or len(owners) != 1:
            raise breakdown_paths.ConversionError(
                f"{source}: translated op {op_index} cannot be mapped unambiguously to "
                f"the split representative run (representative ops: {representative_ops}, "
                f"outside run: {unknown})"
            )
        return next(iter(owners))

    def representative_run(self, rule):
        source = rule["source_node_id"]
        node = self.nodes.get(source)
        if node is None:
            raise breakdown_paths.ConversionError(f"split rule targets unknown node {source!r}")
        run = sorted(int(i) for i in node.get("op_indices") or [])
        expect_len = rule.get("expect_length")
        if expect_len is not None and len(run) != expect_len:
            raise breakdown_paths.ConversionError(
                f"{source}: run length {len(run)} != expected {expect_len}. "
                "The structure or the capture changed; fix the rule against the "
                "model source rather than widening it."
            )

        expect_types = rule.get("expect_op_types")
        if expect_types:
            actual = [self.attributor.kernels[i].get("normalized_name")
                      or self.attributor.kernels[i].get("task_type") for i in run]
            if actual != expect_types:
                raise breakdown_paths.ConversionError(
                    f"{source}: operator types {actual} != expected {expect_types}"
                )
        return run

    def representative_ops(self, op_index, targets):
        previous_evidence = self.attributor.evidence[op_index]
        if op_index in targets:
            return [op_index]
        representative_op = previous_evidence.get("representative_op_index")
        if representative_op is not None:
            return [representative_op]
        return previous_evidence.get("representative_op_indices") or []

    def remap_claim(self, rule, op_index, targets):
        source = rule["source_node_id"]
        previous_evidence = self.attributor.evidence[op_index]
        representative_ops = self.representative_ops(op_index, targets)
        target = self.target_for_claim(source, op_index, representative_ops, targets)
        layer_index = previous_evidence.get("layer_index")
        self.attributor.owner.pop(op_index, None)
        self.attributor.evidence.pop(op_index, None)
        self.attributor.claim(
            op_index, target,
            {"kind": "asserted_split", "rule": rule.get("name"),
             "source_node_id": source,
             "representative_op_indices": representative_ops},
            layer_index=layer_index,
        )

    def apply(self, rule):
        source = rule["source_node_id"]
        run = self.representative_run(rule)
        targets = self.targets_for(rule, run)
        source_claims = [op_index for op_index, owner in self.attributor.owner.items()
                         if owner == source]
        for op_index in source_claims:
            self.remap_claim(rule, op_index, targets)
        return rule.get("name") or source

    def run(self, rules):
        applied = []
        for rule in rules.get("splits") or []:
            applied.append(self.apply(rule))
        return applied


def apply_split_rules(attributor, rules, nodes):
    """Split folded runs only after their declared profiles match exactly."""
    return SplitRuleApplier(attributor, nodes).run(rules)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="explicit breakdown config path")
    parser.add_argument("--breakdown", required=True)
    parser.add_argument("--nodes", required=True, help="node_index.json")
    parser.add_argument("--kernels",
                        help="kernel rows; defaults to <breakdown>/raw_ops.json")
    parser.add_argument("--kernel-details",
                        help="raw_ops_details.json carrying the AI Core counters; "
                             "defaults to <breakdown>/raw_ops_details.json")
    parser.add_argument("--split-rules",
                        help="JSON file of asserted split rules for folded runs")
    parser.add_argument("--out", required=True)
    return parser.parse_args()


@dataclass(frozen=True)
class RunInputs:
    config: dict
    index: dict
    nodes: list
    kernel_path: str
    raw: object
    kernels: list
    details_path: str
    counters: dict


def load_run_inputs(args):
    config = breakdown_paths.load_json(
        breakdown_paths.config_or_die(args.breakdown, args.config)
    )
    index = breakdown_paths.load_json(args.nodes)
    nodes = index["nodes"]
    kernel_path = args.kernels or os.path.join(args.breakdown, "raw_ops.json")
    raw = breakdown_paths.load_json(kernel_path)
    kernels = raw.get("operators") if isinstance(raw, dict) else raw
    if not kernels:
        raise breakdown_paths.ConversionError(f"no kernel rows in {kernel_path}")
    details_path = args.kernel_details or os.path.join(args.breakdown, "raw_ops_details.json")
    counters = load_counters(details_path)
    return RunInputs(
        config=config,
        index=index,
        nodes=nodes,
        kernel_path=kernel_path,
        raw=raw,
        kernels=kernels,
        details_path=details_path,
        counters=counters,
    )


def attribution_rows(attributor, counters):
    rows = []
    for op_index in sorted(attributor.owner):
        kernel = attributor.kernels[op_index]
        evidence = attributor.evidence[op_index]
        rows.append({
            "op_index": op_index,
            "org_index": kernel.get("org_index"),
            "owner_node_id": attributor.owner[op_index],
            "layer_index": evidence.get("layer_index"),
            "op_name": kernel.get("original_name"),
            "op_type": kernel.get("normalized_name") or kernel.get("task_type"),
            "duration_us": kernel.get("duration_us"),
            "duplicate_of": kernel.get("duplicate_of"),
            "start_time_us": kernel.get("start_time_us"),
            "stream_id": kernel.get("stream_id"),
            "input_shapes": shape_list(kernel.get("input_shapes")),
            "output_shapes": shape_list(kernel.get("output_shapes")),
            "attribution_evidence": evidence["kind"],
            **counters.get(op_index, {}),
        })
    return rows


def output_payload(args, inputs, result, rows):
    attributor, translation, splits = result
    total = len(attributor.kernels)
    claimed = len(attributor.owner)
    return {
        "schema_version": 1,
        "breakdown": os.path.abspath(args.breakdown),
        "kernel_source": os.path.abspath(inputs.kernel_path),
        "counter_source": os.path.abspath(inputs.details_path) if inputs.counters else None,
        "counter_rows": len(inputs.counters),
        "representative_step": (inputs.raw.get("step_id")
                                if isinstance(inputs.raw, dict) else None),
        "summary": {
            "kernels_total": total, "kernels_attributed": claimed,
            "coverage_pct": round(100.0 * claimed / total, 4) if total else 0.0,
            "unattributed": attributor.unclaimed(), "conflicts": attributor.conflicts,
            "instance_translations": translation, "split_rules_applied": splits,
            "evidence_mix": dict(Counter(row["attribution_evidence"] for row in rows)),
        },
        "per_node_kernel_counts": dict(Counter(row["owner_node_id"] for row in rows)),
        "rows": rows,
    }


def run_attribution(args, inputs):
    attributor = Attributor(inputs.kernels, inputs.nodes)
    apply_direct(attributor, inputs.nodes, inputs.config)
    translation = apply_instance_ranges(
        attributor, inputs.config, inputs.index, inputs.nodes
    )
    splits = (apply_split_rules(
        attributor, breakdown_paths.load_json(args.split_rules), inputs.nodes
    ) if args.split_rules else [])
    return attributor, translation, splits


def report_result(args, attributor, translation, splits, rows):
    total = len(attributor.kernels)
    claimed = len(attributor.owner)
    logger.info("WROTE %s", args.out)
    logger.info("kernels %s/%s attributed (%.2f%%)",
                claimed, total, 100.0 * claimed / total)
    logger.info("evidence mix: %s",
                dict(Counter(row["attribution_evidence"] for row in rows)))
    if translation["instances"]:
        logger.info("instance translation: %s claims across %s non-representative invocations",
                    translation["translated"], translation["instances"])
    if splits:
        logger.info("split rules applied: %s", splits)
    if attributor.conflicts:
        logger.error("\nFAIL %s kernel(s) claimed twice:", len(attributor.conflicts))
        for conflict in attributor.conflicts[:10]:
            logger.error("  op %s: %s (%s) vs %s (%s)",
                         conflict["op_index"], conflict["first"],
                         conflict["first_evidence"], conflict["second"],
                         conflict["second_evidence"])
        return 1
    unclaimed = attributor.unclaimed()
    if unclaimed:
        logger.error("\nFAIL %s kernel(s) unattributed: %s%s",
                     len(unclaimed), unclaimed[:20],
                     " ..." if len(unclaimed) > 20 else "")
        logger.error("Do not redistribute the remainder. Find the run whose boundary is "
                     "wrong and compare it against the model source.")
        return 1
    logger.info("\nPASS every kernel attributed exactly once")
    return 0


def main():
    args = parse_args()
    inputs = load_run_inputs(args)
    attributor, translation, splits = run_attribution(args, inputs)
    rows = attribution_rows(attributor, inputs.counters)
    breakdown_paths.dump_json(
        output_payload(args, inputs, (attributor, translation, splits), rows), args.out
    )
    return report_result(args, attributor, translation, splits, rows)


if __name__ == "__main__":
    sys.exit(breakdown_paths.run_cli(main))
