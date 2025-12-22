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

#ifndef MSPROF_ENGINE_RPC_DATA_HANDLE_H
#define MSPROF_ENGINE_RPC_DATA_HANDLE_H

#include "utils/utils.h"
#include "hdc/hdc_sender.h"

namespace Msprof {
namespace Engine {
using namespace analysis::dvvp::common::error;
using namespace analysis::dvvp::transport;

class IDataHandle {
public:
    IDataHandle() {}
    virtual ~IDataHandle() {}

public:
    virtual int32_t Init() = 0;
    virtual int32_t UnInit() = 0;
    virtual int32_t Flush() = 0;
    virtual int32_t SendData(CONST_VOID_PTR data, uint32_t dataLen, const std::string fileName = "",
        const std::string jobCtx = "") = 0;
};

class HdcDataHandle : public IDataHandle {
public:
    HdcDataHandle(const std::string &moduleNameWithId, int32_t hostPid, int32_t devId);
    ~HdcDataHandle() override;

public:
    int32_t Init() override;
    int32_t UnInit() override;
    int32_t Flush() override;
    int32_t SendData(CONST_VOID_PTR data, uint32_t dataLen, const std::string fileName = "",
        const std::string jobCtx = "") override;

private:
    std::string moduleNameWithId_; // like: DATA_PREPROCESS-80858-3
    int32_t hostPid_;
    int32_t devId_;
    SHARED_PTR_ALIA<HdcSender> hdcSender_;
};

class RpcDataHandle {
public:
    RpcDataHandle(const std::string &moduleNameWithId, const std::string &module, int32_t hostPid, int32_t devId);
    virtual ~RpcDataHandle();

public:
    int32_t Init() const;
    int32_t UnInit() const;
    int32_t Flush() const;
    int32_t SendData(CONST_VOID_PTR data, uint32_t dataLen, const std::string fileName, const std::string jobCtx);
    bool IsReady() const;
    int32_t TryToConnect();

private:
    std::string moduleNameWithId_; // like: DATA_PREPROCESS-80858-3
    std::string module_; // the module name, like: DATA_PREPROCESS
    int32_t hostPid_;
    int32_t devId_;
    SHARED_PTR_ALIA<IDataHandle> dataHandle_;
};
}}
#endif
