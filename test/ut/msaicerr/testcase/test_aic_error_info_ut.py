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

from ms_interface.utils import ExceptionRootCause
from ms_interface.aic_error_info import AicErrorInfo
from conftest import MSAICERR_PATH, CommonAssert
import sys
from unittest.mock import Mock
import struct

dump_data_pb2 = Mock(name="dump_data_pb2")
dump_data_pb2.__name__ = 'ms_interface.dump_data_pb2'
sys.modules['ms_interface.dump_data_pb2'] = dump_data_pb2

protobuf_message = Mock(name="google.protobuf.message")
protobuf_message.__name__ = 'google.protobuf.message'
sys.modules['google.protobuf.message'] = protobuf_message
sys.path.append(MSAICERR_PATH)

IFU_ERROR = '0x13b023938000\nifu_err_type bit[50:48]=000' \
            '  meaning:read poison, 读到脏数据\nifu_err_addr' \
            ' bit[47:2]=0001001110110000001000111001001110000000000000' \
            '  meaning:IFU Error Address [47:2]  approximate:0x13b023938000'

MTE_ERROR_21 = '0x21\nmte_err_type bit[26:24]=000           ' \
               '  meaning:aipp_mte_ex_round : 表示访问外部存储绕回\n' \
               'mte_err_addr bit[22:8]=000000000000000' \
               '  meaning:MTE Error Address [19:5]  approximate:0x0'

MTE_ERROR_46 = '0x46\nmte_err_type bit[26:24]=000           ' \
               '  meaning:uzp_write_over_turn_err\n' \
               'mte_err_addr bit[22:8]=000000000000000' \
               '  meaning:MTE Error Address [19:5]  approximate:0x0'

MTE_ERROR_34 = '0x34\nmte_err_type bit[26:24]=000           ' \
               '  meaning:fmc_read_over_turn_err\n' \
               'mte_err_addr bit[22:8]=000000000000000' \
               '  meaning:MTE Error Address [19:5]  approximate:0x0'

MTE_ERROR_25 = '0x25\nmte_err_type bit[26:24]=000           ' \
               '  meaning:fmd_write_over_turn_err\n' \
               'mte_err_addr bit[22:8]=000000000000000' \
               '  meaning:MTE Error Address [19:5]  approximate:0x0'

MTE_ERROR_23 = '0x23\nmte_err_type bit[26:24]=000           ' \
               '  meaning:read poison, 读到脏数据\n' \
               'mte_err_addr bit[22:8]=000000000000000' \
               '  meaning:MTE Error Address [19:5]  approximate:0x0'

BIU_ERROR = '0x0\nbiu_err_addr bit[24:0]=0000000000000000000000000' \
            '  in hex:0x0'

CUBE_ERROR = '0x3e\ncube_err_addr bit[16:8]=000000000' \
             '  meaning:CUBE Error Address [17:9]  approximate:0x0'

VEC_ERROR = '0x3e27677\nvec_err_addr bit[28:16]=0001111100010' \
            '  meaning:VEC Error Address [17:5]      approximate:0x7c40\n' \
            'vec_err_rcnt bit[15:8]=01110110     ' \
            '  meaning:VEC Error repeat count [7:0]  repeats:118'

CCU_ERROR = '0x3e2767\nccu_err_addr bit[22:8]=011111000100111' \
            '  meaning:CCU Error Address [17:3]  approximate:0x1f138'

VEC_ERR_INFO = 'VEC_ERR_INFO : No VEC_ERR_INFO found\n' \
               'vec_ub_ecc, ecc error, 硬件问题'

IFU_ERR_INFO = 'IFU_ERR_INFO : No IFU_ERR_INFO found\n' \
               'ifu_bus_err, BIU返回bus error给IFU, 意味着从out取指令错误, \n' \
               '        IFU_ERR_INFO中的ifu_err_type记录了异常类型, ifu_err_addr记录了错误的地址'

MTE_ERR_INFO = 'MTE_ERR_INFO : No MTE_ERR_INFO found\n' \
               """mte_biu_rdwr_resp, 通过BIU读写out数据错误, MTE_ERR_INFO中的mte_err_type记录了异常类型, 
        mte_err_addr记录了发生错误的地址(是触发问题的另一面的地址, 比如out -> L1读错误, 记的是L1地址, 
        又如ub -> out写错误, 记的是ub地址)"""

CUBE_ERR_INFO = 'CUBE_ERR_INFO: No CUBE_ERR_INFO found\n' \
                'cube_l0c_self_rdwr_cflt, 前后两条指令的L0C地址相同, ' \
                '可能同时出现对相同的L0C地址同时读写的场景, \n' \
                '        CUBE_ERR_INFO中的cube_err_addr记录了冲突的地址'

CCU_ERR_INFO = 'CCU_ERR_INFO : No CCU_ERR_INFO found\n' \
               'ccu_illegal_instr, 非法执行: 1.指令的binary错误  ' \
               '2.指令地址非对齐'

BIU_ERR_INFO = 'BIU_ERR_INFO : No BIU_ERR_INFO found\n' \
    'biu_l2_write_oob, L2访问写越界, BIU_ERR_INFO中的biu_err_addr记录了越界的地址'


class TestUtilsMethods(CommonAssert):
    def test_find_extra_pc(self, mocker):
        aicerr_info = AicErrorInfo()
        mocker.patch('ms_interface.utils.hexstr_to_list_bin',
                     return_value=[63, 62, 61, 60])
        aicerror_info = aicerr_info.find_extra_pc()
        self.assertEqual(aicerror_info, '')

    def test_analyse_ifu_errinfo(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.extra_info = '<exception_print>IFU_ERR_INFO=0x13b023938000'
        errinfo = aicerr_info._analyse_ifu_errinfo()
        self.assertEqual(errinfo, IFU_ERROR)

    def test_analyse_mte_errinfo_err_bir_46(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.extra_info = '<exception_print>MTE_ERR_INFO=0x46'
        errinfo = aicerr_info._analyse_mte_errinfo(46)
        self.assertEqual(errinfo, MTE_ERROR_46)

    def test_analyse_mte_errinfo_err_bir_34(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.extra_info = '<exception_print>MTE_ERR_INFO=0x34'
        errinfo = aicerr_info._analyse_mte_errinfo(34)
        self.assertEqual(errinfo, MTE_ERROR_34)

    def test_analyse_mte_errinfo_err_bir_25(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.extra_info = '<exception_print>MTE_ERR_INFO=0x25'
        errinfo = aicerr_info._analyse_mte_errinfo(25)
        self.assertEqual(errinfo, MTE_ERROR_25)

    def test_analyse_mte_errinfo_err_bir_23(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.extra_info = '<exception_print>MTE_ERR_INFO=0x23'
        errinfo = aicerr_info._analyse_mte_errinfo(23)
        self.assertEqual(errinfo, MTE_ERROR_23)

    def test_analyse_mte_errinfo_err_bir_21(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.extra_info = '<exception_print>MTE_ERR_INFO=0x21'
        errinfo = aicerr_info._analyse_mte_errinfo(21)
        self.assertEqual(errinfo, MTE_ERROR_21)

    def test_analyse_biu_errinfo(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.extra_info = '<exception_print>BIU_ERR_INFO=0x0'
        errinfo = aicerr_info._analyse_biu_errinfo()
        self.assertEqual(errinfo, BIU_ERROR)

    def test_analyse_cube_errinfo(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.extra_info = '<exception_print>CUBE_ERR_INFO=0x3e'
        errinfo = aicerr_info._analyse_cube_errinfo()
        self.assertEqual(errinfo, CUBE_ERROR)

    def test_analyse_vec_errinfo(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.extra_info = 'VEC_ERR_INFO=0x3e27677'
        errinfo = aicerr_info._analyse_vec_errinfo()
        self.assertEqual(errinfo, VEC_ERROR)

    def test_analyse_ccu_errinfo(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.extra_info = '<exception_print>CCU_ERR_INFO=0x3e2767'
        errinfo = aicerr_info._analyse_ccu_errinfo()
        self.assertEqual(errinfo, CCU_ERROR)

    def test_get_conclusion_pc_err(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.atomic_clean_check = True
        aicerr_info.flag_check = False
        aicerr_info.rts_block_dim = 40
        aicerr_info.driver_aicore_num = 20
        aicerr_info.data_dump_result = True
        aicerr_info.aic_error_info['current_pc'] = '0x0'
        res = aicerr_info.get_conclusion()
        self.assertEqual(
            res, 'The line number of the operator error instruction is 0.\n')

    def test_get_conclusion_data_invalid(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.atomic_clean_check = True
        aicerr_info.flag_check = False
        aicerr_info.rts_block_dim = 40
        aicerr_info.driver_aicore_num = 20
        aicerr_info.data_dump_result = True
        aicerr_info.aic_error_info['current_pc'] = '0x1'
        aicerr_info.atomic_add_err = False
        aicerr_info.dump_info = 'data invalid'
        res = aicerr_info.get_conclusion()
        self.assertEqual(
            res, 'The maintenance and test information is insufficient or the format is incorrect, contact technical support.\n')

    def test_block_dim(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.atomic_clean_check = True
        aicerr_info.flag_check = False
        aicerr_info.rts_block_dim = 41
        aicerr_info.driver_aicore_num = 20
        res = aicerr_info.get_conclusion()
        self.assertEqual(
            res, 'The number of AI Cores in the environment is less than that required by the operator.\n')

    def test_atomic_clean_check(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.atomic_clean_check = False
        res = aicerr_info.get_conclusion()
        self.assertEqual(
            res, 'The memset or atomic_clean operator is not inserted before this operator in the graph, while memory cleanup is required before operator execution.\n')

    def test_flag_check(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.atomic_clean_check = True
        aicerr_info.flag_check = True
        res = aicerr_info.get_conclusion()
        self.assertEqual(
            res, 'The set_flag and wait_flag instructions are not used together in the operator code.\n')

    def test_tiling_data(self, mocker):
        aicerr_info = AicErrorInfo()
        aicerr_info.tiling_data = 'tiling data'
        mock_data = struct.pack('q', int('1234567891234567'))
        mock_open = mocker.mock_open(read_data=mock_data)
        mocker.patch('builtins.open', mock_open)
        res = aicerr_info._get_tiling_str()
        self.assertIn(res, 'tiling data in int32: [1016835847, 287445]')
        self.assertIn(res, 'tiling data in int64: [1234567891234567]')
        self.assertIn(
            res, 'tiling data in float16: [-0.10980224609375, 1.1513671875, 874.5, 2.384185791015625e-07]')

    def test_args_result_check(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.check_args_result = False
        res = aicerr_info.get_conclusion()
        self.assertEqual(
            True, 'If the arguments are inconsistent before and after operator execution' in res)

    def test_abnormal_addr_check(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.addr_valid = False
        res = aicerr_info.get_conclusion()
        self.assertEqual(
            True, 'The input/output memory address of the operator is abnormal' in res)
        aicerr_info2 = AicErrorInfo()
        aicerr_info2.data_dump_result = False
        res2 = aicerr_info2.get_conclusion()
        self.assertEqual(
            True, 'The input/output memory address of the operator is abnormal' in res2)

    def test_env_check(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.env_available = False
        res = aicerr_info.get_conclusion()
        self.assertEqual(
            res, 'Failed to execute the built-in sample operator. Check the environment.\n')

    def test_single_op_exec_succ(self):
        aicerr_info = AicErrorInfo()
        aicerr_info.single_op_test_result = True
        res = aicerr_info.get_conclusion()
        self.assertEqual(
            True, 'The single-operator test case is successfully executed.' in res)

    def test_internal_err(self):
        ExceptionRootCause().causes = []
        aicerr_info = AicErrorInfo()
        res = aicerr_info.get_conclusion()
        self.assertEqual(res, 'Internal error. Contact technical support.\n')

        aicerr_info = AicErrorInfo()
        ExceptionRootCause().causes.append('Can not find xxx')
        res = aicerr_info.get_conclusion()
        self.assertEqual(
            True, 'The maintenance and test information is insufficient or the format is incorrect' in res)
