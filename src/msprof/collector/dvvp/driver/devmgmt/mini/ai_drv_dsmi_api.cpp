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

#include "ai_drv_dsmi_api.h"
#include <cerrno>
#include <map>
#include "errno/error_code.h"
#include "config/config_manager.h"
namespace Analysis {
namespace Dvvp {
namespace Driver {
using namespace Analysis::Dvvp::Common::Config;
using namespace analysis::dvvp::common::error;

int32_t DrvGetAicoreInfo(int32_t deviceId, int64_t &freq)
{
    if (deviceId < 0) {
        return PROFILING_FAILED;
    }
    MSPROF_LOGD("DrvGetAicoreInfo Freq %u", freq);
    return PROFILING_SUCCESS;
}

std::string DrvGeAicFrq(int32_t deviceId)
{
    MSPROF_LOGD("DrvGeAicFrq devId %d", deviceId);
    const std::string defAicFrq = Analysis::Dvvp::Common::Config::ConfigManager::instance()->GetAicDefFrequency();
    return defAicFrq;
}
}}}
