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
import { cp, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import vm from "node:vm";

const repoIndex = process.argv.indexOf("--repo");
const sourceRepo = repoIndex >= 0 && process.argv[repoIndex + 1] ? resolve(process.argv[repoIndex + 1]) : null;
if (!sourceRepo) throw new Error("Pass --repo <existing-report-repo>");
const skillRoot = resolve(new URL("..", import.meta.url).pathname);
const generator = resolve(skillRoot, "scripts/generate-report.mjs");
const work = await mkdtemp(join(tmpdir(), "skill3-safety-"));
const sourceParent = dirname(sourceRepo);
const fixtureParent = resolve(work, "fixture");
const repo = resolve(fixtureParent, basename(sourceRepo));

async function files(root, prefix = "") {
  const result = [];
  for (const entry of await readdir(root, { withFileTypes: true })) {
    const relative = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (entry.isDirectory()) result.push(...await files(resolve(root, entry.name), relative));
    else result.push(relative);
  }
  return result.sort();
}

async function snapshot(root) {
  const entries = {};
  for (const relative of await files(root)) {
    entries[relative] = createHash("sha256").update(await readFile(resolve(root, relative))).digest("hex");
  }
  return entries;
}

function run(args) {
  return spawnSync(process.execPath, [generator, "--repo", repo, ...args], { encoding: "utf8" });
}

function backendPaths(source) {
  const sandbox = { window: {} };
  vm.runInNewContext(source, sandbox, { filename: "report-config.js" });
  const config = sandbox.window.ReportRuntimeConfig || {};
  return [config.analysis, config.performance, config.timeline];
}

try {
  await cp(sourceParent, fixtureParent, { recursive: true });
  const configBefore = await readFile(resolve(repo, "report/report-config.js"), "utf8");
  const refresh = run(["--refresh-template"]);
  if (refresh.status !== 0) throw new Error(`refresh fixture failed:\n${refresh.stderr}${refresh.stdout}`);
  const configAfter = await readFile(resolve(repo, "report/report-config.js"), "utf8");
  if (JSON.stringify(backendPaths(configBefore)) !== JSON.stringify(backendPaths(configAfter))) {
    throw new Error("--refresh-template changed model-specific backend paths");
  }

  const beforeCheck = await snapshot(repo);
  const check = run(["--check"]);
  if (check.status !== 0) throw new Error(`read-only check fixture failed:\n${check.stderr}${check.stdout}`);
  const afterCheck = await snapshot(repo);
  if (JSON.stringify(beforeCheck) !== JSON.stringify(afterCheck)) throw new Error("--check modified the repository");

  const indexPath = resolve(repo, "report/index.html");
  const indexSource = await readFile(indexPath, "utf8");
  await writeFile(indexPath, `${indexSource}\n<!-- undeclared template drift -->\n`);
  const driftedCheck = run(["--check"]);
  if (driftedCheck.status === 0) throw new Error("--check accepted undeclared index.html template drift");
  await writeFile(indexPath, indexSource);

  const beforeFailure = await snapshot(resolve(repo, "report"));
  const missingTrace = resolve(work, "missing-trace.json");
  const failed = run(["--trace", missingTrace]);
  if (failed.status === 0) throw new Error("intentional generation failure unexpectedly succeeded");
  const afterFailure = await snapshot(resolve(repo, "report"));
  if (JSON.stringify(beforeFailure) !== JSON.stringify(afterFailure)) throw new Error("generation failure did not restore the complete prior report");

  console.log("OK   --check is byte-for-byte read-only");
  console.log("OK   --check rejects undeclared principal runtime template drift");
  console.log("OK   template refresh preserves model-specific paths");
  console.log("OK   failed generation restores the complete prior report");
} finally {
  await rm(work, { recursive: true, force: true });
}
