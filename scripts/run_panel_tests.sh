#!/bin/bash
# 面板測試專用運行腳本

set -e

echo "🎨 Discord 面板互動測試專用運行器"
echo "====================================="

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# 運行所有面板測試
run_all_panel_tests() {
    echo -e "${BLUE}🎨 運行所有面板測試${NC}"
    
    uv run pytest \
        -c pytest_panel.toml \
        -m "panel" \
        --tb=short \
        --disable-warnings \
        -v \
        tests/unit/cogs/
    
    echo -e "${GREEN}✅ 所有面板測試完成${NC}"
}

# 運行按鈕互動測試
run_button_tests() {
    echo -e "${BLUE}🔘 運行按鈕互動測試${NC}"
    
    uv run pytest \
        -m "panel and button" \
        --tb=short \
        -v \
        tests/unit/cogs/
    
    echo -e "${GREEN}✅ 按鈕測試完成${NC}"
}

# 運行選擇器測試
run_select_tests() {
    echo -e "${BLUE}📋 運行選擇器測試${NC}"
    
    uv run pytest \
        -m "panel and select" \
        --tb=short \
        -v \
        tests/unit/cogs/
    
    echo -e "${GREEN}✅ 選擇器測試完成${NC}"
}

# 運行模態框測試
run_modal_tests() {
    echo -e "${BLUE}📝 運行模態框測試${NC}"
    
    uv run pytest \
        -m "panel and modal" \
        --tb=short \
        -v \
        tests/unit/cogs/
    
    echo -e "${GREEN}✅ 模態框測試完成${NC}"
}

# 運行特定面板測試
run_specific_panel() {
    local panel_name=$1
    
    if [ -z "$panel_name" ]; then
        echo -e "${RED}❌ 請指定面板名稱${NC}"
        echo "可用面板: achievement, welcome, activity_meter"
        exit 1
    fi
    
    echo -e "${BLUE}🎯 運行 ${panel_name} 面板測試${NC}"
    
    uv run pytest \
        -m "panel" \
        --tb=short \
        -v \
        tests/unit/cogs/${panel_name}/test_*panel*.py
    
    echo -e "${GREEN}✅ ${panel_name} 面板測試完成${NC}"
}

# 運行面板效能測試
run_panel_performance() {
    echo -e "${BLUE}⚡ 運行面板效能測試${NC}"
    
    uv run pytest \
        -m "panel and performance" \
        --benchmark-only \
        --benchmark-sort=mean \
        tests/unit/cogs/
    
    echo -e "${GREEN}✅ 面板效能測試完成${NC}"
}

# 運行面板錯誤處理測試
run_panel_error_tests() {
    echo -e "${BLUE}🚨 運行面板錯誤處理測試${NC}"
    
    uv run pytest \
        -m "panel and error_handling" \
        --tb=short \
        -v \
        tests/unit/cogs/
    
    echo -e "${GREEN}✅ 面板錯誤處理測試完成${NC}"
}

# 運行面板併發測試
run_panel_concurrent_tests() {
    echo -e "${BLUE}🔄 運行面板併發測試${NC}"
    
    uv run pytest \
        -m "panel and concurrent" \
        --tb=short \
        -v \
        tests/unit/cogs/
    
    echo -e "${GREEN}✅ 面板併發測試完成${NC}"
}

# 面板測試覆蓋率報告
generate_panel_coverage() {
    echo -e "${BLUE}📊 生成面板測試覆蓋率報告${NC}"
    
    uv run pytest \
        -c pytest_panel.toml \
        -m "panel" \
        --cov=src/cogs/*/panel \
        --cov-report=html:reports/panel_coverage \
        --cov-report=term-missing \
        --cov-fail-under=80 \
        tests/unit/cogs/
    
    echo -e "${GREEN}✅ 面板覆蓋率報告生成完成${NC}"
    echo -e "${YELLOW}📁 報告位置: reports/panel_coverage/index.html${NC}"
}

# 互動式面板測試
run_interactive_panel_test() {
    echo -e "${BLUE}🖱️  互動式面板測試${NC}"
    echo -e "${YELLOW}此模式將逐個運行面板測試，按 Enter 繼續下一個${NC}"
    
    # 獲取所有面板測試文件
    panel_files=($(find tests/unit/cogs -name "*panel*.py" -type f))
    
    for file in "${panel_files[@]}"; do
        echo -e "${PURPLE}測試文件: $file${NC}"
        
        uv run pytest \
            -v \
            --tb=short \
            "$file"
        
        echo -e "${YELLOW}按 Enter 繼續下一個測試文件...${NC}"
        read -r
    done
    
    echo -e "${GREEN}✅ 互動式測試完成${NC}"
}

# 面板測試偵錯模式
run_panel_debug() {
    echo -e "${BLUE}🐛 面板測試偵錯模式${NC}"
    
    uv run pytest \
        -m "panel" \
        --tb=long \
        --capture=no \
        --log-cli-level=DEBUG \
        -v \
        -s \
        tests/unit/cogs/
    
    echo -e "${GREEN}✅ 偵錯模式完成${NC}"
}

# 顯示面板測試統計
show_panel_stats() {
    echo -e "${BLUE}📈 面板測試統計${NC}"
    
    echo "測試文件統計:"
    find tests/unit/cogs -name "*panel*.py" -type f | wc -l | xargs echo "面板測試文件數量:"
    
    echo ""
    echo "測試標記統計:"
    uv run pytest --collect-only -m "panel" -q tests/unit/cogs/ 2>/dev/null | grep "test session" || echo "無法獲取統計"
    
    echo ""
    echo "模組覆蓋:"
    for cog_dir in tests/unit/cogs/*/; do
        cog_name=$(basename "$cog_dir")
        if ls "$cog_dir"*panel*.py 1> /dev/null 2>&1; then
            echo -e "${GREEN}✅ $cog_name${NC}"
        else
            echo -e "${RED}❌ $cog_name${NC}"
        fi
    done
}

# 顯示幫助
show_help() {
    echo "Discord 面板測試專用運行器"
    echo ""
    echo "用法: $0 [選項]"
    echo ""
    echo "選項:"
    echo "  all           運行所有面板測試"
    echo "  button        運行按鈕互動測試"
    echo "  select        運行選擇器測試"
    echo "  modal         運行模態框測試"
    echo "  panel <名稱>  運行特定面板測試"
    echo "  performance   運行面板效能測試"
    echo "  error         運行面板錯誤處理測試"
    echo "  concurrent    運行面板併發測試"
    echo "  coverage      生成面板測試覆蓋率報告"
    echo "  interactive   互動式面板測試"
    echo "  debug         偵錯模式運行面板測試"
    echo "  stats         顯示面板測試統計"
    echo "  help          顯示此幫助"
    echo ""
    echo "範例:"
    echo "  $0 all                      # 所有面板測試"
    echo "  $0 panel achievement        # 成就面板測試"
    echo "  $0 button                   # 按鈕測試"
    echo "  $0 coverage                 # 覆蓋率報告"
}

# 主函數
main() {
    case "${1:-help}" in
        all)
            run_all_panel_tests
            ;;
        button)
            run_button_tests
            ;;
        select)
            run_select_tests
            ;;
        modal)
            run_modal_tests
            ;;
        panel)
            run_specific_panel "$2"
            ;;
        performance)
            run_panel_performance
            ;;
        error)
            run_panel_error_tests
            ;;
        concurrent)
            run_panel_concurrent_tests
            ;;
        coverage)
            mkdir -p reports
            generate_panel_coverage
            ;;
        interactive)
            run_interactive_panel_test
            ;;
        debug)
            run_panel_debug
            ;;
        stats)
            show_panel_stats
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