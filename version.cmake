# -----------------------------------------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# -----------------------------------------------------------------------------------------------------------

set_cann_package(oam-tools VERSION "9.2.0")

set_cann_build_dependencies(runtime ">=9.0")
set_cann_build_dependencies(metadef ">=9.0")

# no depend
set_cann_run_dependencies(runtime ">=9.0")
set_cann_run_dependencies(bisheng-compiler ">=9.0")
set_cann_run_dependencies(ops-cv ">=9.0")
set_cann_run_dependencies(ops-math ">=9.0")
set_cann_run_dependencies(ops-legacy ">=9.0")

# depend: runtime
set_cann_run_dependencies(metadef ">=9.0")

# depend: runtime, metadef
set_cann_run_dependencies(hcomm ">=9.0")

# depend: hcomm
set_cann_run_dependencies(hccl ">=9.0")
set_cann_run_dependencies(ge-executor ">=9.0")

# depend: ge-executor
set_cann_run_dependencies(ge-compiler ">=9.0")

# depend: ge-compiler
set_cann_run_dependencies(tbe-tik ">=9.0")

# depend: tbe-tik, bisheng-compiler
set_cann_run_dependencies(asc-devkit ">=9.0")

# depend: asc-devkit
set_cann_run_dependencies(graph-autofusion ">=9.0")

# depend: asc-devkit
set_cann_run_dependencies(opbase ">=9.0")

# depend: opbase
set_cann_run_dependencies(ops-nn ">=9.0")

# depend: ops-nn
set_cann_run_dependencies(ops-transformer ">=9.0")
