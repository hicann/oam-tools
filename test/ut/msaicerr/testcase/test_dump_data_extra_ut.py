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
import tempfile
from unittest.mock import Mock

import numpy as np
import pytest

from conftest import MSAICERR_PATH
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.dump_data_parser import DumpDataParser
from ms_interface.utils import AicErrException

sys.path.append(MSAICERR_PATH)


def _make_parser(dest_dtype="", output_path="", dump_path=None):
    # 默认值在导入期求值，取不到 tmp_path fixture；用 gettempdir 避免硬编码 /tmp
    if dump_path is None:
        dump_path = os.path.join(tempfile.gettempdir(), "data.bin")
    return DumpDataParser(dump_path, AicErrorInfo(), dest_dtype, output_path)


def test_no_dest_dtype():
    parser = _make_parser(dest_dtype="")
    result = parser.convert_bin_file_to_npy()
    assert "Need to specify the dtype" in result


def test_invalid_dest_dtype():
    parser = _make_parser(dest_dtype="not_a_dtype")
    result = parser.convert_bin_file_to_npy()
    assert "Invalid dest_dtype" in result


def test_convert_success(mocker, tmp_path):
    parser = _make_parser(dest_dtype="float16",
                          output_path=str(tmp_path),
                          dump_path=str(tmp_path / "data.bin"))
    mocker.patch("numpy.fromfile", return_value=np.ones(4, dtype=np.float16))
    saved = mocker.patch("numpy.save")
    _ = parser.convert_bin_file_to_npy()
    assert saved.called
    assert len(parser.bin_data_list) == 1


def test_convert_dtype_mismatch_warning(mocker, tmp_path):
    # file name carries .int8 but dest_dtype is float16 -> warning branch
    parser = _make_parser(dest_dtype="float16",
                          output_path=str(tmp_path),
                          dump_path=str(tmp_path / "data.int8.bin"))
    mocker.patch("numpy.fromfile", return_value=np.ones(4, dtype=np.float16))
    mocker.patch("numpy.save")
    result = parser.convert_bin_file_to_npy()
    assert "different from dest_dtype" in result


def test_convert_failure_raises(mocker, tmp_path):
    parser = _make_parser(dest_dtype="float16",
                          output_path=str(tmp_path),
                          dump_path=str(tmp_path / "data.bin"))
    mocker.patch("numpy.fromfile", side_effect=RuntimeError("boom"))
    with pytest.raises(AicErrException):
        parser.convert_bin_file_to_npy()


def test_convert_bfloat16_registers_ext_dtype(mocker, tmp_path):
    # -d xxx.bin -dtype bfloat16 这条路径不经过 _to_numpy_dtype，必须自行触发
    # bfloat16ext 注册，否则 astype("bfloat16") 抛 TypeError: data type not understood。
    parser = _make_parser(dest_dtype="bfloat16",
                          output_path=str(tmp_path),
                          dump_path=str(tmp_path / "data.bin"))
    register = mocker.patch.object(DumpDataParser, "_register_ext_dtype", return_value=True)
    # 注册由桩接管，故 astype("bfloat16") 也要绕开：用假数组顶掉 fromfile 的返回值，
    # 这样用例在未装 bfloat16ext 的环境里也能跑（否则真 astype 会抛 TypeError）。
    fake = Mock()
    fake.astype.return_value = fake
    mocker.patch("numpy.fromfile", return_value=fake)
    mocker.patch("numpy.clip", return_value=fake)
    mocker.patch("numpy.save")
    parser.convert_bin_file_to_npy()
    assert register.called
    fake.astype.assert_any_call("bfloat16")


def test_convert_bfloat16_without_ext_raises(mocker, tmp_path):
    # bfloat16ext 未安装时给出明确报错，而不是让 astype 抛出难懂的 TypeError
    parser = _make_parser(dest_dtype="bfloat16",
                          output_path=str(tmp_path),
                          dump_path=str(tmp_path / "data.bin"))
    mocker.patch.object(DumpDataParser, "_register_ext_dtype", return_value=False)
    with pytest.raises(AicErrException):
        parser.convert_bin_file_to_npy()
