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
import pytest

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

    @staticmethod
    def test_get_ub_size_not_tbe(monkeypatch, mocker):
        # 必须显式让 "from tbe.common import platform" 失败，不能依赖环境里
        # 恰好没有 tbe：CANN 自带 tbe，其导入会因缺 scipy 中途失败，留下
        # tbe=None 但 tbe.common 已被缓存为真模块（部分初始化的导入缓存）。
        # 此后该 import 经缓存命中而不抛 ImportError，被测分支走不到 return 0，
        # 于是本用例单独跑通过、进全量套件即失败，且云端与本地失败的用例名不同。
        # 把条目设为 None 是 CPython 约定：sys.modules[x] is None 时 import x
        # 直接抛 ImportError。monkeypatch 会在用例结束后自动还原。
        for mod_name in ("tbe", "tbe.common", "tbe.common.platform"):
            monkeypatch.setitem(sys.modules, mod_name, None)
        ub_size = compile_op.get_ub_size()
        assert ub_size == 0

    @staticmethod
    def test_get_ub_size_import_error(mocker):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("tbe"):
                raise ImportError("mocked tbe import error")
            return real_import(name, *args, **kwargs)

        mocker.patch("builtins.__import__", side_effect=mock_import)
        ub_size = compile_op.get_ub_size()
        assert ub_size == 0

    @staticmethod
    def test_get_ub_size_attribute_error(mocker):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("tbe"):
                raise AttributeError("module 'numpy' has no attribute 'bool'")
            return real_import(name, *args, **kwargs)

        mocker.patch("builtins.__import__", side_effect=mock_import)
        ub_size = compile_op.get_ub_size()
        assert ub_size == 0

    def test_get_soc_version_failed(self, monkeypatch, mocker):
        custom_paths = [MSAICERR_PATH, f"{cur_abspath}/../res/package"]
        monkeypatch.setattr(sys, "path", custom_paths)
        mocker.patch("ms_interface.ascend950.compile_op.DSMIInterface", side_effect=OSError("mocked dsmi"))
        ub_size = compile_op.get_ub_size()
        assert ub_size == 0

    @pytest.mark.skip
    def test_get_ub_size_success(self, monkeypatch, mocker):
        custom_paths = [MSAICERR_PATH, f"{cur_abspath}/../res/package"]
        monkeypatch.setattr(sys, "path", custom_paths)
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
        # 写入与当前芯片一致的标记文件，命中复用分支
        marker_dir = temp_dir / op_name
        marker_dir.mkdir(parents=True, exist_ok=True)
        (marker_dir / CompileOP.COMPILE_CHIP_MARKER).write_text("Ascend950")
        mocker.patch.object(Path, "rglob", return_value=['test.o'])
        build_res = compile_op.get_compile_file(temp_dir)
        shutil.rmtree(temp_dir)
        assert len(build_res) == 2

    def test_get_compile_file_chip_mismatch_recompile(self, mocker):
        # 标记文件记录的芯片与当前芯片不一致时，不能复用旧产物，应重新编译
        temp_dir = Path(cur_abspath) / "test_get_compile_file_chip_mismatch"
        marker_dir = temp_dir / op_name
        marker_dir.mkdir(parents=True, exist_ok=True)
        (marker_dir / CompileOP.COMPILE_CHIP_MARKER).write_text("Ascend950")
        # 旧芯片残留的编译产物
        old_build = marker_dir / 'build_out' / 'op_kernel'
        old_build.mkdir(parents=True, exist_ok=True)
        old_build.joinpath(f'{op_name}_add_custom.o').write_text("old")
        mocker.patch("shutil.which", return_value=False)
        other_chip_op = CompileOP(op_name, inputs, outputs, 'Ascend910_96', 'Ascend910_96')
        build_res = other_chip_op.get_compile_file(temp_dir)
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        # 未命中复用而进入编译流程，因 msopgen 缺失返回空
        assert build_res == []

    def test_get_compile_file_clean_failed_return_empty(self, mocker):
        # 清理旧目录失败时，get_compile_file 应提前返回空，避免复用旧芯片产物
        temp_dir = Path(cur_abspath) / "test_get_compile_file_clean_failed"
        (temp_dir / op_name).mkdir(parents=True, exist_ok=True)
        mocker.patch("shutil.which", return_value=True)
        mocker.patch("shutil.rmtree", side_effect=OSError("mock"))
        build_res = compile_op.get_compile_file(temp_dir)
        mocker.stopall()
        shutil.rmtree(temp_dir)
        assert build_res == []

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

    def test_get_chip_marker_file(self):
        # 标记文件应位于 compile_temp_dir/{op_name}/.compile_chip
        temp_dir = Path(cur_abspath) / "test_get_chip_marker_file"
        marker_file = compile_op._get_chip_marker_file(temp_dir)
        assert marker_file == temp_dir / op_name / CompileOP.COMPILE_CHIP_MARKER

    def test_write_chip_marker_success(self):
        # 写入标记文件后内容应为当前芯片
        temp_dir = Path(cur_abspath) / "test_write_chip_marker_success"
        compile_op._write_chip_marker(temp_dir)
        marker_file = temp_dir / op_name / CompileOP.COMPILE_CHIP_MARKER
        assert marker_file.read_text() == "Ascend950"
        shutil.rmtree(temp_dir)

    def test_write_chip_marker_oserror(self, mocker):
        # 写入失败时仅告警，不应抛异常
        temp_dir = Path(cur_abspath) / "test_write_chip_marker_oserror"
        mocker.patch.object(Path, "write_text", side_effect=OSError("mock"))
        warn_log = mocker.patch("ms_interface.ascend950.compile_op.utils.print_warn_log")
        compile_op._write_chip_marker(temp_dir)
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        assert warn_log.called
        assert "Failed to write compile chip marker" in warn_log.call_args[0][0]

    def test_is_cache_chip_matched_true(self):
        # 标记文件存在且与当前芯片一致时返回 True
        temp_dir = Path(cur_abspath) / "test_is_cache_chip_matched_true"
        (temp_dir / op_name).mkdir(parents=True, exist_ok=True)
        (temp_dir / op_name / CompileOP.COMPILE_CHIP_MARKER).write_text("Ascend950")
        assert compile_op._is_cache_chip_matched(temp_dir) is True
        shutil.rmtree(temp_dir)

    def test_is_cache_chip_matched_no_marker(self):
        # 标记文件不存在时返回 False
        temp_dir = Path(cur_abspath) / "test_is_cache_chip_matched_no_marker"
        (temp_dir / op_name).mkdir(parents=True, exist_ok=True)
        assert compile_op._is_cache_chip_matched(temp_dir) is False
        shutil.rmtree(temp_dir)

    def test_is_cache_chip_matched_mismatch(self):
        # 标记文件记录的芯片与当前芯片不一致时返回 False
        temp_dir = Path(cur_abspath) / "test_is_cache_chip_matched_mismatch"
        (temp_dir / op_name).mkdir(parents=True, exist_ok=True)
        (temp_dir / op_name / CompileOP.COMPILE_CHIP_MARKER).write_text("Ascend910_96")
        assert compile_op._is_cache_chip_matched(temp_dir) is False
        shutil.rmtree(temp_dir)

    def test_is_cache_chip_matched_read_oserror(self, mocker):
        # 读取标记文件失败时返回 False 并告警
        temp_dir = Path(cur_abspath) / "test_is_cache_chip_matched_read_oserror"
        (temp_dir / op_name).mkdir(parents=True, exist_ok=True)
        (temp_dir / op_name / CompileOP.COMPILE_CHIP_MARKER).write_text("Ascend950")
        mocker.patch.object(Path, "read_text", side_effect=OSError("mock"))
        warn_log = mocker.patch("ms_interface.ascend950.compile_op.utils.print_warn_log")
        assert compile_op._is_cache_chip_matched(temp_dir) is False
        shutil.rmtree(temp_dir)
        assert warn_log.called
        assert "Failed to read compile chip marker" in warn_log.call_args[0][0]

    def test_clean_op_build_dir_exist(self):
        # 旧算子目录存在时应被清理，清理成功返回 True
        temp_dir = Path(cur_abspath) / "test_clean_op_build_dir_exist"
        op_dir = temp_dir / op_name
        op_dir.mkdir(parents=True, exist_ok=True)
        op_dir.joinpath("old.o").write_text("old")
        assert compile_op._clean_op_build_dir(temp_dir) is True
        assert not op_dir.exists()
        shutil.rmtree(temp_dir)

    def test_clean_op_build_dir_not_exist(self):
        # 目录不存在时为空操作，不应报错，返回 True
        temp_dir = Path(cur_abspath) / "test_clean_op_build_dir_not_exist"
        assert compile_op._clean_op_build_dir(temp_dir) is True
        assert not temp_dir.exists()

    def test_clean_op_build_dir_oserror(self, mocker):
        # 清理失败时记录错误日志并返回 False，不应抛异常
        temp_dir = Path(cur_abspath) / "test_clean_op_build_dir_oserror"
        (temp_dir / op_name).mkdir(parents=True, exist_ok=True)
        mocker.patch("shutil.rmtree", side_effect=OSError("mock"))
        error_log = mocker.patch("ms_interface.ascend950.compile_op.utils.print_error_log")
        assert compile_op._clean_op_build_dir(temp_dir) is False
        mocker.stopall()
        shutil.rmtree(temp_dir)
        assert error_log.called
        assert "Failed to clean old compile dir" in error_log.call_args[0][0]
