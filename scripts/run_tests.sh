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
# build.sh moves generated cann-oam-tools_*.run packages to build_out/.
BUILD_OUT_DIR="${BASEPATH}/build_out"

declare -A TEST_CASES=(
    ["asys_st"]="pytest"
    ["asys_ut"]="pytest"
    ["msaicerr_st"]="pytest"
    ["msaicerr_ut"]="pytest"
    ["msprof_ut"]="gtest"
    ["install_st"]="pytest"
    ["upgrade_st"]="pytest"
    ["uninstall_st"]="pytest"
)

VALID_COMPONENTS=("asys" "msaicerr" "msprof" "install" "upgrade" "uninstall" "all")

print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --component <name>  Specify component to test:"
    echo "                        asys, msaicerr, msprof, install, upgrade, uninstall, all (default: all)"
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
    echo "  $0 --component install               # Run install ST"
    echo "  $0 --component upgrade               # Run upgrade ST"
    echo "  $0 --component uninstall             # Run uninstall ST"
}

parse_args() {
    COMPONENT="all"
    RUN_UT=false
    RUN_ST=false
    RUN_COV=false

    if [[ $# -eq 0 ]]; then
        RUN_UT=true
        RUN_ST=true
        return 0
    fi

    local parsed_args
    parsed_args=$(getopt -a -o h -l help,component:,ut,st,cov -- "$@") || {
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
            --cov)
                RUN_COV=true
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
        components=("asys" "msaicerr" "msprof" "install" "upgrade" "uninstall")
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
                # install/upgrade/uninstall have no UT counterpart
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
                install)
                    result+=("install_st")
                    ;;
                upgrade)
                    result+=("upgrade_st")
                    ;;
                uninstall)
                    result+=("uninstall_st")
                    ;;
            esac
        fi
    done

    echo "${result[@]}"
}

is_package_st_case() {
    case "$1" in
        install_st|upgrade_st|uninstall_st)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

find_run_package() {
    local pkg
    pkg=$(find "${BUILD_OUT_DIR}" -maxdepth 1 -type f -name "cann-oam-tools_*.run" 2>/dev/null \
        | sort -V | tail -n 1)
    if [[ -n "${pkg}" ]]; then
        echo "${pkg}"
        return 0
    fi
    return 1
}

ensure_run_package_for_st_cases() {
    local test_cases=("$@")
    local case_name
    local need_package=false

    for case_name in "${test_cases[@]}"; do
        if is_package_st_case "${case_name}"; then
            need_package=true
            break
        fi
    done

    if [[ "${need_package}" != "true" ]]; then
        return 0
    fi

    local run_pkg
    run_pkg=$(find_run_package || true)
    if [[ -n "${run_pkg}" ]]; then
        echo "INFO: Using run package: ${run_pkg}"
        return 0
    fi

    echo "INFO: install/upgrade/uninstall ST requires a cann-oam-tools .run package."
    echo "INFO: No cann-oam-tools_*.run found in ${BUILD_OUT_DIR}; building package first."
    if ! bash "${BASEPATH}/build.sh" --noexec; then
        echo "ERROR: Failed to build run package with bash build.sh --noexec"
        return 1
    fi

    run_pkg=$(find_run_package || true)
    if [[ -z "${run_pkg}" ]]; then
        echo "ERROR: build.sh finished but no cann-oam-tools_*.run was found in ${BUILD_OUT_DIR}"
        return 1
    fi

    echo "INFO: Prepared run package: ${run_pkg}"
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
    if [[ -f "${BUILD_OUTPUT_DIR}/${case_name}.exitcode" ]]; then
        exit_code=$(cat "${BUILD_OUTPUT_DIR}/${case_name}.exitcode")
    fi
    exit_code=${exit_code:-0}

    # 异常退出检测：信号杀死(exit_code >= 128) 或输出含崩溃标记。
    # 此时框架未正常完成，通过/失败统计不可靠，改为打印崩溃信息和未完成用例。
    local crashed=false
    if [[ "$exit_code" =~ ^[0-9]+$ ]] && [[ $exit_code -ge 128 ]]; then
        crashed=true
    fi
    if grep -qE "Segmentation fault|core dumped" "$output_file"; then
        crashed=true
    fi
    if grep -qE "==ERROR:.*Sanitizer" "$output_file"; then
        crashed=true
    fi
    if grep -qE "Aborted|SIGABRT|signal 6" "$output_file"; then
        crashed=true
    fi

    if [[ "$crashed" == "true" ]]; then
        echo "FAILURE: Test case $case_name crashed abnormally (ExitCode=$exit_code)"
        echo "--- Error output ---"
        grep -nE "Segmentation fault|core dumped|Aborted|SIGABRT|==ERROR:.*Sanitizer|AddressSanitizer|runtime error:" "$output_file" 2>/dev/null | head -20
        echo "--- Test case(s) that did not complete ---"
        # 找出所有 [ RUN ] 但没有对应 [ OK ] 或逐条 [ FAILED ] 的用例
        awk '
        /^\[ RUN      \] / {
            idx = index($0, "] ")
            testname = substr($0, idx + 2)
            started[testname] = NR
        }
        /^\[       OK \] / {
            idx = index($0, "] ")
            testname = substr($0, idx + 2)
            sub(/ \([0-9]+ ms\).*/, "", testname)
            delete started[testname]
        }
        /^\[  FAILED  \] [A-Za-z_]/ {
            idx = index($0, "] ")
            testname = substr($0, idx + 2)
            sub(/ \([0-9]+ ms\).*/, "", testname)
            delete started[testname]
        }
        END {
            for (t in started) print t
        }
        ' "$output_file"
        return 1
    fi

    # 正常退出：解析并打印用例统计
    local passed_count=0
    local failed_count=0

    if [[ $exit_code -ne 0 ]]; then
        echo "FAILURE: Test case $case_name exited with code $exit_code (expected 0)"
        return_code=1
    fi

    if grep -qE "^\[  PASSED  \]" "$output_file"; then
        # 一个 case 可能运行多个 gtest target，输出含多段 [ PASSED ]，需累加求和
        passed_count=$(grep -E "^\[  PASSED  \]" "$output_file" | awk '{gsub(/tests?\.$/,"",$4); s+=$4} END{print s}')
    fi
    passed_count=${passed_count:-0}

    if grep -qE "^\[  FAILED  \]" "$output_file"; then
        # 同上：累加所有 target 的失败用例数（取每段汇总行的数字）
        failed_count=$(grep -E "^\[  FAILED  \] [0-9]+ test" "$output_file" | awk '{s+=$4} END{print s}')
    fi
    failed_count=${failed_count:-0}

    if grep -qE "runtime error:" "$output_file"; then
        echo "FAILURE: Test case $case_name has runtime errors"
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
    if [[ -f "${BUILD_OUTPUT_DIR}/${case_name}.exitcode" ]]; then
        exit_code=$(cat "${BUILD_OUTPUT_DIR}/${case_name}.exitcode")
    fi
    exit_code=${exit_code:-0}

    # 异常退出检测：信号杀死(exit_code >= 128) 或输出含崩溃标记。
    # 此时框架未正常完成，通过/失败统计不可靠，改为打印崩溃信息和错误输出。
    local crashed=false
    if [[ "$exit_code" =~ ^[0-9]+$ ]] && [[ $exit_code -ge 128 ]]; then
        crashed=true
    fi
    if grep -qE "Segmentation fault|core dumped" "$output_file"; then
        crashed=true
    fi
    if grep -qE "Fatal Python error" "$output_file"; then
        crashed=true
    fi
    if grep -qE "==ERROR:.*Sanitizer" "$output_file"; then
        crashed=true
    fi
    if grep -qE "Aborted|SIGABRT|signal 6" "$output_file"; then
        crashed=true
    fi

    if [[ "$crashed" == "true" ]]; then
        echo "FAILURE: Test case $case_name crashed abnormally (ExitCode=$exit_code)"
        echo "--- Error output ---"
        grep -nE "Segmentation fault|core dumped|Fatal Python error|==ERROR:.*Sanitizer|AddressSanitizer|Aborted|SIGABRT" "$output_file" 2>/dev/null | head -20
        echo "--- Traceback (if any) ---"
        grep -nE "Traceback \(most recent call last\)|^Error:|^Exception:|raise .*Error" "$output_file" 2>/dev/null | head -20
        echo "--- Last 20 lines of output ---"
        tail -20 "$output_file"
        return 1
    fi

    # 正常退出：解析并打印用例统计
    local passed_count=0
    local failed_count=0
    local error_count=0

    if [[ $exit_code -ne 0 ]]; then
        echo "FAILURE: Test case $case_name exited with code $exit_code (expected 0)"
        return_code=1
    fi

    local summary_line
    # pytest appends "(HH:MM:SS)" after the seconds when total time exceeds 1 minute.
    summary_line=$(grep -E "^=+ .* in [0-9.]+s( \([0-9:]+\))? =+$" "$output_file")

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

run_pytest_with_coverage() {
    local case_name="$1"
    local source_dir="$2"
    local test_dir="$3"
    local output_file="$4"
    local cov_dir="${BUILD_OUTPUT_DIR}/${case_name}_cov"

    mkdir -p "${cov_dir}"
    # Each case gets its own COVERAGE_FILE so concurrent or sequential runs of
    # different components do not overwrite one another's .coverage data file.
    export COVERAGE_FILE="${cov_dir}/.coverage"

    python3 -m coverage run --source="${source_dir}" -m pytest "${test_dir}" > "${output_file}" 2>&1
    echo $? > "${BUILD_OUTPUT_DIR}/${case_name}.exitcode"
    python3 -m coverage report >> "${output_file}" 2>&1
    python3 -m coverage html -d "${BUILD_OUTPUT_DIR}/${case_name}_html" >> "${output_file}" 2>&1

    unset COVERAGE_FILE
}

run_pytest_plain() {
    local case_name="$1"
    local test_dir="$2"
    local output_file="$3"

    python3 -m pytest "${test_dir}" > "${output_file}" 2>&1
    echo $? > "${BUILD_OUTPUT_DIR}/${case_name}.exitcode"
}

# Collect C++ gcov coverage for a gtest case (e.g. msprof_ut).
# $1 case_name (used for *_cov / *_html dir naming, aligned with pytest cases)
# $2 capture_dir: build subdir holding .gcno/.gcda (the UT build tree)
# $3 extract_arg: 覆盖率统计口径。可为：
#      - lcov path glob（如 '*/src/msprof/*'），按通配符保留；
#      - 一个已存在的白名单文件路径，按其中逐行列出的源文件精确保留。
# $4 output_file: test log to append the coverage summary to
collect_gcov_coverage() {
    local case_name="$1"
    local capture_dir="$2"
    local extract_arg="$3"
    local output_file="$4"
    local cov_dir="${BUILD_OUTPUT_DIR}/${case_name}_cov"
    local html_dir="${BUILD_OUTPUT_DIR}/${case_name}_html"
    # lcov/geninfo and genhtml accept different --ignore-errors categories
    # (e.g. gcov/mismatch are capture-only), so keep two separate lists.
    local ign="--ignore-errors=mismatch,gcov,source,negative,unused,empty,inconsistent"
    local html_ign="--ignore-errors=source,inconsistent,unmapped,category,corrupt"

    mkdir -p "${cov_dir}"

    # baseline (zero counts for every instrumented file) so files that no test
    # exercised still count toward the denominator, like coverage.py --source.
    lcov -c -i -d "${capture_dir}" -o "${cov_dir}/base.info" ${ign} >> "${output_file}" 2>&1
    lcov -c -d "${capture_dir}" -o "${cov_dir}/run.info" ${ign} >> "${output_file}" 2>&1
    lcov -a "${cov_dir}/base.info" -a "${cov_dir}/run.info" \
        -o "${cov_dir}/total.info" ${ign} >> "${output_file}" 2>&1
    # 口径：白名单文件 → 按文件列表精确 extract；否则按通配符 extract。
    if [[ -f "${extract_arg}" ]]; then
        local extract_files=()
        local _f
        while IFS= read -r _f; do
            [[ -n "${_f}" ]] && extract_files+=("${_f}")
        done < "${extract_arg}"
        lcov --extract "${cov_dir}/total.info" "${extract_files[@]}" \
            -o "${cov_dir}/coverage.info" ${ign} >> "${output_file}" 2>&1
    else
        lcov --extract "${cov_dir}/total.info" "${extract_arg}" \
            -o "${cov_dir}/coverage.info" ${ign} >> "${output_file}" 2>&1
    fi

    genhtml "${cov_dir}/coverage.info" -o "${html_dir}" ${html_ign} >> "${output_file}" 2>&1

    local cov_ratio="N/A"
    cov_ratio=$(lcov --summary "${cov_dir}/coverage.info" ${ign} 2>&1 \
        | grep -E "lines\.+:" | head -1 | grep -oE "[0-9]+\.[0-9]+%" | head -1 | sed 's/%//')
    cov_ratio=${cov_ratio:-N/A}
    echo "${case_name}: gcov parsed: Cov=${cov_ratio}%"
}

# 动态生成 msprof 覆盖率统计白名单：
# oam-tools 本仓只编译/安装 acp 与 msprofbin 两个模块，其余 lib(profapi/profimpl/
# msprofiler 等)在 runtime 仓编译。覆盖率只应统计这两个模块实际编译的源文件，
# 因此从二者的生产 CMakeLists 动态解析源文件清单，避免分母混入本仓不编译的代码。
# $1 输出白名单文件路径
gen_msprof_cov_whitelist() {
    local out_file="$1"
    local collector_dir="${BASEPATH}/src/msprof/collector"
    python3 - "$collector_dir" "$out_file" <<'PYEOF'
import os, re, sys
collector = sys.argv[1]
out_file = sys.argv[2]
dvvp = os.path.join(collector, "dvvp")
varmap = {
    "PROF_BASIC_DIR": os.path.join(collector, "basic"),
    "MSPROF_SOURCE_DIR": collector,
    "MSPROF_DIR": os.path.join(collector, "..", ".."),
}
def resolve(token, cmdir):
    m = re.match(r'\$\{([A-Z_]+)\}/(.*)', token)
    if m:
        var, rest = m.group(1), m.group(2)
        if var in varmap:
            return os.path.normpath(os.path.join(varmap[var], rest))
        return None
    if token.startswith("$"):
        return None
    return os.path.normpath(os.path.join(cmdir, token))
srcs = set()
for cm in [os.path.join(dvvp, "acp", "CMakeLists.txt"),
           os.path.join(dvvp, "msprofbin", "CMakeLists.txt")]:
    if not os.path.isfile(cm):
        continue
    cmdir = os.path.dirname(cm)
    txt = open(cm).read()
    for tok in re.findall(r'[^\s"()]+\.(?:cpp|c)\b', txt):
        p = resolve(tok, cmdir)
        if p and os.path.isfile(p):
            srcs.add(os.path.abspath(p))
with open(out_file, "w") as f:
    for s in sorted(srcs):
        f.write(s + "\n")
print("msprof cov whitelist: %d source files" % len(srcs))
PYEOF
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
            run_pytest_with_coverage "${case_name}" "./src/asys" "./test/st/asys/testcase" "${output_file}"
            ;;
        asys_ut)
            run_pytest_with_coverage "${case_name}" "./src/asys" "./test/ut/asys/testcase" "${output_file}"
            ;;
        msaicerr_st)
            run_pytest_with_coverage "${case_name}" "./src/msaicerr" "./test/st/msaicerr/testcase" "${output_file}"
            ;;
        msaicerr_ut)
            run_pytest_with_coverage "${case_name}" "./src/msaicerr" "./test/ut/msaicerr/testcase" "${output_file}"
            ;;
        msprof_ut)
            local msprof_ut_manifest="${BUILD_OUTPUT_DIR}/msprof_ut_targets.txt"
            local msprof_ut_rc=0
            : > "${output_file}"
            if [[ ! -f "${msprof_ut_manifest}" ]]; then
                echo "ERROR: msprof ut target manifest not found at ${msprof_ut_manifest}" | tee -a "${output_file}"
                echo "1" > "${BUILD_OUTPUT_DIR}/${case_name}.exitcode"
                return 1
            fi
            while IFS= read -r ut_bin; do
                [[ -z "${ut_bin}" ]] && continue
                if [[ -f "${ut_bin}" ]]; then
                    echo "----- running ${ut_bin} -----" >> "${output_file}"
                    "${ut_bin}" >> "${output_file}" 2>&1 || msprof_ut_rc=1
                else
                    echo "ERROR: msprof_utest binary not found at ${ut_bin}" | tee -a "${output_file}"
                    msprof_ut_rc=1
                fi
            done < "${msprof_ut_manifest}"
            echo ${msprof_ut_rc} > "${BUILD_OUTPUT_DIR}/${case_name}.exitcode"
            if [[ "${RUN_COV}" == "true" ]]; then
                local msprof_cov_whitelist="${BUILD_OUTPUT_DIR}/msprof_cov_files.txt"
                gen_msprof_cov_whitelist "${msprof_cov_whitelist}" >> "${output_file}" 2>&1
                collect_gcov_coverage "${case_name}" \
                    "${BUILD_OUTPUT_DIR}/test/ut/msprof" \
                    "${msprof_cov_whitelist}" "${output_file}"
            fi
            ;;
        install_st)
            run_pytest_plain "${case_name}" "./test/st/install/testcase" "${output_file}"
            ;;
        upgrade_st)
            run_pytest_plain "${case_name}" "./test/st/upgrade/testcase" "${output_file}"
            ;;
        uninstall_st)
            run_pytest_plain "${case_name}" "./test/st/uninstall/testcase" "${output_file}"
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

    # Check if chip_handler.py exists when asys component is involved
    # (chip_handler.py is generated by cmake configure from chip_handler.py.in)
    if [[ "$COMPONENT" == "asys" || "$COMPONENT" == "all" ]]; then
        if [[ ! -f "${BASEPATH}/src/asys/common/chip_handler.py" ]]; then
            echo "ERROR: chip_handler.py not found at ${BASEPATH}/src/asys/common/chip_handler.py"
            echo "This file is generated by cmake configure from chip_handler.py.in."
            echo "Please run cmake configure first:"
            echo "  mkdir -p build && cd build && cmake .. && cd .."
            exit 1
        fi
    fi

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
    ensure_run_package_for_st_cases "${test_cases[@]}" || exit 1

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
