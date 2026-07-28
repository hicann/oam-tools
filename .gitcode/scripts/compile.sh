#!/bin/bash
# ----------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
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
set -e
echo $(grep -E "^VERSION_ID=" /etc/os-release | cut -d'"' -f2)
if [[ "${task_name}" == *ubuntu24* ]]; then
    export PATH=/opt/buildtools/python-3.10.2/bin:$PATH
    sudo update-alternatives --set gcc /usr/bin/gcc-14
else
    if [[ -f "/opt/rh/devtoolset-7/enable" ]]; then
        echo "source devtoolset"
        source /opt/rh/devtoolset-7/enable
    fi
fi

rm -rf /home/jenkins/opensource/ubuntu20/lib_cache/protobuf*
rm -rf /home/jenkins/opensource/lib_cache/protobuf*

if [[ "${task_name}" =~ Compile_Ascend_X86_ubuntu24 ]]; then
    sed -i "1i set(CMAKE_EXPORT_COMPILE_COMMANDS ON)" "CMakeLists.txt"
    echo "api-check=compile" >> "${ATOMGIT_OUTPUT}"
else
    echo "api-check=continue" >> "${ATOMGIT_OUTPUT}"
fi

if [ "${target_branch}" = "master" ]; then
    if [[ "${task_name}" == *X86* ]]; then
        export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libsqlite3.so
    else
        export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libsqlite3.so
    fi
fi

gcc --version
source /home/jenkins/Ascend/cann/bin/setenv.bash
set +e

echo "exec cmd: [bash build.sh --make_clean --cann_3rd_lib_path="/home/jenkins/opensource"]"
bash build.sh --make_clean --cann_3rd_lib_path="/home/jenkins/opensource"
ret=$?

exit $ret
