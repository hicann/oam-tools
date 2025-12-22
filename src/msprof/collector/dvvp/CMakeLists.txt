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

add_subdirectory(acp)
add_subdirectory(adprof)
add_subdirectory(msprof)
add_subdirectory(msprofbin)
add_subdirectory(profapi)
add_subdirectory(msprofiler)
add_subdirectory(profhal)

set(hdcCpp
    profhal/adx/stub/adx_prof_api.cpp
    profhal/adx/wrapper/hdc_api.cpp
    profhal/adx/wrapper/memory_utils.cpp
)

####################### libprofimpl.so ###########################

set(profimplCpp
    analyze/src/analyzer.cpp
    analyze/src/analyzer_base.cpp
    analyze/src/analyzer_ge.cpp
    analyze/src/analyzer_hwts.cpp
    analyze/src/analyzer_ffts.cpp
    analyze/src/analyzer_ts.cpp
    analyze/src/analyzer_rt.cpp
    analyze/src/op_desc_parser.cpp
    common/cmd_log/cmd_log.cpp
    common/config/config_manager.cpp
    common/config/feature_manager.cpp
    common/memory/chunk_pool.cpp
    common/platform/platform.cpp
    common/socket/local_socket.cpp
    common/statistics/perf_count.cpp
    common/thread/thread.cpp
    common/thread/thread_pool.cpp
    common/utils/utils.cpp
    common/json/json.cpp
    ${PROF_BASIC_DIR}/osal/osal.c
    common/validation/param_validation.cpp
    common/json/json.cpp
    driver/channel/ai_drv_prof_api.cpp
    driver/devmgmt/ai_drv_dev_api.cpp
    driver/devmgmt/ai_drv_dsmi_api.cpp
    profimpl/collect/job_wrapper/src/collection_job.cpp
    profimpl/collect/job_wrapper/src/collection_register.cpp
    profimpl/collect/job_wrapper/src/job_device_soc.cpp
    profimpl/collect/job_wrapper/src/job_factory.cpp
    profimpl/collect/job_wrapper/src/prof_channel_manager.cpp
    profimpl/collect/job_wrapper/src/prof_comm_job.cpp
    profimpl/collect/job_wrapper/src/prof_soc_pmu_job.cpp
    profimpl/collect/job_wrapper/src/prof_l2cache_job.cpp
    profimpl/collect/job_wrapper/src/prof_ts_job.cpp
    profimpl/collect/job_wrapper/src/prof_stars_job.cpp
    profimpl/collect/job_wrapper/src/prof_ccu_job.cpp
    profimpl/collect/job_wrapper/src/prof_hwts_log_job.cpp
    profimpl/collect/job_wrapper/src/prof_instr_perf_job.cpp
    profimpl/collect/job_wrapper/src/prof_biu_perf_job.cpp
    profimpl/collect/job_wrapper/src/prof_aicore_job.cpp
    profimpl/collect/job_wrapper/src/prof_aicpu_job.cpp
    profimpl/collect/job_wrapper/src/prof_sys_info_job.cpp
    profimpl/collect/job_wrapper/src/prof_hardware_mem_job.cpp
    profimpl/collect/job_wrapper/src/prof_dvpp_job.cpp
    profimpl/collect/job_wrapper/src/prof_lpm_job.cpp
    profimpl/collect/job_wrapper/src/prof_inter_connection_job.cpp
    profimpl/collect/job_wrapper/src/prof_io_job.cpp
    profimpl/collect/job_wrapper/src/prof_timer.cpp
    profimpl/collect/job_wrapper/src/prof_perf_job.cpp
    profimpl/collect/job_wrapper/src/prof_host_job.cpp
    profimpl/collect/job_wrapper/src/prof_diagnostic_job.cpp
    profimpl/collect/job_wrapper/src/prof_adprof_job.cpp
    profimpl/collect/job_wrapper/src/prof_drv_event.cpp
    profimpl/collect/job_wrapper/src/adprof_collector_proxy.cpp
    msprof/common/src/receive_data.cpp
    msprof/common/src/msprof_reporter.cpp
    msprof/dynamic_profiling/src/dyn_prof_server.cpp
    msprof/dynamic_profiling/src/dyn_prof_thread.cpp
    msprof/dynamic_profiling/src/dyn_prof_mgr.cpp
    msprof/engine/src/prof_acl_mgr.cpp
    msprof/engine/src/uploader_dumper.cpp
    msprof/msproftx/src/msprof_tx_manager.cpp
    msprof/msproftx/src/msprof_tx_reporter.cpp
    msprof/msproftx/src/prof_stamp_pool.cpp
    profimpl/adapter/src/command_handle.cpp
    profimpl/adapter/src/msprofiler_impl.cpp
    profimpl/adapter/src/msprofiler_adaptor.cpp
    profimpl/adapter/src/msproftx_adaptor.cpp
    profimpl/adapter/src/msprofiler_acl_api.cpp
    profimpl/adapter/src/json_parser.cpp
    profimpl/report/prof_reporter_mgr.cpp
    profimpl/aicpu/prof_aicpu_api.cpp
    profimpl/aicpu/prof_hal_plugin.cpp
    profimpl/platform/platform_interface.cpp
    profimpl/platform/base_analyzer.cpp
    profimpl/platform/nano_platform.cpp
    profimpl/platform/mini_v3_platform.cpp
    profimpl/platform/mdc_mini_v3_platform.cpp
    profimpl/platform/cloud_v2_platform.cpp
    profimpl/platform/david_platform.cpp
    profimpl/platform/david_v121_platform.cpp
    profimpl/platform/mdc_lite_platform.cpp
    profimpl/platform/cloud_platform.cpp
    profimpl/platform/dc_platform.cpp
    profimpl/platform/mini_platform.cpp
    profimpl/platform/mdc_platform.cpp
    profimpl/platform/tiny_v1_platform.cpp
    task_handle/src/device.cpp
    task_handle/src/info_json.cpp
    task_handle/src/prof_manager.cpp
    task_handle/src/prof_params_adapter.cpp
    task_handle/src/prof_task.cpp
    task_handle/src/task_relationship_mgr.cpp
    transport/file_ageing.cpp
    transport/file_slice.cpp
    transport/file_transport.cpp
    transport/parser_transport.cpp
    transport/prof_channel.cpp
    transport/uploader.cpp
    transport/uploader_mgr.cpp
    transport/hash_data.cpp
    transport/hdc/helper_transport.cpp
    ${CppPath}
)

set(profimplInc
    ${TOP_DIR}/graphengine/inc/external
    ${TOP_DIR}/graphengine/inc/framework/common
    ${TOP_DIR}/inc
    ${TOP_DIR}/inc/aicpu
    ${TOP_DIR}/inc/driver
    ${TOP_DIR}/inc/external
    ${TOP_DIR}/inc/external/acl
    ${TOP_DIR}/abl/libc_sec/include
    ${TOP_DIR}/ace/npuruntime/inc
    ${TOP_DIR}/metadef/inc
    ${TOP_DIR}/ace/npuruntime/runtime/dfx/src/msprof/include/toolchain
    msprof/dynamic_profiling/include
    msprof/engine/include
    msprof/common/include
    msprof/drvprof/include
    msprof/devprof/include
    msprof/platform/include
    msprof/msproftx/include
    analyze/inc
    common
    common/errno
    common/json
    ${PROF_BASIC_DIR}/osal
    common/logger
    common/queue
    common/singleton
    common/utils
    common/config
    common/validation
    common/statistics
    common/platform
    profhal/adx/inc
    profhal/halinc
    profimpl/adapter/inc
    profimpl/report
    profimpl/aicpu
    profimpl/platform
    profimpl/inc
    msprofiler/
    msprof/common/include
    message
    transport
    task_handle/include
    driver/inc
    profimpl/collect/job_wrapper/include
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/../../include/external/driver
    ${ASCEND_CANN_PACKAGE_PATH}/include
    ${ASCEND_CANN_PACKAGE_PATH}/include/acl
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/metadef
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/runtime
)


set(profimplFwcSrc
    ${profimplCpp}
)

add_library(profimpl_fwk_share SHARED
    ${profimplFwcSrc}
    depend/wrapper/error_manager/msprof_error_manager.cpp
    ${hdcCpp}
)

target_compile_options(profimpl_fwk_share PRIVATE
    -fPIC
    -shared
    -fstack-protector-all
    -fno-strict-aliasing
    -fno-common
    -Wall
    -Wextra
    -Wfloat-equal
    $<$<CONFIG:Release>:-D_FORTIFY_SOURCE=2 -Os>
    $<$<CONFIG:Debug>:-D_FORTIFY_SOURCE=2 -Os>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Debug>>:/MTd>
    $<$<AND:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,$<STREQUAL:${CMAKE_CONFIGURATION_TYPES},Release>>:/MT>
)

target_include_directories(profimpl_fwk_share PRIVATE
    ${profimplInc}
    ${TOP_DIR}/graphengine/inc
    ${TOP_DIR}/graphengine/inc/framework
    ${TOP_DIR}/metadef/inc
    ${TOP_DIR}/metadef/inc/external
    depend/include/wrapper
    profapi/inc
)

set_target_properties(profimpl_fwk_share
    PROPERTIES
    OUTPUT_NAME $<IF:$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>,libprofimpl,profimpl>
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/
)

target_compile_definitions(profimpl_fwk_share PRIVATE
    $<$<STREQUAL:${CMAKE_BUILD_TYPE},Debug>:MSPROF_DEBUG>
    $<$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>:NOMINMAX>
    $<$<STREQUAL:${TARGET_SYSTEM_NAME},Windows>:WIN32>
)

target_link_options(profimpl_fwk_share PRIVATE
    -Wl,-z,relro,-z,now,-z,noexecstack
    -Wl,-Bsymbolic
    -Wl,--exclude-libs=ALL
)

if (PRODUCT)
    if (${TARGET_SYSTEM_NAME} STREQUAL "Windows")
        target_link_libraries(profimpl_fwk_share PRIVATE
            ascend_hal
        )
    else()
        target_link_libraries(profimpl_fwk_share PRIVATE
            ascend_hal_stub
        )
    endif()
endif()

target_link_libraries(profimpl_fwk_share PRIVATE
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
    ascend_hal
    error_manager
    -Wl,--as-needed
)

install(TARGETS profimpl_fwk_share OPTIONAL
    LIBRARY DESTINATION ${INSTALL_LIBRARY_DIR}
)
####################### libprofimpl.so ###########################