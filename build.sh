#!/bin/bash
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


BASEPATH=$(cd "$(dirname $0)"; pwd)
SCRIPT_DIR="${BASEPATH}"
BUILD_RELATIVE_PATH="build"
BUILD_OUT="build_out"
CORE_NUMS=$(cat /proc/cpuinfo| grep "processor"| wc -l)

# print usage message
dotted_line="----------------------------------------------------------------"
usage() {
    echo "Usage:"
    echo ""
    echo "    -h, --help     Print usage"
    echo "    -v, --verbose  Display build command"
    echo "Default Build Pkg Options:"
    echo $dotted_line
    echo "    -j<N>          Set the number of threads used for building oam_tools, default is 8"
    echo "    -O<N>          Compile optimization options, support [O0 O1 O2 O3], default is O2"
    echo "    --make_clean "
    echo "                   Make clean and delete build directory, bundle directory, and version file"
    echo "    --build-type=<TYPE>"
    echo "                   Specify build type (TYPE options: Release/Debug), default is Release"
    echo "    --pkg          Build run package"
    echo "    --ascend_install_path=<PATH>"
    echo "                   Set ascend package install path, default /usr/local/Ascend/cann"
    echo "    --cann_3rd_lib_path=<PATH>"
    echo "                   Set ascend third_party package install path, default ./third_party"
    echo "Test Options:"
    echo $dotted_line
    echo "    -u             Build and run all unit tests"
    echo "    --noexec       Only compile ut, do not execute"
    echo "    --cov          Enable code coverage for unit tests"
    echo "    --component <name>"
    echo "                   Specify component to test:"
    echo "                   asys, msaicerr, msprof, install, upgrade, uninstall, all (default: all)"
    echo "    --ut           Run UT tests only (default when -u is specified)"
    echo "    --st           Run ST tests only"
    echo ""
}

# parse and set options
checkopts() {
    VERBOSE=""
    THREAD_NUM=8
    ENABLE_UT="off"
    MAKE_CLEAN_ALL="off"
    EXEC_TEST="off"
    BUILD_TYPE="Release"
    BUILD_MODE=""
    ENABLE_COVERAGE="off"
    TEST_COMPONENT="all"
    RUN_UT_ONLY="off"
    RUN_ST_ONLY="off"

    if [[ -n "${ASCEND_HOME_PATH}" ]]; then
        echo "env exists ASCEND_HOME_PATH : ${ASCEND_HOME_PATH}"
    elif [ $UID -eq 0 ]; then
        export ASCEND_HOME_PATH=/usr/local/Ascend/latest
    else
        export ASCEND_HOME_PATH=~/Ascend/latest
    fi
    ASCEND_INSTALL_PATH="${ASCEND_HOME_PATH}"
    CANN_3RD_LIB_PATH="$BASEPATH/third_party"

    # Process the options
    parsed_args=$(getopt -a -o j:hvuO: -l help,verbose,cov,make_clean,build-type:,noexec,ascend_install_path:,pkg,asan,cann_3rd_lib_path:,component:,ut,st -- "$@") || {
    usage
    exit 1
    }

    eval set -- "$parsed_args"

    while true; do
    case "$1" in
        -h | --help)
        usage
        exit 0
        ;;
        -j)
        THREAD_NUM="$2"
        shift 2
        ;;
        -v | --verbose)
        VERBOSE="VERBOSE=1"
        shift
        ;;
        -u)
        ENABLE_UT="on"
        EXEC_TEST="on"
        shift
        ;;
        -O)
        BUILD_MODE="-O$2"
        shift 2
        ;;
        --cov)
        ENABLE_COVERAGE="on"
        shift
        ;;
        --make_clean)
        MAKE_CLEAN_ALL="on"
        shift
        ;;
        --build-type)
        BUILD_TYPE=$2
        shift 2
        ;;
        --noexec)
        EXEC_TEST="off"
        shift
        ;;
        --ascend_install_path)
        ASCEND_HOME_PATH="$(realpath $2)"
        shift 2
        ;;
        --cann_3rd_lib_path)
        CANN_3RD_LIB_PATH="$(realpath $2)"
        shift 2
        ;;
        --asan)
        ENABLE_ASAN="on"
        shift
        ;;
        --component)
        TEST_COMPONENT="$2"
        shift 2
        ;;
        --ut)
        RUN_UT_ONLY="on"
        shift
        ;;
        --st)
        RUN_ST_ONLY="on"
        shift
        ;;
        --pkg)
        shift
        ;;
        --)
        shift
        break
        ;;
        *)
        echo "Undefined option: $1"
        usage
        exit 1
        ;;
    esac
    done
}

mk_dir() {
    local create_dir="$1"
    mkdir -pv "${create_dir}"
    echo "created ${create_dir}"
}

# 安全删除目录：非空判断 + 存在性检查 + 恢复写权限后再删除，禁止 rm -rf。
safe_rm_dir() {
    local dir_path="$1"
    if [ -z "${dir_path}" ] || [ ! -d "${dir_path}" ]; then
        return
    fi
    chmod -R u+w "${dir_path}" 2>/dev/null
    rm -r -- "${dir_path}"
}

clean_cpack_staging() {
    local build_path="$1"
    local cpack_path="${build_path%/}/_CPack_Packages"

    if [ -z "${build_path}" ] || [ -z "${cpack_path}" ]; then
        return
    fi

    echo "clear cpack staging directory"
    safe_rm_dir "${cpack_path}"
}

print_success() {
  echo
  echo $dotted_line
  local msg="$1"
  echo -e "${COLOR_GREEN}[SUCCESS] ${msg}${COLOR_RESET}"
  echo $dotted_line
  echo
}

# oam_tools build start
cmake_generate_make() {
    local build_path="$1"
    local cmake_args="$2"
    if [[ "${MAKE_CLEAN_ALL}" == "on" ]];then
        echo "clear all files in build directory"
        safe_rm_dir "${build_path}"
    fi
    mk_dir "${build_path}"
    cd "${build_path}"
    [ -f CMakeCache.txt ] && rm CMakeCache.txt
    [ -f Makefile ] && rm Makefile
    [ -f cmake_install.cmake ] && rm cmake_install.cmake
    [ -d CMakeFiles ] && safe_rm_dir CMakeFiles
    echo "${cmake_args}"
    cmake ${cmake_args} ..
    if [ 0 -ne $? ]; then
        echo "execute command: cmake ${cmake_args} .. failed."
        exit 1
    fi
}

REPOSITORY_NAME="oam"

# create build path
build_oam_tools() {
    echo "ARCH: $(arch)"
    # === 新增判断逻辑 ===
    # 1. 先处理 --make_clean：清理 bundle 目录
    if [[ "${MAKE_CLEAN_ALL}" == "on" ]]; then
        echo "--make_clean: clearing bundle directory"
        safe_rm_dir "bundle"
    fi

    # 2. 处理 --make_clean：清理 submodule 目录（msprof, msprobe）
    if [[ "${MAKE_CLEAN_ALL}" == "on" ]]; then
        echo "--make_clean: clearing submodule directory (msprof, msprobe)"
        safe_rm_dir "submodule"
    fi

    # === 判断逻辑结束 ===
    # bundle 闭源包拉取/解压已迁至 cmake/install_bundle.cmake；
    # msprof wheel 构建与 msaccucmp/compare 同步已迁至 cmake/build_submodules.cmake，
    # 均由 cmake 配置期负责，此处不再调用。
    echo "create build directory and build oam_tools"
    cd "${BASEPATH}"
    ENABLE_BINARY=TRUE
    BUILD_PATH="${BASEPATH}/${BUILD_RELATIVE_PATH}"
    BUILD_OUT_PATH="${BASEPATH}/${BUILD_OUT}"
    CMAKE_ARGS="\
    -DCMAKE_INSTALL_PREFIX=${BUILD_PATH} \
    -DENABLE_UT=${ENABLE_UT} \
    -DASCEND_INSTALL_PATH=${ASCEND_INSTALL_PATH} \
    -DCANN_3RD_LIB_PATH=${CANN_3RD_LIB_PATH} \
    -DDCMAKE_WGET_FLAGS='--no-check-certificate' \
    -DCMAKE_BUILD_TYPE=${BUILD_TYPE} \
    -DBUILD_MODE=${BUILD_MODE} \
    -DENABLE_GCOV=${ENABLE_COVERAGE} \
    -DENABLE_ASAN=${ENABLE_ASAN} \
    -DENABLE_UT=${ENABLE_UT} \
    -DENABLE_SIGN=${ENABLE_SIGN} \
    -DBUILD_OPEN_PROJECT=ON\
    -DENABLE_PACKAGE=TRUE"
    cmake_generate_make "${BUILD_PATH}" "${CMAKE_ARGS}"

    make ${VERBOSE} -j${THREAD_NUM} && clean_cpack_staging "${BUILD_PATH}" && make package
    # make package
    if [ 0 -ne $? ]; then
        echo "execute command: make ${VERBOSE} -j${THREAD_NUM} && make install failed."
        return 1
    fi
    if [ -f cann*.run ];then
        mkdir -pv "$BUILD_OUT_PATH"
        mv cann*.run "$BUILD_OUT_PATH"
    else
        echo "package oam_tools run failed"
        return 1
    fi

    echo "oam_tools build success!"
}

# Python-only components have no compiled artefacts and don't need build_oam_tools.
# When -u is used and the requested component is in this list, skip the heavy
# build (cmake/make/cpack/.run packaging, msprof wheel, msprobe staging, etc.).
is_python_only_component() {
    case "$1" in
        asys|msaicerr) return 0 ;;
        *) return 1 ;;
    esac
}

generate_asys_chip_handler() {
    echo "---------------- generating chip_handler.py for asys component ----------------"
    cmake -P "${BASEPATH}/src/asys/asys.cmake" || { echo "generate chip_handler.py failed."; exit 1; }
}

main() {
    cd "${BASEPATH}"
    checkopts "$@"
    if [ "$THREAD_NUM" -gt "$CORE_NUMS" ];then
        echo "compile thread num:$THREAD_NUM over core num:$CORE_NUMS, adjust to core num"
        THREAD_NUM=$CORE_NUMS
    fi

    local skip_build="off"
    if [[ "${ENABLE_UT}" == "on" && "${EXEC_TEST}" == "on" ]] && is_python_only_component "${TEST_COMPONENT}"; then
        skip_build="on"
        echo "---------------- skip oam_tools build for python-only component: ${TEST_COMPONENT} ----------------"
        generate_asys_chip_handler
    fi

    if [[ "${skip_build}" == "off" ]]; then
        g++ -v
        echo "---------------- oam_tools build start ----------------"
        build_oam_tools || { echo "oam_tools build failed."; exit 1; }
        echo "---------------- oam_tools build finished ----------------"
    fi

    if [[ "${ENABLE_UT}" == "on" && "${EXEC_TEST}" == "on" ]];then
        if [[ -f "${ASCEND_HOME_PATH}/bin/setenv.bash" ]]; then
            source "${ASCEND_HOME_PATH}/bin/setenv.bash"
        else
            echo "WARNING: ${ASCEND_HOME_PATH}/bin/setenv.bash not found, skipping source"
        fi
        export LD_LIBRARY_PATH="${BASEPATH}/${BUILD_RELATIVE_PATH}"/:$LD_LIBRARY_PATH
        
        local run_tests_args=()
        if [[ "$TEST_COMPONENT" != "all" ]]; then
            run_tests_args+=("--component" "$TEST_COMPONENT")
        fi
        if [[ "$RUN_UT_ONLY" == "on" ]]; then
            run_tests_args+=("--ut")
        fi
        if [[ "$RUN_ST_ONLY" == "on" ]]; then
            run_tests_args+=("--st")
        fi
        if [[ "$ENABLE_COVERAGE" == "on" ]]; then
            run_tests_args+=("--cov")
        fi

        bash "${BASEPATH}/scripts/run_tests.sh" "${run_tests_args[@]}"
        if [ $? -ne 0 ]; then
            echo "Execute run_tests.sh failed."
            exit 1
        fi
        echo "Execute run_tests.sh successful."
    fi
}

main "$@"
