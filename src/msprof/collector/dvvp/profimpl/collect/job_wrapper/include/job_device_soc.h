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

#ifndef ANALYSIS_DVVP_JOB_DEVICE_SOC_H
#define ANALYSIS_DVVP_JOB_DEVICE_SOC_H

#include <array>
#include "collection_register.h"
#include "job_adapter.h"
#include "uploader_mgr.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {
class JobDeviceSoc : public JobAdapter {
public:
    explicit JobDeviceSoc(int32_t devIndexId);
    ~JobDeviceSoc() override;

public:
    int32_t StartProf(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params) override;
    int32_t StopProf(void) override;

private:
    int32_t CreateCollectionJobArray();
    int32_t CreateTsCollectionJobArray();
    int32_t CreateSysCollectionJobArray();
    int32_t DoCreateCollectionJobArray();
    int32_t RegisterCollectionJobs() const;
    void UnRegisterCollectionJobs();
    void StoreData(const std::string &path, const std::string &fileName);
    int32_t SendData(const std::string &fileName, const std::string &data);
    int32_t ParseTsCpuConfig(SHARED_PTR_ALIA<PMUEventsConfig> cfg);
    int32_t ParseAiCoreConfig(SHARED_PTR_ALIA<PMUEventsConfig> cfg);
    int32_t ParseAivConfig(SHARED_PTR_ALIA<PMUEventsConfig> cfg);
    int32_t ParseControlCpuConfig(SHARED_PTR_ALIA<PMUEventsConfig> cfg);
    int32_t ParseLlcConfig(SHARED_PTR_ALIA<PMUEventsConfig> cfg);
    int32_t ParseDdrCpuConfig(SHARED_PTR_ALIA<PMUEventsConfig> cfg);
    int32_t ParsePmuConfig(SHARED_PTR_ALIA<PMUEventsConfig> cfg);
    int32_t ParseHbmConfig(SHARED_PTR_ALIA<PMUEventsConfig> cfg);
    std::string GenerateFileName(const std::string &fileName);
    std::string GenerateDurationdata();
    void GetAndStoreStartTime(const int32_t &hostProfiling);
    int32_t StoreTime(const std::string &fileName, const std::string &startTime);
    int32_t StartProfHandle(SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params);

private:
    int32_t devIndexId_;
    bool isStarted_;
    std::string tmpResultDir_;
    std::string jobId_;
    SHARED_PTR_ALIA<analysis::dvvp::message::ProfileParams> params_;
    SHARED_PTR_ALIA<CollectionJobCommonParams> collectionJobCommCfg_;
    std::array<CollectionJobT, NR_MAX_COLLECTION_JOB> collectionJobV_;
};
}}}
#endif
