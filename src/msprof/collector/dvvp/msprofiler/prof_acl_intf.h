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

#ifndef PROF_ACL_API_H
#define PROF_ACL_API_H
namespace Msprof {
namespace Engine {
namespace Intf {
enum ProfType {
    ACL_API_TYPE,
    ACL_GRPH_API_TYPE,
    OP_TYPE
};

enum AclProfOpType {
    ACL_OP_DESC_SIZE,
    ACL_OP_TYPE_LEN,
    ACL_OP_NUM,
    ACL_OP_TYPE,
    ACL_OP_NAME_LEN,
    ACL_OP_NAME,
    ACL_OP_START,
    ACL_OP_END,
    ACL_OP_DURATION,
    ACL_OP_GET_FLAG,
    ACL_OP_GET_ATTR,
};
}
}
}
#endif
