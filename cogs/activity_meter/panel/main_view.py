"""
活躍度系統主要面板視圖類別
- 基於 StandardPanelView 的統一面板架構
- 提供完整的活躍度系統管理介面
- 支援多頁面切換和響應式設計
- 實現提示詞 v1.71 的完整架構
"""

import discord
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime, timedelta

from ...core.base_cog import StandardPanelView, StandardEmbedBuilder
from ..config import config
from ..database.database import ActivityDatabase
from .embeds.settings_embed import create_settings_embed
from .embeds.preview_embed import create_preview_embed
from .embeds.stats_embed import create_stats_embed
from .components.buttons import CloseButton, RefreshButton, PreviewButton
from .components.selectors import PageSelector, StyleSelector, ChannelSelector, TimeSelector, STYLE_CONFIGS
from .managers import PageManager, PermissionManager, DataManager, UIManager

logger = logging.getLogger("activity_meter")

# 錯誤代碼體系
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

class ActivityPanelView(StandardPanelView):
    """
    活躍度系統設定面板 - v1.71 優化版本
    
    功能：
    - 動態按鈕面板架構
    - 頁面選擇器系統
    - 進度條風格選擇
    - 統計資訊顯示
    - 完整的錯誤處理體系
    """
    
    def __init__(self, bot: discord.Client, guild_id: int, author_id: int):
        """
        初始化面板
        
        Args:
            bot: Discord 機器人實例
            guild_id: 伺服器 ID
            author_id: 作者 ID（用於權限檢查）
        """
        super().__init__(
            timeout=300,
            required_permissions=["manage_guild"],
            admin_only=False,
            moderator_only=False,
            author_id=author_id,
            guild_id=guild_id
        )
        
        self.bot = bot
        self.guild_id = guild_id
        self.author_id = author_id
        self.db = ActivityDatabase()
        
        # 當前頁面狀態
        self.current_page = "settings"
        
        # 快取區
        self._cache = {}
        self._cache_expire = 10  # 秒
        self._cache_time = {}
        
        # 初始化管理器架構
        self._setup_managers()
        
        # 初始化動態組件系統
        self._setup_dynamic_components()
    
    def _setup_managers(self):
        """設置管理器架構"""
        # 創建管理器實例
        self.page_manager = PageManager()
        self.permission_manager = PermissionManager()
        self.data_manager = DataManager()
        self.ui_manager = UIManager(self.data_manager, self.permission_manager)
        
        logger.info("活躍度面板管理器架構已初始化")
    
    def _setup_dynamic_components(self):
        """設置動態組件系統"""
        # 根據當前頁面添加對應組件
        self._update_page_components(self.current_page)
    
    def _update_page_components(self, page_name: str):
        """根據頁面動態更新組件"""
        # 清除所有組件
        self.clear_items()
        
        # 添加頁面選擇器（第一行）
        self.add_item(PageSelector(self))
        
        # 根據頁面添加對應組件
        if page_name == "settings":
            self._add_settings_components()
        elif page_name == "preview":
            self._add_preview_components()
        elif page_name == "stats":
            self._add_stats_components()
        
        # 添加關閉按鈕
        close_button = self.create_standard_button(
            label="關閉面板", style="danger", emoji="❌"
        )
        close_button.callback = self.close_callback
        self.add_item(close_button)
    
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
        # 第一行：風格選擇器
        self.add_item(StyleSelector(self))
        
        # 第二行：操作按鈕
        preview_button = self.create_standard_button(
            label="預覽效果", style="secondary", emoji="👀"
        )
        preview_button.callback = self.preview_style_callback
        self.add_item(preview_button)
        
        apply_button = self.create_standard_button(
            label="套用設定", style="primary", emoji="✅"
        )
        apply_button.callback = self.apply_settings_callback
        self.add_item(apply_button)
    
    def _add_preview_components(self):
        """添加預覽頁面組件"""
        self.add_item(ProgressBarPreviewButton(self))
    
    def _add_stats_components(self):
        """添加統計頁面組件"""
        # 統計功能按鈕
        ranking_button = self.create_standard_button(
            label="查看月度排行榜", style="primary", emoji="🏆"
        )
        ranking_button.callback = self.show_monthly_ranking_callback
        self.add_item(ranking_button)
        
        trend_button = self.create_standard_button(
            label="查看訊息量變化", style="secondary", emoji="📈"
        )
        trend_button.callback = self.show_message_trend_callback
        self.add_item(trend_button)
    
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
    
    async def start(self, interaction: discord.Interaction):
        """
        啟動面板 - 這是關鍵入口點
        
        Args:
            interaction: Discord 互動
        """
        try:
            # 1. 檢查權限
            if not await self.check_permissions(interaction):
                return
                
            # 2. 構建初始嵌入訊息
            embed = self.build_initial_embed()
            
            # 3. 發送響應
            await interaction.response.send_message(
                embed=embed,
                view=self,
                ephemeral=False
            )
            
        except Exception as e:
            await self.handle_error(interaction, e)
    
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
    
    async def update_panel_display(self, interaction: discord.Interaction):
        """更新面板顯示"""
        try:
            # 根據當前頁面構建對應的嵌入訊息
            if self.current_page == "settings":
                embed = await self.build_settings_embed()
            elif self.current_page == "preview":
                embed = await self.build_preview_embed()
            elif self.current_page == "stats":
                embed = await self.build_stats_embed()
            else:
                embed = self.build_initial_embed()
            
            # 更新訊息
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            # 如果 edit_message 失敗，嘗試發送新訊息
            try:
                await interaction.response.edit_message(embed=embed, view=self)
            except Exception:
                error_embed = self.create_error_embed(
                    "❌ 面板更新失敗",
                    "無法更新面板顯示，請重新開啟面板"
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    async def handle_error(self, interaction: discord.Interaction, error: Exception):
        """統一錯誤處理"""
        try:
            if isinstance(error, ActivityMeterError):
                embed = self.create_error_embed(
                    f"❌ 錯誤 {error.error_code}",
                    error.message
                )
            else:
                # 捕捉常見權限/驗證錯誤
                if isinstance(error, PermissionError):
                    embed = self.create_error_embed(
                        "❌ 錯誤 E001",
                        "權限不足：需要管理伺服器權限"
                    )
                elif isinstance(error, ValueError):
                    embed = self.create_error_embed(
                        "❌ 錯誤 E999",
                        f"輸入格式錯誤：{str(error)}"
                    )
                else:
                    embed = self.create_error_embed(
                        "❌ 未知錯誤",
                        "發生未預期的錯誤，請稍後再試"
                    )
            # 嘗試用edit_message，若失敗則fallback send_message
            try:
                await interaction.response.edit_message(embed=embed, view=self)
            except Exception:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            # 如果錯誤處理本身失敗，發送簡單錯誤訊息
            try:
                await interaction.response.send_message(
                    "❌ 發生錯誤，請稍後再試",
                    ephemeral=True
                )
            except Exception:
                pass
    
    def create_error_embed(self, title: str, description: str) -> discord.Embed:
        """創建錯誤嵌入訊息"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.red()
        )
        embed.set_footer(text="如有問題，請聯繫管理員")
        return embed
    
    # 頁面構建方法
    async def build_settings_embed(self) -> discord.Embed:
        """構建設定頁面嵌入"""
        guild = self.bot.get_guild(self.guild_id)
        cache_key = 'settings_embed'
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        settings = await self.db.load_settings(self.guild_id)
        progress_style = settings.get('progress_style', 'classic')
        announcement_channel = settings.get('announcement_channel')
        announcement_time = settings.get('announcement_time', 21)
        embed = await create_settings_embed(
            guild, 
            announcement_channel,
            progress_style,
            announcement_time
        )
        self._set_cache(cache_key, embed)
        return embed
    
    async def build_preview_embed(self) -> discord.Embed:
        """構建預覽頁面嵌入"""
        guild = self.bot.get_guild(self.guild_id)
        cache_key = 'preview_embed'
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        embed = await create_preview_embed(self.bot, guild, self.db)
        self._set_cache(cache_key, embed)
        return embed
    
    async def build_stats_embed(self) -> discord.Embed:
        """構建統計頁面嵌入"""
        guild = self.bot.get_guild(self.guild_id)
        cache_key = 'stats_embed'
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        embed = await create_stats_embed(self.bot, guild, self.db)
        self._set_cache(cache_key, embed)
        return embed
    
    # 回調方法
    async def preview_style_callback(self, interaction: discord.Interaction):
        """預覽風格回調"""
        try:
            if not self.can_edit_settings(interaction.user):
                await interaction.response.send_message(
                    "❌ 您沒有權限編輯設定",
                    ephemeral=True
                )
                return
            
            # 獲取當前設定的進度條風格
            current_style = await self.get_current_progress_style()
            
            # 生成預覽圖片
            preview_file = await self.render_progress_preview(current_style)
            
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
            await self.handle_error(interaction, e)
    
    async def apply_settings_callback(self, interaction: discord.Interaction):
        """套用設定回調"""
        try:
            if not self.can_edit_settings(interaction.user):
                await interaction.response.send_message(
                    "❌ 您沒有權限編輯設定",
                    ephemeral=True
                )
                return
            
            # 保存設定到數據庫
            await self.save_current_settings()
            
            # 設定變更後清除快取
            self._cache.clear()
            
            await interaction.response.send_message(
                "✅ 設定已成功套用",
                ephemeral=True
            )
            
        except Exception as e:
            await self.handle_error(interaction, e)
    
    async def show_monthly_ranking_callback(self, interaction: discord.Interaction):
        """顯示月度排行榜"""
        try:
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
    
    async def show_message_trend_callback(self, interaction: discord.Interaction):
        """顯示訊息量變化趨勢"""
        try:
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
    
    # 輔助方法
    async def get_current_progress_style(self) -> str:
        """獲取當前進度條風格"""
        # 從數據庫載入設定
        return await self.db.get_progress_style(self.guild_id)
    
    async def render_progress_preview(self, style: str) -> discord.File:
        """渲染進度條預覽圖片"""
        try:
            import io
            from PIL import Image, ImageDraw, ImageFont
            
            # 獲取風格配置
            style_config = STYLE_CONFIGS.get(style, STYLE_CONFIGS["classic"])
            
            # 創建圖片
            width, height = 400, 60
            image = Image.new('RGBA', (width, height), style_config["bg_color"])
            draw = ImageDraw.Draw(image)
            
            # 繪製邊框
            border_color = style_config["border_color"]
            draw.rectangle([0, 0, width-1, height-1], outline=border_color, width=2)
            
            # 繪製進度條
            progress = 75  # 示例進度
            progress_width = int((width - 20) * progress / 100)
            progress_color = (0, 255, 0) if style == "neon" else (255, 255, 255)
            
            # 進度條背景
            draw.rectangle([10, 15, width-10, height-15], fill=(50, 50, 50))
            
            # 進度條
            draw.rectangle([10, 15, 10 + progress_width, height-15], fill=progress_color)
            
            # 添加文字
            try:
                # 嘗試使用系統字體
                font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 16)
            except:
                # 如果沒有Arial，使用預設字體
                font = ImageFont.load_default()
            
            text = f"{progress}%"
            text_color = style_config["text_color"]
            
            # 計算文字位置
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = (width - text_width) // 2
            text_y = (height - text_height) // 2
            
            # 繪製文字
            draw.text((text_x, text_y), text, fill=text_color, font=font)
            
            # 保存到內存
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            buffer.seek(0)
            
            return discord.File(buffer, filename=f"preview_{style}.png")
            
        except Exception as e:
            raise ActivityMeterError("E301", f"進度條渲染失敗：{str(e)}")
    
    async def save_current_settings(self):
        """保存當前設定"""
        try:
            # 獲取當前設定
            settings = await self.db.load_settings(self.guild_id)
            
            # 保存所有設定到數據庫
            await self.db.save_all_settings(
                self.guild_id,
                settings.get('progress_style', 'classic'),
                settings.get('announcement_channel', None),
                settings.get('announcement_time', 21)
            )
            
        except Exception as e:
            raise ActivityMeterError("E402", f"設定保存失敗：{str(e)}")
    
    # 設定更新方法
    async def update_progress_style(self, interaction: discord.Interaction, style: str):
        """更新進度條風格"""
        try:
            # 檢查風格是否有效
            if style not in STYLE_CONFIGS:
                await interaction.response.send_message(
                    "❌ 無效的進度條風格",
                    ephemeral=True
                )
                return
            
            # 保存到數據庫
            await self.db.save_progress_style(self.guild_id, style)
            
            await interaction.response.send_message(
                f"✅ 進度條風格已更新為：{style}",
                ephemeral=True
            )
            
        except Exception as e:
            await self.handle_error(interaction, e)
    
    async def update_announcement_channel(self, interaction: discord.Interaction, channel_id: int):
        """更新公告頻道"""
        try:
            # 檢查頻道是否存在
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message(
                    "❌ 找不到指定的頻道",
                    ephemeral=True
                )
                return
            
            # 檢查機器人權限
            if not channel.permissions_for(interaction.guild.me).send_messages:
                await interaction.response.send_message(
                    "❌ 機器人沒有在該頻道發送訊息的權限",
                    ephemeral=True
                )
                return
            
            # 保存到數據庫
            await self.db.set_report_channel(self.guild_id, channel_id)
            
            await interaction.response.send_message(
                f"✅ 公告頻道已設定為：{channel.name}",
                ephemeral=True
            )
            
        except Exception as e:
            await self.handle_error(interaction, e)
    
    async def update_announcement_time(self, interaction: discord.Interaction, hour: int):
        """更新公告時間"""
        try:
            # 檢查時間是否有效
            if not 0 <= hour <= 23:
                await interaction.response.send_message(
                    "❌ 無效的時間格式",
                    ephemeral=True
                )
                return
            
            # 保存到數據庫
            await self.db.save_announcement_time(self.guild_id, hour)
            
            await interaction.response.send_message(
                f"✅ 公告時間已設定為：{hour:02d}:00",
                ephemeral=True
            )
            
        except Exception as e:
            await self.handle_error(interaction, e)


class ProgressBarPreviewButton(discord.ui.Button):
    """進度條風格預覽按鈕"""
    
    def __init__(self, view):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="預覽進度條風格",
            emoji="👀",
            row=1
        )
        # 在 Discord.py 2.5.2 中，不能直接設置屬性
        # 使用 __dict__ 來設置 view 屬性
        self.__dict__['view'] = view
    
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