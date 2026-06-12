# 多流与控核官方文档索引（最新可检索版本）

本文整理当前官方站点中与多流、控核以及本仓库案例中实际使用到的相关 API 对应的**最新可检索版本**文档。

说明：

- 这里的“最新”指当前官方站点可稳定检索到的最新页面版本。
- 不同 API 的最新页面版本不完全一致，不能强行统一到同一个版本号。
- 如果某个 API 没有检索到更高版本的独立页面，就保留当前能确认的最新官方页面。

## 1. 总说明文档

### 多流总说明

- [图内多流表达功能（Ascend IR）- 7.3.0](https://www.hiascend.com/document/detail/zh/Pytorch/730/modthirdparty/torchairuseguide/torchair_00033.html)
- [图内多流表达功能（aclgraph）- 7.3.0](https://www.hiascend.com/document/detail/zh/Pytorch/730/modthirdparty/torchairuseguide/torchair_00024.html)

### 图模式入口

- [PyTorch 图模式使用（TorchAir）入口 - 7.3.0](https://www.hiascend.com/document/detail/zh/Pytorch/730/index/index.html)

## 2. 多流相关 API

### TorchAir scope / ops

- `torchair.scope.npu_stream_switch`
  - [npu_stream_switch - 7.2.0](https://www.hiascend.com/document/detail/zh/Pytorch/720/modthirdparty/torchairuseguide/torchair_00101.html)

- `torchair.scope.npu_wait_tensor`
  - [npu_wait_tensor - 7.3.0](https://www.hiascend.com/document/detail/zh/Pytorch/730/modthirdparty/torchairuseguide/torchair_00114.html)

- `torchair.ops.npu_record_tagged_stream`
  - [npu_record_tagged_stream - 7.2.0](https://www.hiascend.com/document/detail/zh/Pytorch/720/modthirdparty/torchairuseguide/torchair_00099.html)

- `torchair.ops.npu_tagged_event_wait`
  - [npu_tagged_event_wait - 7.3.0](https://www.hiascend.com/document/detail/zh/Pytorch/730/modthirdparty/torchairuseguide/torchair_00108.html)

- `torchair.ops.wait`
  - [wait - 7.3.0](https://www.hiascend.com/document/detail/zh/Pytorch/730/modthirdparty/torchairuseguide/torchair_00111.html)

### 说明

- `npu_tagged_event_record` 这次整理中没有稳定检索到比总说明页更适合直接引用的更高版本独立页面。
- 如果后续仓库文档要引用该能力，建议优先引用“图内多流表达功能”总说明，再辅以本仓库案例代码。

## 3. 控核相关 API

### TorchAir 控核接口

- `torchair.scope.limit_core_num`
  - [limit_core_num - 7.1.0](https://www.hiascend.com/document/detail/zh/Pytorch/710/modthirdparty/torchairuseguide/torchair_00091.html)

### torch_npu stream 资源限制接口

- `torch_npu.set_stream_limit`
  - [torch_npu.set_stream_limit - 7.3.0](https://www.hiascend.com/document/detail/zh/Pytorch/730/apiref/torchnpuCustomsapi/docs/context/torch_npu-set_stream_limit.md)

- `torch_npu.get_stream_limit`
  - [torch_npu.get_stream_limit - 7.2.0](https://www.hiascend.com/document/detail/zh/Pytorch/720/apiref/torchnpuCustomsapi/context/torch_npu-get_stream_limit.md)

## 4. 与案例联动的补充 API

### 预取

- `torch_npu.npu_prefetch`
  - [torch_npu.npu_prefetch - 7.0.0](https://www.hiascend.com/document/detail/zh/Pytorch/700/apiref/apilist/ptaoplist_000530.html)

说明：

- `npu_prefetch` 不是多流 API，但在 `LongCat-Flash` 的“多流 + 控核 + 预取”联动里是关键补充能力。

## 5. 与仓库案例的对应关系

### DeepSeek-V3.2-Exp / DeepSeek-R1 / Kimi-K2 / GLM-5

重点参考：

- [图内多流表达功能（Ascend IR）- 7.3.0](https://www.hiascend.com/document/detail/zh/Pytorch/730/modthirdparty/torchairuseguide/torchair_00033.html)
- [npu_stream_switch - 7.2.0](https://www.hiascend.com/document/detail/zh/Pytorch/720/modthirdparty/torchairuseguide/torchair_00101.html)
- [npu_wait_tensor - 7.3.0](https://www.hiascend.com/document/detail/zh/Pytorch/730/modthirdparty/torchairuseguide/torchair_00114.html)
- [npu_record_tagged_stream - 7.2.0](https://www.hiascend.com/document/detail/zh/Pytorch/720/modthirdparty/torchairuseguide/torchair_00099.html)
- [npu_tagged_event_wait - 7.3.0](https://www.hiascend.com/document/detail/zh/Pytorch/730/modthirdparty/torchairuseguide/torchair_00108.html)

### LongCat-Flash

重点参考：

- [图内多流表达功能（Ascend IR）- 7.3.0](https://www.hiascend.com/document/detail/zh/Pytorch/730/modthirdparty/torchairuseguide/torchair_00033.html)
- [limit_core_num - 7.1.0](https://www.hiascend.com/document/detail/zh/Pytorch/710/modthirdparty/torchairuseguide/torchair_00091.html)
- [torch_npu.set_stream_limit - 7.3.0](https://www.hiascend.com/document/detail/zh/Pytorch/730/apiref/torchnpuCustomsapi/docs/context/torch_npu-set_stream_limit.md)
- [torch_npu.get_stream_limit - 7.2.0](https://www.hiascend.com/document/detail/zh/Pytorch/720/apiref/torchnpuCustomsapi/context/torch_npu-get_stream_limit.md)
- [torch_npu.npu_prefetch - 7.0.0](https://www.hiascend.com/document/detail/zh/Pytorch/700/apiref/apilist/ptaoplist_000530.html)

### Prefill Micro-Batch 双流流水

重点参考：

- [图内多流表达功能（Ascend IR）- 7.3.0](https://www.hiascend.com/document/detail/zh/Pytorch/730/modthirdparty/torchairuseguide/torchair_00033.html)
- [图内多流表达功能（aclgraph）- 7.3.0](https://www.hiascend.com/document/detail/zh/Pytorch/730/modthirdparty/torchairuseguide/torchair_00024.html)

## 6. 版本结论

当前这批能力里，能确认到的最新可检索版本大致如下：

- 优先使用 `7.3.0`
  - 图内多流表达功能
  - aclgraph 多流表达功能
  - `npu_wait_tensor`
  - `npu_tagged_event_wait`
  - `torch_npu.set_stream_limit`
  - TorchAir 图模式总入口

- 当前检索到的最新页面不是 `7.3.0`
  - `npu_stream_switch`：7.2.0
  - `npu_record_tagged_stream`：7.2.0
  - `torch_npu.get_stream_limit`：7.2.0
  - `limit_core_num`：7.1.0
  - `torch_npu.npu_prefetch`：7.0.0

因此，在仓库文档中应采用“**每个接口分别取最新页面**”的策略，而不是统一写成同一个版本号。
