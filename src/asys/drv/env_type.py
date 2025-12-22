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

from common import log_error
from common import RetCode
from common import Singleton


class LoadSoType(metaclass=Singleton):
    def __init__(self):
        self.drvdsmi = None
        self.drvhal = None
        self.asendml = None
        self.ascend_trace = None
        self.env_type = ""

    @staticmethod
    def load_dll(so_name):
        try:
            dll = ctypes.cdll.LoadLibrary(so_name)
        except OSError as err:
            log_error(f"OSError: {err}")
            return RetCode.FAILED
        return dll

    def get_drvdsmi_env_type(self):
        if self.drvdsmi is None:
            if self.get_env_type() == "EP":
                so_name = "libdrvdsmi_host.so"
            else:
                so_name = "libdrvdsmi.so"
            self.drvdsmi = self.load_dll(so_name)
        return self.drvdsmi

    def get_drvhal_env_type(self):
        if self.drvhal is None:
            so_name = "libascend_hal.so"
            self.drvhal = self.load_dll(so_name)
        return self.drvhal

    def get_ascend_ml(self):
        # libascend_ml.so is only in the toolkit run pkg.
        if self.asendml is None and self.get_env_type() == "EP":
            so_name = "libascend_ml.so"
            self.asendml = self.load_dll(so_name)
        return self.asendml

    def get_ascend_trace(self):
        if self.ascend_trace is None:
            so_name = "libascend_trace.so"
            self.ascend_trace = self.load_dll(so_name)
        return self.ascend_trace

    def get_env_type(self):
        if self.env_type:
            return self.env_type
        dev = self.get_drvhal_env_type()
        if dev != RetCode.FAILED:
            dev.drvGetPlatformInfo.argtypes = [ctypes.POINTER(ctypes.c_int)]
            num = ctypes.c_int(-1)
            ret = dev.drvGetPlatformInfo(ctypes.pointer(num))
            if ret == 0:
                if num.value == 0:
                    self.env_type = "RC"
                elif num.value == 1:
                    self.env_type = "EP"
        return self.env_type

    @ staticmethod
    def ctypes_close_library(lib):
        if lib and lib != RetCode.FAILED:
            dlclose_func = ctypes.CDLL(None).dlclose
            dlclose_func.argtypes = [ctypes.c_void_p]
            dlclose_func.restype = ctypes.c_int
            dlclose_func(lib._handle)

    def dll_close(self):
        self.ctypes_close_library(self.drvdsmi)
        self.ctypes_close_library(self.drvhal)
        self.ctypes_close_library(self.asendml)
        self.ctypes_close_library(self.ascend_trace)
        self.drvdsmi = None
        self.drvhal = None
        self.asendml = None
        self.ascend_trace = None
