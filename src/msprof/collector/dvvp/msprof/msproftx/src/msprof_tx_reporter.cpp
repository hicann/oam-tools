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

#include "msprof_tx_reporter.h"
#include <cstdint>
#include "runtime/base.h"
#include "errno/error_code.h"
#include "utils/utils.h"
#include "msprof_dlog.h"
#include "securec.h"

using namespace analysis::dvvp::common::error;
namespace Msprof {
namespace MsprofTx {
MsprofTxReporter::MsprofTxReporter() : isInit_(false), reporterCallback_(nullptr) {}

MsprofTxReporter::~MsprofTxReporter() {}

int32_t MsprofTxReporter::Init()
{
    if (reporterCallback_ == nullptr) {
        MSPROF_LOGE("[Init]ReporterCallback_ is nullptr!");
        return PROFILING_FAILED;
    }

    isInit_ = true;
    MSPROF_LOGI("[Init]MsprofTxReporter init success.");
    return PROFILING_SUCCESS;
}

int32_t MsprofTxReporter::UnInit()
{
    if (reporterCallback_ == nullptr) {
        MSPROF_LOGE("[UnInit]ReporterCallback_ is nullptr!");
        return PROFILING_FAILED;
    }

    isInit_ = false;
    MSPROF_LOGI("[UnInit]ReporetCallback UnInit success.");
    return PROFILING_SUCCESS;
}

int32_t MsprofTxReporter::Report(MsprofTxInfo &data) const
{
    if (reporterCallback_ == nullptr) {
        MSPROF_LOGE("[TxReport]ReporterCallback_ is nullptr!");
        return MSPROF_ERROR;
    }

    if (!isInit_) {
        MSPROF_LOGE("[TxReport]Reporter is not inited!");
        return MSPROF_ERROR;
    }

    MsprofAdditionalInfo info;
    info.level = MSPROF_REPORT_TX_LEVEL;
    info.type = MSPROF_REPORT_TX_BASE_TYPE;
    info.dataLen = sizeof(data);
    errno_t ret = memcpy_s(info.data, MSPROF_ADDTIONAL_INFO_DATA_LENGTH, &data, sizeof(MsprofTxInfo));
    FUNRET_CHECK_EXPR_ACTION(ret != EOK, return MSPROF_ERROR, "[TxReport]Failed to memcpy for tx info data.");
    return reporterCallback_(1, &info, sizeof(info));
}

void MsprofTxReporter::SetReporterCallback(const ProfAdditionalBufPushCallback func)
{
    reporterCallback_ = func;
}
} // namespace MsprofTx
} // namespace Msprof
