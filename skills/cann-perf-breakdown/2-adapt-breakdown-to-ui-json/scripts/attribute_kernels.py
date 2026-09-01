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
"""Account for every representative-step kernel and attribute model/runtime rows.

Evidence, in order of authority:

1. A leaf's own `op_indices` — the breakdown already proved these.
2. `trace_instances[].op_range` — a repeated group's representative leaf offsets
   translate to every other invocation by range arithmetic, so all 32 layers
   inherit attribution without a single name comparison.
3. An explicit profile assertion from a rules file, for runs the breakdown folded
   into one leaf that the report needs split.

Never leaf-label similarity. Every attributable kernel is claimed exactly once;
profiler-only bookkeeping explicitly classified by Skill 1 remains ownerless but
counts as accounted coverage. Any other remainder is a defect, not a rounding
difference.
"""
import argparse
import collections
import json
import os
import re
import sys
from collections import Counter

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import breakdown_paths  # noqa: E402


def jload(path):
    with open(path) as handle:
        return json.load(handle)


def jdump(obj, path):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w") as handle:
        json.dump(obj, handle, ensure_ascii=False, indent=1)
        handle.write("\n")


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
            raise SystemExit(
                f"op_index {op_index} claimed by {node_id} is not in the "
                f"representative step (have {len(self.kernels)} kernels). "
                "The breakdown and the kernel rows disagree; do not guess."
            )
        if node_id not in self.nodes:
            raise SystemExit(
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


def excluded_kernel_indices(config, kernel_indices):
    """Return Skill 1's explicitly excluded profiler rows after boundary checks.

    Exclusion is an accounting category, not an attribution owner. Skill 1's
    readiness gate validates reason codes and evidence; this boundary additionally
    refuses dangling indices so a malformed handoff cannot hide missing work.
    """
    available = set(kernel_indices)
    excluded = set()
    for entry in config.get("excluded_profiler_ops") or []:
        for raw_index in entry.get("op_indices") or []:
            if isinstance(raw_index, bool) or not isinstance(raw_index, int):
                raise SystemExit(
                    f"excluded op_index {raw_index!r} is not an integer"
                )
            if raw_index not in available:
                raise SystemExit(
                    f"excluded op_index {raw_index} is not in the representative "
                    f"step (have {len(available)} kernels). The breakdown and the "
                    "kernel rows disagree; do not hide it as an exclusion."
                )
            excluded.add(raw_index)
    return excluded


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


def apply_instance_ranges(attributor, config, index, nodes):
    """Stage 2: translate the representative invocation onto every other one.

    A repeated group declares one representative instance and an `op_range` per
    invocation. Equal-length ranges make the offset exact, so a leaf owning
    offset k in the representative owns offset k everywhere. This is range
    arithmetic over declared facts, not pattern matching.
    """
    instances = config.get("trace_instances") or []
    if not instances:
        return {"translated": 0, "instances": 0, "communication_extras": 0}

    by_group = {}
    for inst in instances:
        by_group.setdefault(inst.get("layer_group_type"), []).append(inst)

    node_by_id = {n["node_id"]: n for n in nodes}
    group_roots = (index.get("roots") or {}).get("layer_structure") or {}
    translated = 0
    used_instances = 0
    communication_extras = 0

    def signature_of(op_index):
        row = attributor.kernels.get(int(op_index))
        if not row:
            return None
        return kernel_signature(row)

    def per_stream(lo, hi):
        """Ops of one invocation grouped by stream, in issue order within each stream.

        A profiler dump is sorted by start time, so ops on CONCURRENT streams interleave
        differently from one invocation to the next -- a `s192` op can land before or after its
        `s189` neighbours. Flat offset arithmetic reads that as a structural difference and,
        worse, silently hands one node another's kernel. Order WITHIN a single stream is
        sequential and therefore stable. Stream ids may differ between invocations, while first
        appearance can swap for concurrent streams, so callers align slots by their complete
        canonical per-stream profiles and reject ambiguous duplicates.
        """
        grouped = collections.OrderedDict()
        for index in range(lo, hi + 1):
            row = attributor.kernels.get(index)
            if row is None:
                continue
            grouped.setdefault(str(row.get("stream_id")), []).append(index)
        return list(grouped.values())

    for group_key, root_id in group_roots.items():
        group_instances = by_group.get(group_key) or []
        if len(group_instances) < 2:
            continue

        representative_id = group_instances[0].get("representative_instance_id")
        representative = next(
            (i for i in group_instances if i.get("instance_id") == representative_id),
            group_instances[0],
        )
        rep_range = representative.get("op_range")
        if not (isinstance(rep_range, list) and len(rep_range) == 2):
            raise SystemExit(f"{group_key}: representative instance has no op_range")
        rep_lo, rep_hi = int(rep_range[0]), int(rep_range[1])
        rep_span = rep_hi - rep_lo

        # Leaves under this group, addressed by (stream slot, position in that stream) in the
        # representative rather than by flat offset -- see per_stream() for why.
        rep_streams = per_stream(rep_lo, rep_hi)
        rep_slot_of = {}
        for slot, indices in enumerate(rep_streams):
            for position, op_index in enumerate(indices):
                rep_slot_of[op_index] = (slot, position)

        offsets = []
        for node_id, node in node_by_id.items():
            if not node_id.startswith(root_id + "/") or node.get("child_ids"):
                continue
            for op_index in node.get("op_indices") or []:
                op_index = int(op_index)
                if rep_lo <= op_index <= rep_hi:
                    offsets.append((rep_slot_of[op_index], node_id))
        if not offsets:
            continue

        for inst in group_instances:
            if inst.get("instance_id") == representative.get("instance_id"):
                continue
            op_range = inst.get("op_range")
            if not (isinstance(op_range, list) and len(op_range) == 2):
                raise SystemExit(
                    f"{inst.get('instance_id')}: missing op_range; cannot translate"
                )
            lo, hi = int(op_range[0]), int(op_range[1])
            # Equal span is necessary but NOT sufficient. Offset translation also assumes the
            # two invocations run the same kernels in the same ORDER. Concurrent streams break
            # that: two ops issued on different streams have no guaranteed relative position
            # in a time-sorted profiler dump, so a pair can appear swapped between invocations
            # while the span stays identical. Translating anyway silently hands one node the
            # other's kernel -- the MoE shared expert ends up owning a routed GroupedMatmul.
            # SKILL.md requires confirming one identical profile per invocation; this is it.
            # Equal span is necessary but NOT sufficient: the invocations must run the same
            # kernels in the same per-stream order, or a positional claim misattributes. This
            # compares operator type per stream slot, which is the identity the translation
            # actually relies on. SKILL.md requires confirming one identical profile; this is
            # it, and it is a hard error rather than a warning because the failure is silent --
            # every kernel still gets an owner, just the wrong one.
            inst_streams = per_stream(lo, hi)
            rep_profile = [[signature_of(i) for i in s] for s in rep_streams]
            inst_profile = [[signature_of(i) for i in s] for s in inst_streams]
            stream_positions = None
            stream_extras = None
            alignment = align_stream_profiles(rep_profile, inst_profile)
            if alignment is not None:
                inst_streams = [inst_streams[slot] for slot in alignment]
                inst_profile = [inst_profile[slot] for slot in alignment]
                stream_positions = [list(range(len(stream))) for stream in rep_streams]
                stream_extras = [[] for _ in rep_streams]
            elif hi - lo != rep_span and len(rep_streams) == len(inst_streams):
                candidates = []
                for rep_stream in rep_streams:
                    rep_rows = [attributor.kernels[i] for i in rep_stream]
                    matches = []
                    for instance_slot, instance_stream in enumerate(inst_streams):
                        instance_rows = [attributor.kernels[i] for i in instance_stream]
                        match = align_stream_profile_with_communication_extras(
                            rep_rows, instance_rows
                        )
                        if match is not None:
                            matches.append((instance_slot, match))
                    candidates.append(matches)
                if all(len(matches) == 1 for matches in candidates):
                    slots = [matches[0][0] for matches in candidates]
                    if len(set(slots)) == len(slots):
                        matches = [matches[0][1] for matches in candidates]
                        inst_streams = [inst_streams[slot] for slot in slots]
                        inst_profile = [[signature_of(i) for i in stream]
                                        for stream in inst_streams]
                        stream_positions = [match["positions"] for match in matches]
                        stream_extras = [match["extras"] for match in matches]
            if stream_positions is None:
                detail = (f"representative has {len(rep_profile)} stream(s) with sizes "
                          f"{[len(s) for s in rep_profile]}, this instance has "
                          f"{len(inst_profile)} with {[len(s) for s in inst_profile]}")
                for slot, (r, i) in enumerate(zip(rep_profile, inst_profile)):
                    if r != i:
                        first = next((k for k, (x, y) in enumerate(zip(r, i)) if x != y), None)
                        if first is not None:
                            detail = (f"stream slot {slot} position {first}: representative "
                                      f"{r[first]!r} vs {i[first]!r}")
                        break
                raise SystemExit(
                    f"{inst.get('instance_id')} cannot be aligned with the "
                    f"{rep_span + 1}-op representative per-stream kernel sequence, so a "
                    f"positional claim would misattribute. {detail}. Give this group "
                    "per-instance op_indices, or split it into its own layer_group."
                )
            layer_index = inst.get("model_layer_index")
            for (slot, position), node_id in offsets:
                attributor.claim(inst_streams[slot][stream_positions[slot][position]], node_id,
                                 {"kind": "instance_range_translation",
                                  "instance_id": inst.get("instance_id")},
                                 layer_index=layer_index)
                translated += 1
            for slot, extra_positions in enumerate(stream_extras):
                for extra_position in extra_positions:
                    signature = signature_of(inst_streams[slot][extra_position])
                    owners = {
                        node_id for (offset_slot, position), node_id in offsets
                        if offset_slot == slot
                        and signature_of(rep_streams[slot][position]) == signature
                    }
                    if len(owners) != 1:
                        raise SystemExit(
                            f"{inst.get('instance_id')} has a surplus communication row "
                            f"with signature {signature!r}, but its declared owner is "
                            f"ambiguous ({sorted(owners)}). Give this instance explicit "
                            "op_indices rather than guessing."
                        )
                    attributor.claim(
                        inst_streams[slot][extra_position], next(iter(owners)),
                        {"kind": "instance_range_communication_extra",
                         "instance_id": inst.get("instance_id")},
                        layer_index=layer_index,
                    )
                    translated += 1
                    communication_extras += 1
            used_instances += 1

    return {"translated": translated, "instances": used_instances,
            "communication_extras": communication_extras}


def apply_split_rules(attributor, rules, nodes):
    """Stage 3: split a folded run, gated on an explicit expected profile.

    Each rule states the run it targets and the exact operator-type sequence it
    expects. A structural change breaks the assertion loudly instead of
    reshuffling kernels into plausible-looking owners.
    """
    applied = []
    for rule in rules.get("splits") or []:
        source = rule["source_node_id"]
        node = next((n for n in nodes if n["node_id"] == source), None)
        if node is None:
            raise SystemExit(f"split rule targets unknown node {source!r}")

        run = sorted(int(i) for i in node.get("op_indices") or [])
        expect_len = rule.get("expect_length")
        if expect_len is not None and len(run) != expect_len:
            raise SystemExit(
                f"{source}: run length {len(run)} != expected {expect_len}. "
                "The structure or the capture changed; fix the rule against the "
                "model source rather than widening it."
            )

        expect_types = rule.get("expect_op_types")
        if expect_types:
            actual = [attributor.kernels[i].get("normalized_name")
                      or attributor.kernels[i].get("task_type") for i in run]
            if actual != expect_types:
                raise SystemExit(
                    f"{source}: operator types {actual} != expected {expect_types}"
                )

        for assignment in rule["assign"]:
            target = assignment["target_node_id"]
            lo, hi = assignment["range"]
            for op_index in run[lo:hi]:
                # Re-claiming from the folded parent to a specific child.
                attributor.owner.pop(op_index, None)
                attributor.claim(op_index, target,
                                 {"kind": "asserted_split", "rule": rule.get("name")})
        applied.append(rule.get("name") or source)
    return applied


def main():
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
    args = parser.parse_args()

    config = jload(breakdown_paths.config_or_die(args.breakdown, args.config))
    index = jload(args.nodes)
    nodes = index["nodes"]

    kernel_path = args.kernels or os.path.join(args.breakdown, "raw_ops.json")
    raw = jload(kernel_path)
    kernels = raw.get("operators") if isinstance(raw, dict) else raw
    if not kernels:
        raise SystemExit(f"no kernel rows in {kernel_path}")

    details_path = args.kernel_details or os.path.join(args.breakdown, "raw_ops_details.json")
    counters = load_counters(details_path)

    attributor = Attributor(kernels, nodes)
    excluded = excluded_kernel_indices(config, attributor.kernels)
    apply_direct(attributor, nodes, config)
    translation = apply_instance_ranges(attributor, config, index, nodes)
    splits = apply_split_rules(attributor, jload(args.split_rules), nodes) \
        if args.split_rules else []

    excluded_with_owner = sorted(excluded & set(attributor.owner))
    if excluded_with_owner:
        raise SystemExit(
            f"kernel(s) both excluded and attributed: {excluded_with_owner}. "
            "Each raw op must belong to exactly one Skill 1 accounting category."
        )

    unclaimed = sorted(set(attributor.unclaimed()) - excluded)
    total = len(attributor.kernels)
    claimed = len(attributor.owner)
    excluded_count = len(excluded)
    accounted = claimed + excluded_count

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
            # msprof reports one collective twice — a COMMUNICATION entry plus the AIV kernel
            # running it, same start and duration. The breakdown marks the second with
            # `duplicate_of` and keeps both rows so op indices stay stable. Carry the mark
            # through: a metric that sums these durations must count the work once.
            "duplicate_of": kernel.get("duplicate_of"),
            "start_time_us": kernel.get("start_time_us"),
            "stream_id": kernel.get("stream_id"),
            "input_shapes": shape_list(kernel.get("input_shapes")),
            "output_shapes": shape_list(kernel.get("output_shapes")),
            "attribution_evidence": evidence["kind"],
            **counters.get(op_index, {}),
        })

    per_node = Counter(row["owner_node_id"] for row in rows)
    jdump({
        "schema_version": 1,
        "breakdown": os.path.abspath(args.breakdown),
        "kernel_source": os.path.abspath(kernel_path),
        "counter_source": os.path.abspath(details_path) if counters else None,
        "counter_rows": len(counters),
        "representative_step": raw.get("step_id") if isinstance(raw, dict) else None,
        "summary": {
            "kernels_total": total,
            "kernels_attributed": claimed,
            "kernels_excluded": excluded_count,
            "kernels_accounted": accounted,
            "attribution_pct": round(100.0 * claimed / total, 4) if total else 0.0,
            "accounting_coverage_pct": (
                round(100.0 * accounted / total, 4) if total else 0.0
            ),
            # Compatibility alias consumed by the existing emitter and validator.
            "coverage_pct": round(100.0 * accounted / total, 4) if total else 0.0,
            "excluded": sorted(excluded),
            "unattributed": unclaimed,
            "conflicts": attributor.conflicts,
            "instance_translations": translation,
            "split_rules_applied": splits,
            "evidence_mix": dict(Counter(row["attribution_evidence"] for row in rows)),
        },
        "per_node_kernel_counts": dict(per_node),
        "rows": rows,
    }, args.out)

    print(f"WROTE {args.out}")
    print(f"kernels {claimed} attributed + {excluded_count} excluded / {total} "
          f"accounted ({100.0 * accounted / total:.2f}%)")
    print(f"evidence mix: {dict(Counter(r['attribution_evidence'] for r in rows))}")
    if translation["instances"]:
        print(f"instance translation: {translation['translated']} claims across "
              f"{translation['instances']} non-representative invocations")
    if splits:
        print(f"split rules applied: {splits}")

    if attributor.conflicts:
        print(f"\nFAIL {len(attributor.conflicts)} kernel(s) claimed twice:")
        for conflict in attributor.conflicts[:10]:
            print(f"  op {conflict['op_index']}: {conflict['first']} "
                  f"({conflict['first_evidence']}) vs {conflict['second']} "
                  f"({conflict['second_evidence']})")
        return 1

    if unclaimed:
        print(f"\nFAIL {len(unclaimed)} kernel(s) unattributed: {unclaimed[:20]}"
              + (" ..." if len(unclaimed) > 20 else ""))
        print("Do not redistribute the remainder. Find the run whose boundary is "
              "wrong and compare it against the model source.")
        return 1

    print(f"\nPASS every kernel accounted for exactly once "
          f"({claimed} attributed, {excluded_count} excluded)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
