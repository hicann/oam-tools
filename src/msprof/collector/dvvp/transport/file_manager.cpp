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
#include "file_manager.h"
#include "file_transport.h"
#include "config/config.h"
#include "errno/error_code.h"
#include "utils/utils.h"
#include "osal/osal_mem.h"
#include "msprof_dlog.h"

namespace analysis {
namespace dvvp {
namespace transport {
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::common::config;
using namespace analysis::dvvp::common::utils;

FileManager::FileManager() {}

FileManager::~FileManager()
{
    transportMap_.clear();
}

int32_t FileManager::InitFileTransport(uint32_t deviceId, const char *flushDir, const char *storageLimit)
{
    auto tranport = FileTransportFactory().CreateFileTransport(
        std::string(flushDir) + MSVP_SLASH, std::string(storageLimit), true);
    if (tranport == nullptr) {
        MSPROF_LOGE("Failed to create transport for device %u.", deviceId);
        return PROFILING_FAILED;
    }
    std::unique_lock<std::mutex> lk(fileMtx_);
    transportMap_[deviceId] = tranport;
    MSPROF_LOGI("Success to create transport for device %u.", deviceId);
    return PROFILING_SUCCESS;
}

int32_t FileManager::SendBuffer(ProfFileChunk* chunk)
{
    int32_t ret = PROFILING_SUCCESS;
    do {
        SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq;
        MSVP_MAKE_SHARED0_NODO(fileChunkReq, analysis::dvvp::ProfileFileChunk, break);
        fileChunkReq->isLastChunk = static_cast<bool>(chunk->isLastChunk);
        fileChunkReq->chunkModule = static_cast<int32_t>(chunk->chunkType);
        fileChunkReq->chunkSize = static_cast<size_t>(chunk->chunkSize);
        fileChunkReq->offset = static_cast<size_t>(chunk->offset);
        fileChunkReq->chunk = std::string(reinterpret_cast<CHAR*>(chunk->chunk), chunk->chunkSize);
        fileChunkReq->fileName = std::string(chunk->fileName);
        fileChunkReq->extraInfo = Utils::PackDotInfo(NULL_CHUNK, std::to_string(chunk->deviceId));
        if (fileChunkReq->chunkModule == PROFILING_IS_CTRL_DATA &&
            chunk->deviceId != DEFAULT_HOST_ID &&
            fileChunkReq->fileName != SAMPLE_JSON) {
            fileChunkReq->fileName.append(".").append(std::to_string(chunk->deviceId));
        }
        MSPROF_LOGI("FileManager send c filename: %s, device: %u, module: %d, size: %u.",
            fileChunkReq->fileName.c_str(), chunk->deviceId, fileChunkReq->chunkModule,
            fileChunkReq->chunkSize);
        std::unique_lock<std::mutex> lk(fileMtx_);
        auto it = transportMap_.find(chunk->deviceId);
        if (it == transportMap_.end()) {
            MSPROF_LOGE("Failed to find transport in file manager, device: %u.", chunk->deviceId);
            ret =  PROFILING_FAILED;
            break;
        }
        ret = it->second->SendBuffer(fileChunkReq);
        if (ret != PROFILING_SUCCESS) {
            MSPROF_LOGE("Failed to send buffer by file manager, device: %u.", chunk->deviceId);
            break;
        }
    } while (0);
    OSAL_MEM_FREE(chunk->chunk);
    OSAL_MEM_FREE(chunk);
    return ret;
}
}  // namespace transport
}  // namespace dvvp
}  // namespace analysis