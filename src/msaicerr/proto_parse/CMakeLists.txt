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

protobuf_generate(dump_data_protos
    CppPath
    HeaderPath
    ${CMAKE_CURRENT_LIST_DIR}/dump_data.proto
    TARGET
)

add_dependencies(dump_data_protos protobuf_host_build ascend_protobuf_static)

add_library(ascend_dump_parser SHARED
    ${CppPath}
    dump_proto_to_json.cpp
)

add_dependencies(ascend_dump_parser dump_data_protos)

target_include_directories(ascend_dump_parser PRIVATE
    ${PROTOBUF_HOST_INCLUDE}
    ${CMAKE_CURRENT_LIST_DIR}
    ${CMAKE_BINARY_DIR}/proto/dump_data_protos
)

target_compile_definitions(ascend_dump_parser PRIVATE
    google=ascend_private
)

target_compile_options(ascend_dump_parser PRIVATE
    -fno-common
    -fstack-protector-all
    -fvisibility-inlines-hidden
    -Wextra
    -Wall
    -Wfloat-equal
    -std=c++17
)

target_link_libraries(ascend_dump_parser PRIVATE
    $<BUILD_INTERFACE:intf_pub_cxx17>
    ascend_protobuf_static
)

target_link_options(ascend_dump_parser PRIVATE
    -Wl,-z,relro,-z,now,-z,noexecstack
    -Wl,-Bsymbolic
    -Wl,--exclude-libs,ALL
)

install(TARGETS ascend_dump_parser OPTIONAL
    LIBRARY DESTINATION ${INSTALL_LIBRARY_DIR}/msaicerr/lib
)
