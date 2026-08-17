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
        r'install\(DIRECTORY\s+"\$\{_msprof_extracted_dir\}/".*?\)',
        content,
        re.S,
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
    assert not any("install(CODE" in ln for ln in code_lines), \
        "不应回退到安装期 install(CODE) 解包方式"


def test_extracted_dir_installed_via_install_directory():
    # 解包产物通过 install(DIRECTORY) 声明进包，落到 profiler_tool 下。
    block = get_install_directory_block()
    assert "tools/profiler/profiler_tool" in block
    assert "COMPONENT oam-tools" in block


def test_install_directory_declares_file_555_but_no_dir_perms():
    # 文件权限显式 555：与运行期 msprof_install.sh 的 change_file_mode 555 一致，
    # 使 --noexec --extract 旁路（不跑安装脚本）下的文件权限不退回 644。
    # 目录权限不声明：交回 cmake 默认的 755。unlink 只看父目录写位，目录必须带
    # owner 写位，否则 build/_CPack_Packages/ 下的产物无法 rm -rf（CI 随机失败）。
    block = get_install_directory_block()
    file_perm = re.search(r"FILE_PERMISSIONS\s+(.*?)(?:DIRECTORY_PERMISSIONS|PATTERN|\))", block, re.S)
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
        assert "OWNER_WRITE" in dir_perm.group(1), \
            "若声明 DIRECTORY_PERMISSIONS，必须含 OWNER_WRITE，否则产物目录无法删除"


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
    assert not any("chmod" in ln for ln in code_lines), \
        "构建期不应出现 chmod（权限应仅由 install(DIRECTORY) 声明式设置）"


def test_extraction_guarded_by_whl_existence():
    # whl 由 configure 期生成，本目录单独联编时不生成。解包段必须有守卫，
    # 等价旧 install(CODE) 的 if(EXISTS)——缺失时静默跳过、不报错。
    # msprof_whl 现由 file(GLOB) 得到（版本字段可变），是列表而非单一路径，
    # 故用 if(msprof_whl) 判空：空列表为假，与 if(EXISTS) 在 0/1 个 whl 时
    # 等价；多个 whl 时 if(EXISTS) 会因列表拼成分号串而误判为假、静默跳过
    # 解包，if(msprof_whl) 无此问题（多 whl 另由前置 FATAL_ERROR 拦住）。
    content = get_cmake_content()
    assert "if(msprof_whl)" in content, \
        "解包段应由 if(msprof_whl) 守卫，缺失 whl 时静默跳过"


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
    match = re.search(
        r'install\(PROGRAMS\s+\$\{msprof_whl\}.*?\)',
        content,
        re.S,
    )
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
