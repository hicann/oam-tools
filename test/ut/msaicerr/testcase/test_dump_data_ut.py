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

import json
import struct

from conftest import MSAICERR_PATH, RES_PATH, CommonAssert
import os
import sys
from argparse import Namespace
import pytest
import numpy as np
from unittest.mock import Mock

sys.path.append(MSAICERR_PATH)
from ms_interface import utils
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.dump_data_parser import DumpDataParser, BigDumpDataParser


dump_file = "exception_info.2.1.20250609144925349"


def create_dump_file(file_name, header_length, body_length):
    with open(file_name, 'wb') as f:
        f.write(struct.pack('Q', header_length))
        f.write(bytearray(range(header_length)))
        for i in range(body_length//256 + 1):
            f.write(bytearray(range(256)))


class Selflib():
    def ParseDumpProtoToJson(self, data_ptr, data_size, path_ptr):
        return 0


class Selfliberr():
    def ParseDumpProtoToJson(self, data_ptr, data_size, path_ptr):
        return 1


class TestUtilsMethods(CommonAssert):
    @pytest.fixture(autouse=True)
    def change_test_dir(self, tmp_path):
        self.temp = tmp_path
        self.debug_info = tmp_path.joinpath("debug_info.txt")
        os.chdir(tmp_path)

    @staticmethod
    def common_mock(mocker, dump_json):
        # mock通用方法
        mocker.patch('ctypes.CDLL', return_value=Selflib())
        with open(f"{dump_file}.json", "w") as f:
            f.write(json.dumps(dump_json))

    def test_big_dump_parser(self, tmp_path, mocker):
        dump_json = {'version': '2.0', 'dump_time': '1749451765349986', 'output': [{'data_type': 0, 'format': 0, 'shape': {'dim': ['2', '2048']}, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'dim_range': [], 'offset': '3'}], 'input': [{'data_type': 0, 'format': 0, 'shape': {'dim': ['10240', '2048']}, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 0, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['2']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 1, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['1']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 2, 'input_type': 2}, {'data_type': 0, 'format': 0, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 5, 'input_type': 7}], 'buffer': [], 'op_name': '', 'attr': [], 'space': [{'type': 0, 'data': '', 'size': '10'}], 'dfx_message': '[AIC_INFO] args(0 to 20) after execute:0x12c200000000, 0x12d340000000, 0x12c1c0000518, 0x12d340000200, 0x12d340004400, 0x12c1c0000438, 0x12c100011000, 0x285a, 0x2, 0x1, 0, 0x2000, 0x8, 0x1, 0x1, 0x2800, 0x2, 0x800, 0x1, 0x1, \n[AIC_INFO] args(20 to 39) after execute:0x2, 0x1, 0x1, 0x1, 0x1, 0x800, 0x1, 0x1, 0x2, 0x1, 0x2, 0xa5a5a5a500000000, 0, 0, 0, 0, 0, 0, 0, \n[Dump][Exception] begin to load normal tensor, index:0\n[Dump][Exception] exception info dump args data, addr:0x12c200000000; size:83886080 bytes\n[Dump][Exception] end to load normal tensor, index:0\n[Dump][Exception] begin to load normal tensor, index:1\n[Dump][Exception] exception info dump args data, addr:0x12d340000000; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:1\n[Dump][Exception] begin to load normal tensor, index:2\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000518; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:2\n[Dump][Exception] begin to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340000200; size:16384 bytes\n[Dump][Exception] end to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340004400; size:76832 bytes\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000438; size:200 bytes\n'}
        self.common_mock(mocker, dump_json)
        create_dump_file(dump_file, 10, 200)
        big_dump_parser = BigDumpDataParser(dump_file)
        dump_json_data = big_dump_parser.parse()
        self.assertEqual(dump_json_data.get('output')[0].get('data_type'), 0)
        self.assertEqual(dump_json_data.get('input')[0].get('shape').get('dim'), ['10240', '2048'])
        self.assertEqual(dump_json_data.get('input')[0].get('size'), '10')
        self.assertEqual(dump_json_data.get('input')[0].get('input_type'), 2)
        self.assertIn(dump_json_data.get('dfx_message'), "[AIC_INFO] args(0 to 20) after")

    def test_big_dump_parser_error(self, tmp_path, mocker, capsys):
        big_dump_parser = BigDumpDataParser(dump_file)
        mocker.patch.object(big_dump_parser, 'check_argument_valid')
        mocker.patch.object(big_dump_parser, '_read_header_length')
        mocker.patch.object(big_dump_parser, '_parse_binary_to_json_data')
        try:
            big_dump_parser.parse()
        except Exception as e:
            self.assertEqual(str(e), "5")
            self.assertIn(capsys.readouterr().out, "No such file or directory: 'exception_info.2.1.20250609144925349'")

    def test_check_argument_valid_file_size_lt_uint64_size_err(self, mocker):
        big_dump_parser = BigDumpDataParser(dump_file)
        with open(dump_file, 'wb') as f:
            f.write(struct.pack('Q', 10))
        try:
            big_dump_parser.check_argument_valid()
        except Exception as e:
            self.assertEqual(str(e), "4")

    def test_check_argument_valid_file_get_size_failed(self, mocker):
        big_dump_parser = BigDumpDataParser(dump_file)
        mocker.patch('os.path.getsize', effect=IOError("test"))
        try:
            big_dump_parser.check_argument_valid()
        except Exception as e:
            self.assertEqual(str(e), "2")

    def test_parse_dump_to_json_load_so_failed(self, mocker):
        big_dump_parser = BigDumpDataParser(dump_file)
        create_dump_file(dump_file, 10, 200)
        try:
            big_dump_parser._parse_dump_to_json()
        except Exception as e:
            self.assertEqual(str(e), "3")

    def test_parse_dump_to_json_load_func_failed(self, mocker):
        big_dump_parser = BigDumpDataParser(dump_file)
        mocker.patch('ctypes.CDLL', return_value=Selfliberr())
        create_dump_file(dump_file, 10, 200)
        try:
            big_dump_parser._parse_dump_to_json()
        except Exception as e:
            self.assertEqual(str(e), "3")

    def test_parse_binary_to_json_data_use_gt_file_size(self, tmp_path, mocker):
        dump_json = {'version': '2.0', 'dump_time': '1749451765349986', 'output': [{'data_type': 0, 'format': 0, 'shape': {'dim': ['2', '2048']}, 'data': '', 'size': '10000', 'sub_format': 0, 'address': '0', 'dim_range': [], 'offset': '3'}], 'input': [{'data_type': 0, 'format': 0, 'shape': {'dim': ['10240', '2048']}, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 0, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['2']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 1, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['1']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 2, 'input_type': 2}, {'data_type': 0, 'format': 0, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 5, 'input_type': 7}], 'buffer': [], 'op_name': '', 'attr': [], 'space': [{'type': 0, 'data': '', 'size': '10'}], 'dfx_message': '[AIC_INFO] args(0 to 20) after execute:0x12c200000000, 0x12d340000000, 0x12c1c0000518, 0x12d340000200, 0x12d340004400, 0x12c1c0000438, 0x12c100011000, 0x285a, 0x2, 0x1, 0, 0x2000, 0x8, 0x1, 0x1, 0x2800, 0x2, 0x800, 0x1, 0x1, \n[AIC_INFO] args(20 to 39) after execute:0x2, 0x1, 0x1, 0x1, 0x1, 0x800, 0x1, 0x1, 0x2, 0x1, 0x2, 0xa5a5a5a500000000, 0, 0, 0, 0, 0, 0, 0, \n[Dump][Exception] begin to load normal tensor, index:0\n[Dump][Exception] exception info dump args data, addr:0x12c200000000; size:83886080 bytes\n[Dump][Exception] end to load normal tensor, index:0\n[Dump][Exception] begin to load normal tensor, index:1\n[Dump][Exception] exception info dump args data, addr:0x12d340000000; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:1\n[Dump][Exception] begin to load normal tensor, index:2\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000518; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:2\n[Dump][Exception] begin to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340000200; size:16384 bytes\n[Dump][Exception] end to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340004400; size:76832 bytes\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000438; size:200 bytes\n'}
        self.common_mock(mocker, dump_json)
        create_dump_file(dump_file, 10, 200)
        big_dump_parser = BigDumpDataParser(dump_file)
        try:
            big_dump_parser.parse()
        except Exception as e:
            self.assertEqual(str(e), "5")

    def test_dump_data_parser(self, mocker):
        dump_json = {'version': '2.0', 'dump_time': '1749451765349986', 'output': [{'data_type': 0, 'format': 0, 'shape': {'dim': ['2', '2048']}, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'dim_range': [], 'offset': '3'}], 'input': [{'data_type': 0, 'format': 0, 'shape': {'dim': ['10240', '2048']}, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 0, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['2']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 1, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['1']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 2, 'input_type': 2}, {'data_type': 0, 'format': 0, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 5, 'input_type': 7}], 'buffer': [], 'op_name': '', 'attr': [], 'space': [{'type': 0, 'data': '', 'size': '10'}], 'dfx_message': '[AIC_INFO] args(0 to 20) after execute:0x12c200000000, 0x12d340000000, 0x12c1c0000518, 0x12d340000200, 0x12d340004400, 0x12c1c0000438, 0x12c100011000, 0x285a, 0x2, 0x1, 0, 0x2000, 0x8, 0x1, 0x1, 0x2800, 0x2, 0x800, 0x1, 0x1, \n[AIC_INFO] args(20 to 39) after execute:0x2, 0x1, 0x1, 0x1, 0x1, 0x800, 0x1, 0x1, 0x2, 0x1, 0x2, 0xa5a5a5a500000000, 0, 0, 0, 0, 0, 0, 0, \n[Dump][Exception] begin to load normal tensor, index:0\n[Dump][Exception] exception info dump args data, addr:0x12c200000000; size:83886080 bytes\n[Dump][Exception] end to load normal tensor, index:0\n[Dump][Exception] begin to load normal tensor, index:1\n[Dump][Exception] exception info dump args data, addr:0x12d340000000; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:1\n[Dump][Exception] begin to load normal tensor, index:2\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000518; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:2\n[Dump][Exception] begin to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340000200; size:16384 bytes\n[Dump][Exception] end to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340004400; size:76832 bytes\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000438; size:200 bytes\n'}
        self.common_mock(mocker, dump_json)
        create_dump_file(dump_file, 10, 200)
        info = AicErrorInfo()
        info.json_file = str(RES_PATH.joinpath("ori_data/collect_json/test.json")) # 指定json文件路径
        dump_data_parser = DumpDataParser(dump_file, info)
        dump_data_parser.parse()
        self.assertIn(info.dump_info, "exception_info.2.1.20250609144925349.input.0.float32.bin")
        self.assertIn(info.dump_info, "shape: (10240, 2048) size: 10 dtype: float32")

        self.assertIn(info.dump_info, "exception_info.2.1.20250609144925349.workspace.0.int8.npy")
        self.assertIn(info.dump_info, "shape: () size: 10 dtype: int8")

        self.assertEqual(dump_data_parser.get_input_data(), [])
        self.assertEqual(dump_data_parser.get_output_data(), [])
        self.assertIn(dump_data_parser.get_bin_data(), "exception_info.2.1.20250609144925349.input.1.int64.bin")
        self.assertIn(dump_data_parser.get_workspace_data(), 'exception_info.2.1.20250609144925349.workspace.0.int8.npy')
        self.assertIn(dump_data_parser.get_dfx_message(), "[AIC_INFO] args(20 to 39)")

    def test_dump_data_parser_other_file(self, mocker):
        info = AicErrorInfo()
        info.json_file = str(RES_PATH.joinpath("ori_data/collect_json/test.json"))  # 指定json文件路径
        with open('text.bin', 'wb') as f:
            f.write(struct.pack('Q', 10))
        dump_data_parser = DumpDataParser('test.bin', info)
        mocker.patch.object(dump_data_parser, 'parse_dump_data', return_value='')
        dump_data_parser.parse()
        self.assertEqual(info.dump_file, [])

    def test_dump_data_parser_other_path(self, tmp_path, mocker):
        info = AicErrorInfo()
        info.json_file = str(RES_PATH.joinpath("ori_data/collect_json/test.json"))  # 指定json文件路径
        dump_data_parser = DumpDataParser(tmp_path, info)
        mocker.patch.object(dump_data_parser, 'parse_dump_data', return_value='')
        dump_data_parser.parse()
        self.assertEqual(info.dump_file, [])

    def test_parse_dump_data_error(self, mocker, capsys):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        mocker.patch.object(BigDumpDataParser, "parse", return_value={})
        mocker.patch.object(dump_data_parser, '_get_json_dtypes', reeturn_value={})
        mocker.patch.object(dump_data_parser, "_save_data_to_bin_file", side_effect=Exception("test"))
        dump_data_parser.parse_dump_data(dump_file)
        self.assertIn(capsys.readouterr().out, "Error Detail: test")

    def test_summary_tensor_without_dtype_bfloat16(self):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = dump_data_parser._summary_tensor_without_dtype('text.bin', 'bfloat16')
        self.assertIn(res, "Can not read with dtype bfloat16")

    def test_check_tensor_data_type_error(self):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = dump_data_parser._check_tensor_data('input', 1, np.array([1, 2]), 'bfloat112')
        self.assertIn(res, 'Can not read with dtype bfloat112!')

    def test_check_tensor_data_type_inf_error(self):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = dump_data_parser._check_tensor_data('input', 1, np.array([np.inf, 2]), 'float16')
        print(res)
        self.assertIn(res, 'input[1] NaN/INF. Input data invalid. Please check!')

    def test_check_tensor_data_type_gt_max_error(self):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = dump_data_parser._check_tensor_data('input', 1, np.array([59000, 2]), 'float16')
        self.assertIn(res, 'input[1] max 59000 or min 2. Input data maybe invalid. Please check!')

    def test_save_data_to_bin_file_not_parse_type(self):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = dump_data_parser._save_data_to_bin_file({'input': []}, 'output', {}, dump_file)
        self.assertEqual(res, '')

    def test_save_data_to_bin_file_parse_type_not_dtype(self):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = dump_data_parser._save_data_to_bin_file({'input': [{'shape': {'dim':['1', '2']}, 'size':'2', 'data': struct.pack('Q', 10)}]}, 'input', {'input': {}}, dump_file)
        self.assertIn(res, 'shape: (1, 2) size: 2 dtype: unknown')

    def test_save_data_to_bin_file_parse_type_error(self, mocker):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        mocker.patch.object(dump_data_parser, '_summary_tensor_without_dtype', side_effect=ValueError('test'))
        try:
            dump_data_parser._save_data_to_bin_file({'input': [{'shape': {'dim':['1', '2']}, 'size':'2', 'data': struct.pack('Q', 10)}]}, 'input', {'input': {}}, dump_file)
        except Exception as e:
            self.assertEqual(str(e), '4')
