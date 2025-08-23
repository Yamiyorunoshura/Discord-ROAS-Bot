 # Discord ADR Bot v2.4.1

一個功能完整的 Discord 機器人，提供活躍度追蹤、歡迎系統、群組保護、資料同步、訊息監控等多項功能。

## 🚀 主要功能

### 📊 活躍度系統 (`cogs/activity_meter`)
- **活躍度計算**：0-100 分制，支援時間衰減機制
- **進度條圖片**：視覺化顯示用戶活躍度
- **排行榜系統**：每日/每月訊息數排行榜
- **自動播報**：可設定頻道自動播報每日排行榜

### 👋 歡迎系統 (`cogs/welcome`)
- **自訂歡迎圖片**：支援背景圖片、字體、顏色自訂
- **多伺服器支援**：每個伺服器可設定不同歡迎圖片
- **圖片快取**：優化圖片載入效能
- **設定面板**：友善的圖形化設定介面

### 🛡️ 群組保護 (`cogs/protection`)
- **反執行檔保護**：自動檢測並處理可疑檔案
- **反連結保護**：可設定白名單的連結過濾
- **智能處理**：支援多種檔案格式與連結類型
- **管理員通知**：違規行為自動通知管理員

### 🔄 資料同步 (`cogs/sync_data`)
- **跨伺服器同步**：用戶資料、設定等跨伺服器同步
- **增量同步**：只同步變更的資料，提升效能
- **衝突解決**：智能處理資料衝突
- **同步狀態追蹤**：詳細的同步進度與狀態

### 📝 訊息監控 (`cogs/message_listener`)
- **訊息記錄**：完整記錄所有訊息內容
- **Webhook 轉播**：支援圖片、GIF、貼圖轉播
- **智能搜尋**：關鍵字、頻道、時間範圍搜尋
- **表情處理**：智能處理外服表情符號

### 🗄️ 資料庫管理 (`cogs/database`)
- **統一資料庫**：所有模組使用統一的資料庫檔案
- **連線池化**：優化資料庫連線效能
- **自動備份**：定期資料庫備份機制
- **錯誤恢復**：資料庫錯誤自動恢復

## 📋 系統需求

- Python 3.13+
- uv 包管理器 (推薦) 或 pip
- Discord.py 2.6.0+
- SQLite 3
- 其他依賴見 `pyproject.toml`

## 🛠️ 安裝指南

### 方法 1: 使用 uv (推薦)

uv 是現代化的 Python 包管理器，提供更快的安裝速度和更好的依賴管理。

#### 1. 安裝 uv
```bash
# macOS/Linux (Homebrew)
brew install uv

# 或使用官方安裝腳本
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### 2. 專案設置
```bash
# 克隆專案
git clone <repository-url>
cd discord-bot

# 一鍵安裝所有依賴（包含開發依賴）
uv sync --extra dev

# 僅安裝生產依賴
uv sync
```

#### 3. 運行機器人
```bash
# 使用 uv 運行
uv run python main.py

# 或啟動虛擬環境後運行
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows
python main.py
```

### 方法 2: 傳統 pip 方式

#### 1. 環境準備
```bash
# 克隆專案
git clone <repository-url>
cd discord-bot

# 建立虛擬環境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows
```

#### 2. 安裝依賴
```bash
# 從 pyproject.toml 安裝
pip install -e ".[dev]"

# 或如果有 requirements.txt (舊版相容)
pip install -r requirement.txt
```

### 3. 設定環境變數
建立 `.env` 檔案：
```env
DISCORD_TOKEN=your_discord_bot_token
DISCORD_GUILD_ID=your_guild_id
```

### 4. 設定 config.py
根據需求修改 `config.py` 中的設定：
- 資料庫路徑
- 日誌路徑
- 權限設定
- 功能開關

### 5. 啟動機器人
```bash
# 使用 uv (推薦)
uv run python main.py

# 或傳統方式
python main.py
```

## ⚡ 開發者工作流程

### 快速開始
```bash
# 複製專案並設置開發環境
git clone <repository-url>
cd discord-bot
uv sync --extra dev

# 運行測試
uv run python -m pytest

# 程式碼格式化
uv run black .
uv run isort .

# 靜態檢查
uv run flake8 .
uv run mypy services/ panels/ core/
```

### 依賴管理
```bash
# 添加新依賴
uv add package-name

# 添加開發依賴
uv add --dev package-name

# 更新依賴
uv lock --upgrade

# 同步環境
uv sync
```

詳細的依賴管理策略請參考 [docs/dependency-policy.md](docs/dependency-policy.md)。

## 🎮 使用方式

### 活躍度系統
```
/活躍度 [成員]          # 查看活躍度進度條
/今日排行榜 [名次]      # 查看今日排行榜
/設定排行榜頻道 [頻道]  # 設定自動播報頻道
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

### uv 相關問題

1. **"uv command not found"**
   - 檢查 uv 是否已安裝：`uv --version`
   - 重新安裝：`brew install uv` (macOS) 或參考官方文檔
   - 檢查 PATH 環境變數

2. **依賴安裝失敗**
   - 清除快取：`uv cache clean`
   - 重新鎖定：`uv lock --refresh`
   - 重新安裝：`uv sync --reinstall`

3. **虛擬環境衝突**
   - 刪除現有環境：`rm -rf .venv`
   - 重新建立：`uv sync --extra dev`

### 常見問題

1. **機器人無法啟動**
   - 檢查 Discord Token 是否正確
   - 確認所有依賴已安裝：`uv sync --extra dev`
   - 檢查 `.env` 檔案格式

2. **權限錯誤**
   - 確認機器人擁有必要權限
   - 檢查 `config.py` 中的權限設定

3. **資料庫錯誤**
   - 檢查資料庫檔案權限
   - 確認資料庫目錄存在
   - 查看錯誤日誌

4. **測試失敗**
   - 運行特定測試：`uv run python -m pytest tests/test_specific.py -v`
   - 檢查依賴：`uv run python -c "import discord; print('Discord.py可用')"`
   - 檢查環境：`uv info`

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

**版本**: v2.4.1  
**最後更新**: 2025-08-23  
**維護者**: Discord Bot Team  
**技術升級**: T1-T10 - 完整模組化系統升級 (Python 3.13 + uv + 成就經濟政府系統)

### 🆕 版本 2.4.1 新功能
- 🎯 **成就系統重建**：全新的成就追蹤與獎勵機制
- 💰 **經濟系統**：完整的虛擬貨幣交易與管理
- 🏛️ **政府系統**：身份組管理與權限控制
- ⚡ **Python 3.13升級**：最新Python版本，效能大幅提升
- 📦 **uv包管理器**：現代化依賴管理，安裝速度提升50%+
- 🐳 **Docker容器化**：跨平台一鍵部署支援
- 🔍 **統一錯誤處理**：標準化錯誤代碼與追蹤系統
- 🧪 **完整測試覆蓋**：單元測試、整合測試與E2E測試
- 📚 **現代化文檔**：完整的開發與部署指南