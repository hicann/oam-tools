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
from ms_interface.single_op_test_frame.common import logger

sys.path.append(MSAICERR_PATH)


@pytest.fixture(autouse=True)
def _restore_level():
    # restore default level after each test so others are unaffected
    yield
    logger.set_logger_level("ERROR")


def test_set_logger_level():
    logger.set_logger_level("DEBUG")
    assert logger.Constant.LOG_LEVEL == "DEBUG"


def test_log_outputs(capsys):
    logger.log("ERROR", "file.py", 10, "a message")
    out = capsys.readouterr().out
    assert "ERROR" in out
    assert "file.py" in out
    assert "a message" in out


def test_log_warn(capsys):
    logger.log_warn("warn message")
    assert "WARN" in capsys.readouterr().out


def test_log_debug_enabled(capsys):
    logger.set_logger_level("DEBUG")
    logger.log_debug("debug message")
    assert "DEBUG" in capsys.readouterr().out


def test_log_debug_disabled(capsys):
    logger.set_logger_level("ERROR")
    logger.log_debug("debug message")
    assert "debug message" not in capsys.readouterr().out


def test_log_info_enabled(capsys):
    logger.set_logger_level("INFO")
    logger.log_info("info message")
    assert "INFO" in capsys.readouterr().out


def test_log_info_disabled(capsys):
    logger.set_logger_level("ERROR")
    logger.log_info("info message")
    assert "info message" not in capsys.readouterr().out


def test_log_err_no_trace(capsys):
    logger.log_err("err message")
    assert "ERROR" in capsys.readouterr().out


def test_log_err_with_trace(capsys):
    try:
        raise ValueError("boom")
    except ValueError:
        logger.log_err("err message", print_trace=True)
    out = capsys.readouterr().out
    assert "ERROR" in out
    assert "Traceback" in out
