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

#ifndef ANALYSIS_DVVP_ANALYZE_ANALYZER_BASE_H
#define ANALYSIS_DVVP_ANALYZE_ANALYZER_BASE_H

#include "utils/utils.h"
#include "data_struct.h"
#include "op_desc_parser.h"
#include "platform/platform.h"

namespace Analysis {
namespace Dvvp {
namespace Analyze {
using namespace analysis::dvvp::common::utils;
class AnalyzerBase {
public:
    AnalyzerBase() : dataPtr_(nullptr), dataLen_(0), analyzedBytes_(0), totalBytes_(0), pmuNum_(0), frequency_(1.0)
    {
        pmuNum_ = Analysis::Dvvp::Common::Platform::Platform::instance()->GetMaxMonitorNumber();
    }
    ~AnalyzerBase()
    {}

protected:
    /**
     * @brief append new data to buffer (if buffer not empty)
     * @param data ptr to data
     * @param len length of data
     */
    void AppendToBufferedData(CONST_CHAR_PTR data, uint32_t len);

    /**
     * @brief copy remaining data to buffer, or clear buffer if offset > buffer.size
     * @param offset offset of remaining data ptr
     */
    void BufferRemainingData(uint32_t offset);

    /**
     * @brief initialize frequency, op's time = (syscnt / frequency)
     */
    int32_t InitFrequency();

    void EraseRtMapByStreamId(uint16_t streamId, std::map<std::string, RtOpInfo> &rtOpInfo) const;
    void HandleDeviceData(const std::string &key, RtOpInfo &devData, uint32_t &time) const;
    void HandleUploadData(const std::string &key, const RtOpInfo &devData) const;
    void ConstructAndUploadOptimizeData(GeOpFlagInfo &opFlagData, const RtOpInfo &rtTsOpdata) const;
    uint32_t GetGraphModelId(uint32_t modelId) const;
    void SetGraphModelId(uint32_t modelId, uint32_t graphId) const;
    bool IsExtPmu() const;
    CONST_CHAR_PTR dataPtr_;
    uint32_t dataLen_;

    std::string buffer_;

    uint64_t analyzedBytes_;
    uint64_t totalBytes_;
    uint32_t pmuNum_;
    double frequency_;

    static bool isFftsPlus_;
    static bool opTypeFlag_;
    static std::map<std::string, RtOpInfo> rtOpInfo_;
    static std::map<std::string, RtOpInfo> tsOpInfo_;
    static std::multimap<std::string, RtOpInfo> tsTmpOpInfo_;
    static std::multimap<uint32_t, GeOpFlagInfo> geContextInfo_;
    static std::multimap<uint32_t, GeOpFlagInfo> geNodeInfo_;
    static std::multimap<uint32_t, GeOpFlagInfo> geApiInfo_;
    static std::multimap<uint32_t, GeOpFlagInfo> geModelInfo_;
    static std::multimap<uint32_t, GeOpFlagInfo> geOpInfo_;
    static std::map<uint32_t, uint32_t> graphIdMap_;    // <modeId, graphId>
    static std::vector<ProfOpDesc> opDescInfos_;
    static std::vector<RtOpInfo> devTmpOpInfo_;
    static std::mutex opDescInfoMtx_;
    static std::mutex graphIdMtx_;
    static std::mutex rtThreadMtx_;
    static std::mutex geThreadMtx_;
    static std::mutex tsThreadMtx_;
};
}  // namespace Analyze
}  // namespace Dvvp
}  // namespace Analysis

#endif
