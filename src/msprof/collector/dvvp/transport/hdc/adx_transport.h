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

#ifndef ANALYSIS_DVVP_TRANSPORT_ADX_TRANSPORT_H
#define ANALYSIS_DVVP_TRANSPORT_ADX_TRANSPORT_H
#include "transport.h"
#include "hdc_api.h"

namespace analysis {
namespace dvvp {
namespace transport {
using namespace analysis::dvvp::common::utils;
using TLV_REQ_PTR = struct tlv_req *;
using CONST_TLV_REQ_PTR = const struct tlv_req *;
using TLV_REQ_2PTR = struct tlv_req **;
class AdxTransport : public ITransport {
public:
    int32_t SendBuffer(CONST_VOID_PTR buffer, int32_t length) override = 0;
    int32_t SendBuffer(SHARED_PTR_ALIA<analysis::dvvp::ProfileFileChunk> fileChunkReq) override = 0;
    int32_t CloseSession() override = 0;
    void WriteDone() override {}
    virtual int32_t SendAdxBuffer(IdeBuffT out, int32_t outLen) = 0;
    virtual int32_t RecvPacket(TLV_REQ_2PTR packet, uint32_t timeout = 0) = 0;
    virtual void DestroyPacket(TLV_REQ_PTR packet) = 0;
};
}  // namespace transport
}  // namespace dvvp
}  // namespace analysis

#endif
