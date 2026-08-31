#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
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

# ruff: noqa: E501, S607, PLR0915, PLR6301, PLR1722  # test mock methods, partial paths, long lines

# pylint: disable=protected-access,redefined-outer-name,attribute-defined-outside-init,unused-argument,broad-exception-caught,unused-import,unused-variable,redefined-builtin,reimported,no-member,function-redefined,possibly-used-before-assignment,no-self-argument,too-many-function-args,unexpected-keyword-arg,no-value-for-parameter  # pytest fixture/mock/cleanup patterns

"""看护"编译产物目录在编译后可被删除"。

背景：打包声明若把目录权限收紧到 555（r-xr-xr-x，无 owner 写位），这些目录会
连同 build/_CPack_Packages/ 下的 staging 子树一起落地。unlink 一个条目要的是
**父目录**的写位，父目录缺 u+w 就删不掉里面的内容——于是 `rm -rf build` 全程
Permission denied。这与 root 无关：目录属主本就是当前用户，属主自己也删不掉。

后果是 CI 随机失败：流水线复用工作区，下一轮清理残留 build/ 时删不掉即报错，
失败与否取决于上一轮是否跑到了产出 555 目录的打包阶段，故表现为随机。

因此打包期不再声明去掉 owner 写位的目录权限（当前做删除处理）；权限收紧的
整改由后续需求统一处理，届时需连带解决产物目录的可删除性。

本用例两层看护：
1. 静态扫描仓内 cmake 声明，禁止再引入"目录权限缺 owner 写位"的声明；
2. 验证机制本身——缺 u+w 的目录树删不掉，补上 u+w 后可删，对应 build.sh
   里 safe_rm_dir 先 chmod -R u+w 再 rm 的兜底做法。
"""

import os
import re
import shutil
import stat
from pathlib import Path

import pytest


# 仓库根标记：这三者同时存在才认定为 oam-tools 仓库根。
REPO_ROOT_MARKERS = ("CMakeLists.txt", "build.sh", "cmake")


def find_repo_root():
    """从本文件向上搜索仓库根，找不到返回 None。

    不按固定层级数推算：用例文件可能被拷到不同深度执行（云端流水线的工作区
    布局与本地不一致），硬编码 parents[N] 会算到不存在的路径上——此时扫不到
    任何文件、违规列表恒为空，看护会静默通过。

    找不到时返回 None 而非抛异常：模块级抛异常会让 pytest 在**收集阶段**报
    ERROR 并中断整个会话（连带其他用例一起挂），影响面远大于本用例本身。
    改由各用例调 require_repo_root() 显式 skip。
    """
    for candidate in Path(__file__).resolve().parents:
        if all((candidate / marker).exists() for marker in REPO_ROOT_MARKERS):
            return candidate
    return None


REPO_ROOT = find_repo_root()


def require_repo_root():
    """静态扫描类用例的前置：拿不到仓库根就 skip，并说清原因。"""
    if REPO_ROOT is None:
        pytest.skip(
            f"未能从 {Path(__file__).resolve()} 向上找到仓库根"
            f"（标记：{', '.join(REPO_ROOT_MARKERS)}），跳过仓内 cmake 静态扫描"
        )
    return REPO_ROOT


# 显式列出要递归扫描的子树（外加仓库根下的 CMakeLists.txt），避免全仓 rglob
# 扫进 build/ 等构建产物与 third_party/、submodule/、bundle/ 等非本仓管控目录。
SCAN_SUBTREES = ("cmake", "src", "test", "scripts")

# 目录权限声明里必须出现的 owner 写位关键字。
OWNER_WRITE_KEYWORD = "OWNER_WRITE"

# 只匹配**递归** chmod 的数字模式（如 chmod -R 555 / chmod -R 0555）。
# 不查非递归 chmod：单个文件设成只读（chmod 440 some_file）是合法用法，
# 且文件无写位不影响删除——unlink 只看父目录写位。批量收紧目录权限惯用 -R，
# 本用例要防的正是这类（历史上的 chmod -R 555 "${_msprof_dir}"）。
CHMOD_MODE_PATTERN = re.compile(r"chmod\s+-R\s+([0-7]{3,4})\b")


def iter_cmake_files():
    """遍历仓内自有的 CMakeLists.txt 与 *.cmake（不含构建产物/三方件目录）。"""
    repo_root = require_repo_root()
    yield repo_root / "CMakeLists.txt"
    for subtree in SCAN_SUBTREES:
        root = repo_root / subtree
        if not root.is_dir():
            continue
        yield from sorted(root.rglob("CMakeLists.txt"))
        yield from sorted(root.rglob("*.cmake"))


# install(DIRECTORY) 的合法关键字（cmake 官方签名，含 MESSAGE_NEVER）。
# 用作 DIRECTORY_PERMISSIONS 权限串的终止边界，避免跨声明匹配。
INSTALL_DIRECTORY_KEYWORDS = (
    "TYPE",
    "DESTINATION",
    "FILE_PERMISSIONS",
    "DIRECTORY_PERMISSIONS",
    "USE_SOURCE_PERMISSIONS",
    "OPTIONAL",
    "MESSAGE_NEVER",
    "CONFIGURATIONS",
    "COMPONENT",
    "EXCLUDE_FROM_ALL",
    "FILES_MATCHING",
    "PATTERN",
    "REGEX",
    "EXCLUDE",
    "PERMISSIONS",
)


def iter_directory_permission_decls():
    """抽取所有 DIRECTORY_PERMISSIONS 声明，产出 (文件, 权限关键字串)。"""
    # 权限关键字连续出现，直到遇到下一个 install(DIRECTORY) 关键字或右括号为止。
    pattern = re.compile(
        r"DIRECTORY_PERMISSIONS\s+(.*?)(?=\b(?:"
        + "|".join(INSTALL_DIRECTORY_KEYWORDS)
        + r")\b|\))",
        re.S,
    )
    for path in iter_cmake_files():
        content = path.read_text(encoding="utf-8")
        for match in pattern.finditer(content):
            yield path, match.group(1)


def test_scan_actually_finds_cmake_files():
    # 自检：下面两条静态看护靠"扫出违规才报错"，若路径算错导致一个文件都扫不到，
    # 违规列表恒为空、用例会静默通过——看护形同虚设。故先确认扫描确实有产出，
    # 且顶层 CMakeLists.txt（本次改动所在文件）在扫描范围内。
    repo_root = require_repo_root()
    files = list(iter_cmake_files())
    assert files, f"未扫到任何 cmake 文件，仓库根可能算错：{repo_root}"
    top_level = repo_root / "CMakeLists.txt"
    assert top_level.is_file(), f"仓库根缺少 CMakeLists.txt：{top_level}"
    assert top_level in files, "顶层 CMakeLists.txt 未被纳入扫描范围"
    # 不断言"仓内必须存在 DIRECTORY_PERMISSIONS 声明"：把仓内声明清理干净是本
    # 看护乐见的结果，不该因此报错。这里只校验扫描链路本身通着——代码行能读出来，
    # 且顶层 CMakeLists.txt 的内容确实被读到（而非读成空）。
    code_lines = list(iter_cmake_code_lines())
    assert code_lines, "未读出任何 cmake 代码行，扫描链路可能失效"
    assert any(rel == Path("CMakeLists.txt") for rel, _ in code_lines), (
        "顶层 CMakeLists.txt 的内容未被读到"
    )


def test_no_directory_permission_decl_drops_owner_write():
    # 关键看护：任何 DIRECTORY_PERMISSIONS 声明都必须含 OWNER_WRITE，
    # 否则落地的目录缺 u+w，其内容无法被 unlink，build/ 删不掉。
    repo_root = require_repo_root()
    offenders = []
    for path, perms in iter_directory_permission_decls():
        if OWNER_WRITE_KEYWORD not in perms:
            rel = path.relative_to(repo_root)
            offenders.append(f"{rel}: DIRECTORY_PERMISSIONS {' '.join(perms.split())}")
    assert not offenders, (
        "以下 DIRECTORY_PERMISSIONS 声明缺少 OWNER_WRITE，会造出无法删除的目录：\n"
        + "\n".join(offenders)
    )


def iter_cmake_code_lines():
    """产出 (相对路径, 代码行)，跳过整行注释。"""
    repo_root = require_repo_root()
    for path in iter_cmake_files():
        rel = path.relative_to(repo_root)
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in (ln for ln in lines if not ln.lstrip().startswith("#")):
            yield rel, line


def iter_chmod_modes_without_owner_write(line):
    """产出该行里摘掉 owner 写位的递归 chmod 数字模式。owner 位含写位即 2/3/6/7。"""
    for mode in CHMOD_MODE_PATTERN.findall(line):
        if not int(mode[-3]) & 0o2:
            yield mode


def test_no_cmake_chmod_strips_owner_write():
    # 打包期不得用递归 chmod 把目录写位摘掉（如 chmod -R 555/550/444/440），
    # 否则等价于上一条的后果。非递归 chmod（多为单个文件）不在检查范围。
    offenders = []
    for rel, line in iter_cmake_code_lines():
        for mode in iter_chmod_modes_without_owner_write(line):
            offenders.append(f"{rel}: chmod {mode} ({line.strip()})")
    assert not offenders, (
        "以下 chmod 摘掉了 owner 写位，会造出无法删除的目录：\n" + "\n".join(offenders)
    )


@pytest.mark.skipif(
    os.geteuid() == 0,
    reason="root 有 CAP_DAC_OVERRIDE，绕过权限位检查，555 目录下 rmtree 照样成功，"
    "无法复现普通用户的 PermissionError（云端 UT 以 root 运行）",
)
def test_dir_without_owner_write_blocks_removal(tmp_path):
    # 机制验证：父目录缺 u+w 时，其中的条目无法 unlink，rm -rf 失败。
    # 这正是 555 目录导致 build/ 删不掉、CI 随机失败的根因。
    #
    # 注意：本条只在**普通用户**下成立。root 不受权限位约束，故上面 skipif；
    # 真正的看护由上面两条静态扫描承担，它们与运行身份无关。
    staging = tmp_path / "staging"
    inner = staging / "tbe"
    inner.mkdir(parents=True)
    (inner / "op.py").write_text("# payload", encoding="utf-8")

    # 收紧为 555（r-xr-xr-x）：可读可遍历，但无写位。
    inner.chmod(0o555)
    try:
        assert not inner.stat().st_mode & stat.S_IWUSR, (
            "用例前提失败：目录仍带 owner 写位"
        )
        with pytest.raises(PermissionError):
            shutil.rmtree(staging)
        assert inner.exists(), "缺 u+w 的目录树本应删除失败"
    finally:
        # 恢复写位，避免 tmp_path 清理阶段再次失败。目录可能已被删掉
        # （如断言未按预期成立），故先判存在再 chmod——否则这里抛
        # FileNotFoundError 会盖住上面断言的真实失败原因。
        if inner.is_dir():
            inner.chmod(0o755)  # nosec B103  # test asserts permission-mask behavior


def test_restoring_owner_write_makes_dir_removable(tmp_path):
    # 兜底做法验证：给目录补回 u+w 后即可删除。
    #
    # 本条只验证"补 u+w 能让目录树可删"这一机制可行性，不验证 build.sh 里
    # safe_rm_dir 的具体实现——后者由 test_build_script.py 的
    # test_safe_rm_dir_defined 静态断言看护（含 `chmod -R u+w` 与 `rm -r`）。
    # 这里用 os.chmod 递归改权限而非调外部 chmod：chmod 在不同发行版下路径不同
    # （/bin 或 /usr/bin），写死绝对路径会在部分环境抛 FileNotFoundError。
    staging = tmp_path / "staging"
    inner = staging / "profiler_tool"
    inner.mkdir(parents=True)
    (inner / "msprof.py").write_text("# payload", encoding="utf-8")
    inner.chmod(0o555)

    for path in (staging, *staging.rglob("*")):
        if path.is_dir():
            path.chmod(path.stat().st_mode | stat.S_IWUSR)
    shutil.rmtree(staging)
    assert not staging.exists(), "补上 u+w 后目录树应能删除"
