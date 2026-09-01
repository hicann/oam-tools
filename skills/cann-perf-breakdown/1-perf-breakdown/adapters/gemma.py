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
"""Gemma 4 adapter.

No MTP. Sliding/full attention follows a `layer_types` pattern built in the config
__init__; classifying individual layers requires evaluating that runtime-built list, so
when it cannot be resolved to literal indices the per-layer sliding/full split is left as
an evidence gap rather than guessed.

Gemma 4 is NOT unconditionally dense. The 26B-A4B variant carries a
`Gemma4SparseMoeBlock` in every decoder layer, gated by `enable_moe_block`, alongside the
dense `Gemma4MLP` -- the two coexist per layer rather than splitting the stack into dense
and MoE ranges, which is why `dense_boundary_keys` is still empty while `moe_expert_keys`
is not. Declaring the family dense would drop the expert path from every layer of a
deployment that has the flag on.
"""
import ast
from .base import BaseAdapter, Fact, rel_ref


class GemmaAdapter(BaseAdapter):
    name = 'gemma'
    main_layer_count_keys = ('num_hidden_layers',)
    prediction_count_keys = ()          # no MTP
    #: Empty NOT because the family is dense, but because there is no dense/MoE *boundary*:
    #: the expert block sits in every layer next to the dense MLP (see module docstring).
    dense_boundary_keys = ()
    moe_expert_keys = ('num_experts',)

    #: `enable_moe_block` defaults to False and `num_experts` to None, so on the Python
    #: defaults alone this asserts nothing — the capability appears only once a checkpoint
    #: config.json supplies real values. That is the intended behaviour: absent evidence
    #: is unknown, not "dense".
    capability_keys = {
        'sliding_window_attention': ('sliding_window', 'layer_types'),
        'moe': ('num_experts', 'enable_moe_block', 'moe_intermediate_size'),
    }

    #: Candidate hints only.
    kernel_anchors = {
        'attention_core': ('FlashAttentionScore', 'PromptFlashAttention',
                           'IncreFlashAttention'),
        'fused_add_norm': ('AddRmsNorm', 'AddRMSNorm'),
    }

    known_deviations = (
        {'id': 'layer_types_runtime_built',
         'reason': 'sliding/full 的逐层分类由 config.__init__ 在运行期构建列表，'
                   'AST 不展开为具体层号；保持 dense 单组而不猜测'},
        {'id': 'enable_moe_block_gated',
         'reason': 'MoE 块由 enable_moe_block 开关控制且与 dense MLP 同层共存；'
                   '实际是否走专家路径取决于部署配置，不能从 Python 默认值推断'},
    )

    def matches(self, evidence):
        classes = evidence.get('class_names', set())
        keys = evidence.get('config_keys', set())
        reasons = []
        named = sorted(c for c in classes if 'Gemma' in c)
        if named:
            reasons.append(f'class 名含 Gemma: {named[:3]}')
        if ('sliding_window' in keys and 'num_hidden_layers' in keys
                and 'first_k_dense_replace' not in keys):
            reasons.append('config 含 sliding_window + num_hidden_layers 且无 '
                           'first_k_dense_replace')
        if not reasons:
            return False
        return ('high' if named else 'medium'), reasons

    def refine(self, facts, layer_groups, prediction_modules, config_defaults,
               config_tree, modeling_tree, base_dir, config_path, modeling_path, gaps):
        if 'sliding_window' in config_defaults:
            val, lineno = config_defaults['sliding_window']
            facts.append(Fact('sliding_window', val,
                              rel_ref(config_path, lineno, base_dir), 'ast_default_arg', 'high'))
        # The sliding/full per-layer split is built at runtime (list comprehension over
        # num_hidden_layers with a modulo pattern). We do not evaluate it statically to
        # concrete indices; record the gap so it is never silently guessed.
        gaps.append('Gemma sliding/full per-layer 分类由 config.__init__ 运行时构建，'
                    '未静态展开为具体层号（保持 dense 单组）')
