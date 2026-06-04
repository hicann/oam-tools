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
# 方式一：msprof 命令行（CLI）采集 —— 黑盒，不改一行模型代码。
# 用法：bash run.sh [device_id]   (默认 7)
set -e
DEV=${1:-7}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT="$HERE/prof_out"
rm -rf "$OUT" && mkdir -p "$OUT"

echo "[01] msprof CLI 采集，device=$DEV"
# 卡号写在 msprof 前：msprof 是父进程，需在其初始化前生效，否则落到 device 0
ASCEND_VISIBLE_DEVICES=$DEV msprof --output="$OUT" \
  --ascendcl=on --runtime-api=on --task-time=on --task-memory=on \
  --ai-core=on --aic-metrics=PipeUtilization --aicpu=on --msproftx=on \
  python3 "$HERE/src/model.py"

echo "[01] 完成，算子耗时 Top："
cat "$OUT"/PROF_*/mindstudio_profiler_output/op_statistic_*.csv 2>/dev/null
