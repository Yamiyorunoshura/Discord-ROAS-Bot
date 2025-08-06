"""成就通知系統核心實作.

此模組實作成就通知系統的核心功能,提供:
- 私訊通知發送
- 伺服器公告發送
- 通知偏好管理
- 通知頻率控制
- 錯誤處理和重試機制
- 通知統計和監控

通知系統遵循以下設計原則:
- 異步處理避免阻塞成就觸發流程
- 支援批量通知處理提升效能
- 實作適當的頻率限制和錯誤處理
- 完整的通知狀態追蹤和統計
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

import discord

from ..database.models import (
    Achievement,
    GlobalNotificationSettings,
    NotificationEvent,
    NotificationPreference,
    UserAchievement,
)

if TYPE_CHECKING:
    from discord.ext import commands

    from ..database.repository import AchievementRepository

logger = logging.getLogger(__name__)

# 通知限制常數
MAX_NOTIFICATIONS_PER_MINUTE = 5  # 每分鐘最大通知數

# =============================================================================
# 通知處理器橋接函數
# =============================================================================


async def create_notification_handler(notifier: AchievementNotifier) -> callable:
    """建立通知處理器函數,用於與 AchievementAwarder 整合.

    Args:
        notifier: AchievementNotifier 實例

    Returns:
        可用於 AchievementAwarder.add_notification_handler 的處理器函數
    """

    async def notification_handler(notification_data: dict[str, Any]) -> None:
        """通知處理器函數.

        Args:
            notification_data: 來自 AchievementAwarder 的通知資料
        """
        try:
            # 將資料轉換為 AchievementNotifier 需要的格式
            await notifier.notify_achievement(
                user_id=notification_data["user_id"],
                guild_id=notification_data["guild_id"],
                achievement=notification_data["achievement"],
                user_achievement=notification_data["user_achievement"],
                notification_type=NotificationType.BOTH,
                trigger_reason=notification_data.get("trigger_reason", "成就條件達成"),
                source_event=notification_data.get("source_event"),
            )

        except Exception as e:
            logger.error(
                "通知處理器橋接失敗",
                extra={
                    "user_id": notification_data.get("user_id"),
                    "achievement_id": notification_data.get("achievement", {}).get(
                        "id"
                    ),
                    "error": str(e),
                },
                exc_info=True,
            )

    return notification_handler


class NotificationType(str, Enum):
    """通知類型列舉."""

    DIRECT_MESSAGE = "dm"
    SERVER_ANNOUNCEMENT = "announcement"
    BOTH = "both"


class NotificationStatus(str, Enum):
    """通知狀態列舉."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class NotificationData:
    """通知資料封裝.

    封裝單一成就通知的完整資訊.
    """

    user_id: int
    """Discord 用戶 ID"""

    guild_id: int
    """Discord 伺服器 ID"""

    achievement: Achievement
    """成就資訊"""

    user_achievement: UserAchievement
    """用戶成就記錄"""

    notification_type: NotificationType = NotificationType.BOTH
    """通知類型"""

    trigger_reason: str = "成就條件達成"
    """觸發原因"""

    source_event: str | None = None
    """來源事件類型"""

    priority: int = 0
    """通知優先級"""

    retry_count: int = 0
    """重試次數"""


@dataclass
class NotificationResult:
    """通知發送結果.

    封裝通知發送的完整結果資訊.
    """

    notification_data: NotificationData
    """原始通知資料"""

    dm_status: NotificationStatus = NotificationStatus.PENDING
    """私訊發送狀態"""

    announcement_status: NotificationStatus = NotificationStatus.PENDING
    """公告發送狀態"""

    dm_error: str | None = None
    """私訊發送錯誤訊息"""

    announcement_error: str | None = None
    """公告發送錯誤訊息"""

    processing_time: float = 0.0
    """處理時間(毫秒)"""

    sent_at: datetime = field(default_factory=datetime.now)
    """發送時間"""


class AchievementNotifier:
    """成就通知系統核心類別.

    負責處理成就通知的發送、管理和監控,提供:
    - 私訊和伺服器公告通知
    - 通知偏好檢查和管理
    - 頻率限制和去重機制
    - 錯誤處理和重試邏輯
    - 完整的通知統計和監控
    """

    def __init__(
        self,
        bot: commands.Bot,
        repository: AchievementRepository,
        max_concurrent_notifications: int = 10,
        notification_timeout: float = 15.0,
        default_retry_limit: int = 3,
        rate_limit_window: int = 60,
    ):
        """初始化成就通知器.

        Args:
            bot: Discord 機器人實例
            repository: 成就資料存取庫
            max_concurrent_notifications: 最大並發通知數
            notification_timeout: 通知發送超時時間(秒)
            default_retry_limit: 預設重試次數限制
            rate_limit_window: 頻率限制時間窗口(秒)
        """
        self._bot = bot
        self._repository = repository
        self._max_concurrent = max_concurrent_notifications
        self._timeout = notification_timeout
        self._retry_limit = default_retry_limit
        self._rate_limit_window = rate_limit_window

        # 併發控制
        self._notification_semaphore = asyncio.Semaphore(max_concurrent_notifications)
        self._active_notifications: set[str] = set()  # user_id:achievement_id
        self._rate_limit_tracker: dict[int, list[datetime]] = {}  # user_id: timestamps

        # 通知隊列和批次處理
        self._notification_queue: asyncio.Queue[NotificationData] = asyncio.Queue()
        self._batch_processor_task: asyncio.Task | None = None
        self._is_processing = False

        # 統計資訊
        self._stats = {
            "total_notifications": 0,
            "successful_dm": 0,
            "successful_announcements": 0,
            "failed_dm": 0,
            "failed_announcements": 0,
            "rate_limited": 0,
            "duplicate_filtered": 0,
            "average_processing_time": 0.0,
            "last_reset": datetime.now(),
        }

        # 通知模板緩存
        self._template_cache: dict[str, dict[str, Any]] = {}

        logger.info(
            "AchievementNotifier 初始化完成",
            extra={
                "max_concurrent": max_concurrent_notifications,
                "timeout": notification_timeout,
                "retry_limit": default_retry_limit,
                "rate_limit_window": rate_limit_window,
            },
        )

    async def __aenter__(self) -> AchievementNotifier:
        """異步上下文管理器進入."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """異步上下文管理器退出."""
        await self.stop()

    # =============================================================================
    # 通知系統生命週期管理
    # =============================================================================

    async def start(self) -> None:
        """開始通知系統."""
        if self._is_processing:
            return

        self._is_processing = True
        self._batch_processor_task = asyncio.create_task(self._batch_processor())

        logger.info("成就通知系統已啟動")

    async def stop(self) -> None:
        """停止通知系統."""
        if not self._is_processing:
            return

        self._is_processing = False

        # 取消批次處理任務
        if self._batch_processor_task:
            self._batch_processor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._batch_processor_task

        # 處理剩餘的通知
        remaining_notifications = []
        while not self._notification_queue.empty():
            try:
                notification = self._notification_queue.get_nowait()
                remaining_notifications.append(notification)
            except asyncio.QueueEmpty:
                break

        if remaining_notifications:
            logger.info(f"處理剩餘通知: {len(remaining_notifications)} 個")
            await self._process_notification_batch(remaining_notifications)

        logger.info("成就通知系統已停止")

    # =============================================================================
    # 公共通知介面
    # =============================================================================

    async def notify_achievement(
        self,
        user_id: int,
        guild_id: int,
        achievement: Achievement,
        user_achievement: UserAchievement,
        notification_type: NotificationType = NotificationType.BOTH,
        trigger_reason: str = "成就條件達成",
        source_event: str | None = None,
    ) -> NotificationResult:
        """發送單一成就通知.

        Args:
            user_id: 用戶 ID
            guild_id: 伺服器 ID
            achievement: 成就資訊
            user_achievement: 用戶成就記錄
            notification_type: 通知類型
            trigger_reason: 觸發原因
            source_event: 來源事件類型

        Returns:
            通知發送結果
        """
        notification_data = NotificationData(
            user_id=user_id,
            guild_id=guild_id,
            achievement=achievement,
            user_achievement=user_achievement,
            notification_type=notification_type,
            trigger_reason=trigger_reason,
            source_event=source_event,
        )

        return await self._process_single_notification(notification_data)

    async def queue_notification(
        self,
        user_id: int,
        guild_id: int,
        achievement: Achievement,
        user_achievement: UserAchievement,
        notification_type: NotificationType = NotificationType.BOTH,
        priority: int = 0,
    ) -> None:
        """將通知加入處理隊列.

        Args:
            user_id: 用戶 ID
            guild_id: 伺服器 ID
            achievement: 成就資訊
            user_achievement: 用戶成就記錄
            notification_type: 通知類型
            priority: 優先級
        """
        notification_data = NotificationData(
            user_id=user_id,
            guild_id=guild_id,
            achievement=achievement,
            user_achievement=user_achievement,
            notification_type=notification_type,
            priority=priority,
        )

        await self._notification_queue.put(notification_data)

        logger.debug(
            "通知已加入隊列",
            extra={
                "user_id": user_id,
                "achievement_id": achievement.id,
                "notification_type": notification_type.value,
                "priority": priority,
            },
        )

    async def batch_notify_achievements(
        self, notifications: list[NotificationData]
    ) -> list[NotificationResult]:
        """批量發送成就通知.

        Args:
            notifications: 通知資料列表

        Returns:
            通知發送結果列表
        """
        if not notifications:
            return []

        return await self._process_notification_batch(notifications)

    # =============================================================================
    # 內部通知處理邏輯
    # =============================================================================

    async def _process_single_notification(
        self, notification_data: NotificationData
    ) -> NotificationResult:
        """處理單一通知發送.

        Args:
            notification_data: 通知資料

        Returns:
            通知發送結果
        """
        start_time = datetime.now()
        notification_key = (
            f"{notification_data.user_id}:{notification_data.achievement.id}"
        )

        try:
            # 檢查是否正在處理中
            if notification_key in self._active_notifications:
                logger.debug(f"通知已在處理中: {notification_key}")
                return NotificationResult(
                    notification_data=notification_data,
                    dm_status=NotificationStatus.FAILED,
                    dm_error="通知正在處理中",
                )

            # 標記為處理中
            self._active_notifications.add(notification_key)

            try:
                # 使用信號量控制並發數
                async with self._notification_semaphore:
                    # 執行通知發送邏輯
                    result = await asyncio.wait_for(
                        self._execute_notification_logic(notification_data),
                        timeout=self._timeout,
                    )

                    # 計算處理時間
                    processing_time = (
                        datetime.now() - start_time
                    ).total_seconds() * 1000
                    result.processing_time = processing_time

                    # 更新統計
                    self._update_notification_stats(result)

                    return result

            finally:
                # 清理處理中標記
                self._active_notifications.discard(notification_key)

        except TimeoutError:
            return NotificationResult(
                notification_data=notification_data,
                dm_status=NotificationStatus.FAILED,
                dm_error=f"通知發送超時({self._timeout}s)",
            )
        except Exception as e:
            logger.error(
                "通知發送處理失敗",
                extra={
                    "user_id": notification_data.user_id,
                    "achievement_id": notification_data.achievement.id,
                    "error": str(e),
                },
                exc_info=True,
            )
            return NotificationResult(
                notification_data=notification_data,
                dm_status=NotificationStatus.FAILED,
                dm_error=str(e),
            )

    async def _execute_notification_logic(
        self, notification_data: NotificationData
    ) -> NotificationResult:
        """執行通知發送邏輯.

        Args:
            notification_data: 通知資料

        Returns:
            通知發送結果
        """
        result = NotificationResult(notification_data=notification_data)

        # 1. 檢查用戶通知偏好
        user_preferences = await self._get_user_notification_preferences(
            notification_data.user_id, notification_data.guild_id
        )

        # 2. 檢查頻率限制
        if await self._is_rate_limited(notification_data.user_id):
            result.dm_status = NotificationStatus.FAILED
            result.dm_error = "超過頻率限制"
            self._stats["rate_limited"] += 1
            return result

        # 3. 檢查去重
        if await self._is_duplicate_notification(notification_data):
            result.dm_status = NotificationStatus.FAILED
            result.dm_error = "重複通知已過濾"
            self._stats["duplicate_filtered"] += 1
            return result

        # 4. 根據偏好和類型發送通知
        if (
            notification_data.notification_type
            in [NotificationType.DIRECT_MESSAGE, NotificationType.BOTH]
            and user_preferences.dm_notifications
        ):
            try:
                await self._send_direct_message_notification(notification_data)
                result.dm_status = NotificationStatus.SENT
            except Exception as e:
                result.dm_status = NotificationStatus.FAILED
                result.dm_error = str(e)

        if (
            notification_data.notification_type
            in [NotificationType.SERVER_ANNOUNCEMENT, NotificationType.BOTH]
            and user_preferences.server_announcements
        ):
            try:
                await self._send_server_announcement_notification(notification_data)
                result.announcement_status = NotificationStatus.SENT
            except Exception as e:
                result.announcement_status = NotificationStatus.FAILED
                result.announcement_error = str(e)

        # 5. 記錄通知事件
        await self._record_notification_event(notification_data, result)

        # 6. 更新 UserAchievement 的 notified 標記
        if NotificationStatus.SENT in (result.dm_status, result.announcement_status):
            await self._repository.mark_achievement_notified(
                notification_data.user_achievement.id
            )

        return result

    async def _send_direct_message_notification(
        self, notification_data: NotificationData
    ) -> None:
        """發送私訊通知.

        Args:
            notification_data: 通知資料
        """
        user = self._bot.get_user(notification_data.user_id)
        if not user:
            try:
                user = await self._bot.fetch_user(notification_data.user_id)
            except discord.NotFound as e:
                raise Exception("用戶不存在") from e

        # 建立通知 embed
        embed = await self._create_achievement_embed(notification_data)

        try:
            await user.send(embed=embed)
            self._stats["successful_dm"] += 1

            logger.info(
                "私訊通知發送成功",
                extra={
                    "user_id": notification_data.user_id,
                    "achievement_id": notification_data.achievement.id,
                },
            )

        except discord.Forbidden as e:
            raise Exception("無法向用戶發送私訊") from e
        except discord.HTTPException as e:
            raise Exception(f"Discord API 錯誤: {e}") from e

    async def _send_server_announcement_notification(
        self, notification_data: NotificationData
    ) -> None:
        """發送伺服器公告通知.

        Args:
            notification_data: 通知資料
        """
        # 取得伺服器通知設定
        guild_settings = await self._get_guild_notification_settings(
            notification_data.guild_id
        )

        if (
            not guild_settings.announcement_enabled
            or not guild_settings.announcement_channel_id
        ):
            raise Exception("伺服器公告功能未啟用或未設定頻道")

        # 取得公告頻道
        channel = self._bot.get_channel(guild_settings.announcement_channel_id)
        if not channel:
            try:
                channel = await self._bot.fetch_channel(
                    guild_settings.announcement_channel_id
                )
            except discord.NotFound as e:
                raise Exception("公告頻道不存在") from e

        # 建立公告 embed
        embed = await self._create_announcement_embed(notification_data)

        # 取得用戶提及
        user = self._bot.get_user(notification_data.user_id)
        user_mention = user.mention if user else f"<@{notification_data.user_id}>"

        content = (
            f"🎉 {user_mention} 獲得了成就 **{notification_data.achievement.name}**!"
        )

        try:
            await channel.send(content=content, embed=embed)
            self._stats["successful_announcements"] += 1

            logger.info(
                "伺服器公告發送成功",
                extra={
                    "user_id": notification_data.user_id,
                    "achievement_id": notification_data.achievement.id,
                    "channel_id": channel.id,
                },
            )

        except discord.Forbidden as e:
            raise Exception("無權在公告頻道發送訊息") from e
        except discord.HTTPException as e:
            raise Exception(f"Discord API 錯誤: {e}") from e

    # =============================================================================
    # 通知內容生成
    # =============================================================================

    async def _create_achievement_embed(
        self, notification_data: NotificationData
    ) -> discord.Embed:
        """建立成就通知 embed.

        Args:
            notification_data: 通知資料

        Returns:
            Discord embed 物件
        """
        achievement = notification_data.achievement

        embed = discord.Embed(
            title="🎉 成就解鎖!",
            description=f"恭喜獲得成就:**{achievement.name}**",
            color=0x00FF00,  # 綠色
            timestamp=notification_data.user_achievement.earned_at,
        )

        embed.add_field(name="成就描述", value=achievement.description, inline=False)

        embed.add_field(name="成就點數", value=f"+{achievement.points} 點", inline=True)

        embed.add_field(
            name="獲得時間",
            value=f"<t:{int(notification_data.user_achievement.earned_at.timestamp())}:F>",
            inline=True,
        )

        if notification_data.trigger_reason:
            embed.add_field(
                name="觸發原因", value=notification_data.trigger_reason, inline=False
            )

        # 添加成就徽章縮圖
        if achievement.badge_url:
            embed.set_thumbnail(url=achievement.badge_url)

        embed.set_footer(text="使用 /成就 查看所有成就")

        return embed

    async def _create_announcement_embed(
        self, notification_data: NotificationData
    ) -> discord.Embed:
        """建立伺服器公告 embed.

        Args:
            notification_data: 通知資料

        Returns:
            Discord embed 物件
        """
        achievement = notification_data.achievement

        embed = discord.Embed(
            description=achievement.description,
            color=0xFFD700,  # 金色
            timestamp=notification_data.user_achievement.earned_at,
        )

        if achievement.points > 0:
            embed.add_field(
                name="獎勵點數", value=f"{achievement.points} 點", inline=True
            )

        # 添加成就徽章縮圖
        if achievement.badge_url:
            embed.set_thumbnail(url=achievement.badge_url)

        return embed

    # =============================================================================
    # 輔助方法和工具函數
    # =============================================================================

    async def _get_user_notification_preferences(
        self, user_id: int, guild_id: int
    ) -> NotificationPreference:
        """取得用戶通知偏好.

        Args:
            user_id: 用戶 ID
            guild_id: 伺服器 ID

        Returns:
            用戶通知偏好
        """
        try:
            preferences = await self._repository.get_notification_preferences(
                user_id, guild_id
            )
            if preferences:
                return preferences
        except Exception as e:
            logger.warning(f"取得用戶通知偏好失敗: {e}")

        # 返回預設偏好
        return NotificationPreference(
            user_id=user_id,
            guild_id=guild_id,
            dm_notifications=True,
            server_announcements=True,
            notification_types=[],
        )

    async def _get_guild_notification_settings(
        self, guild_id: int
    ) -> GlobalNotificationSettings:
        """取得伺服器通知設定.

        Args:
            guild_id: 伺服器 ID

        Returns:
            伺服器通知設定
        """
        try:
            settings = await self._repository.get_global_notification_settings(guild_id)
            if settings:
                return settings
        except Exception as e:
            logger.warning(f"取得伺服器通知設定失敗: {e}")

        # 返回預設設定
        return GlobalNotificationSettings(
            guild_id=guild_id, announcement_enabled=False, rate_limit_seconds=60
        )

    async def _is_rate_limited(self, user_id: int) -> bool:
        """檢查用戶是否受頻率限制.

        Args:
            user_id: 用戶 ID

        Returns:
            是否受限制
        """
        now = datetime.now()
        cutoff_time = now - timedelta(seconds=self._rate_limit_window)

        # 清理過期記錄
        if user_id in self._rate_limit_tracker:
            self._rate_limit_tracker[user_id] = [
                timestamp
                for timestamp in self._rate_limit_tracker[user_id]
                if timestamp > cutoff_time
            ]
        else:
            self._rate_limit_tracker[user_id] = []

        # 檢查頻率限制(每分鐘最多 5 個通知)
        recent_notifications = len(self._rate_limit_tracker[user_id])
        if recent_notifications >= MAX_NOTIFICATIONS_PER_MINUTE:
            return True

        # 記錄本次通知時間
        self._rate_limit_tracker[user_id].append(now)
        return False

    async def _is_duplicate_notification(
        self, notification_data: NotificationData
    ) -> bool:
        """檢查是否為重複通知.

        Args:
            notification_data: 通知資料

        Returns:
            是否為重複通知
        """
        notification_key = (
            f"{notification_data.user_id}:{notification_data.achievement.id}"
        )
        return notification_key in self._active_notifications

    async def _record_notification_event(
        self, notification_data: NotificationData, result: NotificationResult
    ) -> None:
        """記錄通知事件.

        Args:
            notification_data: 通知資料
            result: 通知結果
        """
        try:
            notification_event = NotificationEvent(
                user_id=notification_data.user_id,
                guild_id=notification_data.guild_id,
                achievement_id=notification_data.achievement.id,
                notification_type=notification_data.notification_type.value,
                sent_at=result.sent_at,
                delivery_status=result.dm_status.value
                if result.dm_status == NotificationStatus.SENT
                else result.announcement_status.value,
                error_message=result.dm_error or result.announcement_error,
                retry_count=notification_data.retry_count,
            )

            await self._repository.create_notification_event(notification_event)

        except Exception as e:
            logger.error(f"記錄通知事件失敗: {e}")

    async def _batch_processor(self) -> None:
        """批次處理器主迴圈."""
        batch_size = 10
        batch_timeout = 5.0

        while self._is_processing:
            try:
                # 收集批次通知
                batch = []
                deadline = asyncio.get_event_loop().time() + batch_timeout

                while (
                    len(batch) < batch_size
                    and asyncio.get_event_loop().time() < deadline
                ):
                    try:
                        timeout = max(0.1, deadline - asyncio.get_event_loop().time())
                        notification = await asyncio.wait_for(
                            self._notification_queue.get(), timeout=timeout
                        )
                        batch.append(notification)
                    except TimeoutError:
                        break

                # 處理批次通知
                if batch:
                    await self._process_notification_batch(batch)

            except Exception as e:
                logger.error(f"批次處理器錯誤: {e}", exc_info=True)
                await asyncio.sleep(1)  # 錯誤後暫停一秒

    async def _process_notification_batch(
        self, notifications: list[NotificationData]
    ) -> list[NotificationResult]:
        """處理通知批次.

        Args:
            notifications: 通知資料列表

        Returns:
            通知結果列表
        """
        if not notifications:
            return []

        # 按優先級排序
        sorted_notifications = sorted(
            notifications, key=lambda n: n.priority, reverse=True
        )

        # 並發處理通知
        tasks = []
        for notification in sorted_notifications:
            task = asyncio.create_task(self._process_single_notification(notification))
            tasks.append(task)

        # 等待所有通知完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 處理異常結果
        notification_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = NotificationResult(
                    notification_data=sorted_notifications[i],
                    dm_status=NotificationStatus.FAILED,
                    dm_error=str(result),
                )
                notification_results.append(error_result)
            else:
                notification_results.append(result)

        logger.info(
            "批次通知處理完成",
            extra={
                "total_notifications": len(notifications),
                "successful": len([
                    r
                    for r in notification_results
                    if NotificationStatus.SENT in (r.dm_status, r.announcement_status)
                ]),
                "failed": len([
                    r
                    for r in notification_results
                    if r.dm_status == NotificationStatus.FAILED
                    and r.announcement_status == NotificationStatus.FAILED
                ]),
            },
        )

        return notification_results

    def _update_notification_stats(self, result: NotificationResult) -> None:
        """更新通知統計.

        Args:
            result: 通知結果
        """
        self._stats["total_notifications"] += 1

        if result.dm_status == NotificationStatus.SENT:
            self._stats["successful_dm"] += 1
        elif result.dm_status == NotificationStatus.FAILED:
            self._stats["failed_dm"] += 1

        if result.announcement_status == NotificationStatus.SENT:
            self._stats["successful_announcements"] += 1
        elif result.announcement_status == NotificationStatus.FAILED:
            self._stats["failed_announcements"] += 1

        # 更新平均處理時間
        total = self._stats["total_notifications"]
        current_avg = self._stats["average_processing_time"]
        self._stats["average_processing_time"] = (
            current_avg * (total - 1) + result.processing_time
        ) / total

    def get_notification_stats(self) -> dict[str, Any]:
        """取得通知統計資訊.

        Returns:
            統計資訊字典
        """
        current_time = datetime.now()
        uptime = (current_time - self._stats["last_reset"]).total_seconds()

        return {
            **self._stats,
            "active_notifications": len(self._active_notifications),
            "queue_size": self._notification_queue.qsize(),
            "is_processing": self._is_processing,
            "uptime_seconds": uptime,
            "notifications_per_second": self._stats["total_notifications"] / uptime
            if uptime > 0
            else 0,
            "success_rate": (
                (self._stats["successful_dm"] + self._stats["successful_announcements"])
                / (self._stats["total_notifications"] * 2)
                if self._stats["total_notifications"] > 0
                else 0
            ),
        }

    def reset_stats(self) -> None:
        """重置通知統計."""
        self._stats = {
            "total_notifications": 0,
            "successful_dm": 0,
            "successful_announcements": 0,
            "failed_dm": 0,
            "failed_announcements": 0,
            "rate_limited": 0,
            "duplicate_filtered": 0,
            "average_processing_time": 0.0,
            "last_reset": datetime.now(),
        }
        logger.info("通知統計已重置")


__all__ = [
    "AchievementNotifier",
    "NotificationData",
    "NotificationResult",
    "NotificationStatus",
    "NotificationType",
    "create_notification_handler",
]
