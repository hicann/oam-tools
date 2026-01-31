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
cmake_minimum_required(VERSION 3.15)
project(Operator_cmp)

set(ORIGIN_MSACCUCMP_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../../../asl/devtools/msaccucmp)
message("MSACCUCMP_DIR : ${ORIGIN_MSACCUCMP_DIR}")
if(EXISTS ${ORIGIN_MSACCUCMP_DIR})
    set(DEST_MSACCUCMP_DIR ${CMAKE_CURRENT_SOURCE_DIR}/msaccucmp)
    file(COPY ${ORIGIN_MSACCUCMP_DIR}/
        DESTINATION ${DEST_MSACCUCMP_DIR}
        FILES_MATCHING PATTERN "*")
    
    set(COPIED_CMAKE_FILE ${DEST_MSACCUCMP_DIR}/CMakeLists.txt)
    file(READ ${COPIED_CMAKE_FILE} CMAKE_CONTENT)
    string(REPLACE "lib" "\${INSTALL_LIBRARY_DIR}" CMAKE_CONTENT ${CMAKE_CONTENT})
    file(WRITE ${COPIED_CMAKE_FILE} ${CMAKE_CONTENT})
    set(TOP_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../../..)
    add_subdirectory(${DEST_MSACCUCMP_DIR})
    add_dependencies(OperatorCmpFiles host_protoc protobuf_host_build ascend_protobuf_static)
else()
    set(OPERATOR_CMP_DIR ${CMAKE_CURRENT_BINARY_DIR}/operator_cmp)
    file(MAKE_DIRECTORY ${OPERATOR_CMP_DIR})
    install(DIRECTORY ${OPERATOR_CMP_DIR} DESTINATION ${INSTALL_LIBRARY_DIR} OPTIONAL)
endif()