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

# device 侧联编场景守卫（编译/链接接口层）：device 侧以各子目录（msprofbin/acp 等）为入口
# 联编，既不经过顶层 CMakeLists.txt，也不经过 dvvp/CMakeLists.txt（即不执行
# cmake/intf_pub.cmake 与 cann-cmake intf_pub 模块），导致 intf_pub_base / intf_pub /
# oam_intf_pub 缺失，后续 target_link_libraries 引用它们时报"目标未定义"。本文件在目标
# 缺失时按其原始定义补齐（复现 cann-cmake intf_pub/intf_pub_linux.cmake 与
# cmake/intf_pub.cmake），非空壳；顶层入口已创建时 if(NOT TARGET) 保证不重复定义。
include_guard(GLOBAL)

# intf_pub_base —— 复现 cann-cmake intf_pub/intf_pub_linux.cmake（oam_intf_pub 的底层依赖）
if(NOT TARGET intf_pub_base)
    add_library(intf_pub_base INTERFACE)
    target_compile_options(intf_pub_base INTERFACE
        -fPIC
        -pipe
        -Wall
        -Wextra
        -Wfloat-equal
        -fno-common
        -fstack-protector-strong
        $<$<BOOL:${ENABLE_ASAN}>:-fsanitize=address -fsanitize=leak -fsanitize-recover=address,all -fno-stack-protector -fno-omit-frame-pointer -g>
        $<$<BOOL:${ENABLE_TSAN}>:-fsanitize=thread -fsanitize-recover=thread,all -g>
        $<$<BOOL:${ENABLE_UBSAN}>:-fsanitize=undefined -fno-sanitize=alignment -g>
        $<$<BOOL:${ENABLE_GCOV}>:-fprofile-arcs -ftest-coverage>
    )
    unset(CXX11_ABI_VALUE)
    if(DEFINED USE_CXX11_ABI)
        if(USE_CXX11_ABI)
            set(CXX11_ABI_VALUE 1)
        else()
            set(CXX11_ABI_VALUE 0)
        endif()
    elseif(NOT PRODUCT_SIDE STREQUAL "device")
        set(CXX11_ABI_VALUE 0)
    endif()
    if(DEFINED CXX11_ABI_VALUE)
        target_compile_definitions(intf_pub_base INTERFACE
            $<$<COMPILE_LANGUAGE:CXX>:_GLIBCXX_USE_CXX11_ABI=${CXX11_ABI_VALUE}>
        )
    endif()
    target_compile_definitions(intf_pub_base INTERFACE
        $<$<CONFIG:Release>:CFG_BUILD_NDEBUG>
        $<$<CONFIG:Debug>:CFG_BUILD_DEBUG>
        $<$<CONFIG:Release>:NDEBUG>
        LINUX=0
    )
    target_link_options(intf_pub_base INTERFACE
        -Wl,-z,relro
        -Wl,-z,now
        -Wl,-z,noexecstack
        $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:-pie>
        $<$<CONFIG:Release>:-Wl,--build-id=none>
        $<$<CONFIG:Release>:-s>
        $<$<BOOL:${ENABLE_ASAN}>:-fsanitize=address -fsanitize=leak -fsanitize-recover=address>
        $<$<BOOL:${ENABLE_TSAN}>:-fsanitize=thread>
        $<$<BOOL:${ENABLE_UBSAN}>:-fsanitize=undefined>
        $<$<BOOL:${ENABLE_GCOV}>:-fprofile-arcs -ftest-coverage>
    )
    target_link_libraries(intf_pub_base INTERFACE
        -pthread
        $<$<BOOL:${ENABLE_GCOV}>:-lgcov>
    )
endif()

# intf_pub —— 复现 cann-cmake intf_pub/intf_pub_linux.cmake（C++17）
if(NOT TARGET intf_pub)
    add_library(intf_pub INTERFACE)
    target_link_libraries(intf_pub INTERFACE
        intf_pub_base
    )
    target_compile_options(intf_pub INTERFACE
        $<$<COMPILE_LANGUAGE:CXX>:-std=c++17>
    )
endif()

# oam_intf_pub —— 复现 cmake/intf_pub.cmake
if(NOT TARGET oam_intf_pub)
    add_library(oam_intf_pub INTERFACE)
    target_link_libraries(oam_intf_pub INTERFACE
        $<BUILD_INTERFACE:intf_pub>
    )
    target_compile_options(oam_intf_pub INTERFACE
        $<$<CONFIG:Release>:-O2>
    )
    target_compile_definitions(oam_intf_pub INTERFACE
        $<$<CONFIG:Release>:_FORTIFY_SOURCE=2>
    )
endif()
