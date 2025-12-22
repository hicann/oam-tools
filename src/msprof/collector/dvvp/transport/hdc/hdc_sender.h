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

#ifndef ANALYSIS_DVVP_COMMON_HDC_SENDER_H
#define ANALYSIS_DVVP_COMMON_HDC_SENDER_H

#include "sender.h"
#include "transport/transport.h"

namespace analysis {
namespace dvvp {
namespace transport {
using namespace analysis::dvvp::streamio::client;
class HdcSender {
public:
    HdcSender();
    virtual ~HdcSender();

public:
    int32_t Init(SHARED_PTR_ALIA<ITransport> transport, const std::string &engineName);
    void Uninit() const;
    int32_t SendData(const std::string &jobCtx, const struct DataChunk &data);
    void Flush() const;

private:
    std::string engineName_;
    SHARED_PTR_ALIA<analysis::dvvp::common::memory::ChunkPool> chunkPool_;
    SHARED_PTR_ALIA<Sender> sender_;
    SHARED_PTR_ALIA<ITransport> transport_;
};
}  // namespace transport
}  // namespace dvvp
}  // namespace analysis

#endif  // ANALYSIS_DVVP_COMMON_HDC_SENDER_H
