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
import shutil

from testcase.conftest import ASYS_SRC_PATH, ut_root_path
sys.path.insert(0, ASYS_SRC_PATH)

from common import consts
from collect.ops import collect_ops
from testcase.conftest import AssertTest, test_case_tmp
from params import ParamDict


def setup_module():
    print("TestOpsCollect ut test start.")


def teardown_module():
    print("TestOpsCollect ut test finsh.")


class TestOpsCollect(AssertTest):

    def setup_method(self):
        for env in ["ASCEND_PROCESS_LOG_PATH", "ASCEND_CACHE_PATH", "ASCEND_WORK_PATH", "ASCEND_CUSTOM_OPP_PATH",
                    "ASCEND_OPP_PATH"]:
            if os.getenv(env):
                os.environ.pop(env)

    def teardown_method(self):
        pass

    def test_ops_collect_success(self, mocker):
        ret = [('dir', ['subdir'], ["test1.o", "test1.json"]),
               ('dir/subdir', [], ["test2.o", "test2.json"])]
        mocker.patch("os.walk", return_value=ret)
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)

        # collect task
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value="./")
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        self.assertTrue(collect_ops("./output") is None)

        # launch task
        mocker.patch("params.ParamDict.get_command", return_value=consts.launch_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value="bash ./test.bash")
        mocker.patch("params.ParamDict.get_ini", return_value="1")
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        ParamDict().asys_output_timestamp_dir = ut_root_path
        self.assertTrue(collect_ops("./output") is None)

    def test_ops_collect_switch_off(self, mocker):
        mocker.patch("params.ParamDict.get_command", return_value=consts.launch_cmd)
        mocker.patch("params.ParamDict.get_ini", return_value="0")
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        self.assertTrue(collect_ops("./output") is None)

    def test_ops_collect_get_source_dir_failed(self, mocker):
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value=False)
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        self.assertTrue(collect_ops("./output") is None)

    def test_ops_collect_copy_failed(self, mocker):
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value=ut_root_path)
        ret = [('dir', ['subdir'], ["test1.o", "test1.json"]),
               ('dir/subdir', [], ["test2.o", "test2.json"])]
        mocker.patch("os.walk", return_value=ret)
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=False)
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        self.assertTrue(collect_ops("./output") is None)

    def test_ops_collect_get_debug_kernel(self, mocker):
        mocker.patch("params.ParamDict.get_command", return_value=consts.collect_cmd)
        mocker.patch("params.ParamDict.get_arg", return_value=ut_root_path)
        mocker.patch("common.FileOperate.check_access", return_value=True)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("common.FileOperate.list_dir", return_value=True)
        mocker.patch("common.FileOperate.copy_dir", return_value=True)
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        os.environ["ASCEND_OPP_PATH"] = ut_root_path
        self.assertTrue(collect_ops("./output") is None)
        
    def test_ops_launch_get_debug_kernel(self, mocker):
        mocker.patch("params.ParamDict.get_command", return_value=consts.launch_cmd)
        mocker.patch("params.ParamDict.get_ini", return_value="0")
        mocker.patch("common.FileOperate.check_access", return_value=True)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("common.FileOperate.list_dir", return_value=True)
        mocker.patch("common.FileOperate.copy_dir", return_value=True)
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        os.environ["ASCEND_OPP_PATH"] = ut_root_path
        self.assertTrue(collect_ops("./output") is None)

    def test_ops_launch_get_debug_kernel_check_path(self, mocker):
        mocker.patch("params.ParamDict.get_command", return_value=consts.launch_cmd)
        mocker.patch("params.ParamDict.get_ini", return_value="1")
        mocker.patch("common.FileOperate.collect_dir", return_value=True)
        mocker.patch("common.FileOperate.check_access", return_value=True)
        mocker.patch("common.FileOperate.check_dir", return_value=True)
        mocker.patch("common.FileOperate.list_dir", return_value=True)
        mocker.patch("common.FileOperate.copy_dir", return_value=True)
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        os.environ["ASCEND_OPP_PATH"] = ut_root_path
        self.assertTrue(collect_ops(ut_root_path+"/debug_kernel") is None)

    def test_ops_collect_opp_config(self, mocker):
        from collect.ops.ops_collect import collect_opp_config

        mocker.patch("collect.ops.ops_collect.collect_file", return_value=True)
        mocker.patch("collect.ops.ops_collect.collect_debug_kernel", return_value=True)
        mocker.patch("collect.ops.ops_collect.collect_custom_opp_config", return_value=True)
        mocker.patch("common.FileOperate.copy_file_to_dir", return_value=True)
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        os.environ["ASCEND_OPP_PATH"] = ut_root_path + "/data/"
        self.assertTrue(collect_opp_config(ut_root_path + "/tempdir/"))
        self.assertTrue(os.path.join(ut_root_path, "tempdir", "dfx", "ops", "vendor_config"))
        shutil.rmtree(ut_root_path + "/tempdir/")

    def test_ops_collect_custom_opp_config(self, mocker):
        from collect.ops.ops_collect import collect_custom_opp_config

        mocker.patch("collect.ops.ops_collect.collect_file", return_value=True)
        mocker.patch("collect.ops.ops_collect.collect_debug_kernel", return_value=True)
        mocker.patch("collect.ops.ops_collect.collect_opp_config", return_value=True)
        mocker.patch("common.FileOperate.copy_file_to_dir", return_value=True)
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=True)
        os.environ["ASCEND_CUSTOM_OPP_PATH"] = ut_root_path + "/data/vendors/customize_1/"
        self.assertTrue(collect_custom_opp_config(ut_root_path + "/tempdir/"))
        self.assertTrue(os.path.join(ut_root_path, "tempdir", "dfx", "ops", "custom_config"))
        shutil.rmtree(ut_root_path + "/tempdir/")

    def test_ops_collect_get_fault_kernel_name(self, mocker):
        from collect.ops.ops_collect import get_fault_kernel_name
        self.assertTrue(get_fault_kernel_name("./") is None)

        mocker.patch("common.FileOperate.check_dir", return_value=True)
        self.assertTrue(get_fault_kernel_name("./") is None)

        class CmdRet:
            def readlines(self):
                return []
            def close(self):
                return []
        mocker.patch("os.popen", return_value=CmdRet())
        self.assertTrue(get_fault_kernel_name("./") is None)

        class CmdRet:
            def readlines(self):
                return [
                    "Aicore kernel execute failed, device_id=0, stream_id=5, report_stream_id=5, task_id=5, flip_num=0, "
                    "fault kernel_name=GatherV2_2a3c199f98e42f598a5d7122750ff150_high_precision_900016000, program id=1"
                ]
            def close(self):
                return []
        mocker.patch("os.popen", return_value=CmdRet())
        self.assertTrue(get_fault_kernel_name("./") == "GatherV2_2a3c199f98e42f598a5d7122750ff150_high_precision_900016000")

        class CmdRet:
            def readlines(self):
                return [
                    "Aicore kernel execute failed, device_id=0, stream_id=5, report_stream_id=5, task_id=5, flip_num=0, "
                    "fault kernel_name=GatherV2_2a3c199f98e42f598a5d7122750ff150_high_precision_900016000_mix_aic, program id=1"
                ]
            def close(self):
                return []
        mocker.patch("os.popen", return_value=CmdRet())
        self.assertTrue(get_fault_kernel_name("./") == "GatherV2_2a3c199f98e42f598a5d7122750ff150_high_precision_900016000")

        class CmdRet:
            def readlines(self):
                return [
                    "Aicore kernel execute failed, device_id=0, stream_id=5, report_stream_id=6, task_id=0, flip_num=0, "
                    "fault kernel_name=00_11_2_GatherV2, fault kernel info ext=te_gatherv2_097ab5be870f5abfbee16f82ff397"
                    "32eccfee1dbe76f3bcd6ef32b08996dd346_1__kernel0, program id=1"
                ]
            def close(self):
                return []
        mocker.patch("os.popen", return_value=CmdRet())
        self.assertTrue(get_fault_kernel_name("./") == "te_gatherv2_097ab5be870f5abfbee16f82ff39732eccfee1dbe76f3bcd6ef32b08996dd346_1__kernel0")

    def test_ops_collect_get_fault_kernel_name_files(self, mocker):
        from collect.ops.ops_collect import get_fault_kernel_name_files

        kernel_name = "te_gatherv2_097ab5be870f5abfbee16f82ff39732eccfee1dbe76f3bcd6ef32b08996dd346_1__kernel0"
        collect_path = ut_root_path + "/data/"

        self.assertTrue(get_fault_kernel_name_files(collect_path, kernel_name) == [ut_root_path + "/data/ops/kernel/GatherV2_2a3c199f98e42f598a5d7122750ff150_high_precision.json"])

    def test_ops_collect_collect_fault_kernel_name_files(self, mocker):
        from collect.ops.ops_collect import collect_ops_files_env_var

        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)
        mocker.patch("collect.ops.ops_collect.get_fault_kernel_name_files", return_value=["./"])
        self.assertTrue(collect_ops_files_env_var("./", "./"))

    def test_ops_collect_collect_ops_from_exception_dump(self, mocker):
        from collect.ops.ops_collect import collect_ops_from_dump

        self.assertTrue(collect_ops_from_dump("./") is False)

        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)
        self.assertTrue(collect_ops_from_dump(ut_root_path + "/data/output") is True)

    def test_collect_l0_exception_dump_cache_path(self, mocker):
        from collect.ops.ops_collect import collect_ops_files_env_var

        mocker.patch("collect.ops.ops_collect.get_fault_kernel_name",
                     return_value="te_gatherv2_097ab5be870f5abfbee16f82ff39732eccfee1dbe76f3bcd6ef32b08996dd346_1__kernel0")
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=False)
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)
        os.environ["ASCEND_PROCESS_LOG_PATH"] = ut_root_path + "/data/asys_test_dir/ascend/log/"
        os.environ["ASCEND_CACHE_PATH"] = ut_root_path + "/data/ops/"
        self.assertTrue(collect_ops_files_env_var(test_case_tmp, "./"))

    def test_collect_l0_exception_dump_work_path(self, mocker):
        from collect.ops.ops_collect import collect_ops_files_env_var

        mocker.patch("collect.ops.ops_collect.get_fault_kernel_name",
                     return_value="te_gatherv2_097ab5be870f5abfbee16f82ff39732eccfee1dbe76f3bcd6ef32b08996dd346_1__kernel0")
        mocker.patch("common.FileOperate.collect_file_to_dir", return_value=True)
        mocker.patch("collect.ops.ops_collect.collect_ops_from_dump", return_value=False)
        os.environ["ASCEND_WORK_PATH"] = ut_root_path + "/data/"
        os.environ["ASCEND_PROCESS_LOG_PATH"] = ut_root_path + "/data/asys_test_dir/ascend/log/"
        self.assertTrue(collect_ops_files_env_var(test_case_tmp, "./"))
