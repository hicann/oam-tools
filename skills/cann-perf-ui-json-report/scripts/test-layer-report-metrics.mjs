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
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import vm from "node:vm";
import { readRuntimeConfig } from "./report-runtime-config.mjs";

const repoFlagIndex = process.argv.indexOf("--repo");
const repoArgument = repoFlagIndex >= 0 ? process.argv[repoFlagIndex + 1] : null;
if (!repoArgument) throw new Error("Pass --repo <report-repo>");
const repoRoot = resolve(repoArgument);

const reportRoot = resolve(repoRoot, "report");
const { config: runtimeConfig } = await readRuntimeConfig(reportRoot);
const readConfiguredJson = (key) => readFile(resolve(reportRoot, runtimeConfig[key]), "utf8").then(JSON.parse);

const [analysis, performance, timeline, architecture, reportDataSource, architectureDataSource, indexHtml] = await Promise.all([
  readConfiguredJson("analysis"),
  readConfiguredJson("performance"),
  readConfiguredJson("timeline"),
  readConfiguredJson("architecture"),
  readFile(resolve(reportRoot, "report-data.js"), "utf8"),
  readFile(resolve(reportRoot, "architecture-data.js"), "utf8"),
  readFile(resolve(reportRoot, "index.html"), "utf8"),
]);

const context = vm.createContext({ window: {} });
vm.runInContext(reportDataSource, context, { filename: "report-data.js" });
vm.runInContext(architectureDataSource, context, { filename: "architecture-data.js" });
const model = context.window.DeepSeekReportData.createReportModel(analysis, performance, timeline);
const events = Array.isArray(timeline.events) ? timeline.events : [];

const performanceById = new Map();
const collectPerformance = (items) => {
  (Array.isArray(items) ? items : Object.values(items || {})).forEach((item) => {
    if (!item || typeof item !== "object") return;
    if (item.node_id) performanceById.set(item.node_id, item);
    collectPerformance(item.children);
  });
};
collectPerformance(performance.modules);

const layerTemplates = Object.values(analysis.layer_structure || {})
  .filter((node) => node?.node_id && !/(mtp|runtime|auxiliary|scaffold)/i.test(`${node.node_id}/${node.name || ""}`))
  .map((node) => ({
    id: node.node_id,
    indices: (node.declared_instance_indices || node.instance_indices || []).map(Number).filter(Number.isInteger),
    observedIndices: (node.instance_indices || []).map(Number).filter(Number.isInteger),
  }));
if (!layerTemplates.length) {
  if (runtimeConfig.capabilities?.repeatedLayers === true) {
    throw new Error(`Report declares repeatedLayers but has no decoder layer templates in ${repoRoot}`);
  }
  console.log(`SKIP ${performance.model_id || analysis.model_id || "model"}: repeated-layer capability is not present`);
  process.exit(0);
}

const candidates = layerTemplates.map((template) => {
  const perf = performanceById.get(template.id);
  if (!perf) throw new Error(`No performance record for decoder template ${template.id}`);
  const indices = template.observedIndices;
  const includeDescendants = perf.metric_scope === "aggregate"
    || perf.metric_scope === "phase_aggregate"
    || perf.aggregate_kind
    || Array.isArray(perf.children);
  const owned = events.filter((event) => includeDescendants
    ? event.owner_node_id === perf.node_id || String(event.owner_node_id || "").startsWith(`${perf.node_id}/`)
    : event.owner_node_id === perf.node_id);
  const observed = indices.filter((index) => owned.some((event) => (
    event.layer_index != null && event.layer_index !== "" && Number(event.layer_index) === index
  )));
  const missing = indices.filter((index) => !observed.includes(index));
  if (missing.length) {
    throw new Error(`${template.id} has no layer-scoped Timeline events for ${missing.join(", ")}`);
  }
  return { template, perf, owned, observed };
});

const results = candidates.flatMap((candidate) => {
  const samplePositions = [0, Math.floor((candidate.observed.length - 1) / 2), candidate.observed.length - 1];
  const sampleLayers = [...new Set(samplePositions.map((position) => candidate.observed[position]))];
  return sampleLayers.map((layerIndex) => {
    const scopedEvents = candidate.owned.filter((event) => (
      event.layer_index != null && event.layer_index !== "" && Number(event.layer_index) === layerIndex
    ));
    const report = model.reportsForLayer(layerIndex)[candidate.perf.node_id];
    if (!report?.isLayerScoped || report.layerIndex !== layerIndex) {
      throw new Error(`Layer ${layerIndex} did not produce a layer-scoped report for ${candidate.perf.node_id}`);
    }
    const operatorValue = report.metrics.find(([label]) => label === "operators")?.[1];
    if (Number(String(operatorValue).replaceAll(",", "")) !== scopedEvents.length) {
      throw new Error(`Layer ${layerIndex} operators mismatch for ${candidate.perf.node_id}: report=${operatorValue}, events=${scopedEvents.length}, reportInstances=${JSON.stringify(report?.instanceIndices)}`);
    }
    const kernelSumValue = report.coreMetrics.find(([label]) => label === "kernel_sum_ms")?.[1];
    const reportKernelSumMs = Number(String(kernelSumValue).replace(" ms", "").replaceAll(",", ""));
    const expectedKernelSumMs = scopedEvents.reduce((sum, event) => sum + Number(event.duration_us || 0), 0) / 1000;
    if (!Number.isFinite(reportKernelSumMs) || Math.abs(reportKernelSumMs - expectedKernelSumMs) > 0.0011) {
      throw new Error(`Layer ${layerIndex} kernel_sum_ms mismatch: report=${reportKernelSumMs}, events=${expectedKernelSumMs}`);
    }
    const graphTimeSharePct = Number(String(report.metricShort).replace("%", "").replaceAll(",", ""));
    const expectedTimeSharePct = Number(performance.total_time_us) > 0
      ? expectedKernelSumMs * 1000 / Number(performance.total_time_us) * 100
      : NaN;
    if (!String(report.metricShort).endsWith("%") || !Number.isFinite(graphTimeSharePct) || Math.abs(graphTimeSharePct - expectedTimeSharePct) > 0.0051) {
      throw new Error(`Layer ${layerIndex} graph time-share mismatch: report=${report.metricShort}, events=${expectedTimeSharePct}%`);
    }
    return {
      templateId: candidate.template.id,
      layerIndex,
      operators: scopedEvents.length,
      kernelSumMs: reportKernelSumMs,
      timeSharePct: graphTimeSharePct,
    };
  });
});

if (indexHtml.includes('id="factList"') || />\s*Evidence\s*</i.test(indexHtml)) {
  throw new Error(`Inspector Evidence markup still exists in ${repoRoot}`);
}

const layerNavigation = context.window.DeepSeekArchitectureData.layerNavigationForGraph(architecture);
const architectureItems = new Map();
const collectArchitectureItem = (item) => {
  architectureItems.set(item.id, item);
  (item.children || []).forEach(collectArchitectureItem);
};
(architecture.roots || []).forEach(collectArchitectureItem);
layerTemplates.forEach((template) => {
  template.graphId = [...architectureItems.values()].find((item) => (
    item.id === template.id || item.backendNodeId === template.id
  ))?.id || template.id;
});
const layerTemplateGraphIds = new Set(layerTemplates.map((template) => template.graphId));
const templateBoundaryEdges = (architecture.edges || []).filter((edge) => (
  edge.semanticEdgeType === "activation"
  && (layerTemplateGraphIds.has(edge.source) || layerTemplateGraphIds.has(edge.target))
));
function hasExternalTemplatePath(templateId, direction) {
  const pending = [templateId];
  const visited = new Set(pending);
  while (pending.length) {
    const current = pending.pop();
    const adjacent = templateBoundaryEdges.filter((edge) => (
      direction === "incoming" ? edge.target === current : edge.source === current
    ));
    for (const edge of adjacent) {
      const nextId = direction === "incoming" ? edge.source : edge.target;
      if (!layerTemplateGraphIds.has(nextId)) return true;
      if (!visited.has(nextId)) {
        visited.add(nextId);
        pending.push(nextId);
      }
    }
  }
  return false;
}
const projectedArchitecture = context.window.DeepSeekArchitectureData.createArchitectureGraph(architecture, {});
const repeatedClusters = projectedArchitecture.clusters.filter((cluster) => cluster.repeat);
const repeatedIds = new Set(repeatedClusters.map((cluster) => cluster.id));
const clusterParents = new Map(projectedArchitecture.clusters.map((cluster) => [cluster.id, cluster.parent]));
const nestedRepeat = repeatedClusters.find((cluster) => {
  let parentId = cluster.parent;
  while (parentId) {
    if (repeatedIds.has(parentId)) return true;
    parentId = clusterParents.get(parentId);
  }
  return false;
});
if (nestedRepeat) throw new Error(`Nested visual layer pager remains at ${nestedRepeat.id}`);
if (!layerNavigation || !repeatedIds.has(layerNavigation.repeatNodeId)) {
  throw new Error(`Global layer navigation is missing from the projected architecture`);
}
const pagerHostItem = architectureItems.get(layerNavigation.repeatNodeId);
if (!Array.isArray(pagerHostItem?.instanceIndices) || pagerHostItem.instanceIndices.length < 1) {
  throw new Error(`Layer pager was promoted outside a repeated layer template: ${layerNavigation.repeatNodeId}`);
}
if (new Set(layerNavigation.instanceIndices).size !== layerNavigation.instanceIndices.length) {
  throw new Error(`Global layer navigation contains duplicate indices`);
}

for (const layerIndex of layerNavigation.instanceIndices) {
  const matchingTemplates = layerTemplates.filter((template) => template.indices.includes(layerIndex));
  if (matchingTemplates.length !== 1) {
    throw new Error(`Layer ${layerIndex} belongs to ${matchingTemplates.length} decoder templates; expected exactly one`);
  }
  const layerReports = model.reportsForLayer(layerIndex);
  const layerView = context.window.DeepSeekArchitectureData.createArchitectureView(
    architecture,
    layerReports,
    [],
    layerIndex,
  );
  layerView.nodes.filter((node) => node.metricBadge && node.metricBadge !== "–").forEach((node) => {
    if (!String(node.metricBadge).endsWith("%")) {
      throw new Error(`Layer ${layerIndex} graph badge is not a time-share percentage: ${node.id}=${node.metricBadge}`);
    }
    const backendNodeId = context.window.DeepSeekArchitectureData.graphToBackendNodeId(architecture, node.id);
    const report = layerReports[backendNodeId];
    if (!report || !Number.isFinite(Number(node.timeSharePct)) || Math.abs(Number(node.timeSharePct) - Number(report.timeSharePct)) > 1e-9) {
      throw new Error(`Layer ${layerIndex} graph heat value does not match report timeSharePct: ${node.id}=${node.timeSharePct}`);
    }
  });
  const visibleIds = new Set([
    ...layerView.nodes.map((node) => node.id),
    ...layerView.clusters.map((cluster) => cluster.id),
  ]);
  if (!visibleIds.has(matchingTemplates[0].graphId)) {
    throw new Error(`Layer ${layerIndex} did not render its template ${matchingTemplates[0].graphId}`);
  }
  const layerPagerHosts = [
    ...layerView.nodes.filter((node) => Number(node.repeatCount) > 1),
    ...layerView.clusters.filter((cluster) => cluster.repeat),
  ].map((item) => item.id);
  if (layerPagerHosts.length !== 1 || layerPagerHosts[0] !== matchingTemplates[0].graphId) {
    throw new Error(`Layer ${layerIndex} pager host mismatch: ${layerPagerHosts.join(", ") || "none"}; expected ${matchingTemplates[0].graphId}`);
  }
  const wrongTemplate = layerTemplates.find((template) => (
    template.graphId !== matchingTemplates[0].graphId && visibleIds.has(template.graphId)
  ));
  if (wrongTemplate) {
    throw new Error(`Layer ${layerIndex} also rendered inactive template ${wrongTemplate.graphId}`);
  }
  const activeTemplateId = matchingTemplates[0].graphId;
  const expectsIncomingBridge = hasExternalTemplatePath(activeTemplateId, "incoming");
  const expectsOutgoingBridge = hasExternalTemplatePath(activeTemplateId, "outgoing");
  if (expectsIncomingBridge || expectsOutgoingBridge) {
    const incomingBridge = layerView.edges.find((edge) => (
      edge.targetItemId === activeTemplateId
      && edge.projectedThroughLayerSelection === true
      && Array.isArray(edge.projectedFromEdgeIds)
      && edge.projectedFromEdgeIds.length > 0
    ));
    const outgoingBridge = layerView.edges.find((edge) => (
      edge.sourceItemId === activeTemplateId
      && edge.projectedThroughLayerSelection === true
      && Array.isArray(edge.projectedFromEdgeIds)
      && edge.projectedFromEdgeIds.length > 0
    ));
    if ((expectsIncomingBridge && !incomingBridge) || (expectsOutgoingBridge && !outgoingBridge)) {
      throw new Error(
        `Layer ${layerIndex} top-level flow is disconnected at ${activeTemplateId}: `
        + `incoming=${incomingBridge?.id || "none"}, outgoing=${outgoingBridge?.id || "none"}`,
      );
    }
    const projectedBridges = [incomingBridge, outgoingBridge].filter(Boolean);
    if (projectedBridges.some((edge) => (
      !visibleIds.has(edge.source) || !visibleIds.has(edge.target)
    ))) {
      throw new Error(`Layer ${layerIndex} selection bridge does not resolve to visible endpoints`);
    }
  }
}

const firstLayer = layerNavigation.instanceIndices[0];
const lastLayer = layerNavigation.instanceIndices.at(-1);
const firstTemplates = layerTemplates.filter((template) => template.indices.includes(firstLayer));
const lastTemplates = layerTemplates.filter((template) => template.indices.includes(lastLayer));
if (firstTemplates.length === 1 && lastTemplates.length === 1 && firstTemplates[0].graphId !== lastTemplates[0].graphId) {
  const sourcePrefix = `${firstTemplates[0].graphId}/`;
  const matchingSourceId = [...architectureItems.keys()].find((id) => {
    if (!id.startsWith(sourcePrefix)) return false;
    const relativePath = id.slice(firstTemplates[0].graphId.length);
    return architectureItems.has(`${lastTemplates[0].graphId}${relativePath}`);
  });
  if (!matchingSourceId) throw new Error(`No isomorphic operator path across layer templates`);
  const relativePath = matchingSourceId.slice(firstTemplates[0].graphId.length);
  const expectedTargetId = `${lastTemplates[0].graphId}${relativePath}`;
  const corresponding = context.window.DeepSeekArchitectureData.correspondingLayerItemForIndex(
    architecture,
    matchingSourceId,
    lastLayer,
  );
  if (corresponding?.id !== expectedTargetId) {
    throw new Error(`Layer operator selection jumped: ${matchingSourceId} -> ${corresponding?.id || "none"}, expected ${expectedTargetId}`);
  }
}

console.log(`OK ${performance.model_id} ${candidates.length} decoder template(s)`);
console.log(`  Layer navigation: ${layerNavigation.instanceIndices[0]}-${layerNavigation.instanceIndices.at(-1)} (${layerNavigation.instanceIndices.length} dots), nested pagers=0`);
results.forEach((result) => console.log(
  `  ${result.templateId} · Layer ${result.layerIndex}: operators=${result.operators}, kernel_sum_ms=${result.kernelSumMs}`,
));
