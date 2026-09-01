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
"""Architecture graph preserves declared cross-structure branch endpoints."""
import os
import sys

import pytest


SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS)
import build_architecture_graph as graph  # noqa: E402


def leaf(node_id, name):
    return {
        "node_id": node_id,
        "name": name,
        "node_kind": "op",
        "code_ref": "model.py:1",
        "children": [],
    }


def module(node_id, name, children):
    return {
        "node_id": node_id,
        "name": name,
        "node_kind": "module",
        "code_ref": "model.py:1",
        "children": children,
    }


def test_resolves_cross_structure_path_and_preserves_cross_invocation():
    source_id = "model/m/moe/tail"
    target_id = "model/m/moe_final/join"
    analysis = {
        "_metric_node_ids": [source_id, target_id],
        "architecture": {"source_of_truth": ["model.py:1"]},
        "stages": {},
        "layer_structure": {
            "moe": module("model/m/moe", "moe", [leaf(source_id, "tail")]),
            "moe_final": module(
                "model/m/moe_final",
                "moe_final",
                [leaf("model/m/moe_final/body", "body"), leaf(target_id, "join")],
            ),
        },
        "runtime_auxiliary": [],
    }
    breakdown = {
        "structures": {
            "moe": {"name": "moe", "children": [{"name": "tail"}]},
            "moe_final": {
                "name": "moe_final",
                "children": [{"name": "body"}, {"name": "join"}],
                "branches": [{
                    "name": "carry",
                    "kind": "cross_invocation",
                    "invocation_offset": 1,
                    "inputs": ["structures/moe/tail"],
                    "output": "join",
                    "source_ref": "model.py:2",
                }],
            },
        }
    }

    result = graph.build(analysis, breakdown)
    carry = next(edge for edge in result["edges"]
                 if edge["semanticEdgeType"] == "residual")

    assert carry["source"] == source_id
    assert carry["target"] == target_id
    assert carry["crossInvocation"] is True
    assert carry["crossStep"] == 1


def test_parallel_branch_rejoins_from_parallel_member_not_fork_point():
    prefix = "model/m/moe/mlp"
    analysis = {
        "_metric_node_ids": [],
        "architecture": {"source_of_truth": ["model.py:1"]},
        "stages": {},
        "layer_structure": {
            "moe": module("model/m/moe", "moe", [
                module(prefix, "mlp", [
                    leaf(f"{prefix}/gate", "gate"),
                    leaf(f"{prefix}/shared_expert", "shared_expert"),
                    leaf(f"{prefix}/routed_experts", "routed_experts"),
                    leaf(f"{prefix}/combine", "combine"),
                ]),
            ]),
        },
        "runtime_auxiliary": [],
    }
    breakdown = {
        "structures": {
            "moe": {
                "name": "moe",
                "children": [{
                    "name": "mlp",
                    "children": [
                        {"name": "gate"},
                        {"name": "shared_expert"},
                        {"name": "routed_experts"},
                        {"name": "combine"},
                    ],
                    "parallel_siblings": [{
                        "name": "experts",
                        "members": ["shared_expert", "routed_experts"],
                    }],
                    "branches": [{
                        "name": "shared_path",
                        "kind": "parallel",
                        "inputs": ["gate"],
                        "output": "combine",
                        "source_ref": "model.py:2",
                    }],
                }],
            },
        },
    }

    result = graph.build(analysis, breakdown)
    pairs = {(edge["source"], edge["target"]) for edge in result["edges"]}

    assert (f"{prefix}/shared_expert", f"{prefix}/combine") in pairs
    assert (f"{prefix}/gate", f"{prefix}/combine") not in pairs


def test_explicit_parallel_edges_replace_false_serial_edges_and_duplicate_join():
    prefix = "model/m/layer"
    children = [
        leaf(f"{prefix}/fork", "fork"),
        leaf(f"{prefix}/dense", "dense"),
        leaf(f"{prefix}/dense_tail", "dense_tail"),
        leaf(f"{prefix}/moe", "moe"),
        leaf(f"{prefix}/moe_tail", "moe_tail"),
        leaf(f"{prefix}/join", "join"),
    ]
    analysis = {
        "_metric_node_ids": [child["node_id"] for child in children],
        "architecture": {"source_of_truth": ["model.py:1"]},
        "stages": {},
        "layer_structure": {"layer": module(prefix, "layer", children)},
        "runtime_auxiliary": [],
    }
    breakdown = {
        "structures": {
            "layer": {
                "name": "layer",
                "children": [{"name": child["name"]} for child in children],
                "branches": [
                    {
                        "name": "fork_to_moe",
                        "kind": "parallel",
                        "inputs": ["fork"],
                        "output": "moe",
                        "source_ref": "model.py:2",
                    },
                    {
                        "name": "parallel_join",
                        "kind": "parallel",
                        "inputs": ["dense_tail", "moe_tail"],
                        "output": "join",
                        "source_ref": "model.py:3",
                    },
                ],
            },
        },
    }

    result = graph.build(analysis, breakdown)
    endpoint_pairs = [(edge["source"], edge["target"]) for edge in result["edges"]]

    assert (f"{prefix}/fork", f"{prefix}/dense") in endpoint_pairs
    assert (f"{prefix}/fork", f"{prefix}/moe") in endpoint_pairs
    assert (f"{prefix}/dense_tail", f"{prefix}/moe") not in endpoint_pairs
    assert endpoint_pairs.count((f"{prefix}/dense_tail", f"{prefix}/join")) == 1
    assert endpoint_pairs.count((f"{prefix}/moe_tail", f"{prefix}/join")) == 1


def test_distinct_branch_declarations_with_same_endpoints_have_unique_edge_ids():
    prefix = "model/m/layer"
    children = [leaf(f"{prefix}/mlp", "mlp"), leaf(f"{prefix}/merge", "merge")]
    analysis = {
        "_metric_node_ids": [child["node_id"] for child in children],
        "architecture": {"source_of_truth": ["model.py:1"]},
        "stages": {},
        "layer_structure": {"layer": module(prefix, "layer", children)},
        "runtime_auxiliary": [],
    }
    breakdown = {
        "structures": {
            "layer": {
                "name": "layer",
                "children": [{"name": "mlp"}, {"name": "merge"}],
                "branches": [
                    {"name": "three_way_merge", "kind": "residual",
                     "inputs": ["mlp"], "output": "merge", "source_ref": "model.py:2"},
                    {"name": "shortcut_to_merge", "kind": "skip",
                     "inputs": ["mlp"], "output": "merge", "source_ref": "model.py:3"},
                ],
            },
        },
    }

    result = graph.build(analysis, breakdown)
    declared = [edge for edge in result["edges"]
                if edge["semanticEdgeType"] == "residual"]

    assert len(declared) == 2
    assert len({edge["id"] for edge in declared}) == 2
    assert {edge["provenance"][0] for edge in declared} == {
        "structures.layer.branches: three_way_merge",
        "structures.layer.branches: shortcut_to_merge",
    }


def test_explicit_top_level_dataflow_preserves_ports_and_orders_roots():
    tail_id = "model/m/moe_final/post_attention_layernorm"
    final_norm_id = "model/m/stages/final_norm"
    lm_head_id = "model/m/stages/lm_head"
    analysis = {
        "_metric_node_ids": [tail_id, final_norm_id, lm_head_id],
        "architecture": {"source_of_truth": ["model.py:1"]},
        "stages": {
            "final_norm": leaf(final_norm_id, "final_norm"),
            "lm_head": leaf(lm_head_id, "lm_head"),
        },
        "layer_structure": {
            "moe_final": module(
                "model/m/moe_final",
                "moe_final",
                [leaf(tail_id, "post_attention_layernorm")],
            ),
        },
        "runtime_auxiliary": [],
        "dataflow": {
            "nodes": [
                {"id": "tail", "structure": "moe_final"},
                {"id": "norm", "structure": "final_norm"},
                {"id": "head", "structure": "lm_head"},
            ],
            "edges": [
                {
                    "source": "tail",
                    "source_port": "post_attention_layernorm",
                    "target": "norm",
                    "kind": "residual",
                    "source_ref": "model.py:2",
                },
                {
                    "source": "norm",
                    "target": "head",
                    "kind": "activation",
                    "source_ref": "model.py:3",
                },
            ],
        },
    }

    result = graph.build(analysis, {"structures": {}})
    dataflow_edges = [edge for edge in result["edges"]
                      if edge["id"].startswith("dataflow::")]

    assert [(edge["source"], edge["target"], edge["semanticEdgeType"])
            for edge in dataflow_edges] == [
        (tail_id, final_norm_id, "residual"),
        (final_norm_id, lm_head_id, "activation"),
    ]
    assert dataflow_edges[0]["dashed"] is True
    assert dataflow_edges[0]["provenance"][-1] == "model.py:2"

    positions = {item["id"]: item["y"]
                 for item in result["nodes"] + result["clusters"]}
    assert positions[tail_id] < positions[final_norm_id] < positions[lm_head_id]


def test_runtime_carry_preserves_declared_invocation_offset():
    source_id = "model/m/stages/source"
    target_id = "model/m/stages/target"
    analysis = {
        "_metric_node_ids": [source_id, target_id],
        "architecture": {"source_of_truth": ["model.py:1"]},
        "stages": {
            "source": leaf(source_id, "source"),
            "target": leaf(target_id, "target"),
        },
        "layer_structure": {},
        "runtime_auxiliary": [],
        "dataflow": {
            "nodes": [
                {"id": "source", "structure": "source"},
                {"id": "target", "structure": "target"},
            ],
            "edges": [{
                "source": "source",
                "target": "target",
                "kind": "runtime_carry",
                "invocation_offset": 3,
                "source_ref": "model.py:4",
            }],
        },
    }

    result = graph.build(analysis, {"structures": {}})
    carry = next(edge for edge in result["edges"] if edge["id"].startswith("dataflow::"))

    assert carry["crossInvocation"] is True
    assert carry["crossStep"] == 3


def test_dataflow_port_must_belong_to_its_endpoint_structure():
    a_id = "model/m/a"
    b_id = "model/m/b"
    analysis = {
        "_metric_node_ids": [],
        "architecture": {"source_of_truth": ["model.py:1"]},
        "stages": {},
        "layer_structure": {
            "a": module(a_id, "a", [leaf(f"{a_id}/out", "out")]),
            "b": module(b_id, "b", [leaf(f"{b_id}/in", "in")]),
        },
        "runtime_auxiliary": [],
        "dataflow": {
            "nodes": [
                {"id": "a", "structure": "a"},
                {"id": "b", "structure": "b"},
            ],
            "edges": [{
                "source": "a",
                "source_port": "structures/b/in",
                "target": "b",
                "kind": "activation",
                "source_ref": "model.py:5",
            }],
        },
    }

    with pytest.raises(SystemExit, match="does not resolve inside a"):
        graph.build(analysis, {"structures": {}})
