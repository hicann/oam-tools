#!/usr/bin/fish
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

#!/usr/bin/env fish
set -x CUR_DIR (realpath (dirname (status --current-filename)))

# common functions
function append_env
    set -l name $argv[1]
    set -l value $argv[2..-1]
    set -l MYPATH
    set -l path
    for path in $$name
        if not contains "$path" $value
            set MYPATH $MYPATH $path
        end
    end
    set -gx $name $MYPATH $value
end

function prepend_env
    set -l name $argv[1]
    set -l value $argv[2..-1]
    set -l MYPATH
    set -l path
    for path in $$name
        if not contains "$path" $value
            set MYPATH $MYPATH $path
        end
    end
    set -gx $name $value $MYPATH
end

function remove_env
    set -l name $argv[1]
    set -l value $argv[2..-1]
    set -l MYPATH
    set -l path
    for path in $$name
        if not contains "$path" $value
            set MYPATH $MYPATH $path
        end
    end
    set -gx $name $MYPATH
end


function get_install_dir
    set -lx version_dir (cat "$CUR_DIR/../version.info" | grep "version_dir" | cut -d"=" -f2)
    if test "-$version_dir" = "-"
        echo (realpath $CUR_DIR/../..)
    else
        echo (realpath $CUR_DIR/../../../latest)
    end
end
set -x INSTALL_DIR (get_install_dir)

set -x toolchain_path "$INSTALL_DIR"
if test -d {$toolchain_path}
    prepend_env TOOLCHAIN_HOME "$toolchain_path"
end
set -e toolchain_path

set -x lib_path "$INSTALL_DIR/python/site-packages/"
if test -d $lib_path
    prepend_env PYTHONPATH "$lib_path"
end
set -e lib_path

set -x op_tools_path "$INSTALL_DIR/python/site-packages/bin/"
if test -d $op_tools_path
    prepend_env PATH "$op_tools_path"
end
set -e op_tools_path

set -x msprof_path "$INSTALL_DIR/tools/profiler/bin/"
if test -d $msprof_path
    prepend_env PATH "$msprof_path"
end
set -e msprof_path

set -x ascend_ml_path "$INSTALL_DIR/tools/aml/lib64"
if test -d $ascend_ml_path
    prepend_env LD_LIBRARY_PATH "$ascend_ml_path" "$ascend_ml_path/plugin"
fi
set -e ascend_ml_path

set -x asys_path "$INSTALL_DIR/tools/ascend_system_advisor/asys"
if test -d asys_path
    prepend_env PATH "$asys_path"
end
set -e asys_path

set -x ccec_compiler_path "$INSTALL_DIR/tools/ccec_compiler/bin"
if test -d $ccec_compiler_path
    prepend_env PATH "$ccec_compiler_path"
end
set -e ccec_compiler_path

set -x msobjdump_path "$INSTALL_DIR/tools/msobjdump/"
if test -d $msobjdump_path
    prepend_env PATH "$msobjdump_path"
end
set -e msobjdump_path

set -x ascendump_path "$INSTALL_DIR/tools/show_kernel_debug_data/"
if test -d $ascendump_path
    prepend_env PATH "$ascendump_path"
end
set -e ascendump_path