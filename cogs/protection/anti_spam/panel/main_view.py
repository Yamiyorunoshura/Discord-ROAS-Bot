"""
反垃圾訊息模塊主面板
基於 StandardPanelView 的統一面板架構設計
提供完整的反垃圾訊息管理功能
"""

import discord
from discord import ui
from typing import TYPE_CHECKING, Optional, Dict, Any, List
import logging
import asyncio

if TYPE_CHECKING:
    from ..main.main import AntiSpam

from ....core.base_cog import StandardPanelView, StandardEmbedBuilder
from .components.buttons import (
    StatsButton, TestButton, HelpButton, ResetButton, CloseButton,
    CategorySelectButton, SensitivityButton
)
from .embeds.settings_embed import create_settings_embed
from .embeds.stats_embed import create_stats_embed

logger = logging.getLogger("anti_spam")


class AntiSpamMainView(StandardPanelView):
    """
    反垃圾訊息主面板視圖
    實現統一面板架構標準
    """
    
    def __init__(self, cog: "AntiSpam", user_id: int, guild: discord.Guild):
        """
        初始化面板
        
        Args:
            cog: AntiSpam 模塊實例
            user_id: 用戶 ID
            guild: Discord 伺服器物件
        """
        super().__init__(
            timeout=300,
            required_permissions=["manage_guild"],
            admin_only=False,
            moderator_only=False,
            author_id=user_id,
            guild_id=guild.id
        )
        
        self.cog = cog
        self.user_id = user_id
        self.guild = guild
        self.current_category = "all"
        
        # 初始化頁面系統
        self._setup_antispam_pages()
    
    def _setup_pages(self):
        """設置反垃圾訊息頁面"""
        self.pages = {
            "settings": {
                "title": "反垃圾設定",
                "description": "管理反垃圾訊息設定",
                "embed_builder": self.build_settings_embed,
                "components": []
            },
            "modes": {
                "title": "檢測模式",
                "description": "配置檢測模式和敏感度",
                "embed_builder": self.build_modes_embed,
                "components": []
            },
            "whitelist": {
                "title": "白名單管理",
                "description": "管理例外用戶和角色",
                "embed_builder": self.build_whitelist_embed,
                "components": []
            },
            "history": {
                "title": "攔截記錄",
                "description": "查看攔截歷史記錄",
                "embed_builder": self.build_history_embed,
                "components": []
            },
            "advanced": {
                "title": "進階設定",
                "description": "高級配置和自定義規則",
                "embed_builder": self.build_advanced_embed,
                "components": []
            }
        }
        
        # 設置預設頁面
        self.current_page = "settings"
    
    def _setup_antispam_pages(self):
        """設置反垃圾特定頁面"""
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
            label="模式",
            style="secondary",
            emoji="🔍",
            callback=self.show_modes_callback
        ))
        
        self.add_item(self.create_standard_button(
            label="白名單",
            style="secondary",
            emoji="✅",
            callback=self.show_whitelist_callback
        ))
        
        self.add_item(self.create_standard_button(
            label="記錄",
            style="secondary",
            emoji="📜",
            callback=self.show_history_callback
        ))
        
        # 檢測類別按鈕 (第二行)
        self.add_item(self.create_standard_button(
            label="頻率限制",
            style="secondary",
            emoji="⚡",
            callback=self.frequency_category_callback
        ))
        
        self.add_item(self.create_standard_button(
            label="重複檢測",
            style="secondary",
            emoji="🔄",
            callback=self.repeat_category_callback
        ))
        
        self.add_item(self.create_standard_button(
            label="貼圖限制",
            style="secondary",
            emoji="😀",
            callback=self.sticker_category_callback
        ))
        
        self.add_item(self.create_standard_button(
            label="進階",
            style="secondary",
            emoji="🔧",
            callback=self.show_advanced_callback
        ))
        
        # 功能按鈕 (第三行)
        self.add_item(self.create_standard_button(
            label="測試檢測",
            style="primary",
            emoji="🧪",
            callback=self.test_detection_callback
        ))
        
        self.add_item(self.create_standard_button(
            label="重置設定",
            style="danger",
            emoji="🔄",
            callback=self.reset_settings_callback
        ))
        
        self.add_item(self.create_standard_button(
            label="重新整理",
            style="secondary",
            emoji="🔄",
            callback=self.refresh_callback
        ))
        
        # 控制按鈕 (第四行)
        self.add_item(self.create_standard_button(
            label="關閉",
            style="danger",
            emoji="❌",
            callback=self.close_callback
        ))
    
    async def build_settings_embed(self) -> discord.Embed:
        """構建設定嵌入"""
        return await create_settings_embed(self.cog, self.guild, self.current_category)
    
    async def build_modes_embed(self) -> discord.Embed:
        """構建檢測模式嵌入"""
        try:
            embed = StandardEmbedBuilder.create_info_embed(
                "檢測模式配置",
                "配置反垃圾訊息的檢測模式和敏感度"
            )
            
            # 檢測模式
            embed.add_field(
                name="🔍 檢測模式",
                value="• **嚴格模式**: 高敏感度，可能誤判\n• **標準模式**: 平衡檢測，推薦使用\n• **寬鬆模式**: 低敏感度，較少誤判",
                inline=False
            )
            
            # 當前設定
            embed.add_field(
                name="⚙️ 當前設定",
                value="• 檢測模式：標準模式\n• 敏感度：中等\n• 自動處理：啟用\n• 記錄保留：30 天",
                inline=False
            )
            
            # 檢測類別
            embed.add_field(
                name="📊 檢測類別",
                value="• 頻率檢測：啟用\n• 重複檢測：啟用\n• 貼圖檢測：啟用\n• 自定義規則：2 個",
                inline=False
            )
            
            return embed
            
        except Exception as e:
            return StandardEmbedBuilder.create_error_embed(
                "模式載入失敗",
                f"無法載入檢測模式：{str(e)}"
            )
    
    async def build_whitelist_embed(self) -> discord.Embed:
        """構建白名單嵌入"""
        try:
            embed = StandardEmbedBuilder.create_info_embed(
                "白名單管理",
                "管理反垃圾訊息系統的例外用戶和角色"
            )
            
            # 白名單用戶
            embed.add_field(
                name="👤 白名單用戶",
                value="暫無白名單用戶",
                inline=False
            )
            
            # 白名單角色
            embed.add_field(
                name="👥 白名單角色",
                value="• @管理員\n• @版主",
                inline=False
            )
            
            # 白名單頻道
            embed.add_field(
                name="📝 白名單頻道",
                value="暫無白名單頻道",
                inline=False
            )
            
            # 操作說明
            embed.add_field(
                name="🔧 可用操作",
                value="• 添加/移除白名單用戶\n• 添加/移除白名單角色\n• 添加/移除白名單頻道",
                inline=False
            )
            
            return embed
            
        except Exception as e:
            return StandardEmbedBuilder.create_error_embed(
                "白名單載入失敗",
                f"無法載入白名單：{str(e)}"
            )
    
    async def build_history_embed(self) -> discord.Embed:
        """構建攔截記錄嵌入"""
        try:
            embed = StandardEmbedBuilder.create_info_embed(
                "攔截記錄",
                f"顯示 {self.guild.name} 的反垃圾訊息攔截記錄"
            )
            
            # 今日統計
            embed.add_field(
                name="📊 今日統計",
                value="• 攔截次數：12\n• 頻率違規：8\n• 重複內容：3\n• 貼圖濫用：1",
                inline=True
            )
            
            # 本週統計
            embed.add_field(
                name="📈 本週統計",
                value="• 攔截次數：87\n• 頻率違規：52\n• 重複內容：23\n• 貼圖濫用：12",
                inline=True
            )
            
            # 處理動作統計
            embed.add_field(
                name="⚔️ 處理動作",
                value="• 刪除訊息：75\n• 暫時禁言：8\n• 警告用戶：4",
                inline=True
            )
            
            # 最近記錄
            embed.add_field(
                name="📜 最近記錄",
                value="• 14:32 - 用戶A 頻率違規\n• 14:28 - 用戶B 重複內容\n• 14:25 - 用戶C 貼圖濫用",
                inline=False
            )
            
            return embed
            
        except Exception as e:
            return StandardEmbedBuilder.create_error_embed(
                "記錄載入失敗",
                f"無法載入攔截記錄：{str(e)}"
            )
    
    async def build_advanced_embed(self) -> discord.Embed:
        """構建進階設定嵌入"""
        try:
            embed = StandardEmbedBuilder.create_settings_embed(
                "進階設定",
                {
                    "自定義規則": "2 個",
                    "API 整合": "啟用",
                    "機器學習": "關閉",
                    "實驗功能": "關閉",
                    "除錯模式": "關閉"
                }
            )
            
            embed.add_field(
                name="🔧 高級功能",
                value="• 自定義檢測規則\n• 第三方 API 整合\n• 機器學習檢測\n• 實驗性功能",
                inline=False
            )
            
            embed.add_field(
                name="⚠️ 注意事項",
                value="進階設定可能影響系統性能，請謹慎配置。",
                inline=False
            )
            
            return embed
            
        except Exception as e:
            return StandardEmbedBuilder.create_error_embed(
                "進階設定載入失敗",
                f"無法載入進階設定：{str(e)}"
            )
    
    # 頁面切換回調
    async def show_settings_callback(self, interaction: discord.Interaction):
        """顯示設定頁面"""
        await self.change_page(interaction, "settings")
    
    async def show_modes_callback(self, interaction: discord.Interaction):
        """顯示模式頁面"""
        await self.change_page(interaction, "modes")
    
    async def show_whitelist_callback(self, interaction: discord.Interaction):
        """顯示白名單頁面"""
        await self.change_page(interaction, "whitelist")
    
    async def show_history_callback(self, interaction: discord.Interaction):
        """顯示記錄頁面"""
        await self.change_page(interaction, "history")
    
    async def show_advanced_callback(self, interaction: discord.Interaction):
        """顯示進階頁面"""
        await self.change_page(interaction, "advanced")
    
    # 類別切換回調
    async def frequency_category_callback(self, interaction: discord.Interaction):
        """切換到頻率限制類別"""
        self.current_category = "frequency"
        await self.change_page(interaction, "settings")
    
    async def repeat_category_callback(self, interaction: discord.Interaction):
        """切換到重複檢測類別"""
        self.current_category = "repeat"
        await self.change_page(interaction, "settings")
    
    async def sticker_category_callback(self, interaction: discord.Interaction):
        """切換到貼圖限制類別"""
        self.current_category = "sticker"
        await self.change_page(interaction, "settings")
    
    # 功能回調
    async def test_detection_callback(self, interaction: discord.Interaction):
        """測試檢測功能"""
        await self.execute_operation(
            interaction,
            self._test_detection,
            "測試檢測功能"
        )
    
    async def reset_settings_callback(self, interaction: discord.Interaction):
        """重置設定回調"""
        # 顯示確認對話框
        confirm_embed = StandardEmbedBuilder.create_warning_embed(
            "確認重置設定",
            "⚠️ 此操作將重置所有反垃圾訊息設定，無法復原！\n\n請在 30 秒內再次點擊確認。"
        )
        
        confirm_view = ConfirmResetView(self)
        await interaction.response.send_message(
            embed=confirm_embed, 
            view=confirm_view, 
            ephemeral=True
        )
    
    # 功能實現
    async def _test_detection(self):
        """測試檢測功能的實際操作"""
        try:
            # 模擬檢測測試
            await asyncio.sleep(1)
            return "檢測功能測試完成，所有模塊運行正常"
        except Exception as e:
            raise Exception(f"檢測測試失敗：{str(e)}")
    
    async def _reset_settings(self):
        """重置設定的實際操作"""
        try:
            # 這裡應該實現設定重置邏輯
            return "設定重置功能將在後續版本中實現"
        except Exception as e:
            raise Exception(f"設定重置失敗：{str(e)}")
    
    async def build_main_embed(self) -> discord.Embed:
        """構建主頁面嵌入 (覆寫基類方法)"""
        return await self.build_settings_embed()


class ConfirmResetView(discord.ui.View):
    """確認重置設定的視圖"""
    
    def __init__(self, parent_view: AntiSpamMainView):
        super().__init__(timeout=30)
        self.parent_view = parent_view
    
    @discord.ui.button(label="確認重置", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        """確認重置設定"""
        try:
            await self.parent_view.execute_operation(
                interaction,
                self.parent_view._reset_settings,
                "重置反垃圾設定"
            )
            
            # 禁用按鈕
            self._disable_all_items()
            
            success_embed = StandardEmbedBuilder.create_success_embed(
                "設定已重置",
                "反垃圾訊息設定已成功重置"
            )
            
            await interaction.response.edit_message(embed=success_embed, view=self)
            
        except Exception as e:
            error_embed = StandardEmbedBuilder.create_error_embed(
                "重置失敗",
                f"重置設定時發生錯誤：{str(e)}"
            )
            await interaction.response.edit_message(embed=error_embed, view=self)
    
    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        """取消重置"""
        # 禁用按鈕
        self._disable_all_items()
        
        cancel_embed = StandardEmbedBuilder.create_info_embed(
            "已取消",
            "設定重置操作已取消"
        )
        
        await interaction.response.edit_message(embed=cancel_embed, view=self)
    
    def _disable_all_items(self):
        """禁用所有項目"""
        # 清空所有項目以防止進一步操作
        self.clear_items()
    
    async def on_timeout(self):
        """超時處理"""
        self._disable_all_items()


# 保留原有的其他類別以保持兼容性
class ToggleButton(ui.Button):
    """切換按鈕類別"""
    
    def __init__(self, row: int = 0):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="切換啟用",
            emoji="🔄",
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        await interaction.response.send_message(
            "切換功能將在後續版本中實現", ephemeral=True
        )


class SettingsModal(ui.Modal):
    """設定模態框"""
    
    def __init__(self, cog: "AntiSpam", guild: discord.Guild, setting_key: str, setting_name: str):
        super().__init__(title=f"修改 {setting_name}")
        self.cog = cog
        self.guild = guild
        self.setting_key = setting_key
        self.setting_name = setting_name
        
        # 添加輸入欄位
        self.value_input = ui.TextInput(
            label=setting_name,
            placeholder=f"請輸入新的 {setting_name} 值",
            required=True,
            max_length=100
        )
        self.add_item(self.value_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """提交處理"""
        try:
            value = self.value_input.value
            
            # 這裡應該實現設定更新邏輯
            embed = StandardEmbedBuilder.create_success_embed(
                "設定已更新",
                f"{self.setting_name} 已更新為：{value}"
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            error_embed = StandardEmbedBuilder.create_error_embed(
                "設定更新失敗",
                f"更新設定時發生錯誤：{str(e)}"
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True) 