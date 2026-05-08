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

PARAM_INVALID="0x0002"
PARAM_INVALID_DES="Invalid input parameter."
FILE_READ_FAILED="0x0082"
FILE_READ_FAILED_DES="File read failed."
OPERATE_FAILED="0x0001"

_CURR_PATH=$(dirname $(readlink -f $0))
_COMMON_INC_FILE="${_CURR_PATH}/common_func.inc"
_OPP_COMMON_FILE="${_CURR_PATH}/oam_common.sh"
. "${_COMMON_INC_FILE}"
. "${_OPP_COMMON_FILE}"

logwitherrorlevel() {
    _ret_status="$1"
    _level="$2"
    _msg="$3"
    if [ "${_ret_status}" != 0 ]; then
        if [ "${_level}" = "error" ]; then
            logandprint "${_msg}"
            exit 1
        else
            logandprint "${_msg}"
        fi
    fi
}

checkdirectoryexist() {
    _path="${1}"
    if [ ! -d "${_path}" ]; then
        logandprint "[ERROR]: ERR_NO:${FILE_READ_FAILED};ERR_DES:Installation directroy [${_path}] does not exist, uninstall failed."
        return 1
    else
        return 0
    fi
}

checkfileexist() {
    _path_param="${1}"
    if [ ! -f "${_path_param}" ];then
        logandprint "[ERROR]: ERR_NO:${FILE_READ_FAILED};ERR_DES:The file (${_path_param}) does not existed."
        return 1
    else
        return 0
    fi
}

# DFS sub-folders cleaner
deleteemptyfolders() {
    _init_dir="$1"
    _aicpu_filter="$2"
    find "${_init_dir}" -mindepth 1 -maxdepth 1 -type d ! \
        -path "${_aicpu_filter}" 2> /dev/null | while read -r dir
    do
        if [ "$(echo "${dir}" | grep "custom")" = "" ]; then
            deleteemptyfolders "${dir}"

            if [ "$(find "${dir}" -mindepth 1 -type d)" = "" ] && \
                [ "$(ls -A "${dir}")" = "" ] >/dev/null; then
                rm -rf -d "${dir}"
            fi
        else
            # remove custom folders which not contains sub-folder or any files
            if [ "$(ls -A "${dir}")" = "" ]; then
                rm -rf -d "${dir}"
            fi
        fi
    done
}

checkinstalledtype() {
    _type="$1"
    if [ "${_type}" != "run" ] &&
    [ "${_type}" != "full" ] &&
    [ "${_type}" != "devel" ]; then
        logandprint "[ERROR]: ERR_NO:${UNAME_NOT_EXIST};ERR_DES:Install type \
[${_ugroup}] of oam-tools module is not right!"
        return 1
    else
        return 0
    fi
}

getinstallpath() {
    docker_root_tmp="$(echo "${docker_root}" | sed "s#/\+\$##g")"
    docker_root_regex="$(echo "${docker_root_tmp}" | sed "s#\/#\\\/#g")"
    relative_path_val=$(echo "${_ABS_INSTALL_PATH}" | sed "s/^${docker_root_regex}//g" | sed "s/\/\+\$//g")
    return
}

unsetenv() {
    logandprint "[INFO]: Unset the environment path"
    target_username=$(getinstalledinfo "${KEY_INSTALLED_UNAME}")
    target_usergroup=$(getinstalledinfo "${KEY_INSTALLED_UGROUP}")
    if [ "${is_docker_install}" = y ] ; then
        uninstall_option="--docker-root=${docker_root}"
    else
        uninstall_option=""
    fi
}

installed_path="$1"
uninstall_mode="$2"
is_quiet="$3"
_CHIP_TYPE="$4"
is_docker_install="$5"
docker_root="$6"
pkg_version_dir="$7"
paramter_num="$#"

logandprint "[INFO]: Command ops_base_uninstall"

if [ "${paramter_num}" != 0 ]; then
    if [ "${installed_path}" = "" ] ||
    [ "${uninstall_mode}" = "" ] ||
    [ "${is_quiet}" = "" ] ; then
        logandprint "[ERROR]: ERR_NO:${PARAM_INVALID};ERR_DES:Empty paramters is invalid\
for call uninstall functions."
        exit 1
    fi
fi

SCENE_FILE="${_CURR_PATH}""/../scene.info"
platform_data=$(grep -e "arch" "$SCENE_FILE" | cut --only-delimited -d"=" -f2-)
ops_base_platform_old_dir=oam-tools_$platform_data-linux
ops_base_platform_dir=oam_tools
upper_opp_platform=$(echo "${ops_base_platform_dir}" | tr 'a-z' 'A-Z')
_FILELIST_FILE="${_CURR_PATH}""/filelist.csv"
_COMMON_PARSER_FILE="${_CURR_PATH}""/install_common_parser.sh"
_TARGET_INSTALL_PATH="${_CURR_PATH}""/../.."
_INSTALL_INFO_SUFFIX="${ops_base_platform_dir}/ascend_install.info"
_VERSION_INFO_SUFFIX="${ops_base_platform_dir}/version.info"

# avoid relative path casued errors by delete floders
_ABS_INSTALL_PATH=$(cd ${_TARGET_INSTALL_PATH}; pwd)
getinstallpath
relative_path_info=${relative_path}
# init log file path
_INSTALL_INFO_FILE="${_ABS_INSTALL_PATH}/${_INSTALL_INFO_SUFFIX}"
if [ ! -f "${_INSTALL_INFO_FILE}" ]; then
    _INSTALL_INFO_FILE="/etc/ascend_install.info"
fi
# this is oam-tools verion info file
_VERSION_INFO_FILE="${_ABS_INSTALL_PATH}/${_VERSION_INFO_SUFFIX}"

# keys of infos in ascend_install.info
KEY_INSTALLED_UNAME="USERNAME"
KEY_INSTALLED_UGROUP="USERGROUP"
KEY_INSTALLED_TYPE="${upper_opp_platform}_INSTALL_TYPE"
KEY_INSTALLED_FEATURE="${upper_opp_platform}_Install_Feature"
KEY_INSTALLED_PATH="${upper_opp_platform}_INSTALL_PATH_VAL"
KEY_INSTALLED_VERSION="${upper_opp_platform}_VERSION"
getinstalledinfo() {
    _key="$1"
    _res=""
    if [ -f "${_INSTALL_INFO_FILE}" ]; then
        chmod 644 "${_INSTALL_INFO_FILE}"> /dev/null 2>&1
        case "${_key}" in
        USERNAME)
            res=$(cat ${_INSTALL_INFO_FILE} | grep "USERNAME" | awk -F = '{print $2}')
            ;;
        USERGROUP)
            res=$(cat ${_INSTALL_INFO_FILE} | grep "USERGROUP" | awk -F = '{print $2}')
            ;;
        ${upper_opp_platform}_INSTALL_TYPE)
            type="INSTALL_TYPE"
            res=$(cat ${_INSTALL_INFO_FILE} | grep "${type}" | awk -F = '{print $2}')
            ;;
        ${upper_opp_platform}_INSTALL_PATH_VAL)
            val="INSTALL_PATH_VAL"
            res=$(cat ${_INSTALL_INFO_FILE} | grep ${val} | awk -F = '{print $2}')
            ;;
        ${upper_opp_platform}_VERSION)
            version="VERSION"
            res=$(cat ${_INSTALL_INFO_FILE} | grep ${version} | awk -F = '{print $2}')
            ;;
        ${upper_opp_platform}_INSTALL_PATH_PARAM)
            param="INSTALL_PATH_PARAM"
            res=$(cat ${_INSTALL_INFO_FILE} | grep ${param} | awk -F = '{print $2}')
            ;;
        esac
    fi
    echo "${res}"
}

logandprint "[INFO]: Begin uninstall the oam-tools module."

# check install folder existed
checkfileexist "${_INSTALL_INFO_FILE}"
logwitherrorlevel "$?" "error" "[ERROR]: ERR_NO:${OPERATE_FAILED};ERR_DES:Uninstall oam-tools module failed."
checkfileexist "${_FILELIST_FILE}"
logwitherrorlevel "$?" "error" "[ERROR]: ERR_NO:${OPERATE_FAILED};ERR_DES:Uninstall oam-tools module failed."
checkfileexist "${_COMMON_PARSER_FILE}"
logwitherrorlevel "$?" "error" "[ERROR]: ERR_NO:${OPERATE_FAILED};ERR_DES:Uninstall oam-tools module failed."
ops_base_sub_dir="${_ABS_INSTALL_PATH}""/${ops_base_platform_dir}"
checkdirectoryexist "${ops_base_sub_dir}"
logwitherrorlevel "$?" "error" "[ERROR]: ERR_NO:${OPERATE_FAILED};ERR_DES:Uninstall oam-tools module failed."

installed_type=$(getinstalledinfo "${KEY_INSTALLED_TYPE}")
checkinstalledtype "${installed_type}"
logwitherrorlevel "$?" "error" "[ERROR]: ERR_NO:${OPERATE_FAILED};ERR_DES:Uninstall oam-tools module failed."

_CUSTOM_PERM="755"
_BUILTIN_PERM="555"
# make the ops_base and the upper folder can write files
is_change_dir_mode="false"
if [ "$(id -u)" != 0 ] && [ ! -w "${_TARGET_INSTALL_PATH}" ]; then
    chmod u+w "${_TARGET_INSTALL_PATH}" 2> /dev/null
    is_change_dir_mode="true"
fi

# change installed folder's permission except aicpu
subdirs=$(ls "${_TARGET_INSTALL_PATH}/${ops_base_platform_dir}" 2> /dev/null)
for dir in ${subdirs}; do
    if [ "${dir}" != "Ascend310" ] && [ "${dir}" != "Ascend310RC" ] && [ "${dir}" != "Ascend910" ] && [ "${dir}" != "Ascend310P" ] && [ "${dir}" != "Ascend" ] && [ "${dir}" != "aicpu" ]; then
        chmod -R "${_CUSTOM_PERM}" "${_TARGET_INSTALL_PATH}/${ops_base_platform_dir}/${dir}" 2> /dev/null
    fi
done
chmod "${_CUSTOM_PERM}" "${_TARGET_INSTALL_PATH}/${ops_base_platform_dir}" 2> /dev/null

get_version "pkg_version" "$_VERSION_INFO_FILE"

# delete oam-tools source files
unsetenv

is_multi_version_pkg "pkg_is_multi_version" "$_VERSION_INFO_FILE "

if [ "${pkg_version_dir}" = "" ]; then
    FINAL_INSTALL_PATH=${_ABS_INSTALL_PATH}
else
    TMP_PATH="${_ABS_INSTALL_PATH}/../../.."
    FINAL_INSTALL_PATH=$(cd ${TMP_PATH}; pwd)
fi

# 赋可写权限
chmod +w -R "${_COMMON_PARSER_FILE}"

sh "${_COMMON_PARSER_FILE}" --package="${ops_base_platform_dir}" --uninstall --recreate-softlink --username="${target_username}" --usergroup="${target_usergroup}" --version=$pkg_version \
    --version-dir=$pkg_version_dir --use-share-info --remove-install-info ${uninstall_option} "${installed_type}" "${FINAL_INSTALL_PATH}" "${_FILELIST_FILE}" "${_CHIP_TYPE}" --recreate-softlink
logwitherrorlevel "$?" "error" "[ERROR]: ERR_NO:${OPERATE_FAILED};ERR_DES:Uninstall oam-tools module failed."


# delete install.info file
if [ "${uninstall_mode}" != "upgrade" ]; then
    logandprint "[INFO]: Delete the install info file (${_INSTALL_INFO_FILE})."
    rm -f "${_INSTALL_INFO_FILE}"
    logwitherrorlevel "$?" "warn" "[WARNING]Delete oam-tools install info file failed, \
please delete it by yourself."
fi

deleteopp(){
    if [ -s "$1" -a -d "$1" ];then
       for file in $(ls -a "$1")
       do
         if [ -f "$1/$file" ];then
           return 1
         fi
        if test -d "$1/$file";then
            if [ "$file" != '.' -a "$file" != '..' ];then
                   return 1
            fi
        fi
       done
       rm -rf -d "$1"
    fi
}

# delete the empty ops_base folder it'self
res_val=$(ls "${ops_base_sub_dir}" 2> /dev/null)
if [ "${res_val}" = "" ]; then
    rm -rf -d "${ops_base_sub_dir}" >> /dev/null 2>&1
fi

# change installed folder's permission except aicpu
subdirs_param=$(ls "${_ABS_INSTALL_PATH}/${ops_base_platform_dir}" 2> /dev/null)
for dir in ${subdirs_param}; do
    if [ "${dir}" != "Ascend310" ] && [ "${dir}" != "Ascend310RC" ] && [ "${dir}" != "Ascend910" ] && [ "${dir}" != "Ascend310P" ] && [ "${dir}" != "Ascend" ] && [ "${dir}" != "aicpu" ]; then
        chmod "${_BUILTIN_PERM}" "${_ABS_INSTALL_PATH}/${ops_base_platform_dir}/${dir}" 2> /dev/null
    fi
done

if [ "${is_change_dir_mode}" = "true" ]; then
    chmod u-w "${_ABS_INSTALL_PATH}" 2> /dev/null
fi

# delete scene.info 
scene_dir="${_ABS_INSTALL_PATH}/${ops_base_platform_dir}/scene.info"
if [ -f ${scene_dir} ]; then
    rm -f ${scene_dir}
fi

# remote atvoss relete softlink
atvoss_dst_dir=${FINAL_INSTALL_PATH}/latest/opp/built-in/op_impl/ai_core/tbe/impl/ascendc/common
chmod u+w "${atvoss_dst_dir}" 2> /dev/null
atvoss_soft_link="${atvoss_dst_dir}""/atvoss"
if [ -L "${atvoss_soft_link}" ];then
    logandprint "[INFO]: Delete the atvoss soft link ("${atvoss_soft_link}")."
    rm -rf "${atvoss_soft_link}"
    logwitherrorlevel "$?" "warn" "[WARNING]Delete atvoss soft link failed, that may cause \
some error to atvoss."
fi
chmod u-w "${atvoss_dst_dir}" 2> /dev/null
atvoss_op_kernel_dst_dir=${FINAL_INSTALL_PATH}/latest/opp/built-in/op_impl/ai_core/tbe/impl/ascendc/common/op_kernel
chmod u+w "${atvoss_op_kernel_dst_dir}" 2> /dev/null
op_kernel_files="math_util.h platform_util.h"
for file_name in $op_kernel_files;
do
    op_kernel_soft_link="${atvoss_op_kernel_dst_dir}""/${file_name}"
    if [ -L "${op_kernel_soft_link}" ];then
        logandprint "[INFO]: Delete the op_kernel soft link (${op_kernel_soft_link})."
        rm -rf "${op_kernel_soft_link}"
        logwitherrorlevel "$?" "warn" "[WARNING]Delete op_kernel atvoss soft link failed, that may cause \
    some error to atvoss."
    fi
done
chmod u-w "${atvoss_op_kernel_dst_dir}" 2> /dev/null

# clean up oam-tools-owned paths under opp/ that filelist.csv either tracks as a directory
# `copy` (skipped by remove_install_files) or doesn't track at all. Without this, an
# uninstall via cann_uninstall.sh leaves libopapi_oam.so plus a tree of empty subdirs
# behind, which in turn prevents the version dir from being removed.
if [ "${uninstall_mode}" != "upgrade" ]; then
    if [ -n "${pkg_version_dir}" ]; then
        oam_install_root="${FINAL_INSTALL_PATH}/${pkg_version_dir}"
    else
        oam_install_root="${FINAL_INSTALL_PATH}"
    fi
    opp_tbe_dir="${oam_install_root}/opp/built-in/op_impl/ai_core/tbe"

    # op_api subtree is created by createOpapiSoftlink during install but is not in
    # filelist.csv; opp_custom_uninstall.sh's softlinksRemove function is undefined
    # in this package, so nothing else cleans it up.
    op_api_dir="${opp_tbe_dir}/op_api"
    if [ -d "${op_api_dir}" ]; then
        logandprint "[INFO]: Delete the op_api directory (${op_api_dir})."
        chmod u+w "${opp_tbe_dir}" 2> /dev/null || true
        chmod -R u+w "${op_api_dir}" 2> /dev/null || true
        rm -rf "${op_api_dir}"
        logwitherrorlevel "$?" "warn" "[WARNING]Delete op_api directory failed, please remove it manually."
    fi

    # config/ and kernel/ are dir-level `copy` entries: remove_install_files skips them,
    # so their chip subdirs (now empty after the `del` entries ran) survive. Use
    # deleteemptyfolders to recursively sweep empty subdirs without touching files
    # owned by other packages.
    for tbe_subdir in "${opp_tbe_dir}/config" "${opp_tbe_dir}/kernel"; do
        if [ -d "${tbe_subdir}" ]; then
            chmod -R u+w "${tbe_subdir}" 2> /dev/null || true
            deleteemptyfolders "${tbe_subdir}"
            if [ "$(ls -A "${tbe_subdir}" 2> /dev/null)" = "" ]; then
                chmod u+w "$(dirname "${tbe_subdir}")" 2> /dev/null || true
                rmdir "${tbe_subdir}" 2> /dev/null || true
            fi
        fi
    done

    # aclnnop/ is another dir-level `copy` entry (filelist line for aclnn_inc). Its
    # contained .h files are tracked as `del` and its `level2/` subdir is mkdir-tracked,
    # so by this point both are gone — but aclnnop/ itself is not mkdir-tracked and
    # survives as an empty directory.
    arch_dir=$(uname -m)
    aclnnop_dir="${oam_install_root}/${arch_dir}-linux/include/aclnnop"
    if [ -d "${aclnnop_dir}" ]; then
        chmod u+w "${aclnnop_dir}" 2> /dev/null || true
        if [ "$(ls -A "${aclnnop_dir}" 2> /dev/null)" = "" ]; then
            chmod u+w "$(dirname "${aclnnop_dir}")" 2> /dev/null || true
            rmdir "${aclnnop_dir}" 2> /dev/null || true
        fi
    fi

    # walk up two parent chains that the parser couldn't fully unwind:
    #   1) opp/built-in/op_impl/ai_core/tbe (held up by op_api/config/kernel above)
    #   2) <arch>-linux/include (held up by aclnnop/ above)
    for chain_leaf in "${opp_tbe_dir}" "${oam_install_root}/${arch_dir}-linux/include"; do
        cleanup_parent="${chain_leaf}"
        while [ "${cleanup_parent}" != "${oam_install_root}" ] && [ "${cleanup_parent}" != "/" ]; do
            if [ -d "${cleanup_parent}" ] && [ "$(ls -A "${cleanup_parent}" 2> /dev/null)" = "" ]; then
                chmod u+w "$(dirname "${cleanup_parent}")" 2> /dev/null || true
                rmdir "${cleanup_parent}" 2> /dev/null || true
            fi
            cleanup_parent="$(dirname "${cleanup_parent}")"
        done
    done
fi

# delete the upper folder when it is empty
dir_existed=$(ls "${_ABS_INSTALL_PATH}" 2> /dev/null)
if [ "${dir_existed}" = "" ] && [ "${uninstall_mode}" != "upgrade" ]; then
    rm -rf -d "${_ABS_INSTALL_PATH}" >> /dev/null 2>&1
fi

# walk up share/info -> share -> <version_dir> (e.g. cann/), removing each parent
# that is now empty. cann_uninstall.sh deletes itself via del_cann_uninstall_package
# at the start of do_remove, so once the package payload is gone the version dir
# itself is just an empty shell that should also be removed.
if [ "${uninstall_mode}" != "upgrade" ]; then
    if [ -n "${pkg_version_dir}" ]; then
        version_root="${FINAL_INSTALL_PATH}/${pkg_version_dir}"
    else
        version_root="${FINAL_INSTALL_PATH}"
    fi
    cleanup_parent="$(dirname "${_ABS_INSTALL_PATH}")"
    while [ -n "${cleanup_parent}" ] && [ "${cleanup_parent}" != "/" ]; do
        if [ -d "${cleanup_parent}" ] && [ "$(ls -A "${cleanup_parent}" 2> /dev/null)" = "" ]; then
            chmod u+w "$(dirname "${cleanup_parent}")" 2> /dev/null || true
            rmdir "${cleanup_parent}" 2> /dev/null || true
        fi
        if [ "${cleanup_parent}" = "${version_root}" ]; then
            break
        fi
        cleanup_parent="$(dirname "${cleanup_parent}")"
    done
fi

subdirs_param_install=$(ls "${installed_path}" 2> /dev/null)
if [ "${subdirs_param_install}" = "" ]; then
    [ -n "${installed_path}" ] && rm -rf "${installed_path}"
fi

logandprint "[INFO]: Oam-tools package uninstalled successfully! Uninstallation takes effect immediately."
exit 0

