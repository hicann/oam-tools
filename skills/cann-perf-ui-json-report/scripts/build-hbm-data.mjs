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
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

function flag(name, fallback = "") {
  const index = process.argv.indexOf(name);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

const inputDir = resolve(flag("--input-dir", "."));
const outPath = resolve(flag("--out", "hbm_series.json"));
const phase = flag("--phase", "decode");

function parseCsv(source) {
  const lines = source.trim().split(/\r?\n/);
  const headers = lines.shift()?.split(",") || [];
  return lines.filter(Boolean).map((line) => {
    const values = line.split(",");
    return Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""]));
  });
}

function numeric(value, label) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) throw new Error(`Invalid ${label}: ${value}`);
  return parsed;
}

const [bandwidthText, occupancyText, mixText, summaryText] = await Promise.all([
  readFile(resolve(inputDir, "hbm_bandwidth_timeline.csv"), "utf8"),
  readFile(resolve(inputDir, "hbm_occupancy_timeline.csv"), "utf8"),
  readFile(resolve(inputDir, "sample_op_mix.csv"), "utf8"),
  readFile(resolve(inputDir, "hbm_summary.json"), "utf8"),
]);

const summary = JSON.parse(summaryText);
const bandwidthRows = parseCsv(bandwidthText).filter((row) => !phase || row.phase === phase);
const occupancyRows = parseCsv(occupancyText).filter((row) => (
  (!phase || row.phase === phase) && row.event === "APP"
));
const mixRows = parseCsv(mixText);
if (!bandwidthRows.length) throw new Error(`No bandwidth rows for phase ${phase || "all"}`);

const originEpochUs = numeric(bandwidthRows[0].epoch_us, "bandwidth epoch_us")
  - numeric(bandwidthRows[0].rel_ms_from_decode_start, "bandwidth relative time") * 1000;
const mixByEpoch = new Map(mixRows.map((row) => [Math.round(Number(row.epoch_us)), row]));

const bandwidthPoints = bandwidthRows.map((row) => {
  const epochUs = numeric(row.epoch_us, "bandwidth epoch_us");
  const mix = mixByEpoch.get(Math.round(epochUs));
  return [
    Number((epochUs - originEpochUs).toFixed(1)),
    numeric(row.read_gbs, "read_gbs"),
    numeric(row.write_gbs, "write_gbs"),
    row.phase,
    row.step === "" ? null : numeric(row.step, "step"),
    mix?.attributed_label || null,
    mix?.window_busy_pct === "" || mix?.window_busy_pct == null ? null : numeric(mix.window_busy_pct, "window_busy_pct"),
  ];
});

const occupancyPoints = occupancyRows.map((row) => [
  Number((numeric(row.epoch_us, "occupancy epoch_us") - originEpochUs).toFixed(1)),
  numeric(row.hbm_gib, "hbm_gib"),
  row.event,
  row.phase,
]);

for (const points of [bandwidthPoints, occupancyPoints]) {
  for (let index = 1; index < points.length; index += 1) {
    if (points[index][0] < points[index - 1][0]) throw new Error("HBM points are not time ordered");
  }
}

const data = {
  schema_version: "1.0",
  source: {
    model: summary.model,
    dtype: summary.dtype,
    device_index: summary.device_index,
    hbm_channels: summary.hbm_channels,
    phase,
    bandwidth_file: "hbm_bandwidth_timeline.csv",
    occupancy_file: "hbm_occupancy_timeline.csv",
    correlation_file: "sample_op_mix.csv",
  },
  time: {
    unit: "us",
    origin: "decode_start",
    origin_epoch_us: originEpochUs,
    start_us: bandwidthPoints[0][0],
    end_us: bandwidthPoints.at(-1)[0],
  },
  bandwidth: {
    unit: "GB/s",
    sample_interval_us: numeric(summary.sample_interval_ms, "sample_interval_ms") * 1000,
    peak_gbs: numeric(summary.roofline?.hbm_peak_gbs_assumed, "hbm_peak_gbs_assumed"),
    points: bandwidthPoints,
    point_fields: ["time_us", "read_gbs", "write_gbs", "phase", "step", "attributed_label", "window_busy_pct"],
  },
  occupancy: {
    unit: "GiB",
    points: occupancyPoints,
    point_fields: ["time_us", "hbm_gib", "event", "phase"],
  },
  summary: summary.decode,
  limitations: [
    "HBM bandwidth is sampled at approximately 100 Hz; a point spans hundreds of kernels.",
    "attributed_label is a sample-window dominant operator type, not per-operator bandwidth attribution.",
    "The profiler exposes no physical address, bank, row, or column fields; this is a continuous time-series line view, not an address heatmap.",
  ],
};

await mkdir(dirname(outPath), { recursive: true });
await writeFile(outPath, `${JSON.stringify(data, null, 2)}\n`);
console.log(`WROTE ${outPath}`);
console.log(`HBM ${bandwidthPoints.length} bandwidth points, ${occupancyPoints.length} occupancy points, phase=${phase}`);
