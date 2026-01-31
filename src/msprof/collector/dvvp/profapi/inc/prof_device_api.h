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
#ifndef PROF_DEVICE_API_H
#define PROF_DEVICE_API_H

#include <map>
#include <string>
#include "aprof_pub.h"
#include "singleton/singleton.h"
namespace ProfAPI {
class ProfDevApi : public analysis::dvvp::common::singleton::Singleton<ProfDevApi> {
public:
    ProfDevApi();
    ~ProfDevApi() override;
    int32_t ProfInit(uint32_t dataType, void *data, uint32_t dataLen);
    int32_t ProfRegisterCallback(uint32_t moduleId, ProfCommandHandle handle);
    int32_t ProfFinalize();
    uint64_t ProfStr2Id(const char *hashInfo, size_t length);
    int32_t ProfReportAdditionalInfo(uint32_t agingFlag, const void *data, uint32_t length);
    int32_t ProfReportBatchAdditionalInfo(uint32_t nonPersistantFlag, const void *data, uint32_t length);
    size_t ProfGetBatchReportMaxSize(uint32_t type);

private:
    void *libHandle_{nullptr};
    std::map<std::string, void *> funcMap_;
};
}
#endif