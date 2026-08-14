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

protobuf_generate(transport_proto
    CppPath
    HeaderPath
    ${MSPROF_SOURCE_DIR}/dvvp/proto/profiler.proto
)

set(profilerSrcFiles
    ${MSPROF_SOURCE_DIR}/dvvp/transport/file_transport.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/config/config_manager.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/utils/utils.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/cmd_log/cmd_log.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/platform/platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/statistics/perf_count.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/json/json.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/message/codec.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/uploader.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/uploader_mgr.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/prof_channel.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/thread/thread.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/thread/thread_pool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/driver/devmgmt/ai_drv_dev_api.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/driver/devmgmt/ai_drv_dsmi_api.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/driver/channel/ai_drv_prof_api.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/file_slice.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/file_ageing.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/hash_data.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/hdc/hdc_transport.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/hdc/helper_transport.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/validation/param_validation.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/depend/stub/error_manager/msprof_error_manager_stub.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/adapter/src/json_parser.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/platform_interface.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/cloud_v2_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/base_analyzer.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/acp_manager.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/acp_api_plugin.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/op_transport.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/op_analyzer.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/op_data_manager.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/op_analyzer_base.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/op_analyzer_pmu.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/op_analyzer_biu.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/op_analyzer_pc_sampling.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/collection_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/collection_register.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_comm_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_channel_manager.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_stars_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_biu_perf_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/acp_compute_device_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/acp_pipe_transfer.cpp
    ${CppPath}
    ${MSPROF_SOURCE_DIR}/basic/osal/osal.c
    ${MSPROF_SOURCE_DIR}/basic/osal/osal_linux.c
    ${MSPROF_SOURCE_DIR}/basic/osal/osal_linux_mem.c
    ${MSPROF_SOURCE_DIR}/dvvp/profhal/adx/wrapper/adx_prof_api.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/pipe_transport.cpp
)

set(localSrcFiles
    test/main.cpp
    test/transport_utest.cpp
    test/uploader_utest.cpp
    test/prof_channel_utest.cpp
    test/hash_data_test.cpp
    test/file_ageing_test.cpp
    test/file_slice_test.cpp
    test/pipe_transport_utest.cpp
    ../stub/hdc-api-stub.cpp
    ../stub/hdc-log-stub.cpp
    ../stub/drv_stub.cpp
    ../stub/mmpa_stub.cpp
    ../stub/prof_api_stub.cpp
    ../stub/devdrv_runtime_api_stub.cpp
    ../stub/profile_drv_user_stub.cpp
)

add_executable(transport
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

target_include_directories(transport PRIVATE
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
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/base
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/aicpu
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/profiling
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/runtime
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/runtime/runtime
    ${MSPROF_SOURCE_DIR}/dvvp/acp/include
    ${MSPROF_SOURCE_DIR}/dvvp/analyze/inc
    ${MSPROF_SOURCE_DIR}/dvvp
    ${MSPROF_SOURCE_DIR}/dvvp/profhal/adx/inc
    ${MSPROF_SOURCE_DIR}/dvvp/profhal/halinc
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/msproftx/mstx/inc
    ${MSPROF_SOURCE_DIR}/dvvp/common
    ${MSPROF_SOURCE_DIR}/dvvp/common/statistics
    ${MSPROF_SOURCE_DIR}/dvvp/common/utils
    ${MSPROF_SOURCE_DIR}/dvvp/common/logger
    ${MSPROF_SOURCE_DIR}/dvvp/common/validation
    ${MSPROF_SOURCE_DIR}/dvvp/common/queue
    ${MSPROF_SOURCE_DIR}/dvvp/common/json
    ${MSPROF_SOURCE_DIR}/dvvp/common/config
    ${MSPROF_SOURCE_DIR}/dvvp/common/singleton
    ${MSPROF_SOURCE_DIR}/dvvp/common/cmd_log
    ${MSPROF_SOURCE_DIR}/dvvp/profapi/inc
    ${MSPROF_SOURCE_DIR}/basic/
    ${MSPROF_SOURCE_DIR}/basic/osal
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/common/include/
    ${MSPROF_SOURCE_DIR}/dvvp/message
    ${MSPROF_SOURCE_DIR}/dvvp/transport
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/engine/include
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/adapter/inc
    ${MSPROF_SOURCE_DIR}/dvvp/driver/inc
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/include
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/inc
    ${MSPROF_SOURCE_DIR}/dvvp/task_handle/include
    ${MSPROF_SOURCE_DIR}/dvvp/aging
    ${MSPROF_SOURCE_DIR}/dvvp/streamio/common/include
    ${CMAKE_BINARY_DIR}/proto/transport_proto/
    ${MSPROF_SOURCE_DIR}/dvvp/depend/include/stub
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform
    ${MSPROF_SOURCE_DIR}/avp/
    ${TOP_DIR}/src/third_party/adcore
    ../stub/
)

target_compile_options(transport PRIVATE
    -g
    -pipe
    -Wall
    -fno-access-control
    -Wfloat-equal
    -Wextra
)

target_compile_definitions(transport PRIVATE
    DLOG_EVENT=4
    OSAL
    MSPROF_DEBUG
    google=ascend_private
)

target_link_libraries(transport PRIVATE
    error_manager_headers
    $<BUILD_INTERFACE:intf_llt_pub>
    alog
    ascend_protobuf_static
    c_sec
    rt
    dl
    pthread
)

set_target_properties(transport
    PROPERTIES
    OUTPUT_NAME transport
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
)
