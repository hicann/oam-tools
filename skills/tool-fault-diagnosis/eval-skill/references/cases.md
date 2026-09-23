# 常见问题案例库

> 本文档收录 Ascend NPU / CANN 8.5.0 历史典型问题及其解决方案，用于日志分析时的快速案例匹配。
>
> **新增案例须经可信度评估**：只有可信度 HIGH（≥85）、关键项全部满足且修复已验证的诊断报告
> 才能写入本文档；可信度 70~84 或待补证的先进 [候选案例库](cases-pending.md)。
> 评分规范见 [confidence-assessment.md](confidence-assessment.md)，
> 入库门槛和格式见 [case-contribution.md](case-contribution.md)，
> 用 `scripts/promote_case.py` 自动生成规范案例块。

---

## CASE-001：训练过程中 loss 突变为 NaN

**问题描述**
使用 FP16 混合精度训练大模型，训练数百步后 loss 突然变为 NaN，此后无法恢复。

**关键日志特征**
```
[WARNING][GE] Op LayerNorm output contains inf/nan, step=342
[INFO][PROF] aicore_time=0.01ms, expected>=1ms  # 几乎为 0，表明算子短路
```

**根因分析**
FP16 动态范围有限（最大 65504），LayerNorm 层的中间激活值溢出后产生 inf，传播到后续算子导致 NaN。

**解决方案**
1. 开启损失缩放（Loss Scaling）：
   ```python
   # torch_npu + apex
   from apex import amp
   model, optimizer = amp.initialize(model, optimizer, opt_level="O1")
   ```
2. 对 LayerNorm 使用 FP32：
   ```python
   nn.LayerNorm(...).to(torch.float32)
   ```
3. 减小初始学习率，避免梯度爆炸。

---

## CASE-002：HCCL AllReduce 超时导致训练挂死

**问题描述**
8 卡训练，某步骤后所有进程卡住，120 秒后全部超时退出。

**关键日志特征**
```
[ERROR][HCCL] AllReduce timeout, rank=3, wait_time=120000ms
[ERROR][HCCL] Rank 5 not ready, hccl_error=timeout
[WARNING][HOST] rank 5 process memory: 95% used
```

**根因分析**
Rank 5 宿主机内存（CPU RAM）严重不足，数据预处理进程被 OOM Killer 杀死，导致该 rank 的梯度同步等待超时，阻塞了所有其他 rank。

**解决方案**
1. 增大宿主机内存或减少 `num_workers` 数量
2. 减小数据预取缓存大小
3. 启用 HCCL 超时诊断日志：
   ```bash
   export HCCL_EXEC_TIMEOUT=300  # 适当延长超时，便于诊断
   ```

---

## CASE-003：算子编译失败（UB 内存溢出）

**问题描述**
使用自定义算子时，TBE 编译阶段报错，任务无法启动。

**关键日志特征**
```
[ERROR][TBE] Compile op CustomConv failed: UB memory overflow
[ERROR][TBE] Required UB: 512KB, Available: 256KB, op=CustomConv, tiling_key=1024x1024
```

**根因分析**
自定义卷积算子的 tiling 分块为 1024×1024，超出 NPU 单核 UB 上限（256KB）。

**解决方案**
1. 减小 tiling 分块大小：
   ```python
   # tiling 配置，将 tile_size 从 1024 改为 256
   tiling_config = {"tile_h": 256, "tile_w": 256}
   ```
2. 使用 CANN 提供的 tiling 工具自动计算最优分块
3. 参考 TBE 开发文档中的 UB 约束说明

---

## CASE-004：图加载失败（HBM OOM）

**问题描述**
大模型推理时，图加载阶段失败，无法完成初始化。

**关键日志特征**
```
[ERROR][GE] Load graph to device failed: memory not enough
[ERROR][ACL] HBM memory allocation failed, requested=32GB, available=28GB
[INFO][MEM] Current HBM usage: 28576MB / 32768MB
```

**根因分析**
模型参数 + 激活内存 + KV cache 共计 > 32GB HBM 容量。

**解决方案**
1. 开启模型并行（张量并行 / 流水线并行）分散到多卡
2. 使用量化推理（INT8/INT4）减少模型内存占用：
   ```python
   # 使用 CANN 量化工具
   from ascendquant import quantize
   quantize(model, quant_config={"mode": "int8"})
   ```
3. 减小 KV cache 大小（缩短 max_seq_len）
4. 开启重计算（recompute）减少激活内存（训练场景）

---

## CASE-005：算子精度不达标（FP16 与 FP32 结果差异过大）

**问题描述**
使用 FP16 计算的矩阵乘法结果与 FP32 参考值相差超过 1%，不满足精度要求。

**关键日志特征**
```
[WARNING][PROF] Op MatMulV2 output max_diff=0.023, threshold=0.01
```

**根因分析**
矩阵规模较大时，FP16 累加误差会放大（mantissa 仅 10 bit）。

**解决方案**
1. 对精度敏感的矩阵乘法使用 FP32 累加：
   ```python
   # torch_npu 中开启高精度模式
   torch.npu.set_float32_matmul_precision("high")
   ```
2. 使用 BF16 替代 FP16（动态范围更大，精度损失更小）
3. 在精度测试时使用 `atol=1e-2, rtol=1e-2` 的合理误差范围

---

## CASE-006：plog 日志轮转导致日志丢失

**问题描述**
任务运行 4 小时后收集日志，发现早期的报错信息已被轮转覆盖。

**关键日志特征**
日志文件只有最近 10 × 100MB = 1GB 的内容，早期 ERROR 信息不存在。

**根因分析**
plog 默认保留 10 个文件，每个 100MB，长时间任务超出轮转上限。

**解决方案**
1. 任务启动后立即后台持续采集日志：
   ```bash
   # 实时同步日志到外部存储
   rsync -av --delete $HOME/ascend/log/plog/ /external/logs/plog/ &
   ```
2. 修改日志轮转配置（增大文件数）：
   ```json
   // /usr/local/Ascend/cann-8.5.0/tools/configure/acl.json
   { "log_file_size": 200, "log_file_num": 50 }
   ```
3. 仅保留 WARNING 以上级别以减少日志量：
   ```bash
   export ASCEND_GLOBAL_LOG_LEVEL=2
   ```
