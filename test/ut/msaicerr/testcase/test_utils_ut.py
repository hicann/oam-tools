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

from ms_interface import utils
from ms_interface.constant import Constant
from ms_interface.constant import ModeCustom
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.single_op_test_frame.single_op_case import SingleOpCase
from ms_interface.single_op_test_frame.runtime import AscendRTSApi
from ms_interface.single_op_test_frame.common.ascend_tbe_op import AscendOpKernel, AscendOpKernelRunner, AscendOpKernelParam
from ms_interface.run_dirty_ub import run_dirty_ub_tik

from conftest import MSAICERR_PATH, CommonAssert
import os
import pytest
import sys
import shutil
from unittest import mock
from unittest.mock import Mock
from pathlib import Path
import subprocess
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
sys.path.append(MSAICERR_PATH)
sys.path.append(f'{cur_abspath}/../res/package')


class TestUtilsMethods(CommonAssert):
    def test_print_info_log(self):
        utils.print_info_log('test info log')

    def test_print_error_log(self):
        utils.print_error_log('test error log')

    def test_print_warn_log(self):
        utils.print_warn_log('test warn log')

    def test_check_path_special_character_is_empty(self):
        with pytest.raises(utils.AicErrException) as error:
            utils.check_path_special_character("")
        self.assertEqual(error.value.args[0],
                         Constant.MS_AICERR_INVALID_PARAM_ERROR)

    # def test_check_path_special_character_is_space(self):
    #     with pytest.raises(utils.AicErrException) as error:
    #         utils.check_path_special_character(os.path.join(cur_abspath,
    #                                                         '../res/ori_data/complie_path'))
    #     self.assertEqual(error.value.args[0],
    #                      Constant.MS_AICERR_INVALID_PARAM_ERROR)

    # def test_check_path_valid(self):
    #     with pytest.raises(utils.AicErrException) as error:
    #         utils.check_path_valid(";*")
    #     self.assertEqual(error.value.args[0],
    #                      Constant.MS_AICERR_INVALID_PARAM_ERROR)

    # def test_check_path_valid_accessible(self):
    #     with pytest.raises(utils.AicErrException) as error:
    #         with mock.patch('os.path.exists', return_value=False):
    #             with mock.patch('os.makedirs', side_effect=OSError):
    #                 utils.check_path_valid(
    #                     os.path.join(cur_abspath,'../res/ori_data/complie_path'), True, True)
    #     self.assertEqual(error.value.args[0],
    #                      Constant.MS_AICERR_INVALID_PATH_ERROR)

    def test_get_str_value_empty(self):
        hexstr_value = utils.get_str_value("")
        self.assertEqual(hexstr_value, -1)

    def test_get_str_value_hex(self):
        hexstr_value = utils.get_str_value("0x11")
        self.assertEqual(hexstr_value, 17)

    def test_get_str_value_dec(self):
        hexstr_value = utils.get_str_value("11")
        self.assertEqual(hexstr_value, 11)

    def test_get_str_value_dec(self):
        hexstr_value = utils.get_str_value("1.34")
        self.assertEqual(hexstr_value, -1)

    def test_get_hexstr_value_0(self):
        hexstr_value = utils.get_hexstr_value("0")
        self.assertEqual(hexstr_value, 0)

    def test_get_hexstr_value(self):
        hexstr_value = utils.get_hexstr_value("A")
        self.assertEqual(hexstr_value, 10)

    def test_get_hexstr_value_invalid(self):
        hexstr_value = utils.get_hexstr_value("G")
        self.assertEqual(hexstr_value, -1)

    def test_hexstr_to_list_bin(self):
        hexstr_value = utils.hexstr_to_list_bin("0x15")
        self.assertEqual(hexstr_value, [4, 2, 0])

    def test_get_01_from_hexstr(self):
        hexstr_value = utils.get_01_from_hexstr("0x15", 3, 0)
        self.assertEqual(hexstr_value, '0101')

    def test_execute_command(self, mocker):
        with pytest.raises(utils.AicErrException) as error:
            mocker.patch('tempfile.SpooledTemporaryFile',
                            side_effect=FileNotFoundError)
            utils.execute_command('')
        self.assertEqual(error.value.args[0],
                         Constant.MS_AICERR_EXECUTE_COMMAND_ERROR)

    def test_run_cmd_output_pass(self):
        res = utils.run_cmd_output('ls')
        assert res

    def test_run_cmd_output_failed(self):
        res = utils.run_cmd_output('hello')
        assert not res

    def test_get_inquire_result_failed(self, mocker):
        mocker.patch('ms_interface.utils.execute_command', return_value=(1, ''))
        res = utils.get_inquire_result(['xxx'], '', match_dict=True)
        assert res == []

        mocker.patch('ms_interface.utils.execute_command', return_value=(0, ''))
        res = utils.get_inquire_result(['xxx'], 'asfdd', match_dict=True)
        assert res == []

    @pytest.mark.skip
    def test_run_dirty_ub(self, mocker):
        temp_dir = Path(cur_abspath).joinpath("../test_run_dirty_ub")
        aic_err_info = AicErrorInfo()
        aic_err_info.kernel_path = '../res/ori_data/asys_output_20230713074104794/dfx/ops/0/'
        aic_err_info.kernel_name = "te_gatherv2_657cb48fa1743a43209d7bc779fe8c294760a5b09b3079a3323fdf18376fc408_1"
        single_op_case = SingleOpCase(aic_err_info, 'op_test')
        config_file = single_op_case.generate_config()
        config_file.update({"compile_temp_dir": temp_dir})
        res = subprocess.run('ls')
        mocker.patch.object(Path, "exists", return_value=False)
        mocker.patch("shutil.which", return_value=True)
        mocker.patch("subprocess.run", return_value=res)
        mocker.patch.object(AscendOpKernelRunner, 'run')
        mocker.patch.object(AscendRTSApi, '_load_runtime_so')
        mocker.patch.object(AscendRTSApi, 'register_kernel_launch_fill_func')
        mocker.patch.object(AscendRTSApi, 'set_device')
        mocker.patch.object(AscendRTSApi, 'create_stream')
        mocker.patch.object(AscendRTSApi, 'reset')
        mocker.patch.object(AscendRTSApi, 'destroy_stream')
        op_kernel_path = temp_dir.joinpath(
            ModeCustom.DIRTY_CUSTOM.value, 'op_kernel')
        op_kernel_path.mkdir(parents=True, exist_ok=True)
        op_kernel_path.joinpath('add_custom.cpp').write_text("test")
        compile_file_path = temp_dir.joinpath(ModeCustom.DIRTY_CUSTOM.value, 'build_out',
                                              'op_kernel')
        compile_file_path.mkdir(parents=True, exist_ok=True)
        compile_file_path.joinpath(f'{ModeCustom.DIRTY_CUSTOM.value}_add_custom.o').write_text(
            "test")
        shutil.copy(Path(cur_abspath).joinpath(
            "../res/ori_data/collect_milan/collection",
            "DirtyCustom_ab1b6750d7f510985325b603cb06dc8b.json"),
            compile_file_path)

        res = run_dirty_ub_tik(config_file, "Ascend910B1", 0)
        assert res