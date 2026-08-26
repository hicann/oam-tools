# UI report data contract

## Contents

- Input ownership
- Skill 2 handoff
- Runtime configuration
- Cross-file invariants
- Optional capabilities
- Output ownership

## Input ownership

| Input | Authoritative for | Not authoritative for |
|---|---|---|
| analysis JSON | Stable backend `node_id`, hierarchy, semantic path, code reference, observed instances | Full source topology or tensor edges |
| performance JSON | Captured metrics, scope, operator count and ratios | Architecture identity beyond `node_id` or diagnosis |
| normalized Timeline JSON | Event bounds, lanes, optional owner and layer instance | Architecture/dataflow edges or fabricated owners |
| raw Chrome Trace JSON | Metadata, duration/counter/flow events and physical lanes | Architecture semantics |
| model architecture graph | Source hierarchy, repeated layers, roles, semantic edges, provenance | Captured timing |
| overlay/bindings | Reviewed backend-to-architecture and normalized-to-raw identity | New architecture facts |
| optional HBM/frequency/findings/expert inventory | Only the fields explicitly contained in each artifact | Missing measurements or inferred advice |

Skill 3 owns presentation, interaction, layout, language/theme behavior, selection synchronization, local transport, and validation. It must not repair backend facts.

## Skill 2 handoff

Prefer `<repo>/ui-report-handoff.json` or `<repo>/ui_facts/ui-report-handoff.json`:

```json
{
  "schema_version": "ui_report_handoff.v1",
  "model_family": "deepseek_v3_2",
  "skill3_adapter": "generic",
  "inputs": {
    "analysis": "../model_analysis_config.json",
    "performance": "../model_perf_data.json",
    "timeline": "../model_timeline.json",
    "trace": "../trace_view.json",
    "bindings": "./outputs/trace_bindings.json",
    "architecture": "./outputs/model_architecture_graph.json",
    "overlay": "./outputs/architecture_overlay_map.json"
  },
  "optional_inputs": {
    "operator_details": "./outputs/operator_details.json",
    "hbm": "./outputs/hbm_series.json",
    "findings": "./outputs/metrics_findings.json",
    "expert_inventory": "./outputs/expert_inventory.json"
  },
  "capabilities": {
    "repeatedLayers": true,
    "expertInventory": true,
    "expectedGraphFeatures": {
      "fanOutMin": 2,
      "fanInMin": 2,
      "residualEdgesMin": 2,
      "parallelRowsMin": 1
    }
  },
  "provenance": {
    "skills": ["cann-perf-breakdown", "cann-perf-breakdown-to-ui-json"],
    "modelSource": "models/modeling_example.py",
    "extractorModel": "model-name"
  }
}
```

Use `skill3_adapter: "generic"` for every Skill 2 output. Skill 3 rejects model-specific adapters; model family alone never authorizes a separate builder.

Legacy `report-config.js` remains readable, but new reports require a handoff. Missing optional artifacts degrade to empty in-memory values; missing required inputs are errors.

## Runtime configuration

`report-config.js` is generated transport configuration, not a model template. Required keys are analysis, performance, timeline, trace, bindings, architecture, and overlay. Optional defaults are operator details, HBM, findings, and expert inventory under `report/outputs/`.

`templateOverrides` may list reviewed runtime files intentionally different from the Skill template. Undeclared template drift is a validation failure.

## Cross-file invariants

Require:

- identical model/report identity across analysis, performance and Timeline;
- unique backend node definitions and performance records;
- exact analysis/performance node coverage unless the schema explicitly declares otherwise;
- every nonempty Timeline owner to resolve to analysis;
- event counts and mapped/unmapped summaries to match events;
- ordered finite event bounds;
- every normalized event to bind to one distinct raw duration event when raw binding is required;
- every architecture edge endpoint to resolve and preserve its semantic/tensor/provenance fields;
- every backend node to have exactly one reviewed mapping classification.

Timeline owner percentage is event-mapping coverage, not architecture coverage.

## Optional capabilities

- `repeatedLayers`: run Layer membership, pager, scoped-metric and selection-preservation tests.
- `expertInventory`: apply MoE presentation only to items with explicit architecture roles or recognized legacy aliases.
- `expectedGraphFeatures`: enforce model-specific minimum graph evidence; do not let an empty fan-out/residual test pass when upstream declared those features.
- HBM: keep its section title visible; collapse missing data and show a localized missing-capture explanation on expansion.

## Output ownership

Treat `report/` as a generated runtime. Build it transactionally and keep the previous complete report on failure. `--check` is strictly read-only. `report-embedded-data.js` mirrors canonical JSON for `file://`; it is never an editable fact source.

The validation manifest distinguishes deterministic checks from browser/visual checks. Deterministic success alone leaves overall status pending until the final smoke test is recorded.
