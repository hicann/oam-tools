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
 
install_msprof_python() {
    logandprint "[INFO]: install_msprof_python start"
    if [ "-${pylocal}" = "-y" ]; then
        createPythonLocalDir "$install_path"
        [ $? -ne 0 ] && return 1
        return 0
    fi

    install_msprof_whl_package "${install_path}/tools/profiler/profiler_tool/msprof-0.0.1-py3-none-any.whl" \
     "${install_path}/tools/profiler/profiler_tool"
    if [ $? -ne 0 ]; then
        return 1
    fi
    return 0
}

install_msprof_whl_package() {
    local _package=$1
    local _python_local_path=$2

    logandprint "[INFO]: start to begin install ${_package}."
    logandprint "[INFO]: The installation path ${_python_local_path} of whl package"
    if [ ! -f "${_package}" ]; then
        # log_and_print ${LEVEL_ERROR} "ERR_NO:0x0080;ERR_DES: The ${_package} does not exist."
        return 1
    fi

    # whl 已在打包阶段预解包（任意版本的 msprof-*.dist-info 存在）时跳过 pip，
    # 避免对已被 entity 级 chmod 锁成只读的子目录再次执行 force-reinstall，
    # 导致 pip 卸载阶段下钻失败。但仍统一执行 chmod 555 收尾，
    # 保持与历史安装路径一致的最终权限。glob 匹配避免硬编码版本号导致 whl 升级后失配。
    local _existing_distinfo
    _existing_distinfo=$(find "${_python_local_path}" -maxdepth 1 -type d -name 'msprof-*.dist-info' -print -quit 2>/dev/null)
    if [ -z "${_existing_distinfo}" ]; then
        pip3 install --upgrade --no-deps --force-reinstall --disable-pip-version-check "${_package}" -t "${_python_local_path}" > /dev/null 2>&1
        if [ $? -ne 0 ]; then
            # log_and_print ${LEVEL_ERROR} "Install ${_package} failed."
            return 1
        fi
    else
        logandprint "[INFO]: msprof whl already extracted at build time, skip pip install."
        # 用目标机的 python3 重新 compileall，生成匹配运行期 Python 的 .pyc 缓存。
        # install_common_parser.sh 已把目录锁为 550，compileall 无法写入 __pycache__；
        # 临时解锁 u+w，编译完再交由后续 change_dir_mode/change_file_mode 锁回 555。
        chmod -R u+w "${_python_local_path}" 2>/dev/null
        # compileall 失败不阻断安装（.pyc 是缓存，缺了 Python 仍能跑），但要打 WARNING
        # 避免静默吞掉磁盘满 / 只读 fs / SELinux 阻断等真实错误，便于运行期排查。
        if ! python3 -m compileall -q "${_python_local_path}" > /dev/null 2>&1; then
            logandprint "[WARNING]: python3 -m compileall failed for ${_python_local_path}; .pyc cache may be missing, msprof will fall back to interpreting .py at runtime."
        fi
    fi
    change_dir_mode 555 ${_python_local_path}
    change_file_mode 555 ${_python_local_path}
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
 
install_msprof_python
[ $? -ne 0 ] && exit 1
 
exit 0