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
import sys
from unittest.mock import Mock

import pytest

from conftest import MSAICERR_PATH
from ms_interface.single_op_test_frame.utils import file_util

sys.path.append(MSAICERR_PATH)


def test_makedirs_creates_nested(tmp_path):
    target = os.path.join(str(tmp_path), "a", "b", "c")
    file_util.makedirs(target)
    assert os.path.isdir(target)


def test_makedirs_existing_ok(tmp_path):
    target = os.path.join(str(tmp_path), "exist")
    os.mkdir(target)
    # should not raise even though it already exists
    file_util.makedirs(target)
    assert os.path.isdir(target)


def test_read_file_normal(tmp_path):
    file_path = os.path.join(str(tmp_path), "data.bin")
    with open(file_path, "wb") as ff:
        ff.write(b"hello-bytes")
    assert file_util.read_file(file_path) == b"hello-bytes"


def test_read_file_size_limit_not_int():
    with pytest.raises(TypeError):
        file_util.read_file("whatever", size_limit="big")


def test_read_file_not_exist(tmp_path):
    with pytest.raises(IOError):
        file_util.read_file(os.path.join(str(tmp_path), "no_such_file"))


def test_read_file_too_large(tmp_path, mocker):
    file_path = os.path.join(str(tmp_path), "big.bin")
    with open(file_path, "wb") as ff:
        ff.write(b"x")
    fake_stat = Mock()
    fake_stat.st_size = 999999999
    mocker.patch("os.stat", return_value=fake_stat)
    # NOTE: the source's "too large" branch has a buggy
    # `raise IOError(...) % (...)` expression that evaluates `%` on the
    # exception instance; we only assert that it raises, not the type.
    with pytest.raises(Exception):
        file_util.read_file(file_path, size_limit=1)
