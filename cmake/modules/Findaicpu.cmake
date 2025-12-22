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

if(aicpu_FOUND)
  message(STATUS "aicpu has been found")
  return()
endif()

include(FindPackageHandleStandardArgs)

if(BUILD_WITH_INSTALLED_DEPENDENCY_CANN_PKG)
  set(AICPU_INC_DIRS
    ${ASCEND_DIR}/${SYSTEM_PREFIX}/include/experiment
    ${ASCEND_DIR}/${SYSTEM_PREFIX}/include/experiment/msprof
    ${ASCEND_DIR}/${SYSTEM_PREFIX}/include/aicpu_common/context
    ${ASCEND_DIR}/${SYSTEM_PREFIX}/include/aicpu_common/context/common
    ${ASCEND_DIR}/${SYSTEM_PREFIX}/include/aicpu_common/context/cpu_proto
    ${ASCEND_DIR}/${SYSTEM_PREFIX}/include/aicpu_common/context/utils
    ${ASCEND_DIR}/${SYSTEM_PREFIX}/include/experiment/datagw/aicpu/common
  )
else()
  set(AICPU_INC_DIRS
    ${TOP_DIR}/abl/msprof/inc
    ${TOP_DIR}/ace/comop/inc
    ${TOP_DIR}/inc/aicpu/cpu_kernels
    ${TOP_DIR}/inc/external/aicpu
    ${TOP_DIR}/asl/ops/cann/ops/built-in/aicpu/context/inc
    ${TOP_DIR}/asl/ops/cann/ops/built-in/aicpu/impl/utils
    ${TOP_DIR}/asl/ops/cann/ops/built-in/aicpu/impl
    ${TOP_DIR}/ops-base/include/aicpu_common/context/common
    ${TOP_DIR}/open_source/eigen
  )
endif()

message(STATUS "Using AICPU include dirs: ${AICPU_INC_DIRS}")
