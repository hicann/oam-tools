# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd. All Rights Reserved.
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
project(MsaicerrProtoParseUT)

find_package(GTest REQUIRED)

add_executable(test_dump_proto_to_json
    test_dump_proto_to_json.cpp
)

target_include_directories(test_dump_proto_to_json PRIVATE
    ${CMAKE_SOURCE_DIR}/src/msaicerr/proto_parse
)

target_link_libraries(test_dump_proto_to_json PRIVATE
    GTest::gtest
    GTest::gtest_main
    ascend_dump_parser
)

include(GoogleTest)
gtest_discover_tests(test_dump_proto_to_json)
