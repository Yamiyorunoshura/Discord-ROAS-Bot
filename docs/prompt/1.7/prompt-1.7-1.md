# 活躍度面板系統開發提示詞 v1.7-1

## 🎯 開發目標

你是一個專業的Discord機器人開發專家，需要根據PRD文檔實現一個完整的活躍度面板系統。請嚴格按照以下要求進行開發：

## 📋 核心需求理解

### 1. 面板實現問題
- **現況**: 活躍度面板並未完全實現，打開面板顯示頁面main不存在
- **目標**: 實現完整的活躍度面板系統，確保所有頁面功能正常運作

### 2. 設計通用性問題
- **現況**: 活躍度面板的設計過於通用
- **目標**: 針對活躍度系統特性優化界面，提供專屬的活躍度管理功能

### 3. 權限設計問題
- **現況**: 面板權限設計不合理
- **目標**: 實現分層權限管理，區分查看權限和操作權限

## 🏗️ 架構設計要求

### 核心組件結構
```
ActivityPanelView (主面板控制器)
├── SettingsPage (設定頁面)
├── PreviewPage (預覽頁面)
├── StatsPage (統計頁面)
└── HistoryPage (歷史頁面)
```

### 權限分層架構
1. **查看權限**: 所有伺服器成員
2. **基本操作權限**: 所有伺服器成員
3. **管理權限**: 擁有「管理伺服器」權限的成員
4. **高級管理權限**: 伺服器管理員

## 🔧 技術實現要求

### 1. 主面板控制器 (ActivityPanelView)
```python
class ActivityPanelView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild_id: int, user_id: int):
        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id
        self.current_page = "settings"
        self.db = ActivityDatabase()
        
    async def start(self, interaction: discord.Interaction):
        """啟動面板"""
        await self.show_page(interaction, self.current_page)
    
    async def show_page(self, interaction: discord.Interaction, page: str):
        """顯示指定頁面"""
        # 實現頁面切換邏輯
```

### 2. 權限檢查器 (PermissionChecker)
```python
class PermissionChecker:
    @staticmethod
    def can_view(user: discord.Member) -> bool:
        """檢查查看權限"""
        return True  # 所有人可查看
    
    @staticmethod
    def can_manage(user: discord.Member) -> bool:
        """檢查管理權限"""
        return user.guild_permissions.manage_guild
    
    @staticmethod
    def can_export(user: discord.Member) -> bool:
        """檢查導出權限"""
        return user.guild_permissions.administrator
```

### 3. 數據庫表結構
必須實現以下數據庫表：
```sql
-- 活躍度主表
CREATE TABLE meter(
  guild_id INTEGER, 
  user_id INTEGER,
  score REAL DEFAULT 0, 
  last_msg INTEGER DEFAULT 0,
  PRIMARY KEY(guild_id, user_id)
);

-- 每日統計表
CREATE TABLE daily(
  ymd TEXT, 
  guild_id INTEGER, 
  user_id INTEGER,
  msg_cnt INTEGER DEFAULT 0,
  PRIMARY KEY(ymd, guild_id, user_id)
);

-- 播報頻道設定表
CREATE TABLE report_channel(
  guild_id INTEGER PRIMARY KEY,
  channel_id INTEGER
);

-- 系統設定表
CREATE TABLE activity_settings(
  guild_id INTEGER PRIMARY KEY,
  activity_gain REAL DEFAULT 5.0,
  activity_decay_per_h REAL DEFAULT 2.0,
  activity_cooldown INTEGER DEFAULT 60,
  report_hour INTEGER DEFAULT 21,
  system_enabled BOOLEAN DEFAULT 1
);
```

## 📄 頁面實現要求

### 1. 設定頁面 (SettingsPage)
**功能要求**:
- 播報頻道設定
- 活躍度計算參數調整
- 自動播報時間設定
- 系統開關控制
- 等級系統設定
- 主題風格設定

**權限要求**:
- 查看: 所有成員
- 修改: 管理伺服器權限

### 2. 預覽頁面 (PreviewPage)
**功能要求**:
- 即時排行榜預覽
- 個人活躍度查詢
- 不同時間範圍切換
- 視覺化效果展示
- 等級系統展示

**權限要求**:
- 查看: 所有成員
- 操作: 所有成員

### 3. 統計頁面 (StatsPage)
**功能要求**:
- 系統使用統計
- 用戶活躍度分析
- 頻道活躍度排行
- 歷史數據趨勢
- 排行榜統計
- 系統性能監控

**權限要求**:
- 查看: 所有成員
- 詳細數據: 管理伺服器權限

### 4. 歷史記錄頁面 (HistoryPage)
**功能要求**:
- 歷史排行榜記錄
- 用戶活躍度變化
- 數據導出功能
- 數據清理功能
- 備份還原功能
- 數據分析報告

**權限要求**:
- 查看: 所有成員
- 導出/管理: 管理伺服器權限

## 🎨 界面設計要求

### 面板佈局
```
┌─────────────────────────────────────┐
│ 📊 活躍度系統管理面板              │
├─────────────────────────────────────┤
│ [設定] [預覽] [統計] [歷史]        │
├─────────────────────────────────────┤
│ [重新整理] [設定頻道] [清除數據]   │
├─────────────────────────────────────┤
│ [關閉]                             │
└─────────────────────────────────────┘
```

### 設計原則
- 使用按鈕式頁面切換
- 保持當前頁面狀態
- 提供頁面載入指示器
- 響應式設計，適配不同螢幕尺寸

## 🔍 錯誤處理要求

### 統一錯誤處理機制
```python
class PanelErrorHandler:
    @staticmethod
    async def handle_database_error(interaction: discord.Interaction, error: Exception):
        """處理資料庫錯誤"""
        logger.error(f"面板資料庫錯誤: {error}")
        await interaction.followup.send(
            "❌ 資料庫操作失敗，請稍後再試",
            ephemeral=True
        )
    
    @staticmethod
    async def handle_permission_error(interaction: discord.Interaction, required_permission: str):
        """處理權限錯誤"""
        await interaction.followup.send(
            f"❌ 需要「{required_permission}」權限才能執行此操作",
            ephemeral=True
        )
```

## ⚡ 性能優化要求

### 緩存機制
- 實現排行榜數據緩存
- 緩存時間設定為5分鐘
- 異步數據加載

### 異步處理
- 所有數據庫操作必須異步
- 使用asyncio.gather進行並發處理
- 避免阻塞主線程

## 📊 數據渲染要求

### 排行榜渲染
```python
async def render_rankings_embed(self, rankings: List[Dict], guild: discord.Guild) -> discord.Embed:
    """渲染排行榜嵌入"""
    lines = []
    for rank, data in enumerate(rankings, 1):
        user_id = data["user_id"]
        msg_cnt = data["msg_cnt"]
        member = guild.get_member(user_id)
        name = member.display_name if member else f"<@{user_id}>"
        lines.append(f"`#{rank:2}` {name:<20} ‧ {msg_cnt} 則")
    
    embed = discord.Embed(
        title=f"📈 活躍排行榜 - {guild.name}",
        description="\n".join(lines),
        colour=discord.Colour.green()
    )
    return embed
```

## 🧪 測試要求

### 功能測試
- 面板載入測試
- 頁面切換測試
- 權限檢查測試
- 數據顯示測試

### 權限測試
- 普通成員權限測試
- 管理員權限測試
- 權限邊界測試

### 性能測試
- 面板響應速度測試
- 數據載入性能測試
- 並發訪問測試

## 📝 代碼質量要求

### 代碼規範
- 使用類型提示 (Type Hints)
- 添加詳細的docstring
- 遵循PEP 8代碼風格
- 使用適當的異常處理

### 模組化設計
- 每個頁面獨立成類
- 使用依賴注入
- 避免循環依賴
- 保持代碼可測試性

## 🚀 實施步驟

### Phase 1: 基礎架構
1. 實現ActivityPanelView主控制器
2. 建立PermissionChecker權限檢查器
3. 實現基礎頁面切換功能

### Phase 2: 核心功能
1. 實現SettingsPage設定頁面
2. 實現PreviewPage預覽頁面
3. 實現StatsPage統計頁面
4. 實現HistoryPage歷史頁面

### Phase 3: 優化完善
1. 添加錯誤處理機制
2. 實現緩存優化
3. 完善界面設計
4. 添加性能監控

### Phase 4: 測試部署
1. 進行功能測試
2. 進行權限測試
3. 進行性能測試
4. 部署上線

## ✅ 驗收標準

### 功能驗收
- [ ] 所有頁面正常載入
- [ ] 頁面切換流暢
- [ ] 權限檢查準確
- [ ] 數據顯示正確

### 性能驗收
- [ ] 面板載入時間 < 2秒
- [ ] 頁面切換時間 < 1秒
- [ ] 支持100+並發用戶

### 用戶體驗驗收
- [ ] 界面直觀易用
- [ ] 錯誤提示清晰
- [ ] 操作流程順暢

## 🔄 開發流程

1. **需求分析**: 仔細閱讀PRD文檔，理解核心需求
2. **架構設計**: 設計清晰的模組架構
3. **逐步實現**: 按照Phase順序逐步實現功能
4. **測試驗證**: 每個階段完成後進行測試
5. **優化完善**: 根據測試結果進行優化

## 📋 重要提醒

1. **嚴格遵循PRD**: 所有功能必須完全符合PRD文檔要求
2. **權限設計**: 必須實現分層權限管理
3. **錯誤處理**: 必須有完善的錯誤處理機制
4. **性能優化**: 必須考慮性能問題
5. **代碼質量**: 必須保持高代碼質量
6. **測試覆蓋**: 必須有充分的測試覆蓋

---

**提示詞版本**: v1.7-1  
**創建日期**: 2025-01-18  
**適用範圍**: 活躍度面板系統開發  
**開發目標**: 實現完整、穩定、易用的活躍度面板系統
