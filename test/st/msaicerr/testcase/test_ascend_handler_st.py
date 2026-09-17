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
import tempfile
from unittest.mock import Mock

from conftest import MSAICERR_PATH

sys.path.append(MSAICERR_PATH)
from ms_interface import ascend_handler, utils
from ms_interface.ascend350.ascend350_handler import Ascend350Handler
from ms_interface.ascend950.ascend950_handler import Ascend950Handler
from ms_interface.ascend960dt.ascend960dt_handler import Ascend960dtHandler


def make_compile_op(mocker, ub_size=1024, compile_file=None, compile_exc=None):
    """构造 CompileOP 桩并挂到被测模块上，返回该桩以便断言调用情况。"""
    compile_op = Mock()
    compile_op.get_ub_size.return_value = ub_size
    if compile_exc is not None:
        compile_op.get_compile_file.side_effect = compile_exc
    else:
        compile_op.get_compile_file.return_value = compile_file
    mocker.patch.object(ascend_handler, "CompileOP", return_value=compile_op)
    return compile_op


def test_ascend950_matches_own_prefix():
    assert Ascend950Handler().is_chip_handler("Ascend950B") is True


def test_ascend950_rejects_other_chip():
    assert Ascend950Handler().is_chip_handler("Ascend960DT") is False


def test_ascend960dt_matches_own_prefix():
    assert Ascend960dtHandler().is_chip_handler("Ascend960DT") is True


def test_ascend960dt_rejects_other_chip():
    assert Ascend960dtHandler().is_chip_handler("Ascend950B") is False


def test_ascend350_matches_own_prefix():
    assert Ascend350Handler().is_chip_handler("Ascend350B4") is True


def test_ascend350_rejects_other_chip():
    assert Ascend350Handler().is_chip_handler("Ascend950B") is False


def test_other_handlers_reject_ascend350():
    assert Ascend950Handler().is_chip_handler("Ascend350") is False
    assert Ascend960dtHandler().is_chip_handler("Ascend350") is False


def test_registry_auto_discovers_ascend350_handler():
    # 注册表靠运行时目录扫描自动发现（无硬编码列表），新增 ascend350 目录即自动生效
    handlers = utils.load_ascend_handlers()
    names = [type(h).__name__ for h in handlers]
    assert "Ascend350Handler" in names


def test_registry_dispatches_ascend350_to_single_handler():
    # Ascend350 平台 soc_version 应唯一命中 Ascend350Handler，不落到其它 handler 或 TIK 兜底
    handlers = utils.load_ascend_handlers()
    matched = [h for h in handlers if h.is_chip_handler("Ascend350B4")]
    assert [type(h).__name__ for h in matched] == ["Ascend350Handler"]


def test_run_dirty_ub_get_ub_size_zero_skips(mocker):
    compile_op = make_compile_op(mocker, ub_size=0)

    ret = Ascend950Handler().run_dirty_ub(
        {"compile_temp_dir": tempfile.gettempdir()}, "Ascend950B", 0
    )

    assert ret is False
    compile_op.get_compile_file.assert_not_called()


def test_run_dirty_ub_compile_exception_skips(mocker):
    # 编译子进程可能因环境缺失抛任意异常，须兜底为跳过
    make_compile_op(mocker, compile_exc=RuntimeError("compile boom"))

    ret = Ascend950Handler().run_dirty_ub(
        {"compile_temp_dir": tempfile.gettempdir()}, "Ascend950B", 0
    )

    assert ret is False


def test_run_dirty_ub_empty_build_result_skips(mocker):
    make_compile_op(mocker, compile_file=None)

    ret = Ascend950Handler().run_dirty_ub(
        {"compile_temp_dir": tempfile.gettempdir()}, "Ascend950B", 0
    )

    assert ret is False


def test_get_compile_file_delegates_to_compile_op(mocker):
    compile_op = make_compile_op(mocker, compile_file=("add.o", "add.json"))

    result = Ascend950Handler().get_compile_file(
        "Ascend950B", os.path.join(tempfile.gettempdir(), "build")
    )

    assert result == ("add.o", "add.json")
    compile_op.get_compile_file.assert_called_once_with(
        os.path.join(tempfile.gettempdir(), "build")
    )
