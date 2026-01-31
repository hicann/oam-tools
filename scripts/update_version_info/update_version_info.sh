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
 
INPUT_FILE="$1"
OUTPUT_FILE="$2"
OUTPUT_DIR=$(dirname ${OUTPUT_FILE})
 
if [ ! -f "${INPUT_FILE}" ];then
    echo "ERROR: input file '${INPUT_FILE}' not found."
    exit 1
fi
 
if [ -n "${tagInfo}" ];then
    TIME_STAMP_ENV=$(echo "${tagInfo}" | sed -n 's/.*\([0-9]\{8\}_[0-9]\{9\}\).*/\1/p')
fi
 
if [ -n "${TIME_STAMP_ENV}" ];then
    TIME_STAMP=${TIME_STAMP_ENV}
else
    TIME_STAMP=$(date +"%Y%m%d_%H%M%S%3N")
fi
 
if [ ! -d "${OUTPUT_DIR}" ];then
    mkdir -p ${OUTPUT_DIR}
fi
 
cp -f ${INPUT_FILE} ${OUTPUT_FILE}
 
if ! grep -q "^timestamp=" "$OUTPUT_FILE"; then
    if [ -s "$OUTPUT_FILE" ] && [ "$(tail -c 1 "$OUTPUT_FILE")" != "" ]; then
        printf '\n' >> "$OUTPUT_FILE"
    fi
 
    printf 'timestamp=%s\n' "${TIME_STAMP}" >> "$OUTPUT_FILE"
else
    NEW_LINE="timestamp=${TIME_STAMP}"
    sed -i "s/^timestamp=.*/$NEW_LINE/" "$OUTPUT_FILE"
fi
 
exit 0