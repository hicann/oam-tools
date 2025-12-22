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

#ifndef MSPROF_ENGINE_RPC_DUMPER_H
#define MSPROF_ENGINE_RPC_DUMPER_H

#include "data_dumper.h"
#include "receive_data.h"
#include "rpc_data_handle.h"
#include "proto/profiler.pb.h"

namespace Msprof {
namespace Engine {
using namespace analysis::dvvp::proto;
class RpcDumper : public DataDumper {
public:
    /**
    * @brief RpcDumper: the construct function
    * @param [in] module: the name of the plugin
    */
    explicit RpcDumper(const std::string &module);
    ~RpcDumper() override;

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

protected:
    void WriteDone() override;
    /**
     * @brief Run: the thread function for deal with user data
     */
    void Run(const struct error_message::Context &errorContext) override;
private:
    /**
    * @brief Dump: transfer FileChunkReq
    * @param [in] message: the user data to be send to remote host
    * @return : success return PROFILING_SUCCESS, failed return PROFIING_FAILED
    */
    int32_t Dump(std::vector<SHARED_PTR_ALIA<FileChunkReq>> &messages);
    int32_t Dump(std::vector<SHARED_PTR_ALIA<ProfileFileChunk>> &message) override;
    int32_t DumpData(std::vector<ReporterDataChunk> &message, SHARED_PTR_ALIA<FileChunkReq> fileChunk);
    void RunDefaultProfileData(std::vector<SHARED_PTR_ALIA<FileChunkReq>>& fileChunks);
    void DoReportRun() override;
    void TimedTask() override;
    int32_t GetNameAndId(const std::string &module);

private:
    std::string module_; // the module name, like: DATA_PREPROCESS
    std::string moduleNameWithId_; // like: DATA_PREPROCESS-80858-3
    int32_t hostPid_;
    int32_t devId_;
    SHARED_PTR_ALIA<RpcDataHandle> dataHandle_;
};
}}
#endif
