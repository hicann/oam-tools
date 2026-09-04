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

set -e

# 脚本功能：安装项目必备的 skills
# 默认技能技能列表
DEFAULT_SKILLS=("gitcode-pr" "gitcode-issue")

# 脚本所在目录的上上级目录为 .claude/skills/
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 先检测本仓已有哪些 skill：本仓已存在的 skill 一律不下载、不覆盖，
# 以保护本仓对 skill 的本地修改不被远端版本覆盖。
MISSING_SKILLS=()
for skill in "${DEFAULT_SKILLS[@]}"; do
    if [ -d "$SKILLS_DIR/$skill" ]; then
        echo "Skip '$skill': already exists in repo, keep local version (no download/overwrite)"
    else
        MISSING_SKILLS+=("$skill")
    fi
done

# 全部已存在则无需克隆，直接结束
if [ ${#MISSING_SKILLS[@]} -eq 0 ]; then
    echo "All default skills already present locally. Nothing to install."
    exit 0
fi

# 创建临时目录
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

# 克隆 skills 仓库（仅当存在缺失的 skill 时）
echo "Cloning skills repository..."
git clone --depth 1 https://gitcode.com/cann-agent/skills.git "$TEMP_DIR/skills"
if [ $? -ne 0 ]; then
    echo "Error: Failed to clone skills repository"
    exit 1
fi

# 检查 skills 目录是否存在
if [ ! -d "$TEMP_DIR/skills/skills" ]; then
    echo "Error: skills directory not found in repository"
    exit 1
fi

# 仅安装本仓缺失的 skill，已存在的不在此列表中，不会被覆盖
echo "Installing skills..."
for skill in "${MISSING_SKILLS[@]}"; do
    if [ -d "$TEMP_DIR/skills/skills/$skill" ]; then
        if ! cp -r "$TEMP_DIR/skills/skills/$skill" "$SKILLS_DIR/"; then
            echo "Error: Failed to install skill '$skill' to $SKILLS_DIR"
            exit 1
        fi
        echo "Installed skill: $skill"
    else
        echo "Warning: Skill '$skill' not found in repository"
    fi
done

echo "All skills installed successfully."
exit 0
