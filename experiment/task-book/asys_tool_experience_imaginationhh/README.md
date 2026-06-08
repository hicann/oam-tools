# asys 故障定位工具实操 Demo

这是一套 **asys 故障定位上手示例**：覆盖任务书要求的三条典型流程，每条都**已实跑可复现**，
并保留真实采集/解析产物。负载用一个**故障注入算子**（故意越界访存触发 AI Core Error），
把「业务复跑 → 故障收集 → AI Core Error 解析」串成一条完整链路。

> **本环境运行状态：✅ 三流程全部实跑通过。** 910B3（容器内逻辑 device 0），CANN 9.1.0。
> 真实触发 `aivec error 0x800000 / MTE DDR address out of range`，asys 完成收集与解析。

> **关于产物数据**：三流程均已在本环境真实跑通，下文的报错行、`info.txt` 节选等均为**实跑结果原文**。
> 参照 msprof demo 对 `perf_data_demo` 的处理，**原始采集日志/Dump 体积大且含环境相关的历史进程信息，未随 PR 入库**；
> `fault-data/` 仅保留目录骨架，全部产物可由仓库脚本一键复现（见末尾「复现步骤」）。文中出现的
> `asys_output_<具体时间戳>` 为本次实跑时的目录名，仅作示例引用。

---

## 1. 目录结构说明

```
asys_tool_experience_imaginationhh/
├── README.md                  # 本文件：目录说明 + 输入输出 + 任务达成情况
├── app/                       # 案例1 业务负载：简单 AI Core Error 故障注入算子
│   ├── src/dirty_kernel.cpp   #   device 侧 AscendC kernel（固定越界 GM 写，全核失败）
│   ├── src/main.cpp           #   host 侧拉起 + 捕获错误码
│   ├── src/CMakeLists.txt     #   ascendc_library 编译配置
│   ├── build.sh               #   一键编译 → build_run/dirty_op
│   └── README.md              #   算子说明与故障注入原理
├── app_complex/               # 案例2 业务负载：复杂故障算子（多算子流水 + 部分核 + 读越界）
│   ├── src/complex_kernel.cpp #   两个 kernel：add_ok（正常）+ gather_bad（后半核读越界）
│   ├── src/main.cpp           #   顺序下发两算子，捕获错误码
│   ├── src/CMakeLists.txt     #   编译 → build_run/complex_op
│   └── build.sh
├── collect.sh                 # 流程1：无需复跑，收集环境已有故障信息
├── launch_rerun.sh            # 流程2：业务复跑 + 故障信息同步收集
├── analyze_aicore_error.sh    # 流程3：AI Core Error 解析
├── fault-data/                # 案例1 产物目录骨架（collect/launch/analyze；原始数据未入库，可脚本复现）
│   ├── collect/               #   asys collect 输出（无复跑场景）
│   ├── launch/                #   asys launch 输出（复跑 + 收集，含真实故障现场）
│   └── analyze/               #   asys analyze 输出（info.txt）
├── fault-data-complex/        # 案例2 产物目录（复杂故障 launch + analyze；同样未附原始数据）
│   ├── launch/                #   复跑 complex_op，抓到 gather_bad + 后半核故障现场
│   └── analyze/               #   analyze 输出（info.txt）
└── feedback.md                # 体验反馈：问题 / 兼容性 / 优化建议
```

## 2. 输入输出说明

### 输入

| 项 | 值 |
|---|---|
| 硬件环境 | Atlas 910B3，容器内 runtime 仅可见 1 张卡（**逻辑 device 0**，物理卡经容器重映射） |
| CANN 版本 | CANN 9.1.0（安装目录记为 `${install_path}`，如 `/usr/local/Ascend/ascend-toolkit`） |
| asys 入口 | `${install_path}/.../tools/ascend_system_advisor/asys/asys`（或配置环境变量后直接 `asys`） |
| 业务脚本 | `app/build_run/dirty_op`（AscendC 故障注入算子，见 [app/README.md](app/README.md)） |
| 复跑命令 | `asys launch --task <repo>/app/build_run/dirty_op --output <repo>/fault-data/launch` |
| 故障触发方式 | kernel 在 `CopyOut` 把输出 GlobalTensor 起始地址 `+OOB_OFFSET(1<<20)` 越界写 GM，AI Core 报 `error code=0x800000`（MTE 地址越界） |

### 输出

| 产物 | 路径 | 说明 |
|---|---|---|
| collect 收集目录 | `fault-data/collect/asys_output_<ts>/` | 无复跑场景采集的运维信息 |
| launch 收集目录 | `fault-data/launch/asys_output_<ts>/` | 复跑业务 + 故障现场 |
| Host CANN 日志 | `dfx/log/host/cann/{debug,run}/plog/` | plog（debug/run 两级），含 AI Core Error 报错行 |
| Device 日志 | `dfx/log/host/cann/{debug,run}/device-0/` | device 侧运行日志 |
| 业务现场 | `dfx/log/host/screen.txt`、`user_cmd` | launch 复跑业务的屏显输出与原始命令（**可复现**） |
| 异常 Dump 目录 | `dfx/data-dump/` | AI Core Error 相关 Dump（launch 模式开启 exception dump 后落盘） |
| atrace/stackcore | `dfx/atrace/` | 进程调度 trace 与堆栈快照 |
| 辅助信息 | `hardware_info.txt` / `software_info.txt` / `status_info.txt` / `health_result.txt` | 硬件 / 软件 / 设备状态 / 健康检查 |
| 解析结果 | `fault-data/analyze/info_<ts>/.../info.txt` | analyze 的根因定位提示（详见第 3 节） |

## 3. 任务达成情况

### 3.1 `asys collect` —— 无需复跑的故障信息收集 ✅

```bash
bash collect.sh        # 内部：asys collect --output fault-data/collect
```

不拉起任何业务，直接扫描环境已有的运维/故障信息。实跑产出
`fault-data/collect/asys_output_<时间戳>/`，关键产物：

- `dfx/log/host/cann/run/plog/`、`debug/plog/`：Host 侧 CANN 运行日志
- `dfx/log/host/cann/run/device-0/`：device 日志
- `dfx/atrace/`：进程调度 trace + stackcore（含此前裸跑 dirty_op 的堆栈快照）
- `hardware_info.txt` / `software_info.txt` / `status_info.txt` / `health_result.txt`：软硬件 + 设备状态 + 健康检查

> 适用：现场已经出过故障、进程已退出，想**快速打包现有信息**给技术支持。
> 局限：只收"已经留下的"，若故障时没开异常 dump，这里也补不出 dump。

### 3.2 `asys launch` —— 业务复跑 + 故障信息收集 ✅

```bash
bash launch_rerun.sh   # 内部：asys launch --task <repo>/app/build_run/dirty_op --output fault-data/launch
```

asys 作为父进程设置 `NPU_COLLECT_PATH` / `ASCEND_GLOBAL_LOG_LEVEL` 等环境变量后拉起业务，
业务结束（无论成败）自动 collect。实跑产出 `fault-data/launch/asys_output_<时间戳>/`：

- `dfx/log/host/screen.txt` 捕获到业务真实报错：
  ```
  [dirty] aclrtSynchronizeStream FAILED -> 507035 (AI Core Error expected)
  ```
- `dfx/log/host/cann/debug/plog/` 捕获到 AI Core Error 现场（每核一条）：
  ```
  there is an exception of aivec error, core id is <N>, error code = 0x800000 ...
  errorStr: The DDR address of the MTE instruction is out of range.
  ```
- `dfx/data-dump/` 目录建立（launch 模式开启 exception dump，区别于无复跑 collect）
- `dfx/log/host/user_cmd` 保留**可复现业务命令**

> 关键差异：launch 比 collect 多了「复跑时主动开启异常 dump」，所以能拿到 collect 拿不到的
> 故障现场。这是定位**可复现故障**的首选。

### 3.3 `asys analyze -r=aicore_error` —— AI Core Error 解析 ✅

```bash
bash analyze_aicore_error.sh <已收集故障目录>   # 内部：asys analyze -r=aicore_error -d 0 --path <dir> --output fault-data/analyze
```

asys analyze 内部调用 msaicerr，对每个 AICERROR 写一份 `info.txt`。本 demo 保留**两份互补**结果：

**(A) 真实触发版** `fault-data/analyze/info_<时间戳>/aicerror/info.txt`
解析上一步 launch 真实抓到的故障目录。msaicerr 走到 Collection 阶段后给出明确诊断：
```
Adump log '[Dump][Exception]' cannot be found in <launch输出>.
Check whether open exception dump.
```
即：plog 里有 AI Core Error 报错，但容器内异常 dump 文件未完整落盘（见 feedback 兼容性记录）。
**这本身就是一次有效的解析——info.txt 准确告诉你"现场不完整、下一步去检查 dump 开关"。**

**(B) 完整样例版** `fault-data/analyze/info_<时间戳>/aicerror_<n>/info.txt`
为展示 analyze 的**完整解析能力**，对一份含完整 dump 的故障样例
（仓库内 msaicerr 测试用例自带的 AI Core Error 收集样例 `test/ut/msaicerr/res/ori_data/<样例目录>`）再跑一次，走完全部 11 步，
`info.txt` 给出 6 大块根因定位：

| info.txt 区块 | 内容（实跑节选，标识已脱敏） |
|---|---|
| 1. Basic information | kernel=`<某融合算子>`，task_id/stream_id/core_id、rts_block_dim 等定位字段 |
| 2. AI Core DFX Register | `AIC_ERROR (0,0,0)`，trap 指令/超时 |
| 3. Operator Error Line | start pc / current pc（出错指令地址） |
| 4. Operator I/O Memory | args before/after 执行的输入输出地址列表 |
| 5. Dump File Parsing | 解析 `exception_info.*` dump |
| 6. Single-Operator Test | 单算子复测结果 |

同时产出 `README.txt`（AICERROR 概要：device/core/task/kernel）与 `debug_info.txt`（日志打印信息）。

> 解读顺序：先看 `README.txt` 概要 → 进 `aicerror_*/info.txt` 看「Basic information」定位是哪个
> kernel/哪条 pc 出错 → 看「Operator I/O Memory」对照输入地址是否非法 → 必要时看 dump 解析。

### 3.4 两条收集路径体验对比

| 维度 | `asys collect`（不复跑） | `asys launch`（复跑+收集） |
|---|---|---|
| 是否需要复跑业务 | 否，秒级打包现有信息 | 是，重新拉起业务命令 |
| 异常 dump | 取决于故障当时是否已开 | **主动开启**（设 NPU_COLLECT_PATH），现场更全 |
| 适用场景 | 故障已发生、进程已退出、抢救现场 | 故障可稳定/偶发复现，要抓完整现场 |
| 对业务侵入 | 零侵入 | 需把业务命令交给 `--task` 拉起 |
| 本 demo 实测 | 256K，结构齐全但无 data-dump | 420K，含 data-dump + screen.txt 业务报错 |

**结论**：先 `launch` 复现拿全现场，再 `analyze` 解析；只有在无法复现（必须保留第一现场）时才用 `collect`。

### 3.5 问题反馈、兼容性记录与优化建议

详见 [feedback.md](feedback.md)，覆盖：业务复跑命令配置、故障信息完整性、输出目录命名、
解析结果可定位性、报错提示指导性、容器/权限/环境变量兼容性等。其中最关键的一条：
**容器内 runtime 仅可见逻辑 device 0，误设 `ASCEND_RT_VISIBLE_DEVICES=7` 会导致 kernel 不下发、采不到故障**。

---

## 4. 复杂故障对照案例（app_complex / fault-data-complex）

案例1（`app/dirty_op`）的故障很"干净"——单算子、固定偏移、写越界、全核同时失败。为了更接近真实
训练故障、并真正检验 asys 的**定位精度**，案例2 设计了一个明显更难的故障：

### 4.1 故障设计（三个提升定位难度的特征）

| 特征 | 设计 | 模拟的真实 bug |
|---|---|---|
| 多算子流水 | 先下发正常 `add_ok_custom`（成功），再下发 `gather_bad_custom`（失败），同 stream 顺序执行 | 一个 step 里多个算子，需定位是**哪个**算子 |
| 部分核失败 | 仅 `blockIdx >= 4` 的后半 4 核注入越界，前 4 核正常 | 数据相关的故障，只在部分核/部分 token 触发 |
| 读越界（非写） | gather 读取基址按 `blockIdx` 运行时偏移到 src 分配区外 | gather/embedding **索引溢出**，比固定写越界隐蔽 |

源码见 [app_complex/src/complex_kernel.cpp](app_complex/src/complex_kernel.cpp)。编译运行：
```bash
bash app_complex/build.sh          # → app_complex/build_run/complex_op
```

### 4.2 故障真实复现（裸跑 + launch 均验证）

`aclrtSynchronizeStream FAILED -> 507035`，launch 抓到的 plog 精确命中设计意图：

```
... aivec error, core id is <N> ... error code = 0x800000 ... blk:<N> ...
errorStr: The DDR address of the MTE instruction is out of range.
[DFX_INFO]AI Core kernel execution failed, ... fault kernel_name=gather_bad_custom_1
```

- 出错算子 = `gather_bad_custom_1`（**第二个**算子，不是 add_ok）✅
- 出错核 = 仅 `blockIdx >= 4` 的**后半 4 核**报错（与算子设计一致），前 4 核无错 ✅
- 错误类型 = MTE 读地址越界 ✅

**采集层（launch）结论：定位一个复杂故障所需的全部线索——哪个算子、哪些核、什么错——launch 全部采到了。**

### 4.3 asys analyze 对复杂故障的实测表现（如实记录）

`bash analyze_aicore_error.sh <fault-data-complex/launch/...>` → `fault-data-complex/analyze/info_*/aicerror/info.txt`：

```
The maintenance and test information is insufficient or the format is incorrect, contact technical support.
1. Adump log '[Dump][Exception]' cannot be found in <launch输出>.
2. Check whether open exception dump.
```

两个真实发现（已写入 [feedback.md](feedback.md) 第 7 节）：

1. **analyze 强依赖异常 dump，缺则停**：容器内 `[Dump][Exception]` adump 文件始终未落盘
   （`含[Dump][Exception]的文件数 = 0`），analyze 走不到根因解析，info.txt 没能体现"哪个算子/哪些核"。
2. **plog 里有答案却未被利用**：launch 的 plog 白纸黑字写着 `fault kernel_name=gather_bad_custom_1`
   和出错核号（后半 4 核），但 analyze 的 `collection/plog/aicore_error/` 目录**为空**，没做 plog 降级解析。

### 4.4 案例1 vs 案例2 小结

| | 案例1 dirty_op | 案例2 complex_op |
|---|---|---|
| 故障形态 | 单算子 / 固定写越界 / 全核失败 | 双算子流水 / 运行时读越界 / 仅后半核失败 |
| launch 采集 | ✅ 完整 | ✅ 完整（含算子名、4 个出错核） |
| analyze（缺 dump 时） | 报 dump 缺失 | 同样报 dump 缺失，复杂特征未体现 |
| 价值 | 跑通三流程基线 | 检验定位精度，暴露 analyze 的 dump 依赖与 plog 降级缺失 |

**总体评价**：asys 的**采集能力**（collect/launch）对简单和复杂故障都够用，原始线索采得全；
但**解析能力**（analyze）在容器这类 dump 无法落盘的常见环境下，因强依赖 dump 且不降级解析 plog，
实际给出的定位有限。最有价值的改进点：**analyze 缺 dump 时应降级提取 plog 里已有的
`fault kernel_name` / `core id` / `errorStr`，填进 info.txt**——这对容器化部署的可用性影响很大。

---

## 任务达成对照（验收标准逐条）

| 验收标准 | 产物 | 状态 |
|---|---|---|
| ≥1 次无需复跑 collect | `collect.sh` + `fault-data/collect/` | ✅ |
| ≥1 次 launch 复跑+收集，留可复现命令 | `launch_rerun.sh` + `app/` + `fault-data/launch/`（含 user_cmd） | ✅ |
| 1 次 aicore_error 解析（真实或样例） | `analyze_aicore_error.sh`（实跑产出 info.txt，节选见 3.3） | ✅ 真实触发 + 完整样例 |
| 查看并解释主要故障产物 | 第 2、3 节（cann 日志 / data-dump / 辅助信息 / info.txt） | ✅ |
| 体验反馈 ≥3 项维度 | `feedback.md`（覆盖 7 项） | ✅ |
| README 三节齐全 | 本文件（目录树 + 输入输出 + 任务达成情况） | ✅ |
| 复杂故障对照 + 工具定位精度评测 | 第 4 节 + `app_complex/` | ✅ 附加 |

## 复现步骤

```bash
# 0. 准备环境（${install_path} 为 CANN 安装目录，如 /usr/local/Ascend/ascend-toolkit）
source ${install_path}/latest/bin/setenv.bash

# 1. 编译故障注入算子
bash app/build.sh

# 2. 流程1：无需复跑收集
bash collect.sh

# 3. 流程2：复跑 + 收集（抓真实 AI Core Error）
bash launch_rerun.sh

# 4. 流程3：解析 AI Core Error
bash analyze_aicore_error.sh                       # 解析 launch 真实输出
# 或对仓库内自带的 msaicerr 故障样例（路径相对于仓库根目录）：
bash analyze_aicore_error.sh test/ut/msaicerr/res/ori_data/<样例目录>

# 5.（可选）复杂故障对照案例：多算子流水 + 部分核 + 读越界
bash app_complex/build.sh
asys launch --task "$(pwd)/app_complex/build_run/complex_op" --output "$(pwd)/fault-data-complex/launch"
bash analyze_aicore_error.sh "$(pwd)/fault-data-complex/launch/$(ls fault-data-complex/launch)"
```
