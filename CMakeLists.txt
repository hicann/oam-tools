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
set(INSTALL_LIBRARY_DIR ${CMAKE_BINARY_DIR}/_CPack_Packages/makeself_staging)

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

include(cmake/func.cmake)
include(version.cmake)
check_pkg_build_deps("oam-tools")
add_version_info_targets()

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
include(cmake/third_party/protobuf.cmake)
include(cmake/third_party/protobuf_fun.cmake)
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
    set(BOOST_INCLUDE_PATH ${ASCEND_3RD_LIB_PATH}/boost)
    include(CMakePrintHelpers)
    include(cmake/third_party/boost.cmake)
    include(cmake/third_party/mockcpp.cmake)
    include(cmake/third_party/gtest_shared.cmake)
    add_dependencies(GTest::gtest mockcpp)
    add_subdirectory(test)
endif()

# 拷贝闭源包到指定目录
set(BUNDLE_PKG ${CMAKE_CURRENT_SOURCE_DIR}/bundle)

# 拷贝 aml 目录内容
if(EXISTS "${BUNDLE_PKG}/aml")
    file(COPY "${BUNDLE_PKG}/aml/lib64/libascend_ml_detect.so" DESTINATION ${INSTALL_LIBRARY_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/lib64)
    file(COPY "${BUNDLE_PKG}/aml/lib64/libascend_ml.so" DESTINATION ${INSTALL_LIBRARY_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/lib64)
    file(COPY "${BUNDLE_PKG}/aml/lib64/plugin" DESTINATION ${INSTALL_LIBRARY_DIR}/tools/aml/lib64)
    file(COPY "${BUNDLE_PKG}/aml/lib64/plugin_v2" DESTINATION ${INSTALL_LIBRARY_DIR}/tools/aml/lib64)

    # 如果 plugin/bin 存在，将其内容移动到 plugin 下并删除 bin
    set(_aml_plugin_bin "${INSTALL_LIBRARY_DIR}/tools/aml/lib64/plugin/bin")
    if(EXISTS "${_aml_plugin_bin}" AND IS_DIRECTORY "${_aml_plugin_bin}")
        # 防御性检查：仅删除位于本次构建目录下的 bin，避免 INSTALL_LIBRARY_DIR
        # 为空或被异常修改时，rm -rf 落到用户文件系统的真实路径上造成数据丢失
        get_filename_component(_aml_plugin_bin_abs "${_aml_plugin_bin}" REALPATH)
        get_filename_component(_build_dir_abs "${CMAKE_BINARY_DIR}" REALPATH)
        string(FIND "${_aml_plugin_bin_abs}" "${_build_dir_abs}/" _aml_under_build)
        if(NOT INSTALL_LIBRARY_DIR OR NOT _aml_under_build EQUAL 0)
            message(FATAL_ERROR
                "Refusing to remove '${_aml_plugin_bin_abs}': path is not under build "
                "directory '${_build_dir_abs}'. Check INSTALL_LIBRARY_DIR="
                "'${INSTALL_LIBRARY_DIR}'.")
        endif()
        execute_process(
            COMMAND ${CMAKE_COMMAND} -E copy_directory
                "${_aml_plugin_bin}"
                "${INSTALL_LIBRARY_DIR}/tools/aml/lib64/plugin"
        )
        execute_process(
            COMMAND ${CMAKE_COMMAND} -E rm -rf "${_aml_plugin_bin}"
        )
    endif()
    unset(_aml_plugin_bin)
endif()

# 拷贝 include 目录
if(EXISTS "${BUNDLE_PKG}/include")
    file(COPY "${BUNDLE_PKG}/include" DESTINATION ${INSTALL_LIBRARY_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux)
endif()

# 拷贝 built-in 目录
if(EXISTS "${BUNDLE_PKG}/built-in")
    file(COPY "${BUNDLE_PKG}/built-in/op_impl/ai_core/tbe" DESTINATION ${INSTALL_LIBRARY_DIR}/opp/built-in/op_impl/ai_core)
    file(COPY "${BUNDLE_PKG}/built-in/op_impl/ai_core/tbe/op_api/lib/linux/${CMAKE_SYSTEM_PROCESSOR}/libopapi_oam.so"
        DESTINATION ${INSTALL_LIBRARY_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/lib64)
endif()

# 创建 bin pkg_inc 目录
file(MAKE_DIRECTORY ${INSTALL_LIBRARY_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/bin)
file(MAKE_DIRECTORY ${INSTALL_LIBRARY_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/pkg_inc)

# 打run包
include(cmake/package.cmake)
pack_built_in()
