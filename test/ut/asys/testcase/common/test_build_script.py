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


def test_clean_cpack_staging_restores_write_permission_before_remove():
    build_content = get_build_script_content()
    match = re.search(r"\nclean_cpack_staging\(\) \{(?P<body>.*?)\n\}", build_content, re.S)
    assert match is not None

    function_body = match.group("body")
    chmod_index = function_body.find('chmod -R u+w "${cpack_path}"')
    remove_index = function_body.find('rm -rf "${cpack_path}"')

    assert 'local cpack_path="${build_path%/}/_CPack_Packages"' in function_body
    assert chmod_index != -1
    assert remove_index != -1
    assert chmod_index < remove_index


def test_package_cleans_cpack_staging_before_make_package():
    build_content = get_build_script_content()
    assert 'make ${VERBOSE} -j${THREAD_NUM} && clean_cpack_staging "${BUILD_PATH}" && make package' in build_content
