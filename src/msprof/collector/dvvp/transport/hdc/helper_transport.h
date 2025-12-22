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

#ifndef ANALYSIS_DVVP_COMMON_HELPER_TRANSPORT_H
#define ANALYSIS_DVVP_COMMON_HELPER_TRANSPORT_H

#include "file_slice.h"
#include "utils/utils.h"
#include "transport/transport.h"
#include "adx_transport.h"
#include "prof_hal_api.h"

namespace analysis {
namespace dvvp {
namespace transport {

class HelperTransport : public ITransport {
public:
    explicit HelperTransport(HDC_SESSION session, bool isClient = false, HDC_CLIENT client = nullptr);
    ~HelperTransport() override;

public:
    int32_t SendBuffer(CONST_VOID_PTR buffer, int32_t length) override;
    int32_t SendBuffer(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq) override;
    void WriteDone() override;
    int32_t CloseSession() override;
    int32_t PackingData(ProfHalStruct &package, SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq);
    int32_t SendPackingData(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq,
        ProfHalStruct &package, SHARED_PTR_ALIA<ProfHalTlv> tlvbuff);
    void FillLastChunk(uint32_t stackLength, ProfHalStruct &package) const;
    int32_t SendAdxBuffer(VOID_PTR out, int32_t outLen) const;
    int32_t ReceivePacket(ProfHalTlv **packet) const;
    void FreePacket(ProfHalTlv *packet) const;

private:
    void Destroy();

private:
    HDC_SESSION session_;
    bool isClient_;
    HDC_CLIENT client_;
    std::mutex sessionMtx_;
    bool isLastChunk_;
};

class HelperTransportFactory {
public:
    HelperTransportFactory() {}
    virtual ~HelperTransportFactory() {}

public:
    SHARED_PTR_ALIA<ITransport> CreateHdcClientTransport(int32_t hostPid, int32_t devId, HDC_CLIENT client) const;
    SHARED_PTR_ALIA<HelperTransport> CreateHdcServerTransport(int32_t logicDevId, HDC_SERVER server) const;
};

int32_t SendBufferPacket(HelperTransport &transport, VOID_PTR buffer, int32_t length);
}  // namespace transport
}  // namespace dvvp
}  // namespace analysis

#endif
