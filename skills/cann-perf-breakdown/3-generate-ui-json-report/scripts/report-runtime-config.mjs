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
import { constants } from "node:fs";
import { resolve } from "node:path";
import vm from "node:vm";

export const REQUIRED_CONFIG_KEYS = [
  "analysis", "performance", "timeline", "trace", "bindings", "architecture", "overlay",
];

export const OPTIONAL_CONFIG_DEFAULTS = Object.freeze({
  operatorDetails: "./outputs/operator_details.json",
  hbm: "./outputs/hbm_series.json",
  findings: "./outputs/metrics_findings.json",
  expertInventory: "./outputs/expert_inventory.json",
});

export const CURRENT_TEMPLATE_VERSION = 2;

export async function exists(path) {
  return access(path, constants.F_OK).then(() => true, () => false);
}

export async function readRuntimeConfig(reportRoot) {
  const configPath = resolve(reportRoot, "report-config.js");
  const source = await readFile(configPath, "utf8");
  const sandbox = { window: {} };
  vm.runInNewContext(source, sandbox, { filename: configPath });
  const raw = sandbox.window.ReportRuntimeConfig;
  if (!raw || typeof raw !== "object") {
    throw new Error(`report-config.js must assign window.ReportRuntimeConfig`);
  }
  const missing = REQUIRED_CONFIG_KEYS.filter((key) => typeof raw[key] !== "string" || !raw[key]);
  if (missing.length) {
    throw new Error(`ReportRuntimeConfig is missing required key(s): ${missing.join(", ")}`);
  }
  const defaultedOptionalKeys = Object.keys(OPTIONAL_CONFIG_DEFAULTS)
    .filter((key) => typeof raw[key] !== "string" || !raw[key]);
  return {
    source,
    raw,
    config: { ...OPTIONAL_CONFIG_DEFAULTS, ...raw },
    defaultedOptionalKeys,
  };
}

export function validateHandoff(handoff, source = "ui-report-handoff.json") {
  if (!handoff || handoff.schema_version !== "ui_report_handoff.v1") {
    throw new Error(`${source} must use schema_version ui_report_handoff.v1`);
  }
  if (!handoff.inputs || typeof handoff.inputs !== "object") {
    throw new Error(`${source} must declare inputs`);
  }
  const inputKeys = ["analysis", "performance", "timeline", "trace", "bindings", "architecture", "overlay"];
  const missing = inputKeys.filter((key) => typeof handoff.inputs[key] !== "string" || !handoff.inputs[key]);
  if (missing.length) throw new Error(`${source} is missing input path(s): ${missing.join(", ")}`);
  if (handoff.capabilities != null && (typeof handoff.capabilities !== "object" || Array.isArray(handoff.capabilities))) {
    throw new Error(`${source}.capabilities must be an object`);
  }
  if (handoff.skill3_adapter != null && handoff.skill3_adapter !== "generic") {
    throw new Error(`${source}.skill3_adapter must be generic`);
  }
  return handoff;
}

export async function findHandoff(repoRoot, explicitPath = null) {
  const candidates = explicitPath
    ? [resolve(explicitPath)]
    : [resolve(repoRoot, "ui-report-handoff.json"), resolve(repoRoot, "ui_facts/ui-report-handoff.json")];
  for (const path of candidates) {
    if (!(await exists(path))) continue;
    return { path, value: validateHandoff(JSON.parse(await readFile(path, "utf8")), path) };
  }
  return null;
}

export function configFromHandoff(handoff, priorConfig = {}) {
  const optional = handoff.optional_inputs || {};
  return {
    templateVersion: CURRENT_TEMPLATE_VERSION,
    analysis: handoff.inputs.analysis,
    performance: handoff.inputs.performance,
    timeline: handoff.inputs.timeline,
    trace: handoff.inputs.trace,
    bindings: handoff.inputs.bindings,
    operatorDetails: optional.operator_details || OPTIONAL_CONFIG_DEFAULTS.operatorDetails,
    architecture: handoff.inputs.architecture,
    overlay: handoff.inputs.overlay,
    hbm: optional.hbm || OPTIONAL_CONFIG_DEFAULTS.hbm,
    findings: optional.findings || OPTIONAL_CONFIG_DEFAULTS.findings,
    expertInventory: optional.expert_inventory || OPTIONAL_CONFIG_DEFAULTS.expertInventory,
    provenance: handoff.provenance || priorConfig.provenance || {},
    capabilities: handoff.capabilities || priorConfig.capabilities || {},
    templateOverrides: handoff.template_overrides || priorConfig.templateOverrides || [],
    handoffSchemaVersion: handoff.schema_version,
  };
}

export function normalizeLegacyConfig(config) {
  return {
    templateVersion: CURRENT_TEMPLATE_VERSION,
    ...OPTIONAL_CONFIG_DEFAULTS,
    ...config,
    provenance: config.provenance || {},
    capabilities: config.capabilities || {},
    templateOverrides: Array.isArray(config.templateOverrides) ? config.templateOverrides : [],
  };
}

export function serializeRuntimeConfig(config) {
  return `window.ReportRuntimeConfig = ${JSON.stringify(config, null, 2)};\n`;
}
