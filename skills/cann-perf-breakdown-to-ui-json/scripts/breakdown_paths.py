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
"""Locate a breakdown's config inside its output directory.

Stage 1 writes `analysis_config_v2.json`, but a delivered bundle often renames it to
`analysis_config.json`. Hardcoding one spelling made a correct breakdown fail the readiness
gate for a filename, so every stage resolves the config through here instead.
"""
import json
import logging
import os
import sys


logger = logging.getLogger(__name__)
error_logger = logging.getLogger(f"{__name__}.errors")
error_logger.propagate = False


class ConversionError(ValueError):
    """A user-facing conversion failure with a stable CLI exit code."""

    def __init__(self, message, exit_code=1, stdout=False):
        super().__init__(message)
        self.exit_code = exit_code
        self.stdout = stdout


def run_cli(main):
    """Run a conversion CLI with message-only stdout logging and clean failures."""
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
    try:
        result = main()
    except ConversionError as error:
        if error.stdout:
            logger.error("%s", error)
        else:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(logging.Formatter("%(message)s"))
            error_logger.addHandler(handler)
            try:
                error_logger.error("%s", error)
            finally:
                error_logger.removeHandler(handler)
                handler.close()
        return error.exit_code
    return 0 if result is None else result


def load_json(path):
    """Load one UTF-8 JSON document."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(document, path):
    """Write one UTF-8 JSON document using the adapter's stable format."""
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=1)
        handle.write("\n")


#: Accepted spellings, most specific first. The v2 name wins when both exist, since a directory
#: holding both is mid-migration and the versioned file is the one stage 1 just wrote.
CONFIG_NAMES = ("analysis_config_v2.json", "analysis_config.json")


def resolve_config(breakdown_dir, explicit=None):
    """Return the path to the breakdown config, or None when no candidate exists.

    `explicit` (a --config argument) always wins and is returned even if absent, so the caller
    reports the path the user actually asked for rather than a silently different one.
    """
    if explicit:
        return explicit
    for name in CONFIG_NAMES:
        candidate = os.path.join(breakdown_dir, name)
        if os.path.exists(candidate):
            return candidate
    return None


def config_or_die(breakdown_dir, explicit=None):
    """Resolve the config or exit with the names that were tried."""
    path = resolve_config(breakdown_dir, explicit)
    if path and os.path.exists(path):
        return path
    tried = explicit or " / ".join(CONFIG_NAMES)
    raise ConversionError(f"No breakdown config in {breakdown_dir} (tried {tried})")


#: Score statuses a conversion may be built from. The tiered statuses all mean "every check the
#: inputs permitted has passed"; they differ only in how much the inputs permitted, which the
#: report states as provenance rather than withholding the report.
CONVERTIBLE_STATUSES = ("passed", "verified", "verified_unbound_scalars",
                        "structure_unverified")


def is_convertible_score(score):
    """Honor the explicit tiered gate and retain status-only legacy compatibility."""
    status_ok = score.get("status") in CONVERTIBLE_STATUSES
    if "convertible" in score:
        return score.get("convertible") is True and status_ok
    return status_ok


def add_score_gate_args(parser):
    """Give a build script the same score gate `run_pipeline.py` applies."""
    parser.add_argument("--allow-unscored", action="store_true",
                        help="build from a breakdown that has not earned conversion. The "
                             "result is exploratory and says so in the report; it is not a "
                             "formal result.")


def require_convertible_score(breakdown_dir, allow_unscored=False, script=None):
    """Refuse to build UI artifacts from a breakdown that failed its own scoring.

    `run_pipeline.py` has always gated on this, but the build scripts it calls did not, and
    SKILL.md documents them as individually runnable. That left the gate guarding one path out
    of two: gemma's score said `needs_iteration` at 15:54 and a full report was assembled at
    15:58 anyway, showing an architecture graph with every residual edge missing. A gate one
    `python3` invocation can walk around is a suggestion.

    Returns the score document (or None when the gate was explicitly waived).
    """
    score_path = os.path.join(breakdown_dir, "breakdown_score.json")
    if not os.path.exists(score_path):
        if allow_unscored:
            return None
        raise ConversionError(
            f"{script or 'this stage'}: no breakdown_score.json in {breakdown_dir}. "
            "Score the breakdown first, or pass --allow-unscored to build an exploratory "
            "report that is labelled as unverified.")
    score = load_json(score_path)
    status = score.get("status")
    if is_convertible_score(score):
        return score
    if allow_unscored:
        return score
    failed = score.get("failed_dimensions") or []
    actions = (score.get("required_actions") or [])[:3]
    raise ConversionError(
        f"{script or 'this stage'}: breakdown_score.json says status={status!r} "
        f"convertible={score.get('convertible')!r} score={score.get('score')!r}; "
        f"failed dimensions {failed}. "
        "Fix the breakdown rather than converting it. "
        + (f"Next: {' | '.join(actions)}. " if actions else "")
        + "Pass --allow-unscored only to produce an explicitly exploratory report.")
