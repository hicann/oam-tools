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
import os

from common import log_error, log_info
from common.const import SIGRTMIN
from drv import LoadSoType

IN_CLOSE_WRITE = 0x00000008  # inotify.h
SIGNAL_ONE_TASK = 0xAABB0002
SIGNAL_ALL_TASK = 0xAABB0003


class AscendTraceDll:

    def __init__(self):
        self.trace_dll = LoadSoType().get_ascend_trace()

    def send_signal_to_pid(self, is_all_task, remote_id):
        """
        use the sigqueue to send signal
        """
        class SignalVal(ctypes.Structure):
            _fields_ = [("sival_int", ctypes.c_int)]

        val = SIGNAL_ALL_TASK if is_all_task else SIGNAL_ONE_TASK
        try:
            ret_code = self.trace_dll.sigqueue(
                ctypes.c_int32(remote_id),
                ctypes.c_int32(SIGRTMIN + 1),  # signal 35
                SignalVal(val)
            )
        except Exception as e:
            log_error(f"Send signal failed, error msg: {e}.")
            return False

        if ret_code != 0:
            log_error("Send signal failed.")
            return False
        return True

    def parse_stackcore_bin_to_txt(self, bin_file_path):
        """
        use the stackcore function to parse the bin file.
        """
        try:
            ret_code = self.trace_dll.AtraceStackcoreParse(bin_file_path.encode(), ctypes.c_int32(len(bin_file_path)))
        except Exception as e:
            log_error(f"Parse stackcore bin file failed, error msg: {e}.")
            return False

        if ret_code == 0:
            log_info(f"stackcore file path: {bin_file_path[:-4]}.txt")
            return True
        else:
            log_error("Parse stackcore bin file failed, check trace logs in the plog.")
            return False
