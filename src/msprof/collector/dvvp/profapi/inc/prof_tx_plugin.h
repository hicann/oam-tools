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
 
#ifndef PROF_TX_PLUGIN_H
#define PROF_TX_PLUGIN_H
#include <cstdint>
#include "prof_load_api.h"
#include "acl/acl_base.h"

namespace ProfAPI {
using ProftxCreateStampFunc = VOID_PTR(*)(void);
using ProftxDestroyStampFunc = void (*)(VOID_PTR);
using ProftxPushFunc = int32_t (*)(VOID_PTR);
using ProftxPopFunc = int32_t (*)(void);
using ProftxRangeStartFunc = int32_t (*)(VOID_PTR, uint32_t *);
using ProftxRangeStopFunc = int32_t (*)(uint32_t);
using ProftxSetStampTraceMessageFunc = int32_t (*)(VOID_PTR, const char *, uint32_t);
using ProftxMarkFunc = int32_t (*)(VOID_PTR);
using ProftxMarkExFunc = int32_t (*)(const char *, size_t, aclrtStream);
using ProftxSetCategoryNameFunc = int32_t (*)(uint32_t, const char *);
using ProftxSetStampCategoryFunc = int32_t (*)(VOID_PTR, uint32_t);
using ProftxSetStampPayloadFunc = int32_t (*)(VOID_PTR, const int32_t, VOID_PTR);

void LoadProftxApiInit(VOID_PTR handle);

class ProfTxPlugin {
public:
    static ProfTxPlugin &GetProftxInstance()
    {
        static ProfTxPlugin plugin;
        return plugin;
    }
    void ProftxApiInit(VOID_PTR handle);
    VOID_PTR ProftxCreateStamp();
    void ProftxDestroyStamp(VOID_PTR stamp);
    int32_t ProftxPush(VOID_PTR stamp);
    int32_t ProftxPop();
    int32_t ProftxRangeStart(VOID_PTR stamp, uint32_t *rangeId);
    int32_t ProftxRangeStop(uint32_t rangeId);
    int32_t ProftxSetStampTraceMessage(VOID_PTR stamp, const char *msg, uint32_t msgLen);
    int32_t ProftxMark(VOID_PTR stamp);
    int32_t ProftxMarkEx(const char *msg, size_t msgLen, aclrtStream stream);
    int32_t ProftxSetCategoryName(uint32_t category, const char *categoryName);
    int32_t ProftxSetStampCategory(VOID_PTR stamp, uint32_t category);
    int32_t ProftxSetStampPayload(VOID_PTR stamp, const int32_t type, VOID_PTR value);
private:
    ProfLoadApi loadApi_;
    ProftxCreateStampFunc proftxCreateStamp_{nullptr};
    ProftxDestroyStampFunc proftxDestroyStamp_{nullptr};
    ProftxPushFunc proftxPush_{nullptr};
    ProftxPopFunc proftxPop_{nullptr};
    ProftxRangeStartFunc proftxRangeStart_{nullptr};
    ProftxRangeStopFunc proftxRangeStop_{nullptr};
    ProftxSetStampTraceMessageFunc proftxSetStampTraceMessage_{nullptr};
    ProftxMarkFunc proftxMark_{nullptr};
    ProftxMarkExFunc proftxMarkEx_{nullptr};
    ProftxSetCategoryNameFunc proftxSetCategoryName_{nullptr};
    ProftxSetStampCategoryFunc proftxSetStampCategory_{nullptr};
    ProftxSetStampPayloadFunc proftxSetStampPayload_{nullptr};
};
}
#endif