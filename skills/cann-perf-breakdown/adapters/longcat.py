# Copyright (c) 2026 Huawei Technologies Co., Ltd.
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
"""LongCat Flash (Lite) adapter.

LongCat uses `num_layers` (with a `num_hidden_layers` property alias) and is
all-MoE (no first_k_dense boundary). It also carries num_nextn_predict_layers.
"""
from .base import BaseAdapter, Fact, rel_ref


class LongcatAdapter(BaseAdapter):
    name = 'longcat'
    main_layer_count_keys = ('num_layers', 'num_hidden_layers')
    prediction_count_keys = ('num_nextn_predict_layers',)
    dense_boundary_keys = ('first_k_dense_replace',)   # absent -> all-MoE
    moe_expert_keys = ('n_routed_experts',)

    capability_keys = {
        'moe': ('n_routed_experts',),
        'zero_expert': ('zero_expert_num', 'n_zero_experts'),
        'mtp': ('num_nextn_predict_layers',),
    }

    #: Candidate hints only — resolved against this model's own op sequence.
    kernel_anchors = {
        'attention_core': ('FlashAttentionScore', 'PromptFlashAttention',
                           'IncreFlashAttention'),
        'router_gating': ('MoeGatingTopKSoftmax', 'TopKSoftmax'),
        'expert_dispatch': ('MoeInitRouting', 'MoeDistributeDispatch'),
        'expert_combine': ('MoeFinalizeRouting', 'MoeDistributeCombine'),
        'grouped_matmul': ('GroupedMatmul', 'GroupedMatMul'),
        'fused_add_norm': ('AddRmsNorm', 'AddRMSNorm'),
    }

    #: LongCat's layer runs two attention blocks around the MoE, so a single-attention
    #: template silently halves the attention cost. Checked against the derived graph.
    dataflow_invariants = (
        {'id': 'dual_attention_per_layer',
         'requires': None,
         'kind': 'min_call_occurrences',
         'match_any': ['attention', 'attn'],
         'min_occurrences': 2,
         'reason': 'LongCat 单层内有两个 attention 块；只声明一个会让 attention 耗时腰斩'},
    )

    known_deviations = (
        {'id': 'zero_expert_routing_data_dependent',
         'reason': 'zero-expert 是否被选中取决于运行期 router 输出，'
                   '静态分析只能确认该支路存在，不能确认它在某次采集中被走过'},
        {'id': 'multiple_config_classes',
         'reason': 'config 模块同时定义 LongcatFlashConfig 与 LongcatFlashNgramConfig，'
                   '两者层数/专家数不同；以 modeling 源码实际 import 的那个为准'},
    )

    def matches(self, evidence):
        classes = evidence.get('class_names', set())
        keys = evidence.get('config_keys', set())
        reasons = []
        named = sorted(c for c in classes if 'Longcat' in c or 'LongCat' in c)
        if named:
            reasons.append(f'class 名含 LongCat: {named[:3]}')
        # Signature: num_layers + experts, and no dense boundary (LongCat is all-MoE).
        if ('num_layers' in keys and 'n_routed_experts' in keys
                and 'first_k_dense_replace' not in keys):
            reasons.append('config 含 num_layers + n_routed_experts 且无 first_k_dense_replace')
        if not reasons:
            return False
        return ('high' if named else 'medium'), reasons
