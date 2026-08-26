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
"""Qwen (7B) adapter.

Qwen7B is a plain dense transformer: num_hidden_layers, QWenBlock, no MoE, no MTP.
"""
from .base import BaseAdapter


class QwenAdapter(BaseAdapter):
    name = 'qwen'
    main_layer_count_keys = ('num_hidden_layers',)
    prediction_count_keys = ()
    dense_boundary_keys = ()
    moe_expert_keys = ('n_routed_experts', 'num_experts')  # future Qwen-MoE; absent in 7B

    #: 7B evidences none of these; they fire only for a Qwen variant that actually has
    #: the keys. Declaring `moe` unconditionally would make a dense model fail D7.
    capability_keys = {
        'moe': ('n_routed_experts', 'num_experts'),
        'shared_expert': ('shared_expert_intermediate_size',),
    }

    #: Candidate hints only.
    kernel_anchors = {
        'attention_core': ('FlashAttentionScore', 'PromptFlashAttention',
                           'IncreFlashAttention'),
        'fused_add_norm': ('AddRmsNorm', 'AddRMSNorm'),
    }

    def matches(self, evidence):
        classes = evidence.get('class_names', set())
        named = sorted(c for c in classes if c.startswith('QWen') or c.startswith('Qwen'))
        if not named:
            return False
        return 'high', [f'class 名以 QWen/Qwen 开头: {named[:3]}']
