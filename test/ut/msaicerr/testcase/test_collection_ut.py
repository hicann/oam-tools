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
import pytest

from conftest import (
    RES_PATH,
    CUR_TIME_STR,
    CommonAssert,
    AICORE_KERNEL_EXECUTE_FAILED,
    AICORE_KERNEL_EXECUTE_FAILED_2,
    GE_DUMP_EXECPTION_TO_FILE_L1,
    DUMP_EXECPTION_TO_FILE
)

from ms_interface.constant import Constant
from ms_interface import utils
from ms_interface.collection import Collection


class TestUtilsMethods(CommonAssert):

    @pytest.fixture(autouse=True)
    def change_test_dir(self, tmp_path):
        self.temp = tmp_path
        self.debug_info = tmp_path.joinpath("debug_info.txt")
        os.chdir(tmp_path)

    @pytest.mark.parametrize(
        "input_path, collect_level, expected",
        [
            ("ori_data/asys_output_20240912164014958", 0, True),
            ("ori_data/asys_output_20240912164014958", 1, True),
        ]
    )
    def test_collect_func(self, input_path, collect_level, expected):
        """
        测试collect 主函数
        """
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = RES_PATH.joinpath(input_path)
        collection = Collection(input_path, output_path)
        collection.collect_level = collect_level
        res = collection.collect()
        self.assertEqual(res, expected)

    def test_collect_check_host_and_device_kernel_name_failed(self, mocker):
        """
        测试检查host 和device kernel_name 失败
        """
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = RES_PATH.joinpath(
            "ori_data/asys_output_20240912164014958")
        collection = Collection(input_path, output_path)
        mocker.patch.object(
            collection, "check_host_and_device_kernel_name", return_value=False)
        res = collection.collect()
        self.assertEqual(res, False)

    def test_collect_check_dump_data_is_valid(self):
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = RES_PATH.joinpath(
            "ori_data/asys_output_20240912164014957")
        collection = Collection(input_path, output_path)
        res = collection.collect()
        self.assertEqual(res, False)
        self.assertIn(self.debug_info.read_text(
        ), "Cannot find dump file exception_info.42.1.1726159207469285 when analyzing")

    def test_collect_get_node_and_kernel_name_filed(self, mocker):
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = RES_PATH.joinpath(
            "ori_data/asys_output_20240912164014958")
        collection = Collection(input_path, output_path)
        mocker.patch.object(collection, "_get_node_and_kernel_name",
                            side_effect=utils.AicErrException('ERROR'))
        res = collection.collect()
        self.assertEqual(res, True)

    def test_collect_plog_file(self):
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = RES_PATH.joinpath(
            "ori_data/asys_output_20240912164014958")
        collection = Collection(input_path, output_path)
        collection.check_argument_valid()
        collection.collect_plog_file()
        res = list(output_path.rglob('*.log'))
        self.assertEqual(len(res), 2)

    def test_collect_plog_file_have_exception_dump(self):
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        input_path.mkdir(parents=True, exist_ok=True)
        input_path.joinpath('exception_dump.log').write_text(
            '[Dump][Exception]')
        input_path.joinpath('aic_info.txt').write_text('[AIC_INFO] dev_func:')
        input_path.joinpath('args_data.log').write_text(
            'exception info dump args data')
        collection = Collection(input_path, output_path)
        collection.check_argument_valid()
        collection.collect_plog_file()
        self.assertEqual(
            bool(list(output_path.rglob('exception_dump/args_data.log'))), True)
        self.assertEqual(
            bool(list(output_path.rglob('exception_dump/aic_info.txt'))), True)

    @pytest.mark.parametrize(
        "collect_level, plog, err_time_res, device_id_res, data_name_res",
        [
            (1, GE_DUMP_EXECPTION_TO_FILE_L1, "2024-12-06-15:17:06.252.046", "1",
             "GatherV2.GatherV21.1.1733469426252033"),  # collect_level is 1 GE LOG
            (0, DUMP_EXECPTION_TO_FILE, "2024-09-12-16:40:08.360.226", "0",
             "exception_info.42.1.1726159207469285"),  # collect_level is 0 DUMP LOG
            (1, DUMP_EXECPTION_TO_FILE, "2024-09-12-16:40:08.360.226",
             "0", "exception_info.42.1.1726159207469285")
            # collect_level is 1  DUMP LOG
        ]
    )
    def test_get_dump_data_info_collect_ge_level(self, collect_level, plog, err_time_res, device_id_res, data_name_res):
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        collection_plog_path = output_path.joinpath('collection/plog')
        collection_plog_path.mkdir(parents=True, exist_ok=True)
        collection = Collection(input_path, output_path)
        collection.collect_level = collect_level
        collection_plog_path.joinpath('ge_exception.log').write_text(plog)
        err_time, device_id, data_name = collection.get_dump_data_info()
        self.assertEqual(err_time, err_time_res)
        self.assertEqual(device_id, device_id_res)
        self.assertEqual(data_name, data_name_res)

    @pytest.mark.parametrize(
        "collect_level, reg_inquire_result",
        [
            (0, [('2026-01-27-16:19:25.335.417', '1', 'MoeReRouting.MoeReRouting.7.20260127161925313'), 
                 ('2026-01-27-16:19:24.987.629', '1', 'MoeReRouting.MoeReRouting.7.20260127161724963')]),
            (1, [('2026-01-27-16:19:25.335.417', '1', 'MoeReRouting.MoeReRouting.7.20260127161925313'), 
                 ('2026-01-27-16:19:24.987.629', '1', 'MoeReRouting.MoeReRouting.7.20260127161724963')])
        ]
    )
    def test_get_dump_file_with_order(self, mocker, collect_level, reg_inquire_result):
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        collection_plog_path = output_path.joinpath('collection/plog')
        collection_plog_path.mkdir(parents=True, exist_ok=True)
        collection = Collection(input_path, output_path)
        collection.collect_level = collect_level
        mocker.patch("ms_interface.utils.get_inquire_result", side_effect=[reg_inquire_result, []])
        err_time, device_id, data_name = collection.get_dump_data_info()
        self.assertEqual(err_time, "2026-01-27-16:19:24.987.629")
        self.assertEqual(device_id, "1")
        self.assertEqual(data_name, "MoeReRouting.MoeReRouting.7.20260127161724963")

    @pytest.mark.parametrize(
        "collect_level, reg_inquire_result",
        [
            (0, [None, None]),
            (1, [None, None])
        ]
    )
    def test_get_dump_file_none_reg_result(self, mocker, collect_level, reg_inquire_result):
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        collection_plog_path = output_path.joinpath('collection/plog')
        collection_plog_path.mkdir(parents=True, exist_ok=True)
        collection = Collection(input_path, output_path)
        collection.collect_level = collect_level
        mocker.patch("ms_interface.utils.get_inquire_result", side_effect=reg_inquire_result)
        with pytest.raises(utils.AicErrException) as e:
            collection.get_dump_data_info()
            self.assertEqual(str(e), str(
                Constant.MS_AICERR_INVALID_PATH_ERROR))

    def test_get_dump_data_info_collect_error_level_one(self):
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        collection_plog_path = output_path.joinpath('collection/plog')
        collection_plog_path.mkdir(parents=True, exist_ok=True)
        collection = Collection(input_path, output_path)
        collection.collect_level = 1
        collection_plog_path.joinpath('ge_exception.log').touch()
        with pytest.raises(utils.AicErrException) as e:
            collection.get_dump_data_info()
            self.assertEqual(str(e), str(
                Constant.MS_AICERR_INVALID_PATH_ERROR))

    def test_get_dump_data_info_collect_error_level_zero(self):
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        collection_plog_path = output_path.joinpath('collection/plog')
        collection_plog_path.mkdir(parents=True, exist_ok=True)
        collection = Collection(input_path, output_path)
        collection.collect_level = 0
        collection_plog_path.joinpath('dump_exception.log').touch()
        with pytest.raises(utils.AicErrException) as e:
            collection.get_dump_data_info()
            self.assertEqual(str(e), str(
                Constant.MS_AICERR_INVALID_PATH_ERROR))

    def test_check_dump_data_is_valid(self):
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = RES_PATH.joinpath(
            "ori_data/asys_output_20240912164014958")
        collection = Collection(input_path, output_path)
        with pytest.raises(utils.AicErrException) as e:
            collection.check_dump_data_is_valid(
                "2024-09-12-16:40:08.360.226", "exception_info.42.1.1")
            self.assertEqual(str(e), str(
                Constant.MS_AICERR_INVALID_DUMP_DATA_ERROR))

    def test_check_host_and_device_kernel_name(self):
        data_name = "GatherV2.GatherV21.1.1733469426252033"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}/dump")
        input_path.mkdir(parents=True, exist_ok=True)
        input_path.joinpath(data_name).touch()
        input_path.joinpath(f'{data_name}.o').touch()
        input_path.joinpath(f'{data_name}_host.o').touch()
        collection = Collection(input_path, output_path)
        res = collection.check_host_and_device_kernel_name(data_name)
        self.assertEqual(res, True)

    @pytest.mark.parametrize(
        "file_name",
        [
            "GatherV2.GatherV21.1.1733469426252033_host.o",   # not found device
            "GatherV2.GatherV21.1.1733469426252033.o"   # not found host
        ]
    )
    def test_check_host_and_device_kernel_name_not_device(self, file_name):
        data_name = "GatherV2.GatherV21.1.1733469426252033"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}/dump")
        input_path.mkdir(parents=True, exist_ok=True)
        input_path.joinpath(data_name).touch()
        input_path.joinpath(f'{file_name}').touch()
        collection = Collection(input_path, output_path)
        res = collection.check_host_and_device_kernel_name(data_name)
        self.assertEqual(res, True)
        self.assertIn(self.debug_info.read_text(),
                      "Cannot find host kernel or device kernel")

    def test_check_host_and_device_kernel_name_device_not_in_host(self):
        data_name = "GatherV2.GatherV21.1.1733469426252033"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}/dump")
        input_path.mkdir(parents=True, exist_ok=True)
        input_path.joinpath(data_name).touch()
        input_path.joinpath(f'GatherV3.GatherV31.1.12121212.o').touch()
        input_path.joinpath(f'{data_name}_host.o').touch()
        collection = Collection(input_path, output_path)
        res = collection.check_host_and_device_kernel_name(data_name)
        self.assertEqual(res, False)

    @pytest.mark.parametrize(
        "is_touch, res",
        [
            (True, True),   # data dump file is exist
            (False, False)  # data dump file is not exist
        ]
    )
    def test_collect_data_dump(self, is_touch, res):
        data_name = "GatherV2.GatherV21.1.1733469426252033"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}/dump")
        input_path.mkdir(parents=True, exist_ok=True)
        if is_touch:
            input_path.joinpath(data_name).touch()
        collection = Collection(input_path, output_path)
        collection.collect_data_dump(0, data_name)
        self.assertEqual(
            bool(list(output_path.rglob(f'collection/dump/{data_name}'))), res)

    def test_collect_data_dump_have_multiple(self):
        data_name = "GatherV2.GatherV21.1.1733469426252033"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        collection_plog_path = output_path.joinpath('collection/plog')
        collection_plog_path.mkdir(parents=True, exist_ok=True)
        collection_plog_path.joinpath("dump.log").write_text(
            f"extra-info/data-dump/0/{data_name}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        input_path.joinpath(
            f"extra-info/data-dump/0/{data_name}").mkdir(parents=True, exist_ok=True)
        input_path.joinpath(
            f"extra-info/data-dump/1/{data_name}").mkdir(parents=True, exist_ok=True)
        collection = Collection(input_path, output_path)
        collection.collect_data_dump(0, data_name)
        self.assertEqual(
            bool(list(output_path.rglob(f'collection/dump/{data_name}'))), True)

    def test_collect_get_node_and_kernel_name__l1(self):
        input_path = RES_PATH.joinpath("ori_data/collect/notffts")
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        collection_plog_path = output_path.joinpath('collection/plog')
        collection_plog_path.mkdir(parents=True, exist_ok=True)
        collection_plog_path.joinpath("plog.log").write_text(f"[INFO] GE(370,python3):2023-07-13-07:42:40.520.040 "
                                                             f"[exception_dumper.cc:274]1432 LogExceptionTvmOpInfo:"
                                                             f"[AIC_INFO] dev_func:te_gatherv2__1__kernel0")

        collection_plog_path.joinpath("plog1.log").write_text("[INFO] GE(370,python3):2023-07-13-07:42:40.517.823 "
                                                              "[exception_dumper.cc:255]1432 LogExceptionTvmOpInfo:"
                                                              "[AIC_INFO] node_name:GatherV2, node_type:GatherV2, "
                                                              "stream_id:2, task_id:6")
        collection = Collection(input_path, output_path)
        kernel_name, node_name = collection.get_node_and_kernel_name_l1()
        self.assertEqual(kernel_name, "te_gatherv2")
        self.assertEqual(node_name, "GatherV2")

    def test_collect_get_node_and_kernel_name_l1(self):
        input_path = RES_PATH.joinpath("ori_data/collect/notffts")
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        collection_plog_path = output_path.joinpath('collection/plog')
        collection_plog_path.mkdir(parents=True, exist_ok=True)
        collection_plog_path.joinpath("plog.log").write_text(f"[INFO] GE(370,python3):2023-07-13-07:42:40.520.040 "
                                                             f"[exception_dumper.cc:274]1432 LogExceptionTvmOpInfo:"
                                                             f"[AIC_INFO] dev_func:te_gatherv2_1_kernel0")

        collection_plog_path.joinpath("plog1.log").write_text("[INFO] GE(370,python3):2023-07-13-07:42:40.517.823 "
                                                              "[exception_dumper.cc:255]1432 LogExceptionTvmOpInfo:"
                                                              "[AIC_INFO] node_name:GatherV2, node_type:GatherV2, "
                                                              "stream_id:2, task_id:6")
        collection = Collection(input_path, output_path)
        kernel_name, node_name = collection.get_node_and_kernel_name_l1()
        self.assertEqual(kernel_name, "te_gatherv2_1_kernel0")
        self.assertEqual(node_name, "GatherV2")

    def test_collect_get_node_and_kernel_name_node_name_error_l1(self):
        input_path = RES_PATH.joinpath("ori_data/collect/notffts")
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        collection_plog_path = output_path.joinpath('collection/plog')
        collection_plog_path.mkdir(parents=True, exist_ok=True)
        collection_plog_path.joinpath("plog.log").write_text(f"[INFO] GE(370,python3):2023-07-13-07:42:40.520.040 "
                                                             f"[exception_dumper.cc:274]1432 LogExceptionTvmOpInfo:"
                                                             f"[AIC_INFO] dev_func:te_gatherv2_1_kernel0")

        collection_plog_path.joinpath("plog1.log").write_text("[INFO] GE(370,python3):2023-07-13-07:42:40.517.823 "
                                                              "[exception_dumper.cc:255]1432 LogExceptionTvmOpInfo:"
                                                              "[AIC_INFO] node_name_error:GatherV2, node_type:GatherV2, "
                                                              "stream_id:2, task_id:6")
        collection = Collection(input_path, output_path)
        with pytest.raises(utils.AicErrException) as e:
            collection.get_node_and_kernel_name_l1()
            self.assertEqual(str(e), str(
                Constant.MS_AICERR_INVALID_SLOG_DATA_ERROR))

    def test_collect_get_node_and_kernel_name_name_error_l1(self):
        input_path = RES_PATH.joinpath("ori_data/collect/notffts")
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        collection_plog_path = output_path.joinpath('collection/plog')
        collection_plog_path.mkdir(parents=True, exist_ok=True)
        collection_plog_path.joinpath("plog.log").write_text(f"[INFO] GE(370,python3):2023-07-13-07:42:40.520.040 "
                                                             f"[exception_dumper.cc:274]1432 LogExceptionTvmOpInfo:"
                                                             f"[AIC_INFO] dev_func_error:te_gatherv2_1_kernel0")
        collection = Collection(input_path, output_path)
        with pytest.raises(utils.AicErrException) as e:
            collection.get_node_and_kernel_name_l1()
            self.assertEqual(str(e), str(
                Constant.MS_AICERR_INVALID_SLOG_DATA_ERROR))

    @pytest.mark.parametrize(
        "plog_content, expected",
        [
            (AICORE_KERNEL_EXECUTE_FAILED,
             "FlashAttentionScore_5881aeec01e51adb01fb1db8be1c04f0_10000000000022420943_mix_aic"),
            (AICORE_KERNEL_EXECUTE_FAILED_2, "2_0_11_GatherV2")
        ]
    )
    def test_collect_get_kernel_name_l0_not_ffts_flag(self, plog_content, expected):
        input_path = RES_PATH.joinpath("ori_data/collect/notffts")
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        data_name = "GatherV2.GatherV21.1.1733469426252033"
        collection_plog_path = output_path.joinpath('collection/plog')
        collection_plog_path.mkdir(parents=True, exist_ok=True)
        collection_plog_path.joinpath("plog.log").write_text(plog_content)
        collection = Collection(input_path, output_path)
        collection.ffts_flag = False
        kernel_name, node_name = collection.get_kernel_name_l0(data_name)
        self.assertEqual(kernel_name, expected)
        self.assertEqual(node_name, "GatherV2.GatherV21.1.1733469426252033")

    def test_collect_get_kernel_name_l0_not_ffts_error_flag(self):
        input_path = RES_PATH.joinpath("ori_data/collect/notffts")
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        data_name = "GatherV2.GatherV21.1.1733469426252033"
        collection_plog_path = output_path.joinpath('collection/plog')
        collection_plog_path.mkdir(parents=True, exist_ok=True)
        collection_plog_path.joinpath("plog.log").write_text(f"[ERROR] RUNTIME(8953,None):2020-12-24-01:10:54.177.528 "
                                                             f"[../../../../../../runtime/feature/src/task.cc:544]8958 "
                                                             f"PrintErrorInfo:execute failed, "
                                                             f"fault kernel_name=-1_0_1_trans_TransData_0, ")
        collection = Collection(input_path, output_path)
        collection.ffts_flag = False
        with pytest.raises(utils.AicErrException) as e:
            collection.get_kernel_name_l0(data_name)
            self.assertEqual(str(e), str(
                Constant.MS_AICERR_INVALID_SLOG_DATA_ERROR))

    def test_collect_get_kernel_name_l0_ffts(self):
        input_path = RES_PATH.joinpath("ori_data/collect/notffts")
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        data_name = "GatherV2.GatherV21.1.1733469426252033"
        collection_plog_path = output_path.joinpath('collection/plog')
        collection_plog_path.mkdir(parents=True, exist_ok=True)
        collection_plog_path.joinpath("plog.log").write_text(f"[ERROR] RUNTIME(1592077,python3):2024-09-12-16:40:07."
                                                             f"468.642 [davinci_kernel_task.cc:1180]1592077 "
                                                             f"PrintErrorInfoForDavinciTask:[INIT]"
                                                             f"[DEFAULT]fftsplus task execute failed, device_id=0, "
                                                             f"stream_id=42, report_stream_id=42, "
                                                             f"task_id=1, flip_num=0, "
                                                             f"fault kernel_name=FlashAttentionScore_"
                                                             f"5881aeec01e51adb01fb1db8be1c04f0_"
                                                             f"10000000000022420943_mix_aic, "
                                                             f"fault kernel info "
                                                             f"ext=FlashAttentionScore_5881aeec01e51adb01fb1db8be1c04f"
                                                             f"0_10000000000022420943_mix_aic, program id=0, "
                                                             f"hash=1208019939949783628.")
        collection = Collection(input_path, output_path)
        collection.ffts_flag = True
        kernel_name, node_name = collection.get_kernel_name_l0(data_name)
        self.assertEqual(
            kernel_name, "FlashAttentionScore_5881aeec01e51adb01fb1db8be1c04f0_10000000000022420943_mix_aic")
        self.assertEqual(node_name, "GatherV2.GatherV21.1.1733469426252033")

    def test_collect_get_kernel_name_l0_ffts_error(self):
        input_path = RES_PATH.joinpath("ori_data/collect/notffts")
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        data_name = "GatherV2.GatherV21.1.1733469426252033"
        collection_plog_path = output_path.joinpath('collection/plog')
        collection_plog_path.mkdir(parents=True, exist_ok=True)
        collection_plog_path.joinpath("plog.log").write_text(f"[ERROR] RUNTIME(1592077,python3):2024-09-12-16:40:07."
                                                             f"468.642 [davinci_kernel_task.cc:1180]1592077 "
                                                             f"PrintErrorInfoForDavinciTask:[INIT]"
                                                             f"[DEFAULT]fftsplus task execute failed, device_id=0, "
                                                             f"stream_id=42, report_stream_id=42, "
                                                             f"task_id=1, flip_num=0, "
                                                             f"fault kernel_name1=FlashAttentionScore_"
                                                             f"5881aeec01e51adb01fb1db8be1c04f0_"
                                                             f"10000000000022420943_mix_aic, "
                                                             f"fault kernel info "
                                                             f"ext=FlashAttentionScore_5881aeec01e51adb01fb1db8be1c04f"
                                                             f"0_10000000000022420943_mix_aic, program id=0, "
                                                             f"hash=1208019939949783628.")
        collection = Collection(input_path, output_path)
        collection.ffts_flag = True
        with pytest.raises(utils.AicErrException) as e:
            collection.get_kernel_name_l0(data_name)
            self.assertEqual(str(e), str(
                Constant.MS_AICERR_INVALID_SLOG_DATA_ERROR))

    def test_collect_kernel_file(self):
        kernel_name1 = "FlashAttentionScore_5881aeec01e51adb01fb1db8be1c04f0_10000000000022420943_mix_aic"
        kernel_name = kernel_name1.replace("__kernel0", "").replace("_mix_aic", "") \
            .replace("_mix_aiv", "")
        input_path = self.temp.joinpath(f"input")
        input_path.mkdir(parents=True, exist_ok=True)
        input_path.joinpath('test.log').write_text(f"{input_path}/{kernel_name}.o, "
                                                   f"{input_path}/{kernel_name}.json, "
                                                   f"{input_path}/{kernel_name}.cce")
        input_path.joinpath(f"{kernel_name}.o").touch()
        input_path.joinpath(f"{kernel_name}.json").touch()
        input_path.joinpath(f"{kernel_name}.cce").touch()
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        collection = Collection(input_path, output_path)
        collection.collect_kernel_file(kernel_name1)
        self.assertEqual(
            bool(list(output_path.rglob(f'{kernel_name}.o'))), True)
        self.assertEqual(
            bool(list(output_path.rglob(f'{kernel_name}.json'))), True)
        self.assertEqual(
            bool(list(output_path.rglob(f'{kernel_name}.cce'))), True)

    def test_collect_kernel_file_no_json(self):
        kernel_name1 = "FlashAttentionScore_5881aeec01e51adb01fb1db8be1c04f0_10000000000022420943_mix_aic"
        kernel_name = kernel_name1.replace("__kernel0", "").replace("_mix_aic", "") \
            .replace("_mix_aiv", "")
        input_path = self.temp.joinpath(f"input")
        input_path.mkdir(parents=True, exist_ok=True)
        input_path.joinpath('test.log').write_text(f"{input_path}/{kernel_name}.o, "
                                                   f"{input_path}/{kernel_name}.cce")
        input_path.joinpath(f"{kernel_name}.o").touch()
        input_path.joinpath(f"{kernel_name}.cce").touch()
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        utils.ExceptionRootCause().cache_error = True
        collection = Collection(input_path, output_path)
        collection.collect_kernel_file(kernel_name1)
        self.assertEqual(
            bool(list(output_path.rglob(f'{kernel_name}.o'))), True)
        self.assertEqual(
            bool(list(output_path.rglob(f'{kernel_name}.cce'))), True)
        self.assertIn(utils.ExceptionRootCause().format_causes(),
                      "related file cannot be found in")

    def test_collect_kernel_file_error(self):
        kernel_name1 = "FlashAttentionScore_5881aeec01e51adb01fb1db8be1c04f0_10000000000022420943_mix_aic"
        input_path = self.temp.joinpath(f"input")
        input_path.mkdir(parents=True, exist_ok=True)
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        utils.ExceptionRootCause().cache_error = True
        collection = Collection(input_path, output_path)
        res = collection.collect_kernel_file(kernel_name1)
        self.assertEqual('', res)

    @pytest.mark.parametrize(
        "graph_name, expected",
        [
            ("ge_proto_1_Build.txt", True),
            ("gBuild.txt", False)
        ]
    )
    def test_collect_ge_graph(self, graph_name, expected):
        input_path = self.temp.joinpath(f"input")
        input_path.mkdir(parents=True, exist_ok=True)
        input_path.joinpath(graph_name).touch()
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        collection = Collection(input_path, output_path)
        collection.collect_ge_graph()
        self.assertEqual(bool(list(output_path.rglob(graph_name))), expected)
