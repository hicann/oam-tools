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
# 03 第一步：TinyMLP → ONNX → .om（pyACL 推理的前置准备）。
# 用法：bash build_model.sh
set -e
# 定位 CANN 环境（找不到会提示先 source set_env.sh）
[ -n "$ASCEND_HOME_PATH" ] || source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true
[ -n "$ASCEND_HOME_PATH" ] || { echo "[错误] 未找到 CANN，请先 source <CANN路径>/set_env.sh" >&2; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$HERE/model_build" && cd "$HERE/model_build"

echo "[03] 导出 ONNX ..."
python3 "$HERE/src/export_onnx.py"

echo "[03] ATC 转 .om (soc=Ascend910B3) ..."
atc --model=tiny_mlp.onnx --framework=5 --output=tiny_mlp \
    --soc_version=Ascend910B3 --input_shape="x:32,1024"

echo "[03] 产物: $(ls tiny_mlp.om 2>/dev/null)"
