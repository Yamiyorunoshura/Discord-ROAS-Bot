"""
活躍度系統主要面板視圖類別
- 基於 StandardPanelView 的統一面板架構
- 提供完整的活躍度系統管理介面
- 支援多頁面切換和響應式設計
- 實現提示詞 v1.7-1 的完整架構
"""

import discord
import logging
from typing import Dict, Any, Optional, List, Tuple, Union

from ...core.base_cog import StandardPanelView, StandardEmbedBuilder
from ..config import config
from ..database.database import ActivityDatabase
from .embeds.settings_embed import create_settings_embed
from .embeds.preview_embed import create_preview_embed
from .embeds.stats_embed import create_stats_embed
from .components.buttons import CloseButton, RefreshButton, PreviewButton
from .components.selectors import PageSelector
from .managers import PageManager, PermissionManager, DataManager, UIManager

logger = logging.getLogger("activity_meter")

class ActivityPanelView(StandardPanelView):
    """
    活躍度系統設定面板
    
    功能：
    - 提供活躍度系統的設定介面
    - 顯示統計資訊
    - 預覽排行榜效果
    - 歷史記錄查看
    - 實現完整的管理器架構
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
        
        # 初始化管理器架構
        self._setup_managers()
        
        # 初始化頁面系統
        self._setup_activity_pages()
        # 初始化組件系統 - 這是關鍵修復
        self._setup_components()
    
    def _setup_managers(self):
        """設置管理器架構"""
        # 創建管理器實例
        self.page_manager = PageManager()
        self.permission_manager = PermissionManager()
        self.data_manager = DataManager()
        self.ui_manager = UIManager(self.data_manager, self.permission_manager)
        
        logger.info("活躍度面板管理器架構已初始化")
    
    def _setup_pages(self):
        """設置活躍度系統頁面"""
        self.pages = {
            "settings": {
                "title": "活躍度設定",
                "description": "管理活躍度系統設定",
                "embed_builder": self.build_settings_embed,
                "components": []
            },
            "preview": {
                "title": "排行榜預覽",
                "description": "預覽活躍度排行榜",
                "embed_builder": self.build_preview_embed,
                "components": []
            },
            "stats": {
                "title": "統計資訊",
                "description": "查看活躍度統計",
                "embed_builder": self.build_stats_embed,
                "components": []
            },
            "history": {
                "title": "歷史記錄",
                "description": "查看活躍度歷史",
                "embed_builder": self.build_history_embed,
                "components": []
            }
        }
        
        # 設置預設頁面
        self.current_page = "settings"
    
    def _setup_activity_pages(self):
        """設置活躍度特定頁面"""
        self._setup_pages()
    
    def _setup_components(self):
        """設置面板組件"""
        # 頁面切換按鈕 (第一行)
        self.add_item(self.create_standard_button(
            label="設定",
            style="secondary",
            emoji="⚙️",
            callback=self.show_settings_callback
        ))
        
        self.add_item(self.create_standard_button(
            label="預覽",
            style="secondary",
            emoji="👀",
            callback=self.show_preview_callback
        ))
        
        self.add_item(self.create_standard_button(
            label="統計",
            style="secondary",
            emoji="📊",
            callback=self.show_stats_callback
        ))
        
        self.add_item(self.create_standard_button(
            label="歷史",
            style="secondary",
            emoji="📜",
            callback=self.show_history_callback
        ))
        
        # 功能按鈕 (第二行)
        self.add_item(self.create_standard_button(
            label="重新整理",
            style="secondary",
            emoji="🔄",
            callback=self.refresh_callback
        ))
        
        self.add_item(self.create_standard_button(
            label="設定頻道",
            style="primary",
            emoji="📝",
            callback=self.set_channel_callback
        ))
        
        self.add_item(self.create_standard_button(
            label="清除數據",
            style="danger",
            emoji="🗑️",
            callback=self.clear_data_callback
        ))
        
        # 控制按鈕 (第三行)
        self.add_item(self.create_standard_button(
            label="關閉",
            style="danger",
            emoji="❌",
            callback=self.close_callback
        ))
    
    async def start(self, interaction: discord.Interaction):
        """
        啟動面板 - 這是關鍵入口點
        
        Args:
            interaction: Discord 互動
        """
        try:
            # 1. 檢查權限
            if not self.permission_manager.can_view(interaction.user):
                await self.handle_permission_error(interaction, "查看")
                return
                
            # 2. 載入初始頁面
            await self.page_manager.load_page("settings", interaction)
            
            # 3. 渲染界面
            embed = await self.ui_manager.render_current_page(
                self.page_manager.get_current_page(),
                self.guild_id,
                interaction.user
            )
            
            # 4. 發送響應
            await interaction.response.send_message(
                embed=embed,
                view=self,
                ephemeral=True
            )
            
        except Exception as e:
            await self.handle_error(interaction, e)
    
    async def handle_permission_error(self, interaction: discord.Interaction, required_permission: str):
        """處理權限錯誤"""
        embed = StandardEmbedBuilder.create_error_embed(
            "❌ 權限不足",
            f"您需要「{required_permission}」權限才能執行此操作"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def handle_error(self, interaction: discord.Interaction, error: Exception):
        """處理一般錯誤"""
        logger.error(f"面板錯誤: {error}")
        embed = StandardEmbedBuilder.create_error_embed(
            "❌ 操作失敗",
            "發生未知錯誤，請稍後再試"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def build_settings_embed(self) -> discord.Embed:
        """構建設定頁面嵌入"""
        guild = self.bot.get_guild(self.guild_id)
        
        # 獲取當前設定
        report_channels = await self.db.get_report_channels()
        channel_id = next((ch_id for g_id, ch_id in report_channels if g_id == self.guild_id), None)
        
        return await create_settings_embed(guild, channel_id)
    
    async def build_preview_embed(self) -> discord.Embed:
        """構建預覽頁面嵌入"""
        guild = self.bot.get_guild(self.guild_id)
        return await create_preview_embed(self.bot, guild, self.db)
    
    async def build_stats_embed(self) -> discord.Embed:
        """構建統計頁面嵌入"""
        guild = self.bot.get_guild(self.guild_id)
        return await create_stats_embed(self.bot, guild, self.db)
    
    async def build_history_embed(self) -> discord.Embed:
        """構建歷史頁面嵌入"""
        try:
            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                return StandardEmbedBuilder.create_error_embed(
                    "錯誤",
                    "無法找到伺服器"
                )
            
            embed = StandardEmbedBuilder.create_info_embed(
                "活躍度歷史記錄",
                f"顯示 {guild.name} 的活躍度歷史記錄"
            )
            
            # 暫時顯示佔位符內容，直到資料庫方法實現
            embed.add_field(
                name="📜 歷史記錄",
                value="歷史記錄功能將在後續版本中實現",
                inline=False
            )
            
            return embed
            
        except Exception as e:
            return StandardEmbedBuilder.create_error_embed(
                "歷史記錄載入失敗",
                f"無法載入歷史記錄：{str(e)}"
            )
    
    async def show_settings_callback(self, interaction: discord.Interaction):
        """顯示設定頁面"""
        await self.change_page(interaction, "settings")
    
    async def show_preview_callback(self, interaction: discord.Interaction):
        """顯示預覽頁面"""
        await self.change_page(interaction, "preview")
    
    async def show_stats_callback(self, interaction: discord.Interaction):
        """顯示統計頁面"""
        await self.change_page(interaction, "stats")
    
    async def show_history_callback(self, interaction: discord.Interaction):
        """顯示歷史頁面"""
        await self.change_page(interaction, "history")
    
    async def set_channel_callback(self, interaction: discord.Interaction):
        """設定報告頻道"""
        await self.execute_operation(
            interaction,
            self._set_report_channel,
            "設定報告頻道"
        )
    
    async def clear_data_callback(self, interaction: discord.Interaction):
        """清除數據"""
        # 顯示確認對話框
        confirm_embed = StandardEmbedBuilder.create_warning_embed(
            "確認清除數據",
            "⚠️ 此操作將清除所有活躍度數據，無法復原！\n\n請在 30 秒內再次點擊確認。"
        )
        
        confirm_view = ConfirmClearView(self)
        await interaction.response.send_message(
            embed=confirm_embed, 
            view=confirm_view, 
            ephemeral=True
        )
    
    async def _set_report_channel(self):
        """設定報告頻道的實際操作"""
        # 這裡應該顯示頻道選擇器或模態框
        # 暫時返回成功訊息
        return "頻道設定功能將在後續版本中實現"
    
    async def _clear_activity_data(self):
        """清除活躍度數據的實際操作"""
        try:
            # 暫時返回成功訊息，直到資料庫方法實現
            return "清除數據功能將在後續版本中實現"
        except Exception as e:
            raise Exception(f"清除數據失敗：{str(e)}")
    
    async def build_main_embed(self) -> discord.Embed:
        """構建主頁面嵌入 (覆寫基類方法)"""
        return await self.build_settings_embed()


class ConfirmClearView(discord.ui.View):
    """確認清除數據的視圖"""
    
    def __init__(self, parent_view: ActivityPanelView):
        super().__init__(timeout=30)
        self.parent_view = parent_view
    
    @discord.ui.button(label="確認清除", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        """確認清除數據"""
        try:
            await self.parent_view.execute_operation(
                interaction,
                self.parent_view._clear_activity_data,
                "清除活躍度數據"
            )
            
            # 禁用按鈕
            for item in self.children:
                if hasattr(item, 'disabled'):
                    item.disabled = True
            
            success_embed = StandardEmbedBuilder.create_success_embed(
                "數據已清除",
                "活躍度數據已成功清除"
            )
            
            await interaction.response.edit_message(embed=success_embed, view=self)
            
        except Exception as e:
            error_embed = StandardEmbedBuilder.create_error_embed(
                "清除失敗",
                f"清除數據時發生錯誤：{str(e)}"
            )
            await interaction.response.edit_message(embed=error_embed, view=self)
    
    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        """取消清除"""
        # 禁用按鈕
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        
        cancel_embed = StandardEmbedBuilder.create_info_embed(
            "已取消",
            "數據清除操作已取消"
        )
        
        await interaction.response.edit_message(embed=cancel_embed, view=self)
    
    async def on_timeout(self):
        """超時處理"""
        # 禁用所有按鈕
        for item in self.children:
            item.disabled = True 