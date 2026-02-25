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

#include "prof_lpm_job.h"
#include "ai_drv_prof_api.h"
#include "utils/utils.h"
#include "config/config.h"
#include "platform/platform.h"
#include "uploader_mgr.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {
using namespace analysis::dvvp::common::config;
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::utils;
using namespace Analysis::Dvvp::Common::Platform;        

/*
 * @berif  : Collect milan frequency conversion data
 */
ProfLpmFreqConvJob::ProfLpmFreqConvJob()
{
    channelId_ = PROF_CHANNEL_LP;
}

ProfLpmFreqConvJob::~ProfLpmFreqConvJob() {}

/*
 * @berif  : Frequency Peripheral Init profiling
 * @param  : cfg : Collect data config information
 * @return : PROFILING_FAILED(-1) : failed
 *         : PROFILING_SUCCESS(0) : success
 */
int32_t ProfLpmFreqConvJob::Init(const SHARED_PTR_ALIA<CollectionJobCfg> cfg)
{
    CHECK_JOB_COMMON_PARAM_RET(cfg, return PROFILING_FAILED);
    if (cfg->comParams->params->hostProfiling) {
        return PROFILING_FAILED;
    }

    collectionJobCfg_ = cfg;
    if (collectionJobCfg_->comParams->params->ai_core_lpm.compare(MSVP_PROF_ON) != 0) {
        MSPROF_LOGI("Frequency conversion is not enabled");
        return PROFILING_FAILED;
    }
    return PROFILING_SUCCESS;
}

int32_t ProfLpmFreqConvJob::Process()
{
    if (Platform::instance()->CheckIfSupport(PLATFORM_TASK_AICORE_LPM_INFO)) {
        std::string filePath =
            collectionJobCfg_->comParams->tmpResultDir + MSVP_SLASH + "lpmInfoConv.data";
        collectionJobCfg_->jobParams.dataPath = filePath;
    }
    return ProfPeripheralJob::Process();
}

/*
 * @berif  : Frequency Peripheral Set Config
 * @param  : None
 * @return : PROFILING_FAILED(-1) : failed
 *         : PROFILING_SUCCESS(0) : success
 */
int32_t ProfLpmFreqConvJob::SetPeripheralConfig()
{
    uint32_t configSize = sizeof(LpmConvProfileConfig);
    LpmConvProfileConfig *configP = static_cast<LpmConvProfileConfig *>(Utils::ProfMalloc(configSize));
    if (configP == nullptr) {
        MSPROF_LOGE("ProfLpmFreqConvJob ProfMalloc LpmConvProfileConfig failed");
        return PROFILING_FAILED;
    }
    configP->period = DEFAULT_INTERVAL;
    configP->version = 1;
    peripheralCfg_.configP = configP;
    peripheralCfg_.configSize = configSize;
    return PROFILING_SUCCESS;
}
}
}
}