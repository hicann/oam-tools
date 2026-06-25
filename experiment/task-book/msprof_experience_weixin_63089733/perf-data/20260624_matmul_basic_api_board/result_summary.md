# Matmul (matmul_basic_api) msprof 性能采集结果摘要

## 采集概况

- 硬件: Atlas A2 (910B3),单芯片,CANN 8.5.2,msprof 25.5.0
- 算子: `mmad_custom<256,64,256,128,128,64,256>`(纯 Matmul,fp16)
- Shape: A[256,64] × B[64,256] → C[256,256]
- 正确性: `test pass!`,error ratio 0.0000(容差 0.0001)
- 采集方式: 命令行 `msprof --application`,在线采集后自动 analyze/export

## 关键性能指标(op_summary.csv)

| 指标 | 数值 | 说明 |
|------|------|------|
| Task Type | AI_CORE | 算子完整下沉到 AI Core,无 AI CPU 回退 |
| Block Dim | 2 | 用 2 个 AI Core(源码 numBlocks=2,singleCoreM=128 切 M 维) |
| Task Duration | 7.840 us | 单算子总耗时 |
| aicore_time | 7.285 us | AI Core 实际执行时间 |
| aic_total_cycles | 26227 | 总 cycle 数 |
| cube_utilization | 9.29% | Cube(MAC)利用率偏低 |
| aic_mac_ratio | 0.044 | MAC 计算占比仅 4.4% |
| aic_mte2_ratio | 0.330 | MTE2(GM→L1 搬入)占比 33%,为最大瓶颈 |
| aic_fixpipe_ratio | 0.274 | Fixpipe(L0C→GM 搬出)占比 27% |
| aic_mte1_ratio | 0.027 | MTE1(L1→L0)占比 2.7% |
| aic_scalar_ratio | 0.104 | 标量占比 10% |

## 性能分析结论

1. **算子全程在 AI Core 执行**,无回退,符合预期。
2. **计算单元未打满**:MAC 占比仅 4.4%、cube 利用率 9.29%。本样例 shape 很小
   (M=256,K=64,N=256,数据量约 A 32KB + B 32KB),计算量远不足以填满 Cube 流水。
3. **瓶颈在数据搬运**:MTE2(搬入)33% + Fixpipe(搬出)27% 合计占六成,典型的
   访存受限(memory-bound)小算子特征。搬运与计算未充分 overlap(本样例为单次直调,
   无 double buffer 流水)。
4. **优化方向**(针对真实大 shape 场景):增大 baseM/baseN/baseK 提升单次 Mmad 计算量、
   引入 double buffer 让 MTE2 搬入与 Mmad 计算 overlap、多核切分匹配 K 维以提升 Cube 占用率。
   本样例作为基础 API 教学样例,未做上述优化,实测数据印证了"小 shape 下搬运主导"的结论。

## 交付数据

解析后的核心性能数据见同目录 `mindstudio_profiler_output/`:

- `op_summary_*.csv` — 算子级详细指标(上表来源)
- `op_statistic_*.csv` — 算子类型聚合(Total Time 7.84us,Ratio 100%)
- `task_time_*.csv` — Task 调度时间线(含 PROFILING_ENABLE/DISABLE 标记 task)
- `api_statistic_*.csv` — Host 侧 AscendCL API 耗时(aclrtResetDevice 236ms 为设备复位,
  aclrtCreateStream/DestroyStream 各约 0.5ms,均为一次性开销,与算子计算无关)
- `msprof_*.json` — timeline trace(可导入 MindStudio Insight 查看)
