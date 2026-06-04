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
# 方式二：AscendC 自定义算子 + msprof 采集（核函数直调）。
# 先 bash build.sh 编出 add_custom_op，再跑本脚本。
# 用法：bash run.sh [device_id]   (默认 7)
set -e
DEV=${1:-7}
[ -n "$ASCEND_HOME_PATH" ] || source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true
[ -n "$ASCEND_HOME_PATH" ] || { echo "[错误] 未找到 CANN，请先 source <CANN路径>/set_env.sh" >&2; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)
BIN="$HERE/build_run/add_custom_op"
OUT="$HERE/prof_out"
[ -x "$BIN" ] || { echo "[02] 未找到 $BIN，请先 bash build.sh" >&2; exit 1; }
rm -rf "$OUT" && mkdir -p "$OUT"
export LD_LIBRARY_PATH="$ASCEND_HOME_PATH/aarch64-linux/lib64:$LD_LIBRARY_PATH"

echo "[02] msprof 采集 AscendC Add 算子，device=$DEV"
ASCEND_VISIBLE_DEVICES=$DEV msprof --output="$OUT" \
  --ascendcl=on --runtime-api=on --task-time=on --task-memory=on \
  --ai-core=on --aic-metrics=PipeUtilization --aicpu=on --msproftx=on \
  "$BIN"

echo "[02] 完成，算子聚合："
cat "$OUT"/PROF_*/mindstudio_profiler_output/op_statistic_*.csv 2>/dev/null
