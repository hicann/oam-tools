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

#ifndef BASIC_OSAL_OSAL_THREAD_H
#define BASIC_OSAL_OSAL_THREAD_H
#include <pthread.h>
#include "osal.h"

#ifdef __cplusplus
extern "C" {
#endif  // __cpluscplus

typedef pthread_mutex_t OsalMutex;
typedef pthread_cond_t OsalCond;

int32_t OsalMutexInit(OsalMutex *mutex);
int32_t OsalMutexLock(OsalMutex *mutex);
int32_t OsalMutexUnlock(OsalMutex *mutex);
int32_t OsalMutexDestroy(OsalMutex *mutex);
int32_t OsalCondInit(OsalCond *condition);
int32_t OsalCondDestroy(OsalCond *condition);
int32_t OsalCondSignal(OsalCond *condition);
VOID OsalCondWait(OsalCond *condition, OsalMutex *mutex);
int32_t OsalCreateThread(OsalThread *threadHandle, UserProcFunc func);

#ifdef __cplusplus
}
#endif  // __cpluscplus
#endif