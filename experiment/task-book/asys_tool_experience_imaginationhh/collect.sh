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
# 流程1：无需复跑业务，直接收集环境中已有的故障/运维信息
# 用法：bash collect.sh [device_id]   默认 device 7
set -e
# asys 入口：优先用 PATH 中的 asys，否则用 CANN 安装目录推导（需先 source setenv）
ASYS=$(command -v asys || echo "${ASCEND_HOME_PATH:-${ASCEND_TOOLKIT_HOME}}/tools/ascend_system_advisor/asys/asys")
# 容器内 runtime 只可见 1 张卡(逻辑 0)，物理 NPU 已被重映射为逻辑 0。
DEVICE=${1:-0}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT="$HERE/fault-data/collect"

echo "[collect] 收集环境已有信息到 $OUT (device $DEVICE)"
"$ASYS" collect --output "$OUT"
echo "[collect] done. 产物目录："
find "$OUT" -maxdepth 2 -type d | sort
