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

#ifndef ANALYSIS_DVVP_JOB_WRAPPER_PROF_AICPU_H
#define ANALYSIS_DVVP_JOB_WRAPPER_PROF_AICPU_H
#include <atomic>
#include "prof_comm_job.h"
#include "prof_drv_event.h"
#include "osal.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {

class ProfAicpuJob : public ProfDrvJob {
public:
    ProfAicpuJob();
    ~ProfAicpuJob() override;
    int32_t Process() override;
    int32_t Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override;
    int32_t Uninit() override;

protected:
    bool CheckAicpuSwitch(void);
    bool CheckMC2Switch(void);
    bool CheckChannelSwitch(void);

protected:
    analysis::dvvp::driver::AI_DRV_CHANNEL channelId_;
    std::string eventGrpName_;
    struct TaskEventAttr eventAttr_;
    std::atomic<uint8_t> processCount_;
    ProfDrvEvent profDrvEvent_;
};

class ProfAiCustomCpuJob : public ProfAicpuJob {
public:
    ProfAiCustomCpuJob();
};

}  // namespace JobWrapper
}
}
#endif