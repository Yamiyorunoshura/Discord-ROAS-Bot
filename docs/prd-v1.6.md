# Discord ADR Bot v1.6 產品需求文檔

## 1. 專案概述

### 1.1 背景
Discord ADR Bot 是一個功能完整的 Discord 機器人，目前已迭代到 v1.5 版本，提供活躍度追蹤、歡迎系統、群組保護、資料同步、訊息監控等多項功能。v1.6 版本將進一步優化架構，提升性能和可維護性。

### 1.2 目標
1. 重構核心模組架構，使其更加模塊化和可維護
2. 優化啟動流程，實現異步並行啟動以提升啟動速度
3. 統一模組結構，提高代碼一致性和可讀性
4. 增強錯誤處理和日誌記錄機制
5. 進一步拆分模組內部邏輯，實現真正的單一職責原則
6. 拆分複雜的UI面板邏輯，提高可維護性和擴展性

## 2. 核心需求

### 2.1 啟動流程優化
- **異步並行啟動**：將啟動程序改為完全異步執行，加快啟動速度
- **智能批次載入**：根據依賴關係自動排序和分批載入模組
- **啟動狀態追蹤**：提供詳細的啟動進度和狀態報告
- **失敗優雅處理**：單一模組失敗不影響其他模組的載入（核心模組除外）

### 2.2 模組架構重構
將以下核心模組重構為統一的架構：
- message_listener（訊息監聽）
- activity_meter（活躍度系統）
- protection（群組保護）
- welcome（歡迎系統）

#### 2.2.1 統一模組結構
每個模組應遵循以下目錄結構，將不同職責的代碼分離到專用子目錄中：
```
cogs/模組名稱/
  ├── __init__.py       # 模組入口點，負責導出和設置
  ├── main/             # 主要邏輯實現目錄
  │   ├── main.py       # 主要業務邏輯協調中心
  │   ├── detector.py   # 偵測相關邏輯（如適用）
  │   ├── actions.py    # 動作執行相關邏輯（如適用）
  │   ├── tasks.py      # 背景任務相關邏輯（如適用）
  │   ├── renderer.py   # 渲染相關邏輯（如適用）
  │   └── utils.py      # 工具函數（如適用）
  ├── config/           # 配置相關目錄
  │   └── config.py     # 模組特定配置項
  ├── database/         # 資料庫相關目錄
  │   └── database.py   # 資料庫操作類
  └── panel/            # 互動面板相關目錄
      ├── main_view.py  # 主要視圖類，作為UI協調中心
      ├── embeds/       # Embed生成相關邏輯
      │   ├── preview_embed.py  # 預覽面板Embed生成
      │   ├── config_embed.py   # 設定面板Embed生成
      │   └── stats_embed.py    # 統計面板Embed生成
      └── components/   # UI元件相關邏輯
          ├── buttons.py      # 按鈕元件集合
          ├── modals.py       # 對話框元件集合
          └── selectors.py    # 選擇器元件集合
```

#### 2.2.2 模組職責劃分
- **__init__.py**：模組入口點，負責導出必要的類和函數，以及實現 `setup` 函數
- **main/main.py**：作為模組的指揮中心，協調各個子模組的工作，但不直接實現具體功能
- **main/detector.py**：專門負責偵測邏輯，如垃圾訊息偵測、惡意連結偵測等
- **main/actions.py**：專門負責執行動作，如刪除訊息、禁言用戶等
- **main/tasks.py**：專門負責背景任務，如定期更新黑名單、重置計數等
- **main/renderer.py**：負責圖片生成、格式化等渲染相關邏輯
- **main/utils.py**：提供模組內共用的工具函數
- **config/config.py**：定義模組特定的配置項、常量和默認值
- **database/database.py**：封裝所有與資料庫相關的操作，提供統一的資料存取介面
- **panel/main_view.py**：作為UI的協調中心，管理面板狀態並組合各種UI元件
- **panel/embeds/**：存放所有Embed生成邏輯，每個檔案專注於一種特定類型的Embed
- **panel/components/**：存放所有UI元件，按類型分類（按鈕、對話框、選擇器等）

#### 2.2.3 面板架構拆分
複雜的UI面板（特別是具有多種狀態或多個分頁的面板）將進一步拆分為：

- **主視圖類**：
  - 存放在 `panel/main_view.py`
  - 負責管理面板狀態（如當前顯示的分頁）
  - 組合各種UI元件
  - 實現面板的生命週期管理（如超時處理）
  - 作為分派器，根據狀態調用適當的Embed生成器

- **Embed生成器**：
  - 存放在 `panel/embeds/` 目錄下
  - 每個檔案專注於生成一種特定類型的Embed
  - 與主視圖類解耦，便於獨立修改和測試
  - 例如 `preview_embed.py` 專門負責生成預覽面板的Embed

- **UI元件**：
  - 存放在 `panel/components/` 目錄下
  - 按元件類型分類：`buttons.py`、`modals.py`、`selectors.py`等
  - 每個元件類專注於自己的功能和回調邏輯
  - 與主視圖類解耦，便於重用和測試

這種拆分方式使得複雜的UI邏輯變得更加清晰和可維護，同時也便於不同開發者同時處理不同部分的UI。

### 2.3 資料庫優化
- **連接池管理**：優化資料庫連接池，避免頻繁建立和關閉連接
- **異步操作**：確保所有資料庫操作都是非阻塞的異步操作
- **事務管理**：改進事務處理，確保資料一致性
- **錯誤處理**：增強資料庫操作的錯誤處理和重試機制

### 2.4 錯誤處理與日誌
- **統一錯誤處理**：實現統一的錯誤處理機制，包括友好的錯誤提示和詳細的日誌記錄
- **結構化日誌**：採用結構化日誌格式，便於日後分析和監控
- **分級日誌**：根據嚴重程度分級記錄日誌，便於問題定位
- **錯誤通知**：重要錯誤自動通知管理員

## 3. 功能模組需求

### 3.1 訊息監聽模組 (message_listener)
#### 3.1.1 主要功能
- **圖片訊息日誌**: 將監聽到的訊息渲染成 Discord 風格的圖片日誌。
- **批次處理**: 透過緩存機制，將多條訊息批次渲染，避免洗版。
- **訊息搜尋**: 提供強大的訊息搜尋功能，支援關鍵字、頻道篩選，並可將結果渲染成圖片。
- **編輯與刪除追蹤**: 獨立記錄訊息的編輯與刪除事件。
- **智慧字型處理**: 自動偵測、下載並設定中文字型，確保跨平台顯示正常。

#### 3.1.2 架構重構
- **main/main.py**: 核心 Cog 類別，協調各元件、註冊監聽器與指令。
- **main/renderer.py**: 包含 `MessageRenderer` 類別，專責將訊息物件渲染成圖片，處理所有 `Pillow` 相關邏輯。
- **main/cache.py**: 包含 `MessageCache` 類別，負責訊息的緩存與批次處理邏輯。
- **main/tasks.py**: 包含 `purge_task` 和 `check_cache_task` 等背景任務。
- **main/utils.py**: 包含字型管理、錯誤處理等通用工具函數。
- **config/config.py**: 定義模組專屬的設定，如圖片尺寸、顏色、預設字型等常數。
- **database/database.py**: 包含 `MessageListenerDB` 類別，封裝所有資料庫操作。
- **panel/**: 實現設定面板及搜尋結果的 UI。
  - **main_view.py**: 主要設定面板 `SettingsView`。
  - **search_view.py**: 搜尋結果的分頁視圖 `SearchPaginationView`。
  - **embeds/**:
    - **settings_embed.py**: 建立設定面板的 Embed。
    - **search_embed.py**: 建立搜尋結果的 Embed。
  - **components/**:
    - **buttons.py**: 設定面板及搜尋面板的按鈕。
    - **selectors.py**: 設定面板的頻道選擇器。
    - **modals.py**: 設定批次大小與時間的對話框。

### 3.2 活躍度系統 (activity_meter)
#### 3.2.1 主要功能
- 活躍度計算與追蹤
- 排行榜生成與顯示
- 活躍度進度條圖片生成
- 自動播報功能

#### 3.2.2 架構重構
- **main/main.py**：實現活躍度系統的協調邏輯
- **main/calculator.py**：專門處理活躍度計算邏輯
- **main/renderer.py**：處理活躍度進度條的圖片生成
- **main/tasks.py**：處理定期排行榜更新和播報任務
- **config/config.py**：定義活躍度系統相關的配置項
- **database/database.py**：處理活躍度數據的存儲和查詢
- **panel/**：實現活躍度系統設定面板
  - **main_view.py**：主要面板視圖類
  - **embeds/**：各種面板狀態的Embed生成器
  - **components/**：按鈕、選擇器等UI元件

### 3.3 群組保護 (protection)
#### 3.3.1 主要功能
- 反垃圾訊息保護
- 反惡意連結保護
- 反惡意程式保護
- 白名單與黑名單管理

#### 3.3.2 架構重構
保護模組是一個包含多個子模組的特殊模組，將進一步細化為：

##### 3.3.2.1 反垃圾訊息 (anti_spam)
- **main/**
  - **main.py**：協調反垃圾訊息功能，接收事件並調用相應處理器
  - **detector.py**：實現所有偵測邏輯（頻率檢查、重複訊息檢查、相似訊息檢查、貼圖檢查）
  - **actions.py**：實現所有違規處理邏輯（刪除訊息、禁言用戶、發送通知）
  - **tasks.py**：實現定期重置計數的背景任務
  - **utils.py**：提供輔助函數，如相似度計算
- **config/config.py**：存放所有常數和預設值
- **database/database.py**：處理設定的存取和統計資料的記錄
- **panel/**：實現設定面板和所有UI元件
  - **main_view.py**：存放主要面板類（_ConfigView）
  - **embeds/**：
    - **main_embed.py**：生成主面板Embed
    - **category_embed.py**：生成各類別設定面板Embed
    - **stats_embed.py**：生成統計資訊面板Embed
  - **components/**：
    - **buttons.py**：存放所有按鈕類（_CloseButton, _ResetButton等）
    - **modals.py**：存放所有對話框類（_EditModal等）
    - **selectors.py**：存放所有選擇器類（_CategorySelect等）

##### 3.3.2.2 反惡意連結 (anti_link)
- **main/**
  - **main.py**：協調反惡意連結功能，接收訊息事件並調用檢查器
  - **detector.py**：實現連結檢測邏輯，包括正則表達式匹配和網域檢查
  - **tasks.py**：實現定期更新遠端黑名單的背景任務和網路請求
  - **actions.py**：實現違規處理邏輯，如刪除訊息和發送警告
- **config/config.py**：存放URL模式、預設白名單、威脅情資來源等常數
- **database/database.py**：處理本地黑白名單的存取
- **panel/**：實現控制面板和所有UI元件
  - **main_view.py**：存放主要面板類（AntiLinkPanel）
  - **embeds/**：
    - **preview_embed.py**：生成預覽面板Embed
    - **config_embed.py**：生成設定面板Embed
    - **stats_embed.py**：生成統計面板Embed
    - **blacklist_embed.py**：生成黑名單面板Embed
    - **whitelist_embed.py**：生成白名單面板Embed
  - **components/**：
    - **buttons.py**：存放所有按鈕類（TutorialButton, WhitelistButton等）
    - **modals.py**：存放所有對話框類（WhitelistModal, DeleteMessageModal等）
    - **selectors.py**：存放所有選擇器類（PanelSelector等）

##### 3.3.2.3 反惡意程式 (anti_executable)
- **main/**
  - **main.py**：協調反惡意程式功能，接收附件事件並調用檢查器
  - **detector.py**：實現檔案檢查邏輯，包括副檔名檢查和檔案簽章檢查
  - **actions.py**：實現違規處理邏輯，如刪除附件和發送警告
- **config/config.py**：存放危險副檔名列表、檔案簽章等常數
- **database/database.py**：處理自定義檔案格式、黑白名單的存取
- **panel/**：實現設定面板和所有UI元件
  - **main_view.py**：存放主要面板類（ExecutableSettingsView）
  - **embeds/**：
    - **main_embed.py**：生成主面板Embed
    - **whitelist_embed.py**：生成白名單面板Embed
    - **blacklist_embed.py**：生成黑名單面板Embed
    - **formats_embed.py**：生成檔案格式面板Embed
  - **components/**：
    - **buttons.py**：存放所有按鈕類（WhitelistButton, BlacklistButton等）
    - **modals.py**：存放所有對話框類（AddWhitelistModal, RemoveBlacklistModal等）
    - **selectors.py**：存放所有選擇器類（如有）

##### 3.3.2.4 共享基礎
- **base.py**：保護模組的共享基礎類別，提供通用功能和介面

### 3.4 歡迎系統 (welcome)
#### 3.4.1 主要功能
- 自訂歡迎圖片生成
- 歡迎訊息發送
- 多伺服器支援
- 圖片快取管理

#### 3.4.2 架構重構
- **main/main.py**：實現歡迎系統的協調邏輯
- **main/renderer.py**：處理歡迎圖片的生成和渲染
- **main/cache.py**：管理圖片和資源的快取
- **config/config.py**：定義歡迎系統相關的配置項
- **database/database.py**：處理歡迎設定的存儲和查詢
- **panel/**：實現歡迎系統設定面板和UI元素
  - **main_view.py**：主要面板視圖類
  - **embeds/**：各種面板狀態的Embed生成器
  - **components/**：按鈕、選擇器等UI元件

## 4. 技術規格

### 4.1 依賴關係
- Python 3.8+
- Discord.py 2.5.2+
- SQLite 3 (主資料庫)
- Pillow (圖片處理)
- aiohttp (非同步 HTTP 請求)
- aiosqlite (非同步 SQLite 操作)

### 4.2 性能要求
- 啟動時間：優化後應比 v1.5 快至少 30%
- 記憶體使用：控制在合理範圍內，避免記憶體洩漏
- 資料庫操作：批次處理和連接池優化，減少 I/O 操作

### 4.3 錯誤處理
- 使用 `try-except` 包裝所有可能出錯的操作
- 實現錯誤重試機制，特別是網路和資料庫操作
- 詳細記錄錯誤堆疊和上下文信息

### 4.4 日誌記錄
- 使用 Python 標準 logging 模組
- 實現日誌輪轉，避免日誌文件過大
- 分模組記錄日誌，便於問題定位

## 5. 實現計劃

### 5.1 架構調整
1. 建立 `core/utils.py` 提取通用工具函數
2. 建立新的模組目錄結構，將功能按職責拆分到子目錄
3. 進一步拆分各模組的主要邏輯，實現單一職責原則
4. 拆分複雜的UI面板邏輯，實現UI元件的高度模組化
5. 將現有功能遷移到新架構
6. 調整模組間的依賴關係
7. 優化啟動流程

### 5.2 代碼重構
1. 重構資料庫操作，使用連接池和異步操作
2. 統一錯誤處理和日誌記錄機制
3. 優化資源使用，實現更好的記憶體管理
4. 改進模組間的通信機制
5. 將大型函數拆分為更小、更專注的函數
6. 將複雜UI邏輯拆分為獨立的視圖、Embed生成器和UI元件

### 5.3 測試與驗證
1. 單元測試：確保各模組功能正常
2. 集成測試：驗證模組間的協作
3. 性能測試：確認啟動時間和資源使用的改進
4. 用戶體驗測試：確保功能對最終用戶的可用性

## 6. 未來擴展

### 6.1 潛在新功能
- 多語言支持
- 更多自訂選項
- API 集成擴展
- 更豐富的數據分析

### 6.2 架構擴展性
新架構設計為高度模塊化，每個模組內部的邏輯也被進一步拆分，使得：
- 新增功能只需添加相應的子模組或檔案
- 修改現有功能只需關注特定子目錄或檔案
- 不同開發者可以同時處理不同模組或同一模組的不同部分而不互相干擾
- 測試更加容易，可以針對特定功能進行單元測試
- 代碼重用性提高，減少重複代碼
- 維護成本降低，問題定位更加精確
- UI元件可以輕鬆重用於不同模組或不同面板

## 7. 交付物

1. 重構後的代碼庫
2. 更新的文檔和說明
3. 性能改進報告
4. 用戶使用指南更新
5. 模組架構圖和職責說明

## 8. 時程規劃

1. 架構設計與規劃：1 週
2. 核心模組重構：2 週
3. 保護子模組深度重構：1 週
4. UI面板拆分重構：1 週
5. 啟動流程優化：1 週
6. 測試與修復：1 週
7. 文檔更新與發布：1 週

總計：8 週