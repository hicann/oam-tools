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
#include<functional>
#include "utils/utils.h"
#include "error_code.h"
#include "adprof_collector_proxy.h"

using namespace analysis::dvvp::common::error;

AdprofCollectorProxy::AdprofCollectorProxy()
{
}

AdprofCollectorProxy::~AdprofCollectorProxy()
{
}

int32_t AdprofCollectorProxy::BindFunction(
    std::function<int32_t(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk>)> reportFunc = nullptr,
    std::function<bool()> adprofStartedFunc = nullptr)
{
    reportFunctionPointer = reportFunc;
    adprofStartedFunctionPointer = adprofStartedFunc;
    return PROFILING_SUCCESS;
}

int32_t AdprofCollectorProxy::Report(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunk)
{
    if (reportFunctionPointer == nullptr) {
        return PROFILING_FAILED;
    }
    return reportFunctionPointer(fileChunk);
}

bool AdprofCollectorProxy::AdprofStarted()
{
    if (adprofStartedFunctionPointer == nullptr) {
        return false;
    }
    return adprofStartedFunctionPointer();
}