#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
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

import pytest
import sys

from conftest import MSAICERR_PATH
from ms_interface.aic_error_info import (
    AicErrorInfo,
    CORRECTED_PC_NOTICE,
    detect_core_err_type,
)
from ms_interface.constant import RetCode

sys.path.append(MSAICERR_PATH)

# private members reached by name to avoid direct protected-member access
GET_ARGS_STR = "_get_args_str"
GET_TILING_STR = "_get_tiling_str"
GET_ADDR_CHECK_STR = "_get_addr_check_str"
GET_AICERROR_INFO = "_get_aicerror_info"
ANALYSE_IFU = "_analyse_ifu_errinfo"
ANALYSE_MTE = "_analyse_mte_errinfo"
ANALYSE_BIU = "_analyse_biu_errinfo"
ANALYSE_CCU = "_analyse_ccu_errinfo"
ANALYSE_CUBE = "_analyse_cube_errinfo"
ANALYSE_VEC = "_analyse_vec_errinfo"


def test_get_args_str_empty():
    assert getattr(AicErrorInfo, GET_ARGS_STR)([]) == "[]"


def test_get_args_str_values():
    result = getattr(AicErrorInfo, GET_ARGS_STR)(["0x1", "0x2"])
    assert result == "[[0x1],[0x2]]"


def test_get_tiling_str_no_data():
    info = AicErrorInfo()
    info.tiling_data = ""
    assert getattr(info, GET_TILING_STR)() == "\n"


def test_get_tiling_str_with_data(mocker):
    info = AicErrorInfo()
    info.tiling_data = "tiling.bin"
    mocker.patch("builtins.open", mocker.mock_open(read_data=b"\x01\x00\x00\x00"))
    result = getattr(info, GET_TILING_STR)()
    assert "tiling data in int32" in result
    assert "tiling data in int64" in result
    assert "tiling data in float16" in result


def test_get_addr_check_str_empty():
    info = AicErrorInfo()
    info.necessary_addr = {}
    assert getattr(info, GET_ADDR_CHECK_STR)() == "\n"


def test_get_addr_check_str_in_range():
    info = AicErrorInfo()
    info.necessary_addr = {
        "input_addr": [{"index": "0", "in_range": True, "size": "16", "addr": "0x100"}],
        "output_addr": [{"index": "0", "in_range": True, "size": "16", "addr": "256"}],
    }
    result = getattr(info, GET_ADDR_CHECK_STR)()
    assert "input[0] addr" in result
    assert "output[0] addr" in result
    assert info.addr_valid is True


def test_get_addr_check_str_out_of_range():
    info = AicErrorInfo()
    info.necessary_addr = {
        "input_addr": [
            {"index": "0", "in_range": False, "size": "16", "addr": "0x100"}
        ],
        "output_addr": [
            {"index": "1", "in_range": False, "size": "16", "addr": "0x200"}
        ],
    }
    result = getattr(info, GET_ADDR_CHECK_STR)()
    assert "out of range" in result
    assert info.addr_valid is False


def test_get_addr_check_str_fault_args_and_workspace():
    info = AicErrorInfo()
    info.necessary_addr = {
        "input_addr": [],
        "output_addr": [],
        "fault_arg_index": [0],
        "need_check_args": [0x1234],
        "workspace": 512,
    }
    result = getattr(info, GET_ADDR_CHECK_STR)()
    assert "cannot find alloc log" in result
    assert "workspace_bytes:512" in result


def test_get_aicerror_info_default(mocker):
    info = AicErrorInfo()
    mocker.patch("ms_interface.utils.hexstr_to_list_bin", return_value=[])
    result = getattr(info, GET_AICERROR_INFO)()
    assert isinstance(result, str)


def test_analyse_full(mocker):
    info = AicErrorInfo()
    mocker.patch.object(info, GET_AICERROR_INFO, return_value="AICERR")
    mocker.patch.object(info, GET_ADDR_CHECK_STR, return_value="ADDR")
    mocker.patch.object(info, GET_TILING_STR, return_value="TILING")
    msg = info.analyse()
    assert "Basic information" in msg
    assert "AICERR" in msg
    assert "ADDR" in msg


def test_ifu_not_found():
    info = AicErrorInfo()
    info.extra_info = "no key here"
    assert getattr(info, ANALYSE_IFU)() == "No IFU_ERR_INFO found"


def test_mte_not_found():
    info = AicErrorInfo()
    info.extra_info = "no key here"
    assert getattr(info, ANALYSE_MTE)(46) == "No MTE_ERR_INFO found"


def test_biu_not_found():
    info = AicErrorInfo()
    info.extra_info = "no key here"
    assert getattr(info, ANALYSE_BIU)() == "No BIU_ERR_INFO found"


def test_ccu_not_found():
    info = AicErrorInfo()
    info.extra_info = "no key here"
    assert getattr(info, ANALYSE_CCU)() == "No CCU_ERR_INFO found"


def test_cube_not_found():
    info = AicErrorInfo()
    info.extra_info = "no key here"
    assert getattr(info, ANALYSE_CUBE)() == "No CUBE_ERR_INFO found"


def test_vec_not_found():
    info = AicErrorInfo()
    info.extra_info = "no key here"
    assert getattr(info, ANALYSE_VEC)() == "No VEC_ERR_INFO found"


def test_mte_err_bit_default():
    info = AicErrorInfo()
    info.extra_info = "MTE_ERR_INFO=0x1"
    # err_bit not in known set -> mte_dict empty -> info "NA"
    result = getattr(info, ANALYSE_MTE)(999)
    assert "NA" in result


def test_conclusion_atomic_add_err():
    info = AicErrorInfo()
    info.atomic_clean_check = True
    info.flag_check = False
    info.atomic_add_err = True
    assert "Atomic add" in info.get_conclusion()


def test_conclusion_single_op_success():
    info = AicErrorInfo()
    info.atomic_clean_check = True
    info.flag_check = False
    info.atomic_add_err = False
    info.aic_error_info = {"current_pc": "0x10"}
    info.dump_info = ""
    info.single_op_test_result = RetCode.FAILED
    assert "single-operator test case" in info.get_conclusion().lower()


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("aicore", "aic"),
        ("aic", "aic"),
        ("aivec", "aiv"),
        ("aivector", "aiv"),
        ("AIV", "aiv"),
        ("aivECTOR", "aiv"),
        ("", "aic"),
        (None, "aic"),
        ("unknown", "aic"),
    ],
)
def test_detect_core_err_type(raw, expected):
    assert detect_core_err_type(raw) == expected


def test_group_core_id_lines_aiv_in_cores_aiv():
    info = AicErrorInfo()
    group = {
        "records": [{"core_err_type": "aiv"}],
        "cores_aic": [],
        "cores_aiv": ["1", "2"],
    }
    result = getattr(info, "_group_core_id_lines")(group)
    assert "core id(aiv)      : [1, 2]" in result
    assert "core id(aic)" not in result


def test_group_core_id_lines_mixed():
    info = AicErrorInfo()
    group = {
        "records": [{"core_err_type": "aic"}],
        "cores_aic": ["0", "1", "2"],
        "cores_aiv": ["1", "2"],
    }
    result = getattr(info, "_group_core_id_lines")(group)
    assert "core id(aic)      : [0, 1, 2]" in result
    assert "core id(aiv)      : [1, 2]" in result
    # 两行的冒号需对齐（标签等宽填充）。
    assert "core id(aiv)      :" in result.replace("core id(aic)      :", "")


def test_get_group_dfx_lists_aic_and_aiv_cores():
    from ms_interface.constant import Constant

    info = AicErrorInfo()
    info.aic_error_groups = [
        (
            "0x10",
            {
                "records": [{"error_code": "0x10", "core_err_type": "aic"}],
                "cores_aic": ["0", "1"],
                "cores_aiv": ["1"],
            },
        )
    ]
    # 只关心表头结构，desc 的位号名取决于 AIC_ERROR_INFO_DICT 内容。
    result = getattr(info, "_get_group_dfx")("default")
    assert "AIC_ERROR         : 0x10" in result
    assert "core id(aic)      : [0, 1]" in result
    assert "core id(aiv)      : [1]" in result
    assert Constant.AIC_ERROR_INFO_DICT is not None


def test_get_group_pc_marks_core_type():
    info = AicErrorInfo()
    info.aic_error_groups = [
        (
            "0x10",
            {
                "records": [
                    {"error_code": "0x10", "core_err_type": "aiv", "core_id": "3"}
                ],
                "cores_aic": [],
                "cores_aiv": ["3"],
            },
        )
    ]
    info.corrected_pc = {}
    result = getattr(info, "_get_group_pc")()
    assert "AIC_ERROR         : 0x10" in result
    assert "core id(aiv)      : 3" in result


def test_get_group_pc_labels_aligned():
    info = AicErrorInfo()
    info.aic_error_groups = [
        (
            "0x10",
            {
                "records": [
                    {
                        "error_code": "0x10",
                        "core_err_type": "aic",
                        "core_id": "0",
                        "start_pc": "0x100",
                        "current_pc": "0x110",
                    }
                ],
                "cores_aic": ["0"],
                "cores_aiv": [],
                "corrected_pc": {"start_pc": "0x100", "current_pc": "0x120"},
            },
        ),
        (
            "0x20",
            {
                "records": [
                    {
                        "error_code": "0x20",
                        "core_err_type": "aiv",
                        "core_id": "1",
                        "start_pc": "0x200",
                        "current_pc": "0x210",
                    }
                ],
                "cores_aic": [],
                "cores_aiv": ["1"],
                "corrected_pc": {"start_pc": "0x200", "current_pc": "0x240"},
            },
        ),
    ]
    result = getattr(info, "_get_group_pc")()
    # AIC_ERROR、core id(aic/aiv) 的冒号列一致（标签 18 位填充），与
    # Basic information / start pc 冒号列对齐
    lines = [
        line
        for line in result.splitlines()
        if line.startswith("AIC_ERROR")
        or line.startswith("core id(")
        or line.startswith("current pc")
        or line.startswith("start pc")
    ]
    colon_cols = {line.index(":") for line in lines}
    assert colon_cols == {18}
    assert "AIC_ERROR         : 0x10" in result
    assert "core id(aic)      : 0" in result
    assert "AIC_ERROR         : 0x20" in result
    assert "core id(aiv)      : 1" in result


def test_get_group_pc_uses_per_group_corrected_pc():
    info = AicErrorInfo()
    info.aic_error_groups = [
        (
            "0x10",
            {
                "records": [
                    {
                        "error_code": "0x10",
                        "core_err_type": "aic",
                        "core_id": "0",
                        "start_pc": "0x100",
                        "current_pc": "0x110",
                    }
                ],
                "cores_aic": ["0"],
                "cores_aiv": [],
                "corrected_pc": {"start_pc": "0x100", "current_pc": "0x120"},
            },
        ),
        (
            "0x20",
            {
                "records": [
                    {
                        "error_code": "0x20",
                        "core_err_type": "aiv",
                        "core_id": "1",
                        "start_pc": "0x200",
                        "current_pc": "0x210",
                    }
                ],
                "cores_aic": [],
                "cores_aiv": ["1"],
                "corrected_pc": {"start_pc": "0x200", "current_pc": "0x240"},
            },
        ),
    ]
    result = getattr(info, "_get_group_pc")()
    # 第一组原值 0x110 修正为 0x120，第二组原值 0x210 修正为 0x240；
    # 第二组不能沿用第一组的修正 current pc。
    assert "current pc        : 0x110" in result
    assert "current pc        : 0x120" in result
    assert "current pc        : 0x210" in result
    assert "current pc        : 0x240" in result
    assert CORRECTED_PC_NOTICE in result


def test_get_group_pc_no_notice_without_correction():
    info = AicErrorInfo()
    info.aic_error_groups = [
        (
            "0x10",
            {
                "records": [
                    {"error_code": "0x10", "core_err_type": "aic", "core_id": "0"}
                ],
                "cores_aic": ["0"],
                "cores_aiv": [],
            },
        )
    ]
    result = getattr(info, "_get_group_pc")()
    assert CORRECTED_PC_NOTICE not in result
