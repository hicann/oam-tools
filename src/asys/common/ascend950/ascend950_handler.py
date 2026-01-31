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

import ctypes
from common import log_debug
from common.device import DeviceInfo
from common.device import DsmiNormalMemoryInfoStru, DsmiTagSensorInfo
from common.device import DSMI_MAIN_CMD_MEMORY, DSMI_SUB_CMD_HBM_MEMORY, MEMEORY_CONVERT_RATIO, SOC_TEMP_ID
from common.const import HBM_BANDWIDTH_USE, NOT_SUPPORT
import common.interface as interface
 
 
class Ascend950Handler(DeviceInfo):
    """Ascend950 device info"""
    SHIFT_BIT = 16
    MASK_BIT = 0xFFFF
    OFFSET = 0x0001
    UNSUPPORTED_KEY_WORDS = [NOT_SUPPORT, f"{NOT_SUPPORT}, {NOT_SUPPORT}"]
 
    def __init__(self):
        super().__init__()
       
    @classmethod
    def get_encode_component_one_id(cls, device_id):
        """Get the encoded component1 id, only supported when device_id < 65536."""
        high_value = device_id >> cls.SHIFT_BIT
        if high_value:
            log_debug("Only supports encode component when device_id in [0, 65536)")
            return 0
        return (cls.OFFSET << cls.SHIFT_BIT) | (device_id & cls.MASK_BIT)
 
    @classmethod
    def need_lp_param(cls):
        return True
 
    def get_device_aic_info(self, device_id):
        """get aicore info, adapter to two component feature of ascend 950"""
        aic_c, aic_v0, aic_f0 = super().get_device_aic_info(device_id)
        component_one_id = self.get_encode_component_one_id(device_id)
        aic_v1, aic_f1 = [NOT_SUPPORT, NOT_SUPPORT]
        if component_one_id:
            _, aic_v1, aic_f1 = super().get_device_aic_info(component_one_id)
        return [aic_c, f"{aic_v0}, {aic_v1}", f"{aic_f0}, {aic_f1}"]
 
    def get_device_bus_info(self, device_id):
        """get bus info, adapter to two component feature of ascend 950"""
        bus_v0, ring_f0, cpu_f0, mate_f0, l2_buf_f0 = super().get_device_bus_info(device_id)
        component_one_id = self.get_encode_component_one_id(device_id)
        bus_v1, ring_f1, mate_f1, l2_buf_f1 = [NOT_SUPPORT, NOT_SUPPORT, NOT_SUPPORT, NOT_SUPPORT]
        if component_one_id:
            bus_v1, ring_f1, _, mate_f1, l2_buf_f1 = super().get_device_bus_info(component_one_id)
        return [f"{bus_v0}, {bus_v1}", f"{ring_f0}, {ring_f1}", cpu_f0, 
                f"{mate_f0}, {mate_f1}", f"{l2_buf_f0}, {l2_buf_f1}"]
    
    def get_device_hbm_info(self, device_id):
        """get hbm info, adapter to Ascend950"""
        p_memory_info = ctypes.pointer(DsmiNormalMemoryInfoStru())
        try:
            ret = self.dsmi_handle.dsmi_get_device_info(
                device_id, DSMI_MAIN_CMD_MEMORY, DSMI_SUB_CMD_HBM_MEMORY, 
                p_memory_info, ctypes.pointer(ctypes.c_uint(ctypes.sizeof(DsmiNormalMemoryInfoStru())))
            )
        except AttributeError:
            return [NOT_SUPPORT, NOT_SUPPORT, NOT_SUPPORT, NOT_SUPPORT]
        if not self.check_status(ret, "Get memory info failed!"):
            return [NOT_SUPPORT, NOT_SUPPORT, NOT_SUPPORT, NOT_SUPPORT]
 
        memory_size = p_memory_info.contents.total_size // MEMEORY_CONVERT_RATIO
        usage = p_memory_info.contents.used_size
        bandwidth = self.get_device_utilization_rate(device_id, HBM_BANDWIDTH_USE)
        return [memory_size, round(usage / MEMEORY_CONVERT_RATIO, 2), NOT_SUPPORT, bandwidth]
    
    def get_device_voltage(self, device_id):
        """get aicore max voltage with 950"""
        voltage_value = super().get_device_voltage(device_id)
        return f"{voltage_value}(Max)" if voltage_value != NOT_SUPPORT else NOT_SUPPORT
 
    def get_device_aicore_frequency(self, device_id):
        """get aicore avg frequency with 950"""
        aicore_frequecy = super().get_device_aicore_frequency(device_id)
        return f"{aicore_frequecy}(Avg)" if aicore_frequecy != NOT_SUPPORT else NOT_SUPPORT
 
    def get_device_temperature(self, device_id):
        p_temperature = ctypes.pointer(DsmiTagSensorInfo())
        try:
            ret = self.dsmi_handle.dsmi_get_soc_sensor_info(ctypes.c_int32(device_id), SOC_TEMP_ID, p_temperature)
        except AttributeError:
            return NOT_SUPPORT
        if not self.check_status(ret, "Get temperature info failed"):
            return NOT_SUPPORT
        return p_temperature.contents.iint
 
    def run_diagnose(self, device_obj, diagnose_devices, run_mode):
        return interface.run_diagnose(device_obj, diagnose_devices, run_mode)