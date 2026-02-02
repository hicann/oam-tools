#!/bin/bash
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

# 获取当前工作目录
WORKING_DIR=$(pwd)
echo "工作目录: $WORKING_DIR"

# Define default values
BUILD_TYPE="${1:-release}"
ARCH="${2:-x86_64}"
BASE_NAME="cann-oam-tools"
SOURCE_URL="https://ascend-cann.obs.cn-north-4.myhuaweicloud.com/CANN/20260202_newest"
BUNDLE_DIR="bundle"
OUTPUT_FILE="${BASE_NAME}-release-${ARCH}.tar.gz"

# Function to display usage
usage() {
    echo "Usage: $0 [build_type] [architecture]"
    echo "Example: $0 release x86_64"
    echo "Defaults: build_type=release, architecture=x86_64"
    echo ""
}
# Display current directory
echo "Current directory: $(pwd)"
echo "Building $BASE_NAME package release for $ARCH"
echo ""

# Create necessary directories
echo "Creating directories..."
mkdir -p "$BUNDLE_DIR"

if [ -f "./build/$OUTPUT_FILE" ]; then
    # Using compiled oam-tools.tar.gz
    echo "Using compiled $OUTPUT_FILE"
    chmod 755 ./build/$OUTPUT_FILE
    cp ./build/$OUTPUT_FILE $OUTPUT_FILE
    if [ $? -ne 0 ]; then
        echo "Error: Failed to cp $OUTPUT_FILE"
        exit 1 
    fi
else
    # 添加了 --tries, --timeout 和 --connect-timeout
    wget -O "$OUTPUT_FILE" "$SOURCE_URL/$OUTPUT_FILE" \
        --no-check-certificate \
        --tries=1 \
        --timeout=5 \
        --connect-timeout=5

    if [ $? -ne 0 ]; then
        echo "Error: Failed to get $OUTPUT_FILE"
        # 如果下载不完整，建议清理可能存在的残留文件
        [ -f "$OUTPUT_FILE" ] && rm "$OUTPUT_FILE"
        rm -rf "$BUNDLE_DIR"
        exit 1 
    fi
fi

tar -zxvf "$OUTPUT_FILE" -C "$BUNDLE_DIR"> /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "Package verification successful"
    echo "Extracted to: $OUTPUT_FILE"

    # 显示解压后的文件结构
    echo "Extracted directory structure:"
    find "$BUNDLE_DIR" -type f | head -20
else
    rm -rf "$BUNDLE_DIR"
    echo "Warning: Package verification failed"
fi

# Remove the downloaded installer
echo "Removing downloaded installer..."
rm -f "$OUTPUT_FILE"

echo ""
echo "=============================================="
echo "Package created successfully!"
echo "Location: $BUNDLE_DIR/"
echo "Package type: Tool Compatibility Package"
echo "Version: $VERSION"
echo "Architecture: $ARCH"
echo "=============================================="