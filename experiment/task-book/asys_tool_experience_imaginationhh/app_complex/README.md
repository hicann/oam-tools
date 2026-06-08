# app_complex —— 复杂 AI Core Error 故障注入算子

> **本环境运行状态：✅ 已实跑。** 910B3 / 容器逻辑 device 0。
> `aclrtSynchronizeStream FAILED -> 507035`，plog 精确报出 `gather_bad_custom_1` + 后半 4 核报错。
> 这是案例2，相对 [app/README.md](../app/README.md) 的简单故障，专门用来检验 asys 的**定位精度**。

## 这是什么

一个**两算子流水**的故障注入程序，刻意设计三个提升定位难度的特征：

| 特征 | 设计 | 模拟的真实 bug |
|---|---|---|
| 多算子流水 | `add_ok_custom`（正常）→ `gather_bad_custom`（失败），同 stream 顺序下发 | 一个 step 多算子，需定位是**哪个** |
| 部分核失败 | 仅 `blockIdx >= 4` 的后半 4 核注入越界 | 数据相关故障，只在部分核触发 |
| 读越界 | gather 读基址按 `blockIdx` 运行时偏移到分配区外 | gather/embedding 索引溢出，比写越界隐蔽 |

> ⚠️ 故障注入用途，非正常算子写法参考。

## 文件

| 文件 | 作用 |
|---|---|
| `src/complex_kernel.cpp` | 两个 kernel：`KernelAddOk`（正常 Add）+ `KernelGatherBad`（后半核读越界） |
| `src/main.cpp` | 顺序下发两算子，`aclrtSynchronizeStream` 捕获错误码 |
| `src/CMakeLists.txt` | `ascendc_library` 编译，生成两个 `aclrtlaunch_*.h` |
| `build.sh` | 一键编译 → `build_run/complex_op` |

## 跑

```bash
bash build.sh            # → build_run/complex_op
./build_run/complex_op   # 容器内默认落逻辑 device 0
```

预期：
```
[complex] step1: launch add_ok_custom (expect success)...
[complex] step2: launch gather_bad_custom (blockIdx>=4 OOB read, expect fail)...
[complex] aclrtSynchronizeStream FAILED -> 507035 (AI Core Error in gather expected)
```

## 故障注入点（complex_kernel.cpp）

```cpp
constexpr int32_t HALF_CORE = USE_CORE_NUM / 2;   // 前 4 核正常，后 4 核故障
constexpr int64_t OOB_STRIDE = 1 << 18;

void KernelGatherBad::Init(GM_ADDR src, GM_ADDR dst) {
    int64_t base = BLOCK_LENGTH * GetBlockIdx();
    if (GetBlockIdx() >= HALF_CORE) {
        base += OOB_STRIDE * GetBlockIdx();   // ★ 后半核读越界，模拟索引溢出
    }
    srcGm.SetGlobalBuffer((__gm__ half *)src + base, BLOCK_LENGTH);
    ...
}
// Process() 里 DataCopy(sL, srcGm[...], ...) 在后半核读非法地址 → AI Core Error
```

实测 plog：`aivec error, core id is <N> ... MTE instruction is out of range`（仅后半 4 核），
`fault kernel_name=gather_bad_custom_1`。analyze 对此的实测表现见
[顶层 README 第 4 节](../README.md) 与 [feedback.md 第 7 节](../feedback.md)。
