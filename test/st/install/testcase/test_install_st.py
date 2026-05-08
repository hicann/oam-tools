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
"""
ST: install – validates the oam-tools .run package installation and extraction.

Tested command forms:
  ./cann-oam-tools_<ver>_linux-<arch>.run --full  --quiet --install-path=<dir>
  ./cann-oam-tools_<ver>_linux-<arch>.run --run   --quiet --install-path=<dir>
  ./cann-oam-tools_<ver>_linux-<arch>.run --devel --quiet --install-path=<dir>
  ./cann-oam-tools_<ver>_linux-<arch>.run --noexec --extract=<dir>

Checks:
  - Exit code is 0
  - No [ERROR] in combined stdout + stderr
  - No [WARNING] in combined stdout + stderr
  - Key installed artefacts exist on disk after successful install
"""

import os
import platform
import shutil
import subprocess

import pytest

_BASH = shutil.which("bash") or "/bin/bash"

_ERROR_KW = "[ERROR]"
_WARNING_KW = "[WARNING]"


def _run(run_package, install_dir, install_type, extra_args=None):
    """Execute the .run package and return CompletedProcess."""
    cmd = [_BASH, run_package, install_type, "--quiet",
           f"--install-path={install_dir}"]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=180)


def _output(result):
    return result.stdout + result.stderr


class TestInstall:
    @pytest.mark.parametrize("install_type", ["--full", "--run", "--devel"])
    def test_install(self, run_package, install_dir, install_type):
        result = _run(run_package, install_dir, install_type)
        out = _output(result)

        assert result.returncode == 0, (
            f"'{install_type}' install exited {result.returncode}:\n{out}"
        )
        assert _ERROR_KW not in out, (
            f"'{install_type}' install output contains {_ERROR_KW!r}:\n{out}"
        )
        assert _WARNING_KW not in out, (
            f"'{install_type}' install output contains {_WARNING_KW!r}:\n{out}"
        )


class TestInstallArtefacts:
    @staticmethod
    def test_install_full(run_package, install_dir):
        _run(run_package, install_dir, "--full")

        info_dir = os.path.join(install_dir, "cann", "share", "info", "oam_tools")
        assert os.path.isdir(info_dir), f"Missing oam_tools info dir: {info_dir}"

        install_info = os.path.join(info_dir, "ascend_install.info")
        assert os.path.isfile(install_info), f"Missing ascend_install.info: {install_info}"

        arch = platform.machine()
        version_h = os.path.join(
            install_dir, "cann", f"{arch}-linux",
            "include", "version", "oam_tools_version.h"
        )
        assert os.path.isfile(version_h), f"Missing version header: {version_h}"

        uninstall_sh = os.path.join(install_dir, "cann", "cann_uninstall.sh")
        assert os.path.isfile(uninstall_sh), f"Missing cann_uninstall.sh: {uninstall_sh}"


class TestExtract:
    @staticmethod
    def test_extract(run_package, install_dir):
        extract_dir = os.path.join(install_dir, "extract")
        result = subprocess.run(
            [_BASH, run_package, "--noexec", f"--extract={extract_dir}"],
            capture_output=True, text=True, timeout=180,
        )
        out = _output(result)

        assert result.returncode == 0, (
            f"--noexec --extract exited {result.returncode}:\n{out}"
        )
        assert _ERROR_KW not in out, (
            f"--noexec --extract output contains {_ERROR_KW!r}:\n{out}"
        )
        assert _WARNING_KW not in out, (
            f"--noexec --extract output contains {_WARNING_KW!r}:\n{out}"
        )
        assert os.path.isdir(extract_dir), (
            f"Extract target directory was not created: {extract_dir}"
        )

