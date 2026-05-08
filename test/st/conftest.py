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

import glob
import os
import shutil
import subprocess
import tempfile

import pytest

_CHMOD = shutil.which("chmod") or "/bin/chmod"

_FILE_DIR = os.path.dirname(os.path.realpath(__file__))
BASEPATH = os.path.abspath(os.path.join(_FILE_DIR, "../../"))
BUILD_OUT_DIR = os.path.join(BASEPATH, "build_out")


def find_run_package():
    pattern = os.path.join(BUILD_OUT_DIR, "cann-oam-tools_*.run")
    pkgs = sorted(glob.glob(pattern))
    return pkgs[-1] if pkgs else None


@pytest.fixture(scope="session")
def run_package():
    """Return path to the built .run package; skip entire session if not built."""
    pkg = find_run_package()
    if not pkg:
        pytest.skip(
            f"No cann-oam-tools*.run found in {BUILD_OUT_DIR}. "
            "Build it first with: bash build.sh"
        )
    return pkg


@pytest.fixture
def install_dir():
    """Provide a fresh install root under build_out/.

    The .run installer (when run as root) rejects ancestors with permissions
    tighter than 0755. pytest's tmp_path defaults to 0700 and tempfile.mkdtemp
    likewise creates 0700 dirs, so we explicitly chmod the parent to 0755.
    build_out itself is created by build.sh with normal umask (0755).
    """
    os.makedirs(BUILD_OUT_DIR, exist_ok=True)
    parent = tempfile.mkdtemp(prefix="oam_st_", dir=BUILD_OUT_DIR)
    os.chmod(parent, 0o755)
    path = os.path.join(parent, "oam_install")
    os.mkdir(path)
    yield path
    subprocess.run([_CHMOD, "-R", "u+w", parent], check=False, capture_output=True)
    shutil.rmtree(parent, ignore_errors=True)
