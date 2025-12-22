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
import sys
from unittest.mock import MagicMock

import pytest
from testcase.conftest import ASYS_SRC_PATH, CONF_SRC_PATH, AssertTest

sys.path.insert(0, ASYS_SRC_PATH)

from drv import LoadSoType


def setup_module():
    print("TestRCEnvTpye ut test start.")


def teardown_module():
    print("TestRCEnvTpye ut test finsh.")


class TestRCEnvTpye(AssertTest):

    def setup_method(self):
        pass

    def teardown_method(self):
        pass

    @pytest.mark.parametrize('ent, env_type', [[0, 'RC'], [1, 'EP']])
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
        mocker.patch.object(LoadSoType, 'get_drvhal_env_type', return_value=mock_dev)
        self.assertTrue(LoadSoType().get_env_type() == env_type)
        LoadSoType.clear()
