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
import { access, cp, mkdir, readdir, realpath, rename, rm, writeFile } from "node:fs/promises";
import { constants } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  configFromHandoff,
  findHandoff,
  normalizeLegacyConfig,
  readRuntimeConfig,
  serializeRuntimeConfig,
} from "./report-runtime-config.mjs";

const skillRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoFlagIndex = process.argv.indexOf("--repo");
const repoArgument = repoFlagIndex >= 0 ? process.argv[repoFlagIndex + 1] : null;
if (!repoArgument) throw new Error("Pass --repo <report-repo>");
const repoRoot = resolve(repoArgument);
const reportRoot = resolve(repoRoot, "report");
const templateRoot = resolve(skillRoot, "assets/report-template");
const checkOnly = process.argv.includes("--check");
const refreshTemplate = process.argv.includes("--refresh-template");
const traceFlagIndex = process.argv.indexOf("--trace");
const traceSource = traceFlagIndex >= 0 && process.argv[traceFlagIndex + 1]
  ? resolve(process.argv[traceFlagIndex + 1])
  : null;
const handoffFlagIndex = process.argv.indexOf("--handoff");
const handoffSource = handoffFlagIndex >= 0 && process.argv[handoffFlagIndex + 1]
  ? resolve(process.argv[handoffFlagIndex + 1])
  : null;
const traceTarget = resolve(repoRoot, "trace_view.json");
const hbmFlagIndex = process.argv.indexOf("--hbm-dir");
const hbmInputDir = hbmFlagIndex >= 0 && process.argv[hbmFlagIndex + 1]
  ? resolve(process.argv[hbmFlagIndex + 1])
  : null;
const architectureValidator = resolve(skillRoot, "scripts/validate-architecture-graph.mjs");
const findingsTarget = resolve(reportRoot, "outputs/metrics_findings.json");
const expertInventoryTarget = resolve(reportRoot, "outputs/expert_inventory.json");
const reportBackup = resolve(repoRoot, "report.prev");
const traceBackup = resolve(repoRoot, "trace_view.prev.json");
let hadPriorReport = false;

if (checkOnly && (refreshTemplate || traceSource || hbmInputDir)) {
  throw new Error("--check is read-only and cannot be combined with --refresh-template, --trace, or --hbm-dir");
}

// Upstream skill diagnostic mapping: error patterns → which skill to check
const UPSTREAM_DIAGNOSTIC = new Map([
  ["tensor.name is required", "Skill 2 (build_architecture_graph.py) — add tensor name/shape/dtype to edges"],
  ["tensor.shape is required", "Skill 2 (build_architecture_graph.py) — add tensor name/shape/dtype to edges"],
  ["tensor.dtype is required", "Skill 2 (build_architecture_graph.py) — add tensor name/shape/dtype to edges"],
  ["unsupported semanticEdgeType", "Skill 2 (build_architecture_graph.py) — use a valid semanticEdgeType"],
  ["unresolved source", "Skill 2 (build_architecture_graph.py) — edge source must reference a declared item"],
  ["unresolved target", "Skill 2 (build_architecture_graph.py) — edge target must reference a declared item"],
  ["self-edge", "Skill 2 (build_architecture_graph.py) — remove self-referencing edges"],
  ["dataflow cycle detected", "Skill 1 (analysis_config_v2) or Skill 2 — check serial ordering in children/branches"],
  ["has no sourceRefs", "Skill 1 (analysis_config_v2) — add source provenance to items"],
  ["not top-to-bottom", "Skill 2 (build_architecture_graph.py) — check node layout ordering"],
  ["has no provenance", "Skill 2 (build_architecture_graph.py) — add edge provenance metadata"],
  ["repeatCount must be", "Skill 2 (build_node_index.py) — fix template repeatCount"],
  ["instanceIndices length", "Skill 2 (build_node_index.py) — fix instanceIndices to match repeatCount"],
  ["residual edge but dashed is not true", "Skill 2 (build_architecture_graph.py) — mark every residual edge dashed=true"],
  ["crossInvocation=true but lacks crossStep", "Skill 2 (build_architecture_graph.py) — declare crossStep/crossSteps for cross-invocation carries"],
  ["fan-out minimum", "Skill 2 (build_architecture_graph.py) — verify fan-out edge generation"],
  ["fan-in minimum", "Skill 2 (build_architecture_graph.py) — verify fan-in edge convergence"],
]);

function diagnoseError(output) {
  const skills = new Set();
  for (const [pattern, advice] of UPSTREAM_DIAGNOSTIC) {
    if (output.includes(pattern)) skills.add(advice);
  }
  if (skills.size > 0) {
    console.error("\n── Upstream Skill Diagnostic ──");
    for (const s of skills) console.error(`  → ${s}`);
  }
}

async function exists(path) {
  return access(path, constants.F_OK).then(() => true, () => false);
}

async function safeRemove(dir) {
  try { await rm(dir, { recursive: true, force: true }); } catch { /* best-effort */ }
}

async function copyMissing(sourceDir, targetDir) {
  await mkdir(targetDir, { recursive: true });
  for (const entry of await readdir(sourceDir, { withFileTypes: true })) {
    const source = resolve(sourceDir, entry.name);
    const target = resolve(targetDir, entry.name);
    if (entry.isDirectory()) {
      await copyMissing(source, target);
    } else if (!(await exists(target))) {
      await cp(source, target);
      console.log(`COPIED ${target}`);
    }
  }
}

function runRaw(script, extraArgs = []) {
  const result = spawnSync(process.execPath, [resolve(skillRoot, "scripts", script), "--repo", repoRoot, ...extraArgs], {
    stdio: "pipe",
    encoding: "utf8",
  });
  return result;
}

function runFileRaw(scriptPath, args = []) {
  return spawnSync(process.execPath, [scriptPath, ...args], { stdio: "pipe", encoding: "utf8" });
}

function run(script, extraArgs = []) {
  const result = runRaw(script, extraArgs);
  process.stdout.write(result.stdout);
  process.stderr.write(result.stderr);
  if (result.error) throw Object.assign(result.error, { stderr: result.stderr });
  if (result.status !== 0) {
    diagnoseError(result.stderr + result.stdout);
    throw Object.assign(new Error(`${script} exited with status ${result.status}`), { stderr: result.stderr });
  }
}

function runFile(scriptPath, args = []) {
  const result = runFileRaw(scriptPath, args);
  process.stdout.write(result.stdout);
  process.stderr.write(result.stderr);
  if (result.error) throw Object.assign(result.error, { stderr: result.stderr });
  if (result.status !== 0) {
    diagnoseError(result.stderr + result.stdout);
    throw Object.assign(new Error(`${scriptPath} exited with status ${result.status}`), { stderr: result.stderr });
  }
}

if (checkOnly) {
  if (!(await exists(resolve(reportRoot, "index.html")))) {
    throw new Error(`Report is not initialized: ${reportRoot}`);
  }
} else {
  await safeRemove(reportBackup);
  hadPriorReport = await exists(reportRoot);
  if (hadPriorReport) await rename(reportRoot, reportBackup);
  try {
    if (refreshTemplate) {
      await cp(templateRoot, reportRoot, { recursive: true, force: true });
      const priorConfig = resolve(reportBackup, "report-config.js");
      if (await exists(priorConfig)) {
        await cp(priorConfig, resolve(reportRoot, "report-config.js"), { force: true });
        console.log("PRESERVED model-specific report-config.js");
      }
      const priorOutputs = resolve(reportBackup, "outputs");
      if (await exists(priorOutputs)) {
        await cp(priorOutputs, resolve(reportRoot, "outputs"), { recursive: true, force: true });
      }
      console.log(`REFRESHED report template at ${reportRoot}`);
    } else if (await exists(reportBackup)) {
      await cp(reportBackup, reportRoot, { recursive: true, force: true });
      await copyMissing(templateRoot, reportRoot);
    } else {
      await copyMissing(templateRoot, reportRoot);
    }
    const handoff = await findHandoff(repoRoot, handoffSource);
    if (handoff) {
      const priorConfigPath = resolve(reportRoot, "report-config.js");
      const priorConfig = hadPriorReport && await exists(priorConfigPath)
        ? (await readRuntimeConfig(reportRoot)).config
        : {};
      await writeFile(priorConfigPath, serializeRuntimeConfig(configFromHandoff(handoff.value, priorConfig)));
      console.log(`GENERATED report-config.js from ${handoff.path}`);
    } else {
      const priorConfigPath = resolve(reportRoot, "report-config.js");
      if (!hadPriorReport) {
        throw new Error("A new report requires ui-report-handoff.json or an explicit --handoff <path>");
      }
      const { config } = await readRuntimeConfig(reportRoot);
      await writeFile(priorConfigPath, serializeRuntimeConfig(normalizeLegacyConfig(config)));
      console.warn("WARN normalized legacy report-config.js; add ui_report_handoff.v1 to remove inference");
    }
  } catch (err) {
    await safeRemove(reportRoot);
    if (await exists(reportBackup)) await rename(reportBackup, reportRoot);
    throw err;
  }
}

const outputsDir = resolve(reportRoot, "outputs");
let traceWasReplaced = false;
let traceWasCreated = false;

let generationFailed = false;
try {
  if (traceSource) {
    if (!(await exists(traceSource))) throw new Error(`Raw TraceView file does not exist: ${traceSource}`);
    const sourceRealPath = await realpath(traceSource);
    const targetRealPath = await realpath(traceTarget).catch(() => null);
    if (sourceRealPath !== targetRealPath) {
      if (!checkOnly && await exists(traceTarget)) {
        await safeRemove(traceBackup);
        await rename(traceTarget, traceBackup);
        traceWasReplaced = true;
      } else if (!checkOnly) {
        traceWasCreated = true;
      }
      await cp(traceSource, traceTarget, { force: true });
      console.log(`COPIED raw TraceView data to ${traceTarget}`);
    }
  }
  if (!(await exists(traceTarget))) {
    throw new Error(`Missing ${traceTarget}; pass --trace <path-to-trace_view.json>`);
  }

  if (!checkOnly) {
    const findingsCandidates = [
      resolve(repoRoot, "metrics_findings.json"),
      resolve(dirname(repoRoot), "metrics_findings.json"),
    ];
    for (const candidate of findingsCandidates) {
      if (candidate !== findingsTarget && await exists(candidate)) {
        await cp(candidate, findingsTarget, { force: true });
        console.log(`COPIED diagnostic findings to ${findingsTarget}`);
        break;
      }
    }
    if (!(await exists(findingsTarget))) {
      await mkdir(dirname(findingsTarget), { recursive: true });
      const { writeFile } = await import("node:fs/promises");
      await writeFile(findingsTarget, JSON.stringify({ schema_version: 1, advisory_only: true, nodes: [] }, null, 2));
      console.log(`WROTE empty optional diagnostic findings`);
    }
    const expertInventoryDirs = [resolve(repoRoot, "ui_facts"), resolve(dirname(repoRoot), "ui_facts")];
    let expertInventorySource = null;
    for (const candidateDir of expertInventoryDirs) {
      if (!(await exists(candidateDir))) continue;
      const match = (await readdir(candidateDir)).find((name) => name.endsWith("_expert_inventory.json"));
      if (match) { expertInventorySource = resolve(candidateDir, match); break; }
    }
    if (expertInventorySource) {
      await cp(expertInventorySource, expertInventoryTarget, { force: true });
      console.log(`COPIED expert inventory to ${expertInventoryTarget}`);
    } else {
      await writeFile(expertInventoryTarget, JSON.stringify({ schema_version: 1, available: false }, null, 2));
      console.log("WROTE empty optional expert inventory");
    }
  }

  if (hbmInputDir && !checkOnly) {
    const result = spawnSync(process.execPath, [
      resolve(skillRoot, "scripts/build-hbm-data.mjs"),
      "--input-dir", hbmInputDir,
      "--out", resolve(outputsDir, "hbm_series.json"),
    ], { stdio: "inherit" });
    if (result.error) throw result.error;
    if (result.status !== 0) throw new Error(`build-hbm-data.mjs exited with status ${result.status}`);
  }

  const handoff = await findHandoff(repoRoot, handoffSource);
  const runtimeConfig = (await readRuntimeConfig(reportRoot)).config;
  if (!handoff) console.warn("WARN legacy report without ui_report_handoff.v1; inferred adapter from report-config.js");
  if (handoff?.value.skill3_adapter && handoff.value.skill3_adapter !== "generic") {
    throw new Error("cann-perf-ui-json-report only supports skill3_adapter=generic; regenerate the handoff with cann-perf-breakdown-to-ui-json");
  }
  if (!(await exists(architectureValidator))) {
    throw new Error(`Missing synchronized architecture validator: ${architectureValidator}`);
  }
  runFile(architectureValidator, [
    resolve(outputsDir, "model_architecture_graph.json"),
    "--source-root", "section/source_architecture",
    "--require-semantic-port-policy",
  ]);
  if (!(await exists(resolve(outputsDir, "trace_bindings.json")))) {
    throw new Error("Missing TraceView bindings; generate them with cann-perf-breakdown-to-ui-json");
  }
  run("build-operator-details.mjs", checkOnly ? ["--check"] : []);
  run("build-embedded-data.mjs", checkOnly ? ["--check"] : []);
  run("validate-report.mjs");
  run("test-layer-report-metrics.mjs");
  run("test-projected-fanout.mjs");

  // ── Write validation manifest ──
  if (!checkOnly) {
    const manifest = {
      schema: "model_skill_validation_manifest.v2",
      generated_at: new Date().toISOString(),
      report_root: reportRoot,
      deterministic_checks: {
        architecture_graph_validated: true,
        trace_bindings_validated: true,
        embedded_data_validated: true,
        report_validated: true,
        layer_metrics_tested: runtimeConfig.capabilities?.repeatedLayers === false ? "not_applicable" : true,
        fanout_tested: true,
      },
      manual_checks: {
        browser_smoke_1440x1000: "not_run",
        file_protocol_smoke: "not_run",
        visual_review: "not_run",
      },
      deterministic_status: "passed",
      overall_status: "pending_manual_validation",
    };
    const manifestDir = resolve(outputsDir);
    await mkdir(manifestDir, { recursive: true });
    const { writeFile } = await import("node:fs/promises");
    await writeFile(resolve(manifestDir, "validation_manifest.json"), JSON.stringify(manifest, null, 2));
    console.log(`WROTE validation manifest`);
  }

  console.log(`${checkOnly ? "CHECKED" : "GENERATED"} ${reportRoot}`);
} catch (err) {
  generationFailed = true;
  console.error(`\nGENERATION FAILED: ${err.message}`);
  if (!checkOnly) {
    await safeRemove(reportRoot);
    if (hadPriorReport) {
      await rename(reportBackup, reportRoot);
      console.log("RESTORED complete prior report");
    }
    if (traceWasReplaced) {
      await safeRemove(traceTarget);
      await rename(traceBackup, traceTarget);
      console.log("RESTORED prior trace_view.json");
    } else if (traceWasCreated) {
      await safeRemove(traceTarget);
      console.log("REMOVED uncommitted trace_view.json");
    }
  }
  process.exit(1);
} finally {
  if (!generationFailed && !checkOnly) {
    await safeRemove(reportBackup);
    if (traceWasReplaced) await safeRemove(traceBackup);
  }
}
