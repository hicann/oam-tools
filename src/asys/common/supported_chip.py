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

import re
from common import DeviceInfo, ChipHandler


class CommandSupportedChipBase:
    """支持的芯片基类"""

    SUPPORTED_CHIP_TYPE = []

    def __init__(self) -> None:
        self.device = DeviceInfo()

    def get_supported_chip_info(self, device_id):
        chip_info = self.device.get_chip_info(device_id)
        if any(re.search(rf"{i}", chip_info) for i in self.SUPPORTED_CHIP_TYPE):
            return True, chip_info
        return False, chip_info
    

class AsysConfigSupportedChip(CommandSupportedChipBase):
    """AsysConfig支持的芯片类型"""

    SUPPORTED_CHIP_TYPE = ChipHandler().get_support_chip_regex_list()


class AsysDiagnoseSupportedChip(CommandSupportedChipBase):
    """AsysDiagnose支持的芯片类型"""

    SUPPORTED_CHIP_TYPE = ChipHandler().get_support_chip_regex_list()


class AsysProfilingSupportedChip(CommandSupportedChipBase):
    """AsysProfiling支持的芯片类型"""

    SUPPORTED_CHIP_TYPE = ChipHandler().get_support_chip_regex_list()