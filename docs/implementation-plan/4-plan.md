# 任務4實施計劃：實作政府系統核心功能

## metadata
- **task_id**: 4
- **project_name**: Discord機器人模組化系統
- **owner**: 開發團隊
- **date**: 2025-08-18
- **project_root**: /Users/tszkinlai/Coding/roas-bot
- **sources**:
  - **requirements**: /Users/tszkinlai/Coding/roas-bot/.kiro/specs/discord-bot-modular-system/requirements.md
  - **task**: /Users/tszkinlai/Coding/roas-bot/.kiro/specs/discord-bot-modular-system/tasks.md
  - **design**: /Users/tszkinlai/Coding/roas-bot/.kiro/specs/discord-bot-modular-system/design.md
- **assumptions**:
  - 任務1（核心架構基礎）已完成且穩定運作
  - 任務2（經濟系統核心）已完成，EconomyService可供整合
  - 任務3（經濟UI）已完成，BasePanel架構可重用
  - Discord.py 2.x環境已配置，支援身分組管理功能
  - 測試環境支援異步操作和資料庫事務
- **constraints**:
  - 必須基於已完成的BaseService架構
  - 需要與EconomyService緊密整合以支援政府部門帳戶
  - 必須保持向後相容性，不影響現有功能
  - 身分組操作需要適當的Discord權限驗證
  - JSON註冊表必須保證資料一致性和備份恢復

## context

### summary
任務4將實作Discord機器人政府系統的完整核心功能，包括部門管理、身分組階層管理、部門註冊表維護，以及政府理事會和部門的獨立帳戶系統。此任務將建立一個完整的政府管理框架，支援常任理事會權限管理、動態部門建立和身分組自動管理功能。

### background
基於前三個任務建立的堅實架構基礎，任務4將實現政府系統這一核心模組。系統需要支援常任理事會對政府部門的全面管理，包括部門建立、身分組階層設定、負責人指派，以及與經濟系統整合的獨立帳戶管理。政府系統將使用JSON格式維護統一的部門註冊表，確保所有部門資訊的結構化存儲和高效查詢。

### goals
- 建立完整的政府部門管理系統，支援動態部門建立和管理
- 實現自動化身分組管理，包括常任理事、部門負責人和部門級別身分組
- 整合經濟系統，為理事會和各部門建立獨立的貨幣帳戶
- 維護統一的JSON部門註冊表，支援完整的CRUD操作和資料一致性
- 建立完善的權限驗證機制，確保只有授權使用者可執行管理操作

## objectives

### functional
- **F1**: 政府系統資料模型建立
  - **description**: 建立DepartmentRegistry資料類別和相關資料庫表格結構，支援JSON註冊表的讀寫機制
  - **acceptance_criteria**:
    - DepartmentRegistry資料類別包含所有必要欄位（id, guild_id, name, head_role_id, head_user_id, level_role_id, level_name, account_id等）
    - 資料庫表格government_departments已建立並包含適當的外鍵約束
    - JSON註冊表讀寫機制支援原子性操作和錯誤恢復
    - 資料遷移腳本可正確建立所有必要的表格和索引

- **F2**: 身分組管理服務實現
  - **description**: 實作RoleService類別，支援身分組建立、階層管理和常任理事身分組自動建立
  - **acceptance_criteria**:
    - RoleService.create_role_if_not_exists方法可建立不存在的身分組
    - 常任理事身分組自動建立機制在guild中不存在時觸發
    - 部門身分組建立功能支援部門負責人和級別身分組的階層設定
    - 身分組權限和顏色可根據部門級別自動配置
    - 支援身分組的指派和移除操作，並記錄操作審計

- **F3**: 政府服務核心邏輯實現
  - **description**: 實作GovernmentService類別，整合RoleService和EconomyService以支援完整的部門管理功能
  - **acceptance_criteria**:
    - 部門建立功能同時建立資料庫記錄、身分組和經濟帳戶
    - 部門更新功能支援部門資訊、負責人和級別的修改
    - 部門刪除功能正確清理所有相關資源（資料庫、身分組、帳戶）
    - 部門註冊表CRUD操作保證資料一致性
    - 與EconomyService整合支援理事會和部門帳戶的建立和管理

- **F4**: 政府系統單元測試建立
  - **description**: 建立完整的測試套件，涵蓋政府服務和身分組服務的所有功能
  - **acceptance_criteria**:
    - 政府服務所有公開方法的單元測試覆蓋率≥90%
    - 身分組服務所有核心功能的測試案例完整
    - 測試包含正常流程、錯誤情況和邊界條件
    - 整合測試驗證與EconomyService的互動正確性
    - 測試資料隔離和清理機制確保測試獨立性

### non_functional
- **N1**: 性能要求
  - **description**: 政府系統操作回應時間和併發處理能力
  - **measurement**: 部門管理操作<500ms p95，身分組操作<200ms p95，支援10個並發部門管理請求

- **N2**: 可靠性要求  
  - **description**: 系統穩定性和資料一致性保證
  - **measurement**: JSON註冊表操作99.9%成功率，資料庫事務100%ACID合規，零資料遺失

- **N3**: 可擴展性要求
  - **description**: 支援大規模部門和身分組管理
  - **measurement**: 支援每個guild最多100個部門，1000個相關身分組，10000個部門成員

## scope

### in_scope
- 政府系統完整的資料模型設計和實現
- RoleService身分組管理服務的核心功能
- GovernmentService政府管理服務的完整業務邏輯  
- 與EconomyService的深度整合以支援政府財政管理
- JSON部門註冊表的設計、實現和維護機制
- 常任理事會權限驗證和管理功能
- 部門建立、更新、刪除的完整工作流程
- 身分組階層的自動建立和管理
- 完整的單元測試和整合測試套件
- 資料遷移腳本和資料庫表格建立
- 錯誤處理和異常恢復機制

### out_of_scope
- 政府系統的使用者介面實現（任務5的範圍）
- Discord Cog的實現和斜線指令整合（任務5的範圍）  
- 政府系統的互動面板和模態對話框（任務5的範圍）
- 成就系統與政府系統的整合（任務6的範圍）
- 政府系統的監控和度量收集
- 政府系統的國際化支援
- 高級權限管理和細粒度權限控制
- 政府系統的API文檔生成

## approach

### architecture_overview
政府系統採用分層架構設計，基於已建立的BaseService基礎架構。系統包含三個核心服務層：RoleService負責身分組管理，GovernmentService負責政府業務邏輯，以及與EconomyService的整合層。資料持久化採用雙重策略：重要的結構化資料存儲在SQLite資料庫中，而部門註冊表以JSON格式存儲以支援快速查詢和導出。整個架構遵循SOLID原則，確保高內聚低耦合的設計。

### modules
- **name**: services/government/models.py
  - **purpose**: 政府系統資料模型定義，包括DepartmentRegistry類別和相關資料結構
  - **interfaces**: 
    - DepartmentRegistry.from_dict() -> DepartmentRegistry
    - DepartmentRegistry.to_dict() -> Dict[str, Any]
    - DepartmentRegistry.validate() -> bool
  - **reuse**: 基於任務1建立的核心資料模型模式

- **name**: services/government/role_service.py  
  - **purpose**: 身分組管理服務，處理Discord身分組的建立、管理和階層設定
  - **interfaces**:
    - RoleService.create_role_if_not_exists(guild, name, **kwargs) -> discord.Role
    - RoleService.ensure_council_role(guild) -> discord.Role
    - RoleService.create_department_roles(guild, department_data) -> Dict[str, discord.Role]
    - RoleService.setup_role_hierarchy(guild, roles_config) -> bool
  - **reuse**: 繼承BaseService，使用任務1的錯誤處理和日誌記錄系統

- **name**: services/government/government_service.py
  - **purpose**: 政府系統核心業務邏輯，整合身分組管理和經濟系統
  - **interfaces**:
    - GovernmentService.create_department(guild_id, department_data) -> int  
    - GovernmentService.update_department(department_id, updates) -> bool
    - GovernmentService.delete_department(department_id) -> bool
    - GovernmentService.get_department_registry(guild_id) -> List[Dict[str, Any]]
  - **reuse**: 繼承BaseService，整合EconomyService進行帳戶管理

- **name**: tests/services/test_government_service.py
  - **purpose**: 政府系統完整的測試套件，包括單元測試和整合測試  
  - **interfaces**: 標準pytest測試介面
  - **reuse**: 使用任務1-3建立的測試框架和測試工具

### data
- **schema_changes**:
  - 建立government_departments表格，包含id, guild_id, name, head_role_id, head_user_id, level_role_id, level_name, account_id, created_at, updated_at欄位
  - 添加外鍵約束連接economy_accounts表格
  - 建立適當的索引以優化guild_id和name的查詢性能
  - 添加JSON部門註冊表存儲機制的檔案系統支援

- **migrations**:  
  - 003_create_government_tables.sql：建立政府系統相關表格
  - 004_add_government_indexes.sql：添加性能優化索引
  - 005_create_json_registry_schema.sql：建立JSON註冊表的結構定義

### test_strategy
- **unit**:
  - 政府服務所有公開方法的單元測試，使用mock對象隔離外部依賴
  - 身分組服務的Discord API互動測試，使用discord.py測試工具
  - 資料模型驗證和序列化測試
  - JSON註冊表讀寫操作的原子性測試

- **integration**:
  - GovernmentService與EconomyService整合測試，驗證帳戶建立和管理
  - GovernmentService與RoleService整合測試，驗證身分組操作
  - 資料庫事務測試，確保部門建立/刪除的資料一致性
  - 完整的部門管理工作流程測試

- **acceptance**:
  - 端到端部門建立流程測試，從請求到完成的完整驗證
  - 權限驗證測試，確保只有授權使用者可執行管理操作  
  - 錯誤恢復測試，驗證系統在異常情況下的恢復能力
  - 性能測試，驗證系統滿足非功能性需求

### quality_gates
- 單元測試覆蓋率≥90%，重點關注政府服務和身分組服務
- 整合測試通過率100%，所有服務間互動正確  
- 性能測試：部門操作p95<500ms，身分組操作p95<200ms
- 代碼品質：Pylint評分≥8.5，無嚴重安全漏洞
- 資料一致性：所有資料庫事務100%滿足ACID屬性

## milestones

- **name**: M1 - 政府系統資料模型完成
  - **deliverables**:
    - services/government/models.py模組完成，包含完整的DepartmentRegistry類別  
    - 資料庫遷移腳本完成並測試通過
    - JSON註冊表讀寫機制實現並通過原子性測試
  - **done_definition**:
    - 所有資料模型類別通過單元測試
    - 資料庫表格成功建立並包含適當約束
    - JSON操作支援事務性和錯誤恢復

- **name**: M2 - 身分組管理服務完成  
  - **deliverables**:
    - services/government/role_service.py模組完成
    - 身分組建立和階層管理功能實現
    - 常任理事身分組自動建立機制實現
  - **done_definition**:
    - RoleService所有公開方法通過單元測試
    - Discord身分組操作正確且無權限錯誤
    - 身分組階層設定符合設計規範

- **name**: M3 - 政府服務核心邏輯完成
  - **deliverables**:
    - services/government/government_service.py模組完成
    - 與EconomyService和RoleService的完整整合
    - 部門CRUD操作的完整實現
  - **done_definition**:
    - GovernmentService所有核心功能通過測試
    - 服務整合測試100%通過
    - 部門管理工作流程端到端測試成功

- **name**: M4 - 測試套件完成和系統整合
  - **deliverables**:
    - tests/services/test_government_service.py完整測試套件
    - 所有整合測試和驗收測試
    - 系統性能和可靠性驗證
  - **done_definition**:
    - 測試覆蓋率達到質量門檻要求
    - 所有功能和非功能需求驗證通過
    - 系統準備好與任務5的UI層整合

## timeline
- **start_date**: 2025-08-18
- **end_date**: 2025-08-25
- **schedule**:
  - **milestone**: M1 - 政府系統資料模型完成
    - **start**: 2025-08-18
    - **end**: 2025-08-19
  - **milestone**: M2 - 身分組管理服務完成
    - **start**: 2025-08-20  
    - **end**: 2025-08-21
  - **milestone**: M3 - 政府服務核心邏輯完成
    - **start**: 2025-08-22
    - **end**: 2025-08-24
  - **milestone**: M4 - 測試套件完成和系統整合
    - **start**: 2025-08-24
    - **end**: 2025-08-25

## dependencies

### external
- **Discord.py**: 版本≥2.0，用於身分組管理和權限操作
- **asyncio**: Python標準庫，用於異步操作和鎖管理
- **SQLite**: 資料庫後端，支援ACID事務處理
- **JSON**: 標準庫，用於部門註冊表序列化

### internal  
- **BaseService**: 任務1提供的核心服務基礎架構
- **EconomyService**: 任務2提供的經濟系統服務，用於帳戶管理整合
- **DatabaseManager**: 任務1提供的資料庫管理器
- **錯誤處理系統**: 任務1建立的異常處理框架

## estimation
- **method**: 故事點估算結合歷史數據分析
- **summary**:
  - **total_person_days**: 6天
  - **confidence**: 高
- **breakdown**:
  - **work_item**: 政府系統資料模型建立
    - **estimate**: 1.5天
  - **work_item**: 身分組管理服務實現
    - **estimate**: 1.5天  
  - **work_item**: 政府服務核心邏輯實現
    - **estimate**: 2天
  - **work_item**: 完整測試套件建立
    - **estimate**: 1天

## risks

- **id**: R1
  - **description**: Discord API限制影響身分組操作頻率
  - **probability**: 中
  - **impact**: 中  
  - **mitigation**: 實現操作節流和重試機制，監控API使用量
  - **contingency**: 如遇到嚴重限制，實現批次操作和延遲執行機制

- **id**: R2
  - **description**: JSON註冊表並發訪問導致資料不一致
  - **probability**: 中
  - **impact**: 高
  - **mitigation**: 實現檔案鎖機制和原子性寫入操作
  - **contingency**: 使用資料庫事務作為主要存儲，JSON作為快取機制

- **id**: R3  
  - **description**: 與EconomyService整合時的複雜度超出預期
  - **probability**: 低
  - **impact**: 中
  - **mitigation**: 早期進行整合測試，與任務2開發者密切協調
  - **contingency**: 簡化初始整合範圍，後續迭代中增強功能

- **id**: R4
  - **description**: Discord權限變更影響身分組管理功能
  - **probability**: 低  
  - **impact**: 高
  - **mitigation**: 實現完整的權限檢查和錯誤處理機制
  - **contingency**: 建立手動權限管理的備用方案

## open_questions

- Discord伺服器中身分組階層的最佳實踐設計是什麼？
- JSON註冊表是否需要版本控制和遷移機制？  
- 政府系統是否需要支援多級審批工作流程？
- 部門刪除時相關帳戶餘額應如何處理？

## notes

- 此任務為政府系統的核心後端實現，不包含使用者介面
- 設計充分考慮了與後續任務5（政府UI）的整合需求
- 特別關注了與經濟系統的深度整合，為政府財政管理奠定基礎
- 測試策略包含了對Discord API的模擬測試，確保在無網路環境下也能執行
- 實現過程中將產生詳細的API文檔，為後續UI開發提供參考

---

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>