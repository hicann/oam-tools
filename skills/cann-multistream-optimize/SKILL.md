---
name: cann-multistream-optimize
description: NPU 多流整网优化技能。用于分析和实施模型的多流优化、双流、stream overlap、控核与 TorchAir 多流改造。先做整网模块 DAG 与模块间并行性分析，再做每个模块的算子级分析、开发调试和验收。触发场景包括：多流优化、双流、stream overlap、控核、整网 DAG、模块拆解、NPU 多流、TorchAir 多流、limit_core_num、多流改造没收益调试。
user-invocable: true
---

# NPU 多流整网优化技能

面向本仓库的 NPU 多流整网优化任务，按“分析 → 开发调试 → 验收”推进。优先参考仓库内已有案例、代码模式和官方 API 索引。

## 概述

本技能解决的是**整网多流优化**。

工作主线固定如下：

1. 先拆整网模块，画模块级 DAG，判断**模块与模块**哪些能并行。
2. 再对**每个模块**拆算子，画模块内算子 DAG，判断模块内哪些算子能并行。
3. 在依赖关系明确后再做多流开发、调试和验收。

分析和实施结果统一落到：

`multi-stream-analysis/<network_or_case_name>.md`

报告结构使用 [`references/report-template.md`](references/report-template.md)。

## 重要原则

- **先整网后局部**：先回答整网主路径和模块间并行性，再进入模块内算子。
- **模块级目标明确**：模块拆解的目标是判断**模块与模块**哪些可并行。
- **每个模块都要下钻**：第二层要对每个模块都补齐算子清单、算子 DAG 和模块内并行性结论。
- **同步必须显式**：多流改造必须有清晰的 `event` / `wait` / `wait_stream` / `wait_tensor` 关系。
- **开关必须可关闭**：多流路径要保留 enable 开关和原始回退路径，方便调试与验收。
- **先证明正确，再追性能**：先验证依赖、功能和精度，再看 overlap 和时延收益。
- **overlap 不等于收益**：出现拖尾、资源争抢、host bound、shape 劣化时，要继续评估控核、和图模式限制。
- **不要混抄案例**：必须先确定当前模型的执行模式，再选一套主 API 路径，不要把 eager 和 graph 风格混着套。
- **调试优化最优编排**：优化点分流编排不唯一，调试时要多尝试不同的编排，选择性能最优方案。

## 工作流程

### 第一步：分析

1. 先读取 [`references/report-template.md`](references/report-template.md)，在 `docs/common/multi-stream-analysis/` 下创建或更新结果文件。
2. 按 [`references/module-decomposition-spec.md`](references/module-decomposition-spec.md) 完成整网模块拆解：
   - 确定分析阶段是 `prefill` 还是 `decode`
   - 产出整网模块清单、依赖清单、Mermaid 模块 DAG
   - 输出模块级并行性结论，统一使用“主串行链 / 可并行组 / 待验证组 / 建议流分组”
3. 对**每个模块**继续做算子级拆解：
   - 产出模块内算子清单、依赖清单、Mermaid 算子 DAG
   - 输出模块内并行性结论，仍使用分组式描述
4. 选案例时按 [`references/case-routing.md`](references/case-routing.md) 进入最接近的模式。

### 第二步：开发

1. 先判断当前代码属于哪种执行模式：
   - eager / patch 风格
   - graph / TorchAir 风格
2. 只选一套主 API 路径实现第一版 overlap：
   - eager / patch：`torch.npu.Stream()`、`record_event()`、`wait_event()`、`wait_stream()`
   - graph / TorchAir：`npu_stream_switch`、`npu_tagged_event_*`、`npu_wait_tensor`
3. 优先做**最小可验证 overlap**：
   - 只改一个明确的并行点
   - 先补同步，再扩大并行窗口
   - 先保留原路径和 enable 开关
4. 若 overlap 已成立但仍有明显拖尾，再评估：
   - `limit_core_num`
   - `set_stream_limit` / `get_stream_limit`
   - `npu_prefetch`
5. 所有开发决策回写结果 md：写清流分组、同步点、开关、回退路径和预期收益。

### 第三步：调试

如果多流编排方式不唯一，多尝试不同的编排方式，选择性能最优的方案。调试时按下面 4 类问题分开处理，不要混在一起排查：

1. **依赖错误 / 同步错误**
   - 重点检查事件记录、等待顺序、跨流汇合点、共享状态写入次序
   - 典型现象：读到未完成结果、死等、结果偶发错误
2. **精度或功能异常**
   - 先对比优化前基线，再按 `prefill/decode → 模块 → 算子` 缩小范围
   - 判断是否是多流引入的状态时序问题，而不是算子本身问题
3. **性能无收益**
   - 重点看 shape 变化、task 数量增加、host bound、带宽争抢、流间资源抢占、拖尾
   - 需要时继续评估控核、预取、superkernel 或缩小 overlap 范围
4. **图模式 / runtime 限制**
   - 重点看 graph break、图模式 API 约束、stream 语义差异、运行时不支持
   - graph 场景优先按 TorchAir 路径排查，不要回退成 eager 思路硬套

### 第四步：验收

验收必须至少覆盖下面 4 类，并把结果回写报告：

1. **功能验收**
   - 多流 enable 前后输出一致
   - 开关关闭后原路径可正常运行
2. **同步验收**
   - 汇合点前后无缺失等待
   - 共享状态、KVCache、通信结果没有读写乱序
3. **性能验收**
   - 记录优化前后关键时延、吞吐或单步耗时，确认确实有 overlap 和时延改善
   - 确认优化点之外的算子或模块耗时没有劣化
   - 如果无收益，要明确是实现问题还是场景不适合
4. **Profile 验收**
   - 确认确实存在 overlap，而不是逻辑上分流但执行上仍串行
   - 确认关键拖尾是否已缩短，是否出现新的空洞或资源争抢

## API 选型规则

### eager / patch 风格

优先使用：

- `torch.npu.Stream()`
- `record_event()`
- `wait_event()`
- `wait_stream()`

适用场景：

- patch 形态改造
- 现有代码已经显式使用 `torch.npu.current_stream()`
- runtime 不走 TorchAir 图内多流表达

### graph / TorchAir 风格

优先使用：

- `npu_stream_switch`
- `npu_wait_tensor`
- `npu_record_tagged_stream`
- `npu_tagged_event_wait`

适用场景：

- `ge_graph` / TorchAir 多流表达
- 代码已经显式使用 scope / tagged event 风格
- 需要把同步关系表达在图内

### 拖尾与资源问题

出现“已 overlap 但收益不稳定”时，再评估：

- `limit_core_num`
- `torch_npu.set_stream_limit`
- `torch_npu.get_stream_limit`
- `torch_npu.npu_prefetch`

使用顺序：

1. 先确认依赖和 overlap 正确
2. 再看是否存在拖尾或资源争抢
3. 最后再引入控核、stream limit 或预取

详细路由见 [`references/api-routing.md`](references/api-routing.md)。

## 参考文档索引

按需读取。

- **整网模块拆解规范**：
  [`references/module-decomposition-spec.md`](references/module-decomposition-spec.md)
- **案例选型路由**：
  [`references/case-routing.md`](references/case-routing.md)
- **官方 API 索引**：
  [`references/official-docs-latest.md`](references/official-docs-latest.md)
- **API 选型路由**：
  [`references/api-routing.md`](references/api-routing.md)
- **固定报告模板**：
  [`references/report-template.md`](references/report-template.md)
