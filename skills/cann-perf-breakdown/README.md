# CANN 性能拆解技能

本目录提供从 NPU profiling 数据到可交互 UI 报告的三阶段流程。按编号顺序使用三个 skill：

| 阶段 | 目录 | 作用 |
| --- | --- | --- |
| 1 | [`1-perf-breakdown`](1-perf-breakdown/) | 根据模型源码建立架构并将 profiling 算子映射到结构节点 |
| 2 | [`2-adapt-breakdown-to-ui-json`](2-adapt-breakdown-to-ui-json/) | 将拆解结果转换为 UI 所需的 analysis、performance、timeline 和架构图数据 |
| 3 | [`3-generate-ui-json-report`](3-generate-ui-json-report/) | 使用转换后的数据生成可交互的 UI 报告 |

完整的阶段衔接、输入输出和门禁说明见 [`MODEL_BREAKDOWN_TO_UI_WORKFLOW.md`](MODEL_BREAKDOWN_TO_UI_WORKFLOW.md)。每个阶段的具体规则以对应目录中的 `SKILL.md` 和 `references/` 为准。

## 安装与调用

```bash
git clone --depth 1 https://gitcode.com/cann/oam-tools.git
mkdir -p ~/.codex/skills
cp -a oam-tools/skills/cann-perf-breakdown ~/.codex/skills/
```

调用：`使用 $cann-perf-breakdown 工作流，输入目录为 <采集目录>，输出目录为 <输出目录>。`

## 快速入口

```bash
python3 2-adapt-breakdown-to-ui-json/scripts/run_pipeline.py \
  --capture-dir <profiling-directory> \
  --model-id <model-id> \
  --out <output-directory>
```

该入口会在输入证据满足阶段门禁时依次执行转换和报告生成；需要 AI 语义映射或审查时，会输出请求文件并暂停，具体继续方式见工作流文档。

## 目录约定

- `1-perf-breakdown/`：模型架构提取、算子归属、校验和评分。
- `2-adapt-breakdown-to-ui-json/`：拆解结果到 UI 数据契约的确定性转换。
- `3-generate-ui-json-report/`：报告资源、运行时数据和前端生成脚本。
- `MODEL_BREAKDOWN_TO_UI_WORKFLOW.md`：三阶段流程导航。
