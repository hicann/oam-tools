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

#include "prof_tx_plugin.h"
#include "errno/error_code.h"

using namespace analysis::dvvp::common::error;

namespace ProfAPI {
void ProfTxPlugin::ProftxApiInit(VOID_PTR handle)
{
    loadApi_.ProfLoadApiInit(handle);
}

VOID_PTR ProfTxPlugin::ProftxCreateStamp()
{
    if (proftxCreateStamp_ == nullptr) {
        proftxCreateStamp_ = loadApi_.LoadProfTxApi<decltype(proftxCreateStamp_)>("ProfAclCreateStamp");
        if (proftxCreateStamp_ == nullptr) {
            return nullptr;
        }
    }

    return proftxCreateStamp_();
}

void ProfTxPlugin::ProftxDestroyStamp(VOID_PTR stamp)
{
    if (proftxDestroyStamp_ == nullptr) {
        proftxDestroyStamp_ = loadApi_.LoadProfTxApi<decltype(proftxDestroyStamp_)>("ProfAclDestroyStamp");
        if (proftxDestroyStamp_ == nullptr) {
            return;
        }
    }

    proftxDestroyStamp_(stamp);
}

int32_t ProfTxPlugin::ProftxPush(VOID_PTR stamp)
{
    if (proftxPush_ == nullptr) {
        proftxPush_ = loadApi_.LoadProfTxApi<decltype(proftxPush_)>("ProfAclPush");
        if (proftxPush_ == nullptr) {
            return PROFILING_FAILED;
        }
    }

    return proftxPush_(stamp);
}

int32_t ProfTxPlugin::ProftxPop()
{
    if (proftxPop_ == nullptr) {
        proftxPop_ = loadApi_.LoadProfTxApi<decltype(proftxPop_)>("ProfAclPop");
        if (proftxPop_ == nullptr) {
            return PROFILING_FAILED;
        }
    }

    return proftxPop_();
}

int32_t ProfTxPlugin::ProftxRangeStart(VOID_PTR stamp, uint32_t *rangeId)
{
    if (proftxRangeStart_ == nullptr) {
        proftxRangeStart_ = loadApi_.LoadProfTxApi<decltype(proftxRangeStart_)>("ProfAclRangeStart");
        if (proftxRangeStart_ == nullptr) {
            return PROFILING_FAILED;
        }
    }

    return proftxRangeStart_(stamp, rangeId);
}

int32_t ProfTxPlugin::ProftxRangeStop(uint32_t rangeId)
{
    if (proftxRangeStop_ == nullptr) {
        proftxRangeStop_ = loadApi_.LoadProfTxApi<decltype(proftxRangeStop_)>("ProfAclRangeStop");
        if (proftxRangeStop_ == nullptr) {
            return PROFILING_FAILED;
        }
    }

    return proftxRangeStop_(rangeId);
}

int32_t ProfTxPlugin::ProftxSetStampTraceMessage(VOID_PTR stamp, const char *msg, uint32_t msgLen)
{
    if (proftxSetStampTraceMessage_ == nullptr) {
        proftxSetStampTraceMessage_ = loadApi_.LoadProfTxApi<decltype(proftxSetStampTraceMessage_)>(
            "ProfAclSetStampTraceMessage");
        if (proftxSetStampTraceMessage_ == nullptr) {
            return PROFILING_FAILED;
        }
    }

    return proftxSetStampTraceMessage_(stamp, msg, msgLen);
}

int32_t ProfTxPlugin::ProftxMark(VOID_PTR stamp)
{
    if (proftxMark_ == nullptr) {
        proftxMark_ = loadApi_.LoadProfTxApi<decltype(proftxMark_)>("ProfAclMark");
        if (proftxMark_ == nullptr) {
            return PROFILING_FAILED;
        }
    }

    return proftxMark_(stamp);
}

int32_t ProfTxPlugin::ProftxMarkEx(const char *msg, size_t msgLen, aclrtStream stream)
{
    if (proftxMarkEx_ == nullptr) {
        proftxMarkEx_ = loadApi_.LoadProfTxApi<decltype(proftxMarkEx_)>("ProfAclMarkEx");
        if (proftxMarkEx_ == nullptr) {
            return PROFILING_FAILED;
        }
    }

    return proftxMarkEx_(msg, msgLen, stream);
}

int32_t ProfTxPlugin::ProftxSetCategoryName(uint32_t category, const char *categoryName)
{
    if (proftxSetCategoryName_ == nullptr) {
        proftxSetCategoryName_ = loadApi_.LoadProfTxApi<decltype(proftxSetCategoryName_)>("ProfAclSetCategoryName");
        if (proftxSetCategoryName_ == nullptr) {
            return PROFILING_FAILED;
        }
    }

    return proftxSetCategoryName_(category, categoryName);
}

int32_t ProfTxPlugin::ProftxSetStampCategory(VOID_PTR stamp, uint32_t category)
{
    if (proftxSetStampCategory_ == nullptr) {
        proftxSetStampCategory_ = loadApi_.LoadProfTxApi<decltype(proftxSetStampCategory_)>("ProfAclSetStampCategory");
        if (proftxSetStampCategory_ == nullptr) {
            return PROFILING_FAILED;
        }
    }

    return proftxSetStampCategory_(stamp, category);
}

int32_t ProfTxPlugin::ProftxSetStampPayload(VOID_PTR stamp, const int32_t type, VOID_PTR value)
{
    if (proftxSetStampPayload_ == nullptr) {
        proftxSetStampPayload_ = loadApi_.LoadProfTxApi<decltype(proftxSetStampPayload_)>("ProfAclSetStampPayload");
        if (proftxSetStampPayload_ == nullptr) {
            return PROFILING_FAILED;
        }
    }

    return proftxSetStampPayload_(stamp, type, value);
}

void LoadProftxApiInit(VOID_PTR handle)
{
    ProfTxPlugin::GetProftxInstance().ProftxApiInit(handle);
}
}
