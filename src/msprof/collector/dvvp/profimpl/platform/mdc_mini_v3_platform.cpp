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
#include "mdc_mini_v3_platform.h"

namespace Dvvp {
namespace Collect {
namespace Platform {
PLATFORM_REGISTER(CHIP_MDC_MINI_V3, MdcMiniV3Platform);
MdcMiniV3Platform::MdcMiniV3Platform()
{
    const std::vector<PlatformFeature> unsupportFeature = {
        PLATFORM_TASK_AICPU,
        PLATFORM_TASK_BLOCK,
        PLATFORM_SYS_DEVICE_NIC,
        PLATFORM_TASK_AICORE_LPM,
        PLATFORM_TASK_DYNAMIC,
        PLATFORM_TASK_DELAY_DURATION,
    };
    for (PlatformFeature feature : unsupportFeature) {
        supportedFeature_.erase(feature);
    }
}
}
}
}