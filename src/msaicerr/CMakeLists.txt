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
project(Msaicerr)

message(${CMAKE_CURRENT_SOURCE_DIR})

add_subdirectory(proto_parse)

set(MS_AIC_ERR_NAME msaicerr_py.tgz)
set(MSAICERR_DIR ${CMAKE_CURRENT_BINARY_DIR}/msaicerr)
set(PROTO_FILE ${CMAKE_CURRENT_SOURCE_DIR}/proto_parse/dump_data.proto)

protobuf_generate_py(toolchain_msaicerr PROTO_SRCS ${PROTO_FILE})

add_custom_target(MsaicerrFiles ALL DEPENDS ascend_dump_parser ${MS_AIC_ERR_NAME})
add_custom_command(OUTPUT  ${MS_AIC_ERR_NAME}
    DEPENDS ${PROTO_SRCS}
    COMMAND rm -rf ${MSAICERR_DIR}
    COMMAND mkdir ${MSAICERR_DIR}
    COMMAND cp -r ${PROTO_SRCS} ${CMAKE_CURRENT_SOURCE_DIR}/ms_interface
    COMMAND cd ${CMAKE_CURRENT_SOURCE_DIR}/ && rm -rf ${MS_AIC_ERR_NAME}
    COMMAND cd ${CMAKE_CURRENT_SOURCE_DIR}/ && find ./ -name '*.py' |xargs tar czf ${MS_AIC_ERR_NAME}
    COMMAND echo ${MSAICERR_DIR}/$(MS_AIC_ERR_NAME)
    COMMAND mv ${CMAKE_CURRENT_SOURCE_DIR}/${MS_AIC_ERR_NAME} ${MSAICERR_DIR} && tar zxvf ${MSAICERR_DIR}/${MS_AIC_ERR_NAME} -C ${MSAICERR_DIR}
    COMMAND rm -rf ${MSAICERR_DIR}/${MS_AIC_ERR_NAME}
)

install(DIRECTORY
    ${MSAICERR_DIR}
    DESTINATION ${INSTALL_LIBRARY_DIR}/msaicerr OPTIONAL)
