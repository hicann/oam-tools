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

import pytest

from conftest import MSAICERR_PATH

sys.path.append(MSAICERR_PATH)
from ms_interface.single_op_test_frame.common import logger


@pytest.fixture(autouse=True)
def restore_level():
    # 用例会改全局日志级别，跑完须恢复"进来时的原值"而非固定写 ERROR：
    # 固定重置会把同进程后续测试模块的默认级别永久改掉，抑制其预期输出。
    original = logger.Constant.LOG_LEVEL
    yield
    logger.set_logger_level(original)


def test_set_logger_level():
    logger.set_logger_level("DEBUG")
    assert logger.Constant.LOG_LEVEL == "DEBUG"


def test_log_outputs_level_file_and_msg(capsys):
    logger.log("ERROR", "some_file.py", 42, "a message")
    out = capsys.readouterr().out
    assert "ERROR" in out
    assert "some_file.py" in out
    assert "42" in out
    assert "a message" in out


def test_log_warn(capsys):
    logger.log_warn("warn message")
    out = capsys.readouterr().out
    assert "WARN" in out
    assert "warn message" in out


def test_log_debug_enabled(capsys):
    logger.set_logger_level("DEBUG")
    logger.log_debug("debug message")
    out = capsys.readouterr().out
    assert "DEBUG" in out
    assert "debug message" in out


def test_log_debug_suppressed_when_level_higher(capsys):
    logger.set_logger_level("ERROR")
    logger.log_debug("debug message")
    assert "debug message" not in capsys.readouterr().out


def test_log_info_enabled(capsys):
    logger.set_logger_level("INFO")
    logger.log_info("info message")
    out = capsys.readouterr().out
    assert "INFO" in out
    assert "info message" in out


def test_log_info_suppressed_when_level_higher(capsys):
    logger.set_logger_level("ERROR")
    logger.log_info("info message")
    assert "info message" not in capsys.readouterr().out


def test_log_err_without_trace(capsys):
    logger.log_err("err message")
    out = capsys.readouterr().out
    assert "ERROR" in out
    assert "Traceback" not in out


def test_log_err_with_trace(capsys):
    try:
        raise ValueError("boom")
    except ValueError:
        logger.log_err("err message", print_trace=True)
    out = capsys.readouterr().out
    assert "ERROR" in out
    assert "Traceback" in out
    assert "boom" in out


def test_log_err_with_trace_but_no_active_exception(capsys):
    # print_trace=True 但无异常上下文时，format_exception 结果为 "NoneType: None"
    logger.log_err("err message", print_trace=True)
    assert "ERROR" in capsys.readouterr().out
