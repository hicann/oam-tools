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
"""Refuse to convert a breakdown that has not earned it.

A conversion inherits every claim the breakdown makes. Exploratory runs, migrated
legacy configs, and stale semantic reviews all produce a report that looks
authoritative while resting on unverified attribution, so they are rejected here
rather than downstream.
"""
import argparse
import hashlib
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import breakdown_paths  # noqa: E402


logger = logging.getLogger(__name__)

REQUIRED_CONFIG_KEYS = ("schema_version", "architecture", "trace_scope",
                        "structures", "stages", "runtime_auxiliary")
VALID_SCOPE_KINDS = ("full_model", "rank_local", "pipeline_stage_local", "unknown")

#: Validation issue ids that report an architecture scalar the supplied files cannot confirm,
#: rather than a structural defect in the decomposition. Kept in sync with the breakdown
#: skill's `score_breakdown.DATA_AVAILABILITY_ISSUE_IDS`.
DATA_AVAILABILITY_ISSUE_IDS = frozenset({"A1", "MT1", "MA1", "SR_EVIDENCE_GAP_FINDING"})


def jload(path):
    with open(path) as handle:
        return json.load(handle)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ReadinessChecks:
    """Accumulate readiness checks and the subset that blocks conversion."""

    def __init__(self):
        self.checks = []
        self.blockers = []

    def record(self, ok, label, detail=""):
        self.checks.append({"ok": bool(ok), "check": label, "detail": detail})
        if not ok:
            self.blockers.append(f"{label}{f': {detail}' if detail else ''}")
        return ok


def check_config_shape(state, config):
    state.record(config.get("schema_version") == 2, "config is schema v2",
                 f"found {config.get('schema_version')!r}")
    missing = [key for key in REQUIRED_CONFIG_KEYS if key not in config]
    state.record(not missing, "config declares every required block",
                 f"missing {missing}" if missing else "")
    migration = config.get("migration") or {}
    if migration:
        state.record(migration.get("status") != "legacy_unverified",
                     "config is not an unverified legacy migration",
                     f"migration.status={migration.get('status')!r}")
    unmapped = config.get("unmapped_ops") or []
    state.record(not unmapped, "unmapped_ops is empty",
                 f"{len(unmapped)} unmapped ops" if unmapped else "")
    scope = (config.get("trace_scope") or {}).get("kind")
    state.record(scope in VALID_SCOPE_KINDS, "trace_scope.kind is declared", f"found {scope!r}")


def check_validation(state, breakdown_dir):
    validation_path = os.path.join(breakdown_dir, "validation_report.json")
    if not state.record(os.path.exists(validation_path), "validation_report.json exists"):
        return
    validation = jload(validation_path)
    blocking = []
    for issue in validation.get("issues", []):
        is_error = issue.get("severity") == "error"
        is_blocking_warning = (
            issue.get("severity") == "warning"
            and issue.get("id") not in DATA_AVAILABILITY_ISSUE_IDS
        )
        if is_error or is_blocking_warning:
            blocking.append(issue)
    status = validation.get("status")
    detail = f"status={status!r}"
    if blocking:
        detail += f"; blocking issues {[issue.get('id') for issue in blocking]}"
    state.record(status in ("passed", "passed_with_warnings") and not blocking,
                 "validation status is convertible", detail)


def check_score(state, breakdown_dir):
    score_path = os.path.join(breakdown_dir, "breakdown_score.json")
    if not state.record(os.path.exists(score_path), "breakdown_score.json exists"):
        return
    score = jload(score_path)
    status = score.get("status")
    state.record(breakdown_paths.is_convertible_score(score),
                 "score conclusion is convertible",
                 f"status={status!r} convertible={score.get('convertible')!r} "
                 f"score={score.get('score')!r}")


def check_semantic_review(state, breakdown_dir, config_path):
    review_path = os.path.join(breakdown_dir, "semantic_review.json")
    if not state.record(os.path.exists(review_path), "semantic_review.json exists"):
        return
    review = jload(review_path)
    bound = (((review.get("artifacts") or {}).get("analysis_config") or {}).get("sha256")
             or review.get("config_sha256")
             or (review.get("bindings") or {}).get("config_sha256"))
    if not bound:
        state.record(False, "semantic review is bound to the config by SHA256",
                     "review records no config_sha256, so staleness cannot be verified; "
                     "re-run prepare_semantic_review.py against the current config")
        return
    actual = sha256(config_path)
    detail = "review was produced for a different config revision" if bound != actual else ""
    state.record(bound == actual, "semantic review still matches the config", detail)


def check(breakdown_dir, config_override=None):
    """Return (checks, blockers). A blocker means do not convert."""
    state = ReadinessChecks()

    config_path = breakdown_paths.resolve_config(breakdown_dir, config_override)
    label = f"{os.path.basename(config_path)} exists" if config_path else "breakdown config exists"
    detail = config_path or f"none of {' / '.join(breakdown_paths.CONFIG_NAMES)} in {breakdown_dir}"
    if not state.record(config_path and os.path.exists(config_path), label, detail):
        return state.checks, state.blockers
    config = jload(config_path)
    check_config_shape(state, config)
    check_validation(state, breakdown_dir)
    check_score(state, breakdown_dir)
    check_semantic_review(state, breakdown_dir, config_path)
    return state.checks, state.blockers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--breakdown", required=True,
                        help="directory holding the breakdown config and its reports")
    parser.add_argument("--config",
                        help="explicit config path; defaults to "
                             f"{' or '.join(breakdown_paths.CONFIG_NAMES)} in --breakdown")
    parser.add_argument("--out", help="write the readiness record here")
    args = parser.parse_args()

    checks, blockers = check(args.breakdown, args.config)
    ready = not blockers
    record = {
        "schema_version": 1,
        "breakdown": os.path.abspath(args.breakdown),
        "ready": ready,
        "checks": checks,
        "blockers": blockers,
    }
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=1)
            handle.write("\n")

    for item in checks:
        logger.info("%s  %s%s", "PASS" if item["ok"] else "FAIL", item["check"],
                    f"  — {item['detail']}" if item["detail"] else "")
    logger.info("")
    if ready:
        logger.info("READY  %s checks passed; conversion may proceed", len(checks))
        return 0
    logger.error("NOT READY  %s blocker(s):", len(blockers))
    for blocker in blockers:
        logger.error("  - %s", blocker)
    logger.error("\nFix the breakdown. Do not convert an unverified breakdown.")
    return 1


if __name__ == "__main__":
    sys.exit(breakdown_paths.run_cli(main))
