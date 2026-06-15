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
#include "ctrl_files_dumper.h"
#include "message/prof_params.h"
#include "osal.h"
#include "utils/utils.h"
#include "transport/transport.h"
#include "message/data_define.h"
#include "config/config.h"
#include "uploader_mgr.h"

namespace analysis {
namespace dvvp {
namespace transport {

namespace {
static constexpr int TIME_US = 1000000;
}

using namespace analysis::dvvp::common::config;
using namespace analysis::dvvp::common::utils;
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::transport;

int CtrlFilesDumper::DumpCollectionTimeInfo(uint32_t deviceId, bool isHostProfiling, bool isStart)
{
    std::string devIdStr = std::to_string(deviceId);
    auto collectionTime = Utils::GetHostTime();
    MSPROF_LOGI("[DumpCollectionTimeInfo]collectionTime:%s us, isStart:%d", collectionTime.c_str(), isStart);
    analysis::dvvp::message::CollectionTimeInfo timeInfo;
    if (!isStart) {
        timeInfo.collectionTimeEnd = collectionTime;
        timeInfo.collectionDateEnd = Utils::TimestampToTime(collectionTime, TIME_US);
    } else {
        timeInfo.collectionTimeBegin = collectionTime;
        timeInfo.collectionDateBegin = Utils::TimestampToTime(collectionTime, TIME_US);
    }
    timeInfo.clockMonotonicRaw = std::to_string(Utils::GetClockMonotonicRaw());
    NanoJson::Json timeInfoJson;
    timeInfo.ToObject(timeInfoJson);
    std::string content = timeInfoJson.ToString();
    MSPROF_LOGI("[DumpCollectionTimeInfo]content:%s", content.c_str());
    SHARED_PTR_ALIA<analysis::dvvp::message::JobContext> jobCtx = nullptr;
    MSVP_MAKE_SHARED0(jobCtx, analysis::dvvp::message::JobContext, return PROFILING_FAILED);
    jobCtx->job_id = devIdStr;
    std::string fileName;
    GeneratorCollectionTimeInfoName(fileName, devIdStr, isHostProfiling, isStart);
    FileDataParams fileDataParams(fileName, true, FileChunkDataModule::PROFILING_IS_CTRL_DATA);
    MSPROF_LOGI("[CreateCollectionTimeInfo]job_id: %s,fileName: %s", devIdStr.c_str(), fileName.c_str());
    int32_t ret = UploaderMgr::instance()->UploadCtrlFileData(devIdStr, content, fileDataParams, jobCtx);
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGE("Failed to upload data for %s", fileName.c_str());
        return PROFILING_FAILED;
    }
    return PROFILING_SUCCESS;
}

void CtrlFilesDumper::GeneratorCollectionTimeInfoName(std::string &fileName, const std::string &deviceId,
                                                      bool isHostProfiling, bool isStart)
{
    std::string prefix = isStart ? "start_info" : "end_info";
    fileName.append(prefix);
    if (!isHostProfiling) {
        fileName.append(".").append(deviceId);
    }
}
} // namespace transport
} // namespace dvvp
} // namespace analysis
