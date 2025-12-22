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

#ifndef PROFILER_MSPROFTXMANAGER_H
#define PROFILER_MSPROFTXMANAGER_H

#include <mutex>
#include <map>
#include <atomic>
#include "utils.h"
#include "common/singleton/singleton.h"
#include "msprof_tx_reporter.h"
#include "prof_stamp_pool.h"
#include "acl/acl_base.h"
namespace Msprof {
namespace MsprofTx {
using ACL_PROF_STAMP_PTR = MsprofStampInstance *;
using CONST_CHAR_PTR = const char *;

enum class EventType {
    MARK = 0,
    PUSH_OR_POP,
    START_OR_STOP,
    MARK_EX
};

class MsprofTxManager : public analysis::dvvp::common::singleton::Singleton<MsprofTxManager> {
public:

    MsprofTxManager();
    ~MsprofTxManager() override;

    // create stamp memory pool, init plugin and push stack
    int32_t Init();
    // destroy resource
    void UnInit();

    // get stamp from memory pool
    ACL_PROF_STAMP_PTR CreateStamp() const;
    // destroy stamp
    void DestroyStamp(const ACL_PROF_STAMP_PTR stamp) const;

    //  save category and name relation
    int32_t SetCategoryName(uint32_t category, const std::string categoryName) const;

    // stamp message manage
    int32_t SetStampCategory(ACL_PROF_STAMP_PTR stamp, uint32_t category) const;
    int32_t SetStampPayload(ACL_PROF_STAMP_PTR stamp, const int32_t type, const void *value) const;
    int32_t SetStampTraceMessage(ACL_PROF_STAMP_PTR stamp, CONST_CHAR_PTR msg, uint32_t msgLen) const;

    // mark stamp
    int32_t Mark(ACL_PROF_STAMP_PTR stamp) const;
    // mark ex
    int32_t MarkEx(CONST_CHAR_PTR msg, size_t msgLen, aclrtStream stream);

    // stamp stack manage
    int32_t Push(ACL_PROF_STAMP_PTR stamp) const;
    int32_t Pop() const;

    // stamp map manage
    int RangeStart(ACL_PROF_STAMP_PTR stamp, uint32_t *rangeId) const;
    int32_t RangeStop(uint32_t rangeId) const;
    void RegisterReporterCallback(const ProfAdditionalBufPushCallback func);
    void RegisterRuntimeTxCallback(const ProfMarkExCallback func);

private:
    int32_t MarkExPoint(aclrtStream stream, MsprofTxInfo &info);

private:
    int32_t ReportStampData(MsprofStampInstance *stamp) const;

    bool isInit_;
    std::mutex mtx_;
    std::shared_ptr<MsprofTxReporter> reporter_;
    std::shared_ptr<ProfStampPool> stampPool_;
    std::map<uint32_t, std::string> categoryNameMap_;
    std::atomic<uint32_t> markExIndex_;
    ProfMarkExCallback rtProfilerTraceExFunc_;
    std::mutex markExMtx_;
};

}
}

#endif // PROFILER_MSPROFTXMANAGER_H
