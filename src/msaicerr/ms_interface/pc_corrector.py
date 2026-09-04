#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd. All Rights Reserved.
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
"""Recover the corrected start/current PC that adump reports.

Two sources, in priority order:

1. adump 已经算好并打印在 plog 里（kernel_symbol_locator.cpp PrintErrorForCore）：
   直接取 fixedStartPC / fixedCurrentPC，与 dump 结果完全一致。
2. plog 里没有该日志时，本地复算 currentPC：把 kernel_pc_fixer.cpp 的
   CloudV2/V4/V5 三张掩码表移植过来，按错误寄存器位段回填 PC，再用
   llvm-symbolizer 把修正后的偏移解析成源码位置。

startPC 的修正在 runtime 侧来自 kernelDeviceStartPC_（device 侧加载地址），
离线拿不到，此时 runtime 自己也是 fixedStartPC = startPC（GetCorrectedStartPC
返回 false 的分支），故回退路径沿用原始 startPC。
"""

import os
import re
import shutil

from ms_interface import utils
from ms_interface.aic_error_info import detect_chip_type
from ms_interface.constant import ChipType, Constant, RegexPattern

# (源寄存器名, 源位段[high, low], 目标 PC 位段[high, low])，与 MakePcFixEntry 一一对应。
V100_ENTRIES = {
    "CUBE": [("CUBE_ERR_0", (7, 0), (9, 2)), ("CUBE_ERR_0", (31, 24), (17, 10))],
    "CCU": [("CCU_ERR_0", (7, 0), (9, 2)), ("CCU_ERR_0", (30, 23), (17, 10))],
    "MTE": [("MTE_ERR_0", (7, 0), (9, 2)), ("MTE_ERR_1", (7, 0), (17, 10))],
    "VEC": [("VEC_ERR_0", (7, 0), (9, 2)), ("VEC_ERR_1", (7, 0), (17, 10))],
    "FIXP": [("FIXP_ERR_0", (7, 0), (9, 2)), ("FIXP_ERR_1", (7, 0), (17, 10))],
}
# AppendV100PcFixGroups 的添加顺序，决定同一 AIC_ERR 内多模块命中的取舍。
V100_MODULE_ORDER = ("CUBE", "CCU", "MTE", "VEC", "FIXP")
V100_AIC_ERR_NUM = 6

_SU_ENTRY = [("SU_ERR_INFO_T0_0", (15, 0), (17, 2))]
# MTE_ERR_INFO_T1_0 值废弃，V4/V5 均统一使用 MTE_ERR_INFO_T0_0。
_MTE_ENTRY = [("MTE_ERR_INFO_T0_0", (15, 0), (17, 2))]
_VEC_ENTRY = [
    ("VEC_ERR_INFO_T0_1", (31, 0), (31, 0)),
    ("VEC_ERR_INFO_T0_2", (16, 0), (48, 32)),
]
_CUBE_ENTRY = [("CUBE_ERR_INFO_T0_1", (15, 0), (17, 2))]
_L1_ENTRY = [("L1_ERR_INFO_T0_1", (15, 0), (17, 2))]

# (触发寄存器名, 模块名, 触发位段[high, low], 修正条目)，按 table_ 扫描顺序排列。
# SC_ERROR_T0_0 没有 PC 映射规则，不入表。
V200_GROUPS = (
    ("SU_ERROR_T0_0", "SU", (31, 0), _SU_ENTRY),
    ("MTE_ERROR_T0_0", "MTE", (31, 0), _MTE_ENTRY),
    ("MTE_ERROR_T1_0", "MTE", (31, 0), _MTE_ENTRY),
    ("VEC_ERROR_T0_0", "VEC", (25, 0), _VEC_ENTRY),
    ("VEC_ERROR_T0_2", "VEC", (1, 0), _VEC_ENTRY),
    ("CUBE_ERROR_T0_0", "CUBE", (15, 0), _CUBE_ENTRY),
    ("CUBE_ERROR_T0_1", "CUBE", (9, 0), _CUBE_ENTRY),
    ("L1_ERROR_T0_0", "L1", (30, 0), _L1_ENTRY),
    ("L1_ERROR_T0_1", "L1", (21, 0), _L1_ENTRY),
)

# V5 复用 V200 寄存器布局，掩码不同；SU_ERROR_T0_1 下标 39，故排在最后。
V300_GROUPS = (
    ("SU_ERROR_T0_0", "SU", (31, 0), _SU_ENTRY),
    ("MTE_ERROR_T0_0", "MTE", (31, 0), _MTE_ENTRY),
    ("MTE_ERROR_T1_0", "MTE", (31, 0), _MTE_ENTRY),
    ("VEC_ERROR_T0_0", "VEC", (29, 0), _VEC_ENTRY),
    ("VEC_ERROR_T0_2", "VEC", (12, 0), _VEC_ENTRY),
    ("CUBE_ERROR_T0_0", "CUBE", (18, 0), _CUBE_ENTRY),
    ("CUBE_ERROR_T0_1", "CUBE", (9, 0), _CUBE_ENTRY),
    ("L1_ERROR_T0_0", "L1", (30, 0), _L1_ENTRY),
    ("L1_ERROR_T0_1", "L1", (22, 0), _L1_ENTRY),
    ("SU_ERROR_T0_1", "SU", (3, 0), _SU_ENTRY),
)

# plog 的 "xxx error info: 0x..." 是 64 位，高 32 位为 *_ERR_1，低 32 位为 *_ERR_0。
V100_PLOG_KEYS = {
    Constant.CUBE_KEY: "CUBE_ERR",
    Constant.CCU_KEY: "CCU_ERR",
    Constant.MTE_KEY: "MTE_ERR",
    Constant.VEC_KEY: "VEC_ERR",
    Constant.IFU_KEY: "IFU_ERR",
    Constant.BIU_KEY: "BIU_ERR",
}
UINT32_MASK = 0xFFFFFFFF
# llvm-symbolizer 的未知位置标记，与 runtime kernel_source_symbolizer.cpp 一致。
UNKNOWN_MARK = "??"


def _mask(high: int, low: int) -> int:
    return ((1 << (high - low + 1)) - 1) << low


def _replace_pc_bits(pc: int, reg_value: int, src: tuple, dst: tuple) -> int:
    """Port of PcFixerInterface::ReplacePcBits."""
    src_mask = _mask(*src)
    dst_mask = _mask(*dst)
    if bin(src_mask).count("1") != bin(dst_mask).count("1"):
        utils.print_warn_log(f"Invalid PC fix mask, src={src}, dst={dst}.")
        return pc
    extracted = (reg_value & src_mask) >> src[1]
    return (pc & ~dst_mask) | ((extracted << dst[1]) & dst_mask)


def _apply_entries(pc: int, entries: list, regs: dict) -> int:
    for reg_name, src, dst in entries:
        if reg_name not in regs:
            # 与 runtime 的 errInfoRegNum >= errRegLen 跳过等价。
            continue
        pc = _replace_pc_bits(pc, regs.get(reg_name), src, dst)
    return pc


def parse_reg_items(reg_line: str) -> dict:
    """Parse "NAME=0xVALUE" pairs out of an adump error register log line."""
    regs = {}
    for name, value in re.findall(r"([A-Z0-9_]+)=(0x[0-9a-fA-F]+)", reg_line):
        regs[name] = utils.get_hexstr_value(value)
    return regs


def parse_fixp_regs(plog_path: str) -> dict:
    """Read FIXP_ERR_0/1 off the runtime `extend info` line.

    FIXP 不在 AICORE_ERR_OCCUR 匹配的 "xxx error info:" 那行，而在同一条日志的
    "The extend info: errcode:(...) ... fixp_error0 info: 0x..., fixp_error1 info: 0x..."
    上（device_error_core_proc.cc PrintCoreInfo，实参 fixPError0/fixPError1）。
    """
    cmd = ["grep", "fixp_error0 info:", "-inrE", plog_path]
    rets = utils.get_inquire_result(cmd, RegexPattern.PLOG_FIXP_ERR)
    if not rets:
        return {}
    fixp0, fixp1 = rets[0]
    regs = {}
    for name, value in (("FIXP_ERR_0", fixp0), ("FIXP_ERR_1", fixp1)):
        parsed = utils.get_hexstr_value(value) if value.startswith("0x") else int(value)
        if parsed >= 0:
            regs[name] = parsed & UINT32_MASK
    return regs


def build_v100_regs(error_code: str, extra_info: str, fixp_regs: dict = None) -> dict:
    """Synthesize the V100 errReg map from the runtime `error info:` line.

    plog 只给 6 个模块的 64 位 *_ERR_INFO 和一个 error_code，没有 adump 那份
    逐寄存器 dump。error_code 的位号按 32 位分组即 AIC_ERR_0..AIC_ERR_5
    （与 AIC_ERROR_INFO_DICT 的扁平位号一致），模块寄存器按高低 32 位拆成
    *_ERR_1 / *_ERR_0。
    """
    regs = {}
    code_value = utils.get_hexstr_value(error_code)
    if code_value > 0:
        for idx in range(V100_AIC_ERR_NUM):
            reg = (code_value >> (idx * 32)) & UINT32_MASK
            if reg:
                regs[f"AIC_ERR_{idx}"] = reg
    regs.update(fixp_regs or {})
    for plog_key, reg_prefix in V100_PLOG_KEYS.items():
        ret = re.findall(rf"{re.escape(plog_key)}=(\S+)", extra_info, re.M)
        if not ret:
            continue
        value = utils.get_hexstr_value(ret[0])
        if value < 0:
            continue
        regs[f"{reg_prefix}_0"] = value & UINT32_MASK
        regs[f"{reg_prefix}_1"] = (value >> 32) & UINT32_MASK
    return regs


def _match_v100_modules(regs: dict) -> list:
    """Port of CloudV2 GetMatchedGroups: AIC_ERR_i 的置位位名决定命中模块。"""
    modules = []
    for idx in range(V100_AIC_ERR_NUM):
        err_val = regs.get(f"AIC_ERR_{idx}", 0)
        if not err_val:
            continue
        module_masks = {}
        for bit in range(32):
            info = Constant.AIC_ERROR_INFO_DICT.get(idx * 32 + bit)
            if not info:
                continue
            module = info.split("_")[0].upper()
            if module in V100_ENTRIES:
                module_masks[module] = module_masks.get(module, 0) | (1 << bit)
        for module in V100_MODULE_ORDER:
            mask = module_masks.get(module, 0)
            if mask and (err_val & mask) and module not in modules:
                modules.append(module)
    return modules


def _match_v200_modules(regs: dict, groups: tuple) -> list:
    matched = []
    for trigger, module, trigger_bits, entries in groups:
        err_val = regs.get(trigger, 0)
        if not err_val or not (err_val & _mask(*trigger_bits)):
            continue
        if any(module == done for done, _ in matched):
            continue
        matched.append((module, entries))
    return matched


def fix_pc_by_error_regs(current_pc: int, regs: dict, chip_type: ChipType) -> int:
    """Port of KernelSymbolLocator::FixPcByErrorRegs.

    命中多个模块时 runtime 取 fixedPcs.front()，即第一个命中的模块。
    """
    if not regs:
        utils.print_warn_log("No error register info, skip fix PC.")
        return current_pc
    # V200/V300 布局以 *_ERROR_T0_* 触发寄存器为准，仅 adump 日志里有；
    # V100 布局只需 plog 里的 AIC_ERR/模块寄存器。
    groups = V300_GROUPS if chip_type is ChipType.ASCEND_950 else V200_GROUPS
    matched = _match_v200_modules(regs, groups)
    if matched:
        module, entries = matched[0]
        fixed = _apply_entries(current_pc, entries, regs)
        utils.print_debug_log(
            f"Fix PC with module={module}, originalPC={hex(current_pc)}, fixedPC={hex(fixed)}."
        )
        return fixed
    modules = _match_v100_modules(regs)
    if not modules:
        utils.print_debug_log("No matched PC fix module, skip fix PC.")
        return current_pc
    fixed = _apply_entries(current_pc, V100_ENTRIES.get(modules[0]), regs)
    utils.print_debug_log(
        f"Fix PC with module={modules[0]}, originalPC={hex(current_pc)}, fixedPC={hex(fixed)}."
    )
    return fixed


def symbolize(o_file: str, offset: int) -> str:
    """Resolve a corrected PC offset to `function at file:line` via llvm-symbolizer."""
    tool = shutil.which(Constant.SYMBOLIZER_FILE)
    if not tool:
        utils.print_warn_log("llvm-symbolizer is not installed.")
        return ""
    if not o_file or not os.path.exists(o_file):
        utils.print_warn_log(f"The *.o file {o_file} does not exist, skip symbolize.")
        return ""
    cmd = [tool, f"-obj={o_file}", hex(offset)]
    status, data = utils.execute_command(cmd)
    if status != 0:
        utils.print_warn_log(f"Failed to symbolize {hex(offset)} in {o_file}.")
        return ""
    lines = [line.strip() for line in data.splitlines() if line.strip()]
    if not lines:
        return ""
    # 默认输出为 "函数名\n源文件:行:列"，未知位置标记为 "??" / "??:0:0"。与 runtime
    # 的 res.ok 判定一致（srcFile 为 "??" 或空即失败），此时视为没解析出位置。
    if any(line.startswith(UNKNOWN_MARK) for line in lines):
        utils.print_warn_log(
            f"llvm-symbolizer cannot resolve {hex(offset)} in {o_file}, "
            "the *.o may have no debug info."
        )
        return ""
    return " at ".join(lines[:2]) if len(lines) > 1 else lines[0]


def parse_corrected_pc_from_log(plog_path: str, core_id: str) -> dict:
    """Read adump's already-corrected PC out of plog.

    kernel_symbol_locator.cpp PrintErrorForCore 打印
    "[Dump][Exception] Error PC information. coreId=..., fixedStartPC=..., fixedCurrentPC=..."。
    """
    cmd = ["grep", "Error PC information", "-inrE", plog_path]
    rets = utils.get_inquire_result(cmd, RegexPattern.ADUMP_FIXED_PC, match_dict=True)
    if not rets:
        return {}
    matched = None
    for ret in rets:
        if core_id and ret.get("core_id") == core_id:
            matched = ret
            break
    if matched is None:
        # grep 覆盖整个 plog 目录，也不按 err_time 关联，取第一条会把别的核
        # （或历次故障）的修正 PC 当本核报出，而正文声称它更可信，反而误导。
        utils.print_warn_log(
            f"No adump Error PC information for core id {core_id}, skip pc correction."
        )
        return {}
    return {
        "start_pc": matched.get("fixed_start_pc"),
        "current_pc": matched.get("fixed_current_pc"),
        "offset": utils.get_hexstr_value(matched.get("fixed_pc_offset")),
        "from_dump": True,
    }


def parse_error_regs_from_log(plog_path: str, core_id: str) -> dict:
    """Collect adump's per-register dump for one core, if present."""
    cmd = ["grep", "Error register information", "-inrE", plog_path]
    rets = utils.get_inquire_result(cmd, RegexPattern.ADUMP_ERR_REGS, match_dict=True)
    if not rets:
        return {}
    regs = {}
    for ret in rets:
        # 单核寄存器分多条打印，需按 coreId 归并。
        if core_id and ret.get("core_id") != core_id:
            continue
        regs.update(parse_reg_items(ret.get("regs", "")))
    return regs


def get_corrected_pc(plog_path: str, info: any, chip_type: ChipType = None) -> dict:
    """Corrected start/current PC for one AI Core error, dump log first.

    Returns {} when neither source yields a corrected PC, in which case the
    caller only reports the original PC.

    chip_type 由调用方按 plog 的 dump info 字段判定后传入，用于选掩码表。
    不传则退回按 error_code 判型 —— 那条路在 error_code 为裸 "0" 时无法区分
    两种芯片，只能落到 910B。
    """
    core_id = info.aic_error_info.get("core_id", "")
    corrected = parse_corrected_pc_from_log(plog_path, core_id)
    if corrected:
        utils.print_debug_log(
            f"Get corrected pc from dump log: start_pc={corrected.get('start_pc')}, "
            f"current_pc={corrected.get('current_pc')}."
        )
        return corrected

    utils.print_info_log(
        "No adump Error PC information in plog, fix pc by error registers locally."
    )
    current_pc = utils.get_hexstr_value(info.aic_error_info.get("current_pc", ""))
    start_pc = utils.get_hexstr_value(info.aic_error_info.get("start_pc", ""))
    if current_pc < 0 or start_pc < 0:
        utils.print_warn_log("Invalid original pc, skip pc correction.")
        return {}
    error_code = info.aic_error_info.get("error_code", "") or ""
    if chip_type is None:
        # detect_chip_type 直接 .strip()，非 str 会抛；这里统一收敛成 str。
        chip_type = detect_chip_type(str(error_code))
    regs = parse_error_regs_from_log(plog_path, core_id)
    if not regs:
        regs = build_v100_regs(error_code, info.extra_info, parse_fixp_regs(plog_path))
    fixed_current_pc = fix_pc_by_error_regs(current_pc, regs, chip_type)
    if fixed_current_pc == current_pc:
        # 没有任何位段被回填（命中 FIXP 但 plog 无该寄存器、950 十进制 error_code
        # 建不出 AIC_ERR_*、无模块命中）。此时报 Corrected Info 会给出与原始完全
        # 相同的两段 PC，却声称更可信，反而误导。
        utils.print_info_log("No pc bits fixed by error registers, skip pc correction.")
        return {}
    if fixed_current_pc < start_pc:
        utils.print_warn_log(
            f"fixedCurrentPC={hex(fixed_current_pc)} < startPC={hex(start_pc)}, "
            "skip pc correction."
        )
        return {}
    return {
        # startPC 的修正源是 device 侧加载地址，离线不可得，与 runtime 的
        # GetCorrectedStartPC 返回 false 分支一致，保持原值。
        "start_pc": hex(start_pc),
        "current_pc": hex(fixed_current_pc),
        "offset": fixed_current_pc - start_pc,
        "from_dump": False,
    }
