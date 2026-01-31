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

import sys

import pytest

from .conftest import CONF_SRC_PATH, ASYS_SRC_PATH


sys.argv.insert(0, CONF_SRC_PATH)
sys.path.insert(0, ASYS_SRC_PATH)

import asys
from params import ParamDict
from .conftest import AssertTest
from common.device import DeviceInfo
from common.chip_handler import g_device_map

class AsysConfig0:
    def AmlStressRestore(self, *args):
        return 0

class AsysConfig1:
    def AmlStressRestore(self, *args):
        return 1


class TestAsysConfig(AssertTest):

    def setup_method(self):
        ParamDict.clear()
        g_device_map.clear()

    def teardown_method(self):
        ParamDict.clear()
        g_device_map.clear()

    @pytest.mark.parametrize(["chip_type"], [("Ascend 910_9591 V1",)])
    def test_asys_config_supported_chip(self, mocker, chip_type):
        sys.argv = [CONF_SRC_PATH, "config", "-d=1", "--restore", "--stress_detect"]
        mocker.patch("common.device.LoadSoType.get_ascend_ml", return_value=AsysConfig0())
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value=chip_type)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())