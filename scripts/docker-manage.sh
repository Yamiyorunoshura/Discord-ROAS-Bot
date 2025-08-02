#!/bin/bash
# Discord ROAS Bot - Docker 管理腳本
# 提供便捷的 Docker 容器管理功能

set -e

# 顏色配置
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
PROJECT_NAME="discord-roas-bot"
IMAGE_NAME="discord-roas-bot"
REGISTRY_URL=${REGISTRY_URL:-""}

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

# 顯示幫助
show_help() {
    cat << EOF
Discord ROAS Bot - Docker 管理腳本

使用方式: $0 <command> [options]

可用命令:
  build [target]         構建 Docker 映像 
                         target: production(預設), development, testing
  
  run [profile]          運行容器
                         profile: dev, test, prod, monitoring
  
  stop                   停止所有容器
  
  restart [service]      重啟服務
  
  logs [service]         查看日誌
  
  shell [service]        進入容器 shell
  
  clean                  清理未使用的映像和容器
  
  health                 檢查容器健康狀態
  
  backup                 執行資料備份
  
  deploy [env]           部署到指定環境
                         env: staging, production
  
  test                   運行測試套件
  
  lint                   運行代碼檢查
  
  setup                  初始化開發環境

範例:
  $0 build development   # 構建開發環境映像
  $0 run dev            # 運行開發環境
  $0 logs discord-bot   # 查看主服務日誌
  $0 shell discord-bot  # 進入主容器 shell
  $0 deploy production  # 部署到生產環境

EOF
}

# 構建映像
build_image() {
    local target=${1:-production}
    
    log_info "構建 Docker 映像 (target: $target)..."
    
    docker build \
        --target "$target" \
        --tag "$IMAGE_NAME:$target" \
        --tag "$IMAGE_NAME:latest" \
        --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
        --build-arg VERSION="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')" \
        .
    
    log_success "映像構建完成: $IMAGE_NAME:$target"
}

# 運行容器
run_containers() {
    local profile=${1:-dev}
    
    log_info "啟動容器 (profile: $profile)..."
    
    case $profile in
        dev|development)
            docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
            ;;
        prod|production)
            docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
            ;;
        test|testing)
            docker-compose --profile test up --build
            ;;
        monitoring)
            docker-compose --profile monitoring up -d
            ;;
        *)
            log_error "未知的 profile: $profile"
            return 1
            ;;
    esac
    
    log_success "容器啟動完成"
    show_container_status
}

# 停止容器
stop_containers() {
    log_info "停止所有容器..."
    docker-compose down
    log_success "容器已停止"
}

# 重啟服務
restart_service() {
    local service=${1:-discord-bot}
    
    log_info "重啟服務: $service"
    docker-compose restart "$service"
    log_success "服務重啟完成"
}

# 查看日誌
show_logs() {
    local service=${1:-discord-bot}
    
    log_info "顯示 $service 服務日誌..."
    docker-compose logs -f "$service"
}

# 進入容器 shell
enter_shell() {
    local service=${1:-discord-bot}
    
    log_info "進入 $service 容器 shell..."
    docker-compose exec "$service" /bin/bash
}

# 清理
cleanup() {
    log_info "清理未使用的 Docker 資源..."
    
    # 清理未使用的映像
    docker image prune -f
    
    # 清理未使用的容器
    docker container prune -f
    
    # 清理未使用的網路
    docker network prune -f
    
    # 清理未使用的資料卷 (小心使用)
    read -p "是否清理未使用的資料卷? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker volume prune -f
    fi
    
    log_success "清理完成"
}

# 檢查健康狀態
check_health() {
    log_info "檢查容器健康狀態..."
    
    # 顯示容器狀態
    docker-compose ps
    
    echo
    log_info "詳細健康檢查..."
    
    # 檢查主服務
    if docker-compose ps discord-bot | grep -q "Up"; then
        log_success "Discord Bot 服務運行正常"
    else
        log_error "Discord Bot 服務異常"
    fi
    
    # 檢查資料庫連接
    if docker-compose exec -T discord-bot python -c "import sqlite3; sqlite3.connect('/app/dbs/activity.db').close()" 2>/dev/null; then
        log_success "資料庫連接正常"
    else
        log_warning "資料庫連接異常"
    fi
    
    # 顯示資源使用情況
    echo
    log_info "資源使用情況:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
}

# 執行備份
run_backup() {
    log_info "執行資料備份..."
    
    # 確保備份目錄存在
    mkdir -p ./backups
    
    # 運行備份服務
    docker-compose --profile backup run --rm backup
    
    log_success "備份完成"
}

# 部署
deploy() {
    local env=${1:-staging}
    
    log_info "部署到 $env 環境..."
    
    case $env in
        staging)
            log_info "部署到測試環境..."
            build_image production
            docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
            ;;
        production)
            log_info "部署到生產環境..."
            
            # 構建並標記映像
            build_image production
            
            if [ -n "$REGISTRY_URL" ]; then
                log_info "推送到映像倉庫..."
                docker tag "$IMAGE_NAME:latest" "$REGISTRY_URL/$IMAGE_NAME:latest"
                docker push "$REGISTRY_URL/$IMAGE_NAME:latest"
            fi
            
            # 運行生產環境
            docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
            ;;
        *)
            log_error "未知的環境: $env"
            return 1
            ;;
    esac
    
    log_success "部署完成"
}

# 運行測試
run_tests() {
    log_info "運行測試套件..."
    
    docker-compose --profile test run --rm discord-bot-test
    
    log_success "測試完成"
}

# 運行代碼檢查
run_lint() {
    log_info "運行代碼品質檢查..."
    
    # 構建開發映像
    build_image development
    
    # 運行檢查
    docker run --rm -v "$(pwd):/app" "$IMAGE_NAME:development" \
        bash -c "uv run ruff check src/ && uv run mypy src/ && uv run black --check src/"
    
    log_success "代碼檢查完成"
}

# 設置開發環境
setup_development() {
    log_info "設置開發環境..."
    
    # 建立必要目錄
    mkdir -p dbs logs cache assets backups
    
    # 建立環境配置檔案
    if [ ! -f .env ]; then
        log_info "建立 .env 檔案..."
        cat > .env << EOF
TOKEN=your_discord_bot_token_here
ENVIRONMENT=development
LOG_LEVEL=DEBUG
FEATURE_ACHIEVEMENTS=true
FEATURE_ACTIVITY_METER=true
FEATURE_MESSAGE_LISTENER=true
FEATURE_PROTECTION=true
FEATURE_WELCOME=true
FEATURE_SYNC_DATA=true
EOF
        log_warning "請編輯 .env 檔案並設定您的 Discord bot token"
    fi
    
    # 構建開發映像
    build_image development
    
    log_success "開發環境設置完成"
    log_info "使用 '$0 run dev' 啟動開發環境"
}

# 顯示容器狀態
show_container_status() {
    echo
    log_info "容器狀態:"
    docker-compose ps
}

# 主函數
main() {
    if [ $# -eq 0 ]; then
        show_help
        exit 0
    fi
    
    local command=$1
    shift
    
    case $command in
        build)
            build_image "$@"
            ;;
        run)
            run_containers "$@"
            ;;
        stop)
            stop_containers
            ;;
        restart)
            restart_service "$@"
            ;;
        logs)
            show_logs "$@"
            ;;
        shell)
            enter_shell "$@"
            ;;
        clean)
            cleanup
            ;;
        health)
            check_health
            ;;
        backup)
            run_backup
            ;;
        deploy)
            deploy "$@"
            ;;
        test)
            run_tests
            ;;
        lint)
            run_lint
            ;;
        setup)
            setup_development
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 執行主函數
main "$@"