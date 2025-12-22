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

function get_thread_num() {
  local _thread_num=1
  _thread_num=$(cat /proc/cpuinfo | grep "processor" | wc -l)
  if [ "${_thread_num}" == "" ]; then
     return 1
  fi
  return ${_thread_num}
}

function get_thread_num_with_json_config() {
  local _thread_num=1
  local _binary_config_full_path=$1
  local _core_num=$(cat /proc/cpuinfo | grep "processor" | wc -l)
  _thread_num=$(cat ${_binary_config_full_path} | grep bin_filename | wc -l)
  if [ "${_thread_num}" == "" ]; then
     return 1
  fi
  if [ ${_thread_num} -gt ${_core_num} ]; then
     return ${_core_num}
  fi
  return ${_thread_num}
}
