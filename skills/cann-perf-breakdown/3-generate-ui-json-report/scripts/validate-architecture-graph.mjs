#!/usr/bin/env node
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

import fs from "node:fs";
import path from "node:path";

const errors = [];
const warnings = [];
const fail = (message) => errors.push(message);
const warn = (message) => warnings.push(message);
const args = process.argv.slice(2);
const allowCycles = args.includes("--allow-cycles");
const requireSemanticPorts = args.includes("--require-semantic-port-policy");
const sourceRootFlag = args.indexOf("--source-root");
const sourceRootId = sourceRootFlag >= 0 ? args[sourceRootFlag + 1] : "section/source_architecture";
const valueFlags = new Set(sourceRootFlag >= 0 ? [sourceRootFlag + 1] : []);
const inputArg = args.find((arg, index) => !arg.startsWith("--") && !valueFlags.has(index));

if (!inputArg || (sourceRootFlag >= 0 && !sourceRootId)) {
  console.error("Usage: validate-architecture-graph.mjs <graph.json> [--source-root <id>] [--require-semantic-port-policy] [--allow-cycles]");
  process.exit(2);
}

let graph;
try {
  graph = JSON.parse(fs.readFileSync(path.resolve(inputArg), "utf8"));
} catch (error) {
  console.error(`ERROR: cannot read JSON: ${error.message}`);
  process.exit(2);
}

if (graph.schema_version !== "model_architecture_graph.v1") {
  fail(`schema_version must be model_architecture_graph.v1, got ${graph.schema_version || "missing"}`);
}
if (!Array.isArray(graph.roots) || graph.roots.length === 0) fail("roots must be a non-empty array");
if (!Array.isArray(graph.edges)) fail("edges must be an array");

const items = new Map();
function visit(item, parentId = "") {
  if (!item || typeof item !== "object") {
    fail(`invalid child under ${parentId || "roots"}`);
    return;
  }
  if (typeof item.id !== "string" || !item.id.trim()) {
    fail(`item under ${parentId || "roots"} has no stable id`);
    return;
  }
  if (items.has(item.id)) {
    fail(`duplicate item id: ${item.id}`);
    return;
  }
  item._parentId = parentId || null;
  items.set(item.id, item);
  if (!Array.isArray(item.children)) fail(`${item.id}.children must be an array`);
  if (item.repeatCount != null) {
    if (!Number.isInteger(item.repeatCount) || item.repeatCount < 1) fail(`${item.id}.repeatCount must be a positive integer`);
    if (Array.isArray(item.instanceIndices) && item.instanceIndices.length !== item.repeatCount) {
      fail(`${item.id}.instanceIndices length does not match repeatCount`);
    }
  }
  (item.children || []).forEach((child) => visit(child, item.id));
}
(graph.roots || []).forEach((root) => visit(root));

const sourceRoot = (graph.roots || []).find((root) => root.id === sourceRootId);
if (!sourceRoot) fail(`source root not found: ${sourceRootId}`);
const sourceIds = new Set();
(function collect(item) {
  if (!item?.id) return;
  sourceIds.add(item.id);
  (item.children || []).forEach(collect);
})(sourceRoot);

const positions = new Map([...(graph.nodes || []), ...(graph.clusters || [])].map((item) => [item.id, item]));
const center = (item) => item ? { x: Number(item.x) + Number(item.width || 0) / 2, y: Number(item.y) + Number(item.height || 0) / 2 } : null;
const allowedEdgeTypes = new Set(["activation", "communication", "parameter", "state", "control", "residual"]);
const tensorRequiredEdgeTypes = new Set(["activation", "residual"]);
const edgeIds = new Set();
const adjacency = new Map([...sourceIds].map((id) => [id, []]));
let scopedEdgeCount = 0;
let verticalPolicyCount = 0;
let sideInputPolicyCount = 0;
let crossInvocationPolicyCount = 0;

for (const [index, edge] of (graph.edges || []).entries()) {
  const edgeId = edge?.id || `edge[${index}]`;
  if (edgeIds.has(edgeId)) fail(`duplicate edge id: ${edgeId}`);
  edgeIds.add(edgeId);
  if (!items.has(edge?.source)) fail(`${edgeId} has unresolved source: ${edge?.source}`);
  if (!items.has(edge?.target)) fail(`${edgeId} has unresolved target: ${edge?.target}`);
  if (edge?.source === edge?.target) fail(`${edgeId} is a self-edge`);
  if (!allowedEdgeTypes.has(edge?.semanticEdgeType)) fail(`${edgeId} has unsupported semanticEdgeType: ${edge?.semanticEdgeType}`);
  if (!edge?.tensor || typeof edge.tensor !== "object") fail(`${edgeId} has no tensor metadata`);

  // Tensor field checks for activation and residual edges — warnings (quality),
  // not hard errors (layout correctness). Missing tensor metadata degrades
  // informational value but does not affect node placement or edge routing.
  if (tensorRequiredEdgeTypes.has(edge.semanticEdgeType)) {
    const t = edge.tensor;
    if (!t.name || typeof t.name !== "string" || !t.name.trim()) {
      warn(`${edgeId} tensor.name is missing for ${edge.semanticEdgeType} edge`);
    }
    if (!t.shape || typeof t.shape !== "string" || !t.shape.trim()) {
      warn(`${edgeId} tensor.shape is missing for ${edge.semanticEdgeType} edge`);
    }
    if (!t.dtype || typeof t.dtype !== "string" || !t.dtype.trim()) {
      warn(`${edgeId} tensor.dtype is missing for ${edge.semanticEdgeType} edge`);
    }
  }

  // Cross-field: tensor.role (if present) must be compatible with semanticEdgeType.
  // dataState=source_only on activation edges is valid (source-analysed activations like qwen7b).
  const tensorRoleMap = { parameter: "parameter", state: "state", weight: "parameter", bias: "parameter" };
  const expectedType = tensorRoleMap[edge?.tensor?.role];
  if (expectedType && edge.semanticEdgeType === "activation") {
    fail(`${edgeId} tensor.role is "${edge.tensor.role}" but semanticEdgeType is activation (expected "${expectedType}")`);
  }

  // Residual edges must be dashed
  if (edge.semanticEdgeType === "residual") {
    if (edge.dashed !== true) {
      fail(`${edgeId} is a residual edge but dashed is not true (got ${JSON.stringify(edge.dashed)})`);
    }
    // Cross-invocation residuals must declare instance semantics
    if (edge.crossInvocation === true) {
      if (!Number.isInteger(edge.crossStep) && !Array.isArray(edge.crossSteps)) {
        fail(`${edgeId} has crossInvocation=true but lacks crossStep or crossSteps to specify which invocations`);
      }
    }
  }

  if (!Array.isArray(edge?.provenance) || edge.provenance.length === 0) fail(`${edgeId} has no provenance`);
  if (!sourceIds.has(edge?.source) || !sourceIds.has(edge?.target)) continue;
  scopedEdgeCount += 1;

  // A cross-invocation carry connects one invocation of a folded template to the NEXT one, so
  // within the single drawn template it necessarily points backwards. That is the shape the
  // edge is required to declare (crossInvocation + crossStep above), and residuals get their
  // own outer-left lane rather than the forward vertical policy, so it is neither a reversed
  // edge nor an intra-template cycle. Excluding it from the adjacency graph and the port
  // policy keeps both checks meaningful for the edges they were written for: a same-invocation
  // edge pointing backwards is still an error.
  const carriesToNextInvocation = edge.crossInvocation === true;
  if (!carriesToNextInvocation) adjacency.get(edge.source)?.push(edge.target);

  if (requireSemanticPorts && !carriesToNextInvocation) {
    const source = center(positions.get(edge.source));
    const target = center(positions.get(edge.target));
    if (!source || !target) {
      fail(`${edgeId} cannot validate port policy without source and target positions`);
      continue;
    }
    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const sideInput = (Math.abs(dy) < 1 && Math.abs(dx) > 0)
      || (edge.semanticEdgeType === "parameter" && Math.abs(dx) > Math.abs(dy));
    if (sideInput) sideInputPolicyCount += 1;
    else {
      verticalPolicyCount += 1;
      if (dy <= 0) fail(`${edgeId} is not top-to-bottom (dy=${dy})`);
    }
  } else if (requireSemanticPorts) {
    crossInvocationPolicyCount += 1;
  }
}

for (const itemId of sourceIds) {
  const item = items.get(itemId);
  if (item?.synthetic !== true && item?.origin !== "backend_trace_extension"
    && (!Array.isArray(item?.sourceRefs) || item.sourceRefs.length === 0)) fail(`${itemId} has no sourceRefs`);
}

// ── ColorKey validation: check all items use known color keys ──
const KNOWN_COLOR_KEYS = new Set([
  // Semantic keys (resolved via alias to opv:*)
  "sem:embedding", "sem:norm", "sem:attention", "sem:position", "sem:rope",
  "sem:qknorm", "sem:linear", "sem:head", "sem:mlp", "sem:act",
  "sem:activation", "sem:gate", "sem:moe", "sem:comm",
  // Module-level keys (aliased to opv:*)
  "module:model", "module:decoder", "module:mhc", "module:ffn", "module:mtp",
  // Resolved opv:* base colors
  "opv:act", "opv:attention", "opv:comm", "opv:decoder", "opv:embedding",
  "opv:gate", "opv:head", "opv:linear", "opv:mlp", "opv:model",
  "opv:moe", "opv:norm", "opv:op", "opv:rope",
]);
let unknownColorKeyCount = 0;
for (const [id, item] of items) {
  const ck = item.colorKey;
  if (ck && !KNOWN_COLOR_KEYS.has(ck)) {
    fail(`${id} has unknown colorKey: "${ck}"`);
    unknownColorKeyCount++;
  }
}
if (unknownColorKeyCount === 0) {
  console.log(`OK: all items use known colorKeys`);
}

if (!allowCycles) {
  // Build ancestor map for template-scope awareness in cycle messages
  const ancestorChain = new Map();
  for (const [id, item] of items) {
    const chain = [];
    let current = item;
    while (current) {
      if (current.repeatCount != null && current.repeatCount > 1) chain.push(current.id);
      current = items.get(current._parentId);
    }
    ancestorChain.set(id, chain);
  }

  const color = new Map();
  const stack = [];
  function findCycle(nodeId) {
    color.set(nodeId, 1);
    stack.push(nodeId);
    for (const target of adjacency.get(nodeId) || []) {
      if (color.get(target) === 1) {
        const cyclePath = [...stack.slice(stack.indexOf(target)), target];
        // Identify folded templates involved in the cycle
        const templates = new Set();
        for (const nid of cyclePath) {
          (ancestorChain.get(nid) || []).forEach((tid) => templates.add(tid));
        }
        const tmplNote = templates.size > 0
          ? ` [involves folded template(s): ${[...templates].join(", ")}]`
          : "";
        return { cycle: cyclePath, tmplNote };
      }
      if (!color.has(target)) {
        const result = findCycle(target);
        if (result) return result;
      }
    }
    stack.pop();
    color.set(nodeId, 2);
    return null;
  }
  for (const nodeId of sourceIds) {
    if (color.has(nodeId)) continue;
    const result = findCycle(nodeId);
    if (result) {
      fail(`dataflow cycle detected: ${result.cycle.join(" -> ")}${result.tmplNote}`);
      break;
    }
  }
}

if (errors.length) {
  errors.forEach((message) => console.error(`ERROR: ${message}`));
}
if (warnings.length) {
  warnings.forEach((message) => console.error(`WARNING: ${message}`));
}
if (errors.length) {
  process.exit(1);
}
console.log(`OK: schema=${graph.schema_version}, ${items.size} total items, ${sourceIds.size} source-scope items, ${scopedEdgeCount} source-scope edges, ${graph.roots.length} roots`);
if (warnings.length) console.log(`WARNINGS: ${warnings.length} quality issues (non-blocking)`);
if (requireSemanticPorts) console.log(`OK: semantic port policy resolves ${verticalPolicyCount} bottom-to-top edges, ${sideInputPolicyCount} declared side input(s) and ${crossInvocationPolicyCount} declared cross-invocation carry/carries`);
