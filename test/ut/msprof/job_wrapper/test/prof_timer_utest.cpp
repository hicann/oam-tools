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
#include <cstdio>
#include <mutex>
#include "thread/thread.h"
#include "prof_timer.h"
#include "transport/transport.h"
#include "transport/hdc/hdc_transport.h"
#include "utils/utils.h"

using namespace analysis::dvvp::common::error;
using namespace Analysis::Dvvp::JobWrapper;
using namespace Analysis::Dvvp::MsprofErrMgr;

class PROF_STAT_FILE_HANDLER_TEST : public testing::Test {
protected:
    virtual void SetUp()
    {
        param = std::make_shared<analysis::dvvp::message::ProfileParams>();
        jobCtx = std::make_shared<analysis::dvvp::message::JobContext>();

        auto transport = std::shared_ptr<analysis::dvvp::transport::HDCTransport>(
            new analysis::dvvp::transport::HDCTransport(session));
        upLoader = std::make_shared<analysis::dvvp::transport::Uploader>(transport);
    }
    virtual void TearDown() {}

public:
    unsigned int devId = 0;
    unsigned int bufSize = 10;
    unsigned int sampleIntervalMs = 100;
    std::string srcFileName = "srcFileName";
    std::string retFileName = "retFileName";
    std::shared_ptr<analysis::dvvp::message::ProfileParams> param;
    std::shared_ptr<analysis::dvvp::message::JobContext> jobCtx;

    HDC_SESSION session = (HDC_SESSION)0x12345678;
    std::shared_ptr<analysis::dvvp::transport::Uploader> upLoader;
};

/////////////////////////////////////////////////////////////
TEST_F(PROF_STAT_FILE_HANDLER_TEST, Init)
{
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::common::memory::Chunk::Init).stubs().will(returnValue(false)).then(returnValue(true));

    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_SYS_STAT, devId, bufSize, sampleIntervalMs});
    attr->srcFileName = srcFileName;
    attr->retFileName = retFileName;
    ProcStatFileHandler statHandler(attr, param, jobCtx, upLoader);
    // Inited
    statHandler.isInited_ = true;
    EXPECT_EQ(PROFILING_FAILED, statHandler.Init());
    // buf init failed
    statHandler.isInited_ = false;
    EXPECT_EQ(PROFILING_FAILED, statHandler.Init());
    // succ
    EXPECT_EQ(PROFILING_SUCCESS, statHandler.Init());
}

TEST_F(PROF_STAT_FILE_HANDLER_TEST, UInit)
{
    GlobalMockObject::verify();

    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_SYS_STAT, devId, bufSize, sampleIntervalMs});
    attr->srcFileName = srcFileName;
    attr->retFileName = retFileName;
    ProcStatFileHandler statHandler(attr, param, jobCtx, upLoader);
    statHandler.isInited_ = false;
    // UInited
    EXPECT_EQ(PROFILING_SUCCESS, statHandler.Uinit());
    // succ
    statHandler.isInited_ = true;
    EXPECT_EQ(PROFILING_SUCCESS, statHandler.Uinit());
}

TEST_F(PROF_STAT_FILE_HANDLER_TEST, Execute)
{
    GlobalMockObject::verify();

    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_SYS_STAT, devId, bufSize, sampleIntervalMs});
    attr->srcFileName = srcFileName;
    attr->retFileName = retFileName;
    ProcStatFileHandler statHandler(attr, param, jobCtx, upLoader);

    // Not Inited
    EXPECT_EQ(PROFILING_SUCCESS, statHandler.Execute());
    // prevTimeStamp_ break;
    MOCKER(analysis::dvvp::common::utils::Utils::GetClockMonotonicRaw).stubs().will(returnValue((unsigned long long)1));
    EXPECT_EQ(PROFILING_SUCCESS, statHandler.Init());
    statHandler.prevTimeStamp_ = 1;
    statHandler.sampleIntervalNs_ = 1;
    EXPECT_EQ(PROFILING_SUCCESS, statHandler.Execute());
    // open file failed
    statHandler.prevTimeStamp_ = 0;
    statHandler.srcFileName_ = "./test/test";
    EXPECT_EQ(PROFILING_SUCCESS, statHandler.Execute());
    // srcFileName is empty
    statHandler.srcFileName_ = "";
    MOCKER_CPP_VIRTUAL(&statHandler, &Analysis::Dvvp::JobWrapper::ProcStatFileHandler::ParseProcFile).stubs();
    MOCKER_CPP(&Analysis::Dvvp::JobWrapper::ProcTimerHandler::StoreData).stubs();
    EXPECT_EQ(PROFILING_SUCCESS, statHandler.Execute());
    // succ
    MOCKER_CPP(&Analysis::Dvvp::JobWrapper::ProcTimerHandler::PacketData).stubs();
    statHandler.srcFileName_ = "./test";
    EXPECT_EQ(PROFILING_SUCCESS, statHandler.Execute());
}

TEST_F(PROF_STAT_FILE_HANDLER_TEST, PacketData)
{
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::common::memory::Chunk::Init).stubs().will(returnValue(false)).then(returnValue(true));

    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_SYS_STAT, devId, bufSize, sampleIntervalMs});
    attr->srcFileName = srcFileName;
    attr->retFileName = retFileName;
    ProcStatFileHandler statHandler(attr, param, jobCtx, upLoader);
    EXPECT_EQ(PROFILING_FAILED, statHandler.Init());
    EXPECT_EQ(PROFILING_SUCCESS, statHandler.Init());

    std::string dest;
    std::string data;
    unsigned int headSize = 1;
    // data null
    statHandler.PacketData(dest, data, headSize);
    // succ
    data = "test";
    statHandler.PacketData(dest, data, headSize);
}

TEST_F(PROF_STAT_FILE_HANDLER_TEST, SendData)
{
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::common::memory::Chunk::Init).stubs().will(returnValue(false)).then(returnValue(true));

    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_SYS_STAT, devId, bufSize, sampleIntervalMs});
    attr->srcFileName = srcFileName;
    attr->retFileName = retFileName;
    ProcStatFileHandler statHandler(attr, param, jobCtx, upLoader);
    EXPECT_EQ(PROFILING_FAILED, statHandler.Init());
    EXPECT_EQ(PROFILING_SUCCESS, statHandler.Init());

    MOCKER_CPP(
        &analysis::dvvp::transport::Uploader::UploadData, int(analysis::dvvp::transport::Uploader::*)(const void*, int))
        .stubs()
        .will(returnValue(0));

    std::string buf("test");

    statHandler.SendData(nullptr, 0);
    statHandler.SendData((const unsigned char*)buf.c_str(), buf.size());
}

TEST_F(PROF_STAT_FILE_HANDLER_TEST, FlushBuf)
{
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::common::memory::Chunk::Init).stubs().will(returnValue(false)).then(returnValue(true));

    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_SYS_STAT, devId, bufSize, sampleIntervalMs});
    attr->srcFileName = srcFileName;
    attr->retFileName = retFileName;
    ProcStatFileHandler statHandler(attr, param, jobCtx, upLoader);
    EXPECT_EQ(PROFILING_FAILED, statHandler.Init());
    EXPECT_EQ(PROFILING_SUCCESS, statHandler.Init());

    MOCKER_CPP(&Analysis::Dvvp::JobWrapper::ProcTimerHandler::SendData).stubs();
    statHandler.buf_.usedSize_ = 1;
    statHandler.isInited_ = true;

    statHandler.FlushBuf();
    statHandler.isInited_ = false;
}

TEST_F(PROF_STAT_FILE_HANDLER_TEST, StoreData)
{
    GlobalMockObject::verify();
    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_SYS_STAT, devId, bufSize, sampleIntervalMs});
    attr->srcFileName = srcFileName;
    attr->retFileName = retFileName;
    ProcStatFileHandler statHandler(attr, param, jobCtx, upLoader);

    MOCKER_CPP(&Analysis::Dvvp::JobWrapper::ProcTimerHandler::SendData).stubs();
    MOCKER_CPP(&Analysis::Dvvp::JobWrapper::ProcTimerHandler::FlushBuf).stubs();
    MOCKER(memcpy_s).stubs().will(returnValue(EOF)).then(returnValue(EOK));

    EXPECT_EQ(PROFILING_SUCCESS, statHandler.Init());
    // size = 0
    std::string data;
    statHandler.StoreData(data);
    // memcpy failed
    data = "123";
    statHandler.StoreData(data);
    // free > size; bufSize = 10
    data = "123";
    statHandler.StoreData(data);
    statHandler.StoreData(data);
    // free < size
    data = "1234567890a";
    statHandler.StoreData(data);

    data = "123356789";
    statHandler.StoreData(data);
    EXPECT_EQ(PROFILING_SUCCESS, statHandler.Uinit());
}

TEST_F(PROF_STAT_FILE_HANDLER_TEST, ParseProcFile)
{
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::common::memory::Chunk::Init).stubs().will(returnValue(false)).then(returnValue(true));
    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_SYS_STAT, devId, bufSize, sampleIntervalMs});
    attr->srcFileName = srcFileName;
    attr->retFileName = retFileName;
    ProcStatFileHandler statHandler(attr, param, jobCtx, upLoader);
    EXPECT_EQ(PROFILING_FAILED, statHandler.Init());
    EXPECT_EQ(PROFILING_SUCCESS, statHandler.Init());

    std::ofstream ofs("./test");
    ofs << "cpu" << std::endl;
    ofs << "cpu" << std::endl;
    ofs << "test" << std::endl;
    ofs.close();

    std::string data;
    std::ifstream ifs("./test");
    statHandler.ParseProcFile(ifs, data);
    ifs.close();

    remove("./test");
}
///////////////////////////////////////////////////////////////////////////////////
class PROF_PID_STAT_FILE_HANDLER_TEST : public testing::Test {
protected:
    virtual void SetUp()
    {
        param = std::make_shared<analysis::dvvp::message::ProfileParams>();
        jobCtx = std::make_shared<analysis::dvvp::message::JobContext>();

        auto transport = std::shared_ptr<analysis::dvvp::transport::HDCTransport>(
            new analysis::dvvp::transport::HDCTransport(session));
        upLoader = std::make_shared<analysis::dvvp::transport::Uploader>(transport);
    }
    virtual void TearDown() {}

public:
    unsigned int devId = 0;
    unsigned int bufSize = 10;
    unsigned int sampleIntervalMs = 100;
    std::string srcFileName = "srcFileName";
    std::string retFileName = "retFileName";
    std::shared_ptr<analysis::dvvp::message::ProfileParams> param;
    std::shared_ptr<analysis::dvvp::message::JobContext> jobCtx;

    HDC_SESSION session = (HDC_SESSION)0x12345678;
    std::shared_ptr<analysis::dvvp::transport::Uploader> upLoader;
    unsigned int pid = 1;
};

TEST_F(PROF_PID_STAT_FILE_HANDLER_TEST, ParseProcFile)
{
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::common::memory::Chunk::Init).stubs().will(returnValue(false)).then(returnValue(true));
    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_SYS_STAT, devId, bufSize, sampleIntervalMs});
    attr->srcFileName = srcFileName;
    attr->retFileName = retFileName;
    attr->pid = pid;
    ProcPidStatFileHandler pidStatHandler(attr, param, jobCtx, upLoader);
    EXPECT_EQ(PROFILING_FAILED, pidStatHandler.Init());
    EXPECT_EQ(PROFILING_SUCCESS, pidStatHandler.Init());

    std::ofstream ofs("./test");
    ofs << "cpu" << std::endl;
    ofs << "cpu" << std::endl;
    ofs << "test" << std::endl;
    ofs.close();

    std::string data;
    std::ifstream ifs("./test");
    pidStatHandler.ParseProcFile(ifs, data);
    ifs.close();

    remove("./test");
}

///////////////////////////////////////////////////////////////////////////////////
class PROF_HOST_CPU_HANDLER_TEST : public testing::Test {
protected:
    virtual void SetUp()
    {
        param = std::make_shared<analysis::dvvp::message::ProfileParams>();
        jobCtx = std::make_shared<analysis::dvvp::message::JobContext>();

        auto transport = std::shared_ptr<analysis::dvvp::transport::HDCTransport>(
            new analysis::dvvp::transport::HDCTransport(session));
        upLoader = std::make_shared<analysis::dvvp::transport::Uploader>(transport);
    }
    virtual void TearDown() {}

public:
    unsigned int devId = 0;
    unsigned int bufSize = 10;
    unsigned int sampleIntervalMs = 20;
    std::string srcFileName = "";
    std::string retFileName = "retFileName";
    std::shared_ptr<analysis::dvvp::message::ProfileParams> param;
    std::shared_ptr<analysis::dvvp::message::JobContext> jobCtx;

    HDC_SESSION session = (HDC_SESSION)0x12345678;
    std::shared_ptr<analysis::dvvp::transport::Uploader> upLoader;
};

TEST_F(PROF_HOST_CPU_HANDLER_TEST, ParseProcFile)
{
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::common::memory::Chunk::Init).stubs().will(returnValue(false)).then(returnValue(true));

    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_HOST_PROC_CPU, 0, bufSize, sampleIntervalMs});
    attr->retFileName = retFileName;
    ProcHostCpuHandler hostCpuHandler(attr, param, jobCtx, upLoader);
    EXPECT_EQ(PROFILING_FAILED, hostCpuHandler.Init());
    EXPECT_EQ(PROFILING_SUCCESS, hostCpuHandler.Init());

    std::string data;
    std::ifstream ifs;
    hostCpuHandler.ParseProcFile(ifs, data);
    hostCpuHandler.ParseProcFile(ifs, data);
}

TEST_F(PROF_HOST_CPU_HANDLER_TEST, ParseSysTime)
{
    GlobalMockObject::verify();

    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_HOST_PROC_CPU, 0, bufSize, sampleIntervalMs});
    attr->retFileName = retFileName;
    ProcHostCpuHandler hostCpuHandler(attr, param, jobCtx, upLoader);
    std::string data = "PROF_HOST_CPU_HANDLER_TEST/ParseSysTime";
    hostCpuHandler.ParseSysTime(data);
    bool check = false;
    char lastChar = data.back();
    if (data.length() > 0 && lastChar == '\n') {
        check = true;
    }
    EXPECT_TRUE(check);
}

TEST_F(PROF_HOST_CPU_HANDLER_TEST, ParseProcTidStat)
{
    GlobalMockObject::verify();

    MOCKER_CPP(&Analysis::Dvvp::JobWrapper::ProcTimerHandler::CheckFileSize)
        .stubs()
        .will(returnValue(false))
        .then(returnValue(true));
    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_HOST_PROC_CPU, 0, bufSize, sampleIntervalMs});
    attr->retFileName = retFileName;
    ProcHostCpuHandler hostCpuHandler(attr, param, jobCtx, upLoader);

    analysis::dvvp::common::utils::Utils::CreateDir("/tmp/PROF_HOST_CPU_HANDLER_TEST/ParseSysTime");
    hostCpuHandler.taskSrc_ = "/tmp/PROF_HOST_CPU_HANDLER_TEST";
    std::string data = "PROF_HOST_CPU_HANDLER_TEST.ParseSysTime";
    hostCpuHandler.ParseProcTidStat(data);
    hostCpuHandler.ParseProcTidStat(data);
    EXPECT_EQ(data, "PROF_HOST_CPU_HANDLER_TEST.ParseSysTime");
    analysis::dvvp::common::utils::Utils::RemoveDir("/tmp/PROF_HOST_CPU_HANDLER_TEST/");
}

///////////////////////////////////////////////////////////////////////////////////
class PROF_HOST_CPU_FREQ_HANDLER_TEST : public testing::Test {
protected:
    virtual void SetUp()
    {
        param = std::make_shared<analysis::dvvp::message::ProfileParams>();
        jobCtx = std::make_shared<analysis::dvvp::message::JobContext>();

        auto transport = std::shared_ptr<analysis::dvvp::transport::HDCTransport>(
            new analysis::dvvp::transport::HDCTransport(session));
        upLoader = std::make_shared<analysis::dvvp::transport::Uploader>(transport);
    }
    virtual void TearDown() {}

public:
    unsigned int bufSize = 10;
    unsigned int sampleIntervalMs = 20;
    std::string retFileName = "retFileName";
    std::shared_ptr<analysis::dvvp::message::ProfileParams> param;
    std::shared_ptr<analysis::dvvp::message::JobContext> jobCtx;

    HDC_SESSION session = (HDC_SESSION)0x12345678;
    std::shared_ptr<analysis::dvvp::transport::Uploader> upLoader;
};

TEST_F(PROF_HOST_CPU_FREQ_HANDLER_TEST, GetThreadCpu)
{
    GlobalMockObject::verify();

    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_HOST_CPU_FREQ, 0, bufSize, sampleIntervalMs});
    attr->retFileName = retFileName;
    ProcHostCpuFreqHandler hostCpuFreqHandler(attr, param, jobCtx, upLoader);

    int32_t cpuId = -1;
    EXPECT_FALSE(hostCpuFreqHandler.GetThreadCpu("/tmp/not_exist_stat_file", cpuId));

    std::ofstream invalidOfs("/tmp/prof_host_cpu_freq_invalid_stat");
    invalidOfs << "invalid_stat_line" << std::endl;
    invalidOfs.close();
    EXPECT_FALSE(hostCpuFreqHandler.GetThreadCpu("/tmp/prof_host_cpu_freq_invalid_stat", cpuId));

    std::ofstream validOfs("/tmp/prof_host_cpu_freq_valid_stat");
    validOfs << "123 (worker) R";
    for (int i = 0; i < 35; ++i) {
        validOfs << " " << i;
    }
    validOfs << " 7" << std::endl;
    validOfs.close();
    EXPECT_TRUE(hostCpuFreqHandler.GetThreadCpu("/tmp/prof_host_cpu_freq_valid_stat", cpuId));
    EXPECT_EQ(cpuId, 7);

    remove("/tmp/prof_host_cpu_freq_invalid_stat");
    remove("/tmp/prof_host_cpu_freq_valid_stat");
}

TEST_F(PROF_HOST_CPU_FREQ_HANDLER_TEST, GetThreadCpuWhenCanonicalizePathFails)
{
    GlobalMockObject::verify();
    MOCKER(analysis::dvvp::common::utils::Utils::CanonicalizePath).stubs().will(returnValue(std::string()));

    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_HOST_CPU_FREQ, 0, bufSize, sampleIntervalMs});
    attr->retFileName = retFileName;
    ProcHostCpuFreqHandler hostCpuFreqHandler(attr, param, jobCtx, upLoader);

    int32_t cpuId = -1;
    EXPECT_FALSE(hostCpuFreqHandler.GetThreadCpu("/tmp/not_exist_stat_file", cpuId));
}

TEST_F(PROF_HOST_CPU_FREQ_HANDLER_TEST, GetThreadCpuWithoutCommandTerminator)
{
    GlobalMockObject::verify();

    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_HOST_CPU_FREQ, 0, bufSize, sampleIntervalMs});
    attr->retFileName = retFileName;
    ProcHostCpuFreqHandler hostCpuFreqHandler(attr, param, jobCtx, upLoader);

    std::ofstream invalidOfs("/tmp/prof_host_cpu_freq_no_command_end_stat");
    invalidOfs << "123 worker R 0 1 2 3" << std::endl;
    invalidOfs.close();

    int32_t cpuId = -1;
    EXPECT_FALSE(hostCpuFreqHandler.GetThreadCpu("/tmp/prof_host_cpu_freq_no_command_end_stat", cpuId));

    remove("/tmp/prof_host_cpu_freq_no_command_end_stat");
}

TEST_F(PROF_HOST_CPU_FREQ_HANDLER_TEST, GetThreadCpuWithNegativeCpuId)
{
    GlobalMockObject::verify();

    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_HOST_CPU_FREQ, 0, bufSize, sampleIntervalMs});
    attr->retFileName = retFileName;
    ProcHostCpuFreqHandler hostCpuFreqHandler(attr, param, jobCtx, upLoader);

    std::ofstream invalidOfs("/tmp/prof_host_cpu_freq_negative_cpu_stat");
    invalidOfs << "123 (worker) R";
    for (int i = 0; i < 35; ++i) {
        invalidOfs << " " << i;
    }
    invalidOfs << " -1" << std::endl;
    invalidOfs.close();

    int32_t cpuId = -1;
    EXPECT_FALSE(hostCpuFreqHandler.GetThreadCpu("/tmp/prof_host_cpu_freq_negative_cpu_stat", cpuId));

    remove("/tmp/prof_host_cpu_freq_negative_cpu_stat");
}

TEST_F(PROF_HOST_CPU_FREQ_HANDLER_TEST, ParseProcFile)
{
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::common::memory::Chunk::Init).stubs().will(returnValue(false)).then(returnValue(true));

    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_HOST_CPU_FREQ, 0, bufSize, sampleIntervalMs});
    attr->retFileName = retFileName;
    ProcHostCpuFreqHandler hostCpuFreqHandler(attr, param, jobCtx, upLoader);
    EXPECT_EQ(PROFILING_FAILED, hostCpuFreqHandler.Init());
    EXPECT_EQ(PROFILING_SUCCESS, hostCpuFreqHandler.Init());

    analysis::dvvp::common::utils::Utils::CreateDir("/tmp/PROF_HOST_CPU_FREQ_HANDLER_TEST/task/100");
    analysis::dvvp::common::utils::Utils::CreateDir(
        "/tmp/PROF_HOST_CPU_FREQ_HANDLER_TEST/sys/devices/system/cpu/cpu7/cpufreq");
    hostCpuFreqHandler.taskSrc_ = "/tmp/PROF_HOST_CPU_FREQ_HANDLER_TEST/task";
    hostCpuFreqHandler.sysCpuRoot_ = "/tmp/PROF_HOST_CPU_FREQ_HANDLER_TEST/sys/devices/system/cpu";
    hostCpuFreqHandler.cpuFreqAvailable_ = true;

    std::ofstream validOfs("/tmp/PROF_HOST_CPU_FREQ_HANDLER_TEST/task/100/stat");
    validOfs << "100 (worker) R";
    for (int i = 0; i < 35; ++i) {
        validOfs << " " << i;
    }
    validOfs << " 7" << std::endl;
    validOfs.close();

    std::ofstream freqOfs("/tmp/PROF_HOST_CPU_FREQ_HANDLER_TEST/sys/devices/system/cpu/cpu7/cpufreq/scaling_cur_freq");
    freqOfs << "1234567" << std::endl;
    freqOfs.close();

    std::string data;
    std::ifstream ifs;
    hostCpuFreqHandler.ParseProcFile(ifs, data);
    EXPECT_NE(data.find("time "), std::string::npos);
    EXPECT_NE(data.find("7 1234567"), std::string::npos);

    analysis::dvvp::common::utils::Utils::RemoveDir("/tmp/PROF_HOST_CPU_FREQ_HANDLER_TEST/");
}

TEST_F(PROF_HOST_CPU_FREQ_HANDLER_TEST, ParseProcFileWhenCpuFreqUnsupported)
{
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::common::memory::Chunk::Init).stubs().will(returnValue(false)).then(returnValue(true));

    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_HOST_CPU_FREQ, 0, bufSize, sampleIntervalMs});
    attr->retFileName = retFileName;
    ProcHostCpuFreqHandler hostCpuFreqHandler(attr, param, jobCtx, upLoader);
    EXPECT_EQ(PROFILING_FAILED, hostCpuFreqHandler.Init());
    EXPECT_EQ(PROFILING_SUCCESS, hostCpuFreqHandler.Init());

    hostCpuFreqHandler.cpuFreqAvailable_ = false;
    hostCpuFreqHandler.taskSrc_ = "/tmp/PROF_HOST_CPU_FREQ_HANDLER_TEST_UNSUPPORTED/task";

    std::string data;
    std::ifstream ifs;
    hostCpuFreqHandler.ParseProcFile(ifs, data);
    EXPECT_TRUE(data.empty());
}

TEST_F(PROF_HOST_CPU_FREQ_HANDLER_TEST, ParseProcFileWhenCanonicalizePathFails)
{
    GlobalMockObject::verify();
    MOCKER_CPP(&analysis::dvvp::common::memory::Chunk::Init).stubs().will(returnValue(true));

    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_HOST_CPU_FREQ, 0, bufSize, sampleIntervalMs});
    attr->retFileName = retFileName;
    ProcHostCpuFreqHandler hostCpuFreqHandler(attr, param, jobCtx, upLoader);
    EXPECT_EQ(PROFILING_SUCCESS, hostCpuFreqHandler.Init());
    hostCpuFreqHandler.cpuFreqAvailable_ = true;
    hostCpuFreqHandler.taskSrc_ = "/tmp/PROF_HOST_CPU_FREQ_HANDLER_TEST_CANONICAL/task";
    hostCpuFreqHandler.sysCpuRoot_ = "/tmp/PROF_HOST_CPU_FREQ_HANDLER_TEST_CANONICAL/sys/devices/system/cpu";
    analysis::dvvp::common::utils::Utils::CreateDir(hostCpuFreqHandler.taskSrc_ + "/100");
    std::ofstream statOfs(hostCpuFreqHandler.taskSrc_ + "/100/stat");
    statOfs << "100 (worker) R";
    for (int i = 0; i < 35; ++i) {
        statOfs << " " << i;
    }
    statOfs << " 7\n";
    statOfs.close();
    MOCKER(analysis::dvvp::common::utils::Utils::CanonicalizePath)
        .stubs()
        .will(returnValue(hostCpuFreqHandler.taskSrc_ + "/100/stat"))
        .then(returnValue(std::string()));

    std::string data;
    std::ifstream ifs;
    hostCpuFreqHandler.ParseProcFile(ifs, data);
    EXPECT_TRUE(data.find("7 ") == std::string::npos);
    analysis::dvvp::common::utils::Utils::RemoveDir("/tmp/PROF_HOST_CPU_FREQ_HANDLER_TEST_CANONICAL/");
}
///////////////////////////////////////////////////////////////////////////////////
class PROF_HOST_MEM_HANDLER_TEST : public testing::Test {
protected:
    virtual void SetUp()
    {
        param = std::make_shared<analysis::dvvp::message::ProfileParams>();
        jobCtx = std::make_shared<analysis::dvvp::message::JobContext>();

        auto transport = std::shared_ptr<analysis::dvvp::transport::HDCTransport>(
            new analysis::dvvp::transport::HDCTransport(session));
        upLoader = std::make_shared<analysis::dvvp::transport::Uploader>(transport);
    }
    virtual void TearDown() {}

public:
    unsigned int devId = 0;
    unsigned int bufSize = 10;
    unsigned int sampleIntervalMs = 20;
    std::string srcFileName = "";
    std::string retFileName = "retFileName";
    std::shared_ptr<analysis::dvvp::message::ProfileParams> param;
    std::shared_ptr<analysis::dvvp::message::JobContext> jobCtx;

    HDC_SESSION session = (HDC_SESSION)0x12345678;
    std::shared_ptr<analysis::dvvp::transport::Uploader> upLoader;
};

TEST_F(PROF_HOST_MEM_HANDLER_TEST, ParseProcFile)
{
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::common::memory::Chunk::Init).stubs().will(returnValue(false)).then(returnValue(true));
    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_HOST_PROC_MEM, 0, bufSize, sampleIntervalMs});
    attr->retFileName = retFileName;
    ProcHostMemHandler hostMemHandler(attr, param, jobCtx, upLoader);
    EXPECT_EQ(PROFILING_FAILED, hostMemHandler.Init());
    EXPECT_EQ(PROFILING_SUCCESS, hostMemHandler.Init());

    std::string data;
    std::ifstream ifs;
    hostMemHandler.ParseProcFile(ifs, data);
    hostMemHandler.ParseProcFile(ifs, data);
}

///////////////////////////////////////////////////////////////////////////////////
class PROF_HOST_NETWORK_HANDLER_TEST : public testing::Test {
protected:
    virtual void SetUp()
    {
        param = std::make_shared<analysis::dvvp::message::ProfileParams>();
        jobCtx = std::make_shared<analysis::dvvp::message::JobContext>();

        auto transport = std::shared_ptr<analysis::dvvp::transport::HDCTransport>(
            new analysis::dvvp::transport::HDCTransport(session));
        upLoader = std::make_shared<analysis::dvvp::transport::Uploader>(transport);
    }
    virtual void TearDown() {}

public:
    unsigned int devId = 0;
    unsigned int bufSize = 10;
    unsigned int sampleIntervalMs = 20;
    std::string srcFileName = "";
    std::string retFileName = "retFileName";
    std::shared_ptr<analysis::dvvp::message::ProfileParams> param;
    std::shared_ptr<analysis::dvvp::message::JobContext> jobCtx;

    HDC_SESSION session = (HDC_SESSION)0x12345678;
    std::shared_ptr<analysis::dvvp::transport::Uploader> upLoader;
};

TEST_F(PROF_HOST_NETWORK_HANDLER_TEST, ParseProcFile)
{
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::common::memory::Chunk::Init).stubs().will(returnValue(false)).then(returnValue(true));
    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_HOST_SYS_NETWORK, 0, bufSize, sampleIntervalMs});
    attr->retFileName = retFileName;
    ProcHostNetworkHandler hostNetworkHandler(attr, param, jobCtx, upLoader);
    EXPECT_EQ(PROFILING_FAILED, hostNetworkHandler.Init());
    EXPECT_EQ(PROFILING_SUCCESS, hostNetworkHandler.Init());

    std::string data;
    std::ifstream ifs;
    hostNetworkHandler.ParseProcFile(ifs, data);
    hostNetworkHandler.ParseProcFile(ifs, data);
}

///////////////////////////////////////////////////////////////////////////////////
class PROF_MEM_FILE_HANDLER_TEST : public testing::Test {
protected:
    virtual void SetUp()
    {
        param = std::make_shared<analysis::dvvp::message::ProfileParams>();
        jobCtx = std::make_shared<analysis::dvvp::message::JobContext>();

        auto transport = std::shared_ptr<analysis::dvvp::transport::HDCTransport>(
            new analysis::dvvp::transport::HDCTransport(session));
        upLoader = std::make_shared<analysis::dvvp::transport::Uploader>(transport);
    }
    virtual void TearDown() {}

public:
    unsigned int devId = 0;
    unsigned int bufSize = 10;
    unsigned int sampleIntervalMs = 100;
    std::string srcFileName = "srcFileName";
    std::string retFileName = "retFileName";
    std::shared_ptr<analysis::dvvp::message::ProfileParams> param;
    std::shared_ptr<analysis::dvvp::message::JobContext> jobCtx;

    HDC_SESSION session = (HDC_SESSION)0x12345678;
    std::shared_ptr<analysis::dvvp::transport::Uploader> upLoader;
};

TEST_F(PROF_MEM_FILE_HANDLER_TEST, ParseProcFile)
{
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::common::memory::Chunk::Init).stubs().will(returnValue(false)).then(returnValue(true));
    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_SYS_MEM, devId, bufSize, sampleIntervalMs});
    attr->srcFileName = srcFileName;
    attr->retFileName = retFileName;
    ProcMemFileHandler memHandler(attr, param, jobCtx, upLoader);
    EXPECT_EQ(PROFILING_FAILED, memHandler.Init());
    EXPECT_EQ(PROFILING_SUCCESS, memHandler.Init());

    std::ofstream ofs("./test");
    ofs << "cpu" << std::endl;
    ofs << "cpu" << std::endl;
    ofs << "test" << std::endl;
    ofs.close();

    std::string data;
    std::ifstream ifs("./test");
    memHandler.ParseProcFile(ifs, data);
    ifs.close();

    remove("./test");
}

///////////////////////////////////////////////////////////////////////////////////
class PROF_PID_MEM_FILE_HANDLER_TEST : public testing::Test {
protected:
    virtual void SetUp()
    {
        param = std::make_shared<analysis::dvvp::message::ProfileParams>();
        jobCtx = std::make_shared<analysis::dvvp::message::JobContext>();

        auto transport = std::shared_ptr<analysis::dvvp::transport::HDCTransport>(
            new analysis::dvvp::transport::HDCTransport(session));
        upLoader = std::make_shared<analysis::dvvp::transport::Uploader>(transport);
    }
    virtual void TearDown() {}

public:
    unsigned int devId = 0;
    unsigned int bufSize = 10;
    unsigned int sampleIntervalMs = 100;
    std::string srcFileName = "srcFileName";
    std::string retFileName = "retFileName";
    std::shared_ptr<analysis::dvvp::message::ProfileParams> param;
    std::shared_ptr<analysis::dvvp::message::JobContext> jobCtx;

    HDC_SESSION session = (HDC_SESSION)0x12345678;
    std::shared_ptr<analysis::dvvp::transport::Uploader> upLoader;
    unsigned int pid = 1;
};

TEST_F(PROF_PID_MEM_FILE_HANDLER_TEST, ParseProcFile)
{
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::common::memory::Chunk::Init).stubs().will(returnValue(false)).then(returnValue(true));
    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_SYS_MEM, devId, bufSize, sampleIntervalMs});
    attr->srcFileName = srcFileName;
    attr->retFileName = retFileName;
    attr->pid = pid;
    ProcPidMemFileHandler pidMemHandler(attr, param, jobCtx, upLoader);
    EXPECT_EQ(PROFILING_FAILED, pidMemHandler.Init());
    EXPECT_EQ(PROFILING_SUCCESS, pidMemHandler.Init());

    std::ofstream ofs("./test");
    ofs << "cpu" << std::endl;
    ofs << "cpu" << std::endl;
    ofs << "test" << std::endl;
    ofs.close();

    std::string data;
    std::ifstream ifs("./test");
    pidMemHandler.ParseProcFile(ifs, data);
    ifs.close();

    remove("./test");
}

///////////////////////////////////////////////////////////////////////////////////
class PROF_ALL_PID_FILE_HANDLER_TEST : public testing::Test {
protected:
    virtual void SetUp()
    {
        param = std::make_shared<analysis::dvvp::message::ProfileParams>();
        jobCtx = std::make_shared<analysis::dvvp::message::JobContext>();

        auto transport = std::shared_ptr<analysis::dvvp::transport::HDCTransport>(
            new analysis::dvvp::transport::HDCTransport(session));
        upLoader = std::make_shared<analysis::dvvp::transport::Uploader>(transport);
    }
    virtual void TearDown() {}

public:
    unsigned int devId = 0;
    unsigned int sampleIntervalMs = 100;
    std::shared_ptr<analysis::dvvp::message::ProfileParams> param;
    std::shared_ptr<analysis::dvvp::message::JobContext> jobCtx;

    HDC_SESSION session = (HDC_SESSION)0x12345678;
    std::shared_ptr<analysis::dvvp::transport::Uploader> upLoader;
};

void fake_get_child_dirs(const std::string& dir, bool is_recur, std::vector<std::string>& pidDirs)
{
    pidDirs.push_back("/proc/1");
    pidDirs.push_back("/proc/2");
    pidDirs.push_back("/proc/test");
}

TEST_F(PROF_ALL_PID_FILE_HANDLER_TEST, Init)
{
    GlobalMockObject::verify();

    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_ALL_PID, devId, 0, sampleIntervalMs});
    ProcAllPidsFileHandler allPidsHandler(attr, param, jobCtx, upLoader);

    MOCKER(analysis::dvvp::common::utils::Utils::GetChildDirs).stubs().will(invoke(fake_get_child_dirs));
    MOCKER_CPP(&Analysis::Dvvp::JobWrapper::ProcAllPidsFileHandler::GetNewExitPids).stubs();
    MOCKER_CPP(&Analysis::Dvvp::JobWrapper::ProcAllPidsFileHandler::HandleExitPids).stubs();
    MOCKER_CPP(&Analysis::Dvvp::JobWrapper::ProcAllPidsFileHandler::HandleNewPids).stubs();
    // Init
    EXPECT_EQ(PROFILING_SUCCESS, allPidsHandler.Init());
    // Execute
    EXPECT_EQ(PROFILING_SUCCESS, allPidsHandler.Execute());
    // ParseProcFile
    std::ifstream ifs;
    std::string data;
    allPidsHandler.ParseProcFile(ifs, data);
    // GetProcessname
    allPidsHandler.GetProcessName(0, data);
}

TEST_F(PROF_ALL_PID_FILE_HANDLER_TEST, GetNewExitPids)
{
    GlobalMockObject::verify();

    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_ALL_PID, devId, 0, sampleIntervalMs});
    ProcAllPidsFileHandler allPidsHandler(attr, param, jobCtx, upLoader);

    // GetNewExitPids
    std::vector<unsigned int> newPids;
    std::vector<unsigned int> exitPids;

    std::vector<unsigned int> curPids;
    curPids.push_back(1);
    curPids.push_back(2);
    curPids.push_back(5);
    std::vector<unsigned int> prevPids;
    prevPids.push_back(1);
    prevPids.push_back(4);

    allPidsHandler.GetNewExitPids(curPids, prevPids, newPids, exitPids);

    // prevPidsSize > curPidsSize
    prevPids.push_back(6);
    allPidsHandler.GetNewExitPids(curPids, prevPids, newPids, exitPids);

    EXPECT_EQ(curPids[1], newPids[0]);
    EXPECT_EQ(prevPids[1], exitPids[0]);

    // HandleNewPids
    allPidsHandler.HandleNewPids(prevPids);
    allPidsHandler.HandleNewPids(newPids);
    // HandleExitPids
    allPidsHandler.HandleExitPids(exitPids);
    // Execute
    allPidsHandler.Execute();
}

///////////////////////////////////////////////////////////////////////////////////
class PROF_TIMER_TEST : public testing::Test {
protected:
    virtual void SetUp()
    {
        param = std::make_shared<analysis::dvvp::message::ProfileParams>();
        jobCtx = std::make_shared<analysis::dvvp::message::JobContext>();

        auto transport = std::shared_ptr<analysis::dvvp::transport::HDCTransport>(
            new analysis::dvvp::transport::HDCTransport(session));
        upLoader = std::make_shared<analysis::dvvp::transport::Uploader>(transport);
    }
    virtual void TearDown() {}

public:
    unsigned int devId = 0;
    unsigned int sampleIntervalMs = 100;
    std::shared_ptr<analysis::dvvp::message::ProfileParams> param;
    std::shared_ptr<analysis::dvvp::message::JobContext> jobCtx;

    HDC_SESSION session = (HDC_SESSION)0x12345678;
    std::shared_ptr<analysis::dvvp::transport::Uploader> upLoader;
};

TEST_F(PROF_TIMER_TEST, Handler)
{
    GlobalMockObject::verify();

    std::shared_ptr<TimerParam> timerParam(new TimerParam(1000));
    ProfTimer timerHandler(timerParam);
    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_ALL_PID, devId, 0, sampleIntervalMs});
    std::shared_ptr<ProcAllPidsFileHandler> allPidsHandler(new ProcAllPidsFileHandler(attr, param, jobCtx, upLoader));

    EXPECT_EQ(PROFILING_SUCCESS, timerHandler.RegisterTimerHandler(PROF_ALL_PID, allPidsHandler));
    EXPECT_EQ(1, timerHandler.Handler());
    EXPECT_EQ(PROFILING_SUCCESS, timerHandler.RemoveTimerHandler(PROF_ALL_PID));
}

TEST_F(PROF_TIMER_TEST, Start)
{
    GlobalMockObject::verify();

    MOCKER(mmCreateTaskWithThreadAttr).stubs().will(returnValue(EN_OK));
    MOCKER(mmJoinTask).stubs().will(returnValue(EN_OK));

    MOCKER(setitimer).stubs().will(returnValue(-1)).then(returnValue(0)).then(returnValue(-1)).then(returnValue(0));

    std::shared_ptr<TimerParam> timerParam(new TimerParam(1000));
    ProfTimer timerHandler(timerParam);
    // start failed
    timerHandler.isStarted_ = true;
    EXPECT_EQ(PROFILING_FAILED, timerHandler.Start());
    // setitimer failed
    timerHandler.isStarted_ = false;
    EXPECT_EQ(PROFILING_SUCCESS, timerHandler.Start());
    // start succ
    EXPECT_EQ(PROFILING_FAILED, timerHandler.Start());
    // stop failed setitimer failed
    EXPECT_EQ(PROFILING_SUCCESS, timerHandler.Stop());
    // stop succ
    std::shared_ptr<TimerAttr> attr(new TimerAttr{PROF_ALL_PID, devId, 0, sampleIntervalMs});
    std::shared_ptr<ProcAllPidsFileHandler> allPidsHandler(new ProcAllPidsFileHandler(attr, param, jobCtx, upLoader));

    EXPECT_EQ(PROFILING_SUCCESS, timerHandler.RegisterTimerHandler(PROF_ALL_PID, allPidsHandler));
    timerHandler.isStarted_ = true;
    EXPECT_EQ(PROFILING_SUCCESS, timerHandler.Stop());
}

TEST_F(PROF_TIMER_TEST, run)
{
    GlobalMockObject::verify();

    std::shared_ptr<TimerParam> timerParam(new TimerParam(1000));
    EXPECT_NE(nullptr, timerParam);
    ProfTimer timerHandler(timerParam);
    auto errorContext = MsprofErrorManager::instance()->GetErrorManagerContext();
    timerHandler.Run(errorContext);
}

class PROF_NET_DEV_STATS_TEST : public testing::Test {
protected:
    virtual void SetUp()
    {
        jobCtx = std::make_shared<analysis::dvvp::message::JobContext>();
        jobCtx->job_id = "0";
        jobCtx->dev_id = "0";
        jobCtx->tag = "tag";
    }
    virtual void TearDown() { GlobalMockObject::verify(); }

public:
    std::shared_ptr<analysis::dvvp::message::JobContext> jobCtx;
};

TEST_F(PROF_NET_DEV_STATS_TEST, Uinit_NotInited)
{
    NetDevStatsHandler h(64, 1000, "0", jobCtx);
    EXPECT_EQ(PROFILING_SUCCESS, h.Uinit());
}

TEST_F(PROF_NET_DEV_STATS_TEST, Execute_NotInited)
{
    NetDevStatsHandler h(64, 1000, "0", jobCtx);
    EXPECT_EQ(PROFILING_SUCCESS, h.Execute());
}

TEST_F(PROF_NET_DEV_STATS_TEST, GetCurDevTaskCount_Empty)
{
    NetDevStatsHandler h(64, 1000, "0", jobCtx);
    EXPECT_EQ(static_cast<size_t>(0), h.GetCurDevTaskCount());
}

TEST_F(PROF_NET_DEV_STATS_TEST, RemoveDevTask_NotRegistered)
{
    NetDevStatsHandler h(64, 1000, "0", jobCtx);
    EXPECT_EQ(PROFILING_SUCCESS, h.RemoveDevTask(7));
}

// File-scope stubs for NetDevStatsHandler tests
static int g_dcmi_init_ok_stub() { return 0; }
static int g_dcmi_init_fail_stub() { return -1; }
static int g_dcmi_card_list_zero_stub(int* cardNum, int*, int)
{
    if (cardNum)
        *cardNum = 0;
    return 0;
}
static int g_dcmi_card_list_fail_stub(int*, int*, int) { return -1; }
static int g_dcmi_dev_num_stub(int, int*) { return 0; }
static int g_dcmi_pkt_stub(int, int, int, struct dcmi_network_pkt_stats_info*) { return 0; }
static int g_dcmi_v2_pkt_fail_stub(int, int, struct dcmi_network_pkt_stats_info*) { return -1; }

TEST_F(PROF_NET_DEV_STATS_TEST, Init_LoadDcmiFails)
{
    NetDevStatsHandler h(64, 1000, "0", jobCtx);
    // Init() calls LoadDcmiApi() → OsalDlopen for dcmi lib normally fails in UT env.
    int32_t ret = h.Init();
    (void)ret;
}

TEST_F(PROF_NET_DEV_STATS_TEST, Init_LoadDcmiV1AllSym_ThenV1InitFails)
{
    // OsalDlopen returns non-null handle, dcmiv2_get_dcmi_version returns null
    // -> isDcmiV2Supported_ = false. LoadDcmiV1Api succeeds (syms non-null),
    // then dcmiInit_ returns failure -> Init FAILED via dcmiInit_() != SUCCESS.
    MOCKER(OsalDlopen).stubs().will(returnValue((void*)0x12345678));
    MOCKER(OsalDlsym)
        .stubs()
        .will(returnValue((void*)nullptr))                                  // v2 version
        .then(returnValue(reinterpret_cast<void*>(&g_dcmi_init_fail_stub))) // dcmi_init
        .then(returnValue(reinterpret_cast<void*>(&g_dcmi_card_list_zero_stub)))
        .then(returnValue(reinterpret_cast<void*>(&g_dcmi_dev_num_stub)))
        .then(returnValue(reinterpret_cast<void*>(&g_dcmi_pkt_stub)));

    NetDevStatsHandler h(64, 1000, "0", jobCtx);
    int32_t ret = h.Init();
    EXPECT_EQ(PROFILING_FAILED, ret);
}

TEST_F(PROF_NET_DEV_STATS_TEST, RegisterDevTask_NoDcmiCardList)
{
    // OsalDlopen succeeds, all v1 syms succeed, dcmi_init succeeds (=0)
    // GetDcmiCardDevId fails because dcmiGetCardList_ stub returns failure
    MOCKER(OsalDlopen).stubs().will(returnValue((void*)0x12345678));
    MOCKER(OsalDlsym)
        .stubs()
        .will(returnValue((void*)nullptr))
        .then(returnValue(reinterpret_cast<void*>(&g_dcmi_init_ok_stub)))
        .then(returnValue(reinterpret_cast<void*>(&g_dcmi_card_list_fail_stub)))
        .then(returnValue(reinterpret_cast<void*>(&g_dcmi_dev_num_stub)))
        .then(returnValue(reinterpret_cast<void*>(&g_dcmi_pkt_stub)));

    NetDevStatsHandler h(64, 1000, "0", jobCtx);
    EXPECT_EQ(PROFILING_SUCCESS, h.Init());
    // RegisterDevTask -> not v2, GetDcmiCardDevId fails
    EXPECT_EQ(PROFILING_FAILED, h.RegisterDevTask(0));
    EXPECT_EQ(static_cast<size_t>(0), h.GetCurDevTaskCount());
    // Remove not registered -> SUCCESS (warn branch)
    EXPECT_EQ(PROFILING_SUCCESS, h.RemoveDevTask(0));
    // Uinit on inited handler -> SUCCESS
    EXPECT_EQ(PROFILING_SUCCESS, h.Uinit());
}

TEST_F(PROF_NET_DEV_STATS_TEST, Init_DoubleInit_Fails)
{
    MOCKER(OsalDlopen).stubs().will(returnValue((void*)0x12345678));
    MOCKER(OsalDlsym)
        .stubs()
        .will(returnValue((void*)nullptr))
        .then(returnValue(reinterpret_cast<void*>(&g_dcmi_init_ok_stub)))
        .then(returnValue(reinterpret_cast<void*>(&g_dcmi_card_list_zero_stub)))
        .then(returnValue(reinterpret_cast<void*>(&g_dcmi_dev_num_stub)))
        .then(returnValue(reinterpret_cast<void*>(&g_dcmi_pkt_stub)));

    NetDevStatsHandler h(64, 1000, "0", jobCtx);
    EXPECT_EQ(PROFILING_SUCCESS, h.Init());
    // Re-init after isInited_ is true -> FAILED
    EXPECT_EQ(PROFILING_FAILED, h.Init());
}

TEST_F(PROF_NET_DEV_STATS_TEST, Execute_V2GetNetdevPktStatsInfo_Fails)
{
    // V2 path: OsalDlopen succeeds, dcmiv2_get_dcmi_version non-null (isDcmiV2Supported_=true),
    // dcmiv2_init succeeds, RegisterDevTask succeeds (v2 uses devId directly),
    // Execute() calls dcmiV2GetNetdevPktStatsInfo_ which returns failure -> covers line 943.
    MOCKER(OsalDlopen).stubs().will(returnValue((void*)0x12345678));
    MOCKER(OsalDlsym)
        .stubs()
        .will(returnValue(reinterpret_cast<void*>(&g_dcmi_init_ok_stub))) // dcmiv2_get_dcmi_version (non-null)
        .then(returnValue(reinterpret_cast<void*>(&g_dcmi_init_ok_stub))) // dcmiv2_init (returns 0)
        .then(returnValue(
            reinterpret_cast<void*>(&g_dcmi_v2_pkt_fail_stub))); // dcmiv2_get_netdev_pkt_stats_info (returns -1)

    NetDevStatsHandler h(64, 1000, "0", jobCtx);
    EXPECT_EQ(PROFILING_SUCCESS, h.Init());
    EXPECT_EQ(PROFILING_SUCCESS, h.RegisterDevTask(0));
    EXPECT_EQ(PROFILING_SUCCESS, h.Execute());
    EXPECT_EQ(PROFILING_SUCCESS, h.Uinit());
}
