#!/bin/bash
# T5 隨機測試執行腳本
# Task ID: T5 - Discord testing: dpytest and random interactions

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 預設參數
DEFAULT_SEED=$(date +%s)
DEFAULT_MAX_STEPS=10
DEFAULT_RUNS=1
DEFAULT_TIMEOUT=300

# 解析命令行參數
SEED=${1:-$DEFAULT_SEED}
MAX_STEPS=${2:-$DEFAULT_MAX_STEPS}
RUNS=${3:-$DEFAULT_RUNS}
TIMEOUT=${4:-$DEFAULT_TIMEOUT}

echo -e "${BLUE}🚀 T5 隨機交互測試執行腳本${NC}"
echo "=================================================="
echo -e "種子 (Seed): ${GREEN}$SEED${NC}"
echo -e "最大步數: ${GREEN}$MAX_STEPS${NC}"
echo -e "執行次數: ${GREEN}$RUNS${NC}"
echo -e "超時時間: ${GREEN}$TIMEOUT${NC} 秒"
echo "=================================================="

# 檢查依賴
echo -e "${YELLOW}📋 檢查環境依賴...${NC}"

if ! command -v python &> /dev/null; then
    echo -e "${RED}❌ Python 未安裝${NC}"
    exit 1
fi

if ! python -c "import pytest" &> /dev/null; then
    echo -e "${RED}❌ pytest 未安裝${NC}"
    exit 1
fi

if ! python -c "from discord.ext import test as dpytest" &> /dev/null; then
    echo -e "${RED}❌ dpytest 未可用${NC}"
    echo -e "${YELLOW}💡 請執行: pip install -e \".[dev]\"${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 環境檢查通過${NC}"

# 創建測試報告目錄
mkdir -p test_reports
mkdir -p logs

# 記錄開始時間
START_TIME=$(date +%s)
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo -e "${YELLOW}🧪 開始執行隨機交互測試...${NC}"

# 測試結果統計
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# 運行測試
for ((i=1; i<=RUNS; i++)); do
    echo -e "${BLUE}📋 執行第 $i/$RUNS 次測試...${NC}"
    
    # 如果是多次運行，為每次使用不同的種子
    if [ $RUNS -gt 1 ]; then
        CURRENT_SEED=$((SEED + i))
    else
        CURRENT_SEED=$SEED
    fi
    
    echo -e "使用種子: ${GREEN}$CURRENT_SEED${NC}"
    
    # 執行測試
    TEST_OUTPUT_FILE="test_reports/random_test_run_${i}_${TIMESTAMP}.log"
    
    # macOS 相容性：使用 gtimeout 或 跳過 timeout
    TIMEOUT_CMD=""
    if command -v gtimeout &> /dev/null; then
        TIMEOUT_CMD="gtimeout $TIMEOUT"
    elif command -v timeout &> /dev/null; then
        TIMEOUT_CMD="timeout $TIMEOUT"
    else
        echo -e "${YELLOW}⚠️  timeout 命令不可用，跳過超時限制${NC}"
    fi
    
    if $TIMEOUT_CMD python -m pytest tests/random/test_random_interactions.py \
        --seed=$CURRENT_SEED \
        --max-steps=$MAX_STEPS \
        -v --tb=short \
        --junitxml="test_reports/random_test_run_${i}_${TIMESTAMP}.xml" \
        > "$TEST_OUTPUT_FILE" 2>&1; then
        
        echo -e "${GREEN}✅ 第 $i 次測試通過${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}❌ 第 $i 次測試失敗${NC}"
        echo -e "${YELLOW}📄 錯誤日誌: $TEST_OUTPUT_FILE${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        
        # 顯示失敗摘要
        if [ -f "$TEST_OUTPUT_FILE" ]; then
            echo -e "${YELLOW}🔍 失敗摘要:${NC}"
            tail -10 "$TEST_OUTPUT_FILE" | grep -E "(FAILED|ERROR|AssertionError)" || echo "無明確錯誤信息"
        fi
    fi
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    # 如果是多次運行，添加間隔
    if [ $i -lt $RUNS ]; then
        echo -e "${BLUE}⏰ 等待 2 秒後繼續...${NC}"
        sleep 2
    fi
done

# 計算總執行時間
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "=================================================="
echo -e "${BLUE}📊 測試執行總結${NC}"
echo "=================================================="
echo -e "總測試數: ${BLUE}$TOTAL_TESTS${NC}"
echo -e "通過測試: ${GREEN}$PASSED_TESTS${NC}"
echo -e "失敗測試: ${RED}$FAILED_TESTS${NC}"
echo -e "成功率: ${GREEN}$(( PASSED_TESTS * 100 / TOTAL_TESTS ))%${NC}"
echo -e "執行時間: ${BLUE}${DURATION}${NC} 秒"

# 生成總結報告
SUMMARY_FILE="test_reports/random_test_summary_${TIMESTAMP}.json"
cat > "$SUMMARY_FILE" << EOF
{
  "test_summary": {
    "timestamp": "${TIMESTAMP}",
    "total_tests": ${TOTAL_TESTS},
    "passed_tests": ${PASSED_TESTS},
    "failed_tests": ${FAILED_TESTS},
    "success_rate": $(( PASSED_TESTS * 100 / TOTAL_TESTS )),
    "duration_seconds": ${DURATION},
    "parameters": {
      "seed": ${SEED},
      "max_steps": ${MAX_STEPS},
      "runs": ${RUNS},
      "timeout": ${TIMEOUT}
    }
  }
}
EOF

echo -e "${GREEN}📋 總結報告已生成: $SUMMARY_FILE${NC}"

# 檢查是否有失敗報告
FAILURE_REPORTS=$(find test_reports -name "random_test_failure_*.json" -newer test_reports 2>/dev/null | wc -l)
if [ $FAILURE_REPORTS -gt 0 ]; then
    echo -e "${YELLOW}🔍 發現 $FAILURE_REPORTS 個失敗報告，可用於重現問題${NC}"
    echo -e "${YELLOW}💡 重現指令示例:${NC}"
    echo "   python -m pytest tests/random/test_random_interactions.py --seed=$SEED"
fi

# 清理舊的測試文件（保留最近 10 個）
find test_reports -name "random_test_*.log" -type f | sort -r | tail -n +11 | xargs rm -f 2>/dev/null || true
find test_reports -name "random_test_*.xml" -type f | sort -r | tail -n +11 | xargs rm -f 2>/dev/null || true

echo "=================================================="

# 設置退出碼
if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}🎉 所有測試通過！${NC}"
    exit 0
else
    echo -e "${RED}💥 有測試失敗，請檢查錯誤報告${NC}"
    exit 1
fi