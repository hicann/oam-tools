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

#ifndef CTRL_FILES_DUMPER_H
#define CTRL_FILES_DUMPER_H
#include <string>
#include <cstring>
#include "singleton/singleton.h"

namespace analysis {
namespace dvvp {
namespace transport {
class CtrlFilesDumper : public analysis::dvvp::common::singleton::Singleton<CtrlFilesDumper> {
public:
    CtrlFilesDumper() {}
    virtual ~CtrlFilesDumper() {}
    
    int DumpCollectionTimeInfo(uint32_t deviceId, bool isHostProfiling, bool isStart);
private:
    void GeneratorCollectionTimeInfoName(std::string &fileName, const std::string &deviceId,
                                         bool isHostProfiling, bool isStart);
};

} // namespace transport
} // namespace dvvp
} // namespace analysis

#endif // CTRL_FILES_DUMPER_H