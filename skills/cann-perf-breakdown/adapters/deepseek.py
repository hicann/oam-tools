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
"""DeepSeek V3 / V3.2 adapter.

Facts still come from the model's own source via AST — this adapter only knows
*where* to look (config key names, is_moe predicate, MTP ModuleDict shape).
"""
from .base import BaseAdapter


class DeepseekAdapter(BaseAdapter):
    name = 'deepseek'
    main_layer_count_keys = ('num_hidden_layers',)
    prediction_count_keys = ('num_nextn_predict_layers',)
    dense_boundary_keys = ('first_k_dense_replace',)
    moe_expert_keys = ('n_routed_experts',)
    shared_expert_keys = ('n_shared_experts',)
    experts_per_token_keys = ('num_experts_per_tok',)

    #: A capability is asserted only when one of its keys is actually present in this
    #: source. `n_shared_experts` is what makes the shared-expert parallel path real; the
    #: V3.2 sparse indexer shows up as index_topk/index_n_heads.
    capability_keys = {
        'moe': ('n_routed_experts', 'first_k_dense_replace'),
        'shared_expert': ('n_shared_experts',),
        'mtp': ('num_nextn_predict_layers',),
        'mla': ('kv_lora_rank', 'q_lora_rank'),
        'sparse_index_attention': ('index_topk', 'index_n_heads'),
    }

    #: V3.2's `index_topk`/`index_n_heads` live in a separate `DeepseekV3IndexConfig` that
    #: the main `DeepseekV3Config` does not inherit, so the config-value channel above never
    #: sees them. The indexer module existing in the modeling source is the evidence.
    capability_class_hints = {
        'sparse_index_attention': ('IndexerAttention', 'Indexer'),
    }

    #: CANDIDATE HINTS for op mapping, never a required table: the same semantic carries
    #: different kernel names across op-library versions and quantisation modes. The
    #: mapper's anchor must still come from this model's own op sequence.
    kernel_anchors = {
        'attention_core': ('FlashAttentionScore', 'PromptFlashAttention',
                           'IncreFlashAttention', 'MLAProlog'),
        'router_gating': ('MoeGatingTopKSoftmax', 'TopKSoftmax'),
        'expert_dispatch': ('MoeInitRouting', 'MoeDistributeDispatch'),
        'expert_combine': ('MoeFinalizeRouting', 'MoeDistributeCombine'),
        'grouped_matmul': ('GroupedMatmul', 'GroupedMatMul'),
        'fused_add_norm': ('AddRmsNorm', 'AddRMSNorm'),
    }

    #: Dataflow shapes the family must exhibit, gated on the capability being evidenced.
    #: These are checked against the AST-derived graph, not asserted from the name.
    dataflow_invariants = (
        {'id': 'shared_expert_parallel',
         'requires': 'shared_expert',
         'reason': '共享专家与路由专家读同一份 MoE 输入，在 combine 点汇合；'
                   '写成串行链会把并行支路的耗时算进主链'},
    )

    known_deviations = (
        {'id': 'quantisation_gated_arms',
         'reason': 'w8a8/量化分支由部署配置在运行前固定，属 config-gated：'
                   '应作为 variants 提取并绑定 execution profile，而非 data-dependent'},
        {'id': 'index_config_not_inherited',
         'reason': 'index_topk/index_n_heads 定义在 DeepseekV3IndexConfig，'
                   '主 config 不继承；sparse indexer 由 modeling 源码的类存在性判定'},
    )

    def matches(self, evidence):
        classes = evidence.get('class_names', set())
        keys = evidence.get('config_keys', set())
        reasons = []
        named = sorted(c for c in classes if 'Deepseek' in c or 'DeepSeek' in c)
        if named:
            reasons.append(f'class 名含 Deepseek: {named[:3]}')
        signature = {'first_k_dense_replace', 'num_nextn_predict_layers'}
        if signature <= keys:
            reasons.append('config 同时含 first_k_dense_replace 与 num_nextn_predict_layers')
        if not reasons:
            return False
        # A class name is the family declaring itself; a key signature only says the config
        # is shaped like this family's, which a derivative could also satisfy.
        return ('high' if named else 'medium'), reasons
