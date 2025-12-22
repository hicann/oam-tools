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

from conftest import MSAICERR_PATH, CommonAssert, cur_abspath, ori_data_path
import os
import pytest
import sys
from unittest.mock import Mock, MagicMock
from pathlib import Path

dump_data_pb2 = Mock(name="dump_data_pb2")
dump_data_pb2.__name__ = 'ms_interface.dump_data_pb2'
sys.modules['ms_interface.dump_data_pb2'] = dump_data_pb2

protobuf_message = Mock(name="google.protobuf.message")
protobuf_message.__name__ = 'google.protobuf.message'
sys.modules['google.protobuf.message'] = protobuf_message

te = Mock(name="te")
te.__name__ = "te"
sys.modules['te'] = te
sys.path.append(MSAICERR_PATH)

cur_abspath = os.path.dirname(__file__)

ori_data_path = Path(cur_abspath).joinpath('../res/ori_data/')
from ms_interface.tiling_data_parser import TilingDataParser
from ms_interface.dump_data_parser import DumpDataParser
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.constant import RegexPattern
from ms_interface.collection import Collection
from ms_interface.aicore_error_parser import AicoreErrorParser
from ms_interface import utils
from ms_interface.constant import Constant, RetCode

class Selflib():

    def rtGetAiCoreCount(self, driver_core_num):
        return 0


class TestUtilsMethods(CommonAssert):

    @pytest.fixture(autouse=True)
    def change_test_dir(self, tmp_path):
        self.temp = tmp_path
        self.debug_info = tmp_path.joinpath("debug_info.txt")
        os.chdir(tmp_path)

    def test_get_atomic_err_log(self, mocker):
        mocker.patch('ms_interface.utils.execute_command',
                     return_value=[1, ''])
        collection = Collection(os.path.join(cur_abspath, '../res/ori_data/complie_path'),
                                os.path.join(cur_abspath, '../res/ori_data/complie_path'))
        collection.collect_plog_path = 'dest_path'
        parser = AicoreErrorParser(collection)
        atomic_err_log = parser._get_atomic_err_log()
        self.assertEqual(atomic_err_log, False)

    def test_check_addr_in_range_hex(self):
        flag = AicoreErrorParser._check_addr_in_range(1, 24, [('0x0', 256)])
        self.assertEqual(flag, True)

    def test_check_addr_in_range_dec(self):
        flag = AicoreErrorParser._check_addr_in_range(1, 24, [('0', 256)])
        self.assertEqual(flag, True)

    def test_check_addr_in_range_error(self):
        flag = AicoreErrorParser._check_addr_in_range(1, 256, [('0', 24)])
        self.assertEqual(flag, False)

    def test_get_info_for_decompile(self, mocker):
        mocker.patch('ms_interface.aic_error_info.'
                     'AicErrorInfo.find_extra_pc', return_value='10100110')
        parser = AicoreErrorParser('collection')
        info = AicErrorInfo()
        info.aic_error_info['current_pc'] = 'x1435'
        info.aic_error_info['start_pc'] = 'x0123'
        diff_str, err_pc = parser._get_info_for_decompile(info)
        self.assertEqual((diff_str, err_pc), ('1312', '1176'))

    def test_get_cce_tbe_code_number_decompile_not_exist(self):
        parser = AicoreErrorParser('collection')
        flag = parser._get_cce_tbe_code_number(
            'decompile_file', 'loc_json_file', 'err_pc', 'info')
        self.assertEqual(flag, False)

    def test_get_cce_tbe_code_number_loc_not_exist(self, mocker):
        mocker.patch('os.path.exists', side_effect=[True, False])
        mocker.patch('ms_interface.aicore_error_parser.'
                     'AicoreErrorParser._read_decompile_file', return_value='0x1234')
        parser = AicoreErrorParser('collection')
        flag = parser._get_cce_tbe_code_number(
            'decompile_file', 'loc_json_file', 'err_pc', 'info')
        self.assertEqual(flag, True)

    def test_get_cce_tbe_code_number_no_cce_code_num(self, mocker):
        parser = AicoreErrorParser('collection')
        mocker.patch('os.path.exists', side_effect=[True, True])
        mocker.patch.object(parser, '_read_decompile_file', return_value='')
        mocker.patch.object(parser, '_read_loc_json_file', return_value=None)
        flag = parser._get_cce_tbe_code_number(
            'decompile_file', 'loc_json_file', 'err_pc', 'info')
        self.assertEqual(flag, False)

    def test_print_single_op_result(self):
        parser = AicoreErrorParser('collection')
        flag = parser.print_single_op_result('../res/ori_data')
        self.assertEqual(flag, None)

    def test_get_data_dump_result_ret(self, mocker):
        mocker.patch('ms_interface.utils.execute_command',
                     return_value=[0, ''])
        collection = Collection(os.path.join(cur_abspath, '../res/ori_data/complie_path'),
                                os.path.join(cur_abspath, '../res/ori_data/complie_path'))
        collection.collect_plog_path = 'dest_path'
        parser = AicoreErrorParser(collection)
        flag = parser._get_data_dump_result()
        self.assertEqual(flag, False)

    def test_need_atomic_clean(self):
        info = AicErrorInfo()
        info.kernel_name = 'kernel_name'
        parser = AicoreErrorParser('collection')
        flag = parser._need_atomic_clean(os.path.join(
            cur_abspath, '../res/ori_data/complie_path'), info)
        self.assertEqual(flag, False)

    def test_run_golden_op(self, mocker):
        info = AicErrorInfo()
        info.kernel_name = 'kernel_name'
        temp_dir = Path(cur_abspath).joinpath("../temp_test_run_golden_op")
        temp_dir.mkdir(parents=True, exist_ok=True)
        parser = AicoreErrorParser('collection')
        mock_return = MagicMock()
        mock_return.returncode = 0
        mocker.patch('subprocess.run', return_value=mock_return)
        mocker.patch.object(AicoreErrorParser,
                            'search_aicerr_log', return_value=True)
        mocker.patch('os.path.exists', return_value=True)
        mocker.patch.object(Path, 'rglob', return_value=[Path(cur_abspath).joinpath(
            "../res/ori_data/collect_milan/collection/AddCustom_ab1b6750d7f510985325b603cb06dc8b.json")])
        mocker.patch('shutil.rmtree')
        flag = parser.run_test_env("Ascend910B4")
        self.assertEqual(flag, False)

    def test_ffts_get_kernel_name_l0_success(self):
        info = AicErrorInfo()
        info.kernel_name = 'kernel_name'
        info.node_name = 'node_name'
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        aic_info = parser.get_kernel_name_l0(info.node_name)
        self.assertEqual(aic_info.task_id, '1')

    def test_not_ffts_get_kernel_name_l0_data(self):
        info = AicErrorInfo()
        info.kernel_name = 'kernel_name'
        info.node_name = 'node_name'
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/notffts/'))
        aic_info = parser.get_kernel_name_l0(info.node_name)
        self.assertEqual(aic_info.task_id, '6')

    def test_ffts1_get_kernel_name_l0_info(self):
        info = AicErrorInfo()
        info.kernel_name = 'kernel_name'
        info.node_name = 'node_name'
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts1/'))
        aic_info = parser.get_kernel_name_l0(info.node_name)
        self.assertEqual(aic_info.task_id, '1')

    def test_get_dump_data_info(self):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts'))
        thread_id, data_name = parser.get_dump_data_info()
        self.assertEqual(thread_id, '1592077')

    def test_collect_driver_aicore_number(self, mocker):
        info = AicErrorInfo()
        info.kernel_name = 'kernel_name'
        info.node_name = 'node_name'
        os.environ['LD_LIBRARY_PATH'] = '/runtime/libruntime.so'
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts1/'))
        mocker.patch('ctypes.cdll.LoadLibrary', return_value=Selflib())
        aic_info = parser.collect_driver_aicore_number()
        self.assertEqual(aic_info, 0)

    def test_invalid_args_compare(self):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts1/'))
        res = parser._get_args_from_info('\[AIC_INFO\] args.*after execute')
        self.assertEqual(res[0], 255085623939072)

    def test_get_atomic_err_log(self):
        info = AicErrorInfo()
        info.kernel_name = 'kernel_name'
        info.node_name = 'node_name'
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts1/'))
        res = parser._get_atomic_err_log()
        self.assertEqual(res, True)

    def test_update_err_pc(self, mocker):
        info = AicErrorInfo()
        info.kernel_name = 'kernel_name'
        info.node_name = 'node_name'
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts1/'))
        res = parser._update_err_pc('0x0', '/', info.node_name)
        self.assertEqual(res, '0x0')
        mocker.patch.object(utils, 'get_inquire_result', return_value="111")
        res = parser._update_err_pc('0x1', "", "")

    def test_ffts_get_kernel_name_l0_task_id(self):
        info = AicErrorInfo()
        info.kernel_name = 'kernel_name'
        info.node_name = 'node_name'
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        res = parser.check_plog_info()
        aic_info = parser.get_kernel_name_l0(info.node_name)
        self.assertEqual(aic_info.task_id, '1')

    def test_cal_shape_size(self):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        res = parser._cal_shape_size("[]")
        self.assertEqual(res, 1)

    def test_get_err_pc(self, mocker):
        mocker.patch('ms_interface.aic_error_info.'
                     'AicErrorInfo.find_extra_pc', return_value='')
        parser = AicoreErrorParser('collection')
        mocker.patch.object(parser, '_get_err_pc', return_value='')
        info = AicErrorInfo()
        info.aic_error_info['current_pc'] = 'x1435'
        info.aic_error_info['start_pc'] = 'x0123'
        diff_str, err_pc = parser._get_info_for_decompile(info)
        self.assertEqual((diff_str, err_pc), ('1312', ''))

    def test_update_err_pc_data(self, mocker):
        info = AicErrorInfo()
        info.kernel_name = 'kernel_name'
        info.node_name = 'node_name'
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        mocker.patch.object(utils, 'get_inquire_result', return_value="111")
        res = parser._update_err_pc('0x1', "", "")
        self.assertEqual(res, '2')

    def test_need_atomic_clean(self):
        info = AicErrorInfo()
        info.kernel_name = 'te_assign_d623a1e1b515a45cdc8c9658e58e2860034dbfbd9ab35f92e1415a0fda9d35c1_1'
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        abs_path = os.path.join(
            cur_abspath, '../res/ori_data/asys_output_20230713074104794/dfx/ops/0/')
        res = parser._need_atomic_clean(abs_path, info)
        self.assertEqual(res, False)

    def test_get_sub_ptr(self):
        info = AicErrorInfo()
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        info.bin_list = ['xxx']
        res = parser._get_sub_ptr(info)
        self.assertEqual(res, {})

    @pytest.mark.skip
    def test_read_decompile_file(self):
        info = AicErrorInfo()
        info.kernel_name = 'te_assign_d623a1e1b515a45cdc8c9658e58e2860034dbfbd9ab35f92e1415a0fda9d35c1_1'
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        abs_path = os.path.join(cur_abspath,
                                '../res/ori_data/asys_output_20230713074104794/dfx/ops/0/te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1.cce')
        res = parser._read_decompile_file(abs_path, '', info)
        self.assertEqual(res, '')

    def test_get_kernel_and_json_file(self):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        res = parser._get_kernel_and_json_file('kernel_name', 'tiling_key')
        self.assertEqual(res, None)

    def test_get_kernel_and_json_file_in_collect_path(self, mocker):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/no_cce/asys_aicerror'))
        json_path = os.path.join(
            cur_abspath, '../res/ori_data/no_cce/asys_aicerror/asys_output_20250508095626087/dfx/ops/GatherV3_9e31943a1a48bf81ddff1fc6379e0be3_high_performance.json')
        o_path_out_collection = os.path.join(
            cur_abspath, '../res/ori_data/asys_output_20230713074104794/dfx/ops/0/te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1.o')
        mocker.patch.object(utils, 'get_inquire_result', return_value=[
                            json_path, o_path_out_collection])
        res = parser._get_kernel_and_json_file(
            'GatherV3_9e31943a1a48bf81ddff1fc6379e0be3_high_performance', 'tiling_key')
        self.assertEqual(res.json_file != '', True)
        self.assertEqual(res.bin_file == '', True)

    @pytest.mark.skip
    def test_parse(self, mocker):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        info = AicErrorInfo()
        info.aic_error_info['err_time'] = "2024-06-22-07:15:34.158.818"
        info.tiling_data_bytes = 'data tiling'.encode('utf-8')
        info.bin_file = "xxx.bin"
        mocker.patch.object(parser, 'add_objdump_to_path', return_value=None)
        mocker.patch.object(parser, 'check_plog_info', return_value=1)
        mocker.patch.object(parser, 'get_op_info', return_value=info)
        mocker.patch.object(parser, 'check_dump_result', return_value=True)
        mocker.patch.object(parser, '_test_single_op',
                            return_value=[False, "11", "single_op"])
        mocker.patch.object(parser, 'check_hash_id', return_value=True)
        mocker.patch.object(DumpDataParser, 'parse', return_value='')
        res = parser.parse()
        self.assertEqual(res, 101)

    def test_check_dump_result_dump_fail(self):
        info = AicErrorInfo()
        dfx_message = ""
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        res = parser.check_dump_result(dfx_message, info)
        self.assertEqual(res, False)

    def test_check_dump_result_dump_noffts_fail(self):
        info = AicErrorInfo()
        dfx_message = ""
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/notffts/'))
        res = parser.check_dump_result(dfx_message, info)
        self.assertEqual(res, False)

    def test_check_dump_result_invalid_addr(self):
        info = AicErrorInfo()
        dfx_message = "[Dump][Exception] the address maybe invalid"
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts1/'))
        res = parser.check_dump_result(dfx_message, info)
        self.assertEqual(res, False)

    def test_check_dump_result_valid(self):
        info = AicErrorInfo()
        dfx_message = "[Dump][Exception] begin to load normal tensor, index:1"
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts1/'))
        res = parser.check_dump_result(dfx_message, info)
        self.assertEqual(res, True)

    @pytest.mark.parametrize(
        "grep_result, result, key_log", [
            ([[], [('node', 'stream', 'task')], ['hash']],
             None, '[AIC_INFO] dev_func:'),
            ([['kernel'], [], ['hash']], None, 'Failed to get node name'),
            ([['kernel'], [('node', 'stream', 'task')], []],
             None, 'Cannot get hash id in plog'),
        ]
    )
    def test_get_node_and_kernel_name_l1_failed(self, mocker, grep_result, result, key_log):
        mocker.patch.object(utils, 'get_inquire_result',
                            side_effect=grep_result)
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts1/'))
        res = parser.get_node_and_kernel_name_l1()
        self.assertEqual(res, result)
        self.assertIn(utils.ExceptionRootCause().format_causes(), key_log)

    def test_get_node_and_kernel_name_l1_noffts(self):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/notffts/'))
        res = parser.get_node_and_kernel_name_l1()
        self.assertEqual(res[0], '2')

    def test_get_node_and_kernel_name_l1_not_hash(self):
        utils.ExceptionRootCause().causes = []
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/hash_check/'))
        res = parser.get_node_and_kernel_name_l1()
        self.assertEqual(
            'Cannot get hash id in plog' in utils.ExceptionRootCause().format_causes(), True)
        self.assertEqual(res, None)

    def test_not_get_dump_data_info_L0_data(self):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/hash_check'))
        parser.parse_level = 0
        with pytest.raises(utils.AicErrException) as error:
            res = parser.get_dump_data_info()
        self.assertEqual(error.value.args[0],
                         Constant.MS_AICERR_INVALID_PATH_ERROR)

    def test_not_get_dump_data_info_L1_data(self):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/hash_check'))
        parser.parse_level = 1
        with pytest.raises(utils.AicErrException) as error:
            res = parser.get_dump_data_info()
        self.assertEqual(error.value.args[0],
                         Constant.MS_AICERR_INVALID_PATH_ERROR)

    def test_check_hash_id(self):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/notffts/'))
        res = parser.check_hash_id('15656883929986130445', os.path.join(cur_abspath,
                                                                        '../res/ori_data/collect/notffts/collection/plog/plog-370_20230713074107861.log'))
        self.assertEqual(res, True)

    def test_check_hash_id_1_failed(self):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/notffts/'))
        res = parser.check_hash_id('1565688392998613', os.path.join(cur_abspath,
                                                                    '../res/ori_data/collect/notffts/collection/plog/plog-370_20230713074107861.log'))
        self.assertEqual(res, False)

    def test_check_hash_id_2_failed(self):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        res = parser.check_hash_id('1565688392998613', os.path.join(cur_abspath,
                                                                    '../res/ori_data/collect/ffts/collection/plog/test_hash_id.log'))
        self.assertEqual(res, False)

    def test_test_single_op(self):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        info = AicErrorInfo()
        res = parser._test_single_op(info, '', 'temp_dir', 'single_op')
        self.assertEqual(res[0], RetCode.SUCCESS)

    def test_get_extra_info(self):
        aic_error = "vec error info: 0x51000070f7, mte error info: 0x500300004d, ifu error info: 0x29883d2080000, ccu error info: 0x22c090001000046, cube error info: 0, biu error info: 0, aic error mask: 0x6500020bd00028c, para base: 0x12c1c0000400."
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        res = parser._get_extra_info(aic_error)
        data = "extra info:\nIFU_ERR_INFO=0x29883d2080000\nCCU_ERR_INFO=0x22c090001000046\nBIU_ERR_INFO=0\nCUBE_ERR_INFO=0\nMTE_ERR_INFO=0x500300004d\nVEC_ERR_INFO=0x51000070f7\n"
        self.assertEqual(res, data)

    def test_get_extra_info_error(self):
        aic_error = "mte error info: 0x500300004d, ccu error info: 0x22c090001000046, cube error info: 0, biu error info: 0, aic error mask: 0x6500020bd00028c, para base: 0x12c1c0000400."
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        res = parser._get_extra_info(aic_error)
        data = "extra info:\nCCU_ERR_INFO=0x22c090001000046\nBIU_ERR_INFO=0\nCUBE_ERR_INFO=0\nMTE_ERR_INFO=0x500300004d\n"
        self.assertEqual(res, data)

    def test_get_op_info(self, mocker):
        os.environ['LD_LIBRARY_PATH'] = './'
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect_milan'))
        mocker.patch.object(
            parser, 'collect_driver_aicore_number', return_value=1)
        info = parser.get_op_info()
        self.assertIn(
            'AddCustom_ab1b6750d7f510985325b603cb06dc8b_0', info.kernel_name)

    def test_get_tiling_data_None(self, mocker):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect_milan'))
        mocker.patch.object(parser, '_get_aic_info',
                            return_value='[AIC_INFO] aaa: 0')
        self.assertEqual(parser._get_tiling_data_l1('a'), '')

    def test_get_tiling_data_value(self, mocker):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect_milan'))
        mocker.patch.object(parser, '_get_aic_info',
                            return_value='[AIC_INFO] tiling_data:0x0001')
        self.assertEqual(parser._get_tiling_data_l1('a'),
                         bytes.fromhex('0001'))

    def test_get_tiling_data_other(self, mocker):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect_milan'))
        mocker.patch.object(parser, '_get_aic_info',
                            return_value='[AIC_INFO] tiling_data:1')
        self.assertEqual(parser._get_tiling_data_l1('a'),
                         bytes('1', 'utf-8'))

    def test_get_tiling_data(self, mocker):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect_milan'))
        mocker.patch.object(TilingDataParser, 'parse', return_value=b'0x1')
        tiling_data = parser.get_tiling_data('a')
        self.assertEqual(tiling_data, b'0x1')

    def test_tiling_data_success(self, mocker):
        info = AicErrorInfo()
        info.kernel_path = self.temp
        info.tiling_data_bytes = b'0x1'
        info.kernel_name = 'test'
        parser = AicoreErrorParser('')
        parser.write_tiling_data_to_file(info)
        self.assertIn(self.debug_info.read_text(), "Tiling data is saved to")

    @pytest.mark.parametrize(
        "test_single_mock, dump_result, expect_log_level",
        [
            # ([(RetCode.SUCCESS, '', '')], False, 'warn'),
            ([(RetCode.SUCCESS, '', ''), (RetCode.FAILED, '', '')], True, 'info'),
            ([(RetCode.SUCCESS, '', ''), (RetCode.SUCCESS, '', ''),
             (RetCode.SUCCESS, '', '')], True, 'debug'),
        ]
    )
    def test_run_single_operator(self, mocker, test_single_mock, dump_result, expect_log_level):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        info = AicErrorInfo()
        info.data_dump_result = dump_result
        mocker.patch('os.path.exists', return_value=True)
        mocker.patch('shutil.rmtree', return_value=None)
        info_mock = mocker.patch('ms_interface.utils.print_info_log')
        debug_mock = mocker.patch('ms_interface.utils.print_debug_log')
        warn_mock = mocker.patch('ms_interface.utils.print_warn_log')
        mocker.patch.object(AicoreErrorParser,
                            'check_hash_id', return_value=True)
        mocker.patch.object(AicoreErrorParser,
                            '_test_single_op', side_effect=test_single_mock)
        parser.run_single_operator(info, "err_i_folder")
        if expect_log_level == 'debug':
            self.assertEqual(debug_mock.call_count, 1)
        elif expect_log_level == 'info':
            self.assertEqual(info_mock.call_count, 2)
        elif expect_log_level == 'warn':
            self.assertEqual(warn_mock.call_count, 1)

    @pytest.mark.parametrize(
        "cce_exist, content, result",
        [
            (False, '', 'Ascend910B2'),
            (True, '//soc_version xxx', 'Ascend910B2'),
            (True, '//soc_version Ascend310B"', 'Ascend310B1'),
            (True, '//soc_version Ascend910B"', 'Ascend910B'),
            (True, '//soc_version Ascend910B1"', 'Ascend910B1'),
        ]
    )
    def test_get_soc_version_from_cce(self, mocker, cce_exist, content, result):
        mocker.patch('os.path.isfile', return_value=cce_exist)
        mocker.patch.object(Path, 'read_text', return_value=content)
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        res = parser.get_soc_version_from_cce('/tmp/cce.txt')
        self.assertEqual(res, result)

    def test_aicerr_regexp(self):
        log = 'RUNTIME(200280,python3):2025-07-07-10:12:17.088.944 [device_error_core_proc.cc:314]201695 ProcessStarsCoreErrorInfo:[EXEC][EXEC]The error from device(chipId:0, dieId:0), serial number is 31, there is an exception of aivec error, core id is 36, error code = 0, dump info: pc start: 0x12400001638c, current: 0x1240000167bc, vec error info: 0x6106ff4758, mte error info: 0x302aa40, ifu error info: 0x2000017df8400, ccu error info: 0x482a21100000000, cube error info: 0, biu error info: 0, aic error mask: 0x6500020bd00028c, para base: 0x12d0c0000800.'
        aic_err_ret = utils.regexp_match_dict(
            RegexPattern.AICORE_ERR_OCCUR, log)
        self.assertNotEqual(aic_err_ret, [])
        aic_err_map = aic_err_ret[0]
        self.assertEqual(aic_err_map['err_time'], '2025-07-07-10:12:17.088.944')
        self.assertEqual(aic_err_map['dev_id'], 'chipId:0, dieId:0')
        self.assertEqual(aic_err_map['thread_id'], '201695')
        self.assertEqual(aic_err_map['core_id'], '36')
        self.assertEqual(aic_err_map['error_code'], '0')
        self.assertEqual(aic_err_map['start_pc'], '0x12400001638c')
        self.assertEqual(aic_err_map['current_pc'], '0x1240000167bc')
        self.assertEqual(aic_err_map['extra_info'], 'vec error info: 0x6106ff4758, mte error info: 0x302aa40, ifu error info: 0x2000017df8400, ccu error info: 0x482a21100000000, cube error info: 0, biu error info: 0, aic error mask: 0x6500020bd00028c, para base: 0x12d0c0000800.')

    def test_get_ffts_addrs_num(self):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        self.assertEqual(parser.get_ffts_addrs_num(), 1)

    def test_get_return_code(self):
        aic_info = AicErrorInfo()
        aic_info.atomic_clean_check = False
        aic_info.atomic_add_err = True
        aic_info.single_op_test_result = RetCode.FAILED
        aic_info.dump_info = "data invalid"
        aic_info.check_args_result = False
        aic_info.data_dump_result = False
        aic_info.env_available = False
        self.assertEqual(AicoreErrorParser.get_return_code(
            aic_info), Constant.MS_AICERR_FRAMEWORK_MEMSET_MISSING)
        aic_info.atomic_clean_check = True
        self.assertEqual(AicoreErrorParser.get_return_code(
            aic_info), Constant.MS_AICERR_ATOMIC_OPERATOR_OVERFLOW)
        aic_info.atomic_add_err = False
        self.assertEqual(AicoreErrorParser.get_return_code(
            aic_info), Constant.MS_AICERR_OPERATOR_INPUT_DATA_ERR)
        aic_info.dump_info = ""
        self.assertEqual(AicoreErrorParser.get_return_code(
            aic_info), Constant.MS_AICERR_OPERATOR_ARGS_OVERWRITTEN)
        aic_info.check_args_result = True
        self.assertEqual(AicoreErrorParser.get_return_code(
            aic_info), Constant.MS_AICERR_MEMORY_ALLOCATION_ERR)
        aic_info.data_dump_result = True
        self.assertEqual(AicoreErrorParser.get_return_code(
            aic_info), Constant.MS_AICERR_SINGLE_OP_ERR)
        aic_info.single_op_test_result = RetCode.SUCCESS
        self.assertEqual(AicoreErrorParser.get_return_code(
            aic_info), Constant.MS_AICERR_HARDWARE_ERR)
        aic_info.env_available = True
        self.assertEqual(AicoreErrorParser.get_return_code(
            aic_info), Constant.MS_AICERR_NONE_ERROR)

    @pytest.mark.parametrize(
        "plog_content, result",
        [
            ("AtomicLaunchKernelWithFlag_test", True),
            ("AtomicLaunchKernelWithFlag_aaaa", False),
        ]
    )
    def test_check_atomic_clean(self, plog_content, result):
        aic_info = AicErrorInfo()
        aic_info.node_name = "test"
        aic_info.kernel_name = "test"
        self.temp.joinpath(f"{aic_info.node_name}.json").write_text(
            '{"compile_info": "1","parameters": ["1", "2", "3"]}')
        self.temp.joinpath("test.plog").write_text(plog_content)
        parser = AicoreErrorParser(self.temp)
        res = parser._check_atomic_clean(str(self.temp), aic_info)
        self.assertEqual(res, result)

    @pytest.mark.parametrize(
        "log_content, kernel_name, result",
        [
            (f"there is an aivec error exception,  test_mix_aic", "test_mix_aic", True),
            (f"there is an aicore error exception,  test_mix_aic", "test_mix_aic", True),
            (f"there is an exception of aivec error,  test_mix_aic", "test_mix_aic", True),
            (f"there is an exception of aicore error,  test_mix_aic",
             "test_mix_aic", True),
            (f"aicore exception,  test_mix_aic", "test_mix_aic", True),
            (f"there is an aivec error exception,  aaa_mix_aic", "test_mix_aic", False),
            (f"there is not error exception,  test_mix_aic", "test_mix_aic", False),
        ]
    )
    def test_search_aicerr_log(self, log_content, kernel_name, result):
        self.temp.joinpath("test.log").write_text(log_content)
        parser = AicoreErrorParser(self.temp)
        self.assertEqual(parser.search_aicerr_log(
            kernel_name, self.temp), result)

    def test_get_occur_before_mark(self):
        decompile_file = ori_data_path.joinpath(
            'decompile_with_o/GatherV2_daad10a93d32be95786cd6e84e734751_high_precision.o.txt')
        self.assertEqual(AicoreErrorParser._get_occur_before_mark(decompile_file, '430', AicErrorInfo()), True)

    def test_get_tiling_l0_ffts(self, mocker):
        log = '[ERROR] RUNTIME(1592077,python3):2024-09-12-16:40:07.362.023 [device_error_proc.cc:1402]1592077 ProcessStarsCoreErrorInfo:[INIT][DEFAULT]The error from device(chipId:0, dieId:0), serial number is 87, there is an fftsplus aivector error exception, core id is 0, error code = 0, dump info: pc start: 0x12c042d73754, current: 0x12c042d75b18, vec error info: 0x99000000a2, mte error info: 0x5003000031, ifu error info: 0x200000007ffc0, ccu error info: 0x280d00000084, cube error info: 0, biu error info: 0, aic error mask: 0x6500020bd00028c, para base: 0x12c040569000.'
        mocker.patch('ms_interface.utils.execute_command',
                     return_value=('', log))
        parser = AicoreErrorParser('')
        mocker.patch.object(parser, 'ffts_flag', True)
        res = parser._get_tiling_l0()
        self.assertEqual(res, (0, 0))

    def test_get_tiling_l1_success(self, mocker):
        log = r'[INFO] IDEDD(200280,python3):2025-07-07-10:12:17.093.111 [dump_operator.cpp:139][tid:201695] [AIC_INFO] dev_func:GatherV2_daad10a93d32be95786cd6e84e734751_high_precision' \
              r'[INFO] IDEDD(200280,python3):2025-07-07-10:12:17.093.126 [dump_operator.cpp:139][tid:201695] [AIC_INFO] tiling_key:900016000' \
              r'[INFO] IDEDD(200280,python3):2025-07-07-10:12:17.093.126 [dump_operator.cpp:139][tid:201695] [AIC_INFO] tiling_key:900016000' \
              r'[INFO] IDEDD(200280,python3):2025-07-07-10:12:17.093.126 [dump_operator.cpp:139][tid:201695] [AIC_INFO] tiling_key:900016000' \
              r'[INFO] IDEDD(200280,python3):2025-07-07-10:12:17.093.088 [dump_operator.cpp:139][tid:201695] [AIC_INFO] block_dim:1' \

        mocker.patch('ms_interface.utils.execute_command',
                     return_value=(0, log))
        parser = AicoreErrorParser('')
        res = parser._get_tiling_l1(
            'GatherV2_daad10a93d32be95786cd6e84e734751_high_precision')
        self.assertEqual(res, (900016000, 1))

    def test_add_objdump_to_path(self, mocker):
        mocker.patch('os.path.exists', return_value=False)
        mocker.patch('shutil.which', return_value='')
        with pytest.raises(utils.AicErrException):
            AicoreErrorParser.add_objdump_to_path()
        self.assertIn(self.debug_info.read_text(), 'Cannot find cce-objdump! please add cce-objdump path in env PATH')

    def test_get_data_dump_result(self, mocker):
        mocker.patch('ms_interface.utils.execute_command',
                     side_effect=[(1, ''), (1, ''), (1, '')])
        parser = AicoreErrorParser('')
        self.assertEqual(parser._get_data_dump_result(), True)

        mocker.patch('ms_interface.utils.execute_command',
                     side_effect=[(1, ''), (0, ''), (0, '')])
        self.assertEqual(parser._get_data_dump_result(), False)

    def test_decompile(self, mocker):
        parser = AicoreErrorParser('')
        parser.parse_level = 1
        mocker.patch('os.path.exists', return_value=True)
        mocker.patch('ms_interface.utils.copy_src_to_dest', return_value=None)
        mocker.patch.object(parser, '_get_decompile_status', return_value=0)
        info = AicErrorInfo()
        info.bin_file = str(ori_data_path.joinpath(
            'decompile_with_o/GatherV2_daad10a93d32be95786cd6e84e734751_high_precision.o'))
        self.assertEqual(parser._decompile('', '', info), False)

    def test_get_v300_error_code(self, mocker):
        parser = AicoreErrorParser('')
        parser.collect_path = str(ori_data_path.joinpath('collect_milan'))
        self.assertEqual(parser._get_v300_error_code(), '0x200000000')

    @pytest.mark.parametrize(
        'get_dump_data_info, get_inquire_result, execute_command, log_res',
        [
            (['1', 'data_name'], [], ['',''], "Aicore error exception does not match"),
            (['1', 'data_name'], [{'thread_id': '2'}], ['',''], "Dump data pid is not the same with rts pid."),
            (['1', 'data_name'], [{'thread_id': '1'}], ['aa','aa'], "Get runtime block_dim failed"),
        ]
    )
    def test_get_op_info_failed(self, mocker, get_dump_data_info, get_inquire_result, execute_command, log_res):
        parser = AicoreErrorParser('')
        mocker.patch.object(parser, 'get_dump_data_info', return_value=get_dump_data_info)
        mocker.patch("ms_interface.utils.get_inquire_result", return_value=get_inquire_result)
        mocker.patch("ms_interface.utils.execute_command", return_value=execute_command)
        parser.get_op_info()
        self.assertIn(self.debug_info.read_text(), log_res)


    def test_collect_driver_aicore_number_filed(self, mocker):
        self.assertEqual(True, True)
        parser = AicoreErrorParser('')

        class Selflib():

            def rtGetAiCoreCount(self, driver_core_num):
                return 1
        mocker.patch('ms_interface.aicore_error_parser._find_runtime_so')
        mocker.patch('ctypes.cdll.LoadLibrary', return_value=Selflib())
        try:
            parser.collect_driver_aicore_number()
        except utils.AicErrException as e:
            self.assertEqual(str(e), '10')
        else:
            self.assertEqual(False, True)