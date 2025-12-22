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
VARPATH="$(dirname "$CURPATH")"
USERNAME=$(id -un)
USERGROUP=$(id -gn)
common_func_path="$CURPATH/common_func.inc"
manager_func_path="$CURPATH/manager_func.sh"

. "$common_func_path"
. "$manager_func_path"

set_comm_log "Latest_manager" "$COMM_LOGFILE"

IS_UPGRADE="n"

while true
do
    case "$1" in
    --upgrade)
        IS_UPGRADE="y"
        shift
        ;;
    *)
        break
        ;;
    esac
done

if ! sh "$CURPATH/install_common_parser.sh" --package="latest_manager" --uninstall --username="$USERNAME" --usergroup="$USERGROUP" \
    --simple-uninstall "full" "$VARPATH" "$CURPATH/filelist.csv" "all"; then
    comm_log "ERROR" "uninstall failed!"
    exit 1
fi

if [ "$IS_UPGRADE" = "n" ]; then
    remove_manager_refs "$VARPATH"
fi

if ! remove_dir_if_empty "$VARPATH"; then
    comm_log "ERROR" "uninstall failed!"
    exit 1
fi
