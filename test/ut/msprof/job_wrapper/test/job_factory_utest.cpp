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
#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "job_factory.h"

using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::message;
using namespace Analysis::Dvvp::JobWrapper;

class JOB_FACTORY_UTEST : public testing::Test {
protected:
    virtual void SetUp() {}
    virtual void TearDown() {}
};

TEST_F(JOB_FACTORY_UTEST, JobSocFactory_CreateJobAdapter)
{
    std::shared_ptr<JobSocFactory> jobFactory;
    MSVP_MAKE_SHARED0(jobFactory, JobSocFactory, return);
    EXPECT_NE(nullptr, jobFactory);
    EXPECT_NE(nullptr, jobFactory->CreateJobAdapter(0));
}
