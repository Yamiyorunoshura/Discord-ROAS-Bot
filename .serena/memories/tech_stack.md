# Discord ADR Bot v1.6 - 技術棧

## 核心技術

### 程式語言
- **Python 3.9+** - 主要開發語言
- 支援異步程式設計（asyncio）
- 型別提示（typing）

### Discord 相關
- **discord.py 2.5.2+** - Discord API 包裝器
- **discord.py[voice]** - 語音功能支援
- 斜線指令（Slash Commands）
- 互動式 UI 組件

### 資料庫
- **SQLite 3** - 主要資料庫
- **aiosqlite 0.21.0+** - 異步 SQLite 支援
- 資料庫連線池管理

### 圖片處理
- **Pillow 11.2.1+** - 圖片處理庫
- 支援多種圖片格式（PNG、JPG、WebP）
- 字體渲染和圖像合成

### 網路和 HTTP
- **aiohttp 3.11.18+** - 異步 HTTP 客戶端
- **requests 2.31.0+** - 同步 HTTP 客戶端
- **tldextract 3.7.0+** - 域名解析

### 環境管理
- **python-dotenv 1.1.0+** - 環境變數管理
- **virtualenv** - 虛擬環境

### 效能優化
- **uvloop 0.19.0+** - 高效能事件循環（非 Windows）
- **cachetools 5.3.2+** - 快取管理
- **zstandard 0.22.0+** - 資料壓縮

### 日誌和監控
- **python-json-logger 2.0.7+** - JSON 日誌格式
- **watchdog 3.0.0+** - 檔案監控
- **psutil 5.9.0+** - 系統監控

### 資料處理
- **python-dateutil 2.8.2+** - 日期時間處理
- **regex 2023.12.25+** - 正則表達式增強
- **pydantic 2.5.0+** - 資料驗證

### 開發工具
- **black 23.12.0+** - 代碼格式化
- **flake8 6.1.0+** - 代碼檢查
- **mypy 1.8.0+** - 靜態類型檢查
- **pytest 7.4.0+** - 測試框架
- **pytest-asyncio 0.21.0+** - 異步測試
- **pytest-mock 3.12.0+** - 模擬測試

### 安全性
- **cryptography 41.0.0+** - 加密支援
- **bandit 1.7.5+** - 安全檢查
- **safety 2.3.0+** - 依賴安全檢查

### 文檔和部署
- **sphinx 7.2.0+** - 文檔生成
- **gunicorn 21.2.0+** - WSGI 伺服器
- **supervisor 4.2.5+** - 進程管理

## 特殊依賴說明

### 平台相關
- **colorama 0.4.6+** - Windows 彩色輸出支援
- **uvloop** - 僅在非 Windows 系統使用

### 字體支援
- **NotoSansCJKtc-Regular.otf** - Google 思源黑體（繁體中文）
- **wqy-microhei.ttc** - 文泉驛微黑字體

### 資料庫結構
- 統一使用 SQLite 資料庫
- 所有資料庫檔案存放於 `dbs/` 目錄
- 支援資料庫連線池和快取