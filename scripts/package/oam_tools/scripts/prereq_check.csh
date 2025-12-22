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

set FILE_NOT_EXIST="0x0080"

set cur_date=`date +"%Y-%m-%d %H:%M:%S"`
echo "[Oam-tools][${cur_date}][INFO]: Start pre installation check of oam-tools module."
python3 --version >/dev/null 2>&1
if ($status != "0") then
set cur_date=`date +"%Y-%m-%d %H:%M:%S"`
exit 0
endif
set python_version=`python3 --version`
set idx=`echo ${python_version} | awk '{print index($0, "3.7.5")}'`
if ($idx > 0) then
set cur_date=`date +"%Y-%m-%d %H:%M:%S"`
exit 0
else
set cur_date=`date +"%Y-%m-%d %H:%M:%S"`
exit 0
endif
