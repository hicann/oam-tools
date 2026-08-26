# 诊断码与 L1 建议对照表

本文是 `compute_metrics.py` 的 `findings[].code` 与建议文本的**唯一来源**。修改建议只改本文，不改代码。

## 定位

- 建议是**纯咨询信息**。它不进 `validation_report.json`、不进 `breakdown_score.json`、不影响 hard_gates、不影响 SKILL.md 的两个停止条件、不参与迭代循环。
- 建议只回答「下一步该看什么数据」，**不断言根因**。指标本身不足以证明根因，断言根因会把猜测伪装成结论。
- 建议不是优化方案。是否值得优化、怎么优化，取决于业务目标和硬件配置，不在本 skill 的判断范围内。

## 聚合作用域的硬性约束

`metrics_findings.json` 每条带 `metric_scope`。当 `metric_scope == "aggregate"` 时（多 invocation 合并统计）：

- `wall_ms` 是各实例 wall 之和乘以 multiplier，可能**超过** step 总 wall（已实测到 `占比%` 达 400.0%）。
- 该作用域的 `gap_pct` / `utilization_pct` 只描述「该组总体」，**不能**推出任何单实例结论。
- 因此聚合节点的建议**必须**先降到 `instance` 作用域复核，再谈动作。所有 `advice_l1` 文本在 aggregate 作用域下自动追加前缀 `[聚合口径]`。

这条与 Skill 3 `app.js` 的 tooltip 免责声明（「表示总量，不代表单层热点或异常等级」）是同一条线，不得只在一处生效。

## ADVICE_TABLE

以下每个 `## code:` 段被 `load_advice_table()` 解析。`next_data` 是必需字段，`not_applicable` 是必需字段。

## code: GAP_BUBBLE

- **advice**: 该节点 wall 显著大于设备忙碌时间，空档不在本节点的 kernel 内部。先确认空档落在哪里：按 `start_time_us` 排序本节点 op，算相邻 op 的 `start[i+1] - (start[i]+duration[i])`，取最大的几段。
- **next_data**: `raw_ops_details.json` 本节点 `op_indices` 的 `start_time_us` / `duration_us`；`ASCEND_PROFILER_OUTPUT/trace_view.json` 对应时间窗；host 侧下发间隔看 `api_statistic.csv`。
- **not_applicable**: 节点 kernel 数 ≤ 2 时 gap 比例无统计意义；`metric_scope == "aggregate"` 时该值是跨实例累加的假空档。

## code: WAIT_DOMINANT

- **advice**: `total_cost - kernel_sum` 占比高，说明成本主要在等待而非计算。先分类等待来源：按 `wait_time` 降序取本节点 top-5 kernel，看它们的前驱算子类型。前驱是集合通信算子则属通信等待；前驱是计算算子而 wait 仍高则看是否跨流依赖；kernel_sum 极小而 wait 极大通常是 host 下发或图执行边界，不是设备侧问题。
- **next_data**: `raw_ops_details.json` 的 `Wait Time(us)` 字段；通信带宽看 `ASCEND_PROFILER_OUTPUT/communication.json` 与 `communication_matrix.json`；host 下发看 `api_statistic.csv`。
- **not_applicable**: `kernel_sum_ms < 0.1` 时 wait 占比会放大到几百甚至上千倍，比例数值不可用于横向比较，只能作为「该节点几乎不计算」的信号。

## code: UTIL_LOW

- **advice**: 忙碌时间占 wall 不足 80%。先区分是「本节点自身有空档」还是「本节点被上游拖慢」：若同时命中 GAP_BUBBLE，按 GAP_BUBBLE 处理；若未命中 GAP_BUBBLE 而利用率仍低，说明 wall 被少数长 kernel 拉长，看 `op_ratio` 里占比最高的算子类型。
- **next_data**: 本节点 `op_ratio`（Skill 2 的 `ui_facts/*_perf_data.json` 已含该字段）；对应算子的 `aic_mac_ratio` / `aiv_vec_ratio` / `aic_mte2_ratio` 判断是计算受限还是访存受限。
- **not_applicable**: 聚合作用域；以及节点只含通信算子时（通信节点的「利用率」语义不同，等待是其正常状态）。

## code: STREAM_PARALLEL_HIGH

- **advice**: kernel 时长算术和显著超过 wall，说明多流重叠执行。这通常是**好现象**，不需要动作。仅在需要归因单个算子耗时时注意：此时不能用 `kernel_sum` 占比代表墙上时钟占比，两者口径不同。
- **next_data**: 若要确认重叠关系，看 `raw_ops_details.json` 的 `Stream ID` 分布与时间区间交叠。
- **not_applicable**: 不适用于以 wall 为口径的耗时排序场景。

## code: STREAM_PARALLEL_MID

- **advice**: 存在中等程度多流重叠。同 STREAM_PARALLEL_HIGH，无需动作，注意口径差异即可。
- **next_data**: 同 STREAM_PARALLEL_HIGH。
- **not_applicable**: 同 STREAM_PARALLEL_HIGH。

## code: UTIL_GOOD

- **advice**: 利用率在 80%~95%，无需动作。
- **next_data**: 无。
- **not_applicable**: 聚合作用域下该值不代表单实例利用率。

## code: CLEAN_SEQUENTIAL

- **advice**: 四项指标彼此接近，属干净顺序执行，无空档无显著等待，无需动作。
- **next_data**: 无。
- **not_applicable**: 无。

## code: NORMAL

- **advice**: 未命中任何异常阈值，无需动作。
- **next_data**: 无。
- **not_applicable**: 无。

## code: NO_DATA

- **advice**: 该节点在代表 step 内没有 kernel。若源码中该模块应当执行，说明拆解的 op 归属可能有缺口，回到 Step 6 检查该节点的 `op_indices`；若该模块本轮确实未执行（config-gated 未选中的分支），属正常。
- **next_data**: `analysis_config.json` 该节点的 `op_indices`；`kernel_attribution.json`。
- **not_applicable**: 无。
