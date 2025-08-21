"""
訊息監聽面板
Task ID: 9 - 重構現有模組以符合新架構

提供訊息監聽系統的使用者介面：
- 監聽設定面板
- 頻道管理
- 訊息搜尋
- 系統監控
"""

import asyncio
import textwrap
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import discord
from discord.ext import commands
from discord.ui import View, Modal, TextInput, Select, ChannelSelect, Button

from panels.base_panel import BasePanel
from services.message.message_service import MessageService
from services.message.models import SearchQuery
from core.exceptions import handle_errors

import logging
logger = logging.getLogger('panels.message')


class MessagePanel(BasePanel):
    """
    訊息監聽面板
    
    提供訊息監聽系統的 Discord UI 互動介面
    """
    
    def __init__(self, message_service: MessageService, config: Optional[Dict[str, Any]] = None):
        """
        初始化訊息面板
        
        參數：
            message_service: 訊息服務實例
            config: 配置參數
        """
        super().__init__(
            name="MessagePanel",
            title="📝 訊息監聽管理面板",
            description="管理訊息監聽、搜尋和設定",
            color=discord.Color.blue()
        )
        
        self.message_service = message_service
        self.config = config or {}
        
        # 添加服務依賴
        self.add_service(message_service, "message")
    
    @handle_errors(log_errors=True)
    async def show_settings_panel(self, interaction: discord.Interaction) -> None:
        """
        顯示訊息監聽設定面板
        
        參數：
            interaction: Discord 互動
        """
        if not interaction.guild:
            await self.send_error(interaction, "此功能只能在伺服器中使用")
            return
        
        try:
            embed = await self._build_settings_embed()
            view = MessageSettingsView(self)
            
            await interaction.response.send_message(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"顯示訊息設定面板失敗：{e}")
            await self.send_error(interaction, "載入設定面板失敗")
    
    @handle_errors(log_errors=True)
    async def show_search_panel(self, interaction: discord.Interaction) -> None:
        """
        顯示訊息搜尋面板
        
        參數：
            interaction: Discord 互動
        """
        if not interaction.guild:
            await self.send_error(interaction, "此功能只能在伺服器中使用")
            return
        
        try:
            await interaction.response.send_modal(SearchModal(self))
            
        except Exception as e:
            logger.error(f"顯示訊息搜尋面板失敗：{e}")
            await self.send_error(interaction, "載入搜尋面板失敗")
    
    @handle_errors(log_errors=True)
    async def show_channel_management(self, interaction: discord.Interaction) -> None:
        """
        顯示頻道管理面板
        
        參數：
            interaction: Discord 互動
        """
        if not interaction.guild:
            await self.send_error(interaction, "此功能只能在伺服器中使用")
            return
        
        try:
            embed = await self._build_channel_management_embed()
            view = ChannelManagementView(self)
            
            await interaction.response.send_message(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"顯示頻道管理面板失敗：{e}")
            await self.send_error(interaction, "載入頻道管理面板失敗")
    
    async def handle_search(self, interaction: discord.Interaction, query: SearchQuery) -> None:
        """
        處理訊息搜尋
        
        參數：
            interaction: Discord 互動
            query: 搜尋查詢
        """
        try:
            await interaction.response.defer(thinking=True)
            
            # 執行搜尋
            result = await self.message_service.search_messages(query)
            
            # 建構結果 embed
            embed = await self._build_search_result_embed(result)
            view = SearchResultView(self, result) if result.has_more else None
            
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"處理訊息搜尋失敗：{e}")
            await interaction.followup.send("❌ 搜尋失敗")
    
    async def handle_setting_update(self, interaction: discord.Interaction, key: str, value: str) -> None:
        """
        處理設定更新
        
        參數：
            interaction: Discord 互動
            key: 設定鍵
            value: 設定值
        """
        try:
            success = await self.message_service.update_setting(key, value)
            
            if success:
                await self.send_success(interaction, f"✅ {key} 已更新")
                # 重新整理面板
                await self._refresh_settings_panel(interaction)
            else:
                await self.send_error(interaction, "更新設定失敗")
                
        except Exception as e:
            logger.error(f"處理設定更新失敗：{e}")
            await self.send_error(interaction, "更新設定時發生錯誤")
    
    async def handle_channel_add(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        """
        處理添加監聽頻道
        
        參數：
            interaction: Discord 互動
            channel: 要添加的頻道
        """
        try:
            success = await self.message_service.add_monitored_channel(channel.id)
            
            if success:
                await self.send_success(interaction, f"✅ 已添加監聽頻道：{channel.mention}")
                # 重新整理面板
                await self._refresh_channel_panel(interaction)
            else:
                await self.send_error(interaction, "添加頻道失敗")
                
        except Exception as e:
            logger.error(f"處理添加頻道失敗：{e}")
            await self.send_error(interaction, "添加頻道時發生錯誤")
    
    async def handle_channel_remove(self, interaction: discord.Interaction, channel_id: int) -> None:
        """
        處理移除監聽頻道
        
        參數：
            interaction: Discord 互動
            channel_id: 要移除的頻道 ID
        """
        try:
            success = await self.message_service.remove_monitored_channel(channel_id)
            
            if success:
                await self.send_success(interaction, f"✅ 已移除監聽頻道：<#{channel_id}>")
                # 重新整理面板
                await self._refresh_channel_panel(interaction)
            else:
                await self.send_error(interaction, "移除頻道失敗")
                
        except Exception as e:
            logger.error(f"處理移除頻道失敗：{e}")
            await self.send_error(interaction, "移除頻道時發生錯誤")
    
    async def _handle_slash_command(self, interaction: discord.Interaction):
        """處理斜線命令"""
        await self.send_warning(interaction, "此功能尚未實現")
    
    async def _build_settings_embed(self) -> discord.Embed:
        """建構設定面板 embed"""
        settings = await self.message_service.get_settings()
        
        embed = await self.create_embed(
            title="📝 訊息監聽設定",
            description="管理訊息監聽的各種設定"
        )
        
        # 基本設定
        embed.add_field(
            name="🔧 監聽狀態",
            value="✅ 已啟用" if settings.enabled else "❌ 已停用",
            inline=True
        )
        
        embed.add_field(
            name="📺 日誌頻道",
            value=f"<#{settings.log_channel_id}>" if settings.log_channel_id else "❌ 未設定",
            inline=True
        )
        
        embed.add_field(
            name="📊 監聽頻道數",
            value=f"{len(settings.monitored_channels)} 個頻道",
            inline=True
        )
        
        # 記錄設定
        embed.add_field(
            name="✏️ 記錄編輯",
            value="✅ 啟用" if settings.record_edits else "❌ 停用",
            inline=True
        )
        
        embed.add_field(
            name="🗑️ 記錄刪除",
            value="✅ 啟用" if settings.record_deletes else "❌ 停用",
            inline=True
        )
        
        embed.add_field(
            name="📅 資料保留",
            value=f"{settings.retention_days} 天",
            inline=True
        )
        
        # 渲染設定
        embed.add_field(
            name="🎨 渲染模式",
            value=settings.render_mode,
            inline=True
        )
        
        embed.set_footer(text="💡 點擊下方按鈕來調整設定")
        return embed
    
    async def _build_channel_management_embed(self) -> discord.Embed:
        """建構頻道管理 embed"""
        settings = await self.message_service.get_settings()
        
        embed = await self.create_embed(
            title="📊 頻道管理",
            description="管理監聽頻道列表"
        )
        
        if settings.monitored_channels:
            channel_list = []
            for channel_id in settings.monitored_channels[:20]:  # 最多顯示20個
                channel_list.append(f"<#{channel_id}>")
            
            embed.add_field(
                name=f"📝 監聽頻道 ({len(settings.monitored_channels)} 個)",
                value="\n".join(channel_list) if channel_list else "無",
                inline=False
            )
            
            if len(settings.monitored_channels) > 20:
                embed.add_field(
                    name="ℹ️ 提示",
                    value=f"還有 {len(settings.monitored_channels) - 20} 個頻道未顯示",
                    inline=False
                )
        else:
            embed.add_field(
                name="📝 監聽頻道",
                value="❌ 尚未設定任何監聽頻道",
                inline=False
            )
        
        embed.set_footer(text="💡 使用下方按鈕添加或移除頻道")
        return embed
    
    async def _build_search_result_embed(self, result) -> discord.Embed:
        """建構搜尋結果 embed"""
        embed = await self.create_embed(
            title="🔍 訊息搜尋結果",
            description=f"找到 {result.total_count} 條符合條件的訊息"
        )
        
        if result.records:
            for i, record in enumerate(result.records[:10], 1):  # 最多顯示10條
                # 格式化時間
                timestamp = datetime.fromtimestamp(record.timestamp)
                time_str = timestamp.strftime("%m/%d %H:%M")
                
                # 截斷內容
                content = record.content[:100] + "..." if len(record.content) > 100 else record.content
                content = content.replace("\n", " ")  # 移除換行
                
                embed.add_field(
                    name=f"{i}. <#{record.channel_id}> - {time_str}",
                    value=f"<@{record.author_id}>: {content}",
                    inline=False
                )
        else:
            embed.add_field(
                name="📭 無結果",
                value="沒有找到符合條件的訊息",
                inline=False
            )
        
        # 搜尋條件
        query_info = []
        if result.query.keyword:
            query_info.append(f"關鍵字: {result.query.keyword}")
        if result.query.channel_id:
            query_info.append(f"頻道: <#{result.query.channel_id}>")
        if result.query.author_id:
            query_info.append(f"作者: <@{result.query.author_id}>")
        
        if query_info:
            embed.add_field(
                name="🔍 搜尋條件",
                value=" | ".join(query_info),
                inline=False
            )
        
        if result.has_more:
            embed.set_footer(text="💡 點擊「下一頁」查看更多結果")
        
        return embed
    
    async def _refresh_settings_panel(self, interaction: discord.Interaction):
        """重新整理設定面板"""
        try:
            if interaction.message:
                new_embed = await self._build_settings_embed()
                new_view = MessageSettingsView(self)
                await interaction.followup.edit_message(
                    interaction.message.id,
                    embed=new_embed,
                    view=new_view
                )
        except Exception as e:
            logger.warning(f"重新整理設定面板失敗：{e}")
    
    async def _refresh_channel_panel(self, interaction: discord.Interaction):
        """重新整理頻道面板"""
        try:
            if interaction.message:
                new_embed = await self._build_channel_management_embed()
                new_view = ChannelManagementView(self)
                await interaction.followup.edit_message(
                    interaction.message.id,
                    embed=new_embed,
                    view=new_view
                )
        except Exception as e:
            logger.warning(f"重新整理頻道面板失敗：{e}")


# ===== UI 元件 =====

class MessageSettingsView(View):
    """訊息設定互動檢視"""
    
    def __init__(self, panel: MessagePanel):
        super().__init__(timeout=300)
        self.panel = panel
    
    @discord.ui.button(label="🔧 切換監聽狀態", style=discord.ButtonStyle.primary)
    async def toggle_enabled(self, interaction: discord.Interaction, button: Button):
        """切換監聽狀態"""
        settings = await self.panel.message_service.get_settings()
        new_value = "false" if settings.enabled else "true"
        await self.panel.handle_setting_update(interaction, "enabled", new_value)
    
    @discord.ui.button(label="📺 設定日誌頻道", style=discord.ButtonStyle.secondary)
    async def set_log_channel(self, interaction: discord.Interaction, button: Button):
        """設定日誌頻道"""
        await interaction.response.send_modal(SetLogChannelModal(self.panel))
    
    @discord.ui.button(label="📅 設定保留天數", style=discord.ButtonStyle.secondary)
    async def set_retention(self, interaction: discord.Interaction, button: Button):
        """設定資料保留天數"""
        await interaction.response.send_modal(SetRetentionModal(self.panel))
    
    @discord.ui.button(label="📊 管理頻道", style=discord.ButtonStyle.green)
    async def manage_channels(self, interaction: discord.Interaction, button: Button):
        """管理監聽頻道"""
        await self.panel.show_channel_management(interaction)
    
    @discord.ui.button(label="🔍 搜尋訊息", style=discord.ButtonStyle.green)
    async def search_messages(self, interaction: discord.Interaction, button: Button):
        """搜尋訊息"""
        await self.panel.show_search_panel(interaction)


class ChannelManagementView(View):
    """頻道管理互動檢視"""
    
    def __init__(self, panel: MessagePanel):
        super().__init__(timeout=300)
        self.panel = panel
    
    @discord.ui.select(
        cls=ChannelSelect,
        placeholder="選擇要添加的頻道",
        channel_types=[discord.ChannelType.text]
    )
    async def add_channel(self, interaction: discord.Interaction, select: ChannelSelect):
        """添加監聽頻道"""
        channel = select.values[0]
        await self.panel.handle_channel_add(interaction, channel)
    
    @discord.ui.button(label="🗑️ 移除頻道", style=discord.ButtonStyle.red)
    async def remove_channel(self, interaction: discord.Interaction, button: Button):
        """移除監聽頻道"""
        await interaction.response.send_modal(RemoveChannelModal(self.panel))


class SearchResultView(View):
    """搜尋結果互動檢視"""
    
    def __init__(self, panel: MessagePanel, result):
        super().__init__(timeout=300)
        self.panel = panel
        self.result = result
    
    @discord.ui.button(label="➡️ 下一頁", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        """下一頁結果"""
        new_query = self.result.query
        new_query.offset += new_query.limit
        await self.panel.handle_search(interaction, new_query)


# ===== Modal 類別 =====

class SearchModal(Modal, title="訊息搜尋"):
    """搜尋 Modal"""
    
    def __init__(self, panel: MessagePanel):
        super().__init__()
        self.panel = panel
    
    keyword = TextInput(
        label="關鍵字",
        placeholder="輸入要搜尋的關鍵字（可留空）",
        required=False,
        max_length=100
    )
    
    channel_id = TextInput(
        label="頻道 ID",
        placeholder="輸入頻道 ID（可留空搜尋所有頻道）",
        required=False,
        max_length=20
    )
    
    author_id = TextInput(
        label="用戶 ID",
        placeholder="輸入用戶 ID（可留空搜尋所有用戶）",
        required=False,
        max_length=20
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        """提交搜尋"""
        try:
            # 建構搜尋查詢
            query = SearchQuery(
                keyword=self.keyword.value or None,
                channel_id=int(self.channel_id.value) if self.channel_id.value else None,
                author_id=int(self.author_id.value) if self.author_id.value else None,
                guild_id=interaction.guild.id if interaction.guild else None,
                end_time=datetime.now(),
                start_time=datetime.now() - timedelta(days=1),  # 預設搜尋最近24小時
                limit=10
            )
            
            await self.panel.handle_search(interaction, query)
            
        except ValueError:
            await self.panel.send_error(interaction, "請輸入有效的 ID 數字")


class SetLogChannelModal(Modal, title="設定日誌頻道"):
    """設定日誌頻道 Modal"""
    
    def __init__(self, panel: MessagePanel):
        super().__init__()
        self.panel = panel
    
    channel_id = TextInput(
        label="頻道 ID",
        placeholder="輸入要設為日誌頻道的 ID",
        required=True,
        max_length=20
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel_id.value)
            await self.panel.handle_setting_update(interaction, "log_channel_id", str(channel_id))
        except ValueError:
            await self.panel.send_error(interaction, "請輸入有效的頻道 ID")


class SetRetentionModal(Modal, title="設定資料保留天數"):
    """設定保留天數 Modal"""
    
    def __init__(self, panel: MessagePanel):
        super().__init__()
        self.panel = panel
    
    days = TextInput(
        label="保留天數",
        placeholder="輸入要保留訊息的天數（1-365）",
        required=True,
        max_length=3
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            days = int(self.days.value)
            if 1 <= days <= 365:
                await self.panel.handle_setting_update(interaction, "retention_days", str(days))
            else:
                await self.panel.send_error(interaction, "保留天數必須在 1-365 之間")
        except ValueError:
            await self.panel.send_error(interaction, "請輸入有效的天數")


class RemoveChannelModal(Modal, title="移除監聽頻道"):
    """移除頻道 Modal"""
    
    def __init__(self, panel: MessagePanel):
        super().__init__()
        self.panel = panel
    
    channel_id = TextInput(
        label="頻道 ID",
        placeholder="輸入要移除的頻道 ID",
        required=True,
        max_length=20
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel_id.value)
            await self.panel.handle_channel_remove(interaction, channel_id)
        except ValueError:
            await self.panel.send_error(interaction, "請輸入有效的頻道 ID")