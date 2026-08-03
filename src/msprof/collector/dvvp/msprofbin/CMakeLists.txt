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

# device 侧联编守卫：本目录可能被单独作为入口联编，补齐缺失的 INTERFACE 目标
include(${CMAKE_CURRENT_LIST_DIR}/../msprof_intf_pub_cxx.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/../msprof_find_target.cmake)
protobuf_generate(msprofbin_proto
    CppPath
    HeaderPath
    ${CMAKE_CURRENT_SOURCE_DIR}/../proto/profiler.proto
    TARGET
)

if(BUILD_OPEN_PROJECT)
    add_dependencies(msprofbin_proto host_protoc ascend_protobuf_static)
endif()

set(msprofBinHeader
    ${SOURCE_DIR}/src
    ${TOP_DIR}/inc
    ${TOP_DIR}/inc/driver
    ${TOP_DIR}/inc/aicpu
    ${TOP_DIR}/../../metadef/inc/common/util/error_manager
    ${MSPROF_DIR}/inc/toolchain
    ${PROTOBUF_HOST_STATIC_INCLUDE}
    ${ASCEND_CANN_PACKAGE_PATH}/include/experiment/metadef/common/util/error_manager
    include
    ../
    ../app
    ../common/utils
    ../msprof/engine/include
    ../host/include/
    ../message/
    ../common
    ../common/json
    ../common/logger
    ../common/queue
    ../common/statistics
    ../common/validation
    ../common/platform
    ../common/json
    ../common/config
    ../../basic/osal
    ../common/errno
    ../depend/include/stub
    ../msprof/common/include/
    ../msprof/dynamic_profiling/include/
    ../profimpl/adapter/inc
    ../profimpl/platform
    ../profimpl/collect/job_wrapper/include
    ../profimpl/inc
    ../msprof/msproftx/mstx/inc
    ../profhal/adx/inc
    ../profhal/halinc
    ../driver/inc
    ../task_handle/include
    ../transport
    ../profhal/adx/inc
)

set(hdcCpp
    ../profhal/adx/stub/adx_prof_api.cpp
    ../profhal/adx/wrapper/hdc_api.cpp
    ../profhal/adx/wrapper/memory_utils.cpp
)

set(msprofbinCpp
    src/msprof_bin.cpp
    src/msopprof_manager.cpp
    src/msprof_manager.cpp
    src/msprof_task.cpp
    src/msprof_params_adapter.cpp
    src/input_parser.cpp
    src/running_mode.cpp
    ../app/application.cpp
    ../app/env_manager.cpp
    ../common/cmd_log/cmd_log.cpp
    ../common/utils/utils.cpp
    ../common/json/json.cpp
    ../../basic/osal/osal.c
    ../common/config/config_manager.cpp
    ../common/memory/chunk_pool.cpp
    ../common/thread/thread.cpp
    ../common/thread/thread_pool.cpp
    ../common/socket/local_socket.cpp
    ../common/statistics/perf_count.cpp
    ../common/validation/param_validation.cpp
    ../common/platform/platform.cpp
    ../common/json/json.cpp
    ../depend/stub/error_manager/msprof_error_manager_stub.cpp
    ../driver/devmgmt/ai_drv_dev_api.cpp
    ../driver/devmgmt/ai_drv_dsmi_api.cpp
    ../driver/channel/ai_drv_prof_api.cpp
    ../profimpl/collect/job_wrapper/src/collection_job.cpp
    ../profimpl/collect/job_wrapper/src/collection_register.cpp
    ../profimpl/collect/job_wrapper/src/job_factory.cpp
    ../profimpl/collect/job_wrapper/src/job_device_rpc.cpp
    ../profimpl/collect/job_wrapper/src/prof_comm_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_soc_pmu_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_l2cache_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_ts_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_stars_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_ccu_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_hwts_log_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_instr_perf_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_biu_perf_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_aicore_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_aicpu_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_sys_info_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_hardware_mem_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_dvpp_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_lpm_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_inter_connection_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_io_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_timer.cpp
    ../profimpl/collect/job_wrapper/src/prof_perf_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_host_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_diagnostic_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_aicpu_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_channel_manager.cpp
    ../profimpl/collect/job_wrapper/src/prof_adprof_job.cpp
    ../profimpl/collect/job_wrapper/src/prof_drv_event.cpp
    ../profimpl/collect/job_wrapper/src/job_device_soc.cpp
    ../profimpl/collect/job_wrapper/src/adprof_collector_proxy.cpp
    ../msprof/dynamic_profiling/src/dyn_prof_client.cpp
    ../profimpl/adapter/src/json_parser.cpp
    ../profimpl/platform/platform_interface.cpp
    ../profimpl/platform/base_analyzer.cpp
    ../profimpl/platform/modena_platform.cpp
    ../profimpl/platform/mini_platform.cpp
    ../profimpl/platform/cloud_v2_platform.cpp
    ../profimpl/platform/david_platform.cpp
    ../profimpl/platform/david_v121_platform.cpp
    ../profimpl/platform/cloud_platform.cpp
    ../profimpl/platform/dc_platform.cpp
    ../profimpl/platform/mdc_lite_platform.cpp
    ../profimpl/platform/mdc_lite_v2_platform.cpp
    ../profimpl/platform/mdc_mini_v3_platform.cpp
    ../profimpl/platform/mdc_platform.cpp
    ../profimpl/platform/mini_v3_platform.cpp
    ../profimpl/platform/mdc_v2_platform.cpp
    ../message/codec.cpp
    ../transport/file_transport.cpp
    ../transport/pipe_transport.cpp
    ../transport/prof_channel.cpp
    ../transport/uploader_mgr.cpp
    ../transport/hash_data.cpp
    ../transport/uploader.cpp
    ../transport/file_ageing.cpp
    ../transport/file_slice.cpp
    ../task_handle/src/info_json.cpp
    ../task_handle/src/task_relationship_mgr.cpp
    ../transport/hdc/data_handle.cpp
    ../transport/hdc/hdc_transport.cpp
    ../transport/hdc/helper_transport.cpp
    ../transport/hdc/device_transport.cpp
    ../transport/hdc/platform/rpc/dev_mgr_api.cpp
    ${hdcCpp}
    ${CppPath}
)

if(${TARGET_SYSTEM_NAME} STREQUAL "Windows")
set(msprofbinCpp
    src/win/msprof_bin.cpp
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
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_BINARY_DIR}/proto/msprofbin_proto
)


target_compile_options(msprofbin PRIVATE
    -fPIE
    -fno-strict-aliasing
    -fno-common
    -Wall
    # PRODUCT_SIDE 已从 build.sh 中移除（仓内仅此处引用，业务上无 host/device
    # 双侧需求），原本传 device 时本行 generator expression 永远求值为空，
    # 即"死代码"；保留本行以备后续如需启用旧 ABI 时取消注释。
    # $<$<STREQUAL:${PRODUCT_SIDE},host>:-D_GLIBCXX_USE_CXX11_ABI=0>
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
    $<BUILD_INTERFACE:oam_intf_pub>
    $<BUILD_INTERFACE:mmpa_headers>
    $<BUILD_INTERFACE:adump_headers>
    $<BUILD_INTERFACE:slog_headers>
    $<BUILD_INTERFACE:msprofbinOnetrack_pub>
    runtime_inc_headers
    stub_adcore_headers    
)

set_target_properties(msprofbin
    PROPERTIES
    OUTPUT_NAME msprof
    LIBRARY_OUTPUT_DIRECTORY ${INSTALL_LIBRARY_DIR}/msprof
)

if (DEFINED PKG_NAME AND PKG_NAME STREQUAL "oam")
    install(TARGETS msprofbin ${INSTALL_OPTIONAL}
        RUNTIME DESTINATION ${INSTALL_LIBRARY_DIR}/tools/profiler/bin
        COMPONENT oam-tools
    )
else()
    install(TARGETS msprofbin ${INSTALL_OPTIONAL}
        RUNTIME DESTINATION ${INSTALL_LIBRARY_DIR}/profiler/bin
        COMPONENT oam-tools
    )

    install(TARGETS msprofbin ${INSTALL_OPTIONAL}
        LIBRARY DESTINATION ${INSTALL_LIBRARY_DIR}/profiler/bin
        COMPONENT oam-tools
    )
endif()

### onetrack target interface

add_library(msprofbinOnetrack_pub INTERFACE)

target_link_libraries(msprofbinOnetrack_pub INTERFACE
    $<BUILD_INTERFACE:oam_intf_pub>
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
    ${CMAKE_CURRENT_SOURCE_DIR}/msprof-0.0.1-py3-none-any.whl
)
# whl 进包权限 555，等价旧 install(CODE) 的 chmod -R 555（安装期终态，不影响重解包）。
install(PROGRAMS ${msprof_whl}
    DESTINATION ${INSTALL_LIBRARY_DIR}/tools/profiler/profiler_tool
    ${INSTALL_OPTIONAL}
    COMPONENT oam-tools
    PERMISSIONS OWNER_READ OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
)

# 构建期解包 whl 进包，等价旧 install(CODE)；if(EXISTS) 守卫单独联编无 whl 的场景。
if(EXISTS "${msprof_whl}")
    set(_msprof_extracted_dir "${CMAKE_CURRENT_BINARY_DIR}/msprof_whl_extracted")
    add_custom_command(
        OUTPUT "${_msprof_extracted_dir}/.extracted"
        # 先删后建：whl 版本恒定，pip 无 --force-reinstall 会判 already satisfied 跳过、残留旧代码。
        COMMAND ${CMAKE_COMMAND} -E remove_directory "${_msprof_extracted_dir}"
        COMMAND ${CMAKE_COMMAND} -E make_directory "${_msprof_extracted_dir}"
        COMMAND pip3 install --no-deps --disable-pip-version-check
                "${msprof_whl}" -t "${_msprof_extracted_dir}"
        COMMAND find "${_msprof_extracted_dir}" -type d -name __pycache__ -prune -exec rm -rf {} +
        COMMAND ${CMAKE_COMMAND} -E touch "${_msprof_extracted_dir}/.extracted"
        DEPENDS ${msprof_whl}
        COMMENT "Extracting msprof whl at build time"
        VERBATIM
    )
    add_custom_target(msprof_whl_extract ALL
        DEPENDS "${_msprof_extracted_dir}/.extracted"
    )
    # 绑定主构建目标，保证 install 依赖的解包产物在构建后就绪。
    add_dependencies(msprofbin msprof_whl_extract)

    # 权限仅在安装期声明 555，等价旧 install(CODE) 的安装期 chmod 555。
    install(DIRECTORY "${_msprof_extracted_dir}/"
        DESTINATION ${INSTALL_LIBRARY_DIR}/tools/profiler/profiler_tool
        ${INSTALL_OPTIONAL}
        COMPONENT oam-tools
        FILE_PERMISSIONS OWNER_READ OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
        DIRECTORY_PERMISSIONS OWNER_READ OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
        PATTERN ".extracted" EXCLUDE
    )
endif()
