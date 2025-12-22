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
 
#ifndef ANALYSIS_DVVP_PROFILER_MSPROF_REPORTER_H
#define ANALYSIS_DVVP_PROFILER_MSPROF_REPORTER_H

#include "acl/acl_base.h"
#include "data_dumper.h"
#include "utils/utils.h"
#include "prof_api.h"

namespace Msprof {
namespace Engine {
using namespace analysis::dvvp::common::utils;

class MsprofReporter {
public:
    MsprofReporter();
    explicit MsprofReporter(const std::string module);
    ~MsprofReporter();

public:
    int32_t HandleReportRequest(uint32_t type, VOID_PTR data, uint32_t len);
    void ForceFlush();
    int32_t SendData(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunk);
    int32_t StartReporter();
    int32_t StopReporter();

public:
    static void InitReporters();

public:
    static std::map<uint32_t, MsprofReporter> reporters_;

private:
    int32_t ReportData(CONST_VOID_PTR data, uint32_t len) const;
    int32_t FlushData() const;
    int32_t GetDataMaxLen(VOID_PTR data, uint32_t len) const;
    int32_t GetHashId(VOID_PTR data, uint32_t len) const;

private:
    std::string module_;
    SHARED_PTR_ALIA<Msprof::Engine::DataDumper> reporter_{nullptr};
};

void FlushAllModule();
void FlushModule();
int32_t SendAiCpuData(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunk);
}  // namespace Engine
}  // namespace Msprof

#endif
