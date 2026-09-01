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
#
"""Changing the Skill 1 gate must not change the Skill 3 handoff."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


NEW_SKILL = Path(__file__).parents[1]
SKILL_COLLECTION = NEW_SKILL.parent
SKILL3 = SKILL_COLLECTION / "3-generate-ui-json-report"
FIXTURE = NEW_SKILL / "tests" / "fixtures" / "synthetic"
EXPECTED_HANDOFF = {
    "fixture-model_analysis_config.json",
    "fixture-model_perf_data.json",
    "fixture-model_timeline.json",
    "outputs/model_architecture_graph.json",
}


def write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def run(*args):
    return subprocess.run(
        [str(item) for item in args],
        capture_output=True,
        text=True,
        check=True,
    )


def make_formal_bundle(root):
    config = root / "analysis_config.json"
    shutil.copyfile(FIXTURE / "analysis_config_v2.json", config)
    # The original converter defaults to the versioned spelling. Identical bytes make both
    # converters consume the same reviewed config while exercising their different resolvers.
    shutil.copyfile(config, root / "analysis_config_v2.json")
    shutil.copyfile(FIXTURE / "raw_ops.json", root / "raw_ops.json")
    digest = hashlib.sha256(config.read_bytes()).hexdigest()
    write_json(root / "validation_report.json", {"status": "passed", "issues": []})
    write_json(root / "critique_report.json", {
        "status": "passed",
        "artifacts": {"analysis_config": {"sha256": digest}},
    })
    write_json(root / "critique_validation.json", {
        "status": "passed",
        "detail": {"clears_candidate": True},
    })
    write_json(root / "breakdown_score.json", {
        "status": "verified",
        "passed_at_cap": True,
        "convertible": True,
        "hard_gates": {"passed": True, "blocking_issues": []},
        "critique_gates": {"passed": True, "blocking_issues": []},
    })
    # This lets the pre-change readiness path accept the same bundle. The new path must ignore
    # it and prove readiness exclusively from the five formal files above.
    write_json(root / "semantic_review.json", {
        "status": "passed",
        "artifacts": {"analysis_config": {"sha256": digest}},
    })


def convert(skill, breakdown, work, handoff):
    scripts = skill / "scripts"
    work.mkdir()
    (handoff / "outputs").mkdir(parents=True)
    run(sys.executable, scripts / "check_breakdown_ready.py",
        "--breakdown", breakdown, "--out", work / "readiness.json")
    run(sys.executable, scripts / "build_node_index.py",
        "--breakdown", breakdown, "--namespace", "model/fixture-model",
        "--out", work / "node_index.json")
    run(sys.executable, scripts / "attribute_kernels.py",
        "--breakdown", breakdown, "--nodes", work / "node_index.json",
        "--out", work / "kernel_attribution.json")
    run(sys.executable, scripts / "emit_ui_facts.py",
        "--breakdown", breakdown, "--nodes", work / "node_index.json",
        "--attribution", work / "kernel_attribution.json",
        "--model-id", "fixture-model", "--report-id", "fixture-report",
        "--peak-bf16-tflops", "376", "--dtype-bytes", "2", "--out", handoff)
    run(sys.executable, scripts / "build_architecture_graph.py",
        "--analysis", handoff / "fixture-model_analysis_config.json",
        "--performance", handoff / "fixture-model_perf_data.json",
        "--breakdown", breakdown / "analysis_config.json",
        "--out", handoff / "outputs" / "model_architecture_graph.json")
    run(sys.executable, scripts / "validate_conversion.py",
        "--out", handoff, "--attribution", work / "kernel_attribution.json")
    run("node", SKILL3 / "scripts" / "validate-architecture-graph.mjs",
        handoff / "outputs" / "model_architecture_graph.json")


def relative_files(root):
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


def collect_values(value, keys, found=None):
    found = found or {key: [] for key in keys}
    if isinstance(value, dict):
        for key, item in value.items():
            if key in found:
                found[key].append(item)
            collect_values(item, keys, found)
    elif isinstance(value, list):
        for item in value:
            collect_values(item, keys, found)
    return found


def test_formal_input_gate_produces_the_complete_skill3_handoff(tmp_path):
    breakdown = tmp_path / "breakdown"
    breakdown.mkdir()
    make_formal_bundle(breakdown)

    handoff = tmp_path / "handoff"
    convert(NEW_SKILL, breakdown, tmp_path / "work", handoff)

    assert relative_files(handoff) == EXPECTED_HANDOFF
    for relative in sorted(EXPECTED_HANDOFF):
        document = json.loads((handoff / relative).read_bytes())
        assert collect_values(document, {
            "node_id", "owner_node_id", "model_id", "report_id", "id_namespace"
        })
