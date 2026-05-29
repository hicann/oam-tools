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
#include <fstream>
#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"
#include "info_json.h"
#include "ai_drv_dev_api.h"
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

TEST(INFO_JSON_TEST, GetHwtsFreq) {
    GlobalMockObject::verify();
    auto configManager = ConfigManager::instance();
    const bool hasOriginalType = configManager->configMap_.count("type") > 0;
    const std::string originalType = hasOriginalType ? configManager->configMap_["type"] : "";
    configManager->configMap_["type"] = std::to_string(static_cast<int32_t>(PlatformType::CHIP_CLOUD_V3));
    InfoJson infoJson("1", "0", 1);
    std::string freq = "1005";
    EXPECT_EQ("1000", infoJson.GetHwtsFreq(freq));
    freq = "1000.1";
    EXPECT_EQ("1000.1", infoJson.GetHwtsFreq(freq));
    if (hasOriginalType) {
        configManager->configMap_["type"] = originalType;
    } else {
        configManager->configMap_.erase("type");
    }
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