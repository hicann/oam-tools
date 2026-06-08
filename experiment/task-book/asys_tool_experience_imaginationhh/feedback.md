# asys 故障定位体验反馈

> 环境：Atlas 910B3，容器内 CANN 9.1.0，runtime 仅可见 1 张卡（逻辑 device 0）。
> 反馈基于本 demo 三流程（collect / launch / analyze -r=aicore_error）的实跑体验。

## 1. 业务复跑命令配置是否清晰

**总体清晰，有两处易踩坑。**

- `asys launch --task "<命令>"`：`--task` 直接吃一条完整 shell 命令，零侵入，体验好。
  实跑 `asys launch --task "<repo>/app/build_run/dirty_op" --output <dir>` 一次成功，
  业务的 stdout/stderr 自动落到 `dfx/log/host/screen.txt`，原始命令落到 `user_cmd`，**可复现性好**。
- **坑1（参数语义）**：`--task` 在 `-h` 里标 `<Positional>` 但实际是 `--task <值>` 的带名参数，
  容易误以为是位置参数。建议帮助文案统一成 `<Required>`。
- **坑2（设备号）**：见第 6 节——容器内必须用逻辑 device 0，文档未提示物理/逻辑卡映射。

## 2. 故障信息收集是否完整

**collect 与 launch 完整度不同，需讲清差异。**

- `asys launch` 复跑路径：会主动设 `NPU_COLLECT_PATH` 开启异常 dump，实跑拿到了
  `dfx/log/host/cann/{debug,run}/plog`（含 `aivec error 0x800000 / MTE out of range` 报错行）、
  `dfx/log/host/cann/run/device-0/` 设备日志、`dfx/data-dump/` 目录、`screen.txt`、`user_cmd`，
  以及 hardware/software/status/health 四份辅助信息。**对定位 AI Core Error 足够。**
- `asys collect` 无复跑路径：只收环境已有信息，**不会**补出 data-dump。若故障当时没开异常 dump，
  这里也拿不到 dump——这是设计使然，但新手容易误以为 collect 能"补救"。
- **建议**：collect 的帮助里点明"不开启异常 dump，dump 缺失请改用 launch 复跑"。

## 3. 输出目录和文件命名是否易理解

**整体规范，少数命名偏机器化。**

- 优点：`asys_output_<timestamp>` 顶层时间戳目录 + `dfx/log/host/cann/{debug,run}/` 分层清晰，
  与 CANN 既有 plog 目录结构一致，老手能直接定位。
- `info.txt` / `README.txt` / `debug_info.txt` 命名直观，README.txt 还给了 AICERROR 概要做导航。
- **不易懂处**：
  - `dfx` 缩写未在产物里任何地方解释（DFX = Design For X / 可维测），首次见会懵。
  - atrace 目录 `trace_<pid>_<tid>_<ts>/schedule_event_<...>/schedule_tracer_FE_Statistics_Trace.txt`
    层级深、命名长，靠肉眼找目标 trace 成本高。
  - analyze 输出 `aicerror_0_20240912164007`（真实触发版退化成 `aicerror`，无序号/时间戳），
    两种命名不一致，脚本化处理时要兼容。

## 4. 解析结果是否便于定位问题

**完整 dump 时非常好用；现场不全时也能给出有效指引。**

- 完整样例的 `info.txt` 6 大块（Basic info / DFX Register / Error Line / I/O Memory /
  Dump Parsing / Single-Op Test）直接点出 **出错 kernel 名、出错 pc、
  task/stream/core id、输入输出地址**，定位链路完整，配合 README.txt 概要可快速锁定。
- 真实触发版（dump 未落盘）的 info.txt 没有"卡死"，而是明确列出
  `Adump log '[Dump][Exception]' cannot be found` + `Check whether open exception dump`，
  **告诉你下一步该查什么**，这点很好。
- **建议**：info.txt 开头的 `The maintenance and test information is insufficient...
  contact technical support` 这句对"dump 缺失"和"格式错误"两种情况都用同一句，
  容易让人以为是工具 bug。建议区分"现场不完整（去开 dump）"与"真异常（联系支持）"。

## 5. 报错提示是否能指导下一步操作

**大部分到位，个别 ERROR 是噪声需降级。**

- 正向：analyze 的 info.txt 明确指引（见第 4 节）；launch 的 screen.txt 直接给业务错误码 507035。
- **噪声**：collect/launch 过程中固定打印
  `[ERROR] Call msnpureport tool failed: msnpureport: command not found`，
  在本容器里 msnpureport 本就不存在，这是环境缺失而非用户操作错误，却以 ERROR 级别报出，
  且不影响主流程成功。建议降为 WARNING 并提示"该工具缺失将跳过 device 侧 msnpureport 导出"。
- `Graph collect failed` / `Ops collect failed` / `The JSON file of the fault kernel_name is not found`
  同理：多为"本场景无此类数据"，建议措辞改为"未发现 X，已跳过"，避免误导。

## 6. 容器 / 权限 / 磁盘 / 环境变量兼容性问题

**这是本次最影响成败的一类，记录如下：**

### 6.1 ★ 设备号：物理卡 vs 容器逻辑卡（最关键）
- 宿主 `npu-smi info` 看到的是**某物理卡号 N**，但容器内 CANN runtime 只可见 **1 张卡（逻辑 0）**。
- 初版脚本里 `export ASCEND_RT_VISIBLE_DEVICES=<物理卡号>`，导致 runtime 直接报：
  ```
  [ERROR] RUNTIME GetVisibleDevices: set ASCEND_RT_VISIBLE_DEVICES error, input data range[0-1)
  ```
  kernel **根本没下发到 NPU**，自然采不到 AI Core Error（dump 目录都不生成）。
- **修复**：脚本一律用 device 0，且**不要** export `ASCEND_RT_VISIBLE_DEVICES`。改对后立刻
  触发 `aivec error 0x800000` 并被 asys 收到。
- **建议**：asys 文档应明确"`-d`/设备号在容器内是逻辑卡号，请以容器内可见范围为准，
  勿照搬宿主 npu-smi 的物理卡号"。

### 6.2 异常 dump 必须由 launch 开启
- 裸跑业务（不经 launch）时 plog 打印 `No Env enable exception dump`，且越界写还会引发
  host 侧 `double free or corruption`，dump 拿不到。
- 只有 `asys launch` 设置 `NPU_COLLECT_PATH` 后异常 dump 才开启。**强依赖关系建议在文档强调**。

### 6.3 容器内异常 dump 落盘不完整
- 即便经 launch 开启 dump，本容器内 `dfx/data-dump/` 仍未拿到可被 msaicerr 解析的
  `exception_info` 文件（plog 有报错但 dump 没落盘），导致真实触发版 analyze 报 dump 缺失。
- 推测与容器对 device dump 路径的权限/挂载限制有关。建议 asys 在 dump 目录为空时，
  显式提示"可能受容器挂载/权限限制，请检查 NPU_COLLECT_PATH 是否可写到 device"。

### 6.4 msnpureport 缺失
- 见 5：容器未安装 msnpureport（属 driver 工具包），device 侧 msnpureport 导出失败。
  不影响 host 侧日志/解析，但会刷 ERROR。

### 6.5 SyntaxWarning 噪声
- 每次执行 asys 都先打印 `info/asys_info.py:80: SyntaxWarning: invalid escape sequence '\s'`
  （正则字符串未用 raw string）。无害但影响观感，建议源码把相关正则改成 `r"..."`。

---

## 7. 复杂故障实测：analyze 定位精度的两个真问题

> 用一个更复杂的故障算子（`app_complex/complex_op`：正常 Add + 越界 gather 两算子流水，
> 仅后半 4 核读越界）专门检验 asys 的定位精度，实测结论如下。

### 7.1 采集层（collect/launch）够用 ✅
launch 复跑后，plog 完整保留了定位所需的全部线索：
```
fault kernel_name=gather_bad_custom_1        ← 准确指出是第二个算子
aivec error, core id is <N>, error code=0x800000  ← 仅后半 4 核报错（与算子设计一致）
errorStr: The DDR address of the MTE instruction is out of range.  ← 读越界
task_id / stream_id 等定位字段齐全
```
即"哪个算子、哪些核、什么错"三要素 launch 全采到了。

### 7.2 ★ analyze 强依赖异常 dump，缺则停（高优先）
容器内 `[Dump][Exception]` adump 文件始终未落盘（实测 `含[Dump][Exception]的文件数 = 0`），
导致 analyze 走不到根因解析，`info.txt` 只输出"dump 缺失、联系技术支持"。
**复杂故障的两个关键特征（哪个算子、哪些核）在 info.txt 里一个都没体现。**
- **影响**：容器化部署（dump 落盘常受挂载/权限限制）下，analyze 实际可用性大打折扣。

### 7.3 ★ plog 里有答案却未被利用（高优先，最值得改）
launch 的 plog 白纸黑字写着 `fault kernel_name=gather_bad_custom_1` 和出错核号（后半 4 核），
但 analyze 的中间目录 `collection/plog/aicore_error/` **为空**，info.txt 也未提取这些字段。
工具在 dump 缺失时**没有降级**去解析已有的 plog 关键信息，等于把现成线索浪费了。
- **建议**：analyze 在缺 dump 时应降级提取 plog 的 `fault kernel_name` / `core id` /
  `task_id` / `errorStr`，至少把"哪个算子、哪些核、什么错"写进 info.txt。
  这条对容器场景的可用性提升最大。

---

## 优化建议汇总（按优先级）

1. **analyze 缺 dump 时降级解析 plog**（7.3）——最高优先，直接决定容器场景能否给出有效定位。
2. **文档补充容器逻辑卡说明**（6.1）——直接决定能否采到故障。
3. **区分"环境缺失/场景无数据"与"真错误"的日志级别**（5、6.4）——减少 ERROR 噪声。
4. **analyze 缺 dump 时的提示更精准**（4、6.3、7.2）——区分"去开 dump"与"联系支持"。
5. **帮助文案**：`--task` 标注、`dfx` 含义、设备号语义（1、3、6.1）。
6. **清理 SyntaxWarning**（6.5）——低优先，纯观感。
