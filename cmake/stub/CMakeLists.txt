# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
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

add_library(ascend_hal_headers INTERFACE)
target_include_directories(ascend_hal_headers INTERFACE
    $<BUILD_INTERFACE:${ASCEND_CANN_PACKAGE_PATH}/include/driver>
    $<INSTALL_INTERFACE:include>
    $<INSTALL_INTERFACE:include/ascend_hal>
    $<INSTALL_INTERFACE:include/ascend_hal/driver>
)

get_filename_component(LOCAL_STUB_PATH "${CMAKE_CURRENT_LIST_DIR}" ABSOLUTE)
set(LOCAL_H2C_PY_PATH ${LOCAL_STUB_PATH}/h2c.py)

add_library(ascend_hal_stub SHARED)

set(LOCAL_ASCEND_H_FILE_PATH ${ASCEND_CANN_PACKAGE_PATH}/include/driver/ascend_hal.h)
set(LOCAL_ASCEND_H_FILE_PATH1 ${ASCEND_CANN_PACKAGE_PATH}/include/driver/ascend_hal_external.h)
set(LOCAL_ASCEND_C_FILE_PATH ${CMAKE_CURRENT_BINARY_DIR}/ascend_hal.c)

add_custom_command(
    OUTPUT ${LOCAL_ASCEND_C_FILE_PATH}
    COMMAND ${HI_PYTHON} ${LOCAL_H2C_PY_PATH} -i ${LOCAL_ASCEND_H_FILE_PATH} ${LOCAL_ASCEND_H_FILE_PATH1} -o ${LOCAL_ASCEND_C_FILE_PATH}
)

target_sources(ascend_hal_stub PRIVATE
    ${LOCAL_ASCEND_C_FILE_PATH}
)

target_include_directories(ascend_hal_stub PRIVATE
    ${MSPROF_DIR}/inc
)

target_link_libraries(ascend_hal_stub
    PRIVATE
        intf_pub_cxx11
        #allow function redefine
        -Wl,-z,muldefs
    PUBLIC
        ascend_hal_headers
)

set_target_properties(ascend_hal_stub
    PROPERTIES
    OUTPUT_NAME ascend_hal
)

set(PKG_NAME ascend_hal)
install(TARGETS ascend_hal_stub ascend_hal_headers
    EXPORT ${PKG_NAME}-targets
    LIBRARY DESTINATION ${INSTALL_LIBRARY_DIR}/stub OPTIONAL COMPONENT opensdk
)
message("INSTALL_LIBRARY_DIR : ${INSTALL_LIBRARY_DIR}")
install(TARGETS ascend_hal_stub ascend_hal_headers
    LIBRARY DESTINATION ${INSTALL_LIBRARY_DIR}/${CMAKE_SYSTEM_PROCESSOR}/stub OPTIONAL COMPONENT opensdk
)
install(FILES   ${ASCEND_CANN_PACKAGE_PATH}/include/driver/ascend_hal_define.h
                ${ASCEND_CANN_PACKAGE_PATH}/include/driver/ascend_hal_error.h
                ${ASCEND_CANN_PACKAGE_PATH}/include/driver/ascend_hal.h
                ${ASCEND_CANN_PACKAGE_PATH}/include/driver/ascend_hal_external.h
    DESTINATION ${INSTALL_INCLUDE_DIR}/ascend_hal/driver COMPONENT opensdk EXCLUDE_FROM_ALL
)