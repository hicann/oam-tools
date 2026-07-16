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

add_library(oam_intf_pub INTERFACE)
target_link_libraries(oam_intf_pub INTERFACE
    $<BUILD_INTERFACE:intf_pub>
)

target_compile_options(oam_intf_pub INTERFACE
    $<$<CONFIG:Release>:-O2>
)

target_compile_definitions(oam_intf_pub INTERFACE
    $<$<CONFIG:Release>:_FORTIFY_SOURCE=2>
)
