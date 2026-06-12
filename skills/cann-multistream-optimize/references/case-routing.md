# 多流案例路由

本文件按**优化模式**路由仓库内多流案例。

> 下表"参考源码"列为 `cann-recipes-infer` 模型仓中的代表实现路径（相对本仓库为外部路径，
> 仅作定位参考，不作为可点击链接）。

## 快速选型表

| 优化模式 | 参考源码 | 什么时候优先选 | 典型风险 |
| --- | --- | --- | --- |
| MoE shared expert 双流 | `models/deepseek-v3.2-exp/models/modeling_deepseek.py`、`models/glm-5/models/modeling_glm.py` | 路由专家和共享专家结果在后面汇合，且 decode shape 稳定 | 同步点放错会导致 merge 读到未完成结果；共享专家过重时 overlap 不一定有收益 |
| Indexer / Prolog 多流 | `models/glm-5/models/indexer.py` | Attention 前处理链路可拆成两段或多段，等待在后面汇合 | 这类优化常常是前处理子链 overlap，不是完整大模块并行，边界容易拆错 |
| KVCache offload 异步流 | `models/deepseek-v3.2-exp/models/offload_cache.py`、`models/glm-5/models/offload_cache.py` | 设备内存紧张，需要把搬运从主计算流剥离 | 主流和搬运流的状态一致性最重要；异步搬运可能掩盖不了 H2D/D2H 带宽瓶颈 |
| Prefill micro-batch 双流 + event | `models/deepseek-r1/models/modeling_deepseek.py` | prefill 同时有明显计算和通信，且切 micro-batch 后 shape 线性度还可以 | 最容易引入 host bound、shape 劣化和事件编排错误 |
| 多流 + 控核 | `models/longcat-flash/models/modeling_longcat_flash.py` | 已有 overlap，但一条流明显拖尾或资源被另一条流吃满 | 控核值不是通用常量；多流、控核、预取和图模式往往是耦合设计 |
| AFD 通信/计算 overlap | 以分离式部署链路为主 | 分离式部署或通信链路成了主要瓶颈 | 重点不在本地双算子并行，而在通信和本地计算 overlap；等待链容易拖尾 |
| Patch 形态多流 | `models/qwen3-next/patches/stage1/0003-feat-moe-multi-stream.patch` | 优化不能直接落到模型仓，需要嵌进 runtime 或 patch | patch 代码更依赖现有生命周期，`wait_stream()` 顺序错了会直接破坏运行时逻辑 |
| 多模态变体 | `models/hunyuan-image-3.0/adaptor_patches/hunyuan.py` | 共享流在模块初始化阶段就作为能力注入，而不是在前向里临时加 scope | 多流能力进入模块构造期后，不能只复制一段前向代码；初始化和分布式上下文要一起看 |

## 使用顺序

1. 先确定当前优化属于哪一类模式。
2. 读对应代表代码或补丁，确认模块边界、依赖关系、实际 API 风格和 enable 开关设计。
3. 如果一个实现同时落在多类模式里，先选主模式，再把其他能力当补充手段。

## 常见误用

- 不要把 `MoE shared expert 双流` 和 `Prefill micro-batch 双流` 当成同一种流水，它们的同步粒度完全不同。
- 不要看到有两条流就默认需要 `limit_core_num`，控核只在资源争抢和拖尾明显时再引入。
- 不要把 `KVCache offload` 这类搬运流当成计算流优化，它优先关注的是状态一致性和带宽掩盖。
- 不要直接拼接多个案例的代码片段，必须先按当前执行模式选一套主路径。
