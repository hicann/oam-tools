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

set(adprofBinHeader
    ../
    ../common
    ../common/utils
    ../common/cmd_log
    ../common/errno
    ../common/logger
    ../common/singleton
    ../depend/include/stub
    ${PROF_BASIC_DIR}/osal
    ${TOP_DIR}/metadef/inc
    ${TOP_DIR}/metadef/inc/external
    ${TOP_DIR}/inc/driver
)

set(adprofbinCpp
    src/adprof_bin.cpp
    ../common/utils/utils.cpp
    ../common/cmd_log/cmd_log.cpp
    ../depend/stub/error_manager/msprof_error_manager_stub.cpp
    ${PROF_BASIC_DIR}/osal/osal.c
)

add_executable(adprof
    ${adprofbinCpp}
)
target_include_directories(adprof PRIVATE
    ${adprofBinHeader}
    ${CMAKE_CURRENT_SOURCE_DIR}
)


target_compile_options(adprof PRIVATE
    -fPIE
    -fno-strict-aliasing
    -fno-common
    -Wall
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wfloat-equal>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wextra>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wno-unused-parameter>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wno-missing-field-initializers>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Werror>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Debug>>:/MTd>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Release>>:/MT>
)

target_compile_definitions(adprof PRIVATE
    google=ascend_private
    $<$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>:NOMINMAX>
    $<$<STREQUAL:${PRODUCT},ascend310rc>:ASCEND310>
    $<$<STREQUAL:${PRODUCT},ascend310>:ASCEND310>
)

target_link_options(adprof PRIVATE
    -Wl,-Bsymbolic
    -Wl,--exclude-libs=ALL
    -Wl,--start-group
    -ldl
)

target_link_libraries(adprof PRIVATE
    $<BUILD_INTERFACE:intf_pub_cxx11>
    $<BUILD_INTERFACE:mmpa_headers>
    $<BUILD_INTERFACE:adump_headers>
    $<BUILD_INTERFACE:slog_headers>
    $<BUILD_INTERFACE:adprofbinOnetrack_pub>
    stackcore
    $<$<STREQUAL:${PRODUCT},ascend910_95>:urma>
    $<$<STREQUAL:${PRODUCT},ascend910_95>:urma_common>
    $<$<STREQUAL:${PRODUCT},ascend910_95esl>:urma>
    $<$<STREQUAL:${PRODUCT},ascend910_95esl>:urma_common>
    $<$<STREQUAL:${PRODUCT},ascend910_96>:urma>
    $<$<STREQUAL:${PRODUCT},ascend910_96>:urma_common>
    $<$<STREQUAL:${PRODUCT},ascend910_96esl>:urma>
    $<$<STREQUAL:${PRODUCT},ascend910_96esl>:urma_common>
)

if ((PRODUCT IN_LIST ASCEND910_95_PRODUCT_LIST) OR (PRODUCT IN_LIST ASCEND910_96_PRODUCT_LIST))
    target_link_directories(adprof PRIVATE
        ${CMAKE_INSTALL_PREFIX}/lib
    )
    add_dependencies(adprof URMA)
endif()

set_target_properties(adprof
    PROPERTIES
    OUTPUT_NAME adprof
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/
)

install(TARGETS adprof OPTIONAL
    LIBRARY DESTINATION ${INSTALL_LIBRARY_DIR}
)

### onetrack target interface

add_library(adprofbinOnetrack_pub INTERFACE)

target_link_libraries(adprofbinOnetrack_pub INTERFACE
    $<BUILD_INTERFACE:intf_pub_cxx11>
    c_sec
    slog
    mmpa
    ascend_hal
    -lpthread
)