# PRD-1.64：Sync Data 模塊面板整合與斜線指令優化

## 📋 需求概述

### 目標
將 sync_data 模塊的斜線指令功能整合到統一面板系統中，優化用戶體驗，並移除重複的斜線指令註冊，避免指令衝突。

### 背景
- 當前 sync_data 模塊同時提供斜線指令和面板兩種交互方式
- 存在功能重複和用戶體驗不一致的問題
- 需要統一到面板系統中，提供更直觀的操作界面

### 優先級
**高** - 影響用戶體驗和系統穩定性

---

## 🎯 核心需求

### 1. 斜線指令整合與註冊管理

#### 1.1 保留唯一面板入口指令
- **保留指令**: `/資料同步面板` (sync_panel)
- **功能**: 作為統一的面板入口點
- **權限**: 需要「管理伺服器」權限

#### 1.2 移除重複斜線指令
需要移除以下指令的註冊：
- `/同步資料` (sync_data_command) - 功能整合到面板的「同步操作」區域
- `/同步歷史` (sync_history_command) - 功能整合到面板的「同步歷史」頁面

#### 1.3 實現方式
```python
# 在 main.py 中註解或移除以下指令的裝飾器
# @app_commands.command(name="同步資料", description="...")
# @app_commands.command(name="同步歷史", description="...")

# 保留這些方法作為內部方法，供面板調用
async def _sync_data_internal(self, guild: discord.Guild, sync_type: str = "full"):
    """內部同步方法，供面板調用"""
    
async def _get_sync_history_internal(self, guild: discord.Guild, limit: int = 10):
    """內部歷史查詢方法，供面板調用"""
```

### 2. 面板分頁系統優化

#### 2.1 現有分頁結構
當前面板已有以下分頁：
- **狀態頁** (status): 顯示同步狀態和基本資訊
- **歷史頁** (history): 顯示同步歷史記錄
- **設定頁** (settings): 管理同步設定
- **診斷頁** (diagnostics): 系統診斷工具

#### 2.2 新增下拉選單導航
在現有按鈕導航基礎上，新增下拉選單作為輔助導航：

```python
class PageSelectDropdown(discord.ui.Select):
    """頁面選擇下拉選單"""
    
    def __init__(self, current_page: str):
        options = [
            discord.SelectOption(
                label="同步狀態",
                description="查看當前同步狀態和基本資訊",
                emoji="📊",
                value="status",
                default=(current_page == "status")
            ),
            discord.SelectOption(
                label="同步歷史",
                description="查看歷史同步記錄",
                emoji="📜",
                value="history",
                default=(current_page == "history")
            ),
            discord.SelectOption(
                label="同步設定",
                description="管理自動同步和範圍設定",
                emoji="⚙️",
                value="settings",
                default=(current_page == "settings")
            ),
            discord.SelectOption(
                label="診斷工具",
                description="系統診斷和故障排除",
                emoji="🔍",
                value="diagnostics",
                default=(current_page == "diagnostics")
            )
        ]
        
        super().__init__(
            placeholder="選擇頁面...",
            min_values=1,
            max_values=1,
            options=options
        )
```

### 3. 面板功能整合

#### 3.1 同步狀態頁面 (status)
- **主要功能**: 顯示當前同步狀態
- **整合內容**:
  - 最近同步時間和結果
  - 同步進度（如果正在同步）
  - 快速同步按鈕：完整同步、角色同步、頻道同步
  - 同步統計數據

#### 3.2 同步歷史頁面 (history)
- **主要功能**: 替代原 `/同步歷史` 指令
- **整合內容**:
  - 分頁顯示同步記錄（每頁10筆）
  - 篩選功能（按時間、狀態、類型）
  - 記錄詳情查看
  - 記錄匯出功能

#### 3.3 同步設定頁面 (settings)
- **主要功能**: 管理同步相關設定
- **整合內容**:
  - 自動同步設定（間隔、類型、通知）
  - 同步範圍設定（角色/頻道篩選）
  - 錯誤處理設定
  - 記錄保留設定

#### 3.4 診斷工具頁面 (diagnostics)
- **主要功能**: 系統診斷和故障排除
- **整合內容**:
  - 系統狀態檢查
  - 錯誤日誌查看
  - 效能指標
  - 測試連接功能

### 4. 同步操作按鈕整合

#### 4.1 整合原斜線指令功能
將 `/同步資料` 指令的三種同步類型整合為面板按鈕：

```python
# 在 _setup_components 方法中添加
# 同步操作按鈕 (第二行)
self.add_item(self.create_standard_button(
    label="完整同步",
    style="primary",
    emoji="🔄",
    callback=self.full_sync_callback
))

self.add_item(self.create_standard_button(
    label="角色同步",
    style="secondary", 
    emoji="👥",
    callback=self.roles_sync_callback
))

self.add_item(self.create_standard_button(
    label="頻道同步",
    style="secondary",
    emoji="📝", 
    callback=self.channels_sync_callback
))
```

#### 4.2 進度反饋機制
- 同步開始時禁用操作按鈕
- 顯示進度條或狀態訊息
- 同步完成後恢復按鈕並更新顯示

---

## 🔧 技術實現規格

### 1. 文件修改清單

#### 1.1 主要修改文件
- `cogs/sync_data/main/main.py`
  - 移除斜線指令裝飾器
  - 將指令方法轉為內部方法
  - 保留 `sync_panel` 指令作為面板入口

#### 1.2 面板系統文件
- `cogs/sync_data/panel/main_view.py`
  - 新增下拉選單組件
  - 整合同步操作回調
  - 優化頁面切換邏輯

- `cogs/sync_data/panel/components/`
  - 新增 `page_selector.py` - 頁面選擇下拉選單
  - 優化 `sync_buttons.py` - 同步操作按鈕

### 2. 核心實現邏輯

#### 2.1 下拉選單實現
```python
class PageSelectDropdown(discord.ui.Select):
    def __init__(self, view: "SyncDataMainView"):
        self.view = view
        # ... 選項設定 ...
        
    async def callback(self, interaction: discord.Interaction):
        selected_page = self.values[0]
        await self.view.change_page(interaction, selected_page)
```

#### 2.2 內部方法轉換
```python
# 原斜線指令方法轉為內部方法
async def _execute_sync_data(self, guild: discord.Guild, sync_type: str):
    """執行同步資料（內部方法）"""
    return await self.sync_guild_data(guild, sync_type)

async def _get_sync_history(self, guild: discord.Guild, limit: int = 10):
    """獲取同步歷史（內部方法）"""
    return await self.db.get_sync_history(guild.id, limit)
```

#### 2.3 面板布局優化
```python
def _setup_components(self):
    """設置面板組件"""
    # 第一行：頁面選擇下拉選單
    self.add_item(PageSelectDropdown(self))
    
    # 第二行：頁面切換按鈕
    # ... 現有按鈕 ...
    
    # 第三行：同步操作按鈕
    # ... 同步功能按鈕 ...
    
    # 第四行：工具按鈕
    # ... 工具功能按鈕 ...
```

### 3. 錯誤處理

#### 3.1 權限檢查
```python
async def _check_permissions(self, interaction: discord.Interaction) -> bool:
    """檢查用戶權限"""
    if not isinstance(interaction.user, discord.Member):
        return False
    return interaction.user.guild_permissions.manage_guild
```

#### 3.2 同步狀態管理
```python
async def _ensure_not_syncing(self, guild_id: int) -> bool:
    """確保不在同步中"""
    return not self.cog._is_syncing(guild_id)
```

#### 3.3 異常處理
```python
@error_handler.handle_error
async def sync_operation(self, interaction: discord.Interaction, sync_type: str):
    """同步操作異常處理"""
    try:
        # 執行同步
        result = await self._execute_sync_data(interaction.guild, sync_type)
        # 處理結果
    except Exception as e:
        # 記錄錯誤並通知用戶
        logger.error(f"同步失敗: {e}")
        await self._send_error_message(interaction, f"同步失敗: {str(e)}")
```

---

## 🎨 用戶體驗流程

### 1. 面板訪問流程
1. 用戶輸入 `/資料同步面板`
2. 系統檢查權限（需要管理伺服器權限）
3. 顯示面板，默認在「同步狀態」頁面
4. 用戶可透過按鈕或下拉選單切換頁面

### 2. 同步操作流程
1. 用戶在狀態頁面選擇同步類型
2. 系統檢查是否正在同步中
3. 開始同步，按鈕變為禁用狀態
4. 顯示進度訊息
5. 同步完成，更新狀態並恢復按鈕

### 3. 歷史查看流程
1. 用戶切換到歷史頁面
2. 系統載入最近的同步記錄
3. 支援分頁瀏覽和篩選
4. 可查看單筆記錄詳情

### 4. 設定管理流程
1. 用戶切換到設定頁面
2. 查看當前設定狀態
3. 透過模態框修改設定
4. 設定生效並顯示確認

---

## 🧪 測試標準

### 1. 功能測試
- [ ] `/資料同步面板` 指令正常工作
- [ ] 原斜線指令 `/同步資料` 和 `/同步歷史` 已移除
- [ ] 面板各頁面正常切換
- [ ] 下拉選單導航正常工作
- [ ] 同步操作按鈕功能正常

### 2. 權限測試
- [ ] 非管理員用戶無法使用面板
- [ ] 權限檢查訊息正確顯示
- [ ] 面板操作權限控制正確

### 3. 同步功能測試
- [ ] 完整同步功能正常
- [ ] 角色同步功能正常
- [ ] 頻道同步功能正常
- [ ] 同步狀態正確顯示
- [ ] 進度反饋機制正常

### 4. 歷史功能測試
- [ ] 歷史記錄正確載入
- [ ] 分頁功能正常
- [ ] 記錄詳情顯示正確
- [ ] 篩選功能正常

### 5. 設定功能測試
- [ ] 自動同步設定正常
- [ ] 同步範圍設定正常
- [ ] 設定保存和載入正常
- [ ] 設定驗證機制正常

### 6. 異常處理測試
- [ ] 同步中斷處理正常
- [ ] 網路異常處理正常
- [ ] 權限異常處理正常
- [ ] 資料庫異常處理正常

---

## 📊 驗收標準

### 1. 指令管理
- ✅ 只有 `/資料同步面板` 指令存在
- ✅ `/同步資料` 和 `/同步歷史` 指令已移除
- ✅ 原有功能完全整合到面板中

### 2. 面板功能
- ✅ 四個頁面（狀態、歷史、設定、診斷）正常工作
- ✅ 下拉選單和按鈕導航都正常
- ✅ 同步操作完全功能正常
- ✅ 設定管理完全功能正常

### 3. 用戶體驗
- ✅ 界面直觀易用
- ✅ 操作流程順暢
- ✅ 錯誤處理用戶友好
- ✅ 權限控制正確

### 4. 系統穩定性
- ✅ 無指令衝突
- ✅ 記憶體使用正常
- ✅ 併發操作安全
- ✅ 錯誤恢復機制正常

---

## 🔄 實施計劃

### 階段 1: 指令整合 (1-2小時)
1. 修改 `main.py` 移除斜線指令
2. 將指令方法轉為內部方法
3. 測試面板入口指令

### 階段 2: 下拉選單實現 (1-2小時)
1. 創建 `page_selector.py`
2. 整合到主面板視圖
3. 測試導航功能

### 階段 3: 功能整合 (2-3小時)
1. 整合同步操作到面板
2. 整合歷史查看到面板
3. 優化用戶體驗

### 階段 4: 測試與優化 (1-2小時)
1. 全面功能測試
2. 錯誤處理測試
3. 性能優化

### 總計時間: 5-9小時

---

## 📝 注意事項

### 1. 向後兼容性
- 內部方法保持原有功能
- 資料庫結構無需改變
- 配置文件保持兼容

### 2. 錯誤處理
- 所有操作都要有異常處理
- 用戶錯誤訊息要友好
- 系統錯誤要記錄日誌

### 3. 性能考慮
- 避免阻塞操作
- 適當的緩存機制
- 資源及時釋放

### 4. 安全性
- 權限檢查必須嚴格
- 輸入驗證必須完整
- 避免SQL注入等安全問題

---

*此需求文件版本: 1.0*  
*創建時間: 2024*  
*最後更新: 2024*