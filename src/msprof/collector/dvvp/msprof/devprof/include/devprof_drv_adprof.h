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
#ifndef DEVPROF_DRV_ADPROF_H
#define DEVPROF_DRV_ADPROF_H

#include <stdint.h>
#include "singleton/singleton.h"
#include "report_buffer.h"
#include "utils.h"

using AdprofStartFunc = int32_t (*)();

struct AdprofCallBack {
    int32_t (*start)();
    int32_t (*stop)();
    void (*exit)();
};

const uint32_t TLV_VERSION = 0x00000100;
const uint32_t TLV_TYPE = 1;

int32_t AdprofStartRegister(struct AdprofCallBack &adprofCallBack, uint32_t devId, int32_t hostPid);
int32_t ReportAdprofFileChunk(const void *data);

class DevprofDrvAdprof : public analysis::dvvp::common::singleton::Singleton<DevprofDrvAdprof> {
public:
    struct AdprofCallBack adprofCallBack_;
    analysis::dvvp::common::queue::ReportBuffer<analysis::dvvp::ProfileFileChunk> adprofFileChunkBuffer{
        analysis::dvvp::ProfileFileChunk{}};
};

#endif