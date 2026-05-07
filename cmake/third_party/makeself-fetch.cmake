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

set(MAKESELF_NAME "makeself")
set(MAKESELF_PATH ${CANN_3RD_LIB_PATH}/makeself)

if(POLICY CMP0135)
    cmake_policy(SET CMP0135 NEW)
endif()

# 默认配置的makeself还是不存在则下载
if (NOT EXISTS "${MAKESELF_PATH}/makeself-header.sh" OR NOT EXISTS "${MAKESELF_PATH}/makeself.sh")
    set(MAKESELF_URL "https://gitcode.com/cann-src-third-party/makeself/releases/download/release-2.5.0-patch1.0/makeself-release-2.5.0-patch1.tar.gz")
    message(STATUS "Downloading ${MAKESELF_NAME} from ${MAKESELF_URL}")

    include(FetchContent)
    FetchContent_Declare(
        ${MAKESELF_NAME}
        URL ${MAKESELF_URL}
        URL_HASH SHA256=bfa730a5763cdb267904a130e02b2e48e464986909c0733ff1c96495f620369a
        DOWNLOAD_DIR ${CANN_3RD_PKG_PATH}
        SOURCE_DIR "${MAKESELF_PATH}"  # 直接解压到此目录
    )
    FetchContent_MakeAvailable(${MAKESELF_NAME})
    execute_process(
        COMMAND chmod 700 "${CMAKE_BINARY_DIR}/makeself/makeself.sh"
        COMMAND chmod 700 "${CMAKE_BINARY_DIR}/makeself/makeself-header.sh"
        -E env
        CMAKE_TLS_VERIFY=0
        RESULT_VARIABLE CHMOD_RESULT
        ERROR_VARIABLE CHMOD_ERROR
    )
endif()