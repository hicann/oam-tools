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

from ms_interface.ascend910_96.ascend91096_handler import Ascend91096Handler
from ms_interface.ascend_handler import AscendHandlerBase


class TestAscend91096HandlerMethods(CommonAssert):
    def test_class_is_subclass_of_ascend_handler_base(self):
        assert issubclass(Ascend91096Handler, AscendHandlerBase)

    def test_handle_chip_pre_value(self):
        self.assertEqual(Ascend91096Handler.handle_chip_pre, "Ascend910_96")

    def test_is_chip_handler_match(self):
        handler = Ascend91096Handler()
        result = handler.is_chip_handler("Ascend910_96")
        assert result

    def test_is_chip_handler_no_match(self):
        handler = Ascend91096Handler()
        result = handler.is_chip_handler("Ascend910B1")
        assert not result

    def test_is_chip_handler_partial_match(self):
        handler = Ascend91096Handler()
        result = handler.is_chip_handler("Ascend910_96B1")
        assert result

    def test_instance_of_ascend_handler_base(self):
        handler = Ascend91096Handler()
        assert isinstance(handler, AscendHandlerBase)
