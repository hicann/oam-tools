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

#ifndef PROF_STAMP_POOL_H
#define PROF_STAMP_POOL_H

#include <map>
#include <mutex>
#include <vector>
#include "prof_common.h"
#include "prof_api.h"
#include "prof_report_api.h"

namespace Msprof {
namespace MsprofTx {

// Specification
constexpr int32_t MAX_STAMP_SIZE = 10000;
constexpr uint32_t CURRENT_STAMP_SIZE = 100;

struct MsprofStampInstance {
    MsprofTxInfo txInfo;
    int32_t id;
    struct MsprofStampInstance* next;
    struct MsprofStampInstance* prev;
};

struct MsprofStampCtrlHandle {
    struct MsprofStampInstance* memPool;
    struct MsprofStampInstance* freelist;
    struct MsprofStampInstance* usedlist;
    uint32_t freeCnt;
    uint32_t usedCnt;
    uint32_t instanceSize;
};

class ProfStampPool {
public:
    ProfStampPool();
    virtual ~ProfStampPool();

    // create stamp memory pool
    int32_t Init(uint32_t size);
    // destroy memory pool
    int32_t UnInit() const;

    // get stamp from memory pool
    MsprofStampInstance* CreateStamp();
    // destroy stamp
    void DestroyStamp(MsprofStampInstance* stamp);

    // push/pob
    int32_t MsprofStampPush(MsprofStampInstance* stamp);
    MsprofStampInstance* MsprofStampPop();

    MsprofStampInstance* GetStampById(uint32_t id) const;
    int32_t GetIdByStamp(const MsprofStampInstance* const stamp) const;

private:
    std::vector<MsprofStampInstance *> singleTStack_;
    std::mutex singleTStackMtx_;
    std::mutex memoryListMtx_;
};

}
}

#endif // PROF_STAMP_POOL_H
