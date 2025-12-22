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

#ifndef ADPROF_COLLECTOR_PROXY_H
#define ADPROF_COLLECTOR_PROXY_H
#include <functional>
#include "singleton/singleton.h"
#include "utils/utils.h"

class AdprofCollectorProxy : public analysis::dvvp::common::singleton::Singleton<AdprofCollectorProxy> {
public:
    AdprofCollectorProxy();
    ~AdprofCollectorProxy() override;

public:
    int32_t BindFunction(
        std::function<int32_t(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk>)> reportFunc,
        std::function<bool()> adprofStartedFunc
    );
    int32_t Report(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunk);
    bool AdprofStarted();

private:
    std::function<int32_t(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk>)> reportFunctionPointer{nullptr};
    std::function<bool()> adprofStartedFunctionPointer{nullptr};
};
#endif