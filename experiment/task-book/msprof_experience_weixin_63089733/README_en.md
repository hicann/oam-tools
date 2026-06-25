# msprof Profiling Tool Experience - weixin_63089733

This directory is the deliverable for GitCode task book [`#129`](https://gitcode.com/cann/oam-tools/issues/129).
It uses the Ascend C `matmul_basic_api` (pure Matmul) operator sample from asc-devkit, performs NPU
performance data collection via the `msprof` command line on a real **Atlas A2 (910B3)** board, and
analyzes the collected results.

## Directory Layout

```text
msprof_experience_weixin_63089733/
├── README.md
├── app/                              # Operator application source (from asc-devkit matmul_basic_api sample)
│   ├── CMakeLists.txt
│   ├── data_utils.h
│   ├── matmul_basic_api.asc          # Ascend C Matmul kernel + direct-call main
│   └── scripts/
│       ├── gen_data.py               # Generate inputs and golden
│       └── verify_result.py          # Accuracy verification
├── perf-data/
│   └── 20260624_matmul_basic_api_board/
│       ├── environment.txt           # Hardware / CANN / collection environment info
│       ├── matmul_basic_api_msprof.log  # msprof collection log
│       ├── result_summary.md         # Performance metric summary and analysis conclusion
│       └── mindstudio_profiler_output/  # Core performance data parsed by msprof
│           ├── op_summary_*.csv      # Operator-level detailed metrics
│           ├── op_statistic_*.csv    # Operator-type aggregation
│           ├── task_time_*.csv       # Task scheduling timeline
│           ├── api_statistic_*.csv   # Host-side AscendCL API latency
│           ├── msprof_*.json         # timeline trace
│           └── README.txt            # Official description of msprof output fields
└── run.sh                            # One-click reproduce script (build -> run -> verify -> profile)
```

## Workload Description

- Operator: Matmul, kernel `mmad_custom<256,64,256,128,128,64,256>`
- Shape: `A[256,64] fp16` × `B[64,256] fp16` -> `C[256,256] fp16`
- Tiling: `singleCoreM=128`, `baseM=128 baseK=64 baseN=256`, `numBlocks=2` (two cores splitting the M dimension)
- Implementation: basic API manually orchestrating the `GM->L1->L0->Mmad->Fixpipe->GM` pipeline
  (L1/L0A/L0B/L0C buffers at each level + HardEvent synchronization)
- Data: `gen_data.py` uses numpy random integers `[-10,10)` cast to fp16
- Correctness: `test pass!`, error ratio `0.0000` (tolerance `0.0001`)

## Test Environment

- Hardware: Atlas A2 **910B3** (`npu-smi` 25.5.0, HBM 65536 MB)
- CANN: **8.5.2** (meets the task book `>=8.5.0` requirement)
- Toolchain: CMake + bisheng, `--npu-arch=dav-2201`, host g++ 9.4.0, aarch64
- msprof: `/home/developer/Ascend/cann-8.5.2/bin/msprof` (25.5.0)
- Collection environment: Huawei Cloud development environment (CANNLab), single chip visible

## Reproduce Commands

```bash
# In the matmul_basic_api sample root of asc-devkit
source /home/developer/Ascend/cann-8.5.2/set_env.sh
mkdir -p build && cd build
cmake -DCMAKE_ASC_ARCHITECTURES=dav-2201 ..
make -j
python3 ../scripts/gen_data.py
./demo
python3 ../scripts/verify_result.py output/output.bin output/golden.bin   # -> test pass!

# msprof command-line collection (note: the output dir must NOT be group/other writable, or msprof refuses)
mkdir -p prof_out && chmod 750 prof_out ./demo
msprof --application="./demo" \
       --output="./prof_out" \
       --ai-core=on --task-time=on --aicpu=on \
       --aic-metrics=PipeUtilization \
       --analyze=on
```

The `run.sh` in this directory wraps the above flow; run `bash run.sh` to reproduce (requires a 910B3 environment).

## Collection Results

`msprof --application` online collection succeeded, with analyze/export completed automatically afterward,
yielding the full parsed data:

| Metric | Value | Description |
|--------|-------|-------------|
| Task Type | **AI_CORE** | Operator fully offloaded to AI Core, no AI CPU fallback |
| Block Dim | 2 | Dual-core execution |
| Task Duration | **7.840 us** | Total single-operator latency |
| cube_utilization | 9.29% | Cube (MAC) utilization |
| aic_mac_ratio | 0.044 | MAC compute ratio |
| aic_mte2_ratio | 0.330 | Load (GM->L1) ratio, the largest item |
| aic_fixpipe_ratio | 0.274 | Store (L0C->GM) ratio |

### Performance Analysis Conclusion

1. The operator runs entirely on the AI Core with no fallback, as expected.
2. Compute units are not saturated (MAC ratio 4.4%, cube utilization 9.29%): this sample shape is very
   small, and the compute volume is insufficient to fill the Cube pipeline.
3. **The bottleneck is data movement**: MTE2 load 33% + Fixpipe store 27% together account for about 60%,
   a typical memory-bound small-operator characteristic. This sample is a single direct call with no
   double buffering, so movement and compute do not overlap.
4. Optimization directions (for real large-shape scenarios): enlarge the base block to raise per-Mmad
   compute volume, introduce double buffering so loads overlap with compute, and split across cores
   matching the K dimension. This sample is for teaching and does not apply these optimizations; the
   measured data confirms the "movement-dominated under small shape" conclusion.

See [`perf-data/20260624_matmul_basic_api_board/result_summary.md`](perf-data/20260624_matmul_basic_api_board/result_summary.md)
for the full metrics and field interpretation.

## Issues and Suggestions

1. Running `msprof ./demo` directly reports `Argument --output=./ is writable by groups` and exits.
   For anti-privilege-escalation reasons msprof refuses a group-writable output dir, but the error does
   not give an actionable hint such as "tighten the directory permissions or specify `--output` explicitly";
   suggest adding it to the error message.
2. `--analyze` is ineffective when `--application` is non-empty (online collection) and prints the
   `The argument --analyze is useless when --application is not empty` WARNING. Suggest the docs clarify
   that online collection auto-analyzes, and `--analyze` is only for the offline `--export` flow, to avoid misuse.

## Acceptance Notes

- Successfully collected performance data on a real 910B3 board using `msprof`; data is complete.
- The parsed output contains four CSVs (`op_summary` / `op_statistic` / `task_time` / `api_statistic`) and a timeline trace.
- Operator accuracy verification passed (`test pass!`).
- Provided a performance analysis conclusion based on real metrics, plus tool-usage feedback.
