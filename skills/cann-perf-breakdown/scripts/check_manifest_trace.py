#!/usr/bin/env python3
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
"""Cross-check a manifest's layer count against per-layer kernel repetition in the trace.

The manifest is static: it reports what the source says. The trace is empirical: it
records what actually ran. When they disagree the manifest is usually the wrong one,
because Python default args describe a model family while the trace describes the
deployed checkpoint.

This check needs no source reading and no AI judgement. If a kernel type appears once
per layer, its count IS the layer count; 61 layers cannot produce 28 attention kernels.
That single arithmetic fact is what makes a confidently-wrong manifest visible.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import breakdown_common as bc  # noqa: E402  (needs HERE on sys.path)

#: Kernels that occur a small fixed number of times per decoder layer. Each is a strong
#: layer-count witness because no runtime fuses or splits them away: attention cores and
#: MoE gates are emitted once per attention / once per MoE block, always.
#: Matched as name prefixes, not exact keys: vendors version and suffix these kernels
#: (`MlaPrologV3`, `MoeGatingTopKHash`, `MoeInitRoutingV3`), so an exact lookup silently
#: matches nothing and the check reports `passed` having tested no witness at all.
LAYER_WITNESS_KERNELS = (
    'FusedInferAttentionScore',
    'PromptFlashAttention',
    'IncreFlashAttention',
    'FlashAttentionScore',
    'MoeGatingTopK',
    'MoeInitRoutingV3',
    'KvRmsNormRopeCache',
    # One MLA prolog per attention block; the DS-family per-layer anchor the mapping
    # protocol already names as the attention entry point.
    'MlaProlog',
    'KvQuantSparseFlashAttention',
)

#: Witnesses that only occur in MoE layers. Dividing these by the *main* layer count reports
#: every partially-MoE model as inconsistent: a stack with 1 dense + 1 MoE layer emits one gate,
#: and 1 % 2 != 0. The divisor for these is the MoE layer count, which the manifest declares via
#: `layer_groups[].classification`. Attention witnesses keep spanning the whole stack.
MOE_ONLY_WITNESSES = ('MoeGatingTopK', 'MoeInitRoutingV3')

#: A witness count must divide evenly by the layer count to be consistent. Allow the
#: usual small per-layer multiplicities (dual sub-layer, separate q/k, MTP tail).
PLAUSIBLE_PER_LAYER = (1, 2, 3, 4, 6, 8)


def _moe_layer_count(manifest):
    """Number of MoE-classified main layers, or None when the manifest does not say.

    A prediction module counts only when it is explicitly classified `moe`. An unclassified
    module is unknown, not assumed MoE: guessing inflates the divisor and turns a consistent
    trace into a reported mismatch. The extra invocations a prediction module contributes are
    already absorbed by the per-layer tail tolerance below.
    """
    groups = manifest.get('layer_groups') or []
    if not groups:
        return None
    counted = list(groups) + list(manifest.get('prediction_modules') or [])
    total = sum(len(bc.expand_layer_group_indices(group)) for group in counted
                if str(group.get('classification') or '').lower() == 'moe')
    return total or None


def _implied_layers(witnesses):
    """Largest N for which every witness count is a plausible per-layer multiple of N.

    This is reported for the reader, never used to overrule the manifest: witnesses cover
    different subsets of the stack, so N is a hypothesis the checkpoint config must confirm.
    Returns None when no single N fits.
    """
    if not witnesses:
        return None
    counts = sorted(witnesses.values())
    for candidate in range(counts[0], 0, -1):
        if all(c % candidate == 0 and (c // candidate) in PLAUSIBLE_PER_LAYER
               for c in counts):
            return candidate
    return None


def _counts(raw_ops):
    counts = {}
    for op in raw_ops.get('operators', []):
        name = op.get('normalized_name') or op.get('name') or ''
        repeat = op.get('repeat') or op.get('count') or 1
        if not isinstance(repeat, int) or repeat < 1:
            repeat = 1
        counts[name] = counts.get(name, 0) + repeat
    return counts


#: Kernels that only an executed MoE path emits. Their presence is qualitative evidence:
#: it does not tell you how many experts or layers, only that expert routing ran at all.
MOE_WITNESS_PREFIXES = ('MoeGatingTopK', 'MoeInitRouting', 'MoeComputeExpertTokens',
                        'GroupedMatmul', 'MoeFinalizeRouting', 'MoeDistribute')


def _check_classification(manifest, counts, issues, detail):
    """MT2 — qualitative: does the declared classification admit what the trace ran?

    MT1 is arithmetic (a per-layer kernel count must divide by the layer count) and so it
    passes whenever the counts happen to divide, no matter what the layers are called. A
    manifest that says every layer is dense while the trace is full of expert-routing
    kernels satisfies MT1 and still describes a different model than the one that ran.
    """
    groups = manifest.get('layer_groups') or []
    if not groups:
        return
    classes = {str(g.get('classification') or '').lower() for g in groups}
    moe_hits = {name: n for name, n in counts.items()
                if any(name.startswith(p) for p in MOE_WITNESS_PREFIXES) and n}
    detail['trace_moe_witnesses'] = moe_hits

    if moe_hits and classes and classes <= {'dense'}:
        witness_text = ', '.join(f'{k}={v}' for k, v in sorted(moe_hits.items())[:5])
        confidence = bc.manifest_fact_confidence(manifest)
        # Unlike MT1, no scalar is in dispute here and the trace cannot be wrong about a
        # kernel it recorded: expert routing either ran or it did not. A low-confidence
        # manifest (unbound MoE key, unreachable checkpoint) has no authority to override
        # that, so this is an error rather than a note.
        issues.append({
            'id': 'MT2', 'severity': 'error',
            'node_path': 'model_manifest.layer_groups',
            'message': (f'manifest 声明全部层为 dense，但 trace 存在 MoE 算子（{witness_text}）。'
                        f'部署的模型与 manifest 架构分类不符'
                        f'（manifest 置信度 {confidence}）。'
                        f'请按 checkpoint config.json 或 trace 证据修正 classification')})
    elif not moe_hits and classes and 'moe' in classes:
        issues.append({
            'id': 'MT2', 'severity': 'warning',
            'node_path': 'model_manifest.layer_groups',
            'message': ('manifest 声明存在 MoE 层，但 trace 无任何 MoE 算子：'
                        '可能是 enable_moe_block=False 的 dense 部署，或该 step 未走到专家路径')})


def _layer_witness_counts(counts):
    witnesses = {}
    for prefix in LAYER_WITNESS_KERNELS:
        total = sum(count for name, count in counts.items() if name.startswith(prefix))
        if total:
            witnesses[prefix] = total
    return witnesses


def _inconsistent_witnesses(witnesses, num_main, moe_layers, detail):
    inconsistent = {}
    for kernel, count in sorted(witnesses.items()):
        is_moe_only = any(kernel.startswith(prefix) for prefix in MOE_ONLY_WITNESSES)
        divisor = moe_layers if (is_moe_only and moe_layers) else num_main
        implied = count / divisor
        detail['implied_layer_counts'][kernel] = count
        if count % divisor == 0 and (count // divisor) in PLAUSIBLE_PER_LAYER:
            continue
        salvaged = any(0 < count - per_layer * divisor <= 2 * per_layer
                       for per_layer in PLAUSIBLE_PER_LAYER)
        if not salvaged:
            inconsistent[kernel] = {
                'count': count,
                'per_layer_if_manifest': round(implied, 3),
                'divisor': divisor,
                'scope': 'moe_layers' if divisor == moe_layers else 'main_layers',
            }
    return inconsistent


def _mt1_issue(manifest, witnesses, inconsistent, num_main, detail):
    witness_text = ', '.join(f'{key}={value["count"]}'
                             for key, value in sorted(inconsistent.items()))
    message = (f'manifest 声明 {num_main} 层，但 trace 的 per-layer kernel 数量无法被其整除'
               f'（{witness_text}）')
    distinct = set(witnesses.values())
    if len(distinct) == 1:
        observed = distinct.pop()
        message += (f'；每个 witness 均出现 {observed} 次，说明本次采集观测到 {observed} 次'
                    f'per-layer 调用（调用次数，不等于层数）')
        detail['observed_invocations'] = observed
    else:
        message += ('；各 witness 计数不一致，说明它们覆盖的层子集不同'
                    '（如注意力锚点跨 dense+MoE+MTP，MoE gate 仅跨 MoE+MTP），'
                    '无法反推单一层数')
        detail['witness_scopes_differ'] = True
    message += '。请核对 checkpoint config.json 与实际加载的权重'
    confidence = bc.manifest_fact_confidence(manifest)
    message += (f'（manifest 置信度 {confidence}；trace 仅为辅助证据，不裁定层数，'
                f'需由 checkpoint config.json 确认。trace 能证伪的只有覆盖率，见 C1）')
    detail['manifest_confidence'] = confidence
    detail['inconsistent_witnesses'] = inconsistent
    return {'id': 'MT1', 'severity': 'warning',
            'node_path': 'model_manifest.num_main_layers', 'message': message}


def check_manifest_trace(manifest, raw_ops):
    """Return (issues, detail). Never raises on odd input; absent evidence -> no issue."""
    issues = []
    num_main = manifest.get('num_main_layers')
    counts = _counts(raw_ops)
    witnesses = _layer_witness_counts(counts)

    moe_layers = _moe_layer_count(manifest)
    _check_classification(manifest, counts, issues, detail_sink := {})
    detail = {'manifest_num_main_layers': num_main,
              'witness_counts': witnesses,
              'moe_layer_count': moe_layers,
              **detail_sink,
              # The layer count the trace alone would support, for the reader. Never authoritative:
              # see the MT1 message and the comment at the issue site.
              'trace_implied_layers': _implied_layers(witnesses),
              'implied_layer_counts': {}}

    if not witnesses:
        detail['note'] = 'trace 中没有可用于反推层数的 witness kernel，跳过'
        return issues, detail
    if not isinstance(num_main, int) or num_main <= 0:
        detail['note'] = 'manifest num_main_layers 不是正整数，跳过'
        return issues, detail

    inconsistent = _inconsistent_witnesses(witnesses, num_main, moe_layers, detail)
    if inconsistent:
        issues.append(_mt1_issue(manifest, witnesses, inconsistent, num_main, detail))

    return issues, detail


def main():
    parser = argparse.ArgumentParser(
        description='Cross-check model_manifest layer count against trace kernel counts')
    parser.add_argument('-m', '--manifest', required=True)
    parser.add_argument('-r', '--raw-ops', required=True)
    parser.add_argument('-o', '--output')
    args = parser.parse_args()

    with open(args.manifest, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    with open(args.raw_ops, 'r', encoding='utf-8') as f:
        raw_ops = json.load(f)

    issues, detail = check_manifest_trace(manifest, raw_ops)
    errors = [i for i in issues if i['severity'] == 'error']
    report = {'script': 'check_manifest_trace.py',
              'status': 'failed' if errors else
                        ('passed_with_warnings' if issues else 'passed'),
              'error_count': len(errors),
              'warning_count': len(issues) - len(errors),
              'issues': issues, 'detail': detail}
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
        bc.emit(f'manifest/trace 交叉校验已写入: {args.output}  status={report["status"]}')
    else:
        bc.emit(text)
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
