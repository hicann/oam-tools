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

# Ascend mode
set(CMAKE_PREFIX_PATH ${ASCEND_DIR}/)

set(CMAKE_MODULE_PATH
  ${CMAKE_CURRENT_SOURCE_DIR}/cmake/modules
  ${CMAKE_MODULE_PATH}
)
message(STATUS "CMAKE_MODULE_PATH            :${CMAKE_MODULE_PATH}")

set(OAM_TOOLS_CXX_FLAGS)
string(APPEND OAM_TOOLS_CXX_FLAGS " ${COMPILE_OP_MODE}")
string(APPEND OAM_TOOLS_CXX_FLAGS " -Wall")
string(APPEND OAM_TOOLS_CXX_FLAGS " -Wextra")
string(APPEND OAM_TOOLS_CXX_FLAGS " -Wshadow")
string(APPEND OAM_TOOLS_CXX_FLAGS " -Wformat=2")
string(APPEND OAM_TOOLS_CXX_FLAGS " -fno-common")
string(APPEND OAM_TOOLS_CXX_FLAGS " -fPIC")
if(NOT "${CMAKE_CXX_COMPILER_ID}" STREQUAL "Clang")
  # TODO: add -Werror when fix all compile warnings
  # string(APPEND OAM_TOOLS_CXX_FLAGS " -Werror")
  string(APPEND OAM_TOOLS_CXX_FLAGS " -Wformat-signedness")
endif()
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${OAM_TOOLS_CXX_FLAGS}")
message(STATUS "compile option:${CMAKE_CXX_FLAGS}")

if(BUILD_WITH_INSTALLED_DEPENDENCY_CANN_PKG)
  if(EXISTS "${ASCEND_CANN_PACKAGE_PATH}/${SYSTEM_PREFIX}/tikcpp/ascendc_kernel_cmake")
    find_package(ASC REQUIRED HINTS ${ASCEND_CANN_PACKAGE_PATH}/${SYSTEM_PREFIX}/tikcpp/ascendc_kernel_cmake)
  else()
    find_package(ASC REQUIRED HINTS ${ASCEND_CANN_PACKAGE_PATH}/compiler/tikcpp/ascendc_kernel_cmake)
  endif()
endif()
find_package(dlog MODULE REQUIRED)
find_package(securec MODULE)
find_package(OPBASE MODULE REQUIRED)
find_package(platform MODULE REQUIRED)
find_package(metadef MODULE REQUIRED)
find_package(runtime MODULE REQUIRED)
find_package(nnopbase MODULE REQUIRED)
find_package(tilingapi MODULE REQUIRED)
find_package(aicpu MODULE REQUIRED)
if(ENABLE_TEST)
  list(APPEND CMAKE_PREFIX_PATH ${ASCEND_DIR}/tools/tikicpulib/lib/cmake)
  find_package(tikicpulib REQUIRED)
endif()