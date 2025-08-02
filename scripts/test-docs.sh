#!/bin/bash
# 文件測試執行腳本

set -e  # 遇到錯誤時停止執行

echo "========================================"
echo "Discord ROAS Bot - 文件測試套件"
echo "========================================"

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 檢查依賴
check_dependencies() {
    echo -e "${BLUE}檢查測試依賴...${NC}"
    
    # 檢查 Python 和 pytest
    if ! command -v python &> /dev/null; then
        echo -e "${RED}錯誤: 未找到 Python${NC}"
        exit 1
    fi
    
    if ! python -c "import pytest" &> /dev/null; then
        echo -e "${YELLOW}警告: pytest 未安裝，正在安裝...${NC}"
        pip install pytest pytest-cov requests beautifulsoup4 markdown pyyaml jsonschema docker
    fi
    
    # 檢查可選依賴
    if ! command -v docker &> /dev/null; then
        echo -e "${YELLOW}警告: Docker 未安裝，部分測試將被跳過${NC}"
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${YELLOW}警告: docker-compose 未安裝，部分測試將被跳過${NC}"
    fi
    
    echo -e "${GREEN}依賴檢查完成${NC}"
}

# 執行文件結構測試
test_documentation() {
    echo -e "${BLUE}執行文件結構和內容測試...${NC}"
    
    python -m pytest tests/docs/test_documentation.py -v \
        --tb=short \
        --color=yes \
        -m "not slow"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 文件測試通過${NC}"
    else
        echo -e "${RED}✗ 文件測試失敗${NC}"
        return 1
    fi
}

# 執行 API 文件測試
test_api_documentation() {
    echo -e "${BLUE}執行 API 文件測試...${NC}"
    
    # 檢查 API 服務是否運行
    if curl -f http://localhost:8080/health &> /dev/null; then
        echo -e "${GREEN}檢測到 API 服務運行，執行完整 API 測試${NC}"
        python -m pytest tests/api_docs/test_api_documentation.py -v \
            --tb=short \
            --color=yes
    else
        echo -e "${YELLOW}API 服務未運行，僅執行靜態文件測試${NC}"
        python -m pytest tests/api_docs/test_api_documentation.py::test_openapi_spec_is_valid -v \
            --tb=short \
            --color=yes
    fi
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ API 文件測試通過${NC}"
    else
        echo -e "${RED}✗ API 文件測試失敗${NC}"
        return 1
    fi
}

# 執行部署文件測試
test_deployment() {
    echo -e "${BLUE}執行部署配置測試...${NC}"
    
    python -m pytest tests/deployment/test_deployment.py -v \
        --tb=short \
        --color=yes \
        -m "not slow"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 部署測試通過${NC}"
    else
        echo -e "${RED}✗ 部署測試失敗${NC}"
        return 1
    fi
}

# 生成測試報告
generate_report() {
    echo -e "${BLUE}生成測試報告...${NC}"
    
    # 執行完整測試並生成報告
    python -m pytest tests/docs tests/api_docs tests/deployment \
        --tb=short \
        --color=yes \
        --junit-xml=test-results/docs-test-results.xml \
        --html=test-results/docs-test-report.html \
        --self-contained-html \
        -m "not slow" \
        || true  # 不因測試失敗而停止報告生成
    
    # 生成自定義報告
    if [ -f "tests/docs/test_documentation.py" ]; then
        echo -e "${BLUE}生成文件驗證報告...${NC}"
        python tests/docs/test_documentation.py
    fi
    
    echo -e "${GREEN}測試報告已生成到 test-results/ 目錄${NC}"
}

# 清理函數
cleanup() {
    echo -e "${BLUE}清理臨時文件...${NC}"
    find . -name "*.pyc" -delete 2>/dev/null || true
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    echo -e "${GREEN}清理完成${NC}"
}

# 主函數
main() {
    # 創建測試結果目錄
    mkdir -p test-results
    
    local exit_code=0
    
    # 執行檢查和測試
    check_dependencies
    
    echo ""
    test_documentation || exit_code=1
    
    echo ""
    test_api_documentation || exit_code=1
    
    echo ""
    test_deployment || exit_code=1
    
    echo ""
    generate_report
    
    echo ""
    cleanup
    
    # 總結
    echo "========================================"
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✓ 所有文件測試通過！${NC}"
        echo -e "${GREEN}文件品質符合標準，可以安全部署。${NC}"
    else
        echo -e "${RED}✗ 部分測試失敗${NC}"
        echo -e "${YELLOW}請檢查上述錯誤並修復後重新執行測試。${NC}"
    fi
    echo "========================================"
    
    exit $exit_code
}

# 處理命令列參數
case "${1:-all}" in
    "docs")
        check_dependencies
        test_documentation
        ;;
    "api")
        check_dependencies
        test_api_documentation
        ;;
    "deployment")
        check_dependencies
        test_deployment
        ;;
    "report")
        check_dependencies
        generate_report
        ;;
    "clean")
        cleanup
        ;;
    "all"|"")
        main
        ;;
    *)
        echo "用法: $0 [docs|api|deployment|report|clean|all]"
        echo ""
        echo "選項:"
        echo "  docs       - 僅執行文件結構和內容測試"
        echo "  api        - 僅執行 API 文件測試"
        echo "  deployment - 僅執行部署配置測試"
        echo "  report     - 生成完整測試報告"
        echo "  clean      - 清理臨時文件"
        echo "  all        - 執行所有測試（預設）"
        exit 1
        ;;
esac