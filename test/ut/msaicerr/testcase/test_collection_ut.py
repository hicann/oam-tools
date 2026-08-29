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
    GE_DUMP_EXCEPTION_TO_FILE_L1,
    DUMP_EXCEPTION_TO_FILE
)

from ms_interface.constant import Constant
from ms_interface import utils
from ms_interface.collection import Collection, is_sub_path


class TestUtilsMethods(CommonAssert):

    # fixture/setup_method 中赋值，此处声明以明确实例属性集合
    debug_info = None
    temp = None

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
            '[Dump][Exception]', encoding='utf-8')
        input_path.joinpath('aic_info.txt').write_text('[AIC_INFO] dev_func:', encoding='utf-8')
        input_path.joinpath('args_data.log').write_text(
            'exception info dump args data', encoding='utf-8')
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
            (1, GE_DUMP_EXCEPTION_TO_FILE_L1, "2024-12-06-15:17:06.252.046", "1",
             "GatherV2.GatherV21.1.1733469426252033"),  # collect_level is 1 GE LOG
            (0, DUMP_EXCEPTION_TO_FILE, "2024-09-12-16:40:08.360.226", "0",
             "exception_info.42.1.1726159207469285"),  # collect_level is 0 DUMP LOG
            (1, DUMP_EXCEPTION_TO_FILE, "2024-09-12-16:40:08.360.226",
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
        collection_plog_path.joinpath('ge_exception.log').write_text(plog, encoding='utf-8')
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
        self.assertIn(self.debug_info.read_text(encoding='utf-8'),
                      "Cannot find host kernel or device kernel")

    def test_check_host_and_device_kernel_name_device_not_in_host(self):
        data_name = "GatherV2.GatherV21.1.1733469426252033"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}/dump")
        input_path.mkdir(parents=True, exist_ok=True)
        input_path.joinpath(data_name).touch()
        input_path.joinpath('GatherV3.GatherV31.1.12121212.o').touch()
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
            f"extra-info/data-dump/0/{data_name}", encoding='utf-8')
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
        collection_plog_path.joinpath("plog.log").write_text("[INFO] GE(370,python3):2023-07-13-07:42:40.520.040 "
                                                             "[exception_dumper.cc:274]1432 LogExceptionTvmOpInfo:"
                                                             "[AIC_INFO] dev_func:te_gatherv2__1__kernel0")

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
        collection_plog_path.joinpath("plog.log").write_text("[INFO] GE(370,python3):2023-07-13-07:42:40.520.040 "
                                                             "[exception_dumper.cc:274]1432 LogExceptionTvmOpInfo:"
                                                             "[AIC_INFO] dev_func:te_gatherv2_1_kernel0")

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
        collection_plog_path.joinpath("plog.log").write_text("[INFO] GE(370,python3):2023-07-13-07:42:40.520.040 "
                                                             "[exception_dumper.cc:274]1432 LogExceptionTvmOpInfo:"
                                                             "[AIC_INFO] dev_func:te_gatherv2_1_kernel0")

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
        collection_plog_path.joinpath("plog.log").write_text("[INFO] GE(370,python3):2023-07-13-07:42:40.520.040 "
                                                             "[exception_dumper.cc:274]1432 LogExceptionTvmOpInfo:"
                                                             "[AIC_INFO] dev_func_error:te_gatherv2_1_kernel0")
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
        collection_plog_path.joinpath("plog.log").write_text(plog_content, encoding='utf-8')
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
        collection_plog_path.joinpath("plog.log").write_text("[ERROR] RUNTIME(8953,None):2020-12-24-01:10:54.177.528 "
                                                             "[../../../../../../runtime/feature/src/task.cc:544]8958 "
                                                             "PrintErrorInfo:execute failed, "
                                                             "fault kernel_name=-1_0_1_trans_TransData_0, ")
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
        collection_plog_path.joinpath("plog.log").write_text("[ERROR] RUNTIME(1592077,python3):2024-09-12-16:40:07."
                                                             "468.642 [davinci_kernel_task.cc:1180]1592077 "
                                                             "PrintErrorInfoForDavinciTask:[INIT]"
                                                             "[DEFAULT]fftsplus task execute failed, device_id=0, "
                                                             "stream_id=42, report_stream_id=42, "
                                                             "task_id=1, flip_num=0, "
                                                             "fault kernel_name=FlashAttentionScore_"
                                                             "5881aeec01e51adb01fb1db8be1c04f0_"
                                                             "10000000000022420943_mix_aic, "
                                                             "fault kernel info "
                                                             "ext=FlashAttentionScore_5881aeec01e51adb01fb1db8be1c04f"
                                                             "0_10000000000022420943_mix_aic, program id=0, "
                                                             "hash=1208019939949783628.")
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
        collection_plog_path.joinpath("plog.log").write_text("[ERROR] RUNTIME(1592077,python3):2024-09-12-16:40:07."
                                                             "468.642 [davinci_kernel_task.cc:1180]1592077 "
                                                             "PrintErrorInfoForDavinciTask:[INIT]"
                                                             "[DEFAULT]fftsplus task execute failed, device_id=0, "
                                                             "stream_id=42, report_stream_id=42, "
                                                             "task_id=1, flip_num=0, "
                                                             "fault kernel_name1=FlashAttentionScore_"
                                                             "5881aeec01e51adb01fb1db8be1c04f0_"
                                                             "10000000000022420943_mix_aic, "
                                                             "fault kernel info "
                                                             "ext=FlashAttentionScore_5881aeec01e51adb01fb1db8be1c04f"
                                                             "0_10000000000022420943_mix_aic, program id=0, "
                                                             "hash=1208019939949783628.")
        collection = Collection(input_path, output_path)
        collection.ffts_flag = True
        with pytest.raises(utils.AicErrException) as e:
            collection.get_kernel_name_l0(data_name)
            self.assertEqual(str(e), str(
                Constant.MS_AICERR_INVALID_SLOG_DATA_ERROR))

    def test_collect_get_kernel_name_l0_sk_scenario(self):
        # SK场景：标志性打印中的kernelName才是正确的算子名，优先返回
        input_path = RES_PATH.joinpath("ori_data/collect/notffts")
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        data_name = "GatherV2.GatherV21.1.1733469426252033"
        collection_plog_path = output_path.joinpath('collection/plog')
        collection_plog_path.mkdir(parents=True, exist_ok=True)
        collection_plog_path.joinpath("plog.log").write_text(
            "[Dump][Exception] Begin to dump callback exception. coreType=0, coreId=1, argAddr=0x1, "
            "argSize=64, binHandle=0x2, extraTensorNum=2, kernelName=Add_sk_kernel_900016000.", encoding='utf-8')
        collection = Collection(input_path, output_path)
        collection.ffts_flag = False
        kernel_name, node_name = collection.get_kernel_name_l0(data_name)
        self.assertEqual(kernel_name, "Add_sk_kernel_900016000")
        self.assertEqual(node_name, "GatherV2.GatherV21.1.1733469426252033")

    def test_collect_kernel_file(self):
        kernel_name1 = "FlashAttentionScore_5881aeec01e51adb01fb1db8be1c04f0_10000000000022420943_mix_aic"
        kernel_name = kernel_name1.replace("__kernel0", "").replace("_mix_aic", "") \
            .replace("_mix_aiv", "")
        input_path = self.temp.joinpath("input")
        input_path.mkdir(parents=True, exist_ok=True)
        input_path.joinpath('test.log').write_text(f"{input_path}/{kernel_name}.o, "
                                                   f"{input_path}/{kernel_name}.json, "
                                                   f"{input_path}/{kernel_name}.cce", encoding='utf-8')
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

    def test_kernel_file_same_prefix_is_not_sub_path(self, tmp_path):
        self.assertEqual(is_sub_path(str(tmp_path / "input_extra/kernel.o"), str(tmp_path / "input")), False)
        self.assertEqual(is_sub_path(str(tmp_path / "input/kernel.o"), str(tmp_path / "input")), True)

    def test_collect_kernel_file_sk_only_host_o(self):
        # SK场景：只生成host.o，没有device .o/.json，仅校验host.o存在，不报error
        kernel_name = "Add_sk_kernel_900016000"
        host_name = f"{kernel_name}_xxx_host.o"
        input_path = self.temp.joinpath("input_sk")
        input_path.mkdir(parents=True, exist_ok=True)
        input_path.joinpath('test.log').write_text(f"{input_path}/{host_name}", encoding='utf-8')
        input_path.joinpath(host_name).touch()
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        utils.ExceptionRootCause().cache_error = True
        collection = Collection(input_path, output_path)
        collection.is_sk = True
        collection.collect_kernel_file(kernel_name)
        self.assertEqual(
            bool(list(output_path.rglob(host_name))), True)
        self.assertNotIn("related file cannot be found in",
                         utils.ExceptionRootCause().format_causes())

    def test_check_host_and_device_kernel_name_sk(self):
        # SK场景：无device .o，跳过host/device一致性检查，直接返回True
        data_name = "GatherV2.GatherV21.1.1733469426252033"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}/dump")
        input_path.mkdir(parents=True, exist_ok=True)
        collection = Collection(input_path, output_path)
        collection.is_sk = True
        res = collection.check_host_and_device_kernel_name(data_name)
        self.assertEqual(res, True)

    def test_collect_kernel_file_no_json(self):
        kernel_name1 = "FlashAttentionScore_5881aeec01e51adb01fb1db8be1c04f0_10000000000022420943_mix_aic"
        kernel_name = kernel_name1.replace("__kernel0", "").replace("_mix_aic", "") \
            .replace("_mix_aiv", "")
        input_path = self.temp.joinpath("input")
        input_path.mkdir(parents=True, exist_ok=True)
        input_path.joinpath('test.log').write_text(f"{input_path}/{kernel_name}.o, "
                                                   f"{input_path}/{kernel_name}.cce", encoding='utf-8')
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
        input_path = self.temp.joinpath("input")
        input_path.mkdir(parents=True, exist_ok=True)
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        utils.ExceptionRootCause().cache_error = True
        collection = Collection(input_path, output_path)
        res = collection.collect_kernel_file(kernel_name1)
        self.assertEqual('', res)

    @pytest.mark.parametrize(
        "name_len, expected",
        [
            (Constant.MAX_FILE_NAME_LEN, False),      # 等于上限，不算超长
            (Constant.MAX_FILE_NAME_LEN + 1, True)    # 超过上限
        ]
    )
    def test_is_oversize_name(self, name_len, expected):
        """
        测试超长名字长度初判的边界
        """
        collection = Collection(self.temp, self.temp)
        self.assertEqual(getattr(collection, "_is_oversize_name")("a" * name_len), expected)

    def test_get_dump_mapping_csv_path(self):
        """
        测试按device_id定位data-dump目录下的mapping.csv
        """
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        for device_id in ("0", "1"):
            dump_path = input_path.joinpath(f"extra-info/data-dump/{device_id}")
            dump_path.mkdir(parents=True, exist_ok=True)
            dump_path.joinpath(Constant.MAPPING_CSV_FILE).write_text(f"1234,{device_id}\n", encoding='utf-8')
        collection = Collection(input_path, output_path)
        res = getattr(collection, "_get_dump_mapping_csv_path")("1")
        self.assertIn(res, "data-dump/1/mapping.csv")

    def test_get_dump_mapping_csv_path_device_id_prefix(self):
        """
        测试device_id为0时不会误命中data-dump/01/下的mapping.csv
        """
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        for device_id in ("01", "0"):
            dump_path = input_path.joinpath(f"extra-info/data-dump/{device_id}")
            dump_path.mkdir(parents=True, exist_ok=True)
            dump_path.joinpath(Constant.MAPPING_CSV_FILE).write_text(f"1234,{device_id}\n", encoding='utf-8')
        collection = Collection(input_path, output_path)
        res = getattr(collection, "_get_dump_mapping_csv_path")("0")
        self.assertIn(res, "data-dump/0/mapping.csv")
        self.assertNotIn(res, "data-dump/01/mapping.csv")

    def test_get_dump_mapping_csv_path_not_exist(self):
        """
        测试report_path下没有mapping.csv时返回空
        """
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        input_path.mkdir(parents=True, exist_ok=True)
        collection = Collection(input_path, output_path)
        self.assertEqual(getattr(collection, "_get_dump_mapping_csv_path")("0"), "")

    def test_get_dump_mapping_csv_path_other_device_only(self):
        """
        测试只有其它device的mapping.csv时返回空，不回退使用别的卡的映射表
        """
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        for device_id in ("1", "2"):
            dump_path = input_path.joinpath(f"extra-info/data-dump/{device_id}")
            dump_path.mkdir(parents=True, exist_ok=True)
            dump_path.joinpath(Constant.MAPPING_CSV_FILE).write_text(f"1234,{device_id}\n", encoding='utf-8')
        collection = Collection(input_path, output_path)
        self.assertEqual(getattr(collection, "_get_dump_mapping_csv_path")("0"), "")
        self.assertIn(self.debug_info.read_text(encoding='utf-8'),
                      f"{Constant.MAPPING_CSV_FILE} of device 0 cannot be found in")

    def test_collect_oversize_scene_other_device_mapping_only(self):
        """
        测试报错device无mapping.csv、其它device有时，不会误用其映射名收集到别的卡的dump。
        退化为按原始名查找，dump文件找不到时collect返回False
        """
        data_name = "a" * 250 + ".42.1.1726159207469285"
        rename = "1234567890123456"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        # 报错device为0，但只有device1落了随机名dump和mapping.csv
        dump_path = input_path.joinpath("extra-info/data-dump/1")
        dump_path.mkdir(parents=True, exist_ok=True)
        dump_path.joinpath(rename).touch()
        dump_path.joinpath(Constant.MAPPING_CSV_FILE).write_text(f"{rename},{data_name}\n", encoding='utf-8')
        input_path.joinpath("plog.txt").write_text(
            "[ERROR] IDEDD(1592077,python3):2024-09-12-16:40:08.360.226 [dump_args.cpp:807]"
            "[tid:1592077] [Dump][Exception] dump exception to file, file: "
            f"./new/extra-info/data-dump/0/{data_name}")
        collection = Collection(input_path, output_path)
        self.assertEqual(collection.collect(), False)
        self.assertEqual(collection.dump_file_rename, "")
        # device1的dump文件没有被误收集
        self.assertEqual(bool(list(output_path.rglob(f'collection/dump/{rename}'))), False)

    def test_resolve_dump_file_rename_normal_name(self, mocker):
        """
        测试普通名字走快路径，不触发find mapping.csv
        """
        collection = Collection(self.temp, self.temp)
        get_csv = mocker.patch.object(collection, "_get_dump_mapping_csv_path")
        self.assertEqual(getattr(collection, "_resolve_dump_file_rename")("0", "short_name"), "")
        self.assertEqual(get_csv.called, False)

    def test_resolve_dump_file_rename_oversize_matched(self, mocker):
        """
        测试超长名字命中映射，返回映射后的随机数字串
        """
        data_name = "a" * 250 + ".42.1.1726159207469285"
        collection = Collection(self.temp, self.temp)
        mocker.patch.object(collection, "_get_dump_mapping_csv_path", return_value="mapping.csv")
        mocker.patch.object(utils, "parse_name_mapping_csv",
                            return_value={data_name: "1234567890123456"})
        self.assertEqual(getattr(collection, "_resolve_dump_file_rename")("0", data_name), "1234567890123456")
        self.assertEqual(collection.dump_file_rename, "1234567890123456")

    def test_is_oversize_name_multi_byte(self):
        """
        测试多字节文件名按字节数判定，字符数未超但字节数已超
        """
        collection = Collection(self.temp, self.temp)
        name = "算" * 100   # 100个字符，UTF-8编码为300字节
        self.assertEqual(len(name) > Constant.MAX_FILE_NAME_LEN, False)
        self.assertEqual(getattr(collection, "_is_oversize_name")(name), True)

    def test_resolve_dump_file_rename_oversize_not_matched(self, mocker):
        """
        测试超长名字未命中映射，返回空串退化为原始名，并打印未命中原因
        """
        data_name = "a" * 250 + ".42.1.1726159207469285"
        collection = Collection(self.temp, self.temp)
        mocker.patch.object(collection, "_get_dump_mapping_csv_path", return_value="mapping.csv")
        mocker.patch.object(utils, "parse_name_mapping_csv", return_value={"other": "1234"})
        self.assertEqual(getattr(collection, "_resolve_dump_file_rename")("0", data_name), "")
        self.assertIn(self.debug_info.read_text(encoding='utf-8'), "it is not recorded in mapping.csv")

    def test_resolve_dump_file_rename_oversize_no_mapping_csv(self, mocker):
        """
        测试超长名字但mapping.csv缺失，日志可区分于"有mapping.csv但未命中"
        """
        data_name = "a" * 250 + ".42.1.1726159207469285"
        collection = Collection(self.temp, self.temp)
        mocker.patch.object(collection, "_get_dump_mapping_csv_path", return_value="")
        self.assertEqual(getattr(collection, "_resolve_dump_file_rename")("0", data_name), "")
        self.assertIn(self.debug_info.read_text(encoding='utf-8'),
                      f"but {Constant.MAPPING_CSV_FILE} cannot be found in")

    def test_check_dump_data_is_valid_with_rename(self):
        """
        测试超长场景下按映射名校验dump文件存在性
        """
        data_name = "a" * 250 + ".42.1.1726159207469285"
        rename = "1234567890123456"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        dump_path = input_path.joinpath("extra-info/data-dump/0")
        dump_path.mkdir(parents=True, exist_ok=True)
        dump_path.joinpath(rename).touch()
        collection = Collection(input_path, output_path)
        # 按映射名可以找到，不抛异常
        collection.check_dump_data_is_valid("2024-09-12-16:40:08.360.226", data_name, rename)
        # 不传rename时按原始名查找，找不到
        with pytest.raises(utils.AicErrException) as e:
            collection.check_dump_data_is_valid("2024-09-12-16:40:08.360.226", data_name)
            self.assertEqual(str(e), str(Constant.MS_AICERR_INVALID_DUMP_DATA_ERROR))

    def test_check_host_and_device_kernel_name_with_rename(self):
        """
        测试超长场景下用映射名定位dump文件所在目录，目录内.o校验逻辑不变
        """
        data_name = "a" * 250 + ".42.1.1726159207469285"
        rename = "1234567890123456"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}/dump")
        input_path.mkdir(parents=True, exist_ok=True)
        input_path.joinpath(rename).touch()
        input_path.joinpath("te_gatherv2.o").touch()
        input_path.joinpath("te_gatherv2_host.o").touch()
        collection = Collection(input_path, output_path)
        self.assertEqual(collection.check_host_and_device_kernel_name(data_name, rename), True)

    def test_collect_data_dump_with_rename(self):
        """
        测试超长场景下按映射名收集dump文件，并一并收集mapping.csv
        """
        data_name = "a" * 250 + ".42.1.1726159207469285"
        rename = "1234567890123456"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        dump_path = input_path.joinpath("extra-info/data-dump/0")
        dump_path.mkdir(parents=True, exist_ok=True)
        dump_path.joinpath(rename).touch()
        dump_path.joinpath(Constant.MAPPING_CSV_FILE).write_text(f"{rename},{data_name}\n", encoding='utf-8')
        collection = Collection(input_path, output_path)
        collection.collect_data_dump("0", data_name, rename)
        self.assertEqual(
            bool(list(output_path.rglob(f'collection/dump/{rename}'))), True)
        self.assertEqual(
            bool(list(output_path.rglob(f'collection/dump/{Constant.MAPPING_CSV_FILE}'))), True)

    def test_collect_data_dump_with_rename_multiple(self):
        """
        测试超长场景下找到多个dump文件时，回查plog的grep关键字用原始名
        """
        data_name = "a" * 250 + ".42.1.1726159207469285"
        rename = "1234567890123456"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        collection_plog_path = output_path.joinpath('collection/plog')
        collection_plog_path.mkdir(parents=True, exist_ok=True)
        collection_plog_path.joinpath("dump.log").write_text(
            f"extra-info/data-dump/0/{data_name}", encoding='utf-8')
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        for device_id in ("0", "1"):
            dump_path = input_path.joinpath(f"extra-info/data-dump/{device_id}")
            dump_path.mkdir(parents=True, exist_ok=True)
            dump_path.joinpath(rename).touch()
        collection = Collection(input_path, output_path)
        collection.collect_data_dump("0", data_name, rename)
        self.assertEqual(
            bool(list(output_path.rglob(f'collection/dump/{rename}'))), True)
        self.assertIn(self.debug_info.read_text(encoding='utf-8'), f"Find dump file {rename}.")

    def test_collect_data_dump_multiple_no_plog_match(self):
        """
        测试找到多个dump文件但plog中查不到data-dump记录时不抛IndexError
        """
        data_name = "GatherV2.GatherV21.1.1733469426252033"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        collection_plog_path = output_path.joinpath('collection/plog')
        collection_plog_path.mkdir(parents=True, exist_ok=True)
        collection_plog_path.joinpath("dump.log").write_text("no data-dump record here", encoding='utf-8')
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        for device_id in ("0", "1"):
            dump_path = input_path.joinpath(f"extra-info/data-dump/{device_id}")
            dump_path.mkdir(parents=True, exist_ok=True)
            dump_path.joinpath(data_name).touch()
        collection = Collection(input_path, output_path)
        res = collection.collect_data_dump("0", data_name)
        self.assertEqual(res, os.path.join(str(output_path), "collection", "dump"))
        self.assertEqual(
            bool(list(output_path.rglob(f'collection/dump/{data_name}'))), True)

    @pytest.mark.parametrize("target_device", ["0", "1"])
    def test_collect_data_dump_multiple_picks_target_device(self, target_device):
        """
        测试多个device目录下存在同名dump文件时，按报错device筛选。
        两个device各跑一次，结果必须各自命中，不能受目录遍历顺序影响
        """
        data_name = "GatherV2.GatherV21.1.1733469426252033"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}_{target_device}")
        collection_plog_path = output_path.joinpath('collection/plog')
        collection_plog_path.mkdir(parents=True, exist_ok=True)
        collection_plog_path.joinpath("dump.log").write_text(
            f"extra-info/data-dump/{target_device}/{data_name}", encoding='utf-8')
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        for device_id in ("0", "1"):
            dump_path = input_path.joinpath(f"extra-info/data-dump/{device_id}")
            dump_path.mkdir(parents=True, exist_ok=True)
            dump_path.joinpath(data_name).write_text(f"device{device_id}", encoding='utf-8')
        collection = Collection(input_path, output_path)
        collection.collect_data_dump(target_device, data_name)
        collected = list(output_path.rglob(f'collection/dump/{data_name}'))
        # 只收集报错device的那一份
        self.assertEqual(len(collected), 1)
        self.assertEqual(collected[0].read_text(encoding='utf-8'), f"device{target_device}")

    def test_collect_data_dump_multiple_device_id_prefix(self):
        """
        测试device_id为0时不会误命中data-dump/01/下的同名dump文件
        """
        data_name = "GatherV2.GatherV21.1.1733469426252033"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        for device_id in ("01", "0"):
            dump_path = input_path.joinpath(f"extra-info/data-dump/{device_id}")
            dump_path.mkdir(parents=True, exist_ok=True)
            dump_path.joinpath(data_name).write_text(f"device{device_id}", encoding='utf-8')
        collection = Collection(input_path, output_path)
        collection.collect_data_dump("0", data_name)
        collected = list(output_path.rglob(f'collection/dump/{data_name}'))
        self.assertEqual(len(collected), 1)
        self.assertEqual(collected[0].read_text(encoding='utf-8'), "device0")

    @pytest.mark.parametrize("target_device", ["0", "1"])
    def test_collect_data_dump_with_rename_multiple_device(self, target_device):
        """
        测试超长场景下多个device目录存在相同映射名时，只收集报错device的那一份。
        映射名在plog中不存在，无法靠回查plog区分，必须按文件所在目录筛选
        """
        data_name = "a" * 250 + ".42.1.1726159207469285"
        rename = "1234567890123456"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}_{target_device}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        for device_id in ("0", "1"):
            dump_path = input_path.joinpath(f"extra-info/data-dump/{device_id}")
            dump_path.mkdir(parents=True, exist_ok=True)
            dump_path.joinpath(rename).write_text(f"device{device_id}", encoding='utf-8')
        collection = Collection(input_path, output_path)
        collection.collect_data_dump(target_device, data_name, rename)
        collected = list(output_path.rglob(f'collection/dump/{rename}'))
        self.assertEqual(len(collected), 1)
        self.assertEqual(collected[0].read_text(encoding='utf-8'), f"device{target_device}")

    def test_collect_oversize_scene(self):
        """
        测试超长名字场景走完整collect流程：按映射名收集dump文件并带上mapping.csv
        """
        data_name = "a" * 250 + ".42.1.1726159207469285"
        rename = "1234567890123456"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        dump_path = input_path.joinpath("extra-info/data-dump/0")
        dump_path.mkdir(parents=True, exist_ok=True)
        dump_path.joinpath(rename).touch()
        dump_path.joinpath(Constant.MAPPING_CSV_FILE).write_text(f"{rename},{data_name}\n", encoding='utf-8')
        input_path.joinpath("plog.txt").write_text(
            "[ERROR] IDEDD(1592077,python3):2024-09-12-16:40:08.360.226 [dump_args.cpp:807]"
            "[tid:1592077] [Dump][Exception] dump exception to file, file: "
            f"./new/extra-info/data-dump/0/{data_name}")
        collection = Collection(input_path, output_path)
        res = collection.collect()
        self.assertEqual(res, True)
        self.assertEqual(collection.dump_file_rename, rename)
        self.assertEqual(
            bool(list(output_path.rglob(f'collection/dump/{rename}'))), True)
        self.assertEqual(
            bool(list(output_path.rglob(f'collection/dump/{Constant.MAPPING_CSV_FILE}'))), True)

    def test_collect_oversize_scene_mapping_csv_found_once(self, mocker):
        """
        测试超长名字场景下mapping.csv只解析一次，collect_data_dump复用缓存不再重复find
        """
        data_name = "a" * 250 + ".42.1.1726159207469285"
        rename = "1234567890123456"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        dump_path = input_path.joinpath("extra-info/data-dump/0")
        dump_path.mkdir(parents=True, exist_ok=True)
        dump_path.joinpath(rename).touch()
        dump_path.joinpath(Constant.MAPPING_CSV_FILE).write_text(f"{rename},{data_name}\n", encoding='utf-8')
        input_path.joinpath("plog.txt").write_text(
            "[ERROR] IDEDD(1592077,python3):2024-09-12-16:40:08.360.226 [dump_args.cpp:807]"
            "[tid:1592077] [Dump][Exception] dump exception to file, file: "
            f"./new/extra-info/data-dump/0/{data_name}")
        collection = Collection(input_path, output_path)
        get_csv = mocker.spy(collection, "_get_dump_mapping_csv_path")
        self.assertEqual(collection.collect(), True)
        self.assertEqual(get_csv.call_count, 1)
        self.assertEqual(
            bool(list(output_path.rglob(f'collection/dump/{Constant.MAPPING_CSV_FILE}'))), True)

    def test_collect_data_dump_with_rename_no_cache(self, mocker):
        """
        测试直接调用collect_data_dump（未经_resolve_dump_file_rename）时缓存为空，
        仍会按需解析mapping.csv
        """
        data_name = "a" * 250 + ".42.1.1726159207469285"
        rename = "1234567890123456"
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        input_path = self.temp.joinpath(f"asys_output_{CUR_TIME_STR}")
        dump_path = input_path.joinpath("extra-info/data-dump/0")
        dump_path.mkdir(parents=True, exist_ok=True)
        dump_path.joinpath(rename).touch()
        dump_path.joinpath(Constant.MAPPING_CSV_FILE).write_text(f"{rename},{data_name}\n", encoding='utf-8')
        collection = Collection(input_path, output_path)
        self.assertEqual(getattr(collection, "_mapping_csv_path"), "")
        get_csv = mocker.spy(collection, "_get_dump_mapping_csv_path")
        collection.collect_data_dump("0", data_name, rename)
        self.assertEqual(get_csv.call_count, 1)
        self.assertEqual(
            bool(list(output_path.rglob(f'collection/dump/{Constant.MAPPING_CSV_FILE}'))), True)

    @pytest.mark.parametrize(
        "graph_name, expected",
        [
            ("ge_proto_1_Build.txt", True),
            ("gBuild.txt", False)
        ]
    )
    def test_collect_ge_graph(self, graph_name, expected):
        input_path = self.temp.joinpath("input")
        input_path.mkdir(parents=True, exist_ok=True)
        input_path.joinpath(graph_name).touch()
        output_path = self.temp.joinpath(f"info_{CUR_TIME_STR}")
        collection = Collection(input_path, output_path)
        collection.collect_ge_graph()
        self.assertEqual(bool(list(output_path.rglob(graph_name))), expected)
