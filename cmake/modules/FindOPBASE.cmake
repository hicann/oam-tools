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

if(OPBASE_FOUND)
  message(STATUS "OpBase has been found")
  return()
endif()

include(FindPackageHandleStandardArgs)

set(OPBASE_HEAD_SEARCH_PATHS
  ${ASCEND_DIR}/${SYSTEM_PREFIX}/pkg_inc
  ${TOP_DIR}/ops-base/pkg_inc             # compile with ci
)

set(OPBASE_LIB_SEARCH_PATHS ${ASCEND_DIR}/${SYSTEM_PREFIX})

find_path(OPBASE_INC_DIR
  NAMES op_common/op_host/util/opbase_export.h
  PATHS ${OPBASE_HEAD_SEARCH_PATHS}
  NO_CMAKE_SYSTEM_PATH
  NO_CMAKE_FIND_ROOT_PATH
)

find_library(OPBASE_LIB_DIR
  NAME ops_base
  PATHS ${OPBASE_LIB_SEARCH_PATHS}
  PATH_SUFFIXES lib64
  NO_CMAKE_SYSTEM_PATH
  NO_CMAKE_FIND_ROOT_PATH
)

find_package_handle_standard_args(OPBASE
            REQUIRED_VARS OPBASE_INC_DIR)

get_filename_component(OPBASE_INC_DIR ${OPBASE_INC_DIR} REALPATH)
if(OPBASE_LIB_DIR)
  get_filename_component(OPBASE_LIB_DIR ${OPBASE_LIB_DIR} REALPATH)
  add_library(opsbase SHARED IMPORTED)
  set_target_properties(opsbase PROPERTIES
    INTERFACE_INCLUDE_DIRECTORIES ${OPBASE_INC_DIR}
    IMPORTED_LOCATION ${OPBASE_LIB_DIR}
  )
else()
  if(BUILD_WITH_INSTALLED_DEPENDENCY_CANN_PKG)
    message(STATUS "Cannot find library ops_base")
  endif()
endif()

if(OPBASE_FOUND)
  if(NOT OPBASE_FIND_QUIETLY)
    message(STATUS "Found OPABSE include:${OPBASE_INC_DIR}")
    message(STATUS "Found OPABSE lib:${OPBASE_LIB_DIR}")
  endif()
  set(OPBASE_INC_DIRS
    ${OPBASE_INC_DIR}
    ${OPBASE_INC_DIR}/op_common
    ${OPBASE_INC_DIR}/op_common/op_host
  )
endif()