# Mode B：仅模型代码的结构拆解

当工作目录中**只有模型源码而无性能数据**时，本 skill 进入 Mode B：仅做静态结构拆解，输出 `model_structure.json`。

---

## 使用条件

- 存在模型源码（`*modeling*.py` 或类似入口）
- 不存在 `kernel_details.csv`、`raw_ops*.json`、`ASCEND_PROFILER_OUTPUT/`

> 若两类输入同时存在 → Mode A；仅有性能数据 → Mode C（见 `mode_c_delegate.md`）。

---

## 输出文件

`outputs/model_structure.json`，schema 沿用 `analysis_config.json`（见 `structure_analysis_guide.md` §C），但有以下差异：

| 字段 | Mode A | Mode B |
|---|---|---|
| 顶层 `mode` | 不存在 | `"structure_only"` |
| 叶节点 `op_indices` | 必有 | **必为 `[]`**（无性能数据可绑定） |
| 节点 `kernels` 数组 | 11 类算子必填 `shape_semantic` | **不填写**（无 raw_ops 可核对） |
| 节点 `branches` | 不存在 | **可选**：表达静态分析无法消歧的分支 |
| `representative_step` | step ID（数字） | `null` |

---

## branches 字段：表达多分支拓扑

源码中存在条件分支但**无法仅靠静态分析判定哪条分支会执行**时（典型：MoE-vs-dense layer、sliding-vs-full attention、是否启用 MTP），在节点上加 `branches` 字段，把每条可能的分支作为一个完整子树列出。

### Schema

```json
{
  "name": "<branch_parent_name>",
  "semantic": "<分支语义说明>",
  "code_ref": "<源码位置>",
  "branches": [
    {
      "condition": "<判断条件，源码原文或等价 Python 表达式>",
      "name": "<本分支名（建议直接用源码类名/函数名）>",
      "semantic": "<本分支说明>",
      "code_ref": "<本分支起止行>",
      "children": [...]
    },
    ...
  ]
}
```

### 示例

#### 例 1：MoE vs dense decoder layer

```json
{
  "name": "decoder_layer_variants",
  "semantic": "Decoder layer with MoE-vs-dense topology determined by config.use_moe",
  "code_ref": "modeling.py:200-350",
  "branches": [
    {
      "condition": "config.use_moe == True",
      "name": "Gemma4DecoderLayer_moe",
      "semantic": "MoE decoder layer with topK expert routing",
      "code_ref": "modeling.py:200-280",
      "children": [
        {"name": "input_layernorm", "code_ref": "modeling.py:220"},
        {"name": "self_attn", "code_ref": "modeling.py:225-260"},
        {"name": "moe_block", "code_ref": "modeling.py:265-280", "children": [
          {"name": "gate", "code_ref": "modeling.py:266"},
          {"name": "experts", "code_ref": "modeling.py:268-278"}
        ]}
      ]
    },
    {
      "condition": "config.use_moe == False",
      "name": "Gemma4DecoderLayer_dense",
      "semantic": "Dense decoder layer with standard MLP",
      "code_ref": "modeling.py:285-350",
      "children": [
        {"name": "input_layernorm", "code_ref": "modeling.py:295"},
        {"name": "self_attn", "code_ref": "modeling.py:300-330"},
        {"name": "mlp", "code_ref": "modeling.py:335-345"}
      ]
    }
  ]
}
```

#### 例 2：sliding window vs full attention

```json
{
  "name": "self_attn_variants",
  "code_ref": "modeling.py:120-180",
  "branches": [
    {"condition": "layer_idx in config.sliding_window_layers", "name": "self_attn_sliding", ...},
    {"condition": "otherwise", "name": "self_attn_full", ...}
  ]
}
```

---

## 拆解流程

1. **读取所有模型源码**（不只是入口文件，包含被引用的子 module 文件）
2. 识别 `ForCausalLM` 顶层类与其 `forward` 主调用链
3. 按 `references/structure_analysis_guide.md` §A.1（节点来源）/§A.2（命名）/§A.3（边界）规则提取结构树
4. 遇到条件分支：
   - **若静态可判定**（如 `config.num_experts > 0` 且 config 已知）→ 选定分支，正常拆树
   - **若静态不可判定** → 用 `branches` 字段保留全部可能性
5. 不绑定 `op_indices`（留空数组）
6. 不填 `kernels` 与 `shape_semantic`（无 raw_ops 可核对）
7. 输出 `outputs/model_structure.json`
8. 运行结构良构性检查（`shape_semantic` 与 `op_coverage` 检查跳过）：

```bash
python scripts/check_structure.py -c outputs/model_structure.json --mode B --json > outputs/issues.json
```

---

## 与 Mode A baseline 的等价性

若同模型已有 Mode A 的 `analysis_config.json`，可校验 Mode B 输出是 Mode A 树的"骨架超集"：

```bash
python scripts/regression_check.py --mode B \
  --baseline run_1/<model>/outputs/analysis_config.json \
  --new outputs/model_structure.json
```

期望：
- 所有 Mode A 节点路径都在 Mode B 中存在
- Mode B 可多出 `branches` 节点（合理）
- 不应少于 Mode A

---

## 不会输出的内容

Mode B 不进入 Step 3 Review、Step 4 报告、Step 5 指标——这些都依赖 op_indices 与 raw_ops。
