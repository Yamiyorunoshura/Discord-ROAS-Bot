# Discord機器人系統整合測試指南

## 概覽

本專案建立了完整的系統整合測試框架，涵蓋端到端測試、跨系統整合、效能負載測試和覆蓋率驗證。此測試系統確保Discord機器人三大核心系統（成就、經濟、政府）能夠完美協作並在生產環境中穩定運行。

## 測試架構

```
tests/
├── test_infrastructure.py          # 測試基礎設施框架
├── integration/                    # 整合測試目錄
│   ├── test_cross_system_integration.py    # 跨系統整合測試
│   ├── test_performance_load.py           # 效能和負載測試
│   └── test_end_to_end_flows.py          # 端到端使用者流程測試
├── test_coverage_validation.py     # 測試覆蓋率驗證
└── conftest.py                     # 測試配置和全域fixture
```

## 快速開始

### 1. 安裝依賴

確保已安裝所有測試相關的依賴：

```bash
pip install pytest pytest-asyncio pytest-mock pytest-cov psutil
```

### 2. 執行基本測試

```bash
# 執行所有測試
python run_integration_tests.py --type full

# 執行特定類型的測試
python run_integration_tests.py --type unit
python run_integration_tests.py --type integration
python run_integration_tests.py --type e2e
```

### 3. 查看覆蓋率報告

```bash
# 執行測試並生成覆蓋率報告
python run_integration_tests.py --type full
# 查看HTML報告
open htmlcov/index.html
```

## 測試類型

### 單元測試
- **目的**：測試個別模組和函數的功能
- **執行**：`pytest tests/ -m "unit and not integration"`
- **覆蓋率要求**：核心模組 ≥95%，其他模組 ≥85%

### 整合測試
- **目的**：測試系統間的互動和資料流
- **執行**：`pytest tests/integration/`
- **包含**：服務整合、資料庫操作、API互動

### 跨系統整合測試
- **目的**：驗證成就、經濟、政府系統間的協作
- **執行**：`pytest tests/integration/test_cross_system_integration.py`
- **測試項目**：
  - 成就獎勵自動發放
  - 政府部門帳戶管理
  - 身分組變更同步
  - 資料一致性驗證

### 效能和負載測試
- **目的**：確保系統在高負載下的穩定性
- **執行**：`pytest tests/integration/test_performance_load.py -m performance`
- **基準標準**：
  - 資料庫查詢 p95 < 100ms
  - 服務操作 p95 < 200ms
  - 支援 20+ 並發使用者

### 端到端測試
- **目的**：模擬完整的使用者操作流程
- **執行**：`pytest tests/integration/test_end_to_end_flows.py`
- **測試場景**：
  - 新使用者上線流程
  - 成就解鎖完整流程
  - 政府部門管理流程
  - 錯誤處理和恢復機制

## 測試配置

### pytest標記

```bash
# 按標記執行測試
pytest -m unit           # 單元測試
pytest -m integration    # 整合測試
pytest -m performance    # 效能測試
pytest -m load          # 負載測試
pytest -m e2e           # 端到端測試
pytest -m cross_system  # 跨系統測試
pytest -m slow          # 慢速測試
```

### 覆蓋率配置

覆蓋率設定在 `pyproject.toml` 中：

```toml
[tool.coverage.run]
source = ["services", "panels", "cogs", "core"]
branch = true

[tool.coverage.report]
precision = 2
show_missing = true
```

## 測試基礎設施

### TestEnvironment

提供隔離的測試環境：

```python
async with create_test_environment() as env:
    # 在隔離環境中執行測試
    db_manager = env.db_manager
    service_registry = env.service_registry
```

### MockDiscordClient

模擬Discord互動：

```python
discord_client = MockDiscordClient(test_env)
interaction = discord_client.create_interaction(
    user_id=12345,
    username="TestUser",
    custom_id="test_action"
)
```

### TestDataGenerator

生成測試資料：

```python
data_generator = TestDataGenerator(test_env)
users = await data_generator.create_test_users(10)
achievements = await data_generator.create_test_achievements(5)
```

## 效能監控

### PerformanceTestEngine

效能測試引擎提供：

- 效能基準設定
- 響應時間監控
- 記憶體使用追蹤
- 吞吐量測量

```python
perf_engine = PerformanceTestEngine()
result = await perf_engine.run_performance_test(
    test_func,
    "database_query",
    iterations=100
)
```

### LoadTestEngine

負載測試引擎支援：

- 並發使用者模擬
- 漸進式負載增加
- 壓力測試
- 效能瓶頸識別

```python
load_engine = LoadTestEngine()
result = await load_engine.run_load_test(
    test_func,
    "concurrent_operations",
    concurrent_users=20,
    operations_per_user=5
)
```

## 覆蓋率驗證

### CoverageValidator

自動驗證測試覆蓋率：

```python
validator = CoverageValidator()
report = await validator.run_coverage_analysis()

# 檢查是否符合門檻
assert report.meets_thresholds
assert report.overall_line_coverage >= 90.0
```

### 覆蓋率門檻

- **核心模組** (core/, services/): ≥95%
- **面板模組** (panels/): ≥90%
- **Cogs模組** (cogs/): ≥85%
- **整體覆蓋率**: ≥90%

## 最佳實踐

### 1. 測試隔離

- 每個測試使用獨立的資料庫
- 測試間不共享狀態
- 自動清理測試資料

### 2. 並行執行

```bash
# 並行執行測試以提高效率
pytest -n auto tests/
```

### 3. 錯誤處理

- 測試預期的錯誤情況
- 驗證錯誤恢復機制
- 確保資料一致性

### 4. 效能監控

- 設定合理的效能基準
- 監控資源使用情況
- 識別效能瓶頸

## 持續整合

### GitHub Actions範例

```yaml
name: Integration Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.10
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: python run_integration_tests.py --type full
      - name: Upload coverage
        uses: codecov/codecov-action@v1
```

## 故障排除

### 常見問題

1. **Discord.py相容性問題**
   - 問題：Python 3.10中的類型註解錯誤
   - 解決：conftest.py中的修復機制已自動處理

2. **資料庫鎖定錯誤**
   - 問題：並發測試導致資料庫鎖定
   - 解決：使用獨立的測試資料庫實例

3. **記憶體不足**
   - 問題：大量並發測試消耗記憶體
   - 解決：調整並發數量或分批執行

### 調試技巧

```python
# 啟用詳細日誌
import logging
logging.basicConfig(level=logging.DEBUG)

# 使用pytest調試選項
pytest --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb
```

## 報告生成

測試執行後會自動生成：

1. **HTML覆蓋率報告**: `htmlcov/index.html`
2. **XML覆蓋率報告**: `coverage.xml`
3. **測試結果報告**: `test_reports/test_report_*.md`
4. **效能分析報告**: 包含在測試結果中

## 貢獻指南

### 添加新測試

1. 確定測試類型和標記
2. 使用適當的fixture
3. 遵循命名慣例
4. 添加必要的文檔

### 修改測試基礎設施

1. 確保向後相容性
2. 更新相關文檔
3. 運行完整測試套件
4. 檢查覆蓋率影響

## 支援

如有問題或建議，請：

1. 查看現有的測試案例
2. 檢查故障排除部分
3. 建立Issue報告問題
4. 參考實施計劃文檔

---

**注意**：此測試系統是Discord機器人品質保證的重要組成部分。請確保所有修改都通過完整的測試套件驗證。