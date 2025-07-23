"""
資料同步系統主要邏輯協調中心
- 作為模組的核心，協調各個子模組的工作
- 處理同步指令和邏輯
- 管理同步流程和狀態
"""

import asyncio
import datetime as dt
import logging
import time
from typing import Optional, Dict, Any, Tuple

import discord
from discord import app_commands
from discord.ext import commands

from ..config.config import (
    SYNC_BATCH_SIZE, SYNC_TIMEOUT, MAX_RETRY_COUNT, MIN_SYNC_INTERVAL,
    get_error_message, get_sync_type_name
)
from ..database.database import SyncDataDatabase

# 使用統一的核心模塊
from ...core import create_error_handler, setup_module_logger, ErrorCodes

# 設置模塊日誌記錄器
logger = setup_module_logger("sync_data")
error_handler = create_error_handler("sync_data", logger)

class SyncDataCog(commands.Cog):
    """
    資料同步管理 Cog
    
    負責同步 Discord 伺服器的角色和頻道資訊到本地資料庫，
    提供智能差異檢測和進度回饋功能。
    """
    
    def __init__(self, bot: commands.Bot):
        """
        初始化資料同步系統
        
        Args:
            bot: Discord 機器人實例
        """
        self.bot = bot
        self.db = SyncDataDatabase(bot)
        self._sync_cache = {}  # 同步快取，避免重複同步
        self._sync_locks = {}  # 同步鎖，防止並發同步
        
    async def cog_load(self):
        """Cog 載入時的初始化"""
        try:
            await self.db.init_db()
            logger.info("【資料同步】Cog 載入完成")
        except Exception as exc:
            logger.error(f"【資料同步】Cog 載入失敗: {exc}")
            raise

    async def cog_unload(self):
        """Cog 卸載時的清理"""
        try:
            # 清理同步鎖
            for lock in self._sync_locks.values():
                if lock.locked():
                    lock.release()
            self._sync_locks.clear()
            logger.info("【資料同步】Cog 卸載完成")
        except Exception as exc:
            logger.error(f"【資料同步】Cog 卸載失敗: {exc}")

    # ───────── 工具方法 ─────────
    def _get_cache_key(self, guild_id: int) -> str:
        """取得快取鍵"""
        return f"sync_{guild_id}"

    def _is_syncing(self, guild_id: int) -> bool:
        """檢查是否正在同步中"""
        cache_key = self._get_cache_key(guild_id)
        if cache_key in self._sync_cache:
            last_sync = self._sync_cache[cache_key]
            # 如果在最小間隔內有同步過，則認為正在同步中
            return (dt.datetime.utcnow() - last_sync).total_seconds() < MIN_SYNC_INTERVAL
        return False

    def _mark_syncing(self, guild_id: int):
        """標記為同步中"""
        cache_key = self._get_cache_key(guild_id)
        self._sync_cache[cache_key] = dt.datetime.utcnow()

    async def _get_sync_lock(self, guild_id: int) -> asyncio.Lock:
        """取得同步鎖"""
        if guild_id not in self._sync_locks:
            self._sync_locks[guild_id] = asyncio.Lock()
        return self._sync_locks[guild_id]

    async def _send_progress_update(self, interaction: discord.Interaction, message: str):
        """發送進度更新訊息"""
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message)
            else:
                await interaction.response.send_message(message)
        except Exception as exc:
            logger.error(f"【資料同步】發送進度更新失敗: {exc}")

    # ───────── 同步邏輯 ─────────
    async def sync_guild_data(self, guild: discord.Guild, sync_type: str = "full") -> Dict[str, Any]:
        """
        同步伺服器資料到資料庫
        
        Args:
            guild: Discord 伺服器物件
            sync_type: 同步類型 ("roles", "channels", "full")
            
        Returns:
            Dict[str, Any]: 同步結果
        """
        start_time = dt.datetime.utcnow()
        result = {
            "success": False,
            "roles_added": 0,
            "roles_updated": 0,
            "roles_deleted": 0,
            "channels_added": 0,
            "channels_updated": 0,
            "channels_deleted": 0,
            "error_message": "",
            "duration": 0.0,
            "sync_type": sync_type
        }
        
        # 取得同步鎖
        sync_lock = await self._get_sync_lock(guild.id)
        
        async with sync_lock:
            try:
                logger.info(f"【資料同步】開始同步伺服器 {guild.id} ({guild.name})，類型：{get_sync_type_name(sync_type)}")
                
                # 根據同步類型執行相應操作
                if sync_type in ["roles", "full"]:
                    # 取得資料庫中的現有角色資料
                    db_roles = await self.db.get_guild_roles(guild.id)
                    db_roles_dict = {row['role_id']: row for row in db_roles}
                    
                    # 同步角色
                    roles_result = await self._sync_roles(guild, db_roles_dict)
                    result["roles_added"], result["roles_updated"], result["roles_deleted"] = roles_result
                
                if sync_type in ["channels", "full"]:
                    # 取得資料庫中的現有頻道資料
                    db_channels = await self.db.get_guild_channels(guild.id)
                    db_channels_dict = {row['channel_id']: row for row in db_channels}
                    
                    # 同步頻道
                    channels_result = await self._sync_channels(guild, db_channels_dict)
                    result["channels_added"], result["channels_updated"], result["channels_deleted"] = channels_result
                
                # 計算耗時
                result["duration"] = (dt.datetime.utcnow() - start_time).total_seconds()
                result["success"] = True
                
                # 記錄同步結果
                await self.db.log_sync_result(
                    guild.id, sync_type, "success",
                    result["roles_added"] + result["roles_updated"] + result["roles_deleted"],
                    result["channels_added"] + result["channels_updated"] + result["channels_deleted"],
                    "", start_time, dt.datetime.utcnow(), result["duration"]
                )
                
                logger.info(
                    f"【資料同步】伺服器 {guild.id} 同步完成："
                    f"角色({result['roles_added']}+/{result['roles_updated']}~/{result['roles_deleted']}-) "
                    f"頻道({result['channels_added']}+/{result['channels_updated']}~/{result['channels_deleted']}-) "
                    f"耗時 {result['duration']:.2f}秒"
                )
                
            except Exception as exc:
                result["error_message"] = str(exc)
                result["duration"] = (dt.datetime.utcnow() - start_time).total_seconds()
                
                # 記錄同步失敗
                await self.db.log_sync_result(
                    guild.id, sync_type, "failed", 0, 0,
                    result["error_message"], start_time, dt.datetime.utcnow(), result["duration"]
                )
                
                logger.error(f"【資料同步】伺服器 {guild.id} 同步失敗: {exc}")
                
        return result

    async def _sync_roles(self, guild: discord.Guild, db_roles_dict: Dict[int, Dict[str, Any]]) -> Tuple[int, int, int]:
        """
        同步角色資料
        
        Args:
            guild: Discord 伺服器物件
            db_roles_dict: 資料庫中的角色字典
            
        Returns:
            Tuple[int, int, int]: (新增數量, 更新數量, 刪除數量)
        """
        added, updated, deleted = 0, 0, 0
        
        try:
            # 處理現有角色
            for role in guild.roles:
                db_role = db_roles_dict.get(role.id)
                
                # 檢查是否需要更新
                needs_update = (
                    not db_role or 
                    db_role['name'] != role.name or 
                    db_role['color'] != str(role.color) or 
                    db_role['permissions'] != role.permissions.value or
                    db_role['position'] != role.position or
                    db_role['mentionable'] != role.mentionable or
                    db_role['hoist'] != role.hoist or
                    db_role['managed'] != role.managed
                )
                
                if needs_update:
                    await self.db.insert_or_replace_role(role)
                    if db_role:
                        updated += 1
                        logger.debug(f"【資料同步】更新角色：{role.name} ({role.id})")
                    else:
                        added += 1
                        logger.debug(f"【資料同步】新增角色：{role.name} ({role.id})")
            
            # 處理已刪除的角色
            current_role_ids = {role.id for role in guild.roles}
            for db_role_id in db_roles_dict:
                if db_role_id not in current_role_ids:
                    await self.db.delete_role(db_role_id)
                    deleted += 1
                    logger.debug(f"【資料同步】刪除角色：{db_roles_dict[db_role_id]['name']} ({db_role_id})")
                    
        except Exception as exc:
            logger.error(f"【資料同步】角色同步失敗: {exc}")
            raise
            
        return added, updated, deleted

    async def _sync_channels(self, guild: discord.Guild, db_channels_dict: Dict[int, Dict[str, Any]]) -> Tuple[int, int, int]:
        """
        同步頻道資料
        
        Args:
            guild: Discord 伺服器物件
            db_channels_dict: 資料庫中的頻道字典
            
        Returns:
            Tuple[int, int, int]: (新增數量, 更新數量, 刪除數量)
        """
        added, updated, deleted = 0, 0, 0
        
        try:
            # 處理現有頻道
            for channel in guild.channels:
                db_channel = db_channels_dict.get(channel.id)
                topic = getattr(channel, 'topic', None)
                category_id = getattr(channel, 'category_id', None)
                
                # 檢查是否需要更新
                needs_update = (
                    not db_channel or 
                    db_channel['name'] != channel.name or 
                    db_channel['type'] != str(channel.type) or 
                    db_channel['topic'] != topic or
                    db_channel['position'] != channel.position or
                    db_channel['category_id'] != category_id
                )
                
                if needs_update:
                    await self.db.insert_or_replace_channel(channel)
                    if db_channel:
                        updated += 1
                        logger.debug(f"【資料同步】更新頻道：{channel.name} ({channel.id})")
                    else:
                        added += 1
                        logger.debug(f"【資料同步】新增頻道：{channel.name} ({channel.id})")
            
            # 處理已刪除的頻道
            current_channel_ids = {channel.id for channel in guild.channels}
            for db_channel_id in db_channels_dict:
                if db_channel_id not in current_channel_ids:
                    await self.db.delete_channel(db_channel_id)
                    deleted += 1
                    logger.debug(f"【資料同步】刪除頻道：{db_channels_dict[db_channel_id]['name']} ({db_channel_id})")
                    
        except Exception as exc:
            logger.error(f"【資料同步】頻道同步失敗: {exc}")
            raise
            
        return added, updated, deleted

    # ───────── 內部方法 ─────────
    async def _execute_sync_data(self, guild: discord.Guild, sync_type: str = "full"):
        """
        執行同步資料（內部方法）
        
        此方法會：
        1. 檢查同步狀態
        2. 比較 Discord 和資料庫的差異
        3. 更新變更的資料
        4. 返回詳細的同步結果
        
        Args:
            guild: Discord 伺服器物件
            sync_type: 同步類型 (full/roles/channels)
            
        Returns:
            dict: 同步結果字典
        """
        # 記錄同步開始
        logger.info(f"【資料同步】開始執行同步 guild={guild.id}, type={sync_type}")
        
        # 防止重複同步
        if self._is_syncing(guild.id):
            logger.warning(f"【資料同步】伺服器 {guild.id} 正在同步中，跳過")
            return {
                "success": False,
                "error_message": "此伺服器正在同步中，請稍後再試",
                "sync_type": sync_type
            }
        
        # 開始同步
        try:
            # 標記為同步中
            self._mark_syncing(guild.id)
            
            # 記錄同步開始
            sync_type_name = get_sync_type_name(sync_type)
            logger.info(f"【資料同步】開始{sync_type_name} - 伺服器：{guild.name}")
            
            if sync_type in ["roles", "full"]:
                logger.info(f"【資料同步】角色數量：{len(guild.roles)}")
            if sync_type in ["channels", "full"]:
                logger.info(f"【資料同步】頻道數量：{len(guild.channels)}")
            
            # 執行同步
            result = await self.sync_guild_data(guild, sync_type)
            
            # 處理結果
            if result["success"]:
                logger.info(f"【資料同步】伺服器 {guild.id} 同步成功完成")
                return result
            else:
                logger.error(f"【資料同步】伺服器 {guild.id} 同步失敗：{result['error_message']}")
                return result
                
        except Exception as exc:
            error_handler.log_error(exc, f"同步伺服器 {guild.id} 資料", "SYNC_ERROR")
            return {
                "success": False,
                "error_message": f"同步過程中發生未預期錯誤：{str(exc)}",
                "sync_type": sync_type
            }
        finally:
            # 同步完成，標記會自動過期（通過時間戳管理）
            pass

    def _format_sync_result(self, result: Dict[str, Any]) -> str:
        """
        格式化同步結果訊息
        
        Args:
            result: 同步結果字典
            
        Returns:
            str: 格式化的結果訊息
        """
        sync_type_name = get_sync_type_name(result["sync_type"])
        message = f"✅ {sync_type_name}完成！\n"
        message += f"⏱️ 耗時：{result['duration']:.2f}秒\n"
        
        if result["sync_type"] in ["roles", "full"]:
            message += f"👥 角色：新增 {result['roles_added']} 個，更新 {result['roles_updated']} 個，刪除 {result['roles_deleted']} 個\n"
        
        if result["sync_type"] in ["channels", "full"]:
            message += f"📺 頻道：新增 {result['channels_added']} 個，更新 {result['channels_updated']} 個，刪除 {result['channels_deleted']} 個"
        
        return message

    async def _get_sync_history_internal(self, guild: discord.Guild, limit: int = 10):
        """
        獲取同步歷史（內部方法）
        
        Args:
            guild: Discord 伺服器物件
            limit: 返回記錄數量限制
            
        Returns:
            list: 同步歷史記錄列表
        """
        try:
            # 取得同步歷史
            history = await self.db.get_sync_history(guild.id, limit=limit)
            logger.info(f"【資料同步】獲取伺服器 {guild.id} 的同步歷史，共 {len(history) if history else 0} 條記錄")
            return history if history else []
            
        except Exception as exc:
            logger.error(f"【資料同步】獲取同步歷史失敗: {exc}")
            error_handler.log_error(exc, f"獲取伺服器 {guild.id} 同步歷史", "HISTORY_ERROR")
            return []

    @app_commands.command(name="資料同步面板", description="開啟資料同步管理面板")
    async def sync_panel(self, interaction: discord.Interaction):
        """
        資料同步面板指令
        
        Args:
            interaction: Discord 互動
        """
        # 權限檢查
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ 此指令只能在伺服器中使用",
                ephemeral=False
            )
            return
            
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ 需要「管理伺服器」權限才能使用此指令",
                ephemeral=False
            )
            return
        
        try:
            # 導入面板視圖
            from ..panel.main_view import SyncDataMainView
            
            # 創建面板視圖
            view = SyncDataMainView(self, interaction.user.id, interaction.guild)
            
            # 獲取初始 Embed
            embed = await view.build_status_embed()
            
            # 發送帶有面板的訊息
            await interaction.response.send_message(embed=embed, view=view, ephemeral=False)
            
        except Exception as exc:
            # 如果面板載入失敗，使用簡單的 Embed
            embed = discord.Embed(
                title="🔄 資料同步系統",
                description="管理伺服器資料同步設定和歷史記錄",
                color=discord.Color.blue()
            )
            
            # 獲取基本統計
            try:
                history = await self.db.get_sync_history(interaction.guild.id, limit=1)
                if history:
                    last_sync = history[0]
                    sync_time = last_sync.get('sync_time', '未知時間')
                    status = "✅ 成功" if last_sync.get('status') == 'success' else "❌ 失敗"
                    
                    embed.add_field(
                        name="📊 最近同步",
                        value=f"時間：{sync_time}\n狀態：{status}",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="📊 最近同步",
                        value="尚未同步",
                        inline=True
                    )
                    
            except Exception:
                embed.add_field(
                    name="📊 最近同步",
                    value="無法載入",
                    inline=True
                )
            
            embed.set_footer(text=f"面板載入失敗: {exc}")
            
            await interaction.response.send_message(embed=embed, ephemeral=False)

 