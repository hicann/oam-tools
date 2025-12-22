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

#include "prof_io_job.h"
#include "utils/utils.h"
#include "config/config.h"
#include "uploader_mgr.h"
#include "ai_drv_prof_api.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {
using namespace analysis::dvvp::common::config;
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::utils;

/*
 * @berif  : Collect NIC profiling data
 */
ProfNicJob::ProfNicJob()
{
    channelId_ = PROF_CHANNEL_NIC;
}

ProfNicJob::~ProfNicJob() {}

/*
 * @berif  : NIC Peripheral Init profiling
 * @param  : cfg : Collect data config information
 * @return : PROFILING_FAILED(-1) : failed
 *         : PROFILING_SUCCESS(0) : success
 */
int32_t ProfNicJob::Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg)
{
    CHECK_JOB_COMMON_PARAM_RET(cfg, return PROFILING_FAILED);
    if (cfg->comParams->params->hostProfiling) {
        return PROFILING_FAILED;
    }
    collectionJobCfg_ = cfg;
    if (collectionJobCfg_->comParams->params->nicProfiling.compare(MSVP_PROF_ON) != 0) {
        MSPROF_LOGI("NIC Profiling not enabled");
        return PROFILING_FAILED;
    }

    std::vector<std::string> profDataFilePathV;
    profDataFilePathV.push_back(collectionJobCfg_->comParams->tmpResultDir);
    profDataFilePathV.push_back("data");
    profDataFilePathV.push_back("nic.data");
    collectionJobCfg_->jobParams.dataPath = Utils::JoinPath(profDataFilePathV);
    samplePeriod_ = PERIPHERAL_INTERVAL_MS_SMIN;
    if (collectionJobCfg_->comParams->params->nicInterval > 0) {
        samplePeriod_ = collectionJobCfg_->comParams->params->nicInterval;
    }
    MSPROF_LOGI("NIC Profiling samplePeriod_:%d", samplePeriod_);

    peripheralCfg_.configP = nullptr;
    peripheralCfg_.configSize = 0;
    return PROFILING_SUCCESS;
}

ProfRoceJob::ProfRoceJob()
{
    channelId_ = PROF_CHANNEL_ROCE;
}
ProfRoceJob::~ProfRoceJob() {}

/*
 * @berif  : ROCE Peripheral Init profiling
 * @param  : cfg : Collect data config information
 * @return : PROFILING_FAILED(-1) : failed
 *         : PROFILING_SUCCESS(0) : success
 */
int32_t ProfRoceJob::Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg)
{
    CHECK_JOB_COMMON_PARAM_RET(cfg, return PROFILING_FAILED);
    if (cfg->comParams->params->hostProfiling) {
        return PROFILING_FAILED;
    }
    collectionJobCfg_ = cfg;
    if (collectionJobCfg_->comParams->params->roceProfiling.compare(MSVP_PROF_ON) != 0) {
        MSPROF_LOGI("ROCE Profiling not enabled");
        return PROFILING_FAILED;
    }

    MSPROF_LOGI("ROCE Profiling enabled");
    std::vector<std::string> profDataFilePathV;
    profDataFilePathV.push_back(collectionJobCfg_->comParams->tmpResultDir);
    profDataFilePathV.push_back("data");
    profDataFilePathV.push_back("roce.data");
    collectionJobCfg_->jobParams.dataPath = Utils::JoinPath(profDataFilePathV);
    samplePeriod_ = PERIPHERAL_INTERVAL_MS_SMIN;
    if (collectionJobCfg_->comParams->params->roceInterval > 0) {
        samplePeriod_ = collectionJobCfg_->comParams->params->roceInterval;
    }

    peripheralCfg_.configP = nullptr;
    peripheralCfg_.configSize = 0;
    return PROFILING_SUCCESS;
}
}
}
}