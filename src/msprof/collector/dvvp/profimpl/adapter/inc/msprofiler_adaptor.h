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

#ifndef MSPROFILER_ADAPTOR_H
#define MSPROFILER_ADAPTOR_H

#include "prof_acl_intf.h"
#include "acl/acl_prof.h"
#include "prof_report_api.h"
#include "msprofiler_acl_api.h"
#include "prof_common.h"

using CONST_VOID_PTR = const void *;

extern "C" MSVP_PROF_API int32_t ProfAclInit(Msprof::Engine::Intf::ProfType type, const char *profilerPath,
    uint32_t length);
extern "C" MSVP_PROF_API int32_t ProfAclWarmup(Msprof::Engine::Intf::ProfType type,
    PROF_CONFIG_CONST_PTR profilerConfig);
extern "C" MSVP_PROF_API int32_t ProfAclStart(Msprof::Engine::Intf::ProfType type,
    PROF_CONFIG_CONST_PTR profilerConfig);
extern "C" MSVP_PROF_API int32_t ProfAclStop(Msprof::Engine::Intf::ProfType type,
    PROF_CONFIG_CONST_PTR profilerConfig);
extern "C" MSVP_PROF_API int32_t ProfAclFinalize(Msprof::Engine::Intf::ProfType type);
extern "C" MSVP_PROF_API int32_t ProfAclSetConfig(aclprofConfigType type, const char *config, size_t configLength);
extern "C" MSVP_PROF_API int32_t ProfAclSubscribe(Msprof::Engine::Intf::ProfType type, uint32_t modelId,
    const aclprofSubscribeConfig *profSubscribeConfig);
extern "C" MSVP_PROF_API Msprofiler::AclApi::ProfCreateTransportFunc ProfCreateParsertransport();
extern "C" MSVP_PROF_API void ProfRegisterTransport(Msprofiler::AclApi::ProfCreateTransportFunc callback);
extern "C" MSVP_PROF_API int32_t ProfAclUnSubscribe(Msprof::Engine::Intf::ProfType type, uint32_t modelId);
extern "C" MSVP_PROF_API int32_t ProfAclDrvGetDevNum();
extern "C" MSVP_PROF_API uint64_t ProfAclGetOpTime(uint32_t type, CONST_VOID_PTR opInfo, size_t opInfoLen,
    uint32_t index);
extern "C" MSVP_PROF_API size_t ProfAclGetId(Msprof::Engine::Intf::ProfType type, CONST_VOID_PTR opInfo,
    size_t opInfoLen, uint32_t index);
extern "C" MSVP_PROF_API int32_t ProfAclGetOpVal(uint32_t type, CONST_VOID_PTR opInfo, size_t opInfoLen,
    uint32_t index, VOID_PTR data, size_t len);
extern "C" MSVP_PROF_API const char *ProfAclGetOpAttriVal(uint32_t type, const void *opInfo, size_t opInfoLen,
    uint32_t index, uint32_t attri);
extern "C" MSVP_PROF_API int32_t ProfImplReportRegTypeInfo(uint16_t level, uint32_t type, const std::string &typeName);
extern "C" MSVP_PROF_API int32_t ProfImplReportDataFormat(uint16_t level, uint32_t type, const std::string &dataFormat);
extern "C" MSVP_PROF_API uint64_t ProfImplReportGetHashId(const std::string &info);
extern "C" MSVP_PROF_API bool ProfImplHostFreqIsEnable();
extern "C" MSVP_PROF_API void ProfImplGetImplInfo(ProfImplInfo& info);
extern "C" MSVP_PROF_API void ProfImplSetApiBufPop(const ProfApiBufPopCallback func);
extern "C" MSVP_PROF_API void ProfImplSetCompactBufPop(const ProfCompactBufPopCallback func);
extern "C" MSVP_PROF_API void ProfImplSetAdditionalBufPop(const ProfAdditionalBufPopCallback func);
extern "C" MSVP_PROF_API void ProfImplIfReportBufEmpty(const ProfReportBufEmptyCallback func);
extern "C" MSVP_PROF_API int32_t ProfAclGetCompatibleFeatures(size_t *featuresSize, void **featuresData);
extern "C" MSVP_PROF_API int32_t ProfAclGetCompatibleFeaturesV2(size_t *featuresSize, void **featuresData);
extern "C" MSVP_PROF_API void ProfImplSetBatchAddBufPop(const ProfBatchAddBufPopCallback func);
extern "C" MSVP_PROF_API void ProfImplSetBatchAddBufIndexShift(const ProfBatchAddBufIndexShiftCallBack func);
extern "C" MSVP_PROF_API int32_t ProfImplGetFeatureIsOn(uint64_t feature);
extern "C" MSVP_PROF_API int32_t ProfImplSubscribeRawData(MsprofRawDataCallback callback);
extern "C" MSVP_PROF_API int32_t ProfImplUnSubscribeRawData();

extern "C" MSVP_PROF_API void ProfImplSetVarAddBlockBufBatchPop(const ProfVarAddBlockBufPopCallback func);
#endif