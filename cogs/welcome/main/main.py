"""
歡迎系統主要邏輯模組

此模組作為歡迎系統的協調中心，整合資料庫、渲染器和快取等組件
"""

import os
import io
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from typing import Dict, Any, Optional, Union

from config import (
    WELCOME_BG_DIR,
    is_allowed
)

from ..config.config import (
    CACHE_TIMEOUT,
    MAX_CACHE_SIZE
)
from ..database import WelcomeDB
from .renderer import WelcomeRenderer
from .cache import WelcomeCache
from ..panel import (
    SettingsView,
    BaseModal,
    SetChannelModal,
    SetTitleModal,
    SetDescModal,
    SetMsgModal,
    SetAvatarXModal,
    SetAvatarYModal,
    SetTitleYModal,
    SetDescYModal,
    SetTitleFontSizeModal,
    SetDescFontSizeModal,
    SetAvatarSizeModal
)

# 使用統一的核心模塊
from ...core import create_error_handler, setup_module_logger, ErrorCodes

# 設置模塊日誌記錄器
logger = setup_module_logger("welcome")
error_handler = create_error_handler("welcome", logger)


class WelcomeCog(commands.Cog):
    """歡迎系統 Cog"""
    
    def __init__(self, bot: commands.Bot):
        """
        初始化歡迎系統
        
        Args:
            bot: Discord Bot 實例
        """
        self.bot = bot
        self.db = WelcomeDB()
        self.renderer = WelcomeRenderer(WELCOME_BG_DIR)
        self.cache = WelcomeCache(timeout=CACHE_TIMEOUT, max_size=MAX_CACHE_SIZE)
        
        # 確保背景圖片目錄存在
        os.makedirs(WELCOME_BG_DIR, exist_ok=True)
        
        # 將對話框類別附加到 Cog 上，以便在 SettingsView 中使用
        self.BaseModal = BaseModal
        self.SetChannelModal = SetChannelModal
        self.SetTitleModal = SetTitleModal
        self.SetDescModal = SetDescModal
        self.SetMsgModal = SetMsgModal
        self.SetAvatarXModal = SetAvatarXModal
        self.SetAvatarYModal = SetAvatarYModal
        self.SetTitleYModal = SetTitleYModal
        self.SetDescYModal = SetDescYModal
        self.SetTitleFontSizeModal = SetTitleFontSizeModal
        self.SetDescFontSizeModal = SetDescFontSizeModal
        self.SetAvatarSizeModal = SetAvatarSizeModal
        
        logger.info("歡迎系統已初始化")
    
    async def _get_welcome_channel(self, guild_id: int) -> Optional[discord.TextChannel]:
        """
        取得設定的歡迎頻道
        
        Args:
            guild_id: Discord 伺服器 ID
            
        Returns:
            Optional[discord.TextChannel]: 歡迎頻道，如果未設定或找不到則為 None
        """
        settings = await self.db.get_settings(guild_id)
        channel_id = settings.get("channel_id")
        
        if not channel_id:
            return None
        
        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return None
        
        return channel
    
    async def _generate_welcome_image(
        self, 
        guild_id: int, 
        member: discord.Member,
        force_refresh: bool = False
    ) -> Optional[io.BytesIO]:
        """
        生成歡迎圖片
        
        Args:
            guild_id: Discord 伺服器 ID
            member: Discord 成員物件
            force_refresh: 是否強制重新生成，忽略快取
            
        Returns:
            Optional[io.BytesIO]: 生成的圖片，如果失敗則為 None
        """
        # 檢查快取
        if not force_refresh:
            cached = self.cache.get(guild_id)
            if cached:
                logger.debug(f"使用快取的歡迎圖片：伺服器 {guild_id}")
                return cached
        
        # 取得設定
        settings = await self.db.get_settings(guild_id)
        bg_path = await self.db.get_background_path(guild_id)
        
        # 如果有背景圖片，確保路徑正確
        if bg_path:
            bg_path = os.path.join(WELCOME_BG_DIR, os.path.basename(bg_path))
            if not os.path.exists(bg_path):
                bg_path = None
        
        # 生成圖片
        image = await self.renderer.generate_welcome_image(member, settings, bg_path)
        
        # 快取圖片
        if image:
            self.cache.set(guild_id, image)
            # 重新取得一份，因為 set 操作會修改原始資料
            return self.cache.get(guild_id)
        
        return None
    
    def _safe_int(self, value: str, default: int = 0) -> int:
        """
        安全地將字串轉換為整數
        
        Args:
            value: 要轉換的字串
            default: 轉換失敗時的預設值
            
        Returns:
            int: 轉換後的整數
        """
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def clear_image_cache(self, guild_id: Optional[int] = None) -> None:
        """
        清除圖片快取
        
        Args:
            guild_id: 要清除的伺服器 ID，如果為 None 則清除所有快取
        """
        self.cache.clear(guild_id)
    
    async def send_welcome_message(
        self, 
        member: discord.Member,
        channel: Optional[discord.TextChannel] = None
    ) -> bool:
        """
        發送歡迎訊息
        
        Args:
            member: 新加入的成員
            channel: 指定的發送頻道，如果為 None 則使用設定的頻道
            
        Returns:
            bool: 是否成功發送
        """
        guild_id = member.guild.id
        
        # 如果沒有指定頻道，使用設定的頻道
        if channel is None:
            channel = await self._get_welcome_channel(guild_id)
            if channel is None:
                logger.debug(f"伺服器 {guild_id} 未設定歡迎頻道")
                return False
        
        try:
            # 取得設定
            settings = await self.db.get_settings(guild_id)
            
            # 生成圖片
            image = await self._generate_welcome_image(guild_id, member)
            
            # 渲染訊息
            message = settings.get("message", "歡迎 {member.mention} 加入 {guild.name}！")
            rendered_message = self.renderer.render_message(
                member, member.guild, channel, message
            )
            
            # 發送訊息
            if image:
                await channel.send(
                    content=rendered_message,
                    file=discord.File(fp=image, filename="welcome.png")
                )
            else:
                await channel.send(content=rendered_message)
            
            logger.info(f"已發送歡迎訊息：伺服器 {guild_id}，成員 {member.id}")
            return True
            
        except Exception as exc:
            logger.error(f"發送歡迎訊息失敗：伺服器 {guild_id}，成員 {member.id}", exc_info=True)
            return False
    
    async def handle_background_upload(
        self, 
        interaction: discord.Interaction,
        attachment: discord.Attachment
    ) -> bool:
        """
        處理背景圖片上傳
        
        Args:
            interaction: Discord 互動物件
            attachment: 上傳的附件
            
        Returns:
            bool: 是否成功上傳
        """
        guild_id = interaction.guild_id
        if not guild_id:
            return False
        
        # 檢查檔案類型
        if not attachment.content_type or not attachment.content_type.startswith(('image/png', 'image/jpeg')):
            await interaction.response.send_message("❌ 只接受 PNG 或 JPG 格式的圖片", ephemeral=True)
            return False
        
        # 檢查檔案大小
        if attachment.size > 5 * 1024 * 1024:  # 5MB
            await interaction.response.send_message("❌ 圖片大小不能超過 5MB", ephemeral=True)
            return False
        
        try:
            # 下載圖片
            image_data = await attachment.read()
            
            # 儲存圖片
            filename = f"bg_{guild_id}_{attachment.filename}"
            file_path = os.path.join(WELCOME_BG_DIR, filename)
            
            with open(file_path, "wb") as f:
                f.write(image_data)
            
            # 更新資料庫
            await self.db.update_welcome_background(guild_id, file_path)
            
            # 清除快取
            self.clear_image_cache(guild_id)
            
            logger.info(f"已上傳背景圖片：伺服器 {guild_id}，檔案 {filename}")
            return True
            
        except Exception as exc:
            logger.error(f"上傳背景圖片失敗：伺服器 {guild_id}", exc_info=True)
            return False
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """
        成員加入事件處理
        
        Args:
            member: 新加入的成員
        """
        await self.send_welcome_message(member)
    
    @app_commands.command(name="歡迎訊息設定", description="設定歡迎訊息的所有內容和樣式")
    @app_commands.guild_only()
    @app_commands.check(is_allowed)
    async def welcome_settings_command(self, interaction: discord.Interaction) -> None:
        """
        歡迎訊息設定指令
        
        Args:
            interaction: Discord 互動物件
        """
        if not interaction.guild_id or not interaction.guild:
            await interaction.response.send_message("❌ 此功能只能在伺服器中使用", ephemeral=True)
            return
        
        # 取得設定
        settings = await self.db.get_settings(interaction.guild_id)
        
        # 建立設定面板
        from ..panel.embeds.settings_embed import build_settings_embed
        embed = await build_settings_embed(self, interaction.guild, settings)
        
        # 建立視圖
        view = SettingsView(self)
        
        # 發送面板
        await interaction.response.send_message(embed=embed, view=view)
        
        # 取得面板訊息
        panel_msg = await interaction.original_response()
        view.panel_msg = panel_msg
    
    @app_commands.command(name="預覽歡迎訊息", description="預覽目前設定的歡迎訊息圖片效果")
    @app_commands.guild_only()
    async def preview_welcome_message(self, interaction: discord.Interaction) -> None:
        """
        預覽歡迎訊息指令
        
        Args:
            interaction: Discord 互動物件
        """
        if not interaction.guild_id or not interaction.guild:
            await interaction.response.send_message("❌ 此功能只能在伺服器中使用", ephemeral=True)
            return
        
        # 確保使用者是成員物件
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ 無法取得成員資訊", ephemeral=True)
            return
        
        await interaction.response.defer(thinking=True)
        
        # 生成預覽圖片
        member = interaction.user
        image = await self._generate_welcome_image(
            interaction.guild_id, member, force_refresh=True
        )
        
        if image:
            # 取得設定
            settings = await self.db.get_settings(interaction.guild_id)
            
            # 渲染訊息
            message = settings.get("message", "歡迎 {member.mention} 加入 {guild.name}！")
            
            # 確保頻道是文字頻道
            channel = None
            if isinstance(interaction.channel, discord.TextChannel):
                channel = interaction.channel
                
            rendered_message = self.renderer.render_message(
                member, interaction.guild, channel, message
            )
            
            await interaction.followup.send(
                content=f"**預覽效果**\n{rendered_message}",
                file=discord.File(fp=image, filename="welcome_preview.png")
            )
        else:
            await interaction.followup.send("❌ 生成預覽圖片失敗") 