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

#ifndef ANALYSIS_DVVP_JOB_FACTORY_H
#define ANALYSIS_DVVP_JOB_FACTORY_H

#include "job_adapter.h"

namespace Analysis {
namespace Dvvp {
namespace JobWrapper {
class JobFactory {
public:
    JobFactory();
    virtual ~JobFactory();
};

class JobSocFactory : public JobFactory {
public:
    JobSocFactory();
    ~JobSocFactory() override;
public:
    SHARED_PTR_ALIA<JobAdapter> CreateJobAdapter(int32_t devIndexId) const;
};
}}}

#endif
