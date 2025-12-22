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
SHELL_DIR=$(cd "$(dirname "$0")" || exit;pwd)
COMMON_SHELL_PATH="$SHELL_DIR/oam_common.sh"
LOG_PATH="/var/log/ascend_seclog/ascend_install.log"
PACKAGE=toolkit
LEVEL_INFO="INFO"
LEVEL_WARN="WARNING"
LEVEL_ERROR="ERROR"

source "${COMMON_SHELL_PATH}"
 
uninstallMsprofPython() {
    # remove msprof
    changeDirMode 750 ${install_path}/tools/profiler/profiler_tool
    changeFileMode 750 ${install_path}/tools/profiler/profiler_tool
    whlUninstallPackage msprof ${install_path}/tools/profiler/profiler_tool analysis
    [ $? -ne 0 ] && return 1
    return 0
}
 
whlUninstallPackage() {
    local module_="$1"
    local python_path_="$2"
    # Root directory name generated after the whl package is installed in the specified path.
    # If parameter 3 is not transferred, the root directory name is the module name by default.
    local module_root_name="$3"
    if [ ! -n "${module_root_name}" ]; then
        module_root_name=${module_}
    fi
 
    log ${LEVEL_INFO} "start to uninstall ${module_}"
    log ${LEVEL_INFO} "The path ${python_path_} of ${module_root_name} whl package to be uninstalled"
    if [ -d "${python_path_}/${module_root_name}" ]; then
        export PYTHONPATH=${python_path_}
    else
        unset PYTHONPATH
    fi
    pip3 uninstall -y "${module_}" > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        log_and_print ${LEVEL_ERROR} "uninstall ${module_} failed."
        return 1
    fi
    log ${LEVEL_INFO} "uninstall ${module_} succeed."
    return 0
}
 
uninstallPython() {
    local _py_path="$install_path/$PACKAGE/python"
    # remove python softlink in toolkit
    if [ -d "$_py_path" ]; then
        rm -rf "$_py_path"
    fi
 
    uninstallMsprofPython
    [ $? -ne 0 ] && return 1
 
    # remove python dir
    removePythonLocalDir
    [ $? -ne 0 ] && return 1
    return 0
}
 
init() {
    [ ! -d "${install_path}" ] && exit 1
 
    if [ ! -z "${version_dir}" ]; then
        install_path="${install_path}/${version_dir}"
        [ ! -d "${install_path}" ] && exit 1
    fi
 
    if [ $(id -u) -eq 0 ]; then
        log_file=${LOG_PATH}
    else
        local _home_path=$(eval echo "~")
        log_file="${_home_path}/${LOG_PATH}"
    fi
}
 
log_file=""
is_quiet=n
pylocal=n
install_path=""
version_dir=""
 
while true; do
    case "$1" in
    --install-path=*)
        install_path=$(echo "$1" | cut -d"=" -f2-)
        [ -z "${install_path}" ] && exit 1
        shift
        ;;
    --version-dir=*)
        version_dir=$(echo "$1" | cut -d"=" -f2-)
        [ -z "${version_dir}" ] && exit 1
        shift
        ;;
    --quiet=*)
        is_quiet=$(echo "$1" | cut -d"=" -f2)
        shift
        ;;
    --pylocal=*)
        pylocal=$(echo "$1" | cut -d"=" -f2)
        shift
        ;;
    --feature=*)
        feature_type=$(echo "$1" | cut -d"=" -f2)
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
 
init
 
uninstallPython
[ $? -ne 0 ] && exit 1
 
exit 0