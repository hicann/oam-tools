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
#include "prof_diagnostic_job.h"
#include "file_transport.h"

using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::message;
using namespace Analysis::Dvvp::JobWrapper;
using namespace analysis::dvvp::common::utils;
using namespace Analysis::Dvvp::MsprofErrMgr;
using namespace Analysis::Dvvp::Common::Platform;

class JOB_WRAPPER_PROF_DIAGNOSTIC_JOB_TEST: public testing::Test {
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
    }
public:
    std::shared_ptr<Analysis::Dvvp::JobWrapper::CollectionJobCfg> collectionJobCfg_;
};

TEST_F(JOB_WRAPPER_PROF_DIAGNOSTIC_JOB_TEST, Init) {
    GlobalMockObject::verify();
    MOCKER_CPP(&Analysis::Dvvp::Common::Platform::Platform::GetPlatformType)
        .stubs()
        .will(returnValue(5));
    Platform::instance()->Init();
    auto ProfDiagnostic = std::make_shared<Analysis::Dvvp::JobWrapper::ProfDiagnostic>();
    do {
        EXPECT_NE(ProfDiagnostic, nullptr);
        if (ProfDiagnostic == nullptr) {
            break;
        }
        EXPECT_EQ(PROFILING_NOTSUPPORT, ProfDiagnostic->Init(collectionJobCfg_));
        collectionJobCfg_->comParams->params->hostProfiling = true;
        EXPECT_EQ(PROFILING_SUCCESS, ProfDiagnostic->Init(collectionJobCfg_));
    } while (0);
}

int32_t UtDlcloseStub(void *handle)
{
    return 0;
}

int32_t g_cliDlopenStubs;
void * UtDlopenStub(const char *fileName, int mode)
{
    if (strcmp(fileName, "libdrvdsmi_host.so") == 0) {
        return &g_cliDlopenStubs;
    }
    return nullptr;
}

int32_t g_faultCount = 0;
int32_t dsmiReadFaultEventStub(int32_t device_id, int timeout, struct dsmi_event_filter filter,
    struct dsmi_event *event)
{
    usleep(5); // 5us
    if (g_faultCount == 2) {
        g_faultCount++;
        return DRV_ERROR_SEND_MESG;
    }
    if (g_faultCount == 0) {
        g_faultCount++;
        return DRV_ERROR_WAIT_TIMEOUT;
    }
    event->type = DMS_FAULT_EVENT;
    event->event_t.dms_event.event_id = 0x81AD8605;
    event->event_t.dms_event.deviceid = 0;
    event->event_t.dms_event.severity = 3;
    event->event_t.dms_event.assertion = 1;
    event->event_t.dms_event.alarm_raised_time = 1622697600;
    strcpy_s(event->event_t.dms_event.event_name, sizeof(event->event_t.dms_event.event_name), "test_error");
    strcpy_s(event->event_t.dms_event.additional_info, sizeof(event->event_t.dms_event.additional_info), "add_info");
    g_faultCount++;
    return DRV_ERROR_NONE;
}

static void *UtDlsymStub(void *handle, const char *symbol) {
    std::string symbol_str = symbol;
    if (symbol_str == "dsmi_read_fault_event") {
        return (void *)dsmiReadFaultEventStub;
    }
    return (void *)0x87654321;
}

TEST_F(JOB_WRAPPER_PROF_DIAGNOSTIC_JOB_TEST, Start) {
    GlobalMockObject::verify();
    MOCKER_CPP(&Analysis::Dvvp::Common::Platform::Platform::GetPlatformType)
        .stubs()
        .will(returnValue(5));
    MOCKER(dlclose).stubs().will(invoke(UtDlcloseStub));
    MOCKER(dlopen).stubs().will(invoke(UtDlopenStub));
    MOCKER(dlsym).stubs().will(invoke(UtDlsymStub));

    std::shared_ptr<FILETransport> trans(new FILETransport("./tmp", "200MB"));
    auto uploader = std::make_shared<analysis::dvvp::transport::Uploader>(trans);
    MOCKER_CPP(&analysis::dvvp::transport::UploaderMgr::GetUploader)
        .stubs()
        .with(any(), outBound(uploader));
    MOCKER_CPP(&Uploader::UploadData, int(Uploader::*)(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk>))
        .stubs()
        .will(returnValue(PROFILING_SUCCESS));

    Platform::instance()->Init();
    auto ProfDiagnostic = std::make_shared<Analysis::Dvvp::JobWrapper::ProfDiagnostic>();
    do {
        EXPECT_NE(ProfDiagnostic, nullptr);
        if (ProfDiagnostic == nullptr) {
            break;
        }
        EXPECT_EQ(PROFILING_SUCCESS, ProfDiagnostic->Process());
        usleep(100);
        EXPECT_EQ(PROFILING_SUCCESS, ProfDiagnostic->Uninit());
    } while (0);
}