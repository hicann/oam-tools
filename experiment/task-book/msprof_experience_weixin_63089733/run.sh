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
# MatmulLeakyRelu msprof reproducer.
set -e

MODE=${1:-simulator}
ROOT=$(cd "$(dirname "$0")" && pwd)
APP_DIR="$ROOT/app"
RUN_ID=$(date +%Y%m%d%H%M%S)
PERF_DIR="$ROOT/perf-data/${RUN_ID}_${MODE}"
LOG_DIR="$ROOT/logs"

mkdir -p "$PERF_DIR" "$LOG_DIR"

source_cann_env() {
    local env_file=$1
    local source_cmd=source

    "$source_cmd" "$env_file"
}

if [ -n "$CANN_SET_ENV" ] && [ -f "$CANN_SET_ENV" ]; then
    source_cann_env "$CANN_SET_ENV"
elif [ -f /home/whj/hw_work_place/Ascend_9.1.0/cann-9.1.0/set_env.sh ]; then
    source_cann_env /home/whj/hw_work_place/Ascend_9.1.0/cann-9.1.0/set_env.sh
elif [ -f /usr/local/Ascend/cann/set_env.sh ]; then
    source_cann_env /usr/local/Ascend/cann/set_env.sh
else
    echo "[ERROR] CANN set_env.sh not found. Set CANN_SET_ENV=/path/to/set_env.sh" >&2
    exit 1
fi

export HOME=${HOME:-/tmp}
export ASCEND_PROCESS_LOG_PATH=${ASCEND_PROCESS_LOG_PATH:-"$LOG_DIR/ascend"}
mkdir -p "$ASCEND_PROCESS_LOG_PATH"

cmake -S "$APP_DIR" -B "$APP_DIR/build"
cmake --build "$APP_DIR/build" --target demo demo_sim -j

cd "$APP_DIR"
python3 scripts/gen_data.py

if [ "$MODE" = "simulator" ]; then
    SOC_VERSION=${SOC_VERSION:-Ascend910B1}
    export LD_LIBRARY_PATH="$ASCEND_HOME_PATH/x86_64-linux/simulator/dav_2201/lib:$LD_LIBRARY_PATH"
    export PATH="$ASCEND_HOME_PATH/tools/msopprof/bin:$PATH"
    export MSOPPROF_EXE_PATH=${MSOPPROF_EXE_PATH:-"$ASCEND_HOME_PATH/tools/msopprof"}
    msprof op simulator --soc-version="$SOC_VERSION" --dump=on \
        --output="$PERF_DIR" "$APP_DIR/build/demo_sim" \
        > "$PERF_DIR/matmul_simulator_msprof.log" 2>&1 || true
elif [ "$MODE" = "board" ]; then
    msprof op --output="$PERF_DIR" "$APP_DIR/build/demo" \
        > "$PERF_DIR/matmul_board_msprof.log" 2>&1 || true
else
    echo "[ERROR] Unsupported mode: $MODE. Use simulator or board." >&2
    exit 2
fi

python3 scripts/verify_result.py output/output.bin output/golden.bin \
    | tee "$PERF_DIR/verification.txt"

echo "[INFO] perf data: $PERF_DIR"
