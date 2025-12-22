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

# function(create_opensource target_name suffix_name product_side install_prefix toolchain_file)

set(open_source_target_name mockcpp)

set(mockcpp_SRC_DIR ${ASCEND_3RD_LIB_PATH}/mockcpp_src)

if (CMAKE_HOST_SYSTEM_PROCESSOR  STREQUAL "aarch64")
    set(mockcpp_CXXFLAGS "-fPIC")
else()
    set(mockcpp_CXXFLAGS "-fPIC -std=c++11")
endif()
set(mockcpp_FLAGS "-fPIC")
set(mockcpp_LINKER_FLAGS "")

if ((NOT DEFINED ABI_ZERO) OR (ABI_ZERO STREQUAL ""))
    set(ABI_ZERO "true")
endif()


if (ABI_ZERO STREQUAL true)
    set(mockcpp_CXXFLAGS "${mockcpp_CXXFLAGS} -D_GLIBCXX_USE_CXX11_ABI=0")
    set(mockcpp_FLAGS "${mockcpp_FLAGS} -D_GLIBCXX_USE_CXX11_ABI=0")
endif()

set(BUILD_WRAPPER ${ASCENDC_TOOLS_ROOT_DIR}/test/cmake/tools/build_ext.sh) # TODO 这个tool在这里是否合适
set(BUILD_TYPE "DEBUG")

if (CMAKE_GENERATOR MATCHES "Unix Makefiles")
    set(IS_MAKE True)
    set(MAKE_CMD "$(MAKE)")
else()
    set(IS_MAKE False)
endif()

#依赖蓝区二进制仓mockcpp
set(BOOST_INCLUDE_DIRS ${mockcpp_SRC_DIR}/../boost)
message(STATUS "cmake install prefix ${CMAKE_INSTALL_PREFIX} mockcpp_SRC_DIR is ${mockcpp_SRC_DIR}")
if (NOT EXISTS "${ASCEND_3RD_LIB_PATH}/mockcpp/lib/libmockcpp.a" OR TRUE)
    set(PATCH_FILE ${mockcpp_SRC_DIR}/../mockcpp-2.7.patch)
    if (NOT EXISTS ${PATCH_FILE})
        message(STATUS, "download mockcpp")
        file(DOWNLOAD
            "https://gitcode.com/cann-src-third-party/mockcpp/releases/download/v2.7-h2/mockcpp-2.7_py3.patch"
            ${PATCH_FILE}
            TIMEOUT 60
        )
    endif()
    include(ExternalProject)
    message(STATUS "third_party_TEM_DIR is ${ASCEND_3RD_LIB_PATH} mockcpp_SRC_DIR is ${CMAKE_COMMAND}")
    ExternalProject_Add(mockcpp
        URL "https://gitcode.com/cann-src-third-party/mockcpp/releases/download/v2.7-h2/mockcpp-2.7.tar.gz"
        DOWNLOAD_DIR ${ASCEND_3RD_LIB_PATH}
        SOURCE_DIR ${mockcpp_SRC_DIR}
        TLS_VERIFY OFF
        PATCH_COMMAND git init && git apply ${PATCH_FILE}

        CONFIGURE_COMMAND ${CMAKE_COMMAND} -G ${CMAKE_GENERATOR}
            -DCMAKE_CXX_FLAGS=${mockcpp_CXXFLAGS}
            -DCMAKE_C_FLAGS=${mockcpp_FLAGS}
            -DBOOST_INCLUDE_DIRS=${BOOST_INCLUDE_DIRS}
            -DCMAKE_SHARED_LINKER_FLAGS=${mockcpp_LINKER_FLAGS}
            -DCMAKE_EXE_LINKER_FLAGS=${mockcpp_LINKER_FLAGS}
            -DBUILD_32_BIT_TARGET_BY_64_BIT_COMPILER=OFF
            -DCMAKE_INSTALL_PREFIX=${ASCEND_3RD_LIB_PATH}/mockcpp
            <SOURCE_DIR>
        BUILD_COMMAND ${${BUILD_TYPE}} $<$<BOOL:${IS_MAKE}>:$(MAKE)>
    )
    message(STATUS, "get mockcpp")
endif()