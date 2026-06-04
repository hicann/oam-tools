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

"""把最小 TinyMLP 导出成 ONNX —— pyACL 链路的第一步。

与 01/04 同一个 TinyMLP（4 层 Linear+GELU，输入 [32,1024]），保持全套 demo 一致。
导出后由 atc 转成 .om，再由 infer.py 用 pyACL 加载推理。

★ 用到你自己的模型：替换 build_model() 和 dummy 输入，重新跑 build_model.sh
  生成新的 .om。若你已有 ONNX/Caffe 模型，可跳过本脚本，直接用 atc 转。
  注意 infer.py 里的输入 shape（32,1024）也要同步改成你的。

用法：python3 export_onnx.py
"""
import logging

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


def build_model():  # ← 换成你的模型
    return nn.Sequential(
        nn.Linear(1024, 1024),
        nn.GELU(),
        nn.Linear(1024, 1024),
        nn.GELU(),
        nn.Linear(1024, 1024),
        nn.GELU(),
        nn.Linear(1024, 1024),
    )


def main():
    model = build_model().eval()
    dummy = torch.randn(32, 1024)  # ← 换成你模型的输入 shape（atc 转静态 shape om）
    torch.onnx.export(
        model, dummy, "tiny_mlp.onnx",
        input_names=["x"], output_names=["y"],
        opset_version=13,
    )
    logger.info("[export] tiny_mlp.onnx 已生成")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
