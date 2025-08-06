#!/bin/bash
# Discord ROAS Bot - 自動化部署腳本
# 支援多環境部署 (development, testing, production)

set -euo pipefail

# 獲取腳本目錄
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 設定預設值
DEPLOYMENT_ENV="${DEPLOYMENT_ENV:-production}"
BUILD_VERSION="${BUILD_VERSION:-$(git describe --tags --always 2>/dev/null || echo 'latest')}"
BUILD_COMMIT="${BUILD_COMMIT:-$(git rev-parse HEAD 2>/dev/null || echo 'unknown')}"
BUILD_DATE="${BUILD_DATE:-$(date -u +"%Y-%m-%dT%H:%M:%SZ")}"
DOCKER_REGISTRY="${DOCKER_REGISTRY:-}"
DRY_RUN="${DRY_RUN:-false}"

# 載入環境配置載入器
if [[ -f "$SCRIPT_DIR/load-env-config.sh" ]]; then
    source "$SCRIPT_DIR/load-env-config.sh"
else
    log_warning "Environment configuration loader not found, using defaults"
fi

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日誌函數
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 顯示使用說明
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

自動化部署 Discord ROAS Bot 到指定環境

OPTIONS:
    -e, --environment ENV    部署環境 (development|testing|production) [預設: production]
    -v, --version VERSION    構建版本標籤 [預設: git describe]
    -r, --registry REGISTRY  Docker 註冊表 URL
    -d, --dry-run           乾執行模式，不實際部署
    -h, --help              顯示此說明

EXAMPLES:
    $0 --environment production --version v2.0.1
    $0 --environment testing --dry-run
    $0 --registry ghcr.io/company/discord-bot --environment production

ENVIRONMENT VARIABLES:
    DEPLOYMENT_ENV    部署環境
    BUILD_VERSION     構建版本
    BUILD_COMMIT      Git commit hash
    BUILD_DATE        構建日期
    DOCKER_REGISTRY   Docker 註冊表
    DRY_RUN          乾執行模式

EOF
}

# 解析命令列參數
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                DEPLOYMENT_ENV="$2"
                shift 2
                ;;
            -v|--version)
                BUILD_VERSION="$2"
                shift 2
                ;;
            -r|--registry)
                DOCKER_REGISTRY="$2"
                shift 2
                ;;
            -d|--dry-run)
                DRY_RUN="true"
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                log_error "未知參數: $1"
                show_usage
                exit 1
                ;;
        esac
    done
}

# 驗證環境參數
validate_environment() {
    case $DEPLOYMENT_ENV in
        development|testing|production)
            log_info "部署環境: $DEPLOYMENT_ENV"
            ;;
        *)
            log_error "無效的部署環境: $DEPLOYMENT_ENV"
            log_error "支援的環境: development, testing, production"
            exit 1
            ;;
    esac
}

# 檢查必要工具
check_prerequisites() {
    log_info "檢查必要工具..."
    
    local missing_tools=()
    
    if ! command -v docker &> /dev/null; then
        missing_tools+=("docker")
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        missing_tools+=("docker-compose")
    fi
    
    if ! command -v git &> /dev/null; then
        missing_tools+=("git")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "缺少必要工具: ${missing_tools[*]}"
        exit 1
    fi
    
    log_success "所有必要工具已安裝"
}

# 構建 Docker 映像
build_docker_image() {
    log_info "構建 Docker 映像..."
    
    local image_tag="discord-roas-bot:${BUILD_VERSION}"
    if [ -n "$DOCKER_REGISTRY" ]; then
        image_tag="${DOCKER_REGISTRY}/discord-roas-bot:${BUILD_VERSION}"
    fi
    
    local build_args=(
        "--build-arg" "BUILD_VERSION=${BUILD_VERSION}"
        "--build-arg" "BUILD_COMMIT=${BUILD_COMMIT}"
        "--build-arg" "BUILD_DATE=${BUILD_DATE}"
        "--build-arg" "DEPLOYMENT_ENV=${DEPLOYMENT_ENV}"
        "--target" "deployment-ready"
        "--tag" "$image_tag"
        "--tag" "${image_tag%-*}:latest"
    )
    
    if [ "$DRY_RUN" = "true" ]; then
        log_warning "乾執行模式: 將會執行以下命令:"
        echo "docker build ${build_args[*]} ."
        return 0
    fi
    
    if docker build "${build_args[@]}" .; then
        log_success "Docker 映像構建成功: $image_tag"
    else
        log_error "Docker 映像構建失敗"
        exit 1
    fi
    
    # 推送到註冊表 (如果指定)
    if [ -n "$DOCKER_REGISTRY" ] && [ "$DRY_RUN" != "true" ]; then
        log_info "推送映像到註冊表: $DOCKER_REGISTRY"
        if docker push "$image_tag" && docker push "${image_tag%-*}:latest"; then
            log_success "映像推送成功"
        else
            log_error "映像推送失敗"
            exit 1
        fi
    fi
}

# 準備部署環境
prepare_deployment() {
    log_info "準備部署環境..."
    
    # 建立必要目錄
    local dirs=("logs" "dbs" "cache" "assets" "backups" "quality-reports")
    for dir in "${dirs[@]}"; do
        if [ "$DRY_RUN" != "true" ]; then
            mkdir -p "$dir"
            log_info "建立目錄: $dir"
        else
            log_warning "乾執行: 將建立目錄 $dir"
        fi
    done
    
    # 設定環境變數檔案
    local env_file=".env.${DEPLOYMENT_ENV}"
    if [ ! -f "$env_file" ] && [ "$DRY_RUN" != "true" ]; then
        log_warning "環境變數檔案不存在: $env_file"
        log_info "建立範例環境變數檔案..."
        cat > "$env_file" << EOF
# Discord ROAS Bot - $DEPLOYMENT_ENV Environment
ENVIRONMENT=$DEPLOYMENT_ENV
TOKEN=your_discord_bot_token_here
DEBUG=false
LOG_LEVEL=INFO

# 資料庫配置
DB_POOL_SIZE=10
DB_QUERY_TIMEOUT=30

# 安全配置
SECURITY_RATE_LIMIT_ENABLED=true

# 功能開關
FEATURE_ACHIEVEMENTS=true
FEATURE_ACTIVITY_METER=true
FEATURE_MESSAGE_LISTENER=true
FEATURE_PROTECTION=true
FEATURE_WELCOME=true
FEATURE_SYNC_DATA=true

# 監控配置
MONITORING_ENABLED=true
METRICS_PORT=9090
EOF
        log_warning "請編輯 $env_file 並設定正確的配置值"
    fi
}

# 執行部署
deploy_application() {
    log_info "部署應用程式到 $DEPLOYMENT_ENV 環境..."
    
    local compose_file="docker-compose.yml"
    local compose_override=""
    
    # 選擇適當的 compose 檔案
    case $DEPLOYMENT_ENV in
        development)
            compose_override="-f docker-compose.dev.yml"
            ;;
        production)
            compose_override="-f docker-compose.prod.yml"
            ;;
    esac
    
    local deploy_cmd="docker-compose -f $compose_file $compose_override"
    
    if [ "$DRY_RUN" = "true" ]; then
        log_warning "乾執行模式: 將會執行以下命令:"
        echo "$deploy_cmd pull"
        echo "$deploy_cmd up -d"
        return 0
    fi
    
    # 拉取最新映像
    log_info "拉取最新映像..."
    if $deploy_cmd pull; then
        log_success "映像拉取成功"
    else
        log_warning "映像拉取失敗，繼續使用本地映像"
    fi
    
    # 啟動服務
    log_info "啟動服務..."
    if $deploy_cmd up -d; then
        log_success "應用程式部署成功"
    else
        log_error "應用程式部署失敗"
        exit 1
    fi
    
    # 等待服務啟動
    log_info "等待服務啟動..."
    sleep 10
    
    # 檢查服務狀態
    if $deploy_cmd ps | grep -q "Up"; then
        log_success "服務運行正常"
    else
        log_error "服務啟動失敗"
        $deploy_cmd logs --tail=50
        exit 1
    fi
}

# 部署後驗證
post_deployment_verification() {
    log_info "執行部署後驗證..."
    
    if [ "$DRY_RUN" = "true" ]; then
        log_warning "乾執行模式: 跳過部署後驗證"
        return 0
    fi
    
    # 檢查健康狀態
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        log_info "健康檢查嘗試 $attempt/$max_attempts..."
        
        if curl -f http://localhost:8080/health &>/dev/null; then
            log_success "健康檢查通過"
            break
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            log_error "健康檢查失敗"
            exit 1
        fi
        
        sleep 5
        ((attempt++))
    done
    
    # 記錄部署資訊
    cat > "deployment-info.json" << EOF
{
    "deployment_date": "$BUILD_DATE",
    "environment": "$DEPLOYMENT_ENV",
    "version": "$BUILD_VERSION",
    "commit": "$BUILD_COMMIT",
    "status": "success"
}
EOF
    
    log_success "部署驗證完成"
}

# 主要執行函數
main() {
    log_info "開始自動化部署流程..."
    log_info "版本: $BUILD_VERSION"
    log_info "提交: $BUILD_COMMIT"
    log_info "日期: $BUILD_DATE"
    
    parse_arguments "$@"
    
    # 載入環境特定配置
    if command -v load_environment_config >/dev/null 2>&1; then
        log_info "載入環境配置: $DEPLOYMENT_ENV"
        load_environment_config "$DEPLOYMENT_ENV" || {
            log_error "無法載入環境配置，使用預設值繼續"
        }
    else
        log_warning "環境配置載入器不可用，使用預設值"
    fi
    
    validate_environment
    check_prerequisites
    build_docker_image
    prepare_deployment
    deploy_application
    post_deployment_verification
    
    log_success "🎉 部署完成！"
    log_info "環境: $DEPLOYMENT_ENV"
    log_info "版本: $BUILD_VERSION"
}

# 執行主函數
main "$@"