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
"""Verify MatmulLeakyRelu output against golden data."""

import logging
import math
import struct
import sys
from pathlib import Path


RTOL = 1e-6
ATOL = 1e-5
LOG_FORMAT = "%(message)s"


def main():
    if len(sys.argv) != 3:
        logging.error("Usage: verify_result.py output.bin golden.bin")
        return 2

    output_path = Path(sys.argv[1])
    golden_path = Path(sys.argv[2])
    output = output_path.read_bytes()
    golden = golden_path.read_bytes()
    if len(output) != len(golden):
        logging.error("size mismatch: output=%d, golden=%d", len(output), len(golden))
        return 1

    count = len(output) // 4
    bad = 0
    max_abs = 0.0
    first_bad = None
    for index in range(count):
        offset = index * 4
        output_value = struct.unpack_from("<f", output, offset)[0]
        golden_value = struct.unpack_from("<f", golden, offset)[0]
        diff = abs(output_value - golden_value)
        max_abs = max(max_abs, diff)
        if not math.isclose(output_value, golden_value, rel_tol=RTOL, abs_tol=ATOL):
            bad += 1
            if first_bad is None:
                first_bad = (index, output_value, golden_value, diff)

    logging.info("checked=%d, bad=%d, max_abs=%s", count, bad, max_abs)
    if first_bad is not None:
        index, output_value, golden_value, diff = first_bad
        logging.error(
            "first_bad: index=%d, output=%s, golden=%s, abs_diff=%s",
            index,
            output_value,
            golden_value,
            diff,
        )
    if bad == 0 and count > 0:
        logging.info("test pass!")
        return 0
    return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    raise SystemExit(main())
