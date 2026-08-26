# Structure Analysis Guide

This guide defines how to derive `analysis_config.json` from model source and `raw_ops.json`. The goal is a correct, clear, and stable architecture representation for module-level timing. **Source semantics determine the breakdown; the kernel sequence locates and validates it.**

## Contents

- [A. Model Structure Tree](#a-model-structure-tree): node sources, names, boundaries, and ambiguity resolution
- [B. Kernel Nodes](#b-kernel-nodes): exact ownership of `raw_ops` operators
- [C. Output Format](#c-output-format): fields, tree rules, and explicit dataflow edges
- [D. Workflow](#d-workflow): Step 2 breakdown and Step 3 review
- [E. Authoritative Schema-v2 Definitions](#e-authoritative-schema-v2-definitions): learned layers, runtime invocations, and exact coverage

Two rules apply everywhere:

1. **Source is primary evidence; trace is supporting evidence and can falsify coverage in only one direction.** One capture normally contains one step and one rank after partitioning and fusion, so it observes a subset of all source paths.

   | Difference | Meaning | Verdict |
   |---|---|---|
   | Present in trace, absent from breakdown | The operator executed but has no owner | Error; C1/C6 block it |
   | Present in breakdown, absent from trace | An unselected branch, another rank's shard, fused operation, or skipped layer | Not an error; at most `info` |
   | Every traced operator has an owner | Coverage is complete | Source remains authoritative; trace cannot adjudicate scalars such as total layers or experts |

   Trace can falsify only coverage. Reversing either direction treats uncaptured data as a defect and makes identical inputs produce capture-dependent conclusions. The implementation contract is `TRACE_CAN_ONLY_FALSIFY_COVERAGE` and `trace_disagreement_severity()` in `breakdown_common.py`.
2. **`children` expresses containment only.** Adjacency does not imply a dataflow edge. Declare residuals, parallel branches, and skips explicitly in `branches`; an undeclared edge does not exist downstream.

## A. Model Structure Tree

### A.1 Allowed node sources

Every node must come from exactly one source below. Do not invent nodes merely to increase granularity. Distinct invocation instances of the same module definition remain distinct instances.

| Source | Meaning | Operator coverage |
|---|---|---|
| Source `torch` module | An `nn.Module` explicitly called on the execution path; the primary node source | Every operation produced by its forward, including Cast, Reshape, and quantization details |
| Stable source function | A clearly scoped, stable semantic function without a module attribute; use only inside an existing module or stage | Every operation inside the function |
| Independent communication stage | all-gather, reduce-scatter, all-to-all, or all-reduce with clear boundaries and no natural enclosing module | One communication call plus necessary adjacent bridge operations |
| Explicit canonical model semantic | One clear main kernel surrounded by implementation details; examples include activation, dispatch, and combine | Main kernel plus its implementation details |

A stable-function node is allowed only when the function is explicitly called on the main path, has a stable semantic responsibility, and uses the source function name as its node name.

### A.2 Naming

1. Prefer the source attribute name from `self.xxx = SomeModule(...)`.
2. Use the source function name when subdividing a module without an attribute boundary.
3. Use a supplemental semantic name only when neither exists.
4. Ensure the name covers the node's actual semantic extent. When only a coarse boundary is stable, use a broader truthful name.
5. Legacy `layer_types` describes decoder-layer types only. Put non-decoder backbone work in `stages` and non-backbone runtime work in `runtime_auxiliary`.
6. Use the exact source decoder class name for a layer type. If structurally different variants share a class, append a short lowercase suffix. Do not abbreviate or omit the class name.

### A.3 Boundaries

#### A.3.1 Derive layer boundaries from decoder source

Read the decoder computation order first, identify its repeated pattern in the operator sequence, then separate structurally different decoder types. Parallel execution may reorder operators even for identical layers.

#### A.3.2 Subdivide only on stable module, function, or semantic boundaries

Subdivide a node when source contains a stable boundary that corresponds to a recognized model structure. Do not turn unstable runs of small implementation operators into nodes. Never promote an internal call to a peer of its owner; make it a child or merge it into the owner.

#### A.3.3 Fold repeated isomorphic stages

Keep one structure definition for repeated instances of the same source module/function and identify instances through index fields. This applies to stages, decoder types, and runtime auxiliary nodes.

For partially isomorphic repetitions where only the final tail differs, fold the first N-1 instances with `instance_indices=[0, ..., N-2]` and create a separately named final-tail entry. When operator count changes only because an accumulation operation such as `ConcatD` grows by one or two operators, treat the instances as isomorphic and fold all N instances.

#### A.3.4 Keep runtime work outside model modules

Token selection, speculative-token verification, input updates, and similar non-backbone logic belong in `runtime_auxiliary`, not lm_head, embedding, or another model module.

#### A.3.5 Understand the complete computation

For interleaved parallel modules, use `stream_id`, input shapes, and output shapes to support boundaries. Every ownership decision must be explainable from source and computation.

#### A.3.6 Model iterative wrappers such as MTP correctly

In legacy-v1 terminology, an internal real decoder class belongs in layer types and must not be inlined into stages. Put surrounding scaffold such as enorm, hnorm, projections, shared head norm, embedding, and lm_head in stages, folded by `stage_indices`. Put graph setup, token sampling, verification, and parameter updates in runtime auxiliary nodes folded by `instance_indices`.

For schema-v2 learned-layer and invocation semantics, E.2 is authoritative and supersedes any legacy `layer_indices` interpretation.

### A.4 Ambiguity resolution order

When ownership is unclear, use this fixed order:

1. Decide whether the operator is model backbone or runtime auxiliary work.
2. For backbone work, merge into the nearest source module.
3. If no suitable module exists, use a stable source function.
4. Preserve a truly independent communication stage.
5. Otherwise use an allowed supplemental semantic name.
6. If uncertainty remains, merge upward into the parent.
7. Put work known to be outside the backbone in `runtime_auxiliary`.

Never invent a node to absorb operators or reshape the tree around one capture's local kernel order.

## B. Kernel Nodes

### B.1 Implementation-detail operations

The following are normally implementation details and not standalone tree nodes:

`Cast`, `Concat`, `Transpose`, `Reshape`, `DynamicQuant`, `Dequant*`, `ScatterNdUpdate`, `Split`, `RotaryMul`, and an `AivKernel` without a clear source-module/function boundary.

Merge them into the nearest source module or function-semantic node.

### B.2 Communication operations

1. Merge communication implemented inside a module/function into that owner.
2. Keep communication as a node only when it is an independent data-movement stage between modules, such as an all-gather after embedding or before lm_head.
3. Decide from the source call location, not the kernel name.
4. Merge an accompanying `AivKernel` into the communication or owning module.

### B.3 Operator mapping

Exact mapping must not rely on vague guesses:

1. Understand each node's computation and start/end boundaries.
2. Align each source computation with concrete operators using source and B.4 evidence.
3. Check for both excess and missing operators. Reanalyze until no gap remains.

### B.4 Supporting evidence

Use `stream_id`, `input_shapes`, and `output_shapes` from `raw_ops.json` as supporting evidence.

- Streams reveal multi-stream parallelism and justify non-contiguous indices within one semantic stage.
- Shapes distinguish same-name operators in different semantic positions, attribute GEMM variants, and verify dimensional boundaries.

### B.5 Optional `shape_semantic`

`shape_semantic` is optional, does not enter formal gates, and does not affect score. It helps diagnose tensor-attribution mistakes but neither its absence nor presence proves correctness. Check it with `run_validation.py --with-shapes` or `validate_shapes.py` only when needed.

Prefer annotations for major GEMM/attention computation, layout-changing communication, and multi-output fused operations. They are unnecessary for pure Cast, Reshape, Transpose, quantization, and dequantization details. Do not define a universal kernel-name list; use family aliases only as hints from `adapters/<family>.py` `kernel_anchors`.

Use these symbols consistently: `B` batch, `T` time/sequence length, `H` heads, `D` head dimension, `hidden`, `ffn`, `E` experts, `topK`, `q_rank`, and `kv_rank`.

Examples:

- `[B*T, hidden] @ [hidden, q_rank]`
- `[B, H, T, D] x [B, H, D, T] -> [B, H, T, T]`
- `[B*T, hidden] -> [B*T, hidden]` for Norm
- `[B*T, H, kv_rank] -> AllGather -> [B*T, H, kv_rank*tp]`

When adding an annotation:

1. Use actual `input_shapes` and `output_shapes`; never infer from architecture intuition.
2. Put inputs left of `->` and every important output on the right.
3. Ensure each named dimension matches a real numeric dimension; give a value for a new non-config symbol.
4. Track every important fused output. Never label Q output as K.
5. Respect absorbed weights and low-rank output shapes in inference implementations.
6. Run `python scripts/validate_shapes.py -c outputs/analysis_config.json` as a diagnostic, not a formal gate.

## C. Output Format

### C.1 Legacy-v1 shape

Legacy v1 used top-level `model_name`, `representative_step`, `notes`, `stages`, `layer_types`, `layer_structure`, and `runtime_auxiliary`. Each layer type had one representative tree and repeated stages used `stage_indices` or `instance_indices`.

```json
{
  "model_name": "model-name",
  "representative_step": 1,
  "notes": "Architecture, layer count, parallelism, and special paths",
  "stages": {
    "preprocessing": {
      "name": "preprocessing",
      "children": [
        {"name": "embedding", "semantic": "Token embedding", "code_ref": "modeling.py:100", "op_indices": [0, 1]}
      ]
    }
  },
  "layer_types": {
    "DecoderLayer": {"layer_indices": [0, 1]}
  },
  "layer_structure": {
    "DecoderLayer": {
      "name": "DecoderLayer",
      "semantic": "Decoder layer",
      "code_ref": "modeling.py:200-350",
      "children": [
        {"name": "self_attn", "semantic": "Self attention", "code_ref": "modeling.py:240", "op_indices": [10, 11]},
        {"name": "mlp", "semantic": "Feed-forward network", "code_ref": "modeling.py:300", "op_indices": [12, 13]}
      ]
    }
  },
  "runtime_auxiliary": [
    {"name": "sampling", "instance_indices": [0, 1], "op_indices": [100, 101]}
  ]
}
```

Schema v2 is authoritative for new output; see E.

### C.2 Legacy top-level fields

| Field | Meaning |
|---|---|
| `model_name` | Model name |
| `representative_step` | Selected step id |
| `notes` | Architecture, layer count, parallelism, and special paths |
| `stages` | Backbone stages outside decoder layers; fold repetitions with `stage_indices` |
| `layer_types` | Decoder types and layer ranges only |
| `layer_structure` | One representative tree per decoder type |
| `runtime_auxiliary` | Observed non-backbone runtime logic; fold repetitions with `instance_indices` |

### C.3 Node fields

| Field | Required | Meaning |
|---|---|---|
| `name` | Yes | Name following A.2 |
| `semantic` | Yes except pure Cast/Reshape detail | Computation meaning, including residual Add, gating Mul, KV Concat, and norm stages |
| `code_ref` | Yes unless genuinely unresolved | `filename.py:line` or `filename.py:start-end` |
| `op_indices` | On leaves | Covered operator indices; may be non-contiguous |
| `children` | On internal nodes | Child array; an internal node may also own extra indices not in a child |
| `kernels` | Optional | Per-kernel `index`, `semantic`, optional `shape_semantic`, and `code_ref` |
| `stage_indices`, `instance_indices` | On repeated stages | Repeated instances represented by one structure |

### C.4 Tree rules

- Every node has `name`.
- Leaves have `op_indices`; internal nodes have `children` and may own additional indices.
- Meaningful nodes and kernels have `semantic` and `code_ref`.
- Keep one definition for repeated isomorphic stages and identify instances by index.
- Put runtime support in `runtime_auxiliary`; never force it into a module tree for coverage.
- Give every identified important backbone and runtime stage an explicit owner.
- `children` is containment only; see C.5 for non-chain connections.
- `shape_semantic` is optional.

### C.5 Explicit dataflow edges

Child order does not encode variable flow. For example:

```python
hidden, residual = self.input_layernorm(hidden, past_residual)
hidden = self.self_attn(hidden)
hidden, residual = self.post_attention_layernorm(hidden, residual)
```

Two residual merges exist without standalone Add kernels or any trace in child order. Therefore an edge omitted from `branches` does not exist downstream. Graph construction and rendering must not infer it.

| Branch field | Meaning |
|---|---|
| `name` | Edge identifier |
| `kind` | `residual` (default), `parallel`, `skip`, `gate`, or `cross_invocation` |
| `inputs` | One or more branch points, using sibling names or full node ids |
| `output` | Merge point |
| `semantic` | Source meaning |
| `source_ref`, `code_ref` | Source location |

Siblings between an input and output are bypassed. Avoid three common errors:

1. Do not reverse direction. Adjacent endpoints that bypass nothing cause D2.
2. Express a fused add-norm carry from the previous invocation in wraparound form, with the input after the output in child order. This represents a cross-invocation carry rather than an intra-layer loop.
3. Declare every multi-consumer fork, including a direct forward-input fork, as `kind: parallel`. Otherwise downstream output serializes it and D4 reports the mismatch.

Cross-check every `merges[]` and `forks[]` in `dataflow_source.json` against declarations. `check_dataflow.py` performs the same comparison.

## D. Workflow

Follow the steps in order because each consumes earlier output.

### D.1 Step 2: Break down structure

#### D.1.1 Select the representative step and layer instance

- Use the only step when only one exists.
- Group by kernel count and kernel-type distribution and choose the stable dominant group. Prefer the group containing the most decoder invocations when counts differ.
- Treat the earliest member as warmup only when its kernel sum is a clear outlier against the later median.
- Otherwise choose the earliest stable step; after skipping an outlier, choose the later step closest to the median.
- Record the step and reason in `notes`; use `-s` only for explicit reproduction.

Choose the first complete decoder instance by default. When layer 0 differs because its input norm is standalone while later layers fuse a previous residual, choose layer 1 as the representative so the template fits typical instances. Record the selected instance and first-layer difference. Keep every structurally different decoder type separate, including an MTP decoder; never merge it with the main decoder.

#### D.1.2 Read complete model source

Read from the outer `ForCausalLM` class through inner submodules. Inventory `self.xxx` registrations, actual forward calls and order, and stable non-module function boundaries. Build nodes only from A.1 sources.

#### D.1.3 Locate decoder boundaries

Use source-derived anchors in the selected operator list. Decoder types describe decoder work only; put other backbone work in stages and non-backbone work in runtime auxiliary. `op_segments.json` is only a candidate starting point.

#### D.1.4 Map operators by source call order

Prefer torch-module boundaries. Use stable semantic functions only when no module boundary exists. Assign each leaf its exact, possibly non-contiguous, `op_indices`.

#### D.1.5 Write `analysis_config.json`

Follow C and the schema-v2 definitions in E.

#### D.1.6 Enrich

```bash
python scripts/analyze_kernels.py --enrich \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json
```

Enrichment adds `op_data` to leaf indices, including index, original index, name, duration, stream, task type, shapes, and raw shape fields, and merges existing kernel semantics and references without changing original fields.

### D.2 Step 3: Review

Run deterministic checks first, then a complete source/trace semantic review. Issue repair may focus on affected nodes, but the nine required checks including Q/K/V, residuals, boundaries, final norm, tail, and runtime must never be skipped.

#### D.2.1 Deterministic checks

Use one unified JSON output:

```bash
python scripts/run_validation.py \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --model-source /path/to/model-source/modeling_<x>.py \
  --semantic-review outputs/semantic_review.json \
  -o outputs/validation_report.json
```

Run individual checks only for diagnosis; never append multiple JSON documents with `>>`:

```bash
python scripts/check_structure.py   -c outputs/analysis_config.json --json
python scripts/check_dataflow.py    -c outputs/analysis_config.json -s models/<x>/modeling_<x>.py --json
python scripts/check_op_coverage.py -c outputs/analysis_config.json -r outputs/raw_ops.json --json
```

| Script | Checks |
|---|---|
| `check_structure.py` | Schema/tree integrity, decoder-type match, required fields, duplicate lists, double ownership |
| `check_dataflow.py` | D1-D7 source/config consistency for residuals, direction, bypass, parallelism, and runtime branches |
| `check_sublayers.py` | Parent equals child union, no overlap, template subset of representative instance |
| `check_op_coverage.py` | Complete non-overlapping coverage and kernel registration |
| `validate_shapes.py` | Optional shape diagnostics, not a formal gate |

#### D.2.2 Semantic review remains mandatory

Exact coverage and set consistency prove ownership, not dataflow semantics. Generate and fill `semantic_review.json` according to `semantic_review_protocol_en.md` even when deterministic issues are empty.

#### D.2.3 Repair deterministic issues

Provide the issue list, only affected configuration nodes, sparse source slices at their `code_ref` locations, and matching raw-operator slices. Verify each ownership and field, edit only confirmed errors, and use shapes and streams as supporting evidence. Return corrected configuration plus review conclusions.

#### D.2.4 Re-enrich, rereview, validate, and score

After a correction, rerun enrichment, create a new hash-bound semantic review, then run unified validation and scoring. Continue from the historical best candidate until accepted or a configured stop condition. Never reuse a stale review.

### D.3 Downstream handoff

- After acceptance, compute metrics and pass `analysis_config.json` to `cann-perf-breakdown-to-ui-json`.
- Mode B emits `model_structure.json` with empty indices and optional branches; it does not enter metric/report stages.
- Mode C delegates to `cann-npu-perfanalysis` and does not run this workflow.

## E. Authoritative Schema-v2 Definitions

Schema v2 separates learned architecture from observed execution. New v2 configuration must not contain legacy `layer_types` or `layer_structure`.

### E.1 Terms

| Term | Definition | Schema field |
|---|---|---|
| Model layer | Decoder layer with independent learned parameters, determined by source construction | `architecture.layer_groups[].model_layer_indices` or `model_layer_range` |
| Prediction module | Independently learned MTP/speculative layer, counted by configuration | `architecture.prediction_modules[].learned_module_count` and appended `model_layer_indices` |
| Trace instance | One observed module invocation in the representative step | `trace_instances[]` |
| Invocation index | Runtime call number for one model layer | `trace_instances[].invocation_index` |
| Representative template | Structure tree used to compress report size, not a layer index | `structures[]` and `representative_instance_id` |
| Execution count | Runtime-call count derived from trace instances; never substitute learned layer count | Derived by scripts |

### E.2 MTP and speculative decoding

Repeated calls reuse one learned module unless source construction proves distinct parameter layers.

- An outer loop invoking one wrapper with an internal decoder N times means one learned prediction module plus N trace instances, all with the same model-layer index.
- Never represent N calls as N learned layers or synthesize indices from kernel order.
- Prediction indices must be at least `num_main_layers`, appended after main layers.
- DS3.2 reference: 61 main layers, Dense 0-2, MoE 3-60, one learned MTP layer at 61; `next_n=3` produces three invocations of layer 61.

### E.3 Capture scope and prohibition on extrapolation

`trace_scope` is optional and states what was captured, not what the model is. Source determines structure; capture scope determines which nodes have measurements.

- Never calculate or copy metrics for uncaptured layers, ranks, or stages. Report them as not captured.
- Declare `rank_local` or `pipeline_stage_local` only with evidence from runtime parallel configuration, launch parameters, rank metadata, and observed layers.
- Without proven PP and with partial observations, omit scope or use `kind=unknown`; never guess pipeline rank and render the full model.
- A missing PP key means `pp=unknown`, not `pp=1`.
- When present, `trace_scope` includes `confidence` and `evidence`.
- MT1 is `info` by default because one step/rank cannot refute source layer count. Use `--fail-on-trace-mismatch` only when blocking is explicitly required.

### E.4 Exact four-way coverage

Every representative-step operator must enter one of the first three classes:

| Class | Source | Meaning |
|---|---|---|
| `mapped_model_ops` | trace instances, stages, and structure leaves | Model computation |
| `mapped_runtime_ops` | `runtime_auxiliary` | Verification, sampling, initialization, and scaffolding |
| `excluded_profiler_ops` | `excluded_profiler_ops` | Profiler/bookkeeping only; `reason_code` must be one of `profiler_marker`, `stream_sync_placeholder`, `cross_step_bookkeeping`, `device_param_update`, or `empty_shape_noop`, with `evidence` |
| `unmapped_ops` | `unmapped_ops` | Unknown ownership; strict validation fails |

Coverage is the exact union of model, runtime, and excluded indices. Never extrapolate by representative-layer count. Missing and duplicate counts do not cancel. Main computation cannot be excluded. A large `unmapped_ops` node is not completion. Formal acceptance requires zero unmapped, duplicate, and out-of-range indices; `--allow-unmapped` is exploratory only. Follow `ai_mapping_protocol_en.md` for Step 6.

### E.5 Evidence and confidence

Architecture and parallelism claims require `architecture.source_of_truth`, layer-group `source_ref`, and, when scope is present, `trace_scope.evidence` and `confidence`. Use `"unknown"` for values that cannot be resolved statically; never fill them from model folklore. The manifest records `source_ref`, extraction `method`, and `confidence` for every fact.

### E.6 Legacy migration

`migrate_config.py` converts v1 to v2 and marks `migration.status = legacy_unverified`. Because v1 `layer_indices` mixed layer identity with invocation count, migrated `trace_instances[].model_layer_index` becomes `"unknown"`. Rerun manifest extraction and architecture validation before treating the result as trusted.
