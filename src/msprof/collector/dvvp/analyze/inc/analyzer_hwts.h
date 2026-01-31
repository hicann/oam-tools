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
#ifndef ANALYSIS_DVVP_ANALYZE_ANALYZER_HWTS_H
#define ANALYSIS_DVVP_ANALYZE_ANALYZER_HWTS_H

#include <map>

#include "analyzer_base.h"
#include "data_struct.h"
#include "utils/utils.h"

namespace Analysis {
namespace Dvvp {
namespace Analyze {
class Analyzer;
class AnalyzerHwts : public AnalyzerBase {
    friend class Analyzer;

public:
    AnalyzerHwts() : opTimeCount_(0), opRepeatCount_(0), totalHwtsTimes_(0), totalHwtsMerges_(0) {}
    ~AnalyzerHwts() {}

public:
    bool IsHwtsData(const std::string &fileName);
    void HwtsParse(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq);

private:
    void ParseOptimizeHwtsData(CONST_CHAR_PTR data, uint32_t len);
    uint8_t GetRptType(CONST_CHAR_PTR data, uint32_t len);
    void PrintStats();
    void HandleOptimizeStartEndData(CONST_CHAR_PTR data, uint8_t rptType);

private:
    uint64_t opTimeCount_;
    uint64_t opRepeatCount_;
    std::map<std::string, OpTime> opTimeDrafts_;  // stores incomplete data
    std::multimap<std::string, OpTime> opTimes_;  // key is taskId-streamId-contextId
    uint32_t totalHwtsTimes_;
    uint32_t totalHwtsMerges_;
};
}  // namespace Analyze
}  // namespace Dvvp
}  // namespace Analysis

#endif
