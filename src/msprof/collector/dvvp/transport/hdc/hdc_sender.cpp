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

#include "hdc_sender.h"
#include "config/config.h"
#include "errno/error_code.h"
#include "message/codec.h"
#include "utils/utils.h"

namespace analysis {
namespace dvvp {
namespace transport {
using namespace analysis::dvvp::common::error;

HdcSender::HdcSender()
    : engineName_(""), chunkPool_(nullptr), sender_(nullptr), transport_(nullptr) {}

HdcSender::~HdcSender()
{
}

int32_t HdcSender::Init(SHARED_PTR_ALIA<ITransport> transport, const std::string &engineName)
{
    if (transport == nullptr || engineName.empty()) {
        MSPROF_LOGE("[Init]transport is null");
        return PROFILING_FAILED;
    }
    engineName_ = engineName;
    transport_ = transport;

    int32_t ret = SenderPool::instance()->Init();
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGE("Init sender pool failed");
        return PROFILING_FAILED;
    }
    const int32_t chunkPoolNum = 64; // 64 : pool num
    const int32_t chunkPoolSize = 64 * 1024; // 64 * 1024 chunk size:64K
    MSVP_MAKE_SHARED2(chunkPool_, analysis::dvvp::common::memory::ChunkPool, chunkPoolNum,
        chunkPoolSize, return PROFILING_FAILED);
    if (!(chunkPool_->Init())) {
        MSPROF_LOGE("Init chunk pool failed.");
        SenderPool::instance()->Uninit();
        return PROFILING_FAILED;
    }

    MSVP_MAKE_SHARED3(sender_, Sender, transport_, engineName_, chunkPool_, return PROFILING_FAILED);
    ret = sender_->Init();
    if (ret != PROFILING_SUCCESS) {
        MSPROF_LOGE("[HdcSender::Init]Sender init failed!");
        chunkPool_->Uninit();
        SenderPool::instance()->Uninit();
        return PROFILING_FAILED;
    }
    MSPROF_LOGI("[%s] Init.", engineName.c_str());
    return PROFILING_SUCCESS;
}

int32_t HdcSender::SendData(const std::string &jobCtx, const struct DataChunk &data)
{
    if (sender_ == nullptr) {
        MSPROF_LOGE("[HdcSender::SendData]sender_ is null");
        return PROFILING_FAILED;
    }

    if (sender_->Send(jobCtx, data) != PROFILING_SUCCESS) {
        MSPROF_LOGE("[HdcSender::SendData]parameters is invalid.");
        return PROFILING_FAILED;
    }
    return PROFILING_SUCCESS;
}

void HdcSender::Flush() const
{
    if (sender_ == nullptr) {
        MSPROF_LOGE("[HdcSender::Flush]sender_ is null");
        return;
    }
    sender_->Flush();
}

void HdcSender::Uninit() const
{
    MSPROF_LOGI("[HdcSender]Uninit begin.");
    if (sender_ != nullptr) {
        sender_->Uninit();
    }
    if (transport_ != nullptr) {
        transport_->CloseSession();
    }
    if (chunkPool_ != nullptr) {
        chunkPool_->Uninit();
    }
    SenderPool::instance()->Uninit();
    MSPROF_LOGI("[HdcSender]Uninit end.");
}
}
}
}