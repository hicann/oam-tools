/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
#include <cstdio>
#include <fstream>
#include <string>

#include "gtest/gtest.h"

#include "ai_drv_prof_api.h"
#include "json_parser.h"
#include "prof_api.h"

using namespace Msprofiler::Parser;
using namespace analysis::dvvp::driver;
using namespace analysis::dvvp::common::config;

namespace {
const char* const JSON_PARSER_TEST_FILE = "./prof_json_parser_utest.json";

class JSON_PARSER_UTEST : public testing::Test {
protected:
    void SetUp() override
    {
        JsonParser::instance()->UnInit();
        std::remove(JSON_PARSER_TEST_FILE);
    }

    void TearDown() override
    {
        JsonParser::instance()->UnInit();
        std::remove(JSON_PARSER_TEST_FILE);
    }

    void WriteJson(const std::string& content) const
    {
        std::ofstream jsonFile(JSON_PARSER_TEST_FILE);
        jsonFile << content;
    }
};

const std::string CANN_JSON = R"({
    "profiler": "off",
    "cann": {
        "modules": [
            {
                "module": "ACL"
            },
            {
                "module": "FRAMEWORK",
                "prof_switch": "off"
            },
            {
                "module": "RUNTIME",
                "prof_switch": "on"
            },
            {
                "module": "UNKNOWN",
                "prof_switch": "off"
            }
        ],
        "reporters": [
            {
                "reporter": "API_EVENT",
                "reporter_switch": "on",
                "report_buffer_len": 16384
            },
            {
                "reporter": "COMPACT",
                "reporter_switch": "off",
                "report_buffer_len": 50000
            },
            {
                "reporter": "ADDITIONAL",
                "reporter_switch": "on"
            },
            {
                "reporter": "UNKNOWN",
                "reporter_switch": "off"
            }
        ]
    }
})";

const std::string DEVICE_JSON = R"({
    "device": {
        "poll_period": 10000,
        "channels": [
            {
                "channel": 6
            },
            {
                "channel": 7,
                "period": 20,
                "threshold": 999,
                "channel_buffer_size": 2097152,
                "driver_buffer_size": 64,
                "prof_switch": "on",
                "reporter_switch": "on"
            },
            {
                "channel": 45,
                "period": 10000,
                "threshold": 100,
                "channel_buffer_size": 10,
                "driver_buffer_size": 10,
                "prof_switch": "off",
                "reporter_switch": "off"
            },
            {
                "channel": 48,
                "period": 20,
                "threshold": 20,
                "channel_buffer_size": 2097152,
                "driver_buffer_size": 100,
                "prof_switch": "on",
                "reporter_switch": "on"
            },
            {
                "channel": 0,
                "period": 10
            },
            {
                "channel": 160,
                "period": 10
            }
        ]
    }
})";

const std::string FULL_JSON = R"({
    "cann": {
        "modules": [
            {
                "module": "MSPROF",
                "prof_switch": "off"
            },
            {
                "module": "DATA_PREPROCESS",
                "prof_switch": "on"
            }
        ],
        "reporters": [
            {
                "reporter": "API_EVENT",
                "report_buffer_len": 8192
            },
            {
                "reporter": "ADDITIONAL",
                "report_buffer_len": 32768,
                "reporter_switch": "off"
            }
        ]
    },
    "device": {
        "channels": [
            {
                "channel": 45,
                "period": 1,
                "threshold": 10,
                "channel_buffer_size": 1048576,
                "driver_buffer_size": 32
            },
            {
                "channel": 48,
                "period": 1000,
                "threshold": 95,
                "channel_buffer_size": 4194304,
                "driver_buffer_size": 128,
                "prof_switch": "off"
            }
        ]
    }
})";
} // namespace

TEST_F(JSON_PARSER_UTEST, InitWithMissingInvalidAndEmptyJsonKeepsDefaults)
{
    JsonParser::instance()->Init("./not_exist_prof_json_parser_utest.json");
    EXPECT_TRUE(JsonParser::instance()->moduleParams_.empty());
    EXPECT_TRUE(JsonParser::instance()->reporterParams_.empty());
    EXPECT_TRUE(JsonParser::instance()->channelParams_.empty());
    JsonParser::instance()->UnInit();

    WriteJson("{ invalid json");
    JsonParser::instance()->Init(JSON_PARSER_TEST_FILE);
    EXPECT_TRUE(JsonParser::instance()->moduleParams_.empty());
    EXPECT_TRUE(JsonParser::instance()->reporterParams_.empty());
    EXPECT_TRUE(JsonParser::instance()->channelParams_.empty());
    JsonParser::instance()->UnInit();

    WriteJson("{}");
    JsonParser::instance()->Init(JSON_PARSER_TEST_FILE);
    EXPECT_TRUE(JsonParser::instance()->moduleParams_.empty());
    EXPECT_TRUE(JsonParser::instance()->reporterParams_.empty());
    EXPECT_TRUE(JsonParser::instance()->channelParams_.empty());
    EXPECT_TRUE(JsonParser::instance()->GetJsonModuleProfSwitch(ASCENDCL));
    EXPECT_TRUE(JsonParser::instance()->GetJsonModuleReporterSwitch(API_EVENT));
    EXPECT_EQ(0U, JsonParser::instance()->GetJsonModuleReporterBufferLen(API_EVENT));
    EXPECT_TRUE(JsonParser::instance()->GetJsonChannelProfSwitch(PROF_CHANNEL_DVPP));
    EXPECT_TRUE(JsonParser::instance()->GetJsonChannelReporterSwitch(PROF_CHANNEL_DVPP));
    EXPECT_EQ(0U, JsonParser::instance()->GetJsonChannelReportBufferLen(PROF_CHANNEL_DVPP));
    EXPECT_EQ(0U, JsonParser::instance()->GetJsonChannelDriverBufferLen(PROF_CHANNEL_DVPP));
    EXPECT_EQ(0U, JsonParser::instance()->GetJsonChannelPeriod(PROF_CHANNEL_DVPP));
    EXPECT_EQ(0U, JsonParser::instance()->GetJsonChannelThreshold(PROF_CHANNEL_DVPP));
}

TEST_F(JSON_PARSER_UTEST, ParsesCannModulesAndReporters)
{
    WriteJson(CANN_JSON);
    JsonParser::instance()->Init(JSON_PARSER_TEST_FILE);

    EXPECT_EQ(3U, JsonParser::instance()->moduleParams_.size());
    EXPECT_EQ(3U, JsonParser::instance()->reporterParams_.size());
    EXPECT_TRUE(JsonParser::instance()->channelParams_.empty());

    EXPECT_TRUE(JsonParser::instance()->GetJsonModuleProfSwitch(ASCENDCL));
    EXPECT_FALSE(JsonParser::instance()->GetJsonModuleProfSwitch(GE));
    EXPECT_TRUE(JsonParser::instance()->GetJsonModuleProfSwitch(RUNTIME));
    EXPECT_TRUE(JsonParser::instance()->GetJsonModuleProfSwitch(HCCL));

    EXPECT_TRUE(JsonParser::instance()->GetJsonModuleReporterSwitch(API_EVENT));
    EXPECT_EQ(16384U, JsonParser::instance()->GetJsonModuleReporterBufferLen(API_EVENT));
    EXPECT_FALSE(JsonParser::instance()->GetJsonModuleReporterSwitch(COMPACT));
    EXPECT_EQ(0U, JsonParser::instance()->GetJsonModuleReporterBufferLen(COMPACT));
    EXPECT_TRUE(JsonParser::instance()->GetJsonModuleReporterSwitch(ADDITIONAL));
    EXPECT_EQ(0U, JsonParser::instance()->GetJsonModuleReporterBufferLen(ADDITIONAL));
}

TEST_F(JSON_PARSER_UTEST, ParsesDeviceChannelsAndBounds)
{
    WriteJson(DEVICE_JSON);
    JsonParser::instance()->Init(JSON_PARSER_TEST_FILE);

    EXPECT_TRUE(JsonParser::instance()->moduleParams_.empty());
    EXPECT_TRUE(JsonParser::instance()->reporterParams_.empty());
    EXPECT_EQ(4U, JsonParser::instance()->channelParams_.size());

    EXPECT_TRUE(JsonParser::instance()->GetJsonChannelReporterSwitch(PROF_CHANNEL_DVPP));
    EXPECT_TRUE(JsonParser::instance()->GetJsonChannelProfSwitch(PROF_CHANNEL_DVPP));
    EXPECT_EQ(0U, JsonParser::instance()->GetJsonChannelReportBufferLen(PROF_CHANNEL_DVPP));
    EXPECT_EQ(0U, JsonParser::instance()->GetJsonChannelDriverBufferLen(PROF_CHANNEL_DVPP));
    EXPECT_EQ(0U, JsonParser::instance()->GetJsonChannelPeriod(PROF_CHANNEL_DVPP));
    EXPECT_EQ(0U, JsonParser::instance()->GetJsonChannelThreshold(PROF_CHANNEL_DVPP));

    EXPECT_TRUE(JsonParser::instance()->GetJsonChannelReporterSwitch(PROF_CHANNEL_DDR));
    EXPECT_TRUE(JsonParser::instance()->GetJsonChannelProfSwitch(PROF_CHANNEL_DDR));
    EXPECT_EQ(2097152U, JsonParser::instance()->GetJsonChannelReportBufferLen(PROF_CHANNEL_DDR));
    EXPECT_EQ(64U, JsonParser::instance()->GetJsonChannelDriverBufferLen(PROF_CHANNEL_DDR));
    EXPECT_EQ(20U, JsonParser::instance()->GetJsonChannelPeriod(PROF_CHANNEL_DDR));
    EXPECT_EQ(999U, JsonParser::instance()->GetJsonChannelThreshold(PROF_CHANNEL_DDR));

    EXPECT_FALSE(JsonParser::instance()->GetJsonChannelReporterSwitch(PROF_CHANNEL_HWTS_LOG));
    EXPECT_FALSE(JsonParser::instance()->GetJsonChannelProfSwitch(PROF_CHANNEL_HWTS_LOG));
    EXPECT_EQ(0U, JsonParser::instance()->GetJsonChannelReportBufferLen(PROF_CHANNEL_HWTS_LOG));
    EXPECT_EQ(10U, JsonParser::instance()->GetJsonChannelDriverBufferLen(PROF_CHANNEL_HWTS_LOG));
    EXPECT_EQ(0U, JsonParser::instance()->GetJsonChannelPeriod(PROF_CHANNEL_HWTS_LOG));
    EXPECT_EQ(0U, JsonParser::instance()->GetJsonChannelThreshold(PROF_CHANNEL_HWTS_LOG));

    EXPECT_TRUE(JsonParser::instance()->GetJsonChannelReporterSwitch(PROF_CHANNEL_AIV_HWTS_LOG));
    EXPECT_TRUE(JsonParser::instance()->GetJsonChannelProfSwitch(PROF_CHANNEL_AIV_HWTS_LOG));
    EXPECT_EQ(2097152U, JsonParser::instance()->GetJsonChannelReportBufferLen(PROF_CHANNEL_AIV_HWTS_LOG));
    EXPECT_EQ(100U, JsonParser::instance()->GetJsonChannelDriverBufferLen(PROF_CHANNEL_AIV_HWTS_LOG));
    EXPECT_EQ(20U, JsonParser::instance()->GetJsonChannelPeriod(PROF_CHANNEL_AIV_HWTS_LOG));
    EXPECT_EQ(20U, JsonParser::instance()->GetJsonChannelThreshold(PROF_CHANNEL_AIV_HWTS_LOG));
}

TEST_F(JSON_PARSER_UTEST, ParsesFullJsonAndInitOnlyOnce)
{
    WriteJson(FULL_JSON);
    JsonParser::instance()->Init(JSON_PARSER_TEST_FILE);

    EXPECT_EQ(2U, JsonParser::instance()->moduleParams_.size());
    EXPECT_EQ(2U, JsonParser::instance()->reporterParams_.size());
    EXPECT_EQ(2U, JsonParser::instance()->channelParams_.size());

    EXPECT_FALSE(JsonParser::instance()->moduleParams_[MSPROF_MODULE_MSPROF].profSwitch);
    EXPECT_TRUE(JsonParser::instance()->GetJsonModuleProfSwitch(AICPU));
    EXPECT_EQ(8192U, JsonParser::instance()->GetJsonModuleReporterBufferLen(API_EVENT));
    EXPECT_TRUE(JsonParser::instance()->GetJsonModuleReporterSwitch(API_EVENT));
    EXPECT_EQ(32768U, JsonParser::instance()->GetJsonModuleReporterBufferLen(ADDITIONAL));
    EXPECT_FALSE(JsonParser::instance()->GetJsonModuleReporterSwitch(ADDITIONAL));

    EXPECT_EQ(1U, JsonParser::instance()->GetJsonChannelPeriod(PROF_CHANNEL_HWTS_LOG));
    EXPECT_EQ(10U, JsonParser::instance()->GetJsonChannelThreshold(PROF_CHANNEL_HWTS_LOG));
    EXPECT_EQ(1048576U, JsonParser::instance()->GetJsonChannelReportBufferLen(PROF_CHANNEL_HWTS_LOG));
    EXPECT_EQ(32U, JsonParser::instance()->GetJsonChannelDriverBufferLen(PROF_CHANNEL_HWTS_LOG));
    EXPECT_TRUE(JsonParser::instance()->GetJsonChannelProfSwitch(PROF_CHANNEL_HWTS_LOG));
    EXPECT_TRUE(JsonParser::instance()->GetJsonChannelReporterSwitch(PROF_CHANNEL_HWTS_LOG));

    EXPECT_EQ(1000U, JsonParser::instance()->GetJsonChannelPeriod(PROF_CHANNEL_AIV_HWTS_LOG));
    EXPECT_EQ(95U, JsonParser::instance()->GetJsonChannelThreshold(PROF_CHANNEL_AIV_HWTS_LOG));
    EXPECT_EQ(4194304U, JsonParser::instance()->GetJsonChannelReportBufferLen(PROF_CHANNEL_AIV_HWTS_LOG));
    EXPECT_EQ(128U, JsonParser::instance()->GetJsonChannelDriverBufferLen(PROF_CHANNEL_AIV_HWTS_LOG));
    EXPECT_FALSE(JsonParser::instance()->GetJsonChannelProfSwitch(PROF_CHANNEL_AIV_HWTS_LOG));
    EXPECT_TRUE(JsonParser::instance()->GetJsonChannelReporterSwitch(PROF_CHANNEL_AIV_HWTS_LOG));

    WriteJson("{}");
    JsonParser::instance()->Init(JSON_PARSER_TEST_FILE);
    EXPECT_EQ(2U, JsonParser::instance()->moduleParams_.size());
    EXPECT_EQ(2U, JsonParser::instance()->reporterParams_.size());
    EXPECT_EQ(2U, JsonParser::instance()->channelParams_.size());
}

TEST_F(JSON_PARSER_UTEST, CheckIds)
{
    EXPECT_TRUE(JsonParser::instance()->CheckJsonModuleId(PROF_JSON_ACL));
    EXPECT_TRUE(JsonParser::instance()->CheckJsonModuleId(PROF_JSON_MSPROF));
    EXPECT_FALSE(JsonParser::instance()->CheckJsonModuleId("INVALID"));

    EXPECT_TRUE(JsonParser::instance()->CheckJsonReporterId(PROF_JSON_API_EVENT));
    EXPECT_TRUE(JsonParser::instance()->CheckJsonReporterId(PROF_JSON_ADDITIONAL));
    EXPECT_FALSE(JsonParser::instance()->CheckJsonReporterId("INVALID"));

    EXPECT_FALSE(JsonParser::instance()->CheckJsonChannelId(PROF_CHANNEL_UNKNOWN));
    EXPECT_TRUE(JsonParser::instance()->CheckJsonChannelId(PROF_CHANNEL_DVPP));
    EXPECT_FALSE(JsonParser::instance()->CheckJsonChannelId(PROF_CHANNEL_MAX));
}
