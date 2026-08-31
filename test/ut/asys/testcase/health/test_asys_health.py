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

# ruff: noqa: E501, S607, PLR0915, PLR6301, PLR1722  # test mock methods, partial paths, long lines

# pylint: disable=protected-access,redefined-outer-name,attribute-defined-outside-init,unused-argument,broad-exception-caught,unused-import,unused-variable,redefined-builtin,reimported,no-member,function-redefined,possibly-used-before-assignment,no-self-argument,too-many-function-args,unexpected-keyword-arg,no-value-for-parameter  # pytest fixture/mock/cleanup patterns

import os
import shutil

from testcase.conftest import test_case_tmp


from params import ParamDict
from health import AsysHealth
from ..conftest import AssertTest


class AsysDeviceInfo:
    @staticmethod
    def get_device_health(*_args):
        return "Healthy"

    @staticmethod
    def get_device_errorcode(*_args):
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

        mocker.patch(
            "health.asys_health.DeviceInfo.get_device_count", return_value=None
        )
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
        obj._save_file(
            {
                0: [
                    AsysDeviceInfo().get_device_health(),
                    AsysDeviceInfo().get_device_errorcode(),
                ]
            }
        )
        self.assertTrue(os.path.isfile(f"{test_case_tmp}/health_result.txt"))
        self.assertTrue(os.listdir(f"{test_case_tmp}") == ["health_result.txt"])
        shutil.rmtree(f"{test_case_tmp}")
