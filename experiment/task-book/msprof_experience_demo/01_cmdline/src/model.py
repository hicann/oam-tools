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

"""最简 TinyMLP 模型 —— msprof CLI 采集的黑盒目标（示例负载）。

故意写得很小很纯：4 层 Linear+GELU，固定输入 [32, 1024]，
warmup ×3 + 测量 ×20。目的不是跑出有意义的业务结果，
而是给 msprof 一个稳定、可复现、算子单一（MatMul 主导）的负载。

★ 用到你自己的模型：CLI 是黑盒方式，连这个脚本都不用改——
  直接把 run.sh 里的 `python3 model.py` 换成你的启动命令即可。
  若想保留本脚本结构，则替换下面的 build_model() 和输入 x。

用法：
    ASCEND_VISIBLE_DEVICES=7 python3 model.py
"""
import logging
import time

import torch
import torch_npu  # noqa: F401  导入即注册 npu 后端

logger = logging.getLogger(__name__)


def build_model():  # ← 换成你的模型
    return torch.nn.Sequential(
        torch.nn.Linear(1024, 1024),
        torch.nn.GELU(),
        torch.nn.Linear(1024, 1024),
        torch.nn.GELU(),
        torch.nn.Linear(1024, 1024),
        torch.nn.GELU(),
        torch.nn.Linear(1024, 1024),
    )


def main():
    device = "npu:0"  # ASCEND_VISIBLE_DEVICES 已把目标卡映射成 0
    model = build_model().to(device).eval()
    x = torch.randn(32, 1024, device=device)  # ← 换成你模型的输入

    with torch.no_grad():
        for _ in range(3):  # warmup：触发编译 / 首次下发，不计入测量
            model(x)
        torch.npu.synchronize()

        t0 = time.time()
        for _ in range(20):  # 测量：20 次稳定推理
            model(x)
        torch.npu.synchronize()
        dt = (time.time() - t0) * 1000

    logger.info("[demo] 20 iters done, total=%.2f ms, avg=%.3f ms/iter", dt, dt / 20)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
