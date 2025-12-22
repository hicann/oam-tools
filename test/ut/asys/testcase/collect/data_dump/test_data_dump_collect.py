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
import os

from testcase.conftest import ASYS_SRC_PATH, ut_root_path
sys.path.insert(0, ASYS_SRC_PATH)

from collect.data_dump.data_dump_collect import collect_data_dump, get_source_dir
from params import ParamDict
from common import consts
from testcase.conftest import AssertTest

def setup_module():
    print("TestDataDumpCollect ut test start.")

def teardown_module():
    print("TestDataDumpCollect ut test finsh.")

class TestDataDumpCollect(AssertTest):

    def setup_method(self):
        pass

    def teardown_method(self):
        pass

    def test_data_dump_collect_success_launch(self, mocker, caplog):
        mocker.patch("params.ParamDict.get_command", return_value=consts.launch_cmd)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("common.FileOperate.collect_dir", return_value=True)
        ParamDict.asys_output_timestamp_dir = ut_root_path
        collect_data_dump("./output")
        self.assertTrue('failed' not in caplog.text)

    def test_data_dump_collect_success_collect(self, mocker, caplog):
        mocker.patch("params.ParamDict.asys_output_timestamp_dir", return_value=ut_root_path)
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("common.FileOperate.collect_dir", return_value=True)
        collect_data_dump("./output")
        self.assertTrue('failed' not in caplog.text)

    def test_data_dump_get_collect_path_npu(self, mocker):
        mocker.patch("params.ParamDict.asys_output_timestamp_dir", return_value=ut_root_path)
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("os.path.exists", return_value=True)

        os.environ["NPU_COLLECT_PATH"] = ut_root_path
        path = get_source_dir()
        self.assertTrue(path == os.path.join(ut_root_path, "extra-info", "data-dump"))

        os.environ.pop("NPU_COLLECT_PATH")

    def test_data_dump_get_collect_path_work(self, mocker, caplog):
        mocker.patch("params.ParamDict.asys_output_timestamp_dir", return_value=ut_root_path)
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("common.FileOperate.collect_dir", return_value=True)

        os.environ["ASCEND_WORK_PATH"] = ut_root_path
        path = get_source_dir()
        self.assertTrue(path == os.path.join(ut_root_path, "extra-info", "data-dump"))

        self.assertTrue('failed' not in caplog.text)
        os.environ.pop("ASCEND_WORK_PATH")
