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
"""看护 entity 子树的 install(DIRECTORY) 必须显式声明文件权限。

XML 对 tools/{asys,msaicerr,hccl_test,operator_cmp,profiler} 与
opp/built-in/op_impl 这几棵树声明了 entity="true"，run 包安装期由
install_common_parser.sh 的 reset_mod_dirs_recursive 递归赋权收口；但 rpm/deb 的
postinst 由 cann-cmake gen_postinst_prerm.py 生成，该脚本不认识 entity 语义，
只对 XML 逐条枚举到的路径发一条不带 -R 的 chmod，树内文件保留**打包期**权限。

于是打包期没显式声明权限的子树，在 rpm/deb 里就会停在 cmake 默认的 644
（历史上 asys/msaicerr/hccl_test/operator_cmp 即如此），显式声明成 440 的会
停在 440（历史上 opp/built-in 即如此）——非 root 用户读不到算子源码。
故这几处必须在打包期就把文件权限写对，不能依赖安装期递归。
"""
import re
from pathlib import Path

import pytest


REPO_ROOT_MARKERS = ("CMakeLists.txt", "build.sh", "cmake")


def find_repo_root():
    """从本文件向上搜索仓库根，找不到返回 None。

    不按固定层级数推算：用例文件可能被拷到不同深度执行，硬编码 parents[N] 会算到
    不存在的路径上，扫不到任何文件时看护会静默通过。找不到时返回 None 而非抛异常，
    避免模块级异常让 pytest 在收集阶段中断整个会话。
    """
    for candidate in Path(__file__).resolve().parents:
        if all((candidate / marker).exists() for marker in REPO_ROOT_MARKERS):
            return candidate
    return None


REPO_ROOT = find_repo_root()

# 待看护的 entity 子树：(文件, DESTINATION 里用于定位该规则的片段)。
# 片段取 DESTINATION 原文而非展开后路径——展开依赖 INSTALL_TOOLS_DIR 的取值。
ENTITY_TREES = (
    ("src/asys/CMakeLists.txt", "${INSTALL_TOOLS_DIR}/ascend_system_advisor"),
    ("src/msaicerr/CMakeLists.txt", "${INSTALL_TOOLS_DIR}/msaicerr"),
    ("src/hccl_test/CMakeLists.txt", "${INSTALL_TOOLS_DIR}"),
    ("src/operator_cmp/CMakeLists.txt", "${INSTALL_TOOLS_DIR}"),
    ("CMakeLists.txt", "opp/built-in/op_impl/ai_core"),
)

# 安装后必须可被任意用户读取并进入（555）。缺 WORLD_READ 即非 root 读不到。
REQUIRED_PERMISSION_KEYWORDS = (
    "OWNER_READ", "OWNER_EXECUTE",
    "GROUP_READ", "GROUP_EXECUTE",
    "WORLD_READ", "WORLD_EXECUTE",
)

# install(DIRECTORY) 合法关键字，用作 FILE_PERMISSIONS 权限串的终止边界。
INSTALL_DIRECTORY_KEYWORDS = (
    "TYPE", "DESTINATION", "FILE_PERMISSIONS", "DIRECTORY_PERMISSIONS",
    "USE_SOURCE_PERMISSIONS", "OPTIONAL", "MESSAGE_NEVER", "CONFIGURATIONS",
    "COMPONENT", "EXCLUDE_FROM_ALL", "FILES_MATCHING", "PATTERN", "REGEX",
    "EXCLUDE", "PERMISSIONS",
)

_FILE_PERMS_RE = re.compile(
    r"FILE_PERMISSIONS\s+(.*?)(?=\b(?:"
    + "|".join(INSTALL_DIRECTORY_KEYWORDS)
    + r")\b|\))",
    re.S,
)


def require_repo_root():
    if REPO_ROOT is None:
        pytest.skip(
            f"未能从 {Path(__file__).resolve()} 向上找到仓库根"
            f"（标记：{', '.join(REPO_ROOT_MARKERS)}），跳过仓内 cmake 静态扫描"
        )
    return REPO_ROOT


def find_statement_end(content, start):
    """从 start 起按括号配平找 install(...) 的收尾右括号，返回其下标。

    只遍历括号字符本身、并用条件表达式累计深度，避免多层嵌套分支。
    未配平（源码被截断）时返回 -1。
    """
    depth = 0
    for match in re.finditer(r"[()]", content[start:]):
        depth += 1 if match.group() == "(" else -1
        if depth == 0:
            return start + match.end() - 1
    return -1


def iter_install_directory_blocks(content):
    """按括号配平切出每个 install(DIRECTORY ...) 语句体。

    不用正则截到第一个 ')'：权限串里的 ${VAR} 与嵌套括号会让贪婪/非贪婪两种写法
    都截错边界。
    """
    for match in re.finditer(r"install\s*\(\s*DIRECTORY", content):
        end = find_statement_end(content, match.start())
        if end != -1:
            yield content[match.start():end + 1]


@pytest.mark.parametrize("relative_path, destination_hint", ENTITY_TREES)
def test_entity_tree_declares_world_readable_file_permissions(
    relative_path, destination_hint
):
    repo_root = require_repo_root()
    cmake_file = repo_root / relative_path
    assert cmake_file.is_file(), f"{relative_path} 不存在"
    content = cmake_file.read_text(encoding="utf-8")

    blocks = [
        block
        for block in iter_install_directory_blocks(content)
        if destination_hint in block
    ]
    # 自检：扫不到规则说明定位片段过时，必须失败而非静默通过。
    assert blocks, (
        f"{relative_path} 中未找到 DESTINATION 含 {destination_hint} 的 "
        f"install(DIRECTORY) 规则，看护定位片段可能已过时"
    )

    for block in blocks:
        declared = _FILE_PERMS_RE.search(block)
        assert declared is not None, (
            f"{relative_path}: entity 子树（{destination_hint}）的 install(DIRECTORY) "
            f"未声明 FILE_PERMISSIONS，rpm/deb 下文件会停在 cmake 默认 644"
        )
        perms = declared.group(1)
        missing = [
            keyword
            for keyword in REQUIRED_PERMISSION_KEYWORDS
            if keyword not in perms
        ]
        assert not missing, (
            f"{relative_path}: entity 子树（{destination_hint}）的 FILE_PERMISSIONS "
            f"缺 {', '.join(missing)}，安装后非 root 用户可能无法读取/执行"
        )


def iter_scanned_cmake_files(repo_root):
    """产出参与扫描的仓内 cmake 文件（仓库根 CMakeLists.txt 与 src、cmake 子树）。"""
    candidates = (
        [repo_root / "CMakeLists.txt"]
        + sorted((repo_root / "src").rglob("CMakeLists.txt"))
        + sorted((repo_root / "cmake").rglob("*.cmake"))
    )
    return [candidate for candidate in candidates if candidate.is_file()]


def iter_world_unreadable_perms(content):
    """产出该文件内缺 WORLD_READ 的 FILE_PERMISSIONS 权限串。"""
    for block in iter_install_directory_blocks(content):
        declared = _FILE_PERMS_RE.search(block)
        if declared is not None and "WORLD_READ" not in declared.group(1):
            yield " ".join(declared.group(1).split())


def test_no_owner_group_read_only_file_permissions():
    """仓内不得再出现"只给 owner/group 读"（440 形态）的文件权限声明。

    440 在 rpm/deb 下不会被 postinst 递归提权，非 root 用户直接读不到。
    """
    repo_root = require_repo_root()
    cmake_files = iter_scanned_cmake_files(repo_root)
    offenders = []
    for cmake_file in cmake_files:
        content = cmake_file.read_text(encoding="utf-8")
        for perms in iter_world_unreadable_perms(content):
            offenders.append(f"{cmake_file.relative_to(repo_root)}: {perms}")
    # 自检：一个文件都没扫到说明路径算错了，此时"无违规"不可信。
    assert cmake_files, "未扫到任何 cmake 文件，仓库根定位可能有误"
    assert not offenders, (
        "以下 FILE_PERMISSIONS 声明缺 WORLD_READ，rpm/deb 安装后非 root 读不到：\n  "
        + "\n  ".join(offenders)
    )
