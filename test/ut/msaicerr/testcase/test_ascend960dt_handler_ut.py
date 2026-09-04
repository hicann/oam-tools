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

from conftest import MSAICERR_PATH, CommonAssert

sys.path.append(MSAICERR_PATH)

from ms_interface.ascend960dt.ascend960dt_handler import Ascend960dtHandler
from ms_interface.ascend_handler import AscendHandlerBase


class TestAscend960dtHandlerMethods(CommonAssert):
    def test_class_is_subclass_of_ascend_handler_base(self):
        assert issubclass(Ascend960dtHandler, AscendHandlerBase)

    def test_handle_chip_pre_value(self):
        self.assertEqual(Ascend960dtHandler.handle_chip_pre, "Ascend960DT")

    def test_is_chip_handler_match(self):
        handler = Ascend960dtHandler()
        result = handler.is_chip_handler("Ascend960DT")
        assert result

    def test_is_chip_handler_no_match(self):
        handler = Ascend960dtHandler()
        result = handler.is_chip_handler("Ascend910B1")
        assert not result

    def test_is_chip_handler_partial_match(self):
        handler = Ascend960dtHandler()
        result = handler.is_chip_handler("Ascend960DTB1")
        assert result

    def test_instance_of_ascend_handler_base(self):
        handler = Ascend960dtHandler()
        assert isinstance(handler, AscendHandlerBase)
