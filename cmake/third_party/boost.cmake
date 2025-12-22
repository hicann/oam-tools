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

set(BOOST_NAME "boost")
set(BOOST_PATH ${ASCEND_3RD_LIB_PATH}/boost)

# 默认配置的boost不存在则下载
if (NOT EXISTS "${BOOST_PATH}/boost/config.hpp")
    set(BOOST_URL "https://gitcode.com/cann-src-third-party/boost/releases/download/v1.87.0/boost_1_87_0.tar.gz")
    message(STATUS "Downloading ${BOOST_NAME} from ${BOOST_URL}")

    include(FetchContent)
    FetchContent_Declare(
        ${BOOST_NAME}
        URL ${BOOST_URL}
        URL_HASH SHA256=f55c340aa49763b1925ccf02b2e83f35fdcf634c9d5164a2acb87540173c741d
        DOWNLOAD_DIR ${third_party_TEM_DIR}
        SOURCE_DIR "${BOOST_PATH}"  # 直接解压到此目录
        TLS_VERIFY OFF
    )
    FetchContent_MakeAvailable(${BOOST_NAME})
endif()