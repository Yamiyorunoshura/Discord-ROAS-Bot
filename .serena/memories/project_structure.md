# Discord ADR Bot v1.6 - 項目結構

## 根目錄結構
```
Discord ADR bot v1.6/
├── main.py                    # 主程式入口
├── config.py                  # 全域配置
├── requirement.txt            # 依賴套件清單
├── .env                       # 環境變數（需自行建立）
├── README.md                  # 項目說明
├── CHANGELOG.md               # 更新日誌
└── deploy.py                  # 部署腳本
```

## 主要目錄

### 1. cogs/ - 功能模組目錄
```
cogs/
├── core/                      # 核心系統模組
├── activity_meter/            # 活躍度系統
├── welcome/                   # 歡迎系統
├── protection/                # 群組保護
├── sync_data/                 # 資料同步
└── message_listener/          # 訊息監控
```

### 2. 資料目錄
```
├── dbs/                       # 資料庫檔案
├── logs/                      # 日誌檔案
├── data/                      # 一般資料
│   └── backgrounds/           # 背景圖片
├── fonts/                     # 字體檔案
└── backups/                   # 備份檔案
```

### 3. 開發目錄
```
├── tests/                     # 測試檔案
│   ├── unit/                  # 單元測試
│   ├── performance/           # 效能測試
│   └── conftest.py            # 測試配置
├── docs/                      # 文檔檔案
├── memory-bank/               # 記憶庫
└── venv/                      # 虛擬環境
```

## 核心模組詳細結構

### cogs/core/ - 核心系統
```
cogs/core/
├── __init__.py
├── base_cog.py               # 基礎 Cog 類別
├── error_handler.py          # 錯誤處理
├── logger.py                 # 日誌系統
├── database_pool.py          # 資料庫連線池
├── cache_manager.py          # 快取管理
├── event_bus.py              # 事件總線
├── dependency_container.py   # 依賴注入
├── api_standard.py           # API 標準
├── health_checker.py         # 健康檢查
├── performance_dashboard.py  # 效能儀表板
├── startup.py                # 啟動管理
└── venv_manager.py           # 虛擬環境管理
```

### 功能模組標準結構
每個功能模組遵循相同的結構模式：
```
cogs/module_name/
├── __init__.py               # 模組入口和 setup 函數
├── main/                     # 主要邏輯
│   ├── __init__.py
│   ├── main.py               # 主要 Cog 類別
│   ├── calculator.py         # 計算邏輯（如有）
│   ├── tasks.py              # 背景任務（如有）
│   ├── renderer.py           # 渲染邏輯（如有）
│   └── utils.py              # 工具函數
├── panel/                    # 使用者介面
│   ├── __init__.py
│   ├── main_view.py          # 主要視圖類別
│   ├── components/           # UI 組件
│   │   ├── __init__.py
│   │   ├── buttons.py        # 按鈕組件
│   │   ├── modals.py         # 模態框組件
│   │   └── selectors.py      # 選擇器組件
│   └── embeds/               # 嵌入訊息
│       ├── __init__.py
│       ├── settings_embed.py # 設定嵌入訊息
│       ├── preview_embed.py  # 預覽嵌入訊息
│       └── stats_embed.py    # 統計嵌入訊息
├── config/                   # 配置設定
│   ├── __init__.py
│   └── config.py             # 模組特定配置
└── database/                 # 資料庫操作
    ├── __init__.py
    └── database.py           # 資料庫類別
```

## 特殊目錄

### memory-bank/ - 記憶庫系統
```
memory-bank/
├── activeContext.md          # 活動上下文
├── progress.md               # 進度追蹤
├── projectbrief.md           # 項目簡介
├── tasks.md                  # 任務管理
├── archive/                  # 歸檔目錄
│   ├── archive-prd-1.64.md
│   └── archive-prd-1.64-qa-fix.md
└── [其他記憶檔案]
```

### custom_modes/ - 自定義模式
```
custom_modes/
├── creative_instructions.md  # 創意指令
├── implement_instructions.md # 實現指令
└── mode_switching_analysis.md # 模式切換分析
```

## 資料庫檔案組織

### dbs/ 目錄
```
dbs/
├── activity.db              # 活躍度系統資料庫
├── welcome.db               # 歡迎系統資料庫
├── message.db               # 訊息記錄資料庫
├── sync_data.db             # 資料同步資料庫
└── protection.db            # 群組保護資料庫
```

### logs/ 目錄
```
logs/
├── main.log                 # 主程式日誌
├── main_error.log           # 主程式錯誤日誌
├── activity_meter.log       # 活躍度系統日誌
├── welcome.log              # 歡迎系統日誌
├── message_listener.log     # 訊息監控日誌
├── sync_data.log            # 資料同步日誌
└── protection.log           # 群組保護日誌
```

## 配置檔案

### 環境變數檔案
```
.env                         # 主要環境變數
.env.development             # 開發環境變數
.env.production              # 生產環境變數
```

### 配置檔案
```
config.py                    # 全域配置
config.txt                   # 文字配置（如有）
```

## 開發工具檔案

### 品質檢查
```
quality_check.py             # 代碼品質檢查
quality_report.json          # 品質報告
run_tests_optimized.py       # 優化測試腳本
```

### 文檔檔案
```
README.md                    # 主要說明
CHANGELOG.md                 # 更新日誌
DEPLOYMENT.md                # 部署指南
README_*.md                  # 各種專項說明
```

## 注意事項

1. **模組獨立性**：每個 cogs 模組應該盡可能獨立
2. **資料庫統一**：使用統一的資料庫管理機制
3. **日誌分離**：每個模組有獨立的日誌檔案
4. **配置分層**：全域配置 + 模組特定配置
5. **測試覆蓋**：每個模組都應該有對應的測試