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
#include "msproftx_adaptor.h"
#include "msprof_tx_manager.h"
#include "platform/platform.h"
#include "msprof_dlog.h"

using namespace Analysis::Dvvp::Common::Platform;
using namespace analysis::dvvp::common::utils;
using namespace analysis::dvvp::common::error;

extern "C" void* ProfAclCreateStamp()
{
    if (Platform::instance()->PlatformIsHelperHostSide()) {
        MSPROF_LOGE("acl api not support in helper");
        return nullptr;
    }
    return Msprof::MsprofTx::MsprofTxManager::instance()->CreateStamp();
}

extern "C" void ProfAclDestroyStamp(VOID_PTR stamp)
{
    if (Platform::instance()->PlatformIsHelperHostSide()) {
        MSPROF_LOGE("acl api not support in helper");
        return;
    }
    if (stamp == nullptr) {
        return;
    }
    auto stampInstancePtr = static_cast<Msprof::MsprofTx::ACL_PROF_STAMP_PTR>(stamp);
    Msprof::MsprofTx::MsprofTxManager::instance()->DestroyStamp(stampInstancePtr);
}

extern "C" int32_t ProfAclSetCategoryName(uint32_t category, const char *categoryName)
{
    if (Platform::instance()->PlatformIsHelperHostSide()) {
        MSPROF_LOGE("acl api not support in helper");
        return ACL_ERROR_FEATURE_UNSUPPORTED;
    }
    return Msprof::MsprofTx::MsprofTxManager::instance()->SetCategoryName(category, categoryName);
}

extern "C" int32_t ProfAclSetStampCategory(VOID_PTR stamp, uint32_t category)
{
    if (Platform::instance()->PlatformIsHelperHostSide()) {
        MSPROF_LOGE("acl api not support in helper");
        return ACL_ERROR_FEATURE_UNSUPPORTED;
    }
    auto stampInstancePtr = static_cast<Msprof::MsprofTx::ACL_PROF_STAMP_PTR>(stamp);
    return Msprof::MsprofTx::MsprofTxManager::instance()->SetStampCategory(stampInstancePtr, category);
}

extern "C" int32_t ProfAclSetStampPayload(VOID_PTR stamp, const int32_t type, CONST_VOID_PTR value)
{
    if (Platform::instance()->PlatformIsHelperHostSide()) {
        MSPROF_LOGE("acl api not support in helper");
        return ACL_ERROR_FEATURE_UNSUPPORTED;
    }
    auto stampInstancePtr = static_cast<Msprof::MsprofTx::ACL_PROF_STAMP_PTR>(stamp);
    return Msprof::MsprofTx::MsprofTxManager::instance()->SetStampPayload(stampInstancePtr, type, value);
}

extern "C" int32_t ProfAclSetStampTraceMessage(VOID_PTR stamp, const char *msg, uint32_t msgLen)
{
    if (Platform::instance()->PlatformIsHelperHostSide()) {
        MSPROF_LOGE("acl api not support in helper");
        return ACL_ERROR_FEATURE_UNSUPPORTED;
    }
    auto stampInstancePtr = static_cast<Msprof::MsprofTx::ACL_PROF_STAMP_PTR>(stamp);
    return Msprof::MsprofTx::MsprofTxManager::instance()->SetStampTraceMessage(stampInstancePtr, msg, msgLen);
}

extern "C" int32_t ProfAclMark(VOID_PTR stamp)
{
    if (Platform::instance()->PlatformIsHelperHostSide()) {
        MSPROF_LOGE("acl api not support in helper");
        return ACL_ERROR_FEATURE_UNSUPPORTED;
    }
    auto stampInstancePtr = static_cast<Msprof::MsprofTx::ACL_PROF_STAMP_PTR>(stamp);
    return Msprof::MsprofTx::MsprofTxManager::instance()->Mark(stampInstancePtr);
}

extern "C" int32_t ProfAclMarkEx(const char *msg, size_t msgLen, aclrtStream stream)
{
    if (Platform::instance()->PlatformIsHelperHostSide()) {
        MSPROF_LOGE("acl api not support in helper");
        return ACL_ERROR_FEATURE_UNSUPPORTED;
    }

    return Msprof::MsprofTx::MsprofTxManager::instance()->MarkEx(msg, msgLen, stream);
}

extern "C" int32_t ProfAclPush(VOID_PTR stamp)
{
    if (Platform::instance()->PlatformIsHelperHostSide()) {
        MSPROF_LOGE("acl api not support in helper");
        return ACL_ERROR_FEATURE_UNSUPPORTED;
    }
    auto stampInstancePtr = static_cast<Msprof::MsprofTx::ACL_PROF_STAMP_PTR>(stamp);
    return Msprof::MsprofTx::MsprofTxManager::instance()->Push(stampInstancePtr);
}

extern "C" int32_t ProfAclPop()
{
    if (Platform::instance()->PlatformIsHelperHostSide()) {
        MSPROF_LOGE("acl api not support in helper");
        return ACL_ERROR_FEATURE_UNSUPPORTED;
    }
    return Msprof::MsprofTx::MsprofTxManager::instance()->Pop();
}

extern "C" int32_t ProfAclRangeStart(VOID_PTR stamp, uint32_t *rangeId)
{
    if (Platform::instance()->PlatformIsHelperHostSide()) {
        MSPROF_LOGE("acl api not support in helper");
        return ACL_ERROR_FEATURE_UNSUPPORTED;
    }
    auto stampInstancePtr = static_cast<Msprof::MsprofTx::ACL_PROF_STAMP_PTR>(stamp);
    return Msprof::MsprofTx::MsprofTxManager::instance()->RangeStart(stampInstancePtr, rangeId);
}

extern "C" int32_t ProfAclRangeStop(uint32_t rangeId)
{
    if (Platform::instance()->PlatformIsHelperHostSide()) {
        MSPROF_LOGE("acl api not support in helper");
        return ACL_ERROR_FEATURE_UNSUPPORTED;
    }
    return Msprof::MsprofTx::MsprofTxManager::instance()->RangeStop(rangeId);
}

extern "C" void MsprofTxInit()
{
    MSPROF_LOGI("msproftx executes Callback and Init.");
    int32_t ret = Msprof::MsprofTx::MsprofTxManager::instance()->Init();
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGW("Initialization of MsprofTxManager unsuccessfully.");
    }
}

extern "C" void MsprofTxUnInit()
{
    MSPROF_LOGI("msproftx executes UnInit.");
    Msprof::MsprofTx::MsprofTxManager::instance()->UnInit();
}

extern "C" MSVP_PROF_API void ProfImplSetAdditionalBufPush(const ProfAdditionalBufPushCallback func)
{
    Msprof::MsprofTx::MsprofTxManager::instance()->RegisterReporterCallback(func);
}

extern "C" MSVP_PROF_API void ProfImplSetMarkEx(const ProfMarkExCallback func)
{
    Msprof::MsprofTx::MsprofTxManager::instance()->RegisterRuntimeTxCallback(func);
}