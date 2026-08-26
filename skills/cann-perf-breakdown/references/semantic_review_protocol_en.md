# Model Breakdown Semantic Review Protocol

Deterministic scripts can prove schema validity, kernel coverage, and set boundaries, but those sets alone cannot prove semantic correctness. Every formal breakdown must include `semantic_review.json`, completed by the AI executing the skill after reading model source, configuration, and the representative step. Scripts validate evidence, artifact versions, and internal consistency.

## Required Review Items

All nine items must appear separately. Do not merge or omit them.

| ID | Required conclusion |
|---|---|
| `source_model_identity` | The manifest, configuration, and reviewed source describe the same model and variant. |
| `module_inventory_complete` | Embedding, every decoder type, final norm, lm_head, prediction modules, and other required modules are complete. |
| `dataflow_edges_complete` | Computation order and input/output edges match `forward()`. |
| `branch_topology_correct` | Parallel branches such as Q/K/V remain independent and were not merged because kernels were adjacent or shared names. |
| `residual_paths_correct` | Attention and MLP residuals have the correct two inputs and merge locations. |
| `layer_boundaries_correct` | Norms, cross-layer fused operations, and every invocation belong to the correct layer without cross-layer capture. |
| `tail_stages_correct` | Final norm, lm_head, sampling, runtime, and other tail stages are classified correctly. |
| `runtime_nodes_observed` | Runtime nodes actually occur in this trace and were not invented from source alone. |
| `code_refs_resolve` | Source references supporting key conclusions exist and their line numbers resolve. |

## Evidence Rules

- Every `passed` item must contain at least one `evidence` entry.
- Every evidence entry must include an `explanation` and at least one of `source_ref`, `config_path`, or `op_indices`.
- Branch, residual, and layer-boundary conclusions should cite both source and a configuration path or operator indices. Free-form prose alone is insufficient.
- `source_evidence` must list at least one forward/config source fragment that was actually read.
- Use `unknown` when a conclusion cannot be established. Use `failed` and add a finding when an error is found. Never use `passed` without sufficient evidence.
- Any `failed` or `unknown` check, and any `error` finding, blocks formal scoring. A `warning` finding also blocks, with the sole exception below.

### Sole Exception: Evidence-Gap Findings

A `warning` finding on `source_model_identity` can report that the inputs do not contain evidence for a scalar, rather than that any semantic conclusion is wrong. A typical case is a capture without checkpoint `config.json`, where layer count can only come from a Python default. Under the code-first rule, source is the architecture truth and the trace does not adjudicate scalars. Record this as an evidence gap: the validator emits `SR_EVIDENCE_GAP_FINDING` with `severity: info`, groups it with `A1`/`MT1`/`MA1`, does not block, and lists its id in `detail.evidence_gap_findings`.

This does **not** lower the gate. The capture-tier mechanism in `score_breakdown.py` enforces the ceiling for an unbound checkpoint. Tier A removes the eight `source_model_identity` points from the denominator (`runnable_max` is 92, below `MIN_TOTAL_SCORE` 95), so the conclusion is capped at `verified_unbound_scalars` and cannot become `verified`. Emitting a normal warning would instead make the top-level status `passed_with_warnings`, causing `GATE_VALIDATION` to classify the candidate as `needs_iteration`, incorrectly turning missing input evidence into a breakdown defect.

The exception covers only a `warning` on this one check. A warning on any other check, or an `error` on this check, still blocks.

## Artifact Binding and Iteration

`semantic_review.json.artifacts` stores SHA256 values for `analysis_config.json`, `raw_ops.json`, and `model_manifest.json`. A change to any file invalidates the previous review immediately. After changing the breakdown configuration, regenerate the request, reread the affected source and trace, and create a new review.

Generate the request first:

```bash
python scripts/prepare_semantic_review.py \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --source-dir models/<model> \
  -o outputs/semantic_review_request.json
```

Fill the request's `review_template`, save it as `semantic_review.json`, and validate it:

```bash
python scripts/validate_semantic_review.py \
  -s outputs/semantic_review.json \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --source-dir models/<model>
```

One hundred percent kernel coverage proves only that each kernel has an owner. It does not prove Q/K/V topology, residual paths, or layer boundaries. Formal scoring and report generation are allowed only after semantic review passes.
