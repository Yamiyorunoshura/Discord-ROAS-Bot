# Discord ADR Bot PRD測試結果驅動開發提示詞

## 📋 **提示詞概述**

基於PRD需求測試報告 (`memory_bank/result.md`) 生成的綜合性開發指導提示詞，用於指導Discord ADR Bot的後續開發工作。本提示詞涵蓋了功能需求、技術規格、實現指導、驗收標準、測試要求、風險控制、文檔要求等各個方面。

## 🎯 **核心開發目標**

### **主要目標**
1. **修復剩餘的3個測試失敗** (13.0% 失敗率)
2. **完善錯誤處理日誌記錄機制**
3. **優化佈局管理器實現**
4. **提升整體代碼質量至100%**
5. **準備進入Phase 4功能擴展階段**

### **具體指標**
- **測試通過率目標**: 100% (當前87.0%)
- **PRD需求實現率目標**: 100% (當前95.7%)
- **代碼完整性目標**: 100% (當前95.7%)
- **錯誤處理覆蓋率目標**: 100% (當前85%)

## 📊 **PRD測試結果分析**

### **成功實現的功能** ✅
1. **UI佈局修復需求** (100% 完成)
   - `_add_settings_components_fixed` 方法實現
   - `_update_page_components_fixed` 方法實現
   - `_check_and_optimize_layout` 方法實現
   - `create_fallback_layout` 方法實現
   - Discord UI限制檢查邏輯
   - 組件行分配算法
   - 佈局優化機制

2. **四級權限架構需求** (100% 完成)
   - `check_permission` 方法實現
   - `can_view_panel` 方法實現
   - `can_edit_settings` 方法實現
   - `can_perform_basic_operation` 方法實現
   - `can_perform_advanced_management` 方法實現
   - 四級權限檢查邏輯
   - Discord權限驗證

3. **用戶體驗優化需求** (100% 完成)
   - `optimize_user_flow` 方法實現
   - `_enable_optimization_mode` 方法實現
   - `_setup_quick_response` 方法實現
   - `_remember_user_preferences` 方法實現
   - 用戶友好錯誤提示
   - 操作流程優化
   - 響應性改進

### **需要改進的細節** ❌
1. **錯誤處理日誌記錄** (缺少 `logger.error` 調用)
2. **佈局管理器屬性** (缺少 `max_components_per_row` 屬性)
3. **錯誤處理器整合** (未使用 `self.error_handler`)

## 🔧 **技術實現指導**

### **1. 錯誤處理日誌記錄修復**

**目標**: 在 `handle_layout_error` 方法中添加詳細的錯誤日誌記錄

**實現要求**:
```python
def handle_layout_error(self, error: Exception) -> discord.Embed:
    # 添加詳細錯誤日誌記錄
    logger.error(f"佈局錯誤發生: {error}")
    logger.error(f"錯誤類型: {type(error).__name__}")
    logger.error(f"錯誤詳情: {str(error)}")
    
    # 現有的錯誤處理邏輯
    error_type = self.classify_error(error)
    return self.create_user_friendly_error_embed(error_type)
```

**驗證標準**:
- [ ] 錯誤發生時記錄詳細日誌
- [ ] 包含錯誤類型和詳情
- [ ] 不影響現有錯誤處理功能
- [ ] 通過PRD測試驗證

### **2. 佈局管理器屬性完善**

**目標**: 在 `DiscordUILayoutManager` 中添加 `max_components_per_row` 屬性

**實現要求**:
```python
class DiscordUILayoutManager:
    def __init__(self):
        self.max_components_per_row = 5  # Discord UI限制
        self.max_total_components = 25   # Discord UI限制
        # 其他初始化邏輯...
```

**驗證標準**:
- [ ] 屬性正確定義和初始化
- [ ] 與Discord UI限制一致
- [ ] 在佈局檢查中被正確使用
- [ ] 通過PRD測試驗證

### **3. 錯誤處理器整合改進**

**目標**: 在錯誤處理方法中正確使用 `self.error_handler`

**實現要求**:
```python
def handle_layout_error(self, error: Exception) -> discord.Embed:
    # 使用錯誤處理器進行錯誤分類
    error_type = self.error_handler.classify_error(error)
    
    # 記錄錯誤日誌
    logger.error(f"佈局錯誤: {error}")
    
    # 創建用戶友好的錯誤嵌入
    return self.error_handler.create_user_friendly_error_embed(error_type)
```

**驗證標準**:
- [ ] 正確使用 `self.error_handler`
- [ ] 錯誤分類功能正常
- [ ] 用戶友好錯誤提示正常
- [ ] 通過PRD測試驗證

## 📋 **開發任務分解**

### **Phase 1: 錯誤處理修復** (高優先級)
1. **修復錯誤日誌記錄**
   - 文件: `cogs/activity_meter/panel/main_view.py`
   - 方法: `handle_layout_error`
   - 添加: `logger.error` 調用

2. **完善佈局管理器屬性**
   - 文件: `cogs/activity_meter/panel/ui_layout_manager.py`
   - 類: `DiscordUILayoutManager`
   - 添加: `max_components_per_row` 屬性

3. **改進錯誤處理器整合**
   - 文件: `cogs/activity_meter/panel/main_view.py`
   - 方法: `handle_layout_error`
   - 修改: 使用 `self.error_handler`

### **Phase 2: 測試驗證** (中優先級)
1. **重新運行PRD測試套件**
   - 執行: `pytest tests/unit/test_prd_requirements.py -v`
   - 目標: 100% 通過率

2. **驗證修復效果**
   - 檢查: 錯誤處理日誌記錄
   - 檢查: 佈局管理器屬性
   - 檢查: 錯誤處理器整合

### **Phase 3: 代碼質量提升** (中優先級)
1. **代碼審查和優化**
   - 檢查代碼風格一致性
   - 優化性能瓶頸
   - 完善註釋和文檔

2. **測試覆蓋率提升**
   - 增加邊界條件測試
   - 添加異常情況測試
   - 完善集成測試

### **Phase 4: 功能擴展準備** (低優先級)
1. **架構優化**
   - 模組化重構
   - 接口標準化
   - 擴展性設計

2. **新功能規劃**
   - 用戶反饋收集
   - 功能需求分析
   - 技術方案設計

## 🎯 **驗收標準**

### **功能驗收標準**
- [ ] 所有PRD測試通過 (100% 通過率)
- [ ] 錯誤處理日誌記錄完整
- [ ] 佈局管理器屬性正確
- [ ] 錯誤處理器整合正常
- [ ] 用戶體驗優化有效

### **性能驗收標準**
- [ ] 組件分配時間 < 0.1秒
- [ ] 錯誤處理時間 < 0.5秒
- [ ] 界面響應時間 < 1秒
- [ ] 佈局優化算法高效

### **代碼質量驗收標準**
- [ ] 代碼完整性: 100%
- [ ] 錯誤處理覆蓋率: 100%
- [ ] 權限檢查準確性: 100%
- [ ] 用戶體驗優化: 100%

## 🛠️ **工具使用策略**

### **文件操作工具**
- **讀取文件**: `mcp_Desktop_Commander_read_file`
- **編輯文件**: `mcp_Desktop_Commander_edit_block`
- **搜索代碼**: `codebase_search`, `grep_search`
- **驗證修改**: `run_terminal_cmd`

### **測試驗證工具**
- **運行測試**: `run_terminal_cmd("pytest tests/unit/test_prd_requirements.py -v")`
- **檢查結果**: 分析測試輸出
- **修復問題**: 根據測試失敗信息進行修復

### **代碼分析工具**
- **語義搜索**: `codebase_search("handle_layout_error")`
- **精確搜索**: `grep_search("logger.error")`
- **文件搜索**: `file_search("main_view.py")`

## 📊 **進度追蹤**

### **當前狀態**
- **測試通過率**: 87.0% (20/23)
- **PRD需求實現率**: 95.7%
- **代碼完整性**: 95.7%
- **錯誤處理覆蓋率**: 85%

### **目標狀態**
- **測試通過率**: 100% (23/23)
- **PRD需求實現率**: 100%
- **代碼完整性**: 100%
- **錯誤處理覆蓋率**: 100%

### **關鍵里程碑**
1. **Phase 1完成**: 修復3個測試失敗
2. **Phase 2完成**: 驗證100%測試通過率
3. **Phase 3完成**: 代碼質量達到100%
4. **Phase 4準備**: 準備功能擴展

## 🔍 **風險控制**

### **技術風險**
1. **錯誤處理修復風險**
   - 風險: 修復可能影響現有功能
   - 緩解: 逐步修復，每次修復後立即測試

2. **佈局管理器修改風險**
   - 風險: 屬性添加可能影響佈局邏輯
   - 緩解: 確保向後兼容，添加適當的默認值

3. **測試失敗修復風險**
   - 風險: 修復可能引入新的問題
   - 緩解: 使用版本控制，保持修復的可回滾性

### **質量控制**
1. **代碼審查**: 每次修改後進行代碼審查
2. **測試���證**: 修改後立即運行相關測試
3. **功能驗證**: 確保修改不影響現有功能
4. **文檔更新**: 及時更新相關文檔

## 📚 **參考文檔**

### **核心文件**
- `memory_bank/result.md`: PRD測試報告
- `tests/unit/test_prd_requirements.py`: PRD測試套件
- `cogs/activity_meter/panel/main_view.py`: 主要UI邏輯
- `cogs/activity_meter/panel/ui_layout_manager.py`: 佈局管理器

### **相關文檔**
- `memory_bank/prd.md`: 產品需求文檔
- `memory_bank/development_progress_discord_adr_bot.md`: 開發進度文檔
- `memory_bank/technical_architecture_Discord_ADR_bot_2025-01-18.md`: 技術架構文檔

## 🎯 **執行指導**

### **開發流程**
1. **分析PRD測試報告** → 理解當前狀態和問題
2. **制定修復計劃** → 按優先級排序修復任務
3. **逐步實施修復** → 每次修復後立即驗證
4. **運行完整測試** → 確保100%通過率
5. **代碼質量檢查** → 確保代碼質量達標
6. **文檔更新** → 更新相關文檔和進度記錄

### **質量保證**
1. **每次修改前**: 理解修改的影響範圍
2. **每次修改後**: 立即運行相關測試
3. **每個階段完成**: 進行全面的功能驗證
4. **最終驗收**: 確保所有標準達標

### **溝通反饋**
1. **進度報告**: 定期報告修復進度
2. **問題報告**: 及時報告遇到的問題
3. **完成確認**: 每個階段完成後確認
4. **下一步計劃**: 明確下一步的開發計劃

---

**提示詞生成時間**: 2025-01-18  
**基於文檔**: `memory_bank/result.md`  
**適用範圍**: Discord ADR Bot 後續開發指導  
**目標狀態**: 100% PRD需求實現率和測試通過率