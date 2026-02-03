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

if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/msaccucmp)
    set(DEST_MSACCUCMP_DIR ${CMAKE_CURRENT_SOURCE_DIR}/msaccucmp)
    set(CMP_TAR_NAME cmp_py.tgz)
    set(OPERATOR_CMP_DIR ${CMAKE_CURRENT_BINARY_DIR}/operator_cmp)
    set(COMPARE compare)
    add_custom_target(OperatorCmpFiles ALL DEPENDS ${CMP_TAR_NAME})
    add_custom_command(OUTPUT ${CMP_TAR_NAME}
        COMMAND rm -rf ${OPERATOR_CMP_DIR}
        COMMAND mkdir ${OPERATOR_CMP_DIR}
        COMMAND cd ${DEST_MSACCUCMP_DIR} && rm -rf ${CMP_TAR_NAME}
        COMMAND cd ${DEST_MSACCUCMP_DIR} && find ./ -name '*.py' |xargs tar czf ${CMP_TAR_NAME}
        COMMAND echo ${OPERATOR_CMP_DIR}/$(CMP_TAR_NAME)
        COMMAND mv ${DEST_MSACCUCMP_DIR}/${CMP_TAR_NAME} ${OPERATOR_CMP_DIR} && tar zxvf ${OPERATOR_CMP_DIR}/${CMP_TAR_NAME} -C ${OPERATOR_CMP_DIR}
        COMMAND rm -rf ${OPERATOR_CMP_DIR}/${CMP_TAR_NAME}
    )
    install(DIRECTORY ${OPERATOR_CMP_DIR} DESTINATION ${INSTALL_LIBRARY_DIR} OPTIONAL)
else()
    set(OPERATOR_CMP_DIR ${CMAKE_CURRENT_BINARY_DIR}/operator_cmp)
    file(MAKE_DIRECTORY ${OPERATOR_CMP_DIR})
    install(DIRECTORY ${OPERATOR_CMP_DIR} DESTINATION ${INSTALL_LIBRARY_DIR} OPTIONAL)
endif()