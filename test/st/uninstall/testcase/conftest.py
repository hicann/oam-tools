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
# run_package and install_dir fixtures are inherited from test/st/conftest.py.

import shutil
import subprocess

import pytest

_BASH = shutil.which("bash") or "/bin/bash"


@pytest.fixture
def installed_dir(run_package, install_dir):
    """Install oam-tools into install_dir, yield the install root for the test."""
    result = subprocess.run(
        [_BASH, run_package, "--full", "--quiet", f"--install-path={install_dir}"],
        capture_output=True, text=True, timeout=180,
    )
    if result.returncode != 0:
        pytest.fail(
            f"Pre-test install failed (rc={result.returncode}):\n"
            f"{result.stdout}{result.stderr}"
        )
    yield install_dir
