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
import subprocess
import os

from testcase.conftest import ASYS_SRC_PATH, ut_root_path
sys.path.insert(0, ASYS_SRC_PATH)
import asys

from collect.graph import collect_graph
from params import ParamDict
from common import FileOperate
from common import consts
from testcase.conftest import AssertTest

def setup_module():
    print("TestGraphCollect ut test start.")

def teardown_module():
    print("TestGraphCollect ut test finsh.")

class TestGraphCollect(AssertTest):

    def setup_method(self):
        pass

    def teardown_method(self):
        pass

    def test_graph_collect_success(self, mocker):
        os.environ["DUMP_GRAPH_PATH"] = "./graph"
        ret = [('dir', ['subdir'], ["ge_onnx_test1.pbtxt", "ge_proto_test1.txt", "TF_GeOp_test1.pbtxt"]),   \
               ('dir/subdir', [], ["ge_onnx_test2.pbtxt", "ge_proto_test2.txt", "TF_GeOp_test2.pbtxt"])]
        mocker.patch("os.walk", return_value=ret)
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value="./")
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)
        self.assertTrue(collect_graph("./output") is None)

        mocker.patch("params.ParamDict.get_command", return_value=consts.launch_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value="bash ./test.bash")
        mocker.patch("params.ParamDict.get_ini", return_value="1")
        ParamDict.asys_output_timestamp_dir = ut_root_path
        self.assertTrue(collect_graph("./output") is None)
        if os.getenv("DUMP_GRAPH_PATH"):
            os.environ.pop("DUMP_GRAPH_PATH")

    @pytest.mark.parametrize("task", [consts.collect_cmd, consts.launch_cmd])
    def test_collect_graph_no_exec(self, mocker, task):
        ret = [('dir', ['subdir'], ["ge_onnx_test1.pbtxt", "ge_proto_test1.txt", "TF_GeOp_test1.pbtxt"]),   \
               ('dir/subdir', [], ["ge_onnx_test2.pbtxt", "ge_proto_test2.txt", "TF_GeOp_test2.pbtxt"])]
        mocker.patch("os.walk", return_value=ret)
        mocker.patch("params.ParamDict.get_command", return_value=task)
        mocker.patch("params.ParamDict.get_ini", return_value="0")
        mocker.patch("params.ParamDict.get_arg", return_value=False)
        mocker.patch("os.path.join", return_value=ut_root_path)
        self.assertTrue(collect_graph("./output") is None)
        if task == consts.launch_cmd:
            os.path.join.assert_not_called()
        else:
            os.path.join.assert_called()

    def test_collect_task_graph_collect_copy_failed(self, mocker, caplog):
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("params.ParamDict.get_ini", return_value="1")
        mocker.patch("params.ParamDict.get_arg", return_value=ut_root_path)
        ret = [('dir', ['subdir'], ["ge_onnx_test1.pbtxt", "ge_proto_test1.txt", "TF_GeOp_test1.pbtxt"]),   \
            ('dir/subdir', [], ["ge_onnx_test2.pbtxt", "ge_proto_test2.txt", "TF_GeOp_test2.pbtxt"])]
        mocker.patch("os.walk", return_value=ret)
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=False)
        self.assertTrue(collect_graph("./output") is None)

    def test_launch_task__graph_collect_get_none_source_dir(self, mocker):
        mocker.patch("params.ParamDict.get_command", return_value=consts.launch_cmd)
        mocker.patch("params.ParamDict.get_ini", return_value="1")
        mocker.patch("common.FileOperate.check_dir", return_value=False)
        mocker.patch("common.FileOperate.copy_dir")
        ParamDict.asys_output_timestamp_dir = ut_root_path
        self.assertTrue(collect_graph("./output") is None)
        FileOperate.copy_dir.assert_not_called()

    def test_graph_collect_success_from_npu_path(self, mocker):
        os.environ["NPU_COLLECT_PATH"] = "./graph"
        ret = [('dir', ['subdir'], ["ge_onnx_test1.pbtxt", "ge_proto_test1.txt", "TF_GeOp_test1.pbtxt"]),   \
               ('dir/subdir', [], ["ge_onnx_test2.pbtxt", "ge_proto_test2.txt", "TF_GeOp_test2.pbtxt"])]
        mocker.patch("os.walk", return_value=ret)
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value="./")
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)
        self.assertTrue(collect_graph("./output") is None)
        if os.getenv("NPU_COLLECT_PATH"):
            os.environ.pop("NPU_COLLECT_PATH")

    def test_graph_collect_success_from_work_path(self, mocker):
        os.environ["ASCEND_WORK_PATH"] = "./graph"
        ret = [('dir', ['subdir'], ["ge_onnx_test1.pbtxt", "ge_proto_test1.txt", "TF_GeOp_test1.pbtxt"]),   \
               ('dir/subdir', [], ["ge_onnx_test2.pbtxt", "ge_proto_test2.txt", "TF_GeOp_test2.pbtxt"])]
        mocker.patch("os.walk", return_value=ret)
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value="./")
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)
        self.assertTrue(collect_graph("./output") is None)
        if os.getenv("ASCEND_WORK_PATH"):
            os.environ.pop("ASCEND_WORK_PATH")
