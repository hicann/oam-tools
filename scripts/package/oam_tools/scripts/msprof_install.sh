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
LEVEL_INFO="INFO"
LEVEL_WARN="WARNING"
LEVEL_ERROR="ERROR"

source "${COMMON_SHELL_PATH}"
 
# log functions
getdate() {
    _cur_date=$(date +"%Y-%m-%d %H:%M:%S")
    echo "${_cur_date}"
}

logandprint() {
    is_error_level=$(echo $1 | grep -E 'ERROR|WARN|INFO')
    if [ "${is_quiet}" != "y" ] || [ "${is_error_level}" != "" ]; then
        echo "[Oam-Tools] [$(getdate)] ""$1"
    fi
    echo "[Oam-Tools] [$(getdate)] ""$1" >> "${_INSTALL_LOG_FILE}"
}
 
installMsprofPython() {
    logandprint "[INFO]: installMsprofPython start"
    if [ "-${pylocal}" = "-y" ]; then
        createPythonLocalDir "$install_path"
        [ $? -ne 0 ] && return 1
        return 0
    fi
 
    installMsprofWhlPackage "${install_path}/tools/profiler/profiler_tool/msprof-0.0.1-py3-none-any.whl" \
     "${install_path}/tools/profiler/profiler_tool"
    if [ $? -ne 0 ]; then
        return 1
    fi
    return 0
}
 
installMsprofWhlPackage() {
    local _package=$1
    local _python_local_path=$2
 
    logandprint "[INFO]: start to begin install ${_package}."
    logandprint "[INFO]: The installation path ${_python_local_path} of whl package"
    if [ ! -f "${_package}" ]; then
        # log_and_print ${LEVEL_ERROR} "ERR_NO:0x0080;ERR_DES: The ${_package} does not exist."
        return 1
    fi
 
    pip3 install --upgrade --no-deps --force-reinstall --disable-pip-version-check "${_package}" -t "${_python_local_path}" > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        # log_and_print ${LEVEL_ERROR} "Install ${_package} failed."
        return 1
    fi
    changeDirMode 555 ${_python_local_path}
    changeFileMode 555 ${_python_local_path}
    logandprint "[INFO]: install ${_package} succeed."
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
feature_type=""
 
while true; do
    case "$1" in
    --install-path=*)
        install_path=$(echo "$1" | cut -d"=" -f2-)
        [ -z "${install_path}" ] && exit 1
        shift
        ;;
    --version-dir=*)
        version_dir=$(echo "$1" | cut -d"=" -f2-)
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
 
installMsprofPython
[ $? -ne 0 ] && exit 1
 
exit 0