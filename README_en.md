# oam-tools

## Overview

The oam-tools (Operations, Administration, and Maintenance) project provides fault diagnosis tools and performance testing and tuning tools for developers. The project includes capabilities such as fault information collection, software and hardware information display, AI core error analysis, and AI task performance collection and analysis. These capabilities improve the efficiency of fault diagnosis and AI task performance analysis.

## 🧩 Supported Hardware

Before setting up the environment, confirm that your hardware is within the supported scope of this tool.

- **CPU architecture**: `aarch64`, `x86_64`
- **Ascend AI processors**:

  | `npu-smi info` Name column | Applicable products | CANN ops package keyword |
  | --- | --- | --- |
  | `910B` | Atlas A2 training series / Atlas 800I A2 inference products | `910b` |
  | `910_93` | Atlas A3 training series / Atlas A3 inference series (the commercial name "910C" maps here) | `910_93` |
  | `950` | Atlas 950 series products | `950` |

  > - `npu-smi info` may print sub-model suffixes (e.g. `910B1` / `910B2` / `910B3` / `910B4`); matching is by "Name column contains the keyword".
  > - "910C" is a commercial alias; package names use `910_93`. There is no `910c` / `910_c` spelling.
  > - Other chips are not yet supported — please open an issue. The full ops package naming convention and download instructions are in [Quick Install](docs/en/quick_install.md#method-3-manual-installation).

## Directory Structure

The key directory structure is as follows:

```
├── cmake                                          # Build configuration directory
├── scripts                                        # Auxiliary build files
├── src                                            # Source code for all modules
|   ├── asys                                       # asys module directory
|   ├── hccl_test                                  # hccl_test module directory
|   ├── msaicerr                                   # msaicerr module directory 
|   ├── msprof                                     # msprof module directory
|   ├── third_party                                # Third-party library headers
|   └── ......
├── test                                           # UT/ST test cases
├── CMakeLists.txt                                 # Build configuration file
├── build.sh                                       # Project build script
└── ......
```

## Environment Preparation

Complete the environment preparation by following the [Quick Installation](docs/en/quick_install.md) guide.

## Source Code Compilation

Run the following command to compile the project:

```bash
bash build.sh
```

To specify a third-party library path, use the `--cann_3rd_lib_path` parameter:

```bash
bash build.sh --cann_3rd_lib_path=${third_party_path}
```

Parameters:
- `--cann_3rd_lib_path`: The directory for storing third-party libraries. The default value is `./third_party`. If third-party libraries do not exist locally, the build script automatically downloads the source code of each third-party library from the gitcode open source repository.
- The build process automatically downloads closed-source binary packages that contain the libraries and header files required for normal operation. Only release versions are provided. **Even if the build option specifies debug, only the release version tar package is downloaded**.
- If the build environment cannot access the network, refer to [Offline Build Environment Preparation](docs/en/quick_install.md#offline-build-environment-preparation) to complete the download and configuration of dependency packages in advance. Then specify the dependency package directory through the `--cann_3rd_lib_path` parameter before running the build.
- For more build parameters, run `bash build.sh -h`.

After the build completes, the `build_out` directory generates a `cann-oam-tools_<cann_version>_linux-<arch>.run` software package, where `<cann_version>` is the version number and `<arch>` is the operating system architecture (possible values: `x86_64` or `aarch64`).

## Installation

Run the following command to install the compiled oam-tools software package:

```bash
./cann-oam-tools_<cann_version>_linux-<arch>.run --full --install-path=${install_path}
```

After installation completes, the user-compiled oam-tools software package replaces the oam-tools related software in the installed CANN development kit package.

> If your environment has a `grep` version greater than 3.8.0, a warning appears during installation, for example `grep: warning: stray \ before -`. This occurs because newer grep versions have stricter validation of expressions, but does not affect installation and usage.

## Verification

After compilation, users can verify whether the project functions work properly.

> Python dependency installation is handled in [Environment Preparation](docs/en/quick_install.md). No additional operations are required.

Compile and run test cases:

```bash
bash build.sh -u
```

To test a specific component, use the `--component` parameter:

Possible values: `asys` (fault information collection), `msaicerr` (AI Core Error analysis), `msprof` (performance tuning), `all` (all components, default)

```bash
bash build.sh -u --component msprof
```

The UT test case compilation output directory is `build`. To clear historical build records, run the following:

```bash
rm -rf build_out/ build/
```

## Pre-commit

Pre-commit is a framework for managing and maintaining Git pre-commit hooks. By automatically executing code checks, formatting, and security scans before code submission, pre-commit ensures code quality and unifies team standards. This significantly reduces CI/CD pipeline failures and improves collaboration efficiency.

This repository has configured pre-commit. Users can refer to [Chapter 3 of the pre-commit configuration guide](https://gitcode.com/cann/infrastructure/blob/main/docs/SC/pre-commit/pre-commit%E9%85%8D%E7%BD%AE%E6%8C%87%E5%AF%BC%E4%B9%A6.md#3-%E7%A4%BE%E5%8C%BA%E8%B4%A1%E7%8C%AE%E8%80%85%E4%BD%BF%E7%94%A8pre-commit%E8%83%BD%E5%8A%9B) in the CANN community to install pre-commit. The first installation requires configuring Java and Maven environments and building jar packages, which takes a relatively long time.

## Related Documentation

[asys Tool User Guide](https://hiascend.com/document/redirect/CannCommunityasys): Introduces the usage of the asys command-line tool, which supports fault information collection, business rerun with fault information collection, software and hardware and Device status information display, health check, comprehensive detection, component detection, trace file parsing/coredump file parsing/stackcore file parsing/coretrace file parsing, real-time stack export, environment configuration, and AI Core Error fault information parsing.

[msaicerr Tool User Guide](https://hiascend.com/document/redirect/CannCommunitymsaicerr): Introduces the usage of the msaicerr command-line tool for analyzing AI Core Error issues, parsing Dump files, and checking environments.

[Performance Tuning Tool User Guide](https://www.hiascend.com/document/redirect/CannCommunityToolProfiling): Introduces the usage of the msprof command-line tool. This tool guides users to collect and analyze key performance indicators of AI tasks running on Ascend AI processors at various running stages, enabling quick identification of software and hardware performance bottlenecks and improving AI task performance analysis efficiency.

[HCCL Performance Test Tool User Guide](https://www.hiascend.com/document/redirect/CannCommunityToolHcclTest): Introduces the usage of the hccl_test tool for testing collective communication functionality and performance in distributed training or inference scenarios.

## Related Information
- [Contributing Guide](CONTRIBUTING_en.md)
- [Security Statement](SECURITY_en.md)
- [License](LICENSE)