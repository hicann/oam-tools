---
name: cann-perf-breakdown-to-ui-json
description: Convert a validated cann-perf-breakdown schema-v2 breakdown (analysis_config_v2.json plus its representative-step kernel rows) into the four backend JSON facts that cann-perf-ui-json-report consumes — analysis config, performance data, normalized timeline, and model_architecture_graph.v1. Use when a breakdown has passed validation and scoring but the UI skill has no inputs yet, when kernels must be attributed to structure nodes without name-similarity matching, when a model has no adapter for this conversion yet, or when diagnosing identity, coverage, or schema mismatches between a breakdown and a report.
---

# Adapt Breakdown to UI JSON

Turn one validated schema-v2 breakdown into the four backend facts the report
runtime reads. This Skill owns exactly the gap between
`cann-perf-breakdown` and `cann-perf-ui-json-report`, and nothing else.

Inputs are read-only. Every derived file goes to `--out`.

The conversion expects the schema-v2 `cann-perf-breakdown` output contract,
including `duplicate_of` markers on duplicate collective records. The optional
end-to-end orchestrator also needs the `cann-perf-ui-json-report` skill for
Stage 3. Install it as a sibling skill or pass its location explicitly:

```bash
python <skill-dir>/scripts/run_pipeline.py \
  --capture-dir <capture-dir> \
  --model-id <model-id> \
  --out <out-dir> \
  --breakdown-config <analysis_config_v2.json> \
  --semantic-review <semantic_review.json> \
  --split-rules <rules.json> \
  --stage3-dir <cann-perf-ui-json-report-dir>
```

Use the individual Step 1-5 commands below when only the Stage 2 facts are
needed. `run_pipeline.py` checks the dependency at the Stage 3 boundary and
fails there instead of producing a partial report that looks complete.

## Scope

```
cann-perf-breakdown        →  THIS SKILL  →  cann-perf-ui-json-report
analysis_config_v2.json        4 UI facts      report/ runtime + HTML
kernel rows (representative)
model source
```

Do not collect profiling data, re-run a model, re-segment layers the breakdown
already segmented, render HTML, or emit optimization advice. A breakdown that
has not reached a convertible validation result and `breakdown_score.json`
`convertible: true` is not ready for conversion; stop and say so instead of
converting it. Tiered score statuses (`verified`, `verified_unbound_scalars`,
`structure_unverified`) describe evidence reach, not different correctness
thresholds; `passed` remains accepted for legacy outputs.

## Non-negotiable rules

- **Never map a kernel by leaf-label similarity.** Attribution evidence is the
  breakdown's own `op_indices`, plus exact operator name, operator type, tensor
  shapes, and position within a consecutive run. Both neighbouring Skills forbid
  name-similarity matching; so does this one.
- **Account for every kernel exactly once.** Assert `len(out) == len(kernels)`
  and that the emitted set contains each kernel object identity once. A
  remainder is a defect, not a rounding difference.
- **Let assertions fail.** Segment boundaries are claims about the capture. When
  an assertion breaks, the structure changed or the capture differs — report it.
  Never widen an assertion, drop a kernel, or fall back to a phase-level owner
  to make a run succeed.
- **Do not invent semantic edges.** Emit an edge only where the breakdown
  declares one: `structures.<group>.branches` gives intra-structure residual/skip
  inputs and output; sequential `children` order gives intra-container activation
  flow; top-level `dataflow.edges` gives cross-structure edges and supersedes the
  legacy linear `model_flow`. Fan-out exists only where it is explicitly declared.
- **Do not fabricate owners.** A timeline event either has evidence-backed
  attribution or stays unmapped. Phase-level fallback owners hide missing work.
- **Source-only nodes carry no metrics.** A structure node the capture never
  observed belongs in `source_only_structure` keyed by `structure_node_id`, not
  `node_id`, so it stays out of the backend node index. It stays visible,
  selectable, and metric-free, and must record a concrete `reason`.
- **Keep runtime auxiliary outside model dataflow.** Sampler windows, token
  sampling, and similar runtime facts live in their own root.
- **No diagnoses or advice.** Time, counts, ratios, and shapes only. Diagnostic
  labels belong to the breakdown's `metrics_report.md`; optimization advice
  belongs to `cann-npu-perfanalysis`. Emitting either here is a contract violation.

Read [references/schema-mapping.md](references/schema-mapping.md) before changing
field names or identity rules.

## Identity contract

The UI validator enforces three rules across the four outputs. Satisfy them by
construction, not by patching afterwards.

- One analysis definition and one performance record per backend `node_id`.
- Every performance `node_id` exists in analysis, and every analysis node that
  carries metrics exists in performance.
- Every nonempty timeline `owner_node_id` resolves to an analysis node.

Choose one `id_namespace` (`model/<model-id>`) and derive every `node_id` from
the breakdown's structural path under it. Set `model_id`, `report_id`, and
`representative_step` identically in all three JSON files. When structure and
run data come from different sources, record both provenances explicitly rather
than blending them into one ambiguous id.

## Step 1 — Verify the breakdown is convertible

```bash
python <skill-dir>/scripts/check_breakdown_ready.py \
  --breakdown <breakdown-dir> \
  --out <work-dir>/readiness.json
```

Requires `schema_version: 2`, a convertible `validation_report.json`,
`breakdown_score.json` with `convertible: true`, `unmapped_ops` empty, and a declared
`trace_scope.kind`. Refuse to continue on `status: exploratory`, on a migrated
config still marked `legacy_unverified`, or when `semantic_review.json` is
absent or its SHA256 binding no longer matches the config.

## Step 2 — Build the node index

```bash
python <skill-dir>/scripts/build_node_index.py \
  --breakdown <breakdown-dir> \
  --namespace model/<model-id> \
  --rename-group <StructureKey>=<node-name> \
  --out <work-dir>/node_index.json
```

Walk `stages`, `structures.<group>.children`, and `runtime_auxiliary` in
declaration order. For each node emit one entry with a stable `node_id`,
`semantic_key`, `node_kind` (`module` / `op` / `runtime_auxiliary`),
`metric_scope`, `name`, `semantic`, `code_ref`, `instance_indices`,
`mapped_kernels`, and `children`.

A breakdown names a repeated group after its source class (`QWenBlock`) while a
report usually addresses it by role (`decoder_layers`). Declare that rename with
`--rename-group`; never derive a role name from a class name heuristically.

The script refuses a node that declares both `children` and `op_indices` — such a
node would count its own kernels twice, once directly and once through
descendants — and refuses two structural nodes colliding on one `node_id`.

Pick `metric_scope` from what the node actually aggregates:

| Scope | Use when |
|---|---|
| `aggregate` | a container summing descendants |
| `all_observed_instances` | a leaf repeated across every layer invocation |
| `single_instance` | a leaf that runs once per step |
| `sampled_window_context` | sampled device context, never compute time |

A repeated layer group becomes one folded node whose `instance_indices` lists
every observed invocation and whose children aggregate the matching kernels from
all of them. Keep the group's source JSON static; per-layer timing is a runtime
overlay, not a structural fact.

## Step 3 — Attribute kernels

```bash
python <skill-dir>/scripts/attribute_kernels.py \
  --breakdown <breakdown-dir> \
  --nodes <work-dir>/node_index.json \
  --split-rules <rules.json> \
  --out <work-dir>/kernel_attribution.json
```

Three evidence sources, in order of authority:

1. **A leaf's own `op_indices`** — the breakdown already proved these.
2. **`trace_instances[].op_range`** — a repeated group declares one
   representative invocation plus a range per invocation. Equal-length ranges
   make the offset exact, so a leaf owning offset *k* in the representative owns
   offset *k* in every other invocation. This is range arithmetic over declared
   facts, not pattern matching, and it carries the bulk of the work: on Qwen-7B,
   64 directly declared claims translate into 1488 more across 31 invocations for
   1552/1552 coverage.
3. **An asserted split rule** — only for runs the breakdown folded into one leaf
   that the report needs separated.

Unequal invocation spans are a hard error: a constant offset would misattribute,
so the script reports which instance differs instead of translating anyway.

After attribution, confirm every non-representative invocation resolved to one
identical profile. On Qwen-7B all 31 translated layers yield exactly 48 kernels
in the same per-node distribution; more than one distinct profile means the
invocations are not interchangeable and the translation assumption is wrong.

For a folded run that must be split, state the expected profile — operator types
in order, run length — in the rules file so a structural change fails loudly:

```json
{"splits": [{
  "name": "mlp_gate_up",
  "source_node_id": "model/<id>/decoder_layers/mlp/gate_up_proj",
  "expect_length": 4,
  "expect_op_types": ["MatMulV2", "Swish", "MatMulV2", "Mul"],
  "assign": [
    {"target_node_id": "model/<id>/decoder_layers/mlp/w2",         "range": [0, 1]},
    {"target_node_id": "model/<id>/decoder_layers/mlp/activation", "range": [1, 2]},
    {"target_node_id": "model/<id>/decoder_layers/mlp/w1",         "range": [2, 3]},
    {"target_node_id": "model/<id>/decoder_layers/mlp/activation", "range": [3, 4]}
  ]
}]}
```

The split is applied to the representative run and every translated invocation.
Each translated claim carries the exact representative `op_index` it came from;
surplus communication rows must resolve to one split target. The rule fails if
any representative op is unassigned or a translated row is ambiguous.

Read the assignment order off the model source, not off the label. In a SwiGLU
where the first MatMul feeds the activation, that MatMul is the up projection
even when a fused label lists gate first — check which tensor reaches `Swish`.

Handle runs that straddle a layer boundary explicitly rather than truncating
them. Record both labels when the capture's own segmentation name differs from
the structural leaf name: keep the structural name in `submodule` and preserve
the original as `capture_submodule`.

The script fails when any kernel is unattributed, attributed twice, or attributed
to a node absent from the index.

## Step 4 — Emit the backend facts

```bash
python <skill-dir>/scripts/emit_ui_facts.py \
  --breakdown <breakdown-dir> \
  --nodes <work-dir>/node_index.json \
  --attribution <work-dir>/kernel_attribution.json \
  --model-id <model-id> --report-id <report-id> \
  --peak-bf16-tflops <value> --dtype-bytes <value> \
  --out <out-dir>
```

Writes `<prefix>_analysis_config.json`, `<prefix>_perf_data.json`, and
`<prefix>_timeline.json`. It refuses to run below 100% attribution coverage.

A node with zero attributed kernels is emitted into `source_only_structure` with
a generated `reason`; replace that text with the concrete capture fact once you
know it, because "no kernel attributed" describes the symptom, not the cause.

The fourth fact — `outputs/model_architecture_graph.json` — needs the declared
`branches` and top-level `dataflow`. Build it with
`scripts/build_architecture_graph.py` per
[references/schema-mapping.md](references/schema-mapping.md) § Graph. Derive
activation edges from sequential `children` order and residual edges from
`structures.<group>.branches`, then resolve cross-structure endpoints and optional
ports from `dataflow.edges`, one edge identity per declaration. Never infer an
edge the breakdown does not declare.

Metrics come from the attributed kernels only:

| Field | Definition |
|---|---|
| `time_us` | sum of attributed kernel durations |
| `time_pct` | `time_us / total_time_us × 100` |
| `nops` | count of attributed kernels |
| `hbm_mb` | logical shape × dtype bytes; a comparison estimate, never measured traffic |
| `gflops` | from declared shapes |
| `mfu_bf16_pct` / `mfu_int8_pct` | mapped effective compute over declared peak; `null` when unavailable |
| `aicore_time_us`, `aiv_time_us`, `aicore_time_pct` | AI Core / AI Vector counter time, and cube time as a share of wall |
| `mac_ratio`, `mte2_ratio`, `mte1_ratio`, `scalar_ratio`, `fixpipe_ratio` | cube pipeline breakdown, time-weighted |
| `vec_ratio`, `aiv_mte2_ratio` | vector pipeline breakdown, time-weighted |
| `cube_utilization_pct` | cube occupancy, time-weighted |
| `aic_total_cycles`, `aiv_total_cycles` | raw core-cycle totals; no clock needed |
| `aicore_cycle_time_us`, `aiv_cycle_time_us` | cycles re-expressed as time; `null` without a known clock |
| `counter_coverage` | how many of the node's kernels carried counters at all |
| `op_ratio` | operator-type time share within the node |

Counter fields come from the `aic_*` / `aiv_*` CSV columns via
`raw_ops_details.json` — `raw_ops.json` has only identity and timing, so
attribution must read the details file or every counter metric emits `null`.
Ratios are **time-weighted** by the counter time they describe; a flat mean lets
a 2 µs Cast outweigh an 84 µs MlaPrologV3. `mac_ratio` vs `mte2_ratio` is the
compute-bound vs memory-bound read.

The perf JSON also carries `aicore_freq_mhz` plus a `device_profile` block from
stage 1's `device_freq.py`: the clock declared by the trace's `AI Core Freq`
counter (usually just two samples — a nameplate, not a curve) cross-checked
against a per-kernel derivation from `cycles / time / cores`. Derived wins;
a mismatch is reported, never averaged away. Always divide cycle counters by the
core count (`Mix Block Dim` for AIV on mixed kernels, else `Block Dim`) —
`aic_total_cycles` is core-summed, so skipping it overstates the clock by the
core count, ~22× on the DS3.2 capture.

Emit every key even when the value is `null`. A missing key and a null value are
different claims; `–` in the UI must mean unavailable, never zero. This applies
hardest to the clock: a capture profiled without counters reports `null`, never
an assumed frequency, because every cycle-derived metric divides by it.

## MoE expert inventory

`build_expert_inventory.py` writes `<model-id>_expert_inventory.json` for any
model declaring experts. It lists **every** declared expert (DS3.2: 256 routed +
1 shared = 257) and gives each a `data_state` saying precisely what the capture
measured. Two independent reasons keep 257 declared experts from becoming 257
measurements, and they must not be conflated:

| `data_state` | Meaning |
|---|---|
| `measured` | own kernels, real per-expert time. The shared expert: replicated on every rank, not fused |
| `fused_measured` | inside a measured kernel, but that kernel covers all resident experts at once — no figure is this expert's alone |
| `remote_ep_shard` | executes on another expert-parallel rank; time **unknown**, not zero |
| `residency_unresolved` | resident count known, global identity not — see below |

**Expert parallelism.** With `moe_ep_size = N` only `n_routed_experts / N`
experts have weights on the profiled rank. On the DS3.2 capture that is **16 of
256**; the other 240 appear only as the all-to-all that dispatches tokens to
them. `moe_ep_size` is derived from the leading dimension of the stacked expert
weight in the `GroupedMatmul` shapes — an observation from the capture, not a
config assumption. Never read the declared *total* from those shapes: they only
ever show one rank's slice, so doing so under-reports the model by the EP factor.

**Kernel fusion.** The resident experts run as one `GroupedMatmul` over a stacked
weight, with `group_list` giving per-expert token counts and the profiler
reporting a single duration. Per-expert time is not recoverable from it. Dividing
the fused duration by token share would produce numbers the hardware never
measured — a validator check rejects any per-expert `time_us` on a non-`measured`
expert for exactly this reason.

**Residency identity needs the rank.** Rank *r* owns
`[r*local, (r+1)*local)`, and msprof has no reason to record `ep_rank`. Without
`--ep-rank` the resident *count* is known but the *identities* are not: defaulting
to rank 0 would assert experts 0–15 ran when the capture may be rank 5's
(80–95). So those entries report `residency_unresolved` and no expert is claimed
resident. Pass `--ep-rank` to resolve.

Never let a non-compute node win default selection. A sampler-window node's wall
clock is not compute time: set `time_us: null` and keep the span in a separate
field such as `sampled_window_span_us`. Ordering nodes by duration otherwise
puts a 0%-time-share node first and the Inspector opens empty.

For the graph, require `schema_version: model_architecture_graph.v1`, a
`section/source_architecture` root, a separate `section/runtime_auxiliary` root,
nonempty `roots`, and explicit `edges`. Derive activation edges from sequential
`children` order and residual edges from `branches`, preserving each declared
`inputs`/`output` pair as its own edge identity with tensor metadata and
provenance. Preserve `dataflow.edges` as explicit cross-structure edges; resolve
their `structure` plus optional `source_port` / `target_port` without reducing a
fork or join to `model_flow`. Mark every item's `dataState` (`mapped` /
`source_only` / `runtime`) and `origin`.

## Step 5 — Validate the conversion

```bash
python <skill-dir>/scripts/validate_conversion.py \
  --out <out-dir> \
  --attribution <work-dir>/kernel_attribution.json
```

Checks identity consistency across the three JSON files, one definition and one
record per `node_id`, 100% timeline owner resolution, kernel-count conservation
against the breakdown, that no `source_only` node carries metrics, that every
required metric key is present, and that graph edges resolve with tensor
metadata and provenance.

Then hand off to the UI Skill's own validators, which are authoritative for the
report:

```bash
node <ui-skill>/scripts/validate-architecture-graph.mjs \
  <out-dir>/outputs/model_architecture_graph.json \
  --source-root section/source_architecture --require-semantic-port-policy
```

## Reporting the result

State the numbers from the produced files: node count, mapped versus
source-only, kernel count and attribution coverage, timeline events, and
`total_time_us`. Show the zero-remainder accounting explicitly, for example
`1643 = 1 + 61 + 30×51 + 50 + 1`, so the segmentation is auditable.

Report failures honestly. A validator that hard-codes another model's node IDs
or module names fails on a correct conversion; say which assertion and why
rather than renaming nodes to satisfy it. Never suppress a failure by generating
data the capture does not contain.

## Handle failures

### Kernel count mismatch

Do not redistribute the remainder. Find the run whose assertion is wrong, print
its operator types and shapes, and compare against the model source. A changed
fusion or a different capture is the usual cause.

### Node not in index

The breakdown declares a structural path the walk missed, or two nodes collide
on one `node_id`. Fix the namespace derivation; never merge two distinct
structural nodes into one id.

### Timeline owner unresolved

Every event needs an owner that exists in analysis. Sampled or runtime events
get an explicit runtime-auxiliary node — not a phase-level fallback, and not a
compute node they do not belong to.

### Metrics present on a source-only node

The node was observed after all, or it was misclassified. Decide from capture
evidence: move it into the mapped set with real metrics, or remove the metrics
and keep the documented `reason`.

### Adapter missing for a model family

Write the segmentation assertions from the model source and the breakdown's
`branches`, and keep them as executable assertions rather than comments. Do not
copy another family's expected profile; a Dense SwiGLU run and an MoE expert run
have different shapes and lengths.
