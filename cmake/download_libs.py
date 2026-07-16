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
import os
import logging
import subprocess
import shutil

logging.basicConfig(level=logging.INFO)


def download_single_file(url, current_dir):
    """下载单个文件"""
    actual_url = url
    custom_name = None

    if isinstance(url, tuple):
        if len(url) == 1:
            actual_url = url[0]
        elif len(url) == 2:
            actual_url = url[0]
            custom_name = url[1]
        else:
            raise ValueError(f"URL tuple length must be 1 or 2, got {len(url)}")

    if actual_url.endswith(".git"):
        repo_name = actual_url.split("/")[-1].replace(".git", "")
        repo_path = os.path.join(current_dir, custom_name if custom_name else repo_name)
        logging.info("Start git clone %s", actual_url)

        git_path = shutil.which('git')
        result = subprocess.run(
            [git_path, "clone", actual_url, repo_path],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            raise RuntimeError(f"git clone failed: {result.stderr}")
        logging.info("Successfully cloned to %s", repo_path)
        return

    file_name = custom_name if custom_name else actual_url.split("/")[-1]
    if not file_name:
        file_name = "downloaded_file"

    # 仅允许 https，杜绝 file:/ 等本地/自定义 scheme。
    if not actual_url.startswith("https://"):
        raise ValueError(f"only https url is allowed, got: {actual_url}")

    file_path = os.path.join(current_dir, file_name)
    logging.info("Start download %s", actual_url)

    wget_path = shutil.which("wget")
    if not wget_path:
        raise RuntimeError("wget not found in PATH")
    result = subprocess.run(
        [wget_path, "--no-check-certificate", "-O", file_path, actual_url],
        capture_output=True,
        text=True,
        check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"wget download failed: {result.stderr}")
    logging.info("Successfully saved to %s", file_path)


def download_files_native(url_list):
    """下载多个文件"""
    current_dir = os.getcwd()
    for url in url_list:
        try:
            download_single_file(url, current_dir)
        except (ValueError, RuntimeError, OSError) as e:
            logging.info("Download file form %s failed: %s", url, e)


if __name__ == "__main__":
    my_urls = [
        (
            "https://gitcode.com/cann-src-third-party/protobuf/releases/download/v25.1"
            "/protobuf-25.1.tar.gz",
        ),
        (
            "https://gitcode.com/cann-src-third-party/makeself/releases/download"
            "/release-2.5.0-patch1.0/makeself-release-2.5.0-patch1.tar.gz",
        ),
        (
            "https://gitcode.com/cann-src-third-party/abseil-cpp/releases/download"
            "/20230802.1/abseil-cpp-20230802.1.tar.gz",
        ),
        (
            "https://gitcode.com/cann-src-third-party/googletest/releases/download"
            "/v1.14.0/googletest-1.14.0.tar.gz",
        ),
        (
            "https://gitcode.com/cann-src-third-party/mockcpp/releases/download"
            "/v2.7-h2/mockcpp-2.7_py3.patch",
        ),
        (
            "https://gitcode.com/cann-src-third-party/mockcpp/releases/download"
            "/v2.7-h2/mockcpp-2.7.tar.gz",
        ),
        (
            "https://cann-3rd.obs.cn-north-4.myhuaweicloud.com"
            "/cann/oam-tools-diag/master/cann-oam-tools-release-x86_64.tar.gz",
        ),
        (
            "https://cann-3rd.obs.cn-north-4.myhuaweicloud.com"
            "/cann/oam-tools-diag/master/cann-oam-tools-release-aarch64.tar.gz",
        ),
        (
            "https://gitcode.com/Ascend/msprobe.git",
        ),
        (
            "https://gitcode.com/Ascend/msprof.git",
        ),
    ]

    download_files_native(my_urls)