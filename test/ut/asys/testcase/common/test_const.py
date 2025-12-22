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
import os
from testcase.conftest import ASYS_SRC_PATH
sys.path.insert(0, ASYS_SRC_PATH)

from common import consts
from ..conftest import AssertTest

def setup_module():
    print("TestConst ut test start.")

def teardown_module():
    print("TestConst ut test finsh.")

class TestConst(AssertTest):

    def test_consts(self, mocker):
        self.assertTrue(consts.help_cmd == "help")
        self.assertTrue(consts.collect_cmd == "collect")
        self.assertTrue(consts.launch_cmd == "launch")
        self.assertTrue(consts.info_cmd == "info")
        self.assertTrue(consts.diagnose_cmd == "diagnose")
        self.assertTrue(consts.analyze_cmd == "analyze")
        self.assertTrue(consts.config_cmd == "config")
        self.assertTrue(consts.health_cmd == "health")
        self.assertTrue(consts.profiling_cmd == "profiling")
        self.assertTrue(consts.cmd_set == ["help", "collect", "launch", "info", "diagnose",
                                             "health", 'analyze', 'config', 'profiling'])

