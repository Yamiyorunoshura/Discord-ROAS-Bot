# welcome.py - 重構版本 (符合新架構)
# ============================================================
# 主要功能：
#  - 整合 WelcomeService 和 WelcomePanel
#  - 提供斜線指令介面
#  - 處理成員加入事件
#  - 向後相容性支援
# 
# 架構變更：
#  - 前後端分離設計
#  - 服務層和面板層分離
#  - 依賴注入和服務註冊
#  - 統一的錯誤處理
# ============================================================

import discord
from discord.ext import commands
from discord import app_commands
import logging
import os

from services.welcome import WelcomeService
from panels.welcome import WelcomePanel
from core.database_manager import get_database_manager
from core.exceptions import handle_errors

from config import (
    WELCOME_DB_PATH,
    WELCOME_LOG_PATH, 
    WELCOME_BG_DIR,
    WELCOME_FONTS_DIR,
    WELCOME_DEFAULT_FONT,
    is_allowed,
)

# 設定日誌記錄器
logger = logging.getLogger("welcome")
logger.setLevel(logging.INFO)


class WelcomeCog(commands.Cog):
    """
    歡迎系統 Cog - 重構版本
    
    使用前後端分離架構，整合 WelcomeService 和 WelcomePanel
    """
    
    def __init__(self, bot: commands.Bot):
        """
        初始化歡迎 Cog
        
        參數：
            bot: Discord 機器人實例
        """
        self.bot = bot
        
        # 服務和面板將在 setup_hook 中初始化
        self.welcome_service: WelcomeService = None
        self.welcome_panel: WelcomePanel = None
        
        # 配置參數
        self.config = {
            'bg_dir': WELCOME_BG_DIR,
            'fonts_dir': WELCOME_FONTS_DIR,
            'default_font': WELCOME_DEFAULT_FONT,
        }
        
        logger.info("WelcomeCog 初始化完成")
    
    async def cog_load(self) -> None:
        """Cog 載入時的設定"""
        try:
            # 嘗試從服務註冊表獲取已初始化的服務
            from core.base_service import service_registry
            
            # 首先嘗試從統一的服務啟動管理器獲取服務
            startup_manager = getattr(self.bot, 'startup_manager', None)
            if startup_manager and 'WelcomeService' in startup_manager.service_instances:
                self.welcome_service = startup_manager.service_instances['WelcomeService']
                logger.info("從服務啟動管理器獲取 WelcomeService")
            
            # 備用方案：從服務註冊表獲取
            elif service_registry.is_registered('WelcomeService'):
                self.welcome_service = service_registry.get_service('WelcomeService')
                logger.info("從服務註冊表獲取 WelcomeService")
            
            # 最後備用方案：自己初始化（向後相容）
            else:
                logger.info("未找到已註冊的 WelcomeService，自行初始化")
                db_manager = await get_database_manager()
                self.welcome_service = WelcomeService(db_manager, self.config)
                await service_registry.register_service(self.welcome_service, 'WelcomeService')
                await self.welcome_service.initialize()
            
            # 確保服務已初始化
            if not self.welcome_service.is_initialized:
                await self.welcome_service.initialize()
            
            # 初始化面板
            self.welcome_panel = WelcomePanel(self.welcome_service, self.config)
            
            logger.info("WelcomeCog 服務和面板已初始化")
            
        except Exception as e:
            logger.error(f"WelcomeCog 載入失敗：{e}")
            raise
    
    async def cog_unload(self) -> None:
        """Cog 卸載時的清理"""
        try:
            if self.welcome_service:
                await self.welcome_service.cleanup()
            logger.info("WelcomeCog 已清理")
        except Exception as e:
            logger.error(f"WelcomeCog 清理失敗：{e}")
    
    # ===== 斜線指令 =====
    
    @app_commands.command(name="歡迎訊息設定", description="設定歡迎訊息的所有內容和樣式")
    async def welcome_settings_command(self, interaction: discord.Interaction):
        """歡迎訊息設定指令"""
        if not is_allowed(interaction, "歡迎訊息設定"):
            await interaction.response.send_message("❌ 你沒有權限執行本指令。", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.response.send_message("❌ 此指令只能在伺服器中使用。", ephemeral=True)
            return
        
        # 委託給面板處理
        await self.welcome_panel.show_settings_panel(interaction)
    
    @app_commands.command(name="預覽歡迎訊息", description="預覽目前設定的歡迎訊息圖片效果")
    async def preview_welcome_message(self, interaction: discord.Interaction):
        """預覽歡迎訊息指令"""
        if not is_allowed(interaction, "預覽歡迎訊息"):
            await interaction.response.send_message("❌ 你沒有權限執行本指令。", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.response.send_message("❌ 此指令只能在伺服器中使用。", ephemeral=True)
            return
        
        # 委託給面板處理
        await self.welcome_panel.preview_welcome_message(interaction)
    
    # ===== 事件處理 =====
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """新成員加入時自動發送歡迎訊息"""
        try:
            if self.welcome_service:
                success = await self.welcome_service.process_member_join(member)
                if success:
                    logger.info(f"成功處理新成員加入：{member.guild.id} - {member.id}")
                else:
                    logger.warning(f"處理新成員加入失敗或未設定：{member.guild.id} - {member.id}")
        except Exception as e:
            logger.error(f"處理新成員加入時發生錯誤：{e}")
    
    # ===== 向後相容性方法 =====
    # 保留一些舊的方法名稱以確保向後相容性
    
    @handle_errors(log_errors=True)
    async def get_settings(self, guild_id: int):
        """向後相容：獲取歡迎設定"""
        if self.welcome_service:
            return await self.welcome_service.get_settings(guild_id)
        return None
    
    @handle_errors(log_errors=True)
    async def update_setting(self, guild_id: int, key: str, value):
        """向後相容：更新設定"""
        if self.welcome_service:
            return await self.welcome_service.update_setting(guild_id, key, value)
        return False
    
    @handle_errors(log_errors=True)
    async def generate_welcome_image(self, guild_id: int, member=None):
        """向後相容：生成歡迎圖片"""
        if self.welcome_service:
            welcome_image = await self.welcome_service.generate_welcome_image(guild_id, member)
            return welcome_image.image  # 返回 PIL Image 物件以保持相容性
        return None
    
    def clear_image_cache(self, guild_id=None):
        """向後相容：清除圖片快取"""
        if self.welcome_service:
            self.welcome_service.clear_cache(guild_id)

# ────────────────────────────
# setup
# ────────────────────────────
async def setup(bot: commands.Bot):
    """設定 WelcomeCog"""
    logger.info("執行 welcome setup()")
    await bot.add_cog(WelcomeCog(bot))