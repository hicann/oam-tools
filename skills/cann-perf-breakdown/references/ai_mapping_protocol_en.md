# Step 6: Executable AI Operator-Mapping Protocol

This document defines how AI maps **every** operator in one representative profiling step to model structure in Mode A Step 6 and produces schema-v2 `analysis_config.json`. Scripts validate the result, but AI performs semantic attribution. This protocol is mandatory.

> Hard rule: **Every operator in the representative step must have an explicit owner**: model, runtime auxiliary, or a strictly allowed exclusion. Never hide hundreds of indices in one `unmapped_ops` node. Non-empty `unmapped_ops` always fails strict validation.

---

## 1. Required Inputs

Obtain and read every input before mapping:

| Input | Source | Purpose |
|---|---|---|
| `model_manifest.json` | Step 2 `extract_model_manifest.py` | Architecture truth: main-layer count, Dense/MoE indices, learned MTP indices, and `source_ref` |
| `dataflow_source.json` | Step 5 `extract_dataflow.py` | **Dataflow truth** from `forward()`: call order, residual `merges`, parallel `forks`, config-gated `variants`, and statically undecidable `unsupported` branches. Cite it for every branch declaration. |
| `raw_ops.compact.json` | Step 4 | Folded operator sequence for locating coarse stage boundaries |
| `raw_ops.json` | Step 4 | Authoritative complete operator sequence with index, name, stream, and shape |
| `op_segments.json` (optional) | `segment_layers.py` | Candidate layer boundaries only; source semantics remain authoritative |
| Model source | `models/<model>/` | Forward semantics for decoder layers, MTP wrappers, lm_head, and embedding |

---

## 2. Mapping Procedure

Follow this order exactly.

### 2.1 Identify complete execution stages first

Use stable anchors to split the full operator sequence into coarse stages before refining it.

**Anchors must come from this model's source and manifest. Never apply a fixed kernel-name list.** Kernel names for the same semantics vary by model family, fusion, quantization, backend version, and operator library. First read the module call order from `dataflow_source.json`, then find its stable repeated patterns in the trace. Family-specific `adapters/<family>.py` `kernel_anchors` are candidate hints only.

Find semantic boundaries rather than literal names:

- **Attention start:** first main attention kernel in each decoder invocation.
- **Layer tail:** residual normalization, possibly fused with the next layer's input norm; see 2.5.1.
- **MoE markers:** gating, routing, grouped GEMM, and dispatch/combine communication.
- **lm_head/logits:** terminal projection plus vocabulary-dimension communication or cast.
- **Sampling/verification:** argmax and speculative-token assembly.
- **Runtime bookkeeping:** parameter updates and warmup collectives.

Use `stream_id` to distinguish parallel stages; see `structure_analysis_guide_en.md` B.4.

### 2.2 Identify each decoder and MTP invocation

Create one `trace_instances[]` record for every observed invocation:

- Store the real continuous `op_range` or non-contiguous `op_indices`, covering every operator in that invocation.
- Set `model_layer_index` to the real index only when source or manifest proves it. Otherwise use `"unknown"`, while still completing `layer_group_type` and operator ownership.
- Set `invocation_index` to the invocation number for that model layer, such as MTP iteration 0, 1, or 2.
- For MTP/speculative decoding, one learned layer invoked N times means N instances with the **same** `model_layer_index`; point them to the template with `representative_instance_id`. Never invent N model layers or synthetic layer indices.

### 2.3 Reuse representative structure definitions without replacing instance mapping

`structures[<layer_group_type>]` stores one representative subtree to reduce report size. It does not provide coverage. Real ownership comes from each `trace_instances` `op_range` or `op_indices`. Representative-tree leaves may omit indices; reporting uses the representative instance for timing.

### 2.4 Assign stages and runtime operators

- Model-backbone stages outside decoder layers, including embedding, final norm, lm_head, and MTP scaffold/output, belong in `stages`; fold repetitions with `stage_indices`.
- Non-backbone runtime logic, including token verification, sampling, input updates, graph/step initialization, and per-MTP-iteration gather/all-gather scaffolding, belongs in `runtime_auxiliary`; fold repetitions with `instance_indices`.
- Merge implementation operators such as Cast, Reshape, Transpose, dynamic quantization, and dequantization into the nearest real module. Do not create standalone structural nodes for them.

### 2.5 Restrict exclusions to profiler and bookkeeping operations

Only operations with no model mathematics and used solely for profiling or device bookkeeping may enter `excluded_profiler_ops`. Each must use an allowed `reason_code` and `evidence`:

`profiler_marker`, `stream_sync_placeholder`, `cross_step_bookkeeping`, `device_param_update`, or `empty_shape_noop`.

Never exclude main computation such as MatMul, Attention, Norm, MoE, communication, Gather, KV cache, or sampling. C6 blocks these exclusions.

### 2.5.1 Three-part ownership for fused add-norm chains

In many implementations, the add-norm kernel at the end of one decoder layer is physically the **next layer's input_layernorm**, fused across layers. Determine this from `dataflow_source.json` `merges[].kind == "fused_in_call"`, not from kernel names.

Fusion links the backbone into a norm chain in which each norm adds the residual left by the previous invocation. Treat its endpoints differently from its interior:

1. **Chain head:** The first layer has no previous invocation and `past_residual is None`, so fusion degenerates to an independent norm. It belongs to the first layer, not a previous layer tail. The first layer therefore has one extra operator; choose a typical later layer as the representative and record the first-layer difference in `instance.note`.
2. **Chain interior:** By convention, assign the fused norm to the current layer tail, with a name such as `input_layernorm_next`. This keeps each invocation's operators contiguous and avoids double-counting the next attention start. One attention-residual endpoint then lies in the previous invocation; declare its `branches[]` edge in wraparound form as described in 2.5.2 so downstream consumers recognize a cross-invocation carry.
3. **Chain tail:** After the last observed layer, no next layer exists. An outer-module final norm or `shared_head_norm` consumes the residual. Register it as a separate `stages` entry. Never attach it to the last layer as a nonexistent next input norm. The last layer cannot reuse an interior template containing `input_layernorm_next`; create a separate structure such as `<Layer>_final` if instance-level override is unavailable. Put the cross-structure residual edge in top-level `dataflow.edges`.

Use source call sites and successor topology, not kernel name, shape, or stream. Tail and interior norms often look identical in the trace, and the invocation operator count can remain unchanged because an outer norm replaces the interior tail norm. Deterministic checks such as SL6 cannot detect this tail error. The distinguishing successor is another attention start for an interior norm and lm_head for the tail norm. `tail_stages_correct` semantic review must enforce it.

### 2.5.2 Declare dataflow edges explicitly

`children` expresses containment only. Adjacent children do not imply an edge, and downstream graph construction and rendering must not infer one from order. Residuals, parallel branches, and skips exist in variable flow and are absent unless declared in `branches`.

For every structure, compare against the module's `merges` and `forks` in `dataflow_source.json`:

- Every `merges[]`, including `fused_in_call` add-norm and `in_place_add` `+=`, requires a matching `branches[]`. A fused form has no standalone Add kernel, so operator order alone cannot reveal it.
- Every `forks[]`, including multiple consumers of a direct `forward()` input, requires a `kind: parallel` declaration. Adjacent children without a branch render incorrectly as a chain.
- `inputs` are branch points and `output` is the merge. Siblings between them are bypassed. Do not reverse direction: a start on the main path with adjacent endpoints and no bypass is a D2 error.
- For a residual endpoint in the previous invocation, use wraparound form with the input positioned after the output in child order. Downstream consumers then recognize a cross-invocation carry rather than an intra-layer cycle.
- Select config-gated `variants`, such as quantization or TP scale, through `execution_profiles` for this capture.
- Runtime-data-dependent `unsupported` branches are statically undecidable. Declare the selected path and reason in `deviations[]`; otherwise D5 blocks.

Every `branches[]` item must contain `source_ref` or `code_ref`. `check_dataflow.py` re-derives the AST graph and compares every declaration; any D1-D7 error blocks formal completion.

### 2.6 Convergence

Require `model_mapped + runtime_mapped + excluded == total_ops`, with `unmapped == 0`, `duplicate == 0`, and `out_of_range == 0`. Continue mapping until all hold.

---

## 3. Step 6 Prompt Template

```text
You are an expert in mapping NPU performance operators to model structure. Map all <TOTAL> operators in the representative step precisely and produce schema-v2 analysis_config.json.

Required inputs:
- model_manifest.json: <content or path>  # architecture truth, layer groups, learned prediction indices, source references, capabilities
- dataflow_source.json: <path>            # forward calls, merges, forks, variants, unsupported branches
- raw_ops.json: <path>                    # complete indexed operator sequence with names, streams, and shapes
- raw_ops.compact.json: <path>            # folded overview
- op_segments.json: <optional path>       # candidate boundaries only
- model source slices: <decoder/prediction/lm_head/embedding forward slices selected by code_ref>

Hard requirements:
1. Derive anchors only from this model's source and manifest. Read forward call order first; never import a fixed kernel-name list from another family.
2. Create one trace_instances[] item per decoder/prediction invocation with its real op_range/op_indices and complete coverage.
3. N calls to one learned MTP/speculative layer mean one learned layer and N invocations with the same model_layer_index and increasing invocation_index. Never create synthetic layers.
4. Use "unknown" when model_layer_index cannot be proved, but still complete layer_group_type and ownership.
5. Put embedding, final norm, lm_head, and prediction scaffold/output in stages, folding repetitions with stage_indices.
6. Put token verification, sampling, input updates, step initialization, and per-iteration scaffolding in runtime_auxiliary, folding repetitions with instance_indices.
7. Only pure profiler/bookkeeping operations may be excluded, and each requires an allowed reason_code plus evidence. Never exclude main computation.
8. Every operator must belong to model, runtime, or excluded. unmapped_ops must be empty.
9. Declare all dataflow edges explicitly. Match every dataflow_source merge, including fused_in_call and in_place_add, with branches[] and every fork with kind: parallel. children is containment only. Include source_ref on every branch.
10. Declare runtime-dependent unsupported paths in deviations and config-gated variants in execution_profiles.
11. Verify sum(model,runtime,excluded)==<TOTAL>, unmapped==0, no duplicates or out-of-range indices, and every merge/fork has a declaration.

Output complete schema-v2 analysis_config.json. Then follow references/semantic_review_protocol_en.md to produce semantic_review.json and pass it to run_validation.py and score_breakdown.py. Completion requires convertible score plus passed semantic review and validation. Continue mapping on any coverage, duplicate, semantic, total-score, or core-dimension failure.
```

---

## 4. Validation Loop

After mapping, complete `semantic_review.json` in Step 8, then run `run_validation.py` in Step 9 and `score_breakdown.py` in Step 10. If any status is not accepted:

- `coverage.unmapped > 0`: return to 2.2/2.4 and assign every index to a real module or runtime node.
- `coverage.duplicate > 0`: two owners overlap; tighten boundaries.
- C6: a main-compute operator was excluded; restore it to a model node.
- Architecture A1-A9: reconcile architecture with manifest and return to Steps 2/3.
- Dataflow D1-D7: compare declarations against `dataflow_source.json`; D1 is a missing residual, D2 reversed direction, D3 bypassing a source-unrelated node, D4 parallel serialized as a chain, D5 an undeclared runtime branch, D6 a called source submodule absent from structure, and D7 a manifest capability without its fork/join.
- Semantic review: correct Q/K/V topology, residuals, layer boundaries, final norm, tail, and runtime against source. Do not substitute 100% kernel coverage for semantic evidence.
- Read `iteration_request.json`, start from `base_config_for_revision`, and fix only failed dimensions and hard gates before re-enrichment, validation, and scoring.
- Regenerate the semantic review after every configuration change. Never reuse stale SHA256 bindings.
- Never lower the 95-point total or dimension thresholds, hide main kernels in exclusions, or delete required branches merely to silence D2/D3.

During exploration, `--allow-unmapped` may show distributions, but its status is `exploratory`, not `passed`, and its report is visibly unverified. It is not a formal result.
