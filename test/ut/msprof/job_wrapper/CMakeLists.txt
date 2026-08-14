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

protobuf_generate(job_wrapper_proto
    CppPath
    HeaderPath
    ${MSPROF_SOURCE_DIR}/dvvp/proto/profiler.proto
)

set(profilerSrcFiles
    #${TOP_DIR}/abl/
    ${MSPROF_SOURCE_DIR}/dvvp/profhal/adx/stub/adx_prof_api.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profhal/adx/wrapper/memory_utils.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/cmd_log/cmd_log.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/socket/local_socket.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/config/config_manager.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/memory/chunk_pool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/platform/platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/statistics/perf_count.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/thread/thread.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/thread/thread_pool.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/utils/utils.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/json/json.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/common/validation/param_validation.cpp
    ${MSPROF_SOURCE_DIR}/basic/osal/osal.c
    ${MSPROF_SOURCE_DIR}/dvvp/depend/stub/error_manager/msprof_error_manager_stub.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/driver/channel/ai_drv_prof_api.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/driver/devmgmt/ai_drv_dev_api.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/driver/devmgmt/ai_drv_dsmi_api.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/collection_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/collection_register.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/job_device_soc.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/job_factory.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_channel_manager.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_comm_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_hardware_mem_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_dvpp_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_lpm_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_inter_connection_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_io_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_ts_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_stars_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_ccu_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_hwts_log_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_instr_perf_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_biu_perf_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_aicore_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_aicpu_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_adprof_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_sys_info_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_l2cache_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_soc_pmu_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_perf_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_timer.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_drv_event.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_host_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/prof_diagnostic_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/src/adprof_collector_proxy.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/message/codec.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/dynamic_profiling/src/dyn_prof_client.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/task_handle/src/info_json.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/task_handle/src/task_relationship_mgr.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/file_slice.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/file_ageing.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/hash_data.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/file_transport.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/hdc/hdc_transport.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/hdc/helper_transport.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/prof_channel.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/uploader.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/uploader_mgr.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/adapter/src/json_parser.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/platform_interface.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/cloud_v2_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/mdc_v2_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/david_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/david_v121_platform.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform/base_analyzer.cpp
)

list(APPEND profilerSrcFiles
    ${MSPROF_SOURCE_DIR}/dvvp/acp/src/acp_compute_device_job.cpp
    ${MSPROF_SOURCE_DIR}/dvvp/transport/pipe_transport.cpp
    ${CppPath}
)

set(localSrcFiles
    test/main.cpp
    ../stub/drv_stub.cpp
    ../stub/prof_api_stub.cpp
    ../stub/hdc-api-stub.cpp
    ../stub/hdc-log-stub.cpp
    ../stub/mmpa_stub.cpp
    ../stub/devdrv_runtime_api_stub.cpp
    ../stub/profile_drv_user_stub.cpp
    ../stub/tsd_stub.cpp
    test/prof_job_utest.cpp
    test/prof_job_ccu_utest.cpp
    test/prof_peripheral_job_utest.cpp
    test/prof_timer_utest.cpp
    test/collection_register_utest.cpp
    test/prof_device_soc_utest.cpp
    test/prof_device_acp_utest.cpp
    test/job_factory_utest.cpp
    test/prof_channel_manager_utest.cpp
    test/prof_host_job_utest.cpp
    test/info_json_test.cpp
    test/prof_diagnostic_utest.cpp
    test/prof_biu_perf_utest.cpp
    test/adx_prof_api_utest.cpp
)


add_executable(job_wrapper
    ${profilerSrcFiles}
    ${localSrcFiles}
)

target_compile_definitions(job_wrapper PRIVATE
    C_SEC
)

set(libmsprofHeaderDir
    ${LIBC_SEC_HEADER}
    ${TOP_DIR}/output/third_party/gtest_shared/include
    ${TOP_DIR}/third_party/libc_sec/include
    ${TOP_DIR}/include/driver
    ${TOP_DIR}/include/external
    ${TOP_DIR}/include/external/acl
    ${TOP_DIR}/src/dfx/error_manager
    ${TOP_DIR}/src/inc
    ${TOP_DIR}/pkg_inc/dump
    ${TOP_DIR}/pkg_inc/aicpu_sched
    ${TOP_DIR}/src/dfx/adump/inc/metadef/external
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/msproftx/mstx/inc
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform
    ${MSPROF_SOURCE_DIR}/dvvp/common/config
    ${MSPROF_SOURCE_DIR}/dvvp/profapi/inc
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/devprof/include
    ${PROTOBUF_HOST_INCLUDE}
    ${TOP_DIR}/src/msprof/inc
    ${TOP_DIR}/src/msprof/inc/toolchain
    ${TOP_DIR}/src/msprof/inc/external
    ${TOP_DIR}/src/msprof/inc/external/acl
    ${LLT_EXTEND_INCLUDE_DIR}
    ${ASCEND_CANN_PACKAGE_PATH}/include
    ${ASCEND_CANN_PACKAGE_PATH}/include/external
    ${ASCEND_CANN_PACKAGE_PATH}/include/acl
    ${ASCEND_CANN_PACKAGE_PATH}/include/mmpa
    ${ASCEND_CANN_PACKAGE_PATH}/include/toolchain
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/runtime
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/slog/toolchain
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/datagw/aicpu
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/base
    ${ASCEND_CANN_PACKAGE_PATH}/pkg_inc/aicpu
)

target_include_directories(job_wrapper PRIVATE
    ${libmsprofHeaderDir}
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/engine/include
    ${MSPROF_SOURCE_DIR}/dvvp/common/utils
    ${TOP_DIR}/abl/msprof/inc/toolchain
    ${TOP_DIR}/abl/libc_sec/include
    ${TOP_DIR}/ace/npuruntime/acl/third_party/inc/graphengine/inc/external/
    ${TOP_DIR}/ace/npuruntime/inc
    ${MSPROF_SOURCE_DIR}/dvvp/analyze/inc
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/engine/include
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/common/include
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/drvprof/include
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/platform/include
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/dynamic_profiling/include
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/msproftx/include
    ${MSPROF_SOURCE_DIR}/dvvp/msprof/include
    ${MSPROF_SOURCE_DIR}/dvvp/common
    ${MSPROF_SOURCE_DIR}/dvvp/common/errno
    ${MSPROF_SOURCE_DIR}/dvvp/common/logger
    ${MSPROF_SOURCE_DIR}/dvvp/common/validation
    ${MSPROF_SOURCE_DIR}/dvvp/common/queue
    ${MSPROF_SOURCE_DIR}/dvvp/common/singleton
    ${MSPROF_SOURCE_DIR}/dvvp/common/utils
    ${MSPROF_SOURCE_DIR}/dvvp/common/json
    ${MSPROF_SOURCE_DIR}/dvvp/common/config
    ${MSPROF_SOURCE_DIR}/basic/osal
    ${MSPROF_SOURCE_DIR}/dvvp/message
    ${MSPROF_SOURCE_DIR}/dvvp/transport
    ${MSPROF_SOURCE_DIR}/dvvp/common/memory/
    ${MSPROF_SOURCE_DIR}/dvvp/streamio/client/include
    ${MSPROF_SOURCE_DIR}/dvvp/streamio/common/include
    ${MSPROF_SOURCE_DIR}/dvvp/streamio/server/include
    ${MSPROF_SOURCE_DIR}/dvvp
    ${MSPROF_SOURCE_DIR}/dvvp/msprofiler
    ${MSPROF_SOURCE_DIR}/dvvp/profapi/inc
    ${MSPROF_SOURCE_DIR}/dvvp/task_handle/include
    ${MSPROF_SOURCE_DIR}/dvvp/driver/inc
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/job_wrapper/include
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/inc
    ${MSPROF_SOURCE_DIR}/dvvp/profhal/adx/inc
    ${MSPROF_SOURCE_DIR}/dvvp/profhal/halinc
    ${MSPROF_SOURCE_DIR}/dvvp/msprofbin/include
    ${TOP_DIR}/graphengine/inc/external
    ${TOP_DIR}/inc
    ${TOP_DIR}/inc/aicpu
    ${TOP_DIR}/inc/driver
    ${TOP_DIR}/inc/external
    ${TOP_DIR}/inc/external/acl
    ${TOP_DIR}/ace/npuruntime/inc
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/adapter/inc
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/report
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/aicpu
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/platform
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect
    ${MSPROF_SOURCE_DIR}/dvvp/profimpl/collect/channel
    ../stub/
    ${TOP_DIR}/llt/abl/msprof/st/stub
    ${TOP_DIR}/llt/abl/msprof/ut/stub
    ${CMAKE_BINARY_DIR}/proto/job_wrapper_proto/
    ${MSPROF_SOURCE_DIR}/dvvp/depend/include/stub
    ${MSPROF_SOURCE_DIR}/dvvp/acp/include
)

target_compile_options(job_wrapper PRIVATE
    -g
    -pipe
    -Wall
    -fno-access-control
    -Wfloat-equal
    -Wextra
)

target_compile_definitions(job_wrapper PRIVATE
    MSPROF_DEBUG
    google=ascend_private
)

target_link_libraries(job_wrapper PRIVATE
    error_manager_headers
    $<BUILD_INTERFACE:intf_llt_pub>
    alog
    ascend_protobuf_static
    c_sec
)

set_target_properties(job_wrapper
    PROPERTIES
    OUTPUT_NAME job_wrapper
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
)
