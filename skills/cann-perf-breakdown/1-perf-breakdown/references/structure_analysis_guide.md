# 结构分析指南

本文档定义如何从模型源码与 `raw_ops.json` 推导出 `analysis_config.json`。目标是**优先**产出正确、清晰、稳定的模型架构表示，为按层、按模块做耗时分析提供可靠输入。**拆分以源码语义为准，kernel 序列只用于定位和验证。**

## 目录

- A. 模型 → 结构树 — 从源码读出节点、命名、边界、歧义消解
  - [A.1 节点来源规则](#a1-节点来源规则) ・ [A.2 命名规则](#a2-命名规则) ・ [A.3 边界划分规则](#a3-边界划分规则) ・ [A.4 歧义消解顺序](#a4-歧义消解顺序)
- B. kernel → 节点 — 把 raw_ops 的算子精确归属到节点
  - [B.1 实现细节 op](#b1-实现细节-op-的处理) ・ [B.2 通信操作](#b2-通信操作的处理) ・ [B.3 op 映射规则](#b3-op-映射规则) ・ [B.4 辅助证据](#b4-辅助证据) ・ [B.5 shape_semantic（可选注解）](#b5-shape_semantic可选注解)
- [C. 输出格式](#c-输出格式) — `analysis_config.json` 的 schema 与字段规范
  - [C.1 顶层 schema](#c1-顶层-schema-与示例) ・ [C.2 顶层字段](#c2-顶层字段说明) ・ [C.3 节点字段](#c3-节点字段说明) ・ [C.4 树结构规则](#c4-树结构规则) ・ [C.5 显式数据流边](#c5-显式数据流边branches)
- [D. 工作流速览](#d-工作流速览) — Step 2 拆解 + Step 3 Review 的执行步骤
- [E. Schema v2 权威定义](#e-schema-v2模型层-vs-运行时调用权威定义) — 模型层 vs 运行时调用、覆盖四分类

**两条贯穿全文的红线**：

1. **源码是主证据，trace 是辅证，且 trace 只能单向证伪**。拆分以源码语义为准。一次采集只覆盖单个 step、单个 rank，且发生在切分与融合之后，所以它看到的是源码所有路径的一个**子集**。这个不对称决定了两个方向的分歧含义完全不同：

   | 方向 | 含义 | 判定 |
   |---|---|---|
   | trace 里有，拆解里没有 | 该算子确实执行过，而拆解没有任何归属 | **错误**（拆解漏了，源码解释不能豁免；由 C1/C6 拦截） |
   | 拆解里有，trace 里没有 | 未执行的分支、其他 rank 的分片、被融合掉的算子、本 step 跳过的层 | **不是错误**（最多记录一条 info） |
   | trace 里的算子在拆解里全部有归属 | 覆盖率完整 | **默认以源码为主，判为无错**。层数、专家数这类 trace 无法裁定的标量由源码单独决定，trace 既不能推翻它，也不能因为"没能佐证"而扣分 |

   **trace 反证的对象是候选拆解，不是源码文件。** trace 与候选不符时，结论是"这份候选写错了"，
   而不是"源码写错了"——源码是主证据，一次采集只是它所有路径的一个子集。

   **但有一个必须阻断的例外**：trace 里出现**无法被模型结构、runtime 逻辑或编译融合解释**的
   计算，说明候选与实际执行矛盾（要么漏了一个真实模块，要么归属完全错了）。这类 op 必须作为
   `error` 阻断，不得以"trace 只是辅证"为由放过。

   换句话说：**trace 能证伪的只有覆盖率与无法解释的计算**。任何检查若反转其中一个方向，就等于把"没采到的数据"当成缺陷，这正是同样输入在三个采集上得出三个不同结论的原因。规则的代码入口是 `breakdown_common.py` 的 `TRACE_CAN_ONLY_FALSIFY_COVERAGE` 与 `trace_disagreement_severity()`。
2. **`children` 只表达包含关系**。相邻不等于有数据流边；残差、并行支路、skip 必须在 `branches` 里显式声明，未声明的边在下游就不存在（见 [C.5](#c5-显式数据流边branches)）。

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
5. **`layer_groups[].type` 只描述 decoder layer 类型**：名称使用源码中 decoder layer 的类名，若模型有多种 decoder layer 或存在 MTP，会有多个 layer group。其余不属于 decoder layer 的步骤放入 `stages`；不属于模型架构主干的运行时逻辑放入 `runtime_auxiliary`。
6. **layer group 命名必须使用源码类名原文**：若源码里同一模型中存在多种有结构差异的 decoder layer，在类名后附加区分后缀。**不允许**使用简写或省略类名。后缀统一使用**全小写短语**。

### A.3 边界划分规则

#### A.3.1 layer 边界优先按源码中的 decoder layer 结构确定

先根据源码分析 decoder layer 的计算顺序，应先在 op 序列中识别这一重复模式，再区分不同的 decoder layer（若存在不同 decoder layer）。需要注意，即使完全相同的 decoder layer，算子序列可能因为并行执行，执行顺序不会完全相同。

#### A.3.2 节点内部允许按函数 / nn.module 或语义继续拆分

如果模块内部源码存在稳定的函数封装边界，且拆分符合模型结构惯例（可以拆出经典模型结构）可以继续拆分。但不要把边界不稳定的连续零散小算子拆成节点。节点的边界要对应语义清晰的代码和算子序列以及稳定的边界。

**禁止**把一个节点内部的调用阶段提升为平级兄弟节点，要么判断是否能作为子节点，要么并入。

#### A.3.3 代表性 step 中重复出现的结构阶段不展开成多份

如果同一源码阶段、模块或函数封装在代表性 step 中重复出现，且这些实例语义一致、内部结构同构，应像 decoder layer 一样按"类型 + 索引"表达，**只保留一份结构定义**，并用索引字段标明重复实例；不要按迭代号或出现顺序展开成多份近乎相同的副本。**这条规则同时适用于 `stages`、`layer_groups` 和 `runtime_auxiliary` 三处**。

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

- 该包装层内部如果包含**真实的 decoder layer 类**，则该内部 decoder layer **必须**进入
  `architecture.prediction_modules`（或对应的 layer group），并且它是**一个**学习到的层：
  外层循环调用它 N 次，就在 `trace_instances` 里记 N 条 invocation，`model_layer_index`
  **全部相同**，用 `invocation_index` 区分第几次。**禁止**因为被调用多次就写成 N 个模型层或
  伪层号（如 `6,7,8`）——那会把一个层的参数量重复计 N 次。**不允许**把该内部 decoder layer
  内联进 `stages` 里。
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

### B.5 shape_semantic（可选注解）

`shape_semantic` 是**可选**注解，不进入正式门禁，也不参与评分。它是叠加在 profiler 已有维度上的一层解释：缺失并不说明拆解错误，填了也不能证明拆解正确。因此把它做成必填曾经既拦不住真错误，又给"不可能出错的证据"发分。

它仍然有用——排查一个 kernel 到底算的是什么时，写清 shape 语义能快速暴露张量归属搞错的情况（例如把 Q 输出当成 K）。需要时用 `run_validation.py --with-shapes` 或直接跑 `validate_shapes.py` 检查一致性。

**建议填写的场景**（按语义，不按 kernel 名）：承担主要计算量的 GEMM 与 attention、改变张量布局的通信、以及多输出的融合算子——这三类最容易把张量认错。纯格式转换（Cast / Reshape / Transpose）与量化辅助（DynamicQuant / Dequant*）没有必要填。

> 此处刻意不列固定 kernel 名表。同一语义在不同模型族与不同算子库版本下名字完全不同，把某一族的名字写成通用规则，等于把适配器该做的事写死进指南。各族已知别名见 `adapters/<family>.py` 的 `kernel_anchors`。

**统一维度符号**：`B`（Batch）、`T`（Time/SeqLen，统一用 T 不用 S）、`H`（NumHeads）、`D`（HeadDim）、`hidden`（hidden_size）、`ffn`（intermediate_size）、`E`（num_experts）、`topK`（experts per token）、`q_rank`（q_lora_rank）、`kv_rank`（kv_lora_rank）。

**示例**：
- `[B*T, hidden] @ [hidden, q_rank]`
- `[B, H, T, D] × [B, H, D, T] → [B, H, T, T]`
- `[B*T, hidden] → [B*T, hidden]`（Norm）
- `[B*T, H, kv_rank] → AllGather → [B*T, H, kv_rank*tp]`（通信）

#### B.5.1 填写时的正确性规则（选择填写就要填对）

1. **先看实际 shape**：以 `raw_ops.json` 里该 kernel 的 `input_shapes` / `output_shapes` 为准，**绝不凭印象或架构直觉猜测**。
2. **`→` 左侧描述输入，右侧描述输出**：左边写主要输入张量（通常是 input[0]）的语义维度，右边写所有关键输出；多输出用逗号分隔。
3. **命名维度必须与实际数值一致**：写 `H_q=128` 就要求实际 tensor 中存在维度 128。引入 config 字段名之外的新符号时必须标注数值。
4. **融合算子须追踪每个关键输出**：多输出融合 kernel 要对照每条 output shape 逐个识别含义，全部列在右侧。**不得**把 Q 输出标成 K —— 这是最常见也最容易被忽略的错标。
5. **注意权重吸收**：某些 attention 实现在推理时会把一个投影权重吸收进另一个，输出维度因此变成低秩维而非原始 head dim。以实际 shape 为准，不要按论文公式推。
6. **验证**：`python scripts/validate_shapes.py -c outputs/analysis_config.json` 确认无 ERROR。这是排查手段，不是流程门禁。

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
  "architecture": {
    "num_main_layers": 6,
    "source_of_truth": "modeling.py:120-140",
    "layer_groups": [
      {"type": "layer_type_a", "model_layer_indices": [0]},
      {"type": "layer_type_b", "model_layer_indices": [1, 2]},
      {"type": "layer_type_c", "model_layer_indices": [3, 4, 5]}
    ]
  },
  "trace_instances": [
    {"layer_group_type": "layer_type_a", "model_layer_index": 0,
     "invocation_index": 0, "op_range": [10, 21]}
  ],
  "structures": {
    "layer_type_a": {
      "name": "layer_type_a",
      "architecture_group_type": "layer_type_a",
      "runtime_pattern": "default",
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
| `architecture` | 学习到的模型架构：`num_main_layers`、`layer_groups[].model_layer_indices`、`prediction_modules`、`source_of_truth`。见 [§E](#e-schema-v2模型层-vs-运行时调用权威定义) |
| `trace_instances` | 运行时**观测到的**每次调用，各带 `layer_group_type`、`model_layer_index`、`invocation_index` 和真实 op 范围。**与 `architecture` 严格分离** |
| `structures` | 每种运行时模板一棵代表性结构树，用于报告体积压缩。顶层结构用 `architecture_group_type` 指向 learned owner，用 `runtime_pattern` 标识采集模板；多个 pattern 可以共享一个 owner。它**不**承担覆盖：真正的 op 归属来自 `trace_instances` |
| `runtime_auxiliary` | 不属于模型架构主干、但在代表性 step 中真实存在的运行时逻辑（token 选择、验证、输入更新、调度辅助逻辑）。重复出现的同类逻辑只保留一份定义，用 `instance_indices` 标明实例 |

### C.3 节点字段说明

| 字段 | 必选 | 说明 |
|---|---|---|
| `name` | 必选 | 节点名（按 [A.2 命名规则](#a2-命名规则)） |
| `semantic` | **必选**（`Cast`/`Reshape` 除外） | 节点或 kernel 的语义说明，如 "Attention QKV projection"。所有有意义的算子（包括 `Add` 残差、`Mul` 门控、`Concat` KV 缓存拼接、RMSNorm 各步骤等）均需填写，清晰说明其在模型中的计算作用 |
| `code_ref` | **必选**（除非无法判断） | 源码位置引用，格式如 `filename.py:line` 或 `filename.py:start-end` |
| `architecture_group_type` | 顶层 runtime pattern 必选 | 指向 `architecture.layer_groups` / `prediction_modules` 中已声明的 learned owner；禁止从 `_B`/`_C` 名称猜测 |
| `runtime_pattern` | 有多个运行时模板时必选 | 采集特有的模板身份，不是 learned layer 类型或层号 |
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
- `children` **只表达包含关系**：相邻两个 child 之间不存在数据流边。所有非链式连接见 [C.5](#c5-显式数据流边branches)。
- `kernels` 的 `shape_semantic` 可选（见 [B.5](#b5-shape_semantic可选注解)）。

### C.5 显式数据流边（`branches`）

`children` 的顺序描述"谁包含谁"，不描述"数据怎么流"。残差、并行支路和 skip 全部活在变量传递里：

```python
hidden, residual = self.input_layernorm(hidden, past_residual)   # 加法在 kernel 内部
hidden = self.self_attn(hidden)
hidden, residual = self.post_attention_layernorm(hidden, residual)
```

这段代码里有两处残差汇合，但 `children` 顺序上**没有任何痕迹**——没有独立的 Add 算子，op 序列里也看不出来。所以规则是：**没有在 `branches` 里声明的边，在下游就等于不存在**，Skill 2 建图与 Skill 3 渲染都禁止从 children 顺序推导连接。一个 norm 了输入却不声明分支的模板，会被正常渲染成一条直链而不报错——这正是整层残差静默丢失的方式。

每条 `branches[]`：

| 字段 | 含义 |
|---|---|
| `name` | 边的标识 |
| `kind` | `residual`（默认）/ `parallel` / `skip` / `gate` / `cross_invocation` |
| `inputs` | 分叉点（一个或多个），可用兄弟节点名或完整节点 id |
| `output` | 汇合点 |
| `semantic` | 这条边在源码里是什么 |
| `source_ref` / `code_ref` | 指向源码行 |

`inputs` 与 `output` 之间的兄弟节点就是被绕过的部分。三条容易写错的地方：

1. **方向不能反**：起点取在主路径上（两端相邻、中间没有被绕过的节点）会被 `check_dataflow.py` 的 D2 判为错误。
2. **跨调用的 carry 写成绕回式**：融合 add-norm 把本层入口 norm 融进上一次调用的尾部，因此注意力残差有一端落在**上一次调用**里。这种边的 `inputs` 位置在 `output` **之后**（在 children 顺序上绕回），下游据此识别为跨 invocation 的 carry 而非层内环。写成正向会复现 G7 要抓的反向残差缺陷。
3. **并行支路必须声明**：一个值被两个消费者读取（含直接读 `forward()` 入参的共享专家形态）要写成 `kind: parallel`。若写成相邻 children 又不给 branches，下游会把并行渲染成串行链（D4）。

写完后用 `dataflow_source.json` 逐条核对：每个 `merges[]` 都要有对应的 `branches[]`，每个 `forks[]` 都要有对应的 parallel 声明；whole-model activation edge 若能唯一匹配到两个不同顶层 owner，还必须写入顶层 `dataflow.edges`。无法唯一匹配时 checker 保持未判定，不猜边。

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
- 不能只检查 representative：首个、representative、末尾 invocation 都要比较计算 op 集、关键 kernel
  类型和后继拓扑。任一端点与代表模板结构不兼容时，必须在源码调用边界支持下建立独立 structure；
  仅 op 数或位置差异不足以猜测一个新语义模块。
- 若存在结构不同的多种 decoder layer，都要选出作为独立 layer_type。
- 若存在 mtp，mtp decoder layer 要提取出来成为一个独立 layer_type。**不得**与主模型的 decoder layer 合并。

#### D.1.2 阅读模型源码，提取模块层级和稳定函数边界

阅读 modeling 源码文件，从最外层 `ForCausalLM` 到最内层子模块，提取完整的执行语义。重点关注：

- `__init__` 中注册了哪些子模块（`self.xxx = ...`）。
- `ModuleList` 的静态整数索引属于调用身份：`self.xxx[0]` 只能对应展开节点 `xxx_0`，不能对应
  `xxx_1`；折叠节点 `xxx` 可继续表示共享模板。动态索引保持 unknown，不从节点名后缀反推源码下标。
- `forward` 中实际调用了哪些模块，调用顺序是什么。

这是唯一允许 LLM 完整扫描源码的阶段。扫描前由 `extract_source_index.py` 确定性生成
`source_index.json`，记录每个文件 SHA256、类/函数、`__init__`/`forward` 行号范围及整体
`source_bundle_hash`；首次候选完成后写 `source_scan_receipt.json`。后续修正和批判不得再次读取源码树。
若 bundle hash 改变，receipt、候选上下文和批判全部失效，必须回到 D.1.2 重新扫描。
首次候选及重扫后的候选都必须显式携带当前 `--source-bundle-hash`，且 mapping request/context
固化的 source index SHA256 仍匹配，驱动才会记录 receipt；未变化的重入只核对源码文件清单和
SHA256，不重复 AST 解析。
- 除 `nn.Module` 之外，是否存在稳定的函数封装边界。

形成模型结构树，节点来源参考 [A.1 节点来源规则](#a1-节点来源规则)。

#### D.1.3 在 op 序列中定位 decoder layer 边界

使用结构锚点在代表性 step 的 op 列表中划分 decoder layer 边界。`layer_groups[].type` 只描述 decoder layer 类型；decoder layer 之外的模型结构应归入 `stages`，不属于模型架构主干的运行时逻辑应归入 `runtime_auxiliary`。

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

Step 3 先用脚本运行预终态确定性门禁。中间修改阶段只运行确定性校验和与改动范围对应的独立
targeted critique；候选通过全部预终态门禁后，才由干净上下文中的独立批判 LLM 按
`critique_protocol.md` 完成最终十一项检查。

#### D.2.1 运行确定性脚本检查

正式流程用统一入口，输出**单一合法 JSON**：

```bash
python scripts/run_validation.py \
  -c outputs/analysis_config.json \
  -r outputs/raw_ops.json \
  -m outputs/model_manifest.json \
  --model-source models/<your_model>/modeling_<x>.py \
  -o outputs/validation_report.json
```

单独调试某一维度时才直接调用子脚本（各自 `--json` 输出单一 JSON，**不要**用 `>>` 把多个 JSON 文档追加进同一个文件——那样产出的不是合法 JSON）：

```bash
python scripts/check_structure.py   -c outputs/analysis_config.json --json
python scripts/check_dataflow.py    -c outputs/analysis_config.json -s models/<x>/modeling_<x>.py --json
python scripts/check_op_coverage.py -c outputs/analysis_config.json -r outputs/raw_ops.json --json
```

脚本规则与本指南直接对齐：

| 脚本 | 检查 |
|---|---|
| `check_structure.py` | 树良构性（schema 完整、`architecture`/`structures` 匹配、必填字段、索引列表无重复、双归属检测） |
| `check_dataflow.py` | **D1-D10：配置声明的边与源码 `forward()` 是否一致，以及源码已证明的跨顶层 owner 激活边是否显式声明** |
| `check_sublayers.py` | 代表结构树子模块一致性（父=子 union、无重叠、模板 ⊆ 代表实例） |
| `check_op_coverage.py` | op 全覆盖、不重叠、`kernels` 登记完整 |
| `validate_shapes.py` | 可选排查：shape_semantic 与实际 tensor shape 一致性（不在正式门禁内） |

#### D.2.2 确定性 issues 为空也不能跳过最终独立批判

Kernel 全覆盖和父子集合一致只能证明"每个 op 有归属"，不能证明 owner **对**。按
`critique_protocol.md` 生成 `critique_request.json`，由**未产出该候选且不继承拆解历史的**批判
LLM 逐项完成十一项检查，写出 `critique_report.json`。使用新窗口或 Codex subagent
`fork_turns=none`，只接收最终阶段 `context_manifest.json.inputs`。

#### D.2.3 修复确定性 issue

拆解 LLM 修正候选时使用以下**输入**：

1. 当前 `revision_request.json` 中的 normalized issues
2. 当前候选 `analysis_config.json`
3. `source_index.json`、`source_bundle_hash` 和脚本生成的 issue 相关函数片段
4. issue `op_indices` 对应的 `raw_ops.slice.json`

不得投喂 `iterations/` 中的旧 config/validation/critique/revision request，也不得投喂 Markdown、
HTML、UI JSON、截图、浏览器验收产物或旧聊天记录。每个阶段的 `context_manifest.json.inputs` 是唯一白名单。

**任务**：

```
依据 issues.json、源码切片、op 切片，对每一项 issue 验证算子归属与字段填写正确性。
若存在错误，直接修正 analysis_config.json 中对应位置；只允许在存在错误时修改。
要精准对齐源码，结合 ops 的 shape 和 stream_id 判断。
不能有任何冗余或遗漏。
```

**输出**：修正后的 `analysis_config.json`。review 结论必须由独立批判 LLM 另行产生。

若 `prepare_revision_context.py` 返回 `needs_controlled_diagnosis`，不得用完整源码、raw ops 或历史会话
绕过。使用 `diagnostic_request.json` 的独立白名单和 schema，在干净上下文中输出受控补丁。路由依据
checker 声明的 artifact ownership 与路径权限，不依据模型名称或错误 ID。模型不得直接编辑基础
`model_manifest.json`；需要协调 manifest/trace 时只能提出 `manifest_hypothesis`，由确定性脚本绑定
基础哈希、应用到派生产物并重跑预终态校验。没有显式权限的未知错误只能诊断，不能自行获得写权限。

#### D.2.4 定向修正、预终态门禁与最终批判

修正后重新运行 D.1.6 enrich，然后只运行确定性校验和 targeted critique。定向批判使用
`targeted_critique_request/report/validation.json` 及独立 schema，不能产生 `passed_at_cap`，不能进入
`score_breakdown.py`。候选通过所有预终态门禁后才运行最终十一项批判；任何 config 变化都会使旧
最终批判 SHA256 失效，必须对当前候选完整重做十一项。

targeted critique 只检查**发生过候选 SHA256 变化**的修订。当前候选与最近一次已评估快照相同，驱动
直接记一次无进展并返回 revision，不创建新的 targeted request。定向报告若把当前 validation 中仍为
error 的同 ID blocker 判为 `passed`，属于 `TC_DETERMINISTIC_CONFLICT`，报告无效；LLM 结论不能覆盖
确定性门禁。

循环执行直至 `passed_at_cap`。默认最多 **4** 次语义修正并启用 `--stall-limit 2`；连续两轮
deterministic error、hard gate、unmapped、duplicate、out-of-range 和定向批判阻断项都未减少，
进入 `blocked_no_progress`；第 4 次仍失败进入 `blocked_max_revisions`。旧 CLI 的
`--max-revisions` 是新参数名；旧 `--max-iterations` 和 `--stall-limit 0` 仍接受，但默认语义以本节为准。
初始候选只建立阻断计数基线，不占用修正额度；两个 blocked 终态会持久化，同一 run 不再继续。

### D.3 与下游的衔接

- 通过 D.2.4 后，`analysis_config.json` 进入 Step 4（generate_report.py）与 Step 5（compute_metrics.py），脚本调用见 SKILL.md。
- 若是 Mode B（仅模型源码），输出文件名为 `model_structure.json`，op_indices 留空，可加 `branches` 字段表达多分支；不进入 Step 4/5。详见 `references/mode_b_branches.md`。
- 若是 Mode C（仅性能数据），不走本流程，委托给仓库内的 `cann-npu-perfanalysis` skill；详见 `references/mode_c_delegate.md`。

---

## E. Schema v2：模型层 vs 运行时调用（**权威定义**）

schema v2 将“学习到的模型架构”与“运行时观测到的执行”彻底分离。v1 的 `layer_types` / `layer_structure` / `layer_indices` 三个字段**已全部废弃**，v2 config **不允许**再出现；本文档不再定义它们的语义。

### E.1 术语定义

| 术语 | 定义 | schema 字段 |
|---|---|---|
| **model layer（模型层）** | 拥有独立学习参数的 decoder layer。由源码构造决定（`nn.ModuleList(range(N))` 等） | `architecture.layer_groups[].model_layer_indices` / `model_layer_range` |
| **prediction module（MTP/预测层）** | 独立学习的预测/推测层。数量由 config（如 `num_nextn_predict_layers`）决定 | `architecture.prediction_modules[].learned_module_count` + `model_layer_indices`（追加在主层号之后） |
| **trace instance（运行时调用）** | 代表性 step 中一次真实模块调用 | `trace_instances[]` |
| **invocation_index** | 同一 model layer 的第几次运行时调用 | `trace_instances[].invocation_index` |
| **representative template（代表模板）** | 用于压缩报告体积的结构树，**不是**层号 | `structures[]` + `trace_instances[].representative_instance_id` |
| **runtime pattern** | 同一 learned owner 在一次采集中因 stream/profiler 行为形成的不同 attribution 模板 | `structures.*.runtime_pattern`；owner 由 `architecture_group_type` 显式给出 |
| **execution_count** | 从 `trace_instances` 派生的调用计数，**禁止**用模型层数代替 | 由脚本推导 |

### E.2 MTP / spec decoding 规则（重写，**唯一解释**）

> 重复调用复用同一个学习到的模块，**除非**源码构造证明存在不同参数层。

- 外层 loop 调用一个内部含 decoder layer 的包装层 N 次：记为 **1 个 learned prediction module + N 个 trace_instances**，N 个 instance 的 `model_layer_index` **全部相同**。
- **禁止**把 N 次调用写成 N 个模型层，**禁止**按 kernel 出现顺序生成伪层号（如 `6,7,8`）。
- **禁止**把 A/B/C 等 runtime pattern 写成新的 learned layer group；它们必须显式指向同一或各自有源码证据的 `architecture_group_type`。
- prediction module 的 `model_layer_indices` **必须** ≥ `num_main_layers`（追加在主层之后，不占用主层号）。
- DS3.2 金标准：`num_main_layers=61`，Dense `[0,1,2]`，MoE `[3..60]`，学习 MTP 层 **1 个**（层号 61）；`next_n=3` 时层 61 有 **3 个 invocation**。

### E.3 采集范围与外推禁令

`trace_scope` 是**可选**字段（不在 schema `required` 里）：它标注这次采集覆盖了什么，而不是模型是什么样。结构由源码决定，采集范围只影响哪些节点有性能数据。

- **不得外推**：没有被采集到的层、rank 或 stage，不得推算或复制指标。报告里这些节点应显示为"未采集"，而不是按代表层的耗时乘个系数。这是硬性规则，与 `trace_scope` 是否填写无关。
- 只有**证据充分**才能声明 `rank_local` / `pipeline_stage_local` 及具体 rank/stage。证据来自 runtime YAML（`parallel_config` 的 tp/ep/pp/cp）、launcher 参数、rank metadata、观测层集合。
- PP 未证明时若只观测到部分层，写 `kind=unknown` 或留空，**禁止**写"可能是 pipeline rank 0"再按完整模型展示。
- YAML 中缺少 PP key 视为 `pp=unknown`（**不是** `pp=1`）。
- trace 有 MoE 但无法从 shape 或正向 runtime/source 证据推导 EP 时，`ep=unknown` 是合法结果，只记录 info；能够推导但候选未声明时为可受限修正的 warning，候选与明确推导冲突时才是 error。
- 填了 `trace_scope` 就要一并给出 `confidence` 与 `evidence`；报告会显示它们。
- 层数与 trace 的交叉校验（`check_manifest_trace.py` 的 MT1）默认只作 `info`：一次采集可能只覆盖单个 step 或单个 rank，trace 不能反驳源码读出的层数。确需阻断时显式传 `--fail-on-trace-mismatch`。

### E.4 精确覆盖规则（四分类）

代表 step 的每个 op 必须归入以下**前三类之一**：

| 类别 | schema 来源 | 说明 |
|---|---|---|
| `mapped_model_ops` | `trace_instances` + `stages` + `structures` 叶子 | 模型模块算子 |
| `mapped_runtime_ops` | `runtime_auxiliary` | 运行时辅助（verify/sample/init/脚手架） |
| `excluded_profiler_ops` | `excluded_profiler_ops` | **仅** profiler/bookkeeping；`reason_code` ∈ {`profiler_marker`,`stream_sync_placeholder`,`cross_step_bookkeeping`,`device_param_update`,`empty_shape_noop`} + `evidence` |
| `unmapped_ops` | `unmapped_ops` | 归属未知 = 未完成；严格校验必然失败 |

- 覆盖率 = model ∪ runtime ∪ excluded 的**精确并集**。**禁止**用“代表层 op 数 × 层数”外推。
- missing 与 duplicate **不得**相互抵消，两者都显式报告。
- 主计算算子（MatMul/Attention/Norm/MoE/通信/Gather/KV cache/采样）**禁止**放入 `excluded_profiler_ops`（脚本 C6 阻断）。
- **禁止**用一个包含几百个索引的 `unmapped_ops` 节点冒充完成；填 `reason` 不算覆盖。
- 正式 `passed` 要求 `unmapped=0`、`duplicate=0`、无越界。探索模式 `--allow-unmapped` 状态为 `exploratory`（非 passed），报告标注未验证。
- 完整的 Step 6 映射规程与提示词模板见 `references/ai_mapping_protocol.md`。

### E.5 证据与置信度

架构与并行声明都必须带证据：`architecture.source_of_truth`、`layer_groups[].source_ref`、`trace_scope.evidence` 与 `confidence`。无法静态解析的值写 `"unknown"`，**禁止**用模型常识补值。manifest 提取器（`extract_model_manifest.py`）对每条事实记录 `source_ref`/`method`/`confidence`。

### E.6 旧版迁移

v1 config 可用 `migrate_config.py` 迁移到 v2，结果标记 `migration.status = legacy_unverified`：因 v1 的 `layer_indices` 混淆了层号与调用次数，迁移后 `trace_instances[].model_layer_index` 一律为 `"unknown"`，必须重新跑 `extract_model_manifest` + `validate_architecture` 才能提升为可信状态。
