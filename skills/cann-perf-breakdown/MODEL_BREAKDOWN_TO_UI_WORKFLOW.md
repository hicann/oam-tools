# 模型拆解到 UI 报告：工作流导航

从一份 NPU profiling 采集到一个可交互性能报告，要依次用三个 skill。

**这个文件只回答「下一步该用哪个 skill」。** 每段具体怎么做、用什么参数、字段怎么定义、断言怎么写，全部看对应 skill 自己的 `SKILL.md` 和 `references/`。

**要改流程，改对应的 skill 文件，不要改这里。** 这里写的任何细节都可能过期；skill 文件才是唯一真相。

---

## 一句话唤醒

```
用 skills/cann-perf-breakdown 三段流程，从 <采集目录> 拆解 <模型名> 并生成两个 HTML 报告
```

对应一条命令：

```bash
python3 <skills>/2-adapt-breakdown-to-ui-json/scripts/run_pipeline.py \
  --capture-dir <采集目录> --model-id <模型名> --out <输出目录>
```

它自动找 `kernel_details.csv` / `trace_view.json` / `modeling_*.py`，跑完全部确定性步骤，
产出 `<输出目录>/breakdown_report.html` 和 `<输出目录>/ui-report/report/index.html`，
最后打印一个 JSON 状态对象。

**两处会停下来等人**，因为它们本身就是 AI 阅读源码的工作，没有脚本：

| status | 含义 | 继续方式 |
|---|---|---|
| `awaiting_ai_mapping` | 需要 AI 把每个 op 归属到结构节点，写出 `analysis_config_v2.json` | 加 `--breakdown-config <文件>` 重跑 |
| `awaiting_semantic_review` | 需要 AI 完成九项语义审查 | 加 `--semantic-review <文件>` 重跑 |

停下时会写出请求文件，里面列好了该读哪些输入、该产出什么。这是设计行为，不是失败 —— 退出码为 0。

继续一份已有拆解时再加 `--manifest <已审查的 model_manifest.json>`：语义审查按 SHA256
绑定到它，重新提取会因格式差异让一份有效审查失效。

重复层组的角色名要显式声明，不允许从类名启发式推导：

```bash
  --rename-group <源码类名>=<报告角色名>     # 可重复
```

其他状态：`needs_iteration`（评分未过，附 `required_actions`）、`failed`（附具体阶段与原因）。

---

## 三个 skill 在哪

全部放在 `skills/cann-perf-breakdown/` 下，按执行顺序编号：

```
skills/cann-perf-breakdown/
  1-perf-breakdown/                 SKILL.md scripts/ references/ schemas/ adapters/
  2-adapt-breakdown-to-ui-json/     SKILL.md scripts/ references/
  3-generate-ui-json-report/        SKILL.md scripts/ assets/ references/ agents/
```

目录名带序号只为标明顺序；每个 skill 的真实名字在自己 `SKILL.md` 的 `name:` 字段里，调用时用那个名字。下文用 `<skills>` 指代 `skills/cann-perf-breakdown` 目录。

## 全链路

```
采集产物                    ①                    ②                       ③
CSV + 源码 + trace  →  perf-breakdown-skill  →  adapt-breakdown-to-ui-json  →  generate-ui-json-report
                        拆解 + 算子归属          转成 4 个 UI facts            report/ 运行时 + 交互
```

| 段 | 目录 / skill 名 | 输入 | 产出 |
|---|---|---|---|
| ① | `<skills>/1-perf-breakdown`<br>`perf-breakdown-skill` | profiling CSV、模型源码、runtime YAML | `analysis_config_v2.json`、`raw_ops*.json`、拆解 HTML |
| ② | `<skills>/2-adapt-breakdown-to-ui-json`<br>`adapt-breakdown-to-ui-json` | ① 的产物 | `*_analysis_config.json`、`*_perf_data.json`、`*_timeline.json`、`model_architecture_graph.json` |
| ③ | `<skills>/3-generate-ui-json-report`<br>`generate-ui-json-report` | ② 的产物 + `trace_view.json` | `report/` 运行时、`trace_index`、`overlay`、`trace_bindings` |

各段入口（细节看各自 `SKILL.md`，这里只为定位）：

```bash
# ① 校验与评分（拆解主体是 AI 按 protocol 执行，不是单个脚本）
python3 <skills>/1-perf-breakdown/scripts/run_validation.py  ...
python3 <skills>/1-perf-breakdown/scripts/score_breakdown.py ...

# ② 五步，顺序固定
python3 <skills>/2-adapt-breakdown-to-ui-json/scripts/check_breakdown_ready.py ...
python3 <skills>/2-adapt-breakdown-to-ui-json/scripts/build_node_index.py      ...
python3 <skills>/2-adapt-breakdown-to-ui-json/scripts/attribute_kernels.py     ...
python3 <skills>/2-adapt-breakdown-to-ui-json/scripts/emit_ui_facts.py         ...
python3 <skills>/2-adapt-breakdown-to-ui-json/scripts/validate_conversion.py   ...

# ③ 需要 node，--repo 必填
node <skills>/3-generate-ui-json-report/scripts/generate-report.mjs --repo <report-repo> ...
```

---

## 从哪一段开始

按手里已有的东西选入口。

| 手里有 | 从哪开始 |
|---|---|
| 只有 profiling 采集和模型源码 | ① |
| 有 `analysis_config_v2.json`，且校验评分已通过 | ② |
| 有 analysis / perf / timeline 三个 JSON | ③ |
| 有报告了，只想补原始 trace 或刷新前端 | ③（局部刷新模式） |
| 有报告了，想改展示/交互 | 直接改 `report/`，不走这条链路 |

## 段间门禁

上一段没到位，下一段不许启动。判据看文件，不看印象。

**① → ②**

```
validation_report.json   status: passed（或 passed_with_warnings 且仅含数据可用性 warning）
breakdown_score.json     convertible: true（status 表达证据层级，不写死 passed）
analysis_config_v2.json  unmapped_ops: []
```

`unmapped_ops` 非空、评分未过、语义审查过期或哈希失配，② 的就绪门禁会直接拒绝。不要绕过它。

**② → ③**

② 的转换校验通过，且三个 JSON 的 `model_id` / `report_id` / `representative_step` 完全一致。

**采集期就要注意的一件事**

`trace_view.json` 第 ① 段用不到，但必须和 CSV 同批留存 —— ③ 段必需，事后补不回来。这是整条链路最容易断的地方。

---

## 三条容易走错的岔路

**`perf_data.json` 和 `timeline.json` 不是 ③ 生成的。**

它们是 ③ 的**输入**，由 ② 产出。③ 只写 `trace_index` / `graph` / `overlay` / `trace_bindings` 四个 outputs。想让 ③ 生成它们会白费功夫。

**① 段末尾的 HTML 不是 ③ 段的报告。**

① 产出的是自包含拆解报告，③ 产出的是交互式 UI 报告，两者由不同 skill 生成、指纹不同。要交互报告就必须走完 ② 和 ③。

**代码是架构真值，trace 单向使用。**

`modeling_*.py` / `config*.py` 决定模型有什么结构。trace 只能证伪不能裁定：trace 跑过的 kernel 没有归属 → 拆解错误；层数、hidden、专家数这类标量 trace 一律不能裁定，因为它可能只采了一步，且 kernel 宽度是并行切分后的量。

checkpoint `config.json` 不可达时以代码为准，记 evidence gap、降 manifest 置信度，但不阻断流程。「代码 N 层 vs trace 观测 M 层」这类分歧不是待解决问题，是已有结论 —— 采集没观测到的结构节点走 source-only 机制（细节见 ② 的 SKILL.md），架构图上照样可见可选，只是不带指标。

---

## 出问题时看哪个文件

| 症状 | 责任段 | 看哪里 |
|---|---|---|
| 算子覆盖率不足 100% | ① | `validation_report.json` |
| 层数 / 架构标量校验失败 | ① | `model_manifest.json` 的置信度与 gap 记录 |
| 语义审查过期 | ① | `semantic_review_validation.json` |
| ② 拒绝启动 | ① | 上面的 ①→② 门禁三项 |
| kernel 归属计数不符 | ② | `kernel_attribution.json` |
| 节点 ID 与报告对不上 | ② | 重复组的角色名重命名声明 |
| timeline owner 无法解析 | ② | 转换校验输出 |
| 身份 / 不变量校验失败 | ③ | ③ 的校验器输出 |
| 源码哈希不匹配 | ③ | 视为重新提取架构的请求，不要只换哈希 |

通用原则：**让断言失败。** 断言破了说明结构变了或采集不同 —— 报告它。不要放宽断言、丢弃 kernel、重新分配余数、或退化到 phase 级 owner 来让流程跑通。绝不通过生成采集里不存在的数据来关闭一个失败。

---

## 展示层陷阱（③ 之后）

数据对但界面读起来不对，通常是这几种。都属于渲染层，改 `report/`，不要回头动 backend JSON。

- **算子占比列表被截断** — 只渲染 top-N 时列表和小于 100%。全列，或把余量并成「其他 N 种 X%」
- **父子百分比混在扁平列表里** — 按时长降序的扁平数组把容器和子节点排成视觉同级，顺着加必然超 100%。按路径深度建树，子节点显示占父节点百分比
- **分母不一致** — kernel 时间之和与端到端墙上时间差一个 launch gap。选定分母后在标签上写明，或把 gap 做成显式节点
- **聚合计数被读成单实例** — 折叠重复组上的 kernel 计数是整步总次数。写成 `<单层> × <实例数> = <总数>`
- **空分组静默消失** — 数据形状与建树假设不符时，过滤后分组为空会被整个丢掉，界面上看不出差别

backend schema 不一致时，报告一个 backend 需求，不要在前端打补丁。

---

## 交付时说什么

报产物文件里的实际数字：节点数、mapped 对 source-only、kernel 数与归属覆盖率、timeline event 数、`total_time_us`。显式展示零余数的账（`<total> = <declared> + <instances> × <per-instance>`），让分段可审计。

同一模型有另一份已知良好报告时，比对与采集无关的值：`hbm_mb` 是声明 shape 与 dtype 的纯函数，跨采集必须精确相等；时间占比合理地不同。**`hbm_mb` 相等而时间占比不同，是正确转换了另一份采集的预期特征。**
