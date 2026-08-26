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
#
"""Model-family adapters for architecture extraction.

Adapters ONLY encapsulate static-extraction differences between model families.
They must never hardcode architecture numbers without a source_ref: every value
an adapter returns is read from the model's own configuration/modeling source via
AST, and carries the file:line it came from.

Selection is by evidence (class names / config keys found in the source), never by
a caller-supplied model name string alone, and never by position in this list.
"""
from .base import BaseAdapter, Fact, GENERIC
from .deepseek import DeepseekAdapter
from .gemma import GemmaAdapter
from .qwen import QwenAdapter
from .longcat import LongcatAdapter

#: Registration order carries NO meaning for selection -- see `resolve_adapter`. It only
#: fixes the order ambiguous candidates are reported in, so the error message is stable.
ADAPTERS = [
    DeepseekAdapter(),
    LongcatAdapter(),
    GemmaAdapter(),
    QwenAdapter(),
]

CONFIDENCE_RANK = {'high': 3, 'medium': 2, 'low': 1}


class AmbiguousAdapterError(Exception):
    """Two or more families claim this source with equal, top-tier confidence.

    Resolving this by list order is what makes a misread architecture invisible: the
    manifest would name one family, carry that family's layer-count and MoE-boundary key
    spellings, and look exactly as authoritative as a correct one. The source genuinely
    matches both signatures -- that is a fact the caller has to see and settle, not
    something this module may decide.
    """

    def __init__(self, candidates):
        self.candidates = candidates
        names = ', '.join(f"{c['adapter']}({c['confidence']})" for c in candidates)
        super().__init__(
            f'适配器选择歧义：{names} 同时以最高置信度匹配同一份源码。'
            f'不按注册顺序裁决——请补充区分性证据（config key / class 名）'
            f'或显式指定适配器。理由：'
            + ' | '.join(f"{c['adapter']}: {'; '.join(c['reasons']) or '未给出理由'}"
                         for c in candidates))


def _normalise(result):
    """Read a `matches()` return value as (confidence, reasons) or None.

    A bare `True` is still accepted so adapters written against the original protocol keep
    working; it is read as 'medium' because a boolean carries no strength information and
    claiming 'high' on its behalf would let it win a tier it never asserted.
    """
    if result is None or result is False:
        return None
    if result is True:
        return 'medium', []
    try:
        confidence, reasons = result
    except (TypeError, ValueError):
        return 'medium', []
    if confidence not in CONFIDENCE_RANK:
        confidence = 'medium'
    return confidence, list(reasons or [])


def resolve_adapter(evidence: dict):
    """Return a selection record: {adapter, confidence, reasons, candidates, ambiguous}.

    Every adapter is consulted; the highest confidence tier wins. A single candidate in
    that tier is the answer. Two or more raise `AmbiguousAdapterError` -- see there for
    why this is not resolved silently. No match at all falls back to the generic base,
    which asserts no family knowledge.
    """
    candidates = []
    for adapter in ADAPTERS:
        verdict = _normalise(adapter.matches(evidence))
        if verdict is None:
            continue
        confidence, reasons = verdict
        candidates.append({'adapter': adapter.name, 'confidence': confidence,
                           'reasons': reasons, '_obj': adapter})

    if not candidates:
        return {'adapter': GENERIC, 'name': GENERIC.name, 'confidence': 'unknown',
                'reasons': ['没有任何族签名匹配；使用不含族知识的 generic 基类'],
                'candidates': [], 'ambiguous': False}

    top = max(CONFIDENCE_RANK[c['confidence']] for c in candidates)
    winners = [c for c in candidates if CONFIDENCE_RANK[c['confidence']] == top]
    reported = [{k: v for k, v in c.items() if k != '_obj'} for c in candidates]
    if len(winners) > 1:
        raise AmbiguousAdapterError([{k: v for k, v in w.items() if k != '_obj'}
                                     for w in winners])
    winner = winners[0]
    return {'adapter': winner['_obj'], 'name': winner['adapter'],
            'confidence': winner['confidence'], 'reasons': winner['reasons'],
            'candidates': reported, 'ambiguous': False}


def select_adapter(evidence: dict):
    """The adapter for this evidence. Raises `AmbiguousAdapterError` on a tie."""
    return resolve_adapter(evidence)['adapter']
