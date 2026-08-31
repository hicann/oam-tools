#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
"""scripts/run_tests.sh 日志解析与覆盖率门禁的回归用例。

这套解析逻辑是纯 shell/awk，改动后极易无声回归，且它决定所有组件的 CI 结论。
本文件用固定样例日志把已踩过的坑钉住：标记被拼在行中间、GTEST_SKIP、日志含
非 UTF-8 字节、覆盖率缺失、79.75% 取整后不得算达标。
"""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest


def find_repo_root(start):
    """按标记文件向上查找仓库根；找不到返回 None（由调用方 skip）。"""
    for candidate in [start, *start.parents]:
        if (candidate / "scripts" / "run_tests.sh").is_file() \
                and (candidate / "CMakeLists.txt").is_file():
            return candidate
    return None


REPO_ROOT = find_repo_root(Path(__file__).resolve())
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(
    REPO_ROOT is None or BASH is None,
    reason="需要仓库根下的 scripts/run_tests.sh 与可用的 bash",
)

# 末行是 `main "$@"`，source 前必须去掉，否则会真的跑起测试。
DRIVER = r"""
set -o pipefail
sed '$ d' "{script}" > "{libfile}"
# shellcheck disable=SC1090
source "{libfile}"

BUILD_OUTPUT_DIR="{outdir}"
RUN_COV={run_cov}
COV_BELOW_BASELINE=()
COV_MISSING=()
{presets}

if [[ "{framework}" == "gtest" ]]; then
    validate_gtest_result "$BUILD_OUTPUT_DIR/{case}_output.log" "{case}" >/dev/null 2>&1
else
    validate_pytest_result "$BUILD_OUTPUT_DIR/{case}_output.log" "{case}" >/dev/null 2>&1
fi
apply_cov_baseline "{case}" >/dev/null 2>&1

echo "STATUS=${{R_STATUS[{case}]}}"
echo "PASSED=${{R_PASSED[{case}]}}"
echo "FAILED=${{R_FAILED[{case}]}}"
echo "SKIPPED=${{R_SKIPPED[{case}]}}"
echo "COV=${{R_COV[{case}]}}"
echo "BASELINE=${{COV_BASELINE}}"
echo "BELOW=${{COV_BELOW_BASELINE[*]}}"
echo "MISSING=${{COV_MISSING[*]}}"
echo "FAILLIST=$(echo "${{R_FAILLIST[{case}]}}" | tr '\n' ';')"
echo "NOTES=$(echo "${{R_NOTES[{case}]}}" | tr '\n' ';')"
"""


@dataclass
class Scenario:
    """一次解析场景的输入：样例日志 + 该用例集的运行环境。

    参数相关性强（同属"喂给解析函数的一次运行"），用具名形式封装而非平铺
    成 7 个位置参数。
    """

    case: str
    framework: str
    log_bytes: bytes
    exit_code: int
    run_cov: str = "false"
    presets: str = ""


def run_validator(tmp_path, scenario):
    """把样例日志喂给 run_tests.sh 的解析函数，回读结果数组。"""
    case = scenario.case
    framework = scenario.framework
    log_bytes = scenario.log_bytes
    exit_code = scenario.exit_code
    run_cov = scenario.run_cov
    presets = scenario.presets
    outdir = tmp_path / "build"
    outdir.mkdir(exist_ok=True)
    (outdir / f"{case}_output.log").write_bytes(log_bytes)
    (outdir / f"{case}.exitcode").write_text(f"{exit_code}\n", encoding="utf-8")

    script = DRIVER.format(
        script=REPO_ROOT / "scripts" / "run_tests.sh",
        libfile=tmp_path / "rt_lib.sh",
        outdir=outdir,
        run_cov=run_cov,
        presets=presets,
        framework=framework,
        case=case,
    )
    completed = subprocess.run(
        [BASH, "-c", script], capture_output=True, text=True, timeout=120, check=False,
    )
    assert completed.returncode == 0, (
        f"驱动脚本执行失败: rc={completed.returncode}\n{completed.stderr}"
    )

    result = {}
    for line in completed.stdout.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            result[key] = value
    # 自检：确认驱动真的跑到了解析逻辑，避免样例没被读取却"全部通过"
    assert result.get("STATUS"), f"未取到解析结果: {completed.stdout}"
    return result


GTEST_HEALTHY = b"""----- running /x/a_utest -----
[==========] Running 2 tests.
[ RUN      ] S.Plain
[       OK ] S.Plain (0 ms)
[ RUN      ] S.Second
[       OK ] S.Second (1 ms)
[  PASSED  ] 2 tests.
"""


def test_gtest_healthy_log_passes(tmp_path):
    res = run_validator(tmp_path, Scenario(case="msprof_ut", framework="gtest", log_bytes=GTEST_HEALTHY, exit_code=0))
    assert res["STATUS"] == "PASS"
    assert res["PASSED"] == "2"
    assert res["FAILED"] == "0"


def test_gtest_marker_glued_mid_line_still_counted(tmp_path):
    """被测代码 printf 未换行时，gtest 标记会被拼到行中间。

    曾因按行首锚定匹配而漏读这些 OK，把通过的用例判成"未完成"，
    进而把整个套件误报 CRASH（实测 msprof_ut ExitCode=0 却报崩溃）。
    """
    log = b"""----- running /x/a_utest -----
[ RUN      ] S.MidLine
==mmSysGetEnv==[id=7001,str=ACP_PIPE_FD][       OK ] S.MidLine (0 ms)
[ RUN      ] S.LeadingSpace
 [       OK ] S.LeadingSpace (0 ms)
[  PASSED  ] 2 tests.
"""
    res = run_validator(tmp_path, Scenario(case="msprof_ut", framework="gtest", log_bytes=log, exit_code=0))
    assert res["STATUS"] == "PASS", f"标记拼行被误判: {res}"
    assert res["PASSED"] == "2"


def test_gtest_skip_marker_not_treated_as_incomplete(tmp_path):
    """GTEST_SKIP() 只输出 [  SKIPPED ]，不输出 [ OK ]。

    漏处理该标记会让被跳过的用例滞留在"已启动未结束"集合里，
    使任何用到 GTEST_SKIP 的套件误报 CRASH。
    """
    log = b"""----- running /x/a_utest -----
[ RUN      ] S.Skipped
/x/foo.cc:12: Skipped
no device available
[  SKIPPED ] S.Skipped (0 ms)
[ RUN      ] S.Plain
[       OK ] S.Plain (0 ms)
[  PASSED  ] 1 test.
[  SKIPPED ] 1 test, listed below:
[  SKIPPED ] S.Skipped
  YOU HAVE 2 DISABLED TESTS
"""
    res = run_validator(tmp_path, Scenario(case="msprof_ut", framework="gtest", log_bytes=log, exit_code=0))
    assert res["STATUS"] == "PASS", f"GTEST_SKIP 被误判: {res}"
    assert res["PASSED"] == "1"
    # SKIPPED 两个来源都要计入：GTEST_SKIP 汇总 1 + DISABLED 2
    assert res["SKIPPED"] == "3", f"SKIPPED 计数错误: {res}"


def test_gtest_truncated_target_with_nonzero_exit_is_crash(tmp_path):
    """target 中途死掉：启动 2 个但只有 1 个打出收尾汇总行。"""
    log = b"""----- running /x/a_utest -----
[ RUN      ] S.Plain
[       OK ] S.Plain (0 ms)
[  PASSED  ] 1 test.
----- running /x/job_wrapper -----
[ RUN      ] JOB.Process
"""
    res = run_validator(tmp_path, Scenario(case="msprof_ut", framework="gtest", log_bytes=log, exit_code=1))
    assert res["STATUS"] == "CRASH", f"真截断未被识别: {res}"
    assert res["PASSED"] == "-", "崩溃时计数不可信，应显示 -"
    assert "1/2" in res["NOTES"], f"未报告 target 收尾比例: {res}"
    assert "job_wrapper" in res["NOTES"], f"未指出最后启动的二进制: {res}"


def test_gtest_target_marker_glued_to_previous_output(tmp_path):
    """上一个二进制末行无换行时，target 标记会被拼到该行中间。

    run_test_case 紧接在上一个二进制输出之后写该标记，若前者崩溃在 printf
    中途（末行没有 \\n），标记就被拼进那半行。按行首数 started 会少一个，
    恰好与 finished 相等——真截断反而判不出 CRASH，残缺的 passed/failed 被
    当完整数据展示。故写标记处必须前置 \\n。
    """
    log = (b"----- running /x/a_utest -----\n"
           b"[ RUN      ] S.A\n"
           b"[       OK ] S.A (0 ms)\n"
           b"[  PASSED  ] 1 test.\n"
           b"crash mid-printf no newline"          # 上一个 target 末行无换行
           b"\n----- running /x/b_utest -----\n"   # 写入处已前置 \n
           b"[ RUN      ] S.B\n")
    res = run_validator(tmp_path, Scenario(
        case="msprof_ut", framework="gtest", log_bytes=log, exit_code=1))
    assert res["STATUS"] == "CRASH", f"真截断未判 CRASH: {res}"
    assert "b_utest" in res["NOTES"], f"last target 指错二进制: {res}"


def test_marker_written_with_leading_newline():
    """写 target 标记必须用前置 \\n，保证它总从行首起。"""
    content = (REPO_ROOT / "scripts" / "run_tests.sh").read_text(encoding="utf-8")
    assert "printf '\\n----- running %s -----\\n'" in content, \
        "写 target 标记应前置 \\n，否则上一个二进制末行无换行时标记被拼行、漏判 CRASH"


def test_grep_guard_catches_forms_without_e_flag():
    """兜底扫描不能只认含 E 的选项串。

    读 $output_file 的 grep 也有 -o / -c / -q 乃至无选项的写法，漏掉它们会
    让这条守卫形同虚设——本 PR 加它正是为拦住"新增 grep 忘加 -a"的回归。
    """
    violating = [
        '    x=$(grep -o "FAILED" "$output_file")',
        '    grep -c "x" "$output_file"',
        '    if grep -q "x" "$output_file"; then',
        '    grep "x" "$output_file"',
    ]
    for line in violating:
        assert reads_log_without_a_flag(line), f"未识别出违规写法: {line.strip()}"

    compliant = [
        '    x=$(LC_ALL=C grep -aoE "y" "$output_file")',
        '    if LC_ALL=C grep -qaE "y" "$output_file"; then',
        '    grep -o "x" /other/file',
    ]
    for line in compliant:
        assert not reads_log_without_a_flag(line), f"合规写法被误报: {line.strip()}"


def test_gtest_missing_summary_but_clean_exit_is_not_crash(tmp_path):
    """退出码为 0 时不得因少收尾汇总行判 CRASH。

    任一 target 返回非零即置 exitcode=1，故 ExitCode=0 表示所有 gtest
    二进制都正常退出，而正常退出的 gtest 必然打印了收尾汇总行。此时
    grep 数不到只可能是标记被其它线程输出劈开的解析假象。
    """
    log = b"""----- running /x/a_utest -----
[ RUN      ] S.Plain
[       OK ] S.Plain (0 ms)
[  PASSED  ] 1 test.
----- running /x/b_utest -----
[ RUN      ] S.Other
[       OK ] S.Other (0 ms)
"""
    res = run_validator(tmp_path, Scenario(case="msprof_ut", framework="gtest", log_bytes=log, exit_code=0))
    assert res["STATUS"] == "PASS", f"退出码0却判崩溃: {res}"


def test_gtest_binary_bytes_do_not_break_counting(tmp_path):
    """日志含 NUL 字节时，grep 会把它判为 binary 文件。

    必须用 NUL（\\x00）而非任意高位字节：GNU grep 判定 binary 的依据是
    NUL，\\x80 这类高位字节不触发，用它写样例会让本用例空转。
    binary 判定生效时，不带 -a 的 grep -o 只打印 "binary file matches"，
    计数全部丢失、失败清单还会混入该假条目。
    """
    log = (b"----- running /x/a_utest -----\n"
           b"[ RUN      ] S.Plain\n"
           b"device raw output: \x00\x80\xff binary junk\n"
           b"[       OK ] S.Plain (0 ms)\n"
           b"[ RUN      ] S.Bad\n"
           b"[  FAILED  ] S.Bad (0 ms)\n"
           b"[  PASSED  ] 1 test.\n"
           b"[  FAILED  ] 1 test, listed below:\n"
           b"[  FAILED  ] S.Bad\n")
    res = run_validator(tmp_path, Scenario(case="msprof_ut", framework="gtest", log_bytes=log, exit_code=1))
    assert res["PASSED"] == "1", f"binary 日志导致计数丢失: {res}"
    assert res["FAILED"] == "1", f"binary 日志导致计数丢失: {res}"
    assert res["STATUS"] == "FAIL"
    # 失败清单要拿到用例名，且不得混入 "binary file matches" 假条目
    assert "S.Bad" in res["FAILLIST"], f"失败清单缺失用例名: {res}"
    assert "binary file" not in res["FAILLIST"].lower(), f"混入假条目: {res}"


def test_gtest_crash_marker_extracted_from_binary_log(tmp_path):
    """崩溃日志往往正是含 NUL 字节的那一类，marker 摘要不能为空。"""
    log = (b"----- running /x/a_utest -----\n"
           b"[ RUN      ] S.Boom\n"
           b"junk \x00\x80 bytes\n"
           b"Segmentation fault (core dumped)\n")
    res = run_validator(tmp_path, Scenario(case="msprof_ut", framework="gtest", log_bytes=log, exit_code=139))
    assert res["STATUS"] == "CRASH"
    assert "Segmentation fault" in res["NOTES"], f"crash marker 摘要为空: {res}"


def make_pytest_log(summary, total_line=None):
    body = f"test/x/test_a.py ....                            [100%]\n{summary}\n"
    if total_line is not None:
        body += f"Name    Stmts   Miss  Cover\n{total_line}\n"
    return body.encode("utf-8")


def test_pytest_counts_include_skipped(tmp_path):
    """曾漏解析 skipped，asys_st 的 74 个 skipped 完全不可见。"""
    log = make_pytest_log(
        "============ 281 passed, 74 skipped in 57.77s ============",
        "TOTAL    5017    653  85.00%",
    )
    res = run_validator(tmp_path, Scenario(case="asys_st", framework="pytest", log_bytes=log, exit_code=0))
    assert res["STATUS"] == "PASS"
    assert res["PASSED"] == "281"
    assert res["SKIPPED"] == "74", f"skipped 未被解析: {res}"


def test_pytest_coverage_7975_does_not_pass_baseline_80(tmp_path):
    """79.75% 不得算达标。

    coverage report 默认输出整数百分比会把 79.75 显示成 80，而基线判定
    正是读该行——取整会让未达标的覆盖率蒙混过关。故改用 --precision=2。
    """
    log = make_pytest_log(
        "============ 200 passed, 5 skipped in 12.30s ============",
        "TOTAL    4577    927  79.75%",
    )
    res = run_validator(tmp_path, Scenario(case="msaicerr_st", framework="pytest", log_bytes=log, exit_code=0))
    assert res["BASELINE"] == "80", f"基线应固定为 80: {res}"
    assert res["STATUS"] == "FAIL", f"79.75% 被误判为达标: {res}"
    assert "msaicerr_st" in res["BELOW"], f"未计入低于基线清单: {res}"


def test_pytest_coverage_just_above_baseline_passes(tmp_path):
    log = make_pytest_log(
        "============ 247 passed, 5 skipped in 12.30s ============",
        "TOTAL    4577    912  80.07%",
    )
    res = run_validator(tmp_path, Scenario(case="msaicerr_st", framework="pytest", log_bytes=log, exit_code=0))
    assert res["STATUS"] == "PASS", f"80.07% 应达标: {res}"
    assert res["BELOW"] == "", f"不应计入低于基线清单: {res}"


def test_pytest_coverage_missing_fails_for_suite_that_should_collect(tmp_path):
    """覆盖率采集失败不得绕过门禁。

    原先见 "-" 即跳过校验，使 coverage report/lcov 失败时只要用例通过
    就 PASS、退出码 0——门禁在最该拦的时候失效。
    """
    log = make_pytest_log(
        "============ 200 passed in 12.30s ============",
    ) + b"No data to report.\n"
    res = run_validator(tmp_path, Scenario(case="msaicerr_st", framework="pytest", log_bytes=log, exit_code=0))
    assert res["STATUS"] == "FAIL", f"覆盖率缺失被放行: {res}"
    assert "msaicerr_st" in res["MISSING"], f"未计入缺失清单: {res}"
    assert "coverage expected" in res["NOTES"], f"未说明缺失原因: {res}"


def test_pytest_no_coverage_scope_suite_is_not_gated(tmp_path):
    """install/upgrade/uninstall ST 走 run_pytest_plain，本无覆盖率口径。

    与"应产出却缺失"必须区分，否则会把无口径的套件误判为 FAIL。
    """
    log = make_pytest_log("============ 7 passed in 65.57s ============")
    res = run_validator(tmp_path, Scenario(case="install_st", framework="pytest", log_bytes=log, exit_code=0))
    assert res["STATUS"] == "PASS", f"无覆盖率口径的套件被门禁误伤: {res}"
    assert res["COV"] == "-"
    assert res["MISSING"] == "", f"不应计入缺失清单: {res}"


def test_msprof_coverage_not_gated_without_cov_flag(tmp_path):
    """msprof 的 gcov 受 --cov 门控，未开启时不应要求覆盖率。"""
    res = run_validator(tmp_path, Scenario(
        case="msprof_ut", framework="gtest", log_bytes=GTEST_HEALTHY,
        exit_code=0, run_cov="false"))
    assert res["STATUS"] == "PASS"
    assert res["MISSING"] == "", f"未开 --cov 却要求 msprof 覆盖率: {res}"


def test_msprof_coverage_gated_with_cov_flag(tmp_path):
    """开了 --cov 时 msprof 必须有覆盖率，缺失即判 FAIL。"""
    res = run_validator(tmp_path, Scenario(
        case="msprof_ut", framework="gtest", log_bytes=GTEST_HEALTHY,
        exit_code=0, run_cov="true"))
    assert res["STATUS"] == "FAIL", f"开 --cov 但覆盖率缺失应判 FAIL: {res}"
    assert "msprof_ut" in res["MISSING"]


def test_msprof_coverage_below_baseline_fails(tmp_path):
    """gcov 覆盖率低于基线同样判 FAIL（预置 R_COV 模拟 lcov 结果）。"""
    res = run_validator(tmp_path, Scenario(
        case="msprof_ut", framework="gtest", log_bytes=GTEST_HEALTHY,
        exit_code=0, run_cov="true", presets='R_COV[msprof_ut]=79.90'))
    assert res["STATUS"] == "FAIL", f"79.90% 应低于基线 80: {res}"
    assert "msprof_ut" in res["BELOW"]


def test_coverage_report_requests_two_decimal_precision():
    """脚本必须给 coverage report 传 --precision=2。

    上面的 79.75% 用例只能证明"比较逻辑对 79.75 判 FAIL"，证明不了脚本
    真的取到了两位小数——样例日志是直接写入 TOTAL 行的，coverage report
    并未执行。少了这个 flag，实际运行时 79.75% 会被 coverage 显示成 80%，
    基线判定读该行即误判达标。故用静态断言把 flag 钉住。
    """
    content = (REPO_ROOT / "scripts" / "run_tests.sh").read_text(encoding="utf-8")
    assert "coverage report --precision=2" in content, \
        "coverage report 缺少 --precision=2，整数百分比会把 79.75% 显示成 80%"


def test_coverage_dirs_cleaned_before_collection():
    """采集前必须清理旧覆盖率产物，否则复跑会读到上一次的结果。

    只 mkdir -p 时，本次 coverage run / lcov 失败后，coverage report /
    lcov --summary 仍会读到上一轮遗留的 .coverage / coverage.info，给出一个
    "看起来达标"的百分比——连"应产出却缺失判 FAIL"的门禁也一并绕过。
    实测：留下旧 .coverage 后不执行 coverage run，report 照样输出 66.67%。
    """
    content = (REPO_ROOT / "scripts" / "run_tests.sh").read_text(encoding="utf-8")
    # pytest 与 gcov 两条采集路径都要清理
    assert content.count('rm -rf "${cov_dir}"') >= 2, \
        "pytest 与 gcov 两处采集前都应 rm -rf 覆盖率目录，防止读到旧产物"
    for marker in ('rm -rf "${cov_dir}" "${BUILD_OUTPUT_DIR}/${case_name}_html"',
                   'rm -rf "${cov_dir}" "${html_dir}"'):
        assert marker in content, f"缺少清理语句: {marker}"


def test_stale_gcda_cleared_before_binaries_run():
    """跑 gtest 前必须清掉 capture_dir 里的旧 .gcda，且必须在运行之前清。

    gcov 计数是累加的：同一个 build tree 复跑时，上一轮的 .gcda 会被本轮
    lcov -c 一起采走，本次没覆盖到的代码也算已覆盖，把 80% 门禁顶上去。
    位置是这条断言的重点——挪到运行之后（如放进 collect_gcov_coverage）
    删掉的就是本轮自己的数据，覆盖率反而变 0。故同时钉住"有清理"与
    "清理在运行之前"。删除目标必须只是 *.gcda：.gcno 是编译期插桩产物，
    一并删掉就没有插桩信息，lcov -c -i 取不到基线。
    """
    content = (REPO_ROOT / "scripts" / "run_tests.sh").read_text(encoding="utf-8")
    clean_stmt = "-name '*.gcda' -type f -delete"
    clean_idx = content.find(clean_stmt)
    assert clean_idx != -1, "gtest 采集路径缺少旧 .gcda 清理，复跑会累加上一轮覆盖率"
    assert "gcno" not in clean_stmt, "删除语句只能匹配 .gcda，不可扩到 .gcno"
    run_idx = content.find('"${ut_bin}" 2>&1 | tee -a "${output_file}"')
    assert run_idx != -1, "未找到 gtest 二进制运行语句，本用例的位置断言已失效"
    assert clean_idx < run_idx, \
        ".gcda 清理必须在二进制运行之前，否则删掉的是本轮自己的覆盖率数据"


def find_grep_short_opts(line):
    """取第一个短选项串（形如 -aoE / -qa / -c）；没有则返回 None。

    不能只认含 E 的选项串：读 $output_file 的 grep 也有 -o / -c / -q 这类
    不带 E 的写法，漏掉它们会让本文件的兜底扫描形同虚设。
    """
    for token in line.split():
        if token.startswith("-") and not token.startswith("--"):
            return token
    return None


def reads_log_without_a_flag(line):
    """该行是否在读 $output_file 却漏了 -a。

    取不到短选项串时也判违规：没有任何选项的 grep（如 grep "x" file）同样
    会在 binary 日志上失效，不能因"识别不出选项"就放过。
    """
    if '"$output_file"' not in line or "grep" not in line:
        return False
    opts = find_grep_short_opts(line)
    return opts is None or "a" not in opts


def test_log_reading_greps_are_binary_safe():
    """凡读 $output_file 的 grep 都要带 -a。

    设备侧日志可能含 NUL 字节而被 grep 判为 binary，此时提取类 grep 只会
    输出 "binary file matches"、内容全丢。上面的 NUL 用例覆盖了计数与
    crash marker 两条路径，这里再做整体扫描，防止新增 grep 时漏加。
    """
    content = (REPO_ROOT / "scripts" / "run_tests.sh").read_text(encoding="utf-8")
    offenders = [
        f"{lineno}: {line.strip()}"
        for lineno, line in enumerate(content.splitlines(), start=1)
        if reads_log_without_a_flag(line)
    ]
    assert not offenders, "以下读日志的 grep 缺少 -a：\n" + "\n".join(offenders)


def test_importerror_text_in_log_does_not_fail_passing_suite(tmp_path):
    """日志正文出现 ImportError 字样不得让全通过的套件判 FAIL。

    这两类日志里该字样是预期输出，不是故障：
      - 用例故意验证异常路径（如 test_get_compile_from_tik_import_error）；
      - 环境缺可选依赖时被测代码自己 catch 后打 WARNING。
    实测曾因扫正文把 704 passed / 0 failed 判成 FAIL，且失败清单为空——
    报了个查不下去的错。pytest 的 failed/error 计数才是权威信号。
    """
    log = (b"WARNING: failed to import te or tbe to compile op, skipped it. "
           b"error: ImportError: No module named 'te'\n"
           b"Traceback (most recent call last):\n"
           b"  File \"x.py\", line 1, in <module>\n"
           b"============ 704 passed, 15 skipped in 12.41s ============\n"
           b"Name    Stmts   Miss  Cover\nTOTAL    4577    457  90.00%\n")
    res = run_validator(tmp_path, Scenario(
        case="msaicerr_ut", framework="pytest", log_bytes=log, exit_code=0))
    assert res["STATUS"] == "PASS", f"日志含 ImportError/Traceback 字样被误判: {res}"
    assert res["PASSED"] == "704"


def test_real_collection_error_still_fails(tmp_path):
    """真实的导入失败会被 pytest 计为 collection error，仍须判 FAIL。"""
    log = (b"ImportError while importing test module 'test_x.py'\n"
           b"============ 1 error in 0.30s ============\n"
           b"Name    Stmts   Miss  Cover\nTOTAL    4577    457  90.00%\n")
    res = run_validator(tmp_path, Scenario(
        case="msaicerr_ut", framework="pytest", log_bytes=log, exit_code=2))
    assert res["STATUS"] == "FAIL", f"真实 collection error 未判 FAIL: {res}"
    assert "collection/runner error" in res["NOTES"], f"未说明原因: {res}"


def test_pytest_failed_case_list_strips_prefix(tmp_path):
    log = make_pytest_log(
        "============ 2 failed, 547 passed in 51.48s ============",
        "TOTAL    5017    653  87.00%",
    ) + (b"=========== short test summary info ===========\n"
         b"FAILED test/ut/x/test_a.py::test_one - AssertionError: boom\n"
         b"FAILED test/ut/x/test_a.py::test_two - AssertionError: bam\n")
    res = run_validator(tmp_path, Scenario(case="asys_ut", framework="pytest", log_bytes=log, exit_code=1))
    assert res["STATUS"] == "FAIL"
    assert res["FAILED"] == "2"
    assert "test_one" in res["FAILLIST"]
    # 区块标题已说明是失败用例，清单里不该再重复 FAILED 前缀
    assert "FAILED test" not in res["FAILLIST"], f"未去掉前缀: {res}"
