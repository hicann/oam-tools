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
 
#ifndef ANALYSIS_DVVP_ANALYZE_ANALYZER_FFTS_H
#define ANALYSIS_DVVP_ANALYZE_ANALYZER_FFTS_H

#include <map>

#include "analyzer_base.h"
#include "data_struct.h"
#include "utils/utils.h"

namespace Analysis {
namespace Dvvp {
namespace Analyze {
class Analyzer;
class AnalyzerFfts : public AnalyzerBase {
    friend class Analyzer;

public:
    AnalyzerFfts() : opTimeCount_(0), opRepeatCount_(0), totalFftsTimes_(0), totalFftsMerges_(0) {}
    ~AnalyzerFfts() {}

public:
    bool IsFftsData(const std::string &fileName) const;
    void FftsParse(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq);

private:
    void PrintStats() const;
    void ParseOptimizeFftsData(CONST_CHAR_PTR data, uint32_t len);
    template<typename T>
    void HandleOptimizeAcsqTaskData(const T *acsqLog, uint32_t logType);
    void HandleOptimizeSubTaskThreadData(const StarsCxtLog *cxtLog, uint32_t logType);
    void StarsRollBackStreamTaskId(uint16_t *streamId, uint16_t *taskId) const;

private:
    uint64_t opTimeCount_;
    uint64_t opRepeatCount_;
    std::map<std::string, OpTime> opDrafts_;      // stores incomplete data
    std::multimap<std::string, OpTime> opTimes_;  // key is taskId-streamId-contextId
    uint32_t totalFftsTimes_;
    uint32_t totalFftsMerges_;
};
}  // namespace Analyze
}  // namespace Dvvp
}  // namespace Analysis

#endif
