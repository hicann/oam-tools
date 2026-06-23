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
#include <iostream>
#include <fstream>
#include "gtest/gtest.h"
#include "mockcpp/mockcpp.hpp"
#include "file_interface.h"
#include "file_transport.h"
#include "transport.h"
#include "errno/error_code.h"
#include "osal/osal_mem.h"
#include "utils/utils.h"

class FileManagerUtest: public testing::Test {
protected:
    virtual void SetUp()
    {
    }
    virtual void TearDown()
    {
        GlobalMockObject::verify();
    }
};

ProfFileChunk * CreateCFileChunk(uint8_t deviceId, uint32_t chunkSize, int32_t type)
{
    ProfFileChunk *chunk = (ProfFileChunk *)OsalMalloc(sizeof(ProfFileChunk));
    chunk->deviceId = deviceId;
    chunk->chunkSize = chunkSize;
    chunk->chunkType = type;
    chunk->isLastChunk = false;
    chunk->offset = -1;
    chunk->chunk = (uint8_t*)OsalMalloc(1048576); // 1*1024*1024
    (void)memset_s(chunk->fileName, sizeof(chunk->fileName), 0, sizeof(chunk->fileName));
    (void)sprintf_s(chunk->fileName, sizeof(chunk->fileName), "%s", "nano_stars_profile.data");
    return chunk;
}

TEST_F(FileManagerUtest, FileTransportBase)
{
    using namespace analysis::dvvp::transport;
    using namespace analysis::dvvp::common::error;
    std::string tmp = "/tmp/FileManagerUtest";
    SHARED_PTR_ALIA<ITransport> fileTransport_null;
    SHARED_PTR_ALIA<FILETransport> fileTransport = std::make_shared<FILETransport>(tmp, "200MB");
    (void)fileTransport->Init();
    SHARED_PTR_ALIA<ITransport> fileTransport_it = fileTransport;
    MOCKER_CPP(&FileTransportFactory::CreateFileTransport)
        .stubs()
        .will(returnValue(fileTransport_null))
        .then(returnValue(fileTransport_it));
    // Failed to create transport
    int32_t ret = ProfInitTransport(0, "/tmp/FileManagerUtest", "200MB");
    EXPECT_EQ(ret, PROFILING_FAILED);
    // Success to create transport for device 0
    ret = ProfInitTransport(0, "/tmp/FileManagerUtest", "200MB");
    EXPECT_EQ(ret, PROFILING_SUCCESS);
    // Failed to find transport in file manager, device: 1
    ret = ProfSendBuffer(CreateCFileChunk(1, 1, 3), "/tmp/FileManagerUtest");
    EXPECT_EQ(ret, PROFILING_FAILED);

    MOCKER_CPP(&FileSlice::SaveDataToLocalFiles)
        .stubs()
        .will(returnValue(PROFILING_FAILED))
        .then(returnValue(PROFILING_SUCCESS));
    // Failed to send buffer by file manager, device: 0
    ret = ProfSendBuffer(CreateCFileChunk(0, 1, 3), "/tmp/FileManagerUtest");
    EXPECT_EQ(ret, PROFILING_FAILED);

    ret = ProfSendBuffer(CreateCFileChunk(0, 1, 3), "/tmp/FileManagerUtest");
    EXPECT_EQ(ret, PROFILING_SUCCESS);
}