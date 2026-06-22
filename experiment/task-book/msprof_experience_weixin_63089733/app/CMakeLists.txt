# ----------------------------------------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# ----------------------------------------------------------------------------------------------------------


cmake_minimum_required(VERSION 3.16)

find_package(ASC REQUIRED)

project(kernel_samples LANGUAGES ASC CXX)

set(ASC_SOURCES
    matmul_leakyrelu.asc
)

set(SHARED_LIBRARIES
    tiling_api
    register
    platform
    m
    dl
)

set(NPU_ARCH "dav-2201" CACHE STRING "NPU architecture")
string(REPLACE "-" "_" NPU_ARCH_PATH "${NPU_ARCH}")

set(COMPILE_OPTIONS
    $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=${NPU_ARCH}>
)

add_executable(demo ${ASC_SOURCES})

target_link_libraries(demo PRIVATE ${SHARED_LIBRARIES})
target_compile_options(demo PRIVATE ${COMPILE_OPTIONS})

add_executable(demo_sim ${ASC_SOURCES})

set_target_properties(demo_sim PROPERTIES
    LINK_FLAGS "-Wl,--disable-new-dtags"
)

set(SIM_LIBRARIES
    runtime_camodel
    npu_drv_camodel
    ${SHARED_LIBRARIES}
)

target_link_libraries(demo_sim PRIVATE ${SIM_LIBRARIES})
target_compile_options(demo_sim PRIVATE ${COMPILE_OPTIONS})


target_link_directories(demo_sim PRIVATE
    $ENV{ASCEND_HOME_PATH}/x86_64-linux/simulator/${NPU_ARCH_PATH}/lib
    $ENV{ASCEND_HOME_PATH}/tools/simulator/${NPU_ARCH_PATH}/lib
)
