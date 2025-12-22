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
if [ -d "$install_path/$version_dir/opp" ]; then
    ln -srfn "$install_path/$version_dir/opp" "$install_path/$latest_dir/ops"
fi

get_version_dir "latest_version_dir" "$install_path/$latest_dir/opp_kernel/version.info"
 
if [ -z "$latest_version_dir" ]; then
    # create op_api soft link
    logandprint "[INFO]: Start create opapi latest softlinks."
    createOpapiLatestSoftlink ${install_path}/${version_dir}
    return_code=$?
    if [ ${return_code} -eq 0 ]; then
        logandprint "[INFO]: Create opapi latest softlinks successfully!"
    elif [ ${return_code} -eq 3 ]; then
        logandprint "[WARNING]: opapi source file does not exist!"
    else
        logandprint "[ERROR]: Create opapi latest softlinks failed!"
    fi
fi

if [ -n "$latest_version_dir" ] && [ -d "$install_path/$latest_version_dir/opp" ]; then
    if [ "${latest_version_dir}" != "${version_dir}" ]; then
        logandprint "[INFO]: opp_kernel version is $latest_version_dir, the pkg version is $version_dir, and the opp_latest soft link is created."
        ln -srfn "$install_path/$latest_version_dir/opp" "$install_path/$latest_dir/opp_latest"
    else
        logandprint "[INFO]: opp_kernel version is $latest_version_dir, the pkg version is $version_dir, and the opp_latest soft link is deleted."
        rm -rf "$install_path/$latest_dir/opp_latest"
    fi
fi
