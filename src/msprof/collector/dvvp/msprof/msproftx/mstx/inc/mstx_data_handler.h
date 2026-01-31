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
#ifndef MSTX_MANAGER_H
#define MSTX_MANAGER_H

#include <atomic>
#include <mutex>
#include <unordered_map>
#include "msprof_error_manager.h"
#include "singleton/singleton.h"
#include "thread/thread.h"
#include "queue/ring_buffer.h"
#include "msprof_tx_manager.h"

namespace Collector {
namespace Dvvp {
namespace Mstx {
using namespace Msprof::MsprofTx;

constexpr size_t RING_BUFFER_DEFAULT_CAPACITY = 512;

enum class MstxDataType {
    DATA_MARK = 0,
    DATA_RANGE_START,
    DATA_RANGE_END,
    DATA_INVALID
};

class MstxDataHandler : public analysis::dvvp::common::singleton::Singleton<MstxDataHandler>,
                    public analysis::dvvp::common::thread::Thread {
public:
    MstxDataHandler();
    ~MstxDataHandler();

    int Start(const std::string &mstxDomainInclude, const std::string &mstxDomainExclude);
    int Stop();
    void Run(const struct error_message::Context &errorContext) override;
    bool IsStart();
    int SaveMstxData(const char* msg, uint64_t mstxEventId, MstxDataType type, uint64_t domainNameHash = 0);

private:
    void Init();
    void Uninit();
    int SaveMarkData(const char* msg, uint64_t mstxEventId, uint64_t domainNameHash);
    int SaveRangeData(const char* msg, uint64_t mstxEventId, MstxDataType type, uint64_t domainNameHash);

    void Flush();
    void ReportData();

private:
    uint32_t processId_{0};
    std::atomic<bool> init_{false};
    std::atomic<bool> start_{false};
    analysis::dvvp::common::queue::RingBuffer<MsprofTxInfo> mstxDataBuf_{MsprofTxInfo{}};
    std::mutex tmpRangeDataMutex_;
    std::unordered_map<uint64_t, MsprofTxInfo> tmpMstxRangeData_;
};
}
}
}
#endif
