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
"""Narrow a raw Chrome-trace to the representative step's time window.

A full msprof capture covers the whole run (here ~55 s / 5.7 M events / 1 GB) while the
report only ever renders the representative step (~28 ms). Stage 3 must inline the trace
into one JS string via `JSON.stringify`, so an unnarrowed capture fails outright with
Node's `RangeError: Invalid string length` -- and even if it fit, shipping a gigabyte of
out-of-window events into a standalone HTML would be pointless.

The window comes from raw_ops.json (the representative step's own kernels), never from a
hardcoded constant, so this stays correct for any capture and any selected step.

Kept: every metadata event (`ph: M`, the process/thread names the lanes are labelled from),
and every timed event overlapping the window. Flow events (`s`/`f`) are kept as pairs --
dropping one half would leave the report drawing an arrow to nothing.
"""
import argparse
import json
import logging
import sys

import breakdown_paths


logger = logging.getLogger(__name__)


def event_start(event):
    try:
        return float(event.get("ts"))
    except (TypeError, ValueError):
        return None


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True, help="raw Chrome-trace JSON")
    ap.add_argument("--raw-ops", required=True, help="raw_ops.json of the representative step")
    ap.add_argument("--output", required=True)
    ap.add_argument("--pad-us", type=float, default=2000.0,
                    help="context kept on each side, so a counter sampled just outside the "
                         "step still renders at the window edge")
    return ap.parse_args()


def trace_window(raw_ops_path, pad_us):
    with open(raw_ops_path, encoding="utf-8") as fh:
        ops = json.load(fh)["operators"]
    start = min(operator["start_time_us"] for operator in ops) - pad_us
    end = max(operator["start_time_us"] + operator["duration_us"] for operator in ops) + pad_us
    return start, end


def load_trace(path):
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    events = payload if isinstance(payload, list) else payload.get("traceEvents")
    if not isinstance(events, list):
        raise breakdown_paths.ConversionError(
            "trace must be an event list or an object containing traceEvents"
        )
    return payload, events


def live_flows(events, start, end):
    flow_ids = set()
    for event in events:
        if event.get("ph") not in ("s", "f"):
            continue
        timestamp = event_start(event)
        if timestamp is not None and start <= timestamp <= end:
            flow_ids.add(event.get("id"))
    return flow_ids


def narrow_events(events, start, end):
    flow_ids = live_flows(events, start, end)
    kept, metadata_count, flow_count = [], 0, 0
    for event in events:
        phase = event.get("ph")
        if phase == "M":
            kept.append(event)
            metadata_count += 1
            continue
        if phase in ("s", "f"):
            if event.get("id") in flow_ids:
                kept.append(event)
                flow_count += 1
            continue
        timestamp = event_start(event)
        if timestamp is None:
            continue
        finish = timestamp + float(event.get("dur") or 0)
        if finish >= start and timestamp <= end:
            kept.append(event)
    return kept, metadata_count, flow_count


def main():
    args = parse_args()
    start, end = trace_window(args.raw_ops, args.pad_us)
    trace_payload, events = load_trace(args.trace)
    kept, metadata_count, flow_count = narrow_events(events, start, end)

    with open(args.output, "w", encoding="utf-8") as fh:
        output_payload = (kept if isinstance(trace_payload, list)
                          else {**trace_payload, "traceEvents": kept})
        json.dump(output_payload, fh)

    logger.info(json.dumps({
        "output": args.output,
        "window_us": [start, end],
        "events_in": len(events),
        "events_kept": len(kept),
        "metadata_kept": metadata_count,
        "flow_events_kept": flow_count,
    }, indent=1))


if __name__ == "__main__":
    sys.exit(breakdown_paths.run_cli(main))
