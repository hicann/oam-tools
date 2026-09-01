# Skill 3 input files

This reference lists the files read by the generic report-generation path and separates them from optional enrichments, locked adapters, demonstrations, generated runtime files, and Markdown instructions.

## Generic required inputs

New reports require a Skill 2 `ui_report_handoff.v1` manifest at `<repo>/ui-report-handoff.json`, `<repo>/ui_facts/ui-report-handoff.json`, or an explicit `--handoff <path>`. The manifest is configuration and provenance, and declares the actual model-specific filenames.

| Handoff key | Typical artifact | Authoritative content |
|---|---|---|
| `inputs.analysis` | `*_analysis_config.json` | Backend `node_id`, hierarchy, semantic path, code reference and observed Layer instances |
| `inputs.performance` | `*_perf_data.json` | Captured node metrics, timing scope, operator counts and ratios |
| `inputs.timeline` | `*_timeline.json` | Normalized event bounds, lanes and optional node/Layer ownership |
| `inputs.trace` | `trace_view.json` | Raw Chrome Trace metadata, duration/counter/flow events and physical lanes |
| `inputs.bindings` | `report/outputs/trace_bindings.json` | Reviewed normalized-event to raw-Trace identity |
| `inputs.architecture` | `report/outputs/model_architecture_graph.json` | Source hierarchy, repeated Layer templates, semantic edges, tensor metadata and provenance |
| `inputs.overlay` | `report/outputs/architecture_overlay_map.json` | Reviewed backend-node to architecture-item classification |

All seven paths are required. Missing required inputs fail generation. Existing legacy reports may retain `report/report-config.js`, but new reports require the handoff.

## Optional inputs

The handoff may declare these under `optional_inputs`. Missing optional artifacts degrade to typed empty data and must not cause Skill 3 to invent measurements, mappings or advice.

| Handoff key | Default artifact | Use |
|---|---|---|
| `operator_details` | `report/outputs/operator_details.json` | Operator index, name, type, Stream, input/output shapes and dtypes |
| `hbm` | `report/outputs/hbm_series.json` | HBM bandwidth, occupancy and supplied device/frequency facts |
| `findings` | `report/outputs/metrics_findings.json` | Backend-authored node-scoped diagnostic findings |
| `expert_inventory` | `report/outputs/expert_inventory.json` | Declared MoE routed/shared-expert inventory |

Skill 3 also discovers the following upstream forms during normal generation:

- Operator details: `<repo>/work/raw_ops_details.json`, then `<repo>/../work/raw_ops_details.json`.
- Findings: `<repo>/metrics_findings.json`, then `<repo>/../metrics_findings.json`.
- Expert inventory: the first `<repo>/ui_facts/*_expert_inventory.json` or `<repo>/../ui_facts/*_expert_inventory.json`.

## HBM input directory

When generation receives `--hbm-dir <aligned-hbm-dir>`, Skill 3 reads exactly:

- `hbm_bandwidth_timeline.csv`
- `hbm_occupancy_timeline.csv`
- `sample_op_mix.csv`
- `hbm_summary.json`

It normalizes them into `report/outputs/hbm_series.json`. AICore frequency currently has no independent generic input file; it must be supplied in the configured HBM/device-profile artifact. Coarse HBM samples do not establish per-operator bandwidth ownership.

## Command-line supplemental inputs

- `--trace <trace_view.json>` replaces or creates the repository's raw Trace transactionally.
- `--handoff <ui-report-handoff.json>` selects an explicit handoff instead of discovery.

## Markdown and model source files

The generic report runtime does not read model-side Markdown as report data. In particular, `issue.md`, design notes and analysis drafts are not injected into the report. Diagnostic advice comes from `metrics_findings.json`, not Markdown.

Agents read the following Skill-owned Markdown only as operating contracts:

- `SKILL.md`
- `references/data-contract.md`
- `references/input-files.md`
- `references/ui-contract.md`
- `references/validation-matrix.md`

Model source paths and extractor identity arrive through handoff `provenance`. Skill 3 does not read or vendor model Python/config files.

## Generated and validation files

The following are generated runtime or validation artifacts rather than upstream fact inputs:

- `report/report-config.js`: generated transport configuration, or a legacy configuration source.
- `report/report-embedded-data.js`: standalone `file://` bundle mirroring configured JSON.
- `report/outputs/operator_details.json`: normalized operator-detail output.
- `report/outputs/hbm_series.json`: normalized HBM output when `--hbm-dir` is used.
- `report/outputs/metrics_findings.json`: copied optional findings or a typed empty placeholder.
- `report/outputs/expert_inventory.json`: copied optional inventory or a typed empty placeholder.
- `report/outputs/validation_manifest.json`: deterministic/manual validation state.

Validators also read report HTML, JavaScript, CSS and design-system assets to check syntax, template hashes, interaction contracts and standalone completeness. These UI assets are not model facts.
