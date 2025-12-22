#!/bin/csh
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

#!/usr/bin/env csh
if ( "-${argv}" != "-" ) then
    set CUR_FILE=${argv}
else
    set CUR_FILE=`readlink -f $0`
endif
set CUR_DIR=`dirname ${CUR_FILE}`
set version_dir=`cat "$CUR_DIR/../version.info" | grep "version_dir" | cut -d"=" -f2`
if ( "-$version_dir" == "-" ) then
    set INSTALL_DIR=`realpath ${CUR_DIR}/../..`
else
    set INSTALL_DIR=`realpath ${CUR_DIR}/../../../latest`
endif

set toolchain_path="${INSTALL_DIR}"
if ( -d ${toolchain_path} ) then
    
set MYPATH=""
if ( $?TOOLCHAIN_HOME == 1 ) then
    set MYPATH="$TOOLCHAIN_HOME"
endif

set MYPATH=`echo "$MYPATH" | tr ':' '\n' | grep -v '^'${toolchain_path}'$' | tr '\n' ':' | sed 's/:$/\n/'`

if ("$MYPATH" == "") then
    setenv TOOLCHAIN_HOME "${toolchain_path}"
else
    setenv TOOLCHAIN_HOME "${toolchain_path}:${MYPATH}"
endif

endif

set lib_path="${INSTALL_DIR}/python/site-packages/"
if (-d ${lib_path}) then
    
set MYPATH=""
if ( $?PYTHONPATH == 1 ) then
    set MYPATH="$PYTHONPATH"
endif

set MYPATH=`echo "$MYPATH" | tr ':' '\n' | grep -v '^'${lib_path}'$' | tr '\n' ':' | sed 's/:$/\n/'`

if ("$MYPATH" == "") then
    setenv PYTHONPATH "${lib_path}"
else
    setenv PYTHONPATH "${lib_path}:${MYPATH}"
endif

endif

set op_tools_path="${INSTALL_DIR}/python/site-packages/bin/"
if (-d ${op_tools_path}) then
    
set MYPATH=""
if ( $?PATH == 1 ) then
    set MYPATH="$PATH"
endif

set MYPATH=`echo "$MYPATH" | tr ':' '\n' | grep -v '^'${op_tools_path}'$' | tr '\n' ':' | sed 's/:$/\n/'`

if ("$MYPATH" == "") then
    setenv PATH "${op_tools_path}"
else
    setenv PATH "${op_tools_path}:${MYPATH}"
endif

endif

set msprof_path="${INSTALL_DIR}/tools/profiler/bin/"
if (-d ${msprof_path}) then
    
set MYPATH=""
if ( $?PATH == 1 ) then
    set MYPATH="$PATH"
endif

set MYPATH=`echo "$MYPATH" | tr ':' '\n' | grep -v '^'${msprof_path}'$' | tr '\n' ':' | sed 's/:$/\n/'`

if ("$MYPATH" == "") then
    setenv PATH "${msprof_path}"
else
    setenv PATH "${msprof_path}:${MYPATH}"
endif

endif

set ascend_ml_path="${INSTALL_DIR}/tools/aml/lib64"
if (-d ${ascend_ml_path}) then
    
set MYPATH=""
if ( $?LD_LIBRARY_PATH == 1 ) then
    set MYPATH="$LD_LIBRARY_PATH"
endif

set MYPATH=`echo "$MYPATH" | tr ':' '\n' | grep -v '^'${ascend_ml_path}:${ascend_ml_path}/plugin'$' | tr '\n' ':' | sed 's/:$/\n/'`

if ("$MYPATH" == "") then
    setenv LD_LIBRARY_PATH "${ascend_ml_path}:${ascend_ml_path}/plugin"
else
    setenv LD_LIBRARY_PATH "${ascend_ml_path}:${ascend_ml_path}/plugin:${MYPATH}"
endif

endif

set asys_path="${INSTALL_DIR}/tools/ascend_system_advisor/asys"
if (-d ${asys_path}) then
    
set MYPATH=""
if ( $?PATH == 1 ) then
    set MYPATH="$PATH"
endif

set MYPATH=`echo "$MYPATH" | tr ':' '\n' | grep -v '^'${asys_path}'$' | tr '\n' ':' | sed 's/:$/\n/'`

if ("$MYPATH" == "") then
    setenv PATH "${asys_path}"
else
    setenv PATH "${asys_path}:${MYPATH}"
endif

endif

set ccec_compiler_path="${INSTALL_DIR}/tools/ccec_compiler/bin"
if (-d ${ccec_compiler_path}) then
    
set MYPATH=""
if ( $?PATH == 1 ) then
    set MYPATH="$PATH"
endif

set MYPATH=`echo "$MYPATH" | tr ':' '\n' | grep -v '^'${ccec_compiler_path}'$' | tr '\n' ':' | sed 's/:$/\n/'`

if ("$MYPATH" == "") then
    setenv PATH "${ccec_compiler_path}"
else
    setenv PATH "${ccec_compiler_path}:${MYPATH}"
endif

endif

set msobjdump_path="${INSTALL_DIR}/tools/msobjdump/"
if (-d ${msobjdump_path}) then
    
set MYPATH=""
if ( $?PATH == 1 ) then
    set MYPATH="$PATH"
endif

set MYPATH=`echo "$MYPATH" | tr ':' '\n' | grep -v '^'${msobjdump_path}'$' | tr '\n' ':' | sed 's/:$/\n/'`

if ("$MYPATH" == "") then
    setenv PATH "${msobjdump_path}"
else
    setenv PATH "${msobjdump_path}:${MYPATH}"
endif

endif

set show_kernel_debug_data_tool_path="${INSTALL_DIR}/tools/show_kernel_debug_data/"
if (-d ${show_kernel_debug_data_tool_path}) then
    
set MYPATH=""
if ( $?PATH == 1 ) then
    set MYPATH="$PATH"
endif

set MYPATH=`echo "$MYPATH" | tr ':' '\n' | grep -v '^'${show_kernel_debug_data_tool_path}'$' | tr '\n' ':' | sed 's/:$/\n/'`

if ("$MYPATH" == "") then
    setenv PATH "${show_kernel_debug_data_tool_path}"
else
    setenv PATH "${show_kernel_debug_data_tool_path}:${MYPATH}"
endif

endif