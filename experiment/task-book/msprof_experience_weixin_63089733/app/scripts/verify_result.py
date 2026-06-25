#!/usr/bin/python3
# coding=utf-8

# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.
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

"""比对 NPU 算子输出与 golden,按相对误差判定精度是否达标。"""

import argparse
import logging

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(message)s")
LOG = logging.getLogger("verify")

# 单点相对误差阈值;超过此值的元素计为 mismatch
POINTWISE_REL_THRESHOLD = 1e-3
# 允许的 mismatch 比例上限
MAX_MISMATCH_FRACTION = 1e-4
# 防止除零的下限
EPS = 1e-9
# 打印 mismatch 明细的最大条数
MAX_REPORT = 100


def load_fp16(path):
    return np.fromfile(path, dtype=np.float16).astype(np.float32)


def pointwise_rel_error(actual, golden):
    denom = np.maximum(np.abs(golden), EPS)
    return np.abs(actual - golden) / denom


def report_mismatches(rel_error, actual, golden):
    bad_positions = np.flatnonzero(rel_error > POINTWISE_REL_THRESHOLD)
    for shown, pos in enumerate(bad_positions):
        if shown >= MAX_REPORT:
            break
        LOG.info(
            "pos=%06d golden=%.9f actual=%.9f rel=%.6f",
            pos, golden[pos], actual[pos], rel_error[pos])
    return bad_positions.size


def check_accuracy(actual_path, golden_path):
    actual = load_fp16(actual_path)
    golden = load_fp16(golden_path)
    if actual.size != golden.size:
        LOG.error("size mismatch: actual=%d golden=%d", actual.size, golden.size)
        return False

    rel_error = pointwise_rel_error(actual, golden)
    mismatch_count = report_mismatches(rel_error, actual, golden)
    mismatch_fraction = mismatch_count / golden.size
    LOG.info(
        "mismatch=%d/%d fraction=%.6f limit=%.6f",
        mismatch_count, golden.size, mismatch_fraction, MAX_MISMATCH_FRACTION)
    return mismatch_fraction <= MAX_MISMATCH_FRACTION


def main():
    parser = argparse.ArgumentParser(description="verify operator output against golden")
    parser.add_argument("actual", help="operator output binary (fp16)")
    parser.add_argument("golden", help="golden binary (fp16)")
    args = parser.parse_args()

    if check_accuracy(args.actual, args.golden):
        LOG.info("test pass!")
        return 0
    LOG.error("test failed: accuracy out of tolerance")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
