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
import os
from argparse import Namespace
from testcase.conftest import ASYS_SRC_PATH, get_root
sys.path.insert(0, ASYS_SRC_PATH)

from params import ParamDict
from common import FileOperate
from testcase.conftest import AssertTest

def setup_module():
    print("TestParamDict ut test start.")

def teardown_module():
    print("TestParamDict ut test finsh.")

class TestParamDict(AssertTest):

    def setup_method(self):
        ParamDict.clear()

    def teardown_method(self):
        pass

    def test_get_command(self, mocker):
        fake_namespace = Namespace(subparser_name="collect", task_dir=get_root(), output=None, tar=None, r=None, remote=None, all=None, quiet=None)
        ParamDict().set_args(fake_namespace)
        self.assertTrue(ParamDict().get_command() == "collect")

        mocker.patch("common.FileOperate.check_file", return_value=True)
        fake_namespace = Namespace(subparser_name="launch", task="bash ./test.bash", output=None, tar=None)
        ParamDict().set_args(fake_namespace)
        self.assertTrue(ParamDict().get_command() == "launch")

    def test_get_arg(self, mocker):
        fake_namespace = Namespace(subparser_name="collect", task_dir="./", output=None, tar=None, r=None, remote=None, all=None, quiet=None)
        ParamDict().set_args(fake_namespace)
        self.assertTrue(ParamDict().get_arg("task_dir") == "./")

        mocker.patch("common.FileOperate.check_file", return_value=True)
        fake_namespace = Namespace(subparser_name="launch", task="bash ./test.bash", output=None, tar=None)
        ParamDict().set_args(fake_namespace)
        self.assertTrue(ParamDict().get_arg("task") == "bash ./test.bash")

    def test_get_deps(self, mocker):
        ParamDict().set_deps([["dep1", "dep1_command"], ["dep2", "dep2_command"]])
        self.assertTrue(ParamDict().get_deps())

    @pytest.mark.parametrize(["ini_name", "ini_value"], [("graph", "1"), ("ops", "0")])
    def test_get_set_ini(self, mocker, ini_name, ini_value):
        ParamDict().set_ini(ini_name, ini_value)
        self.assertTrue(ParamDict().get_ini(ini_name) == ini_value)

    def test_set_deps(self, mocker):
        deps_set = [["dep1", "dep1_command"], ["dep2", "dep2_command"]]
        ParamDict().set_deps(deps_set)
        self.assertTrue(ParamDict().get_deps().get("dep1") == "dep1_command")
        self.assertTrue(ParamDict().get_deps().get("dep2") == "dep2_command")

    def test_set_args(self, mocker):
        fake_namespace = Namespace(subparser_name="collect", task_dir="./", output=None, tar=None, r=None, remote=None, all=None, quiet=None)
        ParamDict().set_args(fake_namespace)
        self.assertTrue(ParamDict().get_arg("task_dir") == "./")

        mocker.patch("common.FileOperate.check_file", return_value=True)
        fake_namespace = Namespace(subparser_name="launch", task="bash ./test.bash", output=None, tar=None)
        ParamDict().set_args(fake_namespace)
        self.assertTrue(ParamDict().get_arg("task") == "bash ./test.bash")

    def test_output_setfail(self, mocker):
        # test output empty string
        fake_namespace = Namespace(subparser_name="collect", task_dir="./", output="", tar=None, r=None, remote=None, all=None, quiet=None)
        self.assertTrue(not ParamDict().set_args(fake_namespace))
        # test output space string
        fake_namespace = Namespace(subparser_name="collect", task_dir="./", output="  ", tar=None, r=None, remote=None, all=None, quiet=None)
        self.assertTrue(not ParamDict().set_args(fake_namespace))
        # test output no write perssion
        fake_namespace = Namespace(subparser_name="collect", task_dir="./", output=get_root(), tar=None, r=None, remote=None, all=None, quiet=None)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("common.FileOperate.check_access", return_value=False)
        self.assertTrue(not ParamDict().set_args(fake_namespace))
        # test output create failed
        fake_namespace = Namespace(subparser_name="collect", task_dir="./", output=get_root(), tar=None, r=None, remote=None, all=None, quiet=None)
        mocker.patch("common.FileOperate.check_dir", return_value=False)
        mocker.patch("common.FileOperate.create_dir", return_value=False)
        self.assertTrue(not ParamDict().set_args(fake_namespace))

    def test_output_setsucc(self, mocker):
        fake_namespace = Namespace(subparser_name="collect", task_dir="./", output=get_root(), tar="True", r=None, remote=None, all=None, quiet=None)
        ParamDict().set_args(fake_namespace)
        self.assertTrue(ParamDict().get_command() == "collect")
        self.assertTrue(ParamDict().get_arg("task_dir") == "./")
        self.assertTrue(ParamDict().get_arg("output") == get_root())
