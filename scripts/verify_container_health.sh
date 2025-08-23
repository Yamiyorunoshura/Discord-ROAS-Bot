#!/bin/bash
# Discord機器人容器健康檢查與驗證工具
# Task ID: T6 - Docker跨平台一鍵啟動腳本開發

set -euo pipefail

# 設定變數
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/docker/compose.yaml"
DEFAULT_PROFILE="default"
OUTPUT_FORMAT="text"
CHECK_TIMEOUT=30

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# 參數預設值
PROFILE="$DEFAULT_PROFILE"
VERBOSE=false
JSON_OUTPUT=false
CONTINUOUS=false
INTERVAL=30

# 函數：顯示用法
show_usage() {
    cat << EOF
使用方法: $0 [選項]

選項:
  -p, --profile PROFILE   檢查指定profile的服務 (預設: default)
  -f, --format FORMAT     輸出格式: text|json (預設: text)
  -v, --verbose           顯示詳細輸出
  -c, --continuous        持續監控模式
  -i, --interval SECONDS  持續監控間隔 (預設: 30)
  -t, --timeout SECONDS   健康檢查超時時間 (預設: 30)
  -h, --help             顯示此說明

範例:
  $0                              # 檢查預設profile的服務健康狀態
  $0 -p prod -f json             # 以JSON格式檢查生產環境
  $0 -v -c -i 10                 # 詳細模式持續監控，每10秒檢查一次
  $0 -p dev --timeout 60         # 檢查開發環境，超時60秒
EOF
}

# 函數：記錄訊息
log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    if [[ "$JSON_OUTPUT" == "true" ]]; then
        return  # JSON模式下不輸出log
    fi
    
    case $level in
        "INFO")  echo -e "${BLUE}[INFO]${NC} ${timestamp} - $message" ;;
        "WARN")  echo -e "${YELLOW}[WARN]${NC} ${timestamp} - $message" ;;
        "ERROR") echo -e "${RED}[ERROR]${NC} ${timestamp} - $message" ;;
        "SUCCESS") echo -e "${GREEN}[SUCCESS]${NC} ${timestamp} - $message" ;;
        "DEBUG") if [[ "$VERBOSE" == "true" ]]; then echo -e "${PURPLE}[DEBUG]${NC} ${timestamp} - $message"; fi ;;
    esac
}

# 函數：檢查單個容器健康狀態
check_container_health() {
    local container_name=$1
    local service_name=$2
    
    if [[ -z "$container_name" ]]; then
        return 1
    fi
    
    local status=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "unknown")
    local state=$(docker inspect --format='{{.State.Status}}' "$container_name" 2>/dev/null || echo "unknown")
    local started_at=$(docker inspect --format='{{.State.StartedAt}}' "$container_name" 2>/dev/null || echo "unknown")
    local restart_count=$(docker inspect --format='{{.RestartCount}}' "$container_name" 2>/dev/null || echo "0")
    
    # 獲取容器資源使用情況
    local cpu_usage=""
    local memory_usage=""
    local memory_limit=""
    
    if command -v docker &> /dev/null && docker stats --no-stream --format "table {{.CPUPerc}}\t{{.MemUsage}}" "$container_name" &> /dev/null; then
        local stats=$(docker stats --no-stream --format "{{.CPUPerc}}\t{{.MemUsage}}" "$container_name" 2>/dev/null || echo "N/A\tN/A")
        cpu_usage=$(echo "$stats" | cut -f1)
        local mem_info=$(echo "$stats" | cut -f2)
        memory_usage=$(echo "$mem_info" | cut -d'/' -f1 | xargs)
        memory_limit=$(echo "$mem_info" | cut -d'/' -f2 | xargs)
    fi
    
    # 檢查關鍵日誌
    local error_logs=""
    local warning_logs=""
    if docker logs --tail 10 "$container_name" 2>&1 | grep -i error &> /dev/null; then
        error_logs=$(docker logs --tail 5 "$container_name" 2>&1 | grep -i error | tail -2 | tr '\n' '; ')
    fi
    if docker logs --tail 10 "$container_name" 2>&1 | grep -i warn &> /dev/null; then
        warning_logs=$(docker logs --tail 5 "$container_name" 2>&1 | grep -i warn | tail -2 | tr '\n' '; ')
    fi
    
    # 構建結果對象
    local result_json=$(cat << EOF
{
    "service": "$service_name",
    "container": "$container_name",
    "state": "$state",
    "health": "$status",
    "started_at": "$started_at",
    "restart_count": $restart_count,
    "cpu_usage": "$cpu_usage",
    "memory_usage": "$memory_usage",
    "memory_limit": "$memory_limit",
    "error_logs": "$error_logs",
    "warning_logs": "$warning_logs",
    "timestamp": "$(date -Iseconds)"
}
EOF
)
    
    echo "$result_json"
}

# 函數：檢查所有服務
check_all_services() {
    cd "$PROJECT_ROOT"
    
    # 獲取正在運行的服務列表
    local services=$(docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" ps --services 2>/dev/null || echo "")
    
    if [[ -z "$services" ]]; then
        log "WARN" "沒有找到運行中的服務（profile: $PROFILE）"
        return 1
    fi
    
    local all_results="[]"
    local healthy_count=0
    local total_count=0
    
    while read -r service; do
        if [[ -n "$service" ]]; then
            total_count=$((total_count + 1))
            log "DEBUG" "檢查服務: $service"
            
            # 獲取容器名稱
            local container_name=$(docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" ps -q "$service" 2>/dev/null | head -1)
            if [[ -n "$container_name" ]]; then
                container_name=$(docker inspect --format='{{.Name}}' "$container_name" | sed 's|^/||')
            fi
            
            local result=$(check_container_health "$container_name" "$service")
            
            # 檢查是否健康
            local health=$(echo "$result" | jq -r '.health // "unknown"')
            local state=$(echo "$result" | jq -r '.state // "unknown"')
            
            if [[ "$health" == "healthy" ]] || [[ "$state" == "running" && "$health" == "unknown" ]]; then
                healthy_count=$((healthy_count + 1))
            fi
            
            # 添加到結果陣列
            all_results=$(echo "$all_results" | jq ". += [$result]")
            
            if [[ "$JSON_OUTPUT" != "true" ]]; then
                local status_color="$RED"
                if [[ "$health" == "healthy" ]] || [[ "$state" == "running" && "$health" == "unknown" ]]; then
                    status_color="$GREEN"
                elif [[ "$health" == "starting" ]]; then
                    status_color="$YELLOW"
                fi
                
                echo -e "服務: ${BLUE}$service${NC} | 容器: ${BLUE}$container_name${NC} | 狀態: ${status_color}$state${NC} | 健康: ${status_color}$health${NC}"
                
                if [[ "$VERBOSE" == "true" ]]; then
                    local cpu=$(echo "$result" | jq -r '.cpu_usage // "N/A"')
                    local mem=$(echo "$result" | jq -r '.memory_usage // "N/A"')
                    local restart=$(echo "$result" | jq -r '.restart_count // "0"')
                    echo -e "  └─ CPU: $cpu | 記憶體: $mem | 重啟次數: $restart"
                    
                    local errors=$(echo "$result" | jq -r '.error_logs // ""')
                    if [[ -n "$errors" && "$errors" != "" ]]; then
                        echo -e "  └─ ${RED}錯誤日誌: $errors${NC}"
                    fi
                fi
            fi
        fi
    done <<< "$services"
    
    # 構建最終結果
    local summary=$(cat << EOF
{
    "profile": "$PROFILE",
    "timestamp": "$(date -Iseconds)",
    "summary": {
        "total_services": $total_count,
        "healthy_services": $healthy_count,
        "unhealthy_services": $((total_count - healthy_count)),
        "overall_health": $(if [[ $healthy_count -eq $total_count && $total_count -gt 0 ]]; then echo '"healthy"'; else echo '"unhealthy"'; fi)
    },
    "services": $all_results
}
EOF
)
    
    if [[ "$JSON_OUTPUT" == "true" ]]; then
        echo "$summary" | jq .
    else
        local overall_status="不健康"
        local status_color="$RED"
        if [[ $healthy_count -eq $total_count && $total_count -gt 0 ]]; then
            overall_status="健康"
            status_color="$GREEN"
        fi
        
        echo ""
        echo -e "總計: $total_count 個服務 | 健康: $healthy_count | 不健康: $((total_count - healthy_count))"
        echo -e "整體狀態: ${status_color}$overall_status${NC}"
        
        if [[ $healthy_count -ne $total_count ]]; then
            return 1
        fi
    fi
}

# 函數：持續監控
continuous_monitor() {
    log "INFO" "開始持續監控模式（間隔: ${INTERVAL}秒）"
    log "INFO" "按 Ctrl+C 停止監控"
    
    while true; do
        if [[ "$JSON_OUTPUT" != "true" ]]; then
            clear
            echo -e "${BLUE}=== Discord機器人容器健康檢查 - $(date) ===${NC}"
            echo ""
        fi
        
        check_all_services
        
        if [[ "$JSON_OUTPUT" != "true" ]]; then
            echo ""
            echo -e "${PURPLE}下次檢查: $(date -d "+${INTERVAL} seconds")${NC}"
        fi
        
        sleep "$INTERVAL"
    done
}

# 主函數
main() {
    # 解析命令行參數
    while [[ $# -gt 0 ]]; do
        case $1 in
            -p|--profile)
                PROFILE="$2"
                shift 2
                ;;
            -f|--format)
                OUTPUT_FORMAT="$2"
                if [[ "$OUTPUT_FORMAT" == "json" ]]; then
                    JSON_OUTPUT=true
                fi
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -c|--continuous)
                CONTINUOUS=true
                shift
                ;;
            -i|--interval)
                INTERVAL="$2"
                shift 2
                ;;
            -t|--timeout)
                CHECK_TIMEOUT="$2"
                shift 2
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
    
    # 檢查Docker Compose檔案
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log "ERROR" "Docker Compose檔案不存在: $COMPOSE_FILE"
        exit 1
    fi
    
    # 檢查jq工具（JSON處理需要）
    if ! command -v jq &> /dev/null; then
        log "ERROR" "需要安裝jq工具來處理JSON輸出"
        if [[ "$JSON_OUTPUT" == "true" ]]; then
            echo '{"error": "jq tool not found", "message": "Please install jq for JSON processing"}' 
        fi
        exit 1
    fi
    
    if [[ "$JSON_OUTPUT" != "true" ]]; then
        log "INFO" "Discord機器人容器健康檢查工具 v1.0 (T6)"
        log "INFO" "Profile: $PROFILE"
        log "INFO" "檢查超時: ${CHECK_TIMEOUT}秒"
    fi
    
    # 執行檢查
    if [[ "$CONTINUOUS" == "true" ]]; then
        continuous_monitor
    else
        check_all_services
    fi
}

# 執行主函數
main "$@"