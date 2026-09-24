/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2026. All rights reserved.
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
#include <memory>
#include <string>
#include <vector>
#include "ai_drv_prof_api.h"
#include "config/config.h"
#include "errno/error_code.h"
#include "json_parser.h"
#include "platform/platform.h"
#include "prof_channel_manager.h"
#include "prof_hwts_log_job.h"

using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::message;
using namespace Analysis::Dvvp::JobWrapper;

using Platform = Analysis::Dvvp::Common::Platform::Platform;
using PlatformFeature = Analysis::Dvvp::Common::Platform::PlatformFeature;

namespace {
void MockPlatformSupport(bool isSupport)
{
    MOCKER_CPP(&Platform::CheckIfSupport, bool(Platform::*)(const PlatformFeature) const)
        .stubs()
        .will(returnValue(isSupport));
}

void MockChannelValid(bool isValid)
{
    MOCKER_CPP(&analysis::dvvp::driver::DrvChannelsMgr::ChannelIsValid).stubs().will(returnValue(isValid));
}

void MockChannelPoller(const std::shared_ptr<analysis::dvvp::transport::ChannelPoll>& poller)
{
    MOCKER_CPP(&ProfChannelManager::GetChannelPoller).stubs().will(returnValue(poller));
}
} // namespace

class JOB_WRAPPER_PROF_HWTS_LOG_F_DIE_JOB_TEST : public testing::Test {
protected:
    void SetUp() override
    {
        collectionJobCfg_ = std::make_shared<CollectionJobCfg>();
        std::shared_ptr<ProfileParams> params(new ProfileParams);
        auto comParams = std::make_shared<CollectionJobCommonParams>();
        comParams->params = params;
        comParams->jobCtx = std::make_shared<JobContext>();
        collectionJobCfg_->comParams = comParams;
        collectionJobCfg_->jobParams.events = std::make_shared<std::vector<std::string>>(0);
        collectionJobCfg_->jobParams.cores = std::make_shared<std::vector<int>>(0);
        collectionJobCfg_->jobParams.dataPath = "fdie_data";
        poller_ = std::make_shared<analysis::dvvp::transport::ChannelPoll>();
    }

    void TearDown() override { collectionJobCfg_.reset(); }

    std::shared_ptr<CollectionJobCfg> collectionJobCfg_;
    std::shared_ptr<analysis::dvvp::transport::ChannelPoll> poller_;
};

TEST_F(JOB_WRAPPER_PROF_HWTS_LOG_F_DIE_JOB_TEST, Init_NullCfg)
{
    GlobalMockObject::verify();

    auto job = std::make_shared<ProfHwtsLogFDieJob>();
    EXPECT_EQ(PROFILING_FAILED, job->Init(nullptr));
}

TEST_F(JOB_WRAPPER_PROF_HWTS_LOG_F_DIE_JOB_TEST, Init_InvalidContext)
{
    GlobalMockObject::verify();

    auto job = std::make_shared<ProfHwtsLogFDieJob>();
    collectionJobCfg_->comParams->params = nullptr;
    EXPECT_EQ(PROFILING_FAILED, job->Init(collectionJobCfg_));
}

TEST_F(JOB_WRAPPER_PROF_HWTS_LOG_F_DIE_JOB_TEST, Init_HostProfilingFailed)
{
    GlobalMockObject::verify();

    auto job = std::make_shared<ProfHwtsLogFDieJob>();
    collectionJobCfg_->comParams->params->hostProfiling = true;
    EXPECT_EQ(PROFILING_FAILED, job->Init(collectionJobCfg_));
}

TEST_F(JOB_WRAPPER_PROF_HWTS_LOG_F_DIE_JOB_TEST, Init_PlatformNotSupport)
{
    GlobalMockObject::verify();
    MockPlatformSupport(false);

    auto job = std::make_shared<ProfHwtsLogFDieJob>();
    EXPECT_EQ(PROFILING_FAILED, job->Init(collectionJobCfg_));
}

TEST_F(JOB_WRAPPER_PROF_HWTS_LOG_F_DIE_JOB_TEST, Init_SwitchOffFailed)
{
    GlobalMockObject::verify();
    MockPlatformSupport(true);

    auto job = std::make_shared<ProfHwtsLogFDieJob>();
    collectionJobCfg_->comParams->params->stars_acsq_task = "off";
    collectionJobCfg_->comParams->params->taskBlock = "off";
    EXPECT_EQ(PROFILING_FAILED, job->Init(collectionJobCfg_));
}

TEST_F(JOB_WRAPPER_PROF_HWTS_LOG_F_DIE_JOB_TEST, Init_TaskBlockOnSuccess)
{
    GlobalMockObject::verify();
    MockPlatformSupport(true);

    auto job = std::make_shared<ProfHwtsLogFDieJob>();
    collectionJobCfg_->comParams->params->taskBlock = MSVP_PROF_ON;
    EXPECT_EQ(PROFILING_SUCCESS, job->Init(collectionJobCfg_));
}

TEST_F(JOB_WRAPPER_PROF_HWTS_LOG_F_DIE_JOB_TEST, Init_StarsAcsqTaskOnSuccess)
{
    GlobalMockObject::verify();
    MockPlatformSupport(true);

    auto job = std::make_shared<ProfHwtsLogFDieJob>();
    collectionJobCfg_->comParams->params->stars_acsq_task = MSVP_PROF_ON;
    EXPECT_EQ(PROFILING_SUCCESS, job->Init(collectionJobCfg_));
}

TEST_F(JOB_WRAPPER_PROF_HWTS_LOG_F_DIE_JOB_TEST, Process_NoCfg)
{
    GlobalMockObject::verify();

    auto job = std::make_shared<ProfHwtsLogFDieJob>();
    EXPECT_EQ(PROFILING_FAILED, job->Process());
}

TEST_F(JOB_WRAPPER_PROF_HWTS_LOG_F_DIE_JOB_TEST, Process_ChannelInvalid)
{
    GlobalMockObject::verify();
    MockPlatformSupport(true);

    auto job = std::make_shared<ProfHwtsLogFDieJob>();
    collectionJobCfg_->comParams->params->taskBlock = MSVP_PROF_ON;
    ASSERT_EQ(PROFILING_SUCCESS, job->Init(collectionJobCfg_));

    MockChannelValid(false);
    EXPECT_EQ(PROFILING_SUCCESS, job->Process());
}

TEST_F(JOB_WRAPPER_PROF_HWTS_LOG_F_DIE_JOB_TEST, Process_StartSuccess)
{
    GlobalMockObject::verify();
    MockPlatformSupport(true);

    auto job = std::make_shared<ProfHwtsLogFDieJob>();
    collectionJobCfg_->comParams->params->taskBlock = MSVP_PROF_ON;
    ASSERT_EQ(PROFILING_SUCCESS, job->Init(collectionJobCfg_));

    MockChannelValid(true);
    MockChannelPoller(poller_);
    MOCKER_CPP(&Msprofiler::Parser::JsonParser::GetJsonChannelPeriod).stubs().will(returnValue((uint32_t)50));
    MOCKER_CPP(&Msprofiler::Parser::JsonParser::GetJsonChannelDriverBufferLen)
        .stubs()
        .will(returnValue((uint32_t)8192));
    MOCKER_CPP(&analysis::dvvp::driver::DrvStarsSocLogStart).stubs().will(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_SUCCESS, job->Process());
}

TEST_F(JOB_WRAPPER_PROF_HWTS_LOG_F_DIE_JOB_TEST, Process_StartFailed)
{
    GlobalMockObject::verify();
    MockPlatformSupport(true);

    auto job = std::make_shared<ProfHwtsLogFDieJob>();
    collectionJobCfg_->comParams->params->taskBlock = MSVP_PROF_ON;
    ASSERT_EQ(PROFILING_SUCCESS, job->Init(collectionJobCfg_));

    MockChannelValid(true);
    MockChannelPoller(poller_);
    MOCKER_CPP(&Msprofiler::Parser::JsonParser::GetJsonChannelPeriod).stubs().will(returnValue((uint32_t)50));
    MOCKER_CPP(&Msprofiler::Parser::JsonParser::GetJsonChannelDriverBufferLen)
        .stubs()
        .will(returnValue((uint32_t)8192));
    MOCKER_CPP(&analysis::dvvp::driver::DrvStarsSocLogStart).stubs().will(returnValue(PROFILING_FAILED));
    EXPECT_EQ(PROFILING_FAILED, job->Process());
}

TEST_F(JOB_WRAPPER_PROF_HWTS_LOG_F_DIE_JOB_TEST, Uninit_NoCfg)
{
    GlobalMockObject::verify();

    auto job = std::make_shared<ProfHwtsLogFDieJob>();
    EXPECT_EQ(PROFILING_SUCCESS, job->Uninit());
}

TEST_F(JOB_WRAPPER_PROF_HWTS_LOG_F_DIE_JOB_TEST, Uninit_ChannelInvalid)
{
    GlobalMockObject::verify();
    MockPlatformSupport(true);

    auto job = std::make_shared<ProfHwtsLogFDieJob>();
    collectionJobCfg_->comParams->params->taskBlock = MSVP_PROF_ON;
    ASSERT_EQ(PROFILING_SUCCESS, job->Init(collectionJobCfg_));

    MockChannelValid(false);
    EXPECT_EQ(PROFILING_SUCCESS, job->Uninit());
}

TEST_F(JOB_WRAPPER_PROF_HWTS_LOG_F_DIE_JOB_TEST, Uninit_StopFailed)
{
    GlobalMockObject::verify();
    MockPlatformSupport(true);

    auto job = std::make_shared<ProfHwtsLogFDieJob>();
    collectionJobCfg_->comParams->params->taskBlock = MSVP_PROF_ON;
    ASSERT_EQ(PROFILING_SUCCESS, job->Init(collectionJobCfg_));

    MockChannelValid(true);
    MockChannelPoller(poller_);
    MOCKER_CPP(&analysis::dvvp::driver::DrvStop).stubs().will(returnValue(PROFILING_FAILED));
    EXPECT_EQ(PROFILING_SUCCESS, job->Uninit());
}

TEST_F(JOB_WRAPPER_PROF_HWTS_LOG_F_DIE_JOB_TEST, Uninit_StopSuccess)
{
    GlobalMockObject::verify();
    MockPlatformSupport(true);

    auto job = std::make_shared<ProfHwtsLogFDieJob>();
    collectionJobCfg_->comParams->params->taskBlock = MSVP_PROF_ON;
    ASSERT_EQ(PROFILING_SUCCESS, job->Init(collectionJobCfg_));

    MockChannelValid(true);
    MockChannelPoller(poller_);
    MOCKER_CPP(&analysis::dvvp::driver::DrvStop).stubs().will(returnValue(PROFILING_SUCCESS));
    EXPECT_EQ(PROFILING_SUCCESS, job->Uninit());
}
