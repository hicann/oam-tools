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
#include "ai_drv_dev_api.h"
#include <set>
#include "errno/error_code.h"
#include "msprof_dlog.h"
#include "ascend_hal.h"
#include "config_manager.h"

namespace analysis {
namespace dvvp {
namespace driver {
using namespace analysis::dvvp::common::error;
using namespace Analysis::Dvvp::Common::Config;

int32_t DrvGetAivNum(uint32_t deviceId, int64_t &aivNum)
{
    const std::set<PlatformType> unsupportTypeSet{PlatformType::CLOUD_TYPE, PlatformType::DC_TYPE};
    auto type = ConfigManager::instance()->GetPlatformType();
    if (unsupportTypeSet.find(type) != unsupportTypeSet.cend()) {
        aivNum = 0;
        MSPROF_LOGI("Driver doesn't support DrvGetAivNum by halGetDeviceInfo interface");
        return PROFILING_SUCCESS;
    }
    drvError_t ret = halGetDeviceInfo(deviceId, static_cast<int32_t>(MODULE_TYPE_VECTOR_CORE),
    static_cast<int32_t>(INFO_TYPE_CORE_NUM), &aivNum);
    if (ret == DRV_ERROR_NOT_SUPPORT) {
        MSPROF_LOGW("Driver doesn't support DrvGetAivNum by halGetDeviceInfo interface, "
            "deviceId=%u, ret=%d", deviceId, static_cast<int32_t>(ret));
        return PROFILING_SUCCESS;
    } else if (ret != DRV_ERROR_NONE) {
        MSPROF_LOGE("Failed to DrvGetAivNum, deviceId=%u, ret=%d", deviceId, static_cast<int32_t>(ret));
        MSPROF_CALL_ERROR("EK9999", "Failed to DrvGetAivNum, deviceId=%u, ret=%d",
            deviceId, static_cast<int32_t>(ret));
        return PROFILING_FAILED;
    }

    MSPROF_LOGI("Succeeded to DrvGetAivNum, deviceId=%u, aivNum=%lld", deviceId, aivNum);
    return PROFILING_SUCCESS;
}
}  // namespace driver
}  // namespace dvvp
}  // namespace analysis
