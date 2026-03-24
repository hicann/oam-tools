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

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASEPATH="$(cd "${SCRIPT_DIR}/.." && pwd)"
BUILD_OUTPUT_DIR="${BASEPATH}/build"

declare -A TEST_CASES=(
    ["asys_st"]="pytest"
    ["asys_ut"]="pytest"
    ["msaicerr_st"]="pytest"
    ["msaicerr_ut"]="pytest"
    ["msprof_ut"]="gtest"
)

VALID_COMPONENTS=("asys" "msaicerr" "msprof" "all")

print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --component <name>  Specify component to test: asys, msaicerr, msprof, all (default: all)"
    echo "  --ut               Run UT tests only"
    echo "  --st               Run ST tests only"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run all tests (UT + ST)"
    echo "  $0 --component asys                  # Run asys UT + ST"
    echo "  $0 --component msaicerr --ut         # Run msaicerr UT only"
    echo "  $0 --st                              # Run all ST tests"
    echo "  $0 --component msprof --ut           # Run msprof UT only"
}

parse_args() {
    COMPONENT="all"
    RUN_UT=false
    RUN_ST=false

    if [[ $# -eq 0 ]]; then
        RUN_UT=true
        RUN_ST=true
        return 0
    fi

    local parsed_args
    parsed_args=$(getopt -a -o h -l help,component:,ut,st -- "$@") || {
        print_usage
        exit 1
    }

    eval set -- "$parsed_args"

    while true; do
        case "$1" in
            -h|--help)
                print_usage
                exit 0
                ;;
            --component)
                COMPONENT="$2"
                shift 2
                ;;
            --ut)
                RUN_UT=true
                shift
                ;;
            --st)
                RUN_ST=true
                shift
                ;;
            --)
                shift
                break
                ;;
            *)
                echo "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
    done

    if [[ "$COMPONENT" != "all" ]] && [[ ! " ${VALID_COMPONENTS[*]} " =~ " ${COMPONENT} " ]]; then
        echo "ERROR: Invalid component '$COMPONENT'. Valid options: ${VALID_COMPONENTS[*]}"
        exit 1
    fi

    if [[ "$RUN_UT" == "false" ]] && [[ "$RUN_ST" == "false" ]]; then
        RUN_UT=true
        RUN_ST=true
    fi
}

get_test_cases() {
    local result=()

    local components=()
    if [[ "$COMPONENT" == "all" ]]; then
        components=("asys" "msaicerr" "msprof")
    else
        components=("$COMPONENT")
    fi

    for comp in "${components[@]}"; do
        if [[ "$RUN_UT" == "true" ]]; then
            case "$comp" in
                asys)
                    result+=("asys_ut")
                    ;;
                msaicerr)
                    result+=("msaicerr_ut")
                    ;;
                msprof)
                    result+=("msprof_ut")
                    ;;
            esac
        fi

        if [[ "$RUN_ST" == "true" ]]; then
            case "$comp" in
                asys)
                    result+=("asys_st")
                    ;;
                msaicerr)
                    result+=("msaicerr_st")
                    ;;
                msprof)
                    ;;
            esac
        fi
    done

    echo "${result[@]}"
}

validate_gtest_result() {
    local output_file="$1"
    local case_name="$2"
    local return_code=0

    if [[ ! -f "$output_file" ]]; then
        echo "ERROR: Output file not found: $output_file"
        return 1
    fi

    local exit_code=0
    local passed_count=0
    local failed_count=0

    if [[ -f "${BUILD_OUTPUT_DIR}/${case_name}.exitcode" ]]; then
        exit_code=$(cat "${BUILD_OUTPUT_DIR}/${case_name}.exitcode")
    fi

    if [[ $exit_code -ne 0 ]]; then
        echo "FAILURE: Test case $case_name exited with code $exit_code (expected 0)"
        return_code=1
    fi

    if grep -qE "^\[  PASSED  \]" "$output_file"; then
        passed_count=$(grep -E "^\[  PASSED  \]" "$output_file" | awk '{print $4}' | sed 's/tests\.$//')
    fi
    passed_count=${passed_count:-0}

    if grep -qE "^\[  FAILED  \]" "$output_file"; then
        failed_count=$(grep -E "^\[  FAILED  \]" "$output_file" | awk '{print $4}' | sed 's/tests, listed below:$//')
    fi
    failed_count=${failed_count:-0}

    if grep -qE "Segmentation fault|core dumped" "$output_file"; then
        echo "FAILURE: Test case $case_name crashed (Segmentation fault or core dumped)"
        return_code=1
    fi

    if grep -qE "==ERROR:.*Sanitizer" "$output_file"; then
        echo "FAILURE: Test case $case_name has Sanitizer errors"
        return_code=1
    fi

    if grep -qE "runtime error:" "$output_file"; then
        echo "FAILURE: Test case $case_name has runtime errors"
        return_code=1
    fi

    if grep -qE "Aborted|SIGABRT|signal 6" "$output_file"; then
        echo "FAILURE: Test case $case_name aborted unexpectedly"
        return_code=1
    fi

    if grep -qE "AddressSanitizer|memory leak" "$output_file"; then
        echo "FAILURE: Test case $case_name has memory issues"
        return_code=1
    fi

    echo "${case_name}: gtest parsed: Passed=$passed_count, Failed=$failed_count, ExitCode=$exit_code"

    if [[ $failed_count -gt 0 ]]; then
        echo "FAILURE: Test case $case_name has $failed_count failed test(s)"
        return_code=1
    fi

    if [[ $passed_count -eq 0 ]] && [[ $failed_count -eq 0 ]]; then
        echo "FAILURE: Test case $case_name ran but produced no test results (possible crash)"
        return_code=1
    fi

    return $return_code
}

validate_pytest_result() {
    local output_file="$1"
    local case_name="$2"
    local return_code=0

    if [[ ! -f "$output_file" ]]; then
        echo "ERROR: Output file not found: $output_file"
        return 1
    fi

    local exit_code=0
    local passed_count=0
    local failed_count=0
    local error_count=0

    if [[ -f "${BUILD_OUTPUT_DIR}/${case_name}.exitcode" ]]; then
        exit_code=$(cat "${BUILD_OUTPUT_DIR}/${case_name}.exitcode")
    fi

    if [[ $exit_code -ne 0 ]]; then
        echo "FAILURE: Test case $case_name exited with code $exit_code (expected 0)"
        return_code=1
    fi

    local summary_line
    summary_line=$(grep -E "^=+ .* in [0-9.]+s =+$" "$output_file")

    failed_count=$(echo "$summary_line" | grep -oE '[0-9]+ failed' | awk '{print $1}')
    passed_count=$(echo "$summary_line" | grep -oE '[0-9]+ passed' | awk '{print $1}')
    error_count=$(echo "$summary_line" | grep -oE '[0-9]+ error' | awk '{print $1}')

    passed_count=${passed_count:-0}
    failed_count=${failed_count:-0}
    error_count=${error_count:-0}

    if grep -qE "ERRORs|errors?" "$output_file" | grep -qv "0 error"; then
        if [[ $error_count -gt 0 ]]; then
            echo "FAILURE: Test case $case_name has collection/runner errors"
            return_code=1
        fi
    fi

    if grep -qE "Traceback \(most recent call last\)" "$output_file"; then
        echo "FAILURE: Test case $case_name has Python traceback (unhandled exception)"
        return_code=1
    fi

    if grep -qE "ImportError|ModuleNotFoundError" "$output_file"; then
        echo "FAILURE: Test case $case_name has import errors"
        return_code=1
    fi

    local cov_covered_ratio="N/A"
    local coverage_line
    coverage_line=$(grep -E "^TOTAL" "$output_file")
    if [[ -n "$coverage_line" ]]; then
        cov_covered_ratio=$(echo "$coverage_line" | awk '{print $4}' | sed 's/%//')
    fi

    echo "${case_name}: pytest parsed: Passed=$passed_count, Failed=$failed_count, Errors=$error_count, Cov=${cov_covered_ratio}%"

    if [[ $failed_count -gt 0 ]]; then
        echo "FAILURE: Test case $case_name has $failed_count failed test(s)"
        return_code=1
    fi

    if [[ $error_count -gt 0 ]]; then
        echo "FAILURE: Test case $case_name has $error_count error(s)"
        return_code=1
    fi

    if [[ $passed_count -eq 0 ]] && [[ $failed_count -eq 0 ]] && [[ $error_count -eq 0 ]]; then
        echo "FAILURE: Test case $case_name ran but produced no test results (possible collection failure)"
        return_code=1
    fi

    return $return_code
}

run_test_case() {
    local case_name="$1"
    local framework="${TEST_CASES[$case_name]}"
    local output_file="${BUILD_OUTPUT_DIR}/${case_name}_output.log"
    local return_code=0

    echo "---"
    echo "STARTING TEST: **$case_name** (Framework: $framework)"

    cd "${BASEPATH}"

    case "$case_name" in
        asys_st)
            python3 -m coverage run --source=./src/asys -m pytest ./test/st/asys/testcase > "${output_file}" 2>&1
            echo $? > "${BUILD_OUTPUT_DIR}/${case_name}.exitcode"
            python3 -m coverage report >> "${output_file}" 2>&1
            python3 -m coverage html -d "${BUILD_OUTPUT_DIR}/${case_name}_html" >> "${output_file}" 2>&1
            ;;
        asys_ut)
            python3 -m coverage run --source=./src/asys -m pytest ./test/ut/asys/testcase > "${output_file}" 2>&1
            echo $? > "${BUILD_OUTPUT_DIR}/${case_name}.exitcode"
            python3 -m coverage report >> "${output_file}" 2>&1
            python3 -m coverage html -d "${BUILD_OUTPUT_DIR}/${case_name}_html" >> "${output_file}" 2>&1
            ;;
        msaicerr_st)
            python3 -m coverage run --source=./src/msaicerr -m pytest ./test/st/msaicerr/testcase > "${output_file}" 2>&1
            echo $? > "${BUILD_OUTPUT_DIR}/${case_name}.exitcode"
            python3 -m coverage report >> "${output_file}" 2>&1
            python3 -m coverage html -d "${BUILD_OUTPUT_DIR}/${case_name}_html" >> "${output_file}" 2>&1
            ;;
        msaicerr_ut)
            python3 -m coverage run --source=./src/msaicerr -m pytest ./test/ut/msaicerr/testcase > "${output_file}" 2>&1
            echo $? > "${BUILD_OUTPUT_DIR}/${case_name}.exitcode"
            python3 -m coverage report >> "${output_file}" 2>&1
            python3 -m coverage html -d "${BUILD_OUTPUT_DIR}/${case_name}_html" >> "${output_file}" 2>&1
            ;;
        msprof_ut)
            if [[ -f "./build/test/ut/msprof/msprofbin/msprof_bin_utest" ]]; then
                "./build/test/ut/msprof/msprofbin/msprof_bin_utest" > "${output_file}" 2>&1
                echo $? > "${BUILD_OUTPUT_DIR}/${case_name}.exitcode"
            else
                echo "ERROR: msprof_utest binary not found at ./build/test/ut/msprof/msprofbin/msprof_bin_utest"
                echo "1" > "${BUILD_OUTPUT_DIR}/${case_name}.exitcode"
                return 1
            fi
            ;;
        *)
            echo "ERROR: Unknown test case: $case_name"
            return 1
            ;;
    esac

    echo "END TEST: **$case_name**"

    if [[ "$framework" == "gtest" ]]; then
        validate_gtest_result "$output_file" "$case_name" || return_code=1
    elif [[ "$framework" == "pytest" ]]; then
        validate_pytest_result "$output_file" "$case_name" || return_code=1
    fi

    if [[ $return_code -ne 0 ]]; then
        echo "FAILURE: Test case **$case_name** **failed**"
        echo "log saved to: **$output_file**"
        echo "--- Failure Details ---"
        tail -100 "$output_file"
        echo "-----------------------"
    else
        echo "SUCCESS: Test case **$case_name** **passed**"
        echo "log saved to: **$output_file**"
    fi

    return $return_code
}

main() {
    parse_args "$@"

    mkdir -p "${BUILD_OUTPUT_DIR}"

    echo "========================================"
    echo "Test Configuration:"
    echo "  Component: $COMPONENT"
    echo "  Run UT: $RUN_UT"
    echo "  Run ST: $RUN_ST"
    echo "  Output Dir: $BUILD_OUTPUT_DIR"
    echo "========================================"

    local test_cases=($(get_test_cases))

    if [[ ${#test_cases[@]} -eq 0 ]]; then
        echo "ERROR: No test cases to run"
        exit 1
    fi

    echo "INFO: Running test cases: ${test_cases[*]}"

    local overall_return_code=0

    for case_name in "${test_cases[@]}"; do
        run_test_case "$case_name" || overall_return_code=1
    done

    echo "========================================"
    if [[ $overall_return_code -eq 0 ]]; then
        echo "RESULT: All test cases passed"
    else
        echo "RESULT: One or more test cases failed"
    fi
    echo "========================================"

    exit $overall_return_code
}

main "$@"
