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

from ms_interface.single_op_test_frame.runtime import AscendRTSApi as RTSApi
from ms_interface.single_op_test_frame.common import ascend_tbe_op
from ms_interface.single_op_test_frame.common.ascend_tbe_op import AscendOpKernelRunner
from ms_interface.single_op_test_frame.common.ascend_tbe_op import AscendOpKernelParam
from ms_interface.single_op_test_frame.common.ascend_tbe_op import AscendOpKernelRunnerParam
from conftest import MSAICERR_PATH, CommonAssert
import sys
import ctypes
from typing import Union
from unittest.mock import Mock, mock_open
import numpy as np
import pytest

s = np.array([1, 2, 3, 4, 5])


te = Mock(name="te")
te.__name__ = "te"
sys.modules['te'] = te
sys.path.append(MSAICERR_PATH)


class AscendRTSApi:
    """
    Class AscendRTSApi
    """

    def __init__(self, simulator_mode: str = None, soc_version: str = None, simulator_lib_path: str = None,
                 simulator_dump_path: str = "./model"):
        self.rtsdll = None

    def malloc(self, memory_size: int) -> ctypes.c_void_p:
        c_memory_p = ctypes.c_void_p(memory_size)
        return c_memory_p

    def free(self, c_memory_p: ctypes.c_void_p):
        return ctypes.c_void_p(None)

    def memcpy(self, c_memory_p: ctypes.c_void_p, memory_size: int, data: Union[bytes, ctypes.c_void_p], data_size: int,
               memcpy_kind: str = "RT_MEMCPY_HOST_TO_HOST", retry_count: int = 0):
        return

    def get_c2c_ctrl_addr(self):
        return ctypes.c_void_p(None)


class AscendOpKernel:
    """
    Class AscendOpKernel
    """
    PageMemorySize = 0x200000  # 内存页大小
    MagicMemorySize = 0x80  # 前后各128个魔术字：0x55
    MagicData = 0x55
    ForwardDestroy = 1
    BackwardDestroy = 2

    def __init__(self, bin_path: str, json_path: str):
        self.block_dim = 8


class ChipInfoStub:

    def get_complete_platform(self):
        return "Ascend310"


@pytest.fixture()
def mock_runner(mocker):
    api_mock = Mock()
    api_mock.return_value = 1
    out_hbm_pointer_mock = Mock()
    out_hbm_pointer_mock.value = 1
    api_mock.malloc.return_value = out_hbm_pointer_mock
    api_mock.memcpy.return_value = None
    api_mock.get_data_from_hbm.return_value = (b'xxx', 0)
    mocker.patch.object(AscendOpKernelRunner,
                        'get_rts_api', return_value=api_mock)
    runner = AscendOpKernelRunner()
    return runner


class TestClassAscendOpKernelRunner(CommonAssert):
    def test_exec_single_case(self, mocker):
        kernel = AscendOpKernel("", "")
        mocker.patch.object(AscendOpKernelRunner,
                            '__init__', return_value=None)
        mocker.patch.object(AscendOpKernelRunner,
                            '_fill_binary', return_value=None)
        mocker.patch.object(AscendOpKernelRunner,
                            '_fill_tiling', return_value=None)
        mocker.patch.object(AscendOpKernelRunner,
                            '_execute_kernel', return_value=[0, 0])
        mocker.patch.object(AscendOpKernelRunner,
                            '_check_magic_memory', return_value=0)
        mocker.patch.object(AscendOpKernelRunner,
                            '__init__', return_value=None)
        runner = AscendOpKernelRunner()
        ascend_op_param = AscendOpKernelRunnerParam(kernel=kernel,
                                                    inputs=None,
                                                    output_input_ref=None,
                                                    tiling_data=None,
                                                    block_dim=8,
                                                    actual_out_info=None,
                                                    bin_list=True,
                                                    sub_ptr_addrs=None,
                                                    ffts_addrs_num=0,
                                                    workspace=0,
                                                    op_test='')
        ret_value = runner.exec_single_case(ascend_op_param)
        self.assertEqual(ret_value, [[], [0, 0, 0]])

    def test_execute_kernel(self, mocker, mock_runner):
        api_mock = Mock()
        api_mock.register_kernel_launch_fill_func.side_effect = None
        mocker.patch.object(RTSApi, '_load_runtime_so', return_value=None)
        runner = mock_runner
        runner.profiling = True
        kernel_mock = Mock()
        kernel_mock.is_registered_to_device.return_value = False
        res = runner._execute_kernel(kernel_mock, [1, 1], 1, 'xxx')
        assert isinstance(res, list)

    def test_fill_workspace(self, mocker, mock_runner):
        kernel_mock = Mock()
        wksp_hbm_pointers = []
        kernel_args = []
        mode = 'tail'
        runner = mock_runner

        kernel_mock.workspace = [1]
        kernel_mock.parameters = [
            {'dtype': 'int8', 'init_value': 1}, None, None, None, None]
        mocker.patch.object(AscendOpKernelParam,
                            'sync_to_device', return_value=None)
        runner._fill_workspace(
            kernel_mock, 0, wksp_hbm_pointers, kernel_args, mode)

    def test_fill_workspace_no_parameter(self, mocker, mock_runner):
        kernel_mock = Mock()
        kernel_mock.workspace = [-1]
        kernel_mock.parameters = [None, None, None, None, None]
        wksp_hbm_pointers = []
        kernel_args = []
        mode = 'tail'
        runner = mock_runner
        runner._fill_workspace(
            kernel_mock, 0, wksp_hbm_pointers, kernel_args, mode)

    def test_fill_binary_subptr_no_args_list(self, mocker, mock_runner):
        mocker.patch.object(AscendOpKernelParam,
                            'sync_to_device', return_value=None)
        runner = mock_runner
        runner._fill_binary_subptr(['xxx'], 1, [], {}, 'magic')

    def test_fill_binary_subptr(self, mocker, mock_runner):
        mock_data = b'\xDE\xAD\xBE\xEF'
        mock_open = mocker.mock_open(read_data=mock_data)
        mocker.patch('builtins.open', mock_open)
        runner = AscendOpKernelRunner()
        assert runner._fill_binary_subptr(
            ['xxx'], 1, [], {'args_list': ['1']}, 'magic') is None

    def test_create_output_param_with_pages_no_param(self, mocker, mock_runner):
        kernel_mock = Mock()
        kernel_mock.workspace = []
        kernel_mock.parameters = [None]
        mode = 'tail'
        data_list = [{'size': 4, 'dtype': 'float32', 'shape': (1,)}, [], (1,)]
        runner = mock_runner
        res = runner._create_output_param_with_pages(
            kernel_mock, data_list, mode)
        assert isinstance(res, AscendOpKernelParam)

    def test_create_output_param_with_pages(self, mocker, mock_runner):
        kernel_mock = Mock()
        kernel_mock.workspace = [-1]
        kernel_mock.parameters = [{'dtype': 'int8', 'init_value': 1}]
        data_list = [{'size': 4, 'dtype': 'float32', 'shape': (1,)}, [], (1,)]
        mode = 'tail'
        runner = mock_runner
        res = runner._create_output_param_with_pages(
            kernel_mock, data_list, mode)
        assert isinstance(res, AscendOpKernelParam)

    def test_fill_inputs(self, mocker, mock_runner):
        runner = mock_runner

        inputs = [AscendOpKernelParam(np_data=np.zeros(1))]
        runner._fill_inputs(inputs, [], [], 'tail')

        inputs = ['xxx.npy']
        mocker.patch('numpy.load', return_value=np.zeros(1))
        runner._fill_inputs(inputs, [], [], 'tail')

        inputs = ['file_path']
        mocker.patch.object(AscendOpKernelParam,
                            'build_op_param_by_data_file', return_value=Mock())
        runner._fill_inputs(inputs, [], [], 'tail')

    def test_fill_outputs(self, mocker, mock_runner):
        kernel_mock = Mock()
        kernel_mock.workspace = [-1]
        kernel_mock.parameters = [{'dtype': 'int8', 'init_value': 1}]
        runner = mock_runner
        output_input_ref = ()
        actual_output_info = ({'size': 4, 'dtype': 'float32', 'shape': (1,)},)
        output_params = []
        kernel_args = []
        input_params = []
        res = runner._fill_outputs(kernel_mock, output_input_ref, actual_output_info,
                                   input_params, output_params, kernel_args, 'tail')
        assert res is None

    def test_fill_tiling(self, mocker, mock_runner):
        runner = mock_runner
        kernel_mock = Mock()
        runner._fill_tiling(kernel_mock, b'xx', [], [])

        kernel_mock.need_do_tiling = False
        runner._fill_tiling(kernel_mock, b'xx', [], [])

        runner._fill_tiling(Mock(), None, [], [])

    def test_check_magic_memory(self, mocker, mock_runner):
        runner = mock_runner
        runner._kernel_params = [Mock()]
        assert runner._check_magic_memory() == 1
        mocker.patch.object(runner, '_check_magic', side_effect=[False, True])
        assert runner._check_magic_memory() == 2
        mocker.patch.object(runner, '_check_magic', return_value=False)
        assert runner._check_magic_memory() == 0

    def test_build_op_param_by_data_file(self, mocker):
        with pytest.raises(IOError):
            AscendOpKernelParam.build_op_param_by_data_file(
                'xxx', 'int8', [1, 1])

        mocker.patch('os.path.exists', return_value=True)
        mocker.patch('numpy.fromfile', return_value=np.zeros(1))
        res = AscendOpKernelParam.build_op_param_by_data_file(
            'xxx', 'int8', [1, 1])
        assert isinstance(res, AscendOpKernelParam)

        mocker.patch(
            'ms_interface.single_op_test_frame.utils.shape_utils.calc_shape_size', return_value=-1)
        with pytest.raises(RuntimeError):
            AscendOpKernelParam.build_op_param_by_data_file(
                'xxx', 'int8', [1, 1])

        mocker.patch(
            'ms_interface.single_op_test_frame.utils.shape_utils.calc_shape_size', return_value=2)
        with pytest.raises(RuntimeError):
            AscendOpKernelParam.build_op_param_by_data_file(
                'xxx', 'int8', [1, 1])

    def test_hbm_pointer_case(self, mocker):
        c_memory_p = ctypes.c_void_p(None)
        kernel = AscendRTSApi()
        runner = AscendOpKernelParam(None, (0,), "float32", kernel, c_memory_p)
        mocker.patch.object(AscendOpKernelParam, '__init__', return_value=None)
        res = runner.hbm_pointer.value
        self.assertEqual(res, 1024)

    def test_sync_to_device_case1(self, mocker):
        c_memory_p = ctypes.c_void_p(None)
        kernel = AscendRTSApi()
        runner = AscendOpKernelParam(s, (1,), "float32", kernel, c_memory_p)
        mocker.patch.object(AscendOpKernelParam, '__init__', return_value=None)
        res = runner.sync_to_device(kernel, 'tail')
        self.assertEqual(res, None)

    def test_sync_to_device_case(self, mocker):
        c_memory_p = ctypes.c_void_p(None)
        kernel = AscendRTSApi()
        runner = AscendOpKernelParam(None, (0,), "float32", kernel, c_memory_p)
        mocker.patch.object(AscendOpKernelParam, '__init__', return_value=None)
        res = runner.sync_to_device(kernel, 'tail')
        self.assertEqual(res, None)

    def test_is_in_device_case(self, mocker):
        c_memory_p = ctypes.c_void_p(10)
        kernel = AscendRTSApi()
        runner = AscendOpKernelParam(None, (0,), "float32", kernel, c_memory_p)
        mocker.patch.object(AscendOpKernelParam, '__init__', return_value=None)
        res = runner.is_in_device()
        self.assertEqual(res, True)

    def test_release_device_case(self, mocker):
        c_memory_p = ctypes.c_void_p(10)
        kernel = AscendRTSApi()
        runner = AscendOpKernelParam(None, (1,), "float32", kernel, c_memory_p)
        mocker.patch.object(AscendOpKernelParam, '__init__', return_value=None)
        res = runner.sync_to_device(kernel, 'tail')
        res1 = runner.release_device()
        self.assertEqual(res1, None)

    def test_run(self, mocker):
        mocker.patch.object(AscendOpKernelRunner,
                            '__init__', return_value=None)
        runner = AscendOpKernelRunner()
        kernel = AscendOpKernel("", "")
        mocker.patch.object(AscendOpKernelRunner,
                            'exec_single_case', return_value=[0, [0, 0, 0]])
        ret_value = runner.run(kernel)
        self.assertEqual(True, "exec single op case success" in ret_value)
        mocker.patch.object(AscendOpKernelRunner,
                            'exec_single_case', return_value=[0, [1, 0, 0]])
        ret_value = runner.run(kernel)
        self.assertEqual(True, "exec single op case failed" in ret_value)
        mocker.patch.object(AscendOpKernelRunner,
                            'exec_single_case', return_value=[0, [0, 0, 1]])
        ret_value = runner.run(kernel)
        self.assertEqual(True, "memery status check" in ret_value)
        mocker.patch.object(AscendOpKernelRunner,
                            'exec_single_case', return_value=[0, [0, 0, 2]])
        ret_value = runner.run(kernel)
        self.assertEqual(True, "memery status check" in ret_value)

    def test_fill_binary(self, mocker):
        mocker.patch.object(ascend_tbe_op.DSMIInterface,
                            '__init__', return_value=None)
        mocker.patch.object(ascend_tbe_op.DSMIInterface,
                            'get_chip_info', return_value=ChipInfoStub())
        mocker.patch.object(AscendOpKernelRunner,
                            '__init__', return_value=None)
        runner = AscendOpKernelRunner()
        runner.ascend_device = None
        runner._kernel_params = []
        mocker.patch('builtins.open', new_callable=mock_open,
                     read_data=b'\x00')
        c_memory_p = ctypes.c_void_p(None)
        kernel = AscendRTSApi()
        runner1 = AscendOpKernelParam(s, (1,), "float32", kernel, c_memory_p)
        mocker.patch.object(AscendOpKernelParam,
                            'build_op_param_by_np_data', return_value=runner1)
        mocker.patch.object(runner1, 'sync_to_device', return_value=None)
        res1 = runner._fill_binary("./", [], [], {}, "")
        self.assertEqual(res1, None)
