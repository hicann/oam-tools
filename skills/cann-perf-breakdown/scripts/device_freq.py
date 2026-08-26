#!/usr/bin/env python3
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
#
"""Derive the device AI Core / AI Vector clock from a capture.

Two independent sources, reported separately so a disagreement stays visible:

`declared` — the `AI Core Freq` counter events msprof writes into trace_view.json
    (`{"name": "AI Core Freq", "ph": "C", "args": {"MHz": 1850}}`). Authoritative but
    sparse: a capture typically carries two samples, one near each end of the window.
    Treat it as a nameplate value, not a curve.

`derived` — cycles / time / cores, per kernel, from the kernel_details.csv counters:
    `aic_total_cycles / aicore_time(us) / Block Dim` and the AIV equivalent. Dense
    (one estimate per counter-bearing kernel) and it is what the MFU denominator
    actually depends on, so it is the value to trust when the two disagree.

The core divisor matters. `aic_total_cycles` sums every core the kernel occupied, so
dividing by time alone yields cores x clock — on a 24-core kernel that reads as
~44 GHz. `Mix Block Dim` wins over `Block Dim` for the vector counters on MIX_AIC
kernels, where the AIV work ran on a different core count than the cube work; using
Block Dim there reports exactly 2x the true clock.

A capture with no counters and no trace events is not an error. Every field goes to
null and callers report the frequency as unavailable rather than assuming a default,
because a wrong clock silently rescales every cycle-derived metric downstream.
"""
import argparse
import json
import os
import statistics
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import breakdown_common as bc  # noqa: E402

#: Plausible AI Core clock range in MHz. Ascend parts run roughly 1.0-2.5 GHz; a value
#: outside this means the divisor was wrong (missing/incorrect core count), not that the
#: hardware was exotic. Such samples are counted and excluded, never silently averaged in.
PLAUSIBLE_MHZ = (800.0, 2600.0)

#: A derived clock this far from the trace-declared value (fractional) is reported as a
#: mismatch. Real captures agree to well under 0.1%; anything larger means the counters and
#: the declared nameplate describe different things and no downstream metric should assume either.
DECLARED_TOLERANCE = 0.02

TRACE_COUNTER_NAME = "AI Core Freq"


def _num(value):
    """Coerce a CSV/JSON scalar to float, or None. 'N/A' and '' are absent, not zero."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.upper() == "N/A":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _core_count(row, prefer_mix):
    """Cores the counter was accumulated over.

    `prefer_mix` selects Mix Block Dim first, which is correct for the AIV counters on a
    MIX_AIC kernel: the vector phase ran on a different core count than the cube phase.
    """
    keys = ("mix_block_dim", "block_dim") if prefer_mix else ("block_dim", "mix_block_dim")
    for key in keys:
        cores = _num(row.get(key))
        if cores and cores > 0:
            return cores
    return None


def _estimate(rows, cycles_key, time_key, prefer_mix):
    """Per-kernel MHz estimates from one counter pair, split into kept and rejected."""
    kept, rejected = [], 0
    for row in rows:
        cycles = _num(row.get(cycles_key))
        micros = _num(row.get(time_key))
        if not cycles or not micros:
            continue
        if cycles <= 0 or micros <= 0:
            continue
        cores = _core_count(row, prefer_mix)
        if not cores:
            continue
        mhz = cycles / micros / cores
        if PLAUSIBLE_MHZ[0] <= mhz <= PLAUSIBLE_MHZ[1]:
            kept.append(mhz)
        else:
            rejected += 1
    return kept, rejected


def _summarize(samples, rejected):
    if not samples:
        return {
            "mhz": None,
            "sample_count": 0,
            "implausible_sample_count": rejected,
            "min_mhz": None,
            "max_mhz": None,
            "spread_pct": None,
        }
    median = statistics.median(samples)
    low, high = min(samples), max(samples)
    return {
        # Median, not mean: one kernel with a misreported core count should not move the clock.
        "mhz": round(median, 2),
        "sample_count": len(samples),
        "implausible_sample_count": rejected,
        "min_mhz": round(low, 2),
        "max_mhz": round(high, 2),
        # Spread is the throttling signal. A stable capture sits near 0; a wide spread means
        # the clock moved during the window and a single representative-step figure understates it.
        "spread_pct": round(100.0 * (high - low) / median, 4) if median else None,
    }


def derive_from_rows(rows):
    """Derived clock from already-parsed kernel detail rows (analyze_kernels JSON keys)."""
    aic_samples, aic_rejected = _estimate(
        rows, "aic_total_cycles", "aicore_time_us", prefer_mix=False)
    aiv_samples, aiv_rejected = _estimate(
        rows, "aiv_total_cycles", "aiv_time_us", prefer_mix=True)

    aic = _summarize(aic_samples, aic_rejected)
    aiv = _summarize(aiv_samples, aiv_rejected)

    combined = aic_samples + aiv_samples
    overall = _summarize(combined, aic_rejected + aiv_rejected)

    return {
        "mhz": overall["mhz"],
        "method": "median(cycles / time_us / cores) per kernel",
        "cores_field": "Mix Block Dim for AIV on mixed kernels, else Block Dim",
        "ai_core": aic,
        "ai_vector": aiv,
        "sample_count": overall["sample_count"],
        "implausible_sample_count": overall["implausible_sample_count"],
        "min_mhz": overall["min_mhz"],
        "max_mhz": overall["max_mhz"],
        "spread_pct": overall["spread_pct"],
    }


def declared_from_trace(trace_path):
    """The `AI Core Freq` counter samples msprof wrote, in timestamp order.

    Returns null fields when the capture has no such events; a trace without them is
    ordinary, not malformed.
    """
    empty = {
        "mhz": None,
        "source": None,
        "sample_count": 0,
        "samples": [],
        "note": None,
    }
    if not trace_path or not os.path.exists(trace_path):
        return dict(empty, note="no trace_view.json supplied")

    try:
        with open(trace_path, encoding="utf-8", errors="replace") as handle:
            events = json.load(handle)
    except (OSError, ValueError) as exc:
        return dict(empty, note=f"trace unreadable: {exc}")

    if isinstance(events, dict):
        events = events.get("traceEvents") or []

    samples = []
    for event in events if isinstance(events, list) else []:
        if not isinstance(event, dict):
            continue
        if event.get("name") != TRACE_COUNTER_NAME or event.get("ph") != "C":
            continue
        mhz = _num((event.get("args") or {}).get("MHz"))
        if mhz is None:
            continue
        samples.append({"ts_us": _num(event.get("ts")), "mhz": mhz})

    if not samples:
        return dict(empty, source=os.path.abspath(trace_path),
                    note=f"no '{TRACE_COUNTER_NAME}' counter events in this capture")

    samples.sort(key=lambda s: (s["ts_us"] is None, s["ts_us"]))
    values = [s["mhz"] for s in samples]
    constant = min(values) == max(values)
    return {
        "mhz": round(statistics.median(values), 2),
        "source": os.path.abspath(trace_path),
        "sample_count": len(samples),
        "samples": samples,
        "note": (
            f"{len(samples)} counter sample(s), constant at {values[0]:.0f} MHz; "
            "a nameplate value, not a frequency curve"
            if constant else
            f"{len(samples)} counter sample(s) ranging {min(values):.0f}-{max(values):.0f} MHz"
        ),
    }


def build_device_profile(rows, trace_path=None):
    """The `device_profile` block: declared clock, derived clock, and their agreement."""
    declared = declared_from_trace(trace_path)
    derived = derive_from_rows(rows)

    # Derived wins: it is dense, per-kernel, and it is the divisor every cycle-derived metric
    # actually used. Declared is the fallback when the capture carries no counters at all.
    if derived["mhz"] is not None:
        effective, basis = derived["mhz"], "derived"
    elif declared["mhz"] is not None:
        effective, basis = declared["mhz"], "declared"
    else:
        effective, basis = None, "unavailable"

    agreement = "unknown"
    delta_pct = None
    if derived["mhz"] is not None and declared["mhz"]:
        delta_pct = round(100.0 * abs(derived["mhz"] - declared["mhz"]) / declared["mhz"], 4)
        agreement = "match" if delta_pct <= DECLARED_TOLERANCE * 100 else "mismatch"

    return {
        "aicore_freq_mhz": effective,
        "aicore_freq_basis": basis,
        "declared": declared,
        "derived": derived,
        "cross_check": {
            "agreement": agreement,
            "delta_pct": delta_pct,
            "tolerance_pct": DECLARED_TOLERANCE * 100,
            "note": (
                "Declared and derived clocks agree, so cycle-derived metrics rest on a "
                "verified clock."
                if agreement == "match" else
                "Declared and derived clocks disagree beyond tolerance; do not assume either "
                "for cycle-derived metrics until the core-count divisor is confirmed."
                if agreement == "mismatch" else
                "Only one source was available, so the clock is unverified."
            ),
        },
        "throttling": {
            "observed": bool(derived["spread_pct"] and derived["spread_pct"] > 1.0),
            "derived_spread_pct": derived["spread_pct"],
            "note": "Spread across per-kernel estimates. Above ~1% suggests the clock moved "
                    "during the capture window.",
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-d", "--details", required=True,
                        help="raw_ops_details.json from analyze_kernels.py")
    parser.add_argument("--trace", help="trace_view.json, for the declared AI Core Freq counter")
    parser.add_argument("-o", "--output", required=True, help="device_freq.json to write")
    args = parser.parse_args()

    try:
        with open(args.details, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        bc.emit_error(f"error: cannot read {args.details}: {exc}\n")
        return 1

    rows = payload.get("operators") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        bc.emit_error(f"error: no operator rows in {args.details}\n")
        return 1

    profile = build_device_profile(rows, args.trace)
    profile["step_id"] = payload.get("step_id") if isinstance(payload, dict) else None

    directory = os.path.dirname(os.path.abspath(args.output))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(profile, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    freq = profile["aicore_freq_mhz"]
    bc.emit(f"WROTE {args.output}")
    bc.emit(f"aicore_freq_mhz = {freq if freq is not None else 'unavailable'} "
          f"({profile['aicore_freq_basis']}), cross-check {profile['cross_check']['agreement']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
