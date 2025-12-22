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

#include "prof_instr_perf_job.h"
#include "errno/error_code.h"
#include "platform/platform.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {
using namespace analysis::dvvp::common::error;
using namespace Analysis::Dvvp::Common::Platform;

ProfInstrPerfJob::ProfInstrPerfJob()
{
}

ProfInstrPerfJob::~ProfInstrPerfJob()
{
}

int32_t ProfInstrPerfJob::Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg)
{
    CHECK_JOB_CONTEXT_PARAM_RET(cfg, return PROFILING_FAILED);
    collectionJobCfg_ = cfg;
    sampleCycle_ = cfg->comParams->params->instrProfilingFreq;
    if (cfg->comParams->params->hostProfiling) {
        return PROFILING_FAILED;
    }
    if (cfg->comParams->params->instrProfiling.compare(MSVP_PROF_ON) != 0 ||
        !Platform::instance()->CheckIfSupport(PLATFORM_SYS_DEVICE_INSTR_PROFILING)) {
        MSPROF_LOGI("Instr profiling profile is not enabled.");
        return PROFILING_FAILED;
    }
    // currently get all instr profiling group id, group id can be configured in the future.
    for (uint32_t groupId = 0; groupId < INSTR_PROFILING_GROUP_MAX_NUM; ++groupId) {
        groupIds_.push_back(groupId);
    }
    MSPROF_LOGI("Instr profiling profile init success, instr profiling groupId: %s.",
        cfg->comParams->params->instrProfiling.c_str());
    return PROFILING_SUCCESS;
}

int32_t ProfInstrPerfJob::Process()
{
    CHECK_JOB_CONTEXT_PARAM_RET(collectionJobCfg_, return PROFILING_FAILED);
    int32_t ret = PROFILING_SUCCESS;
    uint32_t devId = collectionJobCfg_->comParams->devId;
    std::vector<std::string> coreName = {"aic", "aiv0", "aiv1"};

    for (const auto groupId : groupIds_) {
        for (size_t i = 0; i < INSTR_PROFILING_GROUP_CHANNEL_NUM; ++i) {
            const auto channelId = groupChannelIdMap_[groupId][i];
            if (!DrvChannelsMgr::instance()->ChannelIsValid(devId, channelId)) {
                MSPROF_LOGW("Channel is invalid, devId:%d, channelId:%d", devId, channelId);
                continue;
            }
            MSPROF_LOGI("Begin to start bui profile buffer, devId:%d, channelId:%d", devId, channelId);
            std::string filePath = collectionJobCfg_->jobParams.dataPath +
                                ".group_" + std::to_string(groupId) + "_" + coreName[i];
            AddReader(collectionJobCfg_->comParams->params->job_id, devId, channelId, filePath);
            InstrProfileConfigT config;
            config.period = sampleCycle_;
            ret = DrvInstrProfileStart(devId, channelId, static_cast<void *>(&config), sizeof(config));
            if (ret != PROFILING_SUCCESS) {
                RemoveReader(collectionJobCfg_->comParams->params->job_id, devId, channelId);
                MSPROF_LOGE("[ProfInstrPerfJob]Process, DrvInstrProfileStart failed. devId:%d, channelId:%d",
                            devId, channelId);
            }
            MSPROF_LOGI("start instr profiling profile buffer, ret=%d, devId:%d, channelId:%d, period:%u",
                ret, devId, channelId, sampleCycle_);
        }
    }
    // return last channel start result
    return ret;
}

int32_t ProfInstrPerfJob::Uninit()
{
    CHECK_JOB_CONTEXT_PARAM_RET(collectionJobCfg_, return PROFILING_FAILED);
    int32_t ret = PROFILING_SUCCESS;
    int32_t devId = collectionJobCfg_->comParams->devId;

    for (auto groupId : groupIds_) {
        for (size_t i = 0; i < INSTR_PROFILING_GROUP_CHANNEL_NUM; ++i) {
            const auto channelId = groupChannelIdMap_[groupId][i];
            if (!DrvChannelsMgr::instance()->ChannelIsValid(devId, channelId)) {
                MSPROF_LOGW("Channel is invalid, devId:%d, channelId:%d", devId, channelId);
                continue;
            }
            ret = DrvStop(devId, channelId);
            if (ret != PROFILING_SUCCESS) {
                MSPROF_LOGE("[ProfInstrPerfJob]DrvStop failed, ret:%d, devId:%d, channelId:%d", ret, devId, channelId);
            }
            RemoveReader(collectionJobCfg_->comParams->params->job_id, devId, channelId);
            collectionJobCfg_->jobParams.events.reset();
        }
    }
    // return last channel stop result
    return ret;
}

}
}
}