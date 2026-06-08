#!/bin/bash
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
# PyTorch API 方式：torch_npu.profiler 代码内插桩采集 —— 白盒。
# 用法：bash pytorch_run.sh [device_id]   (默认自动探测第一张可用卡)
set -e
# 不硬编码卡号：默认取第一张可用 NPU，避免单卡环境卡号非 0/7 时失败
DEV=${1:-$(ls /dev/davinci[0-9]* 2>/dev/null | grep -o '[0-9]*$' | head -1)}
DEV=${DEV:-0}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT="$HERE/perf-data"
rm -rf "$OUT" && mkdir -p "$OUT"

echo "[pytorch] torch_npu.profiler 采集，device=$DEV"
ASCEND_VISIBLE_DEVICES=$DEV python3 "$HERE/app/model_with_profiler.py" "$OUT"

echo "[pytorch] 完成，step 拆分（API 独有）："
cat "$OUT"/*_ascend_pt/ASCEND_PROFILER_OUTPUT/step_trace_time.csv 2>/dev/null
