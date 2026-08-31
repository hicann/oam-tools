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
#include "securec.h"
#include <sys/wait.h>
#include <sys/types.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <libgen.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <dirent.h>
#include <sys/time.h>
#include <sys/vfs.h>
#include <locale>
#include <errno.h>
#include <algorithm>
#include <fstream>
// mac
#include <net/if.h>
#include <sys/prctl.h>
#include "file_slice.h"
#include "message/prof_params.h"
#include "thread/thread_pool.h"

using namespace analysis::dvvp::common::thread;
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::transport;

class COMMON_FILE_SLICE_TEST : public testing::Test {
protected:
    virtual void SetUp() {}
    virtual void TearDown() { GlobalMockObject::verify(); }

private:
};

TEST_F(COMMON_FILE_SLICE_TEST, GetSliceKey)
{
    std::string dir = "/tmp";
    std::string limit = "500MB";
    FileSlice wfTransport(128, dir, limit);
    std::string fileName = "hwts.log";
    std::string key = wfTransport.GetSliceKey(dir, fileName);
    EXPECT_STREQ("/tmp/hwts.log.slice_", key.c_str());
}

TEST_F(COMMON_FILE_SLICE_TEST, Init_failed)
{
    std::string dir = "";
    std::string limit = "500MB";
    FileSlice wfTransport(128, dir, limit);
    EXPECT_EQ(PROFILING_FAILED, wfTransport.Init());

    FileSlice wfTransport1(128, "/tmp/../../aaa/b", limit);
}

TEST_F(COMMON_FILE_SLICE_TEST, SetChunkTime)
{
    std::string dir = "/tmp";
    std::string limit = "500MB";
    FileSlice wfTransport(128, dir, limit);
    wfTransport.Init();
    int ret = wfTransport.SetChunkTime("", 0, 1);
    EXPECT_EQ(PROFILING_FAILED, ret);

    MOCKER(analysis::dvvp::common::utils::Utils::IsFileExist).stubs().will(returnValue(false));

    MOCKER(analysis::dvvp::common::utils::Utils::GetFileSize).stubs().will(returnValue(0));

    ret = wfTransport.SetChunkTime("hwts.log.slice_", 0, 1);
    EXPECT_EQ(PROFILING_SUCCESS, ret);
}

TEST_F(COMMON_FILE_SLICE_TEST, WriteToLocalFiles)
{
    std::string key = "hwts.log.slice_";
    const char* data = "test";
    int dataLen = strlen(data);
    int offset = -1;
    bool isLastChunk = true;
    std::string dir = "/tmp";
    FileSlice wfTransport(128, dir, "200MB");
    wfTransport.Init();

    MOCKER(analysis::dvvp::common::utils::Utils::IsFileExist)
        .stubs()
        .will(returnValue(true))
        .then(returnValue(false))
        .then(returnValue(false))
        .then(returnValue(true));

    MOCKER(analysis::dvvp::common::utils::Utils::GetFileSize)
        .stubs()
        .will(returnValue(127 * 1024 + 1))
        .then(returnValue(128 * 1024 + 1));

    MOCKER_CPP(&analysis::dvvp::transport::FileSlice::CreateDoneFile)
        .stubs()
        .will(returnValue(false))
        .then(returnValue(true));

    // key.length() = 0
    int ret = wfTransport.WriteToLocalFiles("", data, dataLen, offset, isLastChunk);
    EXPECT_EQ(PROFILING_FAILED, ret);
    // Failed to create file:hwts.log.slice_
    ret = wfTransport.WriteToLocalFiles(key, data, dataLen, offset, isLastChunk);
    EXPECT_EQ(PROFILING_FAILED, ret);

    // open failed
    isLastChunk = false;
    key = "/tmp/not_exist_dir/hwts.log";
    ret = wfTransport.WriteToLocalFiles(key, data, dataLen, offset, isLastChunk);
    EXPECT_EQ(PROFILING_FAILED, ret);

    // diskFull return true
    key = "hwts.log.slice_";
    ret = wfTransport.WriteToLocalFiles(key, data, dataLen, offset, isLastChunk);
    EXPECT_EQ(PROFILING_SUCCESS, ret);

    // open file failed
    key = "/tmp/not_exist_dir/hwts.log";
    ret = wfTransport.WriteToLocalFiles(key, data, dataLen, offset, isLastChunk);
    EXPECT_EQ(PROFILING_FAILED, ret);

    // create done file failed
    key = "hwts.log.slice_";
    ret = wfTransport.WriteToLocalFiles(key, data, dataLen, 0, isLastChunk);
    EXPECT_EQ(PROFILING_SUCCESS, ret);

    ret = wfTransport.WriteToLocalFiles(key, data, dataLen, 0, isLastChunk);
    EXPECT_EQ(PROFILING_SUCCESS, ret);
}

TEST_F(COMMON_FILE_SLICE_TEST, CheckDirAndMessage)
{
    std::shared_ptr<analysis::dvvp::ProfileFileChunk> message(new analysis::dvvp::ProfileFileChunk());
    message->fileName = "test";
    message->offset = -1;
    message->chunk = "123";
    message->chunkSize = 3;
    message->isLastChunk = false;

    std::string dir = "/home/test";
    std::string limit = "500MB";
    FileSlice wfTransport(128, dir, limit);

    // nullptr input
    std::shared_ptr<analysis::dvvp::ProfileFileChunk> nullptrMessage = nullptr;
    int ret = wfTransport.CheckDirAndMessage(nullptrMessage, dir);
    EXPECT_EQ(PROFILING_FAILED, ret);

    // isLastChunk and chuckSize zero
    message->chunkSize = 0;
    message->isLastChunk = true;
    ret = wfTransport.CheckDirAndMessage(message, dir);
    EXPECT_EQ(PROFILING_SUCCESS, ret);

    // chuckSize zero
    message->isLastChunk = false;
    ret = wfTransport.CheckDirAndMessage(message, dir);
    EXPECT_EQ(PROFILING_FAILED, ret);

    MOCKER(analysis::dvvp::common::utils::Utils::CreateDir)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));

    // failed to CreateDir
    message->chunkSize = 3;
    ret = wfTransport.CheckDirAndMessage(message, dir);
    EXPECT_EQ(PROFILING_FAILED, ret);
    ret = wfTransport.CheckDirAndMessage(message, dir);
    EXPECT_EQ(PROFILING_SUCCESS, ret);
}

TEST_F(COMMON_FILE_SLICE_TEST, SaveDataToLocalFiles)
{
    std::string dir = "/home/test";
    std::string limit = "500MB";
    std::shared_ptr<analysis::dvvp::ProfileFileChunk> message(new analysis::dvvp::ProfileFileChunk());
    message->fileName = "test";
    message->offset = -1;
    message->chunk = "123";
    message->chunkSize = 3;
    message->isLastChunk = false;
    message->extraInfo = "0.0";

    std::string invalidHomeDir = "";
    std::string homeDir = "/home/test";
    MOCKER(analysis::dvvp::common::utils::Utils::IdeReplaceWaveWithHomedir)
        .stubs()
        .will(returnValue(invalidHomeDir))
        .then(returnValue(homeDir));
    MOCKER(analysis::dvvp::common::utils::Utils::CreateDir)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&FileSlice::CheckDirAndMessage)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&FileSlice::WriteCtrlDataToFile).stubs().will(returnValue(PROFILING_FAILED));

    FileSlice wfTransport(128, dir, limit);
    wfTransport.Init();

    // nullptr input
    std::shared_ptr<analysis::dvvp::ProfileFileChunk> nullptrMessage = nullptr;
    int ret = wfTransport.SaveDataToLocalFiles(nullptrMessage, dir);
    EXPECT_EQ(PROFILING_FAILED, ret);

    // Failed to CheckDirAndMessage
    ret = wfTransport.SaveDataToLocalFiles(message, dir);
    EXPECT_EQ(PROFILING_FAILED, ret);

    // isLastChunk and chuckSize zero
    message->chunkSize = 0;
    message->isLastChunk = true;
    ret = wfTransport.SaveDataToLocalFiles(message, dir);
    EXPECT_EQ(PROFILING_SUCCESS, ret);

    // Failed to WriteCtrlDataToFile
    message->chunkSize = 3;
    message->isLastChunk = false;
    message->chunkModule = analysis::dvvp::common::config::FileChunkDataModule::PROFILING_IS_CTRL_DATA;
    ret = wfTransport.SaveDataToLocalFiles(message, dir);
    EXPECT_EQ(PROFILING_FAILED, ret);
    message->chunkModule = analysis::dvvp::common::config::FileChunkDataModule::PROFILING_IS_FROM_MSPROF_HOST;
    std::string invalidKey = "";
    std::string key = "hwts.log.slice_";
    MOCKER_CPP(&FileSlice::GetSliceKey).stubs().will(returnValue(invalidKey)).then(returnValue(key));

    MOCKER_CPP(&FileSlice::SetChunkTime)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    MOCKER_CPP(&FileSlice::WriteToLocalFiles)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));

    // GetSliceKey return length 0
    ret = wfTransport.SaveDataToLocalFiles(message, dir);
    EXPECT_EQ(PROFILING_FAILED, ret);

    // SetChunkTime return Failed
    message->fileName = "/home/test/test.log";
    ret = wfTransport.SaveDataToLocalFiles(message, dir);
    EXPECT_EQ(PROFILING_FAILED, ret);

    // WriteToLocalFiles Failed
    ret = wfTransport.SaveDataToLocalFiles(message, dir);
    EXPECT_EQ(PROFILING_FAILED, ret);
}

TEST_F(COMMON_FILE_SLICE_TEST, CreateDoneFile)
{
    GlobalMockObject::verify();
    MOCKER(analysis::dvvp::common::utils::Utils::GetFileSize).stubs().will(returnValue(1000));

    std::string absolutePath = "";
    std::string fileSize = "1000";
    std::string startTime = "0";
    std::string endTime = "1";
    std::string limit = "500MB";
    std::string dir = "/tmp";
    FileSlice wfTransport(128, dir, limit);
    wfTransport.Init();
    bool ret = wfTransport.CreateDoneFile(absolutePath, fileSize, startTime, endTime, absolutePath);
    EXPECT_EQ(true, ret);

    std::string fileName = "hwts.log";
    absolutePath = "hwts.log.slice_";
    MOCKER(analysis::dvvp::common::utils::Utils::IsFileExist).stubs().will(returnValue(false));
    wfTransport.GetSliceKey(dir, fileName);
    wfTransport.SetChunkTime(dir + fileName + ".slice_", 0, 0);
    ret = wfTransport.CreateDoneFile(absolutePath, fileSize, startTime, endTime, "/home/test/hwts.log.slice_0");
    EXPECT_EQ(true, ret);

    MOCKER(analysis::dvvp::common::utils::Utils::IsFileExist).stubs().will(returnValue(true));
    wfTransport.GetSliceKey(dir, fileName);
    wfTransport.SetChunkTime(dir + fileName + ".slice_", 0, 0);
    ret = wfTransport.CreateDoneFile(absolutePath, fileSize, startTime, endTime, "/home/test/hwts.log.slice_0");
    EXPECT_EQ(true, ret);
}

TEST_F(COMMON_FILE_SLICE_TEST, CreateDoneFileForFail)
{
    std::string absolutePath = "";
    std::string fileSize = "1000";
    std::string startTime = "0";
    std::string endTime = "1";
    std::string dir = "/tmp";
    std::string limit = "500MB";

    FileSlice wfTransport(128, dir, limit);
    wfTransport.Init();
    bool ret = wfTransport.CreateDoneFile(absolutePath, fileSize, startTime, endTime, absolutePath);
    EXPECT_EQ(true, ret);

    std::string fileName = "hwts.log";
    absolutePath = "hwts.log.slice_";
    MOCKER(analysis::dvvp::common::utils::Utils::IsFileExist).stubs().will(returnValue(false));
    wfTransport.GetSliceKey(dir, fileName);
    wfTransport.SetChunkTime(dir + fileName + ".slice_", 0, 0);
    ret = wfTransport.CreateDoneFile(absolutePath, fileSize, startTime, endTime, "/home/test/hwts.log.slice_0");
    EXPECT_EQ(true, ret);

    MOCKER(analysis::dvvp::common::utils::Utils::IsFileExist).stubs().will(returnValue(true));
    wfTransport.GetSliceKey(dir, fileName);
    wfTransport.SetChunkTime(dir + fileName + ".slice_", 0, 0);
    ret = wfTransport.CreateDoneFile(absolutePath, fileSize, startTime, endTime, "/home/test/hwts.log.slice_0");
    EXPECT_EQ(true, ret);
}

TEST_F(COMMON_FILE_SLICE_TEST, CreateDoneFileForOpenFail)
{
    std::string absolutePath = "./data/host_start.log";
    std::string dir = "/home/test/";
    std::string limit = "500MB";

    FileSlice wfTransport(128, dir, limit);
    wfTransport.Init();
    bool ret = wfTransport.CreateDoneFile(absolutePath, "1000", "", "", "");
    EXPECT_EQ(false, ret);
}

TEST_F(COMMON_FILE_SLICE_TEST, FileSliceFlush)
{
    std::string dir = "/home/test";
    std::string limit = "500MB";

    FileSlice wfTransport(128, dir, limit);
    wfTransport.Init();
    std::string fileName = "test.log";
    wfTransport.GetSliceKey(dir, fileName);

    MOCKER_CPP(&analysis::dvvp::transport::FileSlice::CreateDoneFile)
        .stubs()
        .will(returnValue(false))
        .then(returnValue(true));

    MOCKER(analysis::dvvp::common::utils::Utils::IsFileExist).stubs().will(returnValue(true));

    MOCKER(analysis::dvvp::common::utils::Utils::GetFileSize).stubs().will(returnValue(128 * 1024));

    int ret = wfTransport.FileSliceFlush();
    EXPECT_EQ(false, ret);
    ret = wfTransport.FileSliceFlush();
    EXPECT_EQ(true, ret);
}

TEST_F(COMMON_FILE_SLICE_TEST, FileSliceFlushPolymorphism)
{
    std::string dir = "/home/test/1234";
    std::string limit = "500MB";
    FileSlice wfTransport(128, dir, limit);

    wfTransport.Init();

    std::string fileName = "test.log";
    wfTransport.GetSliceKey(dir, fileName);

    MOCKER_CPP(&analysis::dvvp::transport::FileSlice::CreateDoneFile)
        .stubs()
        .will(returnValue(false))
        .then(returnValue(true));

    MOCKER(analysis::dvvp::common::utils::Utils::IsFileExist).stubs().will(returnValue(true));

    MOCKER(analysis::dvvp::common::utils::Utils::GetFileSize).stubs().will(returnValue(128 * 1024));

    std::string jobIDRelative = "1234";
    std::string devID = "0";
    std::string fileSliceName = "";
    fileSliceName.append(".").append(devID).append(".slice_");
    wfTransport.GetSliceKey(dir, fileSliceName);

    int ret = wfTransport.FileSliceFlushByJobID(jobIDRelative, devID);
    EXPECT_EQ(PROFILING_FAILED, ret);
    ret = wfTransport.FileSliceFlushByJobID(jobIDRelative, devID);
    EXPECT_EQ(PROFILING_SUCCESS, ret);
}

TEST_F(COMMON_FILE_SLICE_TEST, WriteCtrlDataToFile)
{
    std::string absolutePath = "/tmp";
    std::string data = "test";
    std::string limit = "500MB";
    FileSlice wfTransport(128, "/tmp", limit);
    remove("/tmp/ctrl_data.txt");
    EXPECT_EQ(PROFILING_SUCCESS, wfTransport.Init());
    EXPECT_EQ(PROFILING_FAILED, wfTransport.WriteCtrlDataToFile("non_exist.txt", data, 0));
    wfTransport.WriteCtrlDataToFile(absolutePath, data, data.size());
    wfTransport.WriteCtrlDataToFile(absolutePath, "", data.size());
    wfTransport.WriteCtrlDataToFile("/tmp/ctrl_data.txt", "test", data.size());
    remove("/tmp/ctrl_data.txt");
}

TEST_F(COMMON_FILE_SLICE_TEST, WriteSliceRollover)
{
    const std::string dir = "/tmp";
    const std::string slice0 = "/tmp/stars_soc.data.slice_0";
    const std::string slice1 = "/tmp/stars_soc.data.slice_1";
    remove(slice0.c_str());
    remove(slice1.c_str());

    // sliceFileMaxKByte_ = 1 -> slice threshold is 1 * 1024 = 1024 bytes (a multiple of 64).
    FileSlice wfTransport(1, dir, "500MB");
    EXPECT_EQ(PROFILING_SUCCESS, wfTransport.Init());

    // Avoid exercising the .done/ageing machinery; only the slice rollover behaviour matters here.
    MOCKER_CPP(&analysis::dvvp::transport::FileSlice::CreateDoneFile).stubs().will(returnValue(true));

    std::string keyName = "stars_soc.data";
    const std::string key = wfTransport.GetSliceKey(dir, keyName); // key -> /tmp/stars_soc.data.slice_

    char chunk[101];
    memset_s(chunk, sizeof(chunk), 'a', sizeof(chunk));
    const int chunkLen = 100;

    // 11 chunks of 100 bytes: the 11th crosses 1024 and finalizes slice_0.
    for (int i = 0; i < 11; ++i) {
        EXPECT_EQ(PROFILING_SUCCESS, wfTransport.WriteToLocalFiles(key, chunk, chunkLen, -1, false));
    }

    EXPECT_EQ(1100, analysis::dvvp::common::utils::Utils::GetFileSize(slice0));
    EXPECT_EQ(-1, analysis::dvvp::common::utils::Utils::GetFileSize(slice1));

    remove(slice0.c_str());
    remove(slice1.c_str());
}
