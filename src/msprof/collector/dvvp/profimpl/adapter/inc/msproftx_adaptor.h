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

#ifndef MSPROFTX_ADAPTOR_H
#define MSPROFTX_ADAPTOR_H
#include "acl/acl_base.h"
#include "prof_report_api.h"

using CONST_VOID_PTR = const void *;

/**
* @name MsprofTxInit
* @brief Init msproftx for prof_acl_mgr.cpp
* @retval void
*/
extern "C" void MsprofTxInit();

/**
 * @name  MsprofTxUnInit
 * @brief Destroy or uninit msproftx for prof_acl_mgr.cpp
 * @return void
 */
extern "C" void MsprofTxUnInit();

extern "C" void* ProfAclCreateStamp();
extern "C" void ProfAclDestroyStamp(VOID_PTR stamp);
extern "C" int32_t ProfAclSetCategoryName(uint32_t category, const char *categoryName);
extern "C" int32_t ProfAclSetStampCategory(VOID_PTR stamp, uint32_t category);
extern "C" int32_t ProfAclSetStampPayload(VOID_PTR stamp, const int32_t type, CONST_VOID_PTR value);
extern "C" int32_t ProfAclSetStampTraceMessage(VOID_PTR stamp, const char *msg, uint32_t msgLen);
extern "C" int32_t ProfAclMark(VOID_PTR stamp);
extern "C" int32_t ProfAclMarkEx(const char *msg, size_t msgLen, aclrtStream stream);
extern "C" int32_t ProfAclPush(VOID_PTR stamp);
extern "C" int32_t ProfAclPop();
extern "C" int32_t ProfAclRangeStart(VOID_PTR stamp, uint32_t *rangeId);
extern "C" int32_t ProfAclRangeStop(uint32_t rangeId);
extern "C" MSVP_PROF_API void ProfImplSetAdditionalBufPush(const ProfAdditionalBufPushCallback func);
extern "C" MSVP_PROF_API void ProfImplSetMarkEx(const ProfMarkExCallback func);

#endif
