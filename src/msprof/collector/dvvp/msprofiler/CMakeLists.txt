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

####################### libmsprofiler.so #########################
set(msprofilerCpp
    ../common/utils/utils.cpp
    ../common/cmd_log/cmd_log.cpp
    ${PROF_BASIC_DIR}/osal/osal.c
    prof_api_common.cpp
)

set(msprofilerInc
   ${TOP_DIR}/graphengine/inc
   ${TOP_DIR}/inc/external
   ${TOP_DIR}/graphengine/inc/external
   ${TOP_DIR}/graphengine/inc/framework/common
   ${TOP_DIR}/metadef/inc
   ../
   ../common
   ../common/utils
   ../common/cmd_log
   ../common/logger
   ../common/json
   ${PROF_BASIC_DIR}/osal
   ../analyze/inc
)

set(msprofilerFwcSrc
    ${msprofilerCpp}
    prof_ge_core.cpp
)

add_library(msprofiler_fwk_share SHARED
    ${msprofilerFwcSrc}
    prof_acl_core.cpp
    prof_acl_api.cpp
    prof_api_runtime.cpp
)

target_include_directories(msprofiler_fwk_share PRIVATE
    ${msprofilerInc}
    ../profapi/inc
    ../depend/include/wrapper
    ${TOP_DIR}/metadef/inc/external
)

set_target_properties(msprofiler_fwk_share
    PROPERTIES
    OUTPUT_NAME $<IF:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,libmsprofiler,msprofiler>
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/
)

target_compile_definitions(msprofiler_fwk_share PRIVATE
    google=ascend_private
    $<$<STREQUAL:${CMAKE_BUILD_TYPE},Debug>:MSPROF_DEBUG>
    $<$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>:NOMINMAX>
    $<$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>:WIN32>
)

target_compile_options(msprofiler_fwk_share PRIVATE
    -fPIC
    -fstack-protector-all
    -fno-strict-aliasing
    -fno-common
    -fvisibility=hidden
    -fvisibility-inlines-hidden
    -Wall
    -Wextra
    -Wfloat-equal
    $<$<CONFIG:Release>:-D_FORTIFY_SOURCE=2 -Os>
    $<$<CONFIG:Debug>:-D_FORTIFY_SOURCE=2 -Os>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Debug>>:/MTd>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Release>>:/MT>
)

target_link_options(msprofiler_fwk_share PRIVATE
    -Wl,-z,relro,-z,now,-z,noexecstack
    -Wl,-Bsymbolic
    -Wl,--exclude-libs=ALL
)

if (PRODUCT)
    if (${TARGET_SYSTEM_NAME} STREQUAL "Windows")
        target_link_libraries(msprofiler_fwk_share PRIVATE
            ascend_hal
        )
    else()
        target_link_libraries(msprofiler_fwk_share PRIVATE
            ascend_hal_stub
        )
    endif()
endif()

target_link_libraries(msprofiler_fwk_share
    PRIVATE
        intf_pub_cxx11
        slog_headers
        mmpa_headers
        adump_headers
        runtime_headers
        -Wl,--no-as-needed
        c_sec
        alog
        mmpa
        profapi_share
        error_manager
        -Wl,--as-needed
    PUBLIC
        msprof_headers
)

if (WIN32)
    set(msprof_targets msprofiler_fwk_share msprof_headers)
else()
    set(msprof_targets msprofiler_fwk_share profapi_share msprof_headers)
endif()
install_package(
    PACKAGE msprof
    TARGETS ${msprof_targets}
    FILES   ${MSPROF_DIR}/inc/toolchain/prof_acl_api.h
            ${MSPROF_DIR}/inc/toolchain/prof_api.h
            ${MSPROF_DIR}/inc/toolchain/prof_common.h
            ${MSPROF_DIR}/inc/toolchain/prof_data_config.h
            ${MSPROF_DIR}/inc/toolchain/prof_engine.h
            ${MSPROF_DIR}/inc/toolchain/prof_reporter.h
            ${MSPROF_DIR}/inc/toolchain/devprof_pub.h
            ${MSPROF_DIR}/inc/toolchain/aprof_pub.h
    DESTINATION ${INSTALL_INCLUDE_DIR}/msprof/toolchain
)
####################### libmsprofiler.so #########################

####################### libmsprofiler_lite.so #########################
set(msprofilerLiteInc
   ${TOP_DIR}/inc/external
   ${TOP_DIR}/metadef/inc
   ${TOP_DIR}/metadef/inc/external
   ${PROF_BASIC_DIR}/osal
   ../
   ../common
   ../common/logger
   ../common/json
)

add_library(msprofiler_fwk_lite_share SHARED
    prof_acl_api.cpp
    prof_api_runtime.cpp
)

target_include_directories(msprofiler_fwk_lite_share PRIVATE
    ${msprofilerLiteInc}
    ../profapi/inc
    ../depend/include/wrapper
)

set_target_properties(msprofiler_fwk_lite_share
    PROPERTIES
    OUTPUT_NAME msprofiler
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/proflib
)

target_compile_definitions(msprofiler_fwk_lite_share PRIVATE
    PROF_LITE
    OSAL
    $<$<STREQUAL:${CMAKE_BUILD_TYPE},Debug>:MSPROF_DEBUG>
)

target_compile_options(msprofiler_fwk_lite_share PRIVATE
    -fPIC
    -fstack-protector-all
    -fno-strict-aliasing
    -fno-common
    -fvisibility=hidden
    -fvisibility-inlines-hidden
    -Wall
    -Wextra
    -Wfloat-equal
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Debug>>:/MTd>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Release>>:/MT>
)

target_link_options(msprofiler_fwk_lite_share PRIVATE
    -Wl,-z,relro,-z,now,-z,noexecstack
    -Wl,-Bsymbolic
    -Wl,--exclude-libs=ALL
)

target_link_libraries(msprofiler_fwk_lite_share
    PRIVATE
        mmpa_headers
        intf_pub_cxx11
        slog_headers
        -Wl,--no-as-needed
        c_sec
        alog
        profapi_lite_share
        -Wl,--as-needed
        mmpa
    PUBLIC
        msprof_headers
)

install(TARGETS msprofiler_fwk_lite_share OPTIONAL
    LIBRARY DESTINATION ${INSTALL_LIBRARY_DIR}/lib
)
####################### libmsprofiler_lite.so #########################

####################### libmsprofiler static lib for windows ###########################
if(${TARGET_SYSTEM_NAME} STREQUAL "Windows")
add_library(msprofiler STATIC
    ${msprofilerFwcSrc}
    prof_acl_core.cpp
    ../depend/stub/error_manager/msprof_error_manager_stub.cpp
    ${hdcCpp}
)

target_include_directories(msprofiler PRIVATE
    ${msprofilerInc}
    ${TOP_DIR}/graphengine/inc
    ${TOP_DIR}/graphengine/inc/framework
    ${TOP_DIR}/metadef/inc
    ${TOP_DIR}/metadef/inc/external
    ../depend/include/stub
    ../profapi/inc
)

set_target_properties(msprofiler
    PROPERTIES
    OUTPUT_NAME msprofiler
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/
)

target_compile_definitions(msprofiler PRIVATE
    google=ascend_private
    FUNC_VISIBILITY
    $<$<STREQUAL:${CMAKE_BUILD_TYPE},Debug>:MSPROF_DEBUG>
    $<$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>:NOMINMAX>
    $<$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>:WIN32>
)

target_compile_options(msprofiler PRIVATE
    -fvisibility=hidden
    -fvisibility-inlines-hidden
    -fPIC
    -fstack-protector-all
    -fno-strict-aliasing
    -fno-common
    -Wall
    -std=c++11
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Debug>>:/MTd>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Release>>:/MT>
)

target_link_options(msprofiler PRIVATE
    -Wl,-z,relro,-z,now,-z,noexecstack
    -Wl,-Bsymbolic
    -Wl,--exclude-libs=ALL
)

target_link_libraries(msprofiler PRIVATE
    $<BUILD_INTERFACE:intf_pub_cxx11>
    $<BUILD_INTERFACE:mmpa_headers>
    $<BUILD_INTERFACE:msprof_headers>
    $<BUILD_INTERFACE:adump_headers>
    $<BUILD_INTERFACE:slog_headers>
    $<BUILD_INTERFACE:runtime_headers>
    -Wl,--no-as-needed
    c_sec
    alog
    mmpa
    ge_executor
    runtime
    $<$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>:ascend_hal>
    -Wl,--as-needed
)

install(TARGETS msprofiler OPTIONAL
    LIBRARY DESTINATION ${INSTALL_LIBRARY_DIR}
)
endif()
####################### libmsprofiler static lib for windows ###########################

############################## msprofiler stub ################################
set(MSPROF_STUB_INC ${MSPROF_DIR}/inc/external)
add_custom_target(
    stub_msprof_src ALL
    DEPENDS  ${CMAKE_CURRENT_BINARY_DIR}/acl_prof_stub.cpp
             ${CMAKE_CURRENT_BINARY_DIR}/ge_prof_stub.cpp
)
add_custom_command(
    OUTPUT  ${CMAKE_CURRENT_BINARY_DIR}/acl_prof_stub.cpp
            ${CMAKE_CURRENT_BINARY_DIR}/ge_prof_stub.cpp
    COMMAND echo "Generating stub files:acl_prof_stub.cpp, ge_prof_stub.cpp."
            && ${HI_PYTHON} ${MSPROF_DIR}/build/stub/gen_stubapi.py ${MSPROF_STUB_INC}
            ${CMAKE_CURRENT_BINARY_DIR}/acl_prof_stub.cpp
            ${CMAKE_CURRENT_BINARY_DIR}/ge_prof_stub.cpp
            && echo "Generating stub files end."
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
    DEPENDS ${MSPROF_DIR}/build/stub/gen_stubapi.py ${MSPROF_STUB_INC}
)
############################## msprofiler stub ################################

###################### stub/libmsprofiler.so #######################

add_library(stub_msprofiler SHARED
    ${CMAKE_CURRENT_BINARY_DIR}/acl_prof_stub.cpp
    ${CMAKE_CURRENT_BINARY_DIR}/ge_prof_stub.cpp
)

set_target_properties(stub_msprofiler
    PROPERTIES
    OUTPUT_NAME msprofiler
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/stub
)

target_include_directories(stub_msprofiler PRIVATE
    ${MSPROF_STUB_INC}
    ${TOP_DIR}/inc/external/acl
    ${TOP_DIR}/inc/external
    ${TOP_DIR}/graphengine/inc/external
    ${TOP_DIR}/metadef/inc/external
)

target_compile_options(stub_msprofiler PRIVATE
    -fPIC
    -fstack-protector-all
    -fno-strict-aliasing
    -fno-common
    -Wall
    -std=c++11
    -fvisibility=hidden
    -fvisibility-inlines-hidden
    -Wfloat-equal
    -Wextra
    $<$<CONFIG:Release>:-D_FORTIFY_SOURCE=2 -Os>
    $<$<CONFIG:Debug>:-D_FORTIFY_SOURCE=2 -Os>
)

target_link_libraries(stub_msprofiler PRIVATE
    $<BUILD_INTERFACE:intf_pub_cxx11>
    $<BUILD_INTERFACE:mmpa_headers>
    $<BUILD_INTERFACE:msprof_headers>
    $<BUILD_INTERFACE:adump_headers>
    $<BUILD_INTERFACE:slog_headers>
    $<BUILD_INTERFACE:runtime_headers>
)

install(TARGETS stub_msprofiler OPTIONAL
    LIBRARY DESTINATION ${INSTALL_LIBRARY_DIR}/${CMAKE_SYSTEM_PROCESSOR}/stub
)
###################### stub/libmsprofiler.so #######################
