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
"""GitCode PR 机械操作脚本（确定性，供 agent 调用后解析 JSON）。

把反复踩坑的固定逻辑固化进脚本，避免大模型每次现写 curl/jq：
- 评论列表必须 per_page=100（v5 默认仅 20 条，会漏看）。
- 流水线结果只认含终态(SUCCESS/FAILED/WARNING)的完成结果，排除"触发成功"噪声。
- 回复评审统一用引用回复（v5 普通评论），不尝试对机器人评审做线程嵌套。
- 触发 compile 先 v4 notes，返回 {id:null} 时回退 v5 comments。
- 探测 fork 目标仓带 HTTP/解析校验，查询失败报错退出，绝不静默回退。

所有子命令输出 JSON 到 stdout，便于上层解析。token 取自 --token 或
环境变量 GITCODE_API_TOKEN。
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time

import requests

GITCODE_V5_API = "https://api.gitcode.com/api/v5"
GITCODE_V4_API = "https://api.gitcode.com/api/v4"
# CI 结论文件（公开、无需 token）：含 codecheck_result/precommit_result/commit_id。
# 注意仅给出 pass/no-pass 结论；逐条告警明细在 openlibing 看板（需登录，
# 且严禁把 GITCODE_API_TOKEN 发往该第三方域名）。
CI_RESULT_URL = (
    "https://ascend-ci.obs.cn-north-4.myhuaweicloud.com"
    "/{repo}/package/{pr}/codecheck.json"
)
REQUEST_TIMEOUT_SEC = 30
HTTP_OK = 200
HTTP_CREATED = 201
PER_PAGE = 100
# 流水线完成结果的终态特征；含其一且非"仅触发成功"才算完成结果。
PIPELINE_TERMINAL_RE = re.compile(r"SUCCESS|FAILED|FAILURE|WARNING|ERROR")
TRIGGER_ONLY_RE = re.compile(r"触发成功")

# 用 logging 输出 JSON 到 stdout（满足"用日志工具"规范，且结果仍在 stdout 供解析）。
logger = logging.getLogger("pr_ops")


class PrOpsError(Exception):
    """业务错误：携带消息与附加字段，由 main 统一输出 JSON 并退出。"""

    def __init__(self, msg, extra=None):
        super().__init__(msg)
        self.msg = msg
        self.extra = extra if extra else {}


def get_token(args):
    """取访问令牌：优先 --token，其次环境变量。"""
    token = getattr(args, "token", None) or os.environ.get("GITCODE_API_TOKEN")
    if not token:
        fail("缺少访问令牌：请传 --token 或设置环境变量 GITCODE_API_TOKEN")
    return token


def fail(msg, **extra):
    """抛出业务错误，由 main 统一输出 JSON 并退出（避免在函数内 sys.exit）。"""
    raise PrOpsError(msg, extra)


def emit(obj):
    """通过 logging 输出成功 JSON 到 stdout（日志工具，而非 print）。"""
    if isinstance(obj, dict) and "ok" not in obj:
        obj = {"ok": True, **obj}
    logger.info("%s", json.dumps(obj, ensure_ascii=False, indent=2))


def v5_get(path, token, params=None):
    """v5 GET，返回 (status_code, json_or_text)。"""
    p = dict(params or {})
    p.setdefault("access_token", token)
    try:
        r = requests.get(
            f"{GITCODE_V5_API}{path}", params=p, timeout=REQUEST_TIMEOUT_SEC
        )
    except requests.exceptions.RequestException as exc:
        fail(f"请求失败: {exc}")
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text


def v5_post(path, token, body):
    """v5 POST JSON，返回 (status_code, json_or_text)。"""
    try:
        r = requests.post(
            f"{GITCODE_V5_API}{path}",
            params={"access_token": token},
            json=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=REQUEST_TIMEOUT_SEC,
        )
    except requests.exceptions.RequestException as exc:
        fail(f"请求失败: {exc}")
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text


def v5_patch(path, token, body):
    """v5 PATCH JSON，返回 (status_code, json_or_text)。"""
    try:
        r = requests.patch(
            f"{GITCODE_V5_API}{path}",
            params={"access_token": token},
            json=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=REQUEST_TIMEOUT_SEC,
        )
    except requests.exceptions.RequestException as exc:
        fail(f"请求失败: {exc}")
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text


def v4_post_note(encoded_repo, pr, token, body):
    """v4 merge_requests notes POST（用于触发 compile）。"""
    url = f"{GITCODE_V4_API}/projects/{encoded_repo}/merge_requests/{pr}/notes"
    try:
        r = requests.post(
            url,
            headers={"PRIVATE-TOKEN": token, "Content-Type": "application/json"},
            json={"body": body},
            timeout=REQUEST_TIMEOUT_SEC,
        )
    except requests.exceptions.RequestException:
        return None
    try:
        return r.json()
    except ValueError:
        return None


def v4_post_discussion(encoded_repo, pr, token, body):
    """v4 merge_requests discussions POST（用于发行内评论）。"""
    url = f"{GITCODE_V4_API}/projects/{encoded_repo}/merge_requests/{pr}/discussions"
    try:
        r = requests.post(
            url,
            headers={"PRIVATE-TOKEN": token, "Content-Type": "application/json"},
            json=body,
            timeout=REQUEST_TIMEOUT_SEC,
        )
    except requests.exceptions.RequestException as exc:
        fail(f"请求失败: {exc}")
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text


def fetch_comments(owner, repo, pr, token):
    """拉取 PR 全部评论，按页循环直到取完，返回完整列表（始终是 list）。

    v5 单页上限 per_page=100；评论超过 100 条时必须继续翻页，否则会漏看
    最新流水线结果/评审意见。循环到某页返回空或不足一页为止。
    """
    all_comments = []
    page = 1
    while True:
        code, data = v5_get(
            f"/repos/{owner}/{repo}/pulls/{pr}/comments",
            token,
            params={"per_page": PER_PAGE, "page": page},
        )
        if code != HTTP_OK:
            fail(f"拉取评论失败 (HTTP {code})", detail=data)
        if not isinstance(data, list):
            fail("评论返回格式异常（非数组）", detail=data)
        all_comments.extend(data)
        if len(data) < PER_PAGE:
            break
        page += 1
    return all_comments


def user_login(comment):
    """兼容 user 为对象或字符串两种返回。"""
    u = comment.get("user")
    if isinstance(u, dict):
        return u.get("login") or u.get("name") or ""
    return u or ""


def parse_remote_url(url):
    """从 git remote URL 解析 (owner, repo)，兼容 ssh / https。"""
    url = url.strip()
    # ssh: git@gitcode.com:owner/repo.git
    m = re.match(r"^[^@]+@[^:]+:([^/]+)/(.+?)(?:\.git)?$", url)
    if m:
        return m.group(1), m.group(2)
    # https: https://gitcode.com/owner/repo.git
    m = re.match(r"^https?://[^/]+/([^/]+)/(.+?)(?:\.git)?$", url)
    if m:
        return m.group(1), m.group(2)
    return None, None


def cmd_resolve_repo(args):
    """从 origin 探测 owner/repo，并查 fork 来源确定 PR 目标仓。

    带 HTTP/解析校验：查询失败或 fork 字段异常直接报错退出，
    只有明确 fork=false 才回退当前仓，绝不静默回退。
    """
    token = get_token(args)
    git_bin = shutil.which("git")
    if not git_bin:
        fail("未找到 git 可执行文件")
    try:
        url = (
            subprocess.check_output(
                [git_bin, "remote", "get-url", args.remote],
                stderr=subprocess.STDOUT,
            )
            .decode()
            .strip()
        )
    except subprocess.CalledProcessError as exc:
        fail(f"读取 git remote '{args.remote}' 失败: {exc.output.decode().strip()}")
    owner, repo = parse_remote_url(url)
    if not owner or not repo:
        fail(f"无法从 remote URL 解析 owner/repo: {url}")

    code, data = v5_get(f"/repos/{owner}/{repo}", token)
    if code != HTTP_OK or not isinstance(data, dict):
        fail(f"查询仓库信息失败 (HTTP {code})，无法确定目标仓", detail=data)
    fork_flag = data.get("fork")
    if fork_flag not in (True, False):
        fail("解析 fork 字段失败（响应异常），终止", detail={"fork": fork_flag})

    if fork_flag:
        parent = (data.get("parent") or {}).get("full_name")
        if not parent or "/" not in parent:
            fail("fork=true 但缺少 parent.full_name，无法确定源仓", detail=parent)
        parent_owner, parent_repo = parent.split("/", 1)
    else:
        parent_owner, parent_repo = owner, repo

    parent_encoded = f"{parent_owner}%2F{parent_repo}"
    emit(
        {
            "owner": owner,
            "repo": repo,
            "is_fork": fork_flag,
            "parent_owner": parent_owner,
            "parent_repo": parent_repo,
            "parent_encoded_repo": parent_encoded,
        }
    )


def parse_task_table(body):
    """从 cann-robot 评论 HTML 解析 [{task, status}]。

    评论形如 <strong>codecheck</strong> ... <td>✅ SUCCESS</td>，
    用正则成对提取任务名与其后的状态词，避免依赖 HTML 解析库。
    """
    tasks = []
    pattern = re.compile(
        r"<strong>\s*([A-Za-z0-9_]+)\s*</strong>.*?"
        r"(SUCCESS|FAILED|FAILURE|WARNING|ERROR|RUNNING|PENDING)",
        re.S,
    )
    for m in pattern.finditer(body):
        tasks.append({"task": m.group(1), "status": m.group(2)})
    return tasks


def is_pipeline_result(comment, since=None):
    """判断一条评论是否为 cann-robot 的流水线完成结果。

    完成结果需含终态(SUCCESS/FAILED/...)，且排除仅含"触发成功"而无任务表
    的触发提示；给定 since 时还须 created_at 晚于该时间（取本轮新结果）。
    """
    if user_login(comment) != "cann-robot":
        return False
    body = comment.get("body", "")
    if not PIPELINE_TERMINAL_RE.search(body):
        return False
    if TRIGGER_ONLY_RE.search(body) and not parse_task_table(body):
        return False
    if since and comment.get("created_at", "") <= since:
        return False
    return True


def cmd_get_pipeline(args):
    """取最新一条流水线完成结果。无完成结果时 has_result=false。

    --since 给定 ISO 时间时，只认 created_at 晚于它的完成结果，
    用于在重新触发后只取本轮新结果，避免误用上一轮的陈旧结果。
    """
    token = get_token(args)
    comments = fetch_comments(args.owner, args.repo, args.pr, token)
    since = getattr(args, "since", None)
    results = []
    for c in comments:
        if not is_pipeline_result(c, since):
            continue
        results.append(c)
    results.sort(key=lambda c: c.get("created_at", ""))
    if not results:
        emit({"has_result": False, "note": "无完成结果，流水线可能仍在运行"})
        return
    latest = results[-1]
    tasks = parse_task_table(latest.get("body", ""))
    # 只有阻断终态(FAILED/FAILURE/ERROR)才算失败；WARNING 是非阻断告警，单列。
    blocking = ("FAILED", "FAILURE", "ERROR")
    failed = [t for t in tasks if t["status"] in blocking]
    warnings = [t for t in tasks if t["status"] == "WARNING"]
    emit(
        {
            "has_result": True,
            # pipeline_pass 只看阻断失败；有 WARNING 但无 FAILED 仍算通过。
            "pipeline_pass": bool(tasks) and not failed,
            "tasks": tasks,
            "failed_tasks": failed,
            "warning_tasks": warnings,
            "created_at": latest.get("created_at"),
            "raw_excerpt": re.sub(r"<[^>]+>", " ", latest.get("body", ""))[:300],
        }
    )


def cmd_get_codecheck(args):
    """拉取 CI 结论文件（公开 obs，无需 token）。

    返回 codecheck_result/precommit_result 与 commit_id——commit_id 可精确
    确认该结论对应哪次提交，比按时间过滤更可靠。明细看板 URL 一并返回，
    但明细需在 openlibing 登录查看，本脚本不访问该第三方域名。
    """
    url = CI_RESULT_URL.format(repo=args.repo, pr=args.pr)
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT_SEC)
    except requests.exceptions.RequestException as exc:
        fail(f"请求 CI 结论失败: {exc}")
    if r.status_code != HTTP_OK:
        emit(
            {
                "has_result": False,
                "http_code": r.status_code,
                "note": "结论文件不存在，流水线可能未产出 codecheck 结论",
            }
        )
        return
    try:
        data = r.json()
    except ValueError:
        fail("CI 结论文件解析失败（非 JSON）", detail=r.text[:200])
    emit(
        {
            "has_result": True,
            "codecheck_result": data.get("codecheck_result"),
            "codecheck_pass": data.get("codecheck_result") == "pass",
            "precommit_result": data.get("precommit_result"),
            "commit_id": data.get("commit_id"),
            "detail_url": data.get("codecheck"),
        }
    )


def cmd_get_state(args):
    """返回 PR state 与 merged_at。"""
    token = get_token(args)
    code, data = v5_get(f"/repos/{args.owner}/{args.repo}/pulls/{args.pr}", token)
    if code != HTTP_OK or not isinstance(data, dict):
        fail(f"查询 PR 状态失败 (HTTP {code})", detail=data)
    emit({"state": data.get("state"), "merged_at": data.get("merged_at")})


def cmd_get_reviews(args):
    """列出人类评审意见：排除 cann-robot、自己、/lgtm /approve。"""
    token = get_token(args)
    comments = fetch_comments(args.owner, args.repo, args.pr, token)
    me = args.me
    reviews = []
    for c in comments:
        login = user_login(c)
        if login in ("cann-robot",):
            continue
        if me and login == me:
            continue
        body = c.get("body", "")
        if re.search(r"/lgtm|/approve", body):
            continue
        reviews.append(
            {
                "discussion_id": c.get("discussion_id"),
                "comment_type": c.get("comment_type"),
                "user": login,
                "created_at": c.get("created_at"),
                "body": body,
            }
        )
    reviews.sort(key=lambda c: c.get("created_at") or "")
    emit({"count": len(reviews), "reviews": reviews})


def cmd_get_files(args):
    """获取 PR 文件变更列表。"""
    token = get_token(args)
    code, data = v5_get(
        f"/repos/{args.owner}/{args.repo}/pulls/{args.pr}/files.json",
        token,
        params={"per_page": PER_PAGE},
    )
    if code != HTTP_OK:
        fail(f"获取文件变更失败 (HTTP {code})", detail=data)
    diffs = data.get("diffs", []) if isinstance(data, dict) else []
    files = []
    for d in diffs:
        st = (d.get("statistic", {}) if isinstance(d, dict) else {}) or {}
        files.append({"new_path": st.get("new_path"), "old_path": st.get("old_path")})
    emit({"count": len(files), "files": files})


def read_body(args):
    """取回复正文：--body 或 --body-file，二者皆无则报错。"""
    if args.body is not None:
        return args.body
    if args.body_file:
        with open(args.body_file, encoding="utf-8") as fp:
            return fp.read()
    raise PrOpsError("缺少回复正文：请传 --body 或 --body-file")


def cmd_reply(args):
    """引用回复（v5 普通评论），发后回查确认可见。"""
    token = get_token(args)
    body = read_body(args)
    code, data = v5_post(
        f"/repos/{args.owner}/{args.repo}/pulls/{args.pr}/comments",
        token,
        {"body": body},
    )
    if code not in (HTTP_OK, HTTP_CREATED):
        fail(f"回复失败 (HTTP {code})", detail=data)
    # 回查确认进入评论区（取正文前 30 字匹配）
    time.sleep(2)
    needle = body[:30]
    comments = fetch_comments(args.owner, args.repo, args.pr, token)
    posted = (
        any(
            needle and needle in c.get("body", "") and user_login(c) == args.me
            for c in comments
        )
        if args.me
        else True
    )
    emit({"posted": posted, "id": data.get("id") if isinstance(data, dict) else None})


def cmd_update_pr(args):
    """更新 PR 的 title / body（描述）。只 PATCH 实际传入的字段。

    多轮修改后 PR 描述易过时；由模型判断是否需更新、写好新描述经
    --body-file 传入，本命令只负责调 PATCH 接口。
    """
    token = get_token(args)
    payload = {}
    if args.title is not None:
        payload["title"] = args.title
    if args.body is not None:
        payload["body"] = args.body
    elif args.body_file:
        with open(args.body_file, encoding="utf-8") as fp:
            payload["body"] = fp.read()
    if not payload:
        fail("未指定要更新的字段：请传 --body/--body-file 或 --title")
    code, data = v5_patch(
        f"/repos/{args.owner}/{args.repo}/pulls/{args.pr}", token, payload
    )
    if code != HTTP_OK:
        fail(f"更新 PR 失败 (HTTP {code})", detail=data)
    emit({"updated": True, "pr": args.pr, "fields": sorted(payload.keys())})


def fetch_diff_refs(owner, repo, pr, token):
    """从 files.json 取 diff_refs(base_sha/start_sha/head_sha)，发行内评论需要。"""
    code, data = v5_get(f"/repos/{owner}/{repo}/pulls/{pr}/files.json", token)
    if code != HTTP_OK or not isinstance(data, dict):
        fail(f"取 diff_refs 失败 (HTTP {code})", detail=data)
    refs = data.get("diff_refs") or {}
    if not refs.get("head_sha"):
        fail("diff_refs 缺 head_sha，无法定位行内评论", detail=refs)
    return refs


def cmd_review(args):
    """发行内评审意见（绑定 文件:行号 的 diff 评论，显示在代码旁）。

    用 files.json 的 diff_refs 拼 position，POST v4 discussions。
    单行评论 start_line 省略时与 line 相同。
    """
    token = get_token(args)
    body = read_body(args)
    refs = fetch_diff_refs(args.owner, args.repo, args.pr, token)
    start_line = args.start_line or args.line
    enc = args.encoded_repo or f"{args.owner}%2F{args.repo}"
    payload = {
        "body": body,
        "line_types": "new",
        "position": {
            "base_sha": refs["base_sha"],
            "start_sha": refs["start_sha"],
            "head_sha": refs["head_sha"],
            "position_type": "text",
            "old_path": args.path,
            "new_path": args.path,
            "old_line": None,
            "new_line": int(args.line),
            "start_old_line": None,
            "start_new_line": int(start_line),
            "ignore_whitespace_change": False,
        },
        "severity": args.severity,
    }
    code, data = v4_post_discussion(enc, args.pr, token, payload)
    if code not in (HTTP_OK, HTTP_CREATED):
        fail(f"发行内评论失败 (HTTP {code})", detail=data)
    disc_id = data.get("id") if isinstance(data, dict) else None
    emit(
        {
            "posted": True,
            "discussion_id": disc_id,
            "path": args.path,
            "line": int(args.line),
        }
    )


def cmd_reply_review(args):
    """回复到已有行内评论的线程里（落在对应 discussion，而非另起独立评论）。

    用 v4 discussions/<discussion_id>/notes 回复；再用 v5 单条评论接口回查，
    确认回复的 discussion_id 与目标一致（这是"落在同一行内线程"的权威证据，
    GET discussion 接口不可用、v5 列表不收行内回复，故必须用单条接口核对）。
    """
    token = get_token(args)
    body = read_body(args)
    enc = args.encoded_repo or f"{args.owner}%2F{args.repo}"
    url = (
        f"{GITCODE_V4_API}/projects/{enc}/merge_requests/{args.pr}"
        f"/discussions/{args.discussion_id}/notes"
    )
    try:
        r = requests.post(
            url,
            headers={"PRIVATE-TOKEN": token, "Content-Type": "application/json"},
            json={"body": body},
            timeout=REQUEST_TIMEOUT_SEC,
        )
    except requests.exceptions.RequestException as exc:
        fail(f"请求失败: {exc}")
    if r.status_code not in (HTTP_OK, HTTP_CREATED):
        fail(f"回复行内评论失败 (HTTP {r.status_code})", detail=r.text[:200])
    try:
        note = r.json()
    except ValueError:
        note = {}
    note_id = note.get("id")
    # 回查：单条评论接口确认 discussion_id 与目标一致
    in_thread = None
    if note_id:
        code, detail = v5_get(
            f"/repos/{args.owner}/{args.repo}/pulls/comments/{note_id}", token
        )
        if code == HTTP_OK and isinstance(detail, dict):
            in_thread = detail.get("discussion_id") == args.discussion_id
    emit(
        {
            "posted": True,
            "note_id": note_id,
            "discussion_id": args.discussion_id,
            "in_thread": in_thread,
        }
    )


def cmd_trigger(args):
    """触发 compile：先 v4 notes，返回 {id:null} 则回退 v5 comments。"""
    token = get_token(args)
    # 记录触发时刻（GitCode 评论时间带 +08:00，这里用本地时区对齐便于比较）
    trigger_ts = time.strftime("%Y-%m-%dT%H:%M:%S+08:00", time.localtime())
    enc = args.encoded_repo or f"{args.owner}%2F{args.repo}"
    via = "v4"
    r = v4_post_note(enc, args.pr, token, "compile")
    if not (isinstance(r, dict) and r.get("id")):
        via = "v5"
        code, data = v5_post(
            f"/repos/{args.owner}/{args.repo}/pulls/{args.pr}/comments",
            token,
            {"body": "compile"},
        )
        if code not in (HTTP_OK, HTTP_CREATED):
            fail(f"触发 compile 失败 (HTTP {code})", detail=data)
    emit({"triggered": True, "via": via, "ts": trigger_ts})


def cmd_delete_comment(args):
    """删除指定评论（v5 DELETE）。"""
    token = get_token(args)
    url = (
        f"{GITCODE_V5_API}/repos/{args.owner}/{args.repo}"
        f"/pulls/comments/{args.comment_id}"
    )
    try:
        r = requests.delete(
            url, params={"access_token": token}, timeout=REQUEST_TIMEOUT_SEC
        )
    except requests.exceptions.RequestException as exc:
        fail(f"请求失败: {exc}")
    emit({"deleted": r.status_code in (HTTP_OK, 204), "http_code": r.status_code})


def cmd_issue_prs(args):
    """查 issue 关联的 PR（确认关联，不关闭 issue）。"""
    token = get_token(args)
    code, data = v5_get(
        f"/repos/{args.owner}/{args.repo}/issues/{args.issue}/pull_requests",
        token,
    )
    if code != HTTP_OK:
        fail(f"查询 issue 关联 PR 失败 (HTTP {code})", detail=data)
    prs = (
        [
            {
                "number": p.get("number"),
                "state": p.get("state"),
                "title": p.get("title"),
            }
            for p in data
        ]
        if isinstance(data, list)
        else []
    )
    emit({"count": len(prs), "pull_requests": prs})


def build_parser():
    """构造 argparse 子命令解析器。"""
    parser = argparse.ArgumentParser(description="GitCode PR 机械操作脚本")
    parser.add_argument("--token", help="GitCode 访问令牌（默认取环境变量）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_repo(p, pr=True):
        p.add_argument("--owner", required=True, help="目标仓 owner（源仓）")
        p.add_argument("--repo", required=True, help="目标仓 repo（源仓）")
        if pr:
            p.add_argument("--pr", required=True, help="PR 号")

    p = sub.add_parser("resolve-repo", help="探测 owner/repo 与 fork 目标仓")
    p.add_argument("--remote", default="origin", help="git remote 名（默认 origin）")
    p.set_defaults(func=cmd_resolve_repo)

    p = sub.add_parser("get-pipeline", help="取最新流水线完成结果")
    add_repo(p)
    p.add_argument("--since", help="只认晚于该 ISO 时间的完成结果（取本轮新结果）")
    p.set_defaults(func=cmd_get_pipeline)

    p = sub.add_parser(
        "get-codecheck", help="取 CI 结论(codecheck/precommit pass + commit_id)"
    )
    add_repo(p)
    p.set_defaults(func=cmd_get_codecheck)

    p = sub.add_parser("get-state", help="取 PR state")
    add_repo(p)
    p.set_defaults(func=cmd_get_state)

    p = sub.add_parser("get-reviews", help="列出人类评审意见")
    add_repo(p)
    p.add_argument("--me", help="自己的用户名（从结果中排除）")
    p.set_defaults(func=cmd_get_reviews)

    p = sub.add_parser("get-files", help="取 PR 文件变更")
    add_repo(p)
    p.set_defaults(func=cmd_get_files)

    p = sub.add_parser("reply", help="引用回复评审（普通评论）")
    add_repo(p)
    p.add_argument("--body", help="回复正文")
    p.add_argument("--body-file", dest="body_file", help="回复正文文件")
    p.add_argument("--me", help="自己的用户名（用于回查确认）")
    p.set_defaults(func=cmd_reply)

    p = sub.add_parser("update-pr", help="更新 PR 描述/标题（多轮修改后同步）")
    add_repo(p)
    p.add_argument("--body", help="新的 PR 描述正文")
    p.add_argument("--body-file", dest="body_file", help="新描述正文文件")
    p.add_argument("--title", help="新的 PR 标题（不传则不改）")
    p.set_defaults(func=cmd_update_pr)

    p = sub.add_parser("review", help="发行内评审意见（绑定 文件:行号 的 diff 评论）")
    add_repo(p)
    p.add_argument("--path", required=True, help="文件相对路径")
    p.add_argument("--line", required=True, help="结束行号（新代码）")
    p.add_argument(
        "--start-line", dest="start_line", help="起始行号（多行选择；省略=单行）"
    )
    p.add_argument("--body", help="评审意见正文")
    p.add_argument("--body-file", dest="body_file", help="评审意见正文文件")
    p.add_argument(
        "--severity",
        default="suggestion",
        help="严重程度 suggestion/warning（默认 suggestion）",
    )
    p.add_argument(
        "--encoded-repo",
        dest="encoded_repo",
        help="源仓 v4 项目路径（默认 owner%%2Frepo）",
    )
    p.set_defaults(func=cmd_review)

    p = sub.add_parser(
        "reply-review", help="回复到已有行内评论线程(落在对应 discussion)"
    )
    add_repo(p)
    p.add_argument(
        "--discussion-id",
        dest="discussion_id",
        required=True,
        help="目标行内评论的 discussion_id(从 get-reviews 取)",
    )
    p.add_argument("--body", help="回复正文")
    p.add_argument("--body-file", dest="body_file", help="回复正文文件")
    p.add_argument(
        "--encoded-repo",
        dest="encoded_repo",
        help="源仓 v4 项目路径(默认 owner%%2Frepo)",
    )
    p.set_defaults(func=cmd_reply_review)

    p = sub.add_parser("trigger", help="触发 compile 流水线")
    add_repo(p)
    p.add_argument(
        "--encoded-repo",
        dest="encoded_repo",
        help="源仓 v4 项目路径（默认 owner%%2Frepo）",
    )
    p.set_defaults(func=cmd_trigger)

    p = sub.add_parser("delete-comment", help="删除指定评论")
    add_repo(p, pr=False)
    p.add_argument("--comment-id", dest="comment_id", required=True)
    p.set_defaults(func=cmd_delete_comment)

    p = sub.add_parser("issue-prs", help="查 issue 关联的 PR")
    add_repo(p, pr=False)
    p.add_argument("--issue", required=True, help="issue 号")
    p.set_defaults(func=cmd_issue_prs)

    return parser


def main():
    """命令行入口：配置日志到 stdout，统一捕获业务错误输出 JSON。"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    args = build_parser().parse_args()
    try:
        args.func(args)
    except PrOpsError as err:
        out = {"ok": False, "error": err.msg}
        out.update(err.extra)
        logger.info("%s", json.dumps(out, ensure_ascii=False, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
