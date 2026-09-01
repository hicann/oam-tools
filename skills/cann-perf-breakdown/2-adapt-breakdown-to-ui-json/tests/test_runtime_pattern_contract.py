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
import os
import sys

import pytest


SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS)

import build_architecture_graph as graph  # noqa: E402
import build_node_index as node_index  # noqa: E402
import emit_ui_facts  # noqa: E402


def config_with_unknown_pattern():
    return {
        "schema_version": 2,
        "architecture": {
            "layer_groups": [{
                "type": "Decoder_moe",
                "model_layer_range": [0, 27],
            }],
            "prediction_modules": [],
        },
        "structures": {
            "Decoder_B": {
                "name": "Decoder_B",
                "architecture_group_type": "Decoder_moe",
                "runtime_pattern": "B",
                "children": [{"name": "attn", "op_indices": [10]}],
            },
        },
        "trace_instances": [
            {"instance_id": "li_2", "model_layer_index": "unknown",
             "invocation_index": 2, "layer_group_type": "Decoder_B"},
            {"instance_id": "li_4", "model_layer_index": "unknown",
             "invocation_index": 4, "layer_group_type": "Decoder_B"},
        ],
    }


def test_unknown_invocations_do_not_become_fabricated_layer_indices():
    builder, roots, all_observed = node_index.build(
        config_with_unknown_pattern(), "model/longcat")
    root = builder.by_id[roots["layer_structure"]["Decoder_B"]]

    assert all_observed == []
    assert root["instance_indices"] == []
    assert root["invocation_count"] == 2
    assert root["architecture_group_type"] == "Decoder_moe"
    assert root["runtime_pattern"] == "B"


def test_ui_fact_and_graph_preserve_template_and_learned_owner():
    builder, roots, _ = node_index.build(config_with_unknown_pattern(), "model/longcat")
    root_id = roots["layer_structure"]["Decoder_B"]
    root = builder.by_id[root_id]
    root["mapped_kernels"] = 1
    emitted = emit_ui_facts.strip(root)
    emitted["children"] = []

    assert emitted["structure_key"] == "Decoder_B"
    assert emitted["architecture_group_type"] == "Decoder_moe"
    assert emitted["runtime_pattern"] == "B"

    analysis = {
        "_metric_node_ids": [root_id],
        "stages": {},
        "layer_structure": {"Decoder_B": emitted},
        "runtime_auxiliary": [],
    }
    result = graph.build(analysis, config_with_unknown_pattern())
    item = result["roots"][0]["children"][0]
    assert item["structureKey"] == "Decoder_B"
    assert item["architectureGroupType"] == "Decoder_moe"
    assert item["runtimePattern"] == "B"


def test_unobserved_pattern_does_not_inherit_another_patterns_layer_indices():
    config = config_with_unknown_pattern()
    config["structures"] = {
        "Decoder_A": {
            "name": "Decoder_A",
            "architecture_group_type": "Decoder_moe",
            "runtime_pattern": "A",
            "children": [{"name": "attn", "op_indices": [10]}],
        },
        "Decoder_B": config["structures"]["Decoder_B"],
    }
    config["trace_instances"] = [{
        "instance_id": "li_2",
        "model_layer_index": 2,
        "invocation_index": 2,
        "layer_group_type": "Decoder_B",
    }]

    builder, roots, all_observed = node_index.build(config, "model/longcat")
    pattern_a = builder.by_id[roots["layer_structure"]["Decoder_A"]]
    pattern_b = builder.by_id[roots["layer_structure"]["Decoder_B"]]

    assert all_observed == [2]
    assert pattern_a["instance_indices"] == []
    assert pattern_a["invocation_count"] == 0
    assert pattern_b["instance_indices"] == [2]
    assert pattern_b["invocation_count"] == 1
    assert pattern_a["declared_instance_indices"] == []
    assert pattern_b["declared_instance_indices"] == []


def test_pattern_layer_index_must_belong_to_its_learned_owner():
    config = config_with_unknown_pattern()
    config["trace_instances"] = [{
        "instance_id": "li_bad",
        "model_layer_index": 99,
        "invocation_index": 0,
        "layer_group_type": "Decoder_B",
    }]

    with pytest.raises(SystemExit, match="architecture does not declare"):
        node_index.build(config, "model/longcat")
