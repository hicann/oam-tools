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
"""Shared Markdown artifact contract for skills, retries, and resume.

The sole JSON fenced block is a structured section *inside* the Markdown file.
Separate JSON files are only execution state or compatibility inputs.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0"
STAGE_FILES = {
    "case_lookup": "case-match.md", "detect": "scenario.md",
    "clean": "clean-result.md", "diagnose": "diagnosis.md",
    "confidence": "confidence.md", "promote": "promotion.md", "report": "report.md",
}
OWNERS = {"case_lookup": "orchestrator-skill", "detect": "orchestrator-skill",
          "clean": "eval-skill", "diagnose": "eval-skill", "confidence": "eval-skill",
          "promote": "eval-skill", "report": "metric-skill"}
STATUSES = {"pending", "running", "success", "skipped", "failed", "blocked"}
FIELDS = ("schema_version", "run_id", "stage", "owner_skill", "status", "attempt",
          "started_at", "finished_at", "inputs", "outputs", "summary", "evidence_gaps",
          "error", "next_action", "result")
JSON_BLOCK = re.compile(r"^```json\s*\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def validate_artifact(data, stage=None, run_id=None, fingerprint=None):
    if not isinstance(data, dict) or any(key not in data for key in FIELDS):
        raise ValueError("Markdown artifact is missing required contract fields")
    if data["schema_version"] != SCHEMA_VERSION or data["stage"] not in STAGE_FILES:
        raise ValueError("Unsupported artifact schema or stage")
    if data["owner_skill"] != OWNERS[data["stage"]] or data["status"] not in STATUSES:
        raise ValueError("Invalid artifact owner or status")
    if not isinstance(data["attempt"], int) or isinstance(data["attempt"], bool) or data["attempt"] < 1:
        raise ValueError("attempt must be a positive integer")
    if not isinstance(data["run_id"], str) or not data["run_id"]:
        raise ValueError("run_id is required")
    for key in ("inputs", "result"):
        if not isinstance(data[key], dict):
            raise ValueError(key + " must be an object")
    for key in ("outputs", "evidence_gaps"):
        if not isinstance(data[key], list):
            raise ValueError(key + " must be an array")
    for key in ("summary", "next_action", "started_at"):
        if not isinstance(data[key], str):
            raise ValueError(key + " must be a string")
    try:
        datetime.fromisoformat(data["started_at"].replace("Z", "+00:00"))
        if data["status"] not in ("pending", "running"):
            datetime.fromisoformat(data["finished_at"].replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Artifact timestamps must be ISO 8601") from exc
    inputs = data["inputs"]
    if not all(key in inputs for key in ("fingerprint", "materials", "upstream", "parameters")):
        raise ValueError("inputs requires fingerprint/materials/upstream/parameters")
    if not re.fullmatch(r"[0-9a-f]{64}", str(inputs["fingerprint"])):
        raise ValueError("inputs.fingerprint must be SHA-256")
    if not isinstance(inputs["materials"], list) or not isinstance(inputs["upstream"], list) or not isinstance(inputs["parameters"], dict):
        raise ValueError("Invalid inputs types")
    for output in data["outputs"]:
        if not isinstance(output, dict) or not isinstance(output.get("path"), str) or not isinstance(output.get("kind"), str):
            raise ValueError("outputs entries require path and kind")
    error = data["error"]
    if error is not None and (not isinstance(error, dict) or not all(key in error for key in ("class", "code", "message"))):
        raise ValueError("error requires class/code/message")
    for actual, expected, label in ((data["stage"], stage, "stage"),
                                    (data["run_id"], run_id, "run_id"),
                                    (inputs["fingerprint"], fingerprint, "input fingerprint")):
        if expected is not None and actual != expected:
            raise ValueError("Artifact " + label + " does not match this execution")
    return data


def read_artifact(path, stage=None, run_id=None, fingerprint=None):
    text = Path(path).read_text(encoding="utf-8-sig")
    matches = list(JSON_BLOCK.finditer(text))
    if len(matches) != 1:
        raise ValueError("Artifact must contain exactly one fenced JSON contract block")
    data = json.loads(matches[0].group(1))
    validate_artifact(data, stage, run_id, fingerprint)
    body = (text[:matches[0].start()] + text[matches[0].end():]).strip()
    return data, body


def write_artifact(path, data, body=""):
    validate_artifact(data)
    if JSON_BLOCK.search(body):
        raise ValueError("Human-readable body must not contain another JSON block")
    # Escaping backticks keeps quoted log fragments from terminating the sole JSON fence.
    structured = json.dumps(data, ensure_ascii=False, indent=2).replace('`', '\\u0060')
    atomic_write(path, "```json\n" + structured +
                 "\n```\n\n" + (body.strip() or "# " + STAGE_FILES[data["stage"]] + "\n\n" + data["summary"]) + "\n")


def new_artifact(stage, run_id, attempt, inputs, output):
    return {"schema_version": SCHEMA_VERSION, "run_id": run_id, "stage": stage,
            "owner_skill": OWNERS[stage], "status": "running", "attempt": attempt,
            "started_at": now_iso(), "finished_at": None, "inputs": inputs,
            "outputs": [{"path": str(output), "kind": "primary_markdown"}],
            "summary": "", "evidence_gaps": [], "error": None, "next_action": "",
            "result": {}}
