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
    message(FATAL_ERROR "makeself not found! Install it with: sudo apt install makeself")
endif()

# 创建临时安装目录
set(STAGING_DIR "${CPACK_CMAKE_BINARY_DIR}/_CPack_Packages/makeself_staging")
file(MAKE_DIRECTORY "${STAGING_DIR}")

# 上一次 cpack 末尾会把 staging 目录权限收紧到 550 等，这里先恢复 owner 写权限，
# 否则二次构建时 cmake --install 写入会因目录无写位而 Permission denied。
if(EXISTS "${STAGING_DIR}")
    execute_process(COMMAND chmod -R u+w "${STAGING_DIR}")
endif()

# 执行安装到临时目录
execute_process(
    COMMAND "${CMAKE_COMMAND}" --install "${CPACK_CMAKE_BINARY_DIR}" --prefix "${STAGING_DIR}"
    RESULT_VARIABLE INSTALL_RESULT
)

if(NOT INSTALL_RESULT EQUAL 0)
    message(FATAL_ERROR "Installation to staging directory failed: ${INSTALL_RESULT}")
endif()

# 生成安装配置文件
set(CSV_OUTPUT ${CPACK_CMAKE_BINARY_DIR}/filelist.csv)
execute_process(
    COMMAND python3 ${CPACK_CMAKE_SOURCE_DIR}/scripts/package/package.py --pkg_name oam_tools --os_arch linux-${CPACK_ARCH}
    WORKING_DIRECTORY ${CPACK_CMAKE_BINARY_DIR}
    OUTPUT_VARIABLE result
    ERROR_VARIABLE error
    RESULT_VARIABLE code
    OUTPUT_STRIP_TRAILING_WHITESPACE
)
message(STATUS "package.py result: ${code}")
if (NOT code EQUAL 0)
    message(FATAL_ERROR "Filelist generation failed: ${result}")
else ()
    message(STATUS "Filelist generated successfully: ${result}")

    if (NOT EXISTS ${CSV_OUTPUT})
        message(FATAL_ERROR "Output file not created: ${CSV_OUTPUT}")
    endif ()
endif ()
set(SCENE_OUT_PUT
    ${CPACK_CMAKE_BINARY_DIR}/scene.info
)
set(OAM_VERSION_OUT_PUT
    ${CPACK_CMAKE_BINARY_DIR}/oam_tools_version.h
)

configure_file(
    ${SCENE_OUT_PUT}
    ${STAGING_DIR}/share/info/oam_tools/
    COPYONLY
)
configure_file(
    ${CSV_OUTPUT}
    ${STAGING_DIR}/share/info/oam_tools/script/
    COPYONLY
)
configure_file(
    ${OAM_VERSION_OUT_PUT}
    ${STAGING_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/include/version/oam_tools_version.h
    COPYONLY
)

 # 统一设置安装的文件权限为550
execute_process(
    COMMAND find ${STAGING_DIR} -type f -exec chmod 550 {} \;
    RESULT_VARIABLE CHMOD_RESULT
)

# 统一设置安装的目录权限为550（避免构建环境 umask 透传，--extract 后目录权限不规范）
execute_process(
    COMMAND find ${STAGING_DIR} -type d -exec chmod 550 {} \;
    RESULT_VARIABLE CHMOD_DIR_RESULT
)

# 文件权限特殊处理
if(EXISTS "${STAGING_DIR}/opp/built-in/op_impl/ai_core/tbe/config")
    execute_process(
        COMMAND chmod -R 555 "${STAGING_DIR}/opp/built-in/op_impl/ai_core/tbe/config";
    )
endif()

if (EXISTS "${STAGING_DIR}/opp/built-in/op_impl/ai_core/tbe/kernel") 
    execute_process(
        COMMAND chmod -R 555 "${STAGING_DIR}/opp/built-in/op_impl/ai_core/tbe/kernel";
    )
endif()

if (EXISTS "${STAGING_DIR}/opp/built-in/op_impl/ai_core/tbe/impl/ops_oam") 
    execute_process(
        COMMAND chmod -R 555 "${STAGING_DIR}/opp/built-in/op_impl/ai_core/tbe/impl/ops_oam";
    )
endif()

if (EXISTS "${STAGING_DIR}/opp/built-in/op_impl/ai_core/tbe/op_host/lib/linux/${CMAKE_SYSTEM_PROCESSOR}/libophost_oam.so") 
    execute_process(
        COMMAND chmod 555 "${STAGING_DIR}/opp/built-in/op_impl/ai_core/tbe/op_host/lib/linux/${CMAKE_SYSTEM_PROCESSOR}/libophost_oam.so";
    )
endif()

if (EXISTS "${STAGING_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/lib64/libopapi_oam.so") 
    execute_process(
        COMMAND chmod 555 "${STAGING_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/lib64/libopapi_oam.so";
    )
endif()

if (EXISTS "${STAGING_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/include/aclnnop") 
    execute_process(
        COMMAND chmod -R 555 "${STAGING_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/include/aclnnop";
    )
endif()

# 设置tools/aml/lib64文件权限为440
execute_process(
    COMMAND find ${STAGING_DIR}/tools/aml/lib64 -type f -exec chmod 440 {} \;
    RESULT_VARIABLE CHMOD_RESULT
)

foreach(aml_so
    "libascend_dump_parser.so"
    "libascend_ml_detect.so"
    "libascend_ml.so"
)
    if(EXISTS "${STAGING_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/lib64/${aml_so}")
        execute_process(COMMAND chmod 440 "${STAGING_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/lib64/${aml_so}")
    endif()
endforeach()

if(EXISTS "${STAGING_DIR}/tools/profiler/profiler_tool")
    execute_process(COMMAND chmod -R 555 "${STAGING_DIR}/tools/profiler/profiler_tool")
endif()

if(EXISTS "${STAGING_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/include/version/oam_tools_version.h")
    execute_process(COMMAND chmod 440 "${STAGING_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/include/version/oam_tools_version.h")
endif()

if(EXISTS "${STAGING_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/conf/path.cfg")
    execute_process(COMMAND chmod 440 "${STAGING_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/conf/path.cfg")
endif()

# share/ 和 share/info install 给 750（owner 可写）；上面 find -type d 一刀切到 550 需改回。
# 注意：share/info/oam_tools 在 install 时实际为 550（filelist 标 750 但被后续 chmod 改回），保持 550。
foreach(_d "share" "share/info")
    if(EXISTS "${STAGING_DIR}/${_d}")
        execute_process(COMMAND chmod 750 "${STAGING_DIR}/${_d}")
    endif()
endforeach()

# scene.info / version.info install 给 440；上面 find -type f 一刀切到 550 需改回。
foreach(_f "share/info/oam_tools/scene.info" "share/info/oam_tools/version.info")
    if(EXISTS "${STAGING_DIR}/${_f}")
        execute_process(COMMAND chmod 440 "${STAGING_DIR}/${_f}")
    endif()
endforeach()

# end 文件权限特殊处理

# SDK 头文件目录 install 给 555。
if(EXISTS "${STAGING_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/include/aclnnop/level2")
    execute_process(COMMAND chmod 555 "${STAGING_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/include/aclnnop/level2")
endif()

# makeself打包
file(STRINGS ${CPACK_CMAKE_BINARY_DIR}/makeself.txt script_output)
string(REPLACE " " ";" makeself_param_string "${script_output}")
string(REGEX MATCH "cann.*\\.run" package_name "${makeself_param_string}")

list(LENGTH makeself_param_string LIST_LENGTH)
math(EXPR INSERT_INDEX "${LIST_LENGTH} - 2")
list(INSERT makeself_param_string ${INSERT_INDEX} "${STAGING_DIR}")

message(STATUS "script output: ${script_output}")
message(STATUS "makeself: ${makeself_param_string}")
message(STATUS "package: ${package_name}")

# 上面 find -type d 把 STAGING_DIR 本身也置为 550，这里临时恢复其 owner 写位，
# 否则 makeself 无法在该目录中创建 .run 输出文件（STAGING_DIR 自身不进归档）。
execute_process(COMMAND chmod u+w "${STAGING_DIR}")

execute_process(COMMAND bash ${MAKESELF_EXE}
        --header ${MAKESELF_HEADER_EXE}
        --help-header share/info/oam_tools/script/help.info
        ${makeself_param_string} share/info/oam_tools/script/install.sh
        WORKING_DIRECTORY ${STAGING_DIR}
        RESULT_VARIABLE EXEC_RESULT
        ERROR_VARIABLE  EXEC_ERROR
)

if(NOT EXEC_RESULT EQUAL 0)
    message(FATAL_ERROR "makeself packaging failed: ${EXEC_ERROR}")
endif()

execute_process(
    COMMAND mkdir -p ${CPACK_PACKAGE_DIRECTORY}
    COMMAND mv ${STAGING_DIR}/${package_name} ${CPACK_PACKAGE_DIRECTORY}/
    COMMAND echo "Move ${STAGING_DIR}/${package_name} to ${CPACK_PACKAGE_DIRECTORY}/"
    WORKING_DIRECTORY ${STAGING_DIR}
)
