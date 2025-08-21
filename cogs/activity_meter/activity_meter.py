# activity_meter.py - 重構版本 (符合新架構)
# ============================================================
# 主要功能：
#  - 整合 ActivityService 和 ActivityPanel
#  - 提供斜線指令介面
#  - 處理訊息事件以更新活躍度
#  - 自動播報機制
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
import time
from datetime import datetime, timezone

from services.activity import ActivityService
from panels.activity import ActivityPanel
from core.database_manager import get_database_manager
from core.exceptions import handle_errors

from config import (
    ACTIVITY_DB_PATH,
    TW_TZ,
    ACT_REPORT_HOUR,
    is_allowed,
)

# 設定日誌記錄器
logger = logging.getLogger("activity_meter")
logger.setLevel(logging.INFO)

class ActivityMeterCog(commands.Cog):
    """
    活躍度系統 Cog - 重構版本
    
    使用前後端分離架構，整合 ActivityService 和 ActivityPanel
    """
    
    def __init__(self, bot: commands.Bot):
        """
        初始化活躍度 Cog
        
        參數：
            bot: Discord 機器人實例
        """
        self.bot = bot
        
        # 服務和面板將在 cog_load 中初始化
        self.activity_service: ActivityService = None
        self.activity_panel: ActivityPanel = None
        
        # 配置參數
        self.config = {
            'db_path': ACTIVITY_DB_PATH,
            'timezone': TW_TZ,
            'report_hour': ACT_REPORT_HOUR,
        }
        
        logger.info("ActivityMeterCog 初始化完成")

    async def cog_load(self) -> None:
        """Cog 載入時的設定"""
        try:
            # 嘗試從服務註冊表獲取已初始化的服務
            from core.base_service import service_registry
            
            # 首先嘗試從統一的服務啟動管理器獲取服務
            startup_manager = getattr(self.bot, 'startup_manager', None)
            if startup_manager and 'ActivityService' in startup_manager.service_instances:
                self.activity_service = startup_manager.service_instances['ActivityService']
                logger.info("從服務啟動管理器獲取 ActivityService")
            
            # 備用方案：從服務註冊表獲取
            elif service_registry.is_registered('ActivityService'):
                self.activity_service = service_registry.get_service('ActivityService')
                logger.info("從服務註冊表獲取 ActivityService")
            
            # 最後備用方案：自己初始化（向後相容）
            else:
                logger.info("未找到已註冊的 ActivityService，自行初始化")
                db_manager = await get_database_manager()
                self.activity_service = ActivityService(db_manager, self.config)
                await service_registry.register_service(self.activity_service, 'ActivityService')
                await self.activity_service.initialize()
            
            # 確保服務已初始化
            if not self.activity_service.is_initialized:
                await self.activity_service.initialize()
            
            # 初始化面板
            self.activity_panel = ActivityPanel(self.activity_service, self.config)
            
            # 啟動自動播報任務
            self.auto_report.start()
            
            logger.info("ActivityMeterCog 服務和面板已初始化")
            
        except Exception as e:
            logger.error(f"ActivityMeterCog 載入失敗：{e}")
            raise
    
    async def cog_unload(self) -> None:
        """Cog 卸載時的清理"""
        try:
            # 停止自動播報任務
            self.auto_report.cancel()
            
            if self.activity_service:
                await self.activity_service.cleanup()
                
            logger.info("ActivityMeterCog 已清理")
        except Exception as e:
            logger.error(f"ActivityMeterCog 清理失敗：{e}")

    # ===== 斜線指令 =====

    @app_commands.command(name="活躍度", description="查看活躍度（進度條）")
    async def 活躍度(self, interaction: discord.Interaction, 成員: discord.Member = None):
        """查看活躍度指令"""
        if not is_allowed(interaction, "活躍度"):
            await interaction.response.send_message("❌ 你沒有權限執行本指令。", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.response.send_message("❌ 此指令只能在伺服器中使用。", ephemeral=True)
            return
        
        # 委託給面板處理
        await self.activity_panel.show_activity_bar(interaction, 成員)

    @app_commands.command(name="今日排行榜", description="查看今日訊息數排行榜")
    async def 今日排行榜(self, interaction: discord.Interaction, 名次: int = 10):
        """今日排行榜指令"""
        if not is_allowed(interaction, "今日排行榜"):
            await interaction.response.send_message("❌ 你沒有權限執行本指令。", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.response.send_message("❌ 此指令只能在伺服器中使用。", ephemeral=True)
            return
        
        # 委託給面板處理
        await self.activity_panel.display_leaderboard(interaction, 名次)

    @app_commands.command(name="設定排行榜頻道", description="設定每日自動播報排行榜的頻道")
    @app_commands.describe(頻道="要播報到哪個文字頻道")
    async def 設定排行榜頻道(self, interaction: discord.Interaction, 頻道: discord.TextChannel):
        """設定排行榜頻道指令"""
        if not is_allowed(interaction, "設定排行榜頻道"):
            await interaction.response.send_message("❌ 你沒有權限執行本指令。", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.response.send_message("❌ 此指令只能在伺服器中使用。", ephemeral=True)
            return
        
        # 委託給面板處理
        await self.activity_panel.set_report_channel(interaction, 頻道)
    
    @app_commands.command(name="活躍度設定", description="查看或修改活躍度系統設定")
    async def 活躍度設定(self, interaction: discord.Interaction):
        """活躍度設定指令"""
        if not is_allowed(interaction, "活躍度設定"):
            await interaction.response.send_message("❌ 你沒有權限執行本指令。", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.response.send_message("❌ 此指令只能在伺服器中使用。", ephemeral=True)
            return
        
        # 委託給面板處理
        await self.activity_panel.show_settings_panel(interaction)

    # ===== 自動播報 =====
    
    @tasks.loop(minutes=1)
    async def auto_report(self):
        """自動播報任務"""
        try:
            now = datetime.now(TW_TZ)
            
            # 只在指定時間的整點播報
            if now.hour != ACT_REPORT_HOUR or now.minute != 0:
                return
            
            # 獲取所有需要播報的伺服器
            if not self.activity_service:
                return
            
            # 查詢所有設定了播報頻道的伺服器
            report_channels = await self.activity_service.db_manager.fetchall(
                "SELECT guild_id, report_channel_id FROM activity_settings WHERE report_channel_id IS NOT NULL AND auto_report_enabled = 1"
            )
            
            # 也檢查舊的播報頻道表（向後相容）
            old_report_channels = await self.activity_service.db_manager.fetchall(
                "SELECT guild_id, channel_id FROM activity_report_channel"
            )
            
            # 合併頻道列表
            all_channels = set()
            for row in report_channels:
                all_channels.add((row['guild_id'], row['report_channel_id']))
            for row in old_report_channels:
                all_channels.add((row['guild_id'], row['channel_id']))
            
            # 為每個伺服器發送報告
            for guild_id, channel_id in all_channels:
                try:
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        continue
                    
                    channel = guild.get_channel(channel_id)
                    if not channel or not isinstance(channel, discord.TextChannel):
                        continue
                    
                    # 發送活躍度報告
                    success = await self.activity_panel.send_activity_report(channel, guild_id)
                    
                    if success:
                        logger.info(f"成功發送自動播報到 {guild_id}:{channel_id}")
                    else:
                        logger.warning(f"發送自動播報失敗到 {guild_id}:{channel_id}")
                        
                except Exception as e:
                    logger.error(f"自動播報處理失敗 {guild_id}:{channel_id} - {e}")
                    
        except Exception as e:
            logger.error(f"自動播報任務執行失敗：{e}")

    @auto_report.before_loop
    async def _wait_ready(self):
        """等待機器人就緒"""
        await self.bot.wait_until_ready()
        
        # 等待服務初始化完成
        while not self.activity_service or not self.activity_service.is_initialized:
            await asyncio.sleep(1)
            
        logger.info("活躍度自動播報任務已啟動")

    # ===== 事件處理 =====
    
    @commands.Cog.listener("on_message")
    async def on_message(self, message: discord.Message):
        """處理訊息事件，更新活躍度"""
        try:
            # 忽略機器人訊息和私人訊息
            if message.author.bot or not message.guild:
                return
            
            # 確保服務已初始化
            if not self.activity_service or not self.activity_service.is_initialized:
                return
            
            # 更新用戶活躍度
            new_score = await self.activity_service.update_activity(
                message.author.id,
                message.guild.id,
                message
            )
            
            logger.debug(f"更新活躍度：用戶 {message.author.id} 在 {message.guild.id}，新分數 {new_score:.1f}")
            
        except Exception as e:
            logger.error(f"處理訊息事件時發生錯誤：{e}")
    
    # ===== 向後相容性方法 =====
    # 保留一些舊的方法名稱以確保向後相容性
    
    @handle_errors(log_errors=True)
    async def get_activity_score(self, user_id: int, guild_id: int) -> float:
        """向後相容：獲取活躍度分數"""
        if self.activity_service:
            return await self.activity_service.get_activity_score(user_id, guild_id)
        return 0.0
    
    @handle_errors(log_errors=True)
    async def get_leaderboard(self, guild_id: int, limit: int = 10) -> list:
        """向後相容：獲取排行榜"""
        if self.activity_service:
            leaderboard = await self.activity_service.get_daily_leaderboard(guild_id, limit)
            # 轉換為舊格式
            return [(entry.user_id, entry.daily_messages) for entry in leaderboard]
        return []

# ────────────────────────────
# setup
# ────────────────────────────
async def setup(bot: commands.Bot):
    """設定 ActivityMeterCog"""
    logger.info("執行 activity_meter setup()")
    await bot.add_cog(ActivityMeterCog(bot))