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
import os
from pathlib import Path

from testcase.conftest import ASYS_SRC_PATH, CONF_SRC_PATH, ut_root_path
sys.path.insert(0, ASYS_SRC_PATH)

from common.supported_chip import AsysConfigSupportedChip, AsysDiagnoseSupportedChip
from ..conftest import AssertTest
from common.device import DeviceInfo
from common.chip_handler import g_device_map

class TestSupportedChip(AssertTest):

    test_file_path = os.path.join(ut_root_path, "test_file")

    def setup_method(self):
        testfile = Path(self.test_file_path)
        testfile.touch(exist_ok=True)
        self.fp = open(testfile)
        g_device_map.clear()

    def teardown_method(self):
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)
    
    @pytest.mark.parametrize(
        ["chip_type", "expect"], 
        [("Ascend 910_9591 V1", True), ("Unknow", False)])
    def test_asys_config_supported_chip(self, mocker, chip_type, expect):
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value=chip_type)
        self.assertTrue(AsysConfigSupportedChip().get_supported_chip_info(0)[0] == expect)
    
    @pytest.mark.parametrize(
        ["chip_type", "expect"], 
        [("Ascend 910_9591 V1", True), ("Unknow", False)]
    )
    def test_asys_diagnose_supported_chip(self, mocker, chip_type, expect):
        mocker.patch.object(DeviceInfo, "get_chip_info", return_value=chip_type)
        self.assertTrue(AsysDiagnoseSupportedChip().get_supported_chip_info(0)[0] == expect)
