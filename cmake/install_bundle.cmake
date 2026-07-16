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

# 闭源包(bundle)拉取与解压：原 install_bundle.sh 的 CMake 版本。
# 按 架构 + 分支 拼出 OBS 地址，下载后解压到 ${OAM_TOOLS_DIR}/bundle。
# 分支固定 master —— 功能分支没有对应的已发布包。
set(OAM_BUNDLE_BRANCH "master")
set(OAM_BUNDLE_BASE_URL
    "https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/cann/oam-tools-diag")

function(oam_install_bundle)
    set(_bundle_dir "${OAM_TOOLS_DIR}/bundle")

    # bundle 已存在且非空即视为就绪，跳过下载（--make_clean 会先删掉它以强制刷新）。
    # 空目录（上一轮下载失败留下的残壳）需重新拉取，否则会带空 bundle 继续、
    # 把"取包失败"推迟成后续 install() 阶段更难定位的报错。
    if(EXISTS "${_bundle_dir}" AND IS_DIRECTORY "${_bundle_dir}")
        file(GLOB _bundle_entries "${_bundle_dir}/*")
        if(_bundle_entries)
            message(STATUS "bundle already present at ${_bundle_dir}, skip download")
            return()
        endif()
        message(STATUS "bundle dir empty, re-downloading")
    endif()

    # 架构直接用 CMAKE_SYSTEM_PROCESSOR（= uname -m），与原 install_bundle.sh 的 ARCH 一致：
    # x86_64 / aarch64 均原样进包名。
    if(NOT CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|aarch64)$")
        message(FATAL_ERROR "unsupported arch for bundle download: ${CMAKE_SYSTEM_PROCESSOR}")
    endif()

    # 编译类型决定本地包名：release/debug（CMAKE_BUILD_TYPE 小写，空则默认 release），
    # 与原 install_bundle.sh 的 OUTPUT_FILE=${BASE_NAME}-${BUILD_TYPE}-${ARCH} 一致。
    if(CMAKE_BUILD_TYPE STREQUAL "")
        set(_build_type "release")
    else()
        string(TOLOWER "${CMAKE_BUILD_TYPE}" _build_type)
    endif()

    # 本地预置包按编译类型查找；下载则始终取 release 包（debug 包只能本地提供，不下载）,
    # 与原脚本 URL 恒为 cann-oam-tools-release-${ARCH} 的行为一致。
    set(_local_tar_name "cann-oam-tools-${_build_type}-${CMAKE_SYSTEM_PROCESSOR}.tar.gz")
    set(_release_tar_name "cann-oam-tools-release-${CMAKE_SYSTEM_PROCESSOR}.tar.gz")
    set(_url "${OAM_BUNDLE_BASE_URL}/${OAM_BUNDLE_BRANCH}/${_release_tar_name}")

    file(MAKE_DIRECTORY "${_bundle_dir}")

    # 离线构建：优先用预置的本地包（含编译类型），命中则免下载。检测顺序与原脚本一致：
    # 先 build/（本地编译产物），再 CANN_3RD_LIB_PATH（原脚本的 ./third_party）。
    set(_local_tar "")
    foreach(_cand
        "${OAM_TOOLS_DIR}/build/${_local_tar_name}"
        "${CANN_3RD_LIB_PATH}/${_local_tar_name}")
        if(_local_tar STREQUAL "" AND EXISTS "${_cand}")
            set(_local_tar "${_cand}")
        endif()
    endforeach()

    if(NOT _local_tar STREQUAL "")
        message(STATUS "bundle using local tarball: ${_local_tar}")
        file(COPY "${_local_tar}" DESTINATION "${_bundle_dir}")
        set(_tar_path "${_bundle_dir}/${_local_tar_name}")
    else()
        # 下载路径只提供 release 包；debug 构建若未预置本地 debug 包，将回退到 release bundle。
        set(_tar_path "${_bundle_dir}/${_release_tar_name}")
        message(STATUS "bundle download (release only): ${_url}")
        file(DOWNLOAD "${_url}" "${_tar_path}"
            TLS_VERIFY OFF
            STATUS _dl_status
            LOG _dl_log)
        list(GET _dl_status 0 _dl_code)
        if(NOT _dl_code EQUAL 0)
            list(GET _dl_status 1 _dl_msg)
            file(REMOVE "${_tar_path}")
            message(FATAL_ERROR "bundle download failed (${_dl_code}: ${_dl_msg})\n"
                "url: ${_url}\n${_dl_log}")
        endif()
    endif()

    # 解压到 bundle 目录，失败即报错（避免带残缺 bundle 继续构建）。
    file(ARCHIVE_EXTRACT
        INPUT "${_tar_path}"
        DESTINATION "${_bundle_dir}")

    # 解压后删除 tar 包，保持 bundle 目录只含解压产物。
    file(REMOVE "${_tar_path}")
    message(STATUS "bundle ready at ${_bundle_dir}")
endfunction()

oam_install_bundle()
