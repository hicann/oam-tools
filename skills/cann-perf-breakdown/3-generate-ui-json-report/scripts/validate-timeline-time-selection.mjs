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
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import vm from "node:vm";

const repoFlagIndex = process.argv.indexOf("--repo");
const repoArgument = repoFlagIndex >= 0 ? process.argv[repoFlagIndex + 1] : null;
if (!repoArgument) throw new Error("Pass --repo <report-repo>");
const patternPath = resolve(
  repoArgument,
  "report/design-system/patterns/timeline-time-selection/pattern.js",
);
const source = await readFile(patternPath, "utf8");
const sandbox = { window: {} };
vm.runInNewContext(source, sandbox, { filename: "timeline-time-selection/pattern.js" });
const helper = sandbox.window.PtoTimelineTimeSelectionPattern;

assert.equal(helper.xToTime(25, 100, 1000, 2000), 1250);
assert.equal(helper.timeToX(1750, 100, 1000, 2000), 75);
assert.deepEqual(
  { ...helper.normalizeSelection({ kind: "range", start: 80, end: 20 }) },
  { kind: "range", start: 20, end: 80 },
);
assert.match(helper.formatSelectionSummary({ start: 1000, end: 1250 }, "zh"), /开始 1,000 µs.*结束 1,250 µs.*持续 250\.0 µs/);
assert.match(helper.formatSelectionSummary({ start: 1000, end: 2250 }, "en"), /Duration 1\.25 ms/);
const summary = {
  dataset: {},
  hidden: true,
  offsetWidth: 200,
  style: {},
  textContent: "",
};
helper.updateSelectionSummary(summary, { kind: "range", start: 100, end: 200 }, "en", {
  rangeStart: 0,
  rangeEnd: 1000,
  trackLeft: 236,
  trackWidth: 1000,
  scrollLeft: 0,
  viewportWidth: 1000,
});
assert.equal(summary.style.left, "386px");
assert.equal(summary.dataset.alignment, "selection-center");
helper.updateSelectionSummary(summary, { kind: "range", start: 100, end: 200 }, "en", {
  rangeStart: 0,
  rangeEnd: 1000,
  trackLeft: 236,
  trackWidth: 1000,
  scrollLeft: 100,
  viewportWidth: 1000,
});
assert.equal(summary.style.left, "286px");

class FakeTarget {
  constructor() {
    this.listeners = new Map();
    this.captured = new Set();
    this.classList = {
      values: new Set(),
      add: (value) => this.classList.values.add(value),
      remove: (value) => this.classList.values.delete(value),
    };
  }

  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(listener);
  }

  removeEventListener(type, listener) {
    this.listeners.get(type)?.delete(listener);
  }

  getBoundingClientRect() {
    return { left: 0, width: 100 };
  }

  focus() {
    this.focused = true;
  }

  setPointerCapture(pointerId) {
    this.captured.add(pointerId);
  }

  hasPointerCapture(pointerId) {
    return this.captured.has(pointerId);
  }

  releasePointerCapture(pointerId) {
    this.captured.delete(pointerId);
  }

  emit(type, properties = {}) {
    const event = {
      button: 0,
      pointerId: 1,
      clientX: 0,
      deltaY: 0,
      ctrlKey: false,
      metaKey: false,
      shiftKey: false,
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
      ...properties,
    };
    this.listeners.get(type)?.forEach((listener) => listener(event));
    return event;
  }
}

const target = new FakeTarget();
const previews = [];
const commits = [];
const selectedEvents = [];
const zooms = [];
const navigations = [];
let clears = 0;
const controller = helper.bindTimelineInteraction({
  target,
  getGeometry: () => ({ width: 100, start: 0, end: 1000 }),
  hitTest: (x) => (x >= 8 && x <= 14 ? { event: { ts: 80, end: 140, dur: 60 } } : null),
  onPreview: (selection) => previews.push({ ...selection }),
  onCommit: (selection) => commits.push({ ...selection }),
  onEventSelect: (event) => selectedEvents.push(event),
  onClear: () => { clears += 1; },
  onZoom: (payload) => zooms.push(payload),
  onNavigate: (payload) => navigations.push(payload),
});

target.emit("pointerdown", { clientX: 10 });
assert.equal(target.focused, true);
assert.equal(target.captured.has(1), true);
target.emit("pointermove", { clientX: 12 });
assert.equal(previews.length, 0);
target.emit("pointerup", { clientX: 12 });
assert.equal(selectedEvents.length, 1);

target.emit("pointerdown", { clientX: 80, pointerId: 2 });
target.emit("pointermove", { clientX: 20, pointerId: 2 });
assert.deepEqual(previews.at(-1), { kind: "range", start: 200, end: 800 });
target.emit("pointerup", { clientX: 10, pointerId: 2 });
assert.deepEqual(commits.at(-1), { kind: "range", start: 100, end: 800 });
assert.equal(target.captured.has(2), false);

const plainWheel = target.emit("wheel", { deltaY: -10 });
assert.equal(plainWheel.defaultPrevented, false);
assert.equal(zooms.length, 0);
const commandWheel = target.emit("wheel", { deltaY: -10, metaKey: true, clientX: 45 });
assert.equal(commandWheel.defaultPrevented, true);
assert.equal(zooms.at(-1).direction, 1);
const controlWheel = target.emit("wheel", { deltaY: 10, ctrlKey: true, clientX: 55 });
assert.equal(controlWheel.defaultPrevented, true);
assert.equal(zooms.at(-1).direction, -1);

target.emit("keydown", { key: "ArrowLeft" });
target.emit("keydown", { key: "ArrowRight", shiftKey: true });
assert.equal(navigations[0].direction, -1);
assert.equal(navigations[1].direction, 1);
assert.equal(navigations[1].accelerated, true);
target.emit("keydown", { key: "Escape" });
assert.equal(clears, 1);

controller.destroy();
assert.equal([...target.listeners.values()].every((listeners) => listeners.size === 0), true);

console.log("OK   timeline time selection interaction contract");
