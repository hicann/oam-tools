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
#ifndef _TSD_STUB_H_
#define _TSD_STUB_H_

void* mmDlsymTsd(void* handle, const char* funcName);
void* mmDlsymTsdError(void* handle, const char* funcName);
int32_t mmDlclose(void* handle);
void* mmDlopen(const char* fileName, int mode);
uint32_t TsdCapabilityGetStubError(const uint32_t logicDeviceId, const int32_t type, const uint64_t ptr);
uint32_t TsdProcessOpenStubError(const uint32_t logicDeviceId, ProcOpenArgs* openArgs);
uint32_t TsdGetProcListStatusError(const uint32_t logicDeviceId, ProcStatusParam* pidInfo, const uint32_t arrayLen);

#endif
