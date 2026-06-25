# msprof 性能工具体验 - weixin_63089733

本目录是 GitCode 任务书 [`#129`](https://gitcode.com/cann/oam-tools/issues/129) 的交付件,
使用 asc-devkit 中的 Ascend C `matmul_basic_api`(纯 Matmul)算子样例,在 **Atlas A2(910B3)** 真实板卡上
通过 `msprof` 命令行方式完成 NPU 性能数据采集,并对采集结果做性能分析。

## 目录结构

```text
msprof_experience_weixin_63089733/
├── README.md
├── app/                              # 算子应用源码(来自 asc-devkit matmul_basic_api 样例)
│   ├── CMakeLists.txt
│   ├── data_utils.h
│   ├── matmul_basic_api.asc          # Ascend C Matmul 核函数 + 直调 main
│   └── scripts/
│       ├── gen_data.py               # 生成输入与 golden
│       └── verify_result.py          # 精度校验
├── perf-data/
│   └── 20260624_matmul_basic_api_board/
│       ├── environment.txt           # 硬件/CANN/采集环境信息
│       ├── matmul_basic_api_msprof.log  # msprof 采集日志
│       ├── result_summary.md         # 性能指标摘要与分析结论
│       └── mindstudio_profiler_output/  # msprof 解析后的核心性能数据
│           ├── op_summary_*.csv      # 算子级详细指标
│           ├── op_statistic_*.csv    # 算子类型聚合
│           ├── task_time_*.csv       # Task 调度时间线
│           ├── api_statistic_*.csv   # Host 侧 AscendCL API 耗时
│           ├── msprof_*.json         # timeline trace
│           └── README.txt            # msprof 输出字段官方说明
└── run.sh                            # 一键复现脚本(编译→跑→校验→采集)
```

## 负载说明

- 算子: Matmul,核函数 `mmad_custom<256,64,256,128,128,64,256>`
- Shape: `A[256,64] fp16` × `B[64,256] fp16` → `C[256,256] fp16`
- Tiling: `singleCoreM=128`、`baseM=128 baseK=64 baseN=256`,`numBlocks=2`(双核切 M 维)
- 实现: 基础 API 手动编排 `GM→L1→L0→Mmad→Fixpipe→GM` 流水(L1/L0A/L0B/L0C 各级 buffer + HardEvent 同步)
- 数据: `gen_data.py` 用 numpy 随机整数 `[-10,10)` 转 fp16
- 正确性: `test pass!`,error ratio `0.0000`(容差 `0.0001`)

## 实测环境

- 硬件: Atlas A2 **910B3**(`npu-smi` 25.5.0,HBM 65536 MB)
- CANN: **8.5.2**(满足任务书 `>=8.5.0` 要求)
- 工具链: CMake + bisheng,`--npu-arch=dav-2201`,host g++ 9.4.0,aarch64
- msprof: `/home/developer/Ascend/cann-8.5.2/bin/msprof`(25.5.0)
- 采集环境: 华为云开发环境(CANNLab),单芯片可见

## 复现命令

```bash
# 在 asc-devkit 的 matmul_basic_api 样例根目录下
source /home/developer/Ascend/cann-8.5.2/set_env.sh
mkdir -p build && cd build
cmake -DCMAKE_ASC_ARCHITECTURES=dav-2201 ..
make -j
python3 ../scripts/gen_data.py
./demo
python3 ../scripts/verify_result.py output/output.bin output/golden.bin   # -> test pass!

# msprof 命令行采集(注意输出目录需 group/other 不可写,否则 msprof 拒绝)
mkdir -p prof_out && chmod 750 prof_out ./demo
msprof --application="./demo" \
       --output="./prof_out" \
       --ai-core=on --task-time=on --aicpu=on \
       --aic-metrics=PipeUtilization \
       --analyze=on
```

本目录 `run.sh` 封装了上述流程,可直接 `bash run.sh` 复现(需在有 910B3 的环境)。

## 采集结果

`msprof --application` 在线采集成功,采集后自动完成 analyze/export,得到完整解析数据:

| 指标 | 数值 | 说明 |
|------|------|------|
| Task Type | **AI_CORE** | 算子完整下沉 AI Core,无 AI CPU 回退 |
| Block Dim | 2 | 双核执行 |
| Task Duration | **7.840 us** | 单算子总耗时 |
| cube_utilization | 9.29% | Cube(MAC)利用率 |
| aic_mac_ratio | 0.044 | MAC 计算占比 |
| aic_mte2_ratio | 0.330 | 搬入(GM→L1)占比,最大项 |
| aic_fixpipe_ratio | 0.274 | 搬出(L0C→GM)占比 |

### 性能分析结论

1. 算子全程在 AI Core 执行,无回退,符合预期。
2. 计算单元未打满(MAC 占比 4.4%、cube 利用率 9.29%):本样例 shape 很小,
   计算量不足以填满 Cube 流水。
3. **瓶颈在数据搬运**:MTE2 搬入 33% + Fixpipe 搬出 27% 合计约六成,典型的访存受限
   小算子特征。本样例为单次直调、无 double buffer,搬运与计算未 overlap。
4. 优化方向(真实大 shape 场景):增大 base 块提升单次 Mmad 计算量、引入 double buffer 让
   搬入与计算 overlap、多核切分匹配 K 维。本样例作教学用,未做这些优化,实测数据印证了
   "小 shape 下搬运主导"的结论。

完整指标与字段解读见 [`perf-data/20260624_matmul_basic_api_board/result_summary.md`](perf-data/20260624_matmul_basic_api_board/result_summary.md)。

## 问题与建议

1. 直接执行 `msprof ./demo` 报 `Argument --output=./ is writable by groups` 并退出。
   msprof 出于防提权拒绝 group 可写的输出目录,但报错未直接给出"请收紧目录权限或显式指定
   `--output`"的可操作提示,建议在报错中补充。
2. `--analyze` 在 `--application` 非空(在线采集)时无效,会打印
   `The argument --analyze is useless when --application is not empty` WARNING。
   建议文档明确:在线采集后自动 analyze,`--analyze` 仅用于离线 `--export` 流程,避免误用。

## 验收说明

- ✅ 成功使用 `msprof` 在 910B3 真实板卡采集到性能数据,数据完整。
- ✅ 解析后含 `op_summary` / `op_statistic` / `task_time` / `api_statistic` 四份 CSV 与 timeline trace。
- ✅ 算子精度校验通过(`test pass!`)。
- ✅ 已给出基于真实指标的性能分析结论与工具使用问题反馈。
