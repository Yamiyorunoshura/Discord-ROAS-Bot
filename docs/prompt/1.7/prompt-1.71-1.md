# Discord ADR Bot v1.71 - 活躍度面板優化開發提示詞

## 🎯 開發目標

基於PRD v1.71需求，實現活躍度面板的全面優化，重點解決以下核心問題：
1. **簡化重複按鈕**：減少UI複雜度，提升用戶體驗
2. **完善錯誤處理**：建立完整的錯誤代碼體系
3. **移除數據導出**：簡化功能，專注核心需求
4. **添加進度條風格選擇**：允許管理員自定義視覺效果
5. **修復權限可見性**：確保面板對所有授權用戶可見

## 📋 核心需求實現指南

### 1. 動態按鈕面板架構

#### 初始狀態設計
```python
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
        value="查看活躍度系統的統計資訊（月度排行榜、訊息量變化）",
        inline=False
    )
    
    embed.set_footer(text="請使用上方下拉選單選擇頁面")
    
    return embed
```

#### 頁面選擇器實現
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
        try:
            # 檢查權限
            if not self.view.can_view_panel(interaction.user):
                await interaction.response.send_message(
                    "❌ 您沒有權限查看此面板",
                    ephemeral=True
                )
                return
            
            selected_page = self.values[0]
            
            # 更新當前頁面
            self.view.current_page = selected_page
            
            # 動態更新面板組件
            self.view._update_page_components(selected_page)
            
            # 更新面板顯示
            await self.view.update_panel_display(interaction)
            
            # 發送確認訊息
            await interaction.response.send_message(
                f"✅ 已切換到 {selected_page} 頁面",
                ephemeral=True
            )
            
        except Exception as e:
            await self.view.handle_error(interaction, e)
```

#### 動態組件更新機制
```python
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

def _clear_page_components(self):
    """清除頁面組件（保留頁面選擇器和關閉按鈕）"""
    # 保存頁面選擇器和關閉按鈕
    page_selector = None
    close_button = None
    
    for child in self.children:
        if isinstance(child, PageSelector):
            page_selector = child
        elif hasattr(child, 'label') and child.label == "關閉面板":
            close_button = child
    
    # 清除所有組件
    self.clear_items()
    
    # 重新添加頁面選擇器和關閉按鈕
    if page_selector:
        self.add_item(page_selector)
    if close_button:
        self.add_item(close_button)

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

### 2. 進度條風格選擇系統

#### 風格枚舉定義
```python
from enum import Enum

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
    "neon": {
        "bg_color": (20, 20, 20, 255),
        "border_color": (0, 255, 255),
        "text_color": (255, 255, 255),
        "shadow": True,
        "glow": True,
        "glow_color": (0, 255, 255)
    },
    "minimal": {
        "bg_color": (255, 255, 255, 255),
        "border_color": (200, 200, 200),
        "text_color": (0, 0, 0),
        "shadow": False,
        "glow": False
    },
    "gradient": {
        "bg_color": (32, 34, 37, 255),
        "border_color": (79, 84, 92),
        "text_color": (255, 255, 255),
        "shadow": True,
        "glow": False,
        "gradient": True,
        "gradient_colors": [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    }
}
```

#### 風格選擇器實現
```python
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
        try:
            # 檢查權限
            if not self.view.can_edit_settings(interaction.user):
                await interaction.response.send_message(
                    "❌ 您沒有權限編輯設定",
                    ephemeral=True
                )
                return
            
            selected_style = self.values[0]
            await self.view.update_progress_style(interaction, selected_style)
            
        except Exception as e:
            await self.view.handle_error(interaction, e)
```

### 3. 設定頁面下拉選單系統

#### 公告頻道選擇器
```python
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
        try:
            # 檢查權限
            if not self.view.can_edit_settings(interaction.user):
                await interaction.response.send_message(
                    "❌ 您沒有權限編輯設定",
                    ephemeral=True
                )
                return
            
            selected_channel_id = int(self.values[0])
            await self.view.update_announcement_channel(interaction, selected_channel_id)
            
        except Exception as e:
            await self.view.handle_error(interaction, e)
```

#### 公告時間選擇器
```python
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
        try:
            # 檢查權限
            if not self.view.can_edit_settings(interaction.user):
                await interaction.response.send_message(
                    "❌ 您沒有權限編輯設定",
                    ephemeral=True
                )
                return
            
            selected_hour = int(self.values[0])
            await self.view.update_announcement_time(interaction, selected_hour)
            
        except Exception as e:
            await self.view.handle_error(interaction, e)
```

### 4. 統計頁面功能實現

#### 月度排行榜功能
```python
async def show_monthly_ranking_callback(self, interaction: discord.Interaction):
    """顯示月度排行榜"""
    try:
        # 檢查權限
        if not self.can_view_panel(interaction.user):
            await interaction.response.send_message(
                "❌ 您沒有權限查看此面板",
                ephemeral=True
            )
            return
        
        # 獲取過去一個月平均活躍度最高的3個人
        top_users = await self.db.get_monthly_top_users(limit=3)
        
        embed = discord.Embed(
            title="🏆 月度活躍度排行榜",
            description="過去一個月平均活躍度最高的成員",
            color=discord.Color.gold()
        )
        
        if not top_users:
            embed.add_field(
                name="📊 無數據",
                value="過去一個月沒有活躍度數據",
                inline=False
            )
        else:
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
```

#### 訊息量變化趨勢功能
```python
async def show_message_trend_callback(self, interaction: discord.Interaction):
    """顯示訊息量變化趨勢"""
    try:
        # 檢查權限
        if not self.can_view_panel(interaction.user):
            await interaction.response.send_message(
                "❌ 您沒有權限查看此面板",
                ephemeral=True
            )
            return
        
        # 獲取本月和上個月的訊息總量
        current_month_count = await self.db.get_monthly_message_count()
        last_month_count = await self.db.get_last_month_message_count()
        
        # 計算百分比變化
        if last_month_count > 0:
            change_percentage = ((current_month_count - last_month_count) / last_month_count) * 100
            change_emoji = "📈" if change_percentage > 0 else "📉"
            change_text = f"{change_percentage:+.1f}%"
            color = discord.Color.green() if change_percentage >= 0 else discord.Color.red()
        else:
            change_percentage = 0
            change_emoji = "📊"
            change_text = "無法比較（上個月無數據）"
            color = discord.Color.blue()
        
        embed = discord.Embed(
            title="📈 訊息量變化趨勢",
            description="本月與上個月的訊息總量比較",
            color=color
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

### 5. 錯誤處理系統

#### 錯誤代碼體系
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

class ActivityMeterError(Exception):
    """活躍度系統錯誤基類"""
    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(f"[{error_code}] {message}")

async def handle_error(self, interaction: discord.Interaction, error: Exception):
    """統一錯誤處理"""
    try:
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
    except Exception as e:
        # 如果錯誤處理本身失敗，發送簡單錯誤訊息
        await interaction.response.send_message(
            "❌ 發生錯誤，請稍後再試",
            ephemeral=True
        )

def create_error_embed(self, title: str, description: str) -> discord.Embed:
    """創建錯誤嵌入訊息"""
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.red()
    )
    embed.set_footer(text="如有問題，請聯繫管理員")
    return embed
```

### 6. 權限可見性修復

#### 權限檢查邏輯
```python
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

async def check_permissions(self, interaction: discord.Interaction) -> bool:
    """檢查用戶權限"""
    if not self.can_view_panel(interaction.user):
        await interaction.response.send_message(
            "❌ 您沒有權限查看此面板",
            ephemeral=True
        )
        return False
    return True
```

### 7. 預覽功能實現

#### 進度條風格預覽
```python
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
        try:
            # 檢查權限
            if not self.view.can_view_panel(interaction.user):
                await interaction.response.send_message(
                    "❌ 您沒有權限查看此面板",
                    ephemeral=True
                )
                return
            
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
            
        except Exception as e:
            await self.view.handle_error(interaction, e)

async def render_progress_preview(self, style: str) -> discord.File:
    """渲染進度條預覽圖片"""
    try:
        # 獲取風格配置
        style_config = STYLE_CONFIGS.get(style, STYLE_CONFIGS["classic"])
        
        # 創建預覽圖片
        image = await self.create_progress_bar_image(
            progress=75,  # 示例進度
            style_config=style_config,
            width=400,
            height=60
        )
        
        # 保存為臨時文件
        temp_path = f"temp_preview_{style}.png"
        image.save(temp_path)
        
        return discord.File(temp_path, filename=f"preview_{style}.png")
        
    except Exception as e:
        raise ActivityMeterError("E301", f"進度條渲染失敗：{str(e)}")
```

## 🔧 數據庫操作實現

### 月度排行榜查詢
```python
async def get_monthly_top_users(self, limit: int = 3) -> List[Tuple[int, float, int]]:
    """獲取過去一個月平均活躍度最高的用戶"""
    try:
        # 計算過去一個月的時間範圍
        now = datetime.now()
        month_ago = now - timedelta(days=30)
        
        query = """
        SELECT user_id, AVG(score) as avg_score, COUNT(*) as message_count
        FROM activity_scores
        WHERE timestamp >= %s
        GROUP BY user_id
        HAVING COUNT(*) >= 1
        ORDER BY avg_score DESC
        LIMIT %s
        """
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, (month_ago, limit))
                results = await cursor.fetchall()
                
        return [(user_id, avg_score, message_count) for user_id, avg_score, message_count in results]
        
    except Exception as e:
        raise ActivityMeterError("E101", f"數據庫查詢失敗：{str(e)}")
```

### 訊息量統計查詢
```python
async def get_monthly_message_count(self) -> int:
    """獲取本月訊息總量"""
    try:
        now = datetime.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        query = """
        SELECT COUNT(*) as message_count
        FROM activity_scores
        WHERE timestamp >= %s
        """
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, (start_of_month,))
                result = await cursor.fetchone()
                
        return result[0] if result else 0
        
    except Exception as e:
        raise ActivityMeterError("E101", f"數據庫查詢失敗：{str(e)}")

async def get_last_month_message_count(self) -> int:
    """獲取上個月訊息總量"""
    try:
        now = datetime.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_of_last_month = (start_of_month - timedelta(days=1)).replace(day=1)
        
        query = """
        SELECT COUNT(*) as message_count
        FROM activity_scores
        WHERE timestamp >= %s AND timestamp < %s
        """
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, (start_of_last_month, start_of_month))
                result = await cursor.fetchone()
                
        return result[0] if result else 0
        
    except Exception as e:
        raise ActivityMeterError("E101", f"數據庫查詢失敗：{str(e)}")
```

### 設定保存和載入
```python
async def save_settings(self, guild_id: int, settings: dict) -> None:
    """保存設定到數據庫"""
    try:
        query = """
        INSERT INTO activity_meter_settings (guild_id, progress_style, announcement_channel, announcement_time)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
        progress_style = VALUES(progress_style),
        announcement_channel = VALUES(announcement_channel),
        announcement_time = VALUES(announcement_time)
        """
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, (
                    guild_id,
                    settings.get('progress_style', 'classic'),
                    settings.get('announcement_channel', None),
                    settings.get('announcement_time', 21)
                ))
                await conn.commit()
                
    except Exception as e:
        raise ActivityMeterError("E402", f"設定保存失敗：{str(e)}")

async def load_settings(self, guild_id: int) -> dict:
    """從數據庫載入設定"""
    try:
        query = """
        SELECT progress_style, announcement_channel, announcement_time
        FROM activity_meter_settings
        WHERE guild_id = %s
        """
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, (guild_id,))
                result = await cursor.fetchone()
                
        if result:
            return {
                'progress_style': result[0],
                'announcement_channel': result[1],
                'announcement_time': result[2]
            }
        else:
            return {
                'progress_style': 'classic',
                'announcement_channel': None,
                'announcement_time': 21
            }
                
    except Exception as e:
        raise ActivityMeterError("E401", f"配置載入失敗：{str(e)}")
```

## 📊 測試驗證要點

### 功能測試檢查清單
- [ ] 面板初始狀態正確顯示頁面選擇下拉選單和頁面簡介
- [ ] 頁面切換下拉選單正常工作，動態更新組件
- [ ] 設定頁面三個下拉選單（風格、頻道、時間）功能完整
- [ ] 預覽頁面進度條風格預覽功能正常
- [ ] 統計頁面月度排行榜顯示正確
- [ ] 統計頁面訊息量變化趨勢計算準確
- [ ] 錯誤代碼正確顯示和處理
- [ ] 權限檢查邏輯正確，面板對所有授權用戶可見
- [ ] 關閉面板按鈕正常工作

### 性能測試要求
- [ ] 面板載入時間 < 2秒
- [ ] 風格切換響應時間 < 1秒
- [ ] 錯誤處理不影響其他功能
- [ ] 記憶體使用量穩定

### 用戶體驗驗證
- [ ] 界面直觀易用，功能分類明確
- [ ] 錯誤提示清晰明確，包含錯誤代碼
- [ ] 風格預覽效果良好，視覺效果滿意
- [ ] 權限控制合理，管理員可正常使用

## 🚀 實施優先級

### Phase 1: 核心架構重構 (最高優先級)
1. 實現動態按鈕面板架構
2. 實現頁面選擇器和初始狀態
3. 修復權限可見性問題
4. 移除不需要的按鈕和功能

### Phase 2: 功能模組實現 (高優先級)
1. 實現進度條風格選擇系統
2. 實現設定頁面下拉選單
3. 實現預覽功能
4. 實現統計頁面功能

### Phase 3: 錯誤處理與優化 (中優先級)
1. 實現錯誤代碼體系
2. 完善錯誤處理邏輯
3. 性能優化
4. 用戶體驗優化

## 📝 開發注意事項

### 代碼質量要求
1. **模組化設計**：每個功能模組獨立實現
2. **錯誤處理**：所有操作都必須有適當的錯誤處理
3. **權限檢查**：每個功能都要進行權限驗證
4. **性能優化**：避免不必要的數據庫查詢和計算
5. **用戶體驗**：提供清晰的用戶反饋和錯誤提示

### 兼容性要求
1. **向後相容**：保持與現有系統的兼容性
2. **數據庫兼容**：確保數據庫操作的正確性
3. **Discord API兼容**：遵循Discord API限制和最佳實踐

### 安全性要求
1. **權限驗證**：嚴格檢查用戶權限
2. **輸入驗證**：驗證所有用戶輸入
3. **錯誤信息**：不暴露敏感信息
4. **資源管理**：正確管理文件和數據庫連接

### 關鍵實現要點
1. **組件更新邏輯**：確保頁面切換時組件正確更新
2. **權限檢查**：每個回調函數都要進行權限檢查
3. **錯誤處理**：使用統一的錯誤處理機制
4. **數據庫操作**：使用連接池，確保連接正確釋放
5. **UI組件排列**：正確設置row參數，避免組件重疊

---

**提示詞版本**: v1.71-1  
**創建日期**: 2025-01-18  
**適用於**: Discord ADR Bot 活躍度面板優化開發  
**狀態**: 待實施
