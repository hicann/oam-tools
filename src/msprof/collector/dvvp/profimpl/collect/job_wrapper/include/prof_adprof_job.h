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

#ifndef ANALYSIS_DVVP_JOB_WRAPPER_PROF_ADPROF_H
#define ANALYSIS_DVVP_JOB_WRAPPER_PROF_ADPROF_H
#include <atomic>
#include "tsd/tsd_client.h"
#include "prof_comm_job.h"
#include "prof_drv_event.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {
using TsdCapabilityGetFunc = uint32_t (*)(const uint32_t logicDeviceId, const int32_t type, const uint64_t ptr);
using TsdProcessOpenFunc = uint32_t (*)(uint32_t logicDeviceId, ProcOpenArgs *openArgs);
using TsdGetProcListStatusFunc = uint32_t (*)(const uint32_t logicDeviceId, ProcStatusParam *pidInfo,
                                              const uint32_t arrayLen);
using ProcessCloseSubProcListFunc = uint32_t (*)(const uint32_t logicDeviceId, const ProcStatusParam *closeList,
                                                 const uint32_t listSize);

class ProfAdprofJob : public ProfDrvJob {
public:
    ProfAdprofJob();
    ~ProfAdprofJob() override;
    int32_t Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override;
    int32_t Process() override;
    int32_t Uninit() override;

private:
    int32_t InitAdprof();
    int32_t LoadTsdApi();
    void BuildSysProfCmdArg(ProcOpenArgs &procOpenArgs);
    void CloseAdprof() const;

private:
    analysis::dvvp::driver::AI_DRV_CHANNEL channelId_;
    ProcStatusParam procStatusParam_;
    struct TaskEventAttr eventAttr_;
    std::atomic<uint8_t> processCount_;
    uint32_t phyId_;
    ProfDrvEvent profDrvEvent_;
    VOID_PTR tsdLibHandle_ = nullptr;
    TsdCapabilityGetFunc tsdCapabilityGet_{nullptr};
    TsdProcessOpenFunc tsdProcessOpen_{nullptr};
    TsdGetProcListStatusFunc tsdGetProcListStatus_{nullptr};
    ProcessCloseSubProcListFunc processCloseSubProcList_{nullptr};
    std::vector<std::string> cmdVec_;
    std::vector<ProcExtParam> params_;
};
}
}
}
#endif