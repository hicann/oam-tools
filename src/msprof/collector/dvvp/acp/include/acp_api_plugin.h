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
#ifndef PROF_ACP_PLUGIN_H
#define PROF_ACP_PLUGIN_H
#include <cstdint>
#include <map>
#include "singleton/singleton.h"
#include "runtime/base.h"
#include "runtime/kernel.h"
#include "runtime/mem.h"
#include "prof_utils.h"

namespace Collector {
namespace Dvvp {
namespace Acp {
using VOID_PTR = void*;
using CONST_VOID_PTR = const VOID_PTR;
using RtSetDeviceFunc = rtError_t (*)(int32_t devId);
using RtStreamSynchronizeFunc = rtError_t (*)(rtStream_t stream);
using RtDevBinaryRegisterFunc = rtError_t (*)(const rtDevBinary_t *, void **);
using RtDevBinaryUnRegisterFunc = rtError_t (*)(void *);
using RtFunctionRegisterFunc = rtError_t (*)(void *, const void *, const char_t *, const void *, uint32_t);
using RtRegisterAllKernelFunc = rtError_t (*)(const rtDevBinary_t *, void **);
using RtGetBinaryDeviceBaseAddressFunc = rtError_t (*)(const void* handle, void** launchBase);
using RtProfSetProSwitchFunc = rtError_t (*)(void *data, uint32_t len);
using RtKernelLaunchFunc = rtError_t (*)(const void *stubFunc, uint32_t blockDim, void *args, uint32_t argsSize,
                                         rtSmDesc_t *smDesc, rtStream_t stm);
using RtKernelLaunchWithHandleFunc = rtError_t (*)(void *hdl, const uint64_t tilingKey, uint32_t blockDim,
                                                   rtArgsEx_t *argsInfo, rtSmDesc_t *smDesc, rtStream_t stm,
                                                   const void *kernelInfo);
using RtKernelLaunchWithHandleV2Func = rtError_t (*)(void *hdl, const uint64_t tilingKey, uint32_t blockDim,
                                                     rtArgsEx_t *argsInfo, rtSmDesc_t *smDesc, rtStream_t stm,
                                                     const rtTaskCfgInfo_t *cfgInfo);
using RtKernelLaunchWithFlagFunc = rtError_t (*)(const void *stubFunc, uint32_t blockDim, rtArgsEx_t *argsInfo,
                                                 rtSmDesc_t *smDesc, rtStream_t stm, uint32_t flags);
using RtKernelLaunchWithFlagV2Func = rtError_t (*)(const void *stubFunc, uint32_t blockDim, rtArgsEx_t *argsInfo,
                                                   rtSmDesc_t *smDesc, rtStream_t stm, uint32_t flags,
                                                   const rtTaskCfgInfo_t *cfgInfo);
using RtMallocFunc = rtError_t (*)(void **devPtr, uint64_t size, rtMemType_t type, const uint16_t moduleId);
using RtFreeFunc = rtError_t (*)(void *devPtr);
using RtMemcpyAsyncFunc = rtError_t (*)(void *dst, uint64_t destMax, const void *src, uint64_t cnt,
    rtMemcpyKind_t kind, rtStream_t stm);

struct ApiStubInfo {
    std::string funcName;
    VOID_PTR funcAddr{ nullptr };
    ApiStubInfo(const std::string name, VOID_PTR addr) : funcName(name), funcAddr(addr) {}
};

class AcpApiPlugin : public analysis::dvvp::common::singleton::Singleton<AcpApiPlugin> {
public:
    AcpApiPlugin();
    ~AcpApiPlugin() override;
    VOID_PTR GetPluginApiStubFunc(const std::string funcName);
    rtError_t ApiRtStreamSynchronize(rtStream_t stream);
    rtError_t ApiRtGetBinaryDeviceBaseAddress(CONST_VOID_PTR handle, VOID_PTR &launchBase);
private:
    void LoadRuntimeApi();
    ProfAPI::PTHREAD_ONCE_T apiLoadFlag_;
    VOID_PTR acpRuntimeLibHandle_{ nullptr };
    RtStreamSynchronizeFunc rtStreamSynchronize_{ nullptr };
    RtGetBinaryDeviceBaseAddressFunc rtGetBinaryDeviceBaseAddress_{ nullptr };
    std::map<std::string, ApiStubInfo> apiStubInfoMap_;
};

}  // namespace Acp
}  // namespace Dvvp
}  // namespace Collector
#endif