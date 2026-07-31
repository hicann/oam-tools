# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------

cmake_minimum_required(VERSION 3.15)
include(cmake/fetch_cann_cmake.cmake)
set(PKG_NAME oam)
project(Oam-Tools)

init_cann_project(PREPEND_MODULE_PATH)
add_cann_target_options()

set(CMAKE_C_FLAGS_RELEASE "")
set(CMAKE_CXX_FLAGS_RELEASE "")

include(cmake/intf_pub.cmake)

# install 参数
set(INSTALL_LIBRARY_DIR ${CMAKE_BINARY_DIR}/_CPack_Packages/makeself_staging)

# Ascend mode
if(DEFINED ENV{ASCEND_HOME_PATH})
  set(ASCEND_DIR $ENV{ASCEND_HOME_PATH})
else()
  if ("$ENV{USER}" STREQUAL "root")
    if(EXISTS /usr/local/Ascend/ascend-toolkit/latest)
      set(ASCEND_DIR /usr/local/Ascend/ascend-toolkit/latest)
    else()
      set(ASCEND_DIR /usr/local/Ascend/latest)
    endif()
  else()
    if(EXISTS $ENV{HOME}/Ascend/ascend-toolkit/latest)
      set(ASCEND_DIR $ENV{HOME}/Ascend/ascend-toolkit/latest)
    else()
      set(ASCEND_DIR $ENV{HOME}/Ascend/latest)
    endif()
  endif()
endif()
set(ASCEND_CANN_PACKAGE_PATH ${ASCEND_DIR})

include(version.cmake)
check_cann_pkg_build_deps("oam-tools")
add_cann_version_info_targets()


set(CMAKE_LIBRARY_PATH ${ASCEND_CANN_PACKAGE_PATH})
link_directories(
    ${ASCEND_CANN_PACKAGE_PATH}
    ${ASCEND_CANN_PACKAGE_PATH}/lib64
    ${ASCEND_CANN_PACKAGE_PATH}/devlib
)
set(CCACHE_PROGRAM "")
find_program(CCACHE_PROGRAM ccache)
if(CCACHE_PROGRAM)
    set(CMAKE_C_COMPILER_LAUNCHER ${CCACHE_PROGRAM})
    set(CMAKE_CXX_COMPILER_LAUNCHER ${CCACHE_PROGRAM})
endif()

if(PROJECT_SOURCE_DIR STREQUAL CMAKE_SOURCE_DIR)
  message(STATUS "compile project with library")
  option(BUILD_WITH_INSTALLED_DEPENDENCY_CANN_PKG "Build oam-tools with cann pkg" ON)
else()
  message(STATUS "compile project with src")
  option(BUILD_WITH_INSTALLED_DEPENDENCY_CANN_PKG "Build oam-tools with cann source" OFF)
endif()
set(OAM_TOOLS_DIR ${CMAKE_CURRENT_SOURCE_DIR})

# 在superbuild模式下，由CMake负责构建msprof wheel 和同步 msaccucmp/compare
include(cmake/build_submodules.cmake)

# 拉取并解压闭源包 bundle（原 install_bundle.sh）；须在下方 bundle/ 的 install() 之前。
include(cmake/install_bundle.cmake)

# protobuf — 通过 cann-cmake 的 add_cann_third_party 引入
add_cann_third_party(protobuf)

set(PROTOC_PROGRAM "")
get_target_property(PROTOC_PROGRAM host_protoc IMPORTED_LOCATION)
set(PROTOBUF_HOST_INCLUDE ${PROTOBUF_LIB_CACHE_DIR}/include)
message("PROTOC_PROGRAM: ${PROTOC_PROGRAM}")

include(cmake/third_party/protobuf_fun.cmake)

include(cmake/dependencies.cmake)
# 外部依赖库及编译选项
include(cmake/third_party/third_party_header_libs.cmake)

add_subdirectory(src/asys)
add_subdirectory(src/msaicerr)
add_subdirectory(src/hccl_test)
add_subdirectory(src/operator_cmp)

set(TOP_DIR "${CMAKE_CURRENT_SOURCE_DIR}" CACHE PATH "Project top directory")
set(HI_PYTHON "python" CACHE PATH "Python Path")
set(INSTALL_CONFIG_DIR cmake)
set(MSPROF_DIR ${CMAKE_CURRENT_SOURCE_DIR}/src/msprof)
set(PROF_BASIC_DIR "${MSPROF_DIR}/collector/basic")
set(TARGET_SYSTEM_NAME "Linux")
add_subdirectory(src/msprof/collector/dvvp/msprofbin)
add_subdirectory(src/msprof/collector/dvvp/acp)

if (ENABLE_COV OR ENABLE_UT)
    set(OAM_SRC_DIR ${CMAKE_CURRENT_SOURCE_DIR}/src)
    include(CMakePrintHelpers)
    add_cann_third_party(boost)
    add_cann_third_party(mockcpp)
    add_cann_third_party(gtest_shared)
    add_dependencies(GTestShared::gtest mockcpp)
    add_subdirectory(test)
endif()

# 拷贝闭源包到指定目录
set(BUNDLE_PKG ${CMAKE_CURRENT_SOURCE_DIR}/bundle)

# 拷贝 aml 目录内容
if(EXISTS "${BUNDLE_PKG}/aml")
    # AICore STL 形态目录(Ascend950)。目录名须与入口 so 里 SOC_PLATFORM_TABLE 的
    # formSubDir 逐字符一致(oam-tools-diag: aml_aicore_stl_platform.cpp)，
    # 形态 so / kernel so / 算子 .o / 算子输入数据(mx.bin)都放这里。
    set(_aml_stl_form_rel "tools/aml/lib64/aicore_stl/ascend950_aicore_stl")
    set(_aml_stl_form_dir "${INSTALL_LIBRARY_DIR}/${_aml_stl_form_rel}")
    # Ascend950形态 so / kernel so / 算子 .o 都在 aml/lib64/ascend950_aicore_stl/ 下，
    set(_aml_stl_bundle_form_dir "${BUNDLE_PKG}/aml/lib64/ascend950_aicore_stl")

    # [TEMP-STL-COMPAT] 临时兼容旧版 oam-tools-diag 包(无 AICore STL 产物)。
    # 后续改为强制校验时，删除本 set 及下面 3 处 _aml_stl_available 判断即可。
    if(EXISTS "${BUNDLE_PKG}/aml/lib64/libaml_aicore_stl.so")
        set(_aml_stl_available TRUE)
    else()
        set(_aml_stl_available FALSE)
        message(STATUS "AICore STL libs not in bundle, skip packaging them.")
    endif()

    file(COPY "${BUNDLE_PKG}/aml/lib64/plugin" DESTINATION ${INSTALL_LIBRARY_DIR}/tools/aml/lib64)
    # 如果 plugin/bin 存在，将其内容移动到 plugin 下并删除 bin
    set(_aml_plugin_bin "${INSTALL_LIBRARY_DIR}/tools/aml/lib64/plugin/bin")
    if(EXISTS "${_aml_plugin_bin}" AND IS_DIRECTORY "${_aml_plugin_bin}")
        # 防御性检查：仅删除位于本次构建目录下的 bin，避免 INSTALL_LIBRARY_DIR
        # 为空或被异常修改时，rm -rf 落到用户文件系统的真实路径上造成数据丢失
        get_filename_component(_aml_plugin_bin_abs "${_aml_plugin_bin}" REALPATH)
        get_filename_component(_build_dir_abs "${CMAKE_BINARY_DIR}" REALPATH)
        string(FIND "${_aml_plugin_bin_abs}" "${_build_dir_abs}/" _aml_under_build)
        if(NOT INSTALL_LIBRARY_DIR OR NOT _aml_under_build EQUAL 0)
            message(FATAL_ERROR
                "Refusing to remove '${_aml_plugin_bin_abs}': path is not under build "
                "directory '${_build_dir_abs}'. Check INSTALL_LIBRARY_DIR="
                "'${INSTALL_LIBRARY_DIR}'.")
        endif()
        execute_process(
            COMMAND ${CMAKE_COMMAND} -E copy_directory
                "${_aml_plugin_bin}"
                "${INSTALL_LIBRARY_DIR}/tools/aml/lib64/plugin"
        )
        # mx.bin 是 AICore STL 的算子输入，须与形态 so 同目录（入口 so 按
        # <自身目录>/<formSubDir>/ 定位数据文件），不能留在被摊平的 plugin/ 下。
        # 上面 copy_directory 会把它一并摊到 plugin/，此处挪到形态目录并清掉残留。
        if(_aml_stl_available AND EXISTS "${_aml_plugin_bin}/mx.bin")  # [TEMP-STL-COMPAT]
            file(COPY "${_aml_plugin_bin}/mx.bin"
                DESTINATION "${_aml_stl_form_dir}")
            execute_process(
                COMMAND ${CMAKE_COMMAND} -E rm -f
                    "${INSTALL_LIBRARY_DIR}/tools/aml/lib64/plugin/mx.bin"
            )
        endif()
        execute_process(
            COMMAND ${CMAKE_COMMAND} -E rm -rf "${_aml_plugin_bin}"
        )
    endif()
    unset(_aml_plugin_bin)

    # install() commands mirror file(COPY) so CPack's cmake --install step also stages these files
    # Guard: these two libs are required; fail loudly at configure time rather than producing
    # a broken run package that only crashes at runtime.
    foreach(_required_lib
        "${BUNDLE_PKG}/aml/lib64/libascend_ml.so"
        "${BUNDLE_PKG}/aml/lib64/libascend_ml_detect.so"
    )
        if(NOT EXISTS "${_required_lib}")
            message(FATAL_ERROR "Required AML library not found: ${_required_lib}")
        endif()
    endforeach()
    file(GLOB _aml_runtime_libs CONFIGURE_DEPENDS
        "${BUNDLE_PKG}/aml/lib64/libascend_ml*.so"
    )
    install(FILES ${_aml_runtime_libs}
        DESTINATION ${CMAKE_SYSTEM_PROCESSOR}-linux/lib64
        COMPONENT oam-tools
    )
    unset(_aml_runtime_libs)
    install(FILES
        ${BUNDLE_PKG}/aml/lib64/plugin/libascend_mix_test.so
        DESTINATION tools/aml/lib64/plugin
        COMPONENT oam-tools
    )
    if(EXISTS "${BUNDLE_PKG}/aml/lib64/plugin/bin/matmul_input_0.bin")
        install(FILES
            ${BUNDLE_PKG}/aml/lib64/plugin/bin/matmul_input_0.bin
            ${BUNDLE_PKG}/aml/lib64/plugin/bin/matmul_input_1.bin
            DESTINATION tools/aml/lib64/plugin
            COMPONENT oam-tools
        )
    endif()
    # AICore STL(Ascend950)算子输入数据:与形态 so 同目录，入口 so 按
    # <自身目录>/<formSubDir>/mx.bin 读取。与 bin/ 下的 matmul_input_*.bin 同源。
    if(_aml_stl_available AND EXISTS "${BUNDLE_PKG}/aml/lib64/plugin/bin/mx.bin")  # [TEMP-STL-COMPAT]
        install(FILES
            ${BUNDLE_PKG}/aml/lib64/plugin/bin/mx.bin
            DESTINATION ${_aml_stl_form_rel}
            COMPONENT oam-tools
        )
    endif()
    install(FILES
        ${BUNDLE_PKG}/aml/lib64/plugin_v2/libascend_stress_detect.so
        DESTINATION tools/aml/lib64/plugin_v2
        COMPONENT oam-tools
    )

    # AICore STL 自诊断三层框架(源自 oam-tools-diag，随 bundle 发布到 aml/lib64):
    #   入口 libaml_aicore_stl.so → host libaml_stl_ascend950.so → kernel libaml_stl_kernel_ascend950.so
    # 分级放置以便后续按 SoC 形态扩展:
    #   aicore_stl/                      入口层，平台无关
    #   aicore_stl/ascend950_aicore_stl/ 形态相关(host so + kernel so + 11 个算子 .o)
    # 形态子目录名须与入口 so 里 SOC_PLATFORM_TABLE 的 formSubDir 逐字符一致
    # (oam-tools-diag: aml_aicore_stl_platform.cpp)：入口 so 用 dladdr 定位自身目录后
    # 拼 <自身目录>/<formSubDir>/ 加载形态 so，名字不一致会在运行期 dlopen 失败。
    # 新增形态时在 aicore_stl/ 下新建对应形态子目录即可。
    if(_aml_stl_available)  # [TEMP-STL-COMPAT]
    # Guard：形态 so 与 kernel so 必需，缺失即在 configure 期报错，避免产出运行期才崩的残缺包。
    foreach(_required_stl_lib
        "${_aml_stl_bundle_form_dir}/libaml_stl_ascend950.so"
        "${_aml_stl_bundle_form_dir}/libaml_stl_kernel_ascend950.so"
    )
        if(NOT EXISTS "${_required_stl_lib}")
            message(FATAL_ERROR "Required AICore STL library not found: ${_required_stl_lib}")
        endif()
    endforeach()
    # 入口层:平台无关，放 aicore_stl/
    install(FILES
        ${BUNDLE_PKG}/aml/lib64/libaml_aicore_stl.so
        DESTINATION tools/aml/lib64/aicore_stl
        COMPONENT oam-tools
    )
    # 形态层(Ascend950):host so + kernel so，放 aicore_stl/ascend950_aicore_stl/
    install(FILES
        ${_aml_stl_bundle_form_dir}/libaml_stl_ascend950.so
        ${_aml_stl_bundle_form_dir}/libaml_stl_kernel_ascend950.so
        DESTINATION ${_aml_stl_form_rel}
        COMPONENT oam-tools
    )
    # 11 个算子 .o(算子目录名生成，随形态增删会变)，用 GLOB 全量纳入。
    # 按形态子目录取，避免将来多形态时把别的形态的 .o 一并捞进本形态目录。
    file(GLOB _stl_kernel_objs CONFIGURE_DEPENDS
        "${_aml_stl_bundle_form_dir}/*.o"
    )
    install(FILES ${_stl_kernel_objs}
        DESTINATION ${_aml_stl_form_rel}
        COMPONENT oam-tools
    )
    unset(_stl_kernel_objs)
    endif()  # [TEMP-STL-COMPAT]
    unset(_aml_stl_available)
    unset(_aml_stl_form_rel)
    unset(_aml_stl_form_dir)
    unset(_aml_stl_bundle_form_dir)
endif()

# 拷贝 built-in 目录
# 显式指定 440 文件权限 / 555 目录权限，与主线 CANN 包对 opp/built-in/op_impl 子树的
# 权限模型对齐。否则 cmake install(DIRECTORY) 默认会把文件重写成 644、目录 755。
# 注：文件 440（owner/group r）+ 目录 555（world rx）这个不对称组合是有意为之 ——
# 主线 CANN 包对该子树就是此模型（other 可遍历目录但读不到文件内容），
# 切勿轻易改成对称形式（如全 550 / 全 444），会破坏与主线的兼容性。
if(EXISTS "${BUNDLE_PKG}/built-in")
    install(DIRECTORY ${BUNDLE_PKG}/built-in/op_impl/ai_core/tbe
        DESTINATION opp/built-in/op_impl/ai_core
        COMPONENT oam-tools
        FILE_PERMISSIONS OWNER_READ GROUP_READ
        DIRECTORY_PERMISSIONS OWNER_READ OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
        PATTERN "op_api" EXCLUDE
    )
    install(FILES
        ${BUNDLE_PKG}/built-in/op_impl/ai_core/tbe/op_api/lib/linux/${CMAKE_SYSTEM_PROCESSOR}/libopapi_oam.so
        DESTINATION ${CMAKE_SYSTEM_PROCESSOR}-linux/lib64
        COMPONENT oam-tools
    )
endif()

# 创建 bin pkg_inc 目录
file(MAKE_DIRECTORY ${INSTALL_LIBRARY_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/bin)
file(MAKE_DIRECTORY ${INSTALL_LIBRARY_DIR}/${CMAKE_SYSTEM_PROCESSOR}-linux/pkg_inc)

# 打run包
include(cmake/package.cmake)
pack_built_in()
