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

# 本文件被 dvvp 及多个子目录 include，用 include_guard 保证一次配置内只执行一次，避免
# find_path 查找、message(WARNING) 等重复执行。
include_guard(GLOBAL)

# runtime_headers —— 复现 cann-cmake Findruntime.cmake：find_path 定位各头文件根后拼子目录
if(NOT TARGET runtime_headers)
    find_path(runtime_INCLUDE_DIR
        NAMES pkg_inc/runtime/rt_external.h
        NO_CMAKE_SYSTEM_PATH
        NO_CMAKE_FIND_ROOT_PATH)
    find_path(_CANN_AICPU_INCLUDE_DIR
        NAMES aicpu_engine_struct.h
        PATH_SUFFIXES pkg_inc/aicpu
        NO_CMAKE_SYSTEM_PATH
        NO_CMAKE_FIND_ROOT_PATH)
    find_path(runtime_acl_INCLUDE_DIR
        NAMES acl/error_codes/rt_error_codes.h
        NO_CMAKE_SYSTEM_PATH
        NO_CMAKE_FIND_ROOT_PATH)
    add_library(runtime_headers INTERFACE IMPORTED)
    if(runtime_INCLUDE_DIR AND _CANN_AICPU_INCLUDE_DIR AND runtime_acl_INCLUDE_DIR)
        set_target_properties(runtime_headers PROPERTIES
            INTERFACE_INCLUDE_DIRECTORIES
                "${runtime_INCLUDE_DIR};${runtime_INCLUDE_DIR}/pkg_inc;${runtime_INCLUDE_DIR}/pkg_inc/aicpu/common;${runtime_INCLUDE_DIR}/pkg_inc/dump;${runtime_INCLUDE_DIR}/pkg_inc/runtime;${runtime_INCLUDE_DIR}/pkg_inc/runtime/runtime;${runtime_INCLUDE_DIR}/pkg_inc/runtime/runtime/rts;${runtime_INCLUDE_DIR}/pkg_inc/profiling;${_CANN_AICPU_INCLUDE_DIR};${_CANN_AICPU_INCLUDE_DIR}/aicpu_schedule;${runtime_acl_INCLUDE_DIR};${runtime_acl_INCLUDE_DIR}/acl;${runtime_acl_INCLUDE_DIR}/acl/error_codes"
        )
    else()
        message(WARNING "runtime headers not found (runtime_INCLUDE_DIR/_CANN_AICPU_INCLUDE_DIR/runtime_acl_INCLUDE_DIR), runtime_headers left without include dirs")
    endif()
endif()

# runtime_inc_headers —— 复现 cmake/dependencies.cmake：INTERFACE 目标转链 runtime_headers
if(NOT TARGET runtime_inc_headers)
    add_library(runtime_inc_headers INTERFACE)
    target_link_libraries(runtime_inc_headers INTERFACE
        runtime_headers
    )
endif()

# stub_adcore_headers —— 复现 cmake/third_party/third_party_header_libs.cmake：指向项目源树。
# 顶层入口用 ${CMAKE_CURRENT_SOURCE_DIR}（仓库根）；本文件被不同层级子目录 include，故用
# ${CMAKE_CURRENT_LIST_DIR}（本文件所在 src/msprof/collector/dvvp）上溯 4 级定位仓库根，
# 不随 include 者所在目录变化。
if(NOT TARGET stub_adcore_headers)
    add_library(stub_adcore_headers INTERFACE)
    target_include_directories(stub_adcore_headers INTERFACE
        ${CMAKE_CURRENT_LIST_DIR}/../../../../src/third_party
        ${CMAKE_CURRENT_LIST_DIR}/../../../../src/third_party/adcore
    )
endif()