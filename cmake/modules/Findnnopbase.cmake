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

if(nnopbase_FOUND)
  message(STATUS "nnopbase has been found")
  return()
endif()

set(nnopbase_FOUND ON)
include(FindPackageHandleStandardArgs)

set(NNOPBASE_ACLNN_HEAD_SEARCH_PATHS
  ${ASCEND_DIR}/${SYSTEM_PREFIX}/include
  ${TOP_DIR}/ace/npuruntime/inc/external/            # compile with ci
)

set(NNOPBASE_OPDEV_HEAD_SEARCH_PATHS
  ${ASCEND_DIR}/${SYSTEM_PREFIX}/include/aclnn
  ${TOP_DIR}/ace/npuruntime/inc/nnopbase/            # compile with ci
)

set(NNOPBASE_LIB_SEARCH_PATHS
  ${ASCEND_DIR}/${SYSTEM_PREFIX}
)

find_path(NNOPBASE_ACLNN_INC_DIR
  NAMES aclnn/aclnn_base.h
  PATHS ${NNOPBASE_ACLNN_HEAD_SEARCH_PATHS}
  NO_CMAKE_SYSTEM_PATH
  NO_CMAKE_FIND_ROOT_PATH
)
if(NOT NNOPBASE_ACLNN_INC_DIR)
  set(nnopbase_FOUND OFF)
endif()

find_path(NNOPBASE_OPDEV_INC_DIR
  NAMES opdev/op_errno.h
  PATHS ${NNOPBASE_OPDEV_HEAD_SEARCH_PATHS}
  NO_CMAKE_SYSTEM_PATH
  NO_CMAKE_FIND_ROOT_PATH
)
if(NOT NNOPBASE_OPDEV_INC_DIR)
  set(nnopbase_FOUND OFF)
endif()

find_library(NNOPBASE_LIB_DIR
  NAME nnopbase
  PATHS ${NNOPBASE_LIB_SEARCH_PATHS}
  PATH_SUFFIXES lib64
  NO_CMAKE_SYSTEM_PATH
  NO_CMAKE_FIND_ROOT_PATH
)

get_filename_component(NNOPBASE_ACLNN_INC_DIR ${NNOPBASE_ACLNN_INC_DIR} REALPATH)
get_filename_component(NNOPBASE_OPDEV_INC_DIR ${NNOPBASE_OPDEV_INC_DIR} REALPATH)

if(NNOPBASE_LIB_DIR)
  get_filename_component(NNOPBASE_LIB_DIR ${NNOPBASE_LIB_DIR} REALPATH)
  add_library(nnopbase SHARED IMPORTED)
  set_target_properties(nnopbase PROPERTIES
    INTERFACE_INCLUDE_DIRECTORIES ${NNOPBASE_OPDEV_INC_DIR}
    IMPORTED_LOCATION ${NNOPBASE_LIB_DIR}
  )
else()
  if(BUILD_WITH_INSTALLED_DEPENDENCY_CANN_PKG)
    message(STATUS "Cannot find library nnopbase")
  endif()
endif()

if(nnopbase_FOUND)
  set(NNOPBASE_INCLUDE_DIRS
    ${NNOPBASE_ACLNN_INC_DIR}
    ${NNOPBASE_OPDEV_INC_DIR}
  )
  message(STATUS "Found aclnn include dir:  ${NNOPBASE_ACLNN_INC_DIR}")
  message(STATUS "Found opdev include dir:  ${NNOPBASE_OPDEV_INC_DIR}")
endif()