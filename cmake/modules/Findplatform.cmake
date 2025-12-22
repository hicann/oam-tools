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

if(platform_FOUND)
  message(STATUS "platform has been found")
  return()
endif()

include(FindPackageHandleStandardArgs)

set(PLATFORM_HEAD_SEARCH_PATHS
  ${ASCEND_DIR}/${SYSTEM_PREFIX}/include
  ${TOP_DIR}/metadef/inc/external            # compile with ci
  ${TOP_DIR}/ace/npuruntime/runtime/platform/inc            # compile with ci
)

set(PLATFORM_LIB_SEARCH_PATHS ${ASCEND_DIR}/${SYSTEM_PREFIX})

find_path(PLATFORM_INC_DIR
  NAMES platform/platform_info.h
  PATHS ${PLATFORM_HEAD_SEARCH_PATHS}
  NO_CMAKE_SYSTEM_PATH
  NO_CMAKE_FIND_ROOT_PATH
)

find_library(PLATFORM_LIB_DIR
  NAME platform
  PATHS ${PLATFORM_LIB_SEARCH_PATHS}
  PATH_SUFFIXES lib64
  NO_CMAKE_SYSTEM_PATH
  NO_CMAKE_FIND_ROOT_PATH
)

find_package_handle_standard_args(platform
      REQUIRED_VARS PLATFORM_INC_DIR)

get_filename_component(PLATFORM_INC_DIR ${PLATFORM_INC_DIR} REALPATH)
if(PLATFORM_LIB_DIR)
  get_filename_component(PLATFORM_LIB_DIR ${PLATFORM_LIB_DIR} REALPATH)
  add_library(platform SHARED IMPORTED)
  set_target_properties(platform PROPERTIES
    INTERFACE_INCLUDE_DIRECTORIES ${PLATFORM_INC_DIR}
    IMPORTED_LOCATION ${PLATFORM_LIB_DIR}
  )
else()
  if(BUILD_WITH_INSTALLED_DEPENDENCY_CANN_PKG)
    message(STATUS "Cannot find library platform")
  endif()
endif()

if(platform_FOUND)
  if(NOT platform_FIND_QUIETLY)
    message(STATUS "Found platform include:${PLATFORM_INC_DIR}")
  endif()
  set(PLATFORM_INC_DIRS ${PLATFORM_INC_DIR})
endif()