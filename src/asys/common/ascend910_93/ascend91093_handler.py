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

from threading import Thread
from common.device import DeviceInfo
import common.interface as interface
 
 
class Ascend91093Handler(DeviceInfo):
    def __init__(self):
        super().__init__()
 
    @classmethod
 	def need_lp_param(cls):
 	    return False
 
    def run_diagnose(self, device_obj, diagnose_devices, run_mode):
        """Multi-thread parallel execution"""
        threads = []
        ret = {}
        master_ids = {}
 
        logic_master_info = interface._get_devices_master_id(device_obj, diagnose_devices)
        if run_mode == "hbm_detect":
            _target_func = interface._run_hbm
        elif run_mode == "cpu_detect":
            _target_func = interface._run_cpu
        else:
            return interface.run_diagnose(device_obj, diagnose_devices, run_mode)
 
        for device_id in diagnose_devices:
            if logic_master_info[device_id] not in master_ids:
                # new thread
                t = Thread(target=_target_func, args=(device_id, device_obj, ret), daemon=True)
                t.start()
                threads.append(t)
                master_ids[logic_master_info[device_id]] = device_id
 
        # wait for all threads to end.
        for t in threads:
            t.join()
 
        ret_logic_id = {}
        for device_id in diagnose_devices:
            ret_logic_id[device_id] = ret[master_ids[logic_master_info[device_id]]]
 
        return ret_logic_id