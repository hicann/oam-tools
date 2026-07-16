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

find_cann_package(unified_dlog MODULE REQUIRED)
find_cann_package(securec MODULE)
find_cann_package(platform MODULE REQUIRED)
find_cann_package(metadef MODULE REQUIRED)
find_cann_package(runtime MODULE REQUIRED)
find_cann_package(ascend_hal MODULE REQUIRED)
find_cann_package(mmpa MODULE REQUIRED)
find_cann_package(slog MODULE REQUIRED)
find_cann_package(adump MODULE REQUIRED)
if(ENABLE_TEST)
  list(APPEND CMAKE_PREFIX_PATH ${ASCEND_DIR}/tools/tikicpulib/lib/cmake)
  find_cann_package(tikicpulib REQUIRED)
endif()

add_library(runtime_inc_headers INTERFACE)
target_link_libraries(runtime_inc_headers INTERFACE 
  runtime_headers
)