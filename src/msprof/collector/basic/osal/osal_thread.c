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
#include "osal_thread.h"

int32_t OsalMutexInit(OsalMutex *mutex)
{
    return pthread_mutex_init(mutex, NULL);
}

int32_t OsalMutexLock(OsalMutex *mutex)
{
    return pthread_mutex_lock(mutex);
}

int32_t OsalMutexUnlock(OsalMutex *mutex)
{
    return pthread_mutex_unlock(mutex);
}

int32_t OsalMutexDestroy(OsalMutex *mutex)
{
    return pthread_mutex_destroy(mutex);
}

int32_t OsalCondInit(OsalCond *condition)
{
    return pthread_cond_init(condition, NULL);
}

int32_t OsalCondDestroy(OsalCond *condition)
{
    return pthread_cond_destroy(condition);
}

int32_t OsalCondSignal(OsalCond *condition)
{
    return pthread_cond_signal(condition);
}

VOID OsalCondWait(OsalCond *condition, OsalMutex *mutex)
{
    (void)pthread_cond_wait(condition, mutex);
}

int32_t OsalCreateThread(OsalThread *threadHandle, UserProcFunc func)
{
    if ((threadHandle == NULL) || (func == NULL)) {
        return OSAL_EN_INVALID_PARAM;
    }
    int32_t ret = pthread_create(threadHandle, NULL, func, NULL);
    if (ret != OSAL_EN_OK) {
        ret = OSAL_EN_ERROR;
    }

    return ret;
}
