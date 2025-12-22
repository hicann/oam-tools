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

from ms_interface.dsmi_interface import DSMIInterface, DsmiChipInfoStru
import sys
from conftest import MSAICERR_PATH
sys.path.append(MSAICERR_PATH)


class TestDsmiInterface:

    def test_get_vector_core_count(self, mocker):
        mocker.patch("ctypes.CDLL")
        dsmi = DSMIInterface()
        assert dsmi.get_vector_core_count(0) == 0

    def test_get_ai_core_count(self, mocker):
        mocker.patch("ctypes.CDLL")
        dsmi = DSMIInterface()
        assert dsmi.get_aicore_count(0) == 0
