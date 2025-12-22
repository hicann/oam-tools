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

#ifndef ANALYSIS_DVVP_JOB_WRAPPER_PROF_TS_JOB_H
#define ANALYSIS_DVVP_JOB_WRAPPER_PROF_TS_JOB_H

#include "prof_comm_job.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {
using namespace analysis::dvvp::common::config;

class ProfTscpuJob : public ProfDrvJob {
public:
    ProfTscpuJob();
    ~ProfTscpuJob() override;
    int32_t Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override;
    int32_t Process() override;
    int32_t Uninit() override;
};

class ProfFmkJob : public ProfDrvJob {
public:
    ProfFmkJob();
    ~ProfFmkJob() override;
    int32_t Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override;
    int32_t Process() override;
    int32_t Uninit() override;
};

class ProfTsTrackJob : public ProfDrvJob {
public:
    ProfTsTrackJob();
    ~ProfTsTrackJob() override;
    int32_t Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override;
    int32_t Process() override;
    int32_t Uninit() override;

protected:
    analysis::dvvp::driver::AI_DRV_CHANNEL channelId_;
};

class ProfAivTsTrackJob : public ProfTsTrackJob {
public:
    ProfAivTsTrackJob();
    ~ProfAivTsTrackJob() override;
    int32_t Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override;
};

}
}
}
#endif