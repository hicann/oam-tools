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

declare -A SOC_MAP
SOC_MAP=([Ascend310P]="Ascend310P3"
          [Ascend310B]="Ascend310B1"
          [Ascend910]="Ascend910A"
          [Ascend910B]="Ascend910B1"
          [Ascend910_93]="Ascend910_9391"
          [Ascend910_95]="Ascend910_9599"
)

OPC_TASK_NAME="opc_cmd.sh"
OUT_TASK_NAME="out_cmd.sh"
OP_CATEGORY_LIST="activation conv foreach vfusion index loss matmul norm optim pooling quant rnn control"

function trans_soc() {
  local _soc_input=$1
  local _soc_input_lower=${_soc_input,,}
  for key in ${!SOC_MAP[*]}; do
    key_lower=${key,,}
    if [ "${_soc_input_lower}" == "${key_lower}" ]; then
      echo ${SOC_MAP[$key]}
      return
    fi
  done

  echo ${_soc_input}
}
