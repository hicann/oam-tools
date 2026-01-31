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
protobuf_generate(msprofbin_proto
    CppPath
    HeaderPath
    ${CMAKE_CURRENT_SOURCE_DIR}/../../proto/profiler.proto
    TARGET
)

add_dependencies(msprofbin_proto host_protoc protobuf_host_build ascend_protobuf_static)

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

set(hdcCpp
    ../../profhal/adx/stub/adx_prof_api.cpp
    ../../profhal/adx/wrapper/hdc_api.cpp
    ../../profhal/adx/wrapper/memory_utils.cpp
)

set(msprofbinCpp
    ../src/msprof_bin.cpp
    ../src/msopprof_manager.cpp
    ../src/msprof_manager.cpp
    ../src/msprof_task.cpp
    ../src/msprof_params_adapter.cpp
    ../src/msprof_params_adapter_closed.cpp
    ../src/input_parser.cpp
    ../src/input_parser_closed.cpp
    ../src/running_mode.cpp
    ../src/running_mode_closed.cpp
    ../../app/application.cpp
    ../../app/env_manager.cpp
    ../../common/cmd_log/cmd_log.cpp
    ../../common/utils/utils.cpp
    ../../common/json/json.cpp
    ${PROF_BASIC_DIR}/osal/osal.c
    ../../common/config/closed/config_manager.cpp
    ../../common/memory/chunk_pool.cpp
    ../../common/thread/thread.cpp
    ../../common/thread/thread_pool.cpp
    ../../common/socket/local_socket.cpp
    ../../common/statistics/perf_count.cpp
    ../../common/validation/param_validation.cpp
    ../../common/validation/param_validation_closed.cpp
    ../../common/platform/platform.cpp
    ../../common/platform/platform_closed.cpp
    ../../common/json/json.cpp
    ../../depend/stub/error_manager/msprof_error_manager_stub.cpp
    ../../driver/devmgmt/ai_drv_dev_api.cpp
    ../../driver/devmgmt/ai_drv_dev_api_closed.cpp
    ../../driver/devmgmt/ai_drv_dsmi_api.cpp
    ../../driver/devmgmt/ai_drv_dsmi_api_closed.cpp
    ../../driver/channel/ai_drv_prof_api.cpp
    ../../profimpl/collect/job_wrapper/src/collection_job.cpp
    ../../profimpl/collect/job_wrapper/src/collection_register.cpp
    ../../profimpl/collect/job_wrapper/src/job_factory.cpp
    ../../profimpl/collect/job_wrapper/src/job_device_rpc.cpp
    ../../profimpl/collect/job_wrapper/src/prof_comm_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_soc_pmu_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_l2cache_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_ts_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_stars_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_ccu_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_hwts_log_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_instr_perf_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_biu_perf_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_aicore_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_aicpu_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_sys_info_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_hardware_mem_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_hardware_mem_job_closed.cpp
    ../../profimpl/collect/job_wrapper/src/prof_dvpp_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_lpm_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_inter_connection_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_io_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_timer.cpp
    ../../profimpl/collect/job_wrapper/src/prof_perf_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_host_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_diagnostic_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_aicpu_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_channel_manager.cpp
    ../../profimpl/collect/job_wrapper/src/prof_adprof_job.cpp
    ../../profimpl/collect/job_wrapper/src/prof_adprof_job_closed.cpp
    ../../profimpl/collect/job_wrapper/src/prof_drv_event.cpp
    ../../profimpl/collect/job_wrapper/src/job_device_soc.cpp
    ../../profimpl/collect/job_wrapper/src/adprof_collector_proxy.cpp
    ../../msprof/dynamic_profiling/src/dyn_prof_client.cpp
    ../../profimpl/adapter/src/json_parser.cpp
    ../../profimpl/platform/platform_interface.cpp
    ../../profimpl/platform/base_analyzer.cpp
    ../../profimpl/platform/mini_platform.cpp
    ../../profimpl/platform/cloud_v2_platform.cpp
    ../../profimpl/platform/david_platform.cpp
    ../../profimpl/platform/david_v121_platform.cpp
    ../../profimpl/platform/cloud_platform.cpp
    ../../profimpl/platform/dc_platform.cpp
    ../../profimpl/platform/mdc_lite_platform.cpp
    ../../profimpl/platform/mdc_mini_v3_platform.cpp
    ../../profimpl/platform/mdc_platform.cpp
    ../../profimpl/platform/mini_v3_platform.cpp
    ../../message/codec.cpp
    ../../transport/file_transport.cpp
    ../../transport/pipe_transport.cpp
    ../../transport/prof_channel.cpp
    ../../transport/uploader_mgr.cpp
    ../../transport/hash_data.cpp
    ../../transport/uploader.cpp
    ../../transport/file_ageing.cpp
    ../../transport/file_ageing_closed.cpp
    ../../transport/file_slice.cpp
    ../../task_handle/src/info_json.cpp
    ../../task_handle/src/task_relationship_mgr.cpp
    ../../transport/hdc/data_handle.cpp
    ../../transport/hdc/hdc_transport.cpp
    ../../transport/hdc/helper_transport.cpp
    ../../transport/hdc/device_transport.cpp
    ../../transport/hdc/platform/rpc/dev_mgr_api.cpp
    ${hdcCpp}
    ${CppPath}
)

if(${TARGET_SYSTEM_NAME} STREQUAL "Windows")
set(msprofbinCpp
    ../src/win/msprof_bin.cpp
)
endif()
add_executable(msprofbin
    ${msprofbinCpp}
)

link_directories(
    ${INSTALL_LIBRARY_DIR}/stub
)

target_include_directories(msprofbin PRIVATE
    ${msprofBinHeader}
    ${CMAKE_CURRENT_SOURCE_DIR}/../
    ${CMAKE_BINARY_DIR}/proto/msprofbin_proto
)


target_compile_options(msprofbin PRIVATE
    -fPIE
    -fno-strict-aliasing
    -fno-common
    -Wall
    -D_GLIBCXX_USE_CXX11_ABI=0
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wfloat-equal>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wextra>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wno-unused-parameter>
    $<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Wno-missing-field-initializers>
    #$<$<NOT:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>>:-Werror>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Debug>>:/MTd>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Release>>:/MT>
)

target_compile_definitions(msprofbin PRIVATE
    SECUREC_USING_STD_SECURE_LIB=0
    google=ascend_private
    $<$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>:NOMINMAX>
)

target_link_options(msprofbin PRIVATE
    -Wl,-Bsymbolic
    -Wl,--exclude-libs=ALL
    -ldl
)

target_link_libraries(msprofbin PRIVATE
    $<BUILD_INTERFACE:intf_pub_cxx17>
    $<BUILD_INTERFACE:mmpa_headers>
    $<BUILD_INTERFACE:adump_headers>
    $<BUILD_INTERFACE:slog_headers>
    $<BUILD_INTERFACE:msprofbinOnetrack_pub>
)

set_target_properties(msprofbin
    PROPERTIES
    OUTPUT_NAME msprof
    LIBRARY_OUTPUT_DIRECTORY ${INSTALL_LIBRARY_DIR}/msprof
)

install(TARGETS msprofbin OPTIONAL
    RUNTIME DESTINATION ${INSTALL_LIBRARY_DIR}/profiler/bin
)

### onetrack target interface

add_library(msprofbinOnetrack_pub INTERFACE)

target_link_libraries(msprofbinOnetrack_pub INTERFACE
    $<BUILD_INTERFACE:intf_pub_cxx17>
    c_sec
    alog
    mmpa
    ascend_hal
    ascend_protobuf_static
    -lpthread
    -ldl
)

add_dependencies(msprofbin msprofbin_proto)

set(msprof_whl
    ${CMAKE_CURRENT_SOURCE_DIR}/../msprof-0.0.1-py3-none-any.whl
)
install(PROGRAMS ${msprof_whl}
    DESTINATION ${INSTALL_LIBRARY_DIR}/profiler/profiler_tool OPTIONAL
)