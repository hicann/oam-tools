# Matmul (matmul_basic_api) msprof Profiling Result Summary

## Collection Overview

- Hardware: Atlas A2 (910B3), single chip, CANN 8.5.2, msprof 25.5.0
- Operator: `mmad_custom<256,64,256,128,128,64,256>` (pure Matmul, fp16)
- Shape: A[256,64] × B[64,256] -> C[256,256]
- Correctness: `test pass!`, error ratio 0.0000 (tolerance 0.0001)
- Collection method: command-line `msprof --application`, with auto analyze/export after online collection

## Key Performance Metrics (op_summary.csv)

| Metric | Value | Description |
|--------|-------|-------------|
| Task Type | AI_CORE | Operator fully offloaded to AI Core, no AI CPU fallback |
| Block Dim | 2 | Uses 2 AI Cores (source numBlocks=2, singleCoreM=128 splits the M dimension) |
| Task Duration | 7.840 us | Total single-operator latency |
| aicore_time | 7.285 us | Actual AI Core execution time |
| aic_total_cycles | 26227 | Total cycle count |
| cube_utilization | 9.29% | Cube (MAC) utilization is low |
| aic_mac_ratio | 0.044 | MAC compute ratio only 4.4% |
| aic_mte2_ratio | 0.330 | MTE2 (GM->L1 load) ratio 33%, the largest bottleneck |
| aic_fixpipe_ratio | 0.274 | Fixpipe (L0C->GM store) ratio 27% |
| aic_mte1_ratio | 0.027 | MTE1 (L1->L0) ratio 2.7% |
| aic_scalar_ratio | 0.104 | Scalar ratio 10% |

## Performance Analysis Conclusion

1. **The operator runs entirely on the AI Core**, no fallback, as expected.
2. **Compute units are not saturated**: MAC ratio only 4.4%, cube utilization 9.29%. This sample shape is
   very small (M=256, K=64, N=256, data volume about A 32KB + B 32KB), and the compute volume is far from
   enough to fill the Cube pipeline.
3. **The bottleneck is data movement**: MTE2 (load) 33% + Fixpipe (store) 27% together account for 60%, a
   typical memory-bound small-operator characteristic. Movement and compute do not overlap well (this
   sample is a single direct call with no double-buffer pipeline).
4. **Optimization directions** (for real large-shape scenarios): enlarge baseM/baseN/baseK to raise the
   per-Mmad compute volume, introduce double buffering so MTE2 loads overlap with Mmad compute, and split
   across cores matching the K dimension to raise Cube occupancy. As a basic-API teaching sample, it does
   not apply the above optimizations; the measured data confirms the "movement-dominated under small shape" conclusion.

## Delivered Data

The parsed core performance data is in `mindstudio_profiler_output/` in the same directory:

- `op_summary_*.csv` — operator-level detailed metrics (source of the table above)
- `op_statistic_*.csv` — operator-type aggregation (Total Time 7.84us, Ratio 100%)
- `task_time_*.csv` — Task scheduling timeline (includes PROFILING_ENABLE/DISABLE marker tasks)
- `api_statistic_*.csv` — host-side AscendCL API latency (aclrtResetDevice 236ms is device reset,
  aclrtCreateStream/DestroyStream about 0.5ms each, all one-time overhead unrelated to operator compute)
- `msprof_*.json` — timeline trace (can be imported into MindStudio Insight)
