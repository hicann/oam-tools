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

import logging
import sys
import pytest
import os
import ctypes
from pathlib import Path

from testcase.conftest import ASYS_SRC_PATH, CONF_SRC_PATH, ut_root_path

sys.path.insert(0, ASYS_SRC_PATH)
from common.device import DeviceInfo
from common.chip_handler import ChipHandler
from common.const import RetCode
from drv import LoadSoType
from ..conftest import AssertTest

class TestDevice(AssertTest):
    test_file_path = os.path.join(ut_root_path, "test_file")

    def setup_method(self):
        testfile = Path(self.test_file_path)
        testfile.touch(exist_ok=True)
        self.fp = open(testfile)

    def teardown_method(self):
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)

    def test_get_device_aic_info_with_910D(self, mocker):
        self.assertTrue(True)

        class AmlDevice():
            @staticmethod
            def AmlDeviceGetAicoreInfo(device_id, info):
                return 0

        mocker.patch("common.device.LoadSoType.get_ascend_ml", return_value=AmlDevice())
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        device_info = ChipHandler().get_handler("950")
        self.assertTrue(device_info.get_device_aic_info(0) == [0, "0, 0", "0, 0"])

    def test_get_device_bus_info_with_910D(self, mocker):
        self.assertTrue(True)

        class AmlDevice():
            @staticmethod
            def AmlDeviceGetBusInfo(device_id, info):
                return 0

        mocker.patch("common.device.LoadSoType.get_ascend_ml", return_value=AmlDevice())
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        device_info = ChipHandler().get_handler("950")
        self.assertTrue(device_info.get_device_bus_info(0) == ["0, 0", "0, 0", 0, "0, 0", "0, 0"])

    @pytest.mark.parametrize(
        ["device_return", "expect"],
        [(0, [0, 0, '-', 0]), (1, ['-', '-', '-', '-'])]
    )
    def test_get_device_hbm_info_with_910D(self, mocker, device_return, expect):
        self.assertTrue(True)

        class DrvDsmi():

            @staticmethod
            def dsmi_get_device_info(device_id, main_cmd, sub_cmd, p_memory_info, size):
                return device_return

            @staticmethod
            def dsmi_get_device_utilization_rate(device_id, device_type, p_utilization):
                return 0

        mocker.patch("common.device.LoadSoType.get_drvdsmi_env_type", return_value=DrvDsmi())
        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        deviceinfo = ChipHandler().get_handler("950")
        self.assertTrue(deviceinfo.get_device_hbm_info(0) == expect)

    @pytest.mark.parametrize(["value", "expect"], [(0, 0), (1, '-')])
    def test_get_950_device_temperature(self, value, expect, mocker):
        self.assertTrue(True)
        class DrvDsmi():
            @staticmethod
            def dsmi_get_soc_sensor_info(device_id, soc_temp, p_memory_info):
                return value

        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        mocker.patch.object(LoadSoType, "get_drvdsmi_env_type", return_value=DrvDsmi())
        deviceinfo = ChipHandler().get_handler("950")
        res = deviceinfo.get_device_temperature(0)
        self.assertTrue(res == expect)

    def test_check_get_device_info(self, mocker, caplog):
        self.assertTrue(True)
        class DrvDsmi():
            @staticmethod
            def dsmi_get_device_power_info(device_id, p):
                return 1

            @staticmethod
            def dsmi_get_device_frequency(device_id, type_device, p):
                return 1

            @staticmethod
            def dsmi_clear_ecc_isolated_statistics_info(device_id):
                return 1

        class DrvHal():
            @staticmethod
            def halGetChipInfo(device_id, p):
                return 1

        mocker.patch("drv.LoadSoType.get_env_type", return_value="EP")
        mocker.patch("drv.LoadSoType.get_drvdsmi_env_type", return_value=DrvDsmi)
        mocker.patch("drv.LoadSoType.get_drvhal_env_type", return_value=DrvHal)
        mocker.patch("drv.LoadSoType.get_ascend_ml", return_value=None)
        deviceinfo = DeviceInfo()
        self.assertTrue(deviceinfo.get_chip_info(0) == 'Unknown')
        self.assertTrue(deviceinfo.get_device_power(0) == '-')
        self.assertTrue(deviceinfo.get_device_frequency(0, 1) == '-')
        deviceinfo.clear_ecc_isolated(0)
        self.assertTrue('Clear ecc isolated failed' in caplog.text)
        device_info_95 = ChipHandler().get_handler("950")
        self.assertTrue(device_info_95.get_encode_component_one_id(65536) == 0)