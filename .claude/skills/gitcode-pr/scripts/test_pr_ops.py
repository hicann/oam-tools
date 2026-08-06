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
"""pr_ops.py 关键路径回归测试。

覆盖 reply-review 走 v5 后的三种落点判定（正常 / 响应缺 note_id / 回查失败），
护住 endpoint 迁移、note_id 语义、comment_type 与 warn 降级行为。

skill 目录不在云端 UT_Test 覆盖范围（其只跑 asys/msaicerr/msprof），故手动运行：
    python3 -m pytest .claude/skills/gitcode-pr/scripts/test_pr_ops.py
"""

import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pr_ops  # noqa: E402


@pytest.fixture(name="args")
def fixture_args():
    """reply-review 的最小参数集。"""
    return types.SimpleNamespace(
        owner="o", repo="r", pr=1, discussion_id="abc", body="x", body_file=None
    )


@pytest.fixture(name="captured")
def fixture_captured(monkeypatch):
    """拦下 emit，返回它收到的 JSON 供断言。"""
    box = {}
    monkeypatch.setattr(pr_ops, "emit", box.update)
    monkeypatch.setattr(pr_ops, "get_token", lambda a: "t")
    monkeypatch.setattr(pr_ops, "read_body", lambda a: "x")
    return box


def test_reply_review_in_thread(monkeypatch, args, captured):
    """note_id 存在且回查 discussion_id 一致 → in_thread=true，无 warn。"""
    monkeypatch.setattr(pr_ops, "v5_post", lambda *a: (201, {"note_id": 9, "id": "hex"}))
    monkeypatch.setattr(
        pr_ops,
        "v5_get",
        lambda *a: (200, {"discussion_id": "abc", "comment_type": "DiffNote"}),
    )
    pr_ops.cmd_reply_review(args)
    assert captured["in_thread"] is True
    assert captured["note_id"] == 9
    assert captured["comment_type"] == "DiffNote"
    assert "warn" not in captured


def test_reply_review_missing_note_id(monkeypatch, args, captured):
    """响应缺 note_id → in_thread 无法判定，必须带 warn 并列出实际 keys。"""
    monkeypatch.setattr(pr_ops, "v5_post", lambda *a: (201, {"id": "hexonly"}))
    pr_ops.cmd_reply_review(args)
    assert captured["note_id"] is None
    assert captured["in_thread"] is None
    assert "note_id" in captured["warn"] and "id" in captured["warn"]


def test_reply_review_verify_failed(monkeypatch, args, captured):
    """回查非 200 → in_thread 静默为 None 不可接受，须带 warn 说明。"""
    monkeypatch.setattr(pr_ops, "v5_post", lambda *a: (201, {"note_id": 9}))
    monkeypatch.setattr(pr_ops, "v5_get", lambda *a: (500, "boom"))
    pr_ops.cmd_reply_review(args)
    assert captured["in_thread"] is None
    assert "回查失败" in captured["warn"]


def test_reply_review_post_failed_keeps_detail(monkeypatch, args, captured):
    """POST 失败时 detail 保留结构化响应（不 str() 截断丢字段）。"""
    payload = {"message": "boom", "code": "E1"}
    monkeypatch.setattr(pr_ops, "v5_post", lambda *a: (400, payload))
    with pytest.raises(pr_ops.PrOpsError) as err:
        pr_ops.cmd_reply_review(args)
    assert err.value.extra["detail"] == payload
    assert json.dumps(err.value.extra["detail"])


def test_review_maps_403_to_hint(monkeypatch, captured):
    """v4 写接口 403 → 报替代指引，而非原始 403。"""
    args = types.SimpleNamespace(
        owner="o", repo="r", pr=1, path="f.py", line=1, start_line=None,
        severity="suggestion", encoded_repo=None, body="x", body_file=None,
    )
    monkeypatch.setattr(
        pr_ops,
        "fetch_diff_refs",
        lambda *a: {"base_sha": "b", "start_sha": "s", "head_sha": "h"},
    )
    monkeypatch.setattr(pr_ops, "v4_post_discussion", lambda *a: (403, {"message": "x"}))
    with pytest.raises(pr_ops.PrOpsError) as err:
        pr_ops.cmd_review(args)
    assert "reply-review" in err.value.msg
