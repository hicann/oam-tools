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
import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "attribute_kernels.py"
SPEC = importlib.util.spec_from_file_location("attribute_kernels", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def run_attribution(tmp_path, monkeypatch, *, excluded=None, claim_indices=(0,)):
    breakdown = tmp_path / "breakdown"
    breakdown.mkdir()
    config = {
        "excluded_profiler_ops": excluded or [],
    }
    nodes = {"nodes": [{
        "node_id": "model/test/compute",
        "child_ids": [],
        "op_indices": list(claim_indices),
    }]}
    kernels = {"operators": [
        {"index": 0, "original_name": "MatMul", "normalized_name": "MatMul",
         "duration_us": 10.0},
        {"index": 1, "original_name": "UpdateModelParam_static_bin",
         "normalized_name": "UpdateModelParam", "duration_us": 1.0},
    ]}
    (breakdown / "analysis_config.json").write_text(json.dumps(config))
    nodes_path = tmp_path / "nodes.json"
    nodes_path.write_text(json.dumps(nodes))
    kernels_path = breakdown / "raw_ops.json"
    kernels_path.write_text(json.dumps(kernels))
    output_path = tmp_path / "attribution.json"
    monkeypatch.setattr(sys, "argv", [
        str(SCRIPT), "--breakdown", str(breakdown), "--nodes", str(nodes_path),
        "--kernels", str(kernels_path), "--out", str(output_path),
    ])
    return MODULE.main(), json.loads(output_path.read_text())


def test_canonical_operator_name_removes_profiler_graph_node_numbers():
    canonical = MODULE.canonical_operator_name

    assert canonical("Mul_8Muls") == canonical("Mul_13Muls") == "MulMuls"
    assert canonical("RealDivMul") == canonical("RealDiv_1Mul") == "RealDivMul"
    assert canonical("AddMul") == canonical("Add_1Mul") == "AddMul"
    assert canonical("Less_1LogicalOrMaskedFillSelectV2") == canonical(
        "Less_2LogicalOr_1MaskedFill_1SelectV2"
    )
    assert canonical("BatchMatMul_1_to_tranpose_batch_matmul") == (
        "BatchMatMul_to_tranpose_batch_matmul"
    )
    assert canonical("AddRmsNorm_3/AddRmsNormCast") == (
        "AddRmsNorm/AddRmsNormCast"
    )
    assert canonical("MatMulV2") == "MatMulV2"


def test_align_stream_profiles_ignores_cross_stream_issue_order():
    representative = [
        ("RmsNorm", "MatMul"),
        ("HcomAllReduce",),
        ("AivKernel",),
    ]
    instance = [
        ("RmsNorm", "MatMul"),
        ("AivKernel",),
        ("HcomAllReduce",),
    ]

    assert MODULE.align_stream_profiles(representative, instance) == [0, 2, 1]


def test_kernel_signature_includes_operator_type_and_tensor_shapes():
    base = {
        "normalized_name": "Mul_8Muls",
        "task_type": "Mul",
        "input_shapes": "1,16;1,16",
        "output_shapes": "1,16",
    }
    same = {
        **base,
        "normalized_name": "Mul_13Muls",
    }
    different_type = {**same, "task_type": "Muls"}
    different_input = {**same, "input_shapes": "1,32;1,32"}
    different_output = {**same, "output_shapes": "1,32"}

    assert MODULE.kernel_signature(base) == MODULE.kernel_signature(same)
    assert MODULE.kernel_signature(base) != MODULE.kernel_signature(different_type)
    assert MODULE.kernel_signature(base) != MODULE.kernel_signature(different_input)
    assert MODULE.kernel_signature(base) != MODULE.kernel_signature(different_output)


def test_align_stream_profile_allows_repeated_communication_stubs():
    compute = {"normalized_name": "MatMul", "task_type": "MatMul",
               "accelerator_core": "AICORE"}
    communication = {"normalized_name": "AivKernel", "task_type": "HcomAllReduce",
                     "input_shapes": "N/A", "output_shapes": "N/A",
                     "accelerator_core": "COMMUNICATION"}

    alignment = MODULE.align_stream_profile_with_communication_extras(
        [compute, communication],
        [compute, communication, communication, communication],
    )

    assert alignment == {"positions": [0, 1], "extras": [2, 3]}


def test_align_stream_profile_rejects_extra_compute_kernel():
    compute = {"normalized_name": "MatMul", "task_type": "MatMul",
               "accelerator_core": "AICORE"}

    assert MODULE.align_stream_profile_with_communication_extras(
        [compute], [compute, compute]
    ) is None


def test_instance_translation_attributes_unique_communication_extras():
    compute = {"normalized_name": "MatMul", "task_type": "MatMul",
               "accelerator_core": "AICORE", "stream_id": "6"}
    communication = {"normalized_name": "AivKernel", "task_type": "HcomAllReduce",
                     "input_shapes": "N/A", "output_shapes": "N/A",
                     "accelerator_core": "COMMUNICATION", "stream_id": "4"}
    kernels = [
        {**compute, "index": 0},
        {**communication, "index": 1},
        {**compute, "index": 2},
        {**communication, "index": 3},
        {**communication, "index": 4},
        {**communication, "index": 5},
    ]
    nodes = [
        {"node_id": "model/group", "child_ids": ["model/group/compute", "model/group/comm"]},
        {"node_id": "model/group/compute", "child_ids": [], "op_indices": [0]},
        {"node_id": "model/group/comm", "child_ids": [], "op_indices": [1]},
    ]
    config = {"trace_instances": [
        {"instance_id": "layer_0", "model_layer_index": 0,
         "layer_group_type": "group", "representative_instance_id": "layer_0",
         "op_range": [0, 1]},
        {"instance_id": "layer_1", "model_layer_index": 1,
         "layer_group_type": "group", "representative_instance_id": "layer_0",
         "op_range": [2, 5]},
    ]}
    index = {"roots": {"layer_structure": {"group": "model/group"}}}
    attributor = MODULE.Attributor(kernels, nodes)
    MODULE.apply_direct(attributor, nodes, config)

    result = MODULE.apply_instance_ranges(attributor, config, index, nodes)

    assert result == {"translated": 4, "instances": 1,
                      "communication_extras": 2}
    assert attributor.owner == {
        0: "model/group/compute", 1: "model/group/comm",
        2: "model/group/compute", 3: "model/group/comm",
        4: "model/group/comm", 5: "model/group/comm",
    }
    assert attributor.evidence[4]["kind"] == "instance_range_communication_extra"


def test_excluded_profiler_op_counts_as_covered_without_fabricating_owner(
        tmp_path, monkeypatch):
    result, output = run_attribution(
        tmp_path,
        monkeypatch,
        excluded=[{
            "op_indices": [1],
            "reason_code": "device_param_update",
            "evidence": "profiler bookkeeping between model stages",
        }],
    )

    assert result == 0
    assert output["summary"]["kernels_attributed"] == 1
    assert output["summary"]["kernels_excluded"] == 1
    assert output["summary"]["kernels_accounted"] == 2
    assert output["summary"]["attribution_pct"] == 50.0
    assert output["summary"]["accounting_coverage_pct"] == 100.0
    assert output["summary"]["coverage_pct"] == 100.0
    assert output["summary"]["excluded"] == [1]
    assert output["summary"]["unattributed"] == []
    assert [row["op_index"] for row in output["rows"]] == [0]


def test_non_excluded_unclaimed_op_still_fails(tmp_path, monkeypatch):
    result, output = run_attribution(tmp_path, monkeypatch)

    assert result == 1
    assert output["summary"]["kernels_attributed"] == 1
    assert output["summary"]["kernels_excluded"] == 0
    assert output["summary"]["coverage_pct"] == 50.0
    assert output["summary"]["unattributed"] == [1]


def test_excluded_profiler_op_must_exist_in_kernel_rows(tmp_path, monkeypatch):
    with pytest.raises(SystemExit, match="excluded op_index 99 is not in"):
        run_attribution(
            tmp_path,
            monkeypatch,
            excluded=[{"op_indices": [99], "reason_code": "device_param_update"}],
        )


def test_excluded_profiler_op_cannot_also_have_an_owner(tmp_path, monkeypatch):
    with pytest.raises(SystemExit, match="both excluded and attributed: \\[1\\]"):
        run_attribution(
            tmp_path,
            monkeypatch,
            excluded=[{"op_indices": [1], "reason_code": "device_param_update"}],
            claim_indices=(0, 1),
        )
