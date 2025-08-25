# message_listener.py - 重構版本 (符合新架構)
# ============================================================
# 主要功能：
#  - 整合 MessageService 和 MessagePanel
#  - 提供斜線指令介面
#  - 處理訊息監聽事件
#  - 向後相容性支援
# 
# 架構變更：
#  - 前後端分離設計
#  - 服務層和面板層分離
#  - 依賴注入和服務註冊
#  - 統一的錯誤處理
# ============================================================

import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
import datetime

from services.message import MessageService
from panels.message import MessagePanel
from core.database_manager import get_database_manager
from core.exceptions import handle_errors

from config import MESSAGE_DB_PATH, MESSAGE_LOG_PATH, is_allowed

# 設定日誌記錄器
logger = logging.getLogger("message_listener")
logger.setLevel(logging.INFO)


class MessageListenerCog(commands.Cog):
    """
    訊息監聽 Cog - 重構版本
    
    使用前後端分離架構，整合 MessageService 和 MessagePanel
    """
    
    def __init__(self, bot: commands.Bot):
        """
        初始化訊息監聽 Cog
        
        參數：
            bot: Discord 機器人實例
        """
        self.bot = bot
        
        # 服務和面板將在 cog_load 中初始化
        self.message_service: MessageService = None
        self.message_panel: MessagePanel = None
        
        # 配置參數
        self.config = {
            'db_path': MESSAGE_DB_PATH,
            'log_path': MESSAGE_LOG_PATH,
            'render': {
                'chat_width': 800,
                'max_height': 2000,
                'avatar_size': 40,
                'max_cached_messages': 10,
                'max_cache_time': 600
            }
        }
        
        logger.info("MessageListenerCog 初始化完成")
    
    async def cog_load(self) -> None:
        """Cog 載入時的設定"""
        try:
            # 嘗試從服務註冊表獲取已初始化的服務
            from core.base_service import service_registry
            
            # 首先嘗試從統一的服務啟動管理器獲取服務
            startup_manager = getattr(self.bot, 'startup_manager', None)
            if startup_manager and 'MessageService' in startup_manager.service_instances:
                self.message_service = startup_manager.service_instances['MessageService']
                logger.info("從服務啟動管理器獲取 MessageService")
            
            # 備用方案：從服務註冊表獲取
            elif service_registry.is_registered('MessageService'):
                self.message_service = service_registry.get_service('MessageService')
                logger.info("從服務註冊表獲取 MessageService")
            
            # 最後備用方案：自己初始化（向後相容）
            else:
                logger.info("未找到已註冊的 MessageService，自行初始化")
                db_manager = await get_database_manager()
                self.message_service = MessageService(db_manager, self.config)
                await service_registry.register_service(self.message_service, 'MessageService')
                await self.message_service.initialize()
            
            # 確保服務已初始化
            if not self.message_service.is_initialized:
                await self.message_service.initialize()
            
            # 初始化面板
            self.message_panel = MessagePanel(self.message_service, self.config)
            
            # 啟動定期任務
            self.purge_task.start()
            
            logger.info("MessageListenerCog 服務和面板已初始化")
            
        except Exception as e:
            logger.error(f"MessageListenerCog 載入失敗：{e}")
            raise
    
    async def cog_unload(self) -> None:
        """Cog 卸載時的清理"""
        try:
            # 停止定期任務
            self.purge_task.cancel()
            
            if self.message_service:
                await self.message_service.cleanup()
            logger.info("MessageListenerCog 已清理")
        except Exception as e:
            logger.error(f"MessageListenerCog 清理失敗：{e}")
    
    # ===== 斜線指令 =====
    
    @app_commands.command(name="訊息監聽設定", description="管理訊息監聽和記錄設定")
    async def message_settings_command(self, interaction: discord.Interaction):
        """訊息監聽設定指令"""
        if not is_allowed(interaction, "訊息監聽設定"):
            await interaction.response.send_message("❌ 你沒有權限執行本指令。", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.response.send_message("❌ 此指令只能在伺服器中使用。", ephemeral=True)
            return
        
        # 委託給面板處理
        await self.message_panel.show_settings_panel(interaction)
    
    @app_commands.command(name="搜尋訊息", description="搜尋歷史訊息記錄")
    async def search_messages_command(self, interaction: discord.Interaction):
        """搜尋訊息指令"""
        if not is_allowed(interaction, "搜尋訊息"):
            await interaction.response.send_message("❌ 你沒有權限執行本指令。", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.response.send_message("❌ 此指令只能在伺服器中使用。", ephemeral=True)
            return
        
        # 委託給面板處理
        await self.message_panel.show_search_panel(interaction)
    
    @app_commands.command(name="頻道管理", description="管理訊息監聽頻道列表")
    async def channel_management_command(self, interaction: discord.Interaction):
        """頻道管理指令"""
        if not is_allowed(interaction, "頻道管理"):
            await interaction.response.send_message("❌ 你沒有權限執行本指令。", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.response.send_message("❌ 此指令只能在伺服器中使用。", ephemeral=True)
            return
        
        # 委託給面板處理
        await self.message_panel.show_channel_management(interaction)
    
    # ===== 事件處理 =====
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """訊息接收事件"""
        try:
            # 忽略機器人訊息
            if message.author.bot:
                return
            
            # 忽略私訊
            if not message.guild:
                return
            
            # 如果服務可用，儲存訊息
            if self.message_service:
                success = await self.message_service.save_message(message)
                if success:
                    logger.debug(f"已儲存訊息：{message.id}")
        
        except Exception as e:
            logger.error(f"處理訊息事件時發生錯誤：{e}")
    
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """訊息編輯事件"""
        try:
            # 忽略機器人訊息
            if after.author.bot:
                return
            
            # 忽略私訊
            if not after.guild:
                return
            
            # 如果服務可用且設定允許記錄編輯
            if self.message_service:
                settings = await self.message_service.get_settings()
                if settings.record_edits:
                    # 儲存編輯後的訊息
                    await self.message_service.save_message(after)
                    logger.debug(f"已記錄訊息編輯：{after.id}")
        
        except Exception as e:
            logger.error(f"處理訊息編輯事件時發生錯誤：{e}")
    
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """訊息刪除事件"""
        try:
            # 忽略機器人訊息
            if message.author.bot:
                return
            
            # 忽略私訊
            if not message.guild:
                return
            
            # 如果服務可用且設定允許記錄刪除
            if self.message_service:
                settings = await self.message_service.get_settings()
                if settings.record_deletes:
                    # 記錄刪除的訊息（可以在這裡添加特殊標記）
                    # 資料庫優化建議：考慮在未來版本中添加 deleted 欄位
                    # 這樣可以實現軟刪除，保留歷史記錄用於審計和分析
                    logger.info(f"訊息已刪除：{message.id} 在頻道 {message.channel.id}")
        
        except Exception as e:
            logger.error(f"處理訊息刪除事件時發生錯誤：{e}")
    
    # ===== 定期任務 =====
    
    @tasks.loop(time=datetime.time(hour=0, minute=0))  # 每天午夜執行
    async def purge_task(self):
        """每日清理舊訊息任務"""
        try:
            if self.message_service:
                deleted_count = await self.message_service.purge_old_messages()
                logger.info(f"定期清理完成：刪除了 {deleted_count} 條舊訊息")
        except Exception as e:
            logger.error(f"定期清理任務失敗：{e}")
    
    # ===== 向後相容性方法 =====
    # 保留一些舊的方法名稱以確保向後相容性
    
    @handle_errors(log_errors=True)
    async def get_setting(self, key: str, default: str = "") -> str:
        """向後相容：獲取設定值"""
        if self.message_service:
            settings = await self.message_service.get_settings()
            return getattr(settings, key, default)
        return default
    
    @handle_errors(log_errors=True)
    async def set_setting(self, key: str, value: str) -> bool:
        """向後相容：設定值"""
        if self.message_service:
            return await self.message_service.update_setting(key, value)
        return False
    
    @handle_errors(log_errors=True)
    async def save_message(self, message: discord.Message) -> bool:
        """向後相容：儲存訊息"""
        if self.message_service:
            return await self.message_service.save_message(message)
        return False
    
    @handle_errors(log_errors=True)
    async def is_channel_monitored(self, channel_id: int) -> bool:
        """向後相容：檢查頻道是否被監聽"""
        if self.message_service:
            return await self.message_service.is_channel_monitored(channel_id)
        return False
    
    @handle_errors(log_errors=True)
    async def refresh_settings(self):
        """向後相容：重新載入設定"""
        if self.message_service:
            await self.message_service.refresh_settings()
    
    @handle_errors(log_errors=True)
    async def refresh_monitored_channels(self):
        """向後相容：重新載入監聽頻道"""
        if self.message_service:
            await self.message_service.refresh_monitored_channels()


# ────────────────────────────
# setup
# ────────────────────────────
async def setup(bot: commands.Bot):
    """設定 MessageListenerCog"""
    logger.info("執行 message_listener setup()")
    await bot.add_cog(MessageListenerCog(bot))