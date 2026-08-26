# Diagnostic Codes and L1 Advice

This document is a read-only English translation of `diagnosis_advice.md`. The runtime `compute_metrics.py` loader reads the Chinese file, which is the **single source of truth** for `findings[].code` values and advice text. Make runtime changes there, then synchronize this translation.

## Scope

- Advice is purely informational. It does not enter `validation_report.json` or `breakdown_score.json`, affect hard gates or the two SKILL.md stop conditions, or participate in iteration.
- Advice answers only "what data should be inspected next." Metrics alone cannot prove a root cause, so do not present a hypothesis as a conclusion.
- Advice is not an optimization prescription. Whether and how to optimize depends on business goals and hardware configuration and is outside this skill's scope.

## Mandatory Aggregate-Scope Constraint

Every `metrics_findings.json` item has `metric_scope`. When `metric_scope == "aggregate"`, multiple invocations have been combined:

- `wall_ms` is the sum of instance walls multiplied by the multiplier and may exceed the total step wall. Ratios of 400% have been observed.
- `gap_pct` and `utilization_pct` describe only the aggregate group and imply nothing about any individual instance.
- Therefore, advice for an aggregate node must first require verification at `instance` scope. Every aggregate `advice_l1` string automatically receives the runtime prefix `[聚合口径]` (aggregate scope).

This is the same rule as the Skill 3 `app.js` tooltip disclaimer: aggregate totals do not identify a single-layer hotspot or severity. Keep both locations consistent.

## ADVICE_TABLE

In the runtime source `diagnosis_advice.md`, `load_advice_table()` parses each matching `## code:` section. This translation mirrors those sections. Both `next_data` and `not_applicable` are required.

## code: GAP_BUBBLE

- **advice**: Node wall time is substantially greater than device busy time, so the gap is outside the node's kernels. Locate it by sorting the node's operators by `start_time_us`, calculating `start[i+1] - (start[i] + duration[i])`, and inspecting the largest intervals.
- **next_data**: `start_time_us` and `duration_us` for this node's `op_indices` in `raw_ops_details.json`; the corresponding interval in `ASCEND_PROFILER_OUTPUT/trace_view.json`; host launch intervals in `api_statistic.csv`.
- **not_applicable**: Gap ratios are not meaningful when the node has two or fewer kernels. With `metric_scope == "aggregate"`, the value is a false cross-instance accumulated gap.

## code: WAIT_DOMINANT

- **advice**: A large `total_cost - kernel_sum` share means waiting dominates computation. Classify the wait by sorting kernels by `wait_time` and inspecting the predecessors of the top five. A collective predecessor indicates communication wait; a compute predecessor with high wait suggests a cross-stream dependency; very small kernel sum with very large wait usually indicates host launch or graph boundaries rather than device computation.
- **next_data**: `Wait Time(us)` in `raw_ops_details.json`; `ASCEND_PROFILER_OUTPUT/communication.json` and `communication_matrix.json` for communication bandwidth; `api_statistic.csv` for host launch.
- **not_applicable**: When `kernel_sum_ms < 0.1`, the wait ratio can expand to hundreds or thousands of percent. Do not compare the ratio across nodes; use it only as a signal that the node performs almost no computation.

## code: UTIL_LOW

- **advice**: Busy time is less than 80% of wall time. Distinguish a gap inside the node from upstream delay. If `GAP_BUBBLE` also applies, follow that advice. Otherwise inspect the highest-share operator type in `op_ratio`, because a small number of long kernels are stretching wall time.
- **next_data**: This node's `op_ratio` in Skill 2 `ui_facts/*_perf_data.json`; use the relevant operator's `aic_mac_ratio`, `aiv_vec_ratio`, and `aic_mte2_ratio` to distinguish compute and memory limits.
- **not_applicable**: Aggregate scope, and communication-only nodes where waiting is normal and utilization has different semantics.

## code: STREAM_PARALLEL_HIGH

- **advice**: The arithmetic sum of kernel durations substantially exceeds wall time, indicating overlapping execution on multiple streams. This is usually beneficial and needs no action. Do not use the `kernel_sum` share as a wall-clock share when attributing individual operator time; the units differ.
- **next_data**: Inspect `Stream ID` distribution and overlapping intervals in `raw_ops_details.json` when overlap must be confirmed.
- **not_applicable**: Wall-time ranking scenarios.

## code: STREAM_PARALLEL_MID

- **advice**: Moderate multi-stream overlap exists. As with `STREAM_PARALLEL_HIGH`, no action is required; preserve the distinction between arithmetic kernel sum and wall time.
- **next_data**: Same as `STREAM_PARALLEL_HIGH`.
- **not_applicable**: Same as `STREAM_PARALLEL_HIGH`.

## code: UTIL_GOOD

- **advice**: Utilization is between 80% and 95%; no action is required.
- **next_data**: None.
- **not_applicable**: At aggregate scope this value does not represent per-instance utilization.

## code: CLEAN_SEQUENTIAL

- **advice**: The four metrics are close, indicating clean sequential execution without meaningful gaps or waits. No action is required.
- **next_data**: None.
- **not_applicable**: None.

## code: NORMAL

- **advice**: No diagnostic threshold was met; no action is required.
- **next_data**: None.
- **not_applicable**: None.

## code: NO_DATA

- **advice**: The node has no kernels in the representative step. If source says the module should execute, operator ownership may be incomplete; return to Step 6 and inspect its `op_indices`. If the module was not selected in this run because of a configuration gate, this is expected.
- **next_data**: The node's `op_indices` in `analysis_config.json`; `kernel_attribution.json`.
- **not_applicable**: None.
