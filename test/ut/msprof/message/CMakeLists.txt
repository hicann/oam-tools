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
set(MSPROF_SOURCE_DIR ${TOP_DIR}/src/msprof/collector)

protobuf_generate(message_utest_proto
    CppPath
    HeaderPath
    ${MSPROF_SOURCE_DIR}/dvvp/proto/profiler.proto
)

set(profilerSrcFiles
    ${MSPROF_SOURCE_DIR}/dvvp/message/codec.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/message/dispatcher.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/utils/utils.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/json/json.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/cmd_log/cmd_log.cpp
    ${MSPROF_SOURCE_DIR}/basic/osal/osal.c
    ${MSPROF_SOURCE_DIR}/dvvp/depend/stub/error_manager/msprof_error_manager_stub.cpp
    ${CppPath}
)

set(localSrcFiles
    test/main.cpp
    test/codec_test.cpp
    test/dispatcher_test.cpp
    test/message_test.cpp
    ../stub/hdc-log-stub.cpp
    ../stub/mmpa_stub.cpp
    ../stub/drv_stub.cpp
    ../stub/devdrv_runtime_api_stub.cpp
)

add_executable(message_utest
    ${profilerSrcFiles}
    ${localSrcFiles}
)

set(libmsprofHeaderDir
    ${LIBC_SEC_HEADER}
    ${TOP_DIR}/output/third_party/gtest_shared/include
    ${TOP_DIR}/third_party/libc_sec/include
    ${TOP_DIR}/src/dfx/error_manager
    ${TOP_DIR}/src/inc
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/msproftx/mstx/inc
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform
    ${MSPROF_SOURCE_DIR}/dvvp/common/config
    ${MSPROF_SOURCE_DIR}/dvvp/profapi/inc
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/devprof/include
)

target_include_directories(message_utest PRIVATE
    ${libmsprofHeaderDir}
    ${PROTOBUF_HOST_INCLUDE}
    ${TOP_DIR}/src/msprof/inc
    ${TOP_DIR}/src/msprof/inc/toolchain
    ${TOP_DIR}/src/msprof/inc/external
    ${TOP_DIR}/src/msprof/inc/external/acl
    ${ASCEND_CANN_PACKAGE_PATH}/include
    ${ASCEND_CANN_PACKAGE_PATH}/include/acl
    ${ASCEND_CANN_PACKAGE_PATH}/include/driver
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/metadef
    ${ASCEND_CANN_PACKAGE_PATH}/include/mmpa
    ${ASCEND_CANN_PACKAGE_PATH}/include/toolchain
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/runtime
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/slog/toolchain
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/datagw/aicpu
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/metadef/common/util/error_manager
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/base
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/aicpu
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/profiling
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/runtime
    ${MSPROF_SOURCE_DIR}/dvvp
    ${MSPROF_SOURCE_DIR}/dvvp/common
    ${MSPROF_SOURCE_DIR}/dvvp/common/json
    ${MSPROF_SOURCE_DIR}/dvvp/common/logger
    ${MSPROF_SOURCE_DIR}/dvvp/common/cmd_log
    ${MSPROF_SOURCE_DIR}/basic/osal
    ${CMAKE_BINARY_DIR}/proto/message_utest_proto/
    ${MSPROF_SOURCE_DIR}/dvvp/depend/include/stub
    ../stub/
)

target_compile_options(message_utest PRIVATE
    -g
    -pipe
    -Wall
    -fno-access-control
    -Wfloat-equal
    -Wextra
)

target_compile_definitions(message_utest PRIVATE
    MSPROF_DEBUG
    google=ascend_private
)

target_link_libraries(message_utest PRIVATE
    $<BUILD_INTERFACE:intf_llt_pub>
    alog
    ascend_protobuf_static
    c_sec
)

set_target_properties(message_utest
    PROPERTIES
    OUTPUT_NAME message_utest
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
)
