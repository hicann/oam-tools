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

#ifndef AICPUFW_CUSTOM_API_STRUCT_H
#define AICPUFW_CUSTOM_API_STRUCT_H

#ifdef __cplusplus
extern "C" {
#endif

struct event_ack {
    unsigned int device_id;
    unsigned int event_id;
    unsigned int subevent_id;
    char* msg;
    unsigned int msg_len;
};

#ifdef __cplusplus
}
#endif
#endif