# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd. All Rights Reserved.
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

############ intf_pub c++17 ############
add_library(intf_llt_pub INTERFACE)
target_compile_options(intf_llt_pub INTERFACE
    $<$<COMPILE_LANGUAGE:CXX>:-std=c++17>
)
target_link_libraries(intf_llt_pub INTERFACE
    $<BUILD_INTERFACE:intf_pub_cxx17>
    c_sec
    dl
    GTest::gtest
    GTest::gtest_main
    ${ASCEND_3RD_LIB_PATH}/mockcpp/lib/libmockcpp.a
)

set(LLT_EXTEND_INCLUDE_DIR
    ${runtime_INCLUDE_DIR}
    ${third_party_INCLUDE_DIR}
    ${MOCKCPP_INCLUDE_DIR}
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/profiling
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/runtime
)

add_subdirectory(ut/msprof/msprofbin)