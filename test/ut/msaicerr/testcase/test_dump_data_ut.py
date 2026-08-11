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
import warnings
import importlib.util

from conftest import MSAICERR_PATH, RES_PATH, CommonAssert
import os
import sys
from argparse import Namespace
import pytest
import numpy as np
from unittest.mock import Mock

sys.path.append(MSAICERR_PATH)
from ms_interface import utils
from ms_interface.constant import Constant
from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.dump_data_parser import DumpDataParser, BigDumpDataParser


dump_file = "exception_info.2.1.20250609144925349"
bin_file = "aclnnAbs_0_L0.AbsAicore.2.20260202152928444.input.0.bin"


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


class SelflibCheckPath():
    def ParseDumpProtoToJson(self, data_ptr, data_size, path_ptr):
        return len(path_ptr) != 0


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

    def test_parse_dump_to_json_check_path(self, mocker):
        big_dump_parser = BigDumpDataParser(dump_file)
        mocker.patch('ctypes.CDLL', return_value=SelflibCheckPath())
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
        # the payload is 10 bytes, not a whole number of float32 elements, keep the raw bin
        self.assertIn(info.dump_info, "exception_info.2.1.20250609144925349.input.0.float32.bin")
        self.assertIn(info.dump_info, "shape: (10240, 2048) size: 10 dtype: float32")

        self.assertIn(info.dump_info, "exception_info.2.1.20250609144925349.workspace.0.int8.npy")
        self.assertIn(info.dump_info, "shape: () size: 10 dtype: int8")

        self.assertEqual(dump_data_parser.get_input_data(), [])
        self.assertEqual(dump_data_parser.get_output_data(), [])
        self.assertIn(dump_data_parser.get_bin_data(), "exception_info.2.1.20250609144925349.input.1.int64.npy")
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

    def test_summary_tensor_empty_array(self, mocker):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        empty_arr = np.array([], dtype=np.float32)
        mocker.patch.object(np, "fromfile", return_value=empty_arr)
        res = dump_data_parser._summary_tensor_without_dtype("text.bin", "float32")
        self.assertIn(res, "Max: N/A, Min: N/A, Mean: N/A, Std: N/A")

    def test_check_tensor_data_type_error(self):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = dump_data_parser._check_tensor_data('input', 1, np.array([1, 2]), 'bfloat112')
        self.assertIn(res, 'Can not read with dtype bfloat112!')

    def test_check_input_nonbin_with_dtype(self):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo(), 'float16')
        res = dump_data_parser.parse()
        self.assertEqual(res, None)

    def test_convert_bin_check_input(self):
        dump_data_parser = DumpDataParser(bin_file, AicErrorInfo())
        res = dump_data_parser.convert_bin_file_to_npy()
        self.assertIn(res, 'Need to specify the dtype when convert a bin file.')

    def test_convert_bin_check_input_dtype_error(self):
        dump_data_parser = DumpDataParser(bin_file, AicErrorInfo(), 'fint8')
        res = dump_data_parser.convert_bin_file_to_npy()
        self.assertIn(res, 'Invalid dest_dtype: fint8')

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
        # data_type is absent, it defaults to enum 0 which maps to undefined
        self.assertIn(res, 'shape: (1, 2) size: 2 dtype: undefined')

    def test_save_data_to_bin_file_dtype_not_in_map(self):
        """the dtype enum is not in the map, the raw enum value is recorded"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = dump_data_parser._save_data_to_bin_file(
            {'input': [{'data_type': 99, 'shape': {'dim': ['8']}, 'size': '8', 'data': struct.pack('Q', 10)}]},
            'input', {'input': {}}, dump_file)
        self.assertIn(res, 'shape: (8,) size: 8 dtype: 99')
        self.assertIn(res, 'input.0.99.bin')

    def test_save_data_to_bin_file_numpy_dtype_saved_as_npy(self):
        """numpy supported dtype is saved as npy with the right dtype and shape"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        raw = np.arange(6, dtype=np.float32).tobytes()
        res = dump_data_parser._save_data_to_bin_file(
            {'input': [{'data_type': 1, 'shape': {'dim': ['2', '3']}, 'size': '24', 'data': raw}]},
            'input', {'input': {}}, dump_file)
        self.assertIn(res, 'shape: (2, 3) size: 24 dtype: float32')
        npy_file = dump_data_parser.get_bin_data()[0]
        assert npy_file.endswith('input.0.float32.npy')
        array = np.load(npy_file)
        self.assertEqual(str(array.dtype), 'float32')
        self.assertEqual(array.shape, (2, 3))

    def test_save_data_to_bin_file_json_dtype_fallback(self):
        """data_type为0(undefined)时回退到json中的dtype"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        raw = np.arange(4, dtype=np.int64).tobytes()
        res = dump_data_parser._save_data_to_bin_file(
            {'input': [{'data_type': 0, 'shape': {'dim': ['4']}, 'size': '32', 'data': raw}]},
            'input', {'input': {0: 'int64'}}, dump_file)
        self.assertIn(res, 'dtype: int64')
        assert dump_data_parser.get_bin_data()[0].endswith('input.0.int64.npy')

    def test_save_data_to_bin_file_size_not_aligned_keep_bin(self):
        """字节数不是itemsize整数倍时无法按该dtype解析，保留原始bin"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = dump_data_parser._save_data_to_bin_file(
            {'input': [{'data_type': 1, 'shape': {'dim': ['1']}, 'size': '3', 'data': b'\x01\x02\x03'}]},
            'input', {'input': {}}, dump_file)
        self.assertIn(res, 'dtype: float32')
        assert dump_data_parser.get_bin_data()[0].endswith('input.0.float32.bin')

    def test_save_data_to_bin_file_non_numpy_dtype_keep_bin(self):
        """numpy不支持的dtype(int4)保存为bin，先给出真实dtype的提示再按常用dtype猜测"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = dump_data_parser._save_data_to_bin_file(
            {'input': [{'data_type': 28, 'shape': {'dim': ['8']}, 'size': '4', 'data': b'\x01\x02\x03\x04'}]},
            'input', {'input': {}}, dump_file)
        self.assertIn(res, 'dtype: int4')
        self.assertIn(res, 'If dtype is int4, summary is: ')
        self.assertIn(res, 'If dtype is float32')
        assert dump_data_parser.get_bin_data()[0].endswith('input.0.int4.bin')

    def test_save_data_to_bin_file_non_numpy_dtype_hint_when_unreadable(self, mocker):
        """numpy无法解析该dtype时，提示中必须带真实dtype名，用户据此安装第三方库"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        # 固定np.dtype对int4抛异常，不依赖环境是否装了注册int4的第三方库
        real_dtype = np.dtype
        mocker.patch('numpy.dtype',
                     side_effect=lambda x: (_ for _ in ()).throw(TypeError()) if x == 'int4' else real_dtype(x))
        res = dump_data_parser._save_data_to_bin_file(
            {'input': [{'data_type': 28, 'shape': {'dim': ['8']}, 'size': '4', 'data': b'\x01\x02\x03\x04'}]},
            'input', {'input': {}}, dump_file)
        self.assertIn(res, 'If dtype is int4, summary is: Can not read with dtype int4!')

    def test_save_data_to_bin_file_undefined_no_named_hint(self):
        """undefined并非真实dtype，不输出带undefined的提示，只做常用dtype猜测"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = dump_data_parser._save_data_to_bin_file(
            {'input': [{'data_type': 0, 'shape': {'dim': ['4']}, 'size': '4', 'data': b'\x01\x02\x03\x04'}]},
            'input', {'input': {}}, dump_file)
        self.assertNotIn(res, 'Can not read with dtype undefined')
        self.assertIn(res, 'If dtype is float32')

    def test_save_data_to_bin_file_not_aligned_no_duplicate_summary(self):
        """字节未对齐但numpy认识该dtype时，只按该dtype给一行summary，不重复猜测"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        res = dump_data_parser._save_data_to_bin_file(
            {'input': [{'data_type': 1, 'shape': {'dim': ['1']}, 'size': '3', 'data': b'\x01\x02\x03'}]},
            'input', {'input': {}}, dump_file)
        self.assertEqual(res.count('If dtype is float32'), 1)
        self.assertNotIn(res, 'If dtype is int64')

    def test_save_data_to_bin_file_space_multi_items(self):
        """space有多个item时全部按workspace的int8 npy落盘"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        item = {'size': '4', 'data': b'\x01\x02\x03\x04'}
        res = dump_data_parser._save_data_to_bin_file(
            {'space': [dict(item), dict(item)]}, 'space', {'input': {}}, dump_file)
        self.assertIn(res, 'dtype: int8')
        workspaces = dump_data_parser.get_workspace_data()
        self.assertEqual(len(workspaces), 2)
        assert workspaces[0].endswith('workspace.0.int8.npy')
        assert workspaces[1].endswith('workspace.1.int8.npy')
        self.assertEqual(dump_data_parser.get_bin_data(), [])

    def test_save_data_to_bin_file_bool_and_complex(self):
        """bool与complex同为numpy支持的dtype，落盘为npy且可正常load"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        dump_data_parser._save_data_to_bin_file(
            {'input': [{'data_type': 11, 'shape': {'dim': ['2']}, 'size': '2',
                        'data': np.array([True, False]).tobytes()},
                       {'data_type': 16, 'shape': {'dim': ['1']}, 'size': '8',
                        'data': np.array([1 + 2j], dtype=np.complex64).tobytes()}]},
            'input', {'input': {}}, dump_file)
        bool_file, complex_file = dump_data_parser.get_bin_data()
        assert bool_file.endswith('input.0.bool.npy')
        assert complex_file.endswith('input.1.complex64.npy')
        self.assertEqual(np.load(bool_file).tolist(), [True, False])
        self.assertEqual(np.load(complex_file).tolist(), [1 + 2j])

    def test_save_data_to_bin_file_shape_mismatch_keeps_flat(self):
        """元素个数与shape不一致时不做reshape，保持一维"""
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        raw = np.arange(4, dtype=np.float32).tobytes()
        dump_data_parser._save_data_to_bin_file(
            {'input': [{'data_type': 1, 'shape': {'dim': ['100', '100']}, 'size': '16', 'data': raw}]},
            'input', {'input': {}}, dump_file)
        array = np.load(dump_data_parser.get_bin_data()[0])
        self.assertEqual(array.shape, (4,))

    def test_to_numpy_dtype(self):
        """numpy原生dtype可解析，非numpy dtype与空值返回None"""
        self.assertEqual(DumpDataParser._to_numpy_dtype('float32'), np.dtype('float32'))
        self.assertEqual(DumpDataParser._to_numpy_dtype('int4'), None)
        self.assertEqual(DumpDataParser._to_numpy_dtype('string'), None)
        self.assertEqual(DumpDataParser._to_numpy_dtype('99'), None)
        self.assertEqual(DumpDataParser._to_numpy_dtype(None), None)
        self.assertEqual(DumpDataParser._to_numpy_dtype(''), None)

    def test_to_numpy_dtype_bfloat16_without_ext(self):
        """bfloat16ext缺失(或装了但numpy仍不认识)时，bfloat16按非numpy dtype处理，落盘为bin"""
        if importlib.util.find_spec('bfloat16ext') is not None:
            pytest.skip('bfloat16ext已安装，该分支不适用')
        self.assertEqual(DumpDataParser._to_numpy_dtype('bfloat16'), None)
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        dump_data_parser._save_data_to_bin_file(
            {'input': [{'data_type': 27, 'shape': {'dim': ['2']}, 'size': '4', 'data': b'\x01\x02\x03\x04'}]},
            'input', {'input': {}}, dump_file)
        assert dump_data_parser.get_bin_data()[0].endswith('input.0.bfloat16.bin')

    def test_to_numpy_dtype_bfloat16_with_ext(self, mocker):
        """bfloat16ext可用时bfloat16视为numpy支持的dtype"""
        bf16_dtype = np.dtype('int16')
        mocker.patch.dict(sys.modules, {'bfloat16ext': Mock()})
        # 桩掉np.dtype模拟扩展注册后numpy可识别bfloat16
        mocker.patch('numpy.dtype', return_value=bf16_dtype)
        self.assertEqual(DumpDataParser._to_numpy_dtype('bfloat16'), bf16_dtype)

    def test_to_numpy_dtype_ext_imported_but_dtype_unregistered(self, mocker):
        """bfloat16ext导入成功但numpy仍未注册该dtype时安全返回None"""
        mocker.patch.dict(sys.modules, {'bfloat16ext': Mock()})
        mocker.patch('numpy.dtype', side_effect=TypeError('not understood'))
        self.assertEqual(DumpDataParser._to_numpy_dtype('bfloat16'), None)

    def test_get_item_dtype(self):
        """dtype取值优先级: 枚举映射 > json > 原始枚举值"""
        self.assertEqual(DumpDataParser._get_item_dtype({'data_type': 2}, 'input', {}, 0), 'float16')
        # workspace固定int8
        self.assertEqual(DumpDataParser._get_item_dtype({}, 'workspace', {}, 0), 'int8')
        # 枚举不在映射表中，直接记录枚举值
        self.assertEqual(DumpDataParser._get_item_dtype({'data_type': 77}, 'input', {'input': {}}, 0), '77')
        # 枚举不在映射表但json有dtype，优先json
        self.assertEqual(
            DumpDataParser._get_item_dtype({'data_type': 77}, 'input', {'input': {0: 'float16'}}, 0), 'float16')
        # undefined不作为有效dtype，回退json
        self.assertEqual(
            DumpDataParser._get_item_dtype({'data_type': 0}, 'input', {'input': {0: 'int32'}}, 0), 'int32')
        self.assertEqual(DumpDataParser._get_item_dtype({'data_type': 0}, 'input', {'input': {}}, 0), 'undefined')

    def test_build_typed_array(self):
        """字节数据按dtype视图化并reshape，无法解析时退化为int8"""
        raw = np.arange(6, dtype=np.float32).tobytes()
        array, np_dtype = DumpDataParser._build_typed_array(raw, 'float32', [2, 3])
        self.assertEqual(np_dtype, np.dtype('float32'))
        self.assertEqual(array.shape, (2, 3))
        # 非numpy dtype
        array, np_dtype = DumpDataParser._build_typed_array(raw, 'int4', [6])
        self.assertEqual(np_dtype, None)
        self.assertEqual(str(array.dtype), 'int8')
        # 字节数未对齐
        array, np_dtype = DumpDataParser._build_typed_array(b'\x01\x02\x03', 'float32', [1])
        self.assertEqual(np_dtype, None)
        # data为None时按空数组处理
        array, np_dtype = DumpDataParser._build_typed_array(None, 'float32', [1])
        self.assertEqual(array.size, 0)

    def test_summary_tensor_array(self):
        """已知dtype的数组直接由内存计算summary"""
        res = DumpDataParser._summary_tensor_array(np.array([1, 3], dtype=np.int32), 'int32')
        self.assertIn(res, 'If dtype is int32, summary is: Max: 3, Min: 1, Mean: 2.0, Std: 1.0')

    def test_summary_tensor_array_empty(self):
        res = DumpDataParser._summary_tensor_array(np.array([], dtype=np.float32), 'float32')
        self.assertIn(res, 'Max: N/A, Min: N/A, Mean: N/A, Std: N/A')

    def test_summary_tensor_array_complex_no_warning(self):
        """complex数组按complex128累加，不产生丢弃虚部的告警"""
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            res = DumpDataParser._summary_tensor_array(
                np.array([1 + 2j, 3 + 4j], dtype=np.complex64), 'complex64')
        self.assertIn(res, 'If dtype is complex64')

    def test_summary_tensor_array_error(self, mocker):
        mocker.patch('numpy.mean', side_effect=ValueError('test'))
        res = DumpDataParser._summary_tensor_array(np.array([1, 2], dtype=np.int32), 'int32')
        self.assertIn(res, 'Can not read with dtype int32!')

    def test_save_data_to_bin_file_parse_type_error(self, mocker):
        dump_data_parser = DumpDataParser(dump_file, AicErrorInfo())
        mocker.patch.object(dump_data_parser, '_summary_tensor_without_dtype', side_effect=ValueError('test'))
        try:
            dump_data_parser._save_data_to_bin_file({'input': [{'shape': {'dim':['1', '2']}, 'size':'2', 'data': struct.pack('Q', 10)}]}, 'input', {'input': {}}, dump_file)
        except Exception as e:
            self.assertEqual(str(e), '4')
