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

#ifndef ANALYSIS_DVVP_JOB_WRAPPER_PROF_HARDWARE_MEM_H
#define ANALYSIS_DVVP_JOB_WRAPPER_PROF_HARDWARE_MEM_H
#include "prof_comm_job.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {
class ProfDdrJob : public ProfPeripheralJob {
public:
    ProfDdrJob();
    ~ProfDdrJob() override;
    int32_t Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override;
    int32_t SetPeripheralConfig() override;
};

class ProfHbmJob : public ProfPeripheralJob {
public:
    ProfHbmJob();
    ~ProfHbmJob() override;
    int32_t Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override;
    int32_t SetPeripheralConfig() override;
};

class ProfAppMemJob : public ProfPeripheralJob {
public:
    ProfAppMemJob();
    ~ProfAppMemJob() override;
    int32_t Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override;
    int32_t SetPeripheralConfig() override;
};

class ProfDevMemJob : public ProfPeripheralJob {
public:
    ProfDevMemJob();
    ~ProfDevMemJob() override;
    int32_t Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override;
    int32_t SetPeripheralConfig() override;
};

class ProfAiStackMemJob : public ProfPeripheralJob {
public:
    ProfAiStackMemJob();
    ~ProfAiStackMemJob() override;
    int32_t Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override;
    int32_t SetPeripheralConfig() override;
};

class ProfLlcJob : public ProfPeripheralJob {
public:
    ProfLlcJob();
    ~ProfLlcJob() override;
    int32_t Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override;
    int32_t SetPeripheralConfig() override;
    bool IsGlobalJobLevel() override;
};

constexpr size_t MAX_QOS_STREAM_COLLECT = 8;
class ProfQosJob : public ProfPeripheralJob {
public:
    ProfQosJob();
    ~ProfQosJob() override;
    int32_t Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override;
    int32_t SetPeripheralConfig() override;
};
}
}
}

#endif
