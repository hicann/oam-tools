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

from conftest import MSAICERR_PATH
import sys
import unittest

sys.path.append(MSAICERR_PATH)
from ms_interface.aic_error_info import (
    AicErrorInfo,
    detect_chip_type,
    parse_david_error_codes,
    parse_stars_error_bits,
)
from ms_interface.constant import ChipType, Constant, RetCode

# All six *_ERR_INFO registers, so every _analyse_* branch has data to parse.
FULL_EXTRA_INFO = (
    "IFU_ERR_INFO=0x1234567890abc "
    "MTE_ERR_INFO=0x1234567890abc "
    "BIU_ERR_INFO=0x1234567 "
    "CCU_ERR_INFO=0x1234567890abc "
    "CUBE_ERR_INFO=0x1234567 "
    "VEC_ERR_INFO=0x1234567890"
)

# Representative bit per dispatch module, taken from AIC_ERROR_INFO_DICT.
BIT_BIU = 1
BIT_CCU = 2
BIT_CUBE = 9
BIT_IFU = 20
BIT_MTE = 21
BIT_VEC = 49


def _make_info(error_code, extra_info=FULL_EXTRA_INFO):
    info = AicErrorInfo()
    info.aic_error_info = {"error_code": error_code}
    info.extra_info = extra_info
    return info


class TestDetectChipType(unittest.TestCase):
    """Format-based routing between the Stars and David error-code dialects."""

    def test_hex_is_stars(self):
        self.assertEqual(detect_chip_type("0x12345678"), ChipType.ASCEND_910B)
        self.assertEqual(detect_chip_type("0Xabcdef"), ChipType.ASCEND_910B)

    def test_bit_list_is_david(self):
        self.assertEqual(detect_chip_type("64, 78"), ChipType.ASCEND_950)
        self.assertEqual(detect_chip_type("64,78"), ChipType.ASCEND_950)
        self.assertEqual(detect_chip_type("128"), ChipType.ASCEND_950)

    def test_bare_zero_is_stars(self):
        # %#PRIx64 drops the 0x prefix for zero, so "0" is ambiguous; both forms
        # share the trap_or_timeout fallback, so it goes to the Stars path.
        self.assertEqual(detect_chip_type("0"), ChipType.ASCEND_910B)

    def test_blank_is_stars(self):
        self.assertEqual(detect_chip_type(""), ChipType.ASCEND_910B)
        self.assertEqual(detect_chip_type("   "), ChipType.ASCEND_910B)

    def test_surrounding_whitespace_ignored(self):
        self.assertEqual(detect_chip_type("  0x4  "), ChipType.ASCEND_910B)
        self.assertEqual(detect_chip_type("  64, 78  "), ChipType.ASCEND_950)


class TestParseDavidErrorCodes(unittest.TestCase):
    def test_preserves_runtime_order(self):
        self.assertEqual(parse_david_error_codes("192, 256, 64"), [192, 256, 64])

    def test_skips_blank_and_garbage(self):
        self.assertEqual(parse_david_error_codes("64, , bad, 78"), [64, 78])

    def test_single_code(self):
        self.assertEqual(parse_david_error_codes("320"), [320])


class TestStarsErrorInfo(unittest.TestCase):
    """910B path: error_code is a raw register value needing a bit scan."""

    def test_single_bit_is_bit_scanned(self):
        # 0x4 sets bit 2, so it resolves to bit 2 rather than dict key 4.
        result = _make_info("0x4")._get_aicerror_info()
        self.assertIn("ccu_call_depth_ovrflw", result)
        self.assertNotIn("ccu_illegal_instr", result)

    def test_multiple_bits(self):
        result = _make_info("0x10004")._get_aicerror_info()
        self.assertIn("ccu_call_depth_ovrflw", result)
        self.assertIn("cube_l0c_ecc", result)

    def test_zero_falls_back_to_trap_or_timeout(self):
        self.assertIn("trap_or_timeout", _make_info("0x0")._get_aicerror_info())

    def test_bit0_and_no_bit_are_distinct(self):
        # 0x1 really sets bit 0 (a bus read error); 0x0 sets no bit at all.
        # These must not collapse onto the same message.
        bit0 = _make_info("0x1")._get_aicerror_info()
        no_bit = _make_info("0x0")._get_aicerror_info()
        self.assertIn("biu_l2_read_oob", bit0)
        self.assertIn("trap_or_timeout", no_bit)
        self.assertNotEqual(bit0, no_bit)

    def test_biu_read_write_symmetry(self):
        self.assertIn("biu_l2_read_oob", _make_info("0x1")._get_aicerror_info())
        self.assertIn("biu_l2_write_oob", _make_info("0x2")._get_aicerror_info())

    def test_unparsable_code_is_not_bit0(self):
        # get_hexstr_value reports -1 for these; without a guard the binary form
        # scans as bit 0 and would be misreported as a bus read error.
        for code in ("", "   ", "garbage"):
            result = _make_info(code)._get_aicerror_info()
            self.assertIn("trap_or_timeout", result, f"{code!r} misresolved")
            self.assertNotIn("biu_l2_read_oob", result, f"{code!r} false BIU error")

    def test_parse_stars_error_bits_guards_invalid(self):
        self.assertEqual(parse_stars_error_bits("0x1"), [0])
        self.assertEqual(parse_stars_error_bits("0x5"), [2, 0])
        self.assertEqual(parse_stars_error_bits("0x0"), [])
        self.assertEqual(parse_stars_error_bits(""), [])
        self.assertEqual(parse_stars_error_bits("garbage"), [])

    def test_find_extra_pc_empty_for_no_bit(self):
        for code in ("0x0", "", "garbage"):
            self.assertEqual(_make_info(code).find_extra_pc(), "")

    def test_every_dispatch_branch(self):
        # One combined code lighting up all six modules, so each
        # _analyse_*_errinfo branch of the dispatch runs.
        code = 0
        for bit in (BIT_BIU, BIT_CCU, BIT_CUBE, BIT_IFU, BIT_MTE, BIT_VEC):
            code |= 1 << bit
        result = _make_info(hex(code))._get_aicerror_info()
        for key in (
            "VEC_ERR_INFO",
            "MTE_ERR_INFO",
            "IFU_ERR_INFO",
            "CUBE_ERR_INFO",
            "CCU_ERR_INFO",
            "BIU_ERR_INFO",
        ):
            self.assertIn(key, result)

    def test_repeated_module_reported_once(self):
        # bits 1 and 4 are both biu/ccu prefixed; handled_err_type dedupes the
        # register block so it is not emitted twice.
        result = _make_info(hex((1 << BIT_CCU) | (1 << 4)))._get_aicerror_info()
        self.assertEqual(result.count("CCU_ERR_INFO"), 1)

    def test_missing_registers_reported(self):
        result = _make_info(hex(1 << BIT_VEC), extra_info="")._get_aicerror_info()
        self.assertIn("No VEC_ERR_INFO found", result)


class TestDavidErrorInfo(unittest.TestCase):
    """950 path: error_code already holds resolved bit numbers."""

    def test_single_bit_direct_lookup(self):
        self.assertIn("MTE_NDDMA_CACHE_ECC", _make_info("64")._get_aicerror_info())

    def test_multiple_bits(self):
        result = _make_info("64, 78")._get_aicerror_info()
        self.assertIn("MTE_NDDMA_CACHE_ECC", result)
        self.assertIn("MTE_INSTR_ILLEGAL_CFG", result)

    def test_unknown_bit_reported(self):
        # Bit 63 has no g_davidErrorMapInfo entry; the number is still shown.
        result = _make_info("64, 63")._get_aicerror_info()
        self.assertIn("MTE_NDDMA_CACHE_ECC", result)
        self.assertIn("unknown error bit 63", result)

    def test_zero_falls_back_to_trap_or_timeout(self):
        self.assertIn("trap_or_timeout", _make_info("0")._get_aicerror_info())

    def test_each_offset_segment_resolves(self):
        for offset in (
            Constant.DAVID_OFFSET_CUBE,
            Constant.DAVID_OFFSET_MTE,
            Constant.DAVID_OFFSET_L1,
            Constant.DAVID_OFFSET_L1_1,
            Constant.DAVID_OFFSET_SC,
            Constant.DAVID_OFFSET_SU,
            Constant.DAVID_OFFSET_VEC,
            Constant.DAVID_OFFSET_VEC_1,
        ):
            # Skip bit 0: a bare "0" is the shared no-error marker and is
            # routed to the Stars fallback, so it cannot exercise a lookup.
            bits = [
                b
                for b in Constant.AIC_ERROR_INFO_DICT_DAVID
                if offset <= b < offset + 32 and b != 0
            ]
            self.assertTrue(bits, f"segment {offset} has no entry")
            result = _make_info(str(bits[0]))._get_aicerror_info()
            expected = Constant.AIC_ERROR_INFO_DICT_DAVID[bits[0]]["name"]
            self.assertIn(expected, result)

    def test_find_extra_pc_returns_empty(self):
        # David logs carry no *_ERR_INFO registers to recover [9:2] from.
        self.assertEqual(_make_info("64, 78").find_extra_pc(), "")


class TestFindExtraPc(unittest.TestCase):
    """Stars [9:2] PC fragment recovery."""

    def test_ccu_short_circuits(self):
        self.assertEqual(_make_info(hex(1 << BIT_CCU)).find_extra_pc(), "")

    def test_mte_concatenates_two_slices(self):
        # MTE takes bits [39:32] + [7:0], so 16 chars rather than 8.
        self.assertEqual(len(_make_info(hex(1 << BIT_MTE)).find_extra_pc()), 16)

    def test_vec_uses_single_slice(self):
        self.assertEqual(len(_make_info(hex(1 << BIT_VEC)).find_extra_pc()), 8)

    def test_no_register_returns_empty(self):
        info = _make_info(hex(1 << BIT_VEC), extra_info="")
        self.assertEqual(info.find_extra_pc(), "")

    def test_non_dispatch_prefix_returns_empty(self):
        # bit 100 is fixp_*, absent from key_map, so no fragment is recoverable.
        self.assertEqual(_make_info(hex(1 << 100)).find_extra_pc(), "")


class TestAnalyseRegisters(unittest.TestCase):
    """Individual register decoders."""

    def test_all_registers_decode(self):
        info = _make_info("0x0")
        for name in ("ifu", "biu", "ccu", "cube", "vec"):
            result = getattr(info, f"_analyse_{name}_errinfo")()
            self.assertNotIn("No ", result)

    def test_all_registers_missing(self):
        info = _make_info("0x0", extra_info="nothing here")
        for name, key in (
            ("ifu", "IFU"),
            ("biu", "BIU"),
            ("ccu", "CCU"),
            ("cube", "CUBE"),
            ("vec", "VEC"),
        ):
            result = getattr(info, f"_analyse_{name}_errinfo")()
            self.assertEqual(result, f"No {key}_ERR_INFO found")

    def test_mte_missing(self):
        info = _make_info("0x0", extra_info="nothing here")
        self.assertEqual(info._analyse_mte_errinfo(21), "No MTE_ERR_INFO found")

    def test_mte_sub_dict_per_err_bit(self):
        # Each of these bits selects a different sub-dictionary for mte_err_type.
        info = _make_info("0x0")
        for err_bit in (46, 34, 25, 23, 21, 999):
            result = info._analyse_mte_errinfo(err_bit)
            self.assertIn("mte_err_type", result)
            self.assertIn("mte_err_addr", result)

    def test_ifu_err_type_recorded(self):
        info = _make_info("0x0")
        info._analyse_ifu_errinfo()
        self.assertEqual(len(info.ifu_err_type), 3)


class TestAnalyseAndConclusion(unittest.TestCase):
    """Full report assembly and root-cause selection."""

    def test_analyse_renders_all_sections(self):
        info = _make_info(hex(1 << BIT_VEC))
        info.necessary_addr = {}
        msg = info.analyse()
        for section in (
            "Basic information",
            "AI Core DFX Register",
            "Operator Error Line Number",
            "Operator Input/Output Memory",
            "Operator Dump File Parsing",
        ):
            self.assertIn(section, msg)

    def test_analyse_prefers_error_code_all(self):
        info = _make_info("0x4")
        info.necessary_addr = {}
        info.error_code_all = "(0x4, 0x0, 0x0)"
        self.assertIn("(0x4, 0x0, 0x0)", info.analyse())

    def test_addr_check_flags_out_of_range(self):
        info = _make_info("0x0")
        info.necessary_addr = {
            "input_addr": [
                {"index": "0", "size": "16", "addr": "0x1000", "in_range": False}
            ],
            "output_addr": [
                {"index": "0", "size": "32", "addr": "8192", "in_range": True}
            ],
            "fault_arg_index": [1],
            "need_check_args": {1: 0xDEAD},
            "workspace": 4096,
        }
        result = info._get_addr_check_str()
        self.assertIn("*[ERROR]input[0] is out of range", result)
        self.assertFalse(info.addr_valid)
        self.assertIn("workspace_bytes:4096", result)
        self.assertIn("cannot find alloc log", result)
        # Decimal and hex addresses both render as hex.
        self.assertIn("0x2000", result)

    def test_addr_check_output_out_of_range(self):
        info = _make_info("0x0")
        info.necessary_addr = {
            "input_addr": [],
            "output_addr": [
                {"index": "1", "size": "8", "addr": "0x10", "in_range": False}
            ],
        }
        result = info._get_addr_check_str()
        self.assertIn("*[ERROR]output[1] is out of range", result)
        self.assertFalse(info.addr_valid)

    def test_args_str_formatting(self):
        self.assertEqual(AicErrorInfo._get_args_str([]), "[]")
        self.assertEqual(AicErrorInfo._get_args_str(["0x1", "0x2"]), "[[0x1],[0x2]]")

    def test_conclusion_atomic_clean_missing(self):
        info = AicErrorInfo()
        info.atomic_clean_check = False
        self.assertIn("memset or atomic_clean", info.get_conclusion())

    def test_conclusion_flag_check(self):
        info = AicErrorInfo()
        info.flag_check = "set_flag"
        self.assertIn("set_flag and wait_flag", info.get_conclusion())

    def test_conclusion_atomic_add_err(self):
        info = AicErrorInfo()
        info.aic_error_info = {"current_pc": "0x10"}
        info.atomic_add_err = True
        self.assertIn("Atomic add", info.get_conclusion())

    def test_conclusion_single_op_failed(self):
        info = AicErrorInfo()
        info.aic_error_info = {"current_pc": "0x10"}
        info.single_op_test_result = RetCode.FAILED
        self.assertIn("single-operator test case", info.get_conclusion())

    def test_conclusion_check_args(self):
        info = AicErrorInfo()
        info.aic_error_info = {"current_pc": "0x10"}
        info.check_args_result = False
        self.assertIn("arguments are inconsistent", info.get_conclusion())

    def test_conclusion_addr_invalid(self):
        info = AicErrorInfo()
        info.aic_error_info = {"current_pc": "0x10"}
        info.addr_valid = False
        self.assertIn(
            "memory address of the operator is abnormal", info.get_conclusion()
        )

    def test_conclusion_env_unavailable(self):
        info = AicErrorInfo()
        info.aic_error_info = {"current_pc": "0x10"}
        info.env_available = False
        self.assertIn("built-in sample operator", info.get_conclusion())

    def test_conclusion_single_op_success(self):
        info = AicErrorInfo()
        info.aic_error_info = {"current_pc": "0x10"}
        info.single_op_test_result = RetCode.SUCCESS
        self.assertIn("msSanitizer", info.get_conclusion())

    def test_root_cause_conclusion_property(self):
        info = AicErrorInfo()
        info.atomic_clean_check = False
        self.assertEqual(info.root_cause_conclusion, info.get_conclusion())


if __name__ == "__main__":
    unittest.main()
