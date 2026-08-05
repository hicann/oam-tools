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

import logging
import sys
import threading

import pytest
from testcase.conftest import ASYS_SRC_PATH
sys.path.insert(0, ASYS_SRC_PATH)

from common.log import close_log, log_info, log_warning


class RecordHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def setup_module():
    print("TestLog ut test start.")


def teardown_module():
    print("TestLog ut test finish.")


class TestLog:

    @pytest.mark.parametrize("log_func", [log_info, log_warning])
    def test_force_log_bypasses_disable_and_restores_state(self, log_func):
        root_logger = logging.getLogger()
        original_disable_level = root_logger.manager.disable
        original_level = root_logger.level
        handler = RecordHandler()
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.DEBUG)
        close_log()
        try:
            log_func("hidden")
            log_func("forced", force=True)
            assert [record.getMessage() for record in handler.records] == ["forced"]
            assert root_logger.manager.disable == logging.WARNING
        finally:
            logging.disable(original_disable_level)
            root_logger.removeHandler(handler)
            root_logger.setLevel(original_level)

    def test_force_log_restores_state_when_logging_fails(self, mocker):
        root_logger = logging.getLogger()
        original_disable_level = root_logger.manager.disable
        logging.disable(logging.CRITICAL)
        mocker.patch("logging.info", side_effect=RuntimeError("logging failed"))
        try:
            with pytest.raises(RuntimeError, match="logging failed"):
                log_info("forced", force=True)
            assert root_logger.manager.disable == logging.CRITICAL
        finally:
            logging.disable(original_disable_level)

    def test_force_log_calls_are_serialized(self, mocker):
        first_entered = threading.Event()
        second_started = threading.Event()
        second_entered = threading.Event()
        release_first = threading.Event()
        original_disable_level = logging.getLogger().manager.disable

        def blocking_info(_):
            first_entered.set()
            release_first.wait(timeout=2)

        def record_warning(_):
            second_entered.set()

        def force_warning():
            second_started.set()
            log_warning("second", force=True)

        mocker.patch("logging.info", side_effect=blocking_info)
        mocker.patch("logging.warning", side_effect=record_warning)
        close_log()
        first_thread = threading.Thread(target=log_info, args=("first",), kwargs={"force": True})
        second_thread = threading.Thread(target=force_warning)
        try:
            first_thread.start()
            assert first_entered.wait(timeout=1)
            second_thread.start()
            assert second_started.wait(timeout=1)
            assert not second_entered.wait(timeout=0.2)
            release_first.set()
            first_thread.join(timeout=1)
            second_thread.join(timeout=1)
            assert not first_thread.is_alive()
            assert not second_thread.is_alive()
            assert logging.getLogger().manager.disable == logging.WARNING
        finally:
            release_first.set()
            first_thread.join(timeout=1)
            second_thread.join(timeout=1)
            logging.disable(original_disable_level)

    def test_debug_log(self, mocker):
        mocker.patch("logging.debug", return_value=None)

    def test_info_log(self, mocker):
        mocker.patch("logging.info", return_value=None)

    def test_warning_log(self, mocker):
        mocker.patch("logging.warning", return_value=None)

    def test_error_log(self, mocker):
        mocker.patch("logging.error", return_value=None)

    def test_critical_log(self, mocker):
        mocker.patch("logging.critical", return_value=None)
