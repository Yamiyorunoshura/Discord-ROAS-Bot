# dpytest 設置指南

**Task ID**: T5 - Discord testing: dpytest and random interactions  
**版本**: 1.0  
**更新日期**: 2025-08-22

## 概述

本指南說明如何設置和使用 dpytest 測試框架來測試 Discord bot 功能。dpytest 是專為 discord.py 設計的測試框架，允許模擬 Discord 環境進行自動化測試。

## 系統要求

- **Python**: 3.10.18 或以上
- **discord.py**: 2.x
- **dpytest**: 0.7.0 或以上
- **pytest**: 7.0.0 或以上
- **pytest-asyncio**: 0.21.0 或以上

## 安裝步驟

### 1. 安裝依賴

```bash
# 安裝開發依賴（包含 dpytest）
pip install -e ".[dev]"

# 或直接安裝 dpytest
pip install dpytest>=0.7.0
```

### 2. 驗證安裝

```bash
# 檢查 dpytest 是否正確安裝
python -c "from discord.ext import test as dpytest; print('dpytest 安裝成功')"
```

### 3. 目錄結構

確保項目具有以下測試目錄結構：

```
roas-bot/
├── tests/
│   ├── dpytest/
│   │   ├── conftest.py          # dpytest 配置
│   │   └── test_basic_flows.py  # 基本測試流程
│   └── random/
│       ├── random_interaction_engine.py  # 隨機交互引擎
│       └── test_random_interactions.py   # 隨機交互測試
├── test_reports/                # 測試報告目錄
└── scripts/
    └── run_random_tests.sh      # 測試執行腳本
```

## 配置設置

### 1. 測試環境變數

在執行測試前設置以下環境變數：

```bash
export TESTING=true
export LOG_LEVEL=WARNING
```

### 2. pytest 配置

項目的 `pyproject.toml` 已包含必要的 pytest 配置：

```toml
[tool.pytest.ini_options]
markers = [
    "dpytest: Discord 測試",
    "random_interaction: 隨機互動測試",
    "stability: 穩定性測試"
]
```

## 使用方法

### 1. 基本測試執行

```bash
# 執行所有 dpytest 測試
python -m pytest tests/dpytest -v

# 執行特定測試文件
python -m pytest tests/dpytest/test_basic_flows.py -v

# 執行隨機交互測試
python -m pytest tests/random/test_random_interactions.py -v
```

### 2. 隨機交互測試

使用提供的腳本執行隨機交互測試：

```bash
# 基本執行（使用預設參數）
./scripts/run_random_tests.sh

# 指定參數執行
./scripts/run_random_tests.sh <seed> <max_steps> <runs> <timeout>

# 範例：使用種子 12345，最大 15 步，執行 3 次，超時 600 秒
./scripts/run_random_tests.sh 12345 15 3 600
```

### 3. 種子重現測試

如果測試失敗，可以使用相同種子重現問題：

```bash
# 使用特定種子執行測試
python -m pytest tests/random/test_random_interactions.py --seed=12345 --max-steps=10
```

## 測試類型

### 1. 基本流程測試 (`test_basic_flows.py`)

- Bot 基本回應測試
- 面板交互測試
- 錯誤處理測試
- 權限檢查測試
- 效能測試

### 2. 隨機交互測試 (`test_random_interactions.py`)

- **基本隨機序列**: 測試隨機生成的交互序列
- **消息交互**: 專注於消息發送和處理
- **命令變化**: 測試不同命令組合
- **併發交互**: 測試並行交互處理

## 故障排除

### 常見問題

#### 1. dpytest 模組無法導入

**錯誤**: `ModuleNotFoundError: No module named 'dpytest'`

**解決方案**:
```bash
# 重新安裝依賴
pip uninstall dpytest -y
pip install dpytest==0.7.0

# 驗證安裝
python -c "from discord.ext import test as dpytest; print('成功')"
```

#### 2. 事件循環錯誤

**錯誤**: `AttributeError: loop attribute cannot be accessed in non-async contexts`

**解決方案**:
- 確保使用正確的 dpytest API（不是所有函數都需要 await）
- 檢查 bot fixture 的配置
- 確認測試環境的異步設置

#### 3. 測試超時

**錯誤**: 測試執行時間過長或掛起

**解決方案**:
- 減少 `max_steps` 參數
- 增加測試超時時間
- 檢查是否有無限循環的交互

#### 4. 權限錯誤

**錯誤**: 測試報告無法寫入

**解決方案**:
```bash
# 確保測試目錄存在且可寫
mkdir -p test_reports logs
chmod 755 test_reports logs
```

### 日誌和調試

#### 1. 啟用詳細日誌

```bash
# 執行測試時啟用詳細輸出
python -m pytest tests/dpytest -v -s --tb=long
```

#### 2. 檢查測試報告

測試失敗時，檢查生成的報告：

```bash
# 查看最新的失敗報告
ls -la test_reports/random_test_failure_*.json

# 查看測試日誌
tail -f logs/main.log
```

#### 3. 調試特定測試

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 在測試中添加調試輸出
logger = logging.getLogger(__name__)
logger.debug("Debug information here")
```

## CI/CD 整合

### GitHub Actions

項目已配置 `.github/workflows/ci.yml` 支援 dpytest：

- **標準測試**: 執行單元和整合測試
- **dpytest 測試**: 執行 Discord 特定測試（實驗性）
- **穩定性測試**: 重複執行測試檢查穩定性
- **品質檢查**: 靜態分析和安全掃描

### 本地 CI 模擬

```bash
# 模擬 CI 環境執行測試
TESTING=true LOG_LEVEL=WARNING python -m pytest tests/dpytest -v --tb=short
```

## 最佳實踐

### 1. 測試設計

- **隔離性**: 每個測試使用獨立的 bot 實例
- **重現性**: 使用種子確保隨機測試可重現
- **清理**: 測試後適當清理資源

### 2. 效能考量

- **並行限制**: 避免過多併發測試
- **資源管理**: 及時清理臨時資源
- **超時設置**: 合理設置測試超時時間

### 3. 錯誤處理

- **優雅失敗**: 測試失敗時生成詳細報告
- **重試機制**: 對於不穩定的測試提供重試
- **錯誤分類**: 區分環境問題和邏輯錯誤

## 進階用法

### 1. 自定義交互類型

在 `random_interaction_engine.py` 中添加新的交互類型：

```python
class InteractionType(Enum):
    CUSTOM_INTERACTION = "custom_interaction"
    # 添加新類型...
```

### 2. 測試數據生成

使用工廠模式生成測試數據：

```python
class TestDataFactory:
    @staticmethod
    def create_test_message(content="test"):
        return {"content": content, "type": "message"}
```

### 3. 測試報告自定義

擴展 `ReproductionReporter` 類以生成自定義報告格式。

## 支援和社群

- **專案文檔**: `/docs/testing/`
- **問題回報**: 在專案 repository 中創建 issue
- **參考資料**: [dpytest 官方文檔](https://github.com/CraftSpider/dpytest)

---

**注意**: 此為 T5 任務的實施文檔。如遇到問題，請參考 `docs/implementation-review/T5-review.md` 了解已知問題和解決方案。