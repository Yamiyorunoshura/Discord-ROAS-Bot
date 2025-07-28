#!/bin/bash
# Discord ADR Bot v2.0 - Unix Shell 啟動腳本
# 自動檢測並創建虛擬環境，兼容 Linux/macOS 系統

set -e  # 遇到錯誤立即退出

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# 日誌函數
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_step() {
    echo -e "${CYAN}[$1/$2] $3${NC}"
}

# 顯示橫幅
print_banner() {
    echo -e "${CYAN}${BOLD}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║              Discord ADR Bot v2.0 - Unix/Linux              ║"
    echo "║                智能啟動腳本 (Shell 版本)                     ║"
    echo "║             支援自動虛擬環境檢測與創建                       ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}\n"
}

# 檢查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 檢查 Python 版本
check_python() {
    log_step 1 5 "檢查 Python 安裝"
    
    if ! command_exists python3; then
        log_error "Python3 未安裝"
        log_info "請安裝 Python 3.10+ 版本"
        exit 1
    fi
    
    # 獲取 Python 版本
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
        log_error "需要 Python 3.10+，當前版本: $PYTHON_VERSION"
        exit 1
    fi
    
    log_success "Python 版本: $PYTHON_VERSION"
}

# 檢查並安裝 uv
check_and_install_uv() {
    log_step 2 5 "檢查 uv 包管理器"
    
    if command_exists uv; then
        UV_VERSION=$(uv --version 2>&1)
        log_success "uv 已安裝: $UV_VERSION"
    else
        log_warning "uv 未安裝，正在安裝..."
        
        # 安裝 uv
        if command_exists curl; then
            curl -LsSf https://astral.sh/uv/install.sh | sh
        elif command_exists wget; then
            wget -qO- https://astral.sh/uv/install.sh | sh
        else
            log_error "需要 curl 或 wget 來安裝 uv"
            log_info "請手動安裝 uv: https://docs.astral.sh/uv/getting-started/installation/"
            exit 1
        fi
        
        # 重新載入 PATH
        export PATH="$HOME/.cargo/bin:$PATH"
        
        # 再次檢查
        if ! command_exists uv; then
            log_error "uv 安裝失敗"
            log_info "請手動安裝 uv 或重新啟動終端"
            exit 1
        fi
        
        UV_VERSION=$(uv --version 2>&1)
        log_success "uv 安裝成功: $UV_VERSION"
    fi
}

# 檢查虛擬環境
detect_virtual_environment() {
    log_step 3 5 "檢查虛擬環境"
    
    # 檢查是否已在虛擬環境中
    if [[ -n "$VIRTUAL_ENV" ]]; then
        log_success "已在虛擬環境中: $VIRTUAL_ENV"
        return 0
    fi
    
    # 檢查常見的虛擬環境目錄
    for venv_dir in ".venv" "venv" ".env" "env"; do
        if [[ -f "$venv_dir/bin/python" ]]; then
            log_success "找到虛擬環境: $venv_dir"
            VENV_PATH="$venv_dir"
            return 0
        fi
    done
    
    log_warning "未找到虛擬環境，正在創建..."
    return 1
}

# 創建虛擬環境
create_virtual_environment() {
    log_info "使用 uv 創建虛擬環境..."
    
    if uv venv .venv; then
        log_success "虛擬環境創建成功: .venv"
        VENV_PATH=".venv"
    else
        log_error "創建虛擬環境失敗"
        exit 1
    fi
}

# 啟動虛擬環境
activate_virtual_environment() {
    log_step 4 5 "啟動虛擬環境"
    
    if [[ -z "$VENV_PATH" ]]; then
        VENV_PATH=".venv"
    fi
    
    if [[ -f "$VENV_PATH/bin/activate" ]]; then
        source "$VENV_PATH/bin/activate"
        log_success "虛擬環境已啟動: $VENV_PATH"
    else
        log_error "找不到啟動腳本: $VENV_PATH/bin/activate"
        exit 1
    fi
}

# 安裝依賴
install_dependencies() {
    log_step 5 5 "檢查並安裝依賴"
    
    if [[ -f "pyproject.toml" ]]; then
        log_info "正在同步依賴套件..."
        if uv sync; then
            log_success "依賴套件已同步"
        else
            log_error "依賴安裝失敗"
            exit 1
        fi
    else
        log_warning "未找到 pyproject.toml，跳過依賴安裝"
    fi
}

# 啟動機器人
start_bot() {
    echo
    log_success "🚀 正在啟動 Discord ADR Bot..."
    log_warning "按 Ctrl+C 停止機器人"
    echo
    
    # 檢查主程式是否存在
    if [[ ! -f "src/main.py" ]]; then
        log_error "找不到主程式 src/main.py"
        exit 1
    fi
    
    # 使用 uv run 啟動機器人
    if uv run python -m src.main run; then
        log_success "機器人正常結束"
    else
        log_error "機器人運行時發生錯誤"
        exit 1
    fi
}

# 清理函數
cleanup() {
    echo
    log_info "正在清理..."
    if [[ -n "$VIRTUAL_ENV" ]]; then
        deactivate 2>/dev/null || true
        log_success "虛擬環境已停用"
    fi
    log_success "👋 感謝使用 Discord ADR Bot!"
}

# 設定陷阱處理中斷信號
trap cleanup EXIT INT TERM

# 主函數
main() {
    print_banner
    
    # 檢查 Python
    check_python
    
    # 檢查並安裝 uv
    check_and_install_uv
    
    # 檢測虛擬環境
    if ! detect_virtual_environment; then
        create_virtual_environment
    fi
    
    # 啟動虛擬環境
    activate_virtual_environment
    
    # 安裝依賴
    install_dependencies
    
    # 啟動機器人
    start_bot
}

# 執行主函數
main "$@"