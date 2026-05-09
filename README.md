# oam-tools

## 🚀 概述

oam-tools（Operations, Administration, and Maintenance）项目为开发者提供故障定位工具和性能测试调优工具，包含故障信息收集，软硬件信息展示，AI core error报错分析，AI任务性能采集和分析等能力，提升故障问题定位和AI任务性能分析效率。

## 🔍 目录结构

关键目录结构如下：

  ```
  ├── cmake                                          # 工程编译目录
  ├── scripts                                        # 辅助构建相关文件
  ├── src                                            # 所有模块的源代码
  |   ├── asys                                       # asys模块目录
  |   ├── hccl_test                                  # hccl_test模块目录
  |   ├── msaicerr                                   # msaicerr模块目录 
  |   ├── msprof                                     # msprof模块目录
  |   ├── third_party                                # 依赖的第三方库头文件
  |   ......
  ├── test                                           # UT/ST用例
  ├── CMakeLists.txt                                 # 构建编译配置文件
  ├── build.sh                                       # 项目工程编译脚本
  ......
  ```


## ⚡️ 环境准备

请先按照[快速安装](docs/quick_install.md)指南完成环境准备。

## 🌐 源码编译

执行以下命令进行编译：

```bash
bash build.sh
```

如需指定第三方库路径，可通过 `--cann_3rd_lib_path` 参数传入：

```bash
bash build.sh --cann_3rd_lib_path=${third_party_path}
```

- `--cann_3rd_lib_path`：第三方库存储目录，默认值为 `./third_party`。若本地不存在第三方库，编译脚本将自动从 gitcode 开源仓库下载各第三方库源码。
- 编译过程中会自动下载闭源二进制包，该包含有保证功能正常运行所需的库及头文件，且仅提供 release 版本，**即使编译选项指定为 debug，也只会下载 release 版本的 tar 包**。
- 若编译环境无法访问网络，请参考[离线编译环境准备](docs/quick_install.md#离线编译环境准备)提前完成依赖包的下载与配置，并通过 `--cann_3rd_lib_path` 参数指定依赖包所在目录后再执行编译。
- 更多编译参数请通过 `bash build.sh -h` 查看。

编译完成后，`build_out` 目录下会生成 `cann-oam-tools_<cann_version>_linux-<arch>.run` 软件包，其中 `<cann_version>` 为版本号，`<arch>` 为操作系统架构（可选值：`x86_64` 或 `aarch64`）。

## 🔨 安装
可执行如下命令安装编译生成的oam-tools软件包：

```bash
./cann-oam-tools_<cann_version>_linux-<arch>.run --full --install-path=${install_path}
```
安装完成之后，用户编译生成的oam-tools软件包会替换已安装CANN开发套件包中的oam-tools相关软件。

> 如果您的环境上`grep`版本大于3.8.0，安装时会出现告警，例如`grep: waring: stray \ before -`，这是由于grep高版本对表达式有更严格的校验，但并不影响安装和使用
                                       

## 🧪 验证

编译完成后，用户可以进行测试验证项目功能是否正常。

> Python 依赖安装已在[环境准备](docs/quick_install.md)中处理，无需额外操作。

编译执行测试用例：
```bash
bash build.sh -u
```

如果希望指定单独组件进行测试，可以使用`--component`参数指定：

可选值：`asys`（故障信息收集）、`msaicerr`（AI Core Error 分析）、`msprof`（性能调优）、`all`（所有组件，默认）

```bash
bash build.sh -u --component msprof
```

UT测试用例编译输出目录为`build`，如果想清除历史编译记录，可以执行如下操作：
```bash
rm -rf build_out/ build/
```

## 🅿️ Pre-commit
pre-commit 是一个用于管理和维护 Git 预提交钩子（hooks）的框架，通过在代码提交前自动化执行代码检查、格式化和安全扫描，确保代码质量并统一团队规范，显著减少 CI/CD 流水线失败并提升协作效率。
本仓已配置pre-commit，用户可以参考CANN社区的[pre-commit配置指导书中第3章节](https://gitcode.com/cann/infrastructure/blob/main/docs/SC/pre-commit/pre-commit%E9%85%8D%E7%BD%AE%E6%8C%87%E5%AF%BC%E4%B9%A6.md#3-%E7%A4%BE%E5%8C%BA%E8%B4%A1%E7%8C%AE%E8%80%85%E4%BD%BF%E7%94%A8pre-commit%E8%83%BD%E5%8A%9B)安装pre-commit, 首次由于需要配置java，maven环境以及构建jar包，需要的时间比较长。

## 📖 相关文档

[asys工具用户指南](https://hiascend.com/document/redirect/CannCommunityasys)：介绍asys命令行工具的使用方法，支持以下功能：故障信息收集、业务复跑+故障信息收集、软硬件和Device状态信息展示、健康检查、综合检测、组件检测、trace文件解析/coredump文件解析/stackcore文件解析/coretrace文件解析、实时堆栈导出、环境配置、AI Core Error故障信息解析等。

[msaicerr工具用户指南](https://hiascend.com/document/redirect/CannCommunitymsaicerr)：介绍msaicerr命令行工具的使用方法，用于分析AI Core Error问题、解析Dump文件、检查环境等。

[性能调优工具用户指南](https://www.hiascend.com/document/redirect/CannCommunityToolProfiling)：介绍msprof命令行工具的使用方法，用于指导用户采集和分析运行在昇腾AI处理器上的AI任务各个运行阶段的关键性能指标，以便快速定位软、硬件性能瓶颈，提升AI任务性能分析的效率。

[HCCL性能测试工具用户指南](https://www.hiascend.com/document/redirect/CannCommunityToolHcclTest)：介绍hccl_test工具的使用方法，用于指导分布式训练或推理场景下，测试集合通信的功能与性能。

## ℹ️ 相关信息
- [贡献指南](CONTRIBUTING.md)
- [安全声明](SECURITY.md)
- [许可证](LICENSE)


