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

# 获取路径下的所有子项
file(GLOB CHILDREN_FILE_AND_FOLDER "${CMAKE_CURRENT_LIST_DIR}/common/ascend*")
message("CHILDREN_FILE_AND_FOLDER : ${CHILDREN_FILE_AND_FOLDER}")
 
# 初始化一个空列表来存储文件夹名称
set(FOLDERS_LIST "")
 
# 遍历每个子项
foreach(CHILD ${CHILDREN_FILE_AND_FOLDER})
    # 检查是否是文件夹
    if(IS_DIRECTORY ${CHILD})
        # 提取文件夹名称
        get_filename_component(FOLDER_NAME ${CHILD} NAME)
        # 将文件夹名称添加到列表中
        list(APPEND FOLDERS_LIST ${FOLDER_NAME})
    endif()
endforeach()
# 输出文件夹列表
message("Found folders: ${FOLDERS_LIST}")
 
set(ASYS_CHIP_HANDLER_LIST "")
set(ASYS_CHIP_HANDLER_IMPORT "")
foreach(CHIP_TYPE_FOLDER ${FOLDERS_LIST})
    include(${CMAKE_CURRENT_LIST_DIR}/common/${CHIP_TYPE_FOLDER}/${CHIP_TYPE_FOLDER}.cmake)
endforeach()
 
string(REPLACE ";" ", \n            " ASYS_CHIP_HANDLER_LIST_STR "${ASYS_CHIP_HANDLER_LIST}")
string(REPLACE ";" "\n" ASYS_CHIP_HANDLER_IMPORT_STR "${ASYS_CHIP_HANDLER_IMPORT}")
message("ASYS_CHIP_HANDLER_LIST_STR: ${ASYS_CHIP_HANDLER_LIST_STR}")
message("ASYS_CHIP_HANDLER_IMPORT_STR: ${ASYS_CHIP_HANDLER_IMPORT_STR}")
 
configure_file(
    ${CMAKE_CURRENT_LIST_DIR}/common/chip_handler.py.in  # 输入模板路径
    ${CMAKE_CURRENT_LIST_DIR}/common/chip_handler.py     # 输出文件路径
    @ONLY                                    # 只替换 @变量@ 格式的占位符
)
 
add_custom_command(OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/chip_handler.py
    COMMAND cp -f ${CMAKE_CURRENT_LIST_DIR}/common/chip_handler.py ${CMAKE_CURRENT_BINARY_DIR}/chip_handler.py
)
add_custom_target(chip_handler DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/chip_handler.py)
 
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/chip_handler.py DESTINATION ${INSTALL_LIBRARY_DIR} OPTIONAL)