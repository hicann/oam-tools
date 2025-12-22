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

set -e

main() {
  echo "[INFO]excute file: $0"
  if [ $# -lt 3 ]; then
    echo "[ERROR]input error"
    echo "[ERROR]bash $0 {task_path} {compile_thread_num} {out_path}"

    exit 1
  fi
  local task_path=$1
  local compile_thread_num=$2
  if [ ${compile_thread_num} -lt 1 ]; then
    echo "[INFO]will set compile_thread_num = 1, the compile_thread_num < 1"
    compile_thread_num=1
  fi
  local output_path="$3"
  mkdir -p $output_path/build_logs/

  source build_env.sh
  opc_cmd_file="${task_path}/${OPC_TASK_NAME}"
  out_cmd_file="${task_path}/${OUT_TASK_NAME}"
  echo "[INFO]exe_task: opc_cmd_file = ${opc_cmd_file}"
  echo "[INFO]exe_task: out_cmd_file = ${out_cmd_file}"
  echo "[INFO]exe_task: compile_thread_num = ${compile_thread_num}"
  echo "ASCENDC_PAR_COMPILE_JOB = ${ASCENDC_PAR_COMPILE_JOB}"

  CURRENT_DIR=$(dirname $(readlink -f ${BASH_SOURCE[0]}))
  local topdir=$(readlink -f ${workdir}/../../..)
  local op_cache_dir=${topdir}/vendor/hisi/build/scripts/op_cache
  if [ -d "${op_cache_dir}" ] && [ "${OP_CACHE_ENABLE}" == "true" ]; then # not exist
    exist_op_cache=true
    python3 ${op_cache_dir}/op_make_hash.py make_public_hash
  fi

  # step1: do compile kernel with compile_thread_num
  [ -e /tmp/binary_exe_task ] || mkfifo /tmp/binary_exe_task
  exec 8<> /tmp/binary_exe_task  # 创建文件描述符8
  rm -rf /tmp/binary_exe_task
  for ((i = 1; i <= ${compile_thread_num}; i++)); do
    echo >&8
  done

  opc_list_num=$(cat ${opc_cmd_file} | wc -l)
  random_opc_nums=$(shuf -i  1-${opc_list_num})
  for i in ${random_opc_nums}; do
    read -u8
    {
      set +e
      cmd_task=$(sed -n ''${i}'p;' ${opc_cmd_file})
      key=$(echo "${cmd_task}" | grep -oP '\w*\.json_\d*')
      echo "[INFO]exe_task: begin to build kernel with cmd: ${cmd_task}."
      start_time=$(date +%s)
      # avoid the opc processe from hanging

      if [ "${exist_op_cache}" == "true" ]; then
        echo "python3 ${op_cache_dir}/op_cache.py -- ${cmd_task}" > "${output_path}/build_logs/${key}.log"
        python3 ${op_cache_dir}/op_cache.py -- ${cmd_task} >> "${output_path}/build_logs/${key}.log" 2>&1
      else
        echo ${cmd_task} > "${output_path}/build_logs/${key}.log"
        timeout 7200 ${cmd_task} >> "${output_path}/build_logs/${key}.log" 2>&1
      fi

      end_time=$(date +%s)
      exe_time=$((end_time - start_time))
      echo "[INFO]exe_task: end to build kernel with cmd: ${cmd_task} --exe_time=${exe_time}"
      echo >&8
    } &
  done
  wait  # 等待所有的算子编译结束

  # step2: gen output one by one
  cat ${out_cmd_file} | while read cmd_task; do
    echo "[INFO]exe_task: begin to gen kernel list with cmd: ${cmd_task}."
    ${cmd_task}
  done
}
set -o pipefail
main "$@" | gawk '{print strftime("[%Y-%m-%d %H:%M:%S]"), $0}'
