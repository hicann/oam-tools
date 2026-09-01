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
#
"""Locate the formal Skill 1 config inside its output directory.

Current Skill 1 bundles publish ``analysis_config.json``. The old versioned filename is accepted
only through an explicit ``--config`` path, so an unreviewed legacy file can never silently win.
"""
import os

#: Only this filename participates in automatic discovery. ``analysis_config_v2.json`` remains
#: available through an explicit path for old bundles.
CONFIG_NAMES = ("analysis_config.json",)
LEGACY_CONFIG_NAMES = ("analysis_config_v2.json",)


def review_config_sha256(review):
    """Return the analysis-config digest recorded by a formal critique."""
    return (((review.get("artifacts") or {}).get("analysis_config") or {}).get("sha256")
            or review.get("config_sha256")
            or (review.get("bindings") or {}).get("config_sha256"))


def resolve_config(breakdown_dir, explicit=None):
    """Return the path to the breakdown config, or None when no candidate exists.

    `explicit` (a --config argument) always wins and is returned even if absent, so the caller
    reports the path the user actually asked for rather than a silently different one.
    """
    if explicit:
        return explicit
    current = os.path.join(breakdown_dir, CONFIG_NAMES[0])
    return current if os.path.exists(current) else None


def config_or_die(breakdown_dir, explicit=None):
    """Resolve the config or exit with the names that were tried."""
    path = resolve_config(breakdown_dir, explicit)
    if path and os.path.exists(path):
        return path
    tried = explicit or CONFIG_NAMES[0]
    raise SystemExit(f"No breakdown config in {breakdown_dir} (tried {tried})")


def is_convertible_score(score):
    """Require every formal Skill 1 score gate; legacy status-only scores are rejected."""
    return bool(
        score.get("passed_at_cap") is True
        and score.get("convertible") is True
        and (score.get("hard_gates") or {}).get("passed") is True
        and (score.get("critique_gates") or {}).get("passed") is True
    )


def require_breakdown_ready(breakdown_dir, explicit_config=None, script=None):
    """Require the complete formal Skill 1 handoff before emitting UI artifacts."""
    # Imported lazily because check_breakdown_ready imports this module for path and score
    # helpers. The checker itself only calls is_convertible_score(), so this does not recurse
    # after both modules have finished loading.
    from check_breakdown_ready import check

    _, blockers = check(breakdown_dir, explicit_config)
    if blockers:
        details = "\n  - ".join(blockers)
        raise SystemExit(
            f"{script or 'this stage'}: breakdown did not clear the formal Skill 1 "
            f"readiness gate:\n  - {details}\n"
            "Fix the breakdown and regenerate all five formal files before converting it."
        )
