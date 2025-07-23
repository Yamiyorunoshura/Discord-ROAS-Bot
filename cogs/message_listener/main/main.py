"""
訊息監聽系統主要邏輯協調中心
- 作為模組的核心，協調各個子模組的工作
- 處理指令和事件
- 管理訊息處理流程
"""

import asyncio
import datetime as dt
import logging
import traceback
from typing import Optional, List, Dict, Any, Union

import discord
from discord import app_commands
from discord.ext import commands, tasks

from ..config.config import is_allowed, MAX_CACHED_MESSAGES, MAX_CACHE_TIME
from ..database.database import MessageListenerDB
from .cache import MessageCache
from .renderer import EnhancedMessageRenderer as MessageRenderer

# 使用統一的核心模塊
from ...core import create_error_handler, setup_module_logger, ErrorCodes

# 設置模塊日誌記錄器
logger = setup_module_logger("message_listener")
error_handler = create_error_handler("message_listener", logger)

class MessageListenerCog(commands.Cog):
    """
    訊息監聽與日誌管理 Cog
    
    提供完整的訊息監控、記錄、搜尋和轉播功能，
    支援多頻道監聽和智能表情處理。
    """
    
    def __init__(self, bot: commands.Bot):
        """
        初始化訊息監聽系統
        
        Args:
            bot: Discord 機器人實例
        """
        self.bot = bot
        self.db = MessageListenerDB()
        self.message_cache = MessageCache()
        self.renderer = MessageRenderer()
        self._settings_cache = {}
        self.monitored_channels = []
        self._views = []  # 追蹤所有活動的視圖
        self._last_refresh = 0  # 上次重新整理設定的時間戳
        
    async def cog_load(self):
        """Cog 載入時的初始化"""
        try:
            await self.db.init_db()
            await self.refresh_settings()
            await self.refresh_monitored_channels()  # 初始化監聽頻道快取
            self.purge_task.start()  # 啟動清理任務
            self.check_cache_task.start()  # 啟動緩存檢查任務
            logger.info("【訊息監聽】Cog 載入完成")
        except Exception as exc:
            logger.error(f"【訊息監聽】Cog 載入失敗: {exc}")
            raise

    async def cog_unload(self):
        """Cog 卸載時的清理"""
        try:
            self.purge_task.cancel()  # 停止清理任務
            self.check_cache_task.cancel()  # 停止緩存檢查任務
            await self.db.close()
            logger.info("【訊息監聽】Cog 卸載完成")
        except Exception as exc:
            logger.error(f"【訊息監聽】Cog 卸載失敗: {exc}")

    async def refresh_settings(self):
        """重新整理設定（含快取機制）"""
        try:
            # 避免頻繁重新整理
            current_time = dt.datetime.utcnow().timestamp()
            if current_time - self._last_refresh < 60:  # 1分鐘內不重複整理
                return
                
            # 取得所有設定
            rows = await self.db.select("SELECT setting_name, setting_value FROM settings")
            self._settings_cache = {row['setting_name']: row['setting_value'] for row in rows}
            self._last_refresh = current_time
            logger.debug("【訊息監聽】設定快取已更新")
        except Exception as exc:
            logger.error(f"【訊息監聽】重新整理設定失敗: {exc}")

    async def refresh_monitored_channels(self):
        """重新整理監聽頻道快取"""
        try:
            self.monitored_channels = await self.db.get_monitored_channels()
            logger.debug(f"【訊息監聽】監聽頻道快取已更新：{len(self.monitored_channels)} 個頻道")
        except Exception as exc:
            logger.error(f"【訊息監聽】重新整理監聽頻道失敗: {exc}")

    async def get_setting(self, key: str, default: str = "") -> str:
        """
        取得設定值（使用快取）
        
        Args:
            key: 設定鍵
            default: 預設值
            
        Returns:
            str: 設定值
        """
        await self.refresh_settings()
        return self._settings_cache.get(key, default)

    async def set_setting(self, key: str, value: str):
        """
        設定值
        
        Args:
            key: 設定鍵
            value: 設定值
        """
        try:
            await self.db.set_setting(key, value)
            self._settings_cache[key] = value
        except Exception as exc:
            logger.error(f"【訊息監聽】設定值失敗：{key}", exc_info=True)

    async def save_message(self, message: discord.Message):
        """
        儲存訊息到資料庫
        
        Args:
            message: Discord 訊息
        """
        try:
            await self.db.save_message(message)
        except Exception as exc:
            logger.error(f"【訊息監聽】儲存訊息失敗：{message.id}", exc_info=True)

    @tasks.loop(time=dt.time(hour=0, minute=0))
    async def purge_task(self):
        """每日清理舊訊息任務"""
        try:
            retention_days = int(await self.get_setting("retention_days", "7"))
            await self.db.purge_old_messages(retention_days)
        except Exception as exc:
            logger.error("【訊息監聽】清理任務失敗", exc_info=True)

    @tasks.loop(seconds=30)
    async def check_cache_task(self):
        """定期檢查緩存，處理超時訊息"""
        try:
            # 檢查所有需要處理的頻道
            for channel_id in self.message_cache.check_all_channels():
                await self.process_channel_messages(channel_id)
        except Exception as exc:
            logger.error("【訊息監聽】檢查訊息緩存失敗", exc_info=True)

    async def process_channel_messages(self, channel_id: int):
        """
        處理頻道緩存的訊息，渲染並發送圖片
        
        Args:
            channel_id: 頻道ID
        """
        try:
            # 取得緩存的訊息
            messages = self.message_cache.get_messages(channel_id)
            if not messages:
                return
                
            # 取得日誌頻道
            guild = self.bot.get_guild(messages[0].guild.id) if messages[0].guild else None
            log_channel = await self._get_log_channel(guild)
            if not log_channel:
                logger.warning(f"【訊息監聽】找不到日誌頻道，無法處理頻道 {channel_id} 的訊息")
                return
                
            # 渲染圖片
            image_path = await self.renderer.render_messages(messages)
            if not image_path:
                logger.error(f"【訊息監聽】渲染頻道 {channel_id} 的訊息失敗")
                return
                
            try:
                # 取得來源頻道資訊
                source_channel = self.bot.get_channel(channel_id)
                channel_name = f"#{source_channel.name}" if isinstance(source_channel, discord.TextChannel) else f"頻道 {channel_id}"
                
                # 發送圖片
                await log_channel.send(
                    f"📢 **{len(messages)} 條來自 {channel_name} 的訊息**",
                    file=discord.File(image_path)
                )
                
                logger.info(f"【訊息監聽】已渲染並發送頻道 {channel_id} 的 {len(messages)} 條訊息")
            finally:
                # 清理臨時檔案
                from . import utils
                utils.safe_remove_file(image_path)
                
            # 清空該頻道的緩存
            self.message_cache.clear_channel(channel_id)
                
        except Exception as exc:
            logger.error(f"【訊息監聽】處理頻道 {channel_id} 的訊息失敗", exc_info=True)
            # 發生錯誤時清空緩存，避免重複處理
            self.message_cache.clear_channel(channel_id)

    # ───────── Slash 指令 ─────────
    @app_commands.command(name="訊息日誌設定", description="設定訊息日誌功能")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def cmd_setting(self, interaction: discord.Interaction):
        """訊息日誌設定指令"""
        try:
            # 確保快取是最新的
            await self.refresh_settings()
            await self.refresh_monitored_channels()
            
            # 動態導入面板視圖類別
            from ..panel.main_view import SettingsView
            
            # 創建並發送設定面板
            view = SettingsView(self)
            await interaction.response.send_message("✅ 訊息日誌設定面板", view=view)
            
            # 儲存訊息引用，用於關閉按鈕
            view.message = await interaction.original_response()
            
            # 將視圖添加到追蹤列表
            self._views.append(view)
        except Exception as exc:
            logger.error("【訊息監聽】載入設定失敗", exc_info=True)
            await interaction.response.send_message("❌ 載入設定失敗，請稍後再試。", ephemeral=True)

    @app_commands.command(name="搜尋訊息", description="查詢最近訊息（支援關鍵字、頻道篩選和截圖搜尋）")
    @app_commands.describe(
        keyword="關鍵字（可空）", 
        channel="限制搜尋的頻道（可空）",
        hours="搜尋時間範圍（小時，預設24）",
        render_image="是否渲染為截圖（預設為否）"
    )
    async def cmd_search(
        self,
        interaction: discord.Interaction,
        keyword: str | None = None,
        channel: discord.TextChannel | None = None,
        hours: int = 24,
        render_image: bool = False,
    ):
        """搜尋訊息指令"""
        # 改進權限檢查 - 允許在日誌頻道中使用或有指定權限
        log_channel_id = await self.get_setting("log_channel_id", "")
        is_in_log_channel = log_channel_id and str(interaction.channel_id) == log_channel_id
        has_permission = is_allowed(interaction, "搜尋訊息")
        
        if not (has_permission or is_in_log_channel):
            await interaction.response.send_message("❌ 你沒有權限執行本指令。必須在日誌頻道中使用或擁有搜尋權限。", ephemeral=True)
            return
            
        try:
            await interaction.response.defer()
            
            # 執行搜尋
            results = await self.db.search_messages(
                keyword=keyword,
                channel_id=channel.id if channel else None,
                hours=hours,
                limit=100
            )
            
            if not results:
                await interaction.followup.send("🔍 沒有找到符合條件的訊息。", ephemeral=True)
                return
            
            # 處理截圖渲染請求
            if render_image and results:
                await interaction.followup.send("🖼️ 正在渲染搜尋結果截圖...", ephemeral=True)
                
                # 導入搜尋結果處理類別
                from .search_processor import process_search_results
                
                # 處理搜尋結果
                image_path = await process_search_results(self.bot, self.renderer, results[:5])
                
                if image_path:
                    try:
                        await interaction.followup.send(
                            f"🔍 搜尋結果截圖（關鍵字: {keyword or '無'}, 頻道: {channel.mention if channel else '全部'}）",
                            file=discord.File(image_path)
                        )
                    finally:
                        from . import utils
                        utils.safe_remove_file(image_path)
                else:
                    await interaction.followup.send("❌ 渲染搜尋結果失敗，請稍後再試。", ephemeral=True)
                    
                return
            
            # 導入分頁視圖類別
            from ..panel.search_view import SearchPaginationView
            
            # 創建分頁視圖
            view = SearchPaginationView(self, results, interaction.user.id)
            await view.send_initial_page(interaction)
            
        except Exception as exc:
            logger.error("【訊息監聽】搜尋訊息失敗", exc_info=True)
            await interaction.followup.send("❌ 搜尋訊息失敗，請稍後再試。", ephemeral=True)

    async def _get_log_channel(self, guild: discord.Guild | None) -> discord.TextChannel | None:
        """
        取得日誌頻道
        
        Args:
            guild: Discord 伺服器
            
        Returns:
            discord.TextChannel | None: 日誌頻道
        """
        try:
            if not guild:
                return None
                
            log_channel_id = await self.get_setting("log_channel_id", "")
            if not log_channel_id:
                return None
                
            channel = self.bot.get_channel(int(log_channel_id))
            if isinstance(channel, discord.TextChannel):
                return channel
        except Exception as exc:
            logger.error("【訊息監聽】取得日誌頻道失敗", exc_info=True)
        return None

    # ───────── 事件監聽器 ─────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """訊息事件監聽器"""
        try:
            # 忽略機器人訊息
            if message.author.bot:
                return
                
            # 檢查是否為監聽頻道（使用快取）
            if message.channel.id not in self.monitored_channels:
                return
            
            # 儲存訊息到資料庫
            await self.save_message(message)
            
            # 將訊息添加到緩存
            if self.message_cache.add_message(message):
                # 若達到條件，則立即處理該頻道訊息
                await self.process_channel_messages(message.channel.id)
                
        except Exception as exc:
            logger.error("【訊息監聽】處理訊息事件失敗", exc_info=True)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """訊息編輯事件監聽器"""
        try:
            if before.author.bot or not await self.get_setting("log_edits", "false") == "true":
                return
                
            # 儲存更新後的訊息
            await self.save_message(after)
            
            # 訊息編輯直接單獨處理
            guild = after.guild
            log_channel = await self._get_log_channel(guild)
            if log_channel:
                # 建立編輯訊息說明
                channel_info = ""
                if isinstance(after.channel, (discord.DMChannel, discord.GroupChannel)):
                    channel_info = "(私人訊息)"
                else:
                    channel_info = f"(來自 {after.channel.mention})"
                    
                edit_note = f"📝 **訊息已編輯** {channel_info}"
                
                # 渲染單條訊息
                messages = [after]
                image_path = await self.renderer.render_messages(messages)
                
                if image_path:
                    try:
                        await log_channel.send(
                            f"{edit_note}\n**作者:** {after.author.mention}",
                            file=discord.File(image_path)
                        )
                    finally:
                        from . import utils
                        utils.safe_remove_file(image_path)
                
        except Exception as exc:
            logger.error("【訊息監聽】處理訊息編輯事件失敗", exc_info=True)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """訊息刪除事件監聽器"""
        try:
            if message.author.bot or not await self.get_setting("log_deletes", "false") == "true":
                return
                
            guild = message.guild
            log_channel = await self._get_log_channel(guild)
            if log_channel:
                # 建立刪除訊息說明
                channel_info = ""
                if isinstance(message.channel, (discord.DMChannel, discord.GroupChannel)):
                    channel_info = "(私人訊息)"
                else:
                    channel_info = f"(來自 {message.channel.mention})"
                    
                delete_note = f"🗑️ **訊息已刪除** {channel_info}"
                
                # 渲染單條訊息
                messages = [message]
                image_path = await self.renderer.render_messages(messages)
                
                if image_path:
                    try:
                        await log_channel.send(
                            f"{delete_note}\n**作者:** {message.author.mention}",
                            file=discord.File(image_path)
                        )
                    finally:
                        from . import utils
                        utils.safe_remove_file(image_path)
                
        except Exception as exc:
            logger.error("【訊息監聽】處理訊息刪除事件失敗", exc_info=True) 