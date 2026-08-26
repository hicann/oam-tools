---
name: cann-perf-breakdown
description: |
  Break down NPU performance data. Use model source as primary evidence to derive structure, then attach kernel_details.csv performance data to that structure.
  Trigger for kernel_details.csv analysis, model-level performance breakdown, LLM bottleneck analysis, source-only architecture extraction, or performance-only diagnosis delegated to cann-npu-perfanalysis.
  Applies to any Transformer family and assumes no fixed module or kernel names.
---

# NPU Performance Breakdown

Break down NPU profiling `kernel_details.csv` into a Transformer hierarchy and produce verifiable structured JSON and performance metrics.

---

## Supported Scenarios

| Scenario | Description |
|---|---|
| LLM performance analysis | Analyze any Transformer family |
| Hierarchical timing | Attribute time to Embedding, Blocks, Head, and other stages |
| Block internals | Analyze Attention, MLP, Norm, and nested submodules |
| Architecture detection | Identify MLA, MoE, GQA, and similar features |
| Source only | Produce a validated structure without binding performance data; express branches with `branches` |
| Performance data only | Delegate eight-dimensional diagnosis to the repository's `cann-npu-perfanalysis` skill |

## Entry Dispatch

Inspect the working directory and select the first matching mode:

| Condition | Mode | Action |
|---|---|---|
| Model source such as `*modeling*.py` plus `kernel_details.csv` or `raw_ops*.json` | **Mode A** | Run the complete schema-v2 11-step scoring loop; emit metrics and enter Stage 2 only after acceptance |
| Model source only | **Mode B** | Extract and validate `model_manifest.json`, then emit non-empty v2 `model_structure.json` with `op_indices=[]` and optional `branches`; see `references/mode_b_branches.md` |
| Performance data only | **Mode C** | Delegate to `cann-npu-perfanalysis`; see `references/mode_c_delegate_en.md` |

Mode C does not enter structure breakdown. Mode A runs all 11 steps. Mode B runs at least architecture extraction, validation, and structure-tree generation.

### Schema-v2 distinctions

- Learned model layers in `architecture.layer_groups` and `prediction_modules` are not runtime calls in `trace_instances`.
- In MTP/speculative decoding, an outer loop calling the same learned decoder layer N times means one learned layer plus N invocations. Never create N learned layers or synthetic indices such as 6, 7, and 8.
- `children` expresses containment only. Residuals, parallel paths, and skips must be declared explicitly in `branches`; downstream consumers must not infer edges from child order.
- Performance exists only for captured scope. Never extrapolate metrics to uncaptured layers. Optional `trace_scope` may be `full_model`, `rank_local`, `pipeline_stage_local`, or `unknown`; without evidence, omit it or use `unknown`.

### Four-way coverage classification

- `mapped_model_ops`: model-module operators owned through trace instances, stages, and structure leaves.
- `mapped_runtime_ops`: runtime support operators in `runtime_auxiliary`.
- `excluded_profiler_ops`: pure profiler/bookkeeping only, with an allowed `reason_code` and `evidence`. Never exclude main computation such as MatMul, Attention, Norm, MoE, communication, Gather, KV cache, or sampling.
- `unmapped_ops`: unknown ownership means mapping is incomplete and strict validation fails. A `reason` does not count as coverage.

`--allow-unmapped` is exploratory and never yields formal `passed`. Every representative-step operator must belong to one of the first three classes. Follow `references/ai_mapping_protocol_en.md`.

One hundred percent kernel coverage does not prove semantic correctness. Source/trace semantic review must also validate Q/K/V branches, residual paths, layer boundaries, and tail stages.

## Mode A: 11-Step Scoring Loop

```text
Step 1  Discover inputs and select a mode
Step 2  extract_model_manifest.py -> model_manifest.json
Step 3  validate_architecture.py
Step 4  analyze_kernels.py -> raw_ops.json, raw_ops_details.json, raw_ops.compact.json
Step 4b device_freq.py -> device_freq.json
Step 5  extract_dataflow.py -> dataflow_source.json
Step 6  AI mapping per ai_mapping_protocol_en.md plus map_trace_instances.py
        -> schema-v2 analysis_config.json
Step 7  Build one reusable structures tree per layer group and validate sublayers
Step 8  Complete source/trace semantic review -> semantic_review.json
Step 9  run_validation.py -> validation_report.json with status exactly passed
Step 10 score_breakdown.py -> breakdown_score.json with convertible=true
        Otherwise revise the historical best candidate from iteration_request.json and return to Step 8
Step 11 compute_metrics.py, only after acceptance
        -> metrics_report.md and advisory metrics_findings.json
```

See `references/breakdown_scoring_en.md` for scoring and stop rules. Any configuration change invalidates the old semantic-review SHA256 binding.

### Stop conditions

Only two conditions stop the loop:

1. `breakdown_score.convertible == true`: runnable correctness is at least 95%; every runnable core dimension reaches its original ratio (architecture 22/25, dataflow and branches 27/30, layer/submodule boundaries 18/20); exact coverage and evidence pass; and every hard gate passes. Evidence-qualified status is `verified`, `verified_unbound_scalars`, or `structure_unverified`. `passed` is legacy compatibility only.
2. `--max-iterations`, default 10, is exhausted without acceptance; status is `blocked_max_iterations`.

`score` is a raw value on a nominal 100-point scale. `runnable_max` is the denominator supported by available inputs. Missing checkpoint/source evidence removes an unanswerable scalar check from the denominator and lowers the evidence ceiling rather than permanently failing a correct structure. Downstream eligibility must use `convertible`, not a new hard-coded `score >= 95` test.

Early stop is disabled by default with `--stall-limit 0`. Enable it explicitly with `--stall-limit N`.

At the iteration limit, report the current score, each failed dimension's deficit, blocked semantic checks, and missing evidence. Never improve a score by lowering gates, deleting main kernels, or expanding exclusions.

Architecture extraction in Steps 2-3 must scan the complete source. Sparse source reads are allowed only for issue repair after Step 8. The skill package must not retain model source, real profiling captures, or test fixtures; callers and repository tests provide validation inputs externally.

### Semantic review and unified validation

```bash
python scripts/prepare_semantic_review.py \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --source-dir /path/to/model-source \
  -o outputs/semantic_review_request.json
# Read source and the representative trace completely, then create outputs/semantic_review.json.

python scripts/run_validation.py \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --source-dir /path/to/model-source \
  --semantic-review outputs/semantic_review.json \
  -o outputs/validation_report.json
# status other than passed blocks formal reporting. --allow-warnings is triage only.

python scripts/score_breakdown.py \
  -v outputs/validation_report.json \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --semantic-review outputs/semantic_review.json \
  -o outputs/breakdown_score.json
# If convertible is not true, consume iteration_request.json and continue. Do not report formally.
```

## Step 1: Extract One Profiling Step

Enumerate steps and choose a stable non-warmup representative. Without `-s`, `analyze_kernels.py` groups by kernel count and kernel-type distribution. It skips the earliest step only when its kernel sum is a clear outlier against the median of later steps, then selects the closest later step. Use `-s` only to reproduce a specific step.

```bash
python scripts/analyze_kernels.py \
  -f kernel_details.csv \
  -o outputs/raw_ops.json \
  -d outputs/raw_ops_details.json \
  -m outputs/steps_summary.md \
  --compact-out outputs/raw_ops.compact.json
```

| Output | Purpose |
|---|---|
| `steps_summary.md` | Per-step count, kernel types, duration, and selection reason |
| `raw_ops.json` | Selected-step operator summary for enrichment and validation |
| `raw_ops_details.json` | Selected-step records with all CSV columns |
| `raw_ops.compact.json` | Folded AI input without timing fields |
| `device_freq.json` | Measured AI Core frequency and cross-check used by cycle-derived metrics |

Each operator includes `org_index`, its zero-based row in `kernel_details.csv`.

### AI Core frequency

```bash
python scripts/device_freq.py \
  -d outputs/raw_ops_details.json \
  --trace ASCEND_PROFILER_OUTPUT/trace_view.json \
  -o outputs/device_freq.json
```

Report two independent sources without averaging:

- `declared`: sparse `AI Core Freq` events in `trace_view.json`, normally a nominal value rather than a curve.
- `derived`: per-kernel `cycles / time / cores`, the value used by downstream cycle-derived metrics. On conflict, use `derived` and record a mismatch in `cross_check.agreement`.

Core count is essential because `aic_total_cycles` is summed over all participating cores. For AIV counters on `MIX_AIC`, prefer `Mix Block Dim`, since vector and cube core counts differ.

If counters are absent, frequency and every derived field are `null`; never substitute an assumed frequency.

### MoE expert facts

For MoE, `model_manifest.json` contains `n_routed_experts`, `n_shared_experts`, and `num_experts_per_tok`, each with source evidence. These are AST-derived declarations, not kernel-shape inference. Never infer total experts from the first dimension of GroupedMatmul weights; that is often only the local EP shard.

Stage 2 `build_expert_inventory.py` generates the per-expert inventory because it needs Stage 2 kernel attribution and measured shared-expert timing. This skill only extracts the three declarations and their references.

Optionally generate candidate layer boundaries:

```bash
python scripts/segment_layers.py -r outputs/raw_ops.json -o outputs/op_segments.json
```

Candidates are hints only; source semantics determine final boundaries. See `references/kernel_data_guide_en.md`.

## Step 2: Break Down Model Structure

Follow `references/structure_analysis_guide_en.md` D.1:

1. Select the representative step and decoder-layer instance.
2. Read model source and derive modules and stable function boundaries.
3. Locate decoder boundaries in the operator sequence.
4. Map every operator to source-backed module/function semantics.
5. Write `analysis_config.json`.
6. Enrich it:

```bash
python scripts/analyze_kernels.py --enrich \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json
```

The guide is authoritative for sources, names, boundaries, and explicit dataflow edges. `shape_semantic` is optional and is not a formal gate.

## Step 3: Validate, Score, and Iterate

Follow `references/structure_analysis_guide_en.md` D.2. Use the unified entry point, which emits one valid JSON document; never append multiple JSON objects with `>>`.

```bash
python scripts/run_validation.py \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --source-dir /path/to/model-source \
  --semantic-review outputs/semantic_review.json \
  -o outputs/validation_report.json
```

- Create a current, hash-bound nine-item semantic review before validation.
- Run scoring afterward. Generate metrics and enter `cann-perf-breakdown-to-ui-json` only when semantic review and validation pass and `convertible=true`.
- Otherwise edit the best candidate referenced by `base_config_for_revision`, correcting only failed dimensions, blocking issues, and validation issues. Never edit `immutable_best_snapshot`.
- Re-enrich, rereview, revalidate, and rescore after every edit. Do not reuse an old review.
- `run_breakdown.py` creates requests and deterministic gates but does not invoke AI. The executing agent must consume mapping, semantic-review, and iteration requests until a stop condition.
- Evaluate at most 10 rounds by default. Read `remaining_iterations`; use early stop only when explicitly configured.
- Run individual checks only for diagnosis. Each `--json` command emits one JSON object.
- Shape validation is optional diagnostic work. MT1 is `info` by default because a partial capture cannot refute source-derived architecture.

## Step 4: Compute Performance Metrics

```bash
python scripts/compute_metrics.py \
  -r outputs/raw_ops_details.json \
  -c outputs/analysis_config.json \
  -o outputs/metrics_report.md \
  --findings-out outputs/metrics_findings.json \
  -d 3
```

| Metric | Definition | Meaning |
|---|---|---|
| `wall_ms` | Last kernel end minus first kernel start | Wall-clock duration including gaps |
| `busy_union_ms` | Union of device-busy intervals | Actual non-overlapping busy time |
| `kernel_sum_ms` | Arithmetic sum of kernel durations | Total work ignoring overlap |
| `total_cost_ms` | Sum of duration plus wait | Full cost including waits |

Derived values include parallelism (`kernel_sum_ms / wall_ms`), `bubble_ms`, and wall share of the step.

| Condition | Threshold | Diagnosis |
|---|---|---|
| kernel sum / wall | > 1.5 | High multi-stream overlap |
| kernel sum / wall | > 1.2 | Moderate overlap |
| wall / busy union | > 1.5 | Gap bubble |
| total cost / kernel sum | > 1.3 | Significant waiting; inspect wait anchors |
| busy union / wall | 80%-95% | Good utilization |
| busy union / wall | < 80% | Low utilization |
| busy union, wall, kernel sum | within 10% | Clean sequential execution |

Apply metrics to decoder layers and subnodes, stages, and runtime auxiliary nodes.

`metrics_findings.json` is advisory only. Codes are `STREAM_PARALLEL_HIGH`, `STREAM_PARALLEL_MID`, `GAP_BUBBLE`, `WAIT_DOMINANT`, `UTIL_GOOD`, `UTIL_LOW`, `CLEAN_SEQUENTIAL`, `NORMAL`, and `NO_DATA`. Findings never affect validation, score, hard gates, stop conditions, or iteration. They say what data to inspect next and must not assert root cause. Aggregate-scope advice cannot be extrapolated to one instance. Runtime advice text is loaded from `references/diagnosis_advice.md`; `references/diagnosis_advice_en.md` is its read-only English translation.

## Outputs

| File | Description |
|---|---|
| `raw_ops.json` | Selected-step operator summary |
| `raw_ops_details.json` | Selected-step full records |
| `raw_ops.compact.json` | Folded AI view |
| `device_freq.json` | Measured and cross-checked AI Core frequency |
| `model_manifest.json` | Source-derived architecture truth and MoE facts |
| `dataflow_source.json` | Source-derived `forward()` dataflow truth |
| `op_segments.json` | Optional boundary candidates |
| `analysis_config.json` | Final Mode A breakdown |
| `model_structure.json` | Mode B structure |
| `semantic_review_request.json`, `semantic_review.json` | Hash-bound review request and conclusions |
| `validation_report.json` | Unified Step 9 validation |
| `breakdown_score.json` | Step 10 score, dimensions, hard gates, and actions |
| `iteration_history.json` | Round history and best snapshots |
| `iteration_request.json` | Targeted next-round request |
| `iterations/` | Immutable round snapshots |
| `metrics_report.md` | Performance report with advisory diagnoses |
| `metrics_findings.json` | Structured advisory findings with `advisory_only: true` |

## References

| File | Use |
|---|---|
| `references/structure_analysis_guide_en.md` | All Step 2 and Step 3 structure rules |
| `references/kernel_data_guide_en.md` | `kernel_details.csv` fields |
| `references/mode_b_branches.md` | Mode B branch representation |
| `references/mode_c_delegate_en.md` | Mode C delegation |
| `references/diagnosis_advice_en.md` | English translation of the runtime diagnostic-advice source |
| `references/ai_mapping_protocol_en.md` | Mandatory full-operator mapping protocol |
| `references/semantic_review_protocol_en.md` | Required source/trace semantic review |
| `references/breakdown_scoring_en.md` | Scoring, hard gates, iteration, and stopping |
| `scripts/extract_model_manifest.py` | Architecture extraction |
| `scripts/validate_architecture.py` | Global architecture validation |
| `scripts/check_manifest_trace.py` | Manifest/trace cross-check |
| `scripts/analyze_kernels.py` | Step extraction and enrichment |
| `scripts/device_freq.py` | Frequency derivation and cross-check |
| `scripts/extract_dataflow.py` | AST-derived dataflow truth |
| `scripts/check_dataflow.py` | D1-D7 source/config checks |
| `scripts/detect_trace_scope.py` | Optional capture-scope detection |
| `scripts/segment_layers.py` | Boundary candidates |
| `scripts/map_trace_instances.py` | Invocation mapping |
| `scripts/check_structure.py` | Tree well-formedness |
| `scripts/validate_shapes.py` | Optional shape diagnostics |
| `scripts/check_op_coverage.py` | Exact union coverage |
| `scripts/check_sublayers.py` | Representative subtree consistency |
| `scripts/prepare_semantic_review.py`, `scripts/validate_semantic_review.py` | Review preparation and deterministic validation |
| `scripts/run_breakdown.py` | Forward-evaluation driver and request gates |
| `scripts/run_validation.py` | Unified validation |
| `scripts/score_breakdown.py` | Deterministic scoring |
| `scripts/migrate_config.py` | v1-to-v2 migration with `legacy_unverified` |
| `scripts/regression_check.py` | Structural and semantic architecture regression |
| `scripts/compute_metrics.py` | Metrics and advisory findings |
| `schemas/*.schema.json` | Strict artifact schemas |
| `adapters/*.py` | Family-specific architecture extraction |
