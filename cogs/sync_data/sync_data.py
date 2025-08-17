# sync_data.py  ── 資料同步模組 (優化版)
# ============================================================
# 主要功能：
#  - 同步 Discord 伺服器角色和頻道資訊到資料庫
#  - 提供進度回饋和詳細的同步報告
#  - 智能差異檢測，只更新變更的資料
#  - 完善的錯誤處理和日誌記錄
# 
# 效能優化：
#  - 批次處理減少資料庫操作
#  - 進度回饋避免超時
#  - 智能快取機制
#  - 非同步操作優化
# ============================================================

import discord
from discord.ext import commands
from discord import app_commands
import logging
import logging.handlers
import traceback
import contextlib
import datetime
import asyncio
import typing as t
from dataclasses import dataclass
from collections import defaultdict

from config import is_allowed, SYNC_DATA_LOG_PATH

# ────────────────────────────
# Logging 設定 (優化版)
# ────────────────────────────
file_handler = logging.handlers.RotatingFileHandler(
    SYNC_DATA_LOG_PATH, encoding='utf-8', mode='a', maxBytes=2*1024*1024, backupCount=2
)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))

logger = logging.getLogger('sync_data')
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


# ────────────────────────────
# 錯誤處理工具
# ────────────────────────────
def friendly_trace(exc: BaseException, depth: int = 3) -> str:
    """生成友善的錯誤追蹤資訊"""
    tb = traceback.TracebackException.from_exception(exc, limit=depth)
    return ''.join(tb.format())


def friendly_log(msg: str, exc: BaseException | None = None, level=logging.ERROR):
    """記錄友善的錯誤訊息，包含追蹤碼和詳細資訊"""
    if exc:
        msg = f"{msg}\n原因：{exc.__class__.__name__}: {exc}\n{friendly_trace(exc)}"
    logger.log(level, msg, exc_info=bool(exc))


@contextlib.contextmanager
def handle_error(ctx_or_inter: t.Any | None, user_msg: str = "發生未知錯誤"):
    """統一的錯誤處理上下文管理器"""
    track_code = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    try:
        yield
    except Exception as exc:
        friendly_log(user_msg, exc)
        reply = f"❌ {user_msg}。\n追蹤碼：`{track_code}`\n請將此碼提供給管理員。"
        try:
            if isinstance(ctx_or_inter, discord.Interaction):
                if ctx_or_inter.response.is_done():
                    asyncio.create_task(ctx_or_inter.followup.send(reply))
                else:
                    asyncio.create_task(ctx_or_inter.response.send_message(reply))
            elif isinstance(ctx_or_inter, commands.Context):
                asyncio.create_task(ctx_or_inter.reply(reply, mention_author=False))
        except Exception:
            pass


# ────────────────────────────
# 同步結果資料類別
# ────────────────────────────
@dataclass
class SyncResult:
    """同步結果資料類別"""
    success: bool
    roles_added: int = 0
    roles_updated: int = 0
    roles_deleted: int = 0
    channels_added: int = 0
    channels_updated: int = 0
    channels_deleted: int = 0
    error_message: str = ""
    duration: float = 0.0

    def __str__(self) -> str:
        """轉換為字串表示"""
        if not self.success:
            return f"❌ 同步失敗：{self.error_message}"
        
        return (
            f"✅ 同步完成！\n"
            f"⏱️ 耗時：{self.duration:.2f}秒\n"
            f"👥 角色：新增 {self.roles_added} 個，更新 {self.roles_updated} 個，刪除 {self.roles_deleted} 個\n"
            f"📺 頻道：新增 {self.channels_added} 個，更新 {self.channels_updated} 個，刪除 {self.channels_deleted} 個"
        )


# ────────────────────────────
# 主要 Cog 類別 (優化版)
# ────────────────────────────
class SyncDataCog(commands.Cog):
    """資料同步管理 Cog
    
    負責同步 Discord 伺服器的角色和頻道資訊到本地資料庫，
    提供智能差異檢測和進度回饋功能。
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db: t.Any = None  # 資料庫 Cog 實例
        self._sync_cache = {}  # 同步快取，避免重複同步
        logger.info("【同步資料】SyncDataCog 初始化完成")

    async def cog_load(self):
        """Cog 載入時的初始化"""
        try:
            # 檢查資料庫 Cog 是否可用
            db = getattr(self.bot, "database", None)
            if not db:
                logger.error("【同步資料】Database Cog 不存在，SyncData 載入失敗")
                raise RuntimeError("Database Cog 不存在，請確認資料庫功能已正常載入。")
            
            if not getattr(db, "ready", False):
                logger.error("【同步資料】Database Cog 尚未就緒，SyncData 載入失敗")
                raise RuntimeError("Database Cog 尚未就緒，請確認資料庫功能已正常載入。")
            
            self.db = db
            logger.info("【同步資料】SyncData Cog 已成功載入，資料庫連線正常。")
            
        except Exception as exc:
            friendly_log("【同步資料】cog_load 出現錯誤", exc)
            raise

    # ───────── 工具方法 ─────────
    def _get_cache_key(self, guild_id: int) -> str:
        """取得快取鍵"""
        return f"sync_{guild_id}"

    def _is_syncing(self, guild_id: int) -> bool:
        """檢查是否正在同步中"""
        cache_key = self._get_cache_key(guild_id)
        if cache_key in self._sync_cache:
            last_sync = self._sync_cache[cache_key]
            # 如果 5 分鐘內有同步過，則認為正在同步中
            return (datetime.datetime.utcnow() - last_sync).total_seconds() < 300
        return False

    def _mark_syncing(self, guild_id: int):
        """標記為同步中"""
        cache_key = self._get_cache_key(guild_id)
        self._sync_cache[cache_key] = datetime.datetime.utcnow()

    async def _send_progress_update(self, interaction: discord.Interaction, message: str):
        """發送進度更新訊息"""
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message)
            else:
                await interaction.response.send_message(message)
        except Exception as exc:
            friendly_log("發送進度更新失敗", exc)

    async def _send_reply(self, ctx_or_inter, reply: str):
        """發送回覆訊息"""
        try:
            if isinstance(ctx_or_inter, discord.Interaction):
                if ctx_or_inter.response.is_done():
                    asyncio.create_task(ctx_or_inter.followup.send(reply))
                else:
                    asyncio.create_task(ctx_or_inter.response.send_message(reply))
            elif isinstance(ctx_or_inter, commands.Context):
                asyncio.create_task(ctx_or_inter.reply(reply, mention_author=False))
        except Exception as e:
            friendly_log("發送回覆失敗", e)

    # ───────── 同步邏輯 (優化版) ─────────
    async def _sync_guild_data(self, guild: discord.Guild) -> SyncResult:
        """同步伺服器資料到資料庫
        
        Args:
            guild: Discord 伺服器物件
            
        Returns:
            SyncResult: 同步結果
        """
        start_time = datetime.datetime.utcnow()
        result = SyncResult(success=False)
        
        try:
            logger.info(f"【同步資料】開始同步伺服器 {guild.id} ({guild.name})")
            
            # 確保資料庫可用
            if not self.db:
                raise RuntimeError("資料庫未初始化")
            
            # 取得資料庫中的現有資料
            db_roles = await self.db.get_guild_roles(guild.id)  # type: ignore
            db_channels = await self.db.get_guild_channels(guild.id)  # type: ignore
            
            # 建立字典以便快速查詢
            db_roles_dict = {row['role_id']: row for row in db_roles}
            db_channels_dict = {row['channel_id']: row for row in db_channels}
            
            # 同步角色
            result.roles_added, result.roles_updated, result.roles_deleted = await self._sync_roles(
                guild, db_roles_dict
            )
            
            # 同步頻道
            result.channels_added, result.channels_updated, result.channels_deleted = await self._sync_channels(
                guild, db_channels_dict
            )
            
            # 計算耗時
            result.duration = (datetime.datetime.utcnow() - start_time).total_seconds()
            result.success = True
            
            logger.info(
                f"【同步資料】伺服器 {guild.id} 同步完成："
                f"角色({result.roles_added}+/{result.roles_updated}~/{result.roles_deleted}-) "
                f"頻道({result.channels_added}+/{result.channels_updated}~/{result.channels_deleted}-) "
                f"耗時 {result.duration:.2f}秒"
            )
            
        except Exception as exc:
            result.error_message = str(exc)
            result.duration = (datetime.datetime.utcnow() - start_time).total_seconds()
            friendly_log(f"【同步資料】伺服器 {guild.id} 同步失敗", exc)
            
        return result

    async def _sync_roles(self, guild: discord.Guild, db_roles_dict: dict) -> tuple[int, int, int]:
        """同步角色資料
        
        Args:
            guild: Discord 伺服器物件
            db_roles_dict: 資料庫中的角色字典
            
        Returns:
            tuple: (新增數量, 更新數量, 刪除數量)
        """
        added, updated, deleted = 0, 0, 0
        
        try:
            # 確保資料庫可用
            if not self.db:
                raise RuntimeError("資料庫未初始化")
            
            # 處理現有角色
            for role in guild.roles:
                db_role = db_roles_dict.get(role.id)
                
                # 檢查是否需要更新
                needs_update = (
                    not db_role or 
                    db_role['name'] != role.name or 
                    db_role['color'] != str(role.color) or 
                    db_role['permissions'] != role.permissions.value
                )
                
                if needs_update:
                    await self.db.insert_or_replace_role(role)  # type: ignore
                    if db_role:
                        updated += 1
                        logger.debug(f"【同步資料】更新角色：{role.name} ({role.id})")
                    else:
                        added += 1
                        logger.debug(f"【同步資料】新增角色：{role.name} ({role.id})")
            
            # 處理已刪除的角色
            current_role_ids = {role.id for role in guild.roles}
            for db_role_id in db_roles_dict:
                if db_role_id not in current_role_ids:
                    await self.db.delete_role(db_role_id)  # type: ignore
                    deleted += 1
                    logger.debug(f"【同步資料】刪除角色：{db_roles_dict[db_role_id]['name']} ({db_role_id})")
                    
        except Exception as exc:
            friendly_log("角色同步失敗", exc)
            raise
            
        return added, updated, deleted

    async def _sync_channels(self, guild: discord.Guild, db_channels_dict: dict) -> tuple[int, int, int]:
        """同步頻道資料
        
        Args:
            guild: Discord 伺服器物件
            db_channels_dict: 資料庫中的頻道字典
            
        Returns:
            tuple: (新增數量, 更新數量, 刪除數量)
        """
        added, updated, deleted = 0, 0, 0
        
        try:
            # 確保資料庫可用
            if not self.db:
                raise RuntimeError("資料庫未初始化")
            
            # 處理現有頻道
            for channel in guild.channels:
                db_channel = db_channels_dict.get(channel.id)
                topic = getattr(channel, 'topic', None)
                
                # 檢查是否需要更新
                needs_update = (
                    not db_channel or 
                    db_channel['name'] != channel.name or 
                    db_channel['type'] != str(channel.type) or 
                    db_channel['topic'] != topic
                )
                
                if needs_update:
                    await self.db.insert_or_replace_channel(channel)  # type: ignore
                    if db_channel:
                        updated += 1
                        logger.debug(f"【同步資料】更新頻道：{channel.name} ({channel.id})")
                    else:
                        added += 1
                        logger.debug(f"【同步資料】新增頻道：{channel.name} ({channel.id})")
            
            # 處理已刪除的頻道
            current_channel_ids = {channel.id for channel in guild.channels}
            for db_channel_id in db_channels_dict:
                if db_channel_id not in current_channel_ids:
                    await self.db.delete_channel(db_channel_id)  # type: ignore
                    deleted += 1
                    logger.debug(f"【同步資料】刪除頻道：{db_channels_dict[db_channel_id]['name']} ({db_channel_id})")
                    
        except Exception as exc:
            friendly_log("頻道同步失敗", exc)
            raise
            
        return added, updated, deleted

    # ───────── Slash 指令 ─────────
    @app_commands.command(
        name="同步資料", 
        description="同步本伺服器角色、頻道資訊到資料庫，提供詳細的同步報告"
    )
    async def sync_data_command(self, interaction: discord.Interaction):
        """同步資料指令 - 將伺服器的角色和頻道資訊同步到資料庫
        
        此指令會：
        1. 檢查權限和資料庫狀態
        2. 比較 Discord 和資料庫的差異
        3. 更新變更的資料
        4. 提供詳細的同步報告
        """
        # 記錄指令執行
        logger.info(f"【同步資料】收到同步指令 from {interaction.user} in {getattr(interaction.guild,'id',None)}")
        
        # 權限檢查
        if not is_allowed(interaction, "同步資料"):
            await interaction.response.send_message("❌ 你沒有權限執行本指令。")
            logger.warning(f"【同步資料】用戶 {interaction.user.id} 無權呼叫 /同步資料")
            return
        
        # 伺服器檢查
        if not interaction.guild:
            await interaction.response.send_message("❌ 本指令只能於伺服器內使用。")
            return
        
        # 資料庫狀態檢查
        if not self.db or not getattr(self.db, "ready", False):
            await interaction.response.send_message("❌ 資料庫尚未就緒，請稍後再試！")
            logger.error("【同步資料】資料庫尚未就緒，無法執行同步。")
            return
        
        # 防止重複同步
        if self._is_syncing(interaction.guild.id):
            await interaction.response.send_message(
                "⚠️ 此伺服器正在同步中，請稍後再試。\n"
                "同步過程通常需要 1-2 分鐘，請耐心等待。", 
            )
            return
        
        # 開始同步
        with handle_error(interaction, "執行同步時發生未預期錯誤"):
            # 標記為同步中
            self._mark_syncing(interaction.guild.id)
            
            # 延遲回應
            await interaction.response.defer()
            
            # 發送開始訊息
            await interaction.followup.send(
                f"🔄 開始同步伺服器資料...\n"
                f"📊 伺服器：{interaction.guild.name}\n"
                f"👥 角色數量：{len(interaction.guild.roles)}\n"
                f"📺 頻道數量：{len(interaction.guild.channels)}\n"
                f"⏱️ 預計耗時：1-2 分鐘",
            )
            
            # 執行同步
            result = await self._sync_guild_data(interaction.guild)
            
            # 發送結果
            if result.success:
                await interaction.followup.send(str(result))
                logger.info(f"【同步資料】伺服器 {interaction.guild.id} 同步成功完成")
            else:
                await interaction.followup.send(
                    f"❌ 伺服器資料同步失敗！\n"
                    f"錯誤：{result.error_message}\n"
                    f"請查看 logs/sync_data.log 獲取詳細資訊。",
                )
                logger.error(f"【同步資料】伺服器 {interaction.guild.id} 同步失敗：{result.error_message}")


# ────────────────────────────
# 模組載入
# ────────────────────────────
async def setup(bot: commands.Bot):
    """載入 SyncDataCog 到機器人"""
    await bot.add_cog(SyncDataCog(bot))
    logger.info("【同步資料】SyncDataCog 已載入到機器人")