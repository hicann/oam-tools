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
import shutil

from testcase.conftest import ASYS_SRC_PATH, test_case_tmp

sys.path.insert(0, ASYS_SRC_PATH)

from params import ParamDict
from health import AsysHealth
from ..conftest import AssertTest


class AsysDeviceInfo:

    @staticmethod
    def get_device_health(*args):
        return "Healthy"

    @staticmethod
    def get_device_errorcode(*args):
        return [[123456, "00000000"], [123456, "00000000"]]


class TestAsysCollect(AssertTest):

    def setup_method(self):
        ParamDict.clear()

    def teardown_method(self):
        ParamDict.clear()

    def test_health_device_num_failed(self, mocker):

        class Args:
            subparser_name = "health"
            d = None

        mocker.patch("health.asys_health.DeviceInfo.get_device_count", return_value=None)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(not AsysHealth().run())

    def test_health_1p(self, mocker):

        class Args:
            subparser_name = "health"
            d = None

        mocker.patch("health.asys_health.DeviceInfo.get_device_count", return_value=1)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysHealth().run())

    def test_health_2p(self, mocker):

        class Args:
            subparser_name = "health"
            d = None

        mocker.patch("health.asys_health.DeviceInfo.get_device_count", return_value=2)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysHealth().run())

    def test_health_d_3(self, mocker):
        class Args:
            subparser_name = "health"
            d = 3

        mocker.patch("health.asys_health.DeviceInfo.get_device_count", return_value=4)
        ParamDict().set_env_type("EP")
        ParamDict().set_args(Args())
        self.assertTrue(AsysHealth().run())

    def test_health_2p_file(self, mocker):
        mocker.patch("health.asys_health.DeviceInfo", return_value=AsysDeviceInfo())
        mocker.patch("health.asys_health.DeviceInfo.get_device_count", return_value=4)
        ParamDict().set_env_type("EP")
        ParamDict().asys_output_timestamp_dir = test_case_tmp
        if not os.path.exists(test_case_tmp):
            os.makedirs(test_case_tmp)

        from health import AsysHealth

        obj = AsysHealth()
        obj._save_file({0: [AsysDeviceInfo().get_device_health(),
                            AsysDeviceInfo().get_device_errorcode()]})
        self.assertTrue(os.path.isfile(f"{test_case_tmp}/health_result.txt"))
        self.assertTrue(os.listdir(f"{test_case_tmp}") == ["health_result.txt"])
        shutil.rmtree(f"{test_case_tmp}")
