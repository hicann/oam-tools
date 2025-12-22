#!/usr/bin/env fish
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

function mk_custom_path
    set -l custom_file_path $argv[1]
    if test (id -u) -eq 0
        return 0
    end
    while read line
        set -l _custom_path (echo "$line" | cut --only-delimited -d= -f2)
        if test -z $_custom_path
            continue
        end
        set -l _custom_path (eval echo "$_custom_path")
        if not test -d $_custom_path
            mkdir -p "$_custom_path"
            if not test $status -eq 0
                set -l cur_date (date +"%Y-%m-%d %H:%M:%S")
                echo "[Common] [$cur_date] [ERROR]: create $_custom_path failed."
                return 1
            end
        end
    end < $custom_file_path
    return 0
end
