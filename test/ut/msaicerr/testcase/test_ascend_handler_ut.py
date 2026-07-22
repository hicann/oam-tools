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

import sys

from unittest import mock
from unittest.mock import Mock, patch
import numpy as np
import pytest

from conftest import MSAICERR_PATH, CommonAssert
sys.path.append(MSAICERR_PATH)


class TestAscendHandlerBaseMethods(CommonAssert):
    def test_is_chip_handler_match(self):
        from ms_interface.ascend_handler import AscendHandlerBase

        class TestHandler(AscendHandlerBase):
            handle_chip_pre = "Ascend910"

        handler = TestHandler()
        assert handler.is_chip_handler("Ascend910B1")

    def test_is_chip_handler_no_match(self):
        from ms_interface.ascend_handler import AscendHandlerBase

        class TestHandler(AscendHandlerBase):
            handle_chip_pre = "Ascend910"

        handler = TestHandler()
        assert not handler.is_chip_handler("Ascend310")

    def test_is_chip_handler_exact_match(self):
        from ms_interface.ascend_handler import AscendHandlerBase
        
        class TestHandler(AscendHandlerBase):
            handle_chip_pre = "Ascend910"

        handler = TestHandler()
        assert handler.is_chip_handler("Ascend910")

    def test_handle_chip_pre_default(self):
        from ms_interface.ascend_handler import AscendHandlerBase
        handler = AscendHandlerBase()
        self.assertEqual(handler.handle_chip_pre, "")

    @pytest.mark.skip
    def test_run_dirty_ub_success(self, mocker):
        from ms_interface.ascend_handler import AscendHandlerBase
        mocker.patch("ms_interface.ascend950.compile_op.CompileOP.get_ub_size",
                     return_value=1024)
        mocker.patch("ms_interface.ascend950.compile_op.CompileOP.get_compile_file",
                     return_value=("/tmp/test.bin", "/tmp/test.json"))
        mocker.patch("ms_interface.single_op_test_frame.common.ascend_tbe_op.AscendOpKernelRunner.__enter__")
        mocker.patch("ms_interface.single_op_test_frame.common.ascend_tbe_op.AscendOpKernelRunner.__exit__")
        mock_runner = mocker.patch(
            "ms_interface.single_op_test_frame.common.ascend_tbe_op.AscendOpKernelRunner.run",
            return_value=True)

        handler = AscendHandlerBase()
        handler.handle_chip_pre = "Ascend910B1"
        configs = {"compile_temp_dir": "/tmp/compile"}
        result = handler.run_dirty_ub(configs, "Ascend910B1", 0)
        assert result
        mock_runner.assert_called_once()

    @pytest.mark.skip
    def test_run_dirty_ub_ub_size_zero(self, mocker):
        from ms_interface.ascend_handler import AscendHandlerBase
        mocker.patch("ms_interface.ascend950.compile_op.CompileOP.get_ub_size",
                     return_value=0)

        handler = AscendHandlerBase()
        configs = {"compile_temp_dir": "/tmp/compile"}
        result = handler.run_dirty_ub(configs, "Ascend910B1", 0)
        assert not result

    @pytest.mark.skip
    def test_run_dirty_ub_compile_failure(self, mocker):
        from ms_interface.ascend_handler import AscendHandlerBase
        mocker.patch("ms_interface.ascend950.compile_op.CompileOP.get_ub_size",
                     return_value=1024)
        mocker.patch("ms_interface.ascend950.compile_op.CompileOP.get_compile_file",
                     side_effect=Exception("compile failed"))

        handler = AscendHandlerBase()
        configs = {"compile_temp_dir": "/tmp/compile"}
        result = handler.run_dirty_ub(configs, "Ascend910B1", 0)
        assert not result

    @pytest.mark.skip
    def test_run_dirty_ub_no_build_result(self, mocker):
        from ms_interface.ascend_handler import AscendHandlerBase
        mocker.patch("ms_interface.ascend950.compile_op.CompileOP.get_ub_size",
                     return_value=1024)
        mocker.patch("ms_interface.ascend950.compile_op.CompileOP.get_compile_file",
                     return_value=())

        handler = AscendHandlerBase()
        configs = {"compile_temp_dir": "/tmp/compile"}
        result = handler.run_dirty_ub(configs, "Ascend910B1", 0)
        assert not result

    @pytest.mark.skip
    def test_get_compile_file_success(self, mocker):
        from ms_interface.ascend_handler import AscendHandlerBase
        mock_compile_op = mocker.patch(
            "ms_interface.ascend950.compile_op.CompileOP")
        mock_instance = mock_compile_op.return_value
        mock_instance.get_compile_file.return_value = ("/tmp/test.bin", "/tmp/test.json")

        class TestHandler(AscendHandlerBase):
            handle_chip_pre = "Ascend910"

        handler = TestHandler()
        result = handler.get_compile_file("Ascend910B1", "/tmp")
        self.assertEqual(result, ("/tmp/test.bin", "/tmp/test.json"))

    def test_get_compile_file_constructs_compile_op_correctly(self, mocker):
        # patch where CompileOP is used (in ascend_handler's namespace)
        mocker.patch("ms_interface.ascend_handler.CompileOP")
        from ms_interface.ascend_handler import AscendHandlerBase
        mock_compile_op = mocker.patch(
            "ms_interface.ascend_handler.CompileOP")
        mock_instance = mock_compile_op.return_value
        mock_instance.get_compile_file.return_value = ("/tmp/test.bin", "/tmp/test.json")

        class TestHandler(AscendHandlerBase):
            handle_chip_pre = "Ascend910"

        handler = TestHandler()
        handler.get_compile_file("Ascend910B1", "/tmp")
        mock_compile_op.assert_called_once()
        call_args = mock_compile_op.call_args[0]
        self.assertEqual(call_args[0], "AddCustom")
