#!/bin/bash
# ROAS Bot v2.4.3 智能快速啟動腳本
# Task ID: 1 - Docker啟動系統修復
# 
# 此腳本整合所有優化功能，提供最佳的啟動體驗

set -euo pipefail

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${ENVIRONMENT:-dev}"
VERBOSE="${VERBOSE:-false}"
FORCE="${FORCE:-false}"
DRY_RUN="${DRY_RUN:-false}"
SKIP_HEALTH_CHECK="${SKIP_HEALTH_CHECK:-false}"

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# 日誌函數
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# 顯示橫幅
show_banner() {
    echo -e "${CYAN}"
    cat << 'EOF'
╭─────────────────────────────────────────────────────────────╮
│                 ROAS Bot v2.4.3 智能啟動系統                  │
│                     Task ID: 1 - Docker優化                  │
╰─────────────────────────────────────────────────────────────╯
EOF
    echo -e "${NC}"
    
    echo -e "${WHITE}專案根目錄:${NC} $PROJECT_ROOT"
    echo -e "${WHITE}環境:${NC} $ENVIRONMENT"
    echo -e "${WHITE}模式:${NC} $([ "$DRY_RUN" == "true" ] && echo "模擬運行" || echo "實際部署")"
    echo -e "${WHITE}開始時間:${NC} $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
}

# 顯示幫助
show_help() {
    cat << EOF
ROAS Bot v2.4.3 智能快速啟動腳本

用法:
    $0 [選項]

選項:
    -e, --environment ENV    設置環境 (dev/prod) [默認: dev]
    -v, --verbose           詳細輸出
    -f, --force             強制啟動，忽略檢查失敗
    -d, --dry-run           模擬運行，不執行實際操作
    -s, --skip-health       跳過健康檢查
    -q, --quick             快速模式（跳過部分檢查）
    -r, --restart           重啟現有服務
    -c, --clean             清理後啟動
    --report-only           僅生成現狀報告
    --use-python            使用Python智能部署系統
    -h, --help              顯示此幫助信息

範例:
    $0                      # 使用默認設置啟動
    $0 -e prod -f           # 強制在生產環境啟動
    $0 -d -v                # 詳細模擬運行
    $0 --quick              # 快速啟動模式
    $0 --clean -e prod      # 清理後在生產環境啟動
EOF
}

# 解析命令行參數
parse_arguments() {
    local use_python=false
    local quick_mode=false
    local restart_mode=false
    local clean_mode=false
    local report_only=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -f|--force)
                FORCE=true
                shift
                ;;
            -d|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -s|--skip-health)
                SKIP_HEALTH_CHECK=true
                shift
                ;;
            -q|--quick)
                quick_mode=true
                shift
                ;;
            -r|--restart)
                restart_mode=true
                shift
                ;;
            -c|--clean)
                clean_mode=true
                shift
                ;;
            --report-only)
                report_only=true
                shift
                ;;
            --use-python)
                use_python=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知參數: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 設置模式標誌
    export QUICK_MODE="$quick_mode"
    export RESTART_MODE="$restart_mode"
    export CLEAN_MODE="$clean_mode"
    export REPORT_ONLY="$report_only"
    export USE_PYTHON="$use_python"
}

# 環境檢查
check_environment() {
    log_info "執行環境檢查..."
    
    # 檢查Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安裝或不在 PATH 中"
        return 1
    fi
    
    # 檢查Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose 未安裝或不在 PATH 中"
        return 1
    fi
    
    # 檢查Docker服務狀態
    if ! docker info &> /dev/null; then
        log_error "Docker 服務未運行"
        return 1
    fi
    
    # 檢查Python環境（如果使用Python模式）
    if [[ "$USE_PYTHON" == "true" ]]; then
        if ! command -v python3 &> /dev/null; then
            log_error "Python3 未安裝"
            return 1
        fi
        
        # 檢查必要的Python模組
        local required_modules=("asyncio" "pathlib" "yaml")
        for module in "${required_modules[@]}"; do
            if ! python3 -c "import $module" &> /dev/null; then
                log_error "缺少Python模組: $module"
                return 1
            fi
        done
    fi
    
    # 檢查項目文件
    local required_files=(
        "docker-compose.${ENVIRONMENT}.yml"
    )
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$PROJECT_ROOT/$file" ]]; then
            log_error "缺少必要文件: $file"
            return 1
        fi
    done
    
    log_success "環境檢查通過"
    return 0
}

# 執行預檢查
pre_flight_check() {
    log_info "執行飛行前檢查..."
    
    # 磁盤空間檢查
    local available_space
    available_space=$(df "$PROJECT_ROOT" | awk 'NR==2 {print $4}')
    local available_gb=$((available_space / 1024 / 1024))
    
    if [[ $available_gb -lt 2 ]]; then
        if [[ "$FORCE" != "true" ]]; then
            log_error "磁盤空間不足 (${available_gb}GB)，需要至少 2GB"
            return 1
        else
            log_warn "磁盤空間不足，但使用強制模式繼續"
        fi
    fi
    
    log_debug "可用磁盤空間: ${available_gb}GB"
    
    # 檢查端口占用
    local ports=("8000" "6379" "3000" "9090")
    local occupied_ports=()
    
    for port in "${ports[@]}"; do
        if lsof -Pi :$port -sTCP:LISTEN -t &> /dev/null; then
            occupied_ports+=("$port")
        fi
    done
    
    if [[ ${#occupied_ports[@]} -gt 0 ]] && [[ "$QUICK_MODE" != "true" ]]; then
        log_warn "以下端口被占用: ${occupied_ports[*]}"
        if [[ "$FORCE" != "true" ]]; then
            log_error "端口衝突，使用 --force 強制繼續或 --clean 清理"
            return 1
        fi
    fi
    
    log_success "飛行前檢查通過"
    return 0
}

# 清理現有服務
cleanup_services() {
    log_info "清理現有服務..."
    
    local compose_file="$PROJECT_ROOT/docker-compose.${ENVIRONMENT}.yml"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[模擬] 將停止並清理服務"
        return 0
    fi
    
    # 停止服務
    if docker-compose -f "$compose_file" ps -q | grep -q .; then
        log_info "停止現有服務..."
        docker-compose -f "$compose_file" down --remove-orphans
    fi
    
    # 清理未使用的資源
    log_info "清理未使用的Docker資源..."
    docker system prune -f --volumes
    
    log_success "清理完成"
}

# 準備服務
prepare_services() {
    log_info "準備服務..."
    
    local compose_file="$PROJECT_ROOT/docker-compose.${ENVIRONMENT}.yml"
    
    # 創建必要目錄
    local directories=("logs" "data" "backups")
    for dir in "${directories[@]}"; do
        mkdir -p "$PROJECT_ROOT/$dir"
        log_debug "創建目錄: $dir"
    done
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[模擬] 將拉取並建置映像"
        return 0
    fi
    
    # 拉取映像
    if [[ "$QUICK_MODE" != "true" ]]; then
        log_info "拉取最新映像..."
        docker-compose -f "$compose_file" pull --ignore-pull-failures
    fi
    
    # 建置映像
    log_info "建置服務映像..."
    docker-compose -f "$compose_file" build --parallel
    
    log_success "服務準備完成"
}

# 啟動服務
start_services() {
    log_info "啟動服務..."
    
    local compose_file="$PROJECT_ROOT/docker-compose.${ENVIRONMENT}.yml"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[模擬] 將啟動所有服務"
        return 0
    fi
    
    # 啟動服務
    log_info "啟動所有服務..."
    docker-compose -f "$compose_file" up -d
    
    # 等待服務啟動
    if [[ "$SKIP_HEALTH_CHECK" != "true" ]]; then
        log_info "等待服務啟動..."
        sleep 10
    fi
    
    log_success "服務啟動完成"
}

# 健康檢查
health_check() {
    if [[ "$SKIP_HEALTH_CHECK" == "true" ]]; then
        log_info "跳過健康檢查"
        return 0
    fi
    
    log_info "執行健康檢查..."
    
    local compose_file="$PROJECT_ROOT/docker-compose.${ENVIRONMENT}.yml"
    local max_retries=12
    local retry_count=0
    
    while [[ $retry_count -lt $max_retries ]]; do
        local healthy_count=0
        local total_count=0
        
        # 獲取服務狀態
        while IFS= read -r line; do
            if [[ -n "$line" ]]; then
                total_count=$((total_count + 1))
                if echo "$line" | grep -q "healthy\|Up"; then
                    healthy_count=$((healthy_count + 1))
                fi
            fi
        done < <(docker-compose -f "$compose_file" ps --format "table {{.State}}" | tail -n +2)
        
        if [[ $healthy_count -eq $total_count ]] && [[ $total_count -gt 0 ]]; then
            log_success "所有服務健康 ($healthy_count/$total_count)"
            return 0
        fi
        
        log_debug "健康服務: $healthy_count/$total_count (重試 $((retry_count + 1))/$max_retries)"
        retry_count=$((retry_count + 1))
        sleep 5
    done
    
    log_warn "健康檢查超時，部分服務可能未完全啟動"
    
    if [[ "$FORCE" != "true" ]]; then
        return 1
    fi
    
    return 0
}

# 顯示服務狀態
show_service_status() {
    log_info "服務狀態概覽:"
    
    local compose_file="$PROJECT_ROOT/docker-compose.${ENVIRONMENT}.yml"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${YELLOW}[模擬模式] 服務狀態會在實際部署後顯示${NC}"
        return 0
    fi
    
    echo ""
    docker-compose -f "$compose_file" ps
    echo ""
    
    # 顯示端口信息
    log_info "服務端點:"
    local services=()
    
    # 從docker-compose文件提取服務和端口信息
    if command -v yq &> /dev/null; then
        # 如果有yq，使用它來解析YAML
        while IFS= read -r service; do
            services+=("$service")
        done < <(yq e '.services | keys | .[]' "$compose_file" 2>/dev/null || echo "")
    else
        # 簡單解析
        services=("discord-bot" "redis" "prometheus" "grafana")
    fi
    
    for service in "${services[@]}"; do
        case $service in
            "discord-bot")
                echo -e "  ${GREEN}🤖 Discord Bot:${NC} http://localhost:8000"
                ;;
            "redis")
                echo -e "  ${RED}📊 Redis:${NC} localhost:6379"
                ;;
            "prometheus")
                echo -e "  ${BLUE}📈 Prometheus:${NC} http://localhost:9090"
                ;;
            "grafana")
                echo -e "  ${PURPLE}📊 Grafana:${NC} http://localhost:3000"
                ;;
        esac
    done
    
    echo ""
}

# 生成狀態報告
generate_report() {
    log_info "生成狀態報告..."
    
    local report_file="$PROJECT_ROOT/logs/startup-report-$(date +%Y%m%d-%H%M%S).json"
    mkdir -p "$(dirname "$report_file")"
    
    local compose_file="$PROJECT_ROOT/docker-compose.${ENVIRONMENT}.yml"
    
    # 基本信息
    cat > "$report_file" << EOF
{
  "report_timestamp": "$(date -Iseconds)",
  "environment": "$ENVIRONMENT",
  "project_root": "$PROJECT_ROOT",
  "startup_method": "bash_script",
  "dry_run": $DRY_RUN,
  "force_mode": $FORCE,
  "quick_mode": $QUICK_MODE
EOF
    
    if [[ "$DRY_RUN" != "true" ]]; then
        # 服務狀態
        echo '  ,"services": {' >> "$report_file"
        
        local first_service=true
        while IFS= read -r line; do
            if [[ -n "$line" ]]; then
                local service_name=$(echo "$line" | awk '{print $1}')
                local service_state=$(echo "$line" | awk '{print $2}')
                
                if [[ "$first_service" == "true" ]]; then
                    first_service=false
                else
                    echo '    ,' >> "$report_file"
                fi
                
                echo "    \"$service_name\": \"$service_state\"" >> "$report_file"
            fi
        done < <(docker-compose -f "$compose_file" ps --format "{{.Name}} {{.State}}" 2>/dev/null)
        
        echo '  }' >> "$report_file"
        
        # Docker系統信息
        echo '  ,"docker_info": {' >> "$report_file"
        echo "    \"version\": \"$(docker --version | cut -d' ' -f3 | tr -d ',')\"," >> "$report_file"
        echo "    \"compose_version\": \"$(docker-compose --version | cut -d' ' -f3 | tr -d ',')\"" >> "$report_file"
        echo '  }' >> "$report_file"
    fi
    
    echo '}' >> "$report_file"
    
    log_success "報告已保存到: $report_file"
}

# 使用Python智能部署系統
use_python_deployment() {
    log_info "使用Python智能部署系統..."
    
    local python_script="$PROJECT_ROOT/scripts/smart_deployment.py"
    
    if [[ ! -f "$python_script" ]]; then
        log_error "Python智能部署腳本不存在: $python_script"
        return 1
    fi
    
    local python_args=()
    python_args+=("--environment" "$ENVIRONMENT")
    
    if [[ "$DRY_RUN" == "true" ]]; then
        python_args+=("--dry-run")
    fi
    
    if [[ "$FORCE" == "true" ]]; then
        python_args+=("--force")
    fi
    
    if [[ "$VERBOSE" == "true" ]]; then
        python_args+=("--verbose")
    fi
    
    if [[ "$REPORT_ONLY" == "true" ]]; then
        python_args+=("--report-only")
    fi
    
    python_args+=("--project-root" "$PROJECT_ROOT")
    
    log_info "執行命令: python3 $python_script ${python_args[*]}"
    
    if python3 "$python_script" "${python_args[@]}"; then
        log_success "Python智能部署完成"
        return 0
    else
        log_error "Python智能部署失敗"
        return 1
    fi
}

# 主要執行流程
main() {
    local start_time=$(date +%s)
    
    # 顯示橫幅
    show_banner
    
    # 錯誤處理
    trap 'log_error "腳本執行被中斷"; exit 1' INT TERM
    
    # 如果使用Python模式
    if [[ "$USE_PYTHON" == "true" ]]; then
        if use_python_deployment; then
            log_success "部署完成"
            return 0
        else
            return 1
        fi
    fi
    
    # 僅生成報告模式
    if [[ "$REPORT_ONLY" == "true" ]]; then
        generate_report
        return 0
    fi
    
    # 執行檢查
    if ! check_environment; then
        log_error "環境檢查失敗"
        return 1
    fi
    
    if [[ "$QUICK_MODE" != "true" ]]; then
        if ! pre_flight_check; then
            log_error "飛行前檢查失敗"
            return 1
        fi
    fi
    
    # 清理模式
    if [[ "$CLEAN_MODE" == "true" ]] || [[ "$RESTART_MODE" == "true" ]]; then
        cleanup_services
    fi
    
    # 準備和啟動服務
    if ! prepare_services; then
        log_error "服務準備失敗"
        return 1
    fi
    
    if ! start_services; then
        log_error "服務啟動失敗"
        return 1
    fi
    
    # 健康檢查
    if ! health_check; then
        log_error "健康檢查失敗"
        return 1
    fi
    
    # 顯示狀態
    show_service_status
    
    # 生成報告
    generate_report
    
    # 計算執行時間
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_success "啟動完成！總耗時: ${duration}秒"
    
    if [[ "$ENVIRONMENT" == "dev" ]]; then
        echo -e "\n${CYAN}開發提示:${NC}"
        echo -e "• 查看日誌: docker-compose -f docker-compose.dev.yml logs -f"
        echo -e "• 停止服務: docker-compose -f docker-compose.dev.yml down"
        echo -e "• 重啟服務: $0 --restart"
    fi
    
    return 0
}

# 解析參數並執行主函數
parse_arguments "$@"
main
exit_code=$?

if [[ $exit_code -eq 0 ]]; then
    log_success "🎉 ROAS Bot v2.4.3 智能啟動完成！"
else
    log_error "😞 啟動過程遇到問題，請檢查上方輸出"
    echo -e "\n${YELLOW}故障排除提示:${NC}"
    echo -e "• 使用 --verbose 獲取詳細信息"
    echo -e "• 使用 --force 忽略警告強制執行"
    echo -e "• 使用 --clean 清理後重新啟動"
    echo -e "• 使用 --use-python 嘗試Python智能部署"
fi

exit $exit_code