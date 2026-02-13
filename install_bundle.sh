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

# Define current work path
WORKING_DIR=$(pwd)
echo "工作目录: $WORKING_DIR"

# Define default values
BUILD_TYPE="${1:-release}"
ARCH="${2:-x86_64}"
BASE_NAME="cann-oam-tools"

# Base url
OBS_BASE_URL="https://ascend-cann.obs.cn-north-4.myhuaweicloud.com/CANN"
# Stable tar.gz url
STABLE_URL="https://ascend-cann.obs.cn-north-4.myhuaweicloud.com/CANN/20260213_newest/cann-oam-tools-release-${ARCH}.tar.gz"

BUNDLE_DIR="bundle"
OUTPUT_FILE="${BASE_NAME}-${BUILD_TYPE}-${ARCH}.tar.gz"

# Function to display usage
usage() {
    echo "Usage: $0 [build_type] [architecture]"
    echo "Example: $0 release x86_64"
    echo "Defaults: build_type=release, architecture=x86_64"
    echo ""
}

# Display current directory
echo "Current directory: $(pwd)"
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
    # Get date str, work for different os and bash env
    CURRENT_DATE_STR=$(date +%Y%m%d)
    
    # Define newest tar.gz url
    URL_TODAY="${OBS_BASE_URL}/${CURRENT_DATE_STR}_newest/cann-oam-tools-release-${ARCH}.tar.gz"
    
    download_success=false

    try_download() {
        local url=$1
        local label=$2
        echo "----------------------------------------------"
        echo "Attempting to download $label..."
        echo "URL: $url"
        
        wget -O "$OUTPUT_FILE" "$url" \
            --no-check-certificate \
            --tries=1 \
            --timeout=5 \
            --connect-timeout=5
        return $?
    }

    if try_download "$URL_TODAY" "TODAY'S PACKAGE"; then
        echo "Success: Downloaded today's package."
        download_success=true
    else
        echo "Notice: Today's package not found or download failed."
        if try_download "$STABLE_URL" "STABLE PACKAGE"; then
            echo "Success: Downloaded stable package."
            download_success=true
        else
            echo "Error: Both today's package and stable package failed to download."
        fi
    fi

    if [ "$download_success" = false ]; then
        echo "Error: Failed to get $OUTPUT_FILE from any source."
        [ -f "$OUTPUT_FILE" ] && rm "$OUTPUT_FILE"
        rm -rf "$BUNDLE_DIR"
        exit 1 
    fi
fi

tar -zxvf "$OUTPUT_FILE" -C "$BUNDLE_DIR"> /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "Package verification successful"
    echo "Extracted to: $OUTPUT_FILE"

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
echo "Final Status: DONE"
echo "Location: $BUNDLE_DIR/"
echo "Architecture: $ARCH"
echo "=============================================="