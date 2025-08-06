# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

本專案旨在打造一個功能全面、高度模組化的 Discord 機器人，其核心圍繞著一個複雜的社會經濟模擬系統。系統主要由以下幾個核心模組構成，並透過先進的軟體架構（如服務導向架構、依賴注入、事件驅動）實現模組間的高內聚與低耦合。

## 開發環境與依賴管理

### 工具鏈
- **Python版本**: 3.12+ (必須)
- **包管理器**: UV (推薦)
- **任務執行**: Makefile 包含所有常用命令

### 常用開發命令

```bash
# 完整開發環境設置
make dev-setup

# 安裝依賴
make install          # 基本依賴
make dev             # 開發依賴

# 代碼品質
make format          # 格式化代碼 (black + ruff)
make lint           # 靜態檢查 (ruff + mypy)
make check          # 完整品質檢查 (format + lint + test)
make security       # 安全檢查 (bandit + safety)

# 測試
make test           # 運行測試
make test-cov       # 運行測試並生成覆蓋率報告
make test-watch     # 監控測試模式

# 運行機器人
make run            # 正常運行
make run-dev        # 開發模式運行
make validate-config # 驗證配置

# 資料庫管理
make db-init        # 初始化資料庫目錄
make db-backup      # 備份資料庫

# 清理
make clean          # 清理臨時文件
make deep-clean     # 深度清理（包含 UV 快取）
```

### 測試執行
```bash
# 運行單個測試模組
uv run pytest tests/unit/test_activity_meter.py -v

# 運行特定測試功能
uv run pytest tests/unit/test_activity_meter.py::TestActivityMeter::test_calculate_activity -v

# 運行帶標記的測試
uv run pytest -m unit         # 單元測試
uv run pytest -m integration  # 整合測試
uv run pytest -m database     # 資料庫測試
```

## 專案架構

### 目錄結構
```
src/
├── core/                    # 核心基礎設施
│   ├── bot.py              # 主 Bot 類別
│   ├── config.py           # 企業級配置管理系統
│   ├── database.py         # 資料庫連線池
│   ├── logger.py           # 日誌系統
│   └── container.py        # 依賴注入容器
├── cogs/                   # 功能模組
│   ├── activity_meter/     # 活躍度追蹤（複雜度：高）
│   ├── message_listener/   # 訊息監聽（複雜度：中）
│   ├── protection/         # 伺服器保護（複雜度：中）
│   ├── welcome/           # 歡迎系統（複雜度：中）
│   └── sync_data/         # 資料同步（複雜度：高）
└── main.py                # 主要入口點
```

### 架構模式

1. **模組化 Cog 架構**: 每個功能作為獨立的 Discord.py Cog
2. **依賴注入容器**: 統一管理服務生命週期和依賴關係
3. **分層架構**: config → database → panel → main 的清晰分層
4. **企業級配置管理**: 支援多來源、熱重載、加密存儲的統一配置系統

### 重要設計模式

- **Factory Pattern**: SettingsFactory 用於配置創建
- **Observer Pattern**: ConfigChangeListener 用於配置變更通知
- **Strategy Pattern**: ConfigMergeEngine 支援多種合併策略
- **Adapter Pattern**: 不同配置來源的統一介面

## 配置系統

專案使用企業級統一配置管理系統，支援：

- **多來源配置**: 環境變數、檔案、命令列、資料庫、遠端 API
- **配置熱重載**: 自動檢測配置變更並通知相關組件
- **敏感資料加密**: 自動加密 token 等敏感配置
- **配置驗證**: 內建驗證規則確保配置正確性

### 配置文件位置
- `.env` - 主要環境配置
- `config.yaml` - YAML 格式配置（可選）
- `src/core/config.py` - 配置類別定義

### 常用配置操作
```python
from src.core.config import get_enhanced_settings, initialize_config_system

# 初始化配置系統
settings = await initialize_config_system()

# 獲取配置
db_url = settings.get_database_url("activity")
log_path = settings.get_log_file_path("main")

# 檢查功能開關
if settings.is_feature_enabled("activity_meter"):
    # 載入活躍度模組
```

## 資料庫架構

### 資料庫配置
- **類型**: SQLite（每模組獨立資料庫文件）
- **位置**: `dbs/` 目錄下
- **連線池**: 支援連線池化和 WAL 模式
- **遷移**: 每個模組管理自己的資料庫初始化

### 主要資料庫
- `activity.db` - 活躍度資料
- `message.db` - 訊息記錄
- `welcome.db` - 歡迎系統配置
- `sync_data.db` - 同步資料狀態

## 模組開發指南

### Cog 模組結構
每個 Cog 模組遵循統一結構：
```
cogs/module_name/
├── __init__.py
├── config/
│   └── config.py           # 模組配置
├── database/
│   └── database.py         # 資料庫操作
├── main/
│   └── main.py            # 主要邏輯
└── panel/                 # UI 組件
    ├── main_view.py       # 主 View
    ├── components/        # UI 組件
    └── embeds/           # Embed 訊息
```

### 新增模組的步驟
1. 創建模組目錄結構
2. 實作 `BaseCog` 繼承
3. 在 `src/core/bot.py` 中註冊模組
4. 更新配置文件添加功能開關
5. 編寫對應測試

## Discord.py 特定考量

### 版本相容性
- 使用 Discord.py 2.5.2+
- 完全支援 Slash Commands
- 支援現代 Components (按鈕、選單、模態框)
- 正確配置 Discord Intents

### UI 組件最佳實踐
```python
# View 類別應繼承自 discord.ui.View
class MainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label="設定", style=discord.ButtonStyle.primary)
    async def settings_button(self, interaction, button):
        # 處理按鈕點擊
```

### Embed 限制
- 標題最多 256 字元
- 描述最多 4096 字元
- 欄位最多 25 個
- 每個欄位值最多 1024 字元
- 總大小不超過 6000 字元

## 重要依賴和版本

```toml
# 核心依賴
discord.py = ">=2.5.2,<3.0.0"
python-dotenv = ">=1.1.0,<2.0.0"
aiosqlite = ">=0.21.0,<1.0.0"
pydantic = ">=2.5.0,<3.0.0"
pydantic-settings = ">=2.1.0,<3.0.0"

# 效能優化
uvloop = ">=0.19.0" # Unix 系統限定
cachetools = ">=5.3.2,<6.0.0"

# 圖像處理
Pillow = ">=11.2.1,<12.0.0"

# 命令列介面
typer = ">=0.12.0,<1.0.0"
rich = ">=13.7.0,<14.0.0"
```

## 除錯和監控

### 日誌系統
- 位置: `logs/` 目錄
- 主要日誌: `main.log`, `main_error.log`
- 模組日誌: 每個模組有獨立日誌文件
- 格式: 支援 JSON、文本、彩色輸出

### 常用除錯命令
```bash
# 查看最新日誌
make logs

# 查看錯誤日誌
make logs-error

# 檢查機器人狀態
make status

# 驗證配置
make validate-config
```

## 已知問題和技術債務

### 高優先級修復
1. **Import 路徑不一致**: 部分舊模組仍使用 `cogs.core.*` 而非 `src.core.*`
2. **錯誤處理不統一**: 不同模組使用不同的錯誤處理機制

### 中優先級改進
1. **測試覆蓋率不足**: 目前約 50%，需要提升至 80%+
2. **效能瓶頸**: 複雜統計查詢可能需要優化

### 修復指引
- 將所有 `from cogs.core.` 改為 `from src.core.`
- 統一使用 `src.core.error_handler` 中的錯誤處理機制
- 為核心模組編寫充分的測試用例

## 部署相關

### 環境變數需求
```env
# 必須配置
TOKEN=your_discord_bot_token

# 可選配置
ENVIRONMENT=development|staging|production
DEBUG=false
LOG_LEVEL=INFO

# 資料庫配置
DB_POOL_SIZE=10
DB_QUERY_TIMEOUT=30

# 安全配置
SECURITY_RATE_LIMIT_ENABLED=true
```

### Docker 支援
```bash
# 構建映像
make docker-build

# 運行容器
make docker-run

# Docker Compose
make docker-compose
```

## 效能考量

### 最佳化建議
- 使用連線池化避免資料庫連線開銷
- 實施適當的快取策略
- 利用 Discord.py 的 bulk 操作
- 監控記憶體使用，特別是大量資料處理時

### 限制和約束
- Discord API 速率限制：50 請求/秒
- SQLite 併發限制：使用 WAL 模式改善
- 記憶體使用：監控大型統計查詢的記憶體消耗

## 開發最佳實踐

1. **遵循現有架構模式**: 新功能應該遵循現有的分層架構
2. **使用依賴注入**: 透過容器管理服務依賴
3. **編寫測試**: 新功能必須包含對應測試
4. **統一錯誤處理**: 使用 `src.core.error_handler`
5. **配置驅動**: 功能開關透過配置系統管理
6. **非同步優先**: 利用 AsyncIO 實現高效併發

這個專案展現了現代 Python Discord 機器人開發的最佳實踐，結合了企業級架構設計與 Discord.py 的最新功能。在開發時請保持對架構一致性的重視，確保新增功能能夠與現有系統seamlessly整合。

## Claude Code 工具效率指南

### 高效批量編輯工具

#### MultiEdit - 批量文件修改
```python
# 在單個文件中執行多個編輯操作
# 比逐個使用 Edit 工具快 3-5 倍
MultiEdit(
    file_path="/path/to/file.py",
    edits=[
        {"old_string": "old_import", "new_string": "new_import"},
        {"old_string": "old_function", "new_string": "new_function", "replace_all": True}
    ]
)
```

#### Edit with replace_all
```python
# 批量替換文件中的所有匹配項
Edit(file_path="/path/to/file.py", old_string="cogs.core", new_string="src.core", replace_all=True)
```

### 高效搜索工具組合

#### Grep - 內容搜索
```bash
# 搜索所有 Python 文件中的導入路徑問題
Grep(pattern="from cogs\.core\.", type="py", output_mode="files_with_matches")

# 搜索特定模式並顯示上下文
Grep(pattern="class.*Cog", type="py", output_mode="content", -A=3, -B=1)

# 多行搜索（跨行模式匹配）
Grep(pattern="async def.*\n.*await", multiline=True, output_mode="content")
```

#### Glob - 文件路徑匹配
```bash
# 快速找到所有需要修改的配置文件
Glob(pattern="**/config/*.py")

# 找到特定模組的所有文件
Glob(pattern="src/cogs/activity_meter/**/*.py")

# 排除測試文件的所有 Python 文件
Glob(pattern="src/**/*.py", exclude="**/test_*")
```

### 並行操作優化

#### 同時執行多個搜索
```python
# 一次性搜索多個模式，並行執行
[
    Grep(pattern="from cogs\.core", type="py"),
    Grep(pattern="import cogs\.core", type="py"),
    Glob(pattern="**/database/*.py")
]
```

#### 並行 Bash 命令
```python
# 同時執行多個命令，提升效率
[
    Bash("find src -name '*.py' | wc -l"),
    Bash("grep -r 'cogs.core' src --include='*.py' | wc -l"),
    Bash("make lint")
]
```

### Task 代理高效使用

#### general-purpose 代理
```python
# 處理複雜的多步驟重構任務
Task(
    subagent_type="general-purpose",
    description="重構導入路徑",
    prompt="搜索並替換所有 'cogs.core' 為 'src.core'，包括：1. 搜索所有相關文件 2. 批量替換 3. 驗證語法正確性"
)
```

### 常用高效命令模式

#### 批量導入路徑修復
```bash
# 使用 find + sed 批量替換
find src -name "*.py" -exec sed -i 's/from cogs\.core/from src.core/g' {} \;
find src -name "*.py" -exec sed -i 's/import cogs\.core/import src.core/g' {} \;
```

#### 快速代碼檢查
```bash
# 並行執行多個代碼品質檢查
make format & make lint & make test & wait
```

### 檔案操作最佳實踐

#### 讀取前批量搜索
```python
# 先用 Grep 找到需要修改的文件，再批量讀取
files = Grep(pattern="problematic_pattern", output_mode="files_with_matches")
# 然後並行讀取這些文件進行修改
```

#### 優先使用 MultiEdit
```python
# ❌ 低效：多次 Edit 調用
Edit(file, "old1", "new1")
Edit(file, "old2", "new2") 
Edit(file, "old3", "new3")

# ✅ 高效：單次 MultiEdit 調用
MultiEdit(file, [
    {"old_string": "old1", "new_string": "new1"},
    {"old_string": "old2", "new_string": "new2"},
    {"old_string": "old3", "new_string": "new3"}
])
```

### 專案特定高效操作

#### Discord.py 模組重構
```python
# 批量更新 Cog 導入路徑
Task(
    subagent_type="general-purpose",
    description="更新所有 Cog 導入",
    prompt="搜索 src/cogs 目錄下所有 .py 文件，將 'from cogs.core' 替換為 'from src.core'"
)
```

#### 配置系統優化
```bash
# 批量驗證配置文件
find . -name "config.py" -exec python -m py_compile {} \;
```

### 效率提升技巧

1. **批量操作優先**: 使用 MultiEdit 而非多次 Edit
2. **並行工具調用**: 在單次回應中調用多個工具
3. **精確搜索**: 使用正則表達式和文件類型過濾
4. **代理授權**: 讓專門代理處理複雜的多步驟任務
5. **命令組合**: 使用 Bash 工具執行組合命令

這些工具和技巧可以將文件修改效率提升 3-10 倍，特別適用於大型代碼庫的重構和批量修改任務。

## MCP Server 整合指南

Claude Code 支援 Model Context Protocol (MCP) 伺服器整合，提供額外的工具和功能。本專案整合了多個 MCP 伺服器以提升開發效率。

### 已整合的 MCP 伺服器

#### Desktop Commander (mcp__desktop-commander__)
全功能檔案系統和進程管理工具，是 Claude Code 的主要檔案操作工具。

**核心功能**:
- **檔案操作**: `read_file`, `write_file`, `edit_block` 進行檔案讀寫和編輯
- **目錄管理**: `list_directory`, `create_directory`, `move_file` 進行目錄操作
- **搜尋功能**: `search_files`, `search_code` 進行檔案和程式碼搜尋
- **進程管理**: `start_process`, `interact_with_process` 管理終端進程
- **本地分析**: 專為本地檔案分析設計，支援 CSV、JSON 等資料處理

**最佳實踐**:
```python
# 1. 檔案讀取和編輯
content = mcp__desktop-commander__read_file(path="D:\\coding\\Discord ROAS Bot\\src\\core\\bot.py")
mcp__desktop-commander__edit_block(
    file_path="D:\\coding\\Discord ROAS Bot\\src\\core\\bot.py",
    old_string="舊程式碼",
    new_string="新程式碼"
)

# 2. 程式碼搜尋
results = mcp__desktop-commander__search_code(
    path="D:\\coding\\Discord ROAS Bot\\src",
    pattern="class.*Cog",
    filePattern="*.py"
)

# 3. 資料分析進程
pid = mcp__desktop-commander__start_process(command="python3 -i", timeout_ms=30000)
mcp__desktop-commander__interact_with_process(
    pid=pid,
    input="import pandas as pd; df = pd.read_csv('data.csv')"
)

# 4. 檔案寫入（分塊）
mcp__desktop-commander__write_file(
    path="D:\\coding\\Discord ROAS Bot\\new_file.py",
    content="第一塊內容（25-30行）",
    mode="rewrite"
)
mcp__desktop-commander__write_file(
    path="D:\\coding\\Discord ROAS Bot\\new_file.py", 
    content="第二塊內容",
    mode="append"
)
```

#### Context7 (mcp__context7__)
專業程式庫文檔查詢工具，提供最新的 API 文檔和程式碼範例。

**核心功能**:
- **程式庫解析**: `resolve-library-id` 解析程式庫名稱為 Context7 ID
- **文檔查詢**: `get-library-docs` 獲取詳細的 API 文檔
- **主題搜尋**: 支援特定主題的精確文檔搜尋
- **程式碼範例**: 提供實際可用的程式碼範例

**最佳實踐**:
```python
# 1. 解析程式庫 ID
library_info = mcp__context7__resolve-library-id(libraryName="discord.py")

# 2. 獲取文檔
docs = mcp__context7__get-library-docs(
    context7CompatibleLibraryID="/rapptz/discord.py",
    topic="cogs",
    tokens=10000
)

# 3. 查詢特定功能
component_docs = mcp__context7__get-library-docs(
    context7CompatibleLibraryID="/rapptz/discord.py",
    topic="ui components buttons",
    tokens=5000
)
```

#### Sequential Thinking (mcp__sequential-thinking__)
結構化思考工具，用於複雜問題分析和多步驟解決方案設計。

**核心功能**:
- **結構化思考**: 分步驟分析複雜問題
- **思考分支**: 探索不同的解決方案路徑
- **思考修正**: 修正和改進之前的分析
- **邏輯驗證**: 驗證解決方案的正確性

**最佳實踐**:
```python
# 1. 開始結構化思考
mcp__sequential-thinking__sequentialthinking(
    thought="分析 Discord 機器人架構重構的第一步：識別目前的問題點",
    thoughtNumber=1,
    totalThoughts=5,
    nextThoughtNeeded=True
)

# 2. 繼續思考並修正
mcp__sequential-thinking__sequentialthinking(
    thought="重新考慮之前的分析，應該先處理導入路徑問題",
    thoughtNumber=2,
    totalThoughts=6,  # 調整總思考數
    nextThoughtNeeded=True,
    isRevision=True,
    revisesThought=1
)

# 3. 分支思考
mcp__sequential-thinking__sequentialthinking(
    thought="探索另一種重構方案：逐步遷移 vs 一次性重構",
    thoughtNumber=3,
    totalThoughts=6,
    nextThoughtNeeded=True,
    branchFromThought=1,
    branchId="alternative_approach"
)

# 4. 完成思考
mcp__sequential-thinking__sequentialthinking(
    thought="綜合分析，確定最佳重構方案並提供實施步驟",
    thoughtNumber=6,
    totalThoughts=6,
    nextThoughtNeeded=False
)
```

### MCP 工具使用策略

#### 1. 程式碼分析工作流程
```
分析需求 → 結構化思考 → 文檔查詢 → 檔案搜尋 → 編輯修改 → 驗證結果
     ↓           ↓           ↓           ↓           ↓           ↓
Sequential   Sequential    Context7    Desktop     Desktop    標準工具
Thinking     Thinking      Docs        Commander   Commander   (Bash/Test)
```

#### 2. 大規模重構工作流程
```python
# 第一步：結構化分析問題
mcp__sequential-thinking__sequentialthinking(
    thought="分析重構需求和影響範圍",
    thoughtNumber=1,
    totalThoughts=4,
    nextThoughtNeeded=True
)

# 第二步：搜尋需要修改的檔案
files = mcp__desktop-commander__search_code(
    path="D:\\coding\\Discord ROAS Bot\\src",
    pattern="from cogs\\.core",
    filePattern="*.py"
)

# 第三步：批量修改
for file_path in affected_files:
    mcp__desktop-commander__edit_block(
        file_path=file_path,
        old_string="from cogs.core",
        new_string="from src.core"
    )

# 第四步：查詢相關文檔確認最佳實踐
docs = mcp__context7__get-library-docs(
    context7CompatibleLibraryID="/rapptz/discord.py",
    topic="extensions cogs"
)
```

#### 3. 效能優化原則
- **思考優先**: 使用 Sequential Thinking 分析複雜問題
- **檔案級操作**: 使用 Desktop Commander 進行精確檔案操作
- **文檔輔助**: 使用 Context7 獲取最新的程式庫文檔
- **分塊處理**: 大檔案寫入採用分塊策略

### 專案特定 MCP 整合

#### Discord.py 開發優化
```python
# 1. 查詢 Discord.py 最新文檔
library_id = mcp__context7__resolve-library-id(libraryName="discord.py")
cog_docs = mcp__context7__get-library-docs(
    context7CompatibleLibraryID=library_id,
    topic="cogs extensions",
    tokens=8000
)

# 2. 搜尋所有 Cog 類別
cogs = mcp__desktop-commander__search_code(
    path="D:\\coding\\Discord ROAS Bot\\src\\cogs",
    pattern="class.*Cog.*:",
    filePattern="*.py"
)

# 3. 分析 Discord 事件處理器
events = mcp__desktop-commander__search_code(
    path="D:\\coding\\Discord ROAS Bot\\src",
    pattern="async def on_.*\\(",
    filePattern="*.py"
)
```

#### 配置系統管理
```python
# 1. 結構化分析配置需求
mcp__sequential-thinking__sequentialthinking(
    thought="分析配置系統的架構和依賴關係",
    thoughtNumber=1,
    totalThoughts=3,
    nextThoughtNeeded=True
)

# 2. 搜尋配置相關檔案
config_files = mcp__desktop-commander__search_files(
    path="D:\\coding\\Discord ROAS Bot\\src",
    pattern="config"
)

# 3. 讀取和分析配置檔案
for config_file in config_files:
    content = mcp__desktop-commander__read_file(path=config_file)
    # 分析配置結構...
```

### 最佳實踐與注意事項

#### 1. Desktop Commander 使用指南
- **絕對路徑**: 始終使用完整的絕對路徑
- **分塊寫入**: 大檔案必須分成 25-30 行的塊
- **搜尋優化**: 使用適當的檔案模式和正則表達式
- **進程管理**: 善用進程工具進行資料分析

#### 2. Context7 最佳實踐
- **先解析後查詢**: 總是先使用 resolve-library-id
- **主題聚焦**: 使用具體的 topic 參數獲得精確結果
- **控制輸出**: 適當設定 tokens 參數控制文檔大小
- **版本特定**: 查詢特定版本的文檔時包含版本資訊

#### 3. Sequential Thinking 策略
- **估算思考數**: 從小的 totalThoughts 開始，需要時調整
- **善用修正**: 使用 isRevision 修正之前的分析
- **分支探索**: 使用 branchFromThought 探索不同方案
- **明確結束**: 確保設定 nextThoughtNeeded=False 完成思考

#### 4. 整合工作流程
```python
# 複雜問題的標準流程
# 1. 思考分析
mcp__sequential-thinking__sequentialthinking(...)

# 2. 文檔查詢（如需要）
docs = mcp__context7__get-library-docs(...)

# 3. 檔案操作
files = mcp__desktop-commander__search_files(...)
content = mcp__desktop-commander__read_file(...)
mcp__desktop-commander__edit_block(...)

# 4. 驗證結果
Bash("make lint")  # 或其他驗證命令
```

### 整合檢查清單

使用 MCP 工具前請確認：
- [ ] Desktop Commander 可以訪問專案目錄
- [ ] 使用絕對路徑進行所有檔案操作
- [ ] Context7 查詢前先解析程式庫 ID
- [ ] Sequential Thinking 適用於複雜問題分析
- [ ] 檔案寫入採用分塊策略
- [ ] 錯誤處理和降級方案已就位

透過有效整合這三個 MCP 伺服器，可以建立一個完整的開發工作流程：Strategic Thinking 負責分析，Context7 提供文檔支援，Desktop Commander 執行具體操作。這種組合特別適合 Discord 機器人專案的複雜開發需求。

