#!/usr/bin/env python3
# coding=utf-8
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
"""Generate deterministic MatmulLeakyRelu input and golden files.

The original asc-devkit sample uses numpy. This task package keeps the
reproducer dependency-light by using only Python standard library.
"""

import os
import struct


M = 1024
N = 640
K = 256


def main():
    os.makedirs("input", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    # IEEE 754 fp16 little-endian: 1.0 = 0x3c00.
    with open("input/x1_gm.bin", "wb") as f:
        f.write(b"\x00\x3c" * (M * K))
    with open("input/x2_gm.bin", "wb") as f:
        f.write(b"\x00\x3c" * (K * N))
    with open("input/bias.bin", "wb") as f:
        f.write(struct.pack("<f", 0.0) * N)

    # A and B are all 1.0, bias is 0, so each output element is K.
    with open("output/golden.bin", "wb") as f:
        f.write(struct.pack("<f", float(K)) * (M * N))


if __name__ == "__main__":
    main()
