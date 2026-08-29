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
import runpy
import sys
from unittest.mock import Mock

from conftest import MSAICERR_PATH
from ms_interface import run_dirty_ub as rdu

sys.path.append(MSAICERR_PATH)

TEST_SINGLE_OP = os.path.join(MSAICERR_PATH, "test_single_op.py")


def test_run_dirty_ub_tik_import_error(mocker, tmp_path):
    # Force the `from tbe import tik` import to fail.
    mocker.patch.dict(sys.modules, {"tbe": None, "tbe.common": None,
                                    "tbe.common.platform": None})
    result = rdu.run_dirty_ub_tik({"compile_temp_dir": str(tmp_path / "x")}, "Ascend910B", 0)
    assert result is False


def test_run_dirty_ub_tik_attribute_error(mocker, tmp_path):
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name.startswith("tbe"):
            raise AttributeError("module 'numpy' has no attribute 'bool'")
        return real_import(name, *args, **kwargs)

    mocker.patch("builtins.__import__", side_effect=mock_import)
    result = rdu.run_dirty_ub_tik({"compile_temp_dir": str(tmp_path / "x")}, "Ascend910B", 0)
    assert result is False


def test_run_dirty_ub_dispatch_to_handler(mocker):
    handler = Mock()
    handler.is_chip_handler.return_value = True
    handler.run_dirty_ub.return_value = True
    mocker.patch("ms_interface.utils.load_ascend_handlers", return_value=[handler])
    assert rdu.run_dirty_ub({}, "Ascend950", 0) is True


def test_run_dirty_ub_fallback_to_tik(mocker):
    handler = Mock()
    handler.is_chip_handler.return_value = False
    mocker.patch("ms_interface.utils.load_ascend_handlers", return_value=[handler])
    mocker.patch.object(rdu, "run_dirty_ub_tik", return_value=True)
    assert rdu.run_dirty_ub({}, "Ascend910B", 0) is True


def test_single_op_script_executes(mocker):
    # test_single_op.py is a sample entry script that calls SingleOpCase.run()
    # at module top level. Execute it in an isolated namespace with run()
    # mocked so it does not touch the real device or sys.modules.
    run_mock = mocker.patch(
        "ms_interface.single_op_test_frame.single_op_case.SingleOpCase.run",
        return_value="ok",
    )
    runpy.run_path(TEST_SINGLE_OP, run_name="not_main")
    assert run_mock.called

