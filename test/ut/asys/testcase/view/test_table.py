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

import sys

import pytest

from testcase.conftest import ASYS_SRC_PATH

sys.path.insert(0, ASYS_SRC_PATH)

from common.const import MAX_CHAR_LINE
from view.table import generate_report


@pytest.mark.parametrize("split_line", [False, True])
def test_generate_report_wraps_long_cells_without_data_loss(split_line):
    long_error = "".join(f"{index:03d}" for index in range(85))
    report = generate_report(
        [["ERROR CODE", "ERROR MESSAGE"]],
        {"none": [["E0001", long_error]]},
        split_line=split_line,
    )
    lines = [line for line in report.splitlines() if line]
    column_width = MAX_CHAR_LINE + 5
    chunks = [
        long_error[index:index + column_width]
        for index in range(0, len(long_error), column_width)
    ]

    assert len(long_error) == 255
    assert len({len(line) for line in lines}) == 1
    assert len(chunks) == 3
    assert all(chunk in report for chunk in chunks)
    chunk_positions = [report.index(chunk) for chunk in chunks]
    assert chunk_positions == sorted(chunk_positions)


@pytest.mark.parametrize("cell_length", range(MAX_CHAR_LINE + 1, MAX_CHAR_LINE + 6))
def test_generate_report_keeps_cells_within_final_column_width_on_one_line(cell_length):
    boundary = "x" * cell_length
    report = generate_report(
        [["ERROR CODE", "ERROR MESSAGE"]],
        {"none": [["E0001", boundary]]},
    )

    assert report.count(boundary) == 1


def test_generate_report_wraps_long_group_names_without_data_loss():
    group_name = "group-" + "x" * (MAX_CHAR_LINE + 12)
    report = generate_report(
        [["ERROR CODE", "ERROR MESSAGE"]],
        {group_name: [["E0001", "ok"]]},
    )
    lines = [line for line in report.splitlines() if line]
    group_label = "--" + group_name
    column_width = MAX_CHAR_LINE + 5
    chunks = [
        group_label[index:index + column_width]
        for index in range(0, len(group_label), column_width)
    ]

    assert len({len(line) for line in lines}) == 1
    assert len(chunks) == 2
    assert all(chunk in report for chunk in chunks)
