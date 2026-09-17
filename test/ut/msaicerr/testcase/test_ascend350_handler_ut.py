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

from conftest import MSAICERR_PATH, CommonAssert

sys.path.append(MSAICERR_PATH)

from ms_interface.ascend350.ascend350_handler import Ascend350Handler
from ms_interface.ascend_handler import AscendHandlerBase


class TestAscend350HandlerMethods(CommonAssert):
    def test_class_is_subclass_of_ascend_handler_base(self):
        assert issubclass(Ascend350Handler, AscendHandlerBase)

    def test_handle_chip_pre_value(self):
        self.assertEqual(Ascend350Handler.handle_chip_pre, "Ascend350")

    def test_compile_chip_value(self):
        # msopgen 暂未适配 Ascend350，编译复用 Ascend950
        self.assertEqual(Ascend350Handler.compile_chip, "Ascend950")

    def test_is_chip_handler_match(self):
        handler = Ascend350Handler()
        result = handler.is_chip_handler("Ascend350")
        assert result

    def test_is_chip_handler_partial_match(self):
        handler = Ascend350Handler()
        result = handler.is_chip_handler("Ascend350B4")
        assert result

    def test_is_chip_handler_no_match(self):
        handler = Ascend350Handler()
        result = handler.is_chip_handler("Ascend910B1")
        assert not result

    def test_is_chip_handler_rejects_ascend950(self):
        handler = Ascend350Handler()
        result = handler.is_chip_handler("Ascend950B")
        assert not result

    def test_instance_of_ascend_handler_base(self):
        handler = Ascend350Handler()
        assert isinstance(handler, AscendHandlerBase)

    def test_run_dirty_ub_compiles_with_ascend950(self, mocker, tmp_path):
        # 单算子复跑：soc_version 为 Ascend350，但传给 msopgen 的编译 chip 是 Ascend950
        mock_compile_op = mocker.patch("ms_interface.ascend_handler.CompileOP")
        mock_instance = mock_compile_op.return_value
        mock_instance.get_ub_size.return_value = 0

        handler = Ascend350Handler()
        configs = {"compile_temp_dir": str(tmp_path / "compile")}
        result = handler.run_dirty_ub(configs, "Ascend350B4", 0)
        assert not result
        call_args = mock_compile_op.call_args[0]
        self.assertEqual(call_args[3], "Ascend350B4")
        self.assertEqual(call_args[4], "Ascend950")

    def test_get_compile_file_compiles_with_ascend950(self, mocker, tmp_path):
        # 标杆算子编译：soc_version 为 Ascend350，但传给 msopgen 的编译 chip 是 Ascend950
        mock_compile_op = mocker.patch("ms_interface.ascend_handler.CompileOP")
        mock_instance = mock_compile_op.return_value
        mock_instance.get_compile_file.return_value = (
            str(tmp_path / "test.bin"),
            str(tmp_path / "test.json"),
        )

        handler = Ascend350Handler()
        build_result = handler.get_compile_file("Ascend350B4", str(tmp_path))
        self.assertEqual(build_result[0], str(tmp_path / "test.bin"))
        call_args = mock_compile_op.call_args[0]
        self.assertEqual(call_args[0], "AddCustom")
        self.assertEqual(call_args[3], "Ascend350B4")
        self.assertEqual(call_args[4], "Ascend950")
