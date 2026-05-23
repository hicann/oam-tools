# Environment Deployment

This document is the basic environment setup for Oam-tools tools. The main purpose is to complete NPU driver, firmware, and CANN software (`Ascend-cann-toolkit` and `Ascend-cann-ops`) installation and complete Oam-Tools source code download in the running environment. Complete the basic environment setup and source code download by following the steps below.

## Environment Preparation

This project provides multiple ways to set up the Ascend environment. Choose according to your needs.

> **Note**: The meanings of build mode and runtime mode mentioned in this document are as follows. Choose according to your actual situation.
>
> - Build mode: For scenarios where you only compile this project without running, you only need to install the CANN toolkit package.
> - Runtime mode: For scenarios where you run this project (compile and run or pure run), you need to install driver and firmware, CANN toolkit package, and CANN ops package.

| Installation Method | Usage Instructions | Usage Scenario |
| ----- | ------ | ------ |
| WebIDE | One-stop development platform that provides an online directly runnable Ascend environment without manual installation. Currently provides single machine computing power and **installs the latest commercial release CANN package by default**. | Suitable for developers without Ascend devices.|
| Docker | Docker image is an efficient deployment method that pre-integrates CANN packages and necessary dependencies. Currently only applicable to Atlas A2 series products, OS only supports Ubuntu operating system. **Installs the latest commercial release CANN package by default**. |Suitable for developers with Ascend devices who need to quickly set up the environment.|
| Manual Installation | Follow [Method 3: Manual Installation](#section_manual_install) in this document for environment preparation |Suitable for developers with Ascend devices who want to experience manual CANN package installation or experience the latest master branch capabilities.|

### Method 1: WebIDE Environment

For developers without Ascend devices, you can directly use the WebIDE development platform, that is, the "One-stop Development Platform". This platform provides an online directly runnable Ascend environment. The environment has pre-installed necessary driver firmware, software packages, and dependencies without manual installation. For more information about the development platform, refer to [LINK](https://gitcode.com/org/cann/discussions/54).

1. Enter the open source project and click the "`Cloud Development`" button. Log in with a certified Huawei Cloud account. If not registered or certified, follow the page prompts to register and certify.

   <img src="../figures/cloudIDE.png" alt="Cloud Platform"  width="750px" height="90px">

2. Follow the page prompts to create and start the cloud development environment. Click "`Connect > WebIDE`" to enter the one-stop development platform. The open source project source code resources are in the `/mnt/workspace` directory by default.

   <img src="../figures/webIDE.png" alt="Cloud Platform"  width="1000px" height="150px">

After environment deployment completes, continue with the following steps:

1. **Install Python Dependencies**

   The WebIDE environment has pre-installed core dependencies. If other libraries are missing when running UT, execute the following command to supplement:
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Verify Environment**

   Refer to the [Environment Verification](#environment-verification) section to confirm that the environment and driver are normal.


### Method 2: Docker Deployment

For developers who do not depend on Ascend devices, if you want to quickly set up an Ascend environment, you can use Docker image deployment.

> **Note**: The image file is relatively large and requires some time to download. Please wait patiently. For docker command option descriptions, query through `docker --help`.

1.**Download Image**

- Step 1: Log in to the host machine as root user. Ensure the host machine has installed Docker engine (version 1.11.2 or higher).
- Step 2: Pull the image that pre-integrates CANN software packages and development dependencies from the [Ascend Image Repository](https://www.hiascend.com/developer/ascendhub/detail/17da20d1c2b6493cb38765adeba85884). The command is as follows. Choose according to the actual architecture:

    ```bash
    # Example: Pull ARM architecture CANN development image
    docker pull --platform=arm64 swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10
    # Example: Pull X86 architecture CANN development image
    docker pull --platform=amd64 swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10
    ```

2.**Run Docker**
After pulling the image, start the container with specific parameters.

```bash
docker run --name oam-tools -it swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10 bash
```
| Parameter | Description | Notes |
| :--- | :--- | :--- |
| `--name oam-tools` | Specify a name for the container for easy management. | Can be customized. |
| `-it` | Combination of `-i` (interactive) and `-t` (allocate pseudo-terminal). | - |
| `swr.cn-south-1.myhuaweicloud.com/ascendhub/cann:8.5.0-910b-ubuntu22.04-py3.10` | Specify the Docker image to run. |Ensure that this image name and tag match exactly with the image you pulled through `docker pull`. |
| `bash` | Command to execute immediately after container starts. | - |

3.**Initialize Environment**
After entering the container, execute the following command to initialize the environment:

```bash
curl -fsSL https://raw.gitcode.com/cann/oam-tools/raw/master/init_env.sh | bash
```

After environment deployment completes, continue with the following steps:

1. **Install Python Dependencies**

   ```bash
   pip3 install -r requirements.txt
   ```

   > Note: init_env.sh has installed pytest, coverage, and other core dependencies. This command ensures all dependencies are complete.

2. **Verify Environment**

   Refer to the [Environment Verification](#environment-verification) section to confirm that the environment and driver are normal.

<a id="section_manual_install"></a>
### Method 3: Manual Installation

For developers with Ascend devices, if you want to manually set up an Ascend environment, refer to the following steps.

#### Prerequisites

    The dependencies used for compiling this project source code are as follows. Note the version requirements.

    - python >= 3.12.0
    - gcc >= 7.3.0
    - cmake >= 3.16.0
    - ccache
    - CANN toolkit package: `Ascend-cann-toolkit_${cann_version}_linux-${arch}.run`
    - CANN ops package: `Ascend-cann-${chip_type}-ops_${cann_version}_linux-${arch}.run`
    - protobuf >= 25.1
    - abseil >= 20230802.1
    - json >= 3.11.3
    - patch >= 2.7.6
    - coverage (only required when running UT, recommended version 7.13.2)
    - googletest (only required when running UT, recommended version 1.14.0)
    - mockcpp (only required when running UT, recommended version 2.7)
    - pytest (only required when running UT, recommended version 9.0.2)
    - pytest-mock (only required when running UT, recommended version 3.15.1)
    
	Where:
    - $\{chip\_type\}: Indicates the Ascend AI processor model (equivalent to `${soc_name}` below), used to compose the CANN ops package name. Run `npu-smi info` and read the `Name` column to identify the chip on this machine, then pick the matching ops package from the table below.
    - $\{cann\_version\}: Indicates the CANN package version number. Must match the Toolkit package version number.
    - $\{arch\}: Indicates the CPU architecture, such as aarch64, x86_64.

Currently supported chip models and their CANN ops packages:

| `npu-smi info` Name column | Applicable products | `${chip_type}` / `${soc_name}` | CANN ops package |
| --- | --- | --- | --- |
| `910B` | Atlas A2 training series / Atlas 800I A2 inference products | `910b` | `Ascend-cann-910b-ops_${cann_version}_linux-${arch}.run` |
| `910_93` | Atlas A3 training series / Atlas A3 inference series (the commercial name "910C" maps here) | `910_93` | `Ascend-cann-910_93-ops_${cann_version}_linux-${arch}.run` |
| `950` | Atlas 950 series products | `950` | `Ascend-cann-950-ops_${cann_version}_linux-${arch}.run` |

> **Notes**
> - The Name column values above are the keywords this tool recognizes. `npu-smi info` may print a string with sub-model suffixes (e.g. `910B1` / `910B2` / `910B3` / `910B4` for the `910B` family); matching is by "Name column contains the keyword".
> - "910C" is a commercial alias and corresponds to `910_93` in package names. There is no `910c` / `910_c` spelling in the download links.
> - The actual ops package filename and available versions follow the [CANN download page](https://www.hiascend.com/cann/download). Only the three chip families above are supported; please open an issue for any other chip you'd like added.

#### Software Installation

1. **Install Driver and Firmware (Runtime Dependency)**

    For driver and firmware download and installation operations, refer to the "Prepare Software Packages" and "Install NPU Driver and Firmware" chapters in the [CANN Software Installation Guide](https://www.hiascend.com/document/redirect/CannCommunityInstWizard). Driver and firmware are runtime dependencies. If you only compile operators, you do not need to install them.

2. **Install CANN Packages**

    - **Scenario 1: Experience master version capabilities or develop based on master version**

        Click [Download Link](https://ascend.devcloud.huaweicloud.com/artifactory/cann-run-mirror/software/master/) to select the latest time version. Download the corresponding package according to product model and environment architecture. The installation command is as follows. For more guidance, refer to the [CANN Software Installation Guide](https://www.hiascend.com/document/redirect/CannCommunityInstWizard).

        1. Install CANN toolkit package

            ```bash
            # Ensure the installation package has executable permissions
            chmod +x Ascend-cann-toolkit_${cann_version}_linux-${arch}.run
            # Installation command
            ./Ascend-cann-toolkit_${cann_version}_linux-${arch}.run --install --install-path=${install_path}
            ```

        2. Install CANN ops package (runtime dependency)

            The ops package is a runtime dependency. If you only compile operators, you do not need to install this package.

            ```bash
            # Ensure the installation package has executable permissions
            chmod +x Ascend-cann-${soc_name}-ops_${cann_version}_linux-${arch}.run
            # Installation command
            ./Ascend-cann-${soc_name}-ops_${cann_version}_linux-${arch}.run --install --install-path=${install_path}
            ```

        - $\{cann\_version\}: Indicates the CANN package version number.
        - $\{arch\}: Indicates the CPU architecture, such as aarch64, x86_64.
        - $\{soc\_name\}: Indicates the NPU model name, equivalent to `${chip_type}` above. See the "supported chip models and CANN ops packages" table in the [Prerequisites](#prerequisites) section for valid values.
        - $\{install\_path\}: Indicates the specified installation path. The ops package must be installed in the same path as the toolkit package. For root user, the default installation is in the `/usr/local/Ascend` directory.

    - **Scenario 2: Experience released version capabilities or develop based on released version**

        Visit the [CANN Official Download Center](https://www.hiascend.com/cann/download), select the release version (only supports CANN 8.5.0 and subsequent versions), and download the corresponding package according to product model and environment architecture. Finally, complete the installation following the commands provided on the webpage.

After environment deployment completes, continue with the following steps:

1. **Install Python Dependencies**

   The manual installation environment requires you to configure Python dependencies yourself. Execute the following command to install the core packages required for UT:
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Verify Environment**

   Refer to the [Environment Verification](#environment-verification) section to confirm that the environment and driver are normal.

## Source Code Download

The source code download command is as follows. Replace `${branch}` with the target branch tag name. For the relationship between source code branch tags and CANN versions, refer to the [release repository](https://gitcode.com/cann/release-management).

```bash
# Download project corresponding branch source code
git clone -b ${branch} https://gitcode.com/cann/oam-tools.git
```

For WebIDE or Docker environments, the latest commercial release version project source code is provided by default. If you need to obtain source code for other versions, you also need to download the source code through the above command.

> Note
> - When using the HTTPS protocol on the gitcode platform, configure and use a personal access token instead of the login password for clone, push, and other operations.
> - If your build environment cannot access the network and cannot download code through git commands, first download the source code in a networked environment, then manually upload it to the target environment.

<a id="offline-build-environment-preparation"></a>
## Offline Build Environment Preparation

If your build environment cannot access the network, you need to manually download third-party libraries, closed-source binary packages, and subrepositories in a networked environment, then manually upload them to your build environment.

### Download Dependency Packages

Run the download script in a networked environment. This script directly downloads and saves the above third-party libraries, closed-source binary packages, and subrepositories in the path where the command is executed. (Downloading subrepositories requires a git environment and [configure gitcode personal access token](https://gitcode.com/setting/token-classic) to ensure git clone can execute correctly)

```bash
# Save files in the current execution path. You can execute the command in different paths (need to modify the script relative path or use absolute path) to change the save location
python cmake/download_libs.py
```

### Upload Dependency Packages

Create a new `third_party_path` directory in the build environment to store third-party open source software and closed-source software
```bash
mkdir -p ${third_party_path}
```

After creating the directory, upload the downloaded third-party libraries, closed-source binary packages, and subrepositories to the `third_party_path` directory.

### Dependency Package List

Third-party libraries, closed-source binary packages, and subrepositories include:
| Open Source Software | Version | Download Address |
|---|---|---|
|protobuf|v25.1|[protobuf-25.1.tar.gz](https://gitcode.com/cann-src-third-party/protobuf/releases/download/v25.1/protobuf-25.1.tar.gz)|
|makeself|2.5.0|[makeself-release-2.5.0-patch1.tar.gz](https://gitcode.com/cann-src-third-party/makeself/releases/download/release-2.5.0-patch1.0/makeself-release-2.5.0-patch1.tar.gz)|
|abseil-cpp|20230802.1|[abseil-cpp-20230802.1.tar.gz](https://gitcode.com/cann-src-third-party/abseil-cpp/releases/download/20230802.1/abseil-cpp-20230802.1.tar.gz)|
|boost|v1.87.0|[boost_1_87_0.tar.gz](https://gitcode.com/cann-src-third-party/boost/releases/download/v1.87.0/boost_1_87_0.tar.gz)|
|gtest|1.14.0|[googletest-1.14.0.tar.gz](https://gitcode.com/cann-src-third-party/googletest/releases/download/v1.14.0/googletest-1.14.0.tar.gz)|
|mockcpp-patch|2.7-h2|[mockcpp-2.7_py3.patch](https://gitcode.com/cann-src-third-party/mockcpp/releases/download/v2.7-h2/mockcpp-2.7_py3.patch)|
|mockcpp|2.7-h2|[mockcpp-2.7.tar.gz](https://gitcode.com/cann-src-third-party/mockcpp/releases/download/v2.7-h2/mockcpp-2.7.tar.gz)|

| Closed-source Binary | Version | Download Address |
|---|---|---|
|cann-oam-tools-release-x86_64.tar.gz|20260213(Stable)|[Download](https://ascend-cann.obs.cn-north-4.myhuaweicloud.com/CANN/20260213_newest/cann-oam-tools-release-x86_64.tar.gz)|
|cann-oam-tools-release-aarch64.tar.gz|20260213(Stable)|[Download](https://ascend-cann.obs.cn-north-4.myhuaweicloud.com/CANN/20260213_newest/cann-oam-tools-release-aarch64.tar.gz)|

| Subrepository | Version | Download Address |
|---|---|---|
|msprobe|master|https://gitcode.com/Ascend/msprobe|
|msprof|master|https://gitcode.com/Ascend/msprof|
|cann-cmake|master-002|[cmake-master-002.tar.gz](https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/cmake/cmake-master-002.tar.gz) |

<a id="environment-verification"></a>
## Environment Verification

After installing CANN packages, verify whether the environment and driver are normal.

- **Check NPU Device**

    ```bash
    # Run npu-smi. If device information displays normally, the driver is normal
    npu-smi info
    ```

    Note the `Name` column in the output and cross-reference it with the "supported chip models and CANN ops packages" table in the [Prerequisites](#prerequisites) section to confirm the chip on this machine matches the installed CANN ops package. If the `Name` column is not in the table, the chip is not yet supported by this tool — please open an issue.
- **Check CANN Installation**

    ```bash
    # View CANN toolkit package version information (default path installation). For WebIDE scenarios, replace /usr/local with /home/developer
    cat /usr/local/Ascend/cann/${arch}-linux/ascend_toolkit_install.info
    # View CANN ops package version information (default path installation). For WebIDE scenarios, replace /usr/local with /home/developer
    cat /usr/local/Ascend/cann/${arch}-linux/ascend_ops_install.info
    ```

- **Check Python Dependencies**

    ```bash
    # Check pytest version
    pytest --version
    # Check coverage version
    coverage --version
    ```
    
    > If the command execution fails, execute `pip3 install -r requirements.txt` to install dependencies.

## Environment Variable Configuration

Choose the appropriate command according to your needs to make environment variables effective.
```bash
# Default path installation, using root user as example (for non-root user, replace /usr/local with ${HOME})
source /usr/local/Ascend/cann/set_env.sh
# Specified path installation
# source ${install_path}/cann/set_env.sh
```