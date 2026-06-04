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
# 方式四：torch_npu.profiler API 采集 —— 白盒，代码内插桩。
# 用法：bash run.sh [device_id]   (默认 7)
set -e
DEV=${1:-7}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT="$HERE/prof_out"
rm -rf "$OUT" && mkdir -p "$OUT"

echo "[04] torch_npu.profiler 采集，device=$DEV"
ASCEND_VISIBLE_DEVICES=$DEV python3 "$HERE/src/model_with_profiler.py" "$OUT"

echo "[04] 完成，step 拆分（API 独有）："
cat "$OUT"/*_ascend_pt/ASCEND_PROFILER_OUTPUT/step_trace_time.csv 2>/dev/null
