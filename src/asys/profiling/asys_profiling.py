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
from datetime import datetime, timezone

from common import log_error, log_info, log_debug
from common.const import MAX_PERIOD, UNKNOWN
from params import ParamDict
from common import AsysProfilingSupportedChip

support_profiling_list = set(["aicore", "dvpp", "os", "link", "memory", "power"])


class AsysProfiling():
    def __init__(self):
        self.device_id = int(ParamDict().get_arg("device_id"))
        self.period = ParamDict().get_arg("period", 0)
        self.output_path = ParamDict().get_arg("output")
        self.run_modes = ParamDict().get_arg("run_mode")
        self.aic_metrics = ParamDict().get_arg("aic_metrics", "PipeUtilization")

    @staticmethod
    def concat_aicore(self, cmd):
        concat_cmd = f"--ai-core=on --aic-mode=sample-based --aic-metrics={self.aic_metrics}"
        log_debug("Concat aicore command.")
        out_cmd = cmd + " " + concat_cmd
        return out_cmd

    @staticmethod
    def concat_dvpp(self, cmd):
        concat_cmd = "--dvpp-profiling=on"
        log_debug("Concat dvpp command.")
        out_cmd = cmd + " " + concat_cmd
        return out_cmd

    @staticmethod
    def concat_link(self, cmd):
        concat_cmd = "--sys-interconnection-profiling=on --sys-io-profiling=on"
        log_debug("Concat link command.")
        out_cmd = cmd + " " + concat_cmd
        return out_cmd

    @staticmethod
    def concat_memory(self, cmd):
        concat_cmd = "--sys-hardware-mem=on --llc-profiling=on"
        log_debug("Concat memory command.")
        out_cmd = cmd + " " + concat_cmd
        return out_cmd

    @staticmethod
    def concat_os(self, cmd):
        concat_cmd = "--sys-profiling=on"
        log_debug("Concat os command.")
        out_cmd = cmd + " " + concat_cmd
        return out_cmd

    @staticmethod
    def concat_power(self, cmd):
        return cmd

    def run(self):
        if not self._check_param():
            return False
        log_info(f"Run mode is {self.run_modes}.")
        cmd = (f"msprof --output={self.output_path} --sys-period={str(self.period)} "
                f"--sys-devices={self.device_id} ") 
        for run_mode in self.run_modes:
            func_name = "_concat_" + run_mode
            func = getattr(self, func_name, None)
            if func:
                cmd = func(cmd)
        ret = self._run_cmd(cmd)
        return ret

    def _check_param(self):
        if self.period < 1 or self.period > MAX_PERIOD:
            log_error("Period is invalid, it should be in [1,2592000].")
            return False

        profiling_supported = AsysProfilingSupportedChip()
        ret, _chip_info = profiling_supported.get_supported_chip_info(self.device_id)
        if not ret:
            if _chip_info == UNKNOWN:
                log_error(f"device id {device} is invalid, please enter a vaild value.")
                return False
            else:
                log_error(f"The diagnose command does not support {_chip_info}.")
                return False

        self.run_modes = set(self.run_modes.split(','))
        if not self.run_modes.issubset(support_profiling_list):
            log_error("Run mode type is unsupported, run 'asys profiling -h' to get help.")
            return False

        utc_dt = datetime.now(timezone.utc)  # UTC time
        dir_name = utc_dt.astimezone().strftime('%Y%m%d%H%M%S%f')[:-3]
        if not self.output_path:
            self.output_path = f"asys_profiling_result_{dir_name}"
        else:
            self.output_path = os.path.join(self.output_path, f"asys_profiling_result_{dir_name}")
        return True

    def _run_cmd(self, cmd):
        log_info(f"Start run: {cmd}, please wait about {self.period} seconds.")
        # Run msprof command
        ret = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, encoding='utf-8', env=os.environ)
        if ret.returncode == 0:
            log_info(f"Succeeded in running profiling.\n{ret.stdout}")
        else:
            log_error(f"Failed to run profiling.\n{ret.stdout}")
            return False
        return True
