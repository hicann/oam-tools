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

#ifndef DEVPROF_API_H
#define DEVPROF_API_H

#include <map>
#include <string>
#include "prof_dev_api.h"

class DevprofApi {
public:
    DevprofApi();
    ~DevprofApi();
    int32_t CheckFeatureIsOn(uint64_t feature);
    int32_t Start(int32_t argc, const char *argv[]);
    int32_t Stop();
    int32_t GetIsExit();
    uint64_t GetHashId(const char *hashInfo, size_t length);
    int32_t AicpuStartRegister(AicpuStartFunc aicpuStartCallback, const struct AicpuStartPara *para);
    int32_t ReportAdditionalInfo(uint32_t nonPersistantFlag, const void *data, uint32_t length);
    int32_t ReportBatchAdditionalInfo(uint32_t nonPersistantFlag, const void *data, uint32_t length);
    size_t GetBatchReportMaxSize(uint32_t type);

    static DevprofApi *Instance() { return &item_; }

private:
    void *libHandle_{nullptr};
    std::map<std::string, void *> funcMap_;
    static DevprofApi item_;
};
#endif