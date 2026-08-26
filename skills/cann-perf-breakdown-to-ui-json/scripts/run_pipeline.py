#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------
"""Drive stages 1-3 end to end, stopping wherever a human judgement is required.

Everything deterministic runs unattended. The two steps that are genuinely AI work -- mapping
every op to a structure node, and reviewing the decomposition against the source -- have no
script, so this stops at `awaiting_ai_mapping` / `awaiting_semantic_review`, writes what the
next actor needs, and never fabricates a passed result.

    python3 run_pipeline.py --capture-dir DIR --model-id NAME --out DIR [--breakdown-config F]

The capture directory is searched for `kernel_details.csv`, `trace_view.json` and the model
source; pass them explicitly to override. Prints one JSON status object and exits non-zero on a
real failure (a stop for AI input is a success -- there is nothing wrong with the run).
"""
import argparse
import glob
import json
import logging
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE2 = os.path.dirname(HERE)
SKILLS = os.path.dirname(STAGE2)
STAGE1 = os.path.join(SKILLS, "cann-perf-breakdown")
STAGE3 = os.path.join(SKILLS, "cann-perf-ui-json-report")

sys.path.insert(0, HERE)
import breakdown_paths  # noqa: E402


logger = logging.getLogger(__name__)
command_logger = logging.getLogger(f"{__name__}.commands")


def run(cmd, **kwargs):
    command_logger.info("$ %s", " ".join(str(part) for part in cmd))
    return subprocess.run([str(part) for part in cmd], capture_output=True, text=True, **kwargs)


def die(status, stage, message, **extra):
    payload = json.dumps(
        {"status": status, "stage": stage, "message": message, **extra},
        ensure_ascii=False,
        indent=1,
    )
    raise breakdown_paths.ConversionError(
        payload, exit_code=0 if status.startswith("awaiting") else 1, stdout=True
    )


def find_one(root, name, explicit=None):
    if explicit:
        return explicit
    hits = sorted(glob.glob(os.path.join(root, "**", name), recursive=True))
    return hits[0] if hits else None


NON_SOURCE_DIRS = ("tests", "fixtures", "test", "skill", "skills", "node_modules",
                   "assets", "__pycache__", ".git")


def find_source_dir(root, explicit=None):
    """Return the directory containing the largest non-fixture modeling file."""
    if explicit:
        return explicit
    hits = []
    for path in sorted(glob.glob(os.path.join(root, "**", "modeling_*.py"), recursive=True)):
        parts = set(os.path.relpath(path, root).split(os.sep)[:-1])
        if not parts & set(NON_SOURCE_DIRS):
            hits.append(path)
    if not hits:
        return None
    hits.sort(key=lambda path: os.path.getsize(path), reverse=True)
    return os.path.dirname(hits[0])


def _branch_obligations(dataflow_path):
    """Summarize residual and parallel declarations the mapper must provide."""
    try:
        with open(dataflow_path, "r", encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError):
        return None
    modules = []
    for module in document.get("modules") or []:
        merges = module.get("merges") or []
        forks = module.get("forks") or []
        if not merges and not forks:
            continue
        merge_records = []
        for merge in merges:
            operands = [item.get("variable") for item in (merge.get("operands") or [])]
            merge_records.append({
                "lineno": merge.get("lineno"), "kind": merge.get("kind") or "add",
                "operands": operands, "note": merge.get("note"),
            })
        fork_records = []
        for fork in forks:
            fork_records.append({
                "variable": fork.get("variable"), "branch_count": fork.get("branch_count"),
                "read_by_calls": fork.get("read_by_calls"), "from_input": fork.get("from_input"),
            })
        modules.append({
            "class_name": module.get("class_name"), "source_path": module.get("source_path"),
            "residual_branches_required": len(merges),
            "parallel_branches_required": len(forks),
            "merges": merge_records, "forks": fork_records,
        })
    if not modules:
        return None
    return {
        "rule": "每个 merges[] 必须对应一条 branches[]（kind: residual，含 fused_in_call / "
                "in_place_add）；每个 forks[] 必须对应一条 kind: parallel 的 branches[]。"
                "children 只表达包含关系，未在 branches 里声明的边在下游等于不存在。",
        "verify_before_submitting":
            "对每个 structure：len(branches of kind residual) >= residual_branches_required "
            "且 len(branches of kind parallel) >= parallel_branches_required。"
            "不满足会被 SL8 / D1 阻断，且架构图会整体缺失残差边。",
        "modules": modules,
    }


def add_capture_args(parser):
    parser.add_argument("--capture-dir", required=True, help="profiling capture directory")
    parser.add_argument("--model-id", required=True,
                        help="report model id, e.g. longcat-flash-lite")
    parser.add_argument("--out", required=True, help="work + output directory")
    parser.add_argument("--csv",
                        help="kernel_details.csv (default: found under --capture-dir)")
    parser.add_argument("--trace",
                        help="trace_view.json (default: found under --capture-dir)")
    parser.add_argument("--source-dir",
                        help="model source dir (default: dir of modeling_*.py)")
    parser.add_argument("--step", help="representative step id; default is auto-selected")
    parser.add_argument("--hbm-dir", action="append", default=[],
                        help="directory holding HBM sample exports. Repeatable, because a "
                             "capture splits them across derived/hbm and derived/correlation. "
                             "Default: discovered under --capture-dir.")
    parser.add_argument("--dataflow",
                        help="dataflow_source.json from extract_dataflow.py. Default: extracted "
                             "from the discovered model source into <out>/work.")


def add_review_args(parser):
    parser.add_argument("--breakdown-config", help="AI-authored analysis_config_v2.json")
    parser.add_argument("--split-rules",
                        help="asserted split rules passed to attribute_kernels.py")
    parser.add_argument("--semantic-review", help="AI-authored semantic_review.json")
    parser.add_argument("--manifest",
                        help="reviewed model_manifest.json; pass the reviewed file when "
                             "continuing an existing breakdown")
    parser.add_argument("--rename-group", action="append", default=[],
                        help="StructureKey=node-name, repeatable")


def add_report_args(parser):
    parser.add_argument("--report-id", help="default: <model-id>/from-breakdown")
    parser.add_argument("--peak-bf16-tflops", default="376")
    parser.add_argument("--dtype-bytes", default="2")
    parser.add_argument("--ep-rank", type=int,
                        help="expert-parallel rank of this capture; only resolves which expert "
                             "indices are resident")
    parser.add_argument("--stage3-dir",
                        help="path to the cann-perf-ui-json-report skill; default: sibling "
                             "under the same skills directory")


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_capture_args(parser)
    add_review_args(parser)
    add_report_args(parser)
    return parser.parse_args()


class Pipeline:
    """Run conversion stages with shared paths and status state."""

    def __init__(self, args):
        self.args = args
        self.out = os.path.abspath(args.out)
        self.work = os.path.join(self.out, "work")
        self.facts = os.path.join(self.out, "ui_facts")
        self.repo = os.path.join(self.out, "ui-report")
        self.stage3 = os.path.abspath(args.stage3_dir or STAGE3)
        self.stage2_scripts = os.path.join(STAGE2, "scripts")
        self.stages = {}
        self.csv = self.trace = self.source = None
        self.raw = self.device_freq = self.manifest = self.dataflow = None
        self.config = self.review = None
        self.nodes = self.attribution = None
        self.graph = self.analysis_fact = self.perf_fact = self.timeline_fact = None
        for directory in (self.work, self.facts, self.repo):
            os.makedirs(directory, exist_ok=True)

    @staticmethod
    def graph_errors(report):
        if not os.path.exists(report):
            return []
        try:
            with open(report, "r", encoding="utf-8") as handle:
                document = json.load(handle)
            return [issue for issue in (document.get("issues") or [])
                    if issue.get("severity") == "error"]
        except (OSError, ValueError):
            return []

    @staticmethod
    def find_hbm_inputs(names, directories):
        found = {}
        for name in names:
            for directory in directories:
                candidate = os.path.join(directory, name)
                if os.path.isfile(candidate):
                    found[name] = candidate
                    break
        return found

    def discover(self):
        self.csv = find_one(self.args.capture_dir, "kernel_details.csv", self.args.csv)
        if not self.csv:
            die("failed", "discover", "no kernel_details.csv under --capture-dir")
        self.trace = find_one(self.args.capture_dir, "trace_view.json", self.args.trace)
        self.source = find_source_dir(self.args.capture_dir, self.args.source_dir)
        if not self.source:
            die("failed", "discover", "no modeling_*.py under --capture-dir; pass --source-dir")
        self.stages["discover"] = {
            "csv": self.csv, "trace": self.trace, "source_dir": self.source,
        }

    def analyze_kernels(self):
        self.raw = os.path.join(self.work, "raw_ops.json")
        cmd = [sys.executable, os.path.join(STAGE1, "scripts/analyze_kernels.py"),
               "-f", self.csv, "-o", self.raw,
               "-d", os.path.join(self.work, "raw_ops_details.json"),
               "--compact-out", os.path.join(self.work, "raw_ops.compact.json"),
               "-m", os.path.join(self.work, "steps_summary.md")]
        if self.args.step:
            cmd += ["-s", self.args.step]
        result = run(cmd)
        if result.returncode:
            die("failed", "raw_ops", result.stderr[-800:])
        self.stages["raw_ops"] = "ok"

    def derive_device_freq(self):
        self.device_freq = os.path.join(self.work, "device_freq.json")
        cmd = [sys.executable, os.path.join(STAGE1, "scripts/device_freq.py"),
               "-d", os.path.join(self.work, "raw_ops_details.json"),
               "-o", self.device_freq]
        if self.trace:
            cmd += ["--trace", self.trace]
        result = run(cmd)
        if result.returncode:
            self.stages["device_freq"] = (
                f"unavailable: {(result.stderr or result.stdout)[-200:]}")
            self.device_freq = None
        else:
            output = result.stdout.strip().splitlines()[-1] if result.stdout else "ok"
            self.stages["device_freq"] = output

    def prepare_manifest(self):
        self.manifest = os.path.join(self.work, "model_manifest.json")
        if self.args.manifest:
            if os.path.abspath(self.args.manifest) != os.path.abspath(self.manifest):
                shutil.copy(self.args.manifest, self.manifest)
            self.stages["manifest"] = f"supplied: {self.args.manifest}"
            return
        result = run([sys.executable,
                      os.path.join(STAGE1, "scripts/extract_model_manifest.py"),
                      "--model-dir", self.source, "--base-dir", STAGE1,
                      "-o", self.manifest])
        self.stages["manifest"] = "ok" if result.returncode == 0 else "error"
        if result.returncode:
            die("failed", "manifest", result.stderr[-800:])

    def extract_dataflow(self):
        self.dataflow = self.args.dataflow
        if self.dataflow:
            self.stages["dataflow"] = self.dataflow
            return
        candidates = sorted(glob.glob(os.path.join(self.source, "modeling_*.py")))
        if not candidates:
            self.stages["dataflow"] = (
                f"no modeling_*.py under {self.source}; dataflow check unavailable")
            return
        derived = os.path.join(self.work, "dataflow_source.json")
        cmd = [sys.executable, os.path.join(STAGE1, "scripts/extract_dataflow.py"),
               "-o", derived]
        for path in candidates:
            cmd += ["-s", path]
        result = run(cmd)
        if result.returncode == 0 and os.path.exists(derived):
            self.dataflow = derived
            self.stages["dataflow"] = derived
        else:
            self.stages["dataflow"] = "extraction failed; dataflow check unavailable"

    def mapping_request(self):
        request = os.path.join(self.out, "ai_mapping_request.json")
        inputs = {
            "model_manifest": self.manifest, "raw_ops": self.raw,
            "raw_ops_compact": os.path.join(self.work, "raw_ops.compact.json"),
            "model_source_dir": self.source,
        }
        payload = {
            "task": "map every op of the representative step to model / runtime_auxiliary "
                    "/ (strictly allowed) excluded, and emit analysis_config_v2.json",
            "protocol": os.path.join(STAGE1, "references/ai_mapping_protocol.md"),
            "inputs": inputs,
            "output_expected": os.path.join(self.work, "analysis_config_v2.json"),
            "then": "re-run this command with --breakdown-config <that file>",
        }
        if self.dataflow and os.path.exists(self.dataflow):
            inputs["dataflow_source"] = self.dataflow
            payload["required_branch_declarations"] = _branch_obligations(self.dataflow)
        with open(request, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=1)
        return request

    def require_mapping(self):
        self.config = breakdown_paths.resolve_config(self.work, self.args.breakdown_config)
        if not (self.config and os.path.exists(self.config)):
            request = self.mapping_request()
            die("awaiting_ai_mapping", "mapping",
                "the op mapping has no script: an AI must read the source and write "
                "analysis_config_v2.json", request=request, stages=self.stages)
        self.stages["mapping"] = self.config

    def require_semantic_review(self):
        self.review = self.args.semantic_review or os.path.join(
            self.work, "semantic_review.json")
        if not os.path.exists(self.review):
            request = os.path.join(self.work, "semantic_review_request.json")
            result = run([sys.executable,
                          os.path.join(STAGE1, "scripts/prepare_semantic_review.py"),
                          "-c", self.config, "-r", self.raw, "-m", self.manifest,
                          "-o", request])
            die("awaiting_semantic_review", "semantic_review",
                "the source/trace semantic review has no script: an AI must complete all nine "
                "checks and write semantic_review.json",
                request=request if result.returncode == 0 else None, stages=self.stages)
        staged_review = os.path.join(self.work, "semantic_review.json")
        if os.path.abspath(self.review) != os.path.abspath(staged_review):
            shutil.copy(self.review, staged_review)
            self.review = staged_review
        self.stages["semantic_review"] = self.review

    def validate_breakdown(self):
        validation = os.path.join(self.work, "validation_report.json")
        cmd = [sys.executable, os.path.join(STAGE1, "scripts/run_validation.py"),
               "-c", self.config, "-r", self.raw, "-m", self.manifest,
               "--source-dir", self.source, "--semantic-review", self.review,
               "--allow-warnings", "-o", validation]
        if self.dataflow:
            cmd += ["--dataflow", self.dataflow]
        result = run(cmd)
        if not os.path.exists(validation):
            die("failed", "validation", result.stderr[-800:] or result.stdout[-800:])
        with open(validation, encoding="utf-8") as handle:
            self.stages["validation"] = json.load(handle).get("status")
        return validation

    def score_breakdown(self, validation):
        score = os.path.join(self.work, "breakdown_score.json")
        result = run([sys.executable, os.path.join(STAGE1, "scripts/score_breakdown.py"),
                      "-c", self.config, "-r", self.raw, "-m", self.manifest,
                      "--validation-report", validation, "--semantic-review", self.review,
                      "-o", score])
        if not os.path.exists(score):
            die("failed", "scoring", result.stderr[-800:] or result.stdout[-800:])
        with open(score, encoding="utf-8") as handle:
            score_doc = json.load(handle)
        self.stages["scoring"] = f"{score_doc.get('score')}/100 {score_doc.get('status')}"
        if not breakdown_paths.is_convertible_score(score_doc):
            die("needs_iteration", "scoring",
                "the breakdown has not earned conversion; fix it rather than converting it",
                score=score, failed_dimensions=score_doc.get("failed_dimensions"),
                required_actions=score_doc.get("required_actions", [])[:6],
                stages=self.stages)

    def run_stage1(self):
        self.analyze_kernels()
        self.derive_device_freq()
        self.prepare_manifest()
        self.extract_dataflow()
        self.require_mapping()
        self.require_semantic_review()
        self.score_breakdown(self.validate_breakdown())

    def check_readiness(self):
        result = run([sys.executable,
                      os.path.join(self.stage2_scripts, "check_breakdown_ready.py"),
                      "--breakdown", self.work, "--config", self.config,
                      "--out", os.path.join(self.work, "readiness.json")])
        if result.returncode:
            die("failed", "readiness", result.stdout[-1200:], stages=self.stages)
        self.stages["readiness"] = "ready"

    def build_node_index(self):
        self.nodes = os.path.join(self.work, "node_index.json")
        cmd = [sys.executable, os.path.join(self.stage2_scripts, "build_node_index.py"),
               "--breakdown", self.work, "--config", self.config,
               "--namespace", f"model/{self.args.model_id}", "--out", self.nodes]
        for rename in self.args.rename_group:
            cmd += ["--rename-group", rename]
        result = run(cmd)
        if result.returncode:
            die("failed", "node_index", result.stderr[-800:], stages=self.stages)
        self.stages["node_index"] = "ok"

    def attribute_kernels(self):
        self.attribution = os.path.join(self.work, "kernel_attribution.json")
        cmd = [sys.executable, os.path.join(self.stage2_scripts, "attribute_kernels.py"),
               "--breakdown", self.work, "--config", self.config,
               "--nodes", self.nodes, "--out", self.attribution]
        if self.args.split_rules:
            cmd += ["--split-rules", self.args.split_rules]
        result = run(cmd)
        if result.returncode:
            die("failed", "attribution", (result.stderr or result.stdout)[-800:],
                stages=self.stages,
                hint="unequal invocation spans mean the group shares a template it should not; "
                     "split the differing layer into its own layer_group in stage 1")
        self.stages["attribution"] = "100%"

    def emit_facts(self):
        cmd = [sys.executable, os.path.join(self.stage2_scripts, "emit_ui_facts.py"),
               "--breakdown", self.work, "--config", self.config,
               "--nodes", self.nodes, "--attribution", self.attribution,
               "--model-id", self.args.model_id,
               "--report-id", self.args.report_id or f"{self.args.model_id}/from-breakdown",
               "--peak-bf16-tflops", self.args.peak_bf16_tflops,
               "--dtype-bytes", self.args.dtype_bytes, "--out", self.facts]
        if self.device_freq:
            cmd += ["--device-freq", self.device_freq]
        result = run(cmd)
        if result.returncode:
            die("failed", "emit_facts", result.stderr[-800:], stages=self.stages)
        self.stages["ui_facts"] = self.facts
        prefix = self.args.model_id
        self.analysis_fact = os.path.join(self.facts, f"{prefix}_analysis_config.json")
        self.perf_fact = os.path.join(self.facts, f"{prefix}_perf_data.json")
        self.timeline_fact = os.path.join(self.facts, f"{prefix}_timeline.json")

    def build_expert_inventory(self):
        output = os.path.join(self.facts, f"{self.args.model_id}_expert_inventory.json")
        cmd = [sys.executable,
               os.path.join(self.stage2_scripts, "build_expert_inventory.py"),
               "--breakdown", self.work, "--config", self.config,
               "--performance", self.perf_fact, "--attribution", self.attribution,
               "--out", output]
        if self.args.ep_rank is not None:
            cmd += ["--ep-rank", str(self.args.ep_rank)]
        result = run(cmd)
        if result.returncode:
            die("failed", "expert_inventory", (result.stderr or result.stdout)[-800:],
                stages=self.stages)
        message = result.stdout.strip().splitlines()[-1] if result.stdout else "ok"
        self.stages["expert_inventory"] = message

    def build_graph(self):
        self.graph = os.path.join(
            self.repo, "report/outputs/model_architecture_graph.json")
        result = run([sys.executable,
                      os.path.join(self.stage2_scripts, "build_architecture_graph.py"),
                      "--analysis", self.analysis_fact, "--performance", self.perf_fact,
                      "--breakdown", self.config, "--out", self.graph])
        if result.returncode:
            die("failed", "graph", (result.stderr or result.stdout)[-800:],
                stages=self.stages)
        self.stages["graph"] = "ok"

    def check_graph_consistency(self):
        report = os.path.join(self.work, "graph_consistency.json")
        result = run([sys.executable,
                      os.path.join(STAGE1, "scripts/check_graph_consistency.py"),
                      "-g", self.graph, "-c", self.config, "-o", report])
        errors = self.graph_errors(report)
        if errors or result.returncode:
            codes = sorted({str(issue.get("id") or issue.get("code")) for issue in errors})
            self.stages["graph_consistency"] = f"errors {codes}" if codes else "failed"
            die("failed", "graph_consistency",
                "the rendered graph contradicts the config; a report built from it would show "
                "a structure the breakdown does not claim",
                report=report, error_codes=codes,
                errors=[issue.get("message") for issue in errors[:4]], stages=self.stages)
        self.stages["graph_consistency"] = "passed"

    def validate_conversion(self):
        result = run([sys.executable,
                      os.path.join(self.stage2_scripts, "validate_conversion.py"),
                      "--out", self.facts, "--attribution", self.attribution,
                      "--config", self.config])
        self.stages["conversion_validation"] = (
            "passed" if result.returncode == 0 else "failed")
        if result.returncode:
            die("failed", "conversion_validation", result.stdout[-1200:], stages=self.stages)

    def run_stage2(self):
        self.check_readiness()
        self.build_node_index()
        self.attribute_kernels()
        self.emit_facts()
        self.build_expert_inventory()
        self.build_graph()
        self.check_graph_consistency()
        self.validate_conversion()

    def require_stage3(self):
        if not os.path.isdir(self.stage3):
            die("failed", "stage3_dependency",
                f"cann-perf-ui-json-report not found at {self.stage3}; install that sibling "
                "skill or pass --stage3-dir", stages=self.stages)
        if not self.trace:
            die("failed", "ui_report",
                "no trace_view.json in the capture; stage 3 requires the raw trace and it "
                "cannot be reconstructed after the fact", stages=self.stages)

    def narrow_trace(self):
        staged_trace = os.path.join(self.repo, "trace_view.json")
        result = run([sys.executable,
                      os.path.join(self.stage2_scripts, "narrow_trace_window.py"),
                      "--trace", self.trace, "--raw-ops", self.raw,
                      "--output", staged_trace])
        if result.returncode:
            die("failed", "trace_window", (result.stderr or result.stdout)[-800:],
                stages=self.stages)
        try:
            self.stages["trace_window"] = json.loads(result.stdout)
        except (ValueError, TypeError):
            self.stages["trace_window"] = "narrowed"

    def copy_facts(self):
        for fact in (self.analysis_fact, self.perf_fact, self.timeline_fact):
            shutil.copy(fact, self.repo)

    def copy_report_template(self):
        template = os.path.join(self.stage3, "assets/report-template")
        for root, _, files in os.walk(template):
            target = os.path.join(self.repo, "report", os.path.relpath(root, template))
            os.makedirs(target, exist_ok=True)
            for name in files:
                shutil.copy(os.path.join(root, name), os.path.join(target, name))

    def hbm_search_dirs(self):
        directories = list(self.args.hbm_dir)
        if directories:
            return directories
        for probe in ("derived/hbm", "derived/correlation", "derived"):
            candidate = os.path.join(self.args.capture_dir, probe)
            if os.path.isdir(candidate):
                directories.append(candidate)
        return directories

    def record_hbm_series(self, series_path):
        try:
            with open(series_path, encoding="utf-8") as handle:
                series = json.load(handle)
            self.stages["hbm"] = {
                "bandwidth_points": len(series.get("bandwidth", {}).get("points") or []),
                "occupancy_points": len(series.get("occupancy", {}).get("points") or []),
                "peak_gbs": series.get("bandwidth", {}).get("peak_gbs"),
            }
        except (OSError, ValueError):
            self.stages["hbm"] = "built"

    def build_hbm(self):
        outputs = os.path.join(self.repo, "report", "outputs")
        os.makedirs(outputs, exist_ok=True)
        names = ["hbm_bandwidth_timeline.csv", "hbm_occupancy_timeline.csv",
                 "sample_op_mix.csv", "hbm_summary.json"]
        directories = self.hbm_search_dirs()
        found = self.find_hbm_inputs(names, directories)
        missing = [name for name in names if name not in found]
        if missing:
            self.stages["hbm"] = f"empty series: missing {missing} under {directories}"
            return
        staged = os.path.join(self.work, "hbm_inputs")
        os.makedirs(staged, exist_ok=True)
        for name, source in found.items():
            shutil.copy(source, os.path.join(staged, name))
        series_path = os.path.join(outputs, "hbm_series.json")
        result = run(["node", os.path.join(self.stage3, "scripts/build-hbm-data.mjs"),
                      "--input-dir", staged, "--out", series_path])
        if result.returncode:
            die("failed", "hbm", (result.stderr or result.stdout)[-800:], stages=self.stages)
        self.record_hbm_series(series_path)

    def build_overlay(self):
        result = run([sys.executable,
                      os.path.join(self.stage2_scripts, "build_overlay_and_config.py"),
                      "--analysis", self.analysis_fact, "--performance", self.perf_fact,
                      "--graph", self.graph, "--repo", self.repo,
                      "--file-prefix", self.args.model_id, "--write-empty-hbm"])
        if result.returncode:
            die("failed", "overlay", (result.stderr or result.stdout)[-800:],
                stages=self.stages)

    def build_bindings(self):
        trace_path = os.path.join(self.repo, "trace_view.json")
        result = run([sys.executable,
                      os.path.join(self.stage2_scripts, "build_trace_bindings.py"),
                      "--timeline", self.timeline_fact, "--attribution", self.attribution,
                      "--trace", trace_path, "--enrich-trace", trace_path,
                      "--out", os.path.join(
                          self.repo, "report/outputs/trace_bindings.json")])
        if result.returncode:
            die("failed", "bindings", (result.stderr or result.stdout)[-800:],
                stages=self.stages)
        self.stages["bindings"] = "ok"

    def assemble_report(self):
        result = run(["node", os.path.join(self.stage3, "scripts/build-embedded-data.mjs"),
                      "--repo", self.repo])
        if result.returncode:
            die("failed", "embedded_data", (result.stderr or result.stdout)[-800:],
                stages=self.stages)
        result = run(["node", os.path.join(self.stage3, "scripts/validate-report.mjs"),
                      "--repo", self.repo])
        failures = [line for line in (result.stdout or "").splitlines()
                    if line.startswith("FAIL")]
        self.stages["ui_validation"] = (
            "passed" if result.returncode == 0 else failures[:6])
        return result.returncode

    def run_stage3(self):
        self.require_stage3()
        self.copy_facts()
        self.narrow_trace()
        self.copy_report_template()
        self.build_hbm()
        self.build_overlay()
        self.build_bindings()
        return self.assemble_report()

    def execute(self):
        self.discover()
        self.run_stage1()
        self.run_stage2()
        return_code = self.run_stage3()
        logger.info(json.dumps({
            "status": "completed" if return_code == 0 else "completed_with_ui_failures",
            "stages": self.stages,
            "ui_report": os.path.join(self.repo, "report/index.html"),
            "serve": f"cd {self.repo} && python3 -m http.server 8081   # then open /report/",
        }, ensure_ascii=False, indent=1))
        return 0 if return_code == 0 else 1


def main():
    return Pipeline(parse_args()).execute()


if __name__ == "__main__":
    command_handler = logging.StreamHandler(sys.stderr)
    command_handler.setFormatter(logging.Formatter("%(message)s"))
    command_logger.addHandler(command_handler)
    command_logger.propagate = False
    sys.exit(breakdown_paths.run_cli(main))
