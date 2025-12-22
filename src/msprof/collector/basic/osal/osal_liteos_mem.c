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

#include "osal_mem.h"
#include "securec.h"
#include "hal_ts.h"
#include "los_typedef.h"
#define EN_OK LOS_OK

OsalVoidPtr OsalMalloc(size_t size)
{
    void *ptr = NULL;
    return (halHostMemAlloc(&ptr, size, 0) == EN_OK) ? ptr : NULL;
}

OsalVoidPtr OsalCalloc(size_t size)
{
    OsalVoidPtr val = NULL;
    val = OsalMalloc(size);
    if (val == NULL) {
        return NULL;
    }

    int32_t err = memset_s(val, size, 0, size);
    if (err != EOK) {
        OSAL_MEM_FREE(val);
        return NULL;
    }

    return val;
}

VOID OsalFree(OsalVoidPtr ptr)
{
    halHostMemFree(ptr);
}

VOID OsalConstFree(const void* ptr)
{
    halHostMemFree(ptr);
}