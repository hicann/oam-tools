# Mode C：仅性能数据，委托给 cann-npu-perfanalysis

当工作目录中**只有性能数据而无模型源码**时，本 skill 进入 Mode C：委托给同一仓库的 `cann-npu-perfanalysis` skill 做 8 维性能诊断（不做模型结构拆解）。

---

## 使用条件

- 存在 `kernel_details.csv` 或 `ASCEND_PROFILER_OUTPUT/` 目录
- 不存在模型源码（`*modeling*.py` 或类似入口）

> 模型源码若也存在 → Mode A；仅有源码 → Mode B（见 `mode_b_branches.md`）。

---

## 委托方式

Mode C 不复用本 skill 的拆解流程。加载 `skills/cann-npu-perfanalysis/SKILL.md` 及其 references 后执行；需要隔离上下文时可交给 general-purpose subagent。

### 步骤

#### 1. 定位仓库内 skill

确认当前仓库存在 `skills/cann-npu-perfanalysis/SKILL.md`。如果缺失，直接报告依赖不完整，不在运行期间下载外部代码。

#### 2. 拉起 subagent

使用 Agent 工具，subagent_type=`general-purpose`，prompt 模板：

```
你将作为 cann-npu-perfanalysis 技能的执行 agent，对以下 NPU profiling 数据做 8 维性能诊断。

技能定义：
- SKILL.md: skills/cann-npu-perfanalysis/SKILL.md
- 参考资料目录: skills/cann-npu-perfanalysis/references/
  - data-schema.md       # CSV/JSON column dictionary
  - metrics-formulas.md  # Phase 1-2 公式
  - thresholds.md        # P0-P3 阈值
  - hardware-specs.md    # 各芯片峰值 TFLOPs

输入数据：
- profile 目录: <ASCEND_PROFILER_OUTPUT_DIR>
  （含 kernel_details.csv、step_trace_time.csv、op_statistic.csv、communication.json、communication_matrix.json）

执行要求：
1. 严格按 SKILL.md 的 Phase 0–4 流程执行（解析 → 计算指标 → 诊断瓶颈 → 输出）
2. 自动检测 V1/V2 schema（看是否有 cube_utilization(%) 列）
3. 缺失文件时跳过对应维度（dim 3/5/6/7），rows < 500 时跳过 dim 7
4. 严格遵循 SKILL.md 的 NEVER 列表

输出文件（写入调用方 outputs/ 目录）：
- analysis_data.json  # 8 维结构化诊断数据，schema 见 SKILL.md 第 255-424 行
- report.md           # 人读报告，含 P0-P3 优先级瓶颈
- report.html         # 用 skills/cann-npu-perfanalysis/references/generate_html.py 渲染

返回：三文件路径 + 一句话顶层结论。
```

#### 3. 处理 subagent 返回

- 若成功：把 `outputs/analysis_data.json` / `report.md` / `report.html` 列入 Mode C 产物
- 若失败（如 profile 目录缺关键文件）：把 subagent 的错误信息直接呈现给用户，不再 fallback

---

## 与本 skill 输出的关系

`cann-npu-perfanalysis` **不做模型结构拆解**——它输出的是性能诊断（迭代效率、算子热点、硬件利用率/MFU、通信效率、设备空泡、等待锚点、层级结构粗判、多卡均衡）。

| 维度 | 本 skill (Mode A) | cann-npu-perfanalysis (Mode C) |
|---|---|---|
| 模型结构树 | ✅ 完整拆解到子模块 | ❌ 只做 MoE-yes/no、layer 数粗判 |
| op→源码归属 | ✅ 精准对齐 | ❌ |
| 性能瓶颈诊断 | ❌（仅给四维指标） | ✅ P0–P3 |
| 硬件利用率 / MFU | ❌ | ✅ |
| 通信效率分析 | ❌ | ✅ |
| 多卡均衡分析 | ❌ | ✅ |

互补关系。**Mode C 与 Mode A 的输出 schema 不同，不做强 diff 校验**。

---

## 依赖策略

- 只使用随 `oam-tools` 一起评审和发布的 `skills/cann-npu-perfanalysis/`
- 不在 skill 运行期间 clone、pull 或执行外部仓库代码
- 依赖缺失时给出明确错误：`Mode C 需要仓库内的 skills/cann-npu-perfanalysis/SKILL.md`

---

## 不会输出的内容

Mode C 不产出 `analysis_config.json`、`raw_ops*.json`、`{prefix}_report.md`、`metrics_report.md`——这些是本 skill Mode A 的产物。Mode C 的全部产物来自 sibling skill。
