cmake_minimum_required(VERSION 3.16.0)
project(ascendc_add_demo)

# CANN 包路径（由 build.sh 传入 -DASCEND_CANN_PACKAGE_PATH）
if(NOT DEFINED ASCEND_CANN_PACKAGE_PATH)
    set(ASCEND_CANN_PACKAGE_PATH $ENV{ASCEND_HOME_PATH})
endif()

set(ASCEND_PYTHON_EXECUTABLE python3)
set(SOC_VERSION "Ascend910B3" CACHE STRING "soc version")
set(RUN_MODE "npu")

# 引入官方 AscendC kernel cmake 基础设施（提供 ascendc_library）
set(ASCENDC_CMAKE_DIR ${ASCEND_CANN_PACKAGE_PATH}/tools/ascendc_tools/cmake)
if(NOT EXISTS ${ASCENDC_CMAKE_DIR})
    set(ASCENDC_CMAKE_DIR ${ASCEND_CANN_PACKAGE_PATH}/compiler/tikcpp/ascendc_kernel_cmake)
endif()
include(${ASCENDC_CMAKE_DIR}/ascendc.cmake)

# device 侧：把 kernel 编成 AscendC 静态库，自动生成 aclrtlaunch_add_custom.h
ascendc_library(ascendc_kernels STATIC
    ${CMAKE_CURRENT_SOURCE_DIR}/add_kernel.cpp
)

# host 侧可执行
add_executable(add_custom_op ${CMAKE_CURRENT_SOURCE_DIR}/main.cpp)
target_include_directories(add_custom_op PRIVATE
    ${ASCEND_CANN_PACKAGE_PATH}/include
    ${ASCEND_CANN_PACKAGE_PATH}/include/acl
)
target_link_directories(add_custom_op PRIVATE
    ${ASCEND_CANN_PACKAGE_PATH}/lib64
)
target_link_libraries(add_custom_op PRIVATE
    ascendc_kernels
    ascendcl
    runtime
    stdc++
)
