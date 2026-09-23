---
name: orchestrator-skill
description: CANN 日志分析的统一调度入口。对已有日志先检索案例库，再识别场景并路由采集、诊断和度量能力；维护每步 Markdown 产物、持续重试与断点恢复。当需要分析日志但不确定场景、处理混合故障信号、统一编排或恢复中断分析时使用。调度替代保持相同证据标准和输出字段。
license: Apache-2.0
---

# 统一调度技能

核心任务是**先检索案例，再分类路由，并可追溯地执行和恢复**。分析只使用当前已提供的材料。
缺证写入 `evidence_gaps` 和结论边界，不发起补采，不通过删步骤、减证据或分数封顶降低诊断能力。

## 固定流程

```text
已有原始日志 + 用户描述
  → errors 入口错误识别（保留位置和原文）
  → case_lookup 案例检索（hit / miss 都继续）
  → detect 场景分类（保留冲突候选）
  → clean 保守清洗与来源映射
  → diagnose 按场景剧本诊断
  → confidence 原五维评分
  → promote 记录案例处置（默认不写库）
  → report 度量报告
```

`collect-skill` 是独立的初始采集能力：用户明确安排采集时先交付原始材料与 `collection.md`。
已有日志进入本流程后不再回调采集，也没有“低分→补采”循环。

## 路由顺序与识别边界

1. 从原始材料提取有位置的错误证据 `errors` 与检索特征，搜索 `eval-skill/references/cases.md`；不从候选区或解决方案段落匹配。
2. 记录命中案例、相同签名、差异、版本待核实项；没有强签名就记 miss。案例库不可读则明确记录 unavailable。
3. 无论 hit、miss 或 unavailable，都对当前现场进行场景分类。命中不是根因确认，分类也不是因果判断。
4. 强现场信号优先于话术和文件名；多种强信号保留 `secondary`、`uncertain` 和证据位置。同一文件行序可辅助选择分析入口，不能跨主机直接推断因果。
5. `137` 不等于 OOM；仅 `EZ9999` 不足以确定 AI Core Error；旧 core 文件不能单凭名字确认为本次崩溃。

场景为 `crash/aicore_error/oom/hang/comm_timeout/compile_error/perf_degradation/precision/generic_error/unknown`。
其中 `perf_degradation` 表示业务性能劣化，与调度策略无关。判定规则、扫描边界及路由见
[场景识别规范](references/scenario-recognition.md)。

## 清洗不能损伤证据

- 使用原始日志做案例检索与初始分类，清洗结果只是可回查的分析视图。
- 保留全部级别、正常进展、重复 ERROR、堆栈续行、空行和文件内原始顺序。
- 只折叠连续完全相同且整行符合明确 DEBUG 心跳模式的噪声；原文、次数、原行号全部留在审计中。
- `--level ERROR` 只标记重点，不删除其他上下文。合并不按单行时间戳排序。
- 原文件只读；编码错误、覆盖原日志、输出路径冲突必须报错。

详见 [清洗证据保护规范](../eval-skill/references/fault-flows/common-flow.md)。

## 运行与恢复

以下命令从当前项目根目录执行，Python 3.8+：

```bash
python3 orchestrator-skill/scripts/detect_scenario.py --input ./logs/ --request "训练中断" --plan-out plan.json
python3 orchestrator-skill/scripts/run_pipeline.py --plan plan.json --dry-run
python3 orchestrator-skill/scripts/run_pipeline.py --plan plan.json
python3 orchestrator-skill/scripts/run_pipeline.py --plan plan.json --status
python3 orchestrator-skill/scripts/run_pipeline.py --plan plan.json --resume
python3 orchestrator-skill/scripts/run_pipeline.py --plan plan.json --restart-from clean
```

`diagnose` 和 `report` 由 Agent 完成，脚本生成 `blocked` 的 Markdown 工作模板后停止。
按对应 skill 填写其 `result` 与正文，核对字段、证据和时间戳，设 `status=success` 后 `--resume`。
必须保留当前 `run_id/stage/attempt/inputs`；不能拿旧报告改个文件名当作本次产物。
没有根因证据时填写 `root_cause.status=undetermined`、事实和限制，也可以完成分析。

## 调度降级、重试和恢复

调度降级仅表示换等价执行方式：例如自动脚本不可用时，保留同一步骤及其 Markdown 模板，
由 Agent 按原标准完成。可在 `plan.json` 中设 `stages.<step>.execution="manual_equivalent"`。
脚本缺失时会进入该等待接口；资源错误持续尝试，永久错误需修复运行条件后恢复。
不自动换工具、切场景、改清洗级别、跳诊断、压低评分上限。

transient 和 resource 执行错误持续自动重试，直到步骤产物通过契约校验；每次尝试留下同名同结构 Markdown 快照。
永久、未知和中断错误停止，避免对不可恢复条件空转。blocked 不消耗重试次数，案例写入的不确定副作用仍需先核对回执。
已完成阶段需输入、参数、脚本、上游和附件内容哈希一致才能复用。

详见 [调度降级与重试](references/degradation-retry.md)、[断点恢复](references/checkpoint-recovery.md)。

## 每步交付与分工

| Step | Owner | 主产物 |
| --- | --- | --- |
| errors（入口） | orchestrator-skill | case-match.md、scenario.md 中的 errors |
| case_lookup | orchestrator-skill | case-match.md |
| detect | orchestrator-skill | scenario.md |
| clean | eval-skill | clean-result.md |
| diagnose | eval-skill | diagnosis.md |
| confidence | eval-skill | confidence.md |
| promote | eval-skill | promotion.md |
| report | metric-skill | report.md |

所有字段、空值语义、失败和重试格式的唯一规范是 [流水线产物契约](references/pipeline-artifacts.md)。
主产物位于 `.cann-orchestrator/artifacts/`，每次尝试同名快照在 `attempts/<step>/<attempt>/`。
JSON 仅用于计划、状态和调用现有子脚本的内部兼容输入，不替代 Markdown 交付。
四个 skill 安装在同一父目录，便于共享契约和跨 skill 引用。
