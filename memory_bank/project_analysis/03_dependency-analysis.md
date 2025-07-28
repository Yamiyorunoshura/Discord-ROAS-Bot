# 依賴關係分析

## Import路徑分析
### 現代化遷移狀況
經過分析，專案已成功從根目錄結構遷移至`src/`目錄結構，但存在以下相容性問題：

#### 已完成遷移的模組
- `src.core.*` - 核心模組已完全更新
- `src.cogs.welcome.*` - 歡迎系統已完成現代化改造
- `src.cogs.sync_data.*` - 資料同步模組使用新的import路徑

#### 混合import路徑的模組
以下模組仍存在舊式import路徑，需要更新：

```python
# 發現的問題import路徑
src/core/bot.py:24:    from cogs.core.event_bus import EventBus, Event, EventPriority, get_global_event_bus
src/core/bot.py:25:    from cogs.core.error_handler import ErrorHandler, ErrorSeverity, create_error_handler
src/core/container.py:28:    from cogs.core.cache_manager import MultiLevelCache, get_global_cache_manager
src/core/container.py:29:    from cogs.core.health_checker import HealthChecker, get_health_checker
```

#### 正確的import路徑模式
```python
# 新架構的正確import路徑
from src.core.bot import ADRBot
from src.core.config import Settings  
from src.core.logger import get_logger
from src.cogs.activity_meter.main.main import ActivityMeter
```

### 模組依賴層次結構
```
第1層 - 核心基礎設施 (Core Infrastructure)
├── src.core.config (配置管理)
├── src.core.logger (日誌系統)  
├── src.core.database (資料庫連線)
├── src.core.container (依賴注入)
└── src.core.compat (相容性輔助)

第2層 - 框架服務 (Framework Services)  
├── src.core.bot (Bot框架)
├── src.core.monitor (監控系統)
└── src.cogs.core.* (舊核心模組，需要遷移)

第3層 - 業務模組 (Business Modules)
├── src.cogs.activity_meter (活躍度追蹤)
├── src.cogs.message_listener (訊息監聽)
├── src.cogs.protection (保護系統)
├── src.cogs.welcome (歡迎系統)
└── src.cogs.sync_data (資料同步)

第4層 - 工具和測試 (Tools & Tests)
├── src.tools.migration (遷移工具)
├── src.tests (測試程式)
└── scripts (部署腳本)
```

## 外部依賴分析
### Python標準庫依賴
- `asyncio` - 非同步程式設計框架
- `pathlib` - 現代路徑處理
- `datetime` - 時間處理
- `json` - JSON序列化
- `sqlite3` - 資料庫操作 (透過aiosqlite)
- `logging` - 日誌記錄
- `typing` - 型別提示 (使用現代語法)

### 第三方依賴 (主要)
#### Discord相關
- `discord.py` (2.x) - Discord API客戶端
- `discord.ext.commands` - 指令框架

#### 資料處理
- `aiosqlite` - 非同步SQLite操作
- `pydantic` - 資料驗證和配置管理
- `pydantic-settings` - 配置管理擴展

#### 圖像處理
- `Pillow (PIL)` - 圖像生成和處理
- 字體檔案支援中文顯示

#### 網路和加密
- `aiohttp` - 非同步HTTP客戶端
- `cryptography` - 配置加密
- `uvloop` - 高效能事件循環 (Unix平台)

#### CLI和配置
- `typer` - 現代CLI框架
- `rich` - 豐富的終端輸出
- `pyyaml` - YAML配置支援
- `python-dotenv` - 環境變數管理
- `watchfiles` - 檔案監控 (熱重載)

#### 開發工具
- `pytest` - 測試框架
- `coverage` - 測試覆蓋率
- `commitizen` - 規範化提交

### 依賴版本約束
```toml
[project]
requires-python = ">=3.12"

[project.dependencies]
discord-py = ">=2.3.0"
aiosqlite = ">=0.19.0"
pydantic = ">=2.5.0"
pydantic-settings = ">=2.1.0"
pillow = ">=10.0.0"
aiohttp = ">=3.9.0"
cryptography = ">=41.0.0"
typer = ">=0.9.0"
rich = ">=13.0.0"
```

## 循環依賴分析
### 發現的潛在問題
1. **事件系統循環依賴**:
   ```python
   # 潛在問題: bot.py → event_bus → error_handler → bot.py
   src/core/bot.py → cogs.core.event_bus
   cogs.core.event_bus → cogs.core.error_handler (可能)
   cogs.core.error_handler → bot instance
   ```

2. **容器和服務循環依賴**:
   ```python
   # 已解決: 使用延遲載入和工廠模式
   src/core/container.py → services
   services → container (透過get_container())
   ```

### 解決方案
- **延遲導入**: 使用函數內導入避免初始化時的循環依賴
- **介面分離**: 定義抽象介面打破具體實現的循環依賴
- **依賴反轉**: 高層模組不依賴低層模組，都依賴抽象

## 相容性問題識別
### Python 3.12相容性
專案已針對Python 3.12進行優化：

#### 已解決的相容性問題
1. **新式型別註解**: 使用`from __future__ import annotations`
2. **現代typing語法**: 使用`list[T]`而非`List[T]`
3. **AsyncIO改進**: 利用Python 3.12的asyncio增強功能
4. **相容性模組**: `src.core.compat`提供向下相容支援

#### 相容性輔助功能
```python
# src/core/compat.py 提供的功能
- AsyncIteratorWrapper: 修復async iterator問題
- create_task_safe: 安全的任務建立
- gather_safe: 安全的協程聚合
- ensure_awaitable: 確保物件可等待
```

### Discord.py 2.x相容性
- **Slash Commands**: 完全支援應用指令
- **Components**: 支援按鈕、選單、模態框等UI組件
- **Intents**: 正確配置所需的Discord權限
- **現代化API**: 使用最新的Discord API特性

### 跨平台相容性
- **路徑處理**: 使用`pathlib.Path`確保跨平台相容
- **事件循環**: Windows使用預設事件循環，Unix使用uvloop
- **檔案權限**: 安全處理不同作業系統的權限設定

## 建議的依賴改進
### 短期改進
1. **完成import路徑遷移**: 將所有`cogs.core.*`更新為`src.core.*`
2. **統一錯誤處理**: 使用一致的錯誤處理模式
3. **清理未使用依賴**: 移除不再需要的舊依賴

### 中期改進  
1. **依賴注入優化**: 完善DI容器的功能和效能
2. **模組解耦**: 減少模組間的緊密耦合
3. **介面標準化**: 定義標準的模組間通信介面

### 長期規劃
1. **微服務架構**: 考慮將大型模組拆分為獨立服務
2. **依賴管理工具**: 使用更先進的依賴管理和版本控制
3. **自動化測試**: 建立完整的依賴關係測試套件