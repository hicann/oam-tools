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
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"
#include "info_json.h"
#include "ai_drv_dev_api.h"
#include "ai_drv_dsmi_api.h"
#include "config/config.h"
#include "config_manager.h"
#include "errno/error_code.h"
#include "msprof_dlog.h"
#include "prof_manager.h"
#include "securec.h"
#include "utils/utils.h"
#include "platform/platform.h"
#include "task_relationship_mgr.h"
#include "json/json.h"

using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::utils;
using namespace analysis::dvvp::common::config;
using namespace Analysis::Dvvp::Common::Platform;
using namespace Analysis::Dvvp::Common::Config;
using namespace analysis::dvvp::host;
using namespace Dvvp::Collect::Platform;

namespace {
class ConfigTypeGuard {
public:
    explicit ConfigTypeGuard(PlatformType type)
    {
        auto configManager = ConfigManager::instance();
        hasOriginalType_ = configManager->configMap_.count("type") > 0;
        if (hasOriginalType_) {
            originalType_ = configManager->configMap_["type"];
        }
        configManager->configMap_["type"] = std::to_string(static_cast<int32_t>(type));
    }

    ~ConfigTypeGuard()
    {
        auto configManager = ConfigManager::instance();
        if (hasOriginalType_) {
            configManager->configMap_["type"] = originalType_;
        } else {
            configManager->configMap_.erase("type");
        }
    }

private:
    bool hasOriginalType_ = false;
    std::string originalType_;
};

int32_t DrvInfoOk(uint32_t, int64_t &out)
{
    out = 0;
    return PROFILING_SUCCESS;
}

int32_t DrvInfoFail(uint32_t, int64_t &)
{
    return PROFILING_FAILED;
}

int32_t DrvInfoOne(uint32_t, int64_t &out)
{
    out = 1;
    return PROFILING_SUCCESS;
}

int32_t DrvInfoA55(uint32_t, int64_t &out)
{
    out = 0x41d05;
    return PROFILING_SUCCESS;
}

void MockSuccessfulDeviceInfo()
{
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetEnvType).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuId).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuEndianLittle).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAivNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCpuOccupyBitmap).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetTsCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCoreId).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCoreNum).stubs().will(invoke(DrvInfoOk));
}
}  // namespace

TEST(INFO_JSON_TEST, GetHwtsFreq) {
    GlobalMockObject::verify();
    ConfigTypeGuard guard(PlatformType::CHIP_CLOUD_V3);
    InfoJson infoJson("1", "0", 1);
    std::string freq = "1005";
    EXPECT_EQ("1000", infoJson.GetHwtsFreq(freq));
    freq = "1000.1";
    EXPECT_EQ("1000.1", infoJson.GetHwtsFreq(freq));
}

TEST(INFO_JSON_TEST, GetHwtsFreqNotCloudV3) {
    GlobalMockObject::verify();
    ConfigTypeGuard guard(PlatformType::CHIP_V4_1_0);
    InfoJson infoJson("1", "0", 1);
    EXPECT_EQ("9999", infoJson.GetHwtsFreq("9999"));
}

TEST(INFO_JSON_TEST, SetPidInfo) {
    GlobalMockObject::verify();
    SHARED_PTR_ALIA<InfoMain> infoMain = nullptr;
    MSVP_MAKE_SHARED0(infoMain, InfoMain, return);
    InfoJson infoJson("1", "0", 1);

    infoJson.SetPidInfo(infoMain, HOST_PID_DEFAULT);
    EXPECT_EQ("NA", infoMain->pid);

    infoJson.SetPidInfo(infoMain, 123);
    EXPECT_EQ("123", infoMain->pid);
}

TEST(INFO_JSON_TEST, SetCannVersionWillNotSetVersionWhenAscendHomePathIsNotSet) {
    GlobalMockObject::verify();

    SHARED_PTR_ALIA<InfoMain> infoMain = nullptr;
    MSVP_MAKE_SHARED0(infoMain, InfoMain, return);

    std::string emptyAscendHome = "";
    InfoJson infoJson("1", "0", 1);

    MOCKER_CPP(&Utils::HandleEnvString)
        .stubs()
        .will(returnValue(emptyAscendHome));

    infoJson.SetCannVersion(infoMain);
    EXPECT_EQ("", infoMain->cannVersion);
}

TEST(INFO_JSON_TEST, SetCannVersionWillNotSetVersionWhenAscendHomePathIsInvalid) {
    GlobalMockObject::verify();

    SHARED_PTR_ALIA<InfoMain> infoMain = nullptr;
    MSVP_MAKE_SHARED0(infoMain, InfoMain, return);

    std::string invalidAscendHome = "/////";
    InfoJson infoJson("1", "0", 1);

    MOCKER_CPP(&Utils::HandleEnvString)
        .stubs()
        .will(returnValue(invalidAscendHome));

    infoJson.SetCannVersion(infoMain);
    EXPECT_EQ("", infoMain->cannVersion);
}

TEST(INFO_JSON_TEST, SetCannVersionWillNotSetVersionWhenVersionFileIsNotAccessible) {
    GlobalMockObject::verify();

    SHARED_PTR_ALIA<InfoMain> infoMain = nullptr;
    MSVP_MAKE_SHARED0(infoMain, InfoMain, return);

    std::string utAscendHome = "./info_ut";
    std::string versionFile = utAscendHome + "/share/info/runtime/version.info";
    Utils::RemoveDir(utAscendHome);
    InfoJson infoJson("1", "0", 1);

    MOCKER_CPP(&Utils::HandleEnvString)
        .stubs()
        .will(returnValue(utAscendHome));

    infoJson.SetCannVersion(infoMain);
    EXPECT_EQ("", infoMain->cannVersion);
    Utils::RemoveDir(utAscendHome);
}

TEST(INFO_JSON_TEST, SetCannVersionWillNotSetVersionWhenVersionFileContentIsInvalid) {
    GlobalMockObject::verify();

    SHARED_PTR_ALIA<InfoMain> infoMain = nullptr;
    MSVP_MAKE_SHARED0(infoMain, InfoMain, return);

    std::string utAscendHome = "./info_ut";
    std::string versionFile = utAscendHome + "/share/info/runtime/version.info";
    Utils::RemoveDir(utAscendHome);
    Utils::CreateDir(utAscendHome + "/share/info/runtime");
    std::ofstream invalidFile(versionFile);
    invalidFile << "invalid_version_content" << std::endl;
    invalidFile.close();

    InfoJson infoJson("1", "0", 1);

    MOCKER_CPP(&Utils::HandleEnvString)
        .stubs()
        .will(returnValue(utAscendHome));

    infoJson.SetCannVersion(infoMain);
    EXPECT_EQ("", infoMain->cannVersion);

    invalidFile.open(versionFile, std::ios::trunc);
    invalidFile << "Version=\n" << std::endl;
    invalidFile.close();
    infoJson.SetCannVersion(infoMain);
    EXPECT_EQ("", infoMain->cannVersion);

    invalidFile.open(versionFile, std::ios::trunc);
    invalidFile << "Version=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" << std::endl;
    invalidFile.close();
    infoJson.SetCannVersion(infoMain);
    EXPECT_EQ("", infoMain->cannVersion);

    remove(versionFile.c_str());
    Utils::RemoveDir(utAscendHome);
}

TEST(INFO_JSON_TEST, SetCannVersionWillSetVersionWhenVersionFileContentIsValid) {
    GlobalMockObject::verify();

    SHARED_PTR_ALIA<InfoMain> infoMain = nullptr;
    MSVP_MAKE_SHARED0(infoMain, InfoMain, return);

    std::string utAscendHome = "./info_ut";
    std::string versionFile = utAscendHome + "/share/info/runtime/version.info";
    Utils::RemoveDir(utAscendHome);
    Utils::CreateDir(utAscendHome + "/share/info/runtime");
    std::ofstream validFile(versionFile);
    validFile << "Version=9.1.0" << std::endl;
    validFile.close();

    InfoJson infoJson("1", "0", 1);

    MOCKER_CPP(&Utils::HandleEnvString)
        .stubs()
        .will(returnValue(utAscendHome));

    infoJson.SetCannVersion(infoMain);
    EXPECT_EQ("9.1.0", infoMain->cannVersion);

    validFile.open(versionFile, std::ios::trunc);
    validFile << "Version=9.1.0\nVersion=9.2.0" << std::endl;
    validFile.close();
    infoJson.SetCannVersion(infoMain);
    EXPECT_EQ("9.1.0", infoMain->cannVersion);

    remove(versionFile.c_str());
    Utils::RemoveDir(utAscendHome);
}

TEST(INFO_JSON_TEST, EncodeInfoMainJsonNull) {
    GlobalMockObject::verify();
    InfoJson infoJson("1", "0", 1);
    SHARED_PTR_ALIA<InfoMain> infoMain = nullptr;
    EXPECT_EQ("", infoJson.EncodeInfoMainJson(infoMain));
}

TEST(INFO_JSON_TEST, EncodeInfoMainJsonFilled) {
    GlobalMockObject::verify();
    ConfigTypeGuard guard(PlatformType::CHIP_V4_1_0);
    InfoJson infoJson("1", "0", 1);
    SHARED_PTR_ALIA<InfoMain> infoMain = nullptr;
    MSVP_MAKE_SHARED0(infoMain, InfoMain, return);

    infoMain->deviceInfos.push_back({1, 0, 4, 1, 4, 4, 4, 0, 0, 0, 4, "ARMv8", "0,1,2,3", "0,1,2,3",
        "1000", "1500", "1500"});
    infoMain->netCardInfos.push_back({"eth0", 100});
    infoMain->infoCpus.push_back({0, "ARM", "1.5GHz", "8", "armv8"});
    infoMain->memoryTotal = 1024;
    infoMain->cpuNums = 8;
    infoMain->sysClockFreq = 100;
    infoMain->cpuCores = 8;
    infoMain->netCardNums = 1;
    infoMain->rankId = 0;
    infoMain->drvVersion = 0x10000;

    std::string content = infoJson.EncodeInfoMainJson(infoMain);
    EXPECT_FALSE(content.empty());
    EXPECT_NE(std::string::npos, content.find("DeviceInfo"));
    EXPECT_NE(std::string::npos, content.find("netCard"));
    EXPECT_NE(std::string::npos, content.find("CPU"));
}

TEST(INFO_JSON_TEST, InitDeviceIdsBranches) {
    GlobalMockObject::verify();
    InfoJson validInfoJson("", "0,1", 1);
    EXPECT_EQ(PROFILING_SUCCESS, validInfoJson.InitDeviceIds());

    InfoJson outOfRangeInfoJson("", "9999", 1);
    EXPECT_EQ(PROFILING_SUCCESS, outOfRangeInfoJson.InitDeviceIds());

    InfoJson negativeInfoJson("", "-1", 1);
    EXPECT_EQ(PROFILING_SUCCESS, negativeInfoJson.InitDeviceIds());

    InfoJson emptyInfoJson("", "", 1);
    EXPECT_EQ(PROFILING_SUCCESS, emptyInfoJson.InitDeviceIds());

    InfoJson invalidInfoJson("", "abc", 1);
    EXPECT_EQ(PROFILING_FAILED, invalidInfoJson.InitDeviceIds());
}

TEST(INFO_JSON_TEST, GetRankIdBranches) {
    GlobalMockObject::verify();
    InfoJson infoJson("", "0", 1);

    setenv("RANK_ID", "5", 1);
    EXPECT_EQ(5, infoJson.GetRankId());

    setenv("RANK_ID", "abc", 1);
    EXPECT_EQ(-1, infoJson.GetRankId());

    unsetenv("RANK_ID");
    EXPECT_EQ(-1, infoJson.GetRankId());

    SHARED_PTR_ALIA<InfoMain> infoMain = nullptr;
    MSVP_MAKE_SHARED0(infoMain, InfoMain, return);
    setenv("RANK_ID", "7", 1);
    infoJson.SetRankId(infoMain);
    EXPECT_EQ(7, infoMain->rankId);
    unsetenv("RANK_ID");
}

TEST(INFO_JSON_TEST, SetVersionInfoPlatformVersionAndDrvVersion) {
    GlobalMockObject::verify();
    InfoJson infoJson("", "0", 1);
    SHARED_PTR_ALIA<InfoMain> infoMain = nullptr;
    MSVP_MAKE_SHARED0(infoMain, InfoMain, return);

    infoJson.SetVersionInfo(infoMain);
    EXPECT_FALSE(infoMain->version.empty());

    infoJson.SetPlatFormVersion(infoMain);

    MOCKER_CPP(&Platform::DrvGetApiVersion).stubs().will(returnValue(static_cast<uint32_t>(0x12345)));
    infoJson.SetDrvVersion(infoMain);
    EXPECT_EQ(0x12345u, infoMain->drvVersion);
}

TEST(INFO_JSON_TEST, OscFrequencyGetters) {
    GlobalMockObject::verify();
    InfoJson infoJson("", "0", 1);

    MOCKER_CPP(&Platform::PlatformGetHostOscFreq).stubs().will(returnValue(std::string("12345")));
    EXPECT_EQ("12345", infoJson.GetHostOscFrequency());
    GlobalMockObject::verify();

    MOCKER_CPP(&Platform::PlatformGetDeviceOscFreq).stubs().will(returnValue(std::string("67890")));
    EXPECT_EQ("67890", infoJson.GetDeviceOscFrequency(0u, "1000"));
}

TEST(INFO_JSON_TEST, GetCtrlCpuInfoBranches) {
    GlobalMockObject::verify();
    InfoJson infoJson("", "0", 1);
    DeviceInfo devInfo;

    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuId).stubs().will(invoke(DrvInfoFail));
    EXPECT_EQ(PROFILING_FAILED, infoJson.GetCtrlCpuInfo(0, devInfo));
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuId).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuCoreNum).stubs().will(invoke(DrvInfoFail));
    EXPECT_EQ(PROFILING_FAILED, infoJson.GetCtrlCpuInfo(0, devInfo));
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuId).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuEndianLittle).stubs().will(invoke(DrvInfoFail));
    EXPECT_EQ(PROFILING_FAILED, infoJson.GetCtrlCpuInfo(0, devInfo));
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuId).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuEndianLittle).stubs().will(invoke(DrvInfoOk));
    EXPECT_EQ(PROFILING_SUCCESS, infoJson.GetCtrlCpuInfo(0, devInfo));
}

TEST(INFO_JSON_TEST, GetDevInfoFailureBranches) {
    GlobalMockObject::verify();
    InfoJson infoJson("", "0", 1);
    DeviceInfo devInfo;

    MOCKER_CPP(&analysis::dvvp::driver::DrvGetEnvType).stubs().will(invoke(DrvInfoFail));
    EXPECT_EQ(PROFILING_FAILED, infoJson.GetDevInfo(0, devInfo));
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::driver::DrvGetEnvType).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuId).stubs().will(invoke(DrvInfoFail));
    EXPECT_EQ(PROFILING_FAILED, infoJson.GetDevInfo(0, devInfo));
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::driver::DrvGetEnvType).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuId).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuEndianLittle).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCpuCoreNum).stubs().will(invoke(DrvInfoFail));
    EXPECT_EQ(PROFILING_FAILED, infoJson.GetDevInfo(0, devInfo));
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::driver::DrvGetEnvType).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuId).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuEndianLittle).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAivNum).stubs().will(invoke(DrvInfoFail));
    EXPECT_EQ(PROFILING_FAILED, infoJson.GetDevInfo(0, devInfo));
}

TEST(INFO_JSON_TEST, GetDevInfoAiCpuCoreIdAndSuccessBranches) {
    GlobalMockObject::verify();
    InfoJson infoJson("", "0", 1);
    DeviceInfo devInfo;

    MOCKER_CPP(&analysis::dvvp::driver::DrvGetEnvType).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuId).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuEndianLittle).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCpuCoreNum).stubs().will(invoke(DrvInfoOne));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAivNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCpuCoreId).stubs().will(invoke(DrvInfoFail));
    EXPECT_EQ(PROFILING_FAILED, infoJson.GetDevInfo(0, devInfo));
    GlobalMockObject::verify();

    MockSuccessfulDeviceInfo();
    EXPECT_EQ(PROFILING_SUCCESS, infoJson.GetDevInfo(0, devInfo));
}

TEST(INFO_JSON_TEST, GetDevInfoLateFailureBranches) {
    GlobalMockObject::verify();
    InfoJson infoJson("", "0", 1);
    DeviceInfo devInfo;

    MOCKER_CPP(&analysis::dvvp::driver::DrvGetEnvType).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuId).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuEndianLittle).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAivNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCpuOccupyBitmap).stubs().will(invoke(DrvInfoFail));
    EXPECT_EQ(PROFILING_FAILED, infoJson.GetDevInfo(0, devInfo));
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::driver::DrvGetEnvType).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuId).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuEndianLittle).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAivNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCpuOccupyBitmap).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetTsCpuCoreNum).stubs().will(invoke(DrvInfoFail));
    EXPECT_EQ(PROFILING_FAILED, infoJson.GetDevInfo(0, devInfo));
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::driver::DrvGetEnvType).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuId).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuEndianLittle).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAivNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCpuOccupyBitmap).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetTsCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCoreId).stubs().will(invoke(DrvInfoFail));
    EXPECT_EQ(PROFILING_FAILED, infoJson.GetDevInfo(0, devInfo));
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::driver::DrvGetEnvType).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuId).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuEndianLittle).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAivNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCpuOccupyBitmap).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetTsCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCoreId).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCoreNum).stubs().will(invoke(DrvInfoFail));
    EXPECT_EQ(PROFILING_FAILED, infoJson.GetDevInfo(0, devInfo));
}

TEST(INFO_JSON_TEST, AddDeviceInfoBranches) {
    GlobalMockObject::verify();
    InfoJson infoJson("", "0", 1);
    EXPECT_EQ(PROFILING_SUCCESS, infoJson.InitDeviceIds());
    SHARED_PTR_ALIA<InfoMain> infoMain = nullptr;
    MSVP_MAKE_SHARED0(infoMain, InfoMain, return);

    MockSuccessfulDeviceInfo();
    MOCKER_CPP(&Analysis::Dvvp::Driver::DrvGeAicFrq).stubs().will(returnValue(std::string("1500")));
    MOCKER_CPP(&Platform::PlatformGetDeviceOscFreq).stubs().will(returnValue(std::string("100")));
    EXPECT_EQ(PROFILING_SUCCESS, infoJson.AddDeviceInfo(infoMain));
    EXPECT_FALSE(infoMain->deviceInfos.empty());
    GlobalMockObject::verify();

    InfoJson failedInfoJson("", "0", 1);
    EXPECT_EQ(PROFILING_SUCCESS, failedInfoJson.InitDeviceIds());
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetEnvType).stubs().will(invoke(DrvInfoFail));
    EXPECT_EQ(PROFILING_FAILED, failedInfoJson.AddDeviceInfo(infoMain));
}

TEST(INFO_JSON_TEST, AddDeviceInfoCpuTypeMatchesMap) {
    GlobalMockObject::verify();
    InfoJson infoJson("", "0", 1);
    EXPECT_EQ(PROFILING_SUCCESS, infoJson.InitDeviceIds());
    SHARED_PTR_ALIA<InfoMain> infoMain = nullptr;
    MSVP_MAKE_SHARED0(infoMain, InfoMain, return);

    MOCKER_CPP(&analysis::dvvp::driver::DrvGetEnvType).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuId).stubs().will(invoke(DrvInfoA55));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetCtrlCpuEndianLittle).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAivNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCpuOccupyBitmap).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetTsCpuCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCoreId).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&analysis::dvvp::driver::DrvGetAiCoreNum).stubs().will(invoke(DrvInfoOk));
    MOCKER_CPP(&Analysis::Dvvp::Driver::DrvGeAicFrq).stubs().will(returnValue(std::string("1500")));
    MOCKER_CPP(&Platform::PlatformGetDeviceOscFreq).stubs().will(returnValue(std::string("100")));

    EXPECT_EQ(PROFILING_SUCCESS, infoJson.AddDeviceInfo(infoMain));
    EXPECT_FALSE(infoMain->deviceInfos.empty());
    EXPECT_EQ("ARMv8_Cortex_A55", infoMain->deviceInfos[0].ctrlCpuId);
}

TEST(INFO_JSON_TEST, AddOtherInfoBranches) {
    GlobalMockObject::verify();
    InfoJson emptyJobInfoJson("", "0", 1);
    SHARED_PTR_ALIA<InfoMain> infoMain = nullptr;
    MSVP_MAKE_SHARED0(infoMain, InfoMain, return);
    EXPECT_EQ(PROFILING_SUCCESS, emptyJobInfoJson.AddOtherInfo(infoMain));
    EXPECT_EQ("NA", infoMain->jobInfo);

    InfoJson jobInfoJson("myJob", "0", 1);
    EXPECT_EQ(PROFILING_SUCCESS, jobInfoJson.AddOtherInfo(infoMain));
    EXPECT_EQ("myJob", infoMain->jobInfo);
}

TEST(INFO_JSON_TEST, AddSysConfSysTimeMemTotalAndNetCardInfo) {
    GlobalMockObject::verify();
    InfoJson infoJson("", "0", 1);
    SHARED_PTR_ALIA<InfoMain> infoMain = nullptr;
    MSVP_MAKE_SHARED0(infoMain, InfoMain, return);

    infoJson.AddSysConf(infoMain);

    MOCKER_CPP(&analysis::dvvp::common::utils::Utils::GetFileSize)
        .stubs()
        .will(returnValue(static_cast<int64_t>(MSVP_LARGE_FILE_MAX_LEN + 1)));
    infoJson.AddSysTime(infoMain);
    infoJson.AddMemTotal(infoMain);
    GlobalMockObject::verify();

    MOCKER_CPP(&analysis::dvvp::common::utils::Utils::GetFileSize)
        .stubs()
        .will(returnValue(static_cast<int64_t>(-1)));
    infoJson.AddSysTime(infoMain);
    infoJson.AddMemTotal(infoMain);
    GlobalMockObject::verify();

    infoJson.AddNetCardInfo(infoMain);
}

TEST(INFO_JSON_TEST, GenerateInitDevicesFail) {
    GlobalMockObject::verify();
    InfoJson infoJson("", "abc", 1);
    std::string content;
    EXPECT_EQ(PROFILING_FAILED, infoJson.Generate(content));
}
