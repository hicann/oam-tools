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
import pytest

sys.path.append(MSAICERR_PATH)

from ms_interface.aic_error_info import AicErrorInfo
from ms_interface.dump_data_parser import DumpDataParser, BigDumpDataParser

dump_file = "exception_info.2.1.20250609144925349"


def create_dump_file(file_name, header_length, body_length):
    with open(file_name, 'wb') as f:
        f.write(struct.pack('Q', header_length))
        f.write(bytearray(range(header_length)))
        f.write(bytearray(range(body_length)))


class Selflib():
    def ParseDumpProtoToJson(self, data_ptr, data_size, path_ptr):
        return 0


class Selfliberr():
    def ParseDumpProtoToJson(self, data_ptr, data_size, path_ptr):
        return 1


class TestUtilsMethods(CommonAssert):
    @pytest.fixture(autouse=True)
    def change_test_dir(self, tmp_path):
        self.old_cwd = os.getcwd()
        self.temp = tmp_path
        self.debug_info = tmp_path.joinpath("debug_info.txt")
        os.chdir(tmp_path)
        yield
        os.chdir(self.old_cwd)

    @staticmethod
    def common_mock(mocker, dump_json):
        # mock通用方法
        mocker.patch('ctypes.CDLL', return_value=Selflib())
        with open(f"{dump_file}.json", "w") as f:
            f.write(json.dumps(dump_json))

    def test_parser_dump_file(self, mocker):
        dump_json = {'version': '2.0', 'dump_time': '1749451765349986', 'output': [{'data_type': 0, 'format': 0, 'shape': {'dim': ['2', '2048']}, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'dim_range': [], 'offset': '3'}], 'input': [{'data_type': 0, 'format': 0, 'shape': {'dim': ['10240', '2048']}, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 0, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['2']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 1, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['1']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 2, 'input_type': 2}, {'data_type': 0, 'format': 0, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 5, 'input_type': 7}], 'buffer': [], 'op_name': '', 'attr': [], 'space': [{'type': 0, 'data': '', 'size': '10'}], 'dfx_message': '[AIC_INFO] args(0 to 20) after execute:0x12c200000000, 0x12d340000000, 0x12c1c0000518, 0x12d340000200, 0x12d340004400, 0x12c1c0000438, 0x12c100011000, 0x285a, 0x2, 0x1, 0, 0x2000, 0x8, 0x1, 0x1, 0x2800, 0x2, 0x800, 0x1, 0x1, \n[AIC_INFO] args(20 to 39) after execute:0x2, 0x1, 0x1, 0x1, 0x1, 0x800, 0x1, 0x1, 0x2, 0x1, 0x2, 0xa5a5a5a500000000, 0, 0, 0, 0, 0, 0, 0, \n[Dump][Exception] begin to load normal tensor, index:0\n[Dump][Exception] exception info dump args data, addr:0x12c200000000; size:83886080 bytes\n[Dump][Exception] end to load normal tensor, index:0\n[Dump][Exception] begin to load normal tensor, index:1\n[Dump][Exception] exception info dump args data, addr:0x12d340000000; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:1\n[Dump][Exception] begin to load normal tensor, index:2\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000518; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:2\n[Dump][Exception] begin to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340000200; size:16384 bytes\n[Dump][Exception] end to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340004400; size:76832 bytes\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000438; size:200 bytes\n'}
        self.common_mock(mocker, dump_json)
        create_dump_file(dump_file, 10, 200)
        info = AicErrorInfo()
        info.json_file = str(RES_PATH.joinpath("ori_data/collect_json/test.json")) # 指定json文件路径
        dump_data_parser = DumpDataParser(dump_file, info)
        dump_data_parser.parse()
        # info.result_info
        self.assertIn(info.dump_info, "exception_info.2.1.20250609144925349.input.0.float32.bin")
        self.assertIn(info.dump_info, "shape: (10240, 2048) size: 10 dtype: float32")

        self.assertIn(info.dump_info, "exception_info.2.1.20250609144925349.workspace.0.int8.npy")
        self.assertIn(info.dump_info, "shape: () size: 10 dtype: int8")

        self.assertEqual(dump_data_parser.get_input_data(), [])
        self.assertEqual(dump_data_parser.get_output_data(), [])
        self.assertIn(dump_data_parser.get_bin_data(), "exception_info.2.1.20250609144925349.input.1.int64.bin")
        self.assertIn(dump_data_parser.get_workspace_data(), 'exception_info.2.1.20250609144925349.workspace.0.int8.npy')
        self.assertIn(dump_data_parser.get_dfx_message(), "[AIC_INFO] args(20 to 39)")

    def test_ctype_cdll_parse_dump_error(self, mocker, capsys):
        mocker.patch('ctypes.CDLL', side_effect=OSError("libascend_dump_parser.so: cannot open shared object file"))
        create_dump_file(dump_file, 10, 200)
        info = AicErrorInfo()
        info.json_file = str(RES_PATH.joinpath("ori_data/collect_json/test.json"))  # 指定json文件路径
        DumpDataParser(dump_file, info).parse()
        self.assertIn(capsys.readouterr().out, "libascend_dump_parser.so: cannot open shared object file")

    def test_parser_dump_to_json_file_error(self, mocker, capsys):
        mocker.patch('ctypes.CDLL', return_value=Selfliberr())
        create_dump_file(dump_file, 10, 200)
        info = AicErrorInfo()
        info.json_file = str(RES_PATH.joinpath("ori_data/collect_json/test.json"))  # 指定json文件路径
        DumpDataParser(dump_file, info).parse()
        self.assertIn(capsys.readouterr().out, "Parse dump file to json failed")

    def test_parser_dump_file_file_size_lt_uint64_size_error(self, mocker, capsys):
        dump_json = {'version': '2.0', 'dump_time': '1749451765349986', 'output': [{'data_type': 0, 'format': 0, 'shape': {'dim': ['2', '2048']}, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'dim_range': [], 'offset': '3'}], 'input': [{'data_type': 0, 'format': 0, 'shape': {'dim': ['10240', '2048']}, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 0, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['2']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 1, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['1']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 2, 'input_type': 2}, {'data_type': 0, 'format': 0, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 5, 'input_type': 7}], 'buffer': [], 'op_name': '', 'attr': [], 'space': [{'type': 0, 'data': '', 'size': '10'}], 'dfx_message': '[AIC_INFO] args(0 to 20) after execute:0x12c200000000, 0x12d340000000, 0x12c1c0000518, 0x12d340000200, 0x12d340004400, 0x12c1c0000438, 0x12c100011000, 0x285a, 0x2, 0x1, 0, 0x2000, 0x8, 0x1, 0x1, 0x2800, 0x2, 0x800, 0x1, 0x1, \n[AIC_INFO] args(20 to 39) after execute:0x2, 0x1, 0x1, 0x1, 0x1, 0x800, 0x1, 0x1, 0x2, 0x1, 0x2, 0xa5a5a5a500000000, 0, 0, 0, 0, 0, 0, 0, \n[Dump][Exception] begin to load normal tensor, index:0\n[Dump][Exception] exception info dump args data, addr:0x12c200000000; size:83886080 bytes\n[Dump][Exception] end to load normal tensor, index:0\n[Dump][Exception] begin to load normal tensor, index:1\n[Dump][Exception] exception info dump args data, addr:0x12d340000000; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:1\n[Dump][Exception] begin to load normal tensor, index:2\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000518; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:2\n[Dump][Exception] begin to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340000200; size:16384 bytes\n[Dump][Exception] end to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340004400; size:76832 bytes\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000438; size:200 bytes\n'}
        self.common_mock(mocker, dump_json)
        with open(dump_file, 'wb') as f:
            f.write(struct.pack('Q', 8))
        info = AicErrorInfo()
        info.json_file = str(RES_PATH.joinpath("ori_data/collect_json/test.json")) # 指定json文件路径
        DumpDataParser(dump_file, info).parse()
        self.assertIn(capsys.readouterr().out, "invalid dump file")


    def test_parser_dump_file_header_len_gt_file_size_error(self, mocker, capsys):
        dump_json = {'version': '2.0', 'dump_time': '1749451765349986', 'output': [{'data_type': 0, 'format': 0, 'shape': {'dim': ['2', '2048']}, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'dim_range': [], 'offset': '3'}], 'input': [{'data_type': 0, 'format': 0, 'shape': {'dim': ['10240', '2048']}, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 0, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['2']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 1, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['1']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 2, 'input_type': 2}, {'data_type': 0, 'format': 0, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 5, 'input_type': 7}], 'buffer': [], 'op_name': '', 'attr': [], 'space': [{'type': 0, 'data': '', 'size': '10'}], 'dfx_message': '[AIC_INFO] args(0 to 20) after execute:0x12c200000000, 0x12d340000000, 0x12c1c0000518, 0x12d340000200, 0x12d340004400, 0x12c1c0000438, 0x12c100011000, 0x285a, 0x2, 0x1, 0, 0x2000, 0x8, 0x1, 0x1, 0x2800, 0x2, 0x800, 0x1, 0x1, \n[AIC_INFO] args(20 to 39) after execute:0x2, 0x1, 0x1, 0x1, 0x1, 0x800, 0x1, 0x1, 0x2, 0x1, 0x2, 0xa5a5a5a500000000, 0, 0, 0, 0, 0, 0, 0, \n[Dump][Exception] begin to load normal tensor, index:0\n[Dump][Exception] exception info dump args data, addr:0x12c200000000; size:83886080 bytes\n[Dump][Exception] end to load normal tensor, index:0\n[Dump][Exception] begin to load normal tensor, index:1\n[Dump][Exception] exception info dump args data, addr:0x12d340000000; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:1\n[Dump][Exception] begin to load normal tensor, index:2\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000518; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:2\n[Dump][Exception] begin to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340000200; size:16384 bytes\n[Dump][Exception] end to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340004400; size:76832 bytes\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000438; size:200 bytes\n'}
        self.common_mock(mocker, dump_json)
        with open(dump_file, 'wb') as f:
            f.write(struct.pack('Q', 100))
            f.write(struct.pack('Q', 10))
        info = AicErrorInfo()
        info.json_file = str(RES_PATH.joinpath("ori_data/collect_json/test.json")) # 指定json文件路径
        DumpDataParser(dump_file, info).parse()
        self.assertIn(capsys.readouterr().out, "Failed to read the dump file")

    def test_parser_dump_file_use_size_gt_file_size_error(self, mocker, capsys):
        dump_json = {'version': '2.0', 'dump_time': '1749451765349986', 'output': [{'data_type': 0, 'format': 0, 'shape': {'dim': ['2', '2048']}, 'data': '', 'size': '100000', 'sub_format': 0, 'address': '0', 'dim_range': [], 'offset': '3'}], 'input': [{'data_type': 0, 'format': 0, 'shape': {'dim': ['10240', '2048']}, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 0, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['2']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 1, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['1']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 2, 'input_type': 2}, {'data_type': 0, 'format': 0, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 5, 'input_type': 7}], 'buffer': [], 'op_name': '', 'attr': [], 'space': [{'type': 0, 'data': '', 'size': '10'}], 'dfx_message': '[AIC_INFO] args(0 to 20) after execute:0x12c200000000, 0x12d340000000, 0x12c1c0000518, 0x12d340000200, 0x12d340004400, 0x12c1c0000438, 0x12c100011000, 0x285a, 0x2, 0x1, 0, 0x2000, 0x8, 0x1, 0x1, 0x2800, 0x2, 0x800, 0x1, 0x1, \n[AIC_INFO] args(20 to 39) after execute:0x2, 0x1, 0x1, 0x1, 0x1, 0x800, 0x1, 0x1, 0x2, 0x1, 0x2, 0xa5a5a5a500000000, 0, 0, 0, 0, 0, 0, 0, \n[Dump][Exception] begin to load normal tensor, index:0\n[Dump][Exception] exception info dump args data, addr:0x12c200000000; size:83886080 bytes\n[Dump][Exception] end to load normal tensor, index:0\n[Dump][Exception] begin to load normal tensor, index:1\n[Dump][Exception] exception info dump args data, addr:0x12d340000000; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:1\n[Dump][Exception] begin to load normal tensor, index:2\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000518; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:2\n[Dump][Exception] begin to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340000200; size:16384 bytes\n[Dump][Exception] end to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340004400; size:76832 bytes\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000438; size:200 bytes\n'}
        self.common_mock(mocker, dump_json)
        create_dump_file(dump_file, 10, 200)
        info = AicErrorInfo()
        info.json_file = str(RES_PATH.joinpath("ori_data/collect_json/test.json")) # 指定json文件路径
        DumpDataParser(dump_file, info).parse()
        self.assertIn(capsys.readouterr().out, "The size of exception_info.2.1.20250609144925349 is invalid, please check the dump file")

    def test_parser_dump_file_not_dump_file_error(self, mocker):
        info = AicErrorInfo()
        info.json_file = str(RES_PATH.joinpath("ori_data/collect_json/test.json")) # 指定json文件路径
        DumpDataParser("test.bin", info).parse()
        self.assertEqual(info.dump_info, "")

    def test_parser_dump_file_not_dump_dir_error(self, mocker):
        info = AicErrorInfo()
        info.json_file = str(RES_PATH.joinpath("ori_data/collect_json/test.json")) # 指定json文件路径
        info.node_name = "test"
        with open("test.bin", "wb") as f:
            f.write(struct.pack("Q", 10))
        DumpDataParser(self.temp, info).parse()
        self.assertEqual(info.dump_info, "")

    def test_parser_dump_file_not_dtype(self, mocker):
        dump_json = {'version': '2.0', 'dump_time': '1749451765349986', 'output': [{'data_type': 0, 'format': 0, 'shape': {'dim': ['2', '2048']}, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'dim_range': [], 'offset': '3'}], 'input': [{'data_type': 0, 'format': 0, 'shape': {'dim': ['10240', '2048']}, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 0, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['2']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 1, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['1']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 2, 'input_type': 2}, {'data_type': 0, 'format': 0, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 5, 'input_type': 7}], 'buffer': [], 'op_name': '', 'attr': [], 'space': [{'type': 0, 'data': '', 'size': '10'}], 'dfx_message': '[AIC_INFO] args(0 to 20) after execute:0x12c200000000, 0x12d340000000, 0x12c1c0000518, 0x12d340000200, 0x12d340004400, 0x12c1c0000438, 0x12c100011000, 0x285a, 0x2, 0x1, 0, 0x2000, 0x8, 0x1, 0x1, 0x2800, 0x2, 0x800, 0x1, 0x1, \n[AIC_INFO] args(20 to 39) after execute:0x2, 0x1, 0x1, 0x1, 0x1, 0x800, 0x1, 0x1, 0x2, 0x1, 0x2, 0xa5a5a5a500000000, 0, 0, 0, 0, 0, 0, 0, \n[Dump][Exception] begin to load normal tensor, index:0\n[Dump][Exception] exception info dump args data, addr:0x12c200000000; size:83886080 bytes\n[Dump][Exception] end to load normal tensor, index:0\n[Dump][Exception] begin to load normal tensor, index:1\n[Dump][Exception] exception info dump args data, addr:0x12d340000000; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:1\n[Dump][Exception] begin to load normal tensor, index:2\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000518; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:2\n[Dump][Exception] begin to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340000200; size:16384 bytes\n[Dump][Exception] end to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340004400; size:76832 bytes\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000438; size:200 bytes\n'}
        self.common_mock(mocker, dump_json)
        create_dump_file(dump_file, 10, 200)
        info = AicErrorInfo()
        DumpDataParser(dump_file, info).parse()
        self.assertIn(info.dump_info, "shape: () size: 10 dtype: unknown")
        self.assertIn(info.dump_info, "If dtype is float32")
        self.assertIn(info.dump_info, "If dtype is float16")
        self.assertIn(info.dump_info, "If dtype is bfloat16")
        self.assertIn(info.dump_info, "If dtype is int32")
        self.assertIn(info.dump_info, "If dtype is int64")

    def test_parser_dump_file_not_output(self, mocker, capsys):
        dump_json = {'version': '2.0', 'dump_time': '1749451765349986', 'input': [{'data_type': 0, 'format': 0, 'shape': {'dim': ['10240', '2048']}, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 0, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['2']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 1, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['1']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 2, 'input_type': 2}, {'data_type': 0, 'format': 0, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 5, 'input_type': 7}], 'buffer': [], 'op_name': '', 'attr': [], 'space': [{'type': 0, 'data': '', 'size': '10'}], 'dfx_message': '[AIC_INFO] args(0 to 20) after execute:0x12c200000000, 0x12d340000000, 0x12c1c0000518, 0x12d340000200, 0x12d340004400, 0x12c1c0000438, 0x12c100011000, 0x285a, 0x2, 0x1, 0, 0x2000, 0x8, 0x1, 0x1, 0x2800, 0x2, 0x800, 0x1, 0x1, \n[AIC_INFO] args(20 to 39) after execute:0x2, 0x1, 0x1, 0x1, 0x1, 0x800, 0x1, 0x1, 0x2, 0x1, 0x2, 0xa5a5a5a500000000, 0, 0, 0, 0, 0, 0, 0, \n[Dump][Exception] begin to load normal tensor, index:0\n[Dump][Exception] exception info dump args data, addr:0x12c200000000; size:83886080 bytes\n[Dump][Exception] end to load normal tensor, index:0\n[Dump][Exception] begin to load normal tensor, index:1\n[Dump][Exception] exception info dump args data, addr:0x12d340000000; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:1\n[Dump][Exception] begin to load normal tensor, index:2\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000518; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:2\n[Dump][Exception] begin to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340000200; size:16384 bytes\n[Dump][Exception] end to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340004400; size:76832 bytes\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000438; size:200 bytes\n'}
        self.common_mock(mocker, dump_json)
        create_dump_file(dump_file, 10, 200)
        info = AicErrorInfo()
        DumpDataParser(dump_file, info).parse()
        self.asseerNotIn(info.dump_info, "exception_info.2.1.20250609144925349.output")

    def test_parser_dump_file_bfloat16_dtype_success(self, mocker):
        dump_json = {'version': '2.0', 'dump_time': '1749451765349986', 'output': [{'data_type': 27, 'format': 0, 'shape': {'dim': ['2', '2048']}, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'dim_range': [], 'offset': '3'}], 'input': [{'data_type': 0, 'format': 0, 'shape': {'dim': ['10240', '2048']}, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 0, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['2']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 1, 'input_type': 2}, {'data_type': 0, 'format': 0, 'shape': {'dim': ['1']}, 'data': '', 'size': '32', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 2, 'input_type': 2}, {'data_type': 0, 'format': 0, 'data': '', 'size': '10', 'sub_format': 0, 'address': '0', 'offset': '0', 'arg_index': 5, 'input_type': 7}], 'buffer': [], 'op_name': '', 'attr': [], 'space': [{'type': 0, 'data': '', 'size': '10'}], 'dfx_message': '[AIC_INFO] args(0 to 20) after execute:0x12c200000000, 0x12d340000000, 0x12c1c0000518, 0x12d340000200, 0x12d340004400, 0x12c1c0000438, 0x12c100011000, 0x285a, 0x2, 0x1, 0, 0x2000, 0x8, 0x1, 0x1, 0x2800, 0x2, 0x800, 0x1, 0x1, \n[AIC_INFO] args(20 to 39) after execute:0x2, 0x1, 0x1, 0x1, 0x1, 0x800, 0x1, 0x1, 0x2, 0x1, 0x2, 0xa5a5a5a500000000, 0, 0, 0, 0, 0, 0, 0, \n[Dump][Exception] begin to load normal tensor, index:0\n[Dump][Exception] exception info dump args data, addr:0x12c200000000; size:83886080 bytes\n[Dump][Exception] end to load normal tensor, index:0\n[Dump][Exception] begin to load normal tensor, index:1\n[Dump][Exception] exception info dump args data, addr:0x12d340000000; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:1\n[Dump][Exception] begin to load normal tensor, index:2\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000518; size:32 bytes\n[Dump][Exception] end to load normal tensor, index:2\n[Dump][Exception] begin to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340000200; size:16384 bytes\n[Dump][Exception] end to load normal tensor, index:3\n[Dump][Exception] exception info dump args data, addr:0x12d340004400; size:76832 bytes\n[Dump][Exception] exception info dump args data, addr:0x12c1c0000438; size:200 bytes\n'}
        self.common_mock(mocker, dump_json)
        create_dump_file(dump_file, 10, 200)
        info = AicErrorInfo()
        info.json_file = str(RES_PATH.joinpath("ori_data/collect_json/test.json")) # 指定json文件路径
        DumpDataParser(dump_file, info).parse()
        # info.result_info
        self.assertIn(info.dump_info, 'exception_info.2.1.20250609144925349.output.0.bfloat16.bin')