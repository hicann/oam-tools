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
# 流程3：AI Core Error 故障信息解析
# asys analyze -r=aicore_error 内部调用 msaicerr，对每个 AICERROR 写出 info.txt。
#   --path  指向已收集的故障目录（launch 输出，或样例目录）
#   -d      指定 device
#   --output 解析结果输出目录
# 用法：
#   bash analyze_aicore_error.sh <已收集故障目录> [device_id]
#   不带参数时默认解析 launch 输出目录
set -e
# asys 入口：优先用 PATH 中的 asys，否则用 CANN 安装目录推导（需先 source setenv）
ASYS=$(command -v asys || echo "${ASCEND_HOME_PATH:-${ASCEND_TOOLKIT_HOME}}/tools/ascend_system_advisor/asys/asys")
HERE=$(cd "$(dirname "$0")" && pwd)
# 容器内 runtime 只可见 1 张卡(逻辑 0)，物理 NPU 已被重映射为逻辑 0。
DEVICE=${2:-0}
OUT="$HERE/fault-data/analyze"

# 默认取 launch 输出下最新的时间戳目录
if [ -n "$1" ]; then
    SRC="$1"
else
    SRC=$(find "$HERE/fault-data/launch" -maxdepth 1 -type d -name "asys_output_*" | sort | tail -1)
fi
[ -n "$SRC" ] && [ -d "$SRC" ] || { echo "[analyze] 未找到待解析故障目录，请传入 <路径> 或先跑 launch_rerun.sh" >&2; exit 1; }

mkdir -p "$OUT"
echo "[analyze] 解析 AI Core Error: --path $SRC -d $DEVICE --output $OUT"
"$ASYS" analyze -r=aicore_error -d "$DEVICE" --path "$SRC" --output "$OUT"
echo "[analyze] done. 解析结果："
find "$OUT" -name "info.txt" 2>/dev/null
