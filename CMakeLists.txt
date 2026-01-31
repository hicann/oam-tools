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

cmake_minimum_required(VERSION 3.15)
set(PKG_NAME oam)
project(Oam-Tools)

set(CMAKE_C_FLAGS_RELEASE "")
set(CMAKE_CXX_FLAGS_RELEASE "")

# install 参数
set(INSTALL_LIBRARY_DIR ${CMAKE_BINARY_DIR}/_CPack_Packages/makeself_staging/oam_tools)

# Ascend mode
if(DEFINED ENV{ASCEND_HOME_PATH})
  set(ASCEND_DIR $ENV{ASCEND_HOME_PATH})
else()
  if ("$ENV{USER}" STREQUAL "root")
    if(EXISTS /usr/local/Ascend/ascend-toolkit/latest)
      set(ASCEND_DIR /usr/local/Ascend/ascend-toolkit/latest)
    else()
      set(ASCEND_DIR /usr/local/Ascend/latest)
    endif()
  else()
    if(EXISTS $ENV{HOME}/Ascend/ascend-toolkit/latest)
      set(ASCEND_DIR $ENV{HOME}/Ascend/ascend-toolkit/latest)
    else()
      set(ASCEND_DIR $ENV{HOME}/Ascend/latest)
    endif()
  endif()
endif()
set(ASCEND_CANN_PACKAGE_PATH ${ASCEND_DIR})

set(ASCEND_COMPUTE_UNIT
    "ascend910b"
    CACHE STRING "soc that need to be compiled")
set(ASCEND_ALL_COMPUTE_UNIT
    "ascend310p;ascend910;ascend910b;ascend910_93;ascend910_95;ascend031;ascend035;ascend310b;ascend910_55;mc62cm12a"
    CACHE STRING "all soc list")

set(CMAKE_LIBRARY_PATH ${ASCEND_CANN_PACKAGE_PATH})
link_directories(
    ${ASCEND_CANN_PACKAGE_PATH}
    ${ASCEND_CANN_PACKAGE_PATH}/lib64
    ${ASCEND_CANN_PACKAGE_PATH}/devlib
)
set(CCACHE_PROGRAM "")
find_program(CCACHE_PROGRAM ccache)
if(CCACHE_PROGRAM)
    set(CMAKE_C_COMPILER_LAUNCHER ${CCACHE_PROGRAM})
    set(CMAKE_CXX_COMPILER_LAUNCHER ${CCACHE_PROGRAM})
endif()

if(PROJECT_SOURCE_DIR STREQUAL CMAKE_SOURCE_DIR)
  message(STATUS "compile project with library")
  option(BUILD_WITH_INSTALLED_DEPENDENCY_CANN_PKG "Build oam-tools with cann pkg" ON)
else()
  message(STATUS "compile project with src")
  option(BUILD_WITH_INSTALLED_DEPENDENCY_CANN_PKG "Build oam-tools with cann source" OFF)
endif()
set(OAM_TOOLS_DIR ${CMAKE_CURRENT_SOURCE_DIR})
# protobuf
include(cmake/protobuf.cmake)
include(cmake/protobuf_fun.cmake)
set(PROTOC_PROGRAM ${PROTOBUF_HOST_DIR}/bin/protoc)
set(PROTOBUF_HOST_INCLUDE ${PROTOBUF_HOST_DIR}/include)
message("PROTOC_PROGRAM: ${PROTOC_PROGRAM}")

# 外部依赖库及编译选项
include(cmake/third_party/third_party_header_libs.cmake)
include(cmake/intf_pub.cmake)

add_subdirectory(src/asys)
add_subdirectory(src/msaicerr)
add_subdirectory(src/hccl_test)
add_subdirectory(src/operator_cmp)

set(TOP_DIR "${CMAKE_CURRENT_SOURCE_DIR}" CACHE PATH "Project top directory")
set(HI_PYTHON "python" CACHE PATH "Python Path")
set(INSTALL_CONFIG_DIR cmake)
set(MSPROF_DIR ${CMAKE_CURRENT_SOURCE_DIR}/src/msprof)
set(PROF_BASIC_DIR "${MSPROF_DIR}/collector/basic")
set(TARGET_SYSTEM_NAME "Linux")
add_subdirectory(src/msprof/collector/dvvp/msprofbin)
add_subdirectory(src/msprof/collector/dvvp/acp)

if (ENABLE_COV OR ENABLE_UT)
    set(ASCEND_3RD_LIB_PATH ${CANN_3RD_LIB_PATH})
    set(OAM_SRC_DIR ${CMAKE_CURRENT_SOURCE_DIR}/src)
    set(MOCKCPP_INCLUDE_DIR ${ASCEND_3RD_LIB_PATH}/mockcpp/include)
    set(MOCKCPP_LIB_DIR ${ASCEND_3RD_LIB_PATH}/mockcpp/lib)
    include(CMakePrintHelpers)
    include(cmake/third_party/boost.cmake)
    include(cmake/third_party/mockcpp.cmake)
    include(cmake/third_party/gtest_shared.cmake)
    add_dependencies(GTest::gtest mockcpp)
    add_subdirectory(test)
endif()

#拷贝闭源包到制定目录
set(BUNDLE_PKG ${CMAKE_CURRENT_SOURCE_DIR}/bundle)
foreach(subdir IN ITEMS "aml" "built-in" "include" "profiler" "operator_cmp")
    if (EXISTS "${BUNDLE_PKG}/${subbdir}")
      file(COPY "${BUNDLE_PKG}/${subbdir}" DESTINATION ${INSTALL_LIBRARY_DIR}/.)
    endif()
endforeach()

# 生成version.info timestamp
set(OAM_TOOLS_VERSION_FILE ${CMAKE_CURRENT_BINARY_DIR}/version/version.info)
add_custom_command(
    OUTPUT ${OAM_TOOLS_VERSION_FILE}
    COMMAND bash ${CMAKE_CURRENT_SOURCE_DIR}/scripts/update_version_info/update_version_info.sh
            ${CMAKE_CURRENT_SOURCE_DIR}/version.info
            ${OAM_TOOLS_VERSION_FILE}
    DEPENDS 
        ${CMAKE_CURRENT_SOURCE_DIR}/version.info
    VERBATIM
)

add_custom_target(generate_version_file ALL DEPENDS "${OAM_TOOLS_VERSION_FILE}")

# 打run包
include(cmake/package.cmake)
pack_built_in()
