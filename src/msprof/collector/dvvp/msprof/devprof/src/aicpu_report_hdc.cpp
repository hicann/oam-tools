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
#include "aicpu_report_hdc.h"
#include <string>
#include <cstdint>
#include "error_code.h"
#include "prof_api.h"
#include "utils.h"
#include "rpc_dumper.h"
#include "message/codec.h"
#include "aicpu_report_hdc.h"

using namespace analysis::dvvp::common::error;
using namespace Msprof::Engine;

AicpuReportHdc::AicpuReportHdc()
{
}
AicpuReportHdc::~AicpuReportHdc()
{
    UnInit();
}

int32_t AicpuReportHdc::Init(std::string &moduleName)
{
    std::lock_guard<std::mutex> lk(mtx_);
    if (started_) {
        return PROFILING_SUCCESS;
    }
    SHARED_PTR_ALIA<RpcDumper> reporter;
    MSVP_MAKE_SHARED1(reporter, RpcDumper, moduleName, return PROFILING_FAILED);
    reporter_ = reporter;
    int32_t ret = reporter_->Start();
    if (ret != PROFILING_SUCCESS) {
        reporter_.reset();
        MSPROF_LOGW("Unable start reporter in aicpu.");
        return ret;
    }
    started_ = true;
    return PROFILING_SUCCESS;
}

int32_t AicpuReportHdc::Report(CONST_REPORT_DATA_PTR rData) const
{
    if (reporter_ == nullptr) {
        MSPROF_LOGE("Reporter is null.");
        return PROFILING_FAILED;
    }
    return reporter_->Report(rData);
}

int32_t AicpuReportHdc::UnInit()
{
    std::lock_guard<std::mutex> lk(mtx_);
    if (reporter_ != nullptr) {
        if (reporter_->Stop() != PROFILING_SUCCESS) {
            MSPROF_LOGE("Aicpu hdc reporter stop failed.");
        }
        reporter_.reset();
        started_ = false;
    }
    return PROFILING_SUCCESS;
}
