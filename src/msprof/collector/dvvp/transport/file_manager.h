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

#ifndef ANALYSIS_DVVP_TRANSPORT_FILE_MANAGER_H
#define ANALYSIS_DVVP_TRANSPORT_FILE_MANAGER_H
#include <map>
#include "singleton.h"
#include "transport.h"
#include "file_interface.h"
namespace analysis {
namespace dvvp {
namespace transport {
class FileManager : public analysis::dvvp::common::singleton::Singleton<FileManager> {
public:
    FileManager();
    ~FileManager() override;
    int32_t InitFileTransport(uint32_t deviceId, const char *flushDir, const char *storageLimit);
    int32_t SendBuffer(ProfFileChunk* chunk);

private:
    std::map<uint32_t, SHARED_PTR_ALIA<ITransport>> transportMap_;
    std::mutex fileMtx_;
};
}  // namespace transport
}  // namespace dvvp
}  // namespace analysis

#endif