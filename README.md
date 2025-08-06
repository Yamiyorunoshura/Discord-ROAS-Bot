# Discord ROAS Bot

一個功能完整的現代化 Discord 機器人，提供活躍度追蹤、歡迎系統、群組保護、資料同步、訊息監控等多項功能。

## 🚀 主要功能

### 🏆 成就系統 (`cogs/achievement`)
- **界面設計**: 使用Discord嵌入式訊息作為控制面板，根據用戶權限顯示不同介面。
- **成就管理**: 管理員可新增/刪除/編輯成就，設置類型、圖標、描述和獎勵。
- **達成條件**: 支持訊息計數、關鍵字、互動等多種類型。
- **獎勵系統**: 主要為Discord身分組，支持多重獎勵。
- **追蹤系統**: 即時監控用戶行為，自動檢測成就達成，支持多成就進度追蹤。

### 📊 活躍度系統 (`cogs/activity_meter`)
- **活躍度計算**：0-100 分制，支援時間衰減機制
- **等級系統**：新手、活躍、資深、專家、傳奇 5 個等級
- **進度條圖片**：漸層效果、主題選擇、動態視覺效果
- **成就徽章**：個性化成就系統和徽章渲染
- **排行榜系統**：每日/每月訊息數排行榜
- **自動播報**：可設定頻道自動播報每日排行榜
- **🎛️ 完整面板系統**：四頁面管理界面（設定、預覽、統計、歷史）
- **🔐 分層權限管理**：智能權限檢查和訪問控制
- **📊 數據可視化**：豐富的統計圖表和趨勢分析

### 👋 歡迎系統 (`cogs/welcome`)
- **自訂歡迎圖片**：支援背景圖片、字體、顏色自訂
- **多格式頭像**：PNG、JPG、WebP 自動回退機制
- **智能重試**：指數退避重試和超時處理
- **多伺服器支援**：每個伺服器可設定不同歡迎圖片
- **圖片快取**：優化圖片載入效能
- **設定面板**：友善的圖形化設定介面

### 🛡️ 群組保護 (`cogs/protection`)
- **反執行檔保護**：自動檢測並處理可疑檔案
- **反連結保護**：可設定白名單的連結過濾
- **反垃圾訊息**：智能檢測和處理垃圾訊息
- **智能處理**：支援多種檔案格式與連結類型
- **管理員通知**：違規行為自動通知管理員

### 🔄 資料同步 (`cogs/sync_data`)
- **跨伺服器同步**：用戶資料、設定等跨伺服器同步
- **增量同步**：只同步變更的資料，提升效能
- **衝突解決**：智能處理資料衝突
- **同步狀態追蹤**：詳細的同步進度與狀態
- **完整面板系統**：308 行完整的管理介面

### 📝 訊息監控 (`cogs/message_listener`)
- **智能批量處理**：機器學習式的自適應批量大小調整
- **訊息記錄**：完整記錄所有訊息內容
- **Webhook 轉播**：支援圖片、GIF、貼圖轉播
- **智能搜尋**：關鍵字、頻道、時間範圍搜尋
- **表情處理**：智能處理外服表情符號
- **Discord 2024 風格**：現代化的視覺渲染

### 🗄️ 資料庫管理 (`cogs/database`)
- **統一資料庫**：所有模組使用統一的資料庫檔案
- **連線池化**：優化資料庫連線效能
- **安全檢查**：防止空值和索引錯誤
- **自動備份**：定期資料庫備份機制
- **錯誤恢復**：資料庫錯誤自動恢復

## 📋 系統需求

- **Python**: 3.12+ (必須)
- **Discord.py**: 2.5.2+
- **現代化工具鏈**: uv, ruff, mypy, pytest 等
- **構建工具**: Make (建議)
- **資料庫**: PostgreSQL (生產環境) / SQLite (開發環境)
- **容器化**: Docker + Docker Compose (可選)
- **其他依賴**: 詳見 `pyproject.toml`

## 🛠️ 安裝指南

### 📚 依賴說明

本專案使用現代化的 Python 工具鏈，主要依賴包括：

#### 核心依賴
- **discord.py** (2.5.2+): Discord API 整合
- **SQLAlchemy** (2.0+): 資料庫 ORM
- **alembic** (1.13+): 資料庫版本控制
- **Pydantic** (2.5+): 配置管理和資料驗證
- **numpy** (2.3.2+): 數值運算和效能優化
- **Pillow** (11.2+): 圖片處理
- **aiosqlite** (0.21+): 異步 SQLite 支援

#### 開發和品質工具
- **pytest** (7.0+): 測試框架
- **ruff** (0.1+): 靜態分析和格式化
- **mypy** (1.7+): 型別檢查
- **black** (24.0+): 程式碼格式化
- **uv**: 現代化包管理器

### 📦 推薦安裝方式

#### 使用 Makefile (推薦)
```bash
# 克隆專案
git clone <repository-url>
cd "Discord ROAS Bot"

# 完整開發環境設置（一鍵安裝）
make dev-setup

# 這個指令會自動執行：
# - 安裝 uv 包管理器
# - 安裝所有依賴
# - 設置開發環境
# - 安裝 pre-commit hooks
# - 初始化資料庫目錄
```

### 🔧 手動安裝

#### 1. 安裝 Make (如果尚未安裝)
```bash
# Ubuntu/Debian
sudo apt install make

# macOS (使用 Homebrew)
brew install make

# Windows (使用 Chocolatey)
choco install make

# Windows (使用 winget)
winget install GnuWin32.Make
```

##### 2. 環境準備
```bash
# 克隆專案
git clone <repository-url>
cd "Discord ROAS Bot"

# 使用 Make 安裝所有依賴
make install

# 或手動安裝 uv (現代化包管理器)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows 上：powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

##### 3. 安裝項目依賴
```bash
# 方法 1：使用 Makefile (推薦)
make dev

# 方法 2：使用 uv 直接安裝
uv sync --all-extras

# 方法 3：使用傳統 pip
pip install -e ".[dev]"
```

##### 4. 設定環境變數
建立 `.env` 檔案：
```env
DISCORD_TOKEN=your_discord_bot_token
DISCORD_GUILD_ID=your_guild_id
ENVIRONMENT=development
LOG_LEVEL=INFO
DATABASE_URL=sqlite:///data/bot.db
```

##### 5. 初始化資料庫
```bash
# 使用 Makefile
make db-init

# 或手動建立
mkdir -p dbs data logs
```

##### 6. 驗證安裝
```bash
# 檢查程式碼品質
make check

# 執行測試
make test

# 驗證配置
make validate-config
```

##### 7. 啟動機器人
```bash
# 開發模式啟動
make run-dev

# 或使用傳統方式
python -m src.main
```

### 🎯 完整依賴安裝清單

#### 核心運行時依賴
```bash
# 自動安裝 (通過 uv sync 或 pip install)
discord.py>=2.5.2,<3.0.0          # Discord API 整合
SQLAlchemy>=2.0.0,<3.0.0           # 資料庫 ORM
alembic>=1.13.0,<2.0.0             # 資料庫遷移
pydantic>=2.5.0,<3.0.0             # 配置管理
pydantic-settings>=2.1.0,<3.0.0    # 設定管理
PyYAML>=6.0.0,<7.0.0               # YAML 配置
aiosqlite>=0.21.0,<1.0.0           # 異步 SQLite
Pillow>=11.2.1,<12.0.0             # 圖片處理
numpy>=2.3.2                       # 數值運算
structlog>=23.2.0,<24.0.0          # 結構化日誌
cachetools>=5.3.2,<6.0.0           # 快取工具
typer>=0.12.0,<1.0.0               # CLI 介面
rich>=13.7.0,<14.0.0               # 美化輸出
```

#### 開發和測試依賴
```bash
# 開發環境自動安裝 (通過 make dev)
pytest>=7.0.0                      # 測試框架
pytest-asyncio>=0.21.0             # 異步測試
pytest-cov                         # 覆蓋率測試
ruff>=0.1.0                        # 靜態分析
mypy>=1.7.0                        # 型別檢查
black>=24.0.0                      # 程式碼格式化
pre-commit                         # Git hooks
dpytest                            # Discord.py 測試
```

### 🔧 常用 Makefile 指令

```bash
# 🚀 環境管理
make dev-setup        # 完整開發環境設置
make install          # 安裝基本依賴
make dev              # 安裝開發依賴
make upgrade          # 升級所有依賴

# 🧪 測試和品質檢查
make test             # 執行測試
make test-cov         # 執行測試並生成覆蓋率報告
make lint             # 執行靜態分析
make lint-strict      # 執行嚴格型別檢查
make quality-check    # 綜合品質檢查
make check            # 執行所有品質檢查

# 🎯 代碼格式化
make format           # 格式化程式碼
make clean            # 清理暫存檔案

# 🚀 運行和部署
make run              # 啟動機器人
make run-dev          # 開發模式啟動
make docker-build     # 建構 Docker 映像
make docker-run       # 在 Docker 中運行

# 🗄️ 資料庫管理
make db-init          # 初始化資料庫
make db-migrate       # 執行資料庫遷移
make db-backup        # 備份資料庫

# 📊 監控和日誌
make logs             # 查看日誌
make status           # 查看狀態
```

### ⚡ 升級與維護

#### 升級依賴
```bash
# 使用 Makefile (推薦)
make upgrade

# 手動升級
uv lock --upgrade
uv sync
```

#### 更新到新版本
```bash
# 拉取最新程式碼
git pull origin main

# 重新安裝依賴
make dev-setup

# 執行資料庫遷移
make db-migrate
```

### 📋 系統需求
- **Python**: 3.12+ (必須)
- **作業系統**: Windows 10+, Ubuntu 20.04+, macOS 11+
- **記憶體**: 最少 512MB RAM (建議 1GB+)
- **硬碟**: 最少 100MB 可用空間
- **網路**: 穩定的網際網路連線
- **Discord**: 有效的 Discord Bot Token

### 🔍 安裝驗證

安裝完成後，使用以下命令驗證：
```bash
# 檢查 Python 版本
python --version  # 應該是 3.12+

# 驗證 uv 安裝
uv --version

# 檢查專案依賴
make check

# 驗證配置
make validate-config

# 執行測試確保一切正常
make test

# 檢查程式碼品質
make quality-check
```

### 🐛 常見安裝問題

#### Python 版本問題
```bash
# 如果 Python 版本過舊
# Ubuntu/Debian
sudo apt update
sudo apt install python3.12 python3.12-venv

# macOS
brew install python@3.12

# Windows
# 從 python.org 下載 Python 3.12+
```

#### uv 安裝問題
```bash
# 如果 uv 安裝失敗，使用 pip 作為備用
pip install uv

# 或使用 pipx
pipx install uv
```

#### Make 不可用
```bash
# 如果沒有 Make，可以手動執行指令
uv sync --all-extras  # 代替 make dev
uv run pytest         # 代替 make test
uv run ruff check src  # 代替 make lint
```

### 📚 詳細文檔
- [完整安裝指南](docs/installation.md)
- [故障排除指南](docs/troubleshooting.md)
- [配置說明](docs/configuration.md)

## 🎮 使用方式

### CLI 命令
```bash
# 機器人運行
make run              # 生產模式啟動
make run-dev          # 開發模式啟動

# 開發工具
make test             # 執行測試
make lint             # 代碼檢查
make format           # 代碼格式化
make quality-check    # 全面品質檢查

# 監控和維護
make logs             # 查看日誌
make status           # 查看狀態
make clean            # 清理暫存檔案
```

### Discord 命令

### 活躍度系統
```
/活躍度 [成員]          # 查看活躍度進度條
/今日排行榜 [名次]      # 查看今日排行榜
/設定排行榜頻道 [頻道]  # 設定自動播報頻道
/活躍度面板              # 開啟完整管理面板
```

### 歡迎系統
```
/歡迎設定              # 開啟歡迎設定面板
```

### 群組保護
```
/保護設定              # 開啟保護設定面板
```

### 資料同步
```
/同步設定              # 開啟同步設定面板
```

### 訊息監控
```
/訊息日誌設定          # 設定訊息日誌
/搜尋訊息 [關鍵字]     # 搜尋歷史訊息
```

## 🔧 配置說明

### 權限設定
在 `config.py` 中設定各功能的權限：
```python
ADMIN_ROLES = ["管理員", "超級管理員"]
MODERATOR_ROLES = ["版主", "管理員"]
```

### 資料庫設定
```python
DBS_DIR = "dbs"                    # 資料庫目錄
ACTIVITY_DB_PATH = "activity.db"   # 活躍度資料庫
WELCOME_DB_PATH = "welcome.db"     # 歡迎系統資料庫
MESSAGE_DB_PATH = "message.db"     # 訊息記錄資料庫
```

### 日誌設定
```python
LOGS_DIR = "logs"                  # 日誌目錄
LOG_LEVEL = logging.INFO           # 日誌等級
```

## 🐛 故障排除

### 常見問題

1. **機器人無法啟動**
   - 檢查 Discord Token 是否正確
   - 確認所有依賴已安裝
   - 檢查 `.env` 檔案格式

2. **權限錯誤**
   - 確認機器人擁有必要權限
   - 檢查 `config.py` 中的權限設定

3. **資料庫錯誤**
   - 檢查資料庫檔案權限
   - 確認資料庫目錄存在
   - 查看錯誤日誌

### 日誌檔案
- `logs/main_error.log` - 主要錯誤日誌
- `logs/activity_meter.log` - 活躍度系統日誌
- `logs/database.log` - 資料庫操作日誌
- `logs/message_listener.log` - 訊息監控日誌

## 📈 效能優化

### 已實作的優化
- **資料庫連線池**：減少連線開銷
- **圖片快取**：避免重複載入
- **批次處理**：減少 I/O 操作
- **非同步優化**：提升並發處理能力
- **記憶體管理**：自動清理暫存資料

### 建議設定
- 定期清理舊日誌檔案
- 監控資料庫大小
- 設定適當的同步頻率

## 🤝 貢獻指南

1. Fork 專案
2. 建立功能分支
3. 提交變更
4. 發起 Pull Request

## 📄 授權

本專案採用 MIT 授權條款。

## 🔗 相關連結

- [Discord.py 文檔](https://discordpy.readthedocs.io/)
- [Discord 開發者文檔](https://discord.com/developers/docs)

## 📞 支援

如有問題或建議，請：
1. 查看 [故障排除](#故障排除) 章節
2. 檢查相關日誌檔案
3. 提交 Issue 或聯絡開發者

---

**版本**: v2.3.0  
**最後更新**: 2025-08-06  

**維護者**: 愛琴海民主共和國科技部