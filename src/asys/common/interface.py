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
from threading import Thread

from common import log_error, log_warning
from common import RetCode
from common.const import DETECT_DEFAULT_TIMEOUT, CPU_DETECT_ERROR_CODE_MIN, CPU_DETECT_ERROR_CODE_MAX, ScreenResult
from params import ParamDict

ERROR_DEVICE_ID = -1


class AmlStressDtestctType(ctypes.Structure):
    _fields_ = [
        ('STRESS_DETECT_ALL', ctypes.c_int),
        ('STRESS_DETECT_TYPE_MAX', ctypes.c_int)
    ]


class AmlStressDetectInfo(ctypes.Structure):
    _fields_ = [
        ('type', AmlStressDtestctType)
    ]


def get_devices_master_id(device_obj, all_devices):
    if len(all_devices) == 1:
        return {all_devices[0]: all_devices[0]}  # logic_id: master_id

    ret = dict()
    for idx in all_devices:
        phy_id = device_obj.get_phyid_from_logicid(idx)
        if phy_id == RetCode.FAILED:
            ret[idx] = ERROR_DEVICE_ID
            continue
        master_id = device_obj.get_masterid_from_phyid(phy_id)
        if master_id == RetCode.FAILED:
            ret[idx] = ERROR_DEVICE_ID
            continue
        ret[idx] = master_id
    return ret


def run_stress_detect(device_id, device_obj, ret):
    info = AmlStressDetectInfo()
    info.type.STRESS_DETECT_ALL = 0

    try:
        ret_code = device_obj.ascend_ml.AmlStressDetect(ctypes.c_int32(device_id), ctypes.byref(info))
    except Exception as e:
        log_error(f"Run stress_detect failed, error_msg: {e}")
        ret_code = None

    if ret_code == 0:
        ret[device_id] = ScreenResult.PASS.value
    else:
        ret[device_id] = ScreenResult.WARN.value
    return ret_code


def run_hbm(device_id, device_obj, ret):
    if device_id == ERROR_DEVICE_ID:
        ret[device_id] = [ScreenResult.WARN.value, "0"]
        return ret
    timeout = ParamDict().get_arg("timeout")
    if timeout is False:
        timeout = DETECT_DEFAULT_TIMEOUT

    # 1: detect once, 0: detect by timeout
    hbm_type = 1 if timeout == 0 else 0

    hbm_ecc_before = device_obj.get_ecc_isolated_page(device_id)
    if isinstance(hbm_ecc_before, int) and hbm_ecc_before < 0:
        device_obj.clear_ecc_isolated(device_id)
        hbm_ecc_before = 0
    try:
        ret_code = device_obj.ascend_ml.AmlHbmDetectWithType(
            ctypes.c_int32(device_id), ctypes.c_uint32(timeout), ctypes.c_uint32(hbm_type)
        )
    except Exception as e:
        log_error(f"Run hbm detect failed, error_msg: {e}")
        ret_code = None
    hbm_ecc_after = device_obj.get_ecc_isolated_page(device_id)
    if hbm_ecc_before == "-" or hbm_ecc_after == "-":
        log_warning("The statistics of all uncorrectable ECC errors in the lifecycle cannot be queried.")
        hbm_ecc_count = "-"
    else:
        hbm_ecc_count = hbm_ecc_after - hbm_ecc_before
    if ret_code == 0:
        ret[device_id] = [ScreenResult.PASS.value, str(hbm_ecc_count)]
    else:
        ret[device_id] = [ScreenResult.WARN.value, "0"]
    return ret_code


def run_cpu(device_id, device_obj, ret):
    if device_id == ERROR_DEVICE_ID:
        ret[device_id] = ScreenResult.WARN.value
        return ret
    timeout = ParamDict().get_arg("timeout")
    if timeout is False:
        timeout = DETECT_DEFAULT_TIMEOUT

    try:
        ret_code = device_obj.ascend_ml.AmlCpuDetect(ctypes.c_int32(device_id), ctypes.c_uint32(timeout))
    except Exception as e:
        log_error(f"Run cpu detect failed, error_msg: {e}")
        ret_code = None

    if ret_code == 0:
        ret[device_id] = ScreenResult.PASS.value
    elif ret_code and CPU_DETECT_ERROR_CODE_MIN <= ret_code <= CPU_DETECT_ERROR_CODE_MAX:
        ret[device_id] = ScreenResult.FAIL.value
    else:
        ret[device_id] = ScreenResult.WARN.value
    return ret_code


def run_diagnose(device_obj, diagnose_devices, run_mode):
    """Multi-thread parallel execution"""

    threads = []
    ret = {}

    if run_mode == "hbm_detect":
        _target_func = run_hbm
    elif run_mode == "cpu_detect":
        _target_func = run_cpu
    else:
        _target_func = run_stress_detect

    for device_id in diagnose_devices:
        # new thread
        t = Thread(target=_target_func, args=(device_id, device_obj, ret), daemon=True)
        t.start()
        threads.append(t)

    # wait for all threads to end.
    for t in threads:
        t.join()

    return ret
