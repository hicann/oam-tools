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

import csv
import os

from common import get_project_conf
from ..conftest import AssertTest


def setup_module():
    print("TestDependentPackage ut test start.")  # noqa: T201  # test diagnostic output


def teardown_module():
    print("TestDependentPackage ut test finish.")  # noqa: T201  # test diagnostic output


class TestDependentPackage(AssertTest):
    """
    Check the query commands in conf/dependent_package.csv.

    Every row is "<package>,<shell command>".  The command is executed by
    asys info, so a command whose pipeline does not grep its own package
    name silently drops the package from the " Dependent Packet " table.
    """

    @staticmethod
    def _read_dep_rows():
        dep_file = os.path.join(get_project_conf(), "dependent_package.csv")
        with open(dep_file, "r", encoding="utf-8", newline="") as fp:
            return list(csv.reader(fp))

    def test_dep_csv_exists(self):
        dep_file = os.path.join(get_project_conf(), "dependent_package.csv")
        self.assertTrue(os.path.isfile(dep_file))

    def test_dep_csv_greps_its_own_package(self):
        """
        The second stage of a "dpkg -l <pkg> | ..." pipeline must be
        "grep <pkg>".  Otherwise the bare package name is executed as a
        command by the shell and the package version is never reported.
        """
        bad_rows = []
        for row in self._read_dep_rows():
            if len(row) < 2:
                continue
            package, command = row[0], row[1]
            stages = [stage.strip() for stage in command.split("|")]
            if not stages[0].startswith("dpkg -l"):
                continue
            if len(stages) < 2:
                # A single-stage pipeline never filters the dpkg header rows,
                # so it must be reported like any other malformed command.
                bad_rows.append((package, command))
            elif stages[1] != "grep " + package:
                bad_rows.append((package, stages[1]))
        assert not bad_rows, (
            "the pipeline must grep the package name, but got: {}".format(bad_rows)
        )

    def test_dep_csv_lapack_dev_command(self):
        """
        The liblapack-dev row must filter the dpkg output by the package
        name instead of running the package name as a command.
        """
        commands = {row[0]: row[1] for row in self._read_dep_rows() if len(row) > 1}
        self.assertTrue("liblapack-dev" in commands)
        assert "grep liblapack-dev" in commands["liblapack-dev"], (
            "the liblapack-dev command must grep the package name, but got: {}".format(
                commands["liblapack-dev"]
            )
        )

    def test_dep_csv_rows_are_not_empty(self):
        for row in self._read_dep_rows():
            if not row:
                continue
            self.assertTrue(len(row) >= 2)
            self.assertTrue(row[0].strip() != "")
            self.assertTrue(row[1].strip() != "")
