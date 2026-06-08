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
# 流程2：业务复跑 + 故障信息同步收集
# asys launch 会设置 NPU_COLLECT_PATH / ASCEND_GLOBAL_LOG_LEVEL 等环境变量拉起业务，
# 业务结束后自动 collect。被复跑的业务 = 故障注入算子 app/build_run/dirty_op。
# 用法：bash launch_rerun.sh [device_id]   默认 device 7
set -e
# asys 入口：优先用 PATH 中的 asys，否则用 CANN 安装目录推导（需先 source setenv）
ASYS=$(command -v asys || echo "${ASCEND_HOME_PATH:-${ASCEND_TOOLKIT_HOME}}/tools/ascend_system_advisor/asys/asys")
# 容器内 runtime 只可见 1 张卡(逻辑 0)，物理 NPU 已被重映射为逻辑 0。
# 切勿设 ASCEND_RT_VISIBLE_DEVICES 为容器外的物理卡号，否则 runtime 报 input data range、kernel 不下发。
DEVICE=${1:-0}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT="$HERE/fault-data/launch"
TASK="$HERE/app/build_run/dirty_op"

[ -x "$TASK" ] || { echo "[launch] 未找到故障算子，请先 bash app/build.sh" >&2; exit 1; }

echo "[launch] 复跑故障算子并收集故障信息到 $OUT (device $DEVICE)"
echo "[launch] 可复现业务命令: $TASK"
"$ASYS" launch --task "$TASK" --output "$OUT"
echo "[launch] done. 产物目录："
find "$OUT" -maxdepth 3 -type d | sort
