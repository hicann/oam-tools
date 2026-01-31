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

import os
import sys
import pytest
from pathlib import Path

from conftest import MSAICERR_PATH, CommonAssert, RES_PATH, cur_abspath, ori_data_path, CUR_TIME_STR, ERROR_INFO, \
    write_log_keyword_to_file

sys.path.append(MSAICERR_PATH)
from ms_interface.constant import RetCode
from ms_interface.aicore_error_parser import AicoreErrorParser
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface import utils, aicore_error_parser
from ms_interface.constant import Constant


class Selflib():
    def rtGetAiCoreCount(self, driver_core_num):
        return 0

class TestUtilsMethods(CommonAssert):

    @pytest.fixture(autouse=True)
    def change_test_dir(self, tmp_path):
        self.temp = tmp_path
        self.debug_info = tmp_path.joinpath("debug_info.txt")
        os.chdir(tmp_path)

    @staticmethod
    def common_mock(mocker):
        # mock通用方法
        mocker.patch('os.path.exists', return_value=True)
        mocker.patch('shutil.rmtree', return_value=True)
        subprocess_result = mocker.MagicMock()
        subprocess_result.returncode = 0
        mocker.patch('subprocess.run', return_value=subprocess_result)
        mocker.patch('ctypes.cdll.LoadLibrary', return_value=Selflib())
        mocker.patch.object(utils, '_print_log_to_txt', return_value=None)
        mocker.patch.object(utils, 'check_path_valid', return_value=True)
        mocker.patch.object(utils, 'write_file', return_value=True)
        mocker.patch.object(utils, 'copy_src_to_dest', return_value=True)
        mocker.patch.object(aicore_error_parser.Path,
                            'write_text', return_value=None)

    def test_print_single_op_result(self):
        parser = AicoreErrorParser('collection')
        flag = parser.print_single_op_result('../res/ori_data')
        self.assertEqual(flag, None)

    def test_ffts_get_kernel_name_l0(self):
        info = AicErrorInfo()
        info.kernel_name = 'kernel_name'
        info.node_name = 'node_name'
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        aic_info = parser.get_kernel_name_l0(info.node_name)
        self.assertEqual(aic_info.task_id, '1')

    def test_get_dump_data_info_notffts(self):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/notffts'))
        parser.parse_level = 1
        dump_data_info_list = parser.get_dump_data_info()
        thread_id, data_name = dump_data_info_list[0]
        self.assertEqual(thread_id, '1534205')

    def test_null_collect_driver_aicore_number(self, mocker):
        info = AicErrorInfo()
        info.kernel_name = 'kernel_name'
        info.node_name = 'node_name'
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts1/'))
        mocker.patch('os.environ', return_value=None)
        mocker.patch('ctypes.cdll.LoadLibrary', return_value=Selflib())
        aic_info = parser.collect_driver_aicore_number()
        self.assertEqual(aic_info, 0)

    def test_collect_driver_aicore_number(self, mocker):
        info = AicErrorInfo()
        info.kernel_name = 'kernel_name'
        info.node_name = 'node_name'
        os.environ['LD_LIBRARY_PATH'] = '/runtime'
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts1/'))
        mocker.patch('ctypes.cdll.LoadLibrary', return_value=Selflib())
        aic_info = parser.collect_driver_aicore_number()
        self.assertEqual(aic_info, 0)

    def test_get_atomic_err_log(self):
        info = AicErrorInfo()
        info.kernel_name = 'kernel_name'
        info.node_name = 'node_name'
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts1/'))
        res = parser._get_atomic_err_log()
        self.assertEqual(res, True)

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

    def test_get_kernel_and_json_file(self):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        res = parser._get_kernel_and_json_file('kernel_name', 'tiling_key')
        self.assertEqual(res, None)

    def test_get_kernel_and_json_file_in_collect_path(self, mocker):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/no_cce/asys_aicerror'))
        json_path = os.path.join(cur_abspath,
                                 '../res/ori_data/no_cce/asys_aicerror/asys_output_20250508095626087/dfx/ops/GatherV3_9e31943a1a48bf81ddff1fc6379e0be3_high_performance.json')
        o_path_out_collection = os.path.join(cur_abspath,
                                             '../res/ori_data/asys_output_20230713074104794/dfx/ops/0/te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1.o')
        mocker.patch.object(utils, 'get_inquire_result', return_value=[
                            json_path, o_path_out_collection])
        res = parser._get_kernel_and_json_file('GatherV3_9e31943a1a48bf81ddff1fc6379e0be3_high_performance',
                                               'tiling_key')
        self.assertEqual(res.json_file != '', True)
        self.assertEqual(res.bin_file == '', True)

    @pytest.mark.parametrize(
        "collect_path, ffts_flag, parse_level, result",
        [
            (os.path.join(RES_PATH, "ori_data/collect/ffts"),
             True, 0, 102),  # 日志中含有D2H failed标识dump数据失败
            (os.path.join(RES_PATH, "ori_data/collect_milan"), False, 0, 0),
            (os.path.join(RES_PATH, "ori_data/collect/l1/"), False, 1, 0),
        ]
    )
    def test_parse(self, mocker, collect_path, ffts_flag, parse_level, result):
        self.common_mock(mocker)
        # mock文件读写操作的方法，需要另外写测试用例测试覆盖这些方法
        mocker.patch.object(AicoreErrorParser, '_decompile', return_value=True)
        mocker.patch.object(AicoreErrorParser,
                            '_need_atomic_clean', return_value=False)
        mocker.patch.object(AicoreErrorParser,
                            'write_tiling_data_to_file', return_value=False)
        mocker.patch.object(AicoreErrorParser,
                            'run_test_env', return_value=True)
        mocker.patch.object(AicoreErrorParser,
                            'comment_cce_in_case', return_value=1)
        mocker.patch.object(AicoreErrorParser, '_test_single_op', return_value=[
                            RetCode.SUCCESS, "11", "single_op"])
        mocker.patch.object(AicoreErrorParser,
                            'collect_driver_aicore_number', return_value=1)
        parser = AicoreErrorParser(collect_path)
        res = parser.parse()
        assert res == result
        assert parser.parse_level == parse_level
        assert parser.ffts_flag == ffts_flag

    def test_decompile(self, mocker):
        self.common_mock(mocker)
        mocker.patch.object(AicoreErrorParser,
                            '_get_decompile_status', return_value=0)
        mocker.patch.object(AicoreErrorParser,
                            '_read_decompile_file', return_value=23)
        mocker.patch.object(AicoreErrorParser,
                            '_get_occur_before_mark', return_value=True)
        info = AicErrorInfo()
        info.kernel_name = 'te_assign_d623a1e1b515a45cdc8c9658e58e2860034dbfbd9ab35f92e1415a0fda9d35c1_1'
        kernel_meta_path = os.path.join(
            cur_abspath, '../res/ori_data/decompile_with_cce/')
        info.cce_file = os.path.join(
            kernel_meta_path, f'{info.kernel_name}.cce')
        info.aic_error_info['current_pc'] = 'x1435'
        info.aic_error_info['start_pc'] = 'x0123'
        parser = AicoreErrorParser(os.path.join(
            RES_PATH, "ori_data/collect/l1/"))
        parser.parse_level = 1
        res = parser._decompile(kernel_meta_path, '/tmp', info)
        self.assertEqual(res, True)
        self.assertEqual(
            info.flag_check, "Please check the set_flag/wait_flag is match or not!!!.")

    def test_invalid_args_compare(self):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts1/'))
        res = parser._get_args_from_info('\[AIC_INFO\] args.*after execute')
        self.assertEqual(res[0], 255085623939072)

    @pytest.mark.parametrize(
        "dfx_message, collect_path",
        [
            ("", os.path.join(RES_PATH, 'ori_data/collect/ffts/')),
            ("", os.path.join(RES_PATH, 'ori_data/collect/notffts/')),
            ("[Dump][Exception] the address maybe invalid",
             os.path.join(RES_PATH, 'ori_data/collect/ffts1/'))
        ]
    )
    def test_check_dump_result_dump_fail(self, dfx_message, collect_path):
        info = AicErrorInfo()
        parser = AicoreErrorParser(os.path.join(cur_abspath, collect_path))
        res = parser.check_dump_result(dfx_message, info)
        self.assertEqual(res, False)

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
        assert res == result
        assert key_log in utils.ExceptionRootCause().format_causes()

    def test_get_node_and_kernel_name_l1_1(self):
        utils.ExceptionRootCause().causes = []
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/hash_check/'))
        res = parser.get_node_and_kernel_name_l1()
        self.assertEqual(
            'Cannot get hash id in plog' in utils.ExceptionRootCause().format_causes(), True)
        self.assertEqual(res, None)

    def test_not_get_dump_data_info_L0(self):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/hash_check'))
        parser.parse_level = 0
        with pytest.raises(utils.AicErrException) as error:
            res = parser.get_dump_data_info()
        self.assertEqual(error.value.args[0],
                         Constant.MS_AICERR_INVALID_PATH_ERROR)

    def test_not_get_dump_data_info_L1(self):
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

    def test_check_hash_id_1(self):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/notffts/'))
        res = parser.check_hash_id('1565688392998613', os.path.join(cur_abspath,
                                                                    '../res/ori_data/collect/notffts/collection/plog/plog-370_20230713074107861.log'))
        self.assertEqual(res, False)

    def test_check_hash_id_2(self):
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        res = parser.check_hash_id('1565688392998613', os.path.join(cur_abspath,
                                                                    '../res/ori_data/collect/ffts/collection/plog/test_hash_id.log'))
        self.assertEqual(res, False)

    def test_test_single_op(self):
        os.environ['PYTHONPATH'] = ''
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect/ffts/'))
        info = AicErrorInfo()
        res = parser._test_single_op(info, '', 'temp_dir', 'single_op')
        self.assertEqual(res[0], RetCode.SUCCESS)

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

    def test_get_op_info(self, mocker):
        os.environ['LD_LIBRARY_PATH'] = './'
        parser = AicoreErrorParser(os.path.join(
            cur_abspath, '../res/ori_data/collect_milan'))
        mocker.patch.object(
            parser, 'collect_driver_aicore_number', return_value=1)
        info = parser.get_op_info()
        msg = info.analyse()
        self.assertIn(
            msg, 'kernel name       : AddCustom_ab1b6750d7f510985325b603cb06dc8b_0')
        self.assertIn(msg, 'AIC_ERROR        : (0x200000000, 0, 0)')
        self.assertIn(msg, 'Single-operator test case not executed.')
        self.assertIn(msg, '2. AI Core DFX Register')
        self.assertIn(msg, '3. Operator Error Line Number')
        self.assertIn(msg, '4. Operator Input/Output Memory')
        self.assertIn(msg, '5. Operator Dump File Parsing')
        self.assertIn(
            msg, '6. Execution Result of the Single-Operator Test Case')

    def test_get_cce_tbe_code_number_no_cce_code_num(self, mocker):
        mocker.patch('os.path.exists', side_effect=[True, True])
        parser = AicoreErrorParser('collection')
        mocker.patch.object(parser, '_read_decompile_file', return_value='')
        mocker.patch.object(parser, '_read_loc_json_file', return_value=None)
        flag = parser._get_cce_tbe_code_number(
            'decompile_file', 'loc_json_file', 'err_pc', 'info')
        self.assertEqual(flag, False)

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
        assert AicoreErrorParser._get_occur_before_mark(
            decompile_file, '430', AicErrorInfo()) == True

    def test_get_tiling_l0_ffts(self, mocker):
        log = '[ERROR] RUNTIME(1592077,python3):2024-09-12-16:40:07.362.023 [device_error_proc.cc:1402]1592077 ProcessStarsCoreErrorInfo:[INIT][DEFAULT]The error from device(chipId:0, dieId:0), serial number is 87, there is an fftsplus aivector error exception, core id is 0, error code = 0, dump info: pc start: 0x12c042d73754, current: 0x12c042d75b18, vec error info: 0x99000000a2, mte error info: 0x5003000031, ifu error info: 0x200000007ffc0, ccu error info: 0x280d00000084, cube error info: 0, biu error info: 0, aic error mask: 0x6500020bd00028c, para base: 0x12c040569000.'
        mocker.patch('ms_interface.utils.execute_command',
                     return_value=('', log))
        parser = AicoreErrorParser('')
        mocker.patch.object(parser, 'ffts_flag', True)
        res = parser._get_tiling_l0()
        assert res == (0, 0)

    def test_get_tiling_l1(self, mocker):
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
        assert res == (900016000, 1)

    def test_add_objdump_to_path(self, mocker):
        mocker.patch('os.path.exists', return_value=False)
        mocker.patch('shutil.which', return_value='')
        with pytest.raises(utils.AicErrException):
            AicoreErrorParser.add_objdump_to_path()

    def test_get_data_dump_result(self, mocker):
        mocker.patch('ms_interface.utils.execute_command',
                     side_effect=[(1, ''), (1, ''), (1, '')])
        parser = AicoreErrorParser('')
        assert parser._get_data_dump_result() == True

        mocker.patch('ms_interface.utils.execute_command',
                     side_effect=[(1, ''), (0, ''), (0, '')])
        assert parser._get_data_dump_result() == False

    def test_decompile(self, mocker):
        parser = AicoreErrorParser('')
        parser.parse_level = 1
        mocker.patch('os.path.exists', return_value=True)
        mocker.patch('ms_interface.utils.copy_src_to_dest', return_value=None)
        mocker.patch.object(parser, '_get_decompile_status', return_value=0)
        info = AicErrorInfo()
        info.bin_file = str(ori_data_path.joinpath(
            'decompile_with_o/GatherV2_daad10a93d32be95786cd6e84e734751_high_precision.o'))
        assert parser._decompile('', '', info) == False

    def test_get_v300_error_code(self, mocker):
        parser = AicoreErrorParser('')
        parser.collect_path = str(ori_data_path.joinpath('collect_milan'))
        assert parser._get_v300_error_code() == '0x200000000'

    @pytest.mark.parametrize(
        'plog_file, log_res',
        [
            (False, "Aicore error exception does not match"),
            (True, "Dump data pid is not the same with rts pid."),
            (True, "Get runtime block_dim failed"),
        ]
    )
    def test_get_parse_info_error(self, mocker, plog_file, log_res):
        collect_path = self.temp.joinpath(f"info_{CUR_TIME_STR}/")
        if plog_file:
            plog_path = collect_path.joinpath('collection/plog')
            plog_path.mkdir(parents=True, exist_ok=True)
            write_log_keyword_to_file(plog_path, [ERROR_INFO])
        parser = AicoreErrorParser(collect_path)
        if 'block_dim' in log_res:
            mocker.patch.object(parser, 'get_dump_data_info', return_value=[('1592077', 'data_name')])
        else:
            mocker.patch.object(parser, 'get_dump_data_info', return_value=[('1', 'data_name')])
        mocker.patch.object(parser, 'add_objdump_to_path', return_value=False)
        mocker.patch.object(parser, 'check_plog_info', return_value=False)
        res = parser.parse()
        self.assertEqual(res,  8)
        self.assertIn(self.debug_info.read_text(), log_res)
