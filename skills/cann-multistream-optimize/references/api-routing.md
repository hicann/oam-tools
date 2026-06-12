# 多流与控核 API 路由

本文件用于把“执行模式 / 问题类型”映射到推荐 API。官方文档版本以 [`official-docs-latest.md`](./official-docs-latest.md) 为准。

## 先判执行模式

| 当前场景 | 推荐 API 风格 | 首选 API | 官方文档入口 |
| --- | --- | --- | --- |
| eager / patch 改造 | 显式流对象 | `torch.npu.Stream()`、`record_event()`、`wait_event()`、`wait_stream()` | 优先参考仓库案例；图内表达总说明见[图内多流表达功能（Ascend IR）](https://www.hiascend.com/document/detail/zh/Pytorch/730/modthirdparty/torchairuseguide/torchair_00033.html) |
| `ge_graph` / TorchAir 图内多流 | TorchAir scope / tagged event | `npu_stream_switch`、`npu_wait_tensor`、`npu_record_tagged_stream`、`npu_tagged_event_wait` | [npu_stream_switch](https://www.hiascend.com/document/detail/zh/Pytorch/720/modthirdparty/torchairuseguide/torchair_00101.html), [npu_wait_tensor](https://www.hiascend.com/document/detail/zh/Pytorch/730/modthirdparty/torchairuseguide/torchair_00114.html), [npu_record_tagged_stream](https://www.hiascend.com/document/detail/zh/Pytorch/720/modthirdparty/torchairuseguide/torchair_00099.html), [npu_tagged_event_wait](https://www.hiascend.com/document/detail/zh/Pytorch/730/modthirdparty/torchairuseguide/torchair_00108.html) |
| `aclgraph` / 图模式入口判断 | 图模式总说明 | 先看图模式入口和多流总说明，再选具体 API | [PyTorch 图模式使用（TorchAir）入口](https://www.hiascend.com/document/detail/zh/Pytorch/730/index/index.html), [图内多流表达功能（aclgraph）](https://www.hiascend.com/document/detail/zh/Pytorch/730/modthirdparty/torchairuseguide/torchair_00024.html) |

## 再判问题类型

| 问题类型 | 推荐 API | 什么时候用 | 注意事项 | 官方文档入口 |
| --- | --- | --- | --- | --- |
| 需要把一段计算切到副流 | `torch.npu.Stream()` 或 `npu_stream_switch` | 已确认两段路径没有直接 `data` 依赖，只在后面汇合 | 先明确汇合点，再决定是否要 event 或 wait | [npu_stream_switch](https://www.hiascend.com/document/detail/zh/Pytorch/720/modthirdparty/torchairuseguide/torchair_00101.html) |
| 需要显式记录和等待事件 | `record_event()` / `wait_event()`；或 `npu_record_tagged_stream` / `npu_tagged_event_wait` | 两条流之间存在控制依赖，但后继不直接吃前驱输出 tensor | 图模式里优先用 tagged event 风格；eager/patch 里优先用 stream event | [npu_record_tagged_stream](https://www.hiascend.com/document/detail/zh/Pytorch/720/modthirdparty/torchairuseguide/torchair_00099.html), [npu_tagged_event_wait](https://www.hiascend.com/document/detail/zh/Pytorch/730/modthirdparty/torchairuseguide/torchair_00108.html) |
| 图内表达 tensor 等待关系 | `npu_wait_tensor` | 需要把依赖表达在图内，而不是只在 Python 侧做 wait | 优先用于 TorchAir 图模式，不要硬套到显式 stream 风格 | [npu_wait_tensor](https://www.hiascend.com/document/detail/zh/Pytorch/730/modthirdparty/torchairuseguide/torchair_00114.html) |
| overlap 已成立但一条流明显拖尾 | `limit_core_num` | 已经看到两条流资源争抢，或一条流长期占满 Core | 先确认拖尾来自资源争抢，而不是依赖或 shape 问题 | [limit_core_num](https://www.hiascend.com/document/detail/zh/Pytorch/710/modthirdparty/torchairuseguide/torchair_00091.html) |
| 需要进一步查看或设置 stream 资源限制 | `torch_npu.get_stream_limit` / `torch_npu.set_stream_limit` | 已进入控核或 stream 资源调优阶段 | 这不是第一手多流 API，通常在资源调优阶段再用 | [torch_npu.get_stream_limit](https://www.hiascend.com/document/detail/zh/Pytorch/720/apiref/torchnpuCustomsapi/context/torch_npu-get_stream_limit.md), [torch_npu.set_stream_limit](https://www.hiascend.com/document/detail/zh/Pytorch/730/apiref/torchnpuCustomsapi/docs/context/torch_npu-set_stream_limit.md) |
| 需要扩大计算窗口，掩盖权重搬运 | `torch_npu.npu_prefetch` | overlap 正确，但仍有访存或带宽空洞可被前序轻算子掩盖 | 只在前序算子不明显抢带宽时使用；常和多流 + 控核联动 | [torch_npu.npu_prefetch](https://www.hiascend.com/document/detail/zh/Pytorch/700/apiref/apilist/ptaoplist_000530.html) |

## 推荐决策顺序

1. 先确定当前是 eager / patch 还是 graph / TorchAir。
2. 先选一套主 API 路径，不要混着写。
3. 先把依赖和同步做对，再确认是否真的有 overlap。
4. 只有在 overlap 正确但拖尾明显时，才进入控核、stream limit、预取调优。

## 常见误区

- 不要在 eager 路径里照搬 TorchAir 的 tagged event 风格。
- 不要把 `limit_core_num` 当成默认步骤；它只解决资源分配问题，不解决依赖错误。
- 不要用 `npu_prefetch` 掩盖一个本来就不该并行的链路；先证明链路没有错误依赖。
- `npu_tagged_event_record` 的独立官方页面不稳定时，优先看总说明页和仓库案例代码，不要自己猜语义。
