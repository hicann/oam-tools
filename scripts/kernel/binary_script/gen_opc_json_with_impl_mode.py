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
gen_opc_json_with_impl_mode.py
"""
import sys
import os
import json
from binary_util.util import wr_json


def main(ori_json, new_json, impl_mole):
    """
    gen output json by binary_file and opc json file
    """
    if not os.path.exists(ori_json):
        print("[ERROR]the ori_json doesnt exist")
        return False
    with open(ori_json, "r") as file_wr:
        binary_json = json.load(file_wr)

    op_list = binary_json.get("op_list", list())
    for idx, bin_list_info in enumerate(op_list):
        bin_filename = bin_list_info.get("bin_filename")
        if bin_filename is None:
            continue
        bin_filename = bin_filename + "_" + impl_mole
        binary_json["op_list"][idx]["bin_filename"] = bin_filename

    wr_json(binary_json, new_json)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])

