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
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <vector>

#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"
#include "errno/error_code.h"
#include "input_parser.h"
#include "config_manager.h"
#include "dyn_prof_client.h"
#include "platform/platform.h"

using namespace analysis::dvvp::common::error;
using namespace Analysis::Dvvp::Msprof;
using namespace Analysis::Dvvp::Common::Config;
using namespace Collector::Dvvp::DynProf;
using namespace Analysis::Dvvp::Common::Platform;

namespace {
constexpr int MSPROF_DAEMON_ERROR = -1;
constexpr int MSPROF_DAEMON_OK = 0;
constexpr int32_t MSPROF_APP_ARGC = 4;
constexpr int32_t SPLIT_APP_ARG_COUNT = 2;
constexpr int32_t INVALID_HOST_OPTION = 999;
constexpr int32_t INVALID_PROCESS = 99999999;
constexpr int32_t CPU_SAMPLING_INTERVAL_FOR_FREQ_TEN = 100;
constexpr int32_t INVALID_FREQ_OPTION = 100;
constexpr int32_t DYNAMIC_OUTPUT_ARG_INDEX = 2;
constexpr int32_t DYNAMIC_APP_ARG_INDEX = 3;
constexpr int32_t DVPP_FREQ_ARG_INDEX = 58;
constexpr int32_t CPU_SAMPLING_FREQ_ARG_INDEX = 59;
constexpr int32_t INVALID_ARG_INDEX = 63;
constexpr int32_t INTERCONNECTION_FREQ_ARG_INDEX = 60;
constexpr int32_t APP_PARAM_EXCEED_MAX_LEN = analysis::dvvp::common::config::MAX_APP_LEN + 1;
constexpr int32_t OP_TYPE_EXCEED_MAX_LEN = 300;
constexpr PlatformType TARGET_CHIP_TYPE = PlatformType::CHIP_MDC_V2;

void SetPlatformTypeForTest(PlatformType platformType)
{
    ConfigManager::instance()->configMap_["type"] = std::to_string(static_cast<int32_t>(platformType));
}

void RefreshArgsManagerForTest()
{
    ArgsManager::instance()->argsList_.clear();
    ArgsManager::instance()->AddArgs();
}

class INPUT_PARSER_UTEST : public testing::Test {
protected:
    void SetUp() override {}
    void TearDown() override { GlobalMockObject::verify(); }
};

TEST_F(INPUT_PARSER_UTEST, ProcessOptions) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    struct MsprofCmdInfo cmdInfo = {{nullptr}};

    std::vector<char> onArgs = {'o', 'n', '\0'};
    std::vector<char> freqArgs = {'1', '0', '\0'};
    std::vector<char> hostArgs = {'c', 'p', 'u', '\0'};

    optarg = onArgs.data();
    EXPECT_EQ(PROFILING_SUCCESS, parser.ProcessOptions(ARGS_OUTPUT, cmdInfo));
    EXPECT_EQ(PROFILING_SUCCESS, parser.ProcessOptions(ARGS_ASCENDCL, cmdInfo));
    optarg = freqArgs.data();
    EXPECT_EQ(PROFILING_SUCCESS, parser.ProcessOptions(ARGS_AIC_FREQ, cmdInfo));
    optarg = hostArgs.data();
    EXPECT_EQ(PROFILING_SUCCESS, parser.ProcessOptions(ARGS_HOST_SYS, cmdInfo));
}

TEST_F(INPUT_PARSER_UTEST, SplitApplicationArgv) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    int32_t argc = 4;
    const char *argv[] = {"msprof", "--output=./", "app", "arg1"};
    int32_t argCount = 1;
    parser.SplitApplicationArgv(argc, argv, argCount);
    EXPECT_EQ(SPLIT_APP_ARG_COUNT, argCount);
}

TEST_F(INPUT_PARSER_UTEST, SplitApplicationArgvWithHelpOnly) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    int32_t argc = 2;
    const char *argv[] = {"msprof", "--help"};
    int32_t argCount = 1;
    parser.SplitApplicationArgv(argc, argv, argCount);
    EXPECT_EQ(SPLIT_APP_ARG_COUNT, argCount);
}

TEST_F(INPUT_PARSER_UTEST, HandleApp) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    parser.params_->application.emplace_back("app");
    parser.params_->application.emplace_back("arg1");
    parser.HandleApp();
    EXPECT_TRUE(parser.params_->app.compare("app") == 0);
    parser.params_->app = "test";
    parser.HandleApp();
    EXPECT_TRUE(parser.params_->app.compare("test") == 0);
}

TEST_F(INPUT_PARSER_UTEST, CheckSysCpu) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    parser.params_->cpu_profiling = "on";
    Platform::instance()->runSide_ = SysPlatformType::HOST;
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.CheckSysCpu());
    Platform::instance()->runSide_ = SysPlatformType::DEVICE;
    parser.params_->cpu_profiling = "off";
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.CheckSysCpu());
    Platform::instance()->runSide_ = SysPlatformType::INVALID;
}

TEST_F(INPUT_PARSER_UTEST, MsprofHostCheckValid) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    struct MsprofCmdInfo cmdInfo = {{nullptr}};
    // invalid options
    EXPECT_EQ(PROFILING_FAILED, parser.MsprofHostCheckValid(cmdInfo, INVALID_HOST_OPTION));

    EXPECT_EQ(PROFILING_FAILED, parser.MsprofHostCheckValid(cmdInfo, NR_ARGS));

    EXPECT_EQ(PROFILING_FAILED, parser.MsprofHostCheckValid(cmdInfo, ARGS_HOST_SYS));

    cmdInfo.args[ARGS_HOST_SYS] = "";
    EXPECT_EQ(PROFILING_FAILED, parser.MsprofHostCheckValid(cmdInfo, ARGS_HOST_SYS));

    cmdInfo.args[ARGS_HOST_SYS] = "cpu,mem";
    EXPECT_EQ(PROFILING_SUCCESS, parser.MsprofHostCheckValid(cmdInfo, ARGS_HOST_SYS));

    cmdInfo.args[ARGS_HOST_SYS] = "cpu,mem,network,osrt";
    EXPECT_EQ(PROFILING_FAILED, parser.MsprofHostCheckValid(cmdInfo, ARGS_HOST_SYS));

    cmdInfo.args[ARGS_HOST_SYS] = "cpu,mem,disk,network,invalid";
    parser.params_->result_dir = "./input_parser_utest";
    EXPECT_EQ(PROFILING_FAILED, parser.MsprofHostCheckValid(cmdInfo, ARGS_HOST_SYS));

    EXPECT_EQ(PROFILING_FAILED, parser.MsprofHostCheckValid(cmdInfo, ARGS_HOST_SYS_PID));
    cmdInfo.args[ARGS_HOST_SYS_PID] = "121312312123";
    EXPECT_EQ(PROFILING_FAILED, parser.MsprofHostCheckValid(cmdInfo, ARGS_HOST_SYS_PID));
    cmdInfo.args[ARGS_HOST_SYS_PID] = "";

    EXPECT_EQ(PROFILING_FAILED, parser.MsprofHostCheckValid(cmdInfo, ARGS_HOST_SYS_USAGE));
    cmdInfo.args[ARGS_HOST_SYS_USAGE] = "cpu,mem";
    EXPECT_EQ(PROFILING_SUCCESS, parser.MsprofHostCheckValid(cmdInfo, ARGS_HOST_SYS_USAGE));
    cmdInfo.args[ARGS_HOST_SYS_USAGE] = "disk,network,osrt";
    EXPECT_EQ(PROFILING_FAILED, parser.MsprofHostCheckValid(cmdInfo, ARGS_HOST_SYS_USAGE));
}

TEST_F(INPUT_PARSER_UTEST, CheckHostSysCmdOutIsExist) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    std::string tempFile = "./CheckHostSysCmdOutIsExist";
    std::ofstream file(tempFile);
    file << "iotop version" << std::endl;
    file.close();
    std::string toolName = "iotop";
    mmProcess tmpProcess = analysis::dvvp::common::config::MSVP_PROCESS;
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckHostSysCmdOutIsExist(tempFile, toolName, tmpProcess));
}

TEST_F(INPUT_PARSER_UTEST, CheckHostOutString) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    std::string tmpStr = "";
    std::string toolName = "iotop";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckHostOutString(tmpStr, toolName));
    tmpStr = "sudo";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckHostOutString(tmpStr, toolName));
    tmpStr = "iotop";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckHostOutString(tmpStr, toolName));
}

TEST_F(INPUT_PARSER_UTEST, UninitCheckHostSysCmd) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    mmProcess checkProcess = INVALID_PROCESS;

    EXPECT_EQ(PROFILING_FAILED, parser.UninitCheckHostSysCmd(checkProcess));
}

TEST_F(INPUT_PARSER_UTEST, CheckOutputValid) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    struct MsprofCmdInfo cmdInfo = {
        {nullptr, nullptr}
    };

    EXPECT_EQ(PROFILING_FAILED, parser.CheckOutputValid(cmdInfo));
    cmdInfo.args[ARGS_OUTPUT] = "";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckOutputValid(cmdInfo));
    cmdInfo.args[ARGS_OUTPUT] = "./";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckOutputValid(cmdInfo));
}

TEST_F(INPUT_PARSER_UTEST, CheckStorageLimitValid) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    struct MsprofCmdInfo cmdInfo = {{nullptr}};

    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckStorageLimitValid(cmdInfo));
    cmdInfo.args[ARGS_STORAGE_LIMIT] = "";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckStorageLimitValid(cmdInfo));
    cmdInfo.args[ARGS_STORAGE_LIMIT] = "1000MB";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckStorageLimitValid(cmdInfo));
    cmdInfo.args[ARGS_STORAGE_LIMIT] = "10MB";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckStorageLimitValid(cmdInfo));
}

TEST_F(INPUT_PARSER_UTEST, GetAppParam) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    std::remove("./GetAppParam");
    EXPECT_EQ(PROFILING_FAILED, parser.GetAppParam(""));
    EXPECT_EQ(PROFILING_FAILED, parser.GetAppParam(" "));
    EXPECT_EQ(PROFILING_FAILED, parser.GetAppParam("./GetAppParam"));
    EXPECT_EQ(PROFILING_FAILED, parser.GetAppParam("./GetAppParam a"));
    std::ofstream file("GetAppParam");
    file << "command not found" << std::endl;
    file.close();
    EXPECT_EQ(PROFILING_SUCCESS, parser.GetAppParam("./GetAppParam a"));
}

TEST_F(INPUT_PARSER_UTEST, CheckAppValid) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    struct MsprofCmdInfo cmdInfo = {{nullptr}};
    std::remove("./CheckAppValid");
    EXPECT_EQ(PROFILING_FAILED, parser.CheckAppValid(cmdInfo));
    cmdInfo.args[ARGS_APPLICATION] = "";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckAppValid(cmdInfo));
    cmdInfo.args[ARGS_APPLICATION] = "        ";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckAppValid(cmdInfo));
    cmdInfo.args[ARGS_APPLICATION] = "bash";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckAppValid(cmdInfo));
    cmdInfo.args[ARGS_APPLICATION] = "./bash";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckAppValid(cmdInfo));
    cmdInfo.args[ARGS_APPLICATION] = "./CheckAppValid a";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckAppValid(cmdInfo));
    cmdInfo.args[ARGS_APPLICATION] = "/bin/ls -l";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckAppValid(cmdInfo));
    std::remove("./CheckAppValid");
    cmdInfo.args[ARGS_APPLICATION] = "python3 -m ais-bench xxx";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckAppValid(cmdInfo));
    EXPECT_EQ("python3", parser.params_->cmdPath);
    EXPECT_EQ("python3", parser.params_->app);
    EXPECT_EQ("-m ais-bench xxx", parser.params_->app_parameters);

    std::vector<char> longAppParam(APP_PARAM_EXCEED_MAX_LEN, 'a');
    longAppParam.emplace_back('\0');
    cmdInfo.args[ARGS_APPLICATION] = longAppParam.data();
    EXPECT_EQ(PROFILING_FAILED, parser.CheckAppValid(cmdInfo));
}

TEST_F(INPUT_PARSER_UTEST, CheckEnvironmentValid) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    struct MsprofCmdInfo cmdInfo = {{nullptr}};

    EXPECT_EQ(PROFILING_FAILED, parser.CheckEnvironmentValid(cmdInfo));
    cmdInfo.args[ARGS_ENVIRONMENT] = "";

    EXPECT_EQ(PROFILING_FAILED, parser.CheckEnvironmentValid(cmdInfo));
    cmdInfo.args[ARGS_ENVIRONMENT] = "aa";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckEnvironmentValid(cmdInfo));
}

TEST_F(INPUT_PARSER_UTEST, CheckPythonPathValid) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    struct MsprofCmdInfo cmdInfo = {{nullptr}};

    EXPECT_EQ(PROFILING_FAILED, parser.CheckPythonPathValid(cmdInfo));
    cmdInfo.args[ARGS_PYTHON_PATH] = "";

    EXPECT_EQ(PROFILING_FAILED, parser.CheckPythonPathValid(cmdInfo));

    parser.params_->pythonPath.clear();
    std::string tests = std::string(1025, 'c');
    std::vector<char> testPath(tests.begin(), tests.end());
    testPath.emplace_back('\0');
    cmdInfo.args[ARGS_PYTHON_PATH] = testPath.data();
    EXPECT_EQ(PROFILING_FAILED, parser.CheckPythonPathValid(cmdInfo));

    cmdInfo.args[ARGS_PYTHON_PATH] = "@";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckPythonPathValid(cmdInfo));

    cmdInfo.args[ARGS_PYTHON_PATH] = "testpython";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckPythonPathValid(cmdInfo));

    Utils::CreateDir("TestPython");
    cmdInfo.args[ARGS_PYTHON_PATH] = "TestPython";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckPythonPathValid(cmdInfo));
    Utils::RemoveDir("TestPython");
    cmdInfo.args[ARGS_PYTHON_PATH] = "/usr/bin/python3";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckPythonPathValid(cmdInfo));
}

TEST_F(INPUT_PARSER_UTEST, ParamsCheck) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    auto pp = parser.params_;
    parser.params_.reset();
    EXPECT_EQ(PROFILING_FAILED, parser.ParamsCheck());
    parser.params_ = pp;

    parser.params_->app_dir = "./test";
    parser.params_->result_dir = "./profiling_data";
    EXPECT_EQ(PROFILING_SUCCESS, parser.ParamsCheck());

    parser.params_->result_dir = "";
    EXPECT_EQ(PROFILING_SUCCESS, parser.ParamsCheck());
    EXPECT_EQ(parser.params_->app_dir, parser.params_->result_dir);

    parser.params_->app_dir = "";
    parser.params_->application.emplace_back("python3");
    parser.params_->result_dir = "";
    EXPECT_EQ(PROFILING_SUCCESS, parser.ParamsCheck());

    parser.params_->application.clear();
    parser.params_->result_dir = "";
    const std::string workPath = "/tmp/msprof_work_path";
    setenv("ASCEND_WORK_PATH", workPath.c_str(), 1);
    EXPECT_EQ(PROFILING_SUCCESS, parser.ParamsCheck());
    EXPECT_EQ(analysis::dvvp::common::utils::Utils::CanonicalizePath(workPath + "/profiling_data"),
        parser.params_->result_dir);
    unsetenv("ASCEND_WORK_PATH");
    Utils::RemoveDir(workPath);
}

TEST_F(INPUT_PARSER_UTEST, WorkPathEnv) {
    std::string resultDir("/tmp/test/profiling");
    setenv("ASCEND_WORK_PATH", resultDir.c_str(), 1);
    const char *argv[] = {"msprof", "--aicpu=on", "python3", "test.py", nullptr};
    optind = 1;
    InputParser parser = InputParser();
    auto params = parser.MsprofGetOpts(MSPROF_APP_ARGC, argv);
    EXPECT_EQ(true, params->result_dir == (resultDir + "/profiling_data"));
    unsetenv("ASCEND_WORK_PATH");
}

TEST_F(INPUT_PARSER_UTEST, OutputPriorityOverWorkPathEnv) {
    const char *oldWorkPathEnv = getenv("ASCEND_WORK_PATH");
    const bool hasOldWorkPathEnv = (oldWorkPathEnv != nullptr);
    const std::string oldWorkPathEnvValue = hasOldWorkPathEnv ? oldWorkPathEnv : "";

    const std::string workPathEnv = "/tmp/msprof_output_priority_work";
    const std::string outputPath = "/tmp/msprof_output_priority_output";
    const std::string outputArg = "--output=" + outputPath;
    setenv("ASCEND_WORK_PATH", workPathEnv.c_str(), 1);

    const char *argv[] = {"msprof", outputArg.c_str(), "--aicpu=on", "python3", "test.py", nullptr};
    optind = 1;
    InputParser parser = InputParser();
    auto params = parser.MsprofGetOpts(5, argv);

    EXPECT_NE(nullptr, params);
    if (params != nullptr) {
        std::string expectedOutput = analysis::dvvp::common::utils::Utils::CanonicalizePath(outputPath);
        EXPECT_EQ(expectedOutput, params->result_dir);
        EXPECT_NE(workPathEnv + "/profiling_data", params->result_dir);
    }

    if (hasOldWorkPathEnv) {
        setenv("ASCEND_WORK_PATH", oldWorkPathEnvValue.c_str(), 1);
    } else {
        unsetenv("ASCEND_WORK_PATH");
    }
    Utils::RemoveDir(outputPath);
}

TEST_F(INPUT_PARSER_UTEST, DefaultOutput) {
    const char *argv[] = {"msprof", "--aicpu=on", "python3", "test.py", nullptr};
    optind = 1;
    InputParser parser = InputParser();
    auto params = parser.MsprofGetOpts(MSPROF_APP_ARGC, argv);
    std::string result = analysis::dvvp::common::utils::Utils::CanonicalizePath("./");
    EXPECT_EQ(true, params->result_dir == result);
}

TEST_F(INPUT_PARSER_UTEST, NtsMetricsDefaultIsEmpty) {
    const char *argv[] = {"msprof", "--aicpu=on", "python3", "test.py", nullptr};
    optind = 1;
    InputParser parser = InputParser();
    auto params = parser.MsprofGetOpts(MSPROF_APP_ARGC, argv);
    ASSERT_NE(nullptr, params);
    EXPECT_TRUE(params->ntsMetrics.empty());
}

TEST_F(INPUT_PARSER_UTEST, SysCpuFreqIsParsedFromCommandLine) {
    const char *argv[] = {"msprof", "--sys-cpu-freq=10", "python3", "test.py", nullptr};
    optind = 1;
    InputParser parser = InputParser();
    auto params = parser.MsprofGetOpts(MSPROF_APP_ARGC, argv);
    ASSERT_NE(nullptr, params);
    EXPECT_EQ(CPU_SAMPLING_INTERVAL_FOR_FREQ_TEN, params->cpu_sampling_interval);
}

TEST_F(INPUT_PARSER_UTEST, MsprofGetOptsRejectsPidSeparatedBySpace) {
    SetPlatformTypeForTest(PlatformType::CHIP_CLOUD_V3);
    const char *argv[] = {"msprof", "--pid", "5", "--sys-devices=0", "--output=./", "--ai-core=on", nullptr};
    optind = 1;
    InputParser parser = InputParser();
    EXPECT_EQ(nullptr, parser.MsprofGetOpts(6, argv));
}

TEST_F(INPUT_PARSER_UTEST, NtsMetricsPipeUtilization) {
    SetPlatformTypeForTest(TARGET_CHIP_TYPE);
    const char *argv[] = {"msprof", "--nts-metrics=PipeUtilization", "python3", "test.py", nullptr};
    optind = 1;
    InputParser parser = InputParser();
    auto params = parser.MsprofGetOpts(MSPROF_APP_ARGC, argv);
    ASSERT_NE(nullptr, params);
    EXPECT_EQ("PipeUtilization", params->ntsMetrics);
}

TEST_F(INPUT_PARSER_UTEST, NtsMetricsCustomPassThrough) {
    SetPlatformTypeForTest(TARGET_CHIP_TYPE);
    const char *argv[] = {"msprof", "--nts-metrics=Custom:0x301,0x312,789", "python3", "test.py", nullptr};
    optind = 1;
    InputParser parser = InputParser();
    auto params = parser.MsprofGetOpts(MSPROF_APP_ARGC, argv);
    ASSERT_NE(nullptr, params);
    EXPECT_EQ("Custom:0x301,0x312,789", params->ntsMetrics);
    EXPECT_EQ("0x301,0x312,0x315", params->ntsPmuEvents);
    std::string serializedParams = params->ToString();
    EXPECT_NE(std::string::npos, serializedParams.find("\"ntsPmuEvents\":\"0x301,0x312,0x315\""));
    EXPECT_EQ(std::string::npos, serializedParams.find("ntsPmuProfilingEvents"));
}

TEST_F(INPUT_PARSER_UTEST, NtsMetricsCustomDecimalPassThrough) {
    SetPlatformTypeForTest(TARGET_CHIP_TYPE);
    const char *argv[] = {"msprof", "--nts-metrics=Custom:769,786,789", "python3", "test.py", nullptr};
    optind = 1;
    InputParser parser = InputParser();
    auto params = parser.MsprofGetOpts(MSPROF_APP_ARGC, argv);
    ASSERT_NE(nullptr, params);
    EXPECT_EQ("Custom:769,786,789", params->ntsMetrics);
    EXPECT_EQ("0x301,0x312,0x315", params->ntsPmuEvents);
}

TEST_F(INPUT_PARSER_UTEST, NtsMetricsCustomTenEvents) {
    SetPlatformTypeForTest(TARGET_CHIP_TYPE);
    const char *argv[] = {"msprof", "--nts-metrics=Custom:1,2,3,4,5,6,7,8,9,10", "python3", "test.py", nullptr};
    optind = 1;
    InputParser parser = InputParser();
    auto params = parser.MsprofGetOpts(MSPROF_APP_ARGC, argv);
    ASSERT_NE(nullptr, params);
    EXPECT_EQ("0x1,0x2,0x3,0x4,0x5,0x6,0x7,0x8,0x9,0xa", params->ntsPmuEvents);
}

TEST_F(INPUT_PARSER_UTEST, NtsMetricsCustomAllowsMaxEvent) {
    SetPlatformTypeForTest(TARGET_CHIP_TYPE);
    const char *argv[] = {"msprof", "--nts-metrics=Custom:0,0x71b,1819", "python3", "test.py", nullptr};
    optind = 1;
    InputParser parser = InputParser();
    auto params = parser.MsprofGetOpts(MSPROF_APP_ARGC, argv);
    ASSERT_NE(nullptr, params);
    EXPECT_EQ("0x0,0x71b,0x71b", params->ntsPmuEvents);
}

TEST_F(INPUT_PARSER_UTEST, NtsMetricsRejectInvalidValues) {
    SetPlatformTypeForTest(TARGET_CHIP_TYPE);
    const char *invalidNameArgv[] = {"msprof", "--nts-metrics=TaskTime", "python3", "test.py", nullptr};
    optind = 1;
    InputParser invalidNameParser = InputParser();
    EXPECT_EQ(nullptr, invalidNameParser.MsprofGetOpts(MSPROF_APP_ARGC, invalidNameArgv));

    const char *emptyArgv[] = {"msprof", "--nts-metrics=", "python3", "test.py", nullptr};
    optind = 1;
    InputParser emptyParser = InputParser();
    EXPECT_EQ(nullptr, emptyParser.MsprofGetOpts(MSPROF_APP_ARGC, emptyArgv));

    const char *emptyCustomArgv[] = {"msprof", "--nts-metrics=Custom:", "python3", "test.py", nullptr};
    optind = 1;
    InputParser emptyCustomParser = InputParser();
    EXPECT_EQ(nullptr, emptyCustomParser.MsprofGetOpts(MSPROF_APP_ARGC, emptyCustomArgv));

    const char *tooManyEventsArgv[] = {
        "msprof", "--nts-metrics=Custom:1,2,3,4,5,6,7,8,9,10,11", "python3", "test.py", nullptr};
    optind = 1;
    InputParser tooManyEventsParser = InputParser();
    EXPECT_EQ(nullptr, tooManyEventsParser.MsprofGetOpts(MSPROF_APP_ARGC, tooManyEventsArgv));

    const char *invalidEventArgv[] = {"msprof", "--nts-metrics=Custom:0x301,abc", "python3", "test.py", nullptr};
    optind = 1;
    InputParser invalidEventParser = InputParser();
    EXPECT_EQ(nullptr, invalidEventParser.MsprofGetOpts(MSPROF_APP_ARGC, invalidEventArgv));

    const char *maxOverflowArgv[] = {"msprof", "--nts-metrics=Custom:0x71c", "python3", "test.py", nullptr};
    optind = 1;
    InputParser maxOverflowParser = InputParser();
    EXPECT_EQ(nullptr, maxOverflowParser.MsprofGetOpts(MSPROF_APP_ARGC, maxOverflowArgv));

    const char *largeEventArgv[] = {"msprof", "--nts-metrics=Custom:0x80000000", "python3", "test.py", nullptr};
    optind = 1;
    InputParser largeEventParser = InputParser();
    EXPECT_EQ(nullptr, largeEventParser.MsprofGetOpts(MSPROF_APP_ARGC, largeEventArgv));
}

TEST_F(INPUT_PARSER_UTEST, NtsMetricsOnlyAvailableOnTargetChip) {
    const char *argv[] = {"msprof", "--nts-metrics=PipeUtilization", "python3", "test.py", nullptr};
    SetPlatformTypeForTest(PlatformType::CLOUD_TYPE);
    optind = 1;
    InputParser parser = InputParser();
    EXPECT_EQ(nullptr, parser.MsprofGetOpts(MSPROF_APP_ARGC, argv));
}

TEST_F(INPUT_PARSER_UTEST, NtsEventsAllowsTargetChip) {
    SetPlatformTypeForTest(TARGET_CHIP_TYPE);
    Platform::instance()->Uninit();
    std::string ntsEvents;

    testing::internal::CaptureStdout();
    testing::internal::CaptureStderr();
    EXPECT_EQ(PROFILING_FAILED, Platform::instance()->GetNtsEvents("PipeUtilization", ntsEvents));
    const std::string outOutput = testing::internal::GetCapturedStdout();
    const std::string errOutput = testing::internal::GetCapturedStderr();
    const std::string logOutput = outOutput + errOutput;

    EXPECT_EQ(std::string::npos, logOutput.find("not supported on current platform"));
}

TEST_F(INPUT_PARSER_UTEST, PrintHelpShowsNtsMetricsOnTargetChip) {
    SetPlatformTypeForTest(TARGET_CHIP_TYPE);
    RefreshArgsManagerForTest();
    std::ostringstream helpOutput;
    auto *oldBuffer = std::cout.rdbuf(helpOutput.rdbuf());
    ArgsManager::instance()->PrintHelp();
    std::cout.rdbuf(oldBuffer);

    const std::string help = helpOutput.str();
    EXPECT_NE(std::string::npos, help.find("--nts-metrics"));
    EXPECT_NE(std::string::npos, help.find("PipeUtilization"));
    EXPECT_NE(std::string::npos, help.find("Custom:<event-list>"));
    EXPECT_NE(std::string::npos, help.find("[0x0, 0x71b]"));
}

TEST_F(INPUT_PARSER_UTEST, PrintHelpHidesNtsMetricsOnOtherPlatform) {
    SetPlatformTypeForTest(PlatformType::CLOUD_TYPE);
    RefreshArgsManagerForTest();
    std::ostringstream helpOutput;
    auto *oldBuffer = std::cout.rdbuf(helpOutput.rdbuf());
    ArgsManager::instance()->PrintHelp();
    std::cout.rdbuf(oldBuffer);

    EXPECT_EQ(std::string::npos, helpOutput.str().find("--nts-metrics"));
}

TEST_F(INPUT_PARSER_UTEST, SetHostSysParam) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    parser.SetHostSysParam("123");
    parser.SetHostSysParam("osrt");
    EXPECT_EQ(parser.params_->host_osrt_profiling, "on");
}

TEST_F(INPUT_PARSER_UTEST, CheckHostSysValid) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    struct MsprofCmdInfo cmdInfo = {{nullptr}};
    cmdInfo.args[ARGS_HOST_SYS] = "invalid";
    parser.params_->result_dir = "./input_parser_utest";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckHostSysValid(cmdInfo));
    cmdInfo.args[ARGS_HOST_SYS] = "cpu,mem";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckHostSysValid(cmdInfo));
}

TEST_F(INPUT_PARSER_UTEST, CheckHostSysUsageValid) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    struct MsprofCmdInfo cmdInfo = {{nullptr}};
    cmdInfo.args[ARGS_HOST_SYS_USAGE] = "disk";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckHostSysUsageValid(cmdInfo));
    cmdInfo.args[ARGS_HOST_SYS_USAGE] = "cpu,mem";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckHostSysUsageValid(cmdInfo));
}

TEST_F(INPUT_PARSER_UTEST, CheckBaseOrder) {
    EXPECT_EQ(ARGS_INSTR_PROFILING, LONG_OPTIONS[ARGS_INSTR_PROFILING].val);
    EXPECT_EQ(ARGS_INSTR_PROFILING_FREQ, LONG_OPTIONS[ARGS_INSTR_PROFILING_FREQ].val);

    GlobalMockObject::verify();
    InputParser parser = InputParser();
    struct MsprofCmdInfo cmdInfo = { {nullptr} };
    auto configManger = Analysis::Dvvp::Common::Config::ConfigManager::instance();

    configManger->configMap_["type"] = "1";
    configManger->isInit_ = true;
    Platform::instance()->Uninit();
    Platform::instance()->Init();

    {
        ArgsManager argsManager = ArgsManager();
        argsManager.argsList_.clear();
        argsManager.AddDvvpArgs();
        EXPECT_EQ(static_cast<size_t>(2), argsManager.argsList_.size());
    }

    cmdInfo.args[ARGS_DVPP_FREQ] = "50";
    EXPECT_EQ(PROFILING_SUCCESS, parser.MsprofFreqCheckValid(cmdInfo, ARGS_DVPP_FREQ));
    cmdInfo.args[ARGS_DVPP_FREQ] = "0"; // 超出 1~100 范围
    EXPECT_EQ(PROFILING_FAILED, parser.MsprofFreqCheckValid(cmdInfo, ARGS_DVPP_FREQ));
    cmdInfo.args[ARGS_DVPP_FREQ] = "101"; // 超出 1~100 范围
    EXPECT_EQ(PROFILING_FAILED, parser.MsprofFreqCheckValid(cmdInfo, ARGS_DVPP_FREQ));

    // 平台支持 DVPP 时, dvpp-profiling 按 on/off 校验取值
    cmdInfo.args[ARGS_DVPP_PROFILING] = "on";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckArgOnOff(cmdInfo, ARGS_DVPP_PROFILING));
    cmdInfo.args[ARGS_DVPP_PROFILING] = "off";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckArgOnOff(cmdInfo, ARGS_DVPP_PROFILING));
    cmdInfo.args[ARGS_DVPP_PROFILING] = "invalid"; // 非法取值
    EXPECT_EQ(PROFILING_FAILED, parser.CheckArgOnOff(cmdInfo, ARGS_DVPP_PROFILING));
    cmdInfo.args[ARGS_DVPP_PROFILING] = nullptr; // 缺省值
    EXPECT_EQ(PROFILING_FAILED, parser.CheckArgOnOff(cmdInfo, ARGS_DVPP_PROFILING));

    MOCKER_CPP(static_cast<bool (Platform::*)(const ::Dvvp::Collect::Platform::PlatformFeature) const>(
                   &Platform::CheckIfSupport))
        .stubs()
        .will(returnValue(false));

    {
        ArgsManager argsManager = ArgsManager();
        argsManager.argsList_.clear();
        argsManager.AddDvvpArgs();
        EXPECT_EQ(static_cast<size_t>(0), argsManager.argsList_.size());
    }

    cmdInfo.args[ARGS_DVPP_FREQ] = "101";
    EXPECT_EQ(PROFILING_SUCCESS, parser.MsprofFreqCheckValid(cmdInfo, ARGS_DVPP_FREQ));

    // 平台不支持 DVPP 时, dvpp-profiling 跳过校验直接放行(返回成功并告警)
    cmdInfo.args[ARGS_DVPP_PROFILING] = "on";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckArgOnOff(cmdInfo, ARGS_DVPP_PROFILING));

    GlobalMockObject::verify();
    Platform::instance()->Uninit();
    configManger->Uninit();
}

TEST_F(INPUT_PARSER_UTEST, CheckBaseInfo) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();

    struct MsprofCmdInfo cmdInfo = { {nullptr} };
    auto configManger = Analysis::Dvvp::Common::Config::ConfigManager::instance();
    Platform::instance()->Init();

    EXPECT_EQ(PROFILING_FAILED, parser.CheckSampleModeValid(cmdInfo, ARGS_AIV_MODE));
    EXPECT_EQ(PROFILING_FAILED, parser.CheckSampleModeValid(cmdInfo, ARGS_AIC_MODE));
    cmdInfo.args[ARGS_AIV_MODE] = "aa";
    cmdInfo.args[ARGS_AIC_MODE] = "aa";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckSampleModeValid(cmdInfo, ARGS_AIV_MODE));
    EXPECT_EQ(PROFILING_FAILED, parser.CheckSampleModeValid(cmdInfo, ARGS_AIC_MODE));
    cmdInfo.args[ARGS_AIV_MODE] = "sample-based";
    cmdInfo.args[ARGS_AIC_MODE] = "sample-based";
    configManger->configMap_["type"] = "5";
    configManger->isInit_ = true;
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckSampleModeValid(cmdInfo, ARGS_AIV_MODE));
    configManger->Uninit();
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckSampleModeValid(cmdInfo, ARGS_AIC_MODE));

    // check aic metrics valid
    EXPECT_EQ(PROFILING_FAILED, parser.CheckAiCoreMetricsValid(cmdInfo, ARGS_AIC_METRICS));
    EXPECT_EQ(PROFILING_FAILED, parser.CheckAiCoreMetricsValid(cmdInfo, ARGS_AIV_METRICS));

    cmdInfo.args[ARGS_AIC_METRICS] = "";
    cmdInfo.args[ARGS_AIV_METRICS] = "";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckAiCoreMetricsValid(cmdInfo, ARGS_AIC_METRICS));
    EXPECT_EQ(PROFILING_FAILED, parser.CheckAiCoreMetricsValid(cmdInfo, ARGS_AIV_METRICS));

    // 固定为已链接的真实平台(type 5), 使 PmuToFeature 的 metric->feature 映射可用;
    // 通过 mock CheckIfSupport 控制平台是否支持对应 feature, 不依赖未链接的平台类
    configManger->configMap_["type"] = "5";
    configManger->isInit_ = true;
    Platform::instance()->Uninit();
    Platform::instance()->Init();

    cmdInfo.args[ARGS_AIC_METRICS] = "1";
    cmdInfo.args[ARGS_AIV_METRICS] = "1";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckAiCoreMetricsValid(cmdInfo, ARGS_AIC_METRICS));
    EXPECT_EQ(PROFILING_FAILED, parser.CheckAiCoreMetricsValid(cmdInfo, ARGS_AIV_METRICS));

    // 平台支持 Memory(MEMORY_PMU): mock CheckIfSupport 对该 feature 返回 true
    GlobalMockObject::verify();
    MOCKER_CPP(static_cast<bool (Platform::*)(const PlatformFeature) const>(&Platform::CheckIfSupport))
        .stubs()
        .with(eq(PLATFORM_TASK_MEMORY_PMU))
        .will(returnValue(true));
    MOCKER_CPP(static_cast<bool (Platform::*)(const PlatformFeature) const>(&Platform::CheckIfSupport))
        .defaults()
        .will(returnValue(false));
    cmdInfo.args[ARGS_AIC_METRICS] = "Memory";
    cmdInfo.args[ARGS_AIV_METRICS] = "Memory";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckAiCoreMetricsValid(cmdInfo, ARGS_AIC_METRICS));
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckAiCoreMetricsValid(cmdInfo, ARGS_AIV_METRICS));

    // 平台不支持 L2Cache(L2_CACHE_PMU): 默认 mock 返回 false
    GlobalMockObject::verify();
    MOCKER_CPP(static_cast<bool (Platform::*)(const PlatformFeature) const>(&Platform::CheckIfSupport))
        .defaults()
        .will(returnValue(false));
    cmdInfo.args[ARGS_AIV_METRICS] = "L2Cache";
    cmdInfo.args[ARGS_AIC_METRICS] = "L2Cache";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckAiCoreMetricsValid(cmdInfo, ARGS_AIC_METRICS));
    EXPECT_EQ(PROFILING_FAILED, parser.CheckAiCoreMetricsValid(cmdInfo, ARGS_AIV_METRICS));

    // 平台支持 optype(PLATFORM_TASK_SCALE): CheckCmdOpTypeIsValid 校验取值格式
    GlobalMockObject::verify();
    MOCKER_CPP(static_cast<bool (Platform::*)(const PlatformFeature) const>(&Platform::CheckIfSupport))
        .stubs()
        .with(eq(PLATFORM_TASK_SCALE))
        .will(returnValue(true));
    MOCKER_CPP(static_cast<bool (Platform::*)(const PlatformFeature) const>(&Platform::CheckIfSupport))
        .defaults()
        .will(returnValue(false));
    parser.params_->opType.clear();
    cmdInfo.args[ARGS_OP_TYPE] = "Index,Index";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckCmdOpTypeIsValid(cmdInfo));
    EXPECT_EQ("Index", parser.params_->opType);
    parser.params_->opType.clear();
    cmdInfo.args[ARGS_OP_TYPE] = ",";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckCmdOpTypeIsValid(cmdInfo));
    parser.params_->opType.clear();
    cmdInfo.args[ARGS_OP_TYPE] = "Index,,MatMul";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckCmdOpTypeIsValid(cmdInfo));
    parser.params_->opType.clear();
    std::string opType(257, 't');
    cmdInfo.args[ARGS_OP_TYPE] = const_cast<char *>(opType.c_str());
    EXPECT_EQ(PROFILING_FAILED, parser.CheckCmdOpTypeIsValid(cmdInfo));
    parser.params_->opType.clear();
    cmdInfo.args[ARGS_OP_TYPE] = "Index,MatMul";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckCmdOpTypeIsValid(cmdInfo));
    parser.params_->opType.clear();
    cmdInfo.args[ARGS_OP_TYPE] = "Index";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckCmdOpTypeIsValid(cmdInfo));

    // 平台支持 PEU_PMU 但不支持 SCALE: metrics 校验通过, optype 校验失败
    GlobalMockObject::verify();
    MOCKER_CPP(static_cast<bool (Platform::*)(const PlatformFeature) const>(&Platform::CheckIfSupport))
        .stubs()
        .with(eq(PLATFORM_TASK_PEU_PMU))
        .will(returnValue(true));
    MOCKER_CPP(static_cast<bool (Platform::*)(const PlatformFeature) const>(&Platform::CheckIfSupport))
        .defaults()
        .will(returnValue(false));
    cmdInfo.args[ARGS_AIC_METRICS] = "PipelineExecuteUtilization";
    cmdInfo.args[ARGS_AIV_METRICS] = "PipelineExecuteUtilization";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckAiCoreMetricsValid(cmdInfo, ARGS_AIV_METRICS));
    EXPECT_EQ(PROFILING_FAILED, parser.CheckCmdOpTypeIsValid(cmdInfo));

    GlobalMockObject::verify();
    configManger->Uninit();
    Platform::instance()->Uninit();

    // check summary format
    EXPECT_EQ(PROFILING_FAILED, parser.CheckExportSummaryFormat(cmdInfo));
    cmdInfo.args[ARGS_SUMMARY_FORMAT] = "aaa";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckExportSummaryFormat(cmdInfo));
    cmdInfo.args[ARGS_SUMMARY_FORMAT] = "csv";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckExportSummaryFormat(cmdInfo));
    cmdInfo.args[ARGS_SUMMARY_FORMAT] = "json";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckExportSummaryFormat(cmdInfo));

    // check llc
    EXPECT_EQ(PROFILING_FAILED, parser.CheckLlcProfilingValid(cmdInfo));
    cmdInfo.args[ARGS_LLC_PROFILING] = "";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckLlcProfilingValid(cmdInfo));
    cmdInfo.args[ARGS_LLC_PROFILING] = "read";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckLlcProfilingValid(cmdInfo));
    cmdInfo.args[ARGS_LLC_PROFILING] = "capacity";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckLlcProfilingValid(cmdInfo));

    // check period
    EXPECT_EQ(PROFILING_FAILED, parser.CheckSysPeriodValid(cmdInfo));
    cmdInfo.args[ARGS_SYS_PERIOD] = "capacity";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckSysPeriodValid(cmdInfo));
    cmdInfo.args[ARGS_SYS_PERIOD] = "-1";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckSysPeriodValid(cmdInfo));
    cmdInfo.args[ARGS_SYS_PERIOD] = "2";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckSysPeriodValid(cmdInfo));

    // check devices
    EXPECT_EQ(PROFILING_FAILED, parser.CheckSysDevicesValid(cmdInfo));
    cmdInfo.args[ARGS_SYS_DEVICES] = "";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckSysDevicesValid(cmdInfo));
    cmdInfo.args[ARGS_SYS_DEVICES] = "all";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckSysDevicesValid(cmdInfo));
    cmdInfo.args[ARGS_SYS_DEVICES] = "A";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckSysDevicesValid(cmdInfo));

    // check arg on off
    EXPECT_EQ(PROFILING_FAILED, parser.CheckArgOnOff(cmdInfo, ARGS_ASCENDCL));
    cmdInfo.args[ARGS_TASK_TIME] = "tas";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckArgOnOff(cmdInfo, ARGS_TASK_TIME));
    cmdInfo.args[ARGS_TASK_TIME] = "off";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckArgOnOff(cmdInfo, ARGS_TASK_TIME));
    cmdInfo.args[ARGS_TASK_TIME] = "L1";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckArgOnOff(cmdInfo, ARGS_TASK_TIME));
    cmdInfo.args[ARGS_TASK_TIME] = "l1";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckArgOnOff(cmdInfo, ARGS_TASK_TIME));
    cmdInfo.args[ARGS_GE_API] = "fwk";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckArgOnOff(cmdInfo, ARGS_GE_API));
    cmdInfo.args[ARGS_GE_API] = "off";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckArgOnOff(cmdInfo, ARGS_GE_API));
    cmdInfo.args[ARGS_GE_API] = "L1";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckArgOnOff(cmdInfo, ARGS_GE_API));
    cmdInfo.args[ARGS_GE_API] = "l1";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckArgOnOff(cmdInfo, ARGS_GE_API));
    cmdInfo.args[ARGS_ASCENDCL] = "A";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckArgOnOff(cmdInfo, ARGS_ASCENDCL));
    cmdInfo.args[ARGS_DVPP_PROFILING] = "on";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckArgOnOff(cmdInfo, ARGS_DVPP_PROFILING));

    // check arg range
    EXPECT_EQ(PROFILING_FAILED, parser.CheckArgRange(cmdInfo,ARGS_INTERCONNECTION_PROFILING, 1, 100));

    cmdInfo.args[ARGS_INTERCONNECTION_PROFILING] = "A";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckArgRange(cmdInfo,ARGS_INTERCONNECTION_PROFILING, 1, 100));
    cmdInfo.args[ARGS_INTERCONNECTION_PROFILING] = "111";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckArgRange(cmdInfo,ARGS_INTERCONNECTION_PROFILING, 1, 100));
    cmdInfo.args[ARGS_INTERCONNECTION_PROFILING] = "1";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckArgRange(cmdInfo,ARGS_INTERCONNECTION_PROFILING, 1, 100));

    // check args is number
    EXPECT_EQ(PROFILING_FAILED, parser.CheckArgsIsNumber(cmdInfo, ARGS_EXPORT_ITERATION_ID));
    cmdInfo.args[ARGS_EXPORT_ITERATION_ID] = "a";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckArgsIsNumber(cmdInfo, ARGS_EXPORT_ITERATION_ID));
    cmdInfo.args[ARGS_EXPORT_ITERATION_ID] = "1";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckArgsIsNumber(cmdInfo, ARGS_EXPORT_ITERATION_ID));

    // check analyze rule valid range
    cmdInfo.args[ARGS_RULE] = nullptr;
    EXPECT_EQ(PROFILING_FAILED, parser.CheckAnalyzeRuleSwitch(cmdInfo));
    cmdInfo.args[ARGS_RULE] = "on";
    EXPECT_EQ(PROFILING_FAILED, parser.CheckAnalyzeRuleSwitch(cmdInfo));
    cmdInfo.args[ARGS_RULE] = "communication";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckAnalyzeRuleSwitch(cmdInfo));
    cmdInfo.args[ARGS_RULE] = "communication,communication_matrix";
    EXPECT_EQ(PROFILING_SUCCESS, parser.CheckAnalyzeRuleSwitch(cmdInfo));

    // params switch valid
    cmdInfo.args[ARGS_IO_PROFILING] = "1";
    cmdInfo.args[ARGS_MODEL_EXECUTION] = "1";
    cmdInfo.args[ARGS_RUNTIME_API] = "1";
    cmdInfo.args[ARGS_AI_CORE] = "1";
    cmdInfo.args[ARGS_AIV] = "1";
    cmdInfo.args[ARGS_CPU_PROFILING] = "1";
    cmdInfo.args[ARGS_SYS_PROFILING] = "1";
    cmdInfo.args[ARGS_PID_PROFILING] = "1";
    cmdInfo.args[ARGS_HARDWARE_MEM] = "1";
    cmdInfo.args[ARGS_INTERCONNECTION_PROFILING] = "1";
    cmdInfo.args[ARGS_DVPP_PROFILING] = "1";
    cmdInfo.args[ARGS_L2_PROFILING] = "1";
    cmdInfo.args[ARGS_AICPU] = "1";
    cmdInfo.args[ARGS_TASK_BLOCK] = "1";
    cmdInfo.args[ARGS_SYS_LOW_POWER] = "1";
    cmdInfo.args[ARGS_DVPP_FREQ] = "1";
    cmdInfo.args[ARGS_IO_SAMPLING_FREQ] = "1";
    cmdInfo.args[ARGS_PID_SAMPLING_FREQ] = "1";
    cmdInfo.args[ARGS_SYS_SAMPLING_FREQ] = "1";
    cmdInfo.args[ARGS_CPU_SAMPLING_FREQ] = "1";
    cmdInfo.args[ARGS_HCCL] = "1";
    cmdInfo.args[ARGS_INSTR_PROFILING] = "1";
    cmdInfo.args[ARGS_PARSE] = "1";
    cmdInfo.args[ARGS_QUERY] = "1";
    cmdInfo.args[ARGS_EXPORT] = "1";
    cmdInfo.args[ARGS_ANALYZE] = "1";
    cmdInfo.args[ARGS_CLEAR] = "1";
    cmdInfo.args[ARGS_TASK_MEMORY] = "on";
    parser.ParamsSwitchValid(cmdInfo, ARGS_TASK_MEMORY);
    parser.ParamsSwitchValid(cmdInfo, ARGS_IO_PROFILING);
    parser.ParamsSwitchValid(cmdInfo, ARGS_MODEL_EXECUTION);
    parser.ParamsSwitchValid(cmdInfo, ARGS_RUNTIME_API);
    parser.ParamsSwitchValid(cmdInfo, ARGS_AI_CORE);
    parser.ParamsSwitchValid(cmdInfo, ARGS_AIV);
    parser.ParamsSwitchValid(cmdInfo, ARGS_CPU_PROFILING);
    parser.ParamsSwitchValid(cmdInfo, ARGS_SYS_PROFILING);
    parser.ParamsSwitchValid(cmdInfo, ARGS_PID_PROFILING);
    parser.ParamsSwitchValid(cmdInfo, ARGS_HARDWARE_MEM);
    parser.ParamsSwitchValid(cmdInfo, ARGS_HCCL);
    parser.ParamsSwitchValid(cmdInfo, ARGS_INSTR_PROFILING);
    parser.ParamsSwitchValid(cmdInfo, 111);
    parser.ParamsSwitchValid2(cmdInfo, 111);
    parser.ParamsSwitchValid2(cmdInfo, ARGS_INTERCONNECTION_PROFILING);
    parser.ParamsSwitchValid2(cmdInfo, ARGS_DVPP_PROFILING);
    parser.ParamsSwitchValid2(cmdInfo, ARGS_L2_PROFILING);
    parser.ParamsSwitchValid2(cmdInfo, ARGS_AICPU);
    parser.ParamsSwitchValid2(cmdInfo, ARGS_TASK_BLOCK);
    parser.ParamsSwitchValid2(cmdInfo, ARGS_SYS_LOW_POWER);
    parser.ParamsSwitchValid2(cmdInfo, ARGS_PARSE);
    parser.ParamsSwitchValid2(cmdInfo, ARGS_QUERY);
    parser.ParamsSwitchValid2(cmdInfo, ARGS_EXPORT);
    parser.ParamsSwitchValid2(cmdInfo, ARGS_ANALYZE);
    parser.ParamsSwitchValid2(cmdInfo, ARGS_CLEAR);
}

TEST_F(INPUT_PARSER_UTEST, PreCheckPlatform) {
    InputParser parser = InputParser();
    const char *argv[] = {"aiv-me"};
    ConfigManager::instance()->configMap_["type"] =
        std::to_string(static_cast<int32_t>(Analysis::Dvvp::Common::Config::PlatformType::END_TYPE));
    EXPECT_EQ(PROFILING_FAILED, parser.PreCheckPlatform(ARGS_AIV, argv));

    ConfigManager::instance()->configMap_["type"] =
        std::to_string(static_cast<int32_t>(Analysis::Dvvp::Common::Config::PlatformType::CLOUD_TYPE));
    Platform::instance()->runSide_ = SysPlatformType::HOST;
    EXPECT_EQ(PROFILING_SUCCESS, parser.PreCheckPlatform(ARGS_DYNAMIC_PROF, argv));
    Platform::instance()->runSide_ = SysPlatformType::INVALID;
}

TEST_F(INPUT_PARSER_UTEST, MsprofCmdCheckValid) {
    InputParser parser = InputParser();
    struct MsprofCmdInfo cmdInfo = {{nullptr}};
    cmdInfo.args[ARGS_AIV_MODE] = "sample-baseddddd";
    cmdInfo.args[ARGS_AIC_METRICS] = "PipeUtilization";
    cmdInfo.args[ARGS_SYS_LOW_POWER] = "bb";
    cmdInfo.args[ARGS_SUMMARY_FORMAT] = "csv";
    cmdInfo.args[ARGS_PYTHON_PATH] = "123";
    cmdInfo.args[ARGS_DYNAMIC_PROF] = "on";
    cmdInfo.args[ARGS_DYNAMIC_PROF_PID] = "123";
    cmdInfo.args[ARGS_DELAY_PROF] = "1";
    cmdInfo.args[ARGS_DURATION_PROF] = "1";
    MOCKER(mmGetOptInd).stubs().will(returnValue(1));
    parser.MsprofCmdCheckValid(cmdInfo, ARGS_AIV_MODE);
    parser.MsprofCmdCheckValid(cmdInfo, ARGS_AIC_METRICS);
    parser.MsprofCmdCheckValid(cmdInfo, ARGS_SYS_LOW_POWER);
    parser.MsprofCmdCheckValid(cmdInfo, ARGS_SUMMARY_FORMAT);
    parser.MsprofCmdCheckValid(cmdInfo, ARGS_PYTHON_PATH);
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.MsprofCmdCheckValid(cmdInfo, ARGS_DYNAMIC_PROF));
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.MsprofCmdCheckValid(cmdInfo, ARGS_DYNAMIC_PROF_PID));
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.MsprofCmdCheckValid(cmdInfo, ARGS_DELAY_PROF));
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.MsprofCmdCheckValid(cmdInfo, ARGS_DURATION_PROF));
}

TEST_F(INPUT_PARSER_UTEST, RejectMissingOptionalArgumentWithoutCoreDump) {
    InputParser parser = InputParser();
    struct MsprofCmdInfo cmdInfo = {{nullptr}};

    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.MsprofDynamicCheckValid(cmdInfo, ARGS_DYNAMIC_PROF_PID));
    EXPECT_TRUE(parser.params_->pid.empty());

    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckArgOnOff(cmdInfo, ARGS_AI_CORE));
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckSysDevicesValid(cmdInfo));
}

TEST_F(INPUT_PARSER_UTEST, MsprofSwitchCheckValid) {
    InputParser parser = InputParser();
    struct MsprofCmdInfo cmdInfo = {{nullptr}};
    ConfigManager::instance()->configMap_["type"] =
        std::to_string(static_cast<int32_t>(Analysis::Dvvp::Common::Config::PlatformType::CHIP_CLOUD_V3));
    cmdInfo.args[ARGS_TASK_BLOCK] = "aa";
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.MsprofSwitchCheckValid(cmdInfo, ARGS_TASK_BLOCK));
    cmdInfo.args[ARGS_TASK_BLOCK] = "on";
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.MsprofSwitchCheckValid(cmdInfo, ARGS_TASK_BLOCK));
    cmdInfo.args[ARGS_TASK_BLOCK] = "off";
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.MsprofSwitchCheckValid(cmdInfo, ARGS_TASK_BLOCK));
    cmdInfo.args[ARGS_TASK_BLOCK] = "all";
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.MsprofSwitchCheckValid(cmdInfo, ARGS_TASK_BLOCK));
}

TEST_F(INPUT_PARSER_UTEST, ParamsCheckTaskBlockOpTypeCrossValidation) {
    InputParser parser = InputParser();
    parser.params_->taskBlock = "on";
    parser.params_->taskBlockShink = "off";
    parser.params_->opType = "";
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.ParamsCheck());

    parser.params_->opType = "MatMul";
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.ParamsCheck());
}

TEST_F(INPUT_PARSER_UTEST, CheckTaskBlockValid) {
    InputParser parser = InputParser();

    MOCKER_CPP(&Platform::CheckIfSupport, bool (Platform::*)(const PlatformFeature) const)
        .stubs()
        .will(returnValue(true));

    MOCKER_CPP(&Analysis::Dvvp::Common::Config::ConfigManager::GetPlatformType)
        .stubs()
        .will(returnValue(Analysis::Dvvp::Common::Config::PlatformType::CHIP_CLOUD_V3))
        .then(returnValue(Analysis::Dvvp::Common::Config::PlatformType::CHIP_CLOUD_V3))
        .then(returnValue(Analysis::Dvvp::Common::Config::PlatformType::CHIP_MDC_V2))
        .then(returnValue(Analysis::Dvvp::Common::Config::PlatformType::CHIP_CLOUD_V4))
        .then(returnValue(Analysis::Dvvp::Common::Config::PlatformType::CHIP_MDC_V2))
        .then(returnValue(Analysis::Dvvp::Common::Config::PlatformType::CHIP_MDC_V2))
        .then(returnValue(Analysis::Dvvp::Common::Config::PlatformType::CHIP_MDC_V2))
        .then(returnValue(Analysis::Dvvp::Common::Config::PlatformType::MINI_TYPE))
        .then(returnValue(Analysis::Dvvp::Common::Config::PlatformType::MINI_TYPE))
        .then(returnValue(Analysis::Dvvp::Common::Config::PlatformType::MINI_TYPE));

    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckTaskBlockValid("--task-block", "all"));
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.CheckTaskBlockValid("--task-block", "on"));
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckTaskBlockValid("--task-block", "invalid_value"));
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckTaskBlockValid("--task-block", "invalid_value"));
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.CheckTaskBlockValid("--task-block", "on"));
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.CheckTaskBlockValid("--task-block", "on"));
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.CheckTaskBlockValid("--task-block", "off"));
}

TEST_F(INPUT_PARSER_UTEST, MsprofFreqCheckValid) {
    InputParser parser = InputParser();
    struct MsprofCmdInfo cmdInfo = {{nullptr}};
    EXPECT_EQ(PROFILING_FAILED, parser.MsprofFreqCheckValid(cmdInfo, INVALID_FREQ_OPTION));
    cmdInfo.args[ARGS_SYS_PERIOD] = "100";
    cmdInfo.args[ARGS_SYS_SAMPLING_FREQ] = "1";
    cmdInfo.args[ARGS_PID_SAMPLING_FREQ] = "1";
    cmdInfo.args[ARGS_CPU_SAMPLING_FREQ] = "10";
    cmdInfo.args[ARGS_INTERCONNECTION_FREQ] = "10";
    cmdInfo.args[ARGS_IO_SAMPLING_FREQ] = "60";
    cmdInfo.args[ARGS_DVPP_FREQ] = "60";
    cmdInfo.args[ARGS_HARDWARE_MEM_SAMPLING_FREQ] = "100";
    cmdInfo.args[ARGS_AIC_FREQ] = "20";
    cmdInfo.args[ARGS_AIV_FREQ] = "20";
    cmdInfo.args[ARGS_EXPORT_ITERATION_ID] = "1";
    cmdInfo.args[ARGS_EXPORT_MODEL_ID] = "1";
    cmdInfo.args[ARGS_INSTR_PROFILING_FREQ] = "1000";
    cmdInfo.args[ARGS_HOST_SYS_USAGE_FREQ] = "20";

    EXPECT_EQ(PROFILING_SUCCESS, parser.MsprofFreqCheckValid(cmdInfo, ARGS_SYS_PERIOD));
    EXPECT_EQ(PROFILING_SUCCESS, parser.MsprofFreqCheckValid(cmdInfo, ARGS_SYS_SAMPLING_FREQ));
    EXPECT_EQ(PROFILING_SUCCESS, parser.MsprofFreqCheckValid(cmdInfo, ARGS_PID_SAMPLING_FREQ));
    EXPECT_EQ(PROFILING_SUCCESS, parser.MsprofFreqCheckValid(cmdInfo, ARGS_CPU_SAMPLING_FREQ));
    EXPECT_EQ(PROFILING_SUCCESS, parser.MsprofFreqCheckValid(cmdInfo, ARGS_INTERCONNECTION_FREQ));
    EXPECT_EQ(PROFILING_SUCCESS, parser.MsprofFreqCheckValid(cmdInfo, ARGS_IO_SAMPLING_FREQ));
    EXPECT_EQ(PROFILING_SUCCESS, parser.MsprofFreqCheckValid(cmdInfo, ARGS_DVPP_FREQ));
    EXPECT_EQ(PROFILING_SUCCESS, parser.MsprofFreqCheckValid(cmdInfo, ARGS_HARDWARE_MEM_SAMPLING_FREQ));
    EXPECT_EQ(PROFILING_SUCCESS, parser.MsprofFreqCheckValid(cmdInfo, ARGS_AIC_FREQ));
    EXPECT_EQ(PROFILING_SUCCESS, parser.MsprofFreqCheckValid(cmdInfo, ARGS_AIV_FREQ));
    EXPECT_EQ(PROFILING_SUCCESS, parser.MsprofFreqCheckValid(cmdInfo, ARGS_EXPORT_ITERATION_ID));
    EXPECT_EQ(PROFILING_SUCCESS, parser.MsprofFreqCheckValid(cmdInfo, ARGS_EXPORT_MODEL_ID));
    EXPECT_EQ(PROFILING_SUCCESS, parser.MsprofFreqCheckValid(cmdInfo, ARGS_INSTR_PROFILING_FREQ));
    EXPECT_EQ(PROFILING_SUCCESS, parser.MsprofFreqCheckValid(cmdInfo, ARGS_HOST_SYS_USAGE_FREQ));

    // Incorrect input
    cmdInfo.args[ARGS_EXPORT_ITERATION_ID] = "";
    EXPECT_EQ(PROFILING_FAILED, parser.MsprofFreqCheckValid(cmdInfo, ARGS_EXPORT_ITERATION_ID));
    cmdInfo.args[ARGS_EXPORT_ITERATION_ID] = "abc";
    EXPECT_EQ(PROFILING_FAILED, parser.MsprofFreqCheckValid(cmdInfo, ARGS_EXPORT_ITERATION_ID));
    cmdInfo.args[ARGS_EXPORT_ITERATION_ID] = "4294967296";
    EXPECT_EQ(PROFILING_FAILED, parser.MsprofFreqCheckValid(cmdInfo, ARGS_EXPORT_ITERATION_ID));
    cmdInfo.args[ARGS_EXPORT_ITERATION_ID] = "4294967295";
    EXPECT_EQ(PROFILING_SUCCESS, parser.MsprofFreqCheckValid(cmdInfo, ARGS_EXPORT_ITERATION_ID));
    cmdInfo.args[ARGS_EXPORT_ITERATION_ID] = "12345678901234567890123456789012345678901234567890123456789012345678901";
    EXPECT_EQ(PROFILING_FAILED, parser.MsprofFreqCheckValid(cmdInfo, ARGS_EXPORT_ITERATION_ID));
}

TEST_F(INPUT_PARSER_UTEST, CheckDynProfValid) {
    struct MsprofCmdInfo cmdInfo = {{nullptr}};
    cmdInfo.args[ARGS_DYNAMIC_PROF] = "on";

    InputParser parser = InputParser();
    parser.params_->app = "";
    parser.params_->dynamic = "";
    parser.params_->pid = "123";
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckDynProfValid(cmdInfo));

    parser.params_->app = "";
    parser.params_->dynamic = "";
    parser.params_->pid = "";
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.CheckDynProfValid(cmdInfo));

    parser.params_->app = "";
    parser.params_->dynamic = "on";
    parser.params_->pid = "";
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckDynProfValid(cmdInfo));

    parser.params_->app = "app";
    parser.params_->dynamic = "on";
    parser.params_->pid = "123";
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckDynProfValid(cmdInfo));

    parser.params_->app = "";
    parser.params_->dynamic = "on";
    parser.params_->pid = "123";

    cmdInfo.args[ARGS_CPU_PROFILING] = "on";
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckDynProfValid(cmdInfo));
    cmdInfo.args[ARGS_SYS_PERIOD] = "10";
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckDynProfValid(cmdInfo));
    cmdInfo.args[ARGS_SYS_DEVICES] = "on";
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckDynProfValid(cmdInfo));
}

TEST_F(INPUT_PARSER_UTEST, PreCheckPlatform_Miniv3) {
    InputParser parser = InputParser();
    const char *argv[] = {"instr-profiling"};
    optind = 1;
    ConfigManager::instance()->configMap_["type"] =
        std::to_string(static_cast<int32_t>(Analysis::Dvvp::Common::Config::PlatformType::MINI_V3_TYPE));
    Platform::instance()->runSide_ = SysPlatformType::DEVICE;
    EXPECT_EQ(PROFILING_FAILED, parser.PreCheckPlatform(ARGS_INSTR_PROFILING, argv));
    EXPECT_EQ(PROFILING_FAILED, parser.PreCheckPlatform(ARGS_INSTR_PROFILING_FREQ, argv));
    Platform::instance()->runSide_ = SysPlatformType::INVALID;
}

TEST_F(INPUT_PARSER_UTEST, PreCheckSwitch310P) {
    InputParser parser = InputParser();
    int32_t argc = 4;
    const char *argv[argc];
    argv[0] = "msprof";
    argv[1] = "--dynamic=on";
    argv[DYNAMIC_OUTPUT_ARG_INDEX] = "--output=./";
    argv[DYNAMIC_APP_ARG_INDEX] = "./main -m ./resnet50.om";

    ConfigManager::instance()->configMap_["type"] =
        std::to_string(static_cast<int32_t>(Analysis::Dvvp::Common::Config::PlatformType::DC_TYPE));
    Platform::instance()->runSide_ = SysPlatformType::HOST;

    EXPECT_EQ(PROFILING_SUCCESS, parser.PreCheckPlatform(ARGS_DYNAMIC_PROF, (const char **)argv));
    EXPECT_EQ(PROFILING_SUCCESS, parser.PreCheckPlatform(ARGS_DYNAMIC_PROF_PID, (const char **)argv));
    EXPECT_EQ(PROFILING_SUCCESS, parser.PreCheckPlatform(ARGS_DELAY_PROF, (const char **)argv));
    EXPECT_EQ(PROFILING_SUCCESS, parser.PreCheckPlatform(ARGS_DURATION_PROF, (const char **)argv));
    Platform::instance()->runSide_ = SysPlatformType::INVALID;
}

/*
 * 函数原型	MsprofArgsType, LONG_OPTIONS[]
 * 函数功能	检测参数配置是否发生错位
 * 注意事项 谨慎修改，确保63位是invalid，并且63之前参数填充满，保证63的前后参数与input_parser.h顺序一致
 */
TEST_F(INPUT_PARSER_UTEST, PreCheckParamOffset) {
    EXPECT_EQ(DVPP_FREQ_ARG_INDEX, ARGS_DVPP_FREQ);
    EXPECT_EQ(CPU_SAMPLING_FREQ_ARG_INDEX, ARGS_CPU_SAMPLING_FREQ);
    EXPECT_EQ(INVALID_ARG_INDEX, ARGS_INVALID);
    EXPECT_EQ(INTERCONNECTION_FREQ_ARG_INDEX, ARGS_INTERCONNECTION_FREQ);
    EXPECT_EQ("dvpp-freq", LONG_OPTIONS[ARGS_DVPP_FREQ].name);                           // 58
    EXPECT_EQ("sys-cpu-freq", LONG_OPTIONS[ARGS_CPU_SAMPLING_FREQ].name);                // 59
    EXPECT_EQ("invalid", LONG_OPTIONS[ARGS_INVALID].name);                               // 63
    EXPECT_EQ("sys-interconnection-freq", LONG_OPTIONS[ARGS_INTERCONNECTION_FREQ].name); // 60
    EXPECT_EQ("nts-metrics", LONG_OPTIONS[ARGS_NTS_METRICS].name);
}
TEST_F(INPUT_PARSER_UTEST, CheckCmdOpTypeIsValid) {
    GlobalMockObject::verify();
    InputParser parser = InputParser();
    struct MsprofCmdInfo cmdInfo = { {nullptr} };

    cmdInfo.args[ARGS_OP_TYPE] = nullptr;
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckCmdOpTypeIsValid(cmdInfo));

    cmdInfo.args[ARGS_OP_TYPE] = "";
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckCmdOpTypeIsValid(cmdInfo));

    std::vector<char> longOpType(OP_TYPE_EXCEED_MAX_LEN + 1, 'a');
    longOpType[OP_TYPE_EXCEED_MAX_LEN] = '\0';
    cmdInfo.args[ARGS_OP_TYPE] = longOpType.data();
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckCmdOpTypeIsValid(cmdInfo));

    cmdInfo.args[ARGS_OP_TYPE] = "MatMul,,Add";
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckCmdOpTypeIsValid(cmdInfo));

    cmdInfo.args[ARGS_OP_TYPE] = "MatMul,MatMul";
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.CheckCmdOpTypeIsValid(cmdInfo));
    EXPECT_EQ("MatMul", parser.params_->opType);

    cmdInfo.args[ARGS_OP_TYPE] = "Add,MatMul,Add";
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.CheckCmdOpTypeIsValid(cmdInfo));
    EXPECT_EQ("Add,MatMul", parser.params_->opType);

    cmdInfo.args[ARGS_OP_TYPE] = "MatMul";
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.CheckCmdOpTypeIsValid(cmdInfo));
    EXPECT_EQ("MatMul", parser.params_->opType);

    cmdInfo.args[ARGS_OP_TYPE] = "MatMul,Add,Softmax";
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.CheckCmdOpTypeIsValid(cmdInfo));
    EXPECT_EQ("Add,MatMul,Softmax", parser.params_->opType);
}

TEST_F(INPUT_PARSER_UTEST, CheckMstxValidWillReturnErrorWhenmstxDomainIncludeAndmstxDomainExcludeAndMstxAllSet)
{
    InputParser parser = InputParser();
    parser.params_->msproftx = "on";
    parser.params_->mstxDomainInclude = "a";
    parser.params_->mstxDomainExclude = "a";
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckMstxValid());
}

TEST_F(INPUT_PARSER_UTEST, CheckMstxValidWillReturnOKWhenmstxDomainIncludeAndmstxDomainExcludeNotSet)
{
    InputParser parser = InputParser();
    parser.params_->msproftx = "on";
    parser.params_->mstxDomainInclude = "";
    parser.params_->mstxDomainExclude = "";
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.CheckMstxValid());
}

TEST_F(INPUT_PARSER_UTEST, CheckMstxValidWillReturnOKWhenmstxDomainIncludeSetOrmstxDomainExcludeSet)
{
    InputParser parser = InputParser();
    parser.params_->msproftx = "on";
    parser.params_->mstxDomainInclude = "a";
    parser.params_->mstxDomainExclude = "";
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.CheckMstxValid());

    parser.params_->mstxDomainInclude = "";
    parser.params_->mstxDomainExclude = "a";
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.CheckMstxValid());
}

TEST_F(INPUT_PARSER_UTEST, CheckMstxValidWillReturnOKWhenmstxDomainIncludeSetOrmstxDomainExcludeSetAndMstxOff)
{
    InputParser parser = InputParser();
    parser.params_->msproftx = "off";
    parser.params_->mstxDomainInclude = "a";
    parser.params_->mstxDomainExclude = "";
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckMstxValid());

    parser.params_->mstxDomainInclude = "";
    parser.params_->mstxDomainExclude = "a";
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckMstxValid());
}

TEST_F(INPUT_PARSER_UTEST, CheckMstxValidWillReturnOKWhenmstxDomainIncludeSetOrmstxDomainExcludeBothNotSetAndMstxOff)
{
    InputParser parser = InputParser();
    parser.params_->msproftx = "off";
    parser.params_->mstxDomainInclude = "";
    parser.params_->mstxDomainExclude = "";
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.CheckMstxValid());
}

TEST_F(INPUT_PARSER_UTEST, CheckExportTypeWillReturnErrorWhenExportTypeInvalid)
{
    InputParser parser = InputParser();
    struct MsprofCmdInfo cmdInfo = {{nullptr}};
    cmdInfo.args[ARGS_EXPORT_TYPE] = "invalid_export_type";
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckExportType(cmdInfo));

    cmdInfo.args[ARGS_EXPORT_TYPE] = nullptr;
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckExportType(cmdInfo));
}

TEST_F(INPUT_PARSER_UTEST, CheckExportTypeWillReturnOKWhenExportTypeValid)
{
    InputParser parser = InputParser();
    struct MsprofCmdInfo cmdInfo = {{nullptr}};
    cmdInfo.args[ARGS_EXPORT_TYPE] = "text";
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.CheckExportType(cmdInfo));
    EXPECT_STREQ("text", parser.params_->exportType.c_str());

    cmdInfo.args[ARGS_EXPORT_TYPE] = "db";
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.CheckExportType(cmdInfo));
    EXPECT_STREQ("db", parser.params_->exportType.c_str());
}

TEST_F(INPUT_PARSER_UTEST, CheckReportsWillReturnErrorWhenReportsInvalid)
{
    InputParser parser = InputParser();
    struct MsprofCmdInfo cmdInfo = {{nullptr}};
    cmdInfo.args[ARGS_REPORTS] = nullptr;
    EXPECT_EQ(MSPROF_DAEMON_ERROR, parser.CheckReports(cmdInfo));
}

TEST_F(INPUT_PARSER_UTEST, CheckReportsWillReturnOKWhenReportsValid)
{
    InputParser parser = InputParser();
    struct MsprofCmdInfo cmdInfo = {{nullptr}};
    cmdInfo.args[ARGS_REPORTS] = "xx";
    EXPECT_EQ(MSPROF_DAEMON_OK, parser.CheckReports(cmdInfo));
    EXPECT_STREQ("xx", parser.params_->reportsPath.c_str());
}

TEST_F(INPUT_PARSER_UTEST, GenerateChipV2PlatSwithMap)
{
    InputParser parser = InputParser();
    auto platMap = parser.GenerateChipV2PlatSwithMap();

    const std::vector<MsprofArgsType> expected = {ARGS_AIV, ARGS_AIV_FREQ, ARGS_AIV_MODE, ARGS_AIV_METRICS,
        ARGS_AICPU, ARGS_IO_PROFILING, ARGS_DYNAMIC_PROF, ARGS_DYNAMIC_PROF_PID, ARGS_DELAY_PROF, ARGS_DURATION_PROF,
        ARGS_DVPP_PROFILING, ARGS_DVPP_FREQ, ARGS_HCCL, ARGS_MODEL_EXECUTION};

    EXPECT_EQ(expected, platMap[PlatformType::CHIP_MDC_V2]);
    EXPECT_EQ(expected, platMap[PlatformType::CHIP_MDC_LITE_V2]);
}

TEST_F(INPUT_PARSER_UTEST, AddHCCLArgs)
{
    ArgsManager argsManager = ArgsManager();

    // Scenario 1: V2 platforms skip the hccl arg, the list stays empty
    SetPlatformTypeForTest(PlatformType::CHIP_MDC_V2);
    argsManager.argsList_.clear();
    argsManager.AddHCCLArgs();
    EXPECT_EQ(static_cast<size_t>(0), argsManager.argsList_.size());

    SetPlatformTypeForTest(PlatformType::CHIP_MDC_LITE_V2);
    argsManager.argsList_.clear();
    argsManager.AddHCCLArgs();
    EXPECT_EQ(static_cast<size_t>(0), argsManager.argsList_.size());

    // Scenario 2: non-V2 platform appends the hccl arg
    SetPlatformTypeForTest(PlatformType::MINI_TYPE);
    argsManager.argsList_.clear();
    argsManager.AddHCCLArgs();
    EXPECT_EQ(static_cast<size_t>(1), argsManager.argsList_.size());
}

} // namespace
