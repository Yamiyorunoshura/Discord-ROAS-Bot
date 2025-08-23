#!/bin/bash
# Discord機器人跨平台一鍵啟動腳本 - Unix/Linux/macOS版本
# Task ID: T6 - Docker跨平台一鍵啟動腳本開發

set -euo pipefail

# 設定變數
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/docker/compose.yaml"
ENV_FILE="$PROJECT_ROOT/.env"
DEFAULT_PROFILE="default"

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# 參數預設值
VERBOSE=false
PROFILE="$DEFAULT_PROFILE"
ENV_FILE_CUSTOM=""
FORCE_REBUILD=false
DETACHED=true

# 函數：顯示用法
show_usage() {
    cat << EOF
使用方法: $0 [選項]

選項:
  -e, --env-file FILE     使用指定的環境變數檔案 (預設: .env)
  -p, --profile PROFILE   使用指定的Docker Compose profile (預設: default)
  -v, --verbose           顯示詳細輸出
  -f, --force-rebuild     強制重建Docker映像
  -i, --interactive       交互式模式（不使用-d執行）
  -h, --help             顯示此說明

可用的profiles:
  default     - 基本服務 (bot + redis)
  dev         - 開發環境 (包含開發工具)
  prod        - 生產環境 (包含監控服務)  
  monitoring  - 僅監控服務 (prometheus + grafana)
  dev-tools   - 開發工具容器

範例:
  $0                          # 使用預設配置啟動
  $0 -v                       # 詳細模式啟動
  $0 -p prod -v              # 啟動生產環境配置
  $0 -e .env.prod -p prod    # 使用自訂環境檔案啟動生產環境
  $0 -f                      # 強制重建後啟動
EOF
}

# 函數：記錄訊息
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

# 函數：檢查系統需求
check_system_requirements() {
    log "INFO" "檢查系統需求..."
    
    # 檢查Docker
    if ! command -v docker &> /dev/null; then
        log "ERROR" "Docker未安裝。請安裝Docker："
        echo "  macOS: https://docs.docker.com/docker-for-mac/install/"
        echo "  Ubuntu: https://docs.docker.com/engine/install/ubuntu/"
        echo "  其他Linux: https://docs.docker.com/engine/install/"
        exit 1
    fi
    
    local docker_version=$(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    log "DEBUG" "發現Docker版本: $docker_version"
    
    # 檢查Docker版本 (需要 >= 20.10.0)
    if ! docker version &> /dev/null; then
        log "ERROR" "Docker未運行。請啟動Docker服務"
        exit 1
    fi
    
    # 檢查Docker Compose
    if ! docker compose version &> /dev/null; then
        log "ERROR" "Docker Compose未安裝或版本過舊。請安裝Docker Compose V2："
        echo "  https://docs.docker.com/compose/install/"
        exit 1
    fi
    
    local compose_version=$(docker compose version --short)
    log "DEBUG" "發現Docker Compose版本: $compose_version"
    
    # 檢查可用磁碟空間 (至少需要2GB)
    local available_space=$(df "$PROJECT_ROOT" | awk 'NR==2 {print $4}')
    if [[ $available_space -lt 2097152 ]]; then # 2GB in KB
        log "WARN" "可用磁碟空間不足2GB，可能影響構建過程"
    fi
    
    log "SUCCESS" "系統需求檢查通過"
}

# 函數：檢查並載入環境變數
load_environment() {
    local env_file="${ENV_FILE_CUSTOM:-$ENV_FILE}"
    
    if [[ ! -f "$env_file" ]]; then
        log "ERROR" "環境變數檔案不存在: $env_file"
        log "INFO" "請建立環境變數檔案，範例："
        cat << 'EOF'
# Discord設定
DISCORD_TOKEN=your_bot_token_here
DISCORD_APPLICATION_ID=your_application_id_here

# 環境設定  
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# 安全設定
SECRET_KEY=your_secret_key_here
ENCRYPTION_KEY=your_encryption_key_here
EOF
        exit 1
    fi
    
    log "INFO" "載入環境變數檔案: $env_file"
    
    # 檢查關鍵環境變數
    source "$env_file"
    
    if [[ -z "${DISCORD_TOKEN:-}" ]]; then
        log "ERROR" "DISCORD_TOKEN未設定在環境變數檔案中"
        exit 1
    fi
    
    if [[ -z "${SECRET_KEY:-}" ]]; then
        log "WARN" "SECRET_KEY未設定，將使用預設值（不建議用於生產環境）"
    fi
    
    log "SUCCESS" "環境變數載入成功"
}

# 函數：檢查Docker Compose檔案
check_compose_file() {
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log "ERROR" "Docker Compose檔案不存在: $COMPOSE_FILE"
        exit 1
    fi
    
    log "DEBUG" "使用Docker Compose檔案: $COMPOSE_FILE"
    
    # 驗證Compose檔案語法
    if ! docker compose -f "$COMPOSE_FILE" config &> /dev/null; then
        log "ERROR" "Docker Compose檔案語法錯誤"
        if [[ "$VERBOSE" == "true" ]]; then
            docker compose -f "$COMPOSE_FILE" config
        fi
        exit 1
    fi
    
    log "SUCCESS" "Docker Compose檔案驗證通過"
}

# 函數：構建和啟動服務
start_services() {
    log "INFO" "啟動Discord機器人服務..."
    
    cd "$PROJECT_ROOT"
    
    local compose_args=(
        "-f" "$COMPOSE_FILE"
        "--profile" "$PROFILE"
    )
    
    if [[ -n "$ENV_FILE_CUSTOM" ]]; then
        compose_args+=("--env-file" "$ENV_FILE_CUSTOM")
    fi
    
    # 強制重建映像
    if [[ "$FORCE_REBUILD" == "true" ]]; then
        log "INFO" "強制重建Docker映像..."
        docker compose "${compose_args[@]}" build --no-cache
    fi
    
    # 拉取最新映像
    log "INFO" "拉取最新映像..."
    docker compose "${compose_args[@]}" pull --ignore-pull-failures
    
    # 啟動服務
    local run_args=()
    if [[ "$DETACHED" == "true" ]]; then
        run_args+=("-d")
    fi
    
    if [[ "$VERBOSE" == "true" ]]; then
        log "DEBUG" "執行命令: docker compose ${compose_args[*]} up ${run_args[*]}"
    fi
    
    docker compose "${compose_args[@]}" up "${run_args[@]}"
    
    if [[ "$DETACHED" == "true" ]]; then
        log "SUCCESS" "服務已在背景啟動"
        
        # 顯示服務狀態
        sleep 5
        docker compose "${compose_args[@]}" ps
        
        log "INFO" "查看日誌: docker compose -f $COMPOSE_FILE --profile $PROFILE logs -f"
        log "INFO" "停止服務: docker compose -f $COMPOSE_FILE --profile $PROFILE down"
    fi
}

# 主函數
main() {
    # 解析命令行參數
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--env-file)
                ENV_FILE_CUSTOM="$2"
                shift 2
                ;;
            -p|--profile)
                PROFILE="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -f|--force-rebuild)
                FORCE_REBUILD=true
                shift
                ;;
            -i|--interactive)
                DETACHED=false
                shift
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
    
    log "INFO" "Discord機器人啟動腳本 v1.0 (T6)"
    log "INFO" "Project Root: $PROJECT_ROOT"
    log "INFO" "Profile: $PROFILE"
    
    check_system_requirements
    load_environment
    check_compose_file
    start_services
    
    log "SUCCESS" "啟動完成！"
}

# 執行主函數
main "$@"