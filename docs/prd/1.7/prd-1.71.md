# Discord ADR Bot v1.71 - 活躍度面板優化需求文檔

## 📋 需求概述

基於當前活躍度面板的使用體驗反饋，需要進行以下優化：
1. **簡化重複按鈕**：減少UI複雜度，提升用戶體驗
2. **完善錯誤處理**：建立完整的錯誤代碼體系
3. **移除數據導出**：簡化功能，專注核心需求
4. **添加進度條風格選擇**：允許管理員自定義視覺效果
5. **修復權限可見性**：確保面板對所有授權用戶可見

## 🎯 核心需求詳解

### 1. 按鈕簡化需求

#### 當前問題
- 面板包含過多重複功能的按鈕
- 按鈕排列雜亂，用戶體驗不佳
- 功能分類不明確

#### 優化方案
- **保留核心按鈕**：
  - 設定頁面：⚙️ 設定（包含進度條風格、公告頻道、公告時間設定）
  - 預覽頁面：👀 預覽（預覽目前進度條風格效果）
  - 統計頁面：📊 統計
- **移除不需要的按鈕**：
  - ❌ 歷史、搜尋、趨勢、清除數據、重新整理按鈕
  - ❌ 所有數據導出相關功能
- **使用下拉式選單**：
  - 頁面切換使用下拉選單
  - 設定選項使用下拉選單
  - 美化面板界面

#### 技術實現
```python
# 新的按鈕配置
CORE_BUTTONS = {
    "settings": ["設定"],  # 包含進度條風格、公告頻道、公告時間
    "preview": ["預覽"],
    "stats": ["統計"]
}

# 下拉選單配置
PAGE_SELECTOR_OPTIONS = [
    {"label": "設定", "value": "settings", "emoji": "⚙️", "description": "系統設定和配置"},
    {"label": "預覽", "value": "preview", "emoji": "👀", "description": "預覽目前進度條風格效果"},
    {"label": "統計", "value": "stats", "emoji": "📊", "description": "查看統計資訊"}
]
```

### 2. 錯誤代碼體系

#### 錯誤分類
- **E001-E099**: 權限相關錯誤
- **E100-E199**: 數據庫操作錯誤
- **E200-E299**: 面板操作錯誤
- **E300-E399**: 渲染相關錯誤
- **E400-E499**: 配置相關錯誤

#### 錯誤處理標準
```python
ERROR_CODES = {
    "E001": "權限不足：需要管理伺服器權限",
    "E002": "權限不足：需要查看頻道權限",
    "E101": "數據庫連接失敗",
    "E102": "數據庫查詢超時",
    "E201": "面板初始化失敗",
    "E202": "頁面切換失敗",
    "E301": "進度條渲染失敗",
    "E302": "圖片生成失敗",
    "E401": "配置載入失敗",
    "E402": "設定保存失敗"
}
```

### 3. 移除不需要的功能

#### 移除範圍
- ❌ 歷史、搜尋、趨勢按鈕
- ❌ 清除數據、重新整理按鈕
- ❌ 所有數據導出相關功能
- ❌ 歷史記錄頁面
- ❌ 複雜的統計功能

#### 保留功能
- ✅ 基本統計顯示
- ✅ 進度條風格預覽
- ✅ 設定管理（進度條風格、公告頻道、公告時間）
- ✅ 統計頁面功能：
  - 過去一個月平均活躍度最高的3個人
  - 訊息總量比上個月的增減百分比
- ✅ 關閉面板按鈕

### 4. 統計頁面功能系統

#### 月度排行榜功能
- **功能描述**：顯示過去一個月平均活躍度最高的3個人
- **數據來源**：活躍度數據庫的月度統計
- **顯示內容**：
  - 用戶名稱
  - 平均活躍度分數
  - 訊息數量
- **排序方式**：按平均活躍度降序排列

#### 訊息量變化趨勢功能
- **功能描述**：比較本月與上個月的訊息總量
- **計算方式**：`(本月數量 - 上個月數量) / 上個月數量 × 100%`
- **顯示內容**：
  - 本月訊息總量
  - 上個月訊息總量
  - 變化百分比（帶正負號）
  - 趨勢圖示（📈 增加，📉 減少）
- **顏色區分**：綠色表示增加，紅色表示減少

### 5. 進度條風格選擇系統

#### 風格選項
1. **Classic (經典)**: 傳統進度條樣式
2. **Modern (現代)**: 2024 Discord風格
3. **Neon (霓虹)**: 發光效果風格
4. **Minimal (極簡)**: 簡潔設計風格
5. **Gradient (漸層)**: 漸變色彩風格

#### 技術實現
```python
class ProgressBarStyle(Enum):
    CLASSIC = "classic"
    MODERN = "modern" 
    NEON = "neon"
    MINIMAL = "minimal"
    GRADIENT = "gradient"

# 風格配置
STYLE_CONFIGS = {
    "classic": {
        "bg_color": (54, 57, 63, 255),
        "border_color": (114, 118, 125),
        "text_color": (255, 255, 255),
        "shadow": True,
        "glow": False
    },
    "modern": {
        "bg_color": (32, 34, 37, 255),
        "border_color": (79, 84, 92),
        "text_color": (220, 221, 222),
        "shadow": True,
        "glow": True
    },
    # ... 其他風格配置
}
```

#### UI設計
- 在設定頁面添加風格選擇器（下拉選單）
- 在設定頁面添加公告頻道選擇器（下拉選單）
- 在設定頁面添加公告時間選擇器（下拉選單）
- 提供即時預覽功能
- 支援管理員權限控制
- 保存用戶偏好設定

### 5. 權限可見性修復

#### 當前問題
- 面板僅對呼出用戶可見
- 其他管理員無法查看面板
- 權限檢查邏輯有誤

#### 修復方案
```python
# 權限檢查邏輯
def can_view_panel(self, user: discord.Member) -> bool:
    """檢查用戶是否可以查看面板"""
    return (
        user.guild_permissions.manage_guild or
        user.guild_permissions.administrator or
        user.id == self.author_id  # 原作者始終可見
    )

def can_edit_settings(self, user: discord.Member) -> bool:
    """檢查用戶是否可以編輯設定"""
    return (
        user.guild_permissions.manage_guild or
        user.guild_permissions.administrator
    )
```

## 🎨 UI/UX 設計規範

### 新的面板佈局設計
```
初始狀態：顯示頁面選擇下拉選單 + 頁面簡介
[選擇頁面 ▼] (設定/預覽/統計)

頁面簡介：
📋 設定頁面：管理進度條風格、公告頻道和公告時間設定
👀 預覽頁面：預覽當前設定的進度條風格效果
📊 統計頁面：查看活躍度系統的統計資訊（月度排行榜、訊息量變化）

選擇頁面後，動態顯示對應頁面的功能按鈕：

設定頁面：
[進度條風格 ▼] [公告頻道 ▼] [公告時間 ▼]
[預覽效果] [套用設定]

預覽頁面：
[預覽進度條風格]

統計頁面：
[查看月度排行榜] [查看訊息量變化]

所有頁面底部：
[關閉面板]
```

### 錯誤提示設計
- 使用統一的錯誤嵌入格式
- 包含錯誤代碼和描述
- 提供解決建議
- 支援錯誤報告功能

### 設定頁面下拉選單設計
```
設定頁面佈局
┌─────────────────────────┐
│ 進度條風格: [Modern ▼]  │
│ 公告頻道: [#general ▼]  │
│ 公告時間: [21:00 ▼]     │
│                         │
│ [預覽效果] [套用設定]    │
└─────────────────────────┘

下拉選單選項：
- 進度條風格: Classic, Modern, Neon, Minimal, Gradient
- 公告頻道: 伺服器內所有文字頻道
- 公告時間: 00:00-23:59 (每小時選擇)
```

## 🔧 技術實現指南

### 1. 動態按鈕面板實現
```python
def _setup_dynamic_panel(self):
    """設置動態按鈕面板"""
    # 初始狀態：顯示頁面選擇下拉選單
    self.add_item(PageSelector(self))
    
    # 關閉按鈕始終顯示在底部
    self.add_item(self.create_standard_button(
        label="關閉面板", style="danger", emoji="❌",
        callback=self.close_callback
    ))

def build_initial_embed(self) -> discord.Embed:
    """構建初始狀態的嵌入訊息"""
    embed = discord.Embed(
        title="📊 活躍度系統管理面板",
        description="歡迎使用活躍度系統管理面板！請選擇要使用的功能頁面。",
        color=discord.Color.blue()
    )
    
    # 添加頁面簡介
    embed.add_field(
        name="📋 設定頁面",
        value="管理進度條風格、公告頻道和公告時間設定",
        inline=False
    )
    
    embed.add_field(
        name="👀 預覽頁面", 
        value="預覽當前設定的進度條風格效果",
        inline=False
    )
    
    embed.add_field(
        name="📊 統計頁面",
        value="查看活躍度系統的統計資訊",
        inline=False
    )
    
    embed.set_footer(text="請使用上方下拉選單選擇頁面")
    
    return embed
```

def _update_page_components(self, page_name: str):
    """根據頁面動態更新組件"""
    # 清除所有現有組件（保留頁面選擇器和關閉按鈕）
    self._clear_page_components()
    
    # 重新添加頁面選擇器
    self.add_item(PageSelector(self))
    
    # 根據頁面添加對應組件
    if page_name == "settings":
        self._add_settings_components()
    elif page_name == "preview":
        self._add_preview_components()
    elif page_name == "stats":
        self._add_stats_components()
    
    # 重新添加關閉按鈕
    self.add_item(self.create_standard_button(
        label="關閉面板", style="danger", emoji="❌",
        callback=self.close_callback
    ))

async def update_panel_display(self, interaction: discord.Interaction):
    """更新面板顯示"""
    try:
        if self.current_page is None:
            # 初始狀態：顯示頁面簡介
            embed = self.build_initial_embed()
        else:
            # 選定頁面：顯示對應頁面內容
            embed = await self.build_page_embed(self.current_page)
        
        # 更新訊息
        await interaction.message.edit(embed=embed, view=self)
        
    except Exception as e:
        await self.handle_error(interaction, e)

def _add_settings_components(self):
    """添加設定頁面組件"""
    # 第一行：下拉選單
    self.add_item(StyleSelector(self))
    self.add_item(ChannelSelector(self))
    self.add_item(TimeSelector(self))
    
    # 第二行：操作按鈕
    self.add_item(self.create_standard_button(
        label="預覽效果", style="secondary", emoji="👀",
        callback=self.preview_style_callback
    ))
    self.add_item(self.create_standard_button(
        label="套用設定", style="primary", emoji="✅",
        callback=self.apply_settings_callback
    ))

def _add_preview_components(self):
    """添加預覽頁面組件"""
    self.add_item(ProgressBarPreviewButton(self))

def _add_stats_components(self):
    """添加統計頁面組件"""
    # 統計功能按鈕
    self.add_item(self.create_standard_button(
        label="查看月度排行榜", style="primary", emoji="🏆",
        callback=self.show_monthly_ranking_callback
    ))
    self.add_item(self.create_standard_button(
        label="查看訊息量變化", style="secondary", emoji="📈",
        callback=self.show_message_trend_callback
    ))
```

### 2. 錯誤處理系統
```python
class ActivityMeterError(Exception):
    """活躍度系統錯誤基類"""
    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(f"[{error_code}] {message}")

async def handle_panel_error(self, interaction: discord.Interaction, error: Exception):
    """統一錯誤處理"""
    if isinstance(error, ActivityMeterError):
        embed = self.create_error_embed(
            f"❌ 錯誤 {error.error_code}",
            error.message
        )
    else:
        embed = self.create_error_embed(
            "❌ 未知錯誤",
            "發生未預期的錯誤，請稍後再試"
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)
```

### 3. 下拉選單系統實現
```python
class PageSelector(discord.ui.Select):
    """頁面選擇下拉選單"""
    
    def __init__(self, view):
        options = [
            discord.SelectOption(label="設定", value="settings", emoji="⚙️", description="系統設定和配置"),
            discord.SelectOption(label="預覽", value="preview", emoji="👀", description="預覽目前進度條風格效果"),
            discord.SelectOption(label="統計", value="stats", emoji="📊", description="查看統計資訊")
        ]
        super().__init__(
            placeholder="選擇頁面",
            options=options,
            row=0
        )
        self.view = view
    
    async def callback(self, interaction: discord.Interaction):
        """頁面選擇回調"""
        selected_page = self.values[0]
        
        # 更新當前頁面
        self.view.current_page = selected_page
        
        # 動態更新面板組件
        await self.view._update_page_components(selected_page)
        
        # 更新面板顯示
        await self.view.update_panel_display(interaction)
        
        # 發送確認訊息
        await interaction.response.send_message(
            f"✅ 已切換到 {selected_page} 頁面",
            ephemeral=True
        )

class StyleSelector(discord.ui.Select):
    """進度條風格選擇器"""
    
    def __init__(self, view):
        options = [
            discord.SelectOption(label="經典", value="classic", emoji="📊"),
            discord.SelectOption(label="現代", value="modern", emoji="🎨"),
            discord.SelectOption(label="霓虹", value="neon", emoji="✨"),
            discord.SelectOption(label="極簡", value="minimal", emoji="⚪"),
            discord.SelectOption(label="漸層", value="gradient", emoji="🌈")
        ]
        super().__init__(
            placeholder="選擇進度條風格",
            options=options,
            row=1
        )
        self.view = view
    
    async def callback(self, interaction: discord.Interaction):
        """風格選擇回調"""
        selected_style = self.values[0]
        await self.view.update_progress_style(interaction, selected_style)

class ChannelSelector(discord.ui.Select):
    """公告頻道選擇器"""
    
    def __init__(self, view):
        # 動態獲取伺服器頻道
        channels = [ch for ch in view.guild.text_channels if ch.permissions_for(view.guild.me).send_messages]
        options = [
            discord.SelectOption(label=ch.name, value=str(ch.id), emoji="📝")
            for ch in channels[:25]  # Discord限制最多25個選項
        ]
        super().__init__(
            placeholder="選擇公告頻道",
            options=options,
            row=1
        )
        self.view = view
    
    async def callback(self, interaction: discord.Interaction):
        """頻道選擇回調"""
        selected_channel_id = int(self.values[0])
        await self.view.update_announcement_channel(interaction, selected_channel_id)

class TimeSelector(discord.ui.Select):
    """公告時間選擇器"""
    
    def __init__(self, view):
        options = [
            discord.SelectOption(label=f"{hour:02d}:00", value=str(hour), emoji="⏰")
            for hour in range(24)
        ]
        super().__init__(
            placeholder="選擇公告時間",
            options=options,
            row=1
        )
        self.view = view
    
    async def callback(self, interaction: discord.Interaction):
        """時間選擇回調"""
        selected_hour = int(self.values[0])
        await self.view.update_announcement_time(interaction, selected_hour)

class ProgressBarPreviewButton(discord.ui.Button):
    """進度條風格預覽按鈕"""
    
    def __init__(self, view):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="預覽進度條風格",
            emoji="👀",
            row=1
        )
        self.view = view
    
    async def callback(self, interaction: discord.Interaction):
        """預覽回調"""
        # 獲取當前設定的進度條風格
        current_style = await self.view.get_current_progress_style()
        
        # 生成預覽圖片
        preview_file = await self.view.render_progress_preview(current_style)
        
        # 發送預覽
        embed = discord.Embed(
            title="👀 進度條風格預覽",
            description=f"當前風格：**{current_style}**\n\n以下是使用此風格的進度條效果：",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(
            embed=embed,
            file=preview_file,
            ephemeral=True
        )

# 統計功能實現
async def show_monthly_ranking_callback(self, interaction: discord.Interaction):
    """顯示月度排行榜"""
    try:
        # 獲取過去一個月平均活躍度最高的3個人
        top_users = await self.db.get_monthly_top_users(limit=3)
        
        embed = discord.Embed(
            title="🏆 月度活躍度排行榜",
            description="過去一個月平均活躍度最高的成員",
            color=discord.Color.gold()
        )
        
        for i, (user_id, avg_score, message_count) in enumerate(top_users, 1):
            member = interaction.guild.get_member(user_id)
            username = member.display_name if member else f"用戶{user_id}"
            
            embed.add_field(
                name=f"{i}. {username}",
                value=f"平均活躍度：{avg_score:.1f}/100\n訊息數量：{message_count}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except Exception as e:
        await self.handle_error(interaction, e)

async def show_message_trend_callback(self, interaction: discord.Interaction):
    """顯示訊息量變化趨勢"""
    try:
        # 獲取本月和上個月的訊息總量
        current_month_count = await self.db.get_monthly_message_count()
        last_month_count = await self.db.get_last_month_message_count()
        
        # 計算百分比變化
        if last_month_count > 0:
            change_percentage = ((current_month_count - last_month_count) / last_month_count) * 100
            change_emoji = "📈" if change_percentage > 0 else "📉"
            change_text = f"{change_percentage:+.1f}%"
        else:
            change_percentage = 0
            change_emoji = "📊"
            change_text = "無法比較（上個月無數據）"
        
        embed = discord.Embed(
            title="📈 訊息量變化趨勢",
            description="本月與上個月的訊息總量比較",
            color=discord.Color.green() if change_percentage >= 0 else discord.Color.red()
        )
        
        embed.add_field(
            name="本月訊息總量",
            value=f"{current_month_count:,} 則",
            inline=True
        )
        
        embed.add_field(
            name="上個月訊息總量",
            value=f"{last_month_count:,} 則",
            inline=True
        )
        
        embed.add_field(
            name="變化趨勢",
            value=f"{change_emoji} {change_text}",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except Exception as e:
        await self.handle_error(interaction, e)
```

## 📊 測試計劃

### 功能測試
- [ ] 面板初始狀態顯示頁面選擇下拉選單和頁面簡介
- [ ] 頁面切換下拉選單正常工作
- [ ] 選擇頁面後動態顯示對應功能按鈕
- [ ] 設定頁面三個下拉選單（風格、頻道、時間）正常
- [ ] 預覽頁面進度條風格預覽功能正常
- [ ] 統計頁面月度排行榜功能正常
- [ ] 統計頁面訊息量變化趨勢功能正常
- [ ] 錯誤代碼正確顯示
- [ ] 權限檢查邏輯正確
- [ ] 面板對所有授權用戶可見
- [ ] 關閉面板按鈕正常工作

### 性能測試
- [ ] 面板載入時間 < 2秒
- [ ] 風格切換響應時間 < 1秒
- [ ] 錯誤處理不影響其他功能
- [ ] 記憶體使用量穩定

### 用戶體驗測試
- [ ] 界面直觀易用
- [ ] 錯誤提示清晰明確
- [ ] 風格預覽效果良好
- [ ] 權限控制合理

## 🚀 實施時間表

### Phase 1: 動態按鈕面板重構 (2天)
- [ ] 實現初始狀態顯示頁面選擇下拉選單和頁面簡介
- [ ] 實現頁面切換時動態更新組件功能
- [ ] 移除不需要的按鈕（歷史、搜尋、趨勢、清除數據、重新整理）
- [ ] 修復權限可見性問題
- [ ] 添加關閉面板按鈕

### Phase 2: 各頁面功能實現 (2天)
- [ ] 實現設定頁面三個下拉選單（風格、頻道、時間）
- [ ] 實現設定頁面操作按鈕（預覽效果、套用設定）
- [ ] 實現預覽頁面進度條風格預覽功能
- [ ] 實現統計頁面月度排行榜功能
- [ ] 實現統計頁面訊息量變化趨勢功能
- [ ] 統一錯誤處理邏輯

### Phase 3: 錯誤系統與測試 (1天)
- [ ] 實現錯誤代碼體系
- [ ] 添加錯誤提示UI
- [ ] 全面功能測試
- [ ] 用戶體驗優化

## 📝 驗收標準

### 功能完整性
- [ ] 動態按鈕面板正常運作
- [ ] 頁面切換功能完整
- [ ] 設定頁面三個下拉選單功能完整
- [ ] 預覽頁面進度條風格預覽功能完整
- [ ] 統計頁面月度排行榜功能完整
- [ ] 統計頁面訊息量變化趨勢功能完整
- [ ] 錯誤處理覆蓋所有場景
- [ ] 權限控制準確
- [ ] 關閉面板功能正常

### 用戶體驗
- [ ] 初始界面顯示頁面簡介，幫助用戶了解功能
- [ ] 頁面切換操作順暢，動態更新組件
- [ ] 各頁面功能按鈕清晰明確
- [ ] 設定選項選擇方便
- [ ] 錯誤提示友好
- [ ] 響應速度滿意

### 技術質量
- [ ] 代碼結構清晰
- [ ] 錯誤處理完善
- [ ] 性能表現良好
- [ ] 向後相容性保持

---

**文檔版本**: v1.71  
**創建日期**: 2025-01-18  
**最後更新**: 2025-01-18  
**狀態**: 待實施