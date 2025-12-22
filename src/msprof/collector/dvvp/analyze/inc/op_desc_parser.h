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

#ifndef ANALYSIS_DVVP_ANALYZE_OP_DESC_PARSER_H
#define ANALYSIS_DVVP_ANALYZE_OP_DESC_PARSER_H

#include <cstdint>
#include <map>
#include "acl_prof.h"
#include "singleton/singleton.h"
#include "utils/utils.h"

namespace Analysis {
namespace Dvvp {
namespace Analyze {
using namespace analysis::dvvp::common::utils;
using CONST_VOID_PTR = const void *;
using UINT32_T_PTR = uint32_t *;
using CHAR_PTR = char *;
using CONST_CHAR_PTR = const char *;
class OpDescParser : public analysis::dvvp::common::singleton::Singleton<OpDescParser> {
public:
    OpDescParser();
    ~OpDescParser() override {}

public:
    static uint32_t GetOpDescSize();
    static int32_t GetOpNum(CONST_VOID_PTR data, uint32_t len, UINT32_T_PTR opNum);
    static int32_t GetModelId(CONST_VOID_PTR data, uint32_t len, uint32_t index, UINT32_T_PTR modelId);
    static int32_t GetThreadId(CONST_VOID_PTR data, uint32_t len, uint32_t index, UINT32_T_PTR threadId);
    static int32_t GetDeviceId(CONST_VOID_PTR data, uint32_t len, uint32_t index, UINT32_T_PTR devId);
    static uint64_t GetOpStart(CONST_VOID_PTR data, uint32_t len, uint32_t index);
    static uint64_t GetOpEnd(CONST_VOID_PTR data, uint32_t len, uint32_t index);
    static uint64_t GetOpDuration(CONST_VOID_PTR data, uint32_t len, uint32_t index);
    static uint64_t GetOpExecutionTime(CONST_VOID_PTR data, uint32_t len, uint32_t index);
    static uint64_t GetOpCubeFops(CONST_VOID_PTR data, uint32_t len, uint32_t index);
    static uint64_t GetOpVectorFops(CONST_VOID_PTR data, uint32_t len, uint32_t index);
    static uint32_t GetOpFlag(CONST_VOID_PTR data, uint32_t len, uint32_t index);
    static const char *GetOpAttriValue(CONST_VOID_PTR data, uint32_t len, uint32_t index,
                                       aclprofSubscribeOpAttri attri);
    uint64_t SetOpTypeAndOpName(const std::string &opType, const std::string &opName);
    int32_t GetOpTypeLen(CONST_VOID_PTR data, uint32_t len, SIZE_T_PTR opTypeLen, uint32_t index);
    int32_t GetOpType(CONST_VOID_PTR data, uint32_t len, CHAR_PTR opType, uint32_t opTypeLen, uint32_t index);
    int32_t GetOpNameLen(CONST_VOID_PTR data, uint32_t len, SIZE_T_PTR opNameLen, uint32_t index);
    int32_t GetOpName(CONST_VOID_PTR data, uint32_t len, CHAR_PTR opName, uint32_t opNameLen, uint32_t index);

private:
    static int32_t CheckData(CONST_VOID_PTR data, uint32_t len);

private:
    std::mutex mtx_;
    uint64_t opIndex_;
    std::map<uint64_t, std::string> opNames_;   // opIndex, opName
    std::map<uint64_t, std::string> opTypes_;   // opIndex, opType
};
}  // namespace Analyze
}  // namespace Dvvp
}  // namespace Analysis

#endif
