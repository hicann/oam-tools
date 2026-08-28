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

import os
import stat
import sys
from unittest.mock import Mock

import pytest

from conftest import MSAICERR_PATH

sys.path.append(MSAICERR_PATH)
from ms_interface.single_op_test_frame.utils import file_util


def test_makedirs_creates_nested_dirs(tmp_path):
    target = os.path.join(str(tmp_path), "a", "b", "c")
    file_util.makedirs(target)
    assert os.path.isdir(target)


def test_makedirs_on_existing_dir_does_not_raise(tmp_path):
    target = os.path.join(str(tmp_path), "exist")
    os.mkdir(target)
    file_util.makedirs(target)
    assert os.path.isdir(target)


def test_makedirs_applies_given_mode(tmp_path):
    # 必须断权限位而非只断 isdir：默认 mode 是 DATA_DIR_MODES(0o750，故意不给
    # world 位)，mode 传递一旦回归，msaicerr 建的数据目录就变成 world 可读可
    # 执行，而只断 isdir 的用例照绿。owner 位不受常见 umask 影响，断言稳定。
    target = os.path.join(str(tmp_path), "moded")
    file_util.makedirs(target, mode=stat.S_IRWXU)
    assert os.path.isdir(target)
    assert stat.S_IMODE(os.stat(target).st_mode) == stat.S_IRWXU


def test_makedirs_stops_at_root():
    # 传入根目录时 _rec_makedir 首个分支即 return，不应抛异常
    file_util.makedirs("/")
    assert os.path.isdir("/")


def test_read_file_returns_bytes(tmp_path):
    file_path = os.path.join(str(tmp_path), "data.bin")
    with open(file_path, "wb") as ff:
        ff.write(b"hello-bytes")
    assert file_util.read_file(file_path) == b"hello-bytes"


def test_read_file_rejects_non_int_size_limit():
    with pytest.raises(TypeError):
        file_util.read_file("whatever", size_limit="big")


def test_read_file_missing_path_raises(tmp_path):
    with pytest.raises(IOError):
        file_util.read_file(os.path.join(str(tmp_path), "no_such_file"))


def test_read_file_over_size_limit_raises(tmp_path, mocker):
    file_path = os.path.join(str(tmp_path), "big.bin")
    with open(file_path, "wb") as ff:
        ff.write(b"x")
    fake_stat = Mock()
    fake_stat.st_size = 999999999
    mocker.patch("os.stat", return_value=fake_stat)
    with pytest.raises(IOError, match="File is too large"):
        file_util.read_file(file_path, size_limit=1)
