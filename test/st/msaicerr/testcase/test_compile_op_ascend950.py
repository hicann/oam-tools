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
import subprocess
import sys
import shutil
from pathlib import Path

from conftest import MSAICERR_PATH, cur_abspath
sys.path.append(MSAICERR_PATH)
from ms_interface.constant import ModeCustom
from ms_interface.ascend950.compile_op import CompileOP

op_name = ModeCustom.ADD_CUSTOM.value
inputs = [{"name": "x", "param_type": "required", "format": ["ND"], "type": ["float16"]},
          {"name": "y", "param_type": "required", "format": ["ND"], "type": ["float16"]}]
outputs = [{"name": "z", "param_type": "required",
            "format": ["ND"], "type": ["float16"]}]
compile_op = CompileOP(op_name, inputs, outputs, 'Ascend950')


class TestCompileOp():

    def test_get_compile_file_golden_have_temp(self, caplog):
        temp_dir = Path(cur_abspath).joinpath(
            "../test_get_compile_file_golden_have_temp")
        compile_file_path = temp_dir.joinpath(
            ModeCustom.ADD_CUSTOM.value, 'build_out', 'op_kernel')
        compile_file_path.mkdir(parents=True, exist_ok=True)
        # 写入与当前芯片一致的标记文件，命中复用分支
        temp_dir.joinpath(ModeCustom.ADD_CUSTOM.value,
                          CompileOP.COMPILE_CHIP_MARKER).write_text("Ascend950")
        compile_file_path.joinpath(
            f'{ModeCustom.ADD_CUSTOM.value}_add_custom.o').write_text("test")
        shutil.copy(Path(cur_abspath).joinpath("../res/ori_data/collect_milan/collection",
                                               "AddCustom_ab1b6750d7f510985325b603cb06dc8b.json"), compile_file_path)
        build_result = compile_op.get_compile_file(temp_dir)
        shutil.rmtree(temp_dir)
        assert f'{ModeCustom.ADD_CUSTOM.value}_add_custom.o' in str(
            build_result[0])
        assert "AddCustom_ab1b6750d7f510985325b603cb06dc8b.json" in str(
            build_result[1])

    def test_get_compile_file_golden_not_temp(self, mocker, caplog):
        temp_dir = Path(cur_abspath).joinpath(
            "../test_get_compile_file_golden_not_temp")
        mocker.patch.object(Path, "exists", return_value=False)
        mocker.patch("shutil.which", return_value=True)
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

        build_result = compile_op.get_compile_file(temp_dir)
        shutil.rmtree(temp_dir)
        assert f'{ModeCustom.ADD_CUSTOM.value}_add_custom.o' in str(
            build_result[0])
        assert "AddCustom_ab1b6750d7f510985325b603cb06dc8b.json" in str(
            build_result[1])

    def test_get_compile_file_not_have_msopgen(self, mocker, caplog):
        temp_dir = Path(cur_abspath).joinpath(
            "../test_get_compile_file_not_have_msopgen")
        mocker.patch("shutil.which", return_value=False)
        build_result = compile_op.get_compile_file(temp_dir)
        assert build_result == []

    def test_get_compile_file_run_subprocess_failed(self, mocker, caplog):
        temp_dir = Path(cur_abspath).joinpath(
            "../test_get_compile_file_run_subprocess_failed")
        mocker.patch.object(Path, "exists", return_value=False)
        mocker.patch("shutil.which", return_value=True)
        res = subprocess.run('test')
        mocker.patch("subprocess.run", return_value=res)
        build_result = compile_op.get_compile_file(temp_dir)
        assert build_result == []

    def test_get_compile_file_get_json_failed(self, mocker, caplog):
        temp_dir = Path(cur_abspath).joinpath(
            "../test_get_compile_file_get_json_failed")
        mocker.patch.object(Path, "exists", return_value=False)
        mocker.patch("shutil.which", return_value=True)
        res = subprocess.run('ls')
        mocker.patch("subprocess.run", return_value=res)
        op_kernel_path = temp_dir.joinpath(
            ModeCustom.ADD_CUSTOM.value, 'op_kernel')
        op_kernel_path.mkdir(parents=True, exist_ok=True)
        op_kernel_path.joinpath('add_custom.cpp').write_text("test")
        build_result = compile_op.get_compile_file(temp_dir)
        shutil.rmtree(temp_dir)
        assert build_result == []

    def test_get_compile_file_chip_marker_written(self, mocker, caplog):
        # 编译成功后应写入芯片标记文件，供后续复用校验
        temp_dir = Path(cur_abspath).joinpath(
            "../test_get_compile_file_chip_marker_written")
        mocker.patch.object(Path, "exists", return_value=False)
        mocker.patch("shutil.which", return_value=True)
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
        build_result = compile_op.get_compile_file(temp_dir)
        marker_file = temp_dir.joinpath(
            ModeCustom.ADD_CUSTOM.value, CompileOP.COMPILE_CHIP_MARKER)
        marker_content = marker_file.read_text()
        shutil.rmtree(temp_dir)
        assert len(build_result) == 2
        assert marker_content == "Ascend950"

    def test_get_compile_file_other_chip_not_reuse(self, mocker, caplog):
        # 旧芯片(Ascend950)产物存在，但当前为 Ascend910_96 且无匹配标记，
        # 不应复用旧产物，而是进入编译流程；msopgen 缺失时返回空。
        temp_dir = Path(cur_abspath).joinpath(
            "../test_get_compile_file_other_chip_not_reuse")
        compile_file_path = temp_dir.joinpath(
            ModeCustom.ADD_CUSTOM.value, 'build_out', 'op_kernel')
        compile_file_path.mkdir(parents=True, exist_ok=True)
        # 旧芯片 Ascend950 的标记与残留产物
        temp_dir.joinpath(ModeCustom.ADD_CUSTOM.value,
                          CompileOP.COMPILE_CHIP_MARKER).write_text("Ascend950")
        compile_file_path.joinpath(
            f'{ModeCustom.ADD_CUSTOM.value}_add_custom.o').write_text("old")
        mocker.patch("shutil.which", return_value=False)
        other_chip_op = CompileOP(op_name, inputs, outputs,
                                  'Ascend910_96', 'Ascend910_96')
        build_result = other_chip_op.get_compile_file(temp_dir)
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        assert build_result == []

