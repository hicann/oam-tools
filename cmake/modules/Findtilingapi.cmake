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

if(tilingapi_FOUND)
  message(STATUS "tilingapi has been found")
  return()
endif()

include(FindPackageHandleStandardArgs)

set(TILINGAPI_HEAD_SEARCH_PATHS
  ${ASCEND_DIR}/${SYSTEM_PREFIX}/include
)

set(TILINGAPI_LIB_SEARCH_PATHS
  ${ASCEND_DIR}/${SYSTEM_PREFIX}
)

find_path(TILINGAPI_INC_DIR
  NAMES tiling/tiling_api.h
  PATHS ${TILINGAPI_SEARCH_PATHS}
  NO_CMAKE_SYSTEM_PATH
  NO_CMAKE_FIND_ROOT_PATH
)

find_library(TILINGAPI_LIB_DIR
  NAME libtiling_api.a
  PATHS ${TILINGAPI_LIB_SEARCH_PATHS}
  PATH_SUFFIXES lib64
  NO_CMAKE_SYSTEM_PATH
  NO_CMAKE_FIND_ROOT_PATH
)

if(TILINGAPI_INC_DIR)
  get_filename_component(TILINGAPI_INC_DIR ${TILINGAPI_INC_DIR} REALPATH)
  message(STATUS "Found tilingapi include:${TILINGAPI_INC_DIR}")
endif()

get_filename_component(TILINGAPI_INC_PREFIX ${TILINGAPI_INC_DIR} DIRECTORY)
set(TILINGAPI_INC_DIRS
  ${TILINGAPI_INC_PREFIX}/include
  ${TILINGAPI_INC_PREFIX}/ascendc
  ${TILINGAPI_INC_PREFIX}/ascendc/include
  ${TILINGAPI_INC_PREFIX}/ascendc/include/highlevel_api
  ${TILINGAPI_INC_PREFIX}/ascendc/include/highlevel_api/lib
  ${TILINGAPI_INC_PREFIX}/ascendc/include/highlevel_api/impl
  ${TILINGAPI_INC_PREFIX}/ascendc/include/highlevel_api/tiling
)
message(STATUS "TILINGAPI_INC_DIRS: ${TILINGAPI_INC_DIRS}")

if(TILINGAPI_LIB_DIR)
  get_filename_component(TILINGAPI_LIB_DIR ${TILINGAPI_LIB_DIR} REALPATH)
  message(STATUS "Found tilingapi lib:${TILINGAPI_LIB_DIR}")
  if(NOT TARGET tiling_api)
    add_library(tiling_api STATIC IMPORTED)
    set_target_properties(tiling_api PROPERTIES
      IMPORTED_LOCATION ${TILINGAPI_LIB_DIR}
    )
  endif()
else()
  if(BUILD_WITH_INSTALLED_DEPENDENCY_CANN_PKG)
    message(STATUS "Cannot find library tiling_api")
  endif()
endif()