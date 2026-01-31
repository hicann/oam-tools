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
The file mainly involves test single op func.
Copyright Information:
Huawei Technologies Co., Ltd. All Rights Reserved © 2024
"""

from ms_interface.single_op_test_frame.single_op_case import SingleOpCase

config = {
    "cce_file": "/yourpath/te_gatherv2_8241ce80d37e6d97ac20a118920e96111fd0f4f0877012278629ce7d5d4c7d4b_1.cce",
    "bin_path": "/yourpath/te_gatherv2_8241ce80d37e6d97ac20a118920e96111fd0f4f0877012278629ce7d5d4c7d4b_1.o",
    "json_path": "/yourpath/te_gatherv2_8241ce80d37e6d97ac20a118920e96111fd0f4f0877012278629ce7d5d4c7d4b_1.json",
    "tiling_data": "/yourpath/te_gatherv2_8241ce80d37e6d97ac20a118920e96111fd0f4f0877012278629ce7d5d4c7d4b_tiling.bin",
    "tiling_key": "0",
    "block_dim": 32,
    "device_id": 0,
    "ffts_addrs_num": 0,
    "input_file_list": [
        "/yourpath/te_gatherv2_8241ce80d37e6d97ac20a118920e96111fd0f4f0877012278629ce7d5d4c7d4b_1.input.0.npy",
        "/yourpath/te_gatherv2_8241ce80d37e6d97ac20a118920e96111fd0f4f0877012278629ce7d5d4c7d4b_1.input.1.npy",
        "/yourpath/te_gatherv2_8241ce80d37e6d97ac20a118920e96111fd0f4f0877012278629ce7d5d4c7d4b_1.input.2.npy"
    ],
    "output_file_list": [
        "/yourpath/te_gatherv2_8241ce80d37e6d97ac20a118920e96111fd0f4f0877012278629ce7d5d4c7d4b_1.output.0.npy"
    ],
    "kernel_name": "te_gatherv2_8241ce80d37e6d97ac20a118920e96111fd0f4f0877012278629ce7d5d4c7d4b_1",
    "compile_temp_dir": "temp_20250331132228"
}
OP_TEST = "single_op"
SingleOpCase.run(config, OP_TEST)
