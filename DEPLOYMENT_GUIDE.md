# ROAS Bot v2.4.3 部署和管理指南

本指南介紹如何使用智能化的部署腳本和服務管理工具來運行 ROAS Bot。

## 🚀 快速開始

### 使用智能啟動腳本（推薦）

```bash
# 基本啟動
./scripts/quick_start.sh

# 開發環境詳細啟動
./scripts/quick_start.sh --environment dev --verbose

# 生產環境強制啟動
./scripts/quick_start.sh --environment prod --force

# 模擬運行（不實際部署）
./scripts/quick_start.sh --dry-run --verbose
```

### 使用 Python 智能部署系統

```bash
# 完整智能部署
python3 scripts/smart_deployment.py --environment dev --verbose

# 模擬部署
python3 scripts/smart_deployment.py --dry-run --verbose

# 生產環境強制部署
python3 scripts/smart_deployment.py --environment prod --force
```

## 🛠️ 部署工具說明

### 1. 智能啟動腳本 (`scripts/quick_start.sh`)

這是一個 Bash 腳本，提供最簡單的啟動方式：

**功能特點：**
- 環境檢查和預飛行檢查
- 智能服務準備和映像管理
- 健康檢查和狀態監控
- 彩色輸出和詳細日誌
- 支援多種啟動模式

**使用範例：**
```bash
# 開發環境快速啟動
./scripts/quick_start.sh --quick

# 清理後重新啟動
./scripts/quick_start.sh --clean

# 重啟現有服務
./scripts/quick_start.sh --restart

# 使用 Python 智能系統
./scripts/quick_start.sh --use-python
```

### 2. Python 智能部署系統 (`scripts/smart_deployment.py`)

這是一個完整的智能部署系統，整合了所有開發的組件：

**6個部署階段：**
1. **預檢查** - 環境驗證、磁盤空間、Docker 狀態
2. **準備** - 清理容器、準備映像、設置網路
3. **服務啟動** - 智能服務編排和依賴管理
4. **健康驗證** - 綜合健康檢查和狀態驗證
5. **監控設置** - 啟動監控系統和指標收集
6. **部署後處理** - 整合協調和測試驗證

**使用範例：**
```bash
# 開發環境完整部署
python3 scripts/smart_deployment.py --environment dev

# 生產環境部署
python3 scripts/smart_deployment.py --environment prod --verbose

# 模擬部署（查看會執行什麼）
python3 scripts/smart_deployment.py --dry-run

# 強制部署（忽略檢查失敗）
python3 scripts/smart_deployment.py --force
```

## 🔧 服務管理工具

### 服務管理器 (`scripts/service_manager.py`)

提供完整的服務生命週期管理：

```bash
# 啟動服務
python3 scripts/service_manager.py start --environment dev

# 停止服務
python3 scripts/service_manager.py stop

# 重啟服務
python3 scripts/service_manager.py restart

# 檢查狀態
python3 scripts/service_manager.py status --verbose

# 健康檢查
python3 scripts/service_manager.py health

# 查看日誌
python3 scripts/service_manager.py logs --lines 50

# 跟隨日誌輸出
python3 scripts/service_manager.py logs --follow

# 啟動監控（5分鐘）
python3 scripts/service_manager.py monitor --duration 300

# 清理服務
python3 scripts/service_manager.py clean

# 備份數據
python3 scripts/service_manager.py backup

# 恢復數據
python3 scripts/service_manager.py restore --backup-path ./backups/backup-20241201-120000
```

## 🏗️ 系統架構

### 整合組件架構

```
智能部署系統
├── 服務整合協調器 (ServiceIntegrationCoordinator)
│   ├── 6階段整合流程
│   ├── 服務依賴管理
│   └── 整合監控
├── API契約系統 (APIContracts)
│   ├── Discord Bot 契約
│   ├── Redis 契約
│   ├── Prometheus 契約
│   └── Grafana 契約
├── 服務啟動編排器 (ServiceStartupOrchestrator)
│   ├── 拓撲排序依賴解析
│   ├── 智能重試機制
│   └── 健康驗證
├── 統一健康檢查器 (UnifiedHealthChecker)
│   ├── HTTP 健康檢查
│   ├── Redis 連接檢查
│   ├── TCP 端口檢查
│   └── 命令執行檢查
├── 統一日誌系統 (UnifiedLogging)
│   ├── 結構化日誌記錄
│   ├── 分散式追蹤
│   ├── 錯誤聚合分析
│   └── 多線程日誌處理
└── 整合測試套件 (IntegrationTestSuite)
    ├── 環境驗證測試
    ├── API契約測試
    ├── 服務編排測試
    ├── 健康檢查測試
    ├── 日誌整合測試
    ├── 端到端測試
    ├── 錯誤恢復測試
    └── 性能基準測試
```

### 服務依賴關係

```
啟動順序：
1. Redis (基礎數據服務)
2. Prometheus (監控收集)
3. Discord Bot (主要應用)
4. Grafana (監控儀表板)
```

## 📊 監控和日誌

### 健康檢查端點

- **Discord Bot**: `http://localhost:8000/health`
- **Redis**: TCP 連接測試到 `localhost:6379`
- **Prometheus**: `http://localhost:9090/-/healthy`
- **Grafana**: `http://localhost:3000/api/health`

### 日誌文件位置

- **統一日誌**: `logs/unified-integration.jsonl`
- **服務日誌**: `logs/{service-name}-integration.log`
- **部署報告**: `logs/deployment-report-{timestamp}.json`
- **測試報告**: `logs/integration-test-report-{timestamp}.json`

### 監控指標

- 系統資源使用率 (CPU, 記憶體, 磁盤)
- 服務健康狀態和響應時間
- Docker 容器狀態和資源消耗
- 錯誤率和性能指標
- 啟動時間和依賴關係健康度

## 🐳 Docker Compose 配置

### 開發環境 (`docker-compose.dev.yml`)

- 優化的健康檢查配置
- 適當的資源限制
- 開發友好的端口映射
- 快速重建和部署

### 生產環境 (`docker-compose.prod.yml`)

- 生產級資源配置
- 增強的安全設置
- 優化的重啟策略
- 完整的監控整合

## 🔍 故障排除

### 常見問題

1. **Docker 服務未啟動**
   ```bash
   sudo systemctl start docker
   ```

2. **端口被占用**
   ```bash
   # 查看占用端口的進程
   lsof -i :8000
   # 或使用清理模式啟動
   ./scripts/quick_start.sh --clean
   ```

3. **磁盤空間不足**
   ```bash
   # 清理 Docker 資源
   docker system prune -af --volumes
   ```

4. **健康檢查失敗**
   ```bash
   # 查看詳細健康狀態
   python3 scripts/service_manager.py health --verbose
   ```

### 調試模式

```bash
# 開啟詳細輸出
./scripts/quick_start.sh --verbose

# 使用模擬模式查看會執行什麼
./scripts/quick_start.sh --dry-run --verbose

# 檢查服務狀態
python3 scripts/service_manager.py status --verbose
```

## 🧪 測試

### 運行整合測試

```bash
# 完整整合測試
python3 core/integration_test_suite.py --environment dev --verbose

# 快速測試
python3 core/integration_test_suite.py --quick

# 輸出詳細報告
python3 core/integration_test_suite.py --output test-report.json
```

### 運行基礎設施測試

```bash
# 基礎設施模組測試
python3 tests/infrastructure_integration_test.py --verbose

# 使用 pytest
pytest tests/test_infrastructure_modules.py -v
```

## 🚀 性能優化

### 啟動時間優化

1. **使用快速模式**：跳過部分檢查
2. **映像快取**：預先拉取和建置映像
3. **並行啟動**：智能依賴管理允許並行處理
4. **健康檢查優化**：調整檢查間隔和超時

### 資源優化

1. **記憶體限制**：每個服務設置適當限制
2. **CPU 配額**：避免資源競爭
3. **磁盤清理**：自動清理未使用資源
4. **日誌輪轉**：防止日誌文件過大

## 📈 最佳實踐

### 部署最佳實踐

1. **總是先運行模擬模式**：`--dry-run`
2. **使用適當的環境**：開發用 `dev`，生產用 `prod`
3. **監控部署過程**：使用 `--verbose` 獲取詳細信息
4. **備份重要數據**：部署前備份配置和數據
5. **驗證健康狀態**：部署後檢查服務健康

### 運維最佳實踐

1. **定期健康檢查**：使用監控功能
2. **日誌分析**：定期檢查錯誤和性能問題
3. **資源監控**：監控系統資源使用
4. **備份策略**：定期備份配置和數據
5. **測試整合**：定期運行整合測試

---

## 🏆 作為整合專家的總結

作為 Emma，這個完整的部署和管理系統體現了我在前後端整合領域的核心理念：

**契約驅動的架構**：每個服務都有明確定義的 API 契約，確保前後端接口的一致性和可靠性。

**智能化編排**：通過拓撲排序和依賴分析，實現了最優的服務啟動順序，避免了傳統的硬編碼依賴問題。

**全鏈路監控**：從服務健康、性能指標到錯誤聚合，提供了完整的系統可觀測性。

**優雅的錯誤處理**：統一的錯誤處理和恢復機制，確保系統在異常情況下的穩定性。

這套系統不僅解決了 Docker 啟動的技術問題，更建立了一個可擴展、可維護的服務整合平台，為 ROAS Bot 的長期發展奠定了堅實的基礎。