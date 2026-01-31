/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
#include "mdc_lite_platform.h"

namespace Dvvp {
namespace Collect {
namespace Platform {
constexpr char LITE_PIPEUTILIZATION[] = "0x500,0x301,0x1,0x701,0x202,0x203,0x34,0x35";
constexpr char LITE_PIPELINEEXECUTEUTILIZATION[] = "0x500,0x301,0x1,0x701,0x202,0x203,0x714";
constexpr char LITE_MEMORY[] = "0x404,0x406,0x566,0x567,0x707,0x709";
constexpr char LITE_MEMORYL0[] = "0x304,0x702,0x306,0x703,0x712,0x30a,0x308";
constexpr char LITE_MEMORYUB[] = "0x3,0x5,0x70c,0x206,0x204,0x57b,0x57c";
constexpr char LITE_AIRTHMETICUTILIZATION[] = "0x302,0x303";
constexpr char LITE_RESOURCECONFLICTRATIO[] = "0x54f,0x551,0x552,0x561,0x563,0x564,0x557";
constexpr char LITE_L2CACHEEVENT[] = "0x78,0x79,0x77,0x71,0x6a,0x6c,0x74,0x62";

PLATFORM_REGISTER(CHIP_MDC_LITE, MdcLitePlatform);
MdcLitePlatform::MdcLitePlatform()
{
    supportedFeature_ = {
        // TASK
        PLATFORM_TASK_ASCENDCL,
        PLATFORM_TASK_AIC_METRICS,
        PLATFORM_TASK_GE_API,
        PLATFORM_TASK_HCCL,
        PLATFORM_TASK_L2_CACHE_REG,
        PLATFORM_TASK_MSPROFTX,
        PLATFORM_TASK_RUNTIME_API,
        PLATFORM_TASK_SWITCH,
        PLATFORM_TASK_TRACE,
        PLATFORM_TASK_TSFW,
        PLATFORM_TASK_TS_MEMCPY,
        PLATFORM_TASK_TS_KEYPOINT,
        PLATFORM_TASK_TRAINING_TRACE,
        PLATFORM_TASK_METRICS,
        PLATFORM_TASK_MEMORY,
        // PMU
        PLATFORM_TASK_AU_PMU,
        PLATFORM_TASK_PU_PMU,
        PLATFORM_TASK_PEU_PMU,
        PLATFORM_TASK_MEMORY_PMU,
        PLATFORM_TASK_MEMORYL0_PMU,
        PLATFORM_TASK_MEMORYUB_PMU,
        PLATFORM_TASK_RCR_PMU,
        // Device
        PLATFORM_SYS_DEVICE_NPU_MODULE_MEM,
        PLATFORM_SYS_DEVICE_DVPP_EX,
        PLATFORM_SYS_DEVICE_DDR,
        PLATFORM_SYS_DEVICE_HBM,
        PLATFORM_SYS_DEVICE_LLC
    };
}

std::string MdcLitePlatform::GetPipeUtilizationMetrics()
{
    return LITE_PIPEUTILIZATION;
}

std::string MdcLitePlatform::GetPipelineExecuteUtilizationMetrics()
{
    return LITE_PIPELINEEXECUTEUTILIZATION;
}

std::string MdcLitePlatform::GetMemoryMetrics()
{
    return LITE_MEMORY;
}

std::string MdcLitePlatform::GetMemoryL0Metrics()
{
    return LITE_MEMORYL0;
}

std::string MdcLitePlatform::GetMemoryUBMetrics()
{
    return LITE_MEMORYUB;
}

std::string MdcLitePlatform::GetArithmeticUtilizationMetrics()
{
    return LITE_AIRTHMETICUTILIZATION;
}

std::string MdcLitePlatform::GetResourceConflictRatioMetrics()
{
    return LITE_RESOURCECONFLICTRATIO;
}

std::string MdcLitePlatform::GetL2CacheEvents()
{
    return LITE_L2CACHEEVENT;
}
}
}
}