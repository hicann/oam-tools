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

echo "NPU_COLLECT_PATH:" $NPU_COLLECT_PATH
echo "ASCEND_PROCESS_LOG_PATH:" $ASCEND_PROCESS_LOG_PATH
echo "ASCEND_WORK_PATH": $ASCEND_WORK_PATH

WORK_DIR=$(cd $(dirname $0); pwd)
echo "WORK_DIR: " $WORK_DIR

# generate host log
host_log_root_path=$ASCEND_PROCESS_LOG_PATH
mkdir -p ${host_log_root_path}/debug/device-0
mkdir -p ${host_log_root_path}/debug/plog
mkdir -p ${host_log_root_path}/run/device-0
mkdir -p ${host_log_root_path}/run/plog
cp -r $WORK_DIR/../atrace $ASCEND_WORK_PATH

touch ${host_log_root_path}/debug/device-0/device-111322_20230116070010213.log
touch ${host_log_root_path}/debug/plog/plog-156072_20230117025353069.log
touch ${host_log_root_path}/run/device-0/device-111631_20230116070034630.log
touch ${host_log_root_path}/run/plog/plog-108234_20230113115427711.log

# generate msn export files
npu_collect_path=$NPU_COLLECT_PATH
mkdir -p ${npu_collect_path}/extra-info/
mkdir -p ${npu_collect_path}/extra-info/graph/0
mkdir -p ${npu_collect_path}/extra-info/ops/0
mkdir -p ${npu_collect_path}/extra-info/data-dump/0
touch ${npu_collect_path}/extra-info/graph/0/ge_onnx_test.pbtxt
touch ${npu_collect_path}/extra-info/graph/0/ge_proto_test.txt
touch ${npu_collect_path}/extra-info/graph/0/TF_GeOp_test.pbtxt
touch ${npu_collect_path}/extra-info/ops/0/te_transdata_d9d56f95bf555c507bd3a5e4e8cf82a5267b873f7a159c0f2d37653515f7730a_1.o
touch ${npu_collect_path}/extra-info/ops/0/te_transdata_d9d56f95bf555c507bd3a5e4e8cf82a5267b873f7a159c0f2d37653515f7730a_1.json
touch ${npu_collect_path}/extra-info/ops/0/te_transdata_d9d56f95bf555c507bd3a5e4e8cf82a5267b873f7a159c0f2d37653515f7730a_1.cce
touch ${npu_collect_path}/extra-info/data-dump/0/BNTrainingReduce.BNTrainingReduce.164.1682441437239036
