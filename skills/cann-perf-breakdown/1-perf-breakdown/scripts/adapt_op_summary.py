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
"""Adapt an msprof op_summary CSV to the breakdown kernel CSV contract.

Step IDs are assigned from workload-authored epoch windows in step_marks.json.
Only kernels whose start timestamp falls inside a recorded step are emitted.
"""

import argparse
import bisect
import csv
import hashlib
import json
import os
import statistics


ALIASES = {
    "Op Name": "Name",
    "OP Type": "Type",
    "Task Type": "Accelerator Core",
    "Task Start Time(us)": "Start Time(us)",
    "Task Duration(us)": "Duration(us)",
    "Task Wait Time(us)": "Wait Time(us)",
}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean(value):
    return (value or "").strip().rstrip("\t")


def main():
    parser = argparse.ArgumentParser(
        description="Assign op_summary kernels to workload steps for perf breakdown"
    )
    parser.add_argument("--op-summary", required=True)
    parser.add_argument("--step-marks", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument(
        "--boundary-anchor-op-type",
        default="GatherV2",
        help="unique model-entry op used to correct the exported task-clock offset",
    )
    args = parser.parse_args()

    with open(args.step_marks, encoding="utf-8") as source:
        marks = json.load(source)
    steps = sorted(marks["steps"], key=lambda item: item["start_us"])
    mark_starts = [item["start_us"] for item in steps]
    if any(item["end_us"] < item["start_us"] for item in steps):
        raise SystemExit("invalid step window: end_us precedes start_us")
    if any(steps[i]["end_us"] >= steps[i + 1]["start_us"] for i in range(len(steps) - 1)):
        raise SystemExit("invalid step windows: overlap detected")

    anchor_candidates = []
    with open(args.op_summary, newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        for row in reader:
            if clean(row.get("OP Type")) != args.boundary_anchor_op_type:
                continue
            try:
                timestamp = float(clean(row["Task Start Time(us)"]))
            except ValueError:
                continue
            if marks["decode_window_us"][0] - 100000 <= timestamp <= marks["decode_window_us"][1] + 100000:
                anchor_candidates.append(timestamp)
    if len(anchor_candidates) != len(steps):
        raise SystemExit(
            f"expected {len(steps)} {args.boundary_anchor_op_type} anchors near decode, "
            f"found {len(anchor_candidates)}"
        )
    anchors = sorted(anchor_candidates)
    offsets = [anchor - mark for anchor, mark in zip(anchors, mark_starts)]
    median_offset = statistics.median(offsets)
    if max(abs(value - median_offset) for value in offsets) > 5000:
        raise SystemExit("entry-anchor to step-mark offset is not stable within 5 ms")
    final_end = steps[-1]["end_us"] + median_offset

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    counts = {str(item["step"]): 0 for item in steps}
    durations = {str(item["step"]): 0.0 for item in steps}
    total_rows = 0
    outside_rows = 0

    with open(args.op_summary, newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise SystemExit("op_summary is empty")
        required = set(ALIASES)
        missing = sorted(required - set(reader.fieldnames))
        if missing:
            raise SystemExit(f"op_summary missing columns: {', '.join(missing)}")
        output_fields = ["Step Id"] + list(ALIASES.values())
        output_fields += [name for name in reader.fieldnames if name not in ALIASES]
        with open(args.output, "w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=output_fields)
            writer.writeheader()
            for row in reader:
                total_rows += 1
                try:
                    timestamp = float(clean(row["Task Start Time(us)"]))
                except ValueError:
                    outside_rows += 1
                    continue
                pos = bisect.bisect_right(anchors, timestamp) - 1
                if pos < 0 or (pos == len(steps) - 1 and timestamp > final_end):
                    outside_rows += 1
                    continue
                step_id = str(steps[pos]["step"])
                adapted = {"Step Id": step_id}
                for source_name, target_name in ALIASES.items():
                    adapted[target_name] = clean(row[source_name])
                for name in reader.fieldnames:
                    if name not in ALIASES:
                        adapted[name] = clean(row[name])
                writer.writerow(adapted)
                counts[step_id] += 1
                durations[step_id] += float(clean(row["Task Duration(us)"]) or 0.0)

    empty_steps = [step_id for step_id, count in counts.items() if count == 0]
    metadata = {
        "adapter": "msprof_op_summary_plus_step_marks_v1",
        "inputs": {
            "op_summary": os.path.realpath(args.op_summary),
            "op_summary_sha256": sha256(args.op_summary),
            "step_marks": os.path.realpath(args.step_marks),
            "step_marks_sha256": sha256(args.step_marks),
        },
        "output": os.path.realpath(args.output),
        "output_sha256": sha256(args.output),
        "assignment_rule": (
            "pair each step mark with its unique GatherV2 model-entry anchor; assign kernels "
            "from that anchor until the next anchor (last step uses end_us + median offset)"
        ),
        "boundary_anchor_op_type": args.boundary_anchor_op_type,
        "clock_offset_us": {
            "median": median_offset,
            "minimum": min(offsets),
            "maximum": max(offsets),
            "per_step": offsets,
        },
        "total_input_rows": total_rows,
        "assigned_rows": sum(counts.values()),
        "outside_decode_step_rows": outside_rows,
        "step_count": len(steps),
        "empty_steps": empty_steps,
        "per_step": [
            {
                "step_id": step_id,
                "kernel_count": counts[step_id],
                "kernel_sum_us": round(durations[step_id], 3),
            }
            for step_id in counts
        ],
    }
    with open(args.metadata, "w", encoding="utf-8") as target:
        json.dump(metadata, target, indent=2)
        target.write("\n")
    print(
        f"[adapt] assigned {metadata['assigned_rows']}/{total_rows} kernels "
        f"to {len(steps)} steps; empty_steps={len(empty_steps)}"
    )


if __name__ == "__main__":
    main()
