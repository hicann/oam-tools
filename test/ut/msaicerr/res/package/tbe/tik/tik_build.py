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

class for_range():
    def __init__(self, a, b):
        pass
    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        return 1
class Tik():
    def __init__(self):
        self.for_range = for_range

    def Tensor(self, a, b, name, scope=None):
        return [0]

    def vec_dup(self):
        pass

    def BuildCCE(self, kernel_name, inputs, outputs, output_files_path):
        pass

    def data_move(self, a, b, c, d, e, f, g):
        pass
    
    def vabs(self, a, b, c, d, e, f, g, h):
        pass
    
    def Scalar(self, a, init_value=0):
        return 0

scope_gm = "tik"
scope_ubuf = "ubuf"