"""
資料同步核心服務 - 重構版本

提供資料同步的核心業務邏輯
採用依賴注入模式設計
"""

import datetime as dt
from typing import Any, Protocol

import discord

from ...core.error_handler import create_error_handler
from ...core.logger import setup_module_logger
from ..cache.cache import ISyncDataCache
from ..config.config import ISyncDataConfig
from ..database.database import ISyncDataDatabase

# 設置模塊日誌記錄器
logger = setup_module_logger("sync_data.service")
error_handler = create_error_handler("sync_data.service", logger)


# ────────────────────────────
# 服務接口定義
# ────────────────────────────
class ISyncDataService(Protocol):
    """資料同步核心服務接口"""

    async def sync_guild_data(
        self, guild: discord.Guild, sync_type: str = "full"
    ) -> dict[str, Any]:
        """同步伺服器資料到資料庫"""
        ...

    async def get_sync_status(self, guild_id: int) -> dict[str, Any]:
        """取得同步狀態"""
        ...

    async def get_sync_statistics(self, guild_id: int) -> dict[str, Any]:
        """取得同步統計資訊"""
        ...

    async def validate_sync_permissions(self, guild: discord.Guild) -> bool:
        """驗證同步權限"""
        ...


class SyncDataService:
    """資料同步核心服務實現"""

    def __init__(
        self,
        db_service: ISyncDataDatabase,
        cache_service: ISyncDataCache,
        config_service: ISyncDataConfig,
    ):
        """
        初始化同步服務

        Args:
            db_service: 資料庫服務
            cache_service: 快取服務
            config_service: 配置服務
        """
        self._db = db_service
        self._cache = cache_service
        self._config = config_service

    async def sync_guild_data(
        self, guild: discord.Guild, sync_type: str = "full"
    ) -> dict[str, Any]:
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
            "sync_type": sync_type,
        }

        # 驗證同步類型
        if sync_type not in self._config.sync_types:
            result["error_message"] = self._config.get_error_message("SYNC_007")
            return result

        # 檢查是否已在同步中
        if self._cache.is_syncing(guild.id):
            result["error_message"] = self._config.get_error_message("SYNC_006")
            return result

        # 取得同步鎖
        sync_lock = self._cache.get_sync_lock(guild.id)

        async with sync_lock:
            try:
                logger.info(
                    f"[資料同步]開始同步伺服器 {guild.id} ({guild.name}),類型:{self._config.get_sync_type_name(sync_type)}"
                )

                # 標記為同步中
                self._cache.mark_syncing(guild.id)

                # 根據同步類型執行相應操作
                if sync_type in ["roles", "full"]:
                    # 取得資料庫中的現有角色資料
                    db_roles = await self._db.get_guild_roles(guild.id)
                    db_roles_dict = {row["role_id"]: row for row in db_roles}

                    # 同步角色
                    roles_result = await self._sync_roles(guild, db_roles_dict)
                    (
                        result["roles_added"],
                        result["roles_updated"],
                        result["roles_deleted"],
                    ) = roles_result

                if sync_type in ["channels", "full"]:
                    # 取得資料庫中的現有頻道資料
                    db_channels = await self._db.get_guild_channels(guild.id)
                    db_channels_dict = {row["channel_id"]: row for row in db_channels}

                    # 同步頻道
                    channels_result = await self._sync_channels(guild, db_channels_dict)
                    (
                        result["channels_added"],
                        result["channels_updated"],
                        result["channels_deleted"],
                    ) = channels_result

                # 計算耗時
                result["duration"] = (dt.datetime.utcnow() - start_time).total_seconds()
                result["success"] = True

                # 記錄同步結果
                await self._db.log_sync_result(
                    guild.id,
                    sync_type,
                    "success",
                    result["roles_added"]
                    + result["roles_updated"]
                    + result["roles_deleted"],
                    result["channels_added"]
                    + result["channels_updated"]
                    + result["channels_deleted"],
                    "",
                    start_time,
                    dt.datetime.utcnow(),
                    result["duration"],
                )

                logger.info(
                    f"[資料同步]伺服器 {guild.id} 同步完成:"
                    f"角色({result['roles_added']}+/{result['roles_updated']}~/{result['roles_deleted']}-) "
                    f"頻道({result['channels_added']}+/{result['channels_updated']}~/{result['channels_deleted']}-) "
                    f"耗時 {result['duration']:.2f}秒"
                )

            except Exception as exc:
                result["error_message"] = str(exc)
                result["duration"] = (dt.datetime.utcnow() - start_time).total_seconds()

                # 記錄同步失敗
                await self._db.log_sync_result(
                    guild.id,
                    sync_type,
                    "failed",
                    0,
                    0,
                    result["error_message"],
                    start_time,
                    dt.datetime.utcnow(),
                    result["duration"],
                )

                error_handler.log_error(
                    exc, f"同步伺服器 {guild.id} 資料", "SYNC_ERROR"
                )

            finally:
                # 清除同步標記
                self._cache.clear_sync_mark(guild.id)

        return result

    async def _sync_roles(
        self, guild: discord.Guild, db_roles_dict: dict[int, dict[str, Any]]
    ) -> tuple[int, int, int]:
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
                    not db_role
                    or db_role["name"] != role.name
                    or db_role["color"] != str(role.color)
                    or db_role["permissions"] != role.permissions.value
                    or db_role["position"] != role.position
                    or db_role["mentionable"] != role.mentionable
                    or db_role["hoist"] != role.hoist
                    or db_role["managed"] != role.managed
                )

                if needs_update:
                    await self._db.insert_or_replace_role(role)
                    if db_role:
                        updated += 1
                        logger.debug(f"[資料同步]更新角色:{role.name} ({role.id})")
                    else:
                        added += 1
                        logger.debug(f"[資料同步]新增角色:{role.name} ({role.id})")

            # 處理已刪除的角色
            current_role_ids = {role.id for role in guild.roles}
            for db_role_id in db_roles_dict:
                if db_role_id not in current_role_ids:
                    await self._db.delete_role(db_role_id)
                    deleted += 1
                    logger.debug(
                        f"[資料同步]刪除角色:{db_roles_dict[db_role_id]['name']} ({db_role_id})"
                    )

        except Exception as exc:
            logger.error(f"[資料同步]角色同步失敗: {exc}")
            raise

        return added, updated, deleted

    async def _sync_channels(
        self, guild: discord.Guild, db_channels_dict: dict[int, dict[str, Any]]
    ) -> tuple[int, int, int]:
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
                topic = getattr(channel, "topic", None)
                category_id = getattr(channel, "category_id", None)

                # 檢查是否需要更新
                needs_update = (
                    not db_channel
                    or db_channel["name"] != channel.name
                    or db_channel["type"] != str(channel.type)
                    or db_channel["topic"] != topic
                    or db_channel["position"] != channel.position
                    or db_channel["category_id"] != category_id
                )

                if needs_update:
                    await self._db.insert_or_replace_channel(channel)
                    if db_channel:
                        updated += 1
                        logger.debug(
                            f"[資料同步]更新頻道:{channel.name} ({channel.id})"
                        )
                    else:
                        added += 1
                        logger.debug(
                            f"[資料同步]新增頻道:{channel.name} ({channel.id})"
                        )

            # 處理已刪除的頻道
            current_channel_ids = {channel.id for channel in guild.channels}
            for db_channel_id in db_channels_dict:
                if db_channel_id not in current_channel_ids:
                    await self._db.delete_channel(db_channel_id)
                    deleted += 1
                    logger.debug(
                        f"[資料同步]刪除頻道:{db_channels_dict[db_channel_id]['name']} ({db_channel_id})"
                    )

        except Exception as exc:
            logger.error(f"[資料同步]頻道同步失敗: {exc}")
            raise

        return added, updated, deleted

    async def get_sync_status(self, guild_id: int) -> dict[str, Any]:
        """
        取得同步狀態

        Args:
            guild_id: 伺服器 ID

        Returns:
            Dict[str, Any]: 同步狀態資訊
        """
        try:
            # 檢查是否正在同步中
            is_syncing = self._cache.is_syncing(guild_id)

            # 取得最後同步記錄
            last_sync = await self._db.get_last_sync_record(guild_id)

            # 取得資料完整性驗證
            integrity = await self._db.validate_data_integrity(guild_id)

            return {
                "guild_id": guild_id,
                "is_syncing": is_syncing,
                "last_sync": last_sync,
                "data_integrity": integrity,
                "cache_stats": self._cache.get_cache_stats()
                if hasattr(self._cache, "get_cache_stats")
                else {},
            }

        except Exception as exc:
            error_handler.log_error(
                exc, f"取得伺服器 {guild_id} 同步狀態", "SYNC_STATUS_ERROR"
            )
            return {
                "guild_id": guild_id,
                "is_syncing": False,
                "last_sync": None,
                "data_integrity": None,
                "error": str(exc),
            }

    async def get_sync_statistics(self, guild_id: int) -> dict[str, Any]:
        """
        取得同步統計資訊

        Args:
            guild_id: 伺服器 ID

        Returns:
            Dict[str, Any]: 同步統計資訊
        """
        try:
            # 取得同步歷史
            history = await self._db.get_sync_history(guild_id, limit=100)

            if not history:
                return {
                    "guild_id": guild_id,
                    "total_syncs": 0,
                    "success_count": 0,
                    "success_rate": 0.0,
                    "average_duration": 0.0,
                    "last_30_days": 0,
                }

            # 計算統計資訊
            total_syncs = len(history)
            success_count = len([h for h in history if h.get("status") == "success"])
            success_rate = (success_count / total_syncs * 100) if total_syncs > 0 else 0

            # 計算平均耗時
            durations = [h.get("duration", 0) for h in history if h.get("duration")]
            average_duration = sum(durations) / len(durations) if durations else 0

            # 計算最近30天的同步次數
            thirty_days_ago = dt.datetime.utcnow() - dt.timedelta(days=30)
            recent_syncs = [
                h
                for h in history
                if h.get("start_time")
                and dt.datetime.fromisoformat(str(h["start_time"])) > thirty_days_ago
            ]

            return {
                "guild_id": guild_id,
                "total_syncs": total_syncs,
                "success_count": success_count,
                "success_rate": success_rate,
                "average_duration": average_duration,
                "last_30_days": len(recent_syncs),
                "recent_history": history[:10],  # 最近10次記錄
            }

        except Exception as exc:
            error_handler.log_error(
                exc, f"取得伺服器 {guild_id} 同步統計", "SYNC_STATS_ERROR"
            )
            return {
                "guild_id": guild_id,
                "total_syncs": 0,
                "success_count": 0,
                "success_rate": 0.0,
                "average_duration": 0.0,
                "last_30_days": 0,
                "error": str(exc),
            }

    async def validate_sync_permissions(self, guild: discord.Guild) -> bool:
        """
        驗證同步權限

        Args:
            guild: Discord 伺服器物件

        Returns:
            bool: 是否有足夠權限
        """
        try:
            # 檢查機器人權限
            bot_member = guild.me
            if not bot_member:
                return False

            # 需要的權限
            required_permissions = [
                "view_channel",
                "read_message_history",
                "manage_roles",
                "manage_channels",
            ]

            permissions = bot_member.guild_permissions
            for perm in required_permissions:
                if not getattr(permissions, perm, False):
                    logger.warning(f"[資料同步]伺服器 {guild.id} 缺少權限:{perm}")
                    return False

            return True

        except Exception as exc:
            error_handler.log_error(
                exc, f"驗證伺服器 {guild.id} 同步權限", "PERMISSION_ERROR"
            )
            return False

    def format_sync_result(self, result: dict[str, Any]) -> str:
        """
        格式化同步結果訊息

        Args:
            result: 同步結果字典

        Returns:
            str: 格式化的結果訊息
        """
        sync_type_name = self._config.get_sync_type_name(result["sync_type"])
        message = f"✅ {sync_type_name}完成!\n"
        message += f"⏱️ 耗時:{result['duration']:.2f}秒\n"

        if result["sync_type"] in ["roles", "full"]:
            message += f"👥 角色:新增 {result['roles_added']} 個,更新 {result['roles_updated']} 個,刪除 {result['roles_deleted']} 個\n"

        if result["sync_type"] in ["channels", "full"]:
            message += f"📺 頻道:新增 {result['channels_added']} 個,更新 {result['channels_updated']} 個,刪除 {result['channels_deleted']} 個"

        return message
