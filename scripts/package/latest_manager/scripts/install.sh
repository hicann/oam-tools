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

CURPATH=$(dirname $(readlink -f "$0"))
USERNAME=$(id -un)
USERGROUP=$(id -gn)
common_func_path="${CURPATH}/common_func.inc"

. "$common_func_path"

INSTALL_PATH=""
IS_UPGRADE="n"

set_comm_log "Latest_manager" "$COMM_LOGFILE"

while true
do
    case "$1" in
    --install-path=*)
        INSTALL_PATH="$(echo "$1" | cut -d"=" -f2-)"
        shift
        ;;
    --upgrade)
        IS_UPGRADE="y"
        shift
        ;;
    -*)
        comm_log "ERROR" "Unsupported parameters : $1"
        exit 1
        ;;
    *)
        break
        ;;
    esac
done

if [ "$INSTALL_PATH" = "" ]; then
    comm_log "ERROR" "--install-path parameter is required!"
    exit 1
fi

if ! sh "$CURPATH/install_common_parser.sh" --package="latest_manager" --install --username="$USERNAME" --usergroup="$USERGROUP" \
    --simple-install "full" "$INSTALL_PATH" "$CURPATH/filelist.csv" "all"; then
    comm_log "ERROR" "install failed!"
    exit 1
fi

if [ "$IS_UPGRADE" = "y" ] && ! "$INSTALL_PATH/manager.sh" "migrate_latest_data"; then
    comm_log "ERROR" "migrate latest data failed!"
    exit 1
fi
