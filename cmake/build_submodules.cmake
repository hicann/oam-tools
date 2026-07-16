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

find_package(Git QUIET)
if (NOT GIT_EXECUTABLE)
    find_program(GIT_EXECUTABLE git)
    if(NOT GIT_EXECUTABLE)
        message(FATAL_ERROR "git not found - required for submodule population")
    endif()
endif()

find_package(Python3 COMPONENTS Interpreter QUIET)
if(NOT Python3_EXECUTABLE)
    find_program(Python3_EXECUTABLE python3)
    if(NOT Python3_EXECUTABLE)
        message(FATAL_ERROR "python3 not found - required for msprof wheel build")
    endif()
endif()

function(oam_populate_submodule NAME GIT_URL RESULT_VAR)
    set(_dest "${OAM_TOOLS_DIR}/submodule/${NAME}")
    # 仅当目录存在且非空时才视为已就绪；空目录（上一轮取源失败留下的残壳）
    # 需重新取源，否则会带着空 submodule 继续、把"取源失败"推迟成更难定位的构建报错。
    if(EXISTS "${_dest}" AND IS_DIRECTORY "${_dest}")
        file(GLOB _dest_entries "${_dest}/*")
        if(_dest_entries)
            message(STATUS "${NAME} submodule already present at ${_dest}")
            set(${RESULT_VAR} "${_dest}" PARENT_SCOPE)
            return()
        endif()
        message(STATUS "${NAME} submodule dir empty, re-populating")
    endif()

    file(MAKE_DIRECTORY "${OAM_TOOLS_DIR}/submodule")

    if(DEFINED CANN_3RD_LIB_PATH AND EXISTS "${CANN_3RD_LIB_PATH}/${NAME}"
        AND IS_DIRECTORY "${CANN_3RD_LIB_PATH}/${NAME}")
        message(STATUS "${NAME} using third_party")
        # copy_directory 失败也要拦截：源目录残缺/权限不足时若不检查返回值，
        # 会得到不完整的 submodule，后续 wheel 构建或 msaccucmp 同步才报错、难定位。
        execute_process(COMMAND ${CMAKE_COMMAND} -E copy_directory
            "${CANN_3RD_LIB_PATH}/${NAME}" "${OAM_TOOLS_DIR}/submodule/${NAME}"
            RESULT_VARIABLE _copy_result)
        if(NOT _copy_result EQUAL 0)
            message(FATAL_ERROR
                "copy ${NAME} from ${CANN_3RD_LIB_PATH} failed (${_copy_result})")
        endif()
    else()
        message(STATUS "${NAME} download via git clone")
        execute_process(
            COMMAND ${GIT_EXECUTABLE} clone --depth 1 "${GIT_URL}" "${NAME}"
            WORKING_DIRECTORY "${OAM_TOOLS_DIR}/submodule"
            RESULT_VARIABLE _clone_result
            OUTPUT_VARIABLE _clone_output
            ERROR_VARIABLE _clone_error
        )
        if(NOT _clone_result EQUAL 0)
            message(FATAL_ERROR
                "git clone ${NAME} failed (${_clone_result}):\n${_clone_error}")
        endif()
    endif()

    set(${RESULT_VAR} "${_dest}" PARENT_SCOPE)
endfunction()

# --- build msprof analysis：构建 wheel 并同步到 msprofbin 源码目录 ---
# 优先用兄弟目录 mindstudio/msprof，否则填充 submodule/msprof。
function(oam_build_msprof_analysis)
    if(EXISTS "${OAM_TOOLS_DIR}/../../mindstudio/msprof")
        message(STATUS "msprof using mindstudio")
        set(_msprof_build_path "${OAM_TOOLS_DIR}/../../mindstudio/msprof")
    else()
        oam_populate_submodule("msprof" "https://gitcode.com/Ascend/msprof.git"
            _msprof_build_path)
    endif()

    execute_process(
        COMMAND ${Python3_EXECUTABLE} "${_msprof_build_path}/build/setup.py"
                bdist_wheel --python-tag=py3 --py-limited-api=cp37
        WORKING_DIRECTORY "${_msprof_build_path}"
        RESULT_VARIABLE _msprof_rc
    )
    if(NOT _msprof_rc EQUAL 0)
        message(FATAL_ERROR "build msprof wheel failed (rc=${_msprof_rc})")
    endif()

    set(_msprof_whl_dst "${OAM_TOOLS_DIR}/src/msprof/collector/dvvp/msprofbin")
    set(_msprof_whl_src "${_msprof_build_path}/dist/msprof-0.0.1-py3-none-any.whl")
    # bdist_wheel 即使 rc=0 也可能因产物名变化而拿不到期望的 whl；file(COPY) 对不存在的
    # 源会静默跳过，导致后续 msprofbin 打包缺 whl。显式校验后再拷。
    if(NOT EXISTS "${_msprof_whl_src}")
        message(FATAL_ERROR "msprof wheel not found after build: ${_msprof_whl_src}")
    endif()
    # 先删后拷：旧 whl 可能是只读（源自只读 third_party 或上一轮规范化），直接覆盖会失败。
    file(REMOVE "${_msprof_whl_dst}/msprof-0.0.1-py3-none-any.whl")
    file(COPY "${_msprof_whl_src}"
        DESTINATION "${_msprof_whl_dst}"
        FILE_PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ
    )
endfunction()

# --- build adump analysis：同步 msaccucmp 到 operator_cmp/msaccucmp/compare ---
# 优先用兄弟目录 mindstudio/msaccucmp，否则填充 submodule/msprobe。
function(oam_build_msaccucmp_analysis)
    if(EXISTS "${OAM_TOOLS_DIR}/../../mindstudio/msaccucmp")
        message(STATUS "msprobe using mindstudio")
        set(_msaccucmp_src
            "${OAM_TOOLS_DIR}/../../mindstudio/msaccucmp/python/msprobe/msaccucmp")
    else()
        oam_populate_submodule("msprobe" "https://gitcode.com/Ascend/msprobe.git"
            _msprobe_dir)
        set(_msaccucmp_src "${_msprobe_dir}/python/msprobe/msaccucmp")
    endif()

    set(_compare_dst "${OAM_TOOLS_DIR}/src/operator_cmp/msaccucmp/compare")
    # file(COPY) 对不存在的源目录会静默跳过，导致 compare/ 变成空目录、operator_cmp
    # 打包内容缺失。显式校验源目录存在再拷。
    if(NOT IS_DIRECTORY "${_msaccucmp_src}")
        message(FATAL_ERROR "msaccucmp source dir not found: ${_msaccucmp_src}")
    endif()
    # 先删后拷 + 规范权限：消除只读源带来的只读产物，保证重复构建可覆盖。
    file(REMOVE_RECURSE "${_compare_dst}")
    file(MAKE_DIRECTORY "${_compare_dst}")
    file(COPY "${_msaccucmp_src}/"
        DESTINATION "${_compare_dst}"
        FILE_PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ
        DIRECTORY_PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE
                              GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
    )
endfunction()

oam_build_msprof_analysis()
oam_build_msaccucmp_analysis()