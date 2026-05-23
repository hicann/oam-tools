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
"""使用 GitCode API 创建 Pull Request.

使用方法:
    python create_pr.py --title "PR-Title" --head "user:branch" \
        --base "develop" --issue "#32"

或使用完整的 body 参数:
    python create_pr.py --title "PR-Title" --head "user:branch" \
        --base "develop" --body "full-description"
"""

import argparse
import logging
import os
import sys

import requests

GITCODE_API_BASE = "https://gitcode.com/api/v5"
REQUEST_TIMEOUT_SEC = 30
HTTP_OK = 200
HTTP_CREATED = 201
SEPARATOR_LEN = 50

logger = logging.getLogger(__name__)


def load_pr_template(template_path=None):
    """加载 PR 模板, 找不到时返回 None."""
    if template_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(
            script_dir, '..', 'assets', 'pr_template.md'
        )

    if not os.path.exists(template_path):
        return None
    with open(template_path, encoding='utf-8') as fp:
        return fp.read()


def build_pr_body(body, issue, description):
    """根据 body / issue / description 构造 PR 描述, 始终返回字符串."""
    if body:
        return body
    if not (issue and description):
        return ""
    template = load_pr_template()
    if not template:
        return ""
    return (
        template
        .replace('{{issue}}', issue)
        .replace('{{description}}', description)
    )


def create_pull_request(owner, repo, token, pr_data):
    """调用 GitCode API 创建 Pull Request, 失败返回 None."""
    logger.info("Creating Pull Request...")
    logger.info("target repo: %s/%s", owner, repo)
    logger.info("head: %s", pr_data.get('head'))
    logger.info("base: %s", pr_data.get('base'))
    logger.info("-" * SEPARATOR_LEN)

    url = f"{GITCODE_API_BASE}/repos/{owner}/{repo}/pulls"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=pr_data,
            timeout=REQUEST_TIMEOUT_SEC,
        )
    except requests.exceptions.RequestException as exc:
        logger.error("request failed: %s", exc)
        return None

    if response.status_code not in (HTTP_OK, HTTP_CREATED):
        logger.error("create failed, status: %s", response.status_code)
        logger.error("response: %s", response.text)
        return None

    result = response.json()
    pr_url = (
        result.get('web_url')
        or result.get('html_url')
        or 'unknown'
    )
    logger.info("Pull Request created.")
    logger.info("PR number: #%s", result.get('number', 'unknown'))
    logger.info("PR url: %s", pr_url)
    logger.info("state: %s", result.get('state', 'unknown'))
    return result


def parse_args():
    """解析命令行参数."""
    parser = argparse.ArgumentParser(
        description='Create GitCode Pull Request via API',
    )
    parser.add_argument('--owner', default='cann', help='repo owner')
    parser.add_argument('--repo', default='metadef', help='repo name')
    parser.add_argument('--title', required=True, help='PR title')
    parser.add_argument(
        '--head', required=True, help='source branch (username:branch)',
    )
    parser.add_argument('--base', default='develop', help='target branch')
    parser.add_argument('--body', help='full PR body')
    parser.add_argument('--issue', help='related issue id (e.g. #32)')
    parser.add_argument('--description', help='PR description summary')
    parser.add_argument('--token', help='GitCode access token')
    return parser.parse_args()


def main():
    """命令行入口."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )
    args = parse_args()
    if not args.token:
        logger.error("--token is required")
        return 1

    pr_data = {
        'title': args.title,
        'head': args.head,
        'base': args.base,
        'body': build_pr_body(args.body, args.issue, args.description or ""),
    }

    result = create_pull_request(args.owner, args.repo, args.token, pr_data)
    if result is None:
        logger.error("please check the error message above")
        return 1

    logger.info("=" * SEPARATOR_LEN)
    logger.info("next steps:")
    logger.info("1. check PR status and CI results")
    logger.info("2. respond to reviewer comments")
    logger.info("3. monitor CI/CD pipeline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
