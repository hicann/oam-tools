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


## ⚡️环境准备

在源码编译前，请先完成基础环境搭建。具体操作请参见[快速安装](docs/quick_install.md)。

## ⬇️ 源码下载

源码下载命令如下，请将`${branch}`替换为目标分支标签名，源码分支标签与CANN版本配套关系参见[release仓库](https://gitcode.com/cann/release-management)。

```bash
# 下载项目对应分支源码
git clone -b ${branch} https://gitcode.com/cann/otm-tools.git
```

对于WebIDE或Docker环境，已默认提供最新商发版本的项目源码，如需获取其他版本的源码，也需通过上述命令下载源码。

> 注意
> - gitcode平台在使用HTTPS协议的时候要配置并使用个人访问令牌代替登录密码进行克隆，推送等操作。
> - 若您的编译环境无法访问网络，无法通过git指令下载代码，请先在联网环境中下载源码，再手动上传至目标环境。

## 🌐 源码编译

### 🛜 联网环境
若您的编译环境可以访问网络，可通过下面命令进行编译：

```bash
bash build.sh
```
或者指定第三方库的地址`third_party_path`

```bash
bash build.sh --cann_3rd_lib_path=${third_party_path}
```

- `--cann_3rd_lib_path`为第三方库的编译结果存储目录，默认值为`./third_party`。执行编译脚本时，若本地没有第三方库，会从gitcode开源仓库下载各个第三方库的源码。
- 编译过程中会下载闭源二进制包，闭源二进制包中包含保证功能正常运行的库及头文件且只提供release版本，**即使编译选项为debug，也只会下载release版本的tar包**
- 更多编译参数可以通过`bash build.sh -h`查看。

### ❗无法访问网络
若您的编译环境无法访问网络，需要在联网环境中手动下载第三方库、闭源二进制包、子仓，并手动上传至您的编译环境中。

在联网环境中运行下载脚本，该脚本会在执行命令的路径下，直接下载并保存上述第三方库、闭源二进制包和子仓（下载子仓需要在有git的环境且[配置gitcode的个人访问令牌](https://gitcode.com/setting/token-classic), 确保能够正确执行git clone）

```
# 在当前执行路径下保存文件，可以在不同的路径下执行命令(需要修改脚本的相对路径，或者使用绝对路径)来改变保存的位置
python cmake/download_libs.py
```

在编译环境中新建一个`third_party_path`目录来存放第三方开源软件和闭源软件
```bash
mkdir -p ${third_party_path}
```

创建好目录后，将下载好的第三方库、闭源二进制包和子仓，上传至目录`third_party_path`，使用如下命令进行编译：
```bash
bash build.sh --cann_3rd_lib_path=${third_party_path}
```

第三方库、闭源二进制包和子仓包括：
| 开源软件 | 版本 | 下载地址 |
|---|---|---|
|protobuf|v25.1|[protobuf-25.1.tar.gz](https://gitcode.com/cann-src-third-party/protobuf/releases/download/v25.1/protobuf-25.1.tar.gz)|
|makeself|2.5.0|[makeself-release-2.5.0-patch1.tar.gz](https://gitcode.com/cann-src-third-party/makeself/releases/download/release-2.5.0-patch1.0/makeself-release-2.5.0-patch1.tar.gz)|
|abseil-cpp|20230802.1|[abseil-cpp-20230802.1.tar.gz](https://gitcode.com/cann-src-third-party/abseil-cpp/releases/download/20230802.1/abseil-cpp-20230802.1.tar.gz)|
|boost|v1.87.0|[boost_1_87_0.tar.gz](https://gitcode.com/cann-src-third-party/boost/releases/download/v1.87.0/boost_1_87_0.tar.gz)|
|gtest|1.14.0|[googletest-1.14.0.tar.gz](https://gitcode.com/cann-src-third-party/googletest/releases/download/v1.14.0/googletest-1.14.0.tar.gz)|
|mockcpp-patch|2.7-h2|[mockcpp-2.7_py3.patch](https://gitcode.com/cann-src-third-party/mockcpp/releases/download/v2.7-h2/mockcpp-2.7_py3.patch)|
|mockcpp|2.7-h2|[mockcpp-2.7.tar.gz](https://gitcode.com/cann-src-third-party/mockcpp/releases/download/v2.7-h2/mockcpp-2.7.tar.gz)|

| 闭源二进制 | 版本 | 下载地址 |
|---|---|---|
|cann-oam-tools-release-x86_64.tar.gz|20260213(Stable)|[Download](https://ascend-cann.obs.cn-north-4.myhuaweicloud.com/CANN/20260213_newest/cann-oam-tools-release-x86_64.tar.gz)|
|cann-oam-tools-release-aarch64.tar.gz|20260213(Stable)|[Download](https://ascend-cann.obs.cn-north-4.myhuaweicloud.com/CANN/20260213_newest/cann-oam-tools-release-aarch64.tar.gz)|

| 子仓 | 版本 | 下载地址 |
|---|---|---|
|msprobe|master|https://gitcode.com/Ascend/msprobe|
|msprof|master|https://gitcode.com/Ascend/msprof|


编译完成之后会在`build_out`目录下生成`cann-oam-tools_<cann_version>_linux-<arch>.run`软件包。
\<cann_version>表示版本号。
\<arch>表示操作系统架构，取值包括x86_64与aarch64。

## 🔨 安装
可执行如下命令安装编译生成的oam-tools软件包：

```bash
./cann-oam-tools_<cann_version>_linux-<arch>.run --full --install-path=${install_path}
```
安装完成之后，用户编译生成的oam-tools软件包会替换已安装CANN开发套件包中的oam-tools相关软件。

> 如果您的环境上`grep`版本大于3.8.0，安装时会出现告警，例如`grep: waring: stray \ before -`，这是由于grep高版本对表达式有更严格的校验，但并不影响安装和使用
                                       

## 🧪 验证 

编译完成后，用户可以进行开发测试（DT：Development Testing），验证项目功能是否正常。

> 如果您按照[快速安装](docs/quick_install.md)已经完成环境搭建，此时应该不需要额外进行操作。当然，如果运行仍报缺少某些python库的问题，您可以尝试执行以下命令安装所缺少的python库(推荐在python虚拟环境中执行，避免污染原有python环境)：
```pip3 install -r requirements.txt```

编译执行测试用例：
```bash
bash build.sh -u
```

如果希望指定单独组件进行测试，可以使用`--component`参数指定：
```bash
bash build.sh -u --component msprof
```

UT测试用例编译输出目录为`build`，如果想清除历史编译记录，可以执行如下操作：
```bash
rm -rf build_out/ build/
```

## 📖 相关文档

[asys工具用户指南](https://hiascend.com/document/redirect/CannCommunityasys)：介绍asys命令行工具的使用方法，支持以下功能：故障信息收集、业务复跑+故障信息收集、软硬件和Device状态信息展示、健康检查、综合检测、组件检测、trace文件解析/coredump文件解析/stackcore文件解析/coretrace文件解析、实时堆栈导出、环境配置、AI Core Error故障信息解析等。

[msaicerr工具用户指南](https://hiascend.com/document/redirect/CannCommunitymsaicerr)：介绍msaicerr命令行工具的使用方法，用于分析AI Core Error问题、解析Dump文件、检查环境等。

[性能调优工具用户指南](https://www.hiascend.com/document/redirect/CannCommunityToolProfiling)：介绍msprof命令行工具的使用方法，用于指导用户采集和分析运行在昇腾AI处理器上的AI任务各个运行阶段的关键性能指标，以便快速定位软、硬件性能瓶颈，提升AI任务性能分析的效率。

[HCCL性能测试工具用户指南](https://www.hiascend.com/document/redirect/CannCommunityToolHcclTest)：介绍hccl_test工具的使用方法，用于指导分布式训练或推理场景下，测试集合通信的功能与性能。

## ℹ️ 相关信息
- [贡献指南](CONTRIBUTING.md)
- [安全声明](SECURITY.md)
- [许可证](LICENSE)


