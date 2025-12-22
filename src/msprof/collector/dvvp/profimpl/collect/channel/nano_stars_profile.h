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

#ifndef DVVP_COLLECT_JOB_WRAPPER_STARS_NANO_PROFILE_H
#define DVVP_COLLECT_JOB_WRAPPER_STARS_NANO_PROFILE_H
#include "channel_job.h"
namespace Dvvp {
namespace Collect {
namespace JobWrapper {
constexpr uint8_t NANO_PMU_EVENT_MAX_NUM = 10;
struct TagNanoStarsProfileConfig {
    uint32_t tag = 0;                                  // 0-enable immediately, 1-enable delay
    uint32_t eventNum = 0;                             // PMU count
    uint16_t event[NANO_PMU_EVENT_MAX_NUM] = {0};      // PMU value
};
class NanoStarsProfile : public ChannelJob {
public:
    NanoStarsProfile()
        : ChannelJob(static_cast<uint32_t>(
        analysis::dvvp::driver::AI_DRV_CHANNEL::PROF_CHANNEL_STARS_NANO_PROFILE),
        "nano_stars_profile.data") {}
    ~NanoStarsProfile() override {}
    int32_t Init(const SHARED_PTR_ALIA<Analysis::Dvvp::JobWrapper::CollectionJobCfg> cfg) override;
    int32_t Process() override;
    int32_t Uninit() override;
    void PackPmuParam(TagNanoStarsProfileConfig &config) const;
};
}
}
}
#endif
