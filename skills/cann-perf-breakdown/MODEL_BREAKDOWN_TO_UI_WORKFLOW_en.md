# Model Breakdown to UI Report: Workflow Guide

This guide routes an NPU profiling capture through the three performance skills. It only answers which skill to use next; detailed rules, fields, parameters, and validations remain in each skill's `SKILL.md` and `references/`.

## One-line invocation

```text
Use the three-stage skills/cann-perf-breakdown workflow to break down <capture-dir> for <model-id> and generate two HTML reports.
```

The deterministic pipeline entry point is:

```bash
python3 <skills>/2-adapt-breakdown-to-ui-json/scripts/run_pipeline.py \
  --capture-dir <capture-dir> --model-id <model-id> --out <output-dir>
```

It discovers `kernel_details.csv`, `trace_view.json`, and model source files, then writes the breakdown report and UI report under the output directory.

## Three stages

| Stage | Directory | Input | Output |
|---|---|---|---|
| 1 | `1-perf-breakdown/` (`perf-breakdown-skill`) | profiling data, model source, runtime YAML | schema-v2 breakdown, mapping, validation, critique, and score |
| 2 | `2-adapt-breakdown-to-ui-json/` (`adapt-breakdown-to-ui-json`) | an approved Stage 1 bundle | UI facts, architecture graph, overlay, trace bindings, and handoff |
| 3 | `3-generate-ui-json-report/` (`generate-ui-json-report`) | Stage 2 handoff and trace data | validated interactive report runtime |

The numeric directory names describe execution order. Runtime lookup must use the unique `name` in each skill's frontmatter.

## Choose a starting stage

| Available input | Start at |
|---|---|
| profiling capture and model source | Stage 1 |
| approved `analysis_config_v2.json` and score | Stage 2 |
| analysis, performance, and timeline JSON files | Stage 3 |
| an existing report that needs trace refresh or UI changes | Stage 3 (local refresh) |

## Stage gates

Stage 1 must provide a passed validation report, a convertible score, and an empty `unmapped_ops` list before Stage 2 can start. Stage 2 must pass conversion validation and keep `model_id`, `report_id`, and `representative_step` consistent before Stage 3 can start.

Two statuses intentionally require AI work and are not script failures:

| Status | Meaning | Continue with |
|---|---|---|
| `awaiting_ai_mapping` | operators need semantic mapping | `--breakdown-config <file>` |
| `awaiting_semantic_review` | source semantics need review | `--semantic-review <file>` |

Other statuses include `needs_iteration` with required actions and `failed` with a concrete stage and reason. Do not infer completion from an exit code alone.

## Data rules

Keep `trace_view.json` with the profiling CSV from collection time because Stage 3 requires it. `perf_data.json` and `timeline.json` are Stage 2 inputs to Stage 3, not Stage 3 outputs. Source code is the architecture authority; trace data can only provide runtime evidence and must not invent missing layers or pipeline ranks.
