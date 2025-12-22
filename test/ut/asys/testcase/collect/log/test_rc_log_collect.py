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

from testcase.conftest import ASYS_SRC_PATH, ut_root_path

sys.path.insert(0, ASYS_SRC_PATH)
import asys

from common import FileOperate
from collect.log import collect_rc_logs
from testcase.conftest import AssertTest


def setup_module():
    print("TestRCLogCollect ut test start.")


def teardown_module():
    print("TestRCLogCollect ut test finsh.")


class TestRCLogCollect(AssertTest):

    def setup_method(self):
        pass

    def teardown_method(self):
        pass

    def test_host_log_collect_failed(self, mocker):
        mocker.patch("collect.log.rc_log_collect.get_log_conf_path", return_value="")
        mocker.patch("common.FileOperate.list_dir", return_value=ut_root_path + "/data/")
        mocker.patch("common.FileOperate.copy_file_to_dir", return_value=True)
        mocker.patch("common.FileOperate.collect_dir", return_value=True)
        mocker.patch("os.walk", return_value=((f"{ut_root_path}/data/scripts", "", ["msnpureport"]), ))
        mocker.patch("params.ParamDict.get_command", return_value="collect")
        self.assertTrue(not collect_rc_logs("./"))

    def test_host_log_collect_failed_no(self, mocker):
        mocker.patch("collect.log.rc_log_collect.get_log_conf_path", return_value="")
        mocker.patch("common.FileOperate.list_dir", return_value=None)
        mocker.patch("common.FileOperate.copy_file_to_dir", return_value=True)

        mocker.patch("params.ParamDict.get_command", return_value="collect")
        self.assertTrue(not collect_rc_logs("./"))
