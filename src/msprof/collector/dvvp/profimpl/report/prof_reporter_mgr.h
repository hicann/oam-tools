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

#ifndef DVVP_COLLECT_REPORT_MSPROF_REPORTER_MGR_H
#define DVVP_COLLECT_REPORT_MSPROF_REPORTER_MGR_H
#include <mutex>
#include <unordered_map>
#include "msprof_reporter.h"

namespace Dvvp {
namespace Collect {
namespace Report {
using namespace analysis::dvvp;
const std::map<uint16_t, std::map<uint32_t, std::string>> DEFAULT_TYPE_INFO = {
    { MSPROF_REPORT_NODE_LEVEL, {
        {MSPROF_REPORT_NODE_BASIC_INFO_TYPE, "node_basic_info"},
        {MSPROF_REPORT_NODE_TENSOR_INFO_TYPE, "tensor_info"},
        {MSPROF_REPORT_NODE_ATTR_INFO_TYPE, "node_attr_info"},
        {MSPROF_REPORT_NODE_FUSION_OP_INFO_TYPE, "fusion_op_info"},
        {MSPROF_REPORT_NODE_CONTEXT_ID_INFO_TYPE, "context_id_info"},
        {MSPROF_REPORT_NODE_LAUNCH_TYPE, "launch"},
        {MSPROF_REPORT_NODE_TASK_MEMORY_TYPE, "task_memory_info"},
        {MSPROF_REPORT_NODE_STATIC_OP_MEM_TYPE, "static_op_mem"},
    }},
    { MSPROF_REPORT_MODEL_LEVEL, {
        {MSPROF_REPORT_MODEL_GRAPH_ID_MAP_TYPE, "graph_id_map"},
        {MSPROF_REPORT_MODEL_EXEOM_TYPE, "model_exeom"},
        {MSPROF_REPORT_MODEL_LOGIC_STREAM_TYPE, "logic_stream_info"}
    }},
    { MSPROF_REPORT_HCCL_NODE_LEVEL, {
        {MSPROF_REPORT_HCCL_MASTER_TYPE, "master"},
        {MSPROF_REPORT_HCCL_SLAVE_TYPE, "slave"}
    }},
    { MSPROF_REPORT_TX_LEVEL, {
        {MSPROF_REPORT_TX_BASE_TYPE, "msproftx"}
    }}
};
class ProfReporterMgr : public analysis::dvvp::common::thread::Thread {
public:
    static ProfReporterMgr &GetInstance()
    {
        static ProfReporterMgr mgr;
        return mgr;
    }
    int32_t Start() override;
    int32_t Stop() override;
    void Run(const struct error_message::Context &errorContext) override;
    int32_t StartReporters();
    int32_t SendAdditionalData(SHARED_PTR_ALIA<ProfileFileChunk> fileChunk);
    void FlushAdditonalData();
    void FlushAllReporter();
    void FlushHostReporters();
    int32_t RegReportTypeInfo(uint16_t level, uint32_t typeId, const std::string &typeName);
    uint64_t GetHashId(const std::string &info) const;
    void GetReportTypeInfo(uint16_t level, uint32_t typeId, std::string& tag);
    int32_t StopReporters();
    void SetSyncReporter();
    void NotifyQuit();

private:
    void FillData(const std::string &saveHashData, SHARED_PTR_ALIA<ProfileFileChunk> fileChunk, bool isLastChunk) const;
    void SaveData(bool isLastChunk);
    ProfReporterMgr();
    ~ProfReporterMgr() override;
    bool isStarted_;
    bool isUploadStarted_;
    bool isSyncReporter_;
    std::mutex regTypeInfoMtx_;
    std::mutex startMtx_;
    std::mutex notifyMtx_;
    std::condition_variable cv_;
    std::unordered_map<uint16_t, std::unordered_map<uint32_t, std::string>> reportTypeInfoMap_;
    std::unordered_map<uint16_t, std::vector<std::pair<uint32_t, std::string>>> reportTypeInfoMapVec_;
    std::unordered_map<uint16_t, uint32_t> indexMap_;
    std::vector<Msprof::Engine::MsprofReporter> reporters_;
};
}
}
}
#endif