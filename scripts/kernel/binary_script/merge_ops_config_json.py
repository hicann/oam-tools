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
import sys
import glob
import json


def read_json_file(file_path):
    try:
        with open(file_path, "r", encoding='utf-8') as f:
            data = json.load(f)
            return data
    except Exception as e:
        print(f"read file {file_path} failed, exception:{e}")
        raise e


def write_json_file(file_path, merged_data):
    if not merged_data:
        return
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"write file {file_path} failed, exception:{e}")
        raise e


def merge_json_files(config_path):
    pattern = os.path.join(config_path, "*.json")
    files = glob.glob(pattern)
    result_file = os.path.join(config_path, os.path.basename(config_path) + "_binary.json")
    if result_file in files:
        files.remove(result_file)
    print("ops config files:", result_file)
    merged_data = {}
    for file in files:
        data = read_json_file(file)
        if "op_type" not in data:
            continue

        op_type = data["op_type"]
        if "op_type" not in merged_data:
            merged_data["op_type"] = op_type
            merged_data["op_list"] = []
        elif merged_data["op_type"] != op_type:
            other_op_type = merged_data["op_type"]
            raise RuntimeError(f"in dir:{config_path} have different op config [{op_type} vs {other_op_type}].")
        if "op_list" in data:
            op_list = data["op_list"]
            if op_list:
                merged_data["op_list"].extend(op_list)

    write_json_file(result_file, merged_data)

if __name__ == "__main__":
    if len(sys.argv) <= 1:
        print(f"usage: {sys.argv[0]} config_path")
        sys.exit(1)
    config_dir = sys.argv[1]
    merge_json_files(config_dir)
