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
#include <mutex>
#include "prof_host_job.h"
#include "config/config.h"
#include "logger/msprof_dlog.h"
#include "platform/platform.h"
#include "uploader_mgr.h"
#include "utils/utils.h"
#include "thread/thread.h"
#include "thread/thread.h"
#include "prof_biu_perf_job.h"
#include "prof_instr_perf_job.h"
#include "file_transport.h"
#include "prof_inner_api.h"
#include "ai_drv_dev_api.h"
#include "mdc_v2_platform.h"

namespace {
std::vector<int32_t> g_startedChannels;

int32_t DrvInstrProfileStartStub(const uint32_t devId, const analysis::dvvp::driver::AI_DRV_CHANNEL channelId,
    void *userData, size_t dataSize)
{
    (void)devId;
    (void)userData;
    (void)dataSize;
    g_startedChannels.push_back(static_cast<int32_t>(channelId));
    return analysis::dvvp::common::error::PROFILING_SUCCESS;
}
}

using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::message;
using namespace Analysis::Dvvp::JobWrapper;
using namespace analysis::dvvp::common::utils;
using namespace Analysis::Dvvp::MsprofErrMgr;
using namespace Analysis::Dvvp::Common::Platform;
using namespace analysis::dvvp::transport;

class JOB_WRAPPER_PROF_BIU_PERF_JOB_TEST: public testing::Test {
protected:
    virtual void SetUp() {
        collectionJobCfg_ = std::make_shared<Analysis::Dvvp::JobWrapper::CollectionJobCfg>();
        std::shared_ptr<analysis::dvvp::message::ProfileParams> params(
            new analysis::dvvp::message::ProfileParams);
        std::shared_ptr<analysis::dvvp::message::JobContext> jobCtx(
            new analysis::dvvp::message::JobContext);
        auto comParams = std::make_shared<Analysis::Dvvp::JobWrapper::CollectionJobCommonParams>();
        comParams->params = params;
        comParams->jobCtx = jobCtx;
        collectionJobCfg_->comParams = comParams;
        collectionJobCfg_->jobParams.events = std::make_shared<std::vector<std::string> >(0);
    }
    virtual void TearDown() {
        collectionJobCfg_.reset();
        GlobalMockObject::verify();
        GlobalMockObject::reset();
    }
public:
    std::shared_ptr<Analysis::Dvvp::JobWrapper::CollectionJobCfg> collectionJobCfg_;
};

TEST_F(JOB_WRAPPER_PROF_BIU_PERF_JOB_TEST, Launch) {
    MOCKER_CPP(&Analysis::Dvvp::Common::Platform::Platform::CheckIfSupport,
        bool (Analysis::Dvvp::Common::Platform::Platform::*)(const Dvvp::Collect::Platform::PlatformFeature) const)
        .stubs()
        .will(returnValue(true));
    auto profBiuPerfJob = std::make_shared<Analysis::Dvvp::JobWrapper::ProfBiuPerfJob>();
    do {
        EXPECT_NE(profBiuPerfJob, nullptr);
        if (profBiuPerfJob == nullptr) {
            break;
        }
        collectionJobCfg_->comParams->params->instrProfiling = "on";
        collectionJobCfg_->comParams->params->hostProfiling = true;
        EXPECT_EQ(PROFILING_FAILED, profBiuPerfJob->Init(collectionJobCfg_));
        collectionJobCfg_->comParams->params->hostProfiling = false;
        EXPECT_EQ(PROFILING_SUCCESS, profBiuPerfJob->Init(collectionJobCfg_));
        collectionJobCfg_->comParams->params->pcSampling = "on";
        EXPECT_EQ(PROFILING_FAILED, profBiuPerfJob->Init(collectionJobCfg_));
        EXPECT_EQ(PROFILING_SUCCESS, profBiuPerfJob->Process());
        EXPECT_EQ(PROFILING_SUCCESS, profBiuPerfJob->Uninit());
    } while (0);
}

TEST_F(JOB_WRAPPER_PROF_BIU_PERF_JOB_TEST, MdcV2InstrProfilingOnlyStartsWhitelistChannels)
{
    g_startedChannels.clear();
    MOCKER_CPP(&Analysis::Dvvp::Common::Platform::Platform::CheckIfSupport,
        bool (Analysis::Dvvp::Common::Platform::Platform::*)(const Dvvp::Collect::Platform::PlatformFeature) const)
        .stubs()
        .will(returnValue(true));
    std::vector<BiuPerfChannelInfo> platformChannels = {
        {0, 0, 0, 11},
        {2, 0, 2, 17},
        {3, 0, 3, 20},
        {5, 0, 5, 26},
    };
    MOCKER_CPP(&Analysis::Dvvp::Common::Platform::Platform::GetBiuPerfChannelInfos,
        std::vector<BiuPerfChannelInfo> (Analysis::Dvvp::Common::Platform::Platform::*)(
            const std::vector<uint32_t> &, uint32_t) const)
        .stubs()
        .will(returnValue(platformChannels));
    int64_t aiCoreNum = 8;
    MOCKER(analysis::dvvp::driver::DrvGetAiCoreNum)
        .stubs()
        .with(any(), outBound(aiCoreNum))
        .will(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&analysis::dvvp::driver::DrvChannelsMgr::ChannelIsValid)
        .stubs()
        .will(returnValue(true));
    MOCKER(analysis::dvvp::driver::DrvInstrProfileStart)
        .stubs()
        .will(invoke(DrvInstrProfileStartStub));

    auto profBiuPerfJob = std::make_shared<Analysis::Dvvp::JobWrapper::ProfBiuPerfJob>();
    collectionJobCfg_->comParams->params->instrProfiling = "on";
    collectionJobCfg_->comParams->params->pcSampling = "off";
    collectionJobCfg_->comParams->params->hostProfiling = false;
    EXPECT_EQ(PROFILING_SUCCESS, profBiuPerfJob->Init(collectionJobCfg_));
    EXPECT_EQ(PROFILING_SUCCESS, profBiuPerfJob->Process());

    std::vector<int32_t> expectedChannels = {11, 17, 20, 26};
    EXPECT_EQ(expectedChannels, g_startedChannels);
}

TEST_F(JOB_WRAPPER_PROF_BIU_PERF_JOB_TEST, BiuPerfJobErrorBranches)
{
    g_startedChannels.clear();
    MOCKER_CPP(&Analysis::Dvvp::Common::Platform::Platform::CheckIfSupport,
        bool (Analysis::Dvvp::Common::Platform::Platform::*)(const Dvvp::Collect::Platform::PlatformFeature) const)
        .stubs()
        .will(returnValue(true));
    std::vector<BiuPerfChannelInfo> platformChannels = {
        {0, 0, 0, 11},
        {1, 0, 1, 14},
    };
    MOCKER_CPP(&Analysis::Dvvp::Common::Platform::Platform::GetBiuPerfChannelInfos,
        std::vector<BiuPerfChannelInfo> (Analysis::Dvvp::Common::Platform::Platform::*)(
            const std::vector<uint32_t> &, uint32_t) const)
        .stubs()
        .will(returnValue(platformChannels));
    int64_t aiCoreNum = 8;
    MOCKER(analysis::dvvp::driver::DrvGetAiCoreNum)
        .stubs()
        .with(any(), outBound(aiCoreNum))
        .will(returnValue(PROFILING_SUCCESS));
    // ChannelIsValid sequence: true, false, true, false
    // Process ch1: valid → DrvStart fails → lines 150-152
    // Process ch2: invalid → lines 134-135
    // Uninit ch1: valid → DrvStop fails → line 173
    // Uninit ch2: invalid → lines 168-169
    MOCKER_CPP(&analysis::dvvp::driver::DrvChannelsMgr::ChannelIsValid)
        .stubs()
        .will(returnValue(true))
        .then(returnValue(false))
        .then(returnValue(true))
        .then(returnValue(false));
    MOCKER(analysis::dvvp::driver::DrvInstrProfileStart)
        .stubs()
        .will(returnValue(PROFILING_FAILED));
    MOCKER(prof_stop)
        .stubs()
        .will(returnValue(PROF_ERROR));

    auto profBiuPerfJob = std::make_shared<Analysis::Dvvp::JobWrapper::ProfBiuPerfJob>();
    collectionJobCfg_->comParams->params->instrProfiling = "on";
    collectionJobCfg_->comParams->params->pcSampling = "off";
    collectionJobCfg_->comParams->params->hostProfiling = false;
    EXPECT_EQ(PROFILING_SUCCESS, profBiuPerfJob->Init(collectionJobCfg_));
    EXPECT_EQ(PROFILING_FAILED, profBiuPerfJob->Process());
    EXPECT_EQ(PROFILING_FAILED, profBiuPerfJob->Uninit());
}

TEST_F(JOB_WRAPPER_PROF_BIU_PERF_JOB_TEST, MdcV2GetBiuPerfChannelInfosReturnsWhitelist)
{
    using namespace Dvvp::Collect::Platform;
    MdcV2Platform mdcV2Platform;
    std::vector<uint32_t> groupVector = {0, 2, 3, 5};
    auto infos = mdcV2Platform.GetBiuPerfChannelInfos(groupVector, groupVector.size());
    // MdcV2 returns a fixed whitelist of 4 channels regardless of input.
    EXPECT_EQ(4u, infos.size());
    std::vector<int32_t> expectedChannelIds = {11, 17, 20, 26};
    for (size_t i = 0; i < infos.size(); i++) {
        EXPECT_EQ(static_cast<int32_t>(infos[i].channelId), expectedChannelIds[i]);
    }
}

// ============ ProfInstrPerfJob tests ============
// Coverage target: prof_instr_perf_job.cpp:71 (MSPROF_LOGI "Begin to start biu profile buffer")

TEST_F(JOB_WRAPPER_PROF_BIU_PERF_JOB_TEST, InstrPerfJob_InitFailed_WhenHostProfiling)
{
    auto job = std::make_shared<Analysis::Dvvp::JobWrapper::ProfInstrPerfJob>();
    ASSERT_NE(job, nullptr);
    collectionJobCfg_->comParams->params->instrProfiling = "on";
    collectionJobCfg_->comParams->params->hostProfiling = true;
    EXPECT_EQ(PROFILING_FAILED, job->Init(collectionJobCfg_));
}

TEST_F(JOB_WRAPPER_PROF_BIU_PERF_JOB_TEST, InstrPerfJob_InitFailed_WhenNotEnabled)
{
    MOCKER_CPP(&Analysis::Dvvp::Common::Platform::Platform::CheckIfSupport,
        bool (Analysis::Dvvp::Common::Platform::Platform::*)(const Dvvp::Collect::Platform::PlatformFeature) const)
        .stubs()
        .will(returnValue(false));
    auto job = std::make_shared<Analysis::Dvvp::JobWrapper::ProfInstrPerfJob>();
    ASSERT_NE(job, nullptr);
    collectionJobCfg_->comParams->params->instrProfiling = "on";
    collectionJobCfg_->comParams->params->hostProfiling = false;
    EXPECT_EQ(PROFILING_FAILED, job->Init(collectionJobCfg_));
}

TEST_F(JOB_WRAPPER_PROF_BIU_PERF_JOB_TEST, InstrPerfJob_ProcessCoversStartBufferLog)
{
    MOCKER_CPP(&Analysis::Dvvp::Common::Platform::Platform::CheckIfSupport,
        bool (Analysis::Dvvp::Common::Platform::Platform::*)(const Dvvp::Collect::Platform::PlatformFeature) const)
        .stubs()
        .will(returnValue(true));
    MOCKER_CPP(&analysis::dvvp::driver::DrvChannelsMgr::ChannelIsValid)
        .stubs()
        .will(returnValue(true));
    MOCKER(analysis::dvvp::driver::DrvInstrProfileStart)
        .stubs()
        .will(returnValue(PROFILING_SUCCESS));
    MOCKER(prof_stop)
        .stubs()
        .will(returnValue(PROFILING_SUCCESS));

    auto job = std::make_shared<Analysis::Dvvp::JobWrapper::ProfInstrPerfJob>();
    ASSERT_NE(job, nullptr);
    collectionJobCfg_->comParams->params->instrProfiling = "on";
    collectionJobCfg_->comParams->params->hostProfiling = false;
    EXPECT_EQ(PROFILING_SUCCESS, job->Init(collectionJobCfg_));
    EXPECT_EQ(PROFILING_SUCCESS, job->Process());
    EXPECT_EQ(PROFILING_SUCCESS, job->Uninit());
}
