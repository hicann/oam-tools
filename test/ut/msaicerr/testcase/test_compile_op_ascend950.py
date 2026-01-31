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
# -------
import os
import subprocess
import sys
import shutil
from pathlib import Path

from conftest import MSAICERR_PATH
sys.path.append(MSAICERR_PATH)
from ms_interface.constant import ModeCustom
from ms_interface.dsmi_interface import DSMIInterface, DsmiChipInfoStru
from ms_interface.ascend950.compile_op import CompileOP

cur_abspath = os.path.dirname(__file__)

op_name = "AddCustom"
inputs = [{"name": "x", "param_type": "required", "format": ["ND"], "type": ["float16"]},
          {"name": "y", "param_type": "required", "format": ["ND"], "type": ["float16"]}]
outputs = [{"name": "z", "param_type": "required",
            "format": ["ND"], "type": ["float16"]}]
compile_op = CompileOP(op_name, inputs, outputs, 'Ascend950')


class TestCompileOp():

    def test_get_ub_size_not_tbe(self, mocker):
        ub_size = compile_op.get_ub_size()
        assert ub_size == 0

    def test_get_soc_version_failed(self, mocker):
        sys.path.append(f"{cur_abspath}/../res/package")
        ub_size = compile_op.get_ub_size()
        assert ub_size == 0

    def test_get_ub_size_success(self, mocker):
        sys.path.append(f"{cur_abspath}/../res/package")
        mocker.patch("ctypes.CDLL")
        mocker.patch.object(DSMIInterface, "get_chip_info",
                            return_value=DsmiChipInfoStru())
        ub_size = compile_op.get_ub_size()
        assert ub_size == 1024

    def test_make_json_file(self):
        temp_dir = Path(cur_abspath) / "test_make_json_file"
        assert compile_op.make_json_file(temp_dir)
        shutil.rmtree(temp_dir)

    def test_get_compile_file_temp_dir_exist(self, mocker):
        temp_dir = Path(cur_abspath) / "test_get_compile_file_temp_dir_exist"
        temp_dir.mkdir(exist_ok=True)
        mocker.patch.object(Path, "rglob", return_value=['test.o'])
        build_res = compile_op.get_compile_file(temp_dir)
        assert len(build_res) == 2

    def test_get_compile_file_temp_dir_not_exist(self, mocker, caplog):
        temp_dir = Path(cur_abspath) / \
            "test_get_compile_file_temp_dir_not_exist"
        mocker.patch("shutil.which", return_value=True)
        mocker.patch.object(Path, "exists", return_value=False)
        res = subprocess.run('ls')
        mocker.patch("subprocess.run", return_value=res)
        op_kernel_path = temp_dir.joinpath(
            ModeCustom.ADD_CUSTOM.value, 'op_kernel')
        op_kernel_path.mkdir(parents=True, exist_ok=True)
        op_kernel_path.joinpath('add_custom.cpp').write_text("test")
        compile_file_path = temp_dir.joinpath(
            ModeCustom.ADD_CUSTOM.value, 'build_out', 'op_kernel')
        compile_file_path.mkdir(parents=True, exist_ok=True)
        compile_file_path.joinpath(
            f'{ModeCustom.ADD_CUSTOM.value}_add_custom.o').write_text("test")
        shutil.copy(Path(cur_abspath).joinpath("../res/ori_data/collect_milan/collection",
                                               "AddCustom_ab1b6750d7f510985325b603cb06dc8b.json"), compile_file_path)

        build_res = compile_op.get_compile_file(temp_dir)
        shutil.rmtree(temp_dir)
        assert len(build_res) == 2

    def test_get_compile_file_compile_failed(self, mocker):
        temp_dir = Path(cur_abspath) / "test_get_compile_file_compile_failed"
        mocker.patch.object(Path, "rglob", return_value=['test.o'])
        mocker.patch("shutil.which", return_value=True)
        res = subprocess.run('test')
        mocker.patch("subprocess.run", return_value=res)
        build_res = compile_op.get_compile_file(temp_dir)
        shutil.rmtree(temp_dir)
        assert len(build_res) == 0