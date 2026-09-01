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
window.ReportRuntimeConfig = {
  templateVersion: 2,
  analysis: null,
  performance: null,
  timeline: null,
  trace: "../trace_view.json",
  bindings: "./outputs/trace_bindings.json",
  operatorDetails: "./outputs/operator_details.json",
  architecture: "./outputs/model_architecture_graph.json",
  overlay: "./outputs/architecture_overlay_map.json",
  hbm: "./outputs/hbm_series.json",
  findings: "./outputs/metrics_findings.json",
  expertInventory: "./outputs/expert_inventory.json",
  provenance: {},
  capabilities: {},
  templateOverrides: [],
};
