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

# ruff: noqa: E501, S607, PLR0915, PLR6301, PLR1722  # test mock methods, partial paths, long lines

# pylint: disable=protected-access,redefined-outer-name,attribute-defined-outside-init,unused-argument,broad-exception-caught,unused-import,unused-variable,redefined-builtin,reimported,no-member,function-redefined,possibly-used-before-assignment,no-self-argument,too-many-function-args,unexpected-keyword-arg,no-value-for-parameter  # pytest fixture/mock/cleanup patterns


from collect.log import collect_host_logs
from testcase.conftest import AssertTest


def setup_module():
    print("TestHostLogCollect ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestHostLogCollect ut test finish.")  # noqa: T201  # test diagnostic output


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
