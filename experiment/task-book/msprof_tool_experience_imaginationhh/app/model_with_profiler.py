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

"""方式四：torch_npu.profiler API 采集 —— 白盒，在训练/推理循环里精确圈定采集区间。

与 CLI 的区别：
- CLI 是旁路黑盒，看不到 PyTorch aten op 的存在；
- API 在代码里插桩，能拿到 aten op 级耗时、Python 调用栈、step 拆分，
  并额外产出 CLI 没有的 step_trace_time.csv（每 step Computing/Free 占比）。

同一个 TinyMLP，方便和 01_cmdline 的结果横向对比。

★ 用到你自己的模型：替换 build_model() 和输入 x（下方均有标注），
  采集配置（make_profiler 那段）和 run.sh 都不用改。
  若你的是训练循环，把 prof.step() 放到每个训练 step 末尾即可。

用法：
    ASCEND_VISIBLE_DEVICES=7 python3 model_with_profiler.py [输出目录]
"""
import logging
import sys

import torch
import torch_npu  # noqa: F401
from torch_npu.profiler import (
    AiCMetrics,
    ProfilerActivity,
    ProfilerLevel,
    profile,
    schedule,
    tensorboard_trace_handler,
)

logger = logging.getLogger(__name__)

WARMUP_STEPS = 3
ACTIVE_STEPS = 5
BATCH, HIDDEN = 32, 1024


def build_model():  # ← 换成你的模型
    layers = []
    for _ in range(3):
        layers += [torch.nn.Linear(HIDDEN, HIDDEN), torch.nn.GELU()]
    layers.append(torch.nn.Linear(HIDDEN, HIDDEN))
    return torch.nn.Sequential(*layers)


def make_profiler(out_dir):
    """构造 profiler。把几个可调"旋钮"单列出来，方便你按需替换：

    - level  采集层级，Level1 含 AI Core PMU；想更轻量可降 Level0
    - pmu    AI Core 指标口径，PipeUtilization 看各计算流水线占用
    - acts   采集两侧，CPU+NPU 都要才能看清"下发 vs 执行"的 gap
    """
    level = ProfilerLevel.Level1
    pmu = AiCMetrics.PipeUtilization
    acts = [ProfilerActivity.CPU, ProfilerActivity.NPU]

    # 保留原始 trace；生产场景可把 data_simplification 设 True 省空间
    # torch_npu 仅以下划线前缀的 _ExperimentalConfig 暴露采集配置，
    # 用 getattr 按名取用，避免直接书写受保护成员
    exp_config_cls = getattr(torch_npu.profiler, "_ExperimentalConfig")
    trace_cfg = exp_config_cls(
        profiler_level=level,
        aic_metrics=pmu,
        data_simplification=False,
    )
    window = schedule(wait=0, warmup=WARMUP_STEPS, active=ACTIVE_STEPS, repeat=1)

    return profile(
        activities=acts,
        schedule=window,
        on_trace_ready=tensorboard_trace_handler(out_dir),
        experimental_config=trace_cfg,
        record_shapes=True,  # 记录算子 input shape
        with_stack=True,     # 记录 Python 调用栈
    )


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "./prof_out"
    device = "npu:0"
    model = build_model().to(device).eval()
    x = torch.randn(BATCH, HIDDEN, device=device)  # ← 换成你模型的输入

    total_steps = WARMUP_STEPS + ACTIVE_STEPS
    profiler = make_profiler(out_dir)
    with torch.no_grad(), profiler as prof:
        for _ in range(total_steps):
            model(x)
            torch.npu.synchronize()
            prof.step()  # 通知 profiler 进入下一 step

    logger.info("[demo] profiler done, output -> %s", out_dir)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
