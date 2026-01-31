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
import shutil
import sys

import pytest
import subprocess
from pathlib import Path

from .conftest import CONF_SRC_PATH, ASYS_SRC_PATH, test_case_tmp
from .conftest import AssertTest

sys.argv.insert(0, CONF_SRC_PATH)
sys.path.insert(0, ASYS_SRC_PATH)

import asys
from params import ParamDict
from common.device import DeviceInfo
from common.chip_handler import g_device_map

class AsysDiagnose0:

    def AmlStressDetect(self, a, b):
        return 0

    def AmlHbmDetectWithType(self, a, b, c):
        return 0

    def AmlCpuDetect(self, a, b):
        return 0

    def AmlStressRestore(self, a):
        return 0

    def halGetDeviceInfo(self, phyid, a, b, masterid):
        return 0

    def drvDeviceGetPhyIdByIndex(self, device_id, phyid):
        return 0

class AsysDiagnose1:

    def AmlStressDetect(self, a, b):
        return 1

    def AmlHbmDetectWithType(self, a, b, c):
        return 1

    def AmlCpuDetect(self, a, b):
        return 1

    def AmlStressRestore(self, a):
        return 1

    def halGetDeviceInfo(self, phyid, a, b, masterid):
        return 1

    def drvDeviceGetPhyIdByIndex(self, device_id, phyid):
        return 1

class TestDiagnose(AssertTest):

    def setup_method(self):
        print("init test environment")
        if not os.getenv("ASCEND_OPP_PATH"):
            os.environ["ASCEND_OPP_PATH"] = "/home"
        if os.path.exists(test_case_tmp):
            shutil.rmtree(test_case_tmp)
        os.mkdir(test_case_tmp)
        os.chdir(test_case_tmp)
        ParamDict.clear()
        g_device_map.clear()

    def teardown_method(self):
        print("clean test environment.")
        if os.getenv("ASCEND_OPP_PATH"):
            os.environ.pop("ASCEND_OPP_PATH")
        if os.path.exists(test_case_tmp):
            shutil.rmtree(test_case_tmp)

    @pytest.mark.parametrize(["chip_type"], [("Ascend 910_95 V1",)])
    def test_diagnose_supported_soc(self, mocker, capsys, chip_type):
        sys.argv = [CONF_SRC_PATH, "diagnose", "-r=hbm_detect", "--timeout=10"]
        mocker.patch("common.device.LoadSoType.get_drvhal_env_type", return_value=AsysDiagnose0())
        mocker.patch("common.device.LoadSoType.get_ascend_ml", return_value=AsysDiagnose1())
        mocker.patch("os.getuid", return_value=0)
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=2)
        mocker.patch.object(DeviceInfo, "get_ecc_isolated_page", return_value=-1)
        mocker.patch.object(DeviceInfo, "clear_ecc_isolated", return_value=-1)
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value=chip_type)
        mocker.patch("os.path.isfile", return_value=True)
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
        captured = capsys.readouterr()
        self.assertTrue("| HBM Detect             | Warn - All             | \n |                        | (0, 0)                 |" in captured.out)