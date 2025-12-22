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

#ifndef ANALYSIS_DVVP_JOB_WRAPPER_PROF_SYS_INFO_JOB_H
#define ANALYSIS_DVVP_JOB_WRAPPER_PROF_SYS_INFO_JOB_H

#include "collection_register.h"
#include "transport/uploader.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {
using namespace analysis::dvvp::common::config;

class ProfSysInfoBase : public ICollectionJob {
public:
    ProfSysInfoBase()
        : sampleIntervalNs_(0)
    {
    }
    ~ProfSysInfoBase() override {}

protected:
    SHARED_PTR_ALIA<CollectionJobCfg> collectionJobCfg_;
    SHARED_PTR_ALIA<analysis::dvvp::transport::Uploader> uploader_;
    unsigned long long sampleIntervalNs_;
};

class ProfSysMemJob : public ProfSysInfoBase {
public:
    ProfSysMemJob();
    ~ProfSysMemJob() override;
    int32_t Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override;
    int32_t Process() override;
    int32_t Uninit() override;
    bool IsGlobalJobLevel() override
    {
        return true;
    }
};

class ProfAllPidsJob : public ProfSysInfoBase {
public:
    ProfAllPidsJob();
    ~ProfAllPidsJob() override;
    int32_t Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override;
    int32_t Process() override;
    int32_t Uninit() override;
    bool IsGlobalJobLevel() override
    {
        return true;
    }
};

class ProfSysStatJob : public ProfSysInfoBase {
public:
    ProfSysStatJob();
    ~ProfSysStatJob() override;
    int32_t Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg) override;
    int32_t Process() override;
    int32_t Uninit() override;
    bool IsGlobalJobLevel() override
    {
        return true;
    }
};
}
}
}
#endif