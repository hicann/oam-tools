#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

import os
import sys
import logging
from dependency_parser import OpDependenciesParser


logger = logging.getLogger()
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
OP_CATEGORY_LIST = []
BASE_PATH = os.getenv('BASE_PATH')



if __name__ == '__main__':
    changed_files_info_file = sys.argv[1]
    changed_files = []
    if not os.path.exists(changed_files_info_file):
        logging.error("[ERROR] change file is not exist, can not get file change info in this pull request.")
        exit(1)
    with open(changed_files_info_file) as or_f:
        changed_files = or_f.readlines()
    parser = OpDependenciesParser(os.getenv('BUILD_PATH'))
    OP_CATEGORY_LIST.extend(parser.get_category_list())
    ops = set()
    for changed_file in changed_files:
        if not os.path.exists(r'{}'.format(changed_file.strip())):
            continue
        changed_file = str(os.path.relpath(changed_file, BASE_PATH)).strip()
        files = changed_file.split('/')
        if len(files) > 2 and files[0] in OP_CATEGORY_LIST:
            op_name = files[1]
            if op_name == 'common':
                op_name = files[0] + '.common'
            ops.add(op_name)

    (_, reverse_op_dependencies) = parser.get_dependencies_by_ops(ops) # 获取反向依赖
    (op_dependencies, _) = parser.get_dependencies_by_ops(reverse_op_dependencies) # 根据反向依赖，获取编译依赖
    compile_ops = ';'.join(list(set(op_dependencies)))
    print('%s:%s' % (';'.join(reverse_op_dependencies), compile_ops))
