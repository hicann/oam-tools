# app —— AI Core Error 故障注入算子

> **本环境运行状态：✅ 已实跑。** 在 910B3（容器逻辑 device 0）上编译运行，稳定触发
> `aivec error 0x800000 / MTE DDR address out of range`，`aclrtSynchronizeStream` 返回 507035。
> 这是给 `asys launch` 复跑、`asys analyze -r=aicore_error` 解析准备的**业务负载**。

## 这是什么

一个**故意制造越界访存**的 AscendC 算子。正常的 element-wise Add（参考
msprof demo 的 `02_api_AscendC` 样例）每个核处理
`BLOCK_LENGTH` 个 fp16 元素；这里在写回阶段把输出 GlobalTensor 的起始地址人为
推到 `OOB_OFFSET = 1<<20` 个元素之外，`DataCopy` 写一个远超分配范围的 GM 地址，
AI Core 执行该 MTE 搬运指令时报异常。

> ⚠️ 这是**故障注入用途**，不是正常算子。它存在的唯一目的就是在 NPU 上稳定跑出一个
> AI Core Error，供故障定位流程演示。请勿当作算子写法参考。

## 文件

| 文件 | 作用 |
|---|---|
| `src/dirty_kernel.cpp` | device 侧 AscendC kernel，`Init()` 给 zGm 加 `OOB_OFFSET` 越界偏移，`CopyOut()` 写回时触发异常 |
| `src/main.cpp` | host 侧：分配显存、`ACLRT_LAUNCH_KERNEL` 拉起 kernel、`aclrtSynchronizeStream` 捕获错误码 |
| `src/CMakeLists.txt` | 用官方 `ascendc_library` 编译，自动生成 `aclrtlaunch_dirty_custom.h` |
| `build.sh` | 一键 cmake 编译 → `build_run/dirty_op` |

## 跑

```bash
bash build.sh          # 编译，产出 build_run/dirty_op
./build_run/dirty_op   # 裸跑（容器内默认落到逻辑 device 0）
```

裸跑预期输出：
```
[dirty] launching fault-injection kernel (OOB GM write)...
[dirty] aclrtSynchronizeStream FAILED -> 507035 (AI Core Error expected)
[dirty] done (ret=507035)
```

> ⚠️ **不要直接裸跑做收集**：裸跑没设 `NPU_COLLECT_PATH`，异常 dump 开关未打开
> （plog 会打印 `No Env enable exception dump`），且越界写可能波及 host 内存触发
> `double free`。正确姿势是用 `asys launch`（见上层 [launch_rerun.sh](../launch_rerun.sh)），
> 它会自动设置 `NPU_COLLECT_PATH` 等环境变量开启异常 dump 并同步收集。

## 故障注入点（dirty_kernel.cpp）

```cpp
constexpr int64_t OOB_OFFSET = 1 << 20;   // 远超 z 实际分配长度

void Init(GM_ADDR x, GM_ADDR y, GM_ADDR z) {
    ...
    // ★ z 的 GlobalBuffer 起始地址人为加上 OOB_OFFSET，使后续写回越界
    zGm.SetGlobalBuffer((__gm__ half *)z + OOB_OFFSET + BLOCK_LENGTH * GetBlockIdx(), BLOCK_LENGTH);
}

void CopyOut(int32_t progress) {
    ...
    DataCopy(zGm[progress * TILE_LENGTH], zLocal, TILE_LENGTH);  // ★ 写越界地址 → AI Core Error
}
```

实测在 plog 中产生（每个 AI Core 一条）：
```
there is an exception of aivec error, core id is <N>, error code = 0x800000 ...
errorStr: The DDR address of the MTE instruction is out of range.
```

## 如何换成你自己的故障场景

这套工程只是「在 NPU 上造一个可被 asys 捕获的 AI Core Error」的最小载体。真实使用时
通常**不需要**故障注入——你把 `asys launch --task` 后面换成你自己**会偶发报错的业务命令**
即可。本算子仅用于在没有现成故障业务时，稳定复现一个 AI Core Error 供流程演练。
