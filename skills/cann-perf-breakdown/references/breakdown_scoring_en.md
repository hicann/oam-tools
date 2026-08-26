# Model Breakdown Scoring and Iteration Protocol

Use this protocol for formal Mode A breakdowns. Scoring does not replace source review. It converts evidence already produced by source inspection, trace analysis, and the unified validator into a stable and comparable quality gate.

## 1. Acceptance Conditions

A breakdown may be converted into a formal downstream report only when all conditions below hold:

1. Runnable-check correctness is at least 95%: `score / runnable_max >= 95%`. `score` remains on a nominal 100-point scale and must not be used alone as the gate. Checks that genuinely cannot run because inputs are absent leave `runnable_max`; the evidence-qualified conclusion explicitly reports the downgrade.
2. **Every runnable core dimension** reaches its original minimum ratio:

   | Dimension | id | Maximum | Minimum |
   |---|---|---:|---:|
   | Architecture integrity | `architecture_integrity` | 25 | 22 |
   | Dataflow and branch correctness | `dataflow_branch_correctness` | 30 | 27 |
   | Layer/submodule boundaries | `layer_submodule_boundaries` | 20 | 18 |
   | Exact kernel coverage | `kernel_exact_coverage` | 20 | 20 |
   | Evidence and traceability | `evidence_traceability` | 5 | 4 |

   Both gates must operate independently: enforce each core ratio and the total correctness ratio separately. When a dimension is genuinely unrunnable because its input is absent, do not award full points and do not let it permanently block an otherwise correct breakdown. Kernel coverage and evidence are always runnable and retain their original thresholds.

   The former Shape/Semantic Consistency and Trace Instance/Scope dimensions were removed. Their 20 points moved to dataflow (+10), architecture (+5), and kernel coverage (+5). Missing `shape_semantic` and a single-step capture describe what evidence is present, not whether the breakdown is correct. Those dimensions rewarded evidence that could not be falsified. Their replacements are machine-checkable against source.

   Each `warning` deducts 20% of that check's weight (`WARNING_STEP`). The old quality set `{1.0, 0.6, 0.0}` made one warning cost 40%, turning thresholds such as 27/30 into a hidden zero-warning rule. One warning is now tolerable; many warnings are not.
3. No hard gate is present.
4. All nine `semantic_review.json` checks and its overall status are `passed`, and artifact SHA256 values are current. The sole exception is a `warning` evidence-gap finding on `source_model_identity`: it reports a missing scalar in the inputs, not a semantic error, and becomes non-blocking `info`. See the sole-exception section in `semantic_review_protocol_en.md`. The capture-tier mechanism below enforces its conclusion ceiling.
5. `run_validation.py` status is `passed`. `passed_with_warnings` and `exploratory` are diagnostic only and cannot produce a formal report. Data-availability findings (`A1`, `MT1`, `MA1`, `SR_EVIDENCE_GAP_FINDING`) use `info`, because they report absent scalar evidence rather than a breakdown defect. Capture tier enforces the real ceiling: tier A removes the eight `source_model_identity` points from the denominator, so `runnable_max` is 92, below 95, and the conclusion is capped at `verified_unbound_scalars`. Using `warning` would make `GATE_VALIDATION` return `needs_iteration`, incorrectly treating absent evidence as a fixable breakdown error.

The final `status` states what the evidence supports: `verified`, `verified_unbound_scalars`, `structure_unverified`, `exploratory`, or `needs_iteration`. The first three have `convertible=true`; `passed` exists only for pre-tier compatibility. Never lower these quality thresholds during iteration.

## 2. The 100-Point Scale

| Dimension | Points | Primary evidence |
|---|---:|---|
| Architecture integrity | 25 | architecture/regression plus `source_model_identity` and `module_inventory_complete` |
| Dataflow and branch correctness | 30 | `check_dataflow.py` D1-D7, structure/sublayers, and semantic review of Q/K/V and residuals |
| Layer/submodule boundaries | 20 | structure/coverage/sublayers plus layer, tail, runtime, and code-reference review |
| Exact kernel coverage | 20 | Exact union of model/runtime/excluded for the representative step; missing, duplicate, out-of-range, and unmapped must all be zero |
| Evidence and traceability | 5 | `source_of_truth`, `code_ref`, manifest `source_ref`, and `evidence_gaps` |

Dataflow has the highest weight because it is both error-prone and deterministically checkable. `forward()` is the dataflow graph; source/config contradictions do not depend on AI self-reporting.

`shape_semantic` and `trace_scope` may remain as optional annotations, but they do not affect scoring or the formal `run_validation.py` gate.

`scripts/score_breakdown.py` computes scores only from structured artifacts and does not accept a manually supplied total.

## 3. Hard Gates

Any item below requires another breakdown even when the score is at least 95:

- Unified validation is not `passed`.
- `semantic_review.json` is missing or failed, or its artifact SHA256 values do not match current config/raw/manifest files.
- `unmapped_ops` is non-empty, or coverage has nonzero unmapped, missing, duplicate, or out-of-range counts.
- A migrated v1 result remains `legacy_unverified`.
- Mode A lacks source truth or usable node `code_ref` values while claiming exact model attribution.
- Validation found a learned-layer count, MTP invocation, Dense/MoE, Q/K/V, residual, or layer-boundary conflict.
- `check_dataflow.py` emits error-level D1, D2, or D5: a source residual merge has no declared `branches`, branch direction is reversed and bypasses nothing, or a runtime-data-dependent source branch lacks an explicit `deviations` selection. These are direct source/config contradictions, not coverage or annotation issues.

Without source, `check_dataflow` abstains. Absence is not a hard failure, but it is not validation evidence; formal Mode A requires source.

Never clear a failure by deleting main-compute kernels, expanding `excluded_profiler_ops`, fabricating `source_ref`, merging independent branches, or lowering thresholds.

## 4. Closed-Loop Iteration

Execute every round in this order:

1. Generate a candidate `analysis_config.json` from source, manifest, raw operators, and `dataflow_source.json`.
2. Run enrichment and generate `semantic_review_request.json`. After complete source and trace review, fill `semantic_review.json`.
3. Run `run_validation.py` and `score_breakdown.py`.
4. Run report and metrics generation only after acceptance.
5. Otherwise read `iteration_request.json`, revise only `blocking_issues`, `failed_dimensions`, and `required_actions`, and restart at step 2.

Every `analysis_config.json` change requires a new semantic review. When the old review hash is stale, the driver stops at `awaiting_semantic_review`; the candidate is not recorded as a low-scoring round.

The driver does not call AI to edit candidates. The agent executing this skill must consume `ai_mapping_request.json`, `semantic_review_request.json`, and `iteration_request.json` and continue mapping, review, and targeted correction until acceptance, a stop condition, or a genuine lack of new evidence.

`run_breakdown.py` stores each round in `iterations/` and maintains `iteration_history.json`. Edit the candidate referenced by `iteration_request.json.base_config_for_revision`. Treat `immutable_best_snapshot` as read-only. A lower-scoring candidate never becomes the new baseline.

### 4.1 Stop Conditions

Only two stop conditions exist:

1. **Accepted:** `breakdown_score.convertible == true`, meaning runnable correctness is at least 95%, every runnable core dimension reaches its ratio, no hard gate exists, and validation and semantic review both pass. Respect the evidence-qualified status; do not misclassify a nominal score below 95 for `verified_unbound_scalars` as requiring iteration.
2. **Iteration limit:** `--max-iterations` rounds, default **10**, have been evaluated without acceptance; status becomes `blocked_max_iterations`.

The driver no longer stops after two non-improving rounds by default. `--stall-limit` defaults to `0`, disabling early stop. To enable it, pass `--stall-limit N`, such as 3. Only N consecutive rounds that neither exceed the historical best score nor reduce hard gates/failed dimensions produce `blocked_no_progress`.

Reducing hard gates or failed dimensions counts as progress even when the score is equal. The agent must use `remaining_iterations` and `consecutive_non_improving_rounds` from `iteration_request.json`; do not stop at `needs_iteration` and do not repeat the same candidate indefinitely.

At `blocked_max_iterations`, report the current score, the deficit for every failed dimension, and the root reason the breakdown remains incorrect, including missing evidence or the semantic check that cannot pass. Do not report only a score.

## 5. Outputs

| File | Meaning |
|---|---|
| `breakdown_score.json` | Current total, dimension scores, hard gates, and corrective actions |
| `semantic_review_request.json` / `semantic_review.json` | Review task and evidence-backed conclusions for the current candidate |
| `iteration_history.json` | All round scores, improvement status, and best-config snapshots |
| `iteration_request.json` | Failed dimensions, hard gates, constraints, and next-round work |
| `iterations/iteration_N_analysis_config.json` | Candidate snapshot for round N |
| `iterations/iteration_N_semantic_review.json` | Semantic-review snapshot for round N |
| `iterations/iteration_N_validation_report.json` | Unified-validation snapshot for round N |
| `iterations/iteration_N_breakdown_score.json` | Score snapshot for round N |
