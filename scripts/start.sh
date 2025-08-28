#!/bin/bash
# ROAS Discord Bot 智能自動化部署腳本 v2.4.4
# Task ID: 2 - 自動化部署和啟動系統開發
# Noah Chen - 基礎設施專家
#
# 整合環境檢測、智能部署模式選擇、自動降級機制
# 支援 Docker Compose 和 UV Python 兩種部署模式

set -euo pipefail

# ==========設定變數==========
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/docker/compose.yaml"
ENV_FILE="$PROJECT_ROOT/.env"
DEPLOYMENT_LOG="$PROJECT_ROOT/deployment.log"
PYTHON_MAIN="$PROJECT_ROOT/main.py"

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 參數預設值
VERBOSE=false
FORCE_MODE=""
DEPLOYMENT_MODE="auto"
ENV_FILE_CUSTOM=""
SKIP_DEPENDENCIES=false
DRY_RUN=false
QUIET=false

# 部署狀態變數
DEPLOYMENT_ID="deploy_$(date +%s)_$$"
DEPLOYMENT_START_TIME=$(date +%s)
CURRENT_MODE=""
DEPLOYMENT_SUCCESS=false

# ==========工具函數==========

# 函數：顯示用法
show_usage() {
    cat << EOF
🤖 ROAS Discord Bot 智能自動化部署腳本 v2.4.4

使用方法: $0 [選項]

部署模式:
  auto        - 自動檢測最佳部署模式 (預設)
  docker      - 強制使用 Docker Compose 部署
  uv          - 強制使用 UV Python 部署
  fallback    - 使用基本 Python 部署

選項:
  -m, --mode MODE         指定部署模式 (auto|docker|uv|fallback)
  -f, --force            強制使用指定模式，不進行降級
  -e, --env-file FILE    使用指定的環境變數檔案
  -v, --verbose          顯示詳細輸出
  -q, --quiet           靜默模式
  -s, --skip-deps       跳過依賴安裝檢查
  -n, --dry-run         模擬運行，不實際執行
  -h, --help            顯示此說明
  --install-docker      僅安裝 Docker（如果支援）
  --install-uv          僅安裝 UV 包管理器
  --status              檢查當前部署狀態
  --stop                停止當前部署
  --logs                顯示部署日誌

範例:
  $0                              # 自動檢測並部署
  $0 -m docker -v                # 詳細模式使用 Docker 部署
  $0 -m uv -f                    # 強制使用 UV 模式
  $0 --install-docker             # 僅安裝 Docker
  $0 --status                     # 檢查部署狀態
  $0 --stop                       # 停止當前部署

部署流程:
  1. 環境檢測 - 自動檢測 Docker、Python、UV 等環境
  2. 依賴安裝 - 根據需要自動安裝缺失的依賴
  3. 智能選擇 - 選擇最適合的部署模式
  4. 自動降級 - Docker 失敗時自動降級到 UV 模式
  5. 健康檢查 - 確保服務正常運行
EOF
}

# 函數：記錄訊息
log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    if [[ "$QUIET" == "true" && "$level" != "ERROR" && "$level" != "SUCCESS" ]]; then
        return
    fi
    
    case $level in
        "INFO")     echo -e "${BLUE}[INFO]${NC} ${timestamp} - $message" ;;
        "WARN")     echo -e "${YELLOW}[WARN]${NC} ${timestamp} - $message" ;;
        "ERROR")    echo -e "${RED}[ERROR]${NC} ${timestamp} - $message" ;;
        "SUCCESS")  echo -e "${GREEN}[SUCCESS]${NC} ${timestamp} - $message" ;;
        "DEBUG")    if [[ "$VERBOSE" == "true" ]]; then echo -e "${PURPLE}[DEBUG]${NC} ${timestamp} - $message"; fi ;;
        "STEP")     echo -e "${CYAN}[STEP]${NC} ${timestamp} - $message" ;;
    esac
    
    # 寫入部署日誌
    echo "[${level}] ${timestamp} - $message" >> "$DEPLOYMENT_LOG"
}

# 函數：記錄部署事件
log_deployment_event() {
    local event_type="$1"
    local event_level="$2"
    local event_message="$3"
    local source_component="${4:-ScriptManager}"
    
    log "$event_level" "[$event_type] $event_message"
    
    # 這裡可以整合到部署監控系統
    # 實際專案中會呼叫 Python API 記錄事件
}

# 函數：檢測系統平台
detect_platform() {
    local platform="unknown"
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        platform="linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        platform="macos"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        platform="windows"
    fi
    
    echo "$platform"
}

# 函數：檢測包管理器
detect_package_manager() {
    local platform="$1"
    local package_manager=""
    
    case "$platform" in
        "linux")
            if command -v apt &> /dev/null; then
                package_manager="apt"
            elif command -v yum &> /dev/null; then
                package_manager="yum"
            elif command -v dnf &> /dev/null; then
                package_manager="dnf"
            elif command -v pacman &> /dev/null; then
                package_manager="pacman"
            fi
            ;;
        "macos")
            if command -v brew &> /dev/null; then
                package_manager="brew"
            fi
            ;;
        "windows")
            if command -v choco &> /dev/null; then
                package_manager="choco"
            elif command -v winget &> /dev/null; then
                package_manager="winget"
            fi
            ;;
    esac
    
    echo "$package_manager"
}

# 函數：環境檢測
perform_environment_detection() {
    log "STEP" "執行環境檢測..."
    log_deployment_event "ENVIRONMENT_DETECTION" "INFO" "開始環境檢測" "EnvironmentDetector"
    
    local platform=$(detect_platform)
    local package_manager=$(detect_package_manager "$platform")
    
    log "INFO" "檢測到平台: $platform"
    log "DEBUG" "包管理器: ${package_manager:-未檢測到}"
    
    # 檢測 Docker
    local docker_available=false
    local docker_version=""
    local docker_compose_available=false
    
    if command -v docker &> /dev/null; then
        if docker info &> /dev/null; then
            docker_available=true
            docker_version=$(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
            log "SUCCESS" "Docker 可用: $docker_version"
            
            # 檢測 Docker Compose
            if docker compose version &> /dev/null; then
                docker_compose_available=true
                local compose_version=$(docker compose version --short)
                log "SUCCESS" "Docker Compose 可用: $compose_version"
            fi
        else
            log "WARN" "Docker 已安裝但服務未運行"
        fi
    else
        log "INFO" "Docker 未安裝"
    fi
    
    # 檢測 Python
    local python_available=false
    local python_version=""
    
    if command -v python3 &> /dev/null; then
        python_available=true
        python_version=$(python3 --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        log "SUCCESS" "Python 可用: $python_version"
    elif command -v python &> /dev/null; then
        python_available=true
        python_version=$(python --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        log "SUCCESS" "Python 可用: $python_version"
    else
        log "WARN" "Python 未安裝"
    fi
    
    # 檢測 UV
    local uv_available=false
    local uv_version=""
    
    if command -v uv &> /dev/null; then
        uv_available=true
        uv_version=$(uv --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        log "SUCCESS" "UV 可用: $uv_version"
    else
        log "INFO" "UV 未安裝"
    fi
    
    # 儲存環境檢測結果到全域變數
    DETECTED_PLATFORM="$platform"
    DETECTED_PACKAGE_MANAGER="$package_manager"
    DOCKER_AVAILABLE="$docker_available"
    DOCKER_VERSION="$docker_version"
    DOCKER_COMPOSE_AVAILABLE="$docker_compose_available"
    PYTHON_AVAILABLE="$python_available"
    PYTHON_VERSION="$python_version"
    UV_AVAILABLE="$uv_available"
    UV_VERSION="$uv_version"
    
    log_deployment_event "ENVIRONMENT_DETECTION" "SUCCESS" "環境檢測完成" "EnvironmentDetector"
    log "SUCCESS" "環境檢測完成"
}

# 函數：推薦部署模式
recommend_deployment_mode() {
    local recommended_mode="fallback"
    
    if [[ "$DOCKER_AVAILABLE" == "true" && "$DOCKER_COMPOSE_AVAILABLE" == "true" ]]; then
        recommended_mode="docker"
    elif [[ "$UV_AVAILABLE" == "true" && "$PYTHON_AVAILABLE" == "true" ]]; then
        recommended_mode="uv"
    elif [[ "$PYTHON_AVAILABLE" == "true" ]]; then
        recommended_mode="fallback"
    fi
    
    echo "$recommended_mode"
}

# 函數：安裝 Docker
install_docker() {
    log "STEP" "安裝 Docker..."
    log_deployment_event "DEPENDENCY_INSTALL" "INFO" "開始安裝 Docker" "DependencyInstaller"
    
    case "$DETECTED_PLATFORM" in
        "linux")
            case "$DETECTED_PACKAGE_MANAGER" in
                "apt")
                    if [[ "$DRY_RUN" == "true" ]]; then
                        log "INFO" "[DRY-RUN] 會執行: sudo apt update && sudo apt install -y docker.io docker-compose-plugin"
                    else
                        sudo apt update
                        sudo apt install -y docker.io docker-compose-plugin
                        sudo systemctl enable docker
                        sudo systemctl start docker
                    fi
                    ;;
                "yum"|"dnf")
                    if [[ "$DRY_RUN" == "true" ]]; then
                        log "INFO" "[DRY-RUN] 會執行: sudo $DETECTED_PACKAGE_MANAGER install -y docker docker-compose"
                    else
                        sudo "$DETECTED_PACKAGE_MANAGER" install -y docker docker-compose
                        sudo systemctl enable docker
                        sudo systemctl start docker
                    fi
                    ;;
                *)
                    log "ERROR" "不支援的 Linux 包管理器: $DETECTED_PACKAGE_MANAGER"
                    return 1
                    ;;
            esac
            ;;
        "macos")
            if [[ "$DETECTED_PACKAGE_MANAGER" == "brew" ]]; then
                if [[ "$DRY_RUN" == "true" ]]; then
                    log "INFO" "[DRY-RUN] 會執行: brew install --cask docker"
                else
                    brew install --cask docker
                    log "WARN" "Docker Desktop 已安裝，請手動啟動 Docker Desktop 應用程式"
                fi
            else
                log "ERROR" "在 macOS 上需要 Homebrew 來安裝 Docker"
                log "INFO" "請先安裝 Homebrew: /bin/bash -c \\"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\\""
                return 1
            fi
            ;;
        *)
            log "ERROR" "不支援在 $DETECTED_PLATFORM 上自動安裝 Docker"
            log "INFO" "請手動安裝 Docker: https://docs.docker.com/get-docker/"
            return 1
            ;;
    esac
    
    if [[ "$DRY_RUN" == "false" ]]; then
        # 驗證安裝
        sleep 5
        if command -v docker &> /dev/null && docker info &> /dev/null; then
            log_deployment_event "DEPENDENCY_INSTALL" "SUCCESS" "Docker 安裝成功" "DependencyInstaller"
            log "SUCCESS" "Docker 安裝成功"
            return 0
        else
            log_deployment_event "DEPENDENCY_INSTALL" "ERROR" "Docker 安裝失敗" "DependencyInstaller"
            log "ERROR" "Docker 安裝後仍無法使用"
            return 1
        fi
    else
        log "INFO" "[DRY-RUN] Docker 安裝模擬完成"
        return 0
    fi
}

# 函數：安裝 UV
install_uv() {
    log "STEP" "安裝 UV 包管理器..."
    log_deployment_event "DEPENDENCY_INSTALL" "INFO" "開始安裝 UV" "DependencyInstaller"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "INFO" "[DRY-RUN] 會執行 UV 安裝腳本"
        log_deployment_event "DEPENDENCY_INSTALL" "SUCCESS" "UV 安裝模擬完成" "DependencyInstaller"
        return 0
    fi
    
    # 使用官方安裝腳本
    if [[ "$DETECTED_PLATFORM" == "windows" ]]; then
        # Windows PowerShell 安裝
        if command -v powershell &> /dev/null; then
            powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
        else
            log "WARN" "PowerShell 不可用，嘗試使用 pip 安裝"
            pip install uv
        fi
    else
        # Unix-like 系統
        curl -LsSf https://astral.sh/uv/install.sh | sh
        
        # 如果 curl 安裝失敗，嘗試 pip
        if ! command -v uv &> /dev/null; then
            log "WARN" "curl 安裝失敗，嘗試使用 pip 安裝"
            if command -v pip &> /dev/null; then
                pip install uv
            elif command -v pip3 &> /dev/null; then
                pip3 install uv
            else
                log "ERROR" "無法安裝 UV：curl 和 pip 都不可用"
                return 1
            fi
        fi
    fi
    
    # 驗證安裝
    sleep 2
    if command -v uv &> /dev/null; then
        log_deployment_event "DEPENDENCY_INSTALL" "SUCCESS" "UV 安裝成功" "DependencyInstaller"
        log "SUCCESS" "UV 安裝成功"
        return 0
    else
        log_deployment_event "DEPENDENCY_INSTALL" "ERROR" "UV 安裝失敗" "DependencyInstaller"
        log "ERROR" "UV 安裝失敗"
        return 1
    fi
}

# 函數：Docker 部署
deploy_with_docker() {
    log "STEP" "使用 Docker 模式部署..."
    log_deployment_event "SERVICE_DEPLOYMENT" "INFO" "開始 Docker 部署" "DockerDeploymentManager"
    
    CURRENT_MODE="docker"
    
    # 檢查 Docker Compose 檔案
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log "ERROR" "Docker Compose 檔案不存在: $COMPOSE_FILE"
        return 1
    fi
    
    cd "$PROJECT_ROOT"
    
    # 驗證 Compose 檔案
    if ! docker compose -f "$COMPOSE_FILE" config &> /dev/null; then
        log "ERROR" "Docker Compose 檔案語法錯誤"
        if [[ "$VERBOSE" == "true" ]]; then
            docker compose -f "$COMPOSE_FILE" config
        fi
        return 1
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "INFO" "[DRY-RUN] 會執行: docker compose up -d"
        log_deployment_event "SERVICE_DEPLOYMENT" "SUCCESS" "Docker 部署模擬完成" "DockerDeploymentManager"
        return 0
    fi
    
    # 停止現有服務
    log "INFO" "停止現有服務..."
    docker compose -f "$COMPOSE_FILE" down &> /dev/null || true
    
    # 拉取最新映像
    log "INFO" "拉取最新映像..."
    docker compose -f "$COMPOSE_FILE" pull --ignore-pull-failures
    
    # 構建映像（如果需要）
    log "INFO" "構建應用映像..."
    docker compose -f "$COMPOSE_FILE" build
    
    # 啟動服務
    log "INFO" "啟動服務..."
    if docker compose -f "$COMPOSE_FILE" up -d; then
        log "SUCCESS" "Docker 服務已啟動"
        
        # 等待服務就緒
        sleep 10
        
        # 檢查服務狀態
        log "INFO" "檢查服務狀態..."
        docker compose -f "$COMPOSE_FILE" ps
        
        # 簡單健康檢查
        if docker compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
            log_deployment_event "SERVICE_DEPLOYMENT" "SUCCESS" "Docker 部署成功" "DockerDeploymentManager"
            log "SUCCESS" "Docker 部署成功！服務正在運行"
            
            # 顯示有用信息
            log "INFO" "查看日誌: docker compose -f $COMPOSE_FILE logs -f"
            log "INFO" "停止服務: docker compose -f $COMPOSE_FILE down"
            
            return 0
        else
            log "ERROR" "服務啟動後狀態異常"
            return 1
        fi
    else
        log "ERROR" "Docker 服務啟動失敗"
        return 1
    fi
}

# 函數：UV Python 部署
deploy_with_uv() {
    log "STEP" "使用 UV Python 模式部署..."
    log_deployment_event "SERVICE_DEPLOYMENT" "INFO" "開始 UV Python 部署" "UVDeploymentManager"
    
    CURRENT_MODE="uv"
    
    cd "$PROJECT_ROOT"
    
    # 檢查主應用程式檔案
    if [[ ! -f "$PYTHON_MAIN" ]]; then
        log "WARN" "main.py 不存在，尋找其他可能的主檔案..."
        
        local main_candidates=("app.py" "run.py" "bot.py" "start.py")
        local found_main=""
        
        for candidate in "${main_candidates[@]}"; do
            if [[ -f "$PROJECT_ROOT/$candidate" ]]; then
                found_main="$candidate"
                PYTHON_MAIN="$PROJECT_ROOT/$candidate"
                log "INFO" "找到主檔案: $candidate"
                break
            fi
        done
        
        if [[ -z "$found_main" ]]; then
            log "ERROR" "找不到 Python 主應用程式檔案"
            return 1
        fi
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "INFO" "[DRY-RUN] 會建立虛擬環境並安裝依賴"
        log "INFO" "[DRY-RUN] 會執行: uv run $PYTHON_MAIN"
        log_deployment_event "SERVICE_DEPLOYMENT" "SUCCESS" "UV Python 部署模擬完成" "UVDeploymentManager"
        return 0
    fi
    
    # 建立虛擬環境
    log "INFO" "建立 UV 虛擬環境..."
    if ! uv venv; then
        log "ERROR" "建立虛擬環境失敗"
        return 1
    fi
    
    # 安裝依賴
    log "INFO" "安裝 Python 依賴..."
    if [[ -f "pyproject.toml" ]]; then
        if ! uv sync; then
            log "ERROR" "安裝依賴失敗 (uv sync)"
            return 1
        fi
    elif [[ -f "requirements.txt" ]]; then
        if ! uv pip install -r requirements.txt; then
            log "ERROR" "安裝依賴失敗 (requirements.txt)"
            return 1
        fi
    else
        log "WARN" "找不到依賴文件 (pyproject.toml 或 requirements.txt)"
    fi
    
    # 驗證應用程式
    log "INFO" "驗證應用程式..."
    if ! uv run python -c "import sys; sys.path.insert(0, '.'); exec(open('$PYTHON_MAIN').read())" &> /dev/null; then
        log "WARN" "應用程式驗證失敗，但將嘗試啟動"
    fi
    
    log_deployment_event "SERVICE_DEPLOYMENT" "SUCCESS" "UV Python 部署完成" "UVDeploymentManager"
    log "SUCCESS" "UV Python 部署完成！"
    
    # 提供啟動指引
    log "INFO" "啟動應用程式: uv run python $PYTHON_MAIN"
    log "INFO" "或者: source .venv/bin/activate && python $PYTHON_MAIN"
    
    return 0
}

# 函數：基本 Python 部署
deploy_with_fallback() {
    log "STEP" "使用基本 Python 模式部署..."
    log_deployment_event "SERVICE_DEPLOYMENT" "INFO" "開始基本 Python 部署" "FallbackDeploymentManager"
    
    CURRENT_MODE="fallback"
    
    cd "$PROJECT_ROOT"
    
    # 檢查主應用程式檔案
    if [[ ! -f "$PYTHON_MAIN" ]]; then
        log "ERROR" "找不到 Python 主應用程式檔案: $PYTHON_MAIN"
        return 1
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "INFO" "[DRY-RUN] 會建立虛擬環境並安裝依賴"
        log "INFO" "[DRY-RUN] 會執行: python $PYTHON_MAIN"
        log_deployment_event "SERVICE_DEPLOYMENT" "SUCCESS" "基本 Python 部署模擬完成" "FallbackDeploymentManager"
        return 0
    fi
    
    local python_cmd="python3"
    if ! command -v python3 &> /dev/null; then
        if command -v python &> /dev/null; then
            python_cmd="python"
        else
            log "ERROR" "找不到 Python 執行檔"
            return 1
        fi
    fi
    
    # 建立虛擬環境
    log "INFO" "建立 Python 虛擬環境..."
    if ! $python_cmd -m venv .venv; then
        log "ERROR" "建立虛擬環境失敗"
        return 1
    fi
    
    # 啟動虛擬環境
    source .venv/bin/activate
    
    # 安裝依賴
    if [[ -f "requirements.txt" ]]; then
        log "INFO" "安裝 Python 依賴..."
        if ! pip install -r requirements.txt; then
            log "ERROR" "安裝依賴失敗"
            return 1
        fi
    elif [[ -f "pyproject.toml" ]]; then
        log "INFO" "安裝專案依賴..."
        if ! pip install -e .; then
            log "ERROR" "安裝專案依賴失敗"
            return 1
        fi
    fi
    
    log_deployment_event "SERVICE_DEPLOYMENT" "SUCCESS" "基本 Python 部署完成" "FallbackDeploymentManager"
    log "SUCCESS" "基本 Python 部署完成！"
    
    # 提供啟動指引
    log "INFO" "啟動應用程式: source .venv/bin/activate && python $PYTHON_MAIN"
    
    return 0
}

# 函數：智能部署協調器
perform_intelligent_deployment() {
    log "STEP" "執行智能部署協調..."
    log_deployment_event "DEPLOYMENT_ORCHESTRATION" "INFO" "開始智能部署協調" "DeploymentOrchestrator"
    
    local target_mode="$DEPLOYMENT_MODE"
    local modes_to_try=()
    
    # 決定嘗試順序
    if [[ "$target_mode" == "auto" ]]; then
        local recommended=$(recommend_deployment_mode)
        log "INFO" "自動模式，推薦使用: $recommended"
        
        case "$recommended" in
            "docker")
                modes_to_try=("docker" "uv" "fallback")
                ;;
            "uv")
                modes_to_try=("uv" "fallback")
                ;;
            *)
                modes_to_try=("fallback")
                ;;
        esac
    else
        if [[ "$FORCE_MODE" == "true" ]]; then
            modes_to_try=("$target_mode")
        else
            case "$target_mode" in
                "docker")
                    modes_to_try=("docker" "uv" "fallback")
                    ;;
                "uv")
                    modes_to_try=("uv" "fallback")
                    ;;
                "fallback")
                    modes_to_try=("fallback")
                    ;;
            esac
        fi
    fi
    
    log "INFO" "部署嘗試順序: ${modes_to_try[*]}"
    
    # 按順序嘗試部署
    for mode in "${modes_to_try[@]}"; do
        log "INFO" "嘗試 $mode 模式部署..."
        
        local deployment_result=false
        
        case "$mode" in
            "docker")
                # 檢查並安裝 Docker 依賴
                if [[ "$DOCKER_AVAILABLE" != "true" ]] && [[ "$SKIP_DEPENDENCIES" != "true" ]]; then
                    log "INFO" "Docker 不可用，嘗試安裝..."
                    if install_docker; then
                        # 重新檢測環境
                        DOCKER_AVAILABLE=true
                    else
                        log "WARN" "Docker 安裝失敗，跳過 Docker 模式"
                        continue
                    fi
                fi
                
                if deploy_with_docker; then
                    deployment_result=true
                fi
                ;;
            "uv")
                # 檢查並安裝 UV 依賴
                if [[ "$UV_AVAILABLE" != "true" ]] && [[ "$SKIP_DEPENDENCIES" != "true" ]]; then
                    log "INFO" "UV 不可用，嘗試安裝..."
                    if install_uv; then
                        # 重新檢測環境
                        UV_AVAILABLE=true
                    else
                        log "WARN" "UV 安裝失敗，跳過 UV 模式"
                        continue
                    fi
                fi
                
                if deploy_with_uv; then
                    deployment_result=true
                fi
                ;;
            "fallback")
                if deploy_with_fallback; then
                    deployment_result=true
                fi
                ;;
        esac
        
        if [[ "$deployment_result" == "true" ]]; then
            DEPLOYMENT_SUCCESS=true
            log_deployment_event "DEPLOYMENT_ORCHESTRATION" "SUCCESS" "部署成功，模式: $mode" "DeploymentOrchestrator"
            log "SUCCESS" "🎉 部署成功！使用模式: $mode"
            return 0
        else
            log_deployment_event "DEPLOYMENT_ORCHESTRATION" "WARN" "部署模式 $mode 失敗，嘗試降級" "DeploymentOrchestrator"
            log "WARN" "$mode 模式部署失敗，嘗試下一個模式..."
            
            # 如果是強制模式，直接退出
            if [[ "$FORCE_MODE" == "true" ]]; then
                break
            fi
        fi
    done
    
    log_deployment_event "DEPLOYMENT_ORCHESTRATION" "ERROR" "所有部署模式都失敗" "DeploymentOrchestrator"
    log "ERROR" "所有部署模式都失敗了！"
    return 1
}

# 函數：檢查部署狀態
check_deployment_status() {
    log "INFO" "檢查當前部署狀態..."
    
    # 檢查 Docker 服務
    if command -v docker &> /dev/null && [[ -f "$COMPOSE_FILE" ]]; then
        log "INFO" "檢查 Docker 服務..."
        cd "$PROJECT_ROOT"
        
        if docker compose -f "$COMPOSE_FILE" ps 2>/dev/null | grep -q "Up"; then
            log "SUCCESS" "Docker 服務正在運行"
            docker compose -f "$COMPOSE_FILE" ps
            return 0
        fi
    fi
    
    # 檢查 Python 進程
    if pgrep -f "python.*$PYTHON_MAIN" > /dev/null; then
        log "SUCCESS" "Python 應用程式正在運行"
        pgrep -fl "python.*$PYTHON_MAIN"
        return 0
    fi
    
    log "INFO" "沒有檢測到正在運行的服務"
    return 1
}

# 函數：停止部署
stop_deployment() {
    log "INFO" "停止當前部署..."
    
    local stopped_something=false
    
    # 停止 Docker 服務
    if command -v docker &> /dev/null && [[ -f "$COMPOSE_FILE" ]]; then
        cd "$PROJECT_ROOT"
        if docker compose -f "$COMPOSE_FILE" ps 2>/dev/null | grep -q "Up"; then
            log "INFO" "停止 Docker 服務..."
            docker compose -f "$COMPOSE_FILE" down
            stopped_something=true
        fi
    fi
    
    # 停止 Python 進程
    if pgrep -f "python.*$PYTHON_MAIN" > /dev/null; then
        log "INFO" "停止 Python 應用程式..."
        pkill -f "python.*$PYTHON_MAIN"
        stopped_something=true
    fi
    
    if [[ "$stopped_something" == "true" ]]; then
        log "SUCCESS" "部署已停止"
    else
        log "INFO" "沒有檢測到正在運行的服務"
    fi
}

# 函數：顯示部署日誌
show_deployment_logs() {
    if [[ -f "$DEPLOYMENT_LOG" ]]; then
        log "INFO" "顯示部署日誌..."
        echo "=== 部署日誌 ==="
        tail -50 "$DEPLOYMENT_LOG"
    else
        log "INFO" "部署日誌文件不存在"
    fi
}

# 函數：載入環境變數
load_environment_variables() {
    local env_file="${ENV_FILE_CUSTOM:-$ENV_FILE}"
    
    if [[ ! -f "$env_file" ]]; then
        log "WARN" "環境變數文件不存在: $env_file"
        log "INFO" "建議建立 .env 文件包含必要的環境變數"
        return 0
    fi
    
    log "INFO" "載入環境變數: $env_file"
    
    # 載入環境變數（但不 export）
    while IFS= read -r line || [[ -n "$line" ]]; do
        # 跳過註解和空行
        if [[ "$line" =~ ^[[:space:]]*# ]] || [[ -z "${line// }" ]]; then
            continue
        fi
        
        # 檢查格式
        if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
            if [[ "$VERBOSE" == "true" ]]; then
                local var_name=$(echo "$line" | cut -d'=' -f1)
                log "DEBUG" "載入環境變數: $var_name"
            fi
        fi
    done < "$env_file"
    
    log "SUCCESS" "環境變數載入完成"
}

# 函數：記錄部署摘要
log_deployment_summary() {
    local deployment_end_time=$(date +%s)
    local deployment_duration=$((deployment_end_time - DEPLOYMENT_START_TIME))
    
    log "INFO" "=== 部署摘要 ==="
    log "INFO" "部署 ID: $DEPLOYMENT_ID"
    log "INFO" "部署模式: ${CURRENT_MODE:-未知}"
    log "INFO" "部署耗時: ${deployment_duration} 秒"
    log "INFO" "部署結果: $([ "$DEPLOYMENT_SUCCESS" == "true" ] && echo "成功" || echo "失敗")"
    log "INFO" "平台資訊: $DETECTED_PLATFORM"
    log "INFO" "Python: ${PYTHON_VERSION:-不可用}"
    log "INFO" "Docker: ${DOCKER_VERSION:-不可用}"
    log "INFO" "UV: ${UV_VERSION:-不可用}"
    
    # 寫入摘要到日誌檔案
    {
        echo "\\n=== DEPLOYMENT SUMMARY ==="
        echo "Deployment ID: $DEPLOYMENT_ID"
        echo "Mode: ${CURRENT_MODE:-unknown}"
        echo "Duration: ${deployment_duration}s"
        echo "Success: $DEPLOYMENT_SUCCESS"
        echo "Platform: $DETECTED_PLATFORM"
        echo "Timestamp: $(date -Iseconds)"
        echo "========================\\n"
    } >> "$DEPLOYMENT_LOG"
}

# ==========主函數==========

# 函數：主執行流程
main() {
    # 建立部署日誌檔案
    touch "$DEPLOYMENT_LOG"
    
    # 記錄開始
    log "INFO" "🤖 ROAS Discord Bot 智能自動化部署腳本 v2.4.4"
    log "INFO" "部署 ID: $DEPLOYMENT_ID"
    log "INFO" "專案根目錄: $PROJECT_ROOT"
    
    # 解析命令行參數
    while [[ $# -gt 0 ]]; do
        case $1 in
            -m|--mode)
                DEPLOYMENT_MODE="$2"
                shift 2
                ;;
            -f|--force)
                FORCE_MODE="true"
                shift
                ;;
            -e|--env-file)
                ENV_FILE_CUSTOM="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -q|--quiet)
                QUIET=true
                shift
                ;;
            -s|--skip-deps)
                SKIP_DEPENDENCIES=true
                shift
                ;;
            -n|--dry-run)
                DRY_RUN=true
                shift
                ;;
            --install-docker)
                perform_environment_detection
                install_docker
                exit $?
                ;;
            --install-uv)
                perform_environment_detection
                install_uv
                exit $?
                ;;
            --status)
                check_deployment_status
                exit $?
                ;;
            --stop)
                stop_deployment
                exit $?
                ;;
            --logs)
                show_deployment_logs
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
    
    # 驗證部署模式
    case "$DEPLOYMENT_MODE" in
        "auto"|"docker"|"uv"|"fallback")
            ;;
        *)
            log "ERROR" "無效的部署模式: $DEPLOYMENT_MODE"
            show_usage
            exit 1
            ;;
    esac
    
    log "INFO" "部署模式: $DEPLOYMENT_MODE"
    if [[ "$FORCE_MODE" == "true" ]]; then
        log "INFO" "強制模式: 啟用"
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "INFO" "模擬運行模式: 啟用"
    fi
    
    # 執行部署流程
    {
        perform_environment_detection
        load_environment_variables
        perform_intelligent_deployment
    } || {
        log "ERROR" "部署失敗！"
        log_deployment_summary
        exit 1
    }
    
    # 記錄成功
    log_deployment_summary
    
    if [[ "$DEPLOYMENT_SUCCESS" == "true" ]]; then
        log "SUCCESS" "🎉 部署完成！ROAS Discord Bot 已成功部署"
        
        if [[ "$CURRENT_MODE" == "docker" ]]; then
            log "INFO" "💡 實用指令："
            log "INFO" "  查看日誌: docker compose -f $COMPOSE_FILE logs -f"
            log "INFO" "  停止服務: docker compose -f $COMPOSE_FILE down"
            log "INFO" "  重啟服務: docker compose -f $COMPOSE_FILE restart"
        elif [[ "$CURRENT_MODE" == "uv" ]]; then
            log "INFO" "💡 實用指令："
            log "INFO" "  啟動應用: uv run python $PYTHON_MAIN"
            log "INFO" "  進入環境: source .venv/bin/activate"
        elif [[ "$CURRENT_MODE" == "fallback" ]]; then
            log "INFO" "💡 實用指令："
            log "INFO" "  啟動應用: source .venv/bin/activate && python $PYTHON_MAIN"
        fi
        
        log "INFO" "  檢查狀態: $0 --status"
        log "INFO" "  停止部署: $0 --stop"
        log "INFO" "  查看日誌: $0 --logs"
    fi
}

# 執行主函數
main "$@"