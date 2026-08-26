# Skill 3 validation matrix

## Deterministic checks

| Area | Required evidence |
|---|---|
| Generation safety | `--check` byte-for-byte read-only; refresh preserves model paths; failure restores complete report/trace |
| Configuration | versioned handoff or existing valid legacy config; field-specific required-key errors; typed optional fallbacks |
| Template | reusable files hash-identical unless a reviewed override is declared |
| Backend identity | matching model/report IDs, node sets, owner IDs, counts and ordered event bounds |
| Architecture | valid schema/endpoints/types/tensors/provenance/ports, no illegal cycles or inferred edges |
| Binding | normalized events uniquely resolve to raw duration events and backend nodes |
| Layer | capability-gated membership, pager, scoped metrics, sibling projection, bridges and selection preservation |
| Branches | discovered fan-out/fan-in/layout semantics survive collapse; declared minimums are enforced |
| Optional data | HBM/findings/operator details/expert inventory either validate when present or degrade honestly when absent |
| Standalone | embedded JSON exactly mirrors all configured source data and has no network runtime dependency |

Avoid treating source-string presence as sufficient behavioral proof. Prefer pure adapter tests and DOM/browser integration. Retain string checks only for static forbidden patterns or wiring that cannot be exercised cheaply.

## Manual checks

Use a 1440 × 1000 browser viewport after deterministic success. Exercise at least one mapped node, source-only node, aggregate, runtime auxiliary node, three non-adjacent Layers, one branch/residual, one Sequence event, empty-canvas reset, Trace zoom/pan/focus, both languages and both themes. Verify console and resource loading.

For standalone delivery also open `report/index.html` via `file://`. Mark browser, file-protocol and visual checks individually in `model_skill_validation_manifest.v2`.

## Status semantics

- `deterministic_status: passed`: all applicable automated checks passed.
- Manual entries: `passed`, `failed`, or `not_run`.
- `overall_status: pending_manual_validation`: deterministic checks passed but one or more manual checks are not run.
- `overall_status: passed`: deterministic and all required manual checks passed.
- `not_applicable` is valid only for a capability explicitly absent; it is never a substitute for missing expected evidence.
