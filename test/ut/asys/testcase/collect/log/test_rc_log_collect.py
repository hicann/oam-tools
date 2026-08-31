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


from testcase.conftest import ut_root_path


from collect.log import collect_rc_logs
from testcase.conftest import AssertTest


def setup_module():
    print("TestRCLogCollect ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestRCLogCollect ut test finish.")  # noqa: T201  # test diagnostic output


class TestRCLogCollect(AssertTest):
    def setup_method(self):
        pass

    def teardown_method(self):
        pass

    def test_host_log_collect_failed(self, mocker):
        mocker.patch("collect.log.rc_log_collect.get_log_conf_path", return_value="")
        mocker.patch(
            "common.FileOperate.list_dir", return_value=ut_root_path + "/data/"
        )
        mocker.patch("common.FileOperate.copy_file_to_dir", return_value=True)
        mocker.patch("common.FileOperate.collect_dir", return_value=True)
        mocker.patch(
            "os.walk",
            return_value=((f"{ut_root_path}/data/scripts", "", ["msnpureport"]),),
        )
        mocker.patch("params.ParamDict.get_command", return_value="collect")
        self.assertTrue(not collect_rc_logs("./"))

    def test_host_log_collect_failed_no(self, mocker):
        mocker.patch("collect.log.rc_log_collect.get_log_conf_path", return_value="")
        mocker.patch("common.FileOperate.list_dir", return_value=None)
        mocker.patch("common.FileOperate.copy_file_to_dir", return_value=True)

        mocker.patch("params.ParamDict.get_command", return_value="collect")
        self.assertTrue(not collect_rc_logs("./"))
