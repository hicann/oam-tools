#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd. All Rights Reserved.
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
"""
Function:
DumpDataParser class. This class mainly involves the parser_dump_data function.
Copyright Information:
Huawei Technologies Co., Ltd. All Rights Reserved © 2020
"""
import json
import os
import struct
import ctypes
import traceback
import sys
from typing import BinaryIO
import numpy as np
from ms_interface import utils
from ms_interface.constant import Constant
from ms_interface.aic_error_info import AicErrorInfo


class ConstManager:
    UINT64_SIZE = 8
    UINT64_FMT = 'Q'
    ONE_GB = 1 * 1024 * 1024 * 1024
    DATA_TYPE_TO_DTYPE_MAP = {
        '1': 'float32',
        '2': 'float16',
        '12': 'float64',
        '3': 'int8',
        '5': 'int16',
        '7': 'int32',
        '8': 'int64',
        '4': 'uint8',
        '6': 'uint16',
        '9': 'uint32',
        '10': 'uint64',
        '11': 'bool',
        '27': 'bfloat16',  # bfloat16 is not supported in numpy
    }

    COMMON_DTYPE = ["float32", "float16", "bfloat16", "int32", "int64"]


class DumpDataParser:
    """
    The class for dump data parser
    """

    def __init__(self, dump_path, info: AicErrorInfo, output_path=""):
        self.dump_path = dump_path
        self.info = info
        self.input_data_list = []
        self.output_data_list = []
        self.workspace_data_list = []
        self.bin_data_list = []
        self.dfx_message = ""
        self.output_path = os.path.realpath(output_path) if output_path else ''
        self.parse_types = ['input', 'output', 'space']

    def get_input_data(self):
        return self.input_data_list

    def get_output_data(self):
        return self.output_data_list

    def get_workspace_data(self):
        return self.workspace_data_list

    def get_bin_data(self):
        return self.bin_data_list

    def get_dfx_message(self):
        return self.dfx_message

    @staticmethod
    def _check_tensor_data(parse_type, index, array, dtype):
        try:
            data_dtype = np.float32 if dtype == "bfloat16" else np.dtype(dtype)
        except TypeError:
            return f"Can not read with dtype {dtype}!\n"
        result_info = ""
        if (np.isinf(array).any() or np.isnan(array).any()):
            result_info = f'{parse_type}[{index}] NaN/INF. Input data invalid. Please check!\n'
            utils.print_error_log(result_info)
        else:
            if data_dtype in (np.int16, np.int32, np.int64, np.uint16, np.uint32, np.uint64):
                dtype_max = np.iinfo(data_dtype).max
                dtype_min = np.iinfo(data_dtype).min
            elif data_dtype in (np.float16, np.float32, np.float64):
                dtype_max = np.finfo(data_dtype).max
                dtype_min = np.finfo(data_dtype).min
            else:
                return ""
            if (np.max(array) > 0.9 * dtype_max) or (np.min(array) < 0.9 * dtype_min):
                result_info = (f'{parse_type}[{index}] max {np.max(array)} or min {np.min(array)}. '
                               f'Input data maybe invalid. Please check!\n')
                utils.print_error_log(result_info)
        return result_info

    @staticmethod
    def _summary_tensor_without_dtype(tensor_file, dtype):
        result_info = ""
        dtypes = [dtype] if dtype else ConstManager.COMMON_DTYPE
        for dtype in dtypes:
            result_info += " " * 4
            result_info += f"If dtype is {dtype}, summary is: "
            try:
                if dtype == "bfloat16":
                    from bfloat16ext import bfloat16
                    # 1. 以int16读取，纯粹的字节拷贝，不会触发溢出异常
                    raw_data = np.fromfile(tensor_file, dtype=np.int16)
                    # 2. 先转为float32处理
                    data_f32 = raw_data.astype(np.float32)
                    # 3. 手动设置数值边界3.3895e+38，防止无法表示的值
                    bf16_limit = 3.3895e+38
                    data_f32 = np.clip(data_f32, -bf16_limit, bf16_limit)
                    # 4. 转回bfloat16， 因为clip过，所以不会触发bfloat16 overflow导致的段错误
                    arr = data_f32.astype("bfloat16")
                arr = np.fromfile(tensor_file, dtype=np.dtype(dtype))
                result_info += f"Max: {np.max(arr)}, Min: {np.min(arr)}, Mean: {np.mean(arr)}, Std: {np.std(arr)}\n"
            except BaseException:
                result_info += f"Can not read with dtype {dtype}!\n"
        return result_info

    def _save_dfx_message(self, dump_json_data):
        self.dfx_message = dump_json_data.get("dfx_message", "")
        utils.print_debug_log(f"Dump exception info: {self.dfx_message}")

    def _collect_dtype_get_json_dtypes(self, json_data, json_dtypes):
        """
        collect inputs and outputs dtype
        @param json_data:  json data
        @param json_dtypes:  json inputs and outputs collect data
        """
        for data in json_data:
            if isinstance(data, dict) and ("index" in data) and ("dtype" in data):
                json_dtypes[data.get('index')] = data.get('dtype')
            elif isinstance(data, list):
                self._collect_dtype_get_json_dtypes(data, json_dtypes)

    def _get_json_dtypes(self):
        """
        Obtains the input and output dtypes in the JSON file.
        @param json_path: the dump json
        """
        json_dtypes = {
            'input': {},
            'output': {}
        }
        if not os.path.exists(self.info.json_file):
            return json_dtypes
        json_data = json.load(open(self.info.json_file))
        inputs_data = json_data.get('supportInfo', {}).get('inputs', [])
        outputs_data = json_data.get('supportInfo', {}).get('outputs', [])
        if inputs_data:
            self._collect_dtype_get_json_dtypes(inputs_data, json_dtypes['input'])
        if outputs_data:
            self._collect_dtype_get_json_dtypes(outputs_data, json_dtypes['output'])
        return json_dtypes

    def _save_data_to_bin_file(self, dump_json_data, parse_type, json_dtype, dump_file):
        result_info = ''
        dump_file_path, dump_file_name = os.path.split(dump_file)
        dump_file_path = self.output_path or dump_file_path
        if not dump_json_data.get(parse_type):
            utils.print_warn_log(f'There is no {parse_type} in {dump_file_name}.')
            return result_info

        if not self.info.kernel_name:
            self.info.kernel_name = dump_file_name

        for index, item in enumerate(dump_json_data.get(parse_type)):
            try:
                if parse_type == "space":
                    dtype = "int8"
                    parse_type = "workspace"
                else:
                    dtype = (ConstManager.DATA_TYPE_TO_DTYPE_MAP.get(str(item.get('data_type', '0'))) or
                             json_dtype.get(parse_type, {}).get(index))
                shape = [int(i) for i in item.get('shape', {}).get('dim', [])]
                result_info += (f"shape: {tuple(shape)} size: {item.get('size', 0)} "
                                f"dtype: {dtype if dtype else 'unknown'}\n")
                array = np.frombuffer(item.get('data'), dtype=np.int8)
                if dtype:
                    file_name = ".".join([self.info.kernel_name, parse_type, str(index),
                                          dtype, "bin" if parse_type != "workspace" else "npy"])
                else:
                    file_name = ".".join([self.info.kernel_name, parse_type, str(index), "bin"])
                dst_file_name = os.path.join(dump_file_path, file_name)

                if parse_type == "workspace":  # workspace save as npy
                    np.save(dst_file_name, array)
                    self.workspace_data_list.append(dst_file_name)
                else:
                    array.tofile(dst_file_name)
                    self.bin_data_list.append(dst_file_name)

                result_info += f'{dst_file_name}\n'
                if dtype:
                    result_info += self._check_tensor_data(parse_type, index, array, dtype)

                result_info += self._summary_tensor_without_dtype(dst_file_name, dtype)
            except (ValueError, IOError, OSError, MemoryError) as error:
                utils.print_error_log(f'Failed to parse the data of {parse_type}:{index} of "{dump_file}". {error}')
                raise utils.AicErrException(Constant.MS_AICERR_INVALID_DUMP_DATA_ERROR)
        return result_info

    def parse_dump_data(self, dump_file):
        """
        Function Description: convert dump data to numpy and bin file
        @param dump_file: the dump file
        """
        result_info = ''
        try:
            current_dir = os.path.abspath(os.path.dirname(__file__))
            compare_dir = os.path.join(current_dir, '..', '..', 'operator_cmp', 'compare')
            sys.path.append(compare_dir)
            big_dump_data_parser = BigDumpDataParser(dump_file)
            dump_json_data = big_dump_data_parser.parse()
            self.info.tiling_data_bytes = big_dump_data_parser.tiling_data
            json_dtype = self._get_json_dtypes()
            # 2. parse dump data
            for parse_type in self.parse_types:
                result_info += self._save_data_to_bin_file(dump_json_data, parse_type, json_dtype, dump_file)
            self._save_dfx_message(dump_json_data)
        except BaseException as e:
            utils.print_debug_log(traceback.format_exc())
            if str(e) == str(Constant.MS_AICERR_INVALID_DUMP_DATA_ERROR):
                e = "invalid dump file"
            utils.print_error_log(f"Failed to parse the data of dump file:{dump_file}, Error Detail: {e}.")
        return result_info

    def parse(self):
        """
        Function Description: dump data parse.
        """
        # get parse data list
        if os.path.isfile(self.dump_path):
            if self.dump_path.endswith(".npy") or self.dump_path.endswith(".bin"):
                utils.print_error_log(f"The dump file cannot be an npy file or a bin file.")
                return
            match_dump_list = [self.dump_path]
        else:
            match_dump_list = []
            match_name = self.info.node_name
            for top, _, files in os.walk(self.dump_path):
                for name in files:
                    if match_name in name:
                        match_dump_list.append(os.path.join(top, name))

        # parse data
        result_info_list = []
        dump_file = None
        for dump_file in match_dump_list:
            if isinstance(dump_file, str) and (dump_file.endswith(".npy") or dump_file.endswith(".bin")):
                continue
            result_info_list.extend(
                [f'Original file: {dump_file}\n', "after convert:\n", self.parse_dump_data(dump_file)])
        result_info = "".join(result_info_list)
        if len(match_dump_list) == 0:
            utils.print_warn_log(f'There is no dump file for "{self.info.node_name}". Please check the dump path.')
        if result_info_list and result_info_list[-1]:
            dump_file_path, dump_file_name = os.path.split(dump_file)
            utils.print_info_log(
                f"Parse dump file finished, result path is: {self.output_path or os.path.abspath(dump_file_path)}"
            )
        self.info.dump_file = match_dump_list
        self.info.dump_info = result_info


class BigDumpDataParser:
    """
    The class for big dump data parser
    """

    def __init__(self: any, dump_file_path: str) -> None:
        self.dump_file_path = dump_file_path
        self.file_size = 0
        self.header_length = 0
        self.tiling_data = None
        self.parse_dump_so = "libascend_dump_parser.so"
        self.dump_json_data = {}
        self.data_types = ['input', 'output', 'buffer', 'space']

    def parse(self: any):
        """
        Parse the dump file path by big dump data format
        :return: DumpData
        :exception when read or parse file error
        """
        self.check_argument_valid()
        try:
            self._parse_dump_to_json()
            with open(self.dump_file_path, 'rb') as dump_file:
                # read header length
                self._read_header_length(dump_file)
                self._parse_binary_to_json_data(dump_file)
                return self.dump_json_data
        except (OSError, IOError, utils.AicErrException) as io_error:
            utils.print_error_log('Failed to read the dump file %s. %s'
                                  % (self.dump_file_path, str(io_error)))
            raise utils.AicErrException(Constant.MS_AICERR_OPEN_FILE_ERROR) from io_error

    def check_argument_valid(self: any) -> None:
        """
        check argument valid
        :exception when invalid
        """
        utils.check_path_valid(self.dump_file_path, False)
        # get file size
        try:
            self.file_size = os.path.getsize(self.dump_file_path)
        except (OSError, IOError) as error:
            utils.print_error_log(f'get the size of dump file {self.dump_file_path} failed.')
            raise utils.AicErrException(Constant.MS_AICERR_INVALID_DUMP_DATA_ERROR) from error
        if self.file_size <= ConstManager.UINT64_SIZE:
            utils.print_warn_log(
                'The size of %s must be greater than %d, but the file size'
                ' is %d. Please check the dump file.'
                % (self.dump_file_path, ConstManager.UINT64_SIZE, self.file_size))
            raise utils.AicErrException(Constant.MS_AICERR_INVALID_DUMP_DATA_ERROR)
        if self.file_size > ConstManager.ONE_GB:
            utils.print_warn_log(
                'The size (%d) of %s exceeds 1GB, it may task more time to run, please wait.'
                % (self.file_size, self.dump_file_path))

    def _parse_dump_to_json(self):
        # read header length
        path_dir, file_name = os.path.split(self.dump_file_path)
        json_file = os.path.join(path_dir, file_name + ".json")
        try:
            with open(self.dump_file_path, 'rb') as dump_file:
                binary_data = dump_file.read()
        except (FileNotFoundError, PermissionError) as error:
            utils.print_error_log(str(error))
            raise utils.AicErrException(Constant.MS_AICERR_OPEN_FILE_ERROR)
        try:
            dump_parse_cdll = ctypes.CDLL(self.parse_dump_so)
        except (OSError, IOError) as error:
            utils.print_error_log(str(error))
            raise utils.AicErrException(Constant.MS_AICERR_CONNECT_ERROR)
        data_ptr = ctypes.c_char_p(binary_data)
        res = dump_parse_cdll.ParseDumpProtoToJson(data_ptr, ctypes.c_size_t(len(binary_data)),
                                                   json_file.encode('utf-8'))
        if res != 0 or not os.path.isfile(json_file):
            utils.print_error_log(f"Parse dump file to json failed.")
            raise utils.AicErrException(Constant.MS_AICERR_CONNECT_ERROR)
        try:
            with open(json_file, 'r') as load_f:
                self.dump_json_data = json.load(load_f)
        except (FileNotFoundError, json.JSONDecodeError, PermissionError) as error:
            utils.print_error_log(str(error))
            raise utils.AicErrException(Constant.MS_AICERR_OPEN_FILE_ERROR)
        #  remove json file
        os.remove(json_file)

    def _parse_binary_to_json_data(self, dump_file: BinaryIO):
        used_size = self.header_length + ConstManager.UINT64_SIZE
        for data_type in self.data_types:
            for item in self.dump_json_data.get(data_type, []):
                size = int(item.get('size', 0))
                used_size += size
                if used_size > self.file_size:
                    utils.print_error_log(f'The size of {self.dump_file_path} is invalid, please check the dump file.')
                    raise utils.AicErrException(Constant.MS_AICERR_INVALID_DUMP_DATA_ERROR)
                item['data'] = dump_file.read(size)
                if data_type == 'input' and int(item.get('input_type', 0)) == Constant.TILING_TYPE:
                    self.tiling_data = item['data']

    def _read_header_length(self: any, dump_file: BinaryIO) -> None:
        # read header length
        header_length = dump_file.read(ConstManager.UINT64_SIZE)
        self.header_length = struct.unpack(ConstManager.UINT64_FMT, header_length)[0]
        # check header_length <= file_size - 8
        if self.header_length > self.file_size - ConstManager.UINT64_SIZE:
            utils.print_warn_log(
                'The header content size (%d) of %s must be less than or'
                ' equal to %d (file size) - %d (header length).'
                ' Please check the dump file.'
                % (self.header_length, self.dump_file_path, self.file_size, ConstManager.UINT64_SIZE))
            raise utils.AicErrException(Constant.MS_AICERR_INVALID_DUMP_DATA_ERROR)
        dump_file.read(self.header_length)
