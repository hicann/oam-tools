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
#include "platform.h"
#include "errno/error_code.h"
#include "ai_drv_dev_api.h"
#include "platform/platform.h"
#include "logger/msprof_dlog.h"
#include "config_manager.h"

namespace Analysis {
namespace Dvvp {
namespace Common {
namespace Platform {
using namespace analysis::dvvp::common::error;
using namespace Analysis::Dvvp::Common::Config;
using namespace analysis::dvvp::common::utils;
using namespace analysis::dvvp::common::config;

const std::string ASCEND_HAL_LIB = "libascend_hal.so";
constexpr uint32_t SUPPORT_ADPROF_VERSION = 0x72316;   // driver supported version 0x72316

bool Platform::CheckIfSupportAdprof(uint32_t deviceId) const
{
    if (deviceId == DEFAULT_HOST_ID) {
        return false;
    }

    if (DrvGetApiVersion() < SUPPORT_ADPROF_VERSION || GetPlatformType() == CHIP_MINI) {
        MSPROF_LOGI("Current version not support driver channel.");
        return false;
    }
    constexpr uint32_t vmngNormalNoneSplitMode = 0;
    uint32_t mode = 0;
    int32_t ret = ascendHalAdaptor_.DrvGetDeviceSplitMode(deviceId, &mode);
    if (ret != DRV_ERROR_NONE) {
        MSPROF_LOGE("Call drvGetDeviceSplitMode failed, return:%d.", ret);
        return false;
    }
    if ((GetPlatformType() == CHIP_DC || GetPlatformType() == CHIP_CLOUD) &&
        mode != vmngNormalNoneSplitMode) {
        MSPROF_LOGI("This chip not support driver channel in split mode.");
        return false;
    }

    return true;
}
}
}
}
}