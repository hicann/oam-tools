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
 
#ifndef PROF_ACL_PLUGIN_H
#define PROF_ACL_PLUGIN_H
#include <stdint.h>
#include "singleton/singleton.h"
#include "prof_utils.h"
#include "transport.h"
namespace ProfAPI {
using VOID_PTR = void *;
using CHAR_PTR = char *;
using PROFAPI_SUBSCRIBECONFIG_CONST_PTR = const void *;
using PROFAPI_CONFIG_CONST_PTR = const void *;
using ProfAclInitFunc = int32_t (*) (uint32_t type, const char *path, uint32_t len);
using ProfAclCtrlFunc = int32_t (*) (uint32_t type, PROFAPI_CONFIG_CONST_PTR config);
using ProfAclFinalizeFunc = int32_t (*) (uint32_t type);
using ProfAclSetConfigFunc = int32_t (*) (uint32_t type, const char *config, uint32_t len);
using ProfAclSubscribeFunc = int32_t (*) (uint32_t type, uint32_t modelId, PROFAPI_SUBSCRIBECONFIG_CONST_PTR config);
using ProfAclUnSubscribeFunc = int32_t (*) (uint32_t type, uint32_t modelId);
using ProfOpSubscribeFunc = int32_t (*) (uint32_t devId, PROFAPI_SUBSCRIBECONFIG_CONST_PTR config);
using ProfOpUnSubscribeFunc = int32_t (*) (uint32_t devId);
using ProfAclDrvGetDevNumFunc = int32_t (*) ();
using ProfAclGetOpTimeFunc = uint64_t (*) (uint32_t type, const void *opInfo, size_t opInfoLen, uint32_t index);
using ProfAclGetIdFunc = size_t (*) (uint32_t type, const void *opInfo, size_t opInfoLen, uint32_t index);
using ProfAclGetOpValFunc = int32_t (*) (uint32_t type, const void *opInfo, size_t opInfoLen,
                                     uint32_t index, void *data, size_t len);
using ProfGetOpExecutionTimeFunc = uint64_t (*) (const void *data, uint32_t len, uint32_t index);
using ProfGetOpAttriValFunc = const char *(*) (uint32_t type, const void *opInfo, size_t opInfoLen,
                                               uint32_t index, uint32_t attri);
using ProfCreateTransportFunc = SHARED_PTR_ALIA<analysis::dvvp::transport::ITransport> (*)();
using ProfCreateTransportTypeFunc = ProfCreateTransportFunc (*)();
using ProfRegisterTransportFunc = void (*)(ProfCreateTransportFunc callback);
using ProfAclGetCompatibleFeaturesFunc = int32_t (*) (size_t *featuresSize, void **featuresData);
class ProfAclPlugin : public analysis::dvvp::common::singleton::Singleton<ProfAclPlugin> {
public:
    void ProfAclApiInit(VOID_PTR handle);
    int32_t ProfAclInit(uint32_t type, const char *profilerPath, uint32_t len);
    int32_t ProfAclStart(uint32_t type, PROFAPI_CONFIG_CONST_PTR profilerConfig);
    int32_t ProfAclStop(uint32_t type, PROFAPI_CONFIG_CONST_PTR profilerConfig);
    int32_t ProfAclFinalize(uint32_t type);
    int32_t ProfAclSubscribe(uint32_t type, uint32_t modelId, PROFAPI_SUBSCRIBECONFIG_CONST_PTR config);
    int32_t ProfAclUnSubscribe(uint32_t type, uint32_t modelId);
    int32_t ProfOpSubscribe(uint32_t devId, PROFAPI_SUBSCRIBECONFIG_CONST_PTR config);
    int32_t ProfOpUnSubscribe(uint32_t type);
    int32_t ProfAclDrvGetDevNum();
    int32_t ProfAclSetConfig(uint32_t configType, const char *config, size_t configLength);
    uint64_t ProfAclGetOpTime(uint32_t type, const void *opInfo, size_t opInfoLen, uint32_t index);
    size_t ProfAclGetId(uint32_t type, const void *opInfo, size_t opInfoLen, uint32_t index);
    int32_t ProfAclGetOpVal(uint32_t type, const void *opInfo, size_t opInfoLen,
                            uint32_t index, void *data, size_t len);
    uint64_t ProfGetOpExecutionTime(const void *data, uint32_t len, uint32_t index);
    const char *ProfGetOpAttriVal(uint32_t type, const void *opInfo, size_t opInfoLen,
                                  uint32_t index, uint32_t attri);
    int32_t ProfAclGetCompatibleFeatures(size_t *featuresSize, void **featuresData);
private:
    VOID_PTR msProfLibHandle_{nullptr};

    PTHREAD_ONCE_T profAclInitFlag_;
    PTHREAD_ONCE_T profAclStartFlag_;
    PTHREAD_ONCE_T profAclStopFlag_;
    PTHREAD_ONCE_T profAclFinalizeFlag_;
    PTHREAD_ONCE_T profAclSetConfigFlag_;
    PTHREAD_ONCE_T profAclSubscribeFlag_;
    PTHREAD_ONCE_T profAclUnSubscribeFlag_;
    PTHREAD_ONCE_T profOpSubscribeFlag_;
    PTHREAD_ONCE_T profOpUnSubscribeFlag_;
    PTHREAD_ONCE_T profAclDrvGetDevNumFlag_;
    PTHREAD_ONCE_T profAclGetOpTimeFlag_;
    PTHREAD_ONCE_T profAclGetIdFlag_;
    PTHREAD_ONCE_T profAclGetOpValFlag_;
    PTHREAD_ONCE_T profGetOpExecutionTimeFlag_;
    PTHREAD_ONCE_T profAclGetOpAttriValFlag_;
    PTHREAD_ONCE_T profAclGetCompatibleFeaturesFlags_;

    ProfAclInitFunc profAclInit_;
    ProfAclCtrlFunc profAclStart_;
    ProfAclCtrlFunc profAclStop_;
    ProfAclFinalizeFunc profAclFinalize_;
    ProfAclSetConfigFunc profAclSetConfig_;
    ProfAclSubscribeFunc profAclSubscribe_;
    ProfAclUnSubscribeFunc profAclUnSubscribe_;
    ProfOpSubscribeFunc profOpSubscribe_;
    ProfOpUnSubscribeFunc profOpUnSubscribe_;
    ProfAclDrvGetDevNumFunc profAclDrvGetNum_;
    ProfAclGetOpTimeFunc profAclGetOpTime_;
    ProfAclGetIdFunc profAclGetId_;
    ProfAclGetOpValFunc profAclGetOpVal_;
    ProfGetOpExecutionTimeFunc profGetOpExecutionTime_;
    ProfGetOpAttriValFunc profGetOpAttriVal_;
    ProfCreateTransportTypeFunc profCreateTransport_{nullptr};
    ProfRegisterTransportFunc profRegisterTransport_{nullptr};
    ProfAclGetCompatibleFeaturesFunc profAclGetCompatibleFeatures_;

    void LoadProfAclInit();
    void LoadProfAclStart();
    void LoadProfAclStop();
    void LoadProfAclFinalize();
    void LoadProfAclSetConfig();
    void LoadProfAclSubscribe();
    void LoadProfAclUnSubscribe();
    void LoadProfOpSubscribe();
    void LoadProfOpUnSubscribe();
    void LoadProfAclDrvGetDevNum();
    void LoadProfAclGetOpTime();
    void LoadProfAclGetId();
    void LoadProfAclGetOpVal();
    void LoadProfGetOpExecutionTime();
    void LoadProfGetOpAttriVal();
    void LoadProfCreateTransport();
    void LoadProfRegisterTransport();
    void LoadProfAclGetCompatibleFeatures();
};
}
#endif
