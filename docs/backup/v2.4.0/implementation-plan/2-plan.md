# 任務2實作計劃：實作經濟系統核心功能

## metadata

- **task_id**: 2
- **project_name**: Discord機器人模組化系統
- **owner**: 開發團隊
- **date**: 2025-08-17
- **project_root**: /Users/tszkinlai/Coding/roas-bot
- **sources**:
  - type: requirements
    path: /Users/tszkinlai/Coding/roas-bot/.kiro/specs/discord-bot-modular-system/requirements.md
  - type: task
    path: /Users/tszkinlai/Coding/roas-bot/.kiro/specs/discord-bot-modular-system/tasks.md
  - type: design
    path: /Users/tszkinlai/Coding/roas-bot/.kiro/specs/discord-bot-modular-system/design.md
- **assumptions**:
  - 任務1的核心架構基礎已完成且穩定運作
  - 開發團隊熟悉discord.py異步程式設計模式
  - 現有的DatabaseManager架構可直接使用
  - 測試環境已配置完成
- **constraints**:
  - 必須基於已完成的BaseService架構
  - 需要保持與現有系統的向後相容性
  - 必須支援並發交易處理
  - 所有敏感操作需要審計記錄

## context

### summary

任務2將實作Discord機器人的經濟系統核心功能，建立完整的帳戶管理、交易處理和貨幣設定系統。系統將支援三種帳戶類型（使用者、政府理事會、政府部門），提供完整的交易審計機制，並為後續的使用者介面和政府系統奠定基礎。

### background

基於任務1已完成的核心架構基礎，包括BaseService抽象類別、DatabaseManager和錯誤處理系統，現在需要實作經濟系統的核心業務邏輯。系統需要支援多種帳戶類型以滿足Discord伺服器中不同角色的財政需求，包括個人使用者、政府理事會和各部門的獨立帳戶管理。

### goals

- 建立完整的經濟系統核心業務邏輯
- 實作多種帳戶類型支援和權限控制
- 建立完整的交易記錄和審計機制
- 提供靈活的貨幣配置管理功能
- 為後續任務提供穩定的API基礎

## objectives

### functional

- **id**: F1
  **description**: 實作經濟系統資料模型，支援三種帳戶類型
  **acceptance_criteria**:
    - 建立完整的資料庫表格結構（economy_accounts, economy_transactions, currency_settings）
    - 實作AccountType枚舉支援USER、GOVERNMENT_COUNCIL、GOVERNMENT_DEPARTMENT類型
    - 建立資料遷移腳本並驗證遷移成功
    - 所有資料模型類別實作完成並通過驗證

- **id**: F2
  **description**: 實作EconomyService核心業務邏輯
  **acceptance_criteria**:
    - EconomyService類別繼承BaseService並實作所有核心方法
    - 支援帳戶建立、餘額查詢、轉帳、交易記錄查詢功能
    - 實作完整的權限驗證機制
    - 所有交易操作包含審計記錄

- **id**: F3
  **description**: 實作貨幣設定管理功能
  **acceptance_criteria**:
    - 支援伺服器級別的貨幣名稱和符號配置
    - 實作配置驗證和更新機制
    - 提供預設配置處理
    - 配置變更即時生效

- **id**: F4
  **description**: 建立完整的單元測試覆蓋
  **acceptance_criteria**:
    - 所有EconomyService方法的單元測試
    - 邊界條件和錯誤情況測試
    - 並發操作測試
    - 測試覆蓋率達到90%以上

### non_functional

- **id**: N1
  **description**: 系統效能要求
  **measurement**: 查詢操作回應時間 < 100ms，轉帳操作 < 200ms

- **id**: N2
  **description**: 資料一致性保證
  **measurement**: 支援並發操作，事務成功率 > 99.9%

- **id**: N3
  **description**: 安全性要求
  **measurement**: 所有敏感操作100%審計記錄，權限驗證通過率100%

## scope

### in_scope

- 經濟系統資料模型設計和實作
- EconomyService核心業務邏輯實作
- 三種帳戶類型的完整支援
- 交易處理和審計機制
- 貨幣配置管理系統
- 完整的單元測試套件
- 與BaseService架構的無縫整合

### out_of_scope

- 使用者介面實作（任務3範圍）
- Discord面板和指令實作（任務3範圍）
- 政府系統的身分組管理（任務4範圍）
- 成就系統的獎勵機制（任務6範圍）
- 效能優化和快取機制（後續版本）

## approach

### architecture_overview

基於任務1建立的前後端分離架構，經濟系統採用服務層模式實作。EconomyService作為核心業務邏輯層，繼承BaseService並實作所有經濟相關的業務規則。系統使用SQLite資料庫儲存帳戶和交易資料，通過DatabaseManager進行資料存取。所有操作遵循事務一致性原則，確保資料完整性。

### modules

- **name**: services/economy/models.py
  **purpose**: 定義經濟系統資料模型，包括AccountType枚舉和資料驗證邏輯
  **interfaces**:
    - AccountType枚舉定義
    - 資料驗證函數
    - 資料庫模型映射
  **reuse**:
    - 使用現有的DatabaseManager基礎架構
    - 整合core/exceptions錯誤處理系統

- **name**: services/economy/economy_service.py
  **purpose**: 實作經濟系統核心業務邏輯和API介面
  **interfaces**:
    - create_account(account_id, account_type, initial_balance)
    - get_balance(account_id)
    - transfer(from_account, to_account, amount, reason)
    - get_transaction_history(account_id, limit)
    - set_currency_config(guild_id, name, symbol)
    - get_currency_config(guild_id)
  **reuse**:
    - 繼承core/base_service.BaseService
    - 使用core/database_manager.DatabaseManager
    - 整合core/exceptions錯誤處理

### data

#### schema_changes

- **economy_accounts表格**:
  - id (TEXT PRIMARY KEY): 帳戶ID，格式為 user_{user_id}_{guild_id}
  - account_type (TEXT): 帳戶類型 (user/government_council/government_department)
  - guild_id (INTEGER): Discord伺服器ID
  - balance (REAL): 帳戶餘額，預設0.0
  - created_at/updated_at (TIMESTAMP): 建立和更新時間

- **economy_transactions表格**:
  - id (INTEGER PRIMARY KEY): 交易ID
  - from_account/to_account (TEXT): 來源和目標帳戶ID
  - amount (REAL): 交易金額
  - transaction_type (TEXT): 交易類型 (transfer/deposit/withdraw/reward)
  - reason (TEXT): 交易原因
  - created_at (TIMESTAMP): 交易時間

- **currency_settings表格**:
  - guild_id (INTEGER PRIMARY KEY): Discord伺服器ID
  - currency_name (TEXT): 貨幣名稱，預設"金幣"
  - currency_symbol (TEXT): 貨幣符號，預設"💰"
  - created_at/updated_at (TIMESTAMP): 建立和更新時間

#### migrations

- 建立001_create_economy_tables.sql遷移腳本
- 包含所有表格的CREATE語句和索引建立
- 實作資料遷移驗證和回滾機制
- 建立基礎測試資料腳本

### test_strategy

#### unit

- EconomyService所有公開方法的單元測試
- 帳戶建立、餘額管理、轉帳邏輯測試
- 權限驗證和錯誤處理測試
- 資料驗證和邊界條件測試

#### integration

- 與DatabaseManager的整合測試
- 資料庫事務和一致性測試
- 並發操作和競態條件測試
- 錯誤恢復和資料完整性測試

#### acceptance

- 完整業務流程的端對端測試
- 多種帳戶類型的互動測試
- 貨幣配置變更的影響測試
- 效能基準測試和負載測試

### quality_gates

- 單元測試覆蓋率 ≥ 90%
- 所有測試穩定通過
- 程式碼審查通過，遵循專案編碼標準
- API文件完整，包含所有公開方法
- 效能測試通過：查詢 < 100ms，交易 < 200ms
- 安全審查通過，所有敏感操作有審計記錄

## milestones

- **name**: M1 - 資料模型完成
  **deliverables**:
    - 完成所有資料庫表格設計和遷移腳本
    - 實作AccountType枚舉和資料模型類別
    - 資料驗證邏輯實作完成
  **done_definition**:
    - 資料庫遷移腳本執行成功
    - 所有資料模型類別通過單元測試
    - 資料驗證邏輯覆蓋所有邊界條件

- **name**: M2 - 核心服務邏輯完成
  **deliverables**:
    - EconomyService類別實作完成
    - 所有核心API方法實作
    - 權限驗證和審計機制實作
  **done_definition**:
    - 所有核心方法通過單元測試
    - 權限驗證邏輯正確運作
    - 交易審計記錄完整

- **name**: M3 - 貨幣配置系統完成
  **deliverables**:
    - 貨幣配置CRUD操作實作
    - 配置驗證和更新機制
    - 預設配置處理邏輯
  **done_definition**:
    - 貨幣配置功能通過所有測試
    - 配置變更即時生效驗證
    - 相容性測試通過

- **name**: M4 - 測試和整合完成
  **deliverables**:
    - 完整的單元測試套件
    - 整合測試和效能測試
    - 程式碼審查和文件完成
  **done_definition**:
    - 測試覆蓋率達到90%以上
    - 所有測試穩定通過
    - 程式碼審查通過且文件完整

## timeline

- **start_date**: 2025-08-17
- **end_date**: 2025-09-06
- **schedule**:
  - milestone: M1 - 資料模型完成
    start: 2025-08-17
    end: 2025-08-21
  - milestone: M2 - 核心服務邏輯完成
    start: 2025-08-22
    end: 2025-08-28
  - milestone: M3 - 貨幣配置系統完成
    start: 2025-08-29
    end: 2025-09-02
  - milestone: M4 - 測試和整合完成
    start: 2025-09-03
    end: 2025-09-06

## dependencies

### external

- discord.py v2.3+ (已安裝，用於Discord API互動)
- SQLite 3.35+ (已配置，用於資料持久化)
- pytest 7.0+ (已安裝，用於單元測試)
- pytest-asyncio 0.21+ (已安裝，用於異步測試)

### internal

- 任務1核心架構基礎 (已完成)
- core/base_service.BaseService (已可用)
- core/database_manager.DatabaseManager (已可用)
- core/exceptions錯誤處理系統 (已可用)

## estimation

### method

故事點估算方法，基於複雜度、工作量和風險因素評估

### summary

- **total_person_days**: 15
- **confidence**: high

### breakdown

- **work_item**: 資料模型設計和實作
  **estimate**: 4天
- **work_item**: EconomyService核心邏輯實作
  **estimate**: 6天
- **work_item**: 貨幣配置系統實作
  **estimate**: 2天
- **work_item**: 測試開發和整合
  **estimate**: 3天

## risks

- **id**: R1
  **description**: 資料庫遷移失敗可能導致資料遺失
  **probability**: low
  **impact**: high
  **mitigation**: 在測試環境充分驗證遷移腳本，建立完整的備份機制
  **contingency**: 實作資料匯出/匯入工具，準備回滾程序

- **id**: R2
  **description**: 並發交易可能導致餘額不一致
  **probability**: medium
  **impact**: high
  **mitigation**: 使用資料庫事務和樂觀鎖機制，實作餘額驗證檢查
  **contingency**: 建立餘額審計工具和自動修正機制

- **id**: R3
  **description**: 權限驗證邏輯複雜可能導致安全漏洞
  **probability**: low
  **impact**: medium
  **mitigation**: 詳細的單元測試覆蓋所有權限場景，進行安全程式碼審查
  **contingency**: 實作操作審計日誌和異常監控

- **id**: R4
  **description**: 與現有系統整合可能出現相容性問題
  **probability**: low
  **impact**: medium
  **mitigation**: 基於已驗證的BaseService架構，進行逐步整合測試
  **contingency**: 保持向後相容性接口，準備適配器模式實作

## open_questions

- 是否需要實作帳戶餘額上限限制機制？
- 交易記錄的保存期限是否需要配置選項？
- 是否需要支援小數點後幾位的精度配置？

## notes

- 此任務為經濟系統的核心基礎，後續任務3（使用者介面）和任務4（政府系統）都將依賴此實作
- 所有API設計考慮了未來擴展性，為成就系統獎勵發放預留了接口
- 採用了嚴格的資料一致性策略，確保財政資料的準確性和可靠性
- 權限控制基於Discord身分組，與現有的機器人權限系統保持一致

---

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>