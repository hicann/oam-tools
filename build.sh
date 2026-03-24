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
    echo "                   Make clean and delete related file"
    echo "    --build-type=<TYPE>"
    echo "                   Specify build type (TYPE options: Release/Debug), default is Release"
    echo "    --pkg          Build run package"
    echo "    --cann_3rd_lib_path=<PATH>"
    echo "                   Set ascend third_party package install path, default ./third_party"
    echo "Test Options:"
    echo $dotted_line
    echo "    -u             Build and run all unit tests"
    echo "    --noexec       Only compile ut, do not execute"
    echo "    --cov          Enable code coverage for unit tests"
    echo "    --component <name>"
    echo "                   Specify component to test: asys, msaicerr, msprof, all (default: all)"
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
    CANN_3RD_LIB_PATH="$BASEPATH/third_party"

    # Process the options
    parsed_args=$(getopt -a -o j:hvuO: -l help,verbose,cov,make_clean,build-type:,noexec,pkg,asan,cann_3rd_lib_path:,component:,ut,st -- "$@") || {
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

print_success() {
  echo
  echo $dotted_line
  local msg="$1"
  echo -e "${COLOR_GREEN}[SUCCESS] ${msg}${COLOR_RESET}"
  echo $dotted_line
  echo
}

# build msprof analysis
build_msprof_analysis() {
    if [ -d "${BASEPATH}/../../mindstudio/msprof" ]; then
        echo "msprof using mindstudio"
        ROOT_PATH="${BASEPATH}/../.."
        BUILD_PATH="${ROOT_PATH}/mindstudio/msprof"
        cd ${BUILD_PATH}
        python3  ${BUILD_PATH}/build/setup.py bdist_wheel --python-tag=py3 --py-limited-api=cp37
        cp ${BUILD_PATH}/dist/msprof-0.0.1-py3-none-any.whl ${BASEPATH}/src/msprof/collector/dvvp/msprofbin
    elif [ -d "${CANN_3RD_LIB_PATH}/msprof" ]; then
        echo "msprof using thrid_party"
        mkdir -p "${BASEPATH}/${BUILD_RELATIVE_PATH}/submodule" && cd ${BASEPATH}/${BUILD_RELATIVE_PATH}/submodule
        [ ! -d "msprof" ] && cp -r "${CANN_3RD_LIB_PATH}/msprof" .
        BUILD_PATH="${BASEPATH}/${BUILD_RELATIVE_PATH}/submodule/msprof"
        cd ${BUILD_PATH}
        python3  ${BUILD_PATH}/build/setup.py bdist_wheel --python-tag=py3 --py-limited-api=cp37
        cp ${BUILD_PATH}/dist/msprof-0.0.1-py3-none-any.whl ${BASEPATH}/src/msprof/collector/dvvp/msprofbin
    else
        echo "msprof download"
        mkdir -p "${BASEPATH}/${BUILD_RELATIVE_PATH}/submodule" && cd ${BASEPATH}/${BUILD_RELATIVE_PATH}/submodule
        [ ! -d "msprof" ] && git clone https://gitcode.com/Ascend/msprof.git
        BUILD_PATH="${BASEPATH}/${BUILD_RELATIVE_PATH}/submodule/msprof"
        cd ${BUILD_PATH}
        python3  ${BUILD_PATH}/build/setup.py bdist_wheel --python-tag=py3 --py-limited-api=cp37
        cp ${BUILD_PATH}/dist/msprof-0.0.1-py3-none-any.whl ${BASEPATH}/src/msprof/collector/dvvp/msprofbin
    fi
}

# build adump analysis
build_adump_analysis() {
    if [ -d "${BASEPATH}/../../mindstudio/msaccucmp" ]; then
        echo "msprobe using mindstudio"
        SOURCE_PATH="${BASEPATH}/../../mindstudio/msaccucmp"
        cd ${BASEPATH}/src/operator_cmp
        [ ! -d "msaccucmp" ] && mkdir -p ${BASEPATH}/src/operator_cmp/msaccucmp
        cp -r ${SOURCE_PATH}/python/msprobe/msaccucmp ${BASEPATH}/src/operator_cmp/msaccucmp/compare
    elif [ -d "${CANN_3RD_LIB_PATH}/msprobe" ]; then
        echo "msprobe using thrid_party"
        BUILD_PATH="${BASEPATH}/${BUILD_RELATIVE_PATH}"
        mkdir -p "${BASEPATH}/${BUILD_RELATIVE_PATH}/submodule" && cd ${BASEPATH}/${BUILD_RELATIVE_PATH}/submodule
        [ ! -d "msprobe" ] && cp -r "${CANN_3RD_LIB_PATH}/msprobe" .
        cd ${BASEPATH}/src/operator_cmp
        [ ! -d "msaccucmp" ] && mkdir ${BASEPATH}/src/operator_cmp/msaccucmp
        cp -r ${BUILD_PATH}/submodule/msprobe/python/msprobe/msaccucmp ${BASEPATH}/src/operator_cmp/msaccucmp/compare
    else
        echo "msprobe download"
        BUILD_PATH="${BASEPATH}/${BUILD_RELATIVE_PATH}"
        mkdir -p "${BASEPATH}/${BUILD_RELATIVE_PATH}/submodule" && cd ${BASEPATH}/${BUILD_RELATIVE_PATH}/submodule
        [ ! -d "msprobe" ] && git clone https://gitcode.com/Ascend/msprobe.git
        cd ${BASEPATH}/src/operator_cmp
        [ ! -d "msaccucmp" ] && mkdir ${BASEPATH}/src/operator_cmp/msaccucmp
        cp -r ${BUILD_PATH}/submodule/msprobe/python/msprobe/msaccucmp ${BASEPATH}/src/operator_cmp/msaccucmp/compare
    fi
}

# oam_tools build start
cmake_generate_make() {
    local build_path="$1"
    local cmake_args="$2"
    if [[ "${MAKE_CLEAN_ALL}" == "on" ]];then
        echo "clear all files in build directory"
        [ -d "${build_path}" ] && rm -rf "${build_path}"
    fi
    mk_dir "${build_path}"
    cd "${build_path}"
    [ -f CMakeCache.txt ] && rm CMakeCache.txt
    [ -f Makefile ] && rm Makefile
    [ -f cmake_install.cmake ] && rm cmake_install.cmake
    [ -d CMakeFiles ] && rm -rf CMakeFiles
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
    ARCH_LOWER=$(uname -m | tr '[:upper:]' '[:lower:]')
    BUILD_TYPE_LOWER=$(echo "$BUILD_TYPE" | tr '[:upper:]' '[:lower:]')
    bash install_bundle.sh $BUILD_TYPE_LOWER $ARCH_LOWER
    if [ 0 -ne $? ]; then
        echo "cannot find cann-oam-tools's tar.gz, exit."
        exit 1
    fi
    build_msprof_analysis
    build_adump_analysis
    echo "create build directory and build oam_tools"
    cd "${BASEPATH}"
    ENABLE_BINARY=TRUE
    BUILD_PATH="${BASEPATH}/${BUILD_RELATIVE_PATH}/"
    BUILD_OUT_PATH="${BASEPATH}/${BUILD_OUT}/"
    CMAKE_ARGS="\
    -DCMAKE_INSTALL_PREFIX=${BUILD_PATH} \
    -DENABLE_UT=${ENABLE_UT} \
    -DBUILD_WITH_INSTALLED_DEPENDENCY_CANN_PKG=ON \
    -DCANN_3RD_LIB_PATH=${CANN_3RD_LIB_PATH} \
    -DPRODUCT_SIDE=device \
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

    make ${VERBOSE} -j${THREAD_NUM} && make package
    # make package
    if [ 0 -ne $? ]; then
        echo "execute command: make ${VERBOSE} -j${THREAD_NUM} && make install failed."
        return 1
    fi
    if [ -f cann*.run ];then
        mkdir -pv $BUILD_OUT_PATH
        mv cann*.run $BUILD_OUT_PATH
    else
        echo "package oam_tools run failed"
        return 1
    fi

    echo "oam_tools build success!"
}

main() {
    cd "${BASEPATH}"
    checkopts "$@"
    if [ "$THREAD_NUM" -gt "$CORE_NUMS" ];then
        echo "compile thread num:$THREAD_NUM over core num:$CORE_NUMS, adjust to core num"
        THREAD_NUM=$CORE_NUMS
    fi

    g++ -v
    echo "---------------- oam_tools build start ----------------"
    build_oam_tools || { echo "oam_tools build failed."; exit 1; }
    echo "---------------- oam_tools build finished ----------------"
    if [[ "${ENABLE_UT}" == "on" && "${EXEC_TEST}" == "on" ]];then
        source "${ASCEND_HOME_PATH}/bin/setenv.bash"
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
        
        bash "${BASEPATH}/scripts/run_tests.sh" "${run_tests_args[@]}"
        if [ $? -ne 0 ]; then
            echo "Execute run_tests.sh failed."
            exit 1
        fi
        echo "Execute run_tests.sh successful."
    fi
}

main "$@"