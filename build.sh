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
    if [[ -n "${ASCEND_HOME_PATH}" ]]; then
        echo "env exists ASCEND_HOME_PATH : ${ASCEND_HOME_PATH}"
    elif [ $UID -eq 0 ]; then
        export ASCEND_HOME_PATH=/usr/local/Ascend/latest
    else
        export ASCEND_HOME_PATH=~/Ascend/latest
    fi
    CANN_3RD_LIB_PATH="$BASEPATH/third_party"

    # Process the options
    parsed_args=$(getopt -a -o j:hvuO: -l help,verbose,cov,make_clean,build-type:,noexec,pkg,asan,cann_3rd_lib_path: -- "$@") || {
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
        ROOT_PATH="${BASEPATH}/../.."
        BUILD_PATH="${ROOT_PATH}/mindstudio/msprof"
        cd ${BUILD_PATH}
        python3  ${BUILD_PATH}/build/setup.py bdist_wheel --python-tag=py3 --py-limited-api=cp37
        cp ${BUILD_PATH}/dist/msprof-0.0.1-py3-none-any.whl ${BASEPATH}/src/msprof/collector/dvvp/msprofbin
    else
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
        SOURCE_PATH="${BASEPATH}/../../mindstudio/msaccucmp"
        cd ${BASEPATH}/src/operator_cmp
        [ ! -d "msaccucmp" ] && mkdir -p ${BASEPATH}/src/operator_cmp/msaccucmp
        cp -r ${SOURCE_PATH}/python/msprobe/msaccucmp ${BASEPATH}/src/operator_cmp/msaccucmp/compare
    else
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

declare -A TEST_CASES=(
    ["asys_st"]="pytest"
    ["asys_ut"]="pytest"
    ["msaicerr_st"]="pytest"
    ["msaicerr_ut"]="pytest"
    ["msprof_ut"]="gtest"
)
oam_tools_test() {
    local return_code=0
    local test_list=()

    # --- 1. Determine which test cases to run ---
    if [ $# -eq 0 ]; then
        # Run all cases if no arguments are provided
        test_list=("${!TEST_CASES[@]}")
        echo "INFO: Running all test cases: ${test_list[@]}"
    else
        # Run only the specified cases
        for arg in "$@"; do
            if [[ -v TEST_CASES[$arg] ]]; then
                test_list+=("$arg")
            else
                echo "ERROR: Invalid test case name '$arg'. Valid cases are: ${!TEST_CASES[*]}" >&2
                return 1
            fi
        done
        echo "INFO: Running specified test cases: ${test_list[*]}"
    fi

    # --- 2. Loop through and execute each test case ---
    for case_name in "${test_list[@]}"; do
        local output_file="${case_name}_output.log"
        local framework="${TEST_CASES[$case_name]}"
        echo "---"
        echo "STARTING TEST: **$case_name** (Framework: $framework)"
        # --- ACTUAL EXECUTION STEP ---
        if [ "$case_name" == "asys_st" ]; then
            coverage run --source=../src/asys -m pytest ../test/st/asys/testcase > "${output_file}" 2>&1
            coverage report >> "${output_file}"
            coverage html -d "$case_name"_html >> "${output_file}"
        elif [ "$case_name" == "asys_ut" ]; then
            coverage run --source=../src/asys -m pytest ../test/ut/asys/testcase > "${output_file}" 2>&1
            coverage report >> "${output_file}"
            coverage html -d "$case_name"_html >> "${output_file}"
        elif [ "$case_name" == "msaicerr_st" ]; then
            coverage run --source=../src/msaicerr -m pytest ../test/st/msaicerr/testcase > "${output_file}" 2>&1
            coverage report >> "${output_file}"
            coverage html -d "$case_name"_html >> "${output_file}"
        elif [ "$case_name" == "msaicerr_ut" ]; then
            coverage run --source=../src/msaicerr -m pytest ../test/ut/msaicerr/testcase > "${output_file}" 2>&1
            coverage report >> "${output_file}"
            coverage html -d "$case_name"_html >> "${output_file}"
        elif [ "$case_name" == "msprof_ut" ]; then
            ./test/ut/msprof/msprofbin/msprof_bin_utest > "${output_file}" 2>&1
        fi
         echo "END TEST: **$case_name**"

        # --- 3. Check the output file for FAILED/Failed keywords ---
        if [ ! -f "$output_file" ]; then
            echo "ERROR: Test case $case_name failed to generate output file: $output_file" >&2
            return_code=1
            continue
        fi

        local passed_count=0
        local failed_count=0
        
        # --- gtest LOGIC (aml_st, aml_ut) ---
        if [ "$framework" == "gtest" ]; then
            # Extract PASSED count
            passed_count=$(grep -E "^\[  PASSED  \]" "$output_file" | awk '{print $4}' | sed 's/tests\.$//')
            # Extract FAILED count
            failed_count=$(grep -E "^\[  FAILED  \]" "$output_file" | awk '{print $4}' | sed 's/tests, listed below:$//')

            # Default to 0 if grep/awk finds nothing (may happen if the run crashed before summary)
            passed_count=${passed_count:-0}
            failed_count=${failed_count:-0}
            
            echo "${case_name}: gtest parsed: Passed=$passed_count, Failed=$failed_count"
            
        # --- pytest LOGIC (asys_st, asys_ut) ---
        elif [ "$framework" == "pytest" ]; then
            # Pytest summary line example: '== 1 failed, 2 passed, 1 skipped in 1.50s =='
            summary_line=$(grep -E "^=+ .* in [0-9.]+s =+$" "$output_file")
            
            # Extract failed count
            failed_count=$(echo "$summary_line" | grep -oE '[0-9]+ failed' | awk '{print $1}')
            
            # Extract passed count
            passed_count=$(echo "$summary_line" | grep -oE '[0-9]+ passed' | awk '{print $1}')
            
            # Default to 0 if grep/awk finds nothing
            passed_count=${passed_count:-0}
            failed_count=${failed_count:-0}

            coverage_line=$(grep -E "TOTAL" "$output_file")
            cov_total_line=$(echo "$coverage_line" | awk '{print $2}')
            cov_covered_line=$(echo "$coverage_line" | awk '{print $3}')
            cov_covered_ratio=$(echo "$coverage_line" | awk '{print $4}' | sed 's/%//')

            echo "${case_name}: pytest parsed: Passed=$passed_count, Failed=$failed_count, Cov=$cov_covered_ratio%"
        fi

        # --- Final Judgment ---
        if [ "$failed_count" -gt 0 ] || [ "$passed_count" -eq 0 ]; then
            echo "FAILURE: Test case **$case_name** **failed** ($failed_count failures out of $(($passed_count + $failed_count)) total)."
            echo "log saved to: **$output_file**"
            cat $output_file
            # Print failure details for the user
            if [ "$framework" == "gtest" ]; then
                echo "--- FAILURE LOG SUMMARY (gtest FAILED tests) ---"
                grep -E "^\[  FAILED  \]" "$output_file"
            elif [ "$framework" == "pytest" ]; then
                echo "--- FAILURE LOG SUMMARY (pytest short summary info) ---"
                grep -A 5 -E "short test summary info" "$output_file"
            fi
            echo "-------------------------------------------------------------"
            return_code=1
        else
            echo "SUCCESS: Test case **$case_name** **passed** ($passed_count successful tests)."
            echo "log saved to: **$output_file**"
        fi
    done

    # --- 4. Return Final Result ---
    echo "---"
    if [ $return_code -eq 0 ]; then
        echo "RESULT: All specified test cases passed. Returning exit code: 0"
    else
        echo "RESULT: One or more test cases failed. Returning exit code: 1"
    fi
    return "$return_code"
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
        oam_tools_test msaicerr_st msaicerr_ut msprof_ut
        if [ $? -ne 0 ]; then
            echo "Execute oam_tools_test failed."
            exit 1
        fi
        echo "Execute oam_tools_test successful."
    fi
}

main "$@"