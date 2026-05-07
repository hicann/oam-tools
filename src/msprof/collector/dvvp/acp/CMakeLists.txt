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

protobuf_generate(profiler_proto
    CppPath
    HeaderPath
    ${CMAKE_CURRENT_SOURCE_DIR}/../proto/profiler.proto
    TARGET
)

add_dependencies(profiler_proto host_protoc protobuf_host_build ascend_protobuf_static)

####################### acp #######################

set(msprofBinHeader
    ${SOURCE_DIR}/src
    ${runtime_INCLUDE_DIR}
    ${third_party_INCLUDE_DIR}
    ${MSPROF_DIR}/inc/toolchain
    ${PROTOBUF_HOST_STATIC_INCLUDE}
    ../include
    ../../
    ../../app
    ../../common/utils
    ../../msprof/engine/include
    ../../host/include/
    ../../message/
    ../../common
    ../../common/json
    ../../common/logger
    ../../common/queue
    ../../common/statistics
    ../../common/validation
    ../../common/platform
    ../../common/json
    ../../common/config/closed
    ${PROF_BASIC_DIR}/osal
    ../../common/errno
    ../../depend/include/stub
    ../../msprof/common/include/
    ../../msprof/dynamic_profiling/include/
    ../../profimpl/adapter/inc
    ../../profimpl/platform
    ../../profimpl/platform/closed
    ../../profimpl/collect/job_wrapper/include
    ../../profimpl/inc
    ../../msprof/msproftx/mstx/inc
    ../../profhal/adx/inc
    ../../profhal/halinc
    ../../driver/inc
    ../../task_handle/include
    ../../transport
    ../../profhal/adx/inc
)

set(acpBinHeader
    ${msprofBinHeader}
    ../../../inc/toolchain
    ${TOP_DIR}/src/third_party/metadef
    ${PROF_BASIC_DIR}/osal
    include
    ../
    ../app
    ../common
    ../common/argparse
    ../common/cmd_log
    ../common/utils
    ../common/errno
    ../common/logger
    ../common/config
    ../common/config/closed
    ../common/singleton
    ../common/platform
    ../common/validation
    ../msprofbin/include
    ../profimpl/platform
    ../profimpl/platform/closed
    ../profimpl/adapter/inc
    ../profimpl/collect/job_wrapper/include
    ../depend/include/stub
    ../msprof/dynamic_profiling/include/
    ../driver/inc
    ../transport
    ../task_handle/include
)

set(acpBinCpp
    src/acp_bin.cpp
    src/acp_command.cpp
    src/acp_pipe_transfer.cpp
    ../app/application.cpp
    ../app/env_manager.cpp
    ../common/argparse/argparser.cpp
    ../common/utils/utils.cpp
    ../common/cmd_log/cmd_log.cpp
    ../common/config/closed/config_manager.cpp
    ../common/validation/param_validation.cpp
    ../common/validation/param_validation_closed.cpp
    ../common/thread/thread.cpp
    ../common/thread/thread_pool.cpp
    ../common/socket/local_socket.cpp
    ../common/json/json.cpp
    ../common/platform/platform.cpp
    ../common/statistics/perf_count.cpp
    ../driver/devmgmt/ai_drv_dev_api.cpp
    ../driver/channel/ai_drv_prof_api.cpp
    ../depend/stub/error_manager/msprof_error_manager_stub.cpp
    ../msprof/dynamic_profiling/src/dyn_prof_client.cpp
    ../task_handle/src/task_relationship_mgr.cpp
    ../profimpl/adapter/src/json_parser.cpp
    ../profimpl/platform/platform_interface.cpp
    ../profimpl/platform/cloud_v2_platform.cpp
    ../profimpl/platform/david_platform.cpp
    ../profimpl/platform/david_v121_platform.cpp
    ../profimpl/platform/base_analyzer.cpp
    ../profimpl/collect/job_wrapper/src/collection_job.cpp
    ../profimpl/collect/job_wrapper/src/collection_register.cpp
    ../profimpl/collect/job_wrapper/src/prof_comm_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_channel_manager.cpp
    ../profimpl/collect/job_wrapper/src/prof_stars_job.cpp
    ../transport/prof_channel.cpp
    ../transport/uploader_mgr.cpp
    ../transport/uploader.cpp
    ${PROF_BASIC_DIR}/osal/osal.c
)

add_executable(acp
    ${acpBinCpp}
)

target_include_directories(acp PRIVATE
    ${acpBinHeader}
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_compile_options(acp PRIVATE
    -fPIE
    -fno-strict-aliasing
    -fno-common
    -Wall
    -D_GLIBCXX_USE_CXX11_ABI=0
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wfloat-equal>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wextra>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wno-unused-parameter>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wno-missing-field-initializers>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Debug>>:/MTd>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Release>>:/MT>
)

target_compile_definitions(acp PRIVATE
    SECUREC_USING_STD_SECURE_LIB=0
    google=ascend_private
    $<$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>:NOMINMAX>
)

target_link_options(acp PRIVATE
    -Wl,-Bsymbolic
    -Wl,--exclude-libs=ALL
    -ldl
)

target_link_libraries(acp PRIVATE
    $<BUILD_INTERFACE:intf_pub_cxx17>
    $<BUILD_INTERFACE:mmpa_headers>
    $<BUILD_INTERFACE:adump_headers>
    $<BUILD_INTERFACE:slog_headers>
    c_sec
    unified_dlog
    mmpa
    ascend_hal
)

set_target_properties(acp
    PROPERTIES
    OUTPUT_NAME acp
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/
)

install(TARGETS acp OPTIONAL
    RUNTIME DESTINATION ${INSTALL_LIBRARY_DIR}/profiler/bin
)

####################### acp end #######################

####################### libascend_profinj.so #######################
set(profinjCpp
    ${PROF_BASIC_DIR}/osal/osal.c
    src/acp_command.cpp
    src/acp_pipe_transfer.cpp
    src/acp_runtime_api.cpp
    src/acp_manager.cpp
    src/acp_api_plugin.cpp
    src/acp_compute_device_job.cpp
    src/op_transport.cpp
    src/op_data_manager.cpp
    src/op_analyzer.cpp
    src/op_analyzer_base.cpp
    src/op_analyzer_pmu.cpp
    src/op_analyzer_biu.cpp
    src/op_analyzer_pc_sampling.cpp
    ../transport/uploader.cpp
    ../transport/uploader_mgr.cpp
    ../transport/prof_channel.cpp
    ../profimpl/platform/platform_interface.cpp
    ../profimpl/platform/cloud_v2_platform.cpp
    ../profimpl/platform/david_platform.cpp
    ../profimpl/platform/david_v121_platform.cpp
    ../profimpl/platform/base_analyzer.cpp
    ../profimpl/adapter/src/json_parser.cpp
    ../profimpl/collect/job_wrapper/src/collection_job.cpp
    ../profimpl/collect/job_wrapper/src/collection_register.cpp
    ../profimpl/collect/job_wrapper/src/prof_comm_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_channel_manager.cpp
    ../profimpl/collect/job_wrapper/src/prof_stars_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_biu_perf_job.cpp
    ../common/platform/platform.cpp
    ../common/utils/utils.cpp
    ../common/config/closed/config_manager.cpp
    ../common/statistics/perf_count.cpp
    ../common/json/json.cpp
    ../common/cmd_log/cmd_log.cpp
    ../common/validation/param_validation_closed.cpp
    ../common/thread/thread.cpp
    ../common/thread/thread_pool.cpp
    ../common/socket/local_socket.cpp
    ../common/argparse/argparser.cpp
    ../driver/devmgmt/ai_drv_dev_api.cpp
    ../driver/channel/ai_drv_prof_api.cpp
    ../driver/devmgmt/ai_drv_dsmi_api.cpp
    ${PROF_BASIC_DIR}/osal/osal.c
    ../app/application.cpp
    ../app/env_manager.cpp
    ../depend/stub/error_manager/msprof_error_manager_stub.cpp
    ../msprof/dynamic_profiling/src/dyn_prof_client.cpp
    ../task_handle/src/task_relationship_mgr.cpp
)

add_library(profinj SHARED
    ${profinjCpp}
)

target_include_directories(profinj PRIVATE
    ${msprofBinHeader}
    ${ASCEND_CANN_PACKAGE_PATH}/include/acl
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/runtime
    ${TOP_DIR}/src/third_party/metadef
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_BINARY_DIR}/proto/profiler_proto/
    ${PROF_BASIC_DIR}/osal
    include/
    ../
    ../depend/include/stub
    ../transport/
    ../common/
    ../common/logger
    ../common/statistics
    ../common/utils
    ../common/validation
    ../common/queue
    ../common/json
    ../common/config/closed
    ../common/singleton
    ../analyze/inc
    ../profimpl/platform/closed
    ../profimpl/platform
    ../profimpl/adapter/inc
    ../driver/inc
    ../message
    ../profimpl/collect/job_wrapper/include/
    ../profapi/inc/
    ../app
    ../common/
    ../common/argparse/
    ../common/cmd_log
    ../common/errno
    ../msprof/dynamic_profiling/include/
    ../task_handle/include
)

set_target_properties(profinj
    PROPERTIES
    OUTPUT_NAME $<IF:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,libascend_profinj,ascend_profinj>
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/
)

target_compile_options(profinj PRIVATE
    -fPIE
    -fno-strict-aliasing
    -fno-common
    -Wall
    -D_GLIBCXX_USE_CXX11_ABI=0
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wfloat-equal>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wextra>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wno-unused-parameter>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wno-missing-field-initializers>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Debug>>:/MTd>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Release>>:/MT>
)

#set (CMAKE_CXX_FLAGS "-std=c++17 -fvisibility-inlines-hidden" ${CMAKE_CXX_FLAGS})
#set (CMAKE_C_FLAGS "-std=c11" ${CMAKE_C_FLAGS})

target_compile_definitions(profinj PRIVATE
    MSPROF_LIB
)

target_link_options(profinj PRIVATE
    -Wl,-Bsymbolic
    -Wl,--exclude-libs=ALL
    -ldl
)

target_link_libraries(profinj PRIVATE
    $<BUILD_INTERFACE:intf_pub_cxx17>
    $<BUILD_INTERFACE:mmpa_headers>
    $<BUILD_INTERFACE:adump_headers>
    $<BUILD_INTERFACE:slog_headers>
    c_sec
    unified_dlog
    mmpa
    ascend_hal
)

install(TARGETS profinj OPTIONAL
    LIBRARY DESTINATION ${INSTALL_LIBRARY_DIR}/profiler/lib64
)

add_dependencies(profinj profiler_proto)
####################### libascend_profinj.so ###########################