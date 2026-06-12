# 昇腾 NPU 硬件规格参考

> **使用时机**：Phase 2 计算 MFU 时需要从本文件查取 Peak TFLOPS；计算通信带宽效率时参考各传输介质理论峰值。

---

## 一、昇腾 910B 系列算力规格

| 芯片型号 | BF16/FP16 峰值算力 (TFLOPs/s) | INT8 峰值算力 (TOPs/s) | HBM 带宽 | 片内 HCCS 带宽 |
|---|---|---|---|---|
| Ascend 910B1 | ~378.88 | ~757.76 | ~900 GB/s | ~400+ GB/s |
| Ascend 910B2 | ~353.89 | ~707.78 | ~900 GB/s | ~400+ GB/s |
| **Ascend 910B3** | **~294.91** | ~589.82 | ~800 GB/s | ~400+ GB/s |
| Ascend 910B4 | ~270.00 | ~540.00 | ~800 GB/s | ~392 GB/s |

**默认假设**：若 profiling 数据中未说明芯片型号，使用 **Ascend 910B3（294.91 TFLOPs/s BF16）** 作为 Peak，并在报告中明确标注"【默认 910B3，请确认实际芯片型号】"。

### 芯片型号检测方法（优先级从高到低）

1. **用户直接指定**：用户在问题中提及芯片型号
2. **profiler_metadata.json**：longcat 风格采集目录中的 `profiler_metadata.json` 或 `profiler_info_N.json` 可能包含设备信息
3. **kernel_details.csv 推断**：根据 `Block Dim` 最大值（910B3 通常为 64，910B4 通常为 32）推断
4. **默认值**：使用 910B3

---

## 二、AI Core 流水线单元说明（V2 Schema）

昇腾 AI Core 包含多个并行执行单元，`kernel_details.csv` V2 Schema 中的 `aic_*_ratio` 字段反映各单元在 kernel 执行期间的时间占比。

| 单元 | 字段 | 功能 | 瓶颈判断 |
|---|---|---|---|
| **MAC/Cube** | `aic_mac_ratio` | 矩阵乘法计算单元（执行 GEMM / Conv） | > 0.8 → Compute Bound |
| **MTE2** | `aic_mte2_ratio` | 数据读取引擎（L2/HBM → L1 Cache） | > 0.8 → Memory Bound（权重加载是瓶颈） |
| **MTE1** | `aic_mte1_ratio` | 数据搬移（L1 → L0，提供 MAC 单元操作数） | 高 → L1 至 L0 搬移是瓶颈 |
| **FixPipe** | `aic_fixpipe_ratio` | 后处理（量化、激活函数、格式转换） | > 0.3 → 后处理是瓶颈 |
| **Scalar** | `aic_scalar_ratio` | 标量运算（地址计算、控制流） | 高 → 标量操作过多，可能 shape 推断复杂 |

各比例之和约等于 1.0（允许小误差）。

### 典型 kernel 流水线模式

| 场景 | 典型比例模式 |
|---|---|
| GEMM（大 batch，高效执行） | aic_mac_ratio ≈ 0.7–0.85，aic_mte2_ratio ≈ 0.1–0.2 |
| GEMM（权重加载瓶颈） | aic_mac_ratio ≈ 0.3–0.4，aic_mte2_ratio ≈ 0.6–0.7 |
| RmsNorm / LayerNorm | aic_mac_ratio ≈ 0，aic_vec_ratio（AIV）≈ 0.6–0.8 |
| 小算子（Mul、Add、Cast） | 所有比例均低，Duration 极短，Wait 可能较高 |

---

## 三、AI Vector Core（AIV）流水线单元

| 单元 | 字段 | 功能 |
|---|---|---|
| **Vector** | `aiv_vec_ratio` | 向量计算（Element-wise 操作） |
| **MTE2** | `aiv_mte2_ratio` | GM → UB（全局内存到统一缓冲区）读取 |
| **MTE3** | `aiv_mte3_ratio` | UB → GM 写入 |
| **Scalar** | `aiv_scalar_ratio` | 标量控制流 |

---

## 四、HCCL 通信传输介质参数

| 介质 | 典型场景 | 理论峰值带宽 | 备注 |
|---|---|---|---|
| **HCCS** | 同机 NPU-NPU 互联 | ~400+ GB/s / 端口 | 昇腾高速片间总线，用于同节点 Tensor Parallelism |
| **RDMA** | 跨节点通信 | ~200–400 Gbps（取决于 IB/RoCE 配置） | 用于节点间 AllReduce / AllGather |
| **SDMA** | 同节点 DMA 传输 | ~数十 GB/s | 节点内辅助传输，带宽低于 HCCS |
| **PCIE** | Host-NPU 传输 | ~64 GB/s（PCIe Gen4 ×16） | 用于 Host-Device 数据迁移 |
| **SIO** | 信号 I/O | 取决于配置 | 辅助通道 |

### 通信带宽健康判断

| 介质 | 实测带宽 | 判断 |
|---|---|---|
| RDMA | > 1.5 GB/s | 正常 |
| RDMA | 0.5–1.5 GB/s | 警告（小包问题或网络拥塞） |
| RDMA | < 0.5 GB/s | 严重（严重小包或链路故障） |
| HCCS | 接近峰值 400 GB/s | 正常 |
| HCCS | < 50 GB/s | 警告（数据量过小或配置问题） |

---

## 五、常见模型 MFU 参考值

| 场景 | 典型 MFU 范围 | 说明 |
|---|---|---|
| 大规模预训练（大 batch，大矩阵） | 40%–65% | AI Core Cube 充分饱和 |
| SFT 微调（中等 batch） | 25%–45% | 稍有碎片，仍较高效 |
| 推理 Prefill（长 prompt） | 20%–50% | 取决于 batch size 和 seq len |
| 推理 Decode（batch=1，单 token） | < 5% | 正常，矩阵 M=1 无法充分利用 Cube |
| 推理 Decode（大 batch，连续 batching） | 15%–40% | batch 越大，MFU 越高 |

> **低 MFU 不等于有问题**：需结合场景和 batch size 综合判断。
