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

# 公共变量：msprof collector 源码根目录，供各子目录 UT 复用
set(MSPROF_SOURCE_DIR ${TOP_DIR}/src/msprof/collector)

############ intf_pub c++17 ############
# 各 msprof UT target 公共链接接口库
add_library(intf_llt_pub INTERFACE)
target_compile_options(intf_llt_pub INTERFACE
    $<$<COMPILE_LANGUAGE:CXX>:-std=c++17>
)
target_link_libraries(intf_llt_pub INTERFACE
    $<BUILD_INTERFACE:intf_pub_cxx17>
    c_sec
    dl
    GTestShared::gtest
    GTestShared::gtest_main
    mockcpp
)

# 各 msprof UT target 公共扩展头文件目录
set(LLT_EXTEND_INCLUDE_DIR
    ${runtime_INCLUDE_DIR}
    ${third_party_INCLUDE_DIR}
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/profiling
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/runtime
)

# ----------------------------------------------------------------------------
# 新增 msprof UT target 时，只需：
#   1) 在本目录下新建子目录（含其 CMakeLists.txt 与可执行 UT target）
#   2) 把该子目录名追加到 MSPROF_UT_SUBDIRS
# 无需改动 scripts/run_tests.sh —— 运行清单由下方自动生成。
# ----------------------------------------------------------------------------
set(MSPROF_UT_SUBDIRS
    acp
    app
    common
    driver
    job_wrapper
    message
    msprofbin
    transport
)

# 逐个加入子目录，并自动收集其中的可执行 UT target
set(_msprof_ut_targets "")
foreach(_subdir ${MSPROF_UT_SUBDIRS})
    add_subdirectory(${_subdir})
    get_property(_subdir_targets
        DIRECTORY ${_subdir}
        PROPERTY BUILDSYSTEM_TARGETS
    )
    foreach(_tgt ${_subdir_targets})
        get_target_property(_tgt_type ${_tgt} TYPE)
        if(_tgt_type STREQUAL "EXECUTABLE")
            list(APPEND _msprof_ut_targets ${_tgt})
        endif()
    endforeach()
endforeach()

# 生成 UT 可执行文件清单，供 scripts/run_tests.sh 读取运行
set(_msprof_ut_manifest_content "")
foreach(_tgt ${_msprof_ut_targets})
    string(APPEND _msprof_ut_manifest_content "$<TARGET_FILE:${_tgt}>\n")
endforeach()
file(GENERATE
    OUTPUT ${CMAKE_BINARY_DIR}/msprof_ut_targets.txt
    CONTENT "${_msprof_ut_manifest_content}"
)
