#!/bin/bash
# T3 併發壓測 CI 整合腳本
# 自動執行壓測並檢查效能門檻

set -e

# 腳本配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPORTS_DIR="$PROJECT_ROOT/test_reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_PREFIX="ci_performance_test_$TIMESTAMP"

# 建立報告目錄
mkdir -p "$REPORTS_DIR"

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

echo_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

echo_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 效能門檻配置
MIN_SUCCESS_RATE=0.99      # 99%
MIN_TPS=1000               # 1000 ops/sec
MAX_P99_LATENCY=100        # 100ms

# 壓測配置
OPERATIONS=5000
WORKERS=10
TEST_TYPE="ci"  # ci, daily, or full

# 解析命令行參數
while [[ $# -gt 0 ]]; do
    case $1 in
        --operations)
            OPERATIONS="$2"
            shift 2
            ;;
        --workers)
            WORKERS="$2"
            shift 2
            ;;
        --type)
            TEST_TYPE="$2"
            shift 2
            ;;
        --success-rate)
            MIN_SUCCESS_RATE="$2"
            shift 2
            ;;
        --min-tps)
            MIN_TPS="$2"
            shift 2
            ;;
        --max-latency)
            MAX_P99_LATENCY="$2"
            shift 2
            ;;
        -h|--help)
            echo "使用方法: $0 [選項]"
            echo "選項:"
            echo "  --operations NUM    總操作數 (預設: $OPERATIONS)"
            echo "  --workers NUM       併發工作者數 (預設: $WORKERS)"
            echo "  --type TYPE         測試類型 ci|daily|full (預設: $TEST_TYPE)"
            echo "  --success-rate RATE 最低成功率 (預設: $MIN_SUCCESS_RATE)"
            echo "  --min-tps NUM       最低TPS (預設: $MIN_TPS)"
            echo "  --max-latency MS    最大P99延遲 (預設: ${MAX_P99_LATENCY}ms)"
            echo "  -h, --help          顯示此幫助"
            exit 0
            ;;
        *)
            echo_error "未知參數: $1"
            exit 1
            ;;
    esac
done

# 根據測試類型調整配置
case $TEST_TYPE in
    "ci")
        OPERATIONS=${OPERATIONS:-1000}
        WORKERS=${WORKERS:-5}
        echo_info "執行 CI 快速壓測"
        ;;
    "daily")
        OPERATIONS=${OPERATIONS:-10000}
        WORKERS=${WORKERS:-10}
        echo_info "執行每日回歸壓測"
        ;;
    "full")
        OPERATIONS=${OPERATIONS:-50000}
        WORKERS=${WORKERS:-20}
        echo_info "執行完整效能測試"
        ;;
    *)
        echo_error "未知測試類型: $TEST_TYPE"
        exit 1
        ;;
esac

echo_info "壓測配置: $OPERATIONS 操作, $WORKERS 工作者"

# 執行壓測
echo_info "開始執行壓測..."
cd "$PROJECT_ROOT"

python scripts/load_test_activity.py \
    --operations "$OPERATIONS" \
    --workers "$WORKERS" \
    --output "$REPORTS_DIR/$REPORT_PREFIX" \
    --verbose

# 檢查壓測是否成功執行
if [ $? -ne 0 ]; then
    echo_error "壓測執行失敗"
    exit 1
fi

# 讀取並分析報告
JSON_REPORT="$REPORTS_DIR/${REPORT_PREFIX}_$(date +%Y%m%d_%H%M%S).json"
MD_REPORT="$REPORTS_DIR/${REPORT_PREFIX}_$(date +%Y%m%d_%H%M%S).md"

# 尋找最新生成的報告文件
JSON_REPORT=$(ls -t "$REPORTS_DIR"/${REPORT_PREFIX}_*.json 2>/dev/null | head -1)
MD_REPORT=$(ls -t "$REPORTS_DIR"/${REPORT_PREFIX}_*.md 2>/dev/null | head -1)

if [ -z "$JSON_REPORT" ] || [ ! -f "$JSON_REPORT" ]; then
    echo_error "找不到壓測報告文件"
    exit 1
fi

echo_info "分析報告: $JSON_REPORT"

# 解析 JSON 報告 (使用 python)
ANALYSIS=$(python3 << EOF
import json
import sys

try:
    with open('$JSON_REPORT', 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    success_rate = report['success_rate']
    tps = report['operations_per_second']
    p99_latency = report['latency_p99']
    
    print(f"SUCCESS_RATE={success_rate}")
    print(f"TPS={tps}")
    print(f"P99_LATENCY={p99_latency}")
    
    # 檢查門檻
    success_rate_pass = success_rate >= $MIN_SUCCESS_RATE
    tps_pass = tps >= $MIN_TPS
    latency_pass = p99_latency <= $MAX_P99_LATENCY
    
    print(f"SUCCESS_RATE_PASS={success_rate_pass}")
    print(f"TPS_PASS={tps_pass}")
    print(f"LATENCY_PASS={latency_pass}")
    
except Exception as e:
    print(f"ERROR={e}", file=sys.stderr)
    sys.exit(1)
EOF
)

if [ $? -ne 0 ]; then
    echo_error "報告分析失敗"
    exit 1
fi

# 提取分析結果
eval "$ANALYSIS"

# 顯示結果
echo
echo "=================== 效能測試結果 ==================="
echo

printf "%-20s %-15s %-10s %-10s\n" "指標" "實際值" "門檻" "狀態"
echo "----------------------------------------------------"

# 成功率檢查
if [ "$SUCCESS_RATE_PASS" = "True" ]; then
    SUCCESS_STATUS="${GREEN}PASS${NC}"
else
    SUCCESS_STATUS="${RED}FAIL${NC}"
fi
printf "%-20s %-15.2f%% %-10.2f%% %s\n" "成功率" "$(echo "$SUCCESS_RATE * 100" | bc -l)" "$(echo "$MIN_SUCCESS_RATE * 100" | bc -l)" "$SUCCESS_STATUS"

# TPS 檢查
if [ "$TPS_PASS" = "True" ]; then
    TPS_STATUS="${GREEN}PASS${NC}"
else
    TPS_STATUS="${RED}FAIL${NC}"
fi
printf "%-20s %-15.2f %-10d %s\n" "TPS (ops/sec)" "$TPS" "$MIN_TPS" "$TPS_STATUS"

# 延遲檢查  
if [ "$LATENCY_PASS" = "True" ]; then
    LATENCY_STATUS="${GREEN}PASS${NC}"
else
    LATENCY_STATUS="${RED}FAIL${NC}"
fi
printf "%-20s %-15.2f ms %-10d ms %s\n" "P99 延遲" "$P99_LATENCY" "$MAX_P99_LATENCY" "$LATENCY_STATUS"

echo "===================================================="

# 總體結果判定
if [ "$SUCCESS_RATE_PASS" = "True" ] && [ "$TPS_PASS" = "True" ] && [ "$LATENCY_PASS" = "True" ]; then
    echo_success "所有效能門檻測試通過！"
    
    # 顯示報告位置
    echo_info "詳細報告:"
    echo "  JSON: $JSON_REPORT"
    echo "  Markdown: $MD_REPORT"
    
    exit 0
else
    echo_error "效能測試未通過門檻要求"
    
    # 顯示失敗詳情
    if [ "$SUCCESS_RATE_PASS" = "False" ]; then
        echo_warning "成功率不足: $(echo "$SUCCESS_RATE * 100" | bc -l)% < $(echo "$MIN_SUCCESS_RATE * 100" | bc -l)%"
    fi
    
    if [ "$TPS_PASS" = "False" ]; then
        echo_warning "TPS 不足: $TPS < $MIN_TPS"
    fi
    
    if [ "$LATENCY_PASS" = "False" ]; then
        echo_warning "延遲過高: $P99_LATENCY ms > $MAX_P99_LATENCY ms"
    fi
    
    echo_info "檢查報告以了解詳情: $MD_REPORT"
    
    exit 1
fi