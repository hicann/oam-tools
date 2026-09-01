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
"""The one-shot pipeline consumes a completed Skill 1 bundle."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "run_pipeline.py"


def load_pipeline_module():
    spec = importlib.util.spec_from_file_location("run_pipeline_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pipeline_resolves_peer_skills_from_its_own_collection():
    module = load_pipeline_module()
    collection = SCRIPT.parents[2].resolve()

    assert Path(module.STAGE1).parent.resolve() == collection
    assert Path(module.STAGE3).parent.resolve() == collection
    assert "name: cann-perf-breakdown" in (Path(module.STAGE1) / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "name: cann-perf-ui-json-report" in (Path(module.STAGE3) / "SKILL.md").read_text(
        encoding="utf-8"
    )


def test_peer_skill_resolution_parses_frontmatter_and_rejects_external_symlinks(tmp_path):
    module = load_pipeline_module()
    collection = tmp_path / "skills"
    collection.mkdir()
    quoted = collection / "quoted"
    quoted.mkdir()
    (quoted / "SKILL.md").write_text(
        '---\nname: "quoted-skill"\ndescription: valid\n---\n', encoding="utf-8"
    )
    decoy = collection / "decoy"
    decoy.mkdir()
    (decoy / "SKILL.md").write_text(
        "---\nname: other\ndescription: 'name: quoted-skill'\n---\n", encoding="utf-8"
    )

    assert Path(module.find_peer_skill("quoted-skill", collection)) == quoted

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "SKILL.md").write_text(
        "---\nname: external-skill\ndescription: outside\n---\n", encoding="utf-8"
    )
    (collection / "external-link").symlink_to(outside, target_is_directory=True)

    try:
        module.find_peer_skill("external-skill", collection)
    except RuntimeError as error:
        assert "found []" in str(error)
    else:
        raise AssertionError("external symlink must not be accepted as a peer skill")


def test_help_exposes_breakdown_input_and_no_semantic_review_option():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "--breakdown" in proc.stdout
    assert "--semantic-review" not in proc.stdout


def test_help_works_without_third_party_python_packages():
    proc = subprocess.run(
        [sys.executable, "-S", str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "--breakdown" in proc.stdout


def test_pipeline_checks_readiness_before_auxiliary_conversion_inputs(tmp_path):
    breakdown = tmp_path / "breakdown"
    breakdown.mkdir()
    out = tmp_path / "out"

    proc = subprocess.run([
        sys.executable,
        str(SCRIPT),
        "--breakdown", str(breakdown),
        "--model-id", "fixture-model",
        "--out", str(out),
    ], capture_output=True, text=True)

    assert proc.returncode == 1
    result = json.loads(proc.stdout)
    assert result["status"] == "failed"
    assert result["stage"] == "readiness"
    assert not (out / "ai_mapping_request.json").exists()


def test_removed_legacy_semantic_review_flow_is_not_referenced():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "prepare_semantic_review.py" not in source
    assert "--semantic-review" not in source
    assert "awaiting_semantic_review" not in source


def test_completed_status_does_not_reference_removed_stage1_report_variable():
    source = SCRIPT.read_text(encoding="utf-8")

    assert '"breakdown_report": html' not in source


def test_pipeline_uses_formal_skill3_generator_and_stops_at_manual_gate():
    source = SCRIPT.read_text(encoding="utf-8")

    assert '"scripts/generate-report.mjs"' in source or '"generate-report.mjs"' in source
    assert '"status": "pending_manual_validation"' in source
    assert '"status": "completed"' not in source
