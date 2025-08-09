#!/bin/bash
# Discord ROAS Bot 測試運行腳本

set -e  # 遇到錯誤時退出

echo "🧪 Discord ROAS Bot 測試套件"
echo "================================="

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m' 
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 檢查依賴
check_dependencies() {
    echo -e "${BLUE}檢查測試依賴...${NC}"
    
    if ! command -v pytest &> /dev/null; then
        echo -e "${RED}❌ pytest 未安裝${NC}"
        exit 1
    fi
    
    if ! command -v uv &> /dev/null; then
        echo -e "${YELLOW}⚠️  建議使用 uv 作為包管理器${NC}"
    fi
    
    echo -e "${GREEN}✅ 依賴檢查完成${NC}"
}

# 運行快速測試
run_fast_tests() {
    echo -e "${BLUE}🏃‍♂️ 運行快速測試 (單元測試 + Mock)${NC}"
    
    uv run pytest \
        -m "unit and mock and not slow" \
        --maxfail=3 \
        --tb=short \
        --disable-warnings \
        --quiet \
        tests/unit/
    
    echo -e "${GREEN}✅ 快速測試完成${NC}"
}

# 運行面板測試
run_panel_tests() {
    echo -e "${BLUE}🎨 運行面板互動測試${NC}"
    
    uv run pytest \
        -c pytest_panel.toml \
        --maxfail=5 \
        --tb=short \
        tests/unit/cogs/*/test_*panel*.py
    
    echo -e "${GREEN}✅ 面板測試完成${NC}"
}

# 運行指令測試
run_command_tests() {
    echo -e "${BLUE}⚡ 運行指令測試${NC}"
    
    uv run pytest \
        -m "command and mock" \
        --maxfail=5 \
        --tb=short \
        tests/unit/cogs/*/test_*command*.py
    
    echo -e "${GREEN}✅ 指令測試完成${NC}"
}

# 運行完整測試套件
run_full_tests() {
    echo -e "${BLUE}🔄 運行完整測試套件${NC}"
    
    uv run pytest \
        --cov=src \
        --cov-report=html \
        --cov-report=term-missing \
        --cov-report=xml \
        --maxfail=10 \
        tests/
    
    echo -e "${GREEN}✅ 完整測試完成${NC}"
    echo -e "${YELLOW}📊 查看覆蓋率報告: htmlcov/index.html${NC}"
}

# 運行效能測試
run_performance_tests() {
    echo -e "${BLUE}⚡ 運行效能測試${NC}"
    
    uv run pytest \
        -m "performance" \
        --benchmark-only \
        --benchmark-sort=mean \
        --benchmark-warmup=off \
        tests/
    
    echo -e "${GREEN}✅ 效能測試完成${NC}"
}

# 運行特定模組測試
run_module_tests() {
    local module=$1
    
    if [ -z "$module" ]; then
        echo -e "${RED}❌ 請指定模組名稱${NC}"
        echo "可用模組: activity_meter, achievement, welcome, protection, government, currency"
        exit 1
    fi
    
    echo -e "${BLUE}🎯 運行 ${module} 模組測試${NC}"
    
    uv run pytest \
        -m "$module" \
        --tb=short \
        tests/unit/cogs/$module/ || true
    
    echo -e "${GREEN}✅ ${module} 模組測試完成${NC}"
}

# CI/CD 測試 (嚴格模式)
run_ci_tests() {
    echo -e "${BLUE}🏗️  運行 CI/CD 測試 (嚴格模式)${NC}"
    
    # 設定嚴格環境變數
    export PYTHONWARNINGS=error
    export TESTING=true
    export ENV=test
    
    uv run pytest \
        --strict-markers \
        --strict-config \
        --cov=src \
        --cov-fail-under=70 \
        --cov-report=xml \
        --junit-xml=pytest-results.xml \
        --maxfail=1 \
        --tb=short \
        -q \
        tests/
    
    echo -e "${GREEN}✅ CI/CD 測試完成${NC}"
}

# 生成測試報告
generate_report() {
    echo -e "${BLUE}📊 生成測試報告${NC}"
    
    # 運行測試並生成詳細報告
    uv run pytest \
        --cov=src \
        --cov-report=html:reports/coverage \
        --cov-report=xml:reports/coverage.xml \
        --cov-report=json:reports/coverage.json \
        --junit-xml=reports/pytest.xml \
        --html=reports/pytest.html \
        --self-contained-html \
        tests/
    
    echo -e "${GREEN}✅ 測試報告生成完成${NC}"
    echo -e "${YELLOW}📁 報告位置: reports/${NC}"
}

# 清理測試文件
cleanup() {
    echo -e "${BLUE}🧹 清理測試文件${NC}"
    
    # 清理測試資料庫
    find . -name "test_*.db" -delete
    find . -name "*.db-journal" -delete
    
    # 清理Python緩存
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete
    
    # 清理pytest緩存
    rm -rf .pytest_cache/
    rm -rf .coverage*
    
    echo -e "${GREEN}✅ 清理完成${NC}"
}

# 顯示幫助
show_help() {
    echo "Discord ROAS Bot 測試運行器"
    echo ""
    echo "用法: $0 [選項]"
    echo ""
    echo "選項:"
    echo "  fast          運行快速測試 (單元測試 + Mock)"
    echo "  panel         運行面板互動測試"
    echo "  command       運行指令測試" 
    echo "  full          運行完整測試套件 (包含覆蓋率)"
    echo "  performance   運行效能測試"
    echo "  module <名稱> 運行特定模組測試"
    echo "  ci            運行 CI/CD 測試 (嚴格模式)"
    echo "  report        生成詳細測試報告"
    echo "  cleanup       清理測試文件"
    echo "  help          顯示此幫助"
    echo ""
    echo "範例:"
    echo "  $0 fast                    # 快速測試"
    echo "  $0 module activity_meter   # 活躍度模組測試"
    echo "  $0 panel                   # 面板測試"
    echo "  $0 full                    # 完整測試"
}

# 主函數
main() {
    case "${1:-help}" in
        fast)
            check_dependencies
            run_fast_tests
            ;;
        panel)
            check_dependencies
            run_panel_tests
            ;;
        command)
            check_dependencies
            run_command_tests
            ;;
        full)
            check_dependencies
            run_full_tests
            ;;
        performance)
            check_dependencies
            run_performance_tests
            ;;
        module)
            check_dependencies
            run_module_tests "$2"
            ;;
        ci)
            check_dependencies
            run_ci_tests
            ;;
        report)
            check_dependencies
            mkdir -p reports
            generate_report
            ;;
        cleanup)
            cleanup
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo -e "${RED}❌ 未知選項: $1${NC}"
            show_help
            exit 1
            ;;
    esac
}

# 執行主函數
main "$@"