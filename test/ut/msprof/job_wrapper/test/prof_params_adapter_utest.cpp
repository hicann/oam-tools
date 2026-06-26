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
#include "acl/acl_prof.h"
#include "config/config.h"
#include "errno/error_code.h"
#include "json/json.h"
#include "message/prof_params.h"
#include "platform/platform.h"
#include "prof_params_adapter.h"
#include "validation/param_validation.h"

using namespace analysis::dvvp::common::config;
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::validation;
using namespace Analysis::Dvvp::Common::Platform;
using namespace Analysis::Dvvp::Host::Adapter;

namespace {
using ProfileParamsPtr = std::shared_ptr<analysis::dvvp::message::ProfileParams>;

std::shared_ptr<ProfParamsAdapter> NewAdapter()
{
    return std::make_shared<ProfParamsAdapter>();
}

ProfileParamsPtr NewParams()
{
    return std::make_shared<analysis::dvvp::message::ProfileParams>();
}

std::shared_ptr<ProfApiStartReq> NewStartReq()
{
    return std::make_shared<ProfApiStartReq>();
}

std::shared_ptr<ProfApiSysConf> NewSysConf()
{
    return std::make_shared<ProfApiSysConf>();
}
}

class JOB_WRAPPER_PROF_PARAMS_ADAPTER_UTEST : public testing::Test {
protected:
    void TearDown() override
    {
        GlobalMockObject::verify();
    }
};

TEST_F(JOB_WRAPPER_PROF_PARAMS_ADAPTER_UTEST, InitAndStartReqTransfer)
{
    auto adapter = NewAdapter();
    auto params = NewParams();
    EXPECT_EQ(PROFILING_SUCCESS, adapter->Init());
    EXPECT_EQ(PROFILING_FAILED, adapter->StartReqTrfToInnerParam(nullptr, params));
    EXPECT_EQ(PROFILING_FAILED, adapter->StartReqTrfToInnerParam(NewStartReq(), nullptr));

    auto req = NewStartReq();
    req->jobId = "job_id";
    req->tsFwTraining = "fw";
    req->hwtsLog = "hwts";
    req->tsTimeline = "timeline";
    req->tsTaskTrack = "task_track";
    req->featureName = "system_trace";
    params->taskTsfw = "on";
    EXPECT_EQ(PROFILING_SUCCESS, adapter->StartReqTrfToInnerParam(req, params));
    EXPECT_EQ("job_id", params->job_id);
    EXPECT_EQ("fw", params->ts_fw_training);
    EXPECT_EQ("hwts", params->hwts_log);
    EXPECT_EQ("timeline", params->ts_timeline);
    EXPECT_EQ("task_track", params->ts_task_track);
    EXPECT_EQ("off", params->hwts_log1);
}

TEST_F(JOB_WRAPPER_PROF_PARAMS_ADAPTER_UTEST, StartCfgTransfer)
{
    auto adapter = NewAdapter();
    auto params = NewParams();
    adapter->StartCfgTrfToInnerParam(PROF_TASK_TSFW_MASK | PROF_TASK_TIME_MASK | PROF_AICPU_TRACE_MASK, params);
    EXPECT_EQ("on", params->taskTsfw);
    EXPECT_EQ(MSVP_PROF_ON, params->ts_memcpy);
    EXPECT_EQ(MSVP_PROF_ON, params->stars_acsq_task);
    EXPECT_EQ(MSVP_PROF_ON, params->aicpuTrace);
}

TEST_F(JOB_WRAPPER_PROF_PARAMS_ADAPTER_UTEST, HostSysValidationAndSetters)
{
    auto adapter = NewAdapter();
    EXPECT_TRUE(adapter->CheckHostSysValid("cpu,mem"));

    MOCKER_CPP(&ParamValidation::CheckHostSysOptionsIsValid)
        .stubs()
        .will(returnValue(false));
    EXPECT_FALSE(adapter->CheckHostSysValid("invalid"));
    GlobalMockObject::verify();

    MOCKER_CPP(&ParamValidation::CheckHostSysUsageOptionsIsValid)
        .stubs()
        .will(returnValue(true));
    EXPECT_TRUE(adapter->CheckHostSysUsageValid("cpu"));
    GlobalMockObject::verify();

    MOCKER_CPP(&ParamValidation::CheckHostSysUsageOptionsIsValid)
        .stubs()
        .will(returnValue(false));
    EXPECT_FALSE(adapter->CheckHostSysUsageValid("invalid"));

    auto params = NewParams();
    adapter->SetHostSysParam("cpu,mem,network,disk,osrt,numa,unknown", params);
    EXPECT_EQ("on", params->host_cpu_profiling);
    EXPECT_EQ("on", params->host_mem_profiling);
    EXPECT_EQ("on", params->host_network_profiling);
    EXPECT_EQ("on", params->host_disk_profiling);
    EXPECT_EQ("on", params->host_osrt_profiling);
    EXPECT_EQ("on", params->host_numa_profiling);

    auto usageParams = NewParams();
    adapter->SetHostSysUsageParam("cpu,mem,unknown", usageParams);
    EXPECT_EQ("on", usageParams->hostAllPidCpuProfiling);
    EXPECT_EQ("on", usageParams->hostAllPidMemProfiling);
}

TEST_F(JOB_WRAPPER_PROF_PARAMS_ADAPTER_UTEST, EncodeDecodeSysConfJson)
{
    auto adapter = NewAdapter();
    EXPECT_TRUE(adapter->EncodeSysConfJson(nullptr).empty());

    auto sysConf = NewSysConf();
    sysConf->aicoreSamplingInterval = 10;
    sysConf->cpuSamplingInterval = 20;
    sysConf->sysSamplingInterval = 30;
    sysConf->appSamplingInterval = 40;
    sysConf->hardwareMemSamplingInterval = 50;
    sysConf->ioSamplingInterval = 60;
    sysConf->interconnectionSamplingInterval = 70;
    sysConf->dvppSamplingInterval = 80;
    sysConf->aivSamplingInterval = 90;
    sysConf->aicoreMetrics = "PipeUtilization";
    sysConf->aivMetrics = "VecRatio";
    sysConf->l2 = "on";
    const std::string encoded = adapter->EncodeSysConfJson(sysConf);
    EXPECT_FALSE(encoded.empty());

    auto decoded = adapter->DecodeSysConfJson(encoded);
    ASSERT_NE(nullptr, decoded);
    EXPECT_EQ(10U, decoded->aicoreSamplingInterval);
    EXPECT_EQ("PipeUtilization", decoded->aicoreMetrics);
    EXPECT_EQ(nullptr, adapter->DecodeSysConfJson(""));
    EXPECT_EQ(nullptr, adapter->DecodeSysConfJson("not-json"));
}

TEST_F(JOB_WRAPPER_PROF_PARAMS_ADAPTER_UTEST, HandleTraceConfAndUpdateSysConf)
{
    auto adapter = NewAdapter();
    std::string oversized(2 * 1024 * 1024, 'a');
    EXPECT_EQ(PROFILING_FAILED, adapter->HandleTaskTraceConf(oversized, NewParams()));
    EXPECT_EQ(PROFILING_FAILED, adapter->HandleTaskTraceConf("{}", nullptr));
    EXPECT_EQ(PROFILING_FAILED, adapter->HandleSystemTraceConf(oversized, NewParams()));
    EXPECT_EQ(PROFILING_FAILED, adapter->HandleSystemTraceConf("{}", nullptr));
    EXPECT_EQ(PROFILING_SUCCESS, adapter->HandleSystemTraceConf("", NewParams()));

    adapter->UpdateSysConf(nullptr, NewParams());
    adapter->UpdateSysConf(NewSysConf(), nullptr);
    auto sysConf = NewSysConf();
    sysConf->cpuSamplingInterval = 5;
    sysConf->sysSamplingInterval = 6;
    sysConf->appSamplingInterval = 7;
    sysConf->hardwareMemSamplingInterval = 8;
    sysConf->ioSamplingInterval = 9;
    sysConf->interconnectionSamplingInterval = 10;
    sysConf->dvppSamplingInterval = 11;
    sysConf->aicoreSamplingInterval = 12;
    sysConf->aivSamplingInterval = 13;
    sysConf->aicoreMetrics = "PipeUtilization";
    sysConf->aivMetrics = "VecRatio";
    auto params = NewParams();
    adapter->UpdateSysConf(sysConf, params);
    EXPECT_EQ("on", params->cpu_profiling);
    EXPECT_EQ("on", params->sys_profiling);
    EXPECT_EQ("on", params->pid_profiling);
    EXPECT_EQ("on", params->hardware_mem);
    EXPECT_EQ("on", params->io_profiling);
    EXPECT_EQ("on", params->interconnection_profiling);
    EXPECT_EQ("on", params->dvpp_profiling);
    EXPECT_EQ("on", params->ai_core_profiling);
    EXPECT_EQ("on", params->aiv_profiling);
}

TEST_F(JOB_WRAPPER_PROF_PARAMS_ADAPTER_UTEST, SetSystemTraceParams)
{
    auto adapter = NewAdapter();
    adapter->SetSystemTraceParams(nullptr, NewParams());
    adapter->SetSystemTraceParams(NewParams(), nullptr);

    auto dst = NewParams();
    auto src = NewParams();
    dst->cpu_profiling = "on";
    dst->io_profiling = "on";
    dst->interconnection_profiling = "on";
    dst->hardware_mem = "on";
    dst->hardware_mem_sampling_interval = 20000;
    dst->isCancel = true;
    src->ts_cpu_profiling_events = "0x11";
    src->ai_ctrl_cpu_profiling_events = "0x8";
    src->llc_profiling_events = "read";
    src->ddr_profiling_events = "read,write";
    src->hbm_profiling_events = "read,write";
    adapter->SetSystemTraceParams(dst, src);
    EXPECT_EQ("on", dst->tsCpuProfiling);
    EXPECT_EQ("on", dst->aiCtrlCpuProfiling);
    EXPECT_EQ("on", dst->nicProfiling);
    EXPECT_EQ("on", dst->pcieProfiling);
    EXPECT_EQ("on", dst->ddr_profiling);
    EXPECT_EQ("on", dst->memProfiling);
}

TEST_F(JOB_WRAPPER_PROF_PARAMS_ADAPTER_UTEST, CheckApiConfigIsValidBranches)
{
    auto adapter = NewAdapter();
    auto params = NewParams();
    EXPECT_EQ(PROFILING_FAILED, adapter->CheckApiConfigIsValid(nullptr, ACL_PROF_STORAGE_LIMIT, "100MB"));

    MOCKER_CPP(&ParamValidation::CheckStorageLimit)
        .stubs()
        .will(returnValue(true));
    EXPECT_EQ(PROFILING_SUCCESS, adapter->CheckApiConfigIsValid(params, ACL_PROF_STORAGE_LIMIT, "100MB"));
    EXPECT_EQ("100MB", params->storageLimit);
    GlobalMockObject::verify();

    MOCKER_CPP(&ParamValidation::CheckLlcConfigValid)
        .stubs()
        .will(returnValue(true));
    EXPECT_EQ(PROFILING_SUCCESS, adapter->CheckApiConfigIsValid(params, ACL_PROF_LLC_MODE, "Bandwidth"));
    EXPECT_EQ("Bandwidth", params->llc_profiling);
    GlobalMockObject::verify();

    MOCKER_CPP(&ParamValidation::CheckArgRange)
        .stubs()
        .will(returnValue(true));
    EXPECT_EQ(PROFILING_SUCCESS, adapter->CheckApiConfigIsValid(params, ACL_PROF_SYS_IO_FREQ, "10"));
    EXPECT_EQ("on", params->io_profiling);
    EXPECT_EQ(PROFILING_SUCCESS, adapter->CheckApiConfigIsValid(params, ACL_PROF_SYS_INTERCONNECTION_FREQ, "10"));
    EXPECT_EQ("on", params->interconnection_profiling);
    EXPECT_EQ(PROFILING_SUCCESS, adapter->CheckApiConfigIsValid(params, ACL_PROF_DVPP_FREQ, "10"));
    EXPECT_EQ("on", params->dvpp_profiling);
    EXPECT_EQ(PROFILING_SUCCESS, adapter->CheckApiConfigIsValid(params, ACL_PROF_HOST_SYS_USAGE_FREQ, "10"));
    EXPECT_EQ(PROFILING_SUCCESS, adapter->CheckApiConfigIsValid(params, ACL_PROF_LOW_POWER_FREQ, "10"));
}

TEST_F(JOB_WRAPPER_PROF_PARAMS_ADAPTER_UTEST, CheckApiConfigSupportBranches)
{
    auto adapter = NewAdapter();
    EXPECT_EQ(PROFILING_SUCCESS, adapter->CheckApiConfigSupport(ACL_PROF_STORAGE_LIMIT));

    MOCKER(&Platform::CheckIfSupport, bool (Platform::*)(const PlatformFeature) const)
        .stubs()
        .will(returnValue(true));
    EXPECT_EQ(PROFILING_SUCCESS, adapter->CheckApiConfigSupport(ACL_PROF_LLC_MODE));
    GlobalMockObject::verify();

    MOCKER(&Platform::CheckIfSupport, bool (Platform::*)(const PlatformFeature) const)
        .stubs()
        .will(returnValue(false));
    EXPECT_EQ(PROFILING_FAILED, adapter->CheckApiConfigSupport(ACL_PROF_LLC_MODE));
    EXPECT_EQ(PROFILING_FAILED, adapter->CheckApiConfigSupport(static_cast<aclprofConfigType>(0xFFFF)));
}

TEST_F(JOB_WRAPPER_PROF_PARAMS_ADAPTER_UTEST, CheckJsonConfigBranches)
{
    auto adapter = NewAdapter();
    NanoJson::JsonValue strVal;
    strVal = std::string("PipeUtilization");
    MOCKER_CPP(&ParamValidation::CheckAicoreMetricsIsValid)
        .stubs()
        .will(returnValue(true));
    EXPECT_TRUE(adapter->CheckJsonConfig("aic_metrics", strVal));
    GlobalMockObject::verify();

    strVal = std::string("on");
    MOCKER_CPP(&ParamValidation::CheckParamL0L1Invalid)
        .stubs()
        .will(returnValue(true));
    EXPECT_TRUE(adapter->CheckJsonConfig("task_trace", strVal));
    GlobalMockObject::verify();

    NanoJson::JsonValue freqVal;
    freqVal = static_cast<uint32_t>(10);
    MOCKER_CPP(&ParamValidation::CheckFreqIsValid)
        .stubs()
        .will(returnValue(true));
    EXPECT_TRUE(adapter->CheckJsonConfig("sys_io_sampling_freq", freqVal));
    GlobalMockObject::verify();

    strVal = std::string("Bandwidth");
    MOCKER_CPP(&ParamValidation::CheckLlcConfigValid)
        .stubs()
        .will(returnValue(true));
    EXPECT_TRUE(adapter->CheckJsonConfig("llc_profiling", strVal));
    GlobalMockObject::verify();

    strVal = std::string("cpu");
    MOCKER_CPP(&ParamValidation::CheckHostSysOptionsIsValid)
        .stubs()
        .will(returnValue(true));
    EXPECT_TRUE(adapter->CheckJsonConfig("host_sys", strVal));
    GlobalMockObject::verify();

    MOCKER_CPP(&ParamValidation::CheckHostSysUsageOptionsIsValid)
        .stubs()
        .will(returnValue(true));
    EXPECT_TRUE(adapter->CheckJsonConfig("host_sys_usage", strVal));
    GlobalMockObject::verify();

    MOCKER_CPP(&ParamValidation::CheckMemServiceflowValid)
        .stubs()
        .will(returnValue(true));
    EXPECT_TRUE(adapter->CheckJsonConfig("sys_mem_serviceflow", strVal));
    GlobalMockObject::verify();

    MOCKER_CPP(&ParamValidation::CheckParamEmptyInvalid)
        .stubs()
        .will(returnValue(true));
    EXPECT_TRUE(adapter->CheckJsonConfig("unknown", strVal));
}

TEST_F(JOB_WRAPPER_PROF_PARAMS_ADAPTER_UTEST, LlcEventHelpers)
{
    auto adapter = NewAdapter();
    EXPECT_FALSE(adapter->GenerateCapacityEvents().empty());
    EXPECT_FALSE(adapter->GenerateBandwidthEvents().empty());
}
