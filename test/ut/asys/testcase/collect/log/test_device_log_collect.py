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

from testcase.conftest import ASYS_SRC_PATH
from testcase.conftest import AssertTest
sys.path.insert(0, ASYS_SRC_PATH)
import asys

from common import FileOperate
from collect.log import collect_device_logs
from testcase.conftest import AssertTest

def setup_module():
    print("TestDeviceLogCollect ut test start.")

def teardown_module():
    print("TestDeviceLogCollect ut test finsh.")

class TestDeviceLogCollect(AssertTest):

    def setup_method(self):
        pass

    def teardown_method(self):
        pass

    def test_device_log_collect_success(self, mocker):
        mocker.patch("collect.log.device_log_collect.collect_host_driver", return_value=True)
        mocker.patch("common.FileOperate.list_dir", return_value=["dev-os-3", "dev-os-7"])
        mocker.patch("common.FileOperate.collect_dir", return_value=True)
        self.assertTrue(collect_device_logs("./", "./output"))

        mocker.patch("common.FileOperate.list_dir", return_value=["dev-os-0"])
        mocker.patch("common.FileOperate.collect_dir", return_value=True)
        self.assertTrue(collect_device_logs("./", "./output"))

    def test_device_log_collect_failed(self, mocker):
        mocker.patch("common.FileOperate.list_dir", return_value=["dev-os-0", "device-os"])
        mocker.patch("common.FileOperate.collect_dir", return_value=False)
        self.assertTrue(not collect_device_logs("./", "./output"))

    def test__device_log_collect_host_driver(self, mocker):
        mocker.patch("collect.log.device_log_collect.collect_slogd", return_value=True)
        mocker.patch("common.FileOperate.collect_dir", return_value=True)
        mocker.patch("common.FileOperate.remove_dir", return_value=True)
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)
        self.assertTrue(not collect_device_logs("./", "./output"))

        mocker.patch("common.FileOperate.list_dir", return_value=["host"])
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=False)
        self.assertTrue(not collect_device_logs("./", "./output"))

        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)
        self.assertTrue(collect_device_logs("./", "./output"))

    def test_collect_slogd_failed(self, mocker, caplog):
        mocker.patch("collect.log.device_log_collect.collect_messages", return_value=True)
        mocker.patch("collect.log.device_log_collect.collect_stackcore", return_value=True)
        mocker.patch("collect.log.device_log_collect.collect_bbox", return_value=True)
        mocker.patch("collect.log.device_log_collect.collect_host_driver", return_value=True)
        mocker.patch("common.FileOperate.list_dir", return_value=["dev-os-0", "device-os"])
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("common.FileOperate.collect_dir", return_value=False)
        self.assertTrue(not collect_device_logs("./", "./output"))
