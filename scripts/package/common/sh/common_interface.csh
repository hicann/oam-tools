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

set func_name = "$1"
switch ( "$func_name" )
    case "mk_custom_path":
        if ( "`id -u`" == 0 ) then
            exit 0
        endif
        set file_path = "$2"
        foreach line ("` cat $file_path `")
            set custom_path = "`echo '$line' | cut --only-delimited -d= -f2`"
            if ( "$custom_path" == "" ) then
                continue
            endif
            set custom_path = "` eval echo $custom_path `"
            if ( ! -d "$custom_path" ) then
                mkdir -p "$custom_path"
                if ( $status != 0 ) then
                    set cur_date = "`date +'%Y-%m-%d %H:%M:%S'`"
                    echo "[Common] [$cur_date] [ERROR]: create $custom_path failed."
                    exit 1
                endif
            endif
        end
        breaksw
    default:
        breaksw
endsw
