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
#include "file_ageing.h"
#include <sys/types.h>
#include "config/config.h"
#include "config_manager.h"
#include "logger/msprof_dlog.h"
#include "utils/utils.h"

namespace analysis {
namespace dvvp {
namespace transport {
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::config;
using namespace analysis::dvvp::common::utils;
using namespace Analysis::Dvvp::Common::Config;
constexpr uint64_t MOVE_BIT = 20;
constexpr uint64_t STORAGE_RESERVED_VOLUME = (STORAGE_LIMIT_DOWN_THD / 10) << MOVE_BIT;

int32_t FileAgeing::Init()
{
    if (ConfigManager::instance()->GetPlatformType() == PlatformType::MINI_TYPE) {
        MSPROF_LOGW("platform type is MINI_TYPE, not support file ageing");
        return PROFILING_SUCCESS;
    }

    unsigned long long totalVolume = 0;
    if (Utils::GetVolumeSize(storageDir_, totalVolume, VolumeSize::TOTAL_SIZE) == PROFILING_FAILED) {
        MSPROF_LOGE("Get totalVolume failed, storageDir_:%s, storage_limit:%s",
            Utils::BaseName(storageDir_).c_str(), storageLimit_.c_str());
        return PROFILING_FAILED;
    }

    unsigned long long availableVolume = 0;
    if (Utils::GetVolumeSize(storageDir_, availableVolume, VolumeSize::AVAIL_SIZE) == PROFILING_FAILED) {
        MSPROF_LOGE("Get availableVolume failed, storageDir_:%s, storage_limit:%s",
            Utils::BaseName(storageDir_).c_str(), storageLimit_.c_str());
        return PROFILING_FAILED;
    }

    uint64_t limit = GetStorageLimit();
    if (limit == 0) {
        limit = availableVolume;
        MSPROF_LOGI("limit is 0, set default value which equal to available volume");
        if (availableVolume < STORAGE_RESERVED_VOLUME) {
            MSPROF_LOGE("Available volume:%" PRIu64 " (%lluMB) less than 20MB. Data will not be collected.",
                availableVolume, (availableVolume >> MOVE_BIT));
            std::string errReason = "The available volume is less than 20MB. " +
                std::string("Data will not be collected. ") +
                "Please check the available disk space in current path and the related profiling configs";
            std::string errValue = std::to_string(availableVolume >> MOVE_BIT) + "MB";
            MSPROF_INPUT_ERROR("EK0003", std::vector<std::string>({"config", "value", "reason"}),
                std::vector<std::string>({"storage limit", errValue, errReason}));
            return PROFILING_FAILED;
        }
    } else {
        limit = (limit < totalVolume) ? limit : totalVolume;
    }

    InitAgeingParams(limit);
    return PROFILING_SUCCESS;
}
}
}
}