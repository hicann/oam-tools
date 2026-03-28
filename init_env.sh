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

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

CANN_VERSION="8.5.0"
CHIP_TYPE="910b"
CANN_BASE_URL="https://ascend.devcloud.huaweicloud.com/artifactory/cann-run/software"
INSTALL_PATH="${INSTALL_PATH:-/usr/local/Ascend}"

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_command() { command -v "$1" &>/dev/null; }

get_arch() {
    local arch=$(uname -m)
    case $arch in
        x86_64) echo "x86_64" ;;
        aarch64) echo "aarch64" ;;
        *) log_error "Unsupported architecture: $arch"; return 1 ;;
    esac
}

detect_cann_path() {
    local paths=(
        "/usr/local/Ascend/ascend-toolkit/latest"
        "/usr/local/Ascend/latest"
        "/usr/local/Ascend/cann-${CANN_VERSION}"
        "/usr/local/Ascend/cann-${CANN_VERSION}-beta.1"
        "/usr/local/Ascend/cann"
        "$HOME/Ascend/ascend-toolkit/latest"
        "$HOME/Ascend/latest"
        "$HOME/Ascend/cann-${CANN_VERSION}"
        "$HOME/Ascend/cann-${CANN_VERSION}-beta.1"
        "$HOME/Ascend/cann"
    )

    for p in "${paths[@]}"; do
        if [ -d "$p" ] && [ -f "$p/bin/setenv.bash" ]; then
            echo "$p"
            return 0
        fi
    done

    if [ -d "/usr/local/Ascend" ]; then
        for d in /usr/local/Ascend/ascend-toolkit/*; do
            [ -d "$d" ] && [ -f "$d/bin/setenv.bash" ] && echo "$d" && return 0
        done
        for d in /usr/local/Ascend/cann-*; do
            [ -d "$d" ] && [ -f "$d/bin/setenv.bash" ] && echo "$d" && return 0
        done
    fi
    return 1
}

install_cann() {
    log_info "Checking CANN installation..."

    local existing_cann=$(detect_cann_path)
    if [ -n "$existing_cann" ]; then
        log_info "CANN already installed at: $existing_cann"
        return 0
    fi

    log_info "CANN not found, starting installation..."
    log_warn "This will download ~3GB of packages"

    local arch=$(get_arch)
    local download_dir="/tmp/cann_install"
    mkdir -p "$download_dir"
    cd "$download_dir"

    local toolkit_pkg="Ascend-cann-toolkit_${CANN_VERSION}_linux-${arch}.run"
    local ops_pkg="Ascend-cann-${CHIP_TYPE}-ops_${CANN_VERSION}_linux-${arch}.run"
    local toolkit_url="${CANN_BASE_URL}/${CANN_VERSION}/${arch}/${toolkit_pkg}"
    local ops_url="${CANN_BASE_URL}/${CANN_VERSION}/${arch}/${ops_pkg}"

    if [ ! -f "$toolkit_pkg" ]; then
        log_info "Downloading CANN toolkit (${arch})..."
        log_info "URL: $toolkit_url"
        wget -q --show-progress --no-check-certificate -O "$toolkit_pkg" "$toolkit_url" || {
            log_error "Failed to download toolkit"
            return 1
        }
    fi

    if [ ! -f "$ops_pkg" ]; then
        log_info "Downloading CANN ops (${CHIP_TYPE}, ${arch})..."
        log_info "URL: $ops_url"
        wget -q --show-progress --no-check-certificate -O "$ops_pkg" "$ops_url" || {
            log_error "Failed to download ops"
            return 1
        }
    fi

    log_info "Installing CANN toolkit..."
    chmod +x "$toolkit_pkg"
    ./$toolkit_pkg --full --install-path="$INSTALL_PATH" || {
        log_error "Failed to install toolkit"
        return 1
    }

    log_info "Installing CANN ops..."
    chmod +x "$ops_pkg"
    ./$ops_pkg --install --install-path="$INSTALL_PATH" || {
        log_warn "Ops installation may have issues (this can be normal on non-NPU systems)"
    }

    log_info "Cleaning up..."
    rm -f "$toolkit_pkg" "$ops_pkg"
    cd - > /dev/null

    log_info "CANN installation completed"
}

setup_cann_env() {
    log_info "Setting up CANN environment..."

    CANN_PATH=$(detect_cann_path)
    if [ -z "$CANN_PATH" ]; then
        log_error "CANN installation not found after installation!"
        return 1
    fi

    log_info "CANN path: $CANN_PATH"
    export ASCEND_HOME_PATH="$CANN_PATH"

    if [ -f "$CANN_PATH/bin/setenv.bash" ]; then
        source "$CANN_PATH/bin/setenv.bash"
        log_info "Sourced setenv.bash"
    fi

    local pkg_inc="$CANN_PATH/pkg_inc"
    local arch_inc=""
    
    if [ -d "$CANN_PATH/x86_64-linux/include" ]; then
        arch_inc="$CANN_PATH/x86_64-linux/include"
    elif [ -d "$CANN_PATH/aarch64-linux/include" ]; then
        arch_inc="$CANN_PATH/aarch64-linux/include"
    fi

    if [ -n "$arch_inc" ] && [ -d "$arch_inc" ]; then
        mkdir -p "$pkg_inc"
        for dir in mmpa fmk ts adump; do
            if [ ! -e "$pkg_inc/$dir" ] && [ -d "$arch_inc/$dir" ]; then
                ln -sf "$arch_inc/$dir" "$pkg_inc/$dir" 2>/dev/null && \
                    log_info "Linked $dir"
            fi
        done
    fi
}

install_system_deps() {
    log_info "Checking system dependencies..."

    if check_command apt-get; then
        apt-get update -qq 2>/dev/null
        local pkgs=""
        check_command curl || pkgs="$pkgs curl"
        check_command wget || pkgs="$pkgs wget"
        check_command git || pkgs="$pkgs git"
        check_command cmake || pkgs="$pkgs cmake"
        check_command make || pkgs="$pkgs make"
        check_command g++ || pkgs="$pkgs g++"
        check_command ccache || pkgs="$pkgs ccache"
        
        if [ -n "$pkgs" ]; then
            log_info "Installing:$pkgs"
            apt-get install -y -qq $pkgs 2>/dev/null || log_warn "Some packages may have failed"
        fi
    elif check_command yum; then
        local pkgs=""
        check_command curl || pkgs="$pkgs curl"
        check_command wget || pkgs="$pkgs wget"
        check_command git || pkgs="$pkgs git"
        check_command cmake || pkgs="$pkgs cmake"
        check_command make || pkgs="$pkgs make"
        check_command g++ || pkgs="$pkgs gcc-c++"
        
        if [ -n "$pkgs" ]; then
            log_info "Installing:$pkgs"
            yum install -y -q $pkgs 2>/dev/null || log_warn "Some packages may have failed"
        fi
    fi

    log_info "cmake: $(cmake --version 2>&1 | head -1)"
    log_info "g++: $(g++ --version 2>&1 | head -1)"
    check_command ccache && log_info "ccache: available" || log_warn "ccache: not installed"
}

install_python_deps() {
    log_info "Checking Python dependencies..."

    local python="python3"
    check_command python3 || python="python"
    
    log_info "Python: $($python --version 2>&1)"

    local required=("pytest>=9.0.1" "coverage>=7.10.0" "pytest-cov>=7.0.0")
    local to_install=()

    for pkg in "${required[@]}"; do
        local name=$(echo "$pkg" | sed 's/>=.*//')
        $python -c "import $name" 2>/dev/null || to_install+=("$pkg")
    done

    if [ ${#to_install[@]} -ne 0 ]; then
        log_info "Installing Python packages: ${to_install[*]}"
        $python -m pip install --upgrade pip -q 2>/dev/null || true
        $python -m pip install "${to_install[@]}" -q 2>/dev/null || \
            log_warn "Some Python packages may have failed to install"
    else
        log_info "All Python dependencies satisfied"
    fi

    check_command pytest && log_info "pytest: $(pytest --version 2>&1 | head -1)"
    check_command coverage && log_info "coverage: $(coverage --version 2>&1 | head -1)"
}

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "oam-tools development environment setup script"
    echo ""
    echo "Options:"
    echo "  --cann-version VERSION   CANN version (default: ${CANN_VERSION})"
    echo "  --chip-type TYPE         Chip type: 910b, 910_93, etc. (default: ${CHIP_TYPE})"
    echo "  --install-path PATH      Installation path (default: ${INSTALL_PATH})"
    echo "  --skip-cann              Skip CANN installation"
    echo "  --help                   Show this help"
    echo ""
    echo "Examples:"
    echo "  $0                       # Install with defaults"
    echo "  $0 --skip-cann           # Skip CANN, install only deps"
    echo "  $0 --chip-type 910_93    # Use 910_93 ops package"
    echo ""
}

main() {
    local SKIP_CANN=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --cann-version)
                CANN_VERSION="$2"
                shift 2
                ;;
            --chip-type)
                CHIP_TYPE="$2"
                shift 2
                ;;
            --install-path)
                INSTALL_PATH="$2"
                shift 2
                ;;
            --skip-cann)
                SKIP_CANN=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_warn "Unknown option: $1"
                shift
                ;;
        esac
    done

    echo ""
    echo "=========================================="
    echo "  oam-tools Development Environment Setup"
    echo "=========================================="
    echo ""
    echo "Configuration:"
    echo "  CANN Version:  ${CANN_VERSION}"
    echo "  Chip Type:     ${CHIP_TYPE}"
    echo "  Install Path:  ${INSTALL_PATH}"
    echo ""

    local work_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$work_dir"
    log_info "Working directory: $work_dir"

    install_system_deps

    if [ "$SKIP_CANN" = true ]; then
        log_info "Skipping CANN installation (--skip-cann)"
    else
        install_cann
    fi

    setup_cann_env
    install_python_deps

    echo ""
    log_info "=========================================="
    log_info "  Development environment ready!"
    log_info "=========================================="
    echo ""
    echo "Next steps:"
    echo "  bash build.sh          # Build project"
    echo "  bash build.sh -u       # Build and run UT"
    echo "  bash build.sh -u --cov # Build with coverage"
    echo ""
}

main "$@"
