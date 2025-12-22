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

MIN_PIP_VERSION=19
PYTHON_VERSION=3.7.5
FILE_NOT_EXIST="0x0080"

log() {
    local content cur_date
    content=$(echo "$@" | cut -d" " -f2-)
    cur_date="$(date +'%Y-%m-%d %H:%M:%S')"
    echo "[Oam-tools] [$cur_date] [$1]: $content"
}

log "INFO" "Oam-tools do pre check started."

log "INFO" "Check pip version."
which pip3 > /dev/null 2>&1
if [ $? -ne 0 ]; then
    log "WARNING" "\033[33mpip3 is not found.\033[0m"
fi

log "INFO" "Check python version."
curpath="$(dirname ${BASH_SOURCE:-$0})"
install_dir="$(realpath $curpath/..)"
common_interface=$(realpath $install_dir/script*/common_interface.bash)
if [ -f "$common_interface" ]; then
    . "$common_interface"
    py_version_check
fi

log "INFO" "Oam-tools do pre check finished."