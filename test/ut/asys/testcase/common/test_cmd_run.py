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
import subprocess
from testcase.conftest import ASYS_SRC_PATH

sys.path.insert(0, ASYS_SRC_PATH)

from common import run_command, run_cmd_output, run_linux_cmd
from ..conftest import AssertTest


def setup_module():
    print("TestCmdRun ut test start.")


def teardown_module():
    print("TestCmdRun ut test finsh.")


class TestCmdRun(AssertTest):

    def test_run_command_success(self, mocker):
        cmd = "ls"
        fake_ret = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        mocker.patch("subprocess.run", return_value=fake_ret)
        self.assertTrue(run_command(cmd) != "NONE")

    def test_run_command_failed(self, mocker):
        cmd = "not supported cmd"
        fake_ret = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        mocker.patch("subprocess.run", return_value=fake_ret)
        self.assertTrue(run_command(cmd) == "NONE")

    def test_run_msnpureport_success(self, mocker):
        cmd = "ls"
        fake_ret = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        mocker.patch("subprocess.run", return_value=fake_ret)
        self.assertTrue(run_cmd_output(cmd)[0])
        self.assertTrue(run_cmd_output(cmd)[1] != "NONE")

    def test_run_msnpureport_failed(self, mocker):
        cmd = "not supported cmd"
        fake_ret = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        mocker.patch("subprocess.run", return_value=fake_ret)
        self.assertTrue(not run_cmd_output(cmd)[0])

    def test_run_linux_cmd(self):
        self.assertTrue(run_linux_cmd("ls"))

    def test_run_linux_cmd_error(self):
        self.assertTrue(not run_linux_cmd(1))