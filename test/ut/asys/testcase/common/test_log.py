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
from testcase.conftest import ASYS_SRC_PATH
sys.path.insert(0, ASYS_SRC_PATH)


def setup_module():
    print("TestLog ut test start.")


def teardown_module():
    print("TestLog ut test finsh.")


class TestLog:

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
