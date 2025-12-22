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
import shutil

import pytest

from .conftest import CONF_SRC_PATH, ASYS_SRC_PATH, test_case_tmp, DrvDsmi
from .conftest import AssertTest

sys.argv.insert(0, CONF_SRC_PATH)
sys.path.insert(0, ASYS_SRC_PATH)

import asys
from params import ParamDict
from common import RetCode
from common.device import DeviceInfo


class AsysDeviceInfo:
    def __init__(self, num):
        self.device_count = num

    @staticmethod
    def get_device_health(*args):
        return "Healthy"

    @staticmethod
    def get_device_errorcode(*args):
        return [[123456, "00000000"], [123456, "00000000"]]

    def get_device_count(self):
        return self.device_count


class TestCollect(AssertTest):

    def setup_method(self):
        print("init test environment")
        ParamDict.clear()

    def teardown_method(self):
        print("clean test environment.")

    def test_health_1p(self, mocker):
        sys.argv = [CONF_SRC_PATH, "health", "-d=0"]
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        mocker.patch("health.asys_health.DeviceInfo", return_value=AsysDeviceInfo(1))
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    def test_health_4p(self, mocker):
        sys.argv = [CONF_SRC_PATH, "health"]
        mocker.patch("health.asys_health.DeviceInfo", return_value=AsysDeviceInfo(4))
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())

    def test_health_2p_file(self, mocker):
        sys.argv = [CONF_SRC_PATH, "collect"]
        mocker.patch("collect.asys_collect.AsysInfo.write_info", return_value=None)
        mocker.patch("collect.asys_collect.collect_host_logs", return_value=None)
        mocker.patch("collect.asys_collect.collect_graph", return_value=None)
        mocker.patch("collect.asys_collect.collect_ops", return_value=None)
        mocker.patch("collect.asys_collect.collect_data_dump", return_value=None)
        mocker.patch("asys.create_out_timestamp_dir", return_value=RetCode.SUCCESS)

        mocker.patch("health.asys_health.DeviceInfo", return_value=AsysDeviceInfo(4))
        ParamDict().set_env_type("EP")
        ParamDict().asys_output_timestamp_dir = test_case_tmp
        self.assertTrue(asys.main())
        self.assertTrue(os.path.isfile(f"{ParamDict().asys_output_timestamp_dir}/health_result.txt"))
        self.assertTrue(os.listdir(f"{ParamDict().asys_output_timestamp_dir}") == ["health_result.txt"])
        shutil.rmtree(f"{ParamDict().asys_output_timestamp_dir}")

    @pytest.mark.parametrize('set_data', [
        'device_errorcode',
        'query_errorstring'
    ])
    def test_get_health_error_code_failed(self, mocker, set_data, caplog):
        sys.argv = [CONF_SRC_PATH, "health", "-d=0"]
        mocker.patch.object(DeviceInfo, "get_device_count", return_value=1)
        if set_data == 'device_errorcode':
            DrvDsmi.set_res(device_errorcode=1)
        elif set_data == 'query_errorstring':
            DrvDsmi.set_res(query_errorstring=1)
        mocker.patch("common.device.LoadSoType.get_drvdsmi_env_type", return_value=DrvDsmi)
        mocker.patch("ctypes.c_int", return_value=ctypes.c_uint(2))
        ParamDict().set_env_type("EP")
        self.assertTrue(asys.main())
