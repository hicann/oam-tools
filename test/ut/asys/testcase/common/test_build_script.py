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

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]


def get_build_script_content():
    return (REPO_ROOT / "build.sh").read_text(encoding="utf-8")


def test_safe_rm_dir_defined():
    build_content = get_build_script_content()
    match = re.search(r"\nsafe_rm_dir\(\) \{(?P<body>.*?)\n\}", build_content, re.S)
    assert match is not None, "safe_rm_dir 函数未定义"

    function_body = match.group("body")
    assert '[ -z "${dir_path}" ] || [ ! -d "${dir_path}" ]' in function_body
    assert 'chmod -R u+w "${dir_path}" 2>/dev/null' in function_body
    assert 'rm -r -- "${dir_path}"' in function_body


def test_clean_cpack_staging_uses_safe_rm_dir():
    build_content = get_build_script_content()
    match = re.search(r"\nclean_cpack_staging\(\) \{(?P<body>.*?)\n\}", build_content, re.S)
    assert match is not None

    function_body = match.group("body")
    assert 'safe_rm_dir "${cpack_path}"' in function_body


def test_package_cleans_cpack_staging_before_make_package():
    build_content = get_build_script_content()
    assert 'make ${VERBOSE} -j${THREAD_NUM} && clean_cpack_staging "${BUILD_PATH}" && make package' in build_content


def test_stale_artifacts_cleaned_before_make_package():
    # make package 前清理 build 目录下历史 cann*.run/rpm/deb，避免旧产物污染本次结果
    # （残留旧后缀被误当本次产物搬走）。清理须在 make package 之前。
    build_content = get_build_script_content()
    rm_idx = build_content.find("rm -f cann*.run cann*.rpm cann*.deb")
    pkg_idx = build_content.find("&& make package")
    assert rm_idx != -1, "make package 前应清理历史 cann*.run/rpm/deb 产物"
    assert rm_idx < pkg_idx, "清理历史产物必须在 make package 之前"


def test_artifact_moved_by_package_type():
    # 只搬本次 PACKAGE_TYPE 对应后缀的产物，不按固定顺序扫描 run/rpm/deb，
    # 避免残留旧后缀先命中导致搬错包类型。
    build_content = get_build_script_content()
    assert 'compgen -G "cann*.${PACKAGE_TYPE}"' in build_content, \
        "产物应按 ${PACKAGE_TYPE} 后缀查找"
    assert 'mv cann*.${PACKAGE_TYPE} "$BUILD_OUT_PATH"' in build_content, \
        "应搬运 ${PACKAGE_TYPE} 后缀的全部产物"
    # 不应再按固定顺序 for ext in run rpm deb 扫描（旧写法会先命中残留 run）。
    assert "for ext in run rpm deb" not in build_content, \
        "不应按固定顺序扫描 run/rpm/deb（会先命中残留旧产物）"
