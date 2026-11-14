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

# ruff: noqa: E501, S607, PLR0915, PLR6301, PLR1722  # test mock methods, partial paths, long lines

# pylint: disable=protected-access,redefined-outer-name,attribute-defined-outside-init,unused-argument,broad-exception-caught,unused-import,unused-variable,redefined-builtin,reimported,no-member,function-redefined,possibly-used-before-assignment,no-self-argument,too-many-function-args,unexpected-keyword-arg,no-value-for-parameter  # pytest fixture/mock/cleanup patterns

import sys
from pathlib import Path


ASYS_SRC = Path(__file__).resolve().parents[5] / "src" / "asys"
sys.path.insert(0, str(ASYS_SRC))

from collect.coretrace import coretrace_collect  # noqa: E402


def setup_module():
    print("TestCoretraceMissingBinary ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestCoretraceMissingBinary ut test finish.")  # noqa: T201  # test diagnostic output


class TestCoretraceMissingBinary:
    def test_missing_binary_state_is_per_instance(self):
        """
        The already-warned binaries must be tracked per instance. A class
        attribute would suppress the warning for every later analysis in
        the same process.
        """
        first = coretrace_collect.ParseCoreTrace(None)
        second = coretrace_collect.ParseCoreTrace(None)

        first.warn_missing("/opt/lib/libmissing.so")

        assert "/opt/lib/libmissing.so" in first.missing_binary
        assert "/opt/lib/libmissing.so" not in second.missing_binary

    def test_missing_binary_warning_repeated_per_instance(self, caplog):
        """
        Within one instance the same missing binary is deduplicated and
        warns only once.
        """
        parser = coretrace_collect.ParseCoreTrace(None)
        parser.warn_missing("/opt/lib/libmissing.so")
        parser.warn_missing("/opt/lib/libmissing.so")

        warnings = [
            record
            for record in caplog.records
            if "is not exists" in record.getMessage()
        ]
        assert len(warnings) == 1

    def test_missing_binary_warning_for_second_instance(self, caplog):
        """
        The warning state of one analysis must not suppress the warning
        of another analysis in the same process.
        """
        first = coretrace_collect.ParseCoreTrace(None)
        first.warn_missing("/opt/lib/libmissing.so")

        second = coretrace_collect.ParseCoreTrace(None)
        second.warn_missing("/opt/lib/libmissing.so")

        warnings = [
            record
            for record in caplog.records
            if "is not exists" in record.getMessage()
        ]
        assert len(warnings) == 2
