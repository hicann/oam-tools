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
from argparse import Namespace

import pytest
import subprocess
import os
import shutil

from testcase.conftest import ASYS_SRC_PATH, ut_root_path, set_env, unset_env
from testcase.conftest import AssertTest

sys.path.insert(0, ASYS_SRC_PATH)

from collect import AsysCollect
from params import ParamDict


def setup_module():
    print("TestAsysMain ut test start.")
    set_env()


def teardown_module():
    print("TestAsysMain ut test finsh.")
    unset_env()


class TestAsysCollect(AssertTest):

    def setup_method(self):
        if os.path.exists(os.path.join(ut_root_path, "asys_output_20230227093645758")):
            shutil.rmtree(os.path.join(ut_root_path, "asys_output_20230227093645758"))
        ParamDict().asys_output_timestamp_dir = os.path.join(ut_root_path, "asys_output_20230227093645758")

    def teardown_method(self):
        ParamDict.clear()
        if os.path.exists(os.path.join(ut_root_path, "asys_output_20230227093645758")):
            shutil.rmtree(os.path.join(ut_root_path, "asys_output_20230227093645758"))

    @pytest.mark.parametrize(['run'], [('not supported',), ('ls',)])
    def test_collect_msnpureport_failed(self, run, mocker, caplog):
        ParamDict().set_env_type("EP")
        mocker.patch("common.FileOperate.create_dir", return_value=True)
        mocker.patch("common.FileOperate.write_file")
        mocker.patch("common.FileOperate.remove_dir")
        fake_ret = subprocess.run(run, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  encoding='utf-8')
        mocker.patch("subprocess.run", return_value=fake_ret)
        mocker.patch("collect.ops.ops_collect.collect_ops", return_value=True)
        asys_collect = AsysCollect()
        self.assertTrue(asys_collect.collect())
        if run == 'ls':
            self.assertTrue("No files or directories in" in caplog.text)

    def test_collect_success(self, mocker):
        ParamDict().set_env_type("EP")
        mocker.patch("common.FileOperate.create_dir", return_value=True)
        mocker.patch("common.FileOperate.copy_dir", return_value=True)
        mocker.patch("common.FileOperate.list_dir", return_value=["asys_ut_test_export_tmp"])
        mocker.patch("common.FileOperate.write_file")
        mocker.patch("os.walk")
        mocker.patch("collect.ops.ops_collect.collect_ops", return_value=True)

        asys_collect = AsysCollect()
        self.assertTrue(asys_collect.collect())

    def test_collect_other_para_error(self, mocker, caplog):
        args = Namespace(subparser_name="collect", task_dir=None, output=None, tar=None, r=None, remote=12345, all=None,
                         quiet=None)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(args)

        asys_collect = AsysCollect()
        self.assertTrue(not asys_collect.collect())
        self.assertTrue("'--remote', '--all' and '--quiet' can be used only when '-r=stacktrace'." in caplog.text)

    def test_collect_rc_software(self):
        from collect.asys_collect import AsysCollect
        ParamDict().set_env_type("RC")
        AsysCollect().collect_status_info()
        self.assertTrue(
            os.path.isfile(os.path.join(ut_root_path, "asys_output_20230227093645758", "software_info.txt")))
        os.remove(os.path.join(ut_root_path, "asys_output_20230227093645758", "software_info.txt"))

    def test_collect_ep_health_status(self):
        from collect.asys_collect import AsysCollect
        ParamDict().set_env_type("EP")
        AsysCollect().collect_status_info()
        AsysCollect().collect_health_info()
        self.assertTrue(
            os.path.isfile(os.path.join(ut_root_path, "asys_output_20230227093645758", "software_info.txt")))
        os.remove(os.path.join(ut_root_path, "asys_output_20230227093645758", "software_info.txt"))
        self.assertTrue(
            os.path.isfile(os.path.join(ut_root_path, "asys_output_20230227093645758", "hardware_info.txt")))
        os.remove(os.path.join(ut_root_path, "asys_output_20230227093645758", "hardware_info.txt"))
        self.assertTrue(
            os.path.isfile(os.path.join(ut_root_path, "asys_output_20230227093645758", "health_result.txt")))
        os.remove(os.path.join(ut_root_path, "asys_output_20230227093645758", "health_result.txt"))

    def test_collect_run(self, mocker):
        mocker.patch.object(AsysCollect, "collect", return_value=True)
        mocker.patch.object(AsysCollect, "clean_work")
        self.assertTrue(AsysCollect().run())

    def test_collect_status_info_timeout(self, mocker, caplog):
        ParamDict().set_env_type("EP")
        mocker.patch("common.FileOperate.create_dir", return_value=True)
        mocker.patch("common.FileOperate.copy_dir", return_value=True)
        mocker.patch("common.FileOperate.list_dir", return_value=["asys_ut_test_export_tmp"])
        mocker.patch("common.FileOperate.write_file")
        mocker.patch("os.walk")
        mocker.patch("collect.ops.ops_collect.collect_ops", return_value=True)
        mocker.patch.object(AsysCollect, 'collect_status_info', side_effect=TimeoutError)
        mocker.patch.object(AsysCollect, 'collect_health_info', side_effect=TimeoutError)

        asys_collect = AsysCollect()
        self.assertTrue(asys_collect.collect())
        self.assertTrue('Timeout in retrieving device status information' in caplog.text)
        self.assertTrue('Timeout in retrieving device health information' in caplog.text)
