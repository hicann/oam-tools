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

curpath=$(dirname $(readlink -f "$0"))
SCENE_FILE="${curpath}""/../scene.info"
OPP_COMMON="${curpath}""/oam_common.sh"
common_func_path="${curpath}/common_func.inc"
. "${OPP_COMMON}"
. "${common_func_path}"
# init arch 
architecture=$(uname -m)
architectureDir="${architecture}-linux"

while true; do
    case "$1" in
    --install-path=*)
        install_path=$(echo "$1" | cut -d"=" -f2-)
        shift
        ;;
    --version-dir=*)
        version_dir=$(echo "$1" | cut -d"=" -f2)
        shift
        ;;
    --latest-dir=*)
        latest_dir=$(echo "$1" | cut -d"=" -f2)
        shift
        ;;
    -*)
        shift
        ;;
    *)
        break
        ;;
    esac
done
get_version_dir "opp_kernel_version_dir" "$install_path/$version_dir/opp_kernel/version.info"

if [ -z "$opp_kernel_version_dir" ]; then
    # before remove the oppkernel, remove the softlinks
    logandprint "[INFO]: Start remove opapi softlinks."
    softlinksRemove ${install_path}/${version_dir}
    if [ $? -ne 0 ]; then
        logandprint "[WARNING]: Remove opapi softlinks failed, some softlinks may not exist."
    else
        logandprint "[INFO]: Remove opapi softlinks successfully."
    fi
fi
