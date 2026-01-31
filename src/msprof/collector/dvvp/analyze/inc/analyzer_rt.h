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
#ifndef ANALYSIS_DVVP_ANALYZE_ANALYZER_RT_H
#define ANALYSIS_DVVP_ANALYZE_ANALYZER_RT_H

#include <map>
#include "analyzer_base.h"
#include "utils/utils.h"
#include "data_struct.h"

namespace Analysis {
namespace Dvvp {
namespace Analyze {
class Analyzer;
class AnalyzerRt : public AnalyzerBase {
    friend class Analyzer;

public:
    AnalyzerRt() : totalRtTimes_(0), totalRtMerges_(0) {}
    ~AnalyzerRt() {}

public:
    bool IsRtCompactData(const std::string &tag) const;

private:
    void ParseRuntimeTrackData(CONST_CHAR_PTR data, uint32_t len, bool ageFlag);
    void HandleRuntimeTrackData(CONST_CHAR_PTR data, bool ageFlag) const;
    void RtCompactParse(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq);
    void PrintStats() const;
    void MatchDeviceOpInfo(std::map<std::string, RtOpInfo> &rtOpInfo,
        std::multimap<std::string, RtOpInfo> &tsTmpOpInfo,
        std::multimap<uint32_t, GeOpFlagInfo> &geOpInfo) const;

private:
    uint32_t totalRtTimes_;
    uint32_t totalRtMerges_;
};
}  // namespace Analyze
}  // namespace Dvvp
}  // namespace Analysis

#endif
