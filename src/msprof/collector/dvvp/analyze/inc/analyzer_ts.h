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
 
#ifndef ANALYSIS_DVVP_ANALYZE_ANALYZER_TS_H
#define ANALYSIS_DVVP_ANALYZE_ANALYZER_TS_H

#include <map>
#include <unordered_map>
#include "analyzer_base.h"
#include "utils/utils.h"
#include "data_struct.h"

namespace Analysis {
namespace Dvvp {
namespace Analyze {
class Analyzer;
class AnalyzerTs : public AnalyzerBase {
    friend class Analyzer;

public:
    AnalyzerTs() : opTimeCount_(0), totalTsMerges_(0)
    {}
    ~AnalyzerTs()
    {}

public:
    bool IsTsData(const std::string &fileName);
    void Parse(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq);

private:
    void ParseTsTrackData(CONST_CHAR_PTR data, uint32_t len);
    void ParseTsTimelineData(CONST_CHAR_PTR data, uint32_t len);
    void ParseTsKeypointData(CONST_CHAR_PTR data, uint32_t len);
    uint8_t GetRptType(CONST_CHAR_PTR data, uint32_t len);

    void PrintStats();

private:
    uint64_t opTimeCount_;
    uint32_t totalTsMerges_;
    std::map<std::string, OpTime> opTimeDrafts_;  // stores incomplete data
    std::multimap<std::string, OpTime> opTimes_;  // key is taskId-streamId-contextId
    std::unordered_map<std::string, KeypointOp> keypointOpInfo_;
};
}  // namespace Analyze
}  // namespace Dvvp
}  // namespace Analysis

#endif
