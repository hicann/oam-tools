//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
import { access, readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import { exists, readRuntimeConfig } from "./report-runtime-config.mjs";

const skillRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoFlagIndex = process.argv.indexOf("--repo");
const repoArgument = repoFlagIndex >= 0 ? process.argv[repoFlagIndex + 1] : null;
if (!repoArgument) throw new Error("Pass --repo <report-repo>");
const repoRoot = resolve(repoArgument);
const reportRoot = resolve(repoRoot, "report");
const templateRoot = resolve(skillRoot, "assets/report-template");

// Files that must be bit-identical copies of the template.
// Data-generated files (report-config.js, report-embedded-data.js, outputs/) are NOT in this list.
const TEMPLATE_VERIFIED_FILES = [
  "index.html",
  "app.css",
  "app.js",
  "report-data.js",
  "architecture-data.js",
  "trace-view.js",
  "hbm-view.js",
  "design-system/tokens/foundation.css",
  "design-system/tokens/semantic.css",
  "design-system/tokens/components.css",
  "design-system/css/style.css",
  "design-system/patterns/workbench-shell/pattern.css",
  "design-system/patterns/workbench-shell/pattern.js",
  "design-system/patterns/ide-frame/pattern.css",
  "design-system/patterns/ide-frame/pattern.js",
  "design-system/patterns/model-graphviz/pattern.css",
  "design-system/patterns/model-graphviz/pattern.js",
  "design-system/patterns/swimlane-task/pattern.css",
  "design-system/patterns/swimlane-task/pattern.js",
  "design-system/patterns/timeline-time-selection/pattern.css",
  "design-system/patterns/timeline-time-selection/pattern.js",
];

async function sha256(filePath) {
  try {
    const content = await readFile(filePath);
    return createHash("sha256").update(content).digest("hex");
  } catch {
    return null;
  }
}

async function checkTemplateHashes(allowedOverrides = []) {
  const mismatches = [];
  const allowed = new Set(Array.isArray(allowedOverrides) ? allowedOverrides : []);
  for (const relPath of TEMPLATE_VERIFIED_FILES) {
    const templateHash = await sha256(resolve(templateRoot, relPath));
    const reportHash = await sha256(resolve(reportRoot, relPath));
    if (!templateHash) {
      console.error(`MISSING template file: ${relPath}`);
      mismatches.push(relPath);
    } else if (!reportHash) {
      console.error(`MISSING report file: ${relPath}`);
      mismatches.push(relPath);
    } else if (templateHash !== reportHash) {
      if (allowed.has(relPath)) {
        console.warn(`OVERRIDE ${relPath} (declared in ReportRuntimeConfig.templateOverrides)`);
      } else {
        console.error(`STALE ${relPath} (template=${templateHash.slice(0, 12)} report=${reportHash.slice(0, 12)})`);
        mismatches.push(relPath);
      }
    }
  }
  if (mismatches.length) {
    console.error(`\n${mismatches.length} undeclared template file(s) out of sync. Run --refresh-template or declare reviewed overrides.`);
  } else {
    console.log(`OK   ${TEMPLATE_VERIFIED_FILES.length} template files verified hash-identical`);
  }
  return mismatches.length === 0;
}

const runtimeFiles = [
  "index.html",
  "report-embedded-data.js",
  "report-config.js",
  "app.css",
  "app.js",
  "report-data.js",
  "architecture-data.js",
  "trace-view.js",
  "hbm-view.js",
  "outputs/hbm_series.json",
  "outputs/model_architecture_graph.json",
  "outputs/architecture_overlay_map.json",
  "outputs/trace_bindings.json",
  "design-system/tokens/foundation.css",
  "design-system/tokens/semantic.css",
  "design-system/tokens/components.css",
  "design-system/css/style.css",
  "design-system/patterns/workbench-shell/pattern.css",
  "design-system/patterns/workbench-shell/pattern.js",
  "design-system/patterns/ide-frame/pattern.css",
  "design-system/patterns/ide-frame/pattern.js",
  "design-system/patterns/model-graphviz/pattern.css",
  "design-system/patterns/model-graphviz/pattern.js",
  "design-system/patterns/swimlane-task/pattern.css",
  "design-system/patterns/swimlane-task/pattern.js",
  "design-system/patterns/timeline-time-selection/pattern.css",
  "design-system/patterns/timeline-time-selection/pattern.js",
];

await Promise.all(runtimeFiles.map((path) => access(resolve(reportRoot, path))));

const readText = (path) => readFile(resolve(reportRoot, path), "utf8");
const { source: configSource, config: runtimeConfig, defaultedOptionalKeys } = await readRuntimeConfig(reportRoot);
// Template hash check — verify runtime files match skill template
const templateHashesOk = await checkTemplateHashes(runtimeConfig.templateOverrides);
const optionalFallback = (key) => key === "findings"
  ? { schema_version: 1, advisory_only: true, nodes: [] }
  : key === "expertInventory"
    ? { schema_version: 1, available: false }
    : key === "operatorDetails"
      ? { schema_version: 1, source: null, count: 0, details: {} }
      : { schema_version: "1.0", bandwidth: { points: [] }, occupancy: { points: [] } };
const readConfiguredJson = async (key) => {
  const path = resolve(reportRoot, runtimeConfig[key]);
  if (!(await exists(path)) && defaultedOptionalKeys.includes(key)) return optionalFallback(key);
  return JSON.parse(await readFile(path, "utf8"));
};
const [indexHtml, embeddedDataSource, appCss, appSource, reportDataSource, architectureDataSource, traceViewSource, hbmViewSource, swimlanePatternSource, swimlanePatternCss, timeSelectionPatternSource, timeSelectionPatternCss, modelGraphPatternSource, modelGraphPatternCss, hbmData, findings, expertInventory, analysis, perf, timeline, rawTraceDocument, graphSpec, overlayMap, traceBindings, operatorDetails] = await Promise.all([
  readText("index.html"),
  readText("report-embedded-data.js"),
  readText("app.css"),
  readText("app.js"),
  readText("report-data.js"),
  readText("architecture-data.js"),
  readText("trace-view.js"),
  readText("hbm-view.js"),
  readText("design-system/patterns/swimlane-task/pattern.js"),
  readText("design-system/patterns/swimlane-task/pattern.css"),
  readText("design-system/patterns/timeline-time-selection/pattern.js"),
  readText("design-system/patterns/timeline-time-selection/pattern.css"),
  readText("design-system/patterns/model-graphviz/pattern.js"),
  readText("design-system/patterns/model-graphviz/pattern.css"),
  readConfiguredJson("hbm"),
  readConfiguredJson("findings"),
  readConfiguredJson("expertInventory"),
  readConfiguredJson("analysis"),
  readConfiguredJson("performance"),
  readConfiguredJson("timeline"),
  readConfiguredJson("trace"),
  readConfiguredJson("architecture"),
  readConfiguredJson("overlay"),
  readConfiguredJson("bindings"),
  readConfiguredJson("operatorDetails"),
]);

new vm.Script(appSource, { filename: "app.js" });
new vm.Script(embeddedDataSource, { filename: "report-embedded-data.js" });
new vm.Script(configSource, { filename: "report-config.js" });
new vm.Script(reportDataSource, { filename: "report-data.js" });
new vm.Script(architectureDataSource, { filename: "architecture-data.js" });
new vm.Script(traceViewSource, { filename: "trace-view.js" });
new vm.Script(hbmViewSource, { filename: "hbm-view.js" });
new vm.Script(timeSelectionPatternSource, { filename: "timeline-time-selection/pattern.js" });

const generationProvenance = runtimeConfig.provenance || analysis.generation_provenance || {};
const provenanceSkills = Array.isArray(generationProvenance.skills) ? generationProvenance.skills.filter(Boolean) : [];
const provenanceModelSource = generationProvenance.modelSource || generationProvenance.model_source;
const provenanceExtractorModel = generationProvenance.extractorModel || generationProvenance.extractor_model;

const sandbox = { window: {} };
const embeddedSandbox = { window: {} };
vm.runInNewContext(embeddedDataSource, embeddedSandbox, { filename: "report-embedded-data.js" });
const embeddedData = embeddedSandbox.window.ReportEmbeddedData;
vm.runInNewContext(reportDataSource, sandbox, { filename: "report-data.js" });
vm.runInNewContext(architectureDataSource, sandbox, { filename: "architecture-data.js" });
const reportModel = sandbox.window.DeepSeekReportData.createReportModel(analysis, perf, timeline);
const graph = sandbox.window.DeepSeekArchitectureData.createArchitectureGraph(graphSpec, reportModel.reports);
const applyExpertInventory = typeof sandbox.window.DeepSeekArchitectureData.applyExpertInventory === "function"
  ? sandbox.window.DeepSeekArchitectureData.applyExpertInventory
  : (value) => value;
const expertGraphSpec = applyExpertInventory(graphSpec, expertInventory);
const expertGraph = sandbox.window.DeepSeekArchitectureData.createArchitectureGraph(expertGraphSpec, reportModel.reports);
const expertItems = collectLogicalItems(expertGraphSpec.roots);
const expertInventoryAvailable = expertInventory?.available !== false
  && Number.isFinite(Number(expertInventory?.declared?.routed_experts));
if (expertInventoryAvailable && typeof sandbox.window.DeepSeekArchitectureData.applyExpertInventory !== "function") {
  throw new Error("This report declares expert inventory but its architecture adapter cannot apply it; refresh the Skill 3 template");
}
const declaredExpertItems = [...expertItems.values()].filter((item) => item.expertRole === "declared-expert");
const routedExpertGroups = [...expertItems.values()].filter((item) => item.expertRole === "routed-group");
const visibleDispatchItems = [...expertItems.values()].filter((item) => item.expertRole === "dispatch" && item.visualHidden !== true);
const moeContainers = [...expertItems.values()].filter((item) => item.expertRole === "moe-container");
const projectedNodeById = new Map(graph.nodes.map((node) => [node.id, node]));
// Only activation-style flow is required to advance down the page. Residual/skip edges are
// exempt by construction: they carry a block's input past the block, and when the block is a
// folded repeated group the sink is the next invocation, i.e. upward. They get their own
// side lane (`residual_outer_left`) precisely so they can span or reverse rows without being
// mistaken for a forward step. Filtering on the policy keeps the guarantee where it belongs.
const nonTopToBottomDataflowEdges = graph.edges.filter((edge) => {
  const source = projectedNodeById.get(edge.source);
  const target = projectedNodeById.get(edge.target);
  return source && target && edge.routingPolicy === "semantic_top_to_bottom"
    && !(Number(target.y) > Number(source.y));
});

function values(value) {
  if (Array.isArray(value)) return value;
  if (value && typeof value === "object") return Object.values(value);
  return [];
}

function hasNoExplicitSub12FontSize(source) {
  return [...source.matchAll(/font-size\s*:\s*(\d+(?:\.\d+)?)px/gi)]
    .every((match) => Number(match[1]) >= 12);
}

function appTypographyHasOnlyFormulaException(source) {
  const withoutMetricFormula = source.replace(/\.metric-formula\s*\{[^}]*\}/gs, "");
  return /\.metric-formula\s*\{[^}]*font-size:\s*11px/s.test(source)
    && hasNoExplicitSub12FontSize(withoutMetricFormula);
}

function collectNodeIds(items, ids = new Set()) {
  for (const node of values(items)) {
    if (!node || typeof node !== "object") continue;
    if (typeof node.node_id === "string" && node.node_id) ids.add(node.node_id);
    collectNodeIds(node.children, ids);
  }
  return ids;
}

function collectLogicalItems(items, byId = new Map()) {
  for (const item of items || []) {
    byId.set(item.id, item);
    collectLogicalItems(item.children, byId);
  }
  return byId;
}

function integerIndices(value) {
  return [...new Set(values(value).map(Number).filter(Number.isInteger))].sort((a, b) => a - b);
}

function declaredGroupIndices(group) {
  const explicit = integerIndices(group?.model_layer_indices);
  if (explicit.length) return explicit;
  const range = group?.model_layer_range;
  if (!Array.isArray(range) || range.length !== 2) return [];
  const start = Number(range[0]);
  const end = Number(range[1]);
  if (!Number.isInteger(start) || !Number.isInteger(end) || end < start) return [];
  return Array.from({ length: end - start + 1 }, (_, offset) => start + offset);
}

function sameIndices(left, right) {
  const a = integerIndices(left);
  const b = integerIndices(right);
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

const analysisNodeIds = collectNodeIds([
  ...values(analysis.stages),
  ...values(analysis.layer_structure),
  ...values(analysis.runtime_auxiliary),
]);
const perfNodeIds = collectNodeIds(perf.modules);
const logicalItems = collectLogicalItems(graphSpec.roots);
const mappingIds = overlayMap.mappings.map((mapping) => mapping.backend_node_id);
const mappingIdSet = new Set(mappingIds);
const graphItems = [...graph.nodes, ...graph.clusters];
const sourceArchitectureCluster = graph.clusters.find((cluster) => cluster.id === "section/source_architecture");
const graphNodeIds = new Set(graph.nodes.map((node) => node.id));
const anchorSide = (anchor) => typeof anchor === "string" ? anchor : anchor?.side;
const graphBackendIds = new Set(graphItems.filter((item) => item.selectable).map((item) => item.backendNodeId).filter(Boolean));
const timelineEvents = values(timeline.events);
const mappedTimelineEvents = timelineEvents.filter((event) => event.owner_node_id).length;
const sourceOnlyItems = graphItems.filter((item) => item.dataState === "source_only");
const sourceOnlyLogicalItems = [...logicalItems.values()].filter((item) => (
  item.origin === "source" && item.dataState === "source_only"
));
const perfRecords = [];
(function collectPerfRecords(items) {
  for (const item of values(items)) {
    if (!item || typeof item !== "object") continue;
    if (typeof item.node_id === "string") perfRecords.push(item);
    collectPerfRecords(item.children);
  }
}(perf.modules));
const perfById = new Map(perfRecords.map((record) => [record.node_id, record]));
const decoderGroups = values(analysis.architecture?.layer_groups);
const decoderTemplates = Object.entries(analysis.layer_structure || {})
  .filter(([, node]) => node?.node_id && !/(mtp|runtime|auxiliary|scaffold)/i.test(`${node.node_id}/${node.name || ""}`))
  .map(([key, node]) => ({ key, node }));
const decoderMembershipErrors = [];
const matchedGroups = new Set();
const layerOwners = new Map();
const overlappingLayers = new Set();
for (const template of decoderTemplates) {
  let group = decoderGroups.find((candidate) => candidate?.type === template.key);
  if (!group && decoderGroups.length === 1 && decoderTemplates.length === 1) group = decoderGroups[0];
  if (!group) {
    decoderMembershipErrors.push(`${template.key}: no matching architecture.layer_groups entry`);
    continue;
  }
  if (matchedGroups.has(group)) {
    decoderMembershipErrors.push(`${group.type}: matched by more than one decoder template`);
    continue;
  }
  matchedGroups.add(group);
  const expected = declaredGroupIndices(group);
  const analysisIndices = integerIndices(
    values(template.node.declared_instance_indices).length
      ? template.node.declared_instance_indices
      : template.node.instance_indices,
  );
  const observedIndices = integerIndices(template.node.instance_indices);
  const graphItem = logicalItems.get(template.node.node_id)
    || [...logicalItems.values()].find((item) => item.backendNodeId === template.node.node_id);
  const graphIndices = integerIndices(graphItem?.instanceIndices);
  const perfRecord = perfById.get(template.node.node_id);
  const perfIndices = integerIndices(perfRecord?.instance_indices);
  if (!expected.length) decoderMembershipErrors.push(`${group.type}: declared layer membership is empty`);
  if (!sameIndices(analysisIndices, expected)) {
    decoderMembershipErrors.push(`${group.type}: analysis membership ${JSON.stringify(analysisIndices)} != declared ${JSON.stringify(expected)}`);
  }
  if (!sameIndices(graphIndices, expected)) {
    decoderMembershipErrors.push(`${group.type}: graph membership ${JSON.stringify(graphIndices)} != declared ${JSON.stringify(expected)}`);
  }
  if (!perfRecord) {
    decoderMembershipErrors.push(`${group.type}: no performance record for ${template.node.node_id}`);
  } else if (!sameIndices(perfIndices, observedIndices)) {
    decoderMembershipErrors.push(`${group.type}: performance membership ${JSON.stringify(perfIndices)} != observed ${JSON.stringify(observedIndices)}`);
  }
  for (const layerIndex of analysisIndices) {
    const previous = layerOwners.get(layerIndex);
    if (previous) overlappingLayers.add(layerIndex);
    else layerOwners.set(layerIndex, group.type);
  }
  const ownedEvents = timelineEvents.filter((event) => (
    event.owner_node_id === template.node.node_id
      || String(event.owner_node_id || "").startsWith(`${template.node.node_id}/`)
  ));
  const eventIndices = integerIndices(ownedEvents.map((event) => event.layer_index));
  const missingObserved = observedIndices.filter((layerIndex) => !eventIndices.includes(layerIndex));
  const unexpectedObserved = eventIndices.filter((layerIndex) => !observedIndices.includes(layerIndex));
  if (missingObserved.length) {
    decoderMembershipErrors.push(`${group.type}: Timeline misses observed layers ${missingObserved.join(",")}`);
  }
  if (unexpectedObserved.length) {
    decoderMembershipErrors.push(`${group.type}: Timeline contains out-of-membership layers ${unexpectedObserved.join(",")}`);
  }
}
if (overlappingLayers.size) {
  decoderMembershipErrors.push(`overlapping decoder-template layers: ${[...overlappingLayers].sort((a, b) => a - b).join(",")}`);
}
if (matchedGroups.size !== decoderGroups.length) {
  const missingGroups = decoderGroups.filter((group) => !matchedGroups.has(group)).map((group) => group.type);
  if (missingGroups.length) decoderMembershipErrors.push(`unmatched decoder groups: ${missingGroups.join(",")}`);
}
const declaredDecoderIndices = integerIndices(decoderGroups.flatMap(declaredGroupIndices));
if (Number.isInteger(Number(analysis.architecture?.num_main_layers))) {
  const expectedMainIndices = Array.from(
    { length: Number(analysis.architecture.num_main_layers) },
    (_, index) => index,
  );
  if (!sameIndices(declaredDecoderIndices, expectedMainIndices)) {
    decoderMembershipErrors.push(`decoder layer-group union ${JSON.stringify(declaredDecoderIndices)} does not cover 0-${expectedMainIndices.at(-1)}`);
  }
}
const rawTraceEvents = Array.isArray(rawTraceDocument) ? rawTraceDocument : values(rawTraceDocument.traceEvents);
const tracePhases = new Set(rawTraceEvents.map((event) => event.ph));
const traceProcessNames = new Set(rawTraceEvents
  .filter((event) => event.ph === "M" && event.name === "process_name")
  .map((event) => event.args?.name)
  .filter(Boolean));
const traceDurationEvents = rawTraceEvents.filter((event) => event.ph === "X");
const traceFlowStarts = rawTraceEvents.filter((event) => event.ph === "s");
const traceFlowFinishes = rawTraceEvents.filter((event) => event.ph === "f");
const bindings = values(traceBindings.bindings);
const operatorDetailRecords = operatorDetails?.details || {};
const operatorDetailsAvailable = operatorDetails?.source != null || Object.keys(operatorDetailRecords).length > 0;
const bindingsMissingOperatorDetails = bindings.filter((binding) => !Object.hasOwn(operatorDetailRecords, String(binding.op_index)));
const hbmBandwidthPoints = values(hbmData.bandwidth?.points);
const hbmOccupancyPoints = values(hbmData.occupancy?.points);
const bindingOpIndices = new Set(bindings.map((binding) => binding.op_index));
const bindingRawIndices = new Set(bindings.map((binding) => binding.raw_source_event_index));
const capabilities = runtimeConfig.capabilities || {};
const expectedProcessTracks = Array.isArray(capabilities.expectedProcessTracks)
  ? capabilities.expectedProcessTracks
  : [];
const requiresRepeatedLayers = capabilities.repeatedLayers === true;
const requiresAicoreFrequency = capabilities.aicoreFrequency === true;
const requiresProvenance = runtimeConfig.handoffSchemaVersion === "ui_report_handoff.v1";

const assertions = [
  [[analysis.model_id, perf.model_id, timeline.model_id].every((value) => value === analysis.model_id), "model_id matches across backend files"],
  [!expertInventoryAvailable || (Number(expertInventory.declared.routed_experts) === expertInventory.experts.filter((item) => item.kind === "routed").length
    && Number(expertInventory.declared.shared_experts) === expertInventory.experts.filter((item) => item.kind === "shared").length), "expert inventory declared counts match its expert records"],
  [!expertInventoryAvailable || Number(expertInventory.expert_parallelism.local_routed_experts) * Number(expertInventory.expert_parallelism.moe_ep_size) === Number(expertInventory.declared.routed_experts), "expert inventory local routed count and EP size cover the declared routed experts"],
  [!expertInventoryAvailable || (moeContainers.length > 0 && routedExpertGroups.length === moeContainers.length
    && visibleDispatchItems.length === 0 && declaredExpertItems.length === moeContainers.length * 3
    && expertGraph.edges.some((edge) => edge.id.startsWith("expert-routing::"))), "Skill 3 projects every MoE as direct Router-to-expert fan-out beside Shared Expert without an extra expert-bank or visible Dispatch layer"],
  [!expertInventoryAvailable || expertInventory.measurability.separable_per_expert === true
    || declaredExpertItems.every((item) => !item.backendNodeId && !item.metricBadge), "fused expert execution never fabricates per-expert backend identity or timing"],
  [!expertInventoryAvailable || expertInventory.expert_parallelism.resident_expert_indices
    || declaredExpertItems.every((item) => /does not identify the resident EP rank/.test(item.attributes?.semantic || "")), "missing EP rank is disclosed instead of assigning resident global expert identities"],
  [!expertInventoryAvailable || (embeddedData.expertInventory && runtimeConfig.expertInventory === "./outputs/expert_inventory.json"), "expert inventory is available to HTTP and standalone reports"],
  [architectureDataSource.includes('dataState: hasCurrentPerformance ? common.dataState : "no_performance_data"')
    && modelGraphPatternSource.includes("node.dataState !== 'no_performance_data'")
    && architectureDataSource.includes('metricBadge: hasPerformanceBadge ? report.metricShort : undefined')
    && modelGraphPatternCss.includes(".pto-model-graphviz-node.is-no-performance-data > rect:first-child"), "mapped architecture nodes without current-Layer performance data render neutral gray without a metric badge and are excluded from heat coloring"],
  [[analysis.report_id, perf.report_id, timeline.report_id].every((value) => value === analysis.report_id), "report_id matches across backend files"],
  [analysisNodeIds.size > 0 && analysisNodeIds.size === perfNodeIds.size && [...analysisNodeIds].every((id) => perfNodeIds.has(id)), "analysis and performance node IDs match exactly"],
  [mappingIds.length === mappingIdSet.size && mappingIdSet.size === analysisNodeIds.size && [...analysisNodeIds].every((id) => mappingIdSet.has(id)), "every backend node has exactly one explicit mapping classification"],
  [overlayMap.mappings.every((mapping) => logicalItems.has(mapping.projected_graph_node_id) && mapping.source_node_ids.every((id) => logicalItems.has(id)) && values(mapping.evidence).length > 0), "all mapping targets resolve and carry evidence"],
  [graphBackendIds.size === analysisNodeIds.size && [...analysisNodeIds].every((id) => graphBackendIds.has(id)), "every backend node resolves to one interactive graph item"],
  [(!requiresRepeatedLayers && decoderTemplates.length === 0) || (decoderTemplates.length > 0 && decoderMembershipErrors.length === 0),
    decoderMembershipErrors.length
      ? `decoder templates have exact, disjoint layer membership and complete Timeline coverage: ${decoderMembershipErrors.join("; ")}`
      : "decoder templates have exact, disjoint layer membership and complete Timeline coverage"],
  [sourceOnlyItems.length > 0 && sourceOnlyItems.every((item) => !item.backendNodeId && !item.metricBadge), "source-only rendered items remain metric-free and have no backend identity"],
  // This asserts a property OF source-only items, not that a model must have one. A capture that
  // exercised every declared structure node has zero, which is a stronger result than a partial
  // one — requiring at least one failed such a report for being too complete.
  [sourceOnlyLogicalItems.every((item) => item.selectable === true && Array.isArray(item.sourceRefs) && item.sourceRefs.length > 0), "source-only architecture items are metadata-selectable and preserve sourceRefs"],
  [graphSpec.schema_version === "model_architecture_graph.v1" && logicalItems.has("section/source_architecture") && logicalItems.has("section/runtime_auxiliary"), "architecture uses the synchronized JSON graph contract with separate source and runtime roots"],
  [(graphSpec.edges || []).every((edge) => logicalItems.has(edge.source) && logicalItems.has(edge.target) && edge.tensor && Array.isArray(edge.provenance) && edge.provenance.length > 0), "architecture edges resolve and preserve tensor metadata plus provenance"],
  [graph.edges.every((edge) => edge.routingPolicy === "parameter_side_input"
    ? edge.curve === "horizontal" && ["left", "right"].includes(anchorSide(edge.sourceAnchor)) && ["left", "right"].includes(anchorSide(edge.targetAnchor))
    : edge.routingPolicy === "parameter_outer_side"
    ? edge.route === "orthogonal" && edge.fixedPorts === true
      && Array.isArray(edge.waypoints) && edge.waypoints.length === 2
      && ["left", "right"].includes(anchorSide(edge.sourceAnchor)) && anchorSide(edge.targetAnchor) === "top"
    // A residual/skip edge leaves and re-enters through a side port and travels in its own
    // lane beside the column, so it clears the nodes it bypasses instead of crossing them.
    // Its waypoints share one x, which is what keeps the lane straight and outside the block.
    : edge.routingPolicy === "residual_outer_left"
    ? edge.sourceAnchor === "left" && edge.targetAnchor === "left"
      && Array.isArray(edge.waypoints) && edge.waypoints.length === 2
      && edge.waypoints[0].x === edge.waypoints[1].x
      && edge.route === "orthogonal" && edge.fixedPorts === true
    : edge.routingPolicy === "semantic_top_to_bottom" && anchorSide(edge.sourceAnchor) === "bottom" && anchorSide(edge.targetAnchor) === "top" && edge.curve === "vertical"), "rendered semantic edges follow bottom-to-top ports with an endpoint gap except declared parameter side inputs and fixed orthogonal residual lanes"],
  [graph.edges.every((edge) => graphNodeIds.has(edge.source) && graphNodeIds.has(edge.target)), "all rendered edges resolve to graph nodes"],
  [graphItems.every((item) => [item.x, item.y, item.width, item.height].every(Number.isFinite) && item.width > 0 && item.height > 0), "graph geometry is finite"],
  [architectureDataSource.includes("clusterTitleMinimumWidth") && architectureDataSource.includes("leafMinimumWidth") && architectureDataSource.includes("estimateLayoutTextWidth"), "graph frames expand to contain long cluster and node titles"],
  [timelineEvents.length === timeline.event_count, "timeline event_count matches the event array"],
  [mappedTimelineEvents === timeline.mapping_summary?.mapped_events && timelineEvents.length - mappedTimelineEvents === timeline.mapping_summary?.unmapped_events, "timeline mapping summary is backend-authored and internally consistent"],
  [timelineEvents.every((event) => !event.owner_node_id || analysisNodeIds.has(event.owner_node_id)), "every mapped timeline owner resolves to a backend node"],
  [traceBindings.model_id === analysis.model_id && traceBindings.report_id === analysis.report_id, "TraceView bindings match the report identity"],
  [bindings.length === timelineEvents.length && bindingOpIndices.size === timelineEvents.length && timelineEvents.every((event) => bindingOpIndices.has(event.op_index)), "every normalized Timeline event has exactly one TraceView binding"],
  [bindingRawIndices.size === bindings.length && bindings.every((binding) => rawTraceEvents[binding.raw_source_event_index]?.ph === "X"), "every binding resolves to one distinct raw duration event"],
  [bindings.every((binding) => analysisNodeIds.has(binding.node_id)), "every TraceView binding resolves to a backend structure node"],
  [traceBindings.summary?.coverage_pct === 100 && traceBindings.summary?.bound_events === timelineEvents.length, "TraceView binding coverage is 100 percent"],
  [reportModel.counts.analysisNodes === analysisNodeIds.size && reportModel.counts.perfNodes === perfNodeIds.size && reportModel.counts.timelineEvents === timelineEvents.length, "runtime adapter preserves backend counts"],
  [perfRecords.length === perfNodeIds.size && perfRecords.every((item) => ["time_us", "time_pct", "nops", "hbm_mb", "mfu_int8_pct", "mfu_bf16_pct", "metric_scope", "op_ratio"].every((key) => Object.hasOwn(item, key))), "every performance node exposes the complete Inspector metric contract"],
  [indexHtml.includes('id="coreMetricGrid"') && reportDataSource.includes("deriveCoreEventMetrics") && reportDataSource.includes("core_event_metrics") && reportDataSource.includes("event_metrics") && reportDataSource.includes("structure_instance_node_id === nodeId") && ["wall_ms", "busy_union_ms", "kernel_sum_ms", "total_cost_ms"].every((key) => reportDataSource.includes(key)), "Inspector promotes all four metrics_report core event metrics and derives scope-correct current-capture fallbacks from mapped events"],
  [graphSpec.metadata?.backendNodeCount === analysisNodeIds.size && overlayMap.validation?.all_backend_nodes_classified === true, "generated artifact metadata matches current backend data"],
  [[runtimeConfig.analysis, runtimeConfig.performance, runtimeConfig.timeline].every((path) => typeof path === "string" && path.endsWith('.json')), "runtime config declares analysis, performance and Timeline JSON"],
  [typeof runtimeConfig.trace === "string" && runtimeConfig.trace.endsWith('.json'), "runtime config declares raw TraceView JSON"],
  [runtimeConfig.bindings === './outputs/trace_bindings.json', "runtime config reads generated structure-to-TraceView bindings"],
  [runtimeConfig.operatorDetails === './outputs/operator_details.json' && operatorDetails?.count === Object.keys(operatorDetailRecords).length, "runtime config reads deterministic per-operator shape and dtype details"],
  [!operatorDetailsAvailable || bindingsMissingOperatorDetails.length === 0, "available raw operator details cover every TraceView binding; unavailable details degrade to placeholders"],
  [rawTraceEvents.length > 0 && traceDurationEvents.length > 0 && ["M", "X"].every((phase) => tracePhases.has(phase)), "raw TraceView contains metadata and duration events"],
  [traceFlowStarts.length > 0 && traceFlowFinishes.length > 0 && ["s", "f"].every((phase) => tracePhases.has(phase)), "raw TraceView contains flow starts and finishes"],
  [expectedProcessTracks.every((name) => traceProcessNames.has(name)), expectedProcessTracks.length
    ? "raw TraceView exposes every handoff-declared process track"
    : "no model-specific Trace process-track set was declared"],
  [indexHtml.includes('src="./report-embedded-data.js"') && indexHtml.indexOf('src="./report-embedded-data.js"') < indexHtml.indexOf('src="./app.js"'), "entry loads standalone data before the application"],
  [indexHtml.includes('<link rel="icon" href="data:,">'), "entry declares an embedded empty favicon so HTTP and file runtimes make no implicit icon request"],
  [indexHtml.includes('src="./report-config.js"') && indexHtml.includes('src="./report-data.js"') && indexHtml.includes('src="./architecture-data.js"') && indexHtml.includes('src="./trace-view.js"') && indexHtml.includes('src="./app.js"'), "entry loads the report adapters"],
  [indexHtml.includes('src="./hbm-view.js"') && appSource.includes('loadJson("hbm", runtimeConfig.hbm)'), "entry loads the optional HBM timeline adapter and data"],
  [appSource.includes("window.ReportEmbeddedData") && ["analysis", "performance", "timeline", "trace", "bindings", "operatorDetails", "architecture", "overlay", "hbm", "findings"].every((key) => Object.hasOwn(embeddedData || {}, key)), "file protocol runtime has all embedded data keys"],
  [JSON.stringify(embeddedData?.analysis) === JSON.stringify(analysis)
    && JSON.stringify(embeddedData?.performance) === JSON.stringify(perf)
    && JSON.stringify(embeddedData?.timeline) === JSON.stringify(timeline)
    && JSON.stringify(embeddedData?.trace) === JSON.stringify(rawTraceDocument)
    && JSON.stringify(embeddedData?.bindings) === JSON.stringify(traceBindings)
    && JSON.stringify(embeddedData?.operatorDetails) === JSON.stringify(operatorDetails)
    && JSON.stringify(embeddedData?.architecture) === JSON.stringify(graphSpec)
    && JSON.stringify(embeddedData?.overlay) === JSON.stringify(overlayMap)
    && JSON.stringify(embeddedData?.hbm) === JSON.stringify(hbmData)
    && JSON.stringify(embeddedData?.findings) === JSON.stringify(findings), "standalone data exactly matches source JSON"],
  [indexHtml.includes('id="traceToolbarMount"') && indexHtml.includes('id="reportFieldTooltip"') && !indexHtml.includes('id="timelineTabStreams"') && /class="[^"]*tab-control[^"]*"[^>]*role="tablist"[^>]*hidden/.test(indexHtml), "Trace controls mount in the title bar while the compatibility tablist and redundant Streams tab stay hidden"],
  [!indexHtml.includes('id="workspaceCrumbs"') && appSource.includes('Profiling 性能报告') && appSource.includes('Profiling Performance Report') && appSource.includes('document.title = reportPageTitle()') && appSource.includes('els.workspaceTitle.textContent = reportPageTitle()'), "visible and browser report titles localize with the UI language and omit the report/schema subtitle"],
  [!indexHtml.includes('id="actionList"') && !appSource.includes('noRecommendationInBackend') && !appSource.includes('noBackendRecommendation') && !indexHtml.includes('id="factList"') && !appSource.includes('els.factList'), "Inspector omits empty recommendations and the Evidence section"],
  [!indexHtml.includes('trace-flow-toggle') && !traceViewSource.includes('type="checkbox"') && traceViewSource.includes("showSelectedFlows: false"), "Flow selection is removed and connections default to hidden until node selection"],
  [modelGraphPatternSource.includes("pagerLabelY") && modelGraphPatternSource.includes("pagerControlsY") && architectureDataSource.includes("REPEAT_CLUSTER_TITLE_HEIGHT = 112"), "repeated-layer title and pager occupy separate reserved rows"],
  [architectureDataSource.includes("REPEAT_PAGER_SIDE_PADDING = 52"), "repeated-layer pager reserves explicit side padding outside both arrows"],
  [architectureDataSource.includes("EDGE_NODE_GAP = 6")
    && architectureDataSource.includes("ROW_GAP = 40")
    && architectureDataSource.includes("BRANCH_ROW_GAP = 64")
    && architectureDataSource.includes('routingPolicy: "parameter_outer_side"')
    && modelGraphPatternSource.includes("fill: 'context-stroke'")
    && modelGraphPatternSource.includes("markerWidth: '8'")
    && modelGraphPatternSource.includes("markerUnits: 'userSpaceOnUse'")
    && modelGraphPatternSource.includes("portOffset(group, edge, source")
    && modelGraphPatternCss.includes(".pto-model-graphviz-edge.is-residual")
    && modelGraphPatternCss.includes("opacity: 0.82"), "architecture edges keep readable source provenance, inherited arrow color, endpoint clearance, shared fan-out forks, and dedicated residual/parameter lanes"],
  [architectureDataSource.includes("function markStructuralShells")
    && architectureDataSource.includes("structuralShellIds.has(item.id)")
    && modelGraphPatternCss.includes("var(--foreground-secondary) 78%"), "single-child synthetic source wrappers stay structural-only and graph edges use a neutral gray"],
  [modelGraphPatternSource.includes("opts.onClearSelection?.({ source: 'canvas' })") && modelGraphPatternCss.includes("pointer-events: visibleStroke") && appSource.includes("onClearSelection()") && appSource.includes("function clearSelection()"), "empty architecture canvas, including cluster interiors, clears selection through the shared page reset path"],
  [traceViewSource.includes("TARGET_EVENT_VIEWPORT_RATIO = 0.5") && traceViewSource.includes("FOCUS_PAN_VIEWPORTS = 8") && traceViewSource.includes("MAX_TRACK_WIDTH = 16000"), "Trace focus uses the 50 percent target while retaining scrollable horizontal context"],
  [traceViewSource.includes('data-trace-action="fit"') && traceViewSource.includes('data-trace-action="focus"') && traceViewSource.includes("focus.disabled = !focusEvent"), "Trace toolbar provides fit-all and selection-gated focus actions"],
  [indexHtml.includes('href="./design-system/patterns/timeline-time-selection/pattern.css"') && indexHtml.includes('src="./design-system/patterns/timeline-time-selection/pattern.js"') && indexHtml.indexOf('src="./design-system/patterns/timeline-time-selection/pattern.js"') < indexHtml.indexOf('src="./trace-view.js"'), "entry loads the shared timeline time-selection pattern before TraceView"],
  [timeSelectionPatternSource.includes("bindTimelineInteraction") && timeSelectionPatternSource.includes("setPointerCapture") && timeSelectionPatternSource.includes("event.ctrlKey") && timeSelectionPatternSource.includes("event.metaKey") && timeSelectionPatternSource.includes("'ArrowLeft'") && timeSelectionPatternSource.includes("'ArrowRight'") && timeSelectionPatternSource.includes("formatSelectionSummary") && timeSelectionPatternCss.includes(".pto-timeline-time-selection-summary"), "shared timeline pattern owns drag capture, modifier-wheel dispatch, keyboard navigation, selection geometry, and exact-time summary"],
  [traceViewSource.includes("PtoTimelineTimeSelectionPattern") && traceViewSource.includes("createSelectionLayer") && traceViewSource.includes("onPreview: (selection)") && traceViewSource.includes("onEventSelect: selectEvent") && traceViewSource.includes("pendingScrollAnchor") && traceViewSource.includes("panTimeline(direction") && traceViewSource.includes("getTimeSelection()"), "TraceView consumes the shared pattern for range selection, event selection, cursor-anchored zoom, keyboard pan, and persistent timestamp state"],
  [appSource.includes("onEventSelect(event)") && appSource.includes('source: "trace-event"') && appSource.includes("syncTrace: false") && appSource.includes("options.syncTrace !== false"), "mapped Trace event clicks synchronize Inspector and architecture without replacing the exact event selection"],
  [traceViewSource.includes("PtoSwimlaneTaskPattern") && traceViewSource.includes("drawTaskBar") && traceViewSource.includes("showLabel: false") && traceViewSource.includes("drawTaskLabel") && traceViewSource.includes("event.streamSequence = nextSequence") && traceViewSource.includes("right.drawWidth - left.drawWidth") && traceViewSource.includes("range.start < occupied.end && range.end > occupied.start") && traceViewSource.includes("const labelOverlays") && traceViewSource.includes('`#${event.streamSequence} · ${eventName}`') && swimlanePatternSource.includes("function drawTaskLabel") && swimlanePatternSource.includes("drawTaskLabel,"), "Trace events use numbered Stream-local labels, preserve adjacent labels, and draw them in a final shared overlay pass"],
  [traceViewSource.includes("const LANE_HEIGHT = 22") && traceViewSource.includes("y: 2") && traceViewSource.includes("height: 18") && traceViewSource.includes("fillRect(x, 2, drawWidth, 18)"), "Trace event bars use 18px height inside unchanged 22px lanes"],
  [swimlanePatternSource.includes("readableTextColor(segment.fill)") && swimlanePatternSource.includes("selectedLightenAmount: 10"), "Swimlane task selection preserves colormap hue and resolves label contrast from each final segment fill"],
  [appSource.includes('performanceHeatmap: { enabled: true }') && modelGraphPatternSource.includes("PERFORMANCE_HEATMAP_TURBO_STOPS") && modelGraphPatternSource.includes("name: 'turbo'") && modelGraphPatternSource.includes("Math.log(resolvedValue)") && modelGraphPatternSource.includes("positiveValues") && modelGraphPatternSource.includes("'#30123B'") && modelGraphPatternSource.includes("'#DA3907'") && !modelGraphPatternSource.includes("baseColor: sourceFill") && modelGraphPatternSource.includes("performanceHeatmapTextColor") && modelGraphPatternCss.includes("var(--model-graphviz-performance-text)") && ["#4145AB", "#39A2FC", "#45F884", "#E8D721", "#DA3907"].every((color) => modelGraphPatternCss.includes(color)), "operator heat defaults on and shares the approved logarithmic Turbo domain with Layer dots and contrast-aware labels"],
  [indexHtml.includes('id="operatorColorLegend"')
    && indexHtml.includes('id="operatorColorLegendMin"')
    && indexHtml.includes('id="operatorColorLegendMax"')
    && indexHtml.includes('data-i18n="operatorColorLegend"')
    && appSource.includes("function updateOperatorColorLegend")
    && appSource.includes("heatmap?.enabled === true")
    && appSource.includes("heatmap.mappedNodeCount")
    && appSource.includes("heatmap.minValue")
    && appSource.includes("heatmap.maxValue")
    && appCss.includes(".operator-color-legend__gradient")
    && ["#30123b", "#4145ab", "#39a2fc", "#45f884", "#e8d721", "#da3907"].every((color) => appCss.includes(color)), "operator heatmap output includes a visible localized Turbo legend whose range is bound to the rendered graph"],
  [modelGraphPatternCss.includes('.pto-model-graphviz-node.is-source-only > rect:first-child') && modelGraphPatternCss.includes('fill: var(--surface-3) !important') && modelGraphPatternCss.includes('.pto-model-graphviz-node.is-source-only .pto-model-graphviz-node-label'), "source-only architecture nodes use neutral deep-gray surfaces and labels instead of semantic or heat colors"],
  [nonTopToBottomDataflowEdges.length === 0, "every projected semantic dataflow edge advances to a lower row"],
  [hbmViewSource.includes("adaptiveDomain") && hbmViewSource.includes("context.lineTo") && hbmViewSource.includes("context.stroke()") && !hbmViewSource.includes("context.arc") && ["read", "write", "occupancy"].every((name) => hbmViewSource.includes(`data-hbm-chart="${name}"`)), "HBM uses three independently scaled continuous Read, Write, and occupancy lines without disconnected sample dots"],
  [traceViewSource.includes("visibleTimelineRange") && traceViewSource.includes("notifyVisibleRange") && traceViewSource.includes("onVisibleRangeChange") && traceViewSource.includes("onViewportInteraction") && appSource.includes("hbmFollowsTrace: false") && appSource.includes("state.hbmFollowsTrace ? state.traceVisibleRange : null") && appSource.includes("state.hbmController?.setRange(range.start, range.end)") && appSource.includes('source === "fit" || source === "reset"') && appSource.includes("state.hbmController?.resetRange()") && hbmViewSource.includes("setRange(start, end)") && hbmViewSource.includes("resetRange()") && hbmViewSource.includes("MIN_VISIBLE_RAW_SAMPLES = 5") && hbmViewSource.includes("minimumVisibleSpan") && hbmViewSource.includes("interpolateSeriesWindow") && hbmViewSource.includes("getSourcePointCounts"), "HBM starts and Fit All resets to the full decode range, while Trace focus uses a sampling-aware window without dropping source samples"],
  [hbmViewSource.includes('HBM Bandwidth & Occupancy') && hbmViewSource.includes('HBM 带宽与占用量') && !hbmViewSource.includes('sample-level alignment') && !hbmViewSource.includes('采样级关联') && !hbmViewSource.includes('hbm-view-meta'), "HBM panel uses a localized metric title without sampling implementation copy"],
  [!requiresAicoreFrequency || (Number.isFinite(Number(perf.device_profile?.aicore_freq_mhz ?? perf.aicore_freq_mhz))
    && Number.isFinite(Number(perf.device_profile?.derived?.min_mhz))
    && Number.isFinite(Number(perf.device_profile?.derived?.max_mhz))
    && hbmViewSource.includes('frequencyTitle: "AICore 频率"')
    && hbmViewSource.includes('frequencyTitle: "AICore Frequency"')
    && hbmViewSource.includes("function createFrequencyMarkup")
    && hbmViewSource.includes("data-frequency-toggle")
    && hbmViewSource.includes("aicore-frequency-step")
    && hbmViewSource.includes("aicore-frequency-derived-band")
    && hbmViewSource.includes('x="4"')
    && hbmViewSource.includes('width="992"')
    && hbmViewSource.includes("aicore-frequency-scale")
    && hbmViewSource.includes("pointY(maximum) / 82 * 100")
    && hbmViewSource.includes("pointY(current) / 82 * 100")
    && hbmViewSource.includes("pointY(minimum) / 82 * 100")
    && hbmViewSource.includes('${formatFrequency(current)} / ${current.toFixed(0)} MHz')
    && hbmViewSource.includes('data-report-tooltip="${crossCheckTip} · ${throttlingTip}"')
    && !hbmViewSource.includes("aicore-frequency-info")
    && !hbmViewSource.includes("aicore-frequency-point")
    && !hbmViewSource.includes("declaredFrequency")
    && !appCss.includes(".aicore-frequency-axis")
    && !hbmViewSource.includes("aicore-frequency-card")
    && !hbmViewSource.includes("aicore-frequency-stats")
    && !hbmViewSource.includes('data-hbm-chart="frequency"')
    && appSource.includes("deviceProfile = perf?.device_profile")
    && appSource.includes("deviceProfile,")), "handoff-declared AICore frequency renders as a collapsible verified range summary without inventing a time-series curve"],
  [findings?.schema_version === 1 && findings?.advisory_only === true && Array.isArray(findings?.nodes) && findings.nodes.every((node) => typeof node.path === "string" && Array.isArray(node.findings)), "diagnostic findings use the advisory-only node-path contract"],
  [indexHtml.includes('id="diagnosisSection"') && indexHtml.includes('id="diagnosisCard"') && appSource.includes("function diagnosisPathForNodeId") && appSource.includes("function findingsForReport") && appSource.includes("function renderDiagnosis") && appSource.includes('diagnosisAdvice: "诊断建议"') && appCss.includes(".diagnosis-card") && appCss.includes("linear-gradient(135deg") && appCss.includes("#9b7bff") && appCss.includes("#66bfff"), "Inspector renders node-scoped diagnostic advice below metrics in a transparent lavender-to-blue card"],
  [hbmViewSource.includes("const hasData") && hbmViewSource.includes("hbm-empty-state") && hbmViewSource.includes("未采集到 HBM") && hbmViewSource.includes('aria-expanded="${hasData}"') && hbmViewSource.includes('<div class="hbm-view-content"${hasData ? "" : " hidden"}>') && !appSource.includes("els.hbmTimelinePanel.hidden = true"), "HBM section keeps its title visible, defaults missing-data content to collapsed, and explains capture absence when expanded"],
  [traceViewSource.includes("collapsedProcessIds") && traceViewSource.includes("data-trace-process-toggle") && traceViewSource.includes("timeline-section-toggle") && appCss.includes('.timeline-section-toggle[aria-expanded="false"]'), "Trace process groups and HBM expose consistent independent expand/collapse controls"],
  [!["architectureStatus", "reportDimension", "graphCount"].some((id) => indexHtml.includes(`id="${id}"`)), "architecture status and Inspector chip rows are absent"],
  [appSource.includes("buildRepeatInstanceMetrics(traceDocument, timelineDocument)") && appSource.includes("layerTimingTotals(timelineDocument, false)") && appSource.includes("traceTotals.size >= timelineTotals.size") && appSource.includes("cluster.instanceMetrics") && appSource.includes("onRepeatInstanceChange"), "repeated-layer dots use the best available raw-Trace or normalized-Timeline heat and retain direct selection"],
  [appSource.includes('layerReferenceKeys') && appSource.includes('layerChildren') && appSource.includes('expandOperatorTree(OPERATOR_TREE)') && appSource.includes('performanceBadgeStyle(report.timeSharePct)') && appSource.includes('performanceBadgeStyle(value, heatValues)') && appSource.includes('Array.isArray(overrideChildren)') && appSource.includes('roots.map((rawNode) => toNode(rawNode))'), "Operator List preserves referenced decoder children, safely adapts tree arrays, and uses Turbo heat badges in both tree and Inspector rows"],
  [appSource.includes("renderLayerSelector") && appSource.includes("data-layer-selector") && appSource.includes('option value=""') && appSource.includes('allLayers: "All Layers"') && appSource.includes('allLayers: "全部层"') && appSource.includes('selector.value === ""') && appSource.includes("state.selectedLayerIndex = null") && appSource.includes("candidate?.backendNodeId === layerBackendNodeId") && appSource.includes("repeatNodeId: layerRepeatNodeId") && appSource.includes("state.repeatInstanceSelections.set(selector.dataset.layerSelector") && appCss.includes(".operator-layer-select"), "Operator List resolves the repeated architecture item by backend identity and offers aggregate All Layers before synchronized concrete Layer choices"],
  [indexHtml.includes('data-operator-tab="summary"') && indexHtml.includes('data-operator-tab="sequence"') && indexHtml.includes("report-tab-control architecture-view-tabs") && indexHtml.includes("inspector-operator-tabs tab-control report-tab-control") && /\.inspector-operator-tabs\s*\{[^}]*align-self:\s*center/s.test(appCss) && !/\.inspector-operator-tabs\s*\{[^}]*width:\s*100%/s.test(appCss) && !/\.inspector-operator-tabs \.tab-control-item\s*\{[^}]*flex:/s.test(appCss), "all report tabs share one compact report-tab-control contract and Inspector tabs keep intrinsic width centered in the Inspector"],
  [appSource.includes('inspectorOperatorTab: "summary"') && appSource.includes("traceEventsForInspector") && appSource.includes("event.streamSequence") && appSource.includes("data-trace-source-index") && appSource.includes('setSelectedEvent(traceEvent, { notify: false })') && appSource.includes("currentRangeContainsEvent") && appSource.includes('operatorSummary: "算子汇总"') && appSource.includes('operatorSequence: "算子序列"') && !indexHtml.includes('class="section-title" data-i18n="operators"') && appCss.includes(".operator-sequence-number"), "Inspector uses self-describing Operator Summary and Operator Sequence tabs without a redundant section title or list narrowing"],
  [indexHtml.includes('id="operatorEventTooltip"') && indexHtml.includes("pto-model-graphviz-hover operator-event-tooltip") && appSource.includes("operatorTooltipHtml") && appSource.includes("operatorTooltipFields") && appSource.includes('["sequence", "name", "stream", "duration", "type", "shape", "dtype", "semantic"]') && appSource.includes("architectureTooltipHtml") && appSource.includes("renderEvidence: architectureTooltipHtml") && appSource.includes("backendNodeId: nodeId") && appSource.includes("events.map(eventDetail)") && appSource.includes("details.map((detail) => detail.shape)") && appSource.includes("details.map((detail) => detail.dtype)") && appSource.includes("operator-tooltip-field__label") && !appSource.includes("pto-model-graphviz-hover-chips\">${chips}") && appSource.includes("operator-stream-tag") && !appSource.includes("operator-sequence-meta") && appSource.includes("clearOperatorEventSelection") && appSource.includes("syncTraceSelection()") && appSource.includes("clearTimeSelection") && appCss.includes(".operator-stream-tag") && appCss.includes(".operator-tooltip-fields"), "operator-list and architecture-node hover details share the same field set, including layer-scoped Stream, duration, type, Shape, Dtype, and semantic data"],
  [appSource.includes("isAggregateReport") && appSource.includes("aggregateTimeShareHint") && appSource.includes('performance-value-badge${aggregate ? " is-aggregate" : ""}') && appCss.includes(".performance-value-badge.is-aggregate") && appCss.includes("cursor: help"), "aggregate total-time badges use a neutral treatment and explain their non-severity meaning on hover"],
  [graph.nodes.filter((node) => node.metricBadge).every((node) => !/%/.test(String(node.typeLabel || ''))) && modelGraphPatternSource.includes("const x = -node.width / 2 + 10 + repeatWidth"), "performance percentages use left badges and never leak into folded/type subtitles"],
  [modelGraphPatternSource.includes('estimateTextWidth(metric, 44, 72) + 4') && modelGraphPatternCss.includes('.pto-model-graphviz-metric-badge') && modelGraphPatternCss.includes('fill: #0A0A0A') && modelGraphPatternCss.includes('.pto-model-graphviz-metric-badge-text') && modelGraphPatternCss.includes('fill: #FFFFFF') && modelGraphPatternCss.includes('.pto-model-graphviz-layer-step-bg') && modelGraphPatternCss.includes('stroke-width: 0'), "model metric badges stay widened black/white across themes and Layer navigation buttons remain borderless"],
  [modelGraphPatternSource.includes('cluster.x + cluster.width - EXPAND_BUTTON_EDGE_GAP - EXPAND_BUTTON_RADIUS') && modelGraphPatternSource.includes('cluster.y + EXPAND_BUTTON_EDGE_GAP + EXPAND_BUTTON_RADIUS') && modelGraphPatternSource.includes('r: EXPAND_BUTTON_RADIUS') && modelGraphPatternSource.includes('d: `M ${toggleX - 5} ${toggleY} H ${toggleX + 5}`'), "expanded-cluster fold controls match collapsed-node expand control geometry and glyph sizing"],
  [architectureDataSource.includes("metadataForGraphItem") && appSource.includes("selectArchitectureItem") && !appSource.includes("architectureMetadataFacts"), "source-only architecture items remain selectable without an Inspector Evidence section or Trace binding"],
  [architectureDataSource.includes('structuralRoot: structuralShellIds.has(item.id)') && modelGraphPatternSource.includes("cluster.structuralRoot ? ' is-structural-root' : ''") && modelGraphPatternCss.includes('.pto-model-graphviz-cluster.is-structural-root') && !modelGraphPatternCss.includes("data-cluster-id='source/qwen7b'"), "structural source shell chains hide their cosmetic frames through a model-agnostic contract"],
  [sourceArchitectureCluster?.structuralRoot === true, "the projected Source architecture root is structural and does not render a redundant outer frame"],
  [appSource.includes("const METRIC_DEFINITIONS =") && ["wall_ms", "busy_union_ms", "kernel_sum_ms", "total_cost_ms", "time share", "operators", "HBM estimate", "MFU INT8", "MFU BF16"].every((label) => appSource.includes(label)) && appSource.includes("metrics_report.md · four-dimensional base metrics") && appSource.includes("metrics_report.md · 四维基础指标") && appSource.includes("UI JSON report data contract"), "all core and supporting Inspector metric titles have documented tooltip definitions and sources"],
  [indexHtml.includes('<html lang="zh-CN" data-theme="dark">') && indexHtml.includes('dsv32-report-language') && appSource.includes('document.documentElement.lang.startsWith("zh") ? "zh" : "en"'), "report defaults to Chinese while preserving an explicitly saved Chinese or English preference"],
  [indexHtml.includes('id="reportInfoToggle"') && indexHtml.includes('id="reportInfoPanel"') && appSource.includes("function reportProvenance()") && appSource.includes("generation_provenance?.extractor_model") && appSource.includes("function renderReportInfo()") && appSource.includes("function setReportInfoExpanded(") && appSource.includes("trigger === els.reportInfoToggle && !els.reportInfoPanel?.hidden") && appSource.includes("trigger !== els.reportInfoToggle") && !appSource.includes('mockData: "Mock 元数据"') && !appSource.includes('mockData: "Mock metadata"') && appCss.includes(".report-info-panel") && appCss.includes(".source-report-ide > .pto-ide-frame__topbar") && appCss.includes("z-index: 220") && appCss.includes(".report-info-toggle .pto-ide-frame__window-icon") && appCss.includes("opacity: 1"), "top-bar Info control is visibly interactive, suppresses its tooltip while open, and exposes localized report provenance above report content"],
  [!requiresProvenance || (provenanceSkills.length > 0 && Boolean(provenanceModelSource) && Boolean(provenanceExtractorModel)), "versioned handoff provides pipeline skill, model-source, and extractor-model provenance metadata"],
  [appCss.includes("min-height: 40px") && appCss.includes("height: 40px") && appCss.includes(".report-field-tooltip") && appCss.includes("var(--surface-3)") && appCss.includes("var(--radius-md)"), "pane headers and shared tooltips follow the design-system size and panel tokens"],
  [appCss.includes('width: max-content') && appCss.includes('max-width: min(320px, calc(100vw - 16px))'), "short shared tooltips shrink to content while long explanations remain viewport-clamped"],
  [appCss.includes('.metric-tile') && appCss.includes('border: 0') && appCss.includes('background: var(--surface-2)') && appCss.includes('.report-root-split.pto-ide-frame__split[data-split-direction="vertical"]') && appCss.includes('padding: 0 0 var(--space-2) var(--space-2)') && appCss.includes('#reportBottomDock') && appCss.includes('margin-right: var(--space-2)'), "Inspector cards are borderless subtle surfaces and workbench panes retain non-duplicated outer spacing"],
  [appCss.includes('.core-metric-grid .metric-tile') && appCss.includes('.core-metric-grid .metric-tile--primary') && appCss.includes('.core-metric-grid .metric-value') && /\.metric-formula\s*\{[^}]*font-size:\s*11px/s.test(appCss) && appCss.includes('.metric-primary-badge') && appCss.includes('background: var(--surface-3)') && appCss.includes('grid-template-columns: repeat(2, minmax(0, 1fr))'), "wall_ms keeps a neutral primary marker, all four core values use a readable two-column grid, and calculations use subordinate typography"],
  [appSource.includes('function coreMetricCalculation(') && appSource.includes('details.last_end_ms') && appSource.includes('details.first_start_ms') && appSource.includes('merged_interval_count') && appSource.includes('kernel_count') && appSource.includes('label === "wall_ms" ? " metric-tile--primary"') && reportDataSource.includes('coreMetricDetails'), "Inspector renders actual calculation operands for every core metric and marks wall_ms as the primary metric"],
  [appSource.includes('label === "time share" ? " metric-tile--full"') && appCss.includes('#metricGrid') && appCss.includes('#metricGrid .metric-tile--full') && appCss.includes('grid-template-columns: max-content minmax(80px, 1fr) max-content') && appCss.includes('grid-column: 1 / -1') && appCss.includes('min-height: 56px') && appCss.includes('#metricGrid .metric-tile--full .metric-bar') && appCss.includes('#metricGrid .metric-tile--full .metric-value'), "supporting metrics use one inline label-axis-value time-share row followed by four equal cards"],
  [appCss.includes('.report-inspector-section') && !appCss.includes('border-bottom: 1px solid var(--inspector-section-divider)'), "Inspector sections use spacing and cards without divider lines"],
  [appCss.includes('.source-report-ide [data-ide-pane="architecture"] > .architecture-view-header') && appCss.includes('height: 56px') && appCss.includes('padding: 10px') && appCss.includes(':root[data-theme="light"] .raw-trace-process-row') && appCss.includes('background: transparent') && appCss.includes(':root[data-theme="light"] .raw-trace-label.is-process'), "architecture tabs retain vertical breathing room and light Trace group headers avoid gray fills"],
  [appCss.includes('.performance-value-badge') && appCss.includes('background: var(--performance-badge-fill') && appCss.includes('.node-name') && appCss.includes('font: var(--text-body)') && appCss.includes('color: var(--foreground)'), "Operator names use primary body text and right-side metrics use filled heat badges"],
  [appTypographyHasOnlyFormulaException(appCss) && [swimlanePatternCss, timeSelectionPatternCss, modelGraphPatternCss].every(hasNoExplicitSub12FontSize) && hbmViewSource.includes('context.font = "12px') && swimlanePatternSource.includes('const font = `600 10px') && modelGraphPatternSource.includes('Math.max(12, Math.min(18, value))'), "visible typography keeps a 12px minimum except the subordinate 11px metric calculation and 10px TraceView event labels"],
  [reportDataSource.includes("reportsForLayer") && reportDataSource.includes("eventLayerIndex") && reportDataSource.includes("isLayerScoped") && !reportDataSource.includes("graphMetricShort") && architectureDataSource.includes("metricBadge: hasPerformanceBadge ? report.metricShort : undefined") && architectureDataSource.includes("timeSharePct: Number.isFinite(Number(report?.timeSharePct))") && !architectureDataSource.includes("graphMetricShort") && appSource.includes("const nodeMetric = report?.metricShort") && appSource.includes('const metricUnit = "%"') && architectureDataSource.includes("correspondingLayerItemForIndex") && architectureDataSource.includes("relativePath") && architectureDataSource.includes("template.instanceIndices.includes(Number(selectedLayerIndex))") && appSource.includes("activeReports()") && appSource.includes("alignSelectedNodeToLayer()") && appSource.includes("!Number.isInteger(layerIndex) || !state.selectedNodeId") && appSource.includes("correspondingItem.backendNodeId") && appSource.includes("not permission to jump to another node or cancel the selection") && appSource.includes("selectedLayerIndex") && traceViewSource.includes("matchesSelection"), "selected Layer context preserves operator identity while graph badges and heat use the layer time-share percentage; absolute kernel time remains Inspector-only"],
  [appCss.includes('[data-trace-action="focus"] svg') && appCss.includes("width: 16px") && appCss.includes("stroke-width: 1.5"), "Trace focus icon uses the approved visible size and 1.5px stroke"],
  [!/\stitle=["']/.test(indexHtml), "static controls use the shared tooltip system instead of native title tooltips"],
  [hbmData.schema_version === "1.0" && hbmBandwidthPoints.every((point) => Array.isArray(point) && point.length >= 3 && point.slice(0, 3).every(Number.isFinite)) && hbmOccupancyPoints.every((point) => Array.isArray(point) && point.length >= 2 && point.slice(0, 2).every(Number.isFinite)), "HBM sampled series has valid finite points"],
  [!/(?:src|href)=["'](?:https?:)?\/\//i.test(indexHtml), "report has no network runtime dependency"],
];

const failed = assertions.filter(([condition]) => !condition);
for (const [condition, label] of assertions) {
  console[condition ? "log" : "error"](`${condition ? "OK  " : "FAIL"} ${label}`);
}
if (failed.length) process.exitCode = 1;
else console.log(`OK   ${runtimeFiles.length} runtime files and ${rawTraceEvents.length} raw TraceView events resolve in ${reportRoot}`);
if (!templateHashesOk) process.exitCode = 1;
