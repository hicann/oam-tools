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
import { access, readFile, writeFile } from "node:fs/promises";
import { constants } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const skillRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoFlagIndex = process.argv.indexOf("--repo");
const repoRoot = resolve(repoFlagIndex >= 0 && process.argv[repoFlagIndex + 1]
  ? process.argv[repoFlagIndex + 1]
  : resolve(skillRoot, "../.."));
const checkOnly = process.argv.includes("--check");
const targetPath = resolve(repoRoot, "report/outputs/operator_details.json");
const candidates = [
  resolve(repoRoot, "work/raw_ops_details.json"),
  resolve(repoRoot, "../work/raw_ops_details.json"),
];

async function exists(path) {
  return access(path, constants.F_OK).then(() => true, () => false);
}

const sourcePath = await candidates.reduce(async (foundPromise, candidate) => (
  (await foundPromise) || ((await exists(candidate)) ? candidate : null)
), Promise.resolve(null));
const source = sourcePath ? JSON.parse(await readFile(sourcePath, "utf8")) : {};
const operators = Array.isArray(source.operators) ? source.operators : [];
const details = Object.fromEntries(operators.flatMap((operator) => {
  const opIndex = Number(operator.index);
  if (!Number.isInteger(opIndex)) return [];
  return [[String(opIndex), {
    op_index: opIndex,
    name: operator.name || "",
    type: operator.type || "",
    stream_id: operator.stream_id ?? null,
    input_shapes: operator.input_shapes || "",
    output_shapes: operator.output_shapes || "",
    input_data_types: operator.input_data_types || "",
    output_data_types: operator.output_data_types || "",
  }]];
}));
const payload = {
  schema_version: 1,
  source: sourcePath ? "work/raw_ops_details.json" : null,
  count: Object.keys(details).length,
  details,
};
const generated = `${JSON.stringify(payload, null, 2)}\n`;

if (checkOnly) {
  const current = await readFile(targetPath, "utf8");
  if (current !== generated) throw new Error(`Stale operator details: ${targetPath}`);
  console.log(`OK   ${payload.count} operator detail records are current`);
} else {
  await writeFile(targetPath, generated);
  console.log(`WROTE ${targetPath} (${payload.count} records)`);
}
