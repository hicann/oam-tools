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

#include "prof_reporter_mgr.h"
#include <algorithm>
#include "receive_data.h"
#include "error_code.h"
#include "uploader_mgr.h"
#include "hash_data.h"

namespace Dvvp {
namespace Collect {
namespace Report {
using namespace analysis::dvvp::common::error;
using namespace Msprof::Engine;
using namespace analysis::dvvp::transport;
using namespace Analysis::Dvvp::MsprofErrMgr;

ProfReporterMgr::ProfReporterMgr() : isStarted_(false), isUploadStarted_(false), isSyncReporter_(false)
{
    indexMap_ = {
        {MSPROF_REPORT_ACL_LEVEL, 0},
        {MSPROF_REPORT_MODEL_LEVEL, 0},
        {MSPROF_REPORT_NODE_LEVEL, 0},
        {MSPROF_REPORT_HCCL_NODE_LEVEL, 0},
        {MSPROF_REPORT_RUNTIME_LEVEL, 0}
    };
    reportTypeInfoMapVec_ = {
        {MSPROF_REPORT_ACL_LEVEL, std::vector<std::pair<uint32_t, std::string>>()},
        {MSPROF_REPORT_MODEL_LEVEL, std::vector<std::pair<uint32_t, std::string>>()},
        {MSPROF_REPORT_NODE_LEVEL, std::vector<std::pair<uint32_t, std::string>>()},
        {MSPROF_REPORT_HCCL_NODE_LEVEL, std::vector<std::pair<uint32_t, std::string>>()},
        {MSPROF_REPORT_RUNTIME_LEVEL, std::vector<std::pair<uint32_t, std::string>>()}
    };
}

ProfReporterMgr::~ProfReporterMgr()
{
    StopReporters();
    reportTypeInfoMap_.clear();
    reportTypeInfoMapVec_.clear();
}

int32_t ProfReporterMgr::Start()
{
    if (isUploadStarted_) {
        MSPROF_LOGW("type info upload has been started!");
        return PROFILING_SUCCESS;
    }

    Thread::SetThreadName(analysis::dvvp::common::config::MSVP_TYPE_INFO_UPLOAD_THREAD_NAME);

    if (Thread::Start() != PROFILING_SUCCESS) {
        MSPROF_LOGE("Failed to start the upload in ProfReporterMgr::Start().");
        return PROFILING_FAILED;
    } else {
        MSPROF_LOGI("Succeeded in starting the upload in ProfReporterMgr::Start().");
    }
    isUploadStarted_ = true;
    return PROFILING_SUCCESS;
}

void ProfReporterMgr::Run(const struct error_message::Context &errorContext)
{
    MsprofErrorManager::instance()->SetErrorContext(errorContext);
    while (!IsQuit()) {
        std::unique_lock<std::mutex> lk(notifyMtx_);
        cv_.wait_for(lk, std::chrono::seconds(1), [this] { return this->IsQuit(); });
        SaveData(false);
        HashData::instance()->SaveNewHashData(false);
    }
}

int32_t ProfReporterMgr::Stop()
{
    MSPROF_LOGI("Stop type info upload thread begin");
    if (!isUploadStarted_) {
        MSPROF_LOGE("type info upload thread not started");
        return PROFILING_FAILED;
    }
    isUploadStarted_ = false;

    int32_t ret = analysis::dvvp::common::thread::Thread::Stop();
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGE("type info upload Thread stop failed");
        return PROFILING_FAILED;
    }

    MSPROF_LOGI("Stop type info upload Thread success");
    return PROFILING_SUCCESS;
}

void ProfReporterMgr::SetSyncReporter()
{
    // set Sync Reporter. This will not start thread.
    isSyncReporter_ = true;
}

int32_t ProfReporterMgr::StartReporters()
{
    std::lock_guard<std::mutex> lk(startMtx_);
    if (isStarted_) {
        MSPROF_LOGI("The reporter have been started, don't need to repeat.");
        return PROFILING_SUCCESS;
    }

    if (reporters_.empty()) {
        for (auto &module : MSPROF_MODULE_REPORT_TABLE) {
            reporters_.emplace_back(MsprofReporter(module.name));
        }
    }

    MSPROF_LOGI("ProfReporterMgr start reporters");
    for (auto &report : reporters_) {
        if (report.StartReporter() != PROFILING_SUCCESS) {
            MSPROF_LOGE("ProfReporterMgr start reporters failed.");
            return PROFILING_FAILED;
        }
    }

    for (auto &level : DEFAULT_TYPE_INFO) {
        for (auto &type : level.second) {
            RegReportTypeInfo(level.first, type.first, type.second);
        }
    }
    if (!isSyncReporter_) {
        Start();
    }
    isStarted_ = true;
    return PROFILING_SUCCESS;
}

int32_t ProfReporterMgr::SendAdditionalData(SHARED_PTR_ALIA<ProfileFileChunk> fileChunk)
{
    return reporters_[ADDITIONAL].SendData(fileChunk);
}

void ProfReporterMgr::FlushAdditonalData()
{
    reporters_[ADDITIONAL].ForceFlush();
}

/**
 * @brief Flush all new reporter for subscribe scene
 */
void ProfReporterMgr::FlushAllReporter()
{
    for (auto &report : reporters_) {
        (void)report.ForceFlush();
    }
}

int32_t ProfReporterMgr::RegReportTypeInfo(uint16_t level, uint32_t typeId, const std::string &typeName)
{
    if (level == 0 && typeName.empty()) {
        MSPROF_LOGI("Register type info is invalid, level: [%u], type name %s", level, typeName.c_str());
        return PROFILING_FAILED;
    }
    MSPROF_LOGD("Register type info of reporter[%u], type id %u, type name %s", level, typeId, typeName.c_str());
    std::lock_guard<std::mutex> lk(regTypeInfoMtx_);
    reportTypeInfoMap_[level][typeId] = typeName;
    auto itr = std::find_if(reportTypeInfoMapVec_[level].begin(), reportTypeInfoMapVec_[level].end(),
        [typeId](const std::pair<uint32_t, std::string>& pair) { return pair.first == typeId; });
    if (itr != std::end(reportTypeInfoMapVec_[level])) {
        itr->second = typeName;
    } else {
        reportTypeInfoMapVec_[level].emplace_back(std::pair<uint32_t, std::string>(typeId, typeName));
    }
    return PROFILING_SUCCESS;
}

void ProfReporterMgr::GetReportTypeInfo(uint16_t level, uint32_t typeId, std::string& tag)
{
    std::lock_guard<std::mutex> lk(regTypeInfoMtx_);
    if (reportTypeInfoMap_.find(level) != reportTypeInfoMap_.end() &&
        reportTypeInfoMap_[level].find(typeId) != reportTypeInfoMap_[level].end()) {
        tag = reportTypeInfoMap_[level][typeId];
    } else {
        MSPROF_LOGW("This data can not found message: level[%u], type[%u].", level, typeId);
        tag = "invalid";
    }
}

uint64_t ProfReporterMgr::GetHashId(const std::string &info) const
{
    return HashData::instance()->GenHashId(info);
}

void ProfReporterMgr::FillData(const std::string &saveHashData,
    SHARED_PTR_ALIA<ProfileFileChunk> fileChunk, bool isLastChunk) const
{
    fileChunk->fileName = "unaging.additional.type_info_dic";
    fileChunk->offset = -1;
    fileChunk->isLastChunk = isLastChunk;
    fileChunk->chunk = saveHashData;
    fileChunk->chunkSize = saveHashData.size();
    fileChunk->chunkModule = FileChunkDataModule::PROFILING_IS_FROM_MSPROF_HOST;
    fileChunk->extraInfo = Utils::PackDotInfo(std::to_string(DEFAULT_HOST_ID), std::to_string(DEFAULT_HOST_ID));
}

void ProfReporterMgr::SaveData(bool isLastChunk)
{
    std::lock_guard<std::mutex> lk(regTypeInfoMtx_);
    SHARED_PTR_ALIA<Uploader> uploader = nullptr;
    UploaderMgr::instance()->GetUploader(std::to_string(DEFAULT_HOST_ID), uploader);
    if (uploader == nullptr) {
        return;
    }

    for (auto &typeInfo : reportTypeInfoMapVec_) {
        // combined hash map data
        std::string saveHashData;
        size_t currentHashSize = typeInfo.second.size();
        for (size_t i = indexMap_[typeInfo.first]; i < currentHashSize; i++) {
            saveHashData.append(std::to_string(typeInfo.first) + "_" + std::to_string(typeInfo.second[i].first) +
                                HASH_DIC_DELIMITER + typeInfo.second[i].second + "\n");
        }
        if (saveHashData.empty()) {
            continue;
        }
        indexMap_[typeInfo.first] = currentHashSize;
        // construct ProfileFileChunk data
        SHARED_PTR_ALIA<ProfileFileChunk> fileChunk = nullptr;
        MSVP_MAKE_SHARED0_NODO(fileChunk, ProfileFileChunk, break);
        FillData(saveHashData, fileChunk, isLastChunk);
        // upload ProfileFileChunk data
        int32_t ret = analysis::dvvp::transport::UploaderMgr::instance()->UploadData(
            std::to_string(DEFAULT_HOST_ID), fileChunk);
        if (ret != PROFILING_SUCCESS) {
            MSPROF_LOGE("Type info upload data failed, level: %u, dataLen:%zu bytes", typeInfo.first,
                saveHashData.size());
            continue;
        }
        MSPROF_EVENT("total_size_type_info[%u], save type info length: %zu bytes, type info size: %zu",
            typeInfo.first, saveHashData.size(), typeInfo.second.size());
    }
}

void ProfReporterMgr::NotifyQuit()
{
    std::lock_guard<std::mutex> lk(notifyMtx_);
    StopNoWait();
    cv_.notify_one();
}

int32_t ProfReporterMgr::StopReporters()
{
    std::lock_guard<std::mutex> lk(startMtx_);
    if (!isStarted_) {
        MSPROF_LOGI("The reporter isn't started, don't need to be stopped.");
        return PROFILING_SUCCESS;
    }
    if (!isSyncReporter_) {
        NotifyQuit();
        Stop();
    }
    MSPROF_LOGI("ProfReporterMgr stop reporters");
    isStarted_ = false;
    for (auto &report : reporters_) {
        if (report.StopReporter() != PROFILING_SUCCESS) {
            return PROFILING_FAILED;
        }
    }
    isSyncReporter_ = false;
    reporters_.clear();
    for (auto &index : indexMap_) {
        index.second = 0;
    }
    return PROFILING_SUCCESS;
}

/**
 * @name  FlushHostReporters
 * @brief Save type info dic data and flush data from report buffer api_event, compact and additional
 */
void ProfReporterMgr::FlushHostReporters()
{
    std::lock_guard<std::mutex> lk(startMtx_);
    if (!isStarted_) {
        MSPROF_LOGI("The reporter isn't started, don't need to flush.");
        return;
    }
    // Save type info dic data
    SaveData(true);
    // Flush new report data
    for (auto &report : reporters_) {
        (void)report.ForceFlush();
    }
}
}
}
}