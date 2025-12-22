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

#include "prof_inter_connection_job.h"
#include "ai_drv_prof_api.h"
#include "utils/utils.h"
#include "config/config.h"
#include "uploader_mgr.h"
#include "platform/platform.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {
using namespace analysis::dvvp::common::config;
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::utils;
using namespace Analysis::Dvvp::Common::Platform;

/**
 * @brief  : Collect HCCS profiling data
 */
ProfHccsJob::ProfHccsJob()
{
    channelId_ = PROF_CHANNEL_HCCS;
}

ProfHccsJob::~ProfHccsJob() {}

/**
 * @brief  : HCCS Peripheral Init profiling
 * @param [in] cfg: Collect data config information
 * @return : PROFILING_FAILED(-1) : failed
 *         : PROFILING_SUCCESS(0) : success
 */
int32_t ProfHccsJob::Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg)
{
    CHECK_JOB_COMMON_PARAM_RET(cfg, return PROFILING_FAILED);
    if (cfg->comParams->params->hostProfiling) {
        return PROFILING_FAILED;
    }
    collectionJobCfg_ = cfg;

    if (collectionJobCfg_->comParams->params->hccsProfiling.compare(MSVP_PROF_ON) != 0) {
        MSPROF_LOGI("HCCS Profiling not enabled");
        return PROFILING_FAILED;
    }

    std::vector<std::string> profDataFilePathV;
    profDataFilePathV.push_back(collectionJobCfg_->comParams->tmpResultDir);
    profDataFilePathV.push_back("data");
    profDataFilePathV.push_back("hccs.data");
    collectionJobCfg_->jobParams.dataPath = Utils::JoinPath(profDataFilePathV);
    samplePeriod_ = PERIPHERAL_INTERVAL_MS_MIN;
    if (collectionJobCfg_->comParams->params->hccsInterval >= PERIPHERAL_INTERVAL_MS_MIN &&
        collectionJobCfg_->comParams->params->hccsInterval <= PERIPHERAL_INTERVAL_MS_MAX) {
        samplePeriod_ = collectionJobCfg_->comParams->params->hccsInterval;
    }

    peripheralCfg_.configP = nullptr;
    peripheralCfg_.configSize = 0;
    return PROFILING_SUCCESS;
}

/**
 * @brief  : Collect PCIE profiling data
 */
ProfPcieJob::ProfPcieJob()
{
    channelId_ = PROF_CHANNEL_PCIE;
}

ProfPcieJob::~ProfPcieJob() {}

/**
 * @brief  : PCIE Peripheral Init profiling
 * @param [in] cfg: Collect data config information
 * @return : PROFILING_FAILED(-1) : failed
 *         : PROFILING_SUCCESS(0) : success
 */
int32_t ProfPcieJob::Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg)
{
    CHECK_JOB_COMMON_PARAM_RET(cfg, return PROFILING_FAILED);
    if (cfg->comParams->params->hostProfiling) {
        return PROFILING_FAILED;
    }
    collectionJobCfg_ = cfg;
    if (collectionJobCfg_->comParams->params->pcieProfiling.compare(MSVP_PROF_ON) != 0) {
        MSPROF_LOGI("PCIE Profiling not enabled");
        return PROFILING_FAILED;
    }

    std::vector<std::string> profDataFilePathV;
    profDataFilePathV.push_back(collectionJobCfg_->comParams->tmpResultDir);
    profDataFilePathV.push_back("data");
    profDataFilePathV.push_back("pcie.data");
    collectionJobCfg_->jobParams.dataPath = Utils::JoinPath(profDataFilePathV);

    samplePeriod_ = PERIPHERAL_INTERVAL_MS_MIN;
    if (collectionJobCfg_->comParams->params->pcieInterval >= PERIPHERAL_INTERVAL_MS_MIN &&
        collectionJobCfg_->comParams->params->pcieInterval <= PERIPHERAL_INTERVAL_MS_MAX) {
        samplePeriod_ = collectionJobCfg_->comParams->params->pcieInterval;
    }

    peripheralCfg_.configP = nullptr;
    peripheralCfg_.configSize = 0;
    return PROFILING_SUCCESS;
}

/**
 * @brief  : Collect ub profiling data
 */
ProfUbJob::ProfUbJob()
{
    channelId_ = PROF_CHANNEL_UB;
}

ProfUbJob::~ProfUbJob() {}

/**
 * @brief  : Ub Peripheral Init profiling
 * @param [in] cfg: Collect data config information
 * @return : PROFILING_FAILED(-1) : failed
 *         : PROFILING_SUCCESS(0) : success
 */
int32_t ProfUbJob::Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg)
{
    CHECK_JOB_COMMON_PARAM_RET(cfg, return PROFILING_FAILED);
    if (cfg->comParams->params->hostProfiling) {
        return PROFILING_FAILED;
    }
    collectionJobCfg_ = cfg;

    if (!Platform::instance()->CheckIfSupport(PLATFORM_SYS_DEVICE_UB)) {
        MSPROF_LOGI("Ub Profiling not support.");
        return PROFILING_FAILED;
    }

    if (collectionJobCfg_->comParams->params->ubProfiling.compare(MSVP_PROF_ON) != 0) {
        MSPROF_LOGI("Ub Profiling not enabled.");
        return PROFILING_FAILED;
    }

    samplePeriod_ = collectionJobCfg_->comParams->params->ubInterval;
    peripheralCfg_.configP = nullptr;
    peripheralCfg_.configSize = 0;
    return PROFILING_SUCCESS;
}
}
}
}