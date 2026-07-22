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

from unittest.mock import Mock, patch
import pytest

from conftest import MSAICERR_PATH, CommonAssert
sys.path.append(MSAICERR_PATH)


class TestGoldenOpMethods(CommonAssert):
    def test_get_block_dim_uses_vector_core_count(self, mocker):
        mock_dsmi = mocker.patch("ms_interface.golden_op.DSMIInterface")
        mock_instance = mock_dsmi.return_value
        mock_instance.get_vector_core_count.return_value = 8
        mock_instance.get_aicore_count.return_value = 16

        from ms_interface.golden_op import GoldenOp
        result = GoldenOp.get_block_dim(0)
        self.assertEqual(result, 8)
        mock_instance.get_vector_core_count.assert_called_once_with(0)

    def test_get_block_dim_fallback_to_aicore_count(self, mocker):
        mock_dsmi = mocker.patch("ms_interface.golden_op.DSMIInterface")
        mock_instance = mock_dsmi.return_value
        mock_instance.get_vector_core_count.return_value = 0
        mock_instance.get_aicore_count.return_value = 24

        from ms_interface.golden_op import GoldenOp
        result = GoldenOp.get_block_dim(0)
        self.assertEqual(result, 24)
        mock_instance.get_aicore_count.assert_called_once_with(0)

    @pytest.mark.skip
    def test_run_golden_op_success(self, mocker):
        mocker.patch("ms_interface.golden_op.get_compile_file",
                     return_value=("/tmp/test.o", "/tmp/test.json"))
        mocker.patch("ms_interface.golden_op.DSMIInterface")
        mocker.patch("ms_interface.golden_op.AscendOpKernel")
        mock_runner = mocker.patch(
            "ms_interface.golden_op.AscendOpKernelRunner")
        mock_instance = mock_runner.return_value.__enter__.return_value
        mock_instance.run.return_value = "success"

        from ms_interface.golden_op import GoldenOp
        golden_op = GoldenOp()
        result = golden_op.run_golden_op("Ascend910B1", 0, "/tmp")
        assert result

    @pytest.mark.skip
    def test_run_golden_op_no_build_result(self, mocker):
        mocker.patch("ms_interface.golden_op.get_compile_file",
                     return_value=[])

        from ms_interface.golden_op import GoldenOp
        golden_op = GoldenOp()
        result = golden_op.run_golden_op("Ascend910B1", 0, "/tmp")
        assert not result

    @pytest.mark.skip
    def test_run_golden_op_execute_failed(self, mocker):
        mocker.patch("ms_interface.golden_op.get_compile_file",
                     return_value=("/tmp/test.o", "/tmp/test.json"))
        mocker.patch("ms_interface.golden_op.DSMIInterface")
        mocker.patch("ms_interface.golden_op.AscendOpKernel")
        mock_runner = mocker.patch(
            "ms_interface.golden_op.AscendOpKernelRunner")
        mock_instance = mock_runner.return_value.__enter__.return_value
        mock_instance.run.return_value = "Execute single op case failed: error"

        from ms_interface.golden_op import GoldenOp
        golden_op = GoldenOp()
        result = golden_op.run_golden_op("Ascend910B1", 0, "/tmp")
        assert not result

    @pytest.mark.skip
    def test_main_entry_success(self, mocker):
        mocker.patch("ms_interface.golden_op.get_compile_file",
                     return_value=("/tmp/test.o", "/tmp/test.json"))
        mocker.patch("ms_interface.golden_op.DSMIInterface")
        mocker.patch("ms_interface.golden_op.AscendOpKernel")
        mock_runner = mocker.patch(
            "ms_interface.golden_op.AscendOpKernelRunner")
        mock_instance = mock_runner.return_value.__enter__.return_value
        mock_instance.run.return_value = "success"
        mocker.patch("sys.argv", ["golden_op.py", "Ascend910B1", "0", "/tmp"])

        from ms_interface.golden_op import GoldenOp
        # just test run_golden_op directly since __main__ block runs at import
        golden_op = GoldenOp()
        result = golden_op.run_golden_op("Ascend910B1", 0, "/tmp")
        assert result

    def test_get_block_dim_static_method(self):
        from ms_interface.golden_op import GoldenOp
        assert callable(GoldenOp.get_block_dim)
