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

"""
gen_opcinfo_from_opinfo.py
"""
import sys
import os
import json
import csv


# 'pylint: disable=invalid-name
def convert_to_snake(op_name):
    """
    convert the op name to snake dtype
    the rule if from func GetModeleName in opcompiler/te_fusion/source/fusion_api.cc
    """
    new_name = ""
    sub_head = False
    name_list = list(op_name)
    for _idx, _char in enumerate(name_list):
        if _char.islower():
            sub_head = False
        if _char.isdigit():
            sub_head = True
        if _char.isupper() and _idx != 0:
            if not sub_head:
                new_name += "_"
                sub_head = True
            else:
                _idx_next = _idx + 1
                if _idx_next < len(name_list):
                    if name_list[_idx_next].islower():
                        new_name += "_"
        new_name += _char

    return new_name.lower()


def get_res_from_file(json_file):
    """
    get_res_from_file get the module name and module func from json_file
    """
    if not os.path.exists(json_file):
        print("[ERROR]the json_file is not existed: ", json_file)
        sys.exit(1)
    with open(json_file, "r") as file_op:
        ops_info_json = json.load(file_op)

    output_res = dict()

    for op_type in ops_info_json.keys():
        op_type_info = ops_info_json.get(op_type)
        is_supported_dynamic = op_type_info.get("dynamicShapeSupport")
        if is_supported_dynamic is None:
            is_supported_dynamic = False
        else:
            is_supported_dynamic = is_supported_dynamic.get("flag") == "true"
        if not is_supported_dynamic:
            continue
        op_file = op_type_info.get("opFile")
        op_interface = op_type_info.get("opInterface")
        if op_file is None:
            op_file = convert_to_snake(op_type)
        else:
            op_file = op_file.get("value")
        if op_interface is None:
            op_interface = convert_to_snake(op_type)
        else:
            op_interface = op_interface.get("value")
        op_file = "dynamic/" + op_file + ".py"

        output_res[op_type] = [op_file, op_interface]
    return output_res


if __name__ == '__main__':
    args = sys.argv

    in_file_path_list = list()
    out_csv_file = None

    for arg in args:
        if arg.endswith("json"):
            in_file_path_list.append(arg)
        elif arg.endswith("csv"):
            out_csv_file = arg

    res = dict()
    wr_header = ['op_type', 'file_name', 'file_func']
    wr_data = list()
    for ops_json_file in in_file_path_list:
        _res = get_res_from_file(ops_json_file)
        for _op_type, _op_value in _res.items():
            if _op_type not in res.keys():
                res[_op_type] = _op_value
                file_name = _op_value[0]
                func_name = _op_value[1]
                wr_data.append({wr_header[0]: _op_type, wr_header[1]: file_name, wr_header[2]: func_name})
                continue
            global_op_value = res.get(_op_type)
            if global_op_value != _op_value:
                print("ERROR", global_op_value, _op_value)

    # wr result to output file
    if out_csv_file is not None:
        fd = os.open(out_csv_file, os.O_RDWR | os.O_CREAT, 0o755)
        with os.fdopen(fd, "w+") as f:
            writer = csv.DictWriter(f, wr_header)
            writer.writeheader()
            writer.writerows(wr_data)
