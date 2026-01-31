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
#ifndef DVVP_COLLECT_JOB_WRAPPER_CHANNEL_JOB_H
#define DVVP_COLLECT_JOB_WRAPPER_CHANNEL_JOB_H
#include "collection_job.h"

namespace Dvvp {
namespace Collect {
namespace JobWrapper {
constexpr int32_t STRING_TO_LONG_WEIGHT = 16;
struct ProfChannelParam {
    ProfChannelParam() : userData(nullptr), dataSize(0), period(0) {}
    void *userData;
    uint32_t dataSize;
    uint32_t period;
};

class ChannelJob : public Analysis::Dvvp::JobWrapper::ICollectionJob {
public:
    ChannelJob();
    ChannelJob(int32_t collectionId, const std::string &name);
    ~ChannelJob() override;
protected:
    int32_t ChannelStart(int32_t devId, int32_t channelId, const ProfChannelParam &param) const;
    void AddReader(int32_t devId, int32_t channelId, const std::string &filePath);
    void RemoveReader(int32_t devId, int32_t channelId) const;

    SHARED_PTR_ALIA<Analysis::Dvvp::JobWrapper::CollectionJobCfg> cfg_;
};
}
}
}
#endif
