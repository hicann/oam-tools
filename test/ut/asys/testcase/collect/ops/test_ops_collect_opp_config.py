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

import os

from testcase.conftest import AssertTest

from collect.ops.ops_collect import collect_opp_config


def setup_module():
    print("TestOpsCollectOppConfig ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestOpsCollectOppConfig ut test finish.")  # noqa: T201  # test diagnostic output


class TestOpsCollectOppConfig(AssertTest):
    """
    The load_priority field of vendors/config.ini must be recognized no
    matter whether the file ends with a newline or not.
    """

    @staticmethod
    def _write_config(tmp_path, content):
        vendors_dir = os.path.join(tmp_path, "vendors")
        os.makedirs(vendors_dir, exist_ok=True)
        config_path = os.path.join(vendors_dir, "config.ini")
        with open(config_path, "w", encoding="utf-8", newline="") as fp:
            fp.write(content)
        return config_path

    def test_collect_opp_config_load_priority_with_newline(self, mocker, tmp_path):
        """
        The load_priority line ends with a newline, the field is found.
        """
        self._write_config(str(tmp_path), "load_priority=vendor_a,vendor_b\n")
        mocker.patch.dict(os.environ, {"ASCEND_OPP_PATH": str(tmp_path)})
        collect_mock = mocker.patch(
            "collect.ops.ops_collect.collect_cfg_json", return_value=True
        )
        mocker.patch("common.FileOperate.copy_file_to_dir", return_value=True)
        self.assertTrue(collect_opp_config("./output"))
        collect_mock.assert_called()
        vendors = [c.args[1] for c in collect_mock.call_args_list]
        self.assertTrue(vendors == ["vendor_a", "vendor_b"])

    def test_collect_opp_config_load_priority_without_newline(self, mocker, tmp_path):
        """
        The config.ini file does not end with a newline, the load_priority
        field must still be found instead of being silently dropped.
        """
        self._write_config(str(tmp_path), "load_priority=vendor_a,vendor_b")
        mocker.patch.dict(os.environ, {"ASCEND_OPP_PATH": str(tmp_path)})
        collect_mock = mocker.patch(
            "collect.ops.ops_collect.collect_cfg_json", return_value=True
        )
        mocker.patch("common.FileOperate.copy_file_to_dir", return_value=True)
        self.assertTrue(collect_opp_config("./output"))
        collect_mock.assert_called()
        vendors = [c.args[1] for c in collect_mock.call_args_list]
        self.assertTrue(vendors == ["vendor_a", "vendor_b"])

    def test_collect_opp_config_without_load_priority(self, mocker, tmp_path):
        """
        A config.ini without the load_priority field is reported as a
        failure instead of collecting nothing silently.
        """
        self._write_config(str(tmp_path), "other_field=1\n")
        mocker.patch.dict(os.environ, {"ASCEND_OPP_PATH": str(tmp_path)})
        collect_mock = mocker.patch(
            "collect.ops.ops_collect.collect_cfg_json", return_value=True
        )
        self.assertTrue(not collect_opp_config("./output"))
        collect_mock.assert_not_called()
