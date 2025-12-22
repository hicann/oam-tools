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

#include "prof_hwts_log_job.h"
#include "errno/error_code.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::config;

ProfHwtsLogJob::ProfHwtsLogJob() : channelId_(PROF_CHANNEL_HWTS_LOG)
{
}

ProfHwtsLogJob::~ProfHwtsLogJob()
{
}

int32_t ProfHwtsLogJob::Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg)
{
    CHECK_JOB_CONTEXT_PARAM_RET(cfg, return PROFILING_FAILED);
    if (cfg->comParams->params->hostProfiling) {
        return PROFILING_FAILED;
    }

    if (cfg->comParams->params->hwts_log.compare("on") != 0) {
        MSPROF_LOGI("hwts_log not enabled");
        return PROFILING_FAILED;
    }
    collectionJobCfg_ = cfg;
    return PROFILING_SUCCESS;
}

int32_t ProfHwtsLogJob::Process()
{
    CHECK_JOB_COMMON_PARAM_RET(collectionJobCfg_, return PROFILING_FAILED);

    MSPROF_LOGI("[ProfHwtsLogJob]Process, hwts_log:%s, aiv_hwts_log:%s",
        collectionJobCfg_->comParams->params->hwts_log.c_str(),
        collectionJobCfg_->comParams->params->hwts_log1.c_str());

    if (!DrvChannelsMgr::instance()->ChannelIsValid(collectionJobCfg_->comParams->devId, channelId_)) {
        MSPROF_LOGW("Channel is invalid, devId:%d, channelId:%d", collectionJobCfg_->comParams->devId,
            channelId_);
        return PROFILING_SUCCESS;
    }
    MSPROF_LOGI("Begin to start profiling hwts log");
    std::string filePath = BindFileWithChannel(collectionJobCfg_->jobParams.dataPath);

    AddReader(collectionJobCfg_->comParams->params->job_id, collectionJobCfg_->comParams->devId, channelId_, filePath);

    int32_t ret = DrvHwtsLogStart(collectionJobCfg_->comParams->devId, channelId_);

    MSPROF_LOGI("start profiling hwts log, ret=%d", ret);
    FUNRET_CHECK_RET_VAL(ret != PROFILING_SUCCESS);
    return ret;
}

int32_t ProfHwtsLogJob::Uninit()
{
    CHECK_JOB_COMMON_PARAM_RET(collectionJobCfg_, return PROFILING_SUCCESS);

    MSPROF_LOGI("[ProfHwtsLogJob]Uninit, hwts_log:%s, aiv_hwts_log:%s",
        collectionJobCfg_->comParams->params->hwts_log.c_str(),
        collectionJobCfg_->comParams->params->hwts_log1.c_str());

    if (!DrvChannelsMgr::instance()->ChannelIsValid(collectionJobCfg_->comParams->devId, channelId_)) {
        MSPROF_LOGW("Channel is invalid, devId:%d, channelId:%d", collectionJobCfg_->comParams->devId,
            channelId_);
        return PROFILING_SUCCESS;
    }
    MSPROF_LOGI("begin to stop profiling hwts_log data");

    int32_t ret = DrvStop(collectionJobCfg_->comParams->devId, channelId_);

    MSPROF_LOGI("stop profiling hwts_log data, ret=%d", ret);

    RemoveReader(collectionJobCfg_->comParams->params->job_id, collectionJobCfg_->comParams->devId, channelId_);

    return PROFILING_SUCCESS;
}

ProfAivHwtsLogJob::ProfAivHwtsLogJob() {}

ProfAivHwtsLogJob::~ProfAivHwtsLogJob() {}

int32_t ProfAivHwtsLogJob::Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg)
{
    CHECK_JOB_CONTEXT_PARAM_RET(cfg, return PROFILING_FAILED);
    if (cfg->comParams->params->hostProfiling) {
        return PROFILING_FAILED;
    }

    if (cfg->comParams->params->hwts_log1.compare("on") != 0) {
        MSPROF_LOGI("aiv_hwts_log not enabled");
        return PROFILING_FAILED;
    }
    collectionJobCfg_ = cfg;
    channelId_ = PROF_CHANNEL_AIV_HWTS_LOG;
    return PROFILING_SUCCESS;
}

}
}
}