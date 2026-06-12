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
"""增量行 codecheck 钩子。

云端 codecheck 是增量的（只查 PR 改动的行），本地若整文件放开这些规则会被
存量违规淹没（本仓存量遍地超长行/超大函数/print），比云端更严、堵死提交。
本钩子用 ruff 全量检查后，只保留命中【本次 staged 改动行】的告警，从而在本地
复现云端增量行为：push 前预警自己引入的违规，又不被存量违规阻塞。

统一用 ruff（一个工具、速度快），select 一组对应云端华为 codecheck 的规则：
- E501    line-too-long              → G.FMT.02 行宽不超过 120
- PLR0915 too-many-statements        → 超大函数
- PLR6301 no-self-use(preview)       → G.CLS.07 应为 staticmethod/classmethod
- T201    print                      → G.LOG.02 使用 logging 而非 print
- S607    start-process-partial-path → G.EDV.05 调外部程序用绝对路径
- PLR1722 sys-exit-alias             → G.ERR.11 相关（避免裸 sys.exit/exit）

（重复代码 R0801 为跨文件块级，ruff 不查；其余华为专有规则若 ruff 无对应，
仍以云端结果为准。新增可查规则时，往 RULES 里追加即可。）
"""
import logging
import shutil
import subprocess
import sys

logger = logging.getLogger("incremental_codecheck")

# 选中的 ruff 规则集（逗号分隔）；max-line-length 与云端一致为 120。
RULES = "E501,T201,S607,PLR0915,PLR6301,PLR1722"
MAX_LINE = "120"


def staged_added_lines(path):
    """返回 path 在 staged diff 中新增/修改的行号集合（新文件侧行号）。"""
    # G.EDV.05：用绝对路径调外部程序，git 不在 PATH 时直接报错而非静默退化。
    git_bin = shutil.which("git")
    if not git_bin:
        logger.error("git not found in PATH")
        return set()
    out = subprocess.run(
        [git_bin, "diff", "--cached", "--unified=0", "--", path],
        capture_output=True, text=True, check=False,
    ).stdout
    added = set()
    new_ln = 0
    for line in out.splitlines():
        if line.startswith("@@"):
            # 形如 @@ -a,b +c,d @@
            seg = line.split("+", 1)[1].split("@@", 1)[0].strip()
            start = int(seg.split(",")[0])
            new_ln = start
        elif line.startswith("+") and not line.startswith("+++"):
            added.add(new_ln)
            new_ln += 1
        elif line.startswith("-") and not line.startswith("---"):
            pass
        else:
            new_ln += 1
    return added


def ruff_msgs(path):
    """跑 ruff，返回 [(lineno, text)]，只含 RULES 选中的规则。

    用 sys.executable -m ruff 调用（sys.executable 为绝对路径，满足 G.EDV.05，
    且不依赖 PATH）。--preview 为开启 PLR6301（no-self-use 属 preview）；配合
    --select 限定后只报选中规则，不会引入其他 preview 规则的噪声（已实测）。
    """
    proc = subprocess.run(
        [
            sys.executable, "-m", "ruff", "check",
            "--preview",
            f"--select={RULES}",
            f"--line-length={MAX_LINE}",
            "--output-format=concise",
            "--no-cache",
            path,
        ],
        capture_output=True, text=True, check=False,
    )
    # ruff 退出码：0=无诊断、1=有诊断（均为正常结果）；>=2 表示工具/配置错误
    # （如非法规则、参数错误）。但 `python -m ruff` 在 ruff 模块缺失/启动失败时也
    # 可能返回 1（stderr 有错、stdout 为空），若按"有诊断"解析空 stdout 会静默放行。
    # 故：>=2 直接判工具错误；==1 时再以 "stdout 为空且 stderr 非空" 兜底判启动失败。
    tool_error = proc.returncode >= 2 or (
        proc.returncode == 1 and not proc.stdout.strip() and proc.stderr.strip()
    )
    if tool_error:
        raise RuntimeError(
            f"ruff 执行失败 (exit={proc.returncode})，本地增量门禁不可靠：\n{proc.stderr.strip()}"
        )
    msgs = []
    for line in proc.stdout.splitlines():
        # concise 格式：path:line:col: CODE message
        parts = line.split(":", 3)
        if len(parts) == 4 and parts[1].isdigit():
            msgs.append((int(parts[1]), parts[3].strip()))
    return msgs


def main(argv):
    files = [f for f in argv if f.endswith(".py")]
    if not files:
        return 0
    hits = []
    for path in files:
        added = staged_added_lines(path)
        if not added:
            continue
        for lineno, text in ruff_msgs(path):
            if lineno in added:
                hits.append(f"{path}:{lineno}: {text}")
    if hits:
        logger.warning("[incremental-codecheck] 本次改动行命中云端规则，请修复：")
        for h in hits:
            logger.warning("  %s", h)
        logger.warning("（仅检查你改动的行，不含存量违规；规则: %s）", RULES)
        return 1
    return 0


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
    sys.exit(main(sys.argv[1:]))
