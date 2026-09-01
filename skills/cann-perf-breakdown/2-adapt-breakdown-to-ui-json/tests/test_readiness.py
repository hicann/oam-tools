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
"""Skill 2 accepts only the formal five-file Skill 1 handoff."""
import hashlib
import json
import os
import subprocess
import sys

import pytest


SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS)
import breakdown_paths  # noqa: E402
import check_breakdown_ready as readiness  # noqa: E402


def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def passing_score():
    return {
        "status": "verified",
        "passed_at_cap": True,
        "convertible": True,
        "hard_gates": {"passed": True, "blocking_issues": []},
        "critique_gates": {"passed": True, "blocking_issues": []},
    }


def make_breakdown(tmp_path, config_name="analysis_config.json"):
    config = {
        "schema_version": 2,
        "architecture": {},
        "trace_scope": {"kind": "unknown"},
        "structures": {},
        "stages": {},
        "runtime_auxiliary": [],
        "unmapped_ops": [],
    }
    config_path = tmp_path / config_name
    write_json(config_path, config)
    write_json(tmp_path / "validation_report.json", {"status": "passed", "issues": []})
    write_json(tmp_path / "critique_report.json", {
        "schema_version": 1,
        "status": "passed",
        "artifacts": {
            "analysis_config": {
                "path": str(config_path),
                "sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
            }
        },
    })
    write_json(tmp_path / "critique_validation.json", {
        "status": "passed",
        "error_count": 0,
        "detail": {"clears_candidate": True},
    })
    write_json(tmp_path / "breakdown_score.json", passing_score())
    return config_path


def blockers(tmp_path, config_override=None):
    return readiness.check(str(tmp_path), config_override)[1]


def test_accepts_formal_five_file_handoff(tmp_path):
    make_breakdown(tmp_path)

    assert blockers(tmp_path) == []


@pytest.mark.parametrize("filename", [
    "analysis_config.json",
    "validation_report.json",
    "critique_report.json",
    "critique_validation.json",
    "breakdown_score.json",
])
def test_requires_each_formal_file(tmp_path, filename):
    make_breakdown(tmp_path)
    (tmp_path / filename).unlink()

    assert blockers(tmp_path)


def test_rejects_passed_with_warnings_validation(tmp_path):
    make_breakdown(tmp_path)
    write_json(tmp_path / "validation_report.json", {
        "status": "passed_with_warnings",
        "issues": [],
    })

    assert any("validation status passed" in item for item in blockers(tmp_path))


def test_rejects_failed_critique_report(tmp_path):
    make_breakdown(tmp_path)
    critique = json.loads((tmp_path / "critique_report.json").read_text())
    critique["status"] = "failed"
    write_json(tmp_path / "critique_report.json", critique)

    assert any("critique status passed" in item for item in blockers(tmp_path))


@pytest.mark.parametrize("mutation, expected", [
    ({"status": "failed", "detail": {"clears_candidate": True}},
     "critique validation status passed"),
    ({"status": "passed", "detail": {"clears_candidate": False}},
     "critique validation clears candidate"),
    ({"status": "passed", "detail": {}},
     "critique validation clears candidate"),
])
def test_rejects_invalid_critique_validation(tmp_path, mutation, expected):
    make_breakdown(tmp_path)
    write_json(tmp_path / "critique_validation.json", mutation)

    assert any(expected in item for item in blockers(tmp_path))


@pytest.mark.parametrize("field_path", [
    ("passed_at_cap",),
    ("convertible",),
    ("hard_gates", "passed"),
    ("critique_gates", "passed"),
])
def test_rejects_each_false_score_gate(tmp_path, field_path):
    make_breakdown(tmp_path)
    score = passing_score()
    target = score
    for key in field_path[:-1]:
        target = target[key]
    target[field_path[-1]] = False
    write_json(tmp_path / "breakdown_score.json", score)

    assert any("score formal gates passed" in item for item in blockers(tmp_path))


def test_shared_readiness_gate_uses_all_four_formal_score_flags(tmp_path):
    make_breakdown(tmp_path)
    score = passing_score()
    score["critique_gates"]["passed"] = False
    write_json(tmp_path / "breakdown_score.json", score)

    with pytest.raises(SystemExit):
        breakdown_paths.require_breakdown_ready(str(tmp_path), script="test")


def test_rejects_legacy_semantic_review_as_formal_input(tmp_path):
    config_path = make_breakdown(tmp_path)
    (tmp_path / "critique_report.json").unlink()
    (tmp_path / "critique_validation.json").unlink()
    write_json(tmp_path / "semantic_review.json", {
        "status": "passed",
        "artifacts": {
            "analysis_config": {
                "sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
            }
        },
    })

    blocked = blockers(tmp_path)
    assert any("critique_report.json exists" in item for item in blocked)
    assert any("critique_validation.json exists" in item for item in blocked)


def test_rejects_targeted_critique_as_formal_input(tmp_path):
    make_breakdown(tmp_path)
    (tmp_path / "critique_report.json").unlink()
    (tmp_path / "critique_validation.json").unlink()
    write_json(tmp_path / "targeted_critique_report.json", {"status": "passed"})
    write_json(tmp_path / "targeted_critique_validation.json", {
        "status": "passed",
        "detail": {"clears_scope": True},
    })

    blocked = blockers(tmp_path)
    assert any("critique_report.json exists" in item for item in blocked)
    assert any("critique_validation.json exists" in item for item in blocked)


def test_rejects_critique_bound_to_a_different_config(tmp_path):
    make_breakdown(tmp_path)
    config_path = tmp_path / "analysis_config.json"
    config = json.loads(config_path.read_text())
    config["architecture"] = {"changed": True}
    write_json(config_path, config)

    assert any("critique still matches the config" in item for item in blockers(tmp_path))


def test_analysis_config_is_the_default_even_when_legacy_name_exists(tmp_path):
    current = make_breakdown(tmp_path)
    write_json(tmp_path / "analysis_config_v2.json", {"schema_version": 2, "legacy": True})

    assert breakdown_paths.resolve_config(str(tmp_path)) == str(current)


def test_legacy_config_name_requires_an_explicit_path(tmp_path):
    legacy = make_breakdown(tmp_path, config_name="analysis_config_v2.json")

    assert breakdown_paths.resolve_config(str(tmp_path)) is None
    assert blockers(tmp_path, str(legacy)) == []


def artifact_entrypoint_args(script, breakdown, tmp_path):
    common = [sys.executable, os.path.join(SCRIPTS, script)]
    if script == "build_node_index.py":
        return common + [
            "--breakdown", str(breakdown),
            "--namespace", "model/fixture-model",
            "--out", str(tmp_path / "node_index.json"),
        ]
    if script == "emit_ui_facts.py":
        return common + [
            "--breakdown", str(breakdown),
            "--nodes", str(tmp_path / "missing-nodes.json"),
            "--attribution", str(tmp_path / "missing-attribution.json"),
            "--model-id", "fixture-model",
            "--report-id", "fixture-report",
            "--out", str(tmp_path / "handoff"),
        ]
    if script == "build_expert_inventory.py":
        return common + [
            "--breakdown", str(breakdown),
            "--performance", str(tmp_path / "missing-performance.json"),
            "--attribution", str(tmp_path / "missing-attribution.json"),
            "--out", str(tmp_path / "expert_inventory.json"),
        ]
    return common + [
        "--analysis", str(tmp_path / "missing-analysis.json"),
        "--performance", str(tmp_path / "missing-performance.json"),
        "--breakdown", str(breakdown / "analysis_config.json"),
        "--out", str(tmp_path / "model_architecture_graph.json"),
    ]


@pytest.mark.parametrize("script", [
    "build_node_index.py",
    "emit_ui_facts.py",
    "build_architecture_graph.py",
    "build_expert_inventory.py",
])
def test_artifact_entrypoints_require_the_complete_formal_handoff(tmp_path, script):
    breakdown = tmp_path / "breakdown"
    breakdown.mkdir()
    make_breakdown(breakdown)
    (breakdown / "critique_report.json").unlink()

    proc = subprocess.run(
        artifact_entrypoint_args(script, breakdown, tmp_path),
        capture_output=True,
        text=True,
    )

    assert proc.returncode != 0
    assert "critique_report.json exists" in proc.stderr


@pytest.mark.parametrize("script", [
    "build_node_index.py",
    "emit_ui_facts.py",
    "build_architecture_graph.py",
    "build_expert_inventory.py",
])
def test_artifact_entrypoints_do_not_offer_an_unscored_bypass(script):
    proc = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, script), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "--allow-unscored" not in proc.stdout
