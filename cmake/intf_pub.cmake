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

# 添加编译选项intf_pub
add_library(intf_pub_base INTERFACE)
target_compile_options(intf_pub_base INTERFACE
    -fPIC
    -pipe
    -Wall
    -Wextra
    -Wfloat-equal
    -fno-common
    -fstack-protector-strong
    -D_GLIBCXX_USE_CXX11_ABI=0
    $<$<BOOL:${ENABLE_ASAN}>:-fsanitize=address -fsanitize=leak -fsanitize-recover=address,all -fno-stack-protector -fno-omit-frame-pointer -g>
    $<$<BOOL:${ENABLE_TSAN}>:-fsanitize=thread -fsanitize-recover=thread,all -g>
    $<$<BOOL:${ENABLE_USAN}>:-fsanitize=undefined -fno-sanitize=alignment -g>
    $<$<BOOL:${ENABLE_GCOV}>:-fprofile-arcs -ftest-coverage>
)

target_link_options(intf_pub_base INTERFACE
    -Wl,-z,relro
    -Wl,-z,now
    -Wl,-z,noexecstack
    -Wl,-Bsymbolic
    $<$<CONFIG:Release>:-Wl,--build-id=none>
    $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:-pie>
    $<$<CONFIG:Release>:-s>
    $<$<BOOL:${ENABLE_ASAN}>:-fsanitize=address -fsanitize=leak -fsanitize-recover=address>
    $<$<BOOL:${ENABLE_TSAN}>:-fsanitize=thread -fsanitize-recover=thread,all -g>
    $<$<BOOL:${ENABLE_USAN}>:-fsanitize=undefined -fno-sanitize=alignment -g>
    $<$<BOOL:${ENABLE_GCOV}>:-fprofile-arcs -ftest-coverage>
)
target_link_libraries(intf_pub_base INTERFACE
    $<$<BOOL:${ENABLE_GCOV}>:-lgcov>
    -lpthread
)

############ intf_pub c++11 ############
add_library(intf_pub_cxx11 INTERFACE)
target_compile_options(intf_pub_cxx11 INTERFACE
    $<$<COMPILE_LANGUAGE:CXX>:-std=c++11>
)
target_link_libraries(intf_pub_cxx11 INTERFACE
    $<BUILD_INTERFACE:intf_pub_base>
)

############ intf_pub c++17 ############
add_library(intf_pub_cxx17 INTERFACE)
target_compile_options(intf_pub_cxx17 INTERFACE
    $<$<COMPILE_LANGUAGE:CXX>:-std=c++17>
)
target_link_libraries(intf_pub_cxx17 INTERFACE
    $<BUILD_INTERFACE:intf_pub_base>
)

############ intf_pub c++17 unasan ############
add_library(intf_pub_cxx17_unasan INTERFACE)
target_compile_options(intf_pub_cxx17_unasan INTERFACE
    -Wall
    -fPIC
    -pipe
    -Wextra
    -Wfloat-equal
    -fno-common
    -fstack-protector-strong
    -D_GLIBCXX_USE_CXX11_ABI=0
    $<$<COMPILE_LANGUAGE:CXX>:-std=c++17>
)
target_link_options(intf_pub_cxx17_unasan INTERFACE
    -Wl,-z,relro
    -Wl,-z,now
    -Wl,-z,noexecstack
    -Wl,-Bsymbolic
    $<$<CONFIG:Release>:-s>
    $<$<CONFIG:Release>:-Wl,--build-id=none>
    $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:-pie>
)
target_link_directories(intf_pub_cxx17_unasan INTERFACE)
target_link_libraries(intf_pub_cxx17_unasan INTERFACE
  -lpthread
)