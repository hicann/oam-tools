# 环境部署

请您先参考下面步骤完成基础环境搭建和源码下载，确保已安装NPU驱动、固件和CANN软件（`Ascend-cann-toolkit`和`Ascend-cann-ops`）等。

## 环境准备

本项目提供多种搭建昇腾环境的方式，请按需选择。

> **说明**：本文提到的编译态和运行态含义如下，请根据实际情况选择。
>
> - 编译态：针对仅编译本项目不运行的场景，只需安装CANN toolkit包。
> - 运行态：针对运行本项目的场景（编译运行或纯运行），需安装驱动与固件、CANN toolkit包、CANN ops包。

|  安装方式  |  使用说明  |  使用场景  |
| ----- | ------ | ------ |
|  WebIDE  | 一站式开发平台，提供在线直接运行的昇腾环境，无需手动安装。<br>当前可提供单机算力，**默认安装最新商发版CANN包**。 | 适用于没有昇腾设备的开发者。|
|  Docker  | Docker镜像是一种高效部署方式，已预集成CANN包和必备依赖。<br>当前仅适用于Atlas A2系列产品，OS仅支持Ubuntu操作系统。**默认安装最新商发版CANN包**。 |适用有昇腾设备，需要快速搭建环境的开发者。|
|  手动安装  | - |适用有昇腾设备，想体验手动安装CANN包或体验最新master分支能力的开发者。|

### 方式1：WebIDE环境

对于无昇腾设备的开发者，可直接使用WebIDE开发平台，即“**一站式开发平台**”，该平台为您提供在线可直接运行的昇腾环境，环境中已安装必备的驱动固件、软件包和依赖，无需手动安装。更多关于开发平台的介绍请参考[LINK](https://gitcode.com/org/cann/discussions/54)。

1. 进入开源项目，单击“`云开发`”按钮，使用已认证过的华为云账号登录。若未注册或认证，请根据页面提示进行注册和认证。

   <img src="./figures/cloudIDE.png" alt="云平台"  width="750px" height="90px">

2. 根据页面提示创建并启动云开发环境，单击“`连接 > WebIDE `”进入一站式开发平台，开源项目的源码资源默认在`/mnt/workspace`目录下。

   <img src="./figures/webIDE.png" alt="云平台"  width="1000px" height="150px">


### 方式2：Docker部署

对于不依赖昇腾设备的开发者，若您想快速搭建昇腾环境，可使用Docker镜像部署。

> **说明**：镜像文件比较大，下载需要一定时间，请您耐心等待。关于docker命令的选项介绍可通过`docker --help`查询。

1.**下载镜像**

- 步骤1：以root用户登录宿主机。确保宿主机已安装Docker引擎（版本1.11.2及以上）。
- 步骤2：从[昇腾镜像仓库](https://www.hiascend.com/developer/ascendhub/detail/17da20d1c2b6493cb38765adeba85884)拉取已预集成CANN软件包及开发所需依赖的镜像。命令如下，根据实际架构选择：

    ```bash
    # 示例：拉取ARM架构的CANN开发镜像
    docker pull --platform=arm64 swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10
    # 示例：拉取X86架构的CANN开发镜像
    docker pull --platform=amd64 swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10
    ```

2.**运行Docker**
拉取镜像后，需要以特定参数启动容器。

```bash
docker run --name oam-tools -it swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10 bash
```
| 参数 | 说明 | 注意事项 |
| :--- | :--- | :--- |
| `--name oam-tools` | 为容器指定名称，便于管理。 | 可自定义。 |
| `-it` | `-i`（交互式）和 `-t`（分配伪终端）的组合参数。 | - |
| `swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10` | 指定要运行的Docker镜像。 |请确保此镜像名和标签（tag）与你通过`docker pull`拉取的镜像完全一致。 |
| `bash` | 容器启动后立即执行的命令。 | - |

3.**初始化环境**
进入容器后，执行以下命令初始化环境：

```bash
curl -fsSL https://raw.gitcode.com/cann/oam-tools/raw/master/init_env.sh | bash
```

### 方式3：手动安装

对于有昇腾设备的开发者，若您想手动搭建昇腾环境，请参考下述步骤。

#### 前置依赖

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
    - patch >= 2.7.6
    - coverage (仅执行UT时依赖，建议版本 7.13.2)
    - googletest（仅执行UT时依赖，建议版本 1.14.0）
    - mockcpp（仅执行UT时依赖，建议版本 2.7）
    - pytest（仅执行UT时依赖，建议版本 9.0.1）
    - pytest-mock (仅执行UT时依赖，建议版本 3.15.1)
    
	其中：
    - \$\{chip\_type\}：表示昇腾AI处理器型号，如910_93、910b等。
    - \$\{cann\_version\}：表示CANN包版本号，需要与Toolkit包版本号相同。
    - \$\{arch\}：表示CPU架构，如aarch64、x86_64。

#### 软件安装

1. **安装驱动与固件（运行态依赖）**

    驱动与固件的下载和安装操作请参考《[CANN软件安装指南](https://www.hiascend.com/document/redirect/CannCommunityInstWizard)》中“准备软件包”和“安装NPU驱动和固件”章节。驱动与固件是运行态依赖，若仅编译算子，可以不安装。

2. **安装CANN包**

    - **场景1：体验master版本能力或基于master版本进行开发**

        请单击[下载链接](https://ascend.devcloud.huaweicloud.com/artifactory/cann-run-mirror/software/master/)，选择最新时间版本，并根据产品型号和环境架构下载对应包。安装命令如下，更多指导参考《[CANN软件安装指南](https://www.hiascend.com/document/redirect/CannCommunityInstWizard)》。

        1. 安装CANN toolkit包

            ```bash
            # 确保安装包具有可执行权限
            chmod +x Ascend-cann-toolkit_${cann_version}_linux-${arch}.run
            # 安装命令
           ./Ascend-cann-toolkit_${cann_version}_linux-${arch}.run --install --install-path=${install_path}
           ```

        2. 安装CANN ops包（运行态依赖）

            ops包是运行态依赖，若仅编译算子，可不安装此包。

            ```bash
            # 确保安装包具有可执行权限
            chmod +x Ascend-cann-${soc_name}-ops_${cann_version}_linux-${arch}.run
            # 安装命令
            ./Ascend-cann-${soc_name}-ops_${cann_version}_linux-${arch}.run --install --install-path=${install_path}
            ```

        - \$\{cann\_version\}：表示CANN包版本号。
        - \$\{arch\}：表示CPU架构，如aarch64、x86_64。
        - \$\{soc\_name\}：表示NPU型号名称。
        - \$\{install\_path\}：表示指定安装路径，ops包需与toolkit包安装在相同路径，root用户默认安装在`/usr/local/Ascend`目录。

    - **场景2：体验已发布版本能力或基于已发布版本进行开发**

        请访问[CANN官网下载中心](https://www.hiascend.com/cann/download)，选择发布版本（仅支持CANN 8.5.0及后续版本），并根据产品型号和环境架构下载对应包，最后参考网页提供的命令完成安装。

## 环境验证

安装完CANN包后，需验证环境和驱动是否正常。

-   **检查NPU设备**

    ```bash
    # 运行npu-smi，若能正常显示设备信息，则驱动正常
    npu-smi info
    ```
-   **检查CANN安装**

    ```bash
    # 查看CANN toolkit包版本信息（默认路径安装），WebIDE场景下将/usr/local替换为/home/developer
    cat /usr/local/Ascend/cann/${arch}-linux/ascend_toolkit_install.info
    # 查看CANN ops包版本信息（默认路径安装），WebIDE场景下将/usr/local替换为/home/developer
    cat /usr/local/Ascend/cann/${arch}-linux/ascend_ops_install.info
    ```

## 环境变量配置

按需选择合适的命令使环境变量生效。
```bash
# 默认路径安装，以root用户为例（非root用户，将/usr/local替换为${HOME}）
source /usr/local/Ascend/cann/set_env.sh
# 指定路径安装
# source ${install_path}/cann/set_env.sh
```