# oam-tools

## 概述

oam-tools（Operations, Administration, and Maintenance）项目为开发者提供故障定位工具和性能测试调优工具，包含故障信息收集，软硬件信息展示，AI core error报错分析，AI任务性能采集和分析等能力，提升故障问题定位和AI任务性能分析效率。

## 目录结构

关键目录结构如下：

  ```
  ├── cmake                                          # 工程编译目录
  ├── scripts                                        # 辅助构建相关文件
  ├── src                                            # 所有模块的源代码
  |   ├── asys                                       # asys模块目录
  |   ├── hccl_test                                  # hccl_test模块目录
  |   ├── msaicerr                                   # msaicerr模块目录 
  |   ├── msprof                                     # msprof模块目录
  |   ├── third_party                                # 依赖包相关文件
  |   ......
  ├── test                                           # UT/ST用例
  ├── CMakeLists.txt                                 # 构建编译配置文件
  ├── build.sh                                       # 项目工程编译脚本
  ......
  ```


## 源码编译&部署

### oam-tools仓整包源码编译

#### 前提条件

使用本项目前，请确保如下基础依赖、NPU驱动和固件已安装。

1. **安装依赖**

    本项目源码编译用到的依赖如下，请注意版本要求。

    - python >= 3.9.0
    - gcc >= 7.3.0
    - cmake >= 3.16.0
    - ccache
    - CANN toolkit组合包：`Ascend-cann-toolkit_${cann_version}_linux-${arch}.run`
    - CANN ops组合包：`Ascend-cann-${chip_type}-ops_${cann_version}_linux-${arch}.run`
    - protobuf >= 25.1
    - abseil >= 20230802.1
    - json >= 3.11.3
    - googletest（仅执行UT时依赖，建议版本 release-1.11.0）
    - mockcpp（仅执行UT时依赖，建议版本 2.7）
    - pytest（仅执行UT时依赖，建议版本 9.0.1）
    
	其中：
    - \$\{chip\_type\}：表示昇腾AI处理器型号，如910_93、910b等。
    - \$\{cann\_version\}：表示CANN包版本号，需要与Toolkit包版本号相同。
    - \$\{arch\}：表示CPU架构，如aarch64、x86_64。

2. **安装驱动与固件（运行态依赖）**

    运行Toolkit时必须安装驱动与固件，安装指导详见《[CANN 软件安装指南](https://www.hiascend.com/document/redirect/CannCommercialInstSoftware)》。

#### 环境准备

1. **安装CANN toolkit包和ops包**

    根据实际环境，下载对应`Ascend-cann-toolkit_${cann_version}_linux-${arch}.run`和`Ascend-cann-${chip_type}-ops_${cann_version}_linux-${arch}.run`包。下载链接为[toolkit x86_64包](https://ascend.devcloud.huaweicloud.com/artifactory/cann-run/software/8.5.0/x86_64/)、[toolkit aarch64包](https://ascend.devcloud.huaweicloud.com/artifactory/cann-run/software/8.5.0/aarch64/)、[ops x86_64包](https://ascend.devcloud.huaweicloud.com/artifactory/cann-run/software/8.5.0/x86_64/)、[ops aarch64包](https://ascend.devcloud.huaweicloud.com/artifactory/cann-run/software/8.5.0/aarch64/)。

    ```bash
    # 确保安装包具有可执行权限
    chmod +x Ascend-cann-toolkit_${cann_version}_linux-${arch}.run
    chmod +x Ascend-cann-${chip_type}-ops_${cann_version}_linux-${arch}.run
    # 安装命令
    ./Ascend-cann-toolkit_${cann_version}_linux-${arch}.run --full --install-path=${install_path}
    ./Ascend-cann-${chip_type}-ops_${cann_version}_linux-${arch}.run --install --install-path=${install_path}
    ```
    - \$\{chip\_type\}：表示昇腾AI处理器型号，如910_93、910b等。
    - \$\{cann\_version\}：表示CANN包版本号。
    - \$\{arch\}：表示CPU架构，如aarch64、x86_64。
    - \$\{install\_path\}：表示指定安装路径，可选，默认安装在`/usr/local/Ascend`目录。

2. **配置环境变量**
	
	根据实际场景，选择合适的命令。

    ```bash
    # 默认路径安装，以root用户为例（非root用户，将/usr/local替换为${HOME}）  
    source /usr/local/Ascend/cann/bin/setenv.bash
    # 指定路径安装
    # source ${install_path}/cann/bin/setenv.bash
    
    # 默认路径安装，以root用户为例（非root用户，将/usr/local替换为${HOME}）
    export ASCEND_INSTALL_PATH=/usr/local/Ascend/cann
    # 指定路径安装
    # export ASCEND_INSTALL_PATH=${install_path}/cann
    ```

3. **下载源码**

    ```bash
    # 下载项目源码，以master分支为例
    git clone https://gitcode.com/cann/oam-tools.git
    ```
    或者在仓库页面上找到“下载ZIP”按钮，点击后会下载一个包含仓库内容的ZIP文件。

#### 编译

`oam-tools`提供一键式编译能力，若您的编译环境可以访问网路，可通过如下命令进行编译：

```bash
bash build.sh --cann_3rd_lib_path=${THIRD_LIB_PATH}
```

- `--cann_3rd_lib_path`为第三方库的编译结果存储目录，默认值为`./third_party`。执行编译脚本时，若本地没有第三方库，会从gitcode开源仓库下载各个第三方库的源码。
- 更多编译参数可以通过`bash build.sh -h`查看。
- 编译过程中会下载闭源二进制包，闭源二进制包中包含保证功能正常运行的库及头文件且只提供release版本，**即使编译选项为debug，也只会下载release版本的tar包**

若您的编译环境无法访问网络，需要在联网环境中手动下载第三方库、闭源二进制包、子仓，并手动上传至您的编译环境中，包括：
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


或者，您可以运行下载脚本，会在执行命令的路径下，直接下载并保存上述第三方库、闭源二进制包和子仓（下载子仓需要在有git的环境且[配置gitcode的个人访问令牌](https://gitcode.com/setting/token-classic), 确保能够正确执行git clone）：
```
# 在当前执行路径下保存文件，可以在不同的路径下执行命令(需要修改脚本的相对路径，或者使用绝对路径)来改变保存的位置
python cmake/download_libs.py
```

您需要在编译环境中新建一个`{your_3rd_party_path}`目录来存放第三方开源软件和闭源软件，创建好目录后，将下载好的压缩包上传至目录`{your_3rd_party_path}`
```bash
mkdir -p {your_3rd_party_path}
```

可以使用如下命令进行编译：
```bash
bash build.sh --cann_3rd_lib_path={your_3rd_party_path}
```

编译完成之后会在`build_out`目录下生成`cann-oam-tools_<cann_version>_linux-<arch>.run`软件包。
\<cann_version>表示版本号。
\<arch>表示操作系统架构，取值包括x86_64与aarch64。

#### 安装
可执行如下命令安装编译生成的oam-tools软件包：

```bash
./cann-oam-tools_<cann_version>_linux-<arch>.run --full --install-path=${install_path}
```
安装完成之后，用户编译生成的oam-tools软件包会替换已安装CANN开发套件包中的oam-tools相关软件。
                                       

## 本地验证 

编译完成后，用户可以进行开发测试（DT：Development Testing），验证项目功能是否正常。
> 说明：执行UT用例依赖[pytest-cov](https://pypi.org/project/pytest-cov/), [coverage](https://pypi.org/project/coverage/), [pytest](https://docs.pytest.org/en/stable/), [googletest](https://google.github.io/googletest/advanced.html#running-a-subset-of-the-tests)，生成代码覆盖率报告需要独立安装lcov软件, UT不支持在虚拟机和conda环境下运行。

> 要求：pytest-cov >=7.0.0, coverage >=7.10.0

- 编译执行`UT`测试用例：

```bash
bash build.sh -u
```
如需获取覆盖率，可使用`--cov`参数（如无需获取覆盖率，可省略此参数）：

```bash
bash build.sh -u --cov
```
UT测试用例编译输出目录为`build`，如果想清除历史编译记录，可以执行如下操作：

```bash
rm -rf build_out/ build/
```

## 相关文档

-[asys工具用户指南](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/850/maintenref/troubleshooting/troubleshooting_0096.html)：介绍asys命令行工具的使用方法，支持以下功能：故障信息收集、业务复跑+故障信息收集、软硬件和Device状态信息展示、健康检查、综合检测、组件检测、trace文件解析/coredump文件解析/stackcore文件解析/coretrace文件解析、实时堆栈导出、环境配置、AI Core Error故障信息解析等。

-[msaicerr工具用户指南](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/850/maintenref/troubleshooting/troubleshooting_0099.html)：介绍msaicerr命令行工具的使用方法，用于分析AI Core Error问题、解析Dump文件、检查环境等。

-[性能调优工具用户指南](https://www.hiascend.com/document/redirect/CannCommunityToolProfiling)：介绍msprof命令行工具的使用方法，用于指导用户采集和分析运行在昇腾AI处理器上的AI任务各个运行阶段的关键性能指标，以便快速定位软、硬件性能瓶颈，提升AI任务性能分析的效率。

-[HCCL性能测试工具用户指南](https://www.hiascend.com/document/redirect/CannCommunityToolHcclTest)：介绍hccl_test工具的使用方法，用于指导分布式训练或推理场景下，测试集合通信的功能与性能。

## 相关信息
- [贡献指南](CONTRIBUTING.md)
- [安全声明](SECURITY.md)
- [许可证](LICENSE)


