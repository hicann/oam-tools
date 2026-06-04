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
# AscendC 核函数直调编译：src/add_kernel.cpp + src/main.cpp → build_run/add_custom_op
# 用法：bash build.sh
set -e
[ -n "$ASCEND_HOME_PATH" ] || source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true
[ -n "$ASCEND_HOME_PATH" ] || { echo "[错误] 未找到 CANN，请先 source <CANN路径>/set_env.sh" >&2; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)
BUILD="$HERE/build_run"
rm -rf "$BUILD" && mkdir -p "$BUILD" && cd "$BUILD"

echo "[02] cmake 编译 (SOC=Ascend910B3) ..."
cmake "$HERE/src" -DASCEND_CANN_PACKAGE_PATH="$ASCEND_HOME_PATH" \
  -DSOC_VERSION=Ascend910B3 -DCMAKE_BUILD_TYPE=Release
cmake --build . -j 4

echo "[02] 产物: $(find "$BUILD" -name add_custom_op -type f)"
