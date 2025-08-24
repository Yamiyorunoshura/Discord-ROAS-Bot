# T5 實施計劃：Discord testing: dpytest and random interactions

## 元數據 (Metadata)

- **任務ID**: T5
- **專案名稱**: roas-bot
- **負責人**: task-planner (David)
- **日期**: 2025-08-22
- **專案根目錄**: /Users/tszkinlai/Coding/roas-bot
- **來源文件**:
  - 需求規格: /Users/tszkinlai/Coding/roas-bot/docs/specs/requirement.md
  - 任務規格: /Users/tszkinlai/Coding/roas-bot/docs/specs/task.md  
  - 設計規格: /Users/tszkinlai/Coding/roas-bot/docs/specs/design.md
- **假設**:
  - 現有pytest測試框架基礎建設已運作正常
  - Discord bot token可在測試環境中使用（或使用mock）
  - CI環境支援GUI-less的Discord測試執行
- **約束**:
  - 必須保持現有測試的通過率，不得引入回歸
  - 隨機測試的執行時間限制在CI可接受範圍內（<10分鐘）
  - dpytest版本需與現有discord.py版本相容

## 上下文 (Context)

### 摘要
實施dpytest測試框架整合與隨機交互測試系統，建立可在本地和CI環境執行的Discord bot測試基礎設施，提供可重現的測試失敗報告機制。

### 背景
當前測試系統缺乏Discord特定的測試框架，無法有效模擬用戶互動場景。根據需求R4，需要整合dpytest以提升測試覆蓋率，並建立隨機交互測試發現潛在的edge cases。

### 目標
- 建立完整的dpytest測試基礎設施
- 實作可重現的隨機交互測試系統
- 確保測試穩定性與可維護性
- 整合至現有CI/CD pipeline

## 目標 (Objectives)

### 功能性需求

**F-1: dpytest測試框架整合**
- 描述: 建立可在本地與CI執行的dpytest測試基礎設施，覆蓋面板與服務正常流程與錯誤處理
- 驗收條件:
  - dpytest測試可在本地環境成功執行，無環境依賴問題
  - CI pipeline整合dpytest任務，所有測試通過
  - 覆蓋achievement_panel.py與terminal_panel.py的主要互動流程
  - 包含錯誤情境測試（如權限不足、服務不可用等）

**F-2: 隨機交互測試與重現報告**
- 描述: 提供可設定種子的隨機互動測試，失敗時輸出包含種子與操作序列的重現資訊
- 驗收條件:
  - 支援--seed參數指定隨機種子，相同種子產生相同操作序列
  - 支援--max-steps參數限制測試步驟數量
  - 測試失敗時產生JSON格式的重現報告，包含種子、操作序列與失敗點
  - 重現報告可用於本地調試，重新執行相同的失敗場景

**F-3: 測試穩定性監控**
- 描述: 重複執行隨機交互測試以確認穩定性，防止flaky測試
- 驗收條件:
  - CI中實作重複執行策略（rerun 3次）
  - 提供穩定性報告，統計通過率與失敗模式
  - 識別並隔離不穩定的測試案例
  - 建立flaky測試的追蹤與修復機制

### 非功能性需求

**N-1: 測試執行效能**
- 描述: 確保測試執行時間在可接受範圍內
- 量化目標: 單次完整dpytest套件執行時間 < 5分鐘，隨機交互測試執行時間 < 10分鐘

**N-2: 測試覆蓋率提升**
- 描述: 透過dpytest提升Discord特定功能的測試覆蓋率
- 量化目標: 面板層(panels/)代碼覆蓋率達到85%以上，服務層核心功能覆蓋率維持90%以上

**N-3: 測試環境隔離**
- 描述: 確保測試間的資料隔離，避免相互影響
- 量化目標: 測試失敗重現率 > 99%，測試間資料污染事件 = 0

## 範圍 (Scope)

### 納入範圍
- tests/dpytest/目錄下的完整測試基礎設施
- 面板層（achievement_panel.py、terminal_panel.py）的dpytest測試
- 隨機交互測試框架與報告生成系統
- CI/CD pipeline的dpytest整合
- 測試穩定性監控與flaky檢測機制

### 排除範圍
- 其他測試類型（單元測試、整合測試）的修改或擴展
- Discord bot的功能性修改或新增
- 效能測試或壓力測試（已在T3中處理）
- 生產環境的測試執行（僅限開發與CI環境）

## 方法 (Approach)

### 架構概覽
採用分層測試架構，基於現有pytest框架，整合dpytest作為Discord特定測試層。隨機交互測試作為獨立模組，提供可配置的測試場景生成與執行。

### 模組設計

**M-1: dpytest測試基礎設施模組**
- 名稱: dpytest-infrastructure  
- 目的: 提供dpytest測試的基礎配置與工具函數
- 介面:
  - setup_test_bot(): 初始化測試用Discord bot實例
  - cleanup_test_environment(): 清理測試環境與資料
  - assert_message_sent(content, channel): 驗證訊息發送
  - simulate_user_interaction(user, action): 模擬用戶互動
- 重用: 基於pytest fixtures與conftest.py配置模式

**M-2: 隨機交互測試引擎模組**  
- 名稱: random-interaction-engine
- 目的: 生成與執行可重現的隨機測試場景
- 介面:
  - RandomTestOrchestrator.generate_sequence(seed, max_steps): 生成操作序列
  - RandomTestOrchestrator.execute_sequence(sequence): 執行測試序列
  - ReproductionReporter.generate_report(failure_info): 生成重現報告
  - SeedManager.validate_seed(seed): 驗證種子有效性
- 重用: 整合現有test_orchestrator_service.py的隨機互動API

**M-3: 測試監控與報告模組**
- 名稱: test-monitoring
- 目的: 監控測試穩定性並生成詳細報告  
- 介面:
  - StabilityMonitor.track_test_result(test_id, result): 追蹤測試結果
  - StabilityMonitor.detect_flaky_tests(): 檢測不穩定測試
  - ReportGenerator.generate_stability_report(): 生成穩定性報告
  - FlakyTestManager.isolate_unstable_tests(): 隔離不穩定測試
- 重用: 基於現有日誌系統與CI報告機制

### 資料設計

**資料結構變更**:
- 新增測試配置資料結構（dpytest_config.json）
- 新增隨機測試序列格式（JSON schema for test sequences）
- 新增測試結果與穩定性追蹤資料結構

**資料遷移**: 不需要 - 此任務不涉及生產資料庫變更

### 測試策略

**單元測試**:
- 隨機序列生成邏輯的正確性測試
- 種子管理與重現性驗證測試
- 報告生成功能的格式與內容驗證

**整合測試**:
- dpytest與現有測試框架的相容性測試
- 多模組協作的端到端流程測試
- CI pipeline整合後的完整流程驗證

**驗收測試**:
- 面板互動的完整用戶流程模擬
- 錯誤場景的正確處理驗證
- 隨機測試的可重現性端到端驗證

### 品質門檻
- dpytest測試套件通過率 >= 95%
- 隨機測試重現成功率 >= 99%  
- 新增測試執行時間增量 < 20%
- 現有測試回歸率 = 0%
- 代碼覆蓋率提升 >= 10%

## 里程碑 (Milestones)

### 里程碑M1: dpytest基礎設施建置
**交付成果**:
- tests/dpytest/conftest.py - 測試環境配置
- tests/dpytest/test_basic_flows.py - 基本流程測試案例
- .github/workflows/ci.yml更新 - CI整合
- docs/testing/dpytest-setup.md - 設置文檔

**完成定義**:
- dpytest測試可在本地成功執行
- CI pipeline包含dpytest任務且通過
- 基本面板流程測試覆蓋率 >= 70%
- 設置文檔完整且可操作

### 里程碑M2: 隨機交互測試系統
**交付成果**:
- tests/random/test_random_interactions.py - 隨機測試實作
- src/services/test_orchestrator_service.py更新 - 隨機互動API
- test_reports/random_test_reproduction.json - 重現報告格式
- scripts/run_random_tests.sh - 執行腳本

**完成定義**:
- 隨機測試支援seed與max-steps參數
- 測試失敗時產生可用的重現報告
- 報告包含完整的操作序列與失敗上下文
- 重現率達到99%以上

### 里程碑M3: 穩定性監控與CI優化
**交付成果**:
- .github/workflows/stability-check.yml - 穩定性檢查工作流
- test_reports/stability_analysis.json - 穩定性分析報告
- tests/utils/flaky_detector.py - 不穩定測試檢測工具
- docs/testing/stability-monitoring.md - 監控文檔

**完成定義**:
- CI實作3次重複執行策略
- 穩定性報告自動生成且資訊完整
- Flaky測試檢測機制運作正常
- 測試穩定性達到目標指標

## 時程 (Timeline)

- **開始日期**: 2025-08-23
- **結束日期**: 2025-08-30
- **總期程**: 8天

**詳細排程**:
- 里程碑M1 (dpytest基礎設施): 2025-08-23 至 2025-08-26 (4天)
- 里程碑M2 (隨機交互測試): 2025-08-26 至 2025-08-28 (3天)  
- 里程碑M3 (穩定性監控): 2025-08-28 至 2025-08-30 (2天)

## 依賴 (Dependencies)

### 外部依賴
- dpytest: ~1.7.0 (需確認與discord.py 2.x相容性)
- pytest: >= 7.0.0 (現有依賴)
- pytest-asyncio: >= 0.21.0 (支援異步測試)

### 內部依賴  
- core/logging.py: 測試日誌記錄
- tests/conftest.py: 現有測試配置基礎
- services/test_orchestrator_service.py: 測試協調服務（需擴展）

## 估算 (Estimation)

### 方法: 故事點估算
### 總工作量: 13人天
### 信心水準: 中等

### 工作分解:
- dpytest框架設置與配置: 3人天
- 基本流程測試案例開發: 3人天
- 隨機交互測試引擎開發: 4人天
- 穩定性監控與報告系統: 2人天
- CI整合與文檔撰寫: 1人天

## 風險 (Risks)

### 風險R1: dpytest版本相容性問題
- **描述**: dpytest可能與現有discord.py版本不相容，導致測試環境無法正常運作
- **機率**: 中等
- **影響**: 高等  
- **緩解措施**: 預先在隔離環境測試相容性，準備版本降級或替代方案
- **應急計劃**: 若相容性問題嚴重，考慮使用mock方式模擬Discord環境或延遲升級discord.py

### 風險R2: 隨機測試不穩定導致CI失敗
- **描述**: 隨機測試可能因為時序或環境差異導致間歇性失敗，影響CI穩定性
- **機率**: 中等
- **影響**: 中等
- **緩解措施**: 實作測試超時機制、重試邏輯，建立測試隔離與清理機制
- **應急計劃**: 將隨機測試設為可選執行，或在CI中使用固定種子集合

### 風險R3: 測試執行時間過長影響CI效率
- **描述**: dpytest和隨機測試可能顯著增加CI執行時間，影響開發效率
- **機率**: 低等
- **影響**: 中等
- **緩解措施**: 設定合理的測試範圍與時間限制，實作並行執行
- **應急計劃**: 將長時間測試移至夜間執行或設為可選任務

## 開放問題 (Open Questions)

目前無開放問題。所有技術決策已基於現有架構與需求明確定義。

## 備註 (Notes)

- 此任務是測試系統完善的關鍵環節，為後續的部署與維運奠定基礎
- dpytest整合將大幅提升Discord bot功能的測試覆蓋率與信心度  
- 隨機交互測試將幫助發現邊界情況與意外的互動模式
- 建議在實施過程中與QA團隊密切協作，確保測試案例的完整性與有效性

## 開發備註 (Dev Notes)

**描述**: 開發者在實施過程中填寫的詳細記錄，符合dev_notes_v1結構
**開發者類型**: 待填入
**時間戳記**: 待填入  
**任務階段**: 初始實施
**重新開發迭代**: 1
**變更摘要**: 待開發者填入（至少50字）
**詳細變更映射**:
  - F-IDs: ["F-1", "F-2", "F-3"]
  - N-IDs: ["N-1", "N-2", "N-3"]  
  - UI-IDs: 無
**實施決策**: 待開發者填入（至少50字）
**風險考量**: 待開發者填入（至少30字）
**維護備註**: 待開發者填入（至少30字）
**挑戰與偏離**: 待開發者填入（至少30字）
**品質指標達成**: 待開發者填入（至少20字）
**驗證警告**: []