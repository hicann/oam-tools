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

from testcase.conftest import ASYS_SRC_PATH
sys.path.insert(0, ASYS_SRC_PATH)
import asys

from common import FileOperate
from collect.log import collect_host_logs
from testcase.conftest import AssertTest

def setup_module():
    print("TestHostLogCollect ut test start.")

def teardown_module():
    print("TestHostLogCollect ut test finsh.")

class TestHostLogCollect(AssertTest):

    def setup_method(self):
        pass

    def teardown_method(self):
        pass

    def test_host_log_collect_success(self, mocker):
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)
        mocker.patch("common.FileOperate.collect_dir", return_value=True)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("params.ParamDict.get_command", return_value="collect")
        self.assertTrue(collect_host_logs("./"))

        mocker.patch("params.ParamDict.get_command", return_value="launch")
        self.assertTrue(collect_host_logs("./"))

    def test_host_log_collect_failed(self, mocker):
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=False)
        mocker.patch("common.FileOperate.collect_dir", return_value=False)
        mocker.patch("common.FileOperate.check_dir", return_value=False)
        mocker.patch("params.ParamDict.get_command", return_value="collect")
        self.assertTrue(not collect_host_logs("./"))

        mocker.patch("params.ParamDict.get_command", return_value="launch")
        self.assertTrue(not collect_host_logs("./"))
