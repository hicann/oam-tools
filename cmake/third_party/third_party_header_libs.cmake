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

# 添加头文件库slog_headers
set(slog_INCLUDE_DIR "${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/base")
add_library(slog_headers INTERFACE IMPORTED)
set_target_properties(slog_headers PROPERTIES
    INTERFACE_INCLUDE_DIRECTORIES "${slog_INCLUDE_DIR}"
)

# 添加头文件库mmpa_headers
set(mmpa_INCLUDE_DIR "${ASCEND_CANN_PACKAGE_PATH}/include")
add_library(mmpa_headers INTERFACE IMPORTED)
set_target_properties(mmpa_headers PROPERTIES
    INTERFACE_INCLUDE_DIRECTORIES "${mmpa_INCLUDE_DIR};${mmpa_INCLUDE_DIR}/mmpa;${mmpa_INCLUDE_DIR}/mmpa/sub_inc"
)

# 添加头文件库adump_headers
set(adump_INCLUDE_DIR "${ASCEND_CANN_PACKAGE_PATH}/pkg_inc")
add_library(adump_headers INTERFACE IMPORTED)
set_target_properties(adump_headers PROPERTIES
    INTERFACE_INCLUDE_DIRECTORIES "${adump_INCLUDE_DIR};${adump_INCLUDE_DIR}/dump"
)

# 查找动态库libascendalog.so
find_library(alog_SHARED_LIBRARY
    NAMES libascendalog.so
    PATH_SUFFIXES lib64
    NO_CMAKE_SYSTEM_PATH
    NO_CMAKE_FIND_ROOT_PATH)

# 添加导入的共享库alog
add_library(alog SHARED IMPORTED)
set_target_properties(alog PROPERTIES
    INTERFACE_COMPILE_DEFINITIONS "LOG_CPP;PROCESS_LOG"
    INTERFACE_LINK_LIBRARIES "slog_headers"
    IMPORTED_LOCATION "${alog_SHARED_LIBRARY}"
)

# 添加Runtime中依赖的文件地址
set(runtime_INCLUDE_DIR
    ${ASCEND_CANN_PACKAGE_PATH}/include
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/dump
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/aicpu
)

# 添加Driver中依赖的文件地址
set(third_party_INCLUDE_DIR
    ${CMAKE_CURRENT_SOURCE_DIR}/src/third_party
    ${CMAKE_CURRENT_SOURCE_DIR}/src/third_party/driver
    ${CMAKE_CURRENT_SOURCE_DIR}/src/third_party/adcore
    ${CMAKE_CURRENT_SOURCE_DIR}/src/third_party/metadef
)