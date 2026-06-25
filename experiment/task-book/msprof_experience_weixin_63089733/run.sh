#!/bin/bash
# ----------------------------------------------------------------------------
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.
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
# matmul_basic_api msprof 一键复现脚本(Atlas A2 910B3 上板)
# 流程: 配置环境 -> 编译 -> 生成数据 -> 执行 -> 精度校验 -> msprof 采集
set -e

ROOT=$(cd "$(dirname "$0")" && pwd)
APP_DIR="$ROOT/app"
BUILD_DIR="$APP_DIR/build"
SOC_ARCH=${SOC_ARCH:-dav-2201}   # 910B3 -> dav-2201

# 1. 配置 CANN 环境(按需用 CANN_SET_ENV 覆盖)
if [ -n "$CANN_SET_ENV" ] && [ -f "$CANN_SET_ENV" ]; then
    source "$CANN_SET_ENV"
elif [ -f /home/developer/Ascend/cann-8.5.2/set_env.sh ]; then
    source /home/developer/Ascend/cann-8.5.2/set_env.sh
elif [ -f /usr/local/Ascend/cann/set_env.sh ]; then
    source /usr/local/Ascend/cann/set_env.sh
else
    echo "[ERROR] CANN set_env.sh 未找到,请用 CANN_SET_ENV=/path/to/set_env.sh 指定" >&2
    exit 1
fi

# 2. 编译
mkdir -p "$BUILD_DIR"
cmake -S "$APP_DIR" -B "$BUILD_DIR" -DCMAKE_ASC_ARCHITECTURES="$SOC_ARCH"
cmake --build "$BUILD_DIR" -j

# 3. 生成输入与 golden(脚本以相对路径写 input/output,需在 build 目录执行)
cd "$BUILD_DIR"
python3 "$APP_DIR/scripts/gen_data.py"

# 4. 执行算子
./demo

# 5. 精度校验
python3 "$APP_DIR/scripts/verify_result.py" output/output.bin output/golden.bin

# 6. msprof 命令行采集
#    注意: msprof 拒绝 group/other 可写的输出目录,这里显式收紧权限
PROF_DIR="$BUILD_DIR/prof_out"
mkdir -p "$PROF_DIR"
chmod 750 "$PROF_DIR" ./demo
msprof --application="./demo" \
       --output="$PROF_DIR" \
       --ai-core=on --task-time=on --aicpu=on \
       --aic-metrics=PipeUtilization \
       --analyze=on

echo "[INFO] 采集完成,解析数据在: $PROF_DIR/PROF_*/mindstudio_profiler_output/"
