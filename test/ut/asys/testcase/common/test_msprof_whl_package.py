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

"""msprofbin/CMakeLists.txt 中 msprof whl 预解包进包方式的看护。

背景：whl 预解包由旧的 install(CODE ...)（安装期 pip + chmod 555）改为构建期
add_custom_command 解包 + install(DIRECTORY ...) 声明进包。

打包期不再显式声明权限，交回 cmake install() 的默认值（文件 644 / 目录 755）；
profiler_tool 子树的权限终态由运行期 msprof_install.sh 末尾的 change_dir_mode /
change_file_mode 555 收口，打包期不重复声明。

本用例参照 test_build_script.py 从源文件抽取声明做断言，锁定解包方式与进包声明，
防止后续无意改回安装期 install(CODE) 或漏掉进包声明造成回归。
"""

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
MSPROFBIN_CMAKE = (
    REPO_ROOT / "src" / "msprof" / "collector" / "dvvp" / "msprofbin" / "CMakeLists.txt"
)


def get_cmake_content():
    return MSPROFBIN_CMAKE.read_text(encoding="utf-8")


def get_install_directory_block():
    """抽取解包目录的 install(DIRECTORY "${_msprof_extracted_dir}/" ...) 块。"""
    content = get_cmake_content()
    match = re.search(
        r'install\(DIRECTORY\s+"\$\{_msprof_extracted_dir\}/".*?\)', content, re.S
    )
    assert match is not None, "未找到解包目录的 install(DIRECTORY ...) 声明"
    return match.group(0)


def test_extraction_happens_at_build_time():
    # 构建期解包：add_custom_command + pip3 解到构建目录，而非安装期 install(CODE)。
    content = get_cmake_content()
    assert "add_custom_command(" in content
    assert "_msprof_extracted_dir" in content
    assert "${CMAKE_CURRENT_BINARY_DIR}/msprof_whl_extracted" in content
    # 不应再用旧的 install(CODE ...) 在安装期跑 pip（排除注释行，只看实际语句）。
    code_lines = [ln for ln in content.splitlines() if not ln.lstrip().startswith("#")]
    assert not any("install(CODE" in ln for ln in code_lines), (
        "不应回退到安装期 install(CODE) 解包方式"
    )


ROOT_CMAKE = REPO_ROOT / "CMakeLists.txt"
# staging 绝对路径与本用例无关（只关心尾部落点），统一替成占位符。
_STAGING_STUB = "/BUILD/_CPack_Packages/makeself_staging"
_VAR_RE = re.compile(r"\$\{(\w+)\}")
# 走"相对路径交 CPACK_PACKAGING_INSTALL_PREFIX 收"那条分支的 PACKAGE_TYPE 取值，
# 与 cann-cmake function/prepare.cmake 的 CPACK_GENERATOR 分支对齐：deb,rpm 与 all
# 同样产出 rpm/deb 包，漏掉它们会让 tools/* 落到绝对 staging 路径而不进包载荷。
PKG_PACKAGE_TYPES = ("rpm", "deb", "deb,rpm", "all")


def resolve_cmake_var(name, package_type):
    """解析根 CMakeLists.txt 中变量 name 在给定 PACKAGE_TYPE 下的取值。

    先在 PACKAGE_TYPE 的对应分支里找 set(name ...)，找不到再退到全文件找。
    按"从 DESTINATION 里提取到的名字"去查，而非把名字写死在用例里——
    变量改名（两处同步改）不应让用例失败，只有落点变了才应该失败。

    分支头只匹配到 "if(PACKAGE_TYPE" 为止，不绑定具体判定表达式：判定条件会随
    cann-cmake 支持的取值增减而调整（rpm/deb/deb,rpm/all），用例关心的是两个分支
    各自给出什么落点，而非条件怎么写。
    """
    content = ROOT_CMAKE.read_text(encoding="utf-8")
    branches = re.search(
        r"if\(PACKAGE_TYPE [^\n]*\)"
        r"(?P<pkg>.*?)else\(\)(?P<run>.*?)endif\(\)",
        content,
        re.S,
    )
    assert branches is not None, "未在根 CMakeLists.txt 找到 PACKAGE_TYPE 分支"
    branch = branches.group("pkg" if package_type in PKG_PACKAGE_TYPES else "run")
    pattern = re.compile(r"set\(" + re.escape(name) + r"\s+([^)]+)\)")
    declared = pattern.search(branch) or pattern.search(content)
    assert declared is not None, f"{package_type}: 根 CMakeLists.txt 未定义 {name}"
    return declared.group(1).strip()


def cmake_branch_condition():
    """取出根 CMakeLists.txt 里 PACKAGE_TYPE 分支的判定表达式原文。"""
    content = ROOT_CMAKE.read_text(encoding="utf-8")
    declared = re.search(r"if\((PACKAGE_TYPE [^\n]*)\)\s*\n", content)
    assert declared is not None, "未在根 CMakeLists.txt 找到 PACKAGE_TYPE 分支判定"
    return declared.group(1)


def eval_cmake_condition(condition, package_type):
    """按 CMake 语义判断 condition 在给定 PACKAGE_TYPE 下是否为真。

    只需支持本判定用到的 STREQUAL / MATCHES 与 OR 组合。
    """
    for clause in condition.split(" OR "):
        matched = re.fullmatch(
            r'PACKAGE_TYPE (STREQUAL|MATCHES) "([^"]*)"', clause.strip()
        )
        assert matched is not None, f"判定子句超出用例支持范围: {clause}"
        operator, operand = matched.groups()
        if operator == "STREQUAL":
            if package_type == operand:
                return True
        elif re.search(operand, package_type):
            return True
    return False


def test_branch_condition_covers_every_packaging_type():
    """判定条件必须命中全部产出 rpm/deb 的取值，run 与空值必须不命中。

    resolve_cmake_var 里的分支归属是用例侧的假定，光靠它无法发现"条件写窄了"——
    条件退回只判 rpm/deb 时，deb,rpm 与 all 在真实构建中落进 else 分支拿到绝对
    staging 路径、文件不进包，而用例仍会读 pkg 分支从而误报通过。故在此直接对
    条件本身求值。
    """
    condition = cmake_branch_condition()
    for package_type in PKG_PACKAGE_TYPES:
        assert eval_cmake_condition(condition, package_type), (
            f"PACKAGE_TYPE={package_type} 会产出 rpm/deb 包，"
            f"但判定 `{condition}` 未命中，文件将落到绝对 staging 路径而不进包"
        )
    for package_type in ("run", ""):
        assert not eval_cmake_condition(condition, package_type), (
            f"PACKAGE_TYPE={package_type or '<空>'} 应走 run 形态，"
            f"但判定 `{condition}` 命中了打包分支"
        )


def expand_destination(destination, package_type):
    """把 DESTINATION 里的 CMake 变量按给定包类型逐层展开成实际路径。"""
    expanded = destination
    for _ in range(10):  # 逐层展开，兼容变量值里嵌套引用其他变量
        names = _VAR_RE.findall(expanded)
        if not names:
            break
        for name in names:
            value = (
                _STAGING_STUB
                if name == "OAM_STAGING_DIR"
                else resolve_cmake_var(name, package_type)
            )
            expanded = expanded.replace("${" + name + "}", value)
    # 自检：展开必须彻底，否则下面的落点断言会因残留 ${...} 而失去意义。
    assert "${" not in expanded, (
        f"{package_type}: DESTINATION 仍有未展开变量 {expanded}"
    )
    return expanded


def test_extracted_dir_installed_via_install_directory():
    # 解包产物通过 install(DIRECTORY) 声明进包。断言的是"展开后落点"而非变量名：
    # 各打包取值（含 deb,rpm / all）与 run 下都必须落到 tools/profiler/profiler_tool。
    block = get_install_directory_block()
    declared = re.search(r"DESTINATION\s+(\S+)", block)
    assert declared is not None, "install(DIRECTORY) 未声明 DESTINATION"
    destination = declared.group(1)
    for package_type in PKG_PACKAGE_TYPES + ("run",):
        expanded = expand_destination(destination, package_type)
        assert expanded.endswith("tools/profiler/profiler_tool"), (
            f"{package_type} 包下解包产物落点应为 tools/profiler/profiler_tool，"
            f"实际 {expanded}"
        )
    assert "COMPONENT oam-tools" in block


def test_install_directory_declares_file_555_but_no_dir_perms():
    # 文件权限显式 555：与运行期 msprof_install.sh 的 change_file_mode 555 一致，
    # 使 --noexec --extract 旁路（不跑安装脚本）下的文件权限不退回 644。
    # 目录权限不声明：交回 cmake 默认的 755。unlink 只看父目录写位，目录必须带
    # owner 写位，否则 build/_CPack_Packages/ 下的产物无法 rm -rf（CI 随机失败）。
    block = get_install_directory_block()
    file_perm = re.search(
        r"FILE_PERMISSIONS\s+(.*?)(?:DIRECTORY_PERMISSIONS|PATTERN|\))", block, re.S
    )
    assert file_perm is not None, "install(DIRECTORY) 应显式声明 FILE_PERMISSIONS 555"
    perms = file_perm.group(1)
    # 555 = READ + EXECUTE for OWNER/GROUP/WORLD，且不含任何 WRITE。
    assert "OWNER_READ" in perms and "OWNER_EXECUTE" in perms
    assert "GROUP_READ" in perms and "GROUP_EXECUTE" in perms
    assert "WORLD_READ" in perms and "WORLD_EXECUTE" in perms
    assert "WRITE" not in perms, "文件 555 权限不应含任何 WRITE 位"
    # 目录权限一律不得摘掉 owner 写位：要么不声明，要么声明里必须含 OWNER_WRITE。
    dir_perm = re.search(r"DIRECTORY_PERMISSIONS\s+(.*?)(?:PATTERN|\))", block, re.S)
    if dir_perm is not None:
        assert "OWNER_WRITE" in dir_perm.group(1), (
            "若声明 DIRECTORY_PERMISSIONS，必须含 OWNER_WRITE，否则产物目录无法删除"
        )


def test_sentinel_file_excluded_from_package():
    # .extracted 是构建期哨兵文件，不应进包。
    block = get_install_directory_block()
    assert 'PATTERN ".extracted" EXCLUDE' in block


def test_extract_target_bound_to_main_target():
    # 解包目标显式绑定主构建目标 msprofbin，保证 install 依赖的产物在构建后就绪。
    content = get_cmake_content()
    assert "add_dependencies(msprofbin msprof_whl_extract)" in content


def test_no_chmod_at_build_time():
    # 构建期不改权限，等价旧 install(CODE) 的"仅安装期设权限"：555 只由
    # install(DIRECTORY) 声明式设置，构建目录保持默认可写，避免重解包时 pip
    # 无法写入被锁成只读的目录。
    content = get_cmake_content()
    code_lines = [ln for ln in content.splitlines() if not ln.lstrip().startswith("#")]
    assert not any("chmod" in ln for ln in code_lines), (
        "构建期不应出现 chmod（权限应仅由 install(DIRECTORY) 声明式设置）"
    )


def test_extraction_guarded_by_whl_existence():
    # whl 由 configure 期生成，本目录单独联编时不生成。解包段必须有守卫，
    # 等价旧 install(CODE) 的 if(EXISTS)——缺失时静默跳过、不报错。
    # msprof_whl 现由 file(GLOB) 得到（版本字段可变），是列表而非单一路径，
    # 故用 if(msprof_whl) 判空：空列表为假，与 if(EXISTS) 在 0/1 个 whl 时
    # 等价；多个 whl 时 if(EXISTS) 会因列表拼成分号串而误判为假、静默跳过
    # 解包，if(msprof_whl) 无此问题（多 whl 另由前置 FATAL_ERROR 拦住）。
    content = get_cmake_content()
    assert "if(msprof_whl)" in content, (
        "解包段应由 if(msprof_whl) 守卫，缺失 whl 时静默跳过"
    )


def test_extracted_dir_cleaned_before_pip():
    # pip 无 --force-reinstall 时对已存在包判 already satisfied
    # 而跳过、残留旧代码。解包前必须先 remove_directory 清空，保证重解包树完全来自
    # 当前 whl（等价旧 install(CODE) 解到每次被 clean_cpack_staging 清空的目录）。
    content = get_cmake_content()
    # remove_directory 必须出现在 pip3 install 之前。
    rm_idx = content.find('remove_directory "${_msprof_extracted_dir}"')
    pip_idx = content.find("pip3 install")
    assert rm_idx != -1, "解包前应 remove_directory 清空 _msprof_extracted_dir"
    assert rm_idx < pip_idx, "remove_directory 必须在 pip3 install 之前执行"


def get_install_programs_whl_block():
    """抽取 whl 自身的 install(PROGRAMS ${msprof_whl} ...) 块。"""
    content = get_cmake_content()
    match = re.search(r"install\(PROGRAMS\s+\$\{msprof_whl\}.*?\)", content, re.S)
    assert match is not None, "未找到 whl 的 install(PROGRAMS ...) 声明"
    return match.group(0)


def test_install_programs_whl_declares_555_permissions():
    # whl 自身保留显式 555：它是文件，无写位不影响目录可删除性，
    # 故与历史终态保持一致（旧 install(CODE) 的 chmod -R 555 连带刷过 whl）。
    block = get_install_programs_whl_block()
    perm = re.search(r"PERMISSIONS\s+(.*?)\)", block, re.S)
    assert perm is not None, "install(PROGRAMS) 应显式声明 PERMISSIONS 555"
    perms = perm.group(1)
    assert "OWNER_READ" in perms and "OWNER_EXECUTE" in perms
    assert "GROUP_READ" in perms and "GROUP_EXECUTE" in perms
    assert "WORLD_READ" in perms and "WORLD_EXECUTE" in perms
    assert "WRITE" not in perms, "555 权限不应含任何 WRITE 位"
