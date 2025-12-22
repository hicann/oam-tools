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
import os
from testcase.conftest import ASYS_SRC_PATH, CONF_SRC_PATH
sys.path.insert(0, ASYS_SRC_PATH)

from common import get_project_conf, get_ascend_home, get_log_conf_path
from ..conftest import AssertTest


def setup_module():
    print("TestPath ut test start.")


def teardown_module():
    print("TestPath ut test finsh.")


class TestPath(AssertTest):

    def test_get_project_root(self, mocker):
        mocker.patch("os.path.abspath", return_value="./")
        self.assertTrue(get_project_conf() == CONF_SRC_PATH + 'conf')

    def test_get_ascend_home(self, mocker):
        mocker.patch("os.getenv", return_value=None)
        self.assertTrue(get_ascend_home() == "/usr/local/Ascend")
        mocker.patch("os.getenv", return_value="/usr/local/Ascend/latest/toolkit")
        self.assertTrue(get_ascend_home() == "/usr/local/Ascend")
        mocker.patch("os.getenv", return_value="/usr/local/Ascend/latest/toolkit:/home/wangxu/Ascend/latest/toolkit")
        self.assertTrue(get_ascend_home() == "/usr/local/Ascend")

    def test_get_log_conf_path(self):
        get_log_conf_path("slog")
        get_log_conf_path("bbox")
