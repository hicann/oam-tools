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

unset(OPTILING_SO_LIB_DIR)

file(GLOB_RECURSE LIB_OP_TILING_SO
    ${ASCEND_DIR}/../liboptiling.so
)

list(FILTER LIB_OP_TILING_SO INCLUDE REGEX "lib/linux/${CMAKE_SYSTEM_PROCESSOR}")

if(LIB_OP_TILING_SO)
    list(GET LIB_OP_TILING_SO 0 LIB_OP_TILING_SO_PATH)
    get_filename_component(LIB_OP_TILING_SO_PATH ${LIB_OP_TILING_SO_PATH} DIRECTORY)
    message(STATUS "Found optiling so lib:${LIB_OP_TILING_SO_PATH}")
else()
    message(STATUS "Cannot find library optiling so")
endif()

