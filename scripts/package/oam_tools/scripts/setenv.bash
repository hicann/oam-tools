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

#!/bin/bash
# common functions
append_env() {
    local name="$1"
    local value="$2"
    local env_value="$(eval echo "\${${name}}" | tr ':' '\n' | grep -v "^${value}$" | tr '\n' ':' | sed 's/:$/\n/')"

    if [ "$env_value" = "" ]; then
        read $name <<EOF
$value
EOF
    else
        read $name <<EOF
$env_value:$value
EOF
    fi
    export $name
}

prepend_env() {
    local name="$1"
    local value="$2"
    local env_value="$(eval echo "\${${name}}" | tr ':' '\n' | grep -v "^${value}$" | tr '\n' ':' | sed 's/:$/\n/')"
    if [ "$env_value" = "" ]; then
        read $name <<EOF
$value
EOF
    else
        read $name <<EOF
$value:$env_value
EOF
    fi
    export $name
}

remove_env() {
    local name="$1"
    local value="$2"

    read $name <<EOF
$(eval echo "\${${name}}" | tr ':' '\n' | grep -v "^${value}$" | tr '\n' ':' | sed 's/:$/\n/')
EOF
    export $name
}

CUR_DIR=`dirname ${BASH_SOURCE[0]}`

version_dir=`cat "$CUR_DIR/../version.info" | grep "version_dir" | cut -d"=" -f2`
if [ -z "$version_dir" ]; then
    INSTALL_DIR=`realpath ${CUR_DIR}/../..`
else
    INSTALL_DIR=`realpath ${CUR_DIR}/../../../../../cann`
fi

toolchain_path="${INSTALL_DIR}/toolkit"
if [ -d ${toolchain_path} ]; then
    prepend_env TOOLCHAIN_HOME "$toolchain_path"
fi

lib_path="${INSTALL_DIR}/python/site-packages/"
if [ -d ${lib_path} ]; then
    prepend_env PYTHONPATH "$lib_path"
fi

op_tools_path="${INSTALL_DIR}/python/site-packages/bin/"
if [ -d ${op_tools_path} ]; then
    prepend_env PATH "$op_tools_path"
fi

msprof_path="${INSTALL_DIR}/tools/profiler/bin/"
if [ -d ${msprof_path} ]; then
    prepend_env PATH "$msprof_path"
fi

ascend_ml_library_path="${INSTALL_DIR}/tools/aml/lib64"
if [ -d ${ascend_ml_library_path} ]; then
    prepend_env LD_LIBRARY_PATH "${ascend_ml_library_path}:${ascend_ml_library_path}/plugin"
fi

asys_path="${INSTALL_DIR}/tools/ascend_system_advisor/asys"
if [ -d ${asys_path} ]; then
    prepend_env PATH "$asys_path"
fi

ccec_compiler_path="${INSTALL_DIR}/tools/ccec_compiler/bin"
if [ -d ${ccec_compiler_path} ]; then
    prepend_env PATH "$ccec_compiler_path"
fi

ascc_path="${INSTALL_DIR}/tools/ascc"
if [ -d ${ascc_path} ]; then
    prepend_env PATH "$ascc_path"
fi

profiler_lib_path="${INSTALL_DIR}/tools/profiler/lib64"
if [ -d ${profiler_lib_path} ]; then
    prepend_env LD_LIBRARY_PATH "${profiler_lib_path}:${profiler_lib_path}/plugin"
fi

msobjdump_path="${INSTALL_DIR}/tools/msobjdump/"
if [ -d ${msobjdump_path} ]; then
    prepend_env PATH "$msobjdump_path"
fi

show_kernel_debug_data_tool_path="${INSTALL_DIR}/tools/show_kernel_debug_data/"
if [ -d ${show_kernel_debug_data_tool_path} ]; then
    prepend_env PATH "$show_kernel_debug_data_tool_path"
fi

toolkit_lib_path="${INSTALL_DIR}/tools/adump/lib64/"
if [ -d ${toolkit_lib_path} ]; then
    prepend_env LD_LIBRARY_PATH "$toolkit_lib_path"
fi