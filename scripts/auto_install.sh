#!/bin/bash
# ROAS Discord Bot v2.4.4 跨平台自動安裝腳本
# Task ID: 2 - 自動化部署和啟動系統開發
# 
# Daniel - DevOps 專家
# 提供跨平台自動安裝功能，支援 Docker、UV、Python 等核心依賴

set -euo pipefail

# 腳本元資料
SCRIPT_NAME="ROAS Bot Auto Installer"
SCRIPT_VERSION="2.4.4"
SUPPORTED_PLATFORMS="Linux, macOS, Windows (Git Bash/WSL)"

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 系統檢測變數
OS_TYPE=""
OS_VERSION=""
ARCH=""
PACKAGE_MANAGER=""
IS_ADMIN=false
HAS_SUDO=false

# 安裝選項
INSTALL_DOCKER=true
INSTALL_UV=true  
INSTALL_PYTHON=false  # 預設不安裝 Python，假設已存在
FORCE_INSTALL=false
DRY_RUN=false
VERBOSE=false

# 函數：顯示使用說明
show_usage() {
    cat << EOF
$SCRIPT_NAME v$SCRIPT_VERSION

用法: $0 [選項]

自動安裝選項:
  --docker-only        僅安裝 Docker
  --uv-only           僅安裝 UV Package Manager
  --python-also       同時安裝 Python（如果不存在）
  --all               安裝所有組件
  
安裝控制:
  -f, --force         強制重新安裝（即使已存在）
  -n, --dry-run       模擬安裝，不實際執行
  --no-docker         跳過 Docker 安裝
  --no-uv             跳過 UV 安裝
  
系統選項:
  -v, --verbose       顯示詳細安裝過程
  -h, --help          顯示此說明
  --check-system      僅檢查系統相容性，不安裝
  
支援平台: $SUPPORTED_PLATFORMS

範例:
  $0                    # 自動安裝 Docker 和 UV
  $0 --docker-only      # 僅安裝 Docker
  $0 --all --force      # 強制重新安裝所有組件
  $0 --dry-run -v       # 查看將要執行的安裝步驟
  $0 --check-system     # 檢查系統相容性
EOF
}

# 函數：日誌記錄
log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case $level in
        "INFO")  echo -e "${BLUE}[INFO]${NC} ${timestamp} - $message" ;;
        "WARN")  echo -e "${YELLOW}[WARN]${NC} ${timestamp} - $message" ;;
        "ERROR") echo -e "${RED}[ERROR]${NC} ${timestamp} - $message" ;;
        "SUCCESS") echo -e "${GREEN}[SUCCESS]${NC} ${timestamp} - $message" ;;
        "DEBUG") if [[ "$VERBOSE" == "true" ]]; then echo -e "${PURPLE}[DEBUG]${NC} ${timestamp} - $message"; fi ;;
    esac
}

# 函數：檢測作業系統和架構
detect_system() {
    log "INFO" "正在檢測系統環境..."
    
    # 檢測作業系統
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS_TYPE="linux"
        if command -v lsb_release &> /dev/null; then
            OS_VERSION=$(lsb_release -ds)
        elif [[ -f /etc/os-release ]]; then
            OS_VERSION=$(grep PRETTY_NAME /etc/os-release | cut -d'"' -f2)
        else
            OS_VERSION="Unknown Linux"
        fi
        
        # 檢測套件管理器
        if command -v apt &> /dev/null; then
            PACKAGE_MANAGER="apt"
        elif command -v yum &> /dev/null; then
            PACKAGE_MANAGER="yum"
        elif command -v dnf &> /dev/null; then
            PACKAGE_MANAGER="dnf"
        elif command -v pacman &> /dev/null; then
            PACKAGE_MANAGER="pacman"
        elif command -v zypper &> /dev/null; then
            PACKAGE_MANAGER="zypper"
        else
            PACKAGE_MANAGER="unknown"
        fi
        
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS_TYPE="macos"
        OS_VERSION=$(sw_vers -productVersion)
        
        if command -v brew &> /dev/null; then
            PACKAGE_MANAGER="brew"
        else
            PACKAGE_MANAGER="none"
        fi
        
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]] || [[ -n "${WSL_DISTRO_NAME:-}" ]]; then
        if [[ -n "${WSL_DISTRO_NAME:-}" ]]; then
            OS_TYPE="wsl"
            OS_VERSION="WSL $(lsb_release -ds 2>/dev/null || echo 'Unknown')"
            PACKAGE_MANAGER="apt"  # 大部分 WSL 使用 Ubuntu
        else
            OS_TYPE="windows"
            OS_VERSION="Windows (Git Bash/MSYS2)"
            if command -v choco &> /dev/null; then
                PACKAGE_MANAGER="choco"
            elif command -v scoop &> /dev/null; then
                PACKAGE_MANAGER="scoop"
            else
                PACKAGE_MANAGER="none"
            fi
        fi
    else
        OS_TYPE="unknown"
        OS_VERSION="Unknown OS"
        PACKAGE_MANAGER="unknown"
    fi
    
    # 檢測系統架構
    ARCH=$(uname -m)
    case $ARCH in
        x86_64|amd64) ARCH="amd64" ;;
        arm64|aarch64) ARCH="arm64" ;;
        armv7l) ARCH="armv7" ;;
        i386|i686) ARCH="386" ;;
        *) ARCH="unknown" ;;
    esac
    
    # 檢測權限
    if [[ $EUID -eq 0 ]]; then
        IS_ADMIN=true
    elif command -v sudo &> /dev/null && sudo -n true 2>/dev/null; then
        HAS_SUDO=true
    fi
    
    log "DEBUG" "系統檢測結果:"
    log "DEBUG" "  作業系統: $OS_TYPE ($OS_VERSION)"
    log "DEBUG" "  系統架構: $ARCH"
    log "DEBUG" "  套件管理器: $PACKAGE_MANAGER"
    log "DEBUG" "  管理員權限: $IS_ADMIN"
    log "DEBUG" "  Sudo 可用: $HAS_SUDO"
}

# 函數：檢查系統相容性
check_system_compatibility() {
    log "INFO" "檢查系統相容性..."
    
    local issues=()
    
    # 檢查作業系統支援
    case $OS_TYPE in
        linux|macos|wsl)
            log "SUCCESS" "作業系統 $OS_TYPE 受支援"
            ;;
        windows)
            log "WARN" "Windows 支援有限，建議使用 WSL 或 Git Bash"
            issues+=("Windows 原生支援有限")
            ;;
        *)
            log "ERROR" "不支援的作業系統: $OS_TYPE"
            issues+=("不支援的作業系統")
            ;;
    esac
    
    # 檢查系統架構
    case $ARCH in
        amd64|arm64)
            log "SUCCESS" "系統架構 $ARCH 受支援"
            ;;
        armv7|386)
            log "WARN" "系統架構 $ARCH 支援有限"
            issues+=("系統架構支援有限")
            ;;
        *)
            log "ERROR" "不支援的系統架構: $ARCH"
            issues+=("不支援的系統架構")
            ;;
    esac
    
    # 檢查套件管理器
    if [[ "$PACKAGE_MANAGER" == "unknown" ]] || [[ "$PACKAGE_MANAGER" == "none" ]]; then
        log "WARN" "未找到套件管理器，可能需要手動安裝"
        issues+=("缺少套件管理器")
    else
        log "SUCCESS" "找到套件管理器: $PACKAGE_MANAGER"
    fi
    
    # 檢查權限
    if [[ "$IS_ADMIN" == "false" ]] && [[ "$HAS_SUDO" == "false" ]]; then
        log "WARN" "缺少管理員權限，可能無法安裝系統套件"
        issues+=("權限不足")
    fi
    
    # 檢查基本工具
    local required_tools=("curl" "git")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log "WARN" "缺少必要工具: $tool"
            issues+=("缺少 $tool")
        else
            log "DEBUG" "工具 $tool 可用"
        fi
    done
    
    # 顯示相容性結果
    if [[ ${#issues[@]} -eq 0 ]]; then
        log "SUCCESS" "系統相容性檢查通過"
        return 0
    else
        log "WARN" "發現 ${#issues[@]} 個相容性問題："
        for issue in "${issues[@]}"; do
            log "WARN" "  - $issue"
        done
        return 1
    fi
}

# 函數：安裝 Homebrew (macOS)
install_homebrew() {
    if [[ "$OS_TYPE" != "macos" ]] || command -v brew &> /dev/null; then
        return 0
    fi
    
    log "INFO" "安裝 Homebrew..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "INFO" "[DRY RUN] 會執行: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        return 0
    fi
    
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # 設置 PATH
    if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -f /usr/local/bin/brew ]]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
    
    if command -v brew &> /dev/null; then
        log "SUCCESS" "Homebrew 安裝成功"
        PACKAGE_MANAGER="brew"
        return 0
    else
        log "ERROR" "Homebrew 安裝失敗"
        return 1
    fi
}

# 函數：檢查 Python 安裝
check_python() {
    log "INFO" "檢查 Python 環境..."
    
    local python_cmd=""
    local python_version=""
    
    if command -v python3 &> /dev/null; then
        python_cmd="python3"
        python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
    elif command -v python &> /dev/null; then
        python_cmd="python"
        python_version=$(python --version 2>&1 | cut -d' ' -f2)
    fi
    
    if [[ -n "$python_cmd" ]]; then
        # 檢查版本是否 >= 3.8
        local major=$(echo "$python_version" | cut -d. -f1)
        local minor=$(echo "$python_version" | cut -d. -f2)
        
        if [[ $major -ge 3 ]] && [[ $minor -ge 8 ]]; then
            log "SUCCESS" "找到合適的 Python 版本: $python_version"
            return 0
        else
            log "WARN" "Python 版本過舊: $python_version (需要 >= 3.8)"
            return 1
        fi
    else
        log "WARN" "未找到 Python 安裝"
        return 1
    fi
}

# 函數：安裝 Python
install_python() {
    if ! check_python || [[ "$FORCE_INSTALL" == "true" ]]; then
        log "INFO" "安裝 Python..."
        
        case $OS_TYPE in
            linux)
                case $PACKAGE_MANAGER in
                    apt)
                        if [[ "$DRY_RUN" == "true" ]]; then
                            log "INFO" "[DRY RUN] 會執行: sudo apt update && sudo apt install -y python3 python3-pip python3-venv"
                        else
                            run_with_sudo apt update
                            run_with_sudo apt install -y python3 python3-pip python3-venv
                        fi
                        ;;
                    yum|dnf)
                        if [[ "$DRY_RUN" == "true" ]]; then
                            log "INFO" "[DRY RUN] 會執行: sudo $PACKAGE_MANAGER install -y python3 python3-pip"
                        else
                            run_with_sudo "$PACKAGE_MANAGER" install -y python3 python3-pip
                        fi
                        ;;
                    pacman)
                        if [[ "$DRY_RUN" == "true" ]]; then
                            log "INFO" "[DRY RUN] 會執行: sudo pacman -S --noconfirm python python-pip"
                        else
                            run_with_sudo pacman -S --noconfirm python python-pip
                        fi
                        ;;
                    *)
                        log "ERROR" "不支援的套件管理器: $PACKAGE_MANAGER"
                        return 1
                        ;;
                esac
                ;;
            macos)
                if [[ "$PACKAGE_MANAGER" == "brew" ]]; then
                    if [[ "$DRY_RUN" == "true" ]]; then
                        log "INFO" "[DRY RUN] 會執行: brew install python3"
                    else
                        brew install python3
                    fi
                else
                    log "ERROR" "macOS 需要 Homebrew 來安裝 Python"
                    return 1
                fi
                ;;
            wsl)
                if [[ "$DRY_RUN" == "true" ]]; then
                    log "INFO" "[DRY RUN] 會執行: sudo apt update && sudo apt install -y python3 python3-pip python3-venv"
                else
                    run_with_sudo apt update
                    run_with_sudo apt install -y python3 python3-pip python3-venv
                fi
                ;;
            windows)
                log "ERROR" "Windows 環境需要手動安裝 Python，請至 https://python.org/downloads"
                return 1
                ;;
            *)
                log "ERROR" "不支援的平台: $OS_TYPE"
                return 1
                ;;
        esac
        
        if check_python; then
            log "SUCCESS" "Python 安裝成功"
        else
            log "ERROR" "Python 安裝失敗"
            return 1
        fi
    else
        log "INFO" "Python 已存在，跳過安裝"
    fi
}

# 函數：檢查 Docker
check_docker() {
    log "INFO" "檢查 Docker 環境..."
    
    if command -v docker &> /dev/null; then
        local docker_version=$(docker --version 2>/dev/null | cut -d' ' -f3 | cut -d',' -f1)
        
        if docker info &>/dev/null; then
            log "SUCCESS" "Docker 運行正常，版本: $docker_version"
            return 0
        else
            log "WARN" "Docker 已安裝但未運行，版本: $docker_version"
            return 1
        fi
    else
        log "INFO" "Docker 未安裝"
        return 1
    fi
}

# 函數：安裝 Docker
install_docker() {
    if ! check_docker || [[ "$FORCE_INSTALL" == "true" ]]; then
        log "INFO" "安裝 Docker..."
        
        case $OS_TYPE in
            linux)
                case $PACKAGE_MANAGER in
                    apt)
                        if [[ "$DRY_RUN" == "true" ]]; then
                            log "INFO" "[DRY RUN] 會執行 Docker 官方安裝腳本"
                        else
                            # 使用 Docker 官方安裝腳本
                            curl -fsSL https://get.docker.com | sh
                            
                            # 添加用戶到 docker 群組
                            if [[ -n "${USER:-}" ]] && ! groups | grep -q docker; then
                                run_with_sudo usermod -aG docker "$USER"
                                log "WARN" "已將用戶加入 docker 群組，請重新登入或執行 'newgrp docker'"
                            fi
                            
                            # 啟動 Docker 服務
                            if systemctl is-active --quiet docker; then
                                log "DEBUG" "Docker 服務已運行"
                            else
                                run_with_sudo systemctl enable docker
                                run_with_sudo systemctl start docker
                            fi
                        fi
                        ;;
                    *)
                        log "WARN" "使用通用安裝方法安裝 Docker"
                        if [[ "$DRY_RUN" == "true" ]]; then
                            log "INFO" "[DRY RUN] 會執行 Docker 官方安裝腳本"
                        else
                            curl -fsSL https://get.docker.com | sh
                        fi
                        ;;
                esac
                ;;
            macos)
                log "WARN" "macOS 需要安裝 Docker Desktop"
                log "INFO" "請至 https://docs.docker.com/docker-for-mac/install/ 下載安裝"
                log "INFO" "或使用: brew install --cask docker"
                
                if [[ "$PACKAGE_MANAGER" == "brew" ]] && [[ "$DRY_RUN" != "true" ]]; then
                    log "INFO" "嘗試使用 Homebrew 安裝 Docker Desktop..."
                    brew install --cask docker
                fi
                ;;
            wsl)
                log "WARN" "WSL 建議安裝 Docker Desktop for Windows 或使用 Linux 安裝方法"
                if [[ "$DRY_RUN" == "true" ]]; then
                    log "INFO" "[DRY RUN] 會執行 Docker 官方安裝腳本"
                else
                    curl -fsSL https://get.docker.com | sh
                fi
                ;;
            windows)
                log "WARN" "Windows 需要安裝 Docker Desktop"
                log "INFO" "請至 https://docs.docker.com/docker-for-windows/install/ 下載安裝"
                ;;
            *)
                log "ERROR" "不支援的平台: $OS_TYPE"
                return 1
                ;;
        esac
        
        # 等待一段時間讓 Docker 啟動
        if [[ "$DRY_RUN" != "true" ]]; then
            log "INFO" "等待 Docker 服務啟動..."
            sleep 5
        fi
        
        if [[ "$DRY_RUN" == "true" ]] || check_docker; then
            log "SUCCESS" "Docker 安裝成功"
        else
            log "WARN" "Docker 安裝可能未完成，請檢查系統狀態"
            return 1
        fi
    else
        log "INFO" "Docker 已正常運行，跳過安裝"
    fi
}

# 函數：檢查 UV
check_uv() {
    log "INFO" "檢查 UV Package Manager..."
    
    if command -v uv &> /dev/null; then
        local uv_version=$(uv --version 2>/dev/null)
        log "SUCCESS" "UV 已安裝，版本: $uv_version"
        return 0
    else
        log "INFO" "UV 未安裝"
        return 1
    fi
}

# 函數：安裝 UV
install_uv() {
    if ! check_uv || [[ "$FORCE_INSTALL" == "true" ]]; then
        log "INFO" "安裝 UV Package Manager..."
        
        if [[ "$DRY_RUN" == "true" ]]; then
            log "INFO" "[DRY RUN] 會執行: curl -LsSf https://astral.sh/uv/install.sh | sh"
        else
            # 使用官方安裝腳本
            curl -LsSf https://astral.sh/uv/install.sh | sh
            
            # 確保 UV 在 PATH 中
            if [[ -f "$HOME/.cargo/bin/uv" ]]; then
                export PATH="$HOME/.cargo/bin:$PATH"
            elif [[ -f "$HOME/.local/bin/uv" ]]; then
                export PATH="$HOME/.local/bin:$PATH"
            fi
            
            # 更新當前 shell 的 PATH
            if [[ -f "$HOME/.bashrc" ]]; then
                echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> "$HOME/.bashrc"
            fi
            if [[ -f "$HOME/.zshrc" ]]; then
                echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> "$HOME/.zshrc"
            fi
        fi
        
        if [[ "$DRY_RUN" == "true" ]] || check_uv; then
            log "SUCCESS" "UV 安裝成功"
        else
            log "ERROR" "UV 安裝失敗"
            return 1
        fi
    else
        log "INFO" "UV 已存在，跳過安裝"
    fi
}

# 函數：執行需要管理員權限的命令
run_with_sudo() {
    if [[ "$IS_ADMIN" == "true" ]]; then
        "$@"
    elif [[ "$HAS_SUDO" == "true" ]]; then
        sudo "$@"
    else
        log "ERROR" "需要管理員權限執行: $*"
        log "INFO" "請以管理員身分運行此腳本，或安裝 sudo"
        return 1
    fi
}

# 函數：安裝後驗證
post_install_verification() {
    log "INFO" "執行安裝後驗證..."
    
    local verification_passed=true
    
    # 驗證 Python
    if [[ "$INSTALL_PYTHON" == "true" ]]; then
        if check_python; then
            log "SUCCESS" "✓ Python 驗證通過"
        else
            log "ERROR" "✗ Python 驗證失敗"
            verification_passed=false
        fi
    fi
    
    # 驗證 Docker
    if [[ "$INSTALL_DOCKER" == "true" ]]; then
        if check_docker; then
            log "SUCCESS" "✓ Docker 驗證通過"
        else
            log "WARN" "✗ Docker 驗證失敗（可能需要重啟或手動配置）"
        fi
    fi
    
    # 驗證 UV
    if [[ "$INSTALL_UV" == "true" ]]; then
        if check_uv; then
            log "SUCCESS" "✓ UV 驗證通過"
        else
            log "ERROR" "✗ UV 驗證失敗"
            verification_passed=false
        fi
    fi
    
    if [[ "$verification_passed" == "true" ]]; then
        log "SUCCESS" "所有組件驗證通過"
        return 0
    else
        log "WARN" "部分組件驗證失敗"
        return 1
    fi
}

# 函數：顯示安裝摘要
show_installation_summary() {
    echo
    log "INFO" "===================================================="
    log "INFO" "$SCRIPT_NAME 安裝摘要"
    log "INFO" "===================================================="
    
    echo -e "${CYAN}系統信息:${NC}"
    echo "  作業系統: $OS_TYPE ($OS_VERSION)"
    echo "  系統架構: $ARCH"
    echo "  套件管理器: $PACKAGE_MANAGER"
    
    echo -e "\n${CYAN}安裝結果:${NC}"
    
    if [[ "$INSTALL_PYTHON" == "true" ]]; then
        if check_python; then
            echo -e "  Python: ${GREEN}已安裝${NC} ($(python3 --version 2>/dev/null || python --version 2>/dev/null))"
        else
            echo -e "  Python: ${RED}安裝失敗${NC}"
        fi
    else
        echo -e "  Python: ${YELLOW}跳過安裝${NC}"
    fi
    
    if [[ "$INSTALL_DOCKER" == "true" ]]; then
        if check_docker; then
            echo -e "  Docker: ${GREEN}已安裝且運行中${NC} ($(docker --version 2>/dev/null | cut -d' ' -f3 | cut -d',' -f1))"
        else
            echo -e "  Docker: ${YELLOW}已安裝但可能需要配置${NC}"
        fi
    else
        echo -e "  Docker: ${YELLOW}跳過安裝${NC}"
    fi
    
    if [[ "$INSTALL_UV" == "true" ]]; then
        if check_uv; then
            echo -e "  UV: ${GREEN}已安裝${NC} ($(uv --version 2>/dev/null))"
        else
            echo -e "  UV: ${RED}安裝失敗${NC}"
        fi
    else
        echo -e "  UV: ${YELLOW}跳過安裝${NC}"
    fi
    
    echo -e "\n${CYAN}下一步操作:${NC}"
    echo "  1. 重新載入 shell 環境: source ~/.bashrc 或重新開啟終端"
    echo "  2. 驗證安裝: ./scripts/start.sh --env-check"
    echo "  3. 開始部署: ./scripts/start.sh"
    
    if [[ "$OS_TYPE" == "linux" ]] && [[ "$INSTALL_DOCKER" == "true" ]]; then
        echo -e "\n${YELLOW}Docker 使用提示:${NC}"
        echo "  - 如果遇到權限問題，請重新登入或執行: newgrp docker"
        echo "  - 確保 Docker 服務運行: sudo systemctl status docker"
    fi
    
    if [[ "$OS_TYPE" == "macos" ]] && [[ "$INSTALL_DOCKER" == "true" ]]; then
        echo -e "\n${YELLOW}Docker Desktop 提示:${NC}"
        echo "  - 啟動 Docker Desktop 應用程式"
        echo "  - 等待 Docker 完全啟動後再進行部署"
    fi
}

# 主函數
main() {
    # 解析命令行參數
    while [[ $# -gt 0 ]]; do
        case $1 in
            --docker-only)
                INSTALL_DOCKER=true
                INSTALL_UV=false
                INSTALL_PYTHON=false
                shift
                ;;
            --uv-only)
                INSTALL_DOCKER=false
                INSTALL_UV=true
                INSTALL_PYTHON=false
                shift
                ;;
            --python-also)
                INSTALL_PYTHON=true
                shift
                ;;
            --all)
                INSTALL_DOCKER=true
                INSTALL_UV=true
                INSTALL_PYTHON=true
                shift
                ;;
            --no-docker)
                INSTALL_DOCKER=false
                shift
                ;;
            --no-uv)
                INSTALL_UV=false
                shift
                ;;
            -f|--force)
                FORCE_INSTALL=true
                shift
                ;;
            -n|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            --check-system)
                detect_system
                check_system_compatibility
                exit $?
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                log "ERROR" "未知選項: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # 顯示歡迎信息
    echo -e "${BLUE}"
    echo "===================================================="
    echo "  $SCRIPT_NAME v$SCRIPT_VERSION"
    echo "  自動安裝 ROAS Discord Bot 部署依賴"
    echo "===================================================="
    echo -e "${NC}"
    
    # 檢測系統
    detect_system
    
    # 檢查系統相容性
    if ! check_system_compatibility; then
        log "WARN" "發現相容性問題，但繼續安裝..."
    fi
    
    # 顯示安裝計劃
    echo -e "${CYAN}安裝計劃:${NC}"
    [[ "$INSTALL_PYTHON" == "true" ]] && echo "  ✓ Python >= 3.8"
    [[ "$INSTALL_DOCKER" == "true" ]] && echo "  ✓ Docker"
    [[ "$INSTALL_UV" == "true" ]] && echo "  ✓ UV Package Manager"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${YELLOW}[DRY RUN 模式] 僅顯示將要執行的操作，不實際安裝${NC}"
    fi
    
    if [[ "$FORCE_INSTALL" == "true" ]]; then
        echo -e "${YELLOW}[強制模式] 將重新安裝已存在的組件${NC}"
    fi
    
    echo
    read -p "是否繼續安裝？[Y/n] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ -n $REPLY ]]; then
        log "INFO" "安裝已取消"
        exit 0
    fi
    
    # 開始安裝過程
    log "INFO" "開始自動安裝過程..."
    
    # 安裝 Homebrew（僅 macOS）
    if [[ "$OS_TYPE" == "macos" ]] && [[ "$PACKAGE_MANAGER" == "none" ]]; then
        install_homebrew
    fi
    
    # 安裝 Python
    if [[ "$INSTALL_PYTHON" == "true" ]]; then
        install_python
    fi
    
    # 安裝 Docker
    if [[ "$INSTALL_DOCKER" == "true" ]]; then
        install_docker
    fi
    
    # 安裝 UV
    if [[ "$INSTALL_UV" == "true" ]]; then
        install_uv
    fi
    
    # 執行安裝後驗證
    if [[ "$DRY_RUN" != "true" ]]; then
        post_install_verification
    fi
    
    # 顯示安裝摘要
    show_installation_summary
    
    log "SUCCESS" "自動安裝完成！"
}

# 執行主函數
main "$@"