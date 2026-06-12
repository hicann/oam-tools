# 结构分析指南

本文档定义如何从模型源码与 `raw_ops.json` 推导出 `analysis_config.json`。目标是**优先**产出正确、清晰、稳定的模型架构表示，为按层、按模块做耗时分析提供可靠输入。**拆分以源码语义为准，kernel 序列只用于定位和验证。**

文档分为四部分：

- **A. 模型 → 结构树**：从源码读出节点、命名、边界、歧义消解
- **B. kernel → 节点**：把 raw_ops 的算子精确归属到节点，含 shape_semantic 必填范围（**单源**）
- **C. 输出格式**：`analysis_config.json` 的 schema 与字段规范
- **D. 工作流速览**：Step 2 拆解 + Step 3 Review 的执行步骤

---

## A. 模型 → 结构树

### A.1 节点来源规则

树中每个节点**只允许**来自以下四类来源之一。**任何不属于以上四类的节点都不允许出现在树中。** 不能为了追求更细粒度临时造新节点。若同一模块定义代码存在多个不同调用实例，要算作多个节点，不能合并为一个。

| 类型 | 含义 | op 覆盖范围 |
|---|---|---|
| **1. 源码中的 torch module** | 在执行路径中被显式调用的 `nn.Module`。最主要的节点来源 | 该模块 forward 产生的全部 op（含其内部细节 Cast/Reshape/Quant 等） |
| **2. 源码中的稳定函数封装语义** | 没有独立模块属性名但被稳定封装为单独函数，且函数职责清楚、边界稳定。**只能作为已有模块或 stage 的内部补充拆分**，不能取代更高层的源码模块边界 | 该函数封装范围的全部 op（含其内部细节） |
| **3. 独立通信阶段** | `all_gather` / `reduce_scatter` / `all_to_all` / `all_reduce` 等通信操作；**仅当**它们在源码中是独立阶段、前后边界清楚、且不自然属于某个已有模块内部时才保留。判断标准见 [B.2](#b2-通信操作的处理) | 单次 hcom 调用（`HcomAllGather` / `HcomReduceScatter` / `HcomAllToAll` / `hcom_allReduce`）及其紧邻的必要桥接实现细节 |
| **4. 明确的典型模型结构语义** | 对应一个明确的"主 kernel"，其余全是围绕它的实现细节 op（Cast/Reshape/DynamicQuant/DequantX）。允许使用补充语义名（如 `activation`、`dispatch`、`combine`），也允许使用源码里的函数名或 kernel 语义名 | 主 kernel + 围绕的实现细节 op |

类型 2 使用条件：
- 该函数在主执行路径上被明确调用
- 它描述的是稳定语义阶段，而不是一次性的实现细节整理
- 节点命名直接使用源码中的函数名

### A.2 命名规则

1. **优先使用源码中的属性名**：`self.xxx = SomeModule(...)` 中的 `xxx` 就是首选节点名。
2. **其次使用源码中的函数名**：当需要在模块内部继续划分，而该阶段没有独立模块属性名时，可以直接使用源码中的函数名。
3. **补充名称最后使用**：只有源码中既没有合适模块名，也没有合适函数名时，才使用允许的补充语义名。
4. **节点名必须覆盖其实际语义范围**：如果当前 trace 只能稳定定位整体边界，则应使用更宽的名字，而不是用过窄的名字覆盖更大的语义范围。
5. **`layer_types` 只描述 decoder layer 类型**：名称使用源码中 decoder layer 的类名，若模型有多种 decoder layer 或存在 mtp，`layer_types` 会有多个。其余不属于 decoder layer 的步骤，应放入 `stages`。不属于模型架构主干的运行时逻辑应放入 `runtime_auxiliary`。
6. **`layer_types` 命名必须使用源码类名原文**：若源码里同一模型中存在多种有结构差异的 decoder layer 时，在类名后附加区分后缀。**不允许**使用简写或省略类名。若需要附加区分后缀，后缀统一使用**全小写短语**。

### A.3 边界划分规则

#### A.3.1 layer 边界优先按源码中的 decoder layer 结构确定

先根据源码分析 decoder layer 的计算顺序，应先在 op 序列中识别这一重复模式，再区分不同的 decoder layer（若存在不同 decoder layer）。需要注意，即使完全相同的 decoder layer，算子序列可能因为并行执行，执行顺序不会完全相同。

#### A.3.2 节点内部允许按函数 / nn.module 或语义继续拆分

如果模块内部源码存在稳定的函数封装边界，且拆分符合模型结构惯例（可以拆出经典模型结构）可以继续拆分。但不要把边界不稳定的连续零散小算子拆成节点。节点的边界要对应语义清晰的代码和算子序列以及稳定的边界。

**禁止**把一个节点内部的调用阶段提升为平级兄弟节点，要么判断是否能作为子节点，要么并入。

#### A.3.3 代表性 step 中重复出现的结构阶段不展开成多份

如果同一源码阶段、模块或函数封装在代表性 step 中重复出现，且这些实例语义一致、内部结构同构，应像 decoder layer 一样按"类型 + 索引"表达，**只保留一份结构定义**，并用索引字段标明重复实例；不要按迭代号或出现顺序展开成多份近乎相同的副本。**这条规则同时适用于 `stages`、`layer_types` 和 `runtime_auxiliary` 三处**。

**部分同构场景的处理模板**：当一组重复阶段中前 N-1 次结构完全同构、只有最后一次尾部略短（典型：spec decoding 的 N 次迭代，前 N-1 次含"采样 + 为下一轮设置"，最后一次只有"采样"没有下一轮设置），**必须**按以下方式折叠：

- 结构同构的部分折叠为**一条**，用 `instance_indices=[0, 1, ..., N-2]` 标明覆盖的实例（`op_indices` 给出任一同构实例的代表性拆分）。
- 非同构的尾部另起一条，单独命名（例如 `xxx_final_iter_tail`），不使用 `instance_indices`。

**op 数渐增（accumulation 类）场景的折叠**：若每次迭代 op 数不同是因为**累积操作**（如历史 spec_tokens 的 `ConcatD` 随迭代变长），这**不构成"非同构"**；应按"kernel 类型序列 + 可变长 ConcatD"视为结构同构的实例，**仍必须用 `instance_indices=[0, 1, ..., N-1]` 折叠**为单条。`op_indices` 给出任一实例的代表性拆分，不同实例间 op 数量的些微差异（±1-2 ops 的 ConcatD 变长）不作为拆分理由。

#### A.3.4 不要求为了完整覆盖而把 runtime 逻辑强塞进模型模块

步骤二的首要目标是产出清晰的模型架构。像 token 选择、spec token 验证、输入更新这类不属于模型主干的逻辑，不应并入 `lm_head`、`embed_tokens` 等模块，应放入 `runtime_auxiliary`。

#### A.3.5 确保完全理解计算过程和对应的算子

遇到并行复杂交错的模块，算子划分要确保完全理解计算过程，可依据 `stream_id`、`input_shapes`、`output_shapes` 辅助划分（详见 [B.4](#b4-辅助证据)），算子划分到模块需要有依据，能和源码、计算过程对应。

#### A.3.6 多次迭代执行的模型包装层的建模方式（如 MTP / spec decoding）

若源码中存在"对模型主干做多次迭代"的包装层（典型例子：MTP / spec decoding 头，外层 loop 调用一个内部包含 decoder layer 的 module N 次），按以下方式建模（**不允许**二义解释）：

- 该包装层内部如果包含**真实的 decoder layer 类**，则该内部 decoder layer **必须**进入 `layer_types`，其 `layer_indices` 覆盖该 decoder layer 在代表性 step 中出现的所有 layer_idx（多次迭代会产生多个 layer_idx 实例）。**不允许**把该内部 decoder layer 内联进 `stages` 里。
- 该包装层的 **scaffold**（例如 enorm / hnorm / eh_proj / shared_head_norm / embed_tokens / lm_head 这类围绕 decoder layer 的辅助模块）放入 `stages`，每次迭代结构同构则用 `stage_indices` 折叠为一份定义。
- 迭代之间、迭代之后的运行时辅助逻辑（graph setup、token sampling、verify、param update 等）放入 `runtime_auxiliary`，结构同构部分用 `instance_indices` 折叠。

### A.4 歧义消解顺序

先根据计算过程、源码及 [B.4 辅助证据](#b4-辅助证据)确定算子对应的具体计算和节点归属。遇到拿不准的 op 归属时，按以下**固定优先级**处理：

1. 先判断它是否属于模型架构主干，还是属于运行时辅助逻辑。
2. 如果属于模型架构主干，优先并入最近的源码模块。
3. 如果源码中没有合适模块，但存在稳定函数封装，使用函数名。
4. 如果是独立通信阶段，保留为通信节点。
5. 如果以上都不适用，再使用允许的补充语义名。
6. 如果仍然不确定，继续向上合并到父节点。
7. 如果明确不属于模型架构主干，则放入 `runtime_auxiliary`。

不能为了覆盖某些 op 而临时创建新节点名，也不能根据单次运行的局部 kernel 排布改动树结构。

---

## B. kernel → 节点

### B.1 实现细节 op 的处理

以下 kernel 类型通常属于实现细节，**默认不作为独立树节点**：

`Cast`、`Concat`、`Transpose`、`Reshape`、`DynamicQuant`、`Dequant*`、`ScatterNdUpdate`、`Split`、`RotaryMul`、`AivKernel`（非明确对应某个源码模块或函数边界时）

处理方式：**并入最近的源码模块节点或函数语义节点。**

### B.2 通信操作的处理

通信 op（`HcomAllGather`、`HcomReduceScatter`、`HcomAllToAll`、`hcom_allReduce` 以及伴随通信的 `AivKernel`）按以下规则处理：

1. **如果通信是某个模块或函数内部实现的一部分**，并入该模块或函数，不单独拆出。
2. **如果通信是模块间独立的数据搬运阶段**，可以保留为树节点。例如 embedding 后的 `all_gather/reduce_scatter`、`forward_lm_head` 前的 `all_gather`。
3. **判断标准以源码为准**：看通信调用发生在谁的 `forward` 或辅助函数内部。如果发生在某个模块或函数内部，就并入该节点。
4. **伴随通信的 `AivKernel` 不单独命名**：应并入最近的通信节点或所属模块节点。

### B.3 op 映射规则

要把 op 精准对应到模型拆解的节点，**不允许有模糊或猜测**。

1. 确保对单个节点的计算过程和起始边界完全理解。
2. 把具体算子和源码的每一个计算对齐，需要结合 [B.4 辅助证据](#b4-辅助证据)和源码判断。
3. 完成对齐后，检验节点的计算流程和对应算子的对应是否有多余或缺漏，需要结合 [B.4 辅助证据](#b4-辅助证据)和源码判断。如果存在问题，需要重新分析并做对应，直到没有 gap。

### B.4 辅助证据

`raw_ops.json` 中的 `stream_id`、`input_shapes`、`output_shapes` 是把算子对应到具体源码和计算过程的重要辅助证据。

**`stream_id` 的用途**：
- 用于识别多 stream 并行执行。
- 用于判断某些节点是否可以使用非连续 `op_indices` 收拢到同一语义阶段。

**shape 的用途**：
- 用于辅助区分同名 op 在不同阶段的语义位置。
- 用于判断某个 `MatMul`、`GroupedMatmul`、`QuantBatchMatmul` 等同名算子更可能属哪个节点。
- 用于核对前后节点是否真的存在维度变化边界。

### B.5 shape_semantic 必填范围（单源）

`kernels` 数组的条目中，对以下算子**必须**提供 `shape_semantic`，用模型维度符号标注 shape 含义：

| 类别 | 算子 |
|---|---|
| **MatMul 类** | `MatMul` / `MatMulV2` / `QuantBatchMatmulV3` / `GroupedMatmul` / `GemmEx` / `BatchMatMul`（及变体） |
| **Attention 类** | `FlashAttentionScore` / `FusedInferAttentionScore` / `KvQuantSparseFlashAttention` |
| **通信类** | `HcomAllGather` / `HcomReduceScatter` / `HcomAllToAll` / `hcom_allReduce` |
| **Norm 类** | `RmsNorm` / `LayerNormV3` / `InplaceAddRmsNorm` / `AddRmsNorm*` / `AddRmsNormDynamicQuant` |
| **Fused 计算类** | `MlaPrologV3` / `DequantSwigluQuant` / `LightningIndexerQuant` / `MoeGatingTopKHash` |
| **旋转位置编码** | `RotaryMul` |
| **KV cache 更新** | `ScatterNdUpdate`、KV cache 拼接用的 `ConcatV2` / `ConcatD` |
| **残差加法** | `Add`（明确为残差连接时） |
| **Embedding/Gather** | `GatherV2` / `GatherV3` |
| **MoE 调度** | `MoeDistributeDispatchV2` / `MoeDistributeCombineV2` |

**免填**：`Cast`、`Reshape`、`Transpose`（纯格式转换）、`DynamicQuant`/`Dequant*`（量化辅助）。

**统一维度符号**：`B`（Batch）、`T`（Time/SeqLen，统一用 T 不用 S）、`H`（NumHeads）、`D`（HeadDim）、`hidden`（hidden_size）、`ffn`（intermediate_size）、`E`（num_experts）、`topK`（experts per token）、`q_rank`（q_lora_rank）、`kv_rank`（kv_lora_rank）。

**示例**：
- `[B*T, hidden] @ [hidden, q_rank]`
- `[B, H, T, D] × [B, H, D, T] → [B, H, T, T]`
- `[B*T, hidden] → [B*T, hidden]`（Norm）
- `[B*T, H, kv_rank] → AllGather → [B*T, H, kv_rank*tp]`（通信）

#### B.5.1 shape_semantic 正确性规则（填写前必须逐一核对）

1. **先看实际 shape**：填写前先查看该 kernel 在 `raw_ops.json` 中的 `input_shapes` 和 `output_shapes`，以实际 shape 为准，**绝不凭印象或架构直觉猜测**。
2. **`→` 左侧描述输入，右侧描述输出**：`→` 左边只写主要输入张量的语义维度（通常是 input[0]），右边写所有关键输出张量；多输出用逗号分隔。
3. **命名维度必须与实际数值一致**：若写 `H_q=128`，则实际输出 tensor 中必须存在维度 128；若写 `kv_rank=512`，则实际 shape 中必须存在 512。**不得**写 config 字段名之外的新符号而不标注数值（如直接写 `H_idx` 而不写 `H_idx=64`）。
4. **fused kernel 须追踪每个关键输出**：对 `MlaPrologV3`、`LightningIndexerQuant`、`AddRmsNormDynamicQuant` 等多输出 fused kernel，需对照 raw_ops 的每条 output shape，识别其含义后在 shape_semantic 右侧列出所有关键输出。**不得**将 Q 输出标成 K，**不得**混用 `H_idx`/`H_q`。
5. **吸收（absorbed）注意**：MLA 推理时 `W_kv_b` 已被吸收进 Q，`MlaPrologV3` 输出的是 `Q_nope_abs[B*T, H_q, kv_rank]`，维度是 `kv_rank`（512）而非 `D_nope`（128）。
6. **验证脚本**：写完 analysis_config.json 并运行 enrich 后，执行 `python scripts/validate_shapes.py -c outputs/analysis_config.json` 确认无 ERROR，再进行下一步。

---

## C. 输出格式

### C.1 顶层 schema 与示例

```json
{
  "model_name": "model-name",
  "representative_step": 1,
  "notes": "简要说明网络结构组成、层数、并行方式和特殊执行路径",
  "stages": {
    "preprocessing": {
      "name": "preprocessing",
      "children": [
        {"name": "stage_module_a", "op_indices": [0, 1, 2]}
      ]
    },
    "repeated_stage_type_x": {
      "name": "repeated_stage_type_x",
      "stage_indices": [0, 1],
      "children": [
        {"name": "stage_module_c", "op_indices": [50, 51]}
      ]
    },
    "postprocessing": {
      "name": "postprocessing",
      "children": [
        {"name": "stage_module_b", "op_indices": [100]},
        {"name": "stage_function_c", "op_indices": [101, 102, 103]}
      ]
    }
  },
  "layer_types": {
    "layer_type_a": {"layer_indices": [0]},
    "layer_type_b": {"layer_indices": [1, 2]},
    "layer_type_c": {"layer_indices": [3, 4, 5]}
  },
  "layer_structure": {
    "layer_type_a": {
      "name": "layer_type_a",
      "semantic": "Decoder layer with self-attention and MLP",
      "code_ref": "modeling.py:200-350",
      "children": [
        {"name": "submodule_1", "semantic": "LayerNorm before attention", "code_ref": "modeling.py:220", "op_indices": [10], "kernels": [{"index": 10, "semantic": "RMSNorm kernel", "code_ref": "modeling.py:222"}]},
        {
          "name": "submodule_2",
          "children": [
            {
              "name": "function_1",
              "children": [
                {"name": "substage_1", "op_indices": [11]},
                {"name": "substage_2", "op_indices": [12, 13, 14]}
              ]
            },
            {"name": "substage_3", "op_indices": [15]},
            {
              "name": "function_2",
              "children": [
                {"name": "submodule_3", "op_indices": [16, 17]}
              ]
            }
          ]
        },
        {"name": "submodule_4", "op_indices": [18]},
        {
          "name": "submodule_5",
          "children": [
            {"name": "substage_4", "op_indices": [19]},
            {"name": "substage_5", "op_indices": [20]},
            {"name": "substage_6", "op_indices": [21]}
          ]
        }
      ]
    }
  },
  "runtime_auxiliary": [
    {
      "name": "runtime_helper_a",
      "op_indices": [200, 201, 202]
    },
    {
      "name": "runtime_helper_b",
      "instance_indices": [0, 1, 2],
      "op_indices": [210, 211]
    }
  ]
}
```

### C.2 顶层字段说明

| 字段 | 说明 |
|---|---|
| `model_name` | 模型名称 |
| `representative_step` | 选定的代表性 step ID |
| `notes` | 网络结构组成、层数、并行方式、特殊执行路径 |
| `stages` | decoder layer 之外、但属于模型架构主干的阶段。重复出现的同类阶段只保留一份定义，用 `stage_indices` 标明实例 |
| `layer_types` | 只列 decoder layer 类型及其层号范围 |
| `layer_structure` | 每种 decoder layer 类型对应一棵代表性结构树。`op_indices` 表示该类型在代表性 step 中的参考拆分，不要求逐一展开所有重复实例 |
| `runtime_auxiliary` | 不属于模型架构主干、但在代表性 step 中真实存在的运行时逻辑（token 选择、验证、输入更新、调度辅助逻辑）。重复出现的同类逻辑只保留一份定义，用 `instance_indices` 标明实例 |

### C.3 节点字段说明

| 字段 | 必选 | 说明 |
|---|---|---|
| `name` | 必选 | 节点名（按 [A.2 命名规则](#a2-命名规则)） |
| `semantic` | **必选**（`Cast`/`Reshape` 除外） | 节点或 kernel 的语义说明，如 "Attention QKV projection"。所有有意义的算子（包括 `Add` 残差、`Mul` 门控、`Concat` KV 缓存拼接、RMSNorm 各步骤等）均需填写，清晰说明其在模型中的计算作用 |
| `code_ref` | **必选**（除非无法判断） | 源码位置引用，格式如 `filename.py:line` 或 `filename.py:start-end` |
| `op_indices` | 叶节点必有 | 该节点覆盖的 op 索引列表，**允许非连续** |
| `children` | 中间节点必有 | 子节点数组；中间节点必要时也可同时带 `op_indices` 表示不属于任何子节点的额外 op |
| `kernels` | 可选 | 节点下的 kernel 语义信息数组，每个元素含 `index`、`semantic`、`shape_semantic`、`code_ref` |
| `stage_indices` / `instance_indices` | 重复阶段必有 | 该结构阶段或辅助逻辑在代表性 step 中重复出现的实例索引。存在时 `op_indices` 只需给出该类型一份代表性拆分 |

### C.4 树结构规则

- 每个节点包含 `name`。
- 叶子节点包含 `op_indices`，允许非连续。
- 中间节点包含 `children`，必要时也可以同时带 `op_indices` 表示不属于任何子节点的额外 op。
- 节点和 kernel **必选**包含 `semantic`（语义说明）和 `code_ref`（源码位置）。
- 同一代表性 step 中重复出现的同构阶段，只保留一份类型定义，并使用 `stage_indices` 或 `instance_indices` 标明重复实例，**不**按迭代展开成多份相同子树。
- **不**要求为了"全覆盖"把 runtime 辅助逻辑强塞进模块树；这类内容应进入 `runtime_auxiliary`。
- **不能**静默遗漏已经识别出的重要阶段。主干结构和 runtime 辅助逻辑都应在配置中有明确归属。
- `kernels` 数组对 [B.5](#b5-shape_semantic-必填范围单源) 列出的算子**必须**填写 `shape_semantic`。

---

## D. 工作流速览

按以下固定顺序执行，每一步的输入依赖前一步的输出。

### D.1 Step 2：拆解模型结构

#### D.1.1 选择代表性 step 和 decoder layer 实例

从 `steps_summary.md`、`raw_ops.compact.json`（或 `raw_ops.json`）中选一个稳定的 decode step（跳过 warmup）。选择标准：

- 如果只有一个 step，不用选择直接使用。
- 先按 kernel_count + kernel 类型分布分组，选择主流稳定分组；若存在多种 op 数量的 step，选择包含最多 decoder layer 的那种作为代表。
- 对同一稳定分组，检查最早 step 的 kernel_sum 是否相对后续 step 中位数明显离群；若离群，把最早 step 视为 warmup/outlier 并跳过。
- 若最早 step 不离群，优先选择最早稳定 step；若跳过 warmup/outlier，则选择后续 step 中 kernel_sum 最接近中位数的一步。
- 在 `notes` 中明示代表 step 及选择原因；需要复现历史报告或特定 step 时，可以显式传 `-s`。

**选择代表性 decoder layer 实例（同 layer_type 内多实例时）**：

同一 `layer_type` 在代表性 step 中会出现多个实例，它们内部结构一致，但首层常常存在融合差异（例如 layer 0 的 `input_layernorm` 是独立 `RmsNorm`，layer 1+ 融合上一层 residual 成 `InplaceAddRmsNorm`）。选择规则：

- 默认选**第一个完整实例**（通常 layer 0）作为 representative 结构。
- **例外（必须遵守）**：若首层因跨层 fusion 差异导致 op 数量或关键 kernel 类型与后续同类实例不同（典型：layer 0 的 `input_layernorm` 是独立 `RmsNorm`、后续层是 `InplaceAddRmsNorm` / `AddRmsNormX` 等融合版），**必须**选第二个实例（通常 layer 1）作为 representative，以使 representative 结构能一致套用在所有其余同类实例上。
- 选定后在 `notes` 中明示选了哪一个实例、以及 layer 0 与后续实例的已知差异，便于步骤三的 stats 脚本识别。
- 若存在结构不同的多种 decoder layer，都要选出作为独立 layer_type。
- 若存在 mtp，mtp decoder layer 要提取出来成为一个独立 layer_type。**不得**与主模型的 decoder layer 合并。

#### D.1.2 阅读模型源码，提取模块层级和稳定函数边界

阅读 modeling 源码文件，从最外层 `ForCausalLM` 到最内层子模块，提取完整的执行语义。重点关注：

- `__init__` 中注册了哪些子模块（`self.xxx = ...`）。
- `forward` 中实际调用了哪些模块，调用顺序是什么。
- 除 `nn.Module` 之外，是否存在稳定的函数封装边界。

形成模型结构树，节点来源参考 [A.1 节点来源规则](#a1-节点来源规则)。

#### D.1.3 在 op 序列中定位 decoder layer 边界

使用结构锚点在代表性 step 的 op 列表中划分 decoder layer 边界。`layer_types` 只描述 decoder layer 类型；decoder layer 之外的模型结构应归入 `stages`，不属于模型架构主干的运行时逻辑应归入 `runtime_auxiliary`。

> 提示：若有 `outputs/op_segments.json`（由 `scripts/segment_layers.py` 生成），可作为 layer 边界**候选起点**；最终边界仍以源码语义为准。

#### D.1.4 逐层映射 op 到源码模块或函数语义

对每一层，按源码中的调用顺序，将 op 序列拆分到各个节点中。节点优先按 `torch module` 划分；当某段逻辑并非独立模块，但在源码中被稳定地封装为单独函数且语义明确时，可以按函数边界或其他稳定模型结构语义划分。把算子映射到对应的节点（参考 [B.3 op 映射规则](#b3-op-映射规则)）。每个叶子节点覆盖的 op 用 `op_indices` 表示，允许非连续。

#### D.1.5 输出 `analysis_config.json`

将结构分析结果写入配置文件。格式见 [C. 输出格式](#c-输出格式)。

#### D.1.6 运行 enrich 命令

```bash
python scripts/analyze_kernels.py --enrich \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json
```

enrich 命令为每个叶节点的 `op_indices` 追加 `op_data` 字段（含 `index`、`org_index`、`name`、`duration_us`、`stream_id`、`task_type`、`input_shapes`、`output_shapes`、`shape_raw`），并将节点 `kernels` 数组中已有的 `semantic`、`shape_semantic`、`code_ref` 合并进对应算子的 `op_data` 条目。原有字段不变。

### D.2 Step 3：Review 拆解结果

Step 3 用脚本暴露问题、AI 仅修正定位过的节点。**不再裸读全量源码与 raw_ops**。

#### D.2.1 运行确定性脚本检查

```bash
python scripts/check_structure.py    -c outputs/analysis_config.json --json > outputs/issues.json
python scripts/validate_shapes.py    -c outputs/analysis_config.json --fail-fast --json >> outputs/issues.json
python scripts/check_op_coverage.py  -c outputs/analysis_config.json -r outputs/raw_ops.json --json >> outputs/issues.json
```

脚本规则与本指南直接对齐：

| 脚本 | 检查 |
|---|---|
| `check_structure.py` | 树良构性（schema 完整、layer_types/layer_structure 匹配、必填字段、索引列表无重复、双归属检测） |
| `validate_shapes.py` | shape_semantic 与实际 tensor shape 一致性 |
| `check_op_coverage.py` | op 全覆盖、不重叠、shape_semantic 必填类算子全在 kernels 数组登记 |

#### D.2.2 若 issues.json 为空 → 跳过 AI review

直接进入 D.3。

#### D.2.3 否则拉起 review subagent

subagent 与主 agent 使用相同模型与推理强度。**输入**：

1. `issues.json`
2. `analysis_config.json` 中 issue 命中的节点（按路径过滤后投喂，**不投喂全量配置**）
3. 这些节点 `code_ref` 行号对应的源码切片（**稀疏读**：用 `Read` 工具的 `offset/limit` 参数只读相关行段）
4. 这些节点 `op_indices` 对应的 raw_ops 切片

**任务**：

```
依据 issues.json、源码切片、op 切片，对每一项 issue 验证算子归属与字段填写正确性。
若存在错误，直接修正 analysis_config.json 中对应位置；只允许在存在错误时修改。
要精准对齐源码，结合 ops 的 shape 和 stream_id 判断。
不能有任何冗余或遗漏。
```

**输出**：修正后的 `analysis_config.json` + review 结论。

#### D.2.4 重新 enrich + 校验

修正后重新运行 D.1.6 enrich 与 D.2.1 三脚本，循环执行直至 issues 列表为空或迭代上限（默认 3 次）。

### D.3 与下游的衔接

- 通过 D.2.4 后，`analysis_config.json` 进入 Step 4（generate_report.py）与 Step 5（compute_metrics.py），脚本调用见 SKILL.md。
- 若是 Mode B（仅模型源码），输出文件名为 `model_structure.json`，op_indices 留空，可加 `branches` 字段表达多分支；不进入 Step 4/5。详见 `references/mode_b_branches.md`。
- 若是 Mode C（仅性能数据），不走本流程，委托给 cann-npu-perfanalysis sibling skill；详见 `references/mode_c_delegate.md`。
