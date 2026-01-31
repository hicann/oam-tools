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

if(POLICY CMP0135)
    cmake_policy(SET CMP0135 NEW)
endif()

include(ExternalProject)
include(GNUInstallDirs)

set(PROTOBUF_SRC_DIR ${CMAKE_BINARY_DIR}/protobuf-src)
set(PROTOBUF_DL_DIR ${CMAKE_BINARY_DIR}/downloads)
set(TOP_DIR ${CMAKE_CURRENT_SOURCE_DIR})
set(SOURCE_DIR ${PROTOBUF_SRC_DIR})

set(PROTOBUF_HOST_STATIC_PKG_DIR ${CMAKE_BINARY_DIR}/protobuf_host_static)
set(SECURITY_COMPILE_OPT "-Wl,-z,relro,-z,now,-z,noexecstack -s -Wl,-Bsymbolic")

set(HOST_PROTOBUF_CXXFLAGS "${SECURITY_COMPILE_OPT} -Wno-maybe-uninitialized -Wno-unused-parameter -fPIC -fstack-protector-all -D_FORTIFY_SOURCE=2 -D_GLIBCXX_USE_CXX11_ABI=0 -O2 -Dgoogle=ascend_private")
include(${CMAKE_CURRENT_LIST_DIR}/protobuf_sym_rename.cmake)
set(HOST_PROTOBUF_CXXFLAGS "${HOST_PROTOBUF_CXXFLAGS} ${PROTOBUF_SYM_RENAME}")

if (NOT EXISTS "${CANN_3RD_LIB_PATH}/protobuf/protobuf-all-25.1.tar.gz" OR NOT EXISTS "${CANN_3RD_LIB_PATH}/abseil-cpp/abseil-cpp-20230802.1.tar.gz")
    set(REQ_URL "https://gitcode.com/cann-src-third-party/protobuf/releases/download/v25.1/protobuf-25.1.tar.gz")
    set(ABS_REQ_URL "https://gitcode.com/cann-src-third-party/abseil-cpp/releases/download/20230802.1/abseil-cpp-20230802.1.tar.gz")
    ExternalProject_Add(protobuf_src_dl
      URL               ${REQ_URL}
      DOWNLOAD_DIR      ${PROTOBUF_DL_DIR}
      DOWNLOAD_NO_EXTRACT 1
      CONFIGURE_COMMAND ""
      BUILD_COMMAND ""
      INSTALL_COMMAND ""
    )
    ExternalProject_Add(abseil_src_dl
      URL               ${ABS_REQ_URL}
      DOWNLOAD_DIR      ${PROTOBUF_DL_DIR}/abseil-cpp
      DOWNLOAD_NO_EXTRACT 1
      CONFIGURE_COMMAND ""
      BUILD_COMMAND ""
      INSTALL_COMMAND ""
    )
    # 下载/解压 protobuf 源码
    ExternalProject_Add(protobuf_src
      DOWNLOAD_COMMAND ""
      COMMAND tar -zxf ${PROTOBUF_DL_DIR}/protobuf-25.1.tar.gz --strip-components 1 -C ${SOURCE_DIR}
      COMMAND tar -zxf ${PROTOBUF_DL_DIR}/abseil-cpp/abseil-cpp-20230802.1.tar.gz --strip-components 1 -C ${SOURCE_DIR}/third_party/abseil-cpp
      PATCH_COMMAND cd ${SOURCE_DIR} && patch -p1 < ${TOP_DIR}/cmake/protobuf_25.1_change_version.patch && cd ${SOURCE_DIR}/third_party/abseil-cpp && patch -p1 < ${TOP_DIR}/cmake/protobuf-hide_absl_symbols.patch
      CONFIGURE_COMMAND ""
      BUILD_COMMAND ""
      INSTALL_COMMAND ""
    )
    add_dependencies(protobuf_src protobuf_src_dl abseil_src_dl)
else()
  set(OPEN_SOURCE_DIR ${TOP_DIR}/../../open_source)
  ExternalProject_Add(protobuf_src
      DOWNLOAD_COMMAND ""
      COMMAND tar -zxf ${OPEN_SOURCE_DIR}/protobuf/protobuf-all-25.1.tar.gz --strip-components 1 -C ${SOURCE_DIR}
      COMMAND tar -zxf ${OPEN_SOURCE_DIR}/abseil-cpp/abseil-cpp-20230802.1.tar.gz --strip-components 1 -C ${SOURCE_DIR}/third_party/abseil-cpp
      PATCH_COMMAND cd ${SOURCE_DIR} && patch -p1 < ${TOP_DIR}/cmake/protobuf_25.1_change_version.patch && cd ${SOURCE_DIR}/third_party/abseil-cpp && patch -p1 < ${TOP_DIR}/cmake/protobuf-hide_absl_symbols.patch
      CONFIGURE_COMMAND ""
      BUILD_COMMAND ""
      INSTALL_COMMAND ""
  )
endif()

ExternalProject_Add(protobuf_host_static_build
    DEPENDS protobuf_src
    SOURCE_DIR ${PROTOBUF_SRC_DIR}
    DOWNLOAD_COMMAND ""
    UPDATE_COMMAND ""
    CONFIGURE_COMMAND ${CMAKE_COMMAND}
        -G ${CMAKE_GENERATOR}
        -DCMAKE_C_COMPILER=${CMAKE_C_COMPILER}
        -DCMAKE_CXX_COMPILER=${CMAKE_CXX_COMPILER}
        -DCMAKE_INSTALL_LIBDIR=lib
        -DBUILD_SHARED_LIBS=OFF
        -Dprotobuf_WITH_ZLIB=OFF
        -DLIB_PREFIX=ascend_
        -DCMAKE_SKIP_RPATH=TRUE
        -Dprotobuf_BUILD_TESTS=OFF
        -DCMAKE_C_COMPILER_LAUNCHER=${CCACHE_PROGRAM}
        -DCMAKE_CXX_COMPILER_LAUNCHER=${CCACHE_PROGRAM}
        -DCMAKE_CXX_FLAGS=${HOST_PROTOBUF_CXXFLAGS}
        -DCMAKE_INSTALL_PREFIX=${PROTOBUF_HOST_STATIC_PKG_DIR}
        -Dprotobuf_BUILD_PROTOC_BINARIES=OFF
        -DABSL_COMPILE_OBJ=TRUE
        <SOURCE_DIR>
    BUILD_COMMAND $(MAKE)
    INSTALL_COMMAND $(MAKE) install
    EXCLUDE_FROM_ALL TRUE
)

set(PROTOBUF_HOST_DIR ${CMAKE_BINARY_DIR}/protobuf_host)
message("PROTOBUF_HOST_DIR : ${PROTOBUF_HOST_DIR}")
ExternalProject_Add(protobuf_host_build
    DEPENDS protobuf_src
    SOURCE_DIR ${PROTOBUF_SRC_DIR}
    DOWNLOAD_COMMAND ""
    UPDATE_COMMAND ""
    CONFIGURE_COMMAND ${CMAKE_COMMAND}
        -DCMAKE_INSTALL_PREFIX=${PROTOBUF_HOST_DIR}
        -Dprotobuf_BUILD_TESTS=OFF
        -DCMAKE_C_COMPILER_LAUNCHER=${CCACHE_PROGRAM}
        -DCMAKE_CXX_COMPILER_LAUNCHER=${CCACHE_PROGRAM}
        -Dprotobuf_WITH_ZLIB=OFF
        <SOURCE_DIR>
    BUILD_COMMAND $(MAKE)
    INSTALL_COMMAND $(MAKE) install
    EXCLUDE_FROM_ALL TRUE
)

add_executable(host_protoc IMPORTED)
set_target_properties(host_protoc PROPERTIES
    IMPORTED_LOCATION ${PROTOBUF_HOST_DIR}/bin/protoc
)
add_dependencies(host_protoc protobuf_host_build)

add_library(ascend_protobuf_static_lib STATIC IMPORTED)
set_target_properties(ascend_protobuf_static_lib PROPERTIES
    IMPORTED_LOCATION ${PROTOBUF_HOST_STATIC_PKG_DIR}/lib/libascend_protobuf.a
)

add_library(ascend_protobuf_static INTERFACE)
target_include_directories(ascend_protobuf_static INTERFACE ${PROTOBUF_HOST_STATIC_PKG_DIR}/include)
target_link_libraries(ascend_protobuf_static INTERFACE ascend_protobuf_static_lib)
add_dependencies(ascend_protobuf_static protobuf_host_static_build)