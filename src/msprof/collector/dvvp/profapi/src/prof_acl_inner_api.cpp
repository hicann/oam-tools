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

#include "prof_inner_api.h"
#include "prof_acl_plugin.h"
#include "prof_cann_plugin.h"

#ifdef __cplusplus
extern "C" {
#endif  // __cplusplus

// prof acl api
MSVP_PROF_API int32_t ProfAclInit(uint32_t type, const char *profilerPath, uint32_t len)
{
    ProfAPI::ProfCannPlugin::instance()->ProfApiInit();
    ProfAPI::ProfCannPlugin::instance()->ProfInitReportBuf();
    ProfAPI::ProfCannPlugin::instance()->ProfTxInit();
    return ProfAPI::ProfAclPlugin::instance()->ProfAclInit(type, profilerPath, len);
}

MSVP_PROF_API int32_t ProfAclStart(uint32_t type, PROFAPI_CONFIG_CONST_PTR profilerConfig)
{
    return ProfAPI::ProfAclPlugin::instance()->ProfAclStart(type, profilerConfig);
}

MSVP_PROF_API int32_t ProfAclStop(uint32_t type, PROFAPI_CONFIG_CONST_PTR profilerConfig)
{
    return ProfAPI::ProfAclPlugin::instance()->ProfAclStop(type, profilerConfig);
}

MSVP_PROF_API int32_t ProfAclFinalize(uint32_t type)
{
    int32_t ret = ProfAPI::ProfAclPlugin::instance()->ProfAclFinalize(type);
    ProfAPI::ProfCannPlugin::instance()->ProfUnInitReportBuf();
    return ret;
}

MSVP_PROF_API int32_t ProfAclDrvGetDevNum()
{
    ProfAPI::ProfCannPlugin::instance()->ProfApiInit();
    return ProfAPI::ProfAclPlugin::instance()->ProfAclDrvGetDevNum();
}

MSVP_PROF_API int32_t ProfAclSetConfig(uint32_t configType, const char *config, size_t configLength)
{
    return ProfAPI::ProfAclPlugin::instance()->ProfAclSetConfig(configType, config, configLength);
}

MSVP_PROF_API int32_t ProfAclGetCompatibleFeatures(size_t *featuresSize, void **featuresData)
{
    return ProfAPI::ProfAclPlugin::instance()->ProfAclGetCompatibleFeatures(featuresSize, featuresData);
}

#ifdef __cplusplus
}
#endif