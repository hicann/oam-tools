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

#ifndef BASIC_OSAL_OSAL_MEM_H
#define BASIC_OSAL_OSAL_MEM_H
#include "osal.h"

#ifdef __cplusplus
extern "C" {
#endif  // __cpluscplus

OsalVoidPtr OsalMalloc(size_t size);
OsalVoidPtr OsalCalloc(size_t size);
VOID OsalFree(OsalVoidPtr ptr);
VOID OsalConstFree(const void* ptr);

#define OSAL_MEM_FREE(ptr) do {  \
    OsalFree(ptr);               \
    (ptr) = NULL;                  \
} while (0)

#ifdef __cplusplus
}
#endif  // __cpluscplus
#endif