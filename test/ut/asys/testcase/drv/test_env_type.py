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

import ctypes
import os
import sys
from unittest.mock import MagicMock

import pytest
from testcase.conftest import ASYS_SRC_PATH, CONF_SRC_PATH, AssertTest

sys.path.insert(0, ASYS_SRC_PATH)

from common import RetCode
from drv import LoadSoType
from drv.env_type import AICORE_STL_SO_NAME, AICORE_STL_SO_SUBPATH


def setup_module():
    print("TestRCEnvTpye ut test start.")


def teardown_module():
    print("TestRCEnvTpye ut test finish.")


class TestRCEnvTpye(AssertTest):
    def setup_method(self):
        LoadSoType.clear()

    def teardown_method(self):
        pass

    @pytest.mark.parametrize("ent, env_type", [[0, "RC"], [1, "EP"]])
    def test_get_env_type(self, ent, env_type, mocker, caplog):
        self.assertTrue(True)
        mock_dev = MagicMock()
        mock_dev.drvGetPlatformInfo.return_value = 0
        mock_dev.drvGetPlatformInfo.argtypes = [ctypes.POINTER(ctypes.c_int)]
        num = ctypes.c_int(0)
        mock_dev.drvGetPlatformInfo(ctypes.pointer(num))

        # 使用 side_effect 来模拟 drvGetPlatformInfo 修改 num 的值
        def side_effect(num_ptr):
            num_ptr.contents.value = ent
            return 0

        mock_dev.drvGetPlatformInfo.side_effect = side_effect
        mocker.patch.object(LoadSoType, "get_drvhal_env_type", return_value=mock_dev)
        self.assertTrue(LoadSoType().get_env_type() == env_type)
        LoadSoType.clear()


class TestAicoreStlSoPath(AssertTest):
    """libaml_aicore_stl.so 装在 tools/aml/lib64/aicore_stl/,不在 LD_LIBRARY_PATH 中,
    必须按 ASCEND_HOME_PATH 拼绝对路径加载(否则入口 so 内部的 dladdr 相对链也会断)。
    """

    @staticmethod
    def _make_so(tmp_path):
        # 造出 <tmp>/tools/aml/lib64/aicore_stl/libaml_aicore_stl.so
        so_dir = tmp_path / AICORE_STL_SO_SUBPATH
        so_dir.mkdir(parents=True)
        so_file = so_dir / AICORE_STL_SO_NAME
        so_file.write_bytes(b"")
        return so_file

    def setup_method(self):
        LoadSoType.clear()

    def teardown_method(self):
        LoadSoType.clear()

    def test_so_path_resolved_under_ascend_home(self, tmp_path, monkeypatch):
        """so 存在时返回其绝对路径。"""
        so_file = self._make_so(tmp_path)
        monkeypatch.setenv("ASCEND_HOME_PATH", str(tmp_path))
        self.assertTrue(LoadSoType.get_aicore_stl_so_path() == os.path.realpath(str(so_file)))

    def test_so_path_none_when_home_unset(self, monkeypatch):
        """ASCEND_HOME_PATH 未设置时返回 None,不抛异常。"""
        monkeypatch.delenv("ASCEND_HOME_PATH", raising=False)
        self.assertTrue(LoadSoType.get_aicore_stl_so_path() is None)

    def test_so_path_none_when_file_absent(self, tmp_path, monkeypatch):
        """ASCEND_HOME_PATH 已设置但 so 未安装时返回 None。"""
        monkeypatch.setenv("ASCEND_HOME_PATH", str(tmp_path))
        self.assertTrue(LoadSoType.get_aicore_stl_so_path() is None)

    def test_load_uses_absolute_path(self, tmp_path, monkeypatch, mocker):
        """EP 侧:必须以绝对路径调 load_dll,而非裸 so 名。

        裸名会走 LD_LIBRARY_PATH(该 so 不在其中),且会让入口 so 内部
        dladdr 定位到错误目录,导致形态 so 加载失败。
        """
        so_file = self._make_so(tmp_path)
        monkeypatch.setenv("ASCEND_HOME_PATH", str(tmp_path))
        mocker.patch.object(LoadSoType, "get_env_type", return_value="EP")
        mock_dll = MagicMock()
        load_dll = mocker.patch.object(LoadSoType, "load_dll", return_value=mock_dll)

        self.assertTrue(LoadSoType().get_aml_aicore_stl() is mock_dll)
        load_dll.assert_called_once_with(os.path.realpath(str(so_file)))
        # 传入的路径必须是绝对路径且指向形态子目录的父目录 aicore_stl/
        passed = load_dll.call_args[0][0]
        self.assertTrue(os.path.isabs(passed))
        self.assertTrue(passed.endswith(os.path.join(AICORE_STL_SO_SUBPATH, AICORE_STL_SO_NAME)))

    def test_load_returns_failed_when_so_absent(self, tmp_path, monkeypatch, mocker):
        """so 缺失时返回 RetCode.FAILED(调用方 asys_diagnose 判的就是这个值),且不调 load_dll。"""
        monkeypatch.setenv("ASCEND_HOME_PATH", str(tmp_path))
        mocker.patch.object(LoadSoType, "get_env_type", return_value="EP")
        load_dll = mocker.patch.object(LoadSoType, "load_dll")

        self.assertTrue(LoadSoType().get_aml_aicore_stl() == RetCode.FAILED)
        self.assertTrue(load_dll.call_count == 0)

    def test_load_returns_failed_when_home_unset(self, monkeypatch, mocker):
        """ASCEND_HOME_PATH 未设置时返回 RetCode.FAILED,且不调 load_dll。"""
        monkeypatch.delenv("ASCEND_HOME_PATH", raising=False)
        mocker.patch.object(LoadSoType, "get_env_type", return_value="EP")
        load_dll = mocker.patch.object(LoadSoType, "load_dll")

        self.assertTrue(LoadSoType().get_aml_aicore_stl() == RetCode.FAILED)
        self.assertTrue(load_dll.call_count == 0)

    def test_no_load_on_rc(self, tmp_path, monkeypatch, mocker):
        """RC 侧不加载该 so(仅 toolkit run 包 EP 侧提供),返回 None 且不调 load_dll。"""
        self._make_so(tmp_path)
        monkeypatch.setenv("ASCEND_HOME_PATH", str(tmp_path))
        mocker.patch.object(LoadSoType, "get_env_type", return_value="RC")
        load_dll = mocker.patch.object(LoadSoType, "load_dll")

        self.assertTrue(LoadSoType().get_aml_aicore_stl() is None)
        self.assertTrue(load_dll.call_count == 0)

    def test_load_cached_once(self, tmp_path, monkeypatch, mocker):
        """单例缓存:重复取只加载一次。"""
        self._make_so(tmp_path)
        monkeypatch.setenv("ASCEND_HOME_PATH", str(tmp_path))
        mocker.patch.object(LoadSoType, "get_env_type", return_value="EP")
        load_dll = mocker.patch.object(LoadSoType, "load_dll", return_value=MagicMock())

        first = LoadSoType().get_aml_aicore_stl()
        second = LoadSoType().get_aml_aicore_stl()
        self.assertTrue(first is second)
        self.assertTrue(load_dll.call_count == 1)
