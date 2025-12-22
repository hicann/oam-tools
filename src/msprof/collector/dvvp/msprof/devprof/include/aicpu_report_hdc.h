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

#ifndef AICPU_REPORT_HDC_H
#define AICPU_REPORT_HDC_H
#include "singleton/singleton.h"
#include "data_dumper.h"
#include "receive_data.h"


class AicpuReportHdc : public analysis::dvvp::common::singleton::Singleton<AicpuReportHdc> {
public:
    AicpuReportHdc();
    ~AicpuReportHdc() override;
public:
    int32_t Init(std::string &moduleName);
    int32_t UnInit();
    int32_t Report(Msprof::Engine::CONST_REPORT_DATA_PTR rData) const;
private:
    bool started_{false};
    SHARED_PTR_ALIA<Msprof::Engine::DataDumper> reporter_;
    std::mutex mtx_;
};
#endif