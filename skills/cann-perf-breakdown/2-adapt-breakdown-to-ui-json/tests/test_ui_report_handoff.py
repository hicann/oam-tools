#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
"""Skill 2 emits the versioned seven-input handoff required by new Skill 3 reports."""
import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_overlay_and_config.py"


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def test_build_overlay_emits_versioned_skill3_handoff(tmp_path):
    repo = tmp_path / "report-repo"
    analysis = tmp_path / "analysis.json"
    performance = tmp_path / "performance.json"
    graph = tmp_path / "graph.json"
    node_id = "model/fixture/stages/embedding"
    write_json(analysis, {
        "model_id": "fixture",
        "model_name": "FixtureModel",
        "report_id": "fixture/report",
        "representative_step": 3,
        "architecture": {"source_of_truth": ["models/modeling_fixture.py:10"]},
        "source_only_structure": [],
    })
    write_json(performance, {"modules": [{"node_id": node_id}]})
    write_json(graph, {
        "roots": [{"id": node_id, "sourceRefs": ["models/modeling_fixture.py:10"]}],
    })

    subprocess.run([
        sys.executable, str(SCRIPT),
        "--analysis", str(analysis),
        "--performance", str(performance),
        "--graph", str(graph),
        "--repo", str(repo),
        "--file-prefix", "fixture",
        "--extractor-model", "Codex test agent",
    ], check=True, capture_output=True, text=True)

    handoff = json.loads((repo / "ui-report-handoff.json").read_text(encoding="utf-8"))
    assert handoff["schema_version"] == "ui_report_handoff.v1"
    assert handoff["skill3_adapter"] == "generic"
    assert set(handoff["inputs"]) == {
        "analysis", "performance", "timeline", "trace", "bindings", "architecture", "overlay"
    }
    assert handoff["provenance"]["modelSource"] == "models/modeling_fixture.py:10"
    assert handoff["provenance"]["extractorModel"] == "Codex test agent"
    assert handoff["provenance"]["skills"] == [
        "cann-perf-breakdown", "cann-perf-breakdown-to-ui-json"
    ]


def test_handoff_capabilities_come_from_current_outputs(tmp_path):
    repo = tmp_path / "report-repo"
    analysis = tmp_path / "analysis.json"
    performance = tmp_path / "performance.json"
    graph = tmp_path / "graph.json"
    inventory = tmp_path / "expert_inventory.json"
    node_id = "model/fixture/layers"
    write_json(analysis, {
        "model_id": "fixture",
        "report_id": "fixture/report",
        "representative_step": 3,
        "architecture": {"source_of_truth": ["modeling_fixture.py:10"]},
        "source_only_structure": [],
    })
    write_json(performance, {
        "aicore_freq_mhz": 1850,
        "device_profile": {"derived": {"min_mhz": 1848, "max_mhz": 1852}},
        "modules": [{"node_id": node_id}],
    })
    write_json(graph, {
        "roots": [{
            "id": node_id,
            "repeatCount": 2,
            "sourceRefs": ["modeling_fixture.py:10"],
        }],
    })
    write_json(inventory, {"available": True})

    subprocess.run([
        sys.executable, str(SCRIPT),
        "--analysis", str(analysis),
        "--performance", str(performance),
        "--graph", str(graph),
        "--repo", str(repo),
        "--expert-inventory", str(inventory),
    ], check=True, capture_output=True, text=True)

    handoff = json.loads((repo / "ui-report-handoff.json").read_text(encoding="utf-8"))
    assert handoff["capabilities"] == {
        "repeatedLayers": True,
        "expertInventory": True,
        "aicoreFrequency": True,
    }


def test_declared_only_frequency_does_not_claim_derived_range_capability(tmp_path):
    repo = tmp_path / "report-repo"
    analysis = tmp_path / "analysis.json"
    performance = tmp_path / "performance.json"
    graph = tmp_path / "graph.json"
    node_id = "model/fixture/stages/embedding"
    write_json(analysis, {
        "model_id": "fixture",
        "report_id": "fixture/report",
        "representative_step": 3,
        "architecture": {"source_of_truth": ["modeling_fixture.py:10"]},
        "source_only_structure": [],
    })
    write_json(performance, {
        "aicore_freq_mhz": 1850,
        "device_profile": {
            "declared": {"mhz": 1850},
            "derived": {"min_mhz": None, "max_mhz": None},
        },
        "modules": [{"node_id": node_id}],
    })
    write_json(graph, {
        "roots": [{"id": node_id, "sourceRefs": ["modeling_fixture.py:10"]}],
    })

    subprocess.run([
        sys.executable, str(SCRIPT),
        "--analysis", str(analysis),
        "--performance", str(performance),
        "--graph", str(graph),
        "--repo", str(repo),
    ], check=True, capture_output=True, text=True)

    handoff = json.loads((repo / "ui-report-handoff.json").read_text(encoding="utf-8"))
    assert handoff["capabilities"]["aicoreFrequency"] is False
