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

set(msProfHeader
    ${TOP_DIR}/metadef/inc
    ${TOP_DIR}/metadef/inc/external
    ${TOP_DIR}/inc/external
    ${TOP_DIR}/ace/npuruntime/inc
    ${TOP_DIR}/ace/npuruntime/inc/external
    ../common
    ../common/logger
    ${PROF_BASIC_DIR}/osal
    ../profimpl/inc
    ./inc/
    ../transport
    ../depend/include/wrapper
    ../
)
set(profApiHeader
    ${TOP_DIR}/ace/npuruntime/runtime/dfx/src/msprof/include/toolchain
    ${msProfHeader}
)

set(profApiCpp
    src/prof_inner_api.cpp
    src/prof_acl_inner_api.cpp
    src/prof_impl_inner_api.cpp
    src/prof_plugin_manager.cpp
    src/prof_cann_plugin.cpp
    src/prof_atls_plugin.cpp
    src/prof_plugin.cpp
    src/prof_tx_plugin.cpp
    src/prof_acl_plugin.cpp
    src/prof_runtime_plugin.cpp
)

####################### libprofapi static lib for windows  begin ###########################
if(${TARGET_SYSTEM_NAME} STREQUAL "Windows")
add_library(profapi_stub STATIC
    stub/profapi_stub.cpp
)

target_include_directories(profapi_stub PRIVATE
    ${profApiHeader}
)

target_compile_definitions(profapi_stub PRIVATE
    google=ascend_private
    FUNC_VISIBILITY
    $<$<STREQUAL:${CMAKE_BUILD_TYPE},Debug>:MSPROF_DEBUG>
    $<$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>:NOMINMAX>
    $<$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>:WIN32>
)

set_target_properties(profapi_stub
    PROPERTIES
    OUTPUT_NAME profapi_stub
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/
)

target_compile_options(profapi_stub PRIVATE
    -fvisibility=hidden
    -fvisibility-inlines-hidden
    -fPIC
    -Wall
    -std=c++11
    -fstack-protector-all
    -fno-strict-aliasing
    -fno-common
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Debug>>:/MTd>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Release>>:/MT>
)

target_link_options(profapi_stub PRIVATE
    -Wl,-z,relro,-z,now,-z,noexecstack
    -Wl,-Bsymbolic
    -Wl,--exclude-libs=ALL
)

target_link_libraries(profapi_stub PRIVATE
    $<BUILD_INTERFACE:intf_pub_cxx11>
    $<BUILD_INTERFACE:mmpa_headers>
    $<BUILD_INTERFACE:slog_headers>
    -Wl,--no-as-needed
    mmpa
    alog
    c_sec
    -Wl,--as-needed
)

install(TARGETS profapi_stub OPTIONAL
    LIBRARY DESTINATION ${INSTALL_LIBRARY_DIR}
)
####################### libprofapi static lib for windows  end ###########################
else()
####################### libprofapi.so ###########################
add_library(profapi_share SHARED
    ${profApiCpp}
)

target_compile_definitions(profapi_share PRIVATE
    $<$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>:WIN32>
)

set_target_properties(profapi_share
    PROPERTIES
    OUTPUT_NAME profapi
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/
)

target_compile_options(profapi_share PRIVATE
    -fstack-protector-all
    -fvisibility=hidden
    -fvisibility-inlines-hidden
    -fno-common
    -Wall
    -std=c++11
    -Wextra
    -Wfloat-equal
    $<$<CONFIG:Release>:-D_FORTIFY_SOURCE=2 -Os>
    $<$<CONFIG:Debug>:-D_FORTIFY_SOURCE=2 -Os>
)

target_link_options(profapi_share PRIVATE
    -Wl,-z,relro,-z,now,-z,noexecstack
    -Wl,-Bsymbolic
    -Wl,--exclude-libs=ALL
)

target_include_directories( profapi_share PRIVATE
    ${profApiHeader}
)

target_link_libraries(profapi_share
    PRIVATE
        intf_pub_cxx11
        mmpa_headers
        slog_headers
        -Wl,--no-as-needed
        mmpa
        alog
        c_sec
        -Wl,--as-needed
    PUBLIC
        msprof_headers
)
####################### libprofapi.so ###########################

####################### libprofapi_lite.so ###########################
add_library(profapi_lite_share SHARED
    src/prof_avp_inner_api.cpp
    src/prof_avp_plugin.cpp
    src/prof_plugin.cpp
)

target_include_directories(profapi_lite_share PRIVATE
    ${profApiHeader}
)

target_compile_definitions(profapi_lite_share PRIVATE
    OSAL
)

set_target_properties(profapi_lite_share
    PROPERTIES
    OUTPUT_NAME profapi
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/proflib
)

target_compile_options(profapi_lite_share PRIVATE
    -fstack-protector-all
    -fvisibility=hidden
    -fvisibility-inlines-hidden
    -Wall
    -std=c++11
    -Wextra
    -Wfloat-equal
    -fno-common
)

target_link_options(profapi_lite_share PRIVATE
    -Wl,-z,relro,-z,now,-z,noexecstack
    -Wl,-Bsymbolic
    -Wl,--exclude-libs=ALL
)

target_include_directories(profapi_lite_share PRIVATE
    ${msProfHeader}
)

target_link_libraries(profapi_lite_share
    PRIVATE
        intf_pub_cxx11
        slog_headers
        -Wl,--no-as-needed
        alog
        c_sec
        -Wl,--as-needed
    PUBLIC
        msprof_headers
)

install(TARGETS profapi_lite_share OPTIONAL
    LIBRARY DESTINATION ${INSTALL_LIBRARY_DIR}/lib
)

####################### libprofapi_lite.so ###########################

endif()
