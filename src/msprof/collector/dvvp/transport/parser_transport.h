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

#ifndef ANALYSIS_DVVP_ANALYZE_PARSER_TRANSPORT_H
#define ANALYSIS_DVVP_ANALYZE_PARSER_TRANSPORT_H

#include "transport.h"
#include "utils/utils.h"

namespace Analysis {
namespace Dvvp {
namespace Analyze {
class Analyzer;
}}}

namespace analysis {
namespace dvvp {
namespace transport {
class Uploader;
// ParserTransport
class ParserTransport : public ITransport {
public:
    explicit ParserTransport(SHARED_PTR_ALIA<Uploader> uploader);
    ~ParserTransport() override;

public:
    int32_t SendBuffer(CONST_VOID_PTR buffer, int32_t length) override;
    int32_t SendBuffer(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq) override;
    int32_t CloseSession() override;
    void WriteDone() override;
    void SetDevId(const std::string &devIdStr) override;
    void SetType(const uint32_t type) override;

private:
    SHARED_PTR_ALIA<Analysis::Dvvp::Analyze::Analyzer> analyzer_;
};

// PipeTransport
class PipeTransport : public ITransport {
public:
    int32_t SendBuffer(CONST_VOID_PTR buffer, int32_t length) override;
    int32_t SendBuffer(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq) override;
    int32_t CloseSession() override;
    void WriteDone() override {}
};
}  // namespace transport
}  // namespace dvvp
}  // namespace analysis

#endif
