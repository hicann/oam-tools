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

const repoIndex = process.argv.indexOf("--repo");
const repoRoot = resolve(repoIndex >= 0 && process.argv[repoIndex + 1]
  ? process.argv[repoIndex + 1]
  : ".");
const reportRoot = resolve(repoRoot, "report");
const { config: runtimeConfig } = await readRuntimeConfig(reportRoot);
const [adapterSource, graphSource] = await Promise.all([
  readFile(resolve(reportRoot, "architecture-data.js"), "utf8"),
  readFile(resolve(reportRoot, "outputs/model_architecture_graph.json"), "utf8"),
]);
const graph = JSON.parse(graphSource);
const sandbox = { window: {} };
vm.runInNewContext(adapterSource, sandbox, { filename: "architecture-data.js" });
const api = sandbox.window.DeepSeekArchitectureData;
const defaultCollapsed = api.defaultCollapsedIds(graph);
const failures = [];
let testedFanOut = 0;
let testedFanIn = 0;
let testedParallelRows = 0;

function assert(condition, message) {
  if (!condition) failures.push(message);
  console[condition ? "log" : "error"](`${condition ? "OK  " : "FAIL"} ${message}`);
}

// ── Build adjacency for reachability checks ──
const activationEdges = (graph.edges || []).filter((e) => e.semanticEdgeType === "activation");
const adj = new Map();
const revAdj = new Map();
for (const e of activationEdges) {
  if (!adj.has(e.source)) adj.set(e.source, []);
  adj.get(e.source).push(e.target);
  if (!revAdj.has(e.target)) revAdj.set(e.target, []);
  revAdj.get(e.target).push(e.source);
}
const dependencyAdj = new Map();
for (const edge of graph.edges || []) {
  if (!dependencyAdj.has(edge.source)) dependencyAdj.set(edge.source, []);
  dependencyAdj.get(edge.source).push(edge.target);
}

function reachable(from, to, visited = new Set()) {
  if (from === to) return true;
  visited.add(from);
  for (const next of dependencyAdj.get(from) || []) {
    if (!visited.has(next) && reachable(next, to, visited)) return true;
  }
  return false;
}

function shortName(id) {
  const parts = id.split("/");
  return parts.slice(-2).join("/");
}

// ── Phase 1: Discover fan-out patterns ──
const fanOutSources = [];
for (const [source, targets] of adj) {
  if (targets.length > 1) fanOutSources.push({ source, branches: targets });
}

// ── Phase 2: Discover fan-in patterns ──
const fanInTargets = [];
for (const [target, sources] of revAdj) {
  if (sources.length > 1) fanInTargets.push({ target, sources });
}

// ── Phase 3: Extract layoutRows (if present) ──
const allLayoutItems = [...(graph.nodes || []), ...(graph.clusters || [])];
const layoutRowsEntries = [];
for (const item of allLayoutItems) {
  if (Array.isArray(item.layoutRows) && item.layoutRows.length > 0) {
    layoutRowsEntries.push({ itemId: item.id, rows: item.layoutRows });
  }
}
// Also check root items in the tree
function collectLayoutRows(rootItems) {
  for (const item of rootItems || []) {
    if (Array.isArray(item.layoutRows) && item.layoutRows.length > 0) {
      layoutRowsEntries.push({ itemId: item.id, rows: item.layoutRows });
    }
    if (Array.isArray(item.children)) collectLayoutRows(item.children);
  }
}
collectLayoutRows(graph.roots);

console.log(`Graph: ${(graph.roots || []).map((r) => r.id?.split("/").pop()).join(", ")}`);
console.log(`  Activation edges: ${activationEdges.length}`);
console.log(`  Fan-out sources: ${fanOutSources.length}`);
console.log(`  Fan-in targets: ${fanInTargets.length}`);
console.log(`  layoutRows entries: ${layoutRowsEntries.length}`);
console.log();

// ── Assertions ──

// A1: Fan-out — all branches preserved after collapse
for (const { source, branches } of fanOutSources) {
  const sourceEdges = (graph.edges || []).filter((e) => e.source === source && e.semanticEdgeType === "activation");
  const edgeIds = sourceEdges.map((e) => e.id);
  testedFanOut += 1;

  // Edge IDs must be unique
  assert(new Set(edgeIds).size === edgeIds.length,
    `fan-out ${shortName(source)}: all ${edgeIds.length} outgoing edges have unique IDs`);

  // After default collapse, each edge must resolve to a visible endpoint
  const view = api.createArchitectureView(graph, {}, defaultCollapsed);
  const projected = view.edges.filter((e) => edgeIds.includes(e.id));
  assert(projected.length === edgeIds.length,
    `fan-out ${shortName(source)}: all ${edgeIds.length} edges survive default collapse (${projected.length}/${edgeIds.length})`);

  const sourceEdgeById = new Map(sourceEdges.map((edge) => [edge.id, edge]));
  for (const pe of projected) {
    const original = sourceEdgeById.get(pe.id);
    assert(pe.sourceItemId === original?.source && pe.targetItemId === original?.target,
      `fan-out ${shortName(source)}: edge ${pe.id} preserves both original item endpoints`);
  }
}

// A2: Fan-in — all source branches reach the join
for (const { target, sources } of fanInTargets) {
  testedFanIn += 1;
  const targetEdges = (graph.edges || []).filter((e) => e.target === target && e.semanticEdgeType === "activation");
  const edgeIds = targetEdges.map((e) => e.id);
  assert(new Set(edgeIds).size === edgeIds.length,
    `fan-in ${shortName(target)}: all ${edgeIds.length} incoming edges have unique IDs`);

  // After default collapse
  const view = api.createArchitectureView(graph, {}, defaultCollapsed);
  const projected = view.edges.filter((e) => edgeIds.includes(e.id));
  assert(projected.length === edgeIds.length,
    `fan-in ${shortName(target)}: all ${edgeIds.length} edges survive default collapse (${projected.length}/${edgeIds.length})`);

  const targetEdgeById = new Map(targetEdges.map((edge) => [edge.id, edge]));
  for (const pe of projected) {
    const original = targetEdgeById.get(pe.id);
    assert(pe.sourceItemId === original?.source && pe.targetItemId === original?.target,
      `fan-in ${shortName(target)}: edge ${pe.id} preserves both original item endpoints`);
  }
}

// A3: layoutRows — same row nodes must not have data dependencies
for (const { itemId, rows } of layoutRowsEntries) {
  for (const [rowIdx, row] of rows.entries()) {
    const rowIds = Array.isArray(row) ? row : [];
    if (rowIds.length < 2) continue;
    testedParallelRows += 1;
    for (let i = 0; i < rowIds.length; i++) {
      for (let j = i + 1; j < rowIds.length; j++) {
        const a = rowIds[i], b = rowIds[j];
        assert(!reachable(a, b, new Set()) && !reachable(b, a, new Set()),
          `layoutRows ${shortName(itemId)} row[${rowIdx}]: ${shortName(a)} and ${shortName(b)} are independent`);
      }
    }
  }
}

// ── Summary ──
console.log();
const summary = [
  `fan-out sources tested: ${testedFanOut}`,
  `fan-in targets tested: ${testedFanIn}`,
  `parallel rows tested: ${testedParallelRows}`,
];
console.log(summary.join(" | "));

if (testedFanOut === 0 && testedFanIn === 0 && testedParallelRows === 0) {
  console.log("NOTE: graph has no fan-out, fan-in, or layoutRows patterns to validate.");
}

const expected = runtimeConfig.capabilities?.expectedGraphFeatures || {};
if (Number.isFinite(Number(expected.fanOutMin))) {
  assert(testedFanOut >= Number(expected.fanOutMin), `declared fan-out minimum ${expected.fanOutMin} is satisfied`);
}
if (Number.isFinite(Number(expected.fanInMin))) {
  assert(testedFanIn >= Number(expected.fanInMin), `declared fan-in minimum ${expected.fanInMin} is satisfied`);
}
if (Number.isFinite(Number(expected.parallelRowsMin))) {
  assert(testedParallelRows >= Number(expected.parallelRowsMin), `declared parallel-row minimum ${expected.parallelRowsMin} is satisfied`);
}
if (expected.residualEdgesMin != null) {
  const residualCount = (graph.edges || []).filter((edge) => edge.semanticEdgeType === "residual").length;
  assert(residualCount >= Number(expected.residualEdgesMin), `declared residual-edge minimum ${expected.residualEdgesMin} is satisfied`);
}

if (failures.length) {
  console.error(`\n${failures.length} FAILURE(S):`);
  failures.forEach((m) => console.error(`  - ${m}`));
  process.exitCode = 1;
} else {
  console.log("OK   all fan-out / fan-in / layoutRows assertions passed");
}
