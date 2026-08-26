# Profiling report UI contract

## Contents

- Architecture graph
- Repeated layers
- Inspector and Operator List
- TraceView
- HBM and optional evidence
- Layout, language and styling

## Architecture graph

- Render top-to-bottom semantic dataflow with bottom-to-top ports. Parallel siblings require declared independent branches or same-row layout; serial descendants must occupy successive rows.
- Preserve every projected edge identity when collapse maps multiple edges to the same endpoints. Keep declared fan-out/fan-in branches distinct.
- Route residual edges through a stable dashed outer-left orthogonal lane with rounded corners. Route long parameter/state inputs outside unrelated nodes and pagers. Never synthesize missing edges.
- Use neutral gray readable edges and inherited fixed-size arrowheads. Keep endpoints clear of node borders.
- Expand frames to contain measured long titles and fold controls. Hide cosmetic single-root structural shells without deleting metadata.
- Source-only and active-Layer no-performance nodes use neutral treatment, no metric badge, and no performance heat.
- Enable time-share heat by default using one logarithmic Turbo domain. Use the same domain for node badges, Operator List badges, legend and Layer dots. Missing values remain gray.
- Render leaf Ops with one centered name; keep generic type details in Inspector. Use consistent expand/fold controls.
- Apply Expert Inventory only to explicitly role-tagged MoE structures (legacy role aliases are accepted). Show Router, representative routed experts, external Shared Expert and Combine. Do not fabricate per-expert timing when execution is fused.

## Repeated layers

- Treat template `node_id` and concrete `layer_index`/`structure_instance_node_id` as different identities.
- Maintain one active Layer context across architecture, Inspector, Operator List, Sequence, Trace and Flow in one render transaction.
- Render one pager for a model-layer hierarchy. Runtime/MTP iteration indices never enter the decoder Layer pager.
- Use each template's declared `instanceIndices`; overlapping membership, unclaimed declared layers, or disagreement across graph/analysis/performance is an error.
- Keep title and pager on separate rows. Dots have at least 24 px targets, timing tooltips and current-layer heat. Pager actions preserve graph transform.
- Layer selection renders only the owning sibling template. Preserve ordinary submodules inside it and bridge only declared top-level paths hidden by presentation filtering.
- Keep the selected operator by exact relative path across isomorphic sibling templates. If no exact counterpart exists, retain semantic selection and show unavailable metrics rather than jumping or clearing.
- Recompute wall, busy union, kernel sum, total cost, operator count, time share, badges and heat from current-layer events. Never copy aggregate metrics into every layer.

## Inspector and Operator List

- Do not render an Evidence section or duplicate mapped-summary chips.
- Show four core metrics first: `wall_ms`, `busy_union_ms`, `kernel_sum_ms`, `total_cost_ms`. Show current operands/formulas; mark wall time with a neutral Primary Metric label, not selection-colored styling.
- Then show time share as one inline full-width card and Operators/HBM estimate/MFU INT8/MFU BF16 as four equal cards. Use `–` for unavailable facts.
- Metric tooltips explain exact definitions and evidence limits; no native `title` attributes.
- Operator List starts with localized All Layers and supports aggregate or concrete Layer scope.
- Use compact centered `Operator Summary` and `Operator Sequence` tabs. Sequence rows remain one line, use TraceView's per-lane `#N`, stable raw source identity, Stream/Layer tags, exact duration, hover and selected state.
- Row or Trace click selects the same concrete event without narrowing the list. Re-click/blank list space clears only event selection.
- Architecture and sequence tooltips use consistent `field: value` rows: ID/sequence, name, Stream, duration/share, type, Shape, Dtype and semantic/source fields. Missing upstream values display `–`.
- Show node-scoped diagnostic findings only when backend data contains them; never invent recommendations or empty placeholder advice.

## TraceView

- Preserve all valid raw metadata, duration, counter and flow events and all physical lanes.
- Render task bars through shared PTO patterns. Keep lanes 22 px and bars 18 px; suppress only truly overlapping inline labels, never bars/tooltips.
- Assign stable one-based sequence within the complete PID/TID lane. Do not use global `op_index` as the visible ordinal.
- Render Flow only for the selected mapped backend node's strict upstream/downstream endpoints. Clearing/source-only selection hides Flow.
- Support cross-lane time selection, exact event selection, Ctrl/Command wheel zoom, keyboard pan, fit, focus and selection reset through shared patterns.
- Node focus targets about half the lane viewport and retains horizontal/vertical scrolling. Keep all lanes visible and dim unrelated events.

## HBM and optional evidence

- Keep the localized HBM section title visible. If valid bandwidth or occupancy is missing, default collapsed and show a localized not-collected message only when expanded.
- With data, render independent continuous Read, Write and occupancy lines from complete source arrays. Keep five sample intervals around narrow linked ranges and interpolate only visible boundaries.
- Do not claim address heatmaps or exact per-operator bandwidth ownership from coarse samples.
- Render AICore frequency as a separate collapsible section only when supplied. Show declared/derived value agreement and throttling status in the chart tooltip; do not invent a time-series from a constant value.
- Report provenance Info uses backend/handoff skills, model source and extractor model. Never ship mock identity as production fact.

## Layout, language and styling

- Default Chinese; preserve a saved language. Localize report title and browser title without changing source-authored architecture labels.
- Use shared PTO tokens, workbench, IDE frame, tab, graph, tooltip, swimlane and selection patterns. Add reusable visual changes to the shared template/pattern first.
- Keep pane headers consistent, controls centered and intrinsic-width, workbench outer spacing visible, and Inspector sections compact without divider lines.
- Keep visible text at least 12 px except 10 px Trace labels and the subordinate 11 px metric formula.
- Support light/dark themes with readable edge, badge, heatmap and tooltip contrast.
