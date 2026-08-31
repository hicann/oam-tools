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

import importlib
import subprocess


from common import run_command, run_cmd_output, run_linux_cmd
from common import cmd_run
from ..conftest import AssertTest


def setup_module():
    print("TestCmdRun ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestCmdRun ut test finish.")  # noqa: T201  # test diagnostic output


class TestCmdRun(AssertTest):
    def test_run_command_success(self, mocker):
        cmd = "ls"
        fake_ret = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            check=False,
        )  # noqa: S607  # nosec B602  # test mock
        mocker.patch("subprocess.run", return_value=fake_ret)
        self.assertTrue(run_command(cmd) != "NONE")

    def test_run_command_failed(self, mocker):
        cmd = "not_exist_cmd"
        fake_ret = subprocess.CompletedProcess(
            args=cmd,
            returncode=127,
            stdout="",
            stderr="/bin/sh: 1: not_exist_cmd: not found\n",
        )
        mocker.patch("subprocess.run", return_value=fake_ret)
        self.assertTrue(run_command(cmd) == "NONE")

    def test_run_msnpureport_success(self, mocker):
        cmd = "ls"
        fake_ret = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            check=False,
        )  # noqa: S607  # nosec B602  # test mock
        mocker.patch("subprocess.run", return_value=fake_ret)
        self.assertTrue(run_cmd_output(cmd)[0])
        self.assertTrue(run_cmd_output(cmd)[1] != "NONE")

    def test_run_msnpureport_failed(self, mocker):
        cmd = "not supported cmd"
        fake_ret = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            check=False,
        )  # noqa: S607  # nosec B602  # test mock
        mocker.patch("subprocess.run", return_value=fake_ret)
        self.assertTrue(not run_cmd_output(cmd)[0])

    def test_run_linux_cmd(self):
        self.assertTrue(run_linux_cmd("ls"))

    def test_run_linux_cmd_error(self):
        self.assertTrue(not run_linux_cmd(1))

    def test_bash_is_str_when_which_misses(self, mocker):
        # shutil.which 取不到 bash 时 BASH 必须回退为 str，否则 argv[0]=None 会抛 TypeError
        mocker.patch("shutil.which", return_value=None)
        try:
            importlib.reload(cmd_run)
            self.assertTrue(isinstance(cmd_run.BASH, str))
        finally:
            mocker.stopall()
            importlib.reload(cmd_run)

    def test_run_command_oserror(self, mocker):
        # bash 不存在时 subprocess.run 抛 OSError，run_command 应兜住并返回 NONE
        mocker.patch("subprocess.run", side_effect=FileNotFoundError("no bash"))
        self.assertTrue(run_command("ls") == "NONE")

    def test_run_cmd_output_oserror(self, mocker):
        mocker.patch("subprocess.run", side_effect=FileNotFoundError("no bash"))
        self.assertTrue(run_cmd_output("ls") == (False, ""))
