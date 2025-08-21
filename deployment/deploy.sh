#!/bin/bash
# Discord機器人部署腳本
# Task ID: 11 - 建立文件和部署準備

set -euo pipefail

# 配置變數
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEPLOYMENT_DIR="/opt/discord-bot"
BACKUP_DIR="/opt/discord-bot/backups"
LOG_FILE="/var/log/discord-bot-deploy.log"

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日誌函數
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✓${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ⚠${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ✗${NC} $1" | tee -a "$LOG_FILE"
}

# 顯示幫助信息
show_help() {
    cat << EOF
Discord機器人部署工具 v2.4.0

使用方法:
    $0 [選項] <命令>

命令:
    deploy <環境>     部署到指定環境 (dev|staging|prod)
    rollback <版本>   回滾到指定版本
    status           查看當前狀態
    logs [服務]       查看日誌
    backup           創建備份
    restore <備份>    恢復備份
    health           健康檢查
    stop             停止所有服務
    start            啟動所有服務
    restart          重啟所有服務

選項:
    -h, --help       顯示此幫助信息
    -v, --verbose    詳細輸出
    -f, --force      強制執行（跳過確認）
    --dry-run        預覽執行（不實際執行）

環境變數:
    DISCORD_TOKEN    Discord機器人Token
    ENVIRONMENT      部署環境
    BACKUP_RETENTION 備份保留天數（預設：30）

範例:
    $0 deploy prod           # 部署到生產環境
    $0 rollback v2.3.0       # 回滾到v2.3.0
    $0 logs discord-bot      # 查看機器人日誌
    $0 backup               # 創建備份

EOF
}

# 檢查必要條件
check_prerequisites() {
    log "檢查部署必要條件..."
    
    # 檢查Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker未安裝"
        exit 1
    fi
    
    # 檢查Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose未安裝"
        exit 1
    fi
    
    # 檢查必要目錄
    mkdir -p "$DEPLOYMENT_DIR" "$BACKUP_DIR"
    
    # 檢查環境變數
    if [[ -z "${DISCORD_TOKEN:-}" ]]; then
        log_error "請設置DISCORD_TOKEN環境變數"
        exit 1
    fi
    
    log_success "必要條件檢查完成"
}

# 創建備份
create_backup() {
    local backup_name="backup_$(date +%Y%m%d_%H%M%S)"
    local backup_path="$BACKUP_DIR/$backup_name"
    
    log "創建備份: $backup_name"
    
    mkdir -p "$backup_path"
    
    # 備份資料庫
    if [[ -f "$DEPLOYMENT_DIR/data/discord_data.db" ]]; then
        cp "$DEPLOYMENT_DIR/data/discord_data.db" "$backup_path/"
        log "備份主資料庫"
    fi
    
    if [[ -f "$DEPLOYMENT_DIR/data/message.db" ]]; then
        cp "$DEPLOYMENT_DIR/data/message.db" "$backup_path/"
        log "備份訊息資料庫"
    fi
    
    # 備份配置文件
    if [[ -f "$DEPLOYMENT_DIR/.env" ]]; then
        cp "$DEPLOYMENT_DIR/.env" "$backup_path/"
        log "備份環境配置"
    fi
    
    # 創建備份信息文件
    cat > "$backup_path/backup_info.json" << EOF
{
    "backup_name": "$backup_name",
    "created_at": "$(date -Iseconds)",
    "version": "$(git describe --tags --always 2>/dev/null || echo 'unknown')",
    "environment": "${ENVIRONMENT:-unknown}",
    "size_bytes": $(du -sb "$backup_path" | cut -f1)
}
EOF
    
    # 壓縮備份
    cd "$BACKUP_DIR"
    tar -czf "${backup_name}.tar.gz" "$backup_name"
    rm -rf "$backup_name"
    
    log_success "備份創建完成: ${backup_name}.tar.gz"
    echo "$backup_name"
}

# 部署函數
deploy() {
    local environment="${1:-dev}"
    local compose_file
    
    case "$environment" in
        dev|development)
            compose_file="docker-compose.dev.yml"
            ;;
        staging)
            compose_file="docker-compose.staging.yml"
            ;;
        prod|production)
            compose_file="docker-compose.prod.yml"
            ;;
        *)
            log_error "不支持的環境: $environment"
            exit 1
            ;;
    esac
    
    log "開始部署到 $environment 環境"
    
    # 檢查部署文件是否存在
    if [[ ! -f "$PROJECT_DIR/$compose_file" ]]; then
        log_error "找不到部署配置文件: $compose_file"
        exit 1
    fi
    
    # 確認部署
    if [[ "${FORCE:-false}" != "true" ]]; then
        echo -n "確認部署到 $environment 環境？ [y/N] "
        read -r confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            log "部署已取消"
            exit 0
        fi
    fi
    
    # 創建部署前備份
    if [[ "$environment" == "prod" || "$environment" == "production" ]]; then
        log "創建部署前備份..."
        local backup_name
        backup_name=$(create_backup)
        echo "ROLLBACK_BACKUP=$backup_name" > "$DEPLOYMENT_DIR/.last_deployment"
    fi
    
    # 複製項目文件到部署目錄
    log "複製項目文件..."
    rsync -av --exclude='.git' --exclude='venv' --exclude='__pycache__' \
          "$PROJECT_DIR/" "$DEPLOYMENT_DIR/"
    
    # 設置環境變數
    export ENVIRONMENT="$environment"
    
    # 執行部署
    cd "$DEPLOYMENT_DIR"
    
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        log "預覽模式 - 將執行以下命令:"
        echo "docker-compose -f $compose_file pull"
        echo "docker-compose -f $compose_file build"
        echo "docker-compose -f $compose_file up -d"
        return 0
    fi
    
    # 拉取最新鏡像
    log "拉取最新鏡像..."
    docker-compose -f "$compose_file" pull
    
    # 構建應用鏡像
    log "構建應用鏡像..."
    docker-compose -f "$compose_file" build
    
    # 啟動服務
    log "啟動服務..."
    docker-compose -f "$compose_file" up -d
    
    # 等待服務啟動
    log "等待服務啟動..."
    sleep 30
    
    # 健康檢查
    if check_health; then
        log_success "部署完成！服務運行正常"
        
        # 記錄部署信息
        cat > "$DEPLOYMENT_DIR/.deployment_info" << EOF
{
    "deployed_at": "$(date -Iseconds)",
    "environment": "$environment",
    "version": "$(git describe --tags --always 2>/dev/null || echo 'unknown')",
    "compose_file": "$compose_file",
    "deployed_by": "$(whoami)"
}
EOF
    else
        log_error "部署失敗！服務健康檢查不通過"
        
        # 如果是生產環境，自動回滾
        if [[ "$environment" == "prod" || "$environment" == "production" ]]; then
            log_warning "自動回滾..."
            local rollback_backup
            rollback_backup=$(grep "ROLLBACK_BACKUP=" "$DEPLOYMENT_DIR/.last_deployment" | cut -d'=' -f2)
            if [[ -n "$rollback_backup" ]]; then
                restore_backup "$rollback_backup"
            fi
        fi
        
        exit 1
    fi
}

# 回滾函數
rollback() {
    local version="$1"
    
    log "回滾到版本: $version"
    
    # 確認回滾
    if [[ "${FORCE:-false}" != "true" ]]; then
        echo -n "確認回滾到 $version？ [y/N] "
        read -r confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            log "回滾已取消"
            exit 0
        fi
    fi
    
    # 檢查備份是否存在
    local backup_file="$BACKUP_DIR/${version}.tar.gz"
    if [[ ! -f "$backup_file" ]]; then
        log_error "找不到版本 $version 的備份文件"
        exit 1
    fi
    
    # 創建回滾前備份
    log "創建回滾前備份..."
    create_backup
    
    # 恢復備份
    restore_backup "$version"
    
    log_success "回滾完成"
}

# 恢復備份
restore_backup() {
    local backup_name="$1"
    local backup_file="$BACKUP_DIR/${backup_name}.tar.gz"
    
    log "恢復備份: $backup_name"
    
    if [[ ! -f "$backup_file" ]]; then
        log_error "找不到備份文件: $backup_file"
        exit 1
    fi
    
    # 停止服務
    cd "$DEPLOYMENT_DIR"
    docker-compose down
    
    # 解壓備份
    cd "$BACKUP_DIR"
    tar -xzf "${backup_name}.tar.gz"
    
    # 恢復文件
    if [[ -f "$BACKUP_DIR/$backup_name/discord_data.db" ]]; then
        cp "$BACKUP_DIR/$backup_name/discord_data.db" "$DEPLOYMENT_DIR/data/"
        log "恢復主資料庫"
    fi
    
    if [[ -f "$BACKUP_DIR/$backup_name/message.db" ]]; then
        cp "$BACKUP_DIR/$backup_name/message.db" "$DEPLOYMENT_DIR/data/"
        log "恢復訊息資料庫"
    fi
    
    if [[ -f "$BACKUP_DIR/$backup_name/.env" ]]; then
        cp "$BACKUP_DIR/$backup_name/.env" "$DEPLOYMENT_DIR/"
        log "恢復環境配置"
    fi
    
    # 清理臨時文件
    rm -rf "$BACKUP_DIR/$backup_name"
    
    # 重新啟動服務
    log "重新啟動服務..."
    docker-compose up -d
    
    log_success "備份恢復完成"
}

# 健康檢查
check_health() {
    log "執行健康檢查..."
    
    local max_attempts=5
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        log "健康檢查嘗試 $attempt/$max_attempts"
        
        # 檢查容器狀態
        if docker-compose ps | grep -q "Up.*healthy"; then
            log_success "所有服務運行正常"
            return 0
        fi
        
        sleep 10
        ((attempt++))
    done
    
    log_error "健康檢查失敗"
    return 1
}

# 查看狀態
show_status() {
    log "查看系統狀態..."
    
    echo "=== 容器狀態 ==="
    docker-compose ps
    
    echo -e "\n=== 系統資源 ==="
    docker stats --no-stream
    
    echo -e "\n=== 磁盤使用 ==="
    df -h | grep -E "(docker|discord-bot)"
    
    if [[ -f "$DEPLOYMENT_DIR/.deployment_info" ]]; then
        echo -e "\n=== 部署信息 ==="
        cat "$DEPLOYMENT_DIR/.deployment_info"
    fi
}

# 查看日誌
show_logs() {
    local service="${1:-}"
    
    if [[ -n "$service" ]]; then
        log "查看 $service 服務日誌..."
        docker-compose logs -f --tail=100 "$service"
    else
        log "查看所有服務日誌..."
        docker-compose logs -f --tail=100
    fi
}

# 清理備份
cleanup_backups() {
    local retention_days="${BACKUP_RETENTION:-30}"
    
    log "清理 $retention_days 天前的備份..."
    
    find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +$retention_days -delete
    
    log_success "備份清理完成"
}

# 主函數
main() {
    # 解析命令行參數
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -v|--verbose)
                set -x
                shift
                ;;
            -f|--force)
                FORCE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            *)
                break
                ;;
        esac
    done
    
    local command="${1:-help}"
    
    # 創建日誌目錄
    mkdir -p "$(dirname "$LOG_FILE")"
    
    case "$command" in
        deploy)
            check_prerequisites
            deploy "${2:-dev}"
            ;;
        rollback)
            if [[ -z "${2:-}" ]]; then
                log_error "請指定要回滾的版本"
                exit 1
            fi
            check_prerequisites
            rollback "$2"
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs "${2:-}"
            ;;
        backup)
            check_prerequisites
            create_backup
            ;;
        restore)
            if [[ -z "${2:-}" ]]; then
                log_error "請指定要恢復的備份"
                exit 1
            fi
            check_prerequisites
            restore_backup "$2"
            ;;
        health)
            check_health
            ;;
        stop)
            log "停止所有服務..."
            docker-compose down
            log_success "服務已停止"
            ;;
        start)
            log "啟動所有服務..."
            docker-compose up -d
            log_success "服務已啟動"
            ;;
        restart)
            log "重啟所有服務..."
            docker-compose restart
            log_success "服務已重啟"
            ;;
        cleanup)
            cleanup_backups
            ;;
        help|*)
            show_help
            exit 0
            ;;
    esac
}

# 執行主函數
main "$@"