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

#ifndef MSPROF_ENGINE_UPLOADER_DUMPER_H
#define MSPROF_ENGINE_UPLOADER_DUMPER_H

#include <memory>
#include "prof_reporter.h"
#include "data_dumper.h"

namespace Msprof {
namespace Engine {
class UploaderDumper : public DataDumper {
public:
    /**
    * @brief UploaderDumper: the construct function
    * @param [in] module: the name of the plugin
    */
    explicit UploaderDumper(const std::string &module);
    virtual ~UploaderDumper();

public:
    /**
    * @brief Report: API for user to report data to profiling
    * @param [in] rData: the data from user
    * @return : success return PROFILING_SUCCESS, failed return PROFIING_FAILED
    */
    int32_t Report(CONST_REPORT_DATA_PTR rData) override;

    /**
    * @brief Start: create a TCP collection to PROFILING SERVER
    *               start a new thread to deal with data from user
    * @return : success return PROFILING_SUCCESS, failed return PROFIING_FAILED
    */
    int32_t Start() override;

    /**
    * @brief Stop: stop the thread to deal with data
    *              disconnect the TCP to PROFILING SERVER
    */
    int32_t Stop() override;

    /**
    * @brief Flush: wait all datas to be send to remove host
    *               then send a FileChunkFlushReq data to remote host tell it data report finished
    * @return : success return PROFILING_SUCCESS, failed return PROFIING_FAILED
    */
    int32_t Flush() override;

    uint32_t GetReportDataMaxLen() const override;

    /**
    * @brief SendData: use interface dump to send data
    */
    int32_t SendData(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunk) override;

protected:
    virtual void WriteDone();
    /**
     * @brief Run: the thread function for deal with user data
     */
    void Run(const struct error_message::Context &errorContext) override;
private:
    /**
    * @brief Dump: transfer ProfileFileChunk
    * @param [in] message: the user data to be send to remote host
    * @return : success return PROFILING_SUCCESS, failed return PROFIING_FAILED
    */
    int32_t Dump(std::vector<SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk>> &messages) override;
    virtual void TimedTask();
    void AddToUploader(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> message) const;

private:
    std::string module_; // the module name
    bool needCache_;
    static const size_t MAX_CACHE_SIZE = 1024; // cached 1024 messages at most
    std::mutex mtx_;
    // model load data of Framework
    std::map<std::string, std::list<SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk>>> modelLoadData_;
    // model load data of Framework {deviceId: [dynProf_1th:FileChunkReq1, dynProf_2th:FileChunkReq2, ...]}}
    std::map<std::string, std::list<std::map<int32_t, SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk>>>> cachedMsg_;
    // model load data cached
    std::map<std::string, std::list<SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk>>> modelLoadDataCached_;
};
}}
#endif
