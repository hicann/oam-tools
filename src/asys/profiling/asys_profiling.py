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

import os
import subprocess

from common import log_error, log_info
from common.const import MAX_PERIOD, UNKNOWN
from params import ParamDict
from common import AsysProfilingSupportedChip

support_profiling_list = set(["aicore", "dvpp"])


class AsysProfiling():
    def __init__(self):
        self.device_id = ParamDict().get_arg("device_id")
        self.period = ParamDict().get_arg("period", 0)
        self.output_path = ParamDict().get_arg("output")
        self.run_modes = ParamDict().get_arg("run_mode")
        self.aic_metrics = ParamDict().get_arg("aic_metrics", "PipeUtilization")

    def run(self):
        if not self._check_param():
            return False
        ret = True
        for run_mode in self.run_modes:
            func_name = "_run_" + run_mode
            func = getattr(self, func_name, None)
            if func:
                returncode = func()
                if not returncode:
                    log_error(f"Error occurred while running {run_mode}. Check logs for more information.")
                    ret = False
        return ret

    def _check_param(self):
        if self.period < 1 or self.period > MAX_PERIOD:
            log_error("Period is invalid, it should be in [1,2592000].")
            return False

        if not self.output_path:
            log_error("Argument 'output' can not be empty string.")
            return False

        devices = set(self.device_id.split(','))
        try:
            for device in devices:
                if int(device) < 0:
                    log_error("Device id is invalid, run 'asys profiling -h' to get help.")
                    return False
        except ValueError:
            log_error("Device id is invalid, run 'asys profiling -h' to get help.")
            return False

        profiling_supported = AsysProfilingSupportedChip()
        for device in devices:
            ret, _chip_info = profiling_supported.get_supported_chip_info(int(device))
            if ret:
                continue
            elif _chip_info == UNKNOWN:
                log_error(f"device id {device} is invalid, please enter a vaild value.")
                return False
            else:
                log_error(f"The diagnose command does not support {_chip_info}.")
                return False

        self.run_modes = set(self.run_modes.split(','))
        if not self.run_modes.issubset(support_profiling_list):
            log_error("Run mode type is unsupported, run 'asys profiling -h' to get help.")
            return False
        return True

    def _run_aicore(self):
        cmd = (f"msprof --output={self.output_path} --sys-period={str(self.period)} "
                f"--sys-devices={self.device_id} --ai-core=on --aic-mode=sample-based "
                f"--aic-metrics={self.aic_metrics}")
        log_info(f"Start run: {cmd}, please wait about {self.period} seconds.")
        ret = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, encoding='utf-8', env=os.environ)
        if ret.returncode == 0:
            log_info(f"Succeeded in running aicore profiling.\n{ret.stdout}")
        else:
            log_error(f"Failed to run aicore profiling.\n{ret.stdout}")
            return False
        return True

    def _run_dvpp(self):
        cmd = (f"msprof --output={self.output_path} --sys-period={str(self.period)} "
                f"--sys-devices={self.device_id} --dvpp-profiling=on")
        log_info(f"Start run: {cmd}, please wait about {self.period} seconds.")
        ret = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, encoding='utf-8', env=os.environ)
        if ret.returncode == 0:
            log_info(f"Succeeded in running dvpp profiling.\n{ret.stdout}")
        else:
            log_error(f"Failed to run dvpp profiling.\n{ret.stdout}")
            return False
        return True
