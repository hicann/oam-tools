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
# makeself.cmake - 自定义 makeself 打包脚本

# 设置 makeself 路径
set(MAKESELF_EXE ${CPACK_MAKESELF_PATH}/makeself.sh)
set(MAKESELF_HEADER_EXE ${CPACK_MAKESELF_PATH}/makeself-header.sh)
if(NOT MAKESELF_EXE)
    message(FATAL_ERROR "makeself not found!")
endif()

execute_process(COMMAND bash ${MAKESELF_EXE}
                        --header ${MAKESELF_HEADER_EXE}
                        --help-header ./help.info
                        --gzip --complevel 4 --nomd5 --sha256
                        ./ ${CPACK_PACKAGE_FILE_NAME} "version:1.0" ./install.sh
                WORKING_DIRECTORY ${CPACK_TEMPORARY_DIRECTORY}
                RESULT_VARIABLE EXEC_RESULT
                ERROR_VARIABLE  EXEC_ERROR
)

if (NOT "${EXEC_RESULT}x" STREQUAL "0x")
    message(FATAL_ERROR "CPack Command error: ${EXEC_RESULT}\n${EXEC_ERROR}")
endif()

execute_process(COMMAND cp ${CPACK_EXTERNAL_BUILT_PACKAGES} ${CPACK_PACKAGE_DIRECTORY}/
    COMMAND echo "Copy ${CPACK_EXTERNAL_BUILT_PACKAGES} to ${CPACK_PACKAGE_DIRECTORY}/"
    WORKING_DIRECTORY ${CPACK_TEMPORARY_DIRECTORY}
)

if (NOT "${CPACK_PACKAGE_DIRECTORY}x" STREQUAL "${CPACK_INSTALL_PREFIX}x")
    execute_process(
        COMMAND ${CMAKE_COMMAND} -E make_directory ${CPACK_INSTALL_PREFIX}
        WORKING_DIRECTORY ${CPACK_TEMPORARY_DIRECTORY}
    )

    execute_process(
        COMMAND cp ${CPACK_EXTERNAL_BUILT_PACKAGES} ${CPACK_INSTALL_PREFIX}/
        COMMAND echo "Copy ${CPACK_EXTERNAL_BUILT_PACKAGES} to ${CPACK_INSTALL_PREFIX}/"
        WORKING_DIRECTORY ${CPACK_TEMPORARY_DIRECTORY}
    )
endif()
