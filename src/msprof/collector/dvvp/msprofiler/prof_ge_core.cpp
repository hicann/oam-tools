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

#include "prof_ge_core.h"
#include <unordered_set>
#include "logger/msprof_dlog.h"
#include "utils/utils.h"
#include "prof_acl_intf.h"
#include "acl/acl_base.h"
#include "prof_inner_api.h"
#include "errno/error_code.h"
#include "prof_api_runtime.h"

using namespace analysis::dvvp::common::utils;
using namespace analysis::dvvp::common::error;
using namespace Msprof::Engine::Intf;

Status aclgrphProfGraphSubscribe(const uint32_t graphId, const aclprofSubscribeConfig *profSubscribeConfig)
{
    return ProfAclSubscribe(ACL_GRPH_API_TYPE, graphId, profSubscribeConfig);
}

Status aclgrphProfGraphUnSubscribe(const uint32_t graphId)
{
    return ProfAclUnSubscribe(ACL_GRPH_API_TYPE, graphId);
}

size_t aclprofGetGraphId(CONST_VOID_PTR opInfo, size_t opInfoLen, uint32_t index)
{
    return ProfAclGetId(ACL_GRPH_API_TYPE, opInfo, opInfoLen, index);
}

namespace ge {
Status aclgrphProfInit(CONST_CHAR_PTR profilerPath, uint32_t length)
{
    if (Utils::IsDynProfMode()) {
        return ACL_ERROR_FEATURE_UNSUPPORTED;
    }

    if (ProfAclInit(ACL_GRPH_API_TYPE, profilerPath, length) != 0) {
        return FAILED;
    }
    return SUCCESS;
}

Status aclgrphProfFinalize()
{
    return ProfAclFinalize(ACL_GRPH_API_TYPE);
}

using PROF_AICORE_EVENTS_PTR = ProfAicoreEvents *;
bool IsProfConfigValid(CONST_UINT32_T_PTR deviceidList, uint32_t deviceNums)
{
    if (deviceidList == nullptr) {
        MSPROF_LOGE("[IsProfConfigValid]deviceIdList is nullptr");
        MSPROF_INPUT_ERROR("EK0001", std::vector<std::string>({"value", "param", "reason"}),
            std::vector<std::string>({"nullptr", "deviceidList", "deviceidList can not be nullptr"}));
        return false;
    }
    if (deviceNums == 0 || deviceNums > MSVP_MAX_DEV_NUM) {
        MSPROF_LOGE("[IsProfConfigValid]The device nums is invalid.");
        std::string errorReason = "The device nums should be in range(0, " + std::to_string(MSVP_MAX_DEV_NUM) + "]";
        MSPROF_INPUT_ERROR("EK0001", std::vector<std::string>({"value", "param", "reason"}),
            std::vector<std::string>({std::to_string(deviceNums), "deviceNums", errorReason}));
        return false;
    }
    // real device num
    const int32_t devCount = ProfAclDrvGetDevNum();
    if (devCount == PROFILING_FAILED) {
        MSPROF_LOGE("[IsProfConfigValid]Get the Device count fail.");
        return false;
    }
    if (deviceNums > static_cast<uint32_t>(devCount)) {
        MSPROF_LOGE("[IsProfConfigValid]Device num(%u) is not in range 1 ~ %d.", deviceNums, devCount);
        std::string errorReason = "The device nums should be in range[1, " + std::to_string(devCount) + "]";
        MSPROF_INPUT_ERROR("EK0001", std::vector<std::string>({"value", "param", "reason"}),
            std::vector<std::string>({std::to_string(deviceNums), "deviceNums", errorReason}));
        return false;
    }
    std::unordered_set<uint32_t> record;
    for (size_t i = 0; i < deviceNums; ++i) {
        uint32_t devId = deviceidList[i];
        if (devId >= static_cast<uint32_t>(devCount)) {
            MSPROF_LOGE("Device id %u is not in range 0 ~ %d(exclude %d)", devId, devCount, devCount);
            std::string errorReason = "The device id should be in range[0, " + std::to_string(devCount) + ")";
            MSPROF_INPUT_ERROR("EK0001", std::vector<std::string>({"value", "param", "reason"}),
                std::vector<std::string>({std::to_string(devId), "device id", errorReason}));
            return false;
        }
        if (record.count(devId) > 0) {
            MSPROF_LOGE("Device id %u is duplicatedly set", devId);
            std::string errorReason = "device id is duplicatedly set";
            MSPROF_INPUT_ERROR("EK0001", std::vector<std::string>({"value", "param", "reason"}),
                std::vector<std::string>({std::to_string(devId), "device id", errorReason}));
            return false;
        }
        record.insert(devId);
    }
    return true;
}

struct aclgrphProfConfig {
    ProfConfig config;
};
using ACL_GRPH_PROF_CONFIG_PTR = aclgrphProfConfig *;

static bool ModifyLogicDeviceId(UINT32_T_PTR deviceIdList, uint32_t deviceNums, ACL_GRPH_PROF_CONFIG_PTR profCfg)
{
    ProfRtAPI::ExtendPlugin::instance()->RuntimeApiInit();
    for (uint32_t i = 0; i < deviceNums; i++) {
        int32_t visibleDevId = 0;
        int32_t ret = ProfRtAPI::ExtendPlugin::instance()->ProfGetVisibleDeviceIdByLogicDeviceId(static_cast<int32_t>(
            deviceIdList[i]),  &visibleDevId);
        if (ret == PROFILING_NOTSUPPORT) {
            MSPROF_LOGI("GetLogicDeviceId is not support, using logic devId");
            if (memcpy_s(profCfg->config.devIdList, sizeof(profCfg->config.devIdList),
                deviceIdList, deviceNums * sizeof(uint32_t)) != EOK) {
                MSPROF_LOGE("copy devID failed. size = %u", deviceNums);
                return false;
            }
            return true;
        } else if (ret != PROFILING_SUCCESS) {
            MSPROF_LOGE("get visible devID failed, logic devId = %d", deviceIdList[i]);
            return false;
        }
        MSPROF_LOGI("Get visible devID = %d", visibleDevId);
        profCfg->config.devIdList[i] = static_cast<uint32_t>(visibleDevId);
    }
    if (!IsProfConfigValid(profCfg->config.devIdList, deviceNums)) {
        return false;
    }
    return true;
}

ACL_GRPH_PROF_CONFIG_PTR aclgrphProfCreateConfig(UINT32_T_PTR deviceidList, uint32_t deviceNums,
    ProfilingAicoreMetrics aicoreMetrics, PROF_AICORE_EVENTS_PTR aicoreEvents, uint64_t dataTypeConfig)
{
    UNUSED(aicoreEvents);
    if (!IsProfConfigValid(deviceidList, deviceNums)) {
        return nullptr;
    }
    ACL_GRPH_PROF_CONFIG_PTR config = new (std::nothrow) aclgrphProfConfig();
    if (config == nullptr) {
        MSPROF_LOGE("new aclgrphProfConfig fail");
        MSPROF_ENV_ERROR("EK0201", std::vector<std::string>({"buf_size"}),
            std::vector<std::string>({std::to_string(sizeof(aclgrphProfConfig))}));
        return nullptr;
    }
    config->config.devNums = deviceNums;
    if (deviceNums != 0) {
        if (!ModifyLogicDeviceId(deviceidList, deviceNums, config)) {
            MSPROF_LOGE("get visible devID failed");
            delete config;
            return nullptr;
        }
    }

    if ((dataTypeConfig & PROF_TASK_TIME_L1_MASK) != 0) { // 采集task time L1，同时配置task time L0
        config->config.dataTypeConfig |= PROF_TASK_TIME;
    }
    // 采集task time L2 或 op attr，同时配置task time L0, L1
    if ((dataTypeConfig & PROF_TASK_TIME_L2_MASK) != 0 || (dataTypeConfig & PROF_OP_ATTR_MASK) != 0) {
        config->config.dataTypeConfig |= PROF_TASK_TIME | PROF_TASK_TIME_L1;
    }
    config->config.devIdList[config->config.devNums] = DEFAULT_HOST_ID;
    config->config.devNums++;
    config->config.aicoreMetrics = static_cast<ProfAicoreMetrics>(aicoreMetrics);
    config->config.dataTypeConfig |= dataTypeConfig | PROF_AICPU_MODEL;
    MSPROF_LOGI("Successfully create prof config");
    return config;
}

Status aclgrphProfDestroyConfig(ACL_GRPH_PROF_CONFIG_PTR profilerConfig)
{
    if (profilerConfig == nullptr) {
        MSPROF_LOGE("Destroy profilerConfig failed, profilerConfig must not be nullptr");
        MSPROF_INPUT_ERROR("EK0003", std::vector<std::string>({"config"}),
            std::vector<std::string>({"profilerConfig"}));
        return FAILED;
    }
    delete profilerConfig;
    MSPROF_LOGI("Successfully destroy prof config.");
    return SUCCESS;
}

Status aclgrphProfStart(ACL_GRPH_PROF_CONFIG_PTR profilerConfig)
{
    if (ProfAclStart(ACL_GRPH_API_TYPE, &profilerConfig->config) != 0) {
        return FAILED;
    }
    return SUCCESS;
}

Status aclgrphProfStop(ACL_GRPH_PROF_CONFIG_PTR profilerConfig)
{
    if (ProfAclStop(ACL_GRPH_API_TYPE, &profilerConfig->config) != 0) {
        return FAILED;
    }
    return SUCCESS;
}
} // namespace ge
