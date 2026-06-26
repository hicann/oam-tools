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
#ifndef TEST_UT_MSPROF_STUB_DOMAIN_TRANSPORT_TRANSPORT_H
#define TEST_UT_MSPROF_STUB_DOMAIN_TRANSPORT_TRANSPORT_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MAX_FILE_CHUNK_NAME_LENGTH 128U

typedef enum {
    FILE_TRANSPORT,
    FLSH_TRANSPORT
} TransportType;

typedef enum {
    PROF_CTRL_DATA = 2,
    PROF_DEVICE_DATA = 3,
    PROF_HOST_DATA = 5,
} FileChunkType;

typedef struct {
    uint8_t isLastChunk;
    uint8_t deviceId;
    uint16_t chunkType;
    uint64_t chunkSize;
    uint32_t offset;
    uint8_t *chunk;
    char fileName[MAX_FILE_CHUNK_NAME_LENGTH];
} ProfFileChunk;

typedef struct {
    int32_t (*SendBuffer)(ProfFileChunk *chunk, const char *dir);
    int32_t (*Flush)();
} Transport;

#ifdef __cplusplus
}
#endif

#endif
