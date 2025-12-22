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

include(FindPackageHandleStandardArgs)
set(runtime_FOUND ON)
#search acl.h
set(ACL_HEAD_SEARCH_PATHS
  ${ASCEND_DIR}/${SYSTEM_PREFIX}/include
  ${TOP_DIR}/ace/npuruntime/acl/inc/external            # compile with ci
)
find_path(ACL_INC_DIR
  NAMES acl/acl.h
  PATHS ${ACL_HEAD_SEARCH_PATHS}
  NO_CMAKE_SYSTEM_PATH
  NO_CMAKE_FIND_ROOT_PATH
)
if(NOT ACL_INC_DIR)
  set(runtime_FOUND OFF)
  message(FATAL_ERROR "no source acl include dir found")
endif()
get_filename_component(ACL_INC_DIR ${ACL_INC_DIR} REALPATH)
message(STATUS "Found source acl include dir:  ${ACL_INC_DIR}")

#search rt_external.h
set(RUNTIME_SEARCH_PATH
  ${ASCEND_DIR}/${SYSTEM_PREFIX}/pkg_inc/runtime
  ${TOP_DIR}/ace/npuruntime/inc            # compile with ci
)
find_path(RUNTIME_INC_DIR
  NAMES rt_external.h
  PATHS ${RUNTIME_SEARCH_PATH}
  NO_CMAKE_SYSTEM_PATH
  NO_CMAKE_FIND_ROOT_PATH
)

if(NOT RUNTIME_INC_DIR)
  message(STATUS "no source pkg runtime include dir found")
  #search rt_external.h
  set(RUNTIME_SEARCH_PATH
    ${ASCEND_DIR}/${SYSTEM_PREFIX}/include/experiment/runtime
    ${TOP_DIR}/ace/npuruntime/inc            # compile with ci
  )
  find_path(RUNTIME_INC_DIR
    NAMES runtime/rt.h
    PATHS ${RUNTIME_SEARCH_PATH}
    NO_CMAKE_SYSTEM_PATH
    NO_CMAKE_FIND_ROOT_PATH
  )
endif()

if(NOT RUNTIME_INC_DIR)
  set(runtime_FOUND OFF)
  message(FATAL_ERROR "no source runtime include dir found")
endif()
get_filename_component(RUNTIME_INC_DIR ${RUNTIME_INC_DIR} REALPATH)

if(runtime_FOUND)
  if(NOT runtime_FIND_QUIETLY)
    message(STATUS "Found source npuruntime include dir: ${RUNTIME_INC_DIR}")
  endif()
  set(NPURUNTIME_INCLUDE_DIRS
    ${ACL_INC_DIR}
    ${RUNTIME_INC_DIR}
    ${RUNTIME_INC_DIR}/runtime
  )
endif()