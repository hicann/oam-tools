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

# 替代 third_party_INCLUDE_DIR 的头文件目标（adcore 头文件，指向项目源树）
add_library(stub_adcore_headers INTERFACE)
target_include_directories(stub_adcore_headers INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR}/src/third_party
    ${CMAKE_CURRENT_SOURCE_DIR}/src/third_party/adcore
)
