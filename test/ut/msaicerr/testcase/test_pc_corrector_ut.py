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

import re
import sys

from conftest import MSAICERR_PATH
from ms_interface import pc_corrector
from ms_interface.aic_error_info import (
    AicErrorInfo,
    detect_chip_type,
    detect_chip_type_by_dump_info,
)
from ms_interface.aicore_error_parser import AicoreErrorParser
from ms_interface.constant import ChipType, RegexPattern

sys.path.append(MSAICERR_PATH)

# bit 49 = vec_data_excp_ccu, i.e. AIC_ERR_1 bit 17.
VEC_ERROR_CODE = hex(1 << 49)
# bit 32 = mte_gdma_read_overflow, i.e. AIC_ERR_1 bit 0.
MTE_ERROR_CODE = hex(1 << 32)

ADUMP_PC_LOG = (
    "[ERROR] ADUMP(1,python3):2025-01-01-00:00:00.000.000 [kernel_symbol_locator.cpp:721]1 "
    "PrintErrorForCore:[Dump][Exception] Error PC information. coreId=12, coreType=0, "
    "originalStartPC=0x12c042d73754, fixedStartPC=0x12c042d73754, "
    "originalCurrentPC=0x12c042d75b18, fixedCurrentPC=0x12c042d74a20, fixedPCOffset=0x12cc."
)
ADUMP_REG_LOG = (
    "[ERROR] ADUMP(1,python3):2025-01-01-00:00:00.000.000 [kernel_symbol_locator.cpp:686]1 "
    "PrintErrorRegisters:[Dump][Exception] Error register information. coreId=12, coreType=0, "
    "SU_ERROR_T0_0=0x8 SU_ERR_INFO_T0_0=0xbeef VEC_ERROR_T0_0=0x0 "
)


def _make_info(error_code=VEC_ERROR_CODE, extra_info="VEC_ERR_INFO=0xce00000020\n"):
    info = AicErrorInfo()
    info.aic_error_info = {
        "core_id": "12",
        "error_code": error_code,
        "start_pc": "0x12c042d73754",
        "current_pc": "0x12c042d75b18",
    }
    info.extra_info = extra_info
    return info


def _write_plog(tmp_path, *lines):
    plog_dir = tmp_path / "collection" / "plog"
    plog_dir.mkdir(parents=True, exist_ok=True)
    (plog_dir / "plog-1.log").write_text("\n".join(lines) + "\n")
    return str(plog_dir)


def test_replace_pc_bits_matches_runtime():
    # CUBE 组第一条: CUBE_ERR_0[7:0] -> pc[9:2]
    assert pc_corrector._replace_pc_bits(0x0, 0xFF, (7, 0), (9, 2)) == 0x3FC
    # 位宽不等时保持原值并告警
    assert pc_corrector._replace_pc_bits(0x1234, 0xFF, (7, 0), (9, 3)) == 0x1234


def test_v100_regs_split_high_low_words():
    regs = pc_corrector.build_v100_regs(VEC_ERROR_CODE, "VEC_ERR_INFO=0x99000000a2\n")
    assert regs.get("AIC_ERR_1") == 0x20000
    assert regs.get("VEC_ERR_0") == 0xA2
    assert regs.get("VEC_ERR_1") == 0x99


def test_v100_module_match_follows_error_bit():
    vec_regs = pc_corrector.build_v100_regs(VEC_ERROR_CODE, "VEC_ERR_INFO=0x99\n")
    assert pc_corrector._match_v100_modules(vec_regs) == ["VEC"]
    mte_regs = pc_corrector.build_v100_regs(MTE_ERROR_CODE, "MTE_ERR_INFO=0x99\n")
    assert pc_corrector._match_v100_modules(mte_regs) == ["MTE"]


def test_fix_pc_v100_vec_group():
    regs = pc_corrector.build_v100_regs(VEC_ERROR_CODE, "VEC_ERR_INFO=0x99000000a2\n")
    fixed = pc_corrector.fix_pc_by_error_regs(
        0x12C042D75B18, regs, ChipType.ASCEND_910B
    )
    # VEC_ERR_0[7:0]=0xa2 -> pc[9:2]; VEC_ERR_1[7:0]=0x99 -> pc[17:10]
    expect = 0x12C042D75B18
    expect = (expect & ~(0xFF << 2)) | (0xA2 << 2)
    expect = (expect & ~(0xFF << 10)) | (0x99 << 10)
    assert fixed == expect


def test_fix_pc_v300_su_group():
    regs = {"SU_ERROR_T0_0": 0x8, "SU_ERR_INFO_T0_0": 0xBEEF}
    fixed = pc_corrector.fix_pc_by_error_regs(0x12C042D75B18, regs, ChipType.ASCEND_950)
    # SU_ERR_INFO_T0_0[15:0] -> pc[17:2]
    assert fixed == (0x12C042D75B18 & ~(0xFFFF << 2)) | (0xBEEF << 2)


def test_fix_pc_no_regs_keeps_original():
    assert pc_corrector.fix_pc_by_error_regs(0x1000, {}, ChipType.ASCEND_910B) == 0x1000
    # 无任何模块命中时同样保持原值
    assert (
        pc_corrector.fix_pc_by_error_regs(
            0x1000, {"AIC_ERR_0": 0}, ChipType.ASCEND_910B
        )
        == 0x1000
    )


def test_adump_fixed_pc_regex():
    ret = re.search(RegexPattern.ADUMP_FIXED_PC, ADUMP_PC_LOG)
    assert ret is not None
    assert ret.group("core_id") == "12"
    assert ret.group("fixed_start_pc") == "0x12c042d73754"
    assert ret.group("fixed_current_pc") == "0x12c042d74a20"
    assert ret.group("fixed_pc_offset") == "0x12cc"


def test_parse_reg_items():
    ret = re.search(RegexPattern.ADUMP_ERR_REGS, ADUMP_REG_LOG)
    assert ret is not None
    regs = pc_corrector.parse_reg_items(ret.group("regs"))
    assert regs == {
        "SU_ERROR_T0_0": 0x8,
        "SU_ERR_INFO_T0_0": 0xBEEF,
        "VEC_ERROR_T0_0": 0x0,
    }


def test_get_corrected_pc_prefers_dump_log(tmp_path):
    plog_path = _write_plog(tmp_path, ADUMP_PC_LOG)
    ret = pc_corrector.get_corrected_pc(plog_path, _make_info())
    assert ret.get("from_dump") is True
    assert ret.get("start_pc") == "0x12c042d73754"
    assert ret.get("current_pc") == "0x12c042d74a20"
    assert ret.get("offset") == 0x12CC


def test_get_corrected_pc_falls_back_to_local_fix(tmp_path):
    plog_path = _write_plog(tmp_path, "nothing to match here")
    ret = pc_corrector.get_corrected_pc(plog_path, _make_info())
    assert ret.get("from_dump") is False
    # start pc 的修正源在 device 侧，离线保持原值
    assert ret.get("start_pc") == "0x12c042d73754"
    assert ret.get("current_pc") == "0x12c042d73880"
    assert ret.get("offset") == 0x12C


def test_get_corrected_pc_skips_when_below_start(tmp_path):
    plog_path = _write_plog(tmp_path, "nothing to match here")
    # 修正后落在 start pc 之前，与 runtime 的 skip lookup symbol 分支一致
    info = _make_info(extra_info="VEC_ERR_INFO=0x300000078\n")
    assert pc_corrector.get_corrected_pc(plog_path, info) == {}


def test_get_corrected_pc_skips_on_core_id_mismatch(tmp_path):
    # plog 只有 coreId=3 的记录，本核是 12：不能把别核的修正 PC 当本核报出
    plog_path = _write_plog(tmp_path, ADUMP_PC_LOG.replace("coreId=12", "coreId=3"))
    info = _make_info(extra_info="")
    assert pc_corrector.get_corrected_pc(plog_path, info) == {}


def test_get_corrected_pc_skips_when_nothing_fixed(tmp_path):
    plog_path = _write_plog(tmp_path, "nothing to match here")
    # 950 十进制 error_code 建不出 AIC_ERR_*，无模块命中，修正空转
    info = _make_info(error_code="12,34", extra_info="VEC_ERR_INFO=0x99000000a2\n")
    assert pc_corrector.get_corrected_pc(plog_path, info) == {}


def test_v300_only_trigger_needs_950_chip_type():
    # V300 独有的 SU_ERROR_T0_1 只在 V300_GROUPS 里，命中即证明按 950 判型
    ret = pc_corrector.fix_pc_by_error_regs(
        0x12C042D73754,
        {"SU_ERROR_T0_1": 0x1, "SU_ERR_INFO_T0_0": 0xDD60},
        ChipType.ASCEND_950,
    )
    assert ret == (0x12C042D73754 & ~(0xFFFF << 2)) | (0xDD60 << 2)
    # 910B 判型下该触发寄存器不在 V200_GROUPS，回落 V100 且无 AIC_ERR 命中
    assert (
        pc_corrector.fix_pc_by_error_regs(
            0x12C042D73754,
            {"SU_ERROR_T0_1": 0x1, "SU_ERR_INFO_T0_0": 0xDD60},
            ChipType.ASCEND_910B,
        )
        == 0x12C042D73754
    )


def test_parse_fixp_regs_from_extend_info(tmp_path):
    plog_path = _write_plog(
        tmp_path,
        "[ERROR] RUNTIME(1,py):2025-01-01-00:00:00.000.000 [device_error_core_proc.cc:1190]1 "
        "PrintCoreInfo:The extend info: errcode:(0x10, 0x0, 0x0) errorStr: xx "
        "fixp_error0 info: 0x3000031, fixp_error1 info: 0x50 fsmId:0, tslot:0.",
    )
    assert pc_corrector.parse_fixp_regs(plog_path) == {
        "FIXP_ERR_0": 0x3000031,
        "FIXP_ERR_1": 0x50,
    }


def test_fix_pc_v100_fixp_group():
    # bit 100 = fixp_err_instr_addr_misal -> AIC_ERR_3 bit 4
    regs = pc_corrector.build_v100_regs(
        hex(1 << 100), "", {"FIXP_ERR_0": 0x3000031, "FIXP_ERR_1": 0x50}
    )
    assert pc_corrector._match_v100_modules(regs) == ["FIXP"]
    fixed = pc_corrector.fix_pc_by_error_regs(
        0x12C042D75B18, regs, ChipType.ASCEND_910B
    )
    expect = 0x12C042D75B18
    expect = (expect & ~(0xFF << 2)) | (0x31 << 2)
    expect = (expect & ~(0xFF << 10)) | (0x50 << 10)
    assert fixed == expect


def test_fix_pc_v200_adump_regs_on_910b():
    # 910B 判型走 V200_GROUPS：CUBE_ERROR_T0_0 触发，CUBE_ERR_INFO_T0_1[15:0] -> pc[17:2]
    regs = {"CUBE_ERROR_T0_0": 0x1, "CUBE_ERR_INFO_T0_1": 0xDD60}
    fixed = pc_corrector.fix_pc_by_error_regs(
        0x12C042D73754, regs, ChipType.ASCEND_910B
    )
    assert fixed == (0x12C042D73754 & ~(0xFFFF << 2)) | (0xDD60 << 2)


def test_fix_pc_v200_trigger_bits_out_of_mask():
    # CUBE_ERROR_T0_0 触发位段为 [15:0]，置位落在 bit 16 时不应命中
    regs = {"CUBE_ERROR_T0_0": 1 << 16, "CUBE_ERR_INFO_T0_1": 0xDD60}
    assert (
        pc_corrector.fix_pc_by_error_regs(0x12C042D73754, regs, ChipType.ASCEND_910B)
        == 0x12C042D73754
    )


def test_pc_str_omits_blank_corrected_instr():
    info = _make_info()
    info.instr = "Error occurred most likely at line: 23c4"
    info.corrected_pc = {"start_pc": "0x1000", "current_pc": "0x2000", "offset": 0x1000}
    info.corrected_instr = ""
    result = info._get_pc_str()
    assert "Corrected Info:" in result
    # 空指令不留空行
    assert "current pc        : 0x2000\n\nThe corrected PC" in result


def test_pc_str_tolerates_none_instr():
    info = _make_info()
    info.instr = None
    info.corrected_instr = None
    info.corrected_pc = {"start_pc": "0x1000", "current_pc": "0x2000", "offset": 0x1000}
    assert "Original Info:" in info._get_pc_str()


DUMP_INFO_950 = (
    "sc error info: 0x1, su error info: 0x2,0x3, mte error info: 0x4, "
    "vec error info: 0x5, cube error info: 0x6, l1 error info: 0x7, "
    "aic error mask: 0x8, para base: 0x9."
)
DUMP_INFO_910B = (
    "vec error info: 0x99000000a2, mte error info: 0x5003000031, "
    "ifu error info: 0x4291886106c00, ccu error info: 0xc79041703b00005b, "
    "cube error info: 0, biu error info: 0, aic error mask: 0x6500020bd000288."
)


def test_detect_chip_type_by_dump_info():
    assert detect_chip_type_by_dump_info(DUMP_INFO_950) is ChipType.ASCEND_950
    assert detect_chip_type_by_dump_info(DUMP_INFO_910B) is ChipType.ASCEND_910B
    # 两族字段都没有时不猜，交给调用方回退
    assert (
        detect_chip_type_by_dump_info("cube error info: 0x6, mte error info: 0x4.")
        is None
    )
    assert detect_chip_type_by_dump_info("") is None


def test_detect_chip_type_by_dump_info_beats_zero_error_code():
    # error_code 为裸 "0" 时按 error_code 判型只能落到 910B，dump info 能判对
    assert detect_chip_type("0") is ChipType.ASCEND_910B
    assert detect_chip_type_by_dump_info(DUMP_INFO_950) is ChipType.ASCEND_950


def test_get_corrected_pc_uses_passed_chip_type(tmp_path):
    plog_path = _write_plog(tmp_path, "nothing to match here")
    info = _make_info(error_code="0", extra_info="")
    # V300 独有的 SU_ERROR_T0_1 只在 V300_GROUPS 里；显式传 950 才命中
    monkey_regs = {"SU_ERROR_T0_1": 0x1, "SU_ERR_INFO_T0_0": 0xDD60}
    expect = (0x12C042D73754 & ~(0xFFFF << 2)) | (0xDD60 << 2)
    assert (
        pc_corrector.fix_pc_by_error_regs(
            0x12C042D75B18, monkey_regs, ChipType.ASCEND_950
        )
        == expect
    )
    # chip_type 缺省时退回 error_code 判型，"0" 落到 910B
    ret = pc_corrector.get_corrected_pc(plog_path, info)
    assert ret == {}


def _make_o_info(tmp_path, bin_name, kernel_name="MyKernel"):
    info = _make_info()
    info.bin_file = str(tmp_path / bin_name)
    info.kernel_path = str(tmp_path)
    info.kernel_name = kernel_name
    return info


def test_symbolize_o_file_falls_back_to_host_o(tmp_path):
    host_o = tmp_path / "MyKernel_1234_host.o"
    host_o.touch()
    # kernel 的 .o 不存在，退到 host.o
    info = _make_o_info(tmp_path, "MyKernel.o")
    assert AicoreErrorParser._get_symbolize_o_file(info) == str(host_o)


def test_symbolize_o_file_prefers_existing_o(tmp_path):
    (tmp_path / "MyKernel_1234_host.o").touch()
    kernel_o = tmp_path / "MyKernel.o"
    kernel_o.touch()
    # .o 存在就用 .o，不看 host.o
    info = _make_o_info(tmp_path, "MyKernel.o")
    assert AicoreErrorParser._get_symbolize_o_file(info) == str(kernel_o)


def test_symbolize_o_file_strips_mix_suffix(tmp_path):
    host_o = tmp_path / "Foo_1234_host.o"
    host_o.touch()
    # host.o 按去后缀名命名，Foo_mix_aic 需先去掉 _mix_aic 才能 glob 到
    info = _make_o_info(tmp_path, "Foo_mix_aic.o", kernel_name="Foo_mix_aic")
    assert AicoreErrorParser._get_symbolize_o_file(info) == str(host_o)


def test_symbolize_o_file_strips_other_suffixes(tmp_path):
    host_o = tmp_path / "Bar_9_host.o"
    host_o.touch()
    for kernel_name in ("Bar_mix_aiv", "Bar__kernel0"):
        info = _make_o_info(tmp_path, f"{kernel_name}.o", kernel_name=kernel_name)
        assert AicoreErrorParser._get_symbolize_o_file(info) == str(host_o)


def test_symbolize_o_file_keeps_original_without_host_o(tmp_path):
    # .o 和 host.o 都拿不到时保持原值，由 symbolize 打告警
    info = _make_o_info(tmp_path, "Other.o", kernel_name="Other")
    assert AicoreErrorParser._get_symbolize_o_file(info) == str(tmp_path / "Other.o")


def test_symbolize_o_file_handles_empty_bin_file(tmp_path):
    info = _make_o_info(tmp_path, "", kernel_name="Nope")
    info.bin_file = ""
    assert AicoreErrorParser._get_symbolize_o_file(info) == ""


def test_corrected_instr_uses_host_o_fallback(tmp_path, monkeypatch):
    host_o = tmp_path / "MyKernel_1234_host.o"
    host_o.touch()
    used = []
    monkeypatch.setattr(
        pc_corrector, "symbolize", lambda o, _: used.append(o) or "fn at a.cce:1:1"
    )
    info = _make_o_info(tmp_path, "MyKernel.o")
    info.corrected_pc = {"start_pc": "0x1000", "current_pc": "0x2000", "offset": 0x1000}
    AicoreErrorParser._set_corrected_instr(info)
    assert used == [str(host_o)]
    assert "fn at a.cce:1:1" in info.corrected_instr


def test_symbolize_treats_unknown_mark_as_failure(tmp_path, monkeypatch):
    o_file = tmp_path / "a.o"
    o_file.write_bytes(b"\x7fELF")
    monkeypatch.setattr(
        pc_corrector.shutil, "which", lambda _: "/usr/bin/llvm-symbolizer"
    )
    monkeypatch.setattr(
        pc_corrector.utils, "execute_command", lambda _: (0, "??\n??:0:0\n")
    )
    assert pc_corrector.symbolize(str(o_file), 0x100) == ""


def test_symbolize_returns_location(tmp_path, monkeypatch):
    o_file = tmp_path / "a.o"
    o_file.write_bytes(b"\x7fELF")
    monkeypatch.setattr(
        pc_corrector.shutil, "which", lambda _: "/usr/bin/llvm-symbolizer"
    )
    monkeypatch.setattr(
        pc_corrector.utils,
        "execute_command",
        lambda _: (0, "my_kernel\n/path/to/kernel.cce:88:3\n"),
    )
    assert pc_corrector.symbolize(str(o_file), 0x100) == (
        "my_kernel at /path/to/kernel.cce:88:3"
    )


def test_corrected_pc_kept_with_hint_when_symbolize_fails(monkeypatch):
    monkeypatch.setattr(pc_corrector, "symbolize", lambda *_: "")
    info = _make_info()
    info.corrected_pc = {"start_pc": "0x1000", "current_pc": "0x2000", "offset": 0x1000}
    AicoreErrorParser._set_corrected_instr(info)
    # 修正 PC 与 symbolizer 无关，照常输出；行号一行换成提示
    result = info._get_pc_str()
    assert "Corrected Info:" in result
    assert "current pc        : 0x2000" in result
    assert "Unable to calculate the corrected line number" in result
    assert "Error occurred most likely at line: 1000" not in result


def test_corrected_instr_has_line_when_symbolize_ok(monkeypatch):
    monkeypatch.setattr(
        pc_corrector, "symbolize", lambda *_: "my_kernel at /path/kernel.cce:88:3"
    )
    info = _make_info()
    info.corrected_pc = {"start_pc": "0x1000", "current_pc": "0x2000", "offset": 0x1000}
    AicoreErrorParser._set_corrected_instr(info)
    result = info._get_pc_str()
    assert "Error occurred most likely at line: 1000" in result
    assert "my_kernel at /path/kernel.cce:88:3" in result
    assert "llvm-symbolizer is not installed" not in result


def test_symbolize_warns_when_tool_missing(tmp_path, monkeypatch):
    warns = []
    monkeypatch.setattr(pc_corrector.utils, "print_warn_log", warns.append)
    monkeypatch.setattr(pc_corrector.shutil, "which", lambda _: None)
    assert pc_corrector.symbolize(str(tmp_path / "a.o"), 0x100) == ""
    assert warns == ["llvm-symbolizer is not installed."]


def test_pc_str_only_original_without_correction():
    info = _make_info()
    info.instr = "Error occurred most likely at line: 23c4"
    result = info._get_pc_str()
    assert "Original Info:" in result
    assert "Corrected Info:" not in result


def test_pc_str_reports_both_when_corrected():
    info = _make_info()
    info.instr = "Error occurred most likely at line: 23c4"
    info.corrected_pc = {"start_pc": "0x1000", "current_pc": "0x2000", "offset": 0x1000}
    info.corrected_instr = "Error occurred most likely at line: 1000"
    result = info._get_pc_str()
    assert "Original Info:" in result
    assert "Corrected Info:" in result
    assert "start pc          : 0x1000" in result
    assert "more " in result and "credible" in result
