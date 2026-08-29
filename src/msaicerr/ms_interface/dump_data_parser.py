#!/usr/bin/env python
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
import importlib
import csv
import json
import os
import random
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
        '3': 'int8',
        '4': 'uint8',
        '5': 'int16',
        '6': 'uint16',
        '7': 'int32',
        '8': 'int64',
        '9': 'uint32',
        '10': 'uint64',
        '11': 'bool',
        '12': 'float64',
        '16': 'complex64',
        '17': 'complex128',
        # below dtype is not supported in native numpy
        '0': 'undefined',
        '13': 'string',
        '14': 'dual_sub_int8',
        '15': 'dual_sub_uint8',
        '18': 'qint8',
        '19': 'qint16',
        '20': 'qint32',
        '21': 'quint8',
        '22': 'quint16',
        '23': 'resource',
        '24': 'string_ref',
        '25': 'dual',
        '26': 'variant',
        '27': 'bfloat16',
        '28': 'int4',
        '29': 'uint1',
        '30': 'int2',
        '31': 'uint2',
        '32': 'complex32',
        '33': 'hifloat8',
        '34': 'float8_e5m2',
        '35': 'float8_e4m3fn',
        '36': 'float8_e8m0',
        '37': 'float6_e3m2',
        '38': 'float6_e2m3',
        '39': 'float4_e2m1',
        '40': 'float4_e1m2',
        '41': 'hifloat4',
        '42': 'hifloat4_scale'
    }

    COMMON_DTYPE = ["float32", "float16", "bfloat16", "int32", "int64"]
    VALID_DTYPES = list(DATA_TYPE_TO_DTYPE_MAP.values())
    # dtypes numpy can represent by itself, data of these dtypes is saved as .npy
    NUMPY_NATIVE_DTYPES = {
        'float32', 'float16', 'float64', 'int8', 'uint8', 'int16', 'uint16',
        'int32', 'uint32', 'int64', 'uint64', 'bool', 'complex64', 'complex128'
    }
    # dtypes numpy can represent once the third party extension is imported
    NUMPY_EXT_DTYPES = {'bfloat16'}


class DumpDataParser:
    """
    The class for dump data parser
    """

    def __init__(self, dump_path, info: AicErrorInfo, dest_dtype="", output_path=""):
        self.dump_path = dump_path
        self.info = info
        self.input_data_list = []
        self.output_data_list = []
        self.workspace_data_list = []
        self.bin_data_list = []
        self.dfx_message = ""
        self.output_path = os.path.realpath(output_path) if output_path else ''
        self.parse_types = ['input', 'output', 'space']
        self.dest_dtype = dest_dtype

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
    def _register_ext_dtype():
        """
        Import bfloat16ext for its side effect: registering bfloat16 in numpy.
        Any code doing astype("bfloat16") must call this first, otherwise numpy
        raises TypeError: data type 'bfloat16' not understood.
        @return: True when the dtype is available
        """
        try:
            # 仅为触发 numpy dtype 注册（副作用导入），不需要绑定名字
            importlib.import_module("bfloat16ext")
            return True
        except ImportError:
            return False

    @staticmethod
    def _to_numpy_dtype(dtype):
        """
        Convert a dump dtype name to the matching numpy dtype.
        @param dtype: the dtype name, may be None or a dtype numpy does not support
        @return: the numpy dtype, or None when numpy can not represent it
        """
        if not dtype:
            return None
        if dtype in ConstManager.NUMPY_EXT_DTYPES:
            if not DumpDataParser._register_ext_dtype():
                return None
        elif dtype not in ConstManager.NUMPY_NATIVE_DTYPES:
            return None
        try:
            return np.dtype(dtype)
        except TypeError:
            return None

    @staticmethod
    def _check_tensor_data(parse_type, index, array, dtype):
        np_dtype = DumpDataParser._to_numpy_dtype(dtype)
        if np_dtype is None:
            return f"Can not read with dtype {dtype}!\n"
        # bfloat16 has no finfo, check its value range as float32
        data_dtype = np.float32 if dtype == "bfloat16" else np_dtype
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
                    # 0. astype("bfloat16") 依赖 bfloat16ext 注册该 dtype，未注册会抛 TypeError
                    DumpDataParser._register_ext_dtype()
                    # 1. 以int16读取，纯粹的字节拷贝，不会触发溢出异常
                    raw_data = np.fromfile(tensor_file, dtype=np.int16)
                    # 2. 先转为float32处理
                    data_f32 = raw_data.astype(np.float32)
                    # 3. 手动设置数值边界3.3895e+38，防止无法表示的值
                    bf16_limit = 3.3895e+38
                    data_f32 = np.clip(data_f32, -bf16_limit, bf16_limit)
                    # 4. 转回bfloat16， 因为clip过，所以不会触发bfloat16 overflow导致的段错误
                    arr = data_f32.astype("bfloat16")
                else:
                    arr = np.fromfile(tensor_file, dtype=np.dtype(dtype))
                if arr.size == 0:
                    result_info += "Max: N/A, Min: N/A, Mean: N/A, Std: N/A\n"
                else:
                    mean_val = np.mean(arr, dtype=np.float64)
                    std_val = np.std(arr, dtype=np.float64)
                    result_info += f"Max: {np.max(arr)}, Min: {np.min(arr)}, Mean: {mean_val}, Std: {std_val}\n"
            except (ValueError, TypeError, OSError):
                result_info += f"Can not read with dtype {dtype}!\n"
        return result_info

    @staticmethod
    def _summary_tensor_array(array, dtype):
        """
        Build the summary of an array whose dtype is already known.
        @param array: the typed numpy array
        @param dtype: the dtype name
        @return: the summary text
        """
        result_info = " " * 4 + f"If dtype is {dtype}, summary is: "
        try:
            if array.size == 0:
                return result_info + "Max: N/A, Min: N/A, Mean: N/A, Std: N/A\n"
            # complex data can not be accumulated as float64 without losing the imaginary part
            acc_dtype = np.complex128 if np.iscomplexobj(array) else np.float64
            mean_val = np.mean(array, dtype=acc_dtype)
            std_val = np.std(array, dtype=acc_dtype)
            return result_info + (f"Max: {np.max(array)}, Min: {np.min(array)}, "
                                  f"Mean: {mean_val}, Std: {std_val}\n")
        except (ValueError, TypeError, OSError):
            # only swallow normal errors here, KeyboardInterrupt/SystemExit must propagate
            return result_info + f"Can not read with dtype {dtype}!\n"

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
        with open(self.info.json_file, encoding='utf-8') as json_file:
            json_data = json.load(json_file)
        inputs_data = json_data.get('supportInfo', {}).get('inputs', [])
        outputs_data = json_data.get('supportInfo', {}).get('outputs', [])
        if inputs_data:
            self._collect_dtype_get_json_dtypes(inputs_data, json_dtypes['input'])
        if outputs_data:
            self._collect_dtype_get_json_dtypes(outputs_data, json_dtypes['output'])
        return json_dtypes

    @staticmethod
    def _get_item_dtype(item, parse_type, json_dtype, index):
        """
        Get the dtype name of one dump item.
        @return: the dtype name, or the raw data_type enum value when it is unknown
        """
        if parse_type == "workspace":
            return "int8"
        data_type = str(item.get('data_type', '0'))
        dtype = ConstManager.DATA_TYPE_TO_DTYPE_MAP.get(data_type)
        # "undefined" carries no dtype, the json dtype is more accurate than it
        if dtype and dtype != 'undefined':
            return dtype
        # fall back to the json dtype, else keep the mapped name or the raw enum value
        return json_dtype.get(parse_type, {}).get(index) or dtype or data_type

    @staticmethod
    def _build_typed_array(raw_data, dtype, shape):
        """
        Build the numpy array of the dump data.
        @return: (array, numpy dtype). The numpy dtype is None when the data can only
                 be read as raw bytes, in that case the array is an int8 array.
        """
        array = np.frombuffer(raw_data or b'', dtype=np.int8)
        np_dtype = DumpDataParser._to_numpy_dtype(dtype)
        if np_dtype is None or array.nbytes % np_dtype.itemsize != 0:
            return array, None
        array = array.view(np_dtype)
        if shape and array.size == int(np.prod(shape)):
            array = array.reshape(shape)
        return array, np_dtype

    def _load_name_mapping(self):
        """
        Load the {original name: renamed name} mapping written by the dump framework.
        @return: the mapping, empty when there is no mapping.csv beside the dump files
        """
        return utils.parse_name_mapping_csv(os.path.join(self.dump_path, Constant.MAPPING_CSV_FILE))

    @staticmethod
    def _gen_random_numeric_name(file_dir, suffix):
        # 与异常dump框架一致，用随机数字串命名，保留后缀以便下游按扩展名读取
        while True:
            name = str(random.randint(10 ** 15, 10 ** 16 - 1)) + suffix
            if not os.path.exists(os.path.join(file_dir, name)):
                return name

    @staticmethod
    def _record_mapping(file_dir, renamed, original_name):
        # 追加一行 {映射后随机数字串},{映射前文件名} 到同级mapping.csv
        mapping_csv = os.path.join(file_dir, Constant.MAPPING_CSV_FILE)
        with open(mapping_csv, 'a', newline='', encoding='utf-8') as csv_file:
            csv.writer(csv_file).writerow([renamed, original_name])

    def _check_file_name_len(self, dst_file_name):
        # NAME_MAX是字节上限，多字节文件名下需按编码后的字节数判断
        if len(os.fsencode(os.path.basename(dst_file_name))) <= Constant.MAX_FILE_NAME_LEN:
            return dst_file_name
        file_dir, file_name = os.path.split(dst_file_name)
        _, suffix = os.path.splitext(file_name)
        renamed = self._gen_random_numeric_name(file_dir, suffix)
        self._record_mapping(file_dir, renamed, file_name)
        utils.print_warn_log(f"The output file name is too long, rename {file_name} to {renamed}.")
        return os.path.join(file_dir, renamed)

    def _build_dst_file_name(self, dump_file_path, parse_type, index, dtype, np_dtype):
        name_parts = [self.info.kernel_name, parse_type, str(index)]
        if dtype:
            name_parts.append(dtype)
        # numpy supported dtype is saved as npy, others keep the raw bin format
        name_parts.append("npy" if np_dtype is not None else "bin")
        return self._check_file_name_len(os.path.join(dump_file_path, ".".join(name_parts)))

    def _save_array(self, array, dst_file_name, parse_type, np_dtype):
        if np_dtype is not None:
            # the name built by _build_dst_file_name already ends with .npy
            np.save(dst_file_name, array)
        else:
            array.tofile(dst_file_name)
        if parse_type == "workspace":
            self.workspace_data_list.append(dst_file_name)
        else:
            self.bin_data_list.append(dst_file_name)
        return dst_file_name

    def _parse_one_item(self, item, parse_type, json_dtype, index, dump_file_path):
        dtype = self._get_item_dtype(item, parse_type, json_dtype, index)
        shape = [int(i) for i in item.get('shape', {}).get('dim', [])]
        result_info = (f"shape: {tuple(shape)} size: {item.get('size', 0)} "
                       f"dtype: {dtype if dtype else 'unknown'}\n")

        array, np_dtype = self._build_typed_array(item.get('data'), dtype, shape)
        dst_file_name = self._build_dst_file_name(dump_file_path, parse_type, index, dtype, np_dtype)
        dst_file_name = self._save_array(array, dst_file_name, parse_type, np_dtype)
        result_info += f'{dst_file_name}\n'

        if np_dtype is not None:
            result_info += self._check_tensor_data(parse_type, index, array, dtype)
            result_info += self._summary_tensor_array(array, dtype)
        elif self._to_numpy_dtype(dtype) is not None:
            # numpy knows the dtype but the byte count is not aligned to its itemsize,
            # read the raw bin with that dtype as before
            result_info += self._summary_tensor_without_dtype(dst_file_name, dtype)
        else:
            # keep the "Can not read with dtype x" hint carrying the real dtype, users
            # rely on it to know which third party library to install
            if dtype and dtype != 'undefined':
                result_info += self._summary_tensor_without_dtype(dst_file_name, dtype)
            # then guess the summary by the common dtypes
            result_info += self._summary_tensor_without_dtype(dst_file_name, None)
        return result_info

    def _save_data_to_bin_file(self, dump_json_data, parse_type, json_dtype, dump_file):
        dump_file_path, dump_file_name = os.path.split(dump_file)
        dump_file_path = self.output_path or dump_file_path
        items = dump_json_data.get(parse_type)
        if not items:
            utils.print_warn_log(f'There is no {parse_type} in {dump_file_name}.')
            return ''

        if not self.info.kernel_name:
            self.info.kernel_name = dump_file_name
        # "space" is dumped as the workspace of the kernel
        parse_type = "workspace" if parse_type == "space" else parse_type

        result_info_list = []
        for index, item in enumerate(items):
            try:
                result_info_list.append(
                    self._parse_one_item(item, parse_type, json_dtype, index, dump_file_path))
            except (TypeError, ValueError, IOError, OSError, MemoryError) as error:
                utils.print_error_log(f'Failed to parse the data of {parse_type}:{index} of "{dump_file}". {error}')
                raise utils.AicErrException(Constant.MS_AICERR_INVALID_DUMP_DATA_ERROR)
        return "".join(result_info_list)

    def convert_bin_file_to_npy(self):
        result_info = ''
        if not self.dest_dtype:
            result_info += "Need to specify the dtype when convert a bin file."
            utils.print_error_log(result_info)
            return result_info

        if self.dest_dtype not in ConstManager.VALID_DTYPES:
            result_info += f"Invalid dest_dtype: {self.dest_dtype}, valid types are {ConstManager.VALID_DTYPES}"
            utils.print_error_log(result_info)
            return result_info

        self.dump_path = os.path.abspath(self.dump_path)
        dump_file_dir, dump_file_name = os.path.split(self.dump_path)
        file_base_name = os.path.splitext(dump_file_name)[0]
        original_dtype = None
        for dtype in ConstManager.VALID_DTYPES:
            if f".{dtype}" in file_base_name:
                original_dtype = dtype
                break

        if original_dtype and original_dtype != self.dest_dtype:
            result_info += (
                f"Warning: Original bin file dtype {original_dtype} is different from dest_dtype {self.dest_dtype}. "
                f"Will process with dest_dtype {self.dest_dtype} as specified."
            )
            utils.print_info_log(result_info)

        output_dir = self.output_path or dump_file_dir
        os.makedirs(output_dir, exist_ok=True)

        for dtype in ConstManager.VALID_DTYPES:
            if f".{dtype}" in file_base_name:
                file_base_name = file_base_name.replace(f".{dtype}", "")
        npy_file_name = f"{file_base_name}.{self.dest_dtype}.npy"
        npy_file_path = os.path.join(output_dir, npy_file_name)

        if self.dest_dtype == "bfloat16" and not DumpDataParser._register_ext_dtype():
            # astype("bfloat16") 依赖 bfloat16ext 注册该 dtype，未注册会抛 TypeError。
            # 本路径（-d xxx.bin -dtype bfloat16）不经过 _to_numpy_dtype，须自行注册。
            utils.print_error_log(
                "Can not convert to bfloat16: the bfloat16ext module is not installed.")
            raise utils.AicErrException(Constant.MS_AICERR_INVALID_DUMP_DATA_ERROR)

        try:
            if self.dest_dtype == "bfloat16":
                raw_data = np.fromfile(self.dump_path, dtype=np.int16)
                data_f32 = raw_data.astype(np.float32)
                bf16_limit = 3.3895e+38
                data_f32 = np.clip(data_f32, -bf16_limit, bf16_limit)
                array = data_f32.astype("bfloat16")
            else:
                array = np.fromfile(self.dump_path, dtype=np.dtype(self.dest_dtype))

            np.save(npy_file_path, array)
            utils.print_info_log(f"Success convert bin to npy: {self.dump_path} -> {npy_file_path}")
            self.bin_data_list.append(npy_file_path)

        except Exception as e:
            utils.print_error_log(f"Failed to convert bin to npy: {str(e)}")
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
        except (OSError, ValueError, TypeError, KeyError, IndexError,
                RuntimeError, utils.AicErrException) as e:
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
            if self.dump_path.endswith(".npy"):
                utils.print_error_log("The dump file cannot be an npy file.")
                return
            elif self.dump_path.endswith(".bin"):
                self.info.dump_info = self.convert_bin_file_to_npy()
                return
            elif self.dest_dtype:
                utils.print_error_log("Invalid parameter: dest_dtype is only valid for bin file conversion.")
                return
            else:
                match_dump_list = [self.dump_path]
        else:
            match_dump_list = []
            match_name = self.info.node_name
            name_mapping = self._load_name_mapping()
            if name_mapping:
                # 超长场景下落盘文件已被重命名，按原始data_name反查随机数字串
                match_name = name_mapping.get(self.info.data_name or self.info.node_name, match_name)
            for top, _, files in os.walk(self.dump_path):
                for name in files:
                    if name == Constant.MAPPING_CSV_FILE:
                        continue
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
            dump_file_path, _ = os.path.split(dump_file)
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
        path_dir, file_name = os.path.split(os.path.abspath(self.dump_file_path))
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
            utils.print_error_log("Parse dump file to json failed.")
            raise utils.AicErrException(Constant.MS_AICERR_CONNECT_ERROR)
        try:
            with open(json_file, 'r', encoding='utf-8') as load_f:
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