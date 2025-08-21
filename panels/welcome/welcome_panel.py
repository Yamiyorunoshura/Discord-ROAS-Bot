"""
歡迎系統面板
Task ID: 9 - 重構現有模組以符合新架構

提供歡迎系統的使用者介面：
- 設定面板
- 預覽功能
- 互動式設定更新
"""

import os
import io
import asyncio
import textwrap
from typing import Optional, Dict, Any
import discord
from discord.ext import commands

from panels.base_panel import BasePanel
from services.welcome.welcome_service import WelcomeService
from core.exceptions import handle_errors

import logging
logger = logging.getLogger('panels.welcome')


class WelcomePanel(BasePanel):
    """
    歡迎系統面板
    
    提供歡迎系統的 Discord UI 互動介面
    """
    
    def __init__(self, welcome_service: WelcomeService, config: Optional[Dict[str, Any]] = None):
        """
        初始化歡迎面板
        
        參數：
            welcome_service: 歡迎服務實例
            config: 配置參數
        """
        super().__init__(
            name="WelcomePanel",
            title="🎉 歡迎訊息設定面板",
            description="在這裡可以自訂歡迎訊息的各種設定",
            color=discord.Color.green()
        )
        
        self.welcome_service = welcome_service
        self.config = config or {}
        self.bg_dir = self.config.get('bg_dir', 'data/backgrounds')
        
        # 添加服務依賴
        self.add_service(welcome_service, "welcome")
    
    @handle_errors(log_errors=True)
    async def show_settings_panel(self, interaction: discord.Interaction) -> None:
        """
        顯示歡迎設定面板
        
        參數：
            interaction: Discord 互動
        """
        if not interaction.guild:
            await self.send_error(interaction, "此功能只能在伺服器中使用")
            return
        
        try:
            # 建構設定面板 embed
            embed = await self._build_settings_embed(interaction.guild)
            view = WelcomeSettingsView(self)
            
            await interaction.response.send_message(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"顯示歡迎設定面板失敗：{e}")
            await self.send_error(interaction, "載入設定面板失敗")
    
    @handle_errors(log_errors=True)
    async def preview_welcome_message(self, interaction: discord.Interaction, target_user: Optional[discord.Member] = None) -> None:
        """
        預覽歡迎訊息
        
        參數：
            interaction: Discord 互動
            target_user: 目標使用者（預設為互動使用者）
        """
        if not interaction.guild:
            await self.send_error(interaction, "此功能只能在伺服器中使用")
            return
        
        try:
            await interaction.response.defer(thinking=True)
            
            user = target_user or interaction.user
            if not isinstance(user, discord.Member):
                await interaction.followup.send("❌ 無法取得成員資訊")
                return
            
            # 生成歡迎圖片
            welcome_image = await self.welcome_service.generate_welcome_image(
                interaction.guild.id, user
            )
            
            # 獲取設定
            settings = await self.welcome_service.get_settings(interaction.guild.id)
            
            # 格式化訊息
            message_content = self.welcome_service._render_template(
                settings.message, user
            )
            
            # 發送預覽
            image_bytes = welcome_image.to_bytes()
            file = discord.File(
                io.BytesIO(image_bytes), 
                filename="welcome_preview.png"
            )
            
            await interaction.followup.send(
                content=f"📋 **歡迎訊息預覽**\n{message_content}",
                file=file
            )
            
        except Exception as e:
            logger.error(f"預覽歡迎訊息失敗：{e}")
            await interaction.followup.send("❌ 預覽生成失敗")
    
    async def handle_setting_update(self, interaction: discord.Interaction, setting_key: str, value: Any) -> None:
        """
        處理設定更新
        
        參數：
            interaction: Discord 互動
            setting_key: 設定鍵
            value: 設定值
        """
        if not interaction.guild:
            await self.send_error(interaction, "此功能只能在伺服器中使用")
            return
        
        try:
            # 更新設定
            success = await self.welcome_service.update_setting(
                interaction.guild.id, setting_key, value
            )
            
            if success:
                await self.send_success(interaction, f"✅ {setting_key} 已更新")
                
                # 重新整理面板
                await self._refresh_settings_panel(interaction)
                
                # 發送預覽
                await self.preview_welcome_message(interaction)
            else:
                await self.send_error(interaction, "更新設定失敗")
                
        except Exception as e:
            logger.error(f"處理設定更新失敗：{e}")
            await self.send_error(interaction, "更新設定時發生錯誤")
    
    async def handle_background_upload(self, interaction: discord.Interaction) -> None:
        """
        處理背景圖片上傳
        
        參數：
            interaction: Discord 互動
        """
        if not interaction.guild:
            await self.send_error(interaction, "此功能只能在伺服器中使用")
            return
        
        try:
            await interaction.response.send_message(
                "📤 **上傳背景圖片**\n\n"
                "請直接貼上 PNG 或 JPG 格式的圖片，我會自動偵測你的上傳！\n"
                "💡 **建議尺寸：** 800x450 像素或更大\n"
                "⏰ **上傳時限：** 3 分鐘"
            )
            
            # 等待使用者上傳圖片
            def check(message):
                return (
                    message.author.id == interaction.user.id and
                    message.channel.id == interaction.channel.id and
                    message.attachments
                )
            
            try:
                message = await interaction.client.wait_for('message', timeout=180.0, check=check)
                
                # 處理附件
                attachment = message.attachments[0]
                if attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    # 下載並儲存圖片
                    image_data = await attachment.read()
                    filename = f"welcome_bg_{interaction.guild.id}{os.path.splitext(attachment.filename)[1]}"
                    filepath = os.path.join(self.bg_dir, filename)
                    
                    with open(filepath, "wb") as f:
                        f.write(image_data)
                    
                    # 更新資料庫
                    await self.welcome_service.update_background(interaction.guild.id, filename)
                    
                    await interaction.followup.send("✅ 背景圖片已上傳並設定！")
                    
                    # 重新整理面板
                    await self._refresh_settings_panel(interaction)
                    
                    # 發送預覽
                    await self.preview_welcome_message(interaction)
                else:
                    await interaction.followup.send("❌ 只接受 PNG/JPG 格式圖片！")
                    
            except asyncio.TimeoutError:
                await interaction.followup.send("⏰ 上傳逾時，請重新操作")
                
        except Exception as e:
            logger.error(f"處理背景圖片上傳失敗：{e}")
            await self.send_error(interaction, "背景圖片上傳失敗")
    
    async def _handle_slash_command(self, interaction: discord.Interaction):
        """處理斜線命令"""
        # 這裡可以根據需要實作特定的斜線命令處理邏輯
        await self.send_warning(interaction, "此功能尚未實現")
    
    async def _build_settings_embed(self, guild: discord.Guild) -> discord.Embed:
        """建構設定面板 embed"""
        settings = await self.welcome_service.get_settings(guild.id)
        
        embed = await self.create_embed(
            title="🎉 歡迎訊息設定面板",
            description="在這裡可以自訂歡迎訊息的各種設定"
        )
        
        # 基本設定
        embed.add_field(
            name="📺 歡迎頻道",
            value=f"<#{settings.channel_id}>" if settings.channel_id else "❌ 未設定",
            inline=False
        )
        
        embed.add_field(
            name="🎨 背景圖片",
            value=f"✅ {settings.background_path}" if settings.background_path else "❌ 未設定",
            inline=False
        )
        
        # 文字設定
        embed.add_field(
            name="📝 圖片標題",
            value=f"```{settings.title}```",
            inline=False
        )
        
        embed.add_field(
            name="📄 圖片內容",
            value=f"```{settings.description}```",
            inline=False
        )
        
        embed.add_field(
            name="💬 歡迎訊息",
            value=f"```{settings.message}```",
            inline=False
        )
        
        # 位置設定
        embed.add_field(
            name="📍 頭像位置",
            value=f"X: {settings.avatar_x}, Y: {settings.avatar_y}",
            inline=True
        )
        embed.add_field(
            name="📍 標題位置",
            value=f"Y: {settings.title_y}",
            inline=True
        )
        embed.add_field(
            name="📍 內容位置",
            value=f"Y: {settings.description_y}",
            inline=True
        )
        
        # 大小設定
        embed.add_field(
            name="🔤 標題字體",
            value=f"{settings.title_font_size}px",
            inline=True
        )
        embed.add_field(
            name="🔤 內容字體",
            value=f"{settings.desc_font_size}px",
            inline=True
        )
        embed.add_field(
            name="🖼️ 頭像大小",
            value=f"{settings.avatar_size}px",
            inline=True
        )
        
        # 詳細說明
        embed.add_field(
            name="✨ 動態欄位使用指南",
            value=textwrap.dedent("""
                **可用的動態欄位：**
                • `{member}` 或 `{member.mention}` → 提及新成員
                • `{member.name}` → 新成員名稱
                • `{member.display_name}` → 新成員顯示名稱
                • `{guild.name}` → 伺服器名稱
                • `{channel}` → 歡迎頻道
                • `{channel:頻道ID}` → 指定頻道
                • `{emoji:表情名稱}` → 伺服器表情
                
                **使用範例：**
                ```
                歡迎 {member} 加入 {guild.name}！
                請到 {channel:123456789012345678} 報到 {emoji:wave}
                ```
            """).strip(),
            inline=False
        )
        
        embed.set_footer(text="💡 點擊下方選單來調整設定 | 設定完成後可使用預覽功能查看效果")
        return embed
    
    async def _refresh_settings_panel(self, interaction: discord.Interaction):
        """重新整理設定面板"""
        try:
            if interaction.message and interaction.guild:
                new_embed = await self._build_settings_embed(interaction.guild)
                new_view = WelcomeSettingsView(self)
                await interaction.followup.edit_message(
                    interaction.message.id,
                    embed=new_embed,
                    view=new_view
                )
        except Exception as e:
            logger.warning(f"重新整理設定面板失敗：{e}")


class WelcomeSettingsView(discord.ui.View):
    """歡迎設定互動檢視"""
    
    def __init__(self, panel: WelcomePanel):
        super().__init__(timeout=300)
        self.panel = panel
    
    @discord.ui.select(
        placeholder="選擇要調整的設定項目",
        min_values=1, max_values=1,
        options=[
            discord.SelectOption(label="📺 設定歡迎頻道", description="設定歡迎訊息發送的頻道"),
            discord.SelectOption(label="📝 設定圖片標題", description="設定歡迎圖片上的標題文字"),
            discord.SelectOption(label="📄 設定圖片內容", description="設定歡迎圖片上的內容文字"),
            discord.SelectOption(label="🎨 上傳背景圖片", description="上傳自訂背景圖片（PNG/JPG）"),
            discord.SelectOption(label="💬 設定歡迎訊息", description="設定純文字歡迎訊息"),
            discord.SelectOption(label="📍 調整頭像 X 位置", description="調整頭像在圖片上的 X 座標"),
            discord.SelectOption(label="📍 調整頭像 Y 位置", description="調整頭像在圖片上的 Y 座標"),
            discord.SelectOption(label="📍 調整標題 Y 位置", description="調整標題的 Y 座標"),
            discord.SelectOption(label="📍 調整內容 Y 位置", description="調整內容的 Y 座標"),
            discord.SelectOption(label="🔤 調整標題字體大小", description="調整標題字體大小（像素）"),
            discord.SelectOption(label="🔤 調整內容字體大小", description="調整內容字體大小（像素）"),
            discord.SelectOption(label="🖼️ 調整頭像大小", description="調整頭像顯示的像素大小"),
        ]
    )
    async def select_setting(self, interaction: discord.Interaction, select: discord.ui.Select):
        """處理設定選擇"""
        option = select.values[0]
        
        if option == "📺 設定歡迎頻道":
            await interaction.response.send_modal(SetChannelModal(self.panel))
        elif option == "📝 設定圖片標題":
            await interaction.response.send_modal(SetTitleModal(self.panel))
        elif option == "📄 設定圖片內容":
            await interaction.response.send_modal(SetDescriptionModal(self.panel))
        elif option == "🎨 上傳背景圖片":
            await self.panel.handle_background_upload(interaction)
        elif option == "💬 設定歡迎訊息":
            await interaction.response.send_modal(SetMessageModal(self.panel))
        elif option == "📍 調整頭像 X 位置":
            await interaction.response.send_modal(SetAvatarXModal(self.panel))
        elif option == "📍 調整頭像 Y 位置":
            await interaction.response.send_modal(SetAvatarYModal(self.panel))
        elif option == "📍 調整標題 Y 位置":
            await interaction.response.send_modal(SetTitleYModal(self.panel))
        elif option == "📍 調整內容 Y 位置":
            await interaction.response.send_modal(SetDescriptionYModal(self.panel))
        elif option == "🔤 調整標題字體大小":
            await interaction.response.send_modal(SetTitleFontSizeModal(self.panel))
        elif option == "🔤 調整內容字體大小":
            await interaction.response.send_modal(SetDescriptionFontSizeModal(self.panel))
        elif option == "🖼️ 調整頭像大小":
            await interaction.response.send_modal(SetAvatarSizeModal(self.panel))


# 設定 Modal 類別
class BaseWelcomeModal(discord.ui.Modal):
    """歡迎設定 Modal 基礎類別"""
    
    def __init__(self, panel: WelcomePanel, **kwargs):
        super().__init__(**kwargs)
        self.panel = panel


class SetChannelModal(BaseWelcomeModal, title="設定歡迎頻道"):
    channel_id = discord.ui.TextInput(
        label="頻道 ID",
        required=True,
        placeholder="請輸入頻道 ID（可在頻道右鍵選單中找到）",
        min_length=17,
        max_length=20
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel_id.value)
            await self.panel.handle_setting_update(interaction, "channel_id", channel_id)
        except ValueError:
            await self.panel.send_error(interaction, "請輸入有效的頻道 ID")


class SetTitleModal(BaseWelcomeModal, title="設定圖片標題"):
    title = discord.ui.TextInput(
        label="標題文字",
        required=True,
        placeholder="可用 {member.name}、{guild.name}、{channel}、{emoji:名稱}",
        max_length=100
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await self.panel.handle_setting_update(interaction, "title", self.title.value)


class SetDescriptionModal(BaseWelcomeModal, title="設定圖片內容"):
    description = discord.ui.TextInput(
        label="內容文字",
        required=True,
        placeholder="可用 {member.mention}、{guild.name}、{channel}、{emoji:名稱}",
        max_length=200
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await self.panel.handle_setting_update(interaction, "description", self.description.value)


class SetMessageModal(BaseWelcomeModal, title="設定歡迎訊息"):
    message = discord.ui.TextInput(
        label="歡迎訊息",
        required=True,
        placeholder="可用 {member}、{channel}、{channel:ID}、{emoji:名稱}",
        max_length=500
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await self.panel.handle_setting_update(interaction, "message", self.message.value)


class SetAvatarXModal(BaseWelcomeModal, title="調整頭像 X 位置"):
    x_position = discord.ui.TextInput(
        label="X 座標（像素）",
        required=True,
        placeholder="建議範圍：0-800",
        min_length=1,
        max_length=4
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            x = int(self.x_position.value)
            await self.panel.handle_setting_update(interaction, "avatar_x", x)
        except ValueError:
            await self.panel.send_error(interaction, "請輸入有效的數字")


class SetAvatarYModal(BaseWelcomeModal, title="調整頭像 Y 位置"):
    y_position = discord.ui.TextInput(
        label="Y 座標（像素）",
        required=True,
        placeholder="建議範圍：0-450",
        min_length=1,
        max_length=4
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            y = int(self.y_position.value)
            await self.panel.handle_setting_update(interaction, "avatar_y", y)
        except ValueError:
            await self.panel.send_error(interaction, "請輸入有效的數字")


class SetTitleYModal(BaseWelcomeModal, title="調整標題 Y 位置"):
    y_position = discord.ui.TextInput(
        label="Y 座標（像素）",
        required=True,
        placeholder="建議範圍：0-450",
        min_length=1,
        max_length=4
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            y = int(self.y_position.value)
            await self.panel.handle_setting_update(interaction, "title_y", y)
        except ValueError:
            await self.panel.send_error(interaction, "請輸入有效的數字")


class SetDescriptionYModal(BaseWelcomeModal, title="調整內容 Y 位置"):
    y_position = discord.ui.TextInput(
        label="Y 座標（像素）",
        required=True,
        placeholder="建議範圍：0-450",
        min_length=1,
        max_length=4
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            y = int(self.y_position.value)
            await self.panel.handle_setting_update(interaction, "description_y", y)
        except ValueError:
            await self.panel.send_error(interaction, "請輸入有效的數字")


class SetTitleFontSizeModal(BaseWelcomeModal, title="調整標題字體大小"):
    font_size = discord.ui.TextInput(
        label="標題字體大小（像素）",
        required=True,
        placeholder="建議範圍：20-60",
        min_length=1,
        max_length=3
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            size = int(self.font_size.value)
            await self.panel.handle_setting_update(interaction, "title_font_size", size)
        except ValueError:
            await self.panel.send_error(interaction, "請輸入有效的數字")


class SetDescriptionFontSizeModal(BaseWelcomeModal, title="調整內容字體大小"):
    font_size = discord.ui.TextInput(
        label="內容字體大小（像素）",
        required=True,
        placeholder="建議範圍：12-40",
        min_length=1,
        max_length=3
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            size = int(self.font_size.value)
            await self.panel.handle_setting_update(interaction, "desc_font_size", size)
        except ValueError:
            await self.panel.send_error(interaction, "請輸入有效的數字")


class SetAvatarSizeModal(BaseWelcomeModal, title="調整頭像大小"):
    avatar_size = discord.ui.TextInput(
        label="頭像像素大小",
        required=True,
        placeholder="建議範圍：100-300",
        min_length=1,
        max_length=4
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            size = int(self.avatar_size.value)
            await self.panel.handle_setting_update(interaction, "avatar_size", size)
        except ValueError:
            await self.panel.send_error(interaction, "請輸入有效的數字")