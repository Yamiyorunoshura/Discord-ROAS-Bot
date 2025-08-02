"""事件驅動觸發處理器.

此模組實作事件驅動的成就觸發處理系統，提供：
- 事件到成就觸發的整合處理
- 批量事件處理和優化
- 事件過濾和預處理機制
- 觸發優先級管理
- 高效能事件處理流程

事件處理器遵循以下設計原則：
- 異步非阻塞處理所有觸發邏輯
- 智慧事件過濾減少不必要的計算
- 批量處理優化高頻率事件
- 優先級機制確保重要事件優先處理
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from ..database.models import Achievement, AchievementType

if TYPE_CHECKING:
    from ..database.repository import AchievementRepository
    from .progress_tracker import ProgressTracker
    from .trigger_engine import TriggerEngine

logger = logging.getLogger(__name__)


@dataclass
class EventTriggerContext:
    """事件觸發上下文.

    封裝事件觸發所需的完整上下文資訊。
    """

    user_id: int
    """用戶 ID"""

    event_type: str
    """事件類型"""

    event_data: dict[str, Any]
    """事件資料"""

    timestamp: datetime
    """事件時間戳"""

    guild_id: int | None = None
    """伺服器 ID"""

    channel_id: int | None = None
    """頻道 ID"""

    priority: int = 0
    """事件優先級（數值越高優先級越高）"""

    batch_key: str | None = None
    """批量處理鍵（相同鍵的事件會被批量處理）"""


@dataclass
class TriggerResult:
    """觸發結果.

    封裝成就觸發檢查的結果資訊。
    """

    user_id: int
    """用戶 ID"""

    achievement_id: int
    """成就 ID"""

    triggered: bool
    """是否觸發"""

    reason: str | None = None
    """觸發原因或失敗原因"""

    processing_time: float = 0.0
    """處理時間（毫秒）"""

    error: str | None = None
    """錯誤訊息"""


class EventTriggerProcessor:
    """事件驅動觸發處理器.

    整合事件監聽和成就觸發檢查的核心處理器，提供：
    - 事件到成就映射和過濾
    - 批量事件處理和優化
    - 優先級管理和負載均衡
    - 詳細的處理統計和監控
    """

    def __init__(
        self,
        repository: AchievementRepository,
        trigger_engine: TriggerEngine,
        progress_tracker: ProgressTracker,
        batch_size: int = 50,
        batch_timeout: float = 5.0,
        max_concurrent_processing: int = 10
    ):
        """初始化事件觸發處理器.

        Args:
            repository: 成就資料存取庫
            trigger_engine: 觸發引擎
            progress_tracker: 進度追蹤器
            batch_size: 批量處理大小
            batch_timeout: 批量處理超時（秒）
            max_concurrent_processing: 最大並發處理數
        """
        self._repository = repository
        self._trigger_engine = trigger_engine
        self._progress_tracker = progress_tracker

        # 批量處理配置
        self._batch_size = batch_size
        self._batch_timeout = batch_timeout
        self._max_concurrent_processing = max_concurrent_processing

        # 事件處理隊列
        self._event_queue: deque[EventTriggerContext] = deque()
        self._priority_queue: deque[EventTriggerContext] = deque()
        self._batch_queues: dict[str, deque[EventTriggerContext]] = defaultdict(deque)

        # 處理狀態
        self._processing_tasks: set[asyncio.Task] = set()
        self._is_processing = False
        self._last_batch_time = datetime.now()

        # 統計資訊
        self._stats = {
            "events_processed": 0,
            "events_filtered": 0,
            "achievements_triggered": 0,
            "processing_errors": 0,
            "average_processing_time": 0.0,
            "last_reset": datetime.now()
        }

        # 事件到成就類型映射快取
        self._event_achievement_mapping: dict[str, list[AchievementType]] = {}
        self._mapping_cache_time: datetime | None = None
        self._mapping_cache_ttl = timedelta(minutes=10)

        logger.info(
            "EventTriggerProcessor 初始化完成",
            extra={
                "batch_size": batch_size,
                "batch_timeout": batch_timeout,
                "max_concurrent": max_concurrent_processing
            }
        )

    async def __aenter__(self) -> EventTriggerProcessor:
        """異步上下文管理器進入."""
        await self._start_background_processing()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """異步上下文管理器退出."""
        await self._stop_background_processing()

    # =============================================================================
    # 事件處理主要介面
    # =============================================================================

    async def process_event(
        self,
        user_id: int,
        event_type: str,
        event_data: dict[str, Any],
        priority: int = 0,
        guild_id: int | None = None,
        channel_id: int | None = None
    ) -> list[TriggerResult]:
        """處理單一事件觸發檢查.

        Args:
            user_id: 用戶 ID
            event_type: 事件類型
            event_data: 事件資料
            priority: 事件優先級
            guild_id: 伺服器 ID
            channel_id: 頻道 ID

        Returns:
            觸發結果列表
        """
        context = EventTriggerContext(
            user_id=user_id,
            event_type=event_type,
            event_data=event_data,
            timestamp=datetime.now(),
            guild_id=guild_id,
            channel_id=channel_id,
            priority=priority
        )

        # 如果是高優先級事件，立即處理
        if priority >= 5:
            return await self._process_event_immediately(context)

        # 否則加入隊列等待批量處理
        await self._enqueue_event(context)
        return []

    async def process_batch_events(
        self,
        events: list[EventTriggerContext]
    ) -> list[TriggerResult]:
        """批量處理事件觸發檢查.

        Args:
            events: 事件上下文列表

        Returns:
            觸發結果列表
        """
        if not events:
            return []

        start_time = datetime.now()
        results = []

        try:
            # 按用戶分組事件以優化處理
            user_events = defaultdict(list)
            for event in events:
                user_events[event.user_id].append(event)

            # 並發處理每個用戶的事件
            tasks = []
            for user_id, user_event_list in user_events.items():
                task = asyncio.create_task(
                    self._process_user_events(user_id, user_event_list)
                )
                tasks.append(task)

            # 等待所有處理完成
            user_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 收集結果
            for user_result in user_results:
                if isinstance(user_result, Exception):
                    logger.error(f"用戶事件處理失敗: {user_result}", exc_info=True)
                    self._stats["processing_errors"] += 1
                else:
                    results.extend(user_result)

            # 更新統計
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            self._update_processing_stats(len(events), processing_time)

            logger.info(
                "批量事件處理完成",
                extra={
                    "event_count": len(events),
                    "user_count": len(user_events),
                    "triggered_count": len([r for r in results if r.triggered]),
                    "processing_time_ms": processing_time
                }
            )

            return results

        except Exception as e:
            logger.error(
                "批量事件處理失敗",
                extra={
                    "event_count": len(events),
                    "error": str(e)
                },
                exc_info=True
            )
            self._stats["processing_errors"] += len(events)
            raise

    # =============================================================================
    # 事件過濾和預處理
    # =============================================================================

    async def _filter_relevant_achievements(
        self,
        event_type: str,
        user_id: int
    ) -> list[Achievement]:
        """過濾與事件相關的成就.

        Args:
            event_type: 事件類型
            user_id: 用戶 ID

        Returns:
            相關的成就列表
        """
        # 更新事件映射快取
        await self._update_event_mapping_cache()

        # 取得相關的成就類型
        relevant_types = self._event_achievement_mapping.get(event_type, [])
        if not relevant_types:
            # 如果沒有映射，檢查所有成就類型
            relevant_types = list(AchievementType)

        # 取得所有啟用的成就
        all_achievements = await self._repository.list_achievements(active_only=True)

        # 過濾相關的成就
        relevant_achievements = [
            achievement for achievement in all_achievements
            if achievement.type in relevant_types
        ]

        # 進一步過濾已獲得的成就
        filtered_achievements = []
        for achievement in relevant_achievements:
            has_achievement = await self._repository.has_user_achievement(user_id, achievement.id)
            if not has_achievement:
                filtered_achievements.append(achievement)

        return filtered_achievements

    async def _preprocess_event_data(
        self,
        context: EventTriggerContext
    ) -> dict[str, Any]:
        """預處理事件資料.

        Args:
            context: 事件上下文

        Returns:
            預處理後的事件資料
        """
        processed_data = context.event_data.copy()

        # 添加標準化欄位
        processed_data.update({
            "event_type": context.event_type,
            "timestamp": context.timestamp.isoformat(),
            "user_id": context.user_id,
            "guild_id": context.guild_id,
            "channel_id": context.channel_id
        })

        # 根據事件類型進行特殊處理
        if context.event_type == "message_sent":
            processed_data = await self._preprocess_message_event(processed_data)
        elif context.event_type == "reaction_added":
            processed_data = await self._preprocess_reaction_event(processed_data)
        elif context.event_type == "voice_joined":
            processed_data = await self._preprocess_voice_event(processed_data)

        return processed_data

    async def _preprocess_message_event(self, event_data: dict[str, Any]) -> dict[str, Any]:
        """預處理訊息事件資料."""
        # 計算訊息長度
        message_content = event_data.get("content", "")
        event_data["message_length"] = len(message_content)

        # 檢查是否包含連結
        event_data["has_links"] = "http" in message_content.lower()

        # 檢查是否包含附件
        event_data["has_attachments"] = event_data.get("attachment_count", 0) > 0

        return event_data

    async def _preprocess_reaction_event(self, event_data: dict[str, Any]) -> dict[str, Any]:
        """預處理反應事件資料."""
        # 標準化表情符號
        emoji = event_data.get("emoji", {})
        if isinstance(emoji, dict):
            event_data["emoji_name"] = emoji.get("name", "")
            event_data["emoji_id"] = emoji.get("id")

        return event_data

    async def _preprocess_voice_event(self, event_data: dict[str, Any]) -> dict[str, Any]:
        """預處理語音事件資料."""
        # 計算語音頻道停留時長
        join_time = event_data.get("join_time")
        leave_time = event_data.get("leave_time")

        if join_time and leave_time:
            join_dt = datetime.fromisoformat(join_time)
            leave_dt = datetime.fromisoformat(leave_time)
            duration_seconds = (leave_dt - join_dt).total_seconds()
            event_data["voice_duration"] = duration_seconds

        return event_data

    # =============================================================================
    # 內部處理邏輯
    # =============================================================================

    async def _process_event_immediately(
        self,
        context: EventTriggerContext
    ) -> list[TriggerResult]:
        """立即處理高優先級事件.

        Args:
            context: 事件上下文

        Returns:
            觸發結果列表
        """
        return await self._process_user_events(context.user_id, [context])

    async def _process_user_events(
        self,
        user_id: int,
        events: list[EventTriggerContext]
    ) -> list[TriggerResult]:
        """處理特定用戶的事件列表.

        Args:
            user_id: 用戶 ID
            events: 事件列表

        Returns:
            觸發結果列表
        """
        results = []

        try:
            # 為每個事件處理觸發檢查
            for event in events:
                start_time = datetime.now()

                # 預處理事件資料
                processed_data = await self._preprocess_event_data(event)

                # 過濾相關成就
                relevant_achievements = await self._filter_relevant_achievements(
                    event.event_type, user_id
                )

                if not relevant_achievements:
                    self._stats["events_filtered"] += 1
                    continue

                # 檢查每個相關成就的觸發條件
                for achievement in relevant_achievements:
                    try:
                        should_trigger, reason = await self._trigger_engine.check_achievement_trigger(
                            user_id=user_id,
                            achievement_id=achievement.id,
                            trigger_context=processed_data
                        )

                        processing_time = (datetime.now() - start_time).total_seconds() * 1000

                        result = TriggerResult(
                            user_id=user_id,
                            achievement_id=achievement.id,
                            triggered=should_trigger,
                            reason=reason,
                            processing_time=processing_time
                        )

                        results.append(result)

                        if should_trigger:
                            self._stats["achievements_triggered"] += 1
                            logger.info(
                                "成就觸發成功",
                                extra={
                                    "user_id": user_id,
                                    "achievement_id": achievement.id,
                                    "event_type": event.event_type,
                                    "reason": reason,
                                    "processing_time_ms": processing_time
                                }
                            )

                    except Exception as e:
                        processing_time = (datetime.now() - start_time).total_seconds() * 1000
                        error_msg = f"觸發檢查失敗: {e}"

                        result = TriggerResult(
                            user_id=user_id,
                            achievement_id=achievement.id,
                            triggered=False,
                            processing_time=processing_time,
                            error=error_msg
                        )

                        results.append(result)
                        self._stats["processing_errors"] += 1

                        logger.error(
                            "成就觸發檢查失敗",
                            extra={
                                "user_id": user_id,
                                "achievement_id": achievement.id,
                                "event_type": event.event_type,
                                "error": str(e)
                            },
                            exc_info=True
                        )

                self._stats["events_processed"] += 1

            return results

        except Exception as e:
            logger.error(
                "用戶事件處理失敗",
                extra={
                    "user_id": user_id,
                    "event_count": len(events),
                    "error": str(e)
                },
                exc_info=True
            )
            raise

    # =============================================================================
    # 背景處理和隊列管理
    # =============================================================================

    async def _start_background_processing(self) -> None:
        """啟動背景處理任務."""
        if not self._is_processing:
            self._is_processing = True
            task = asyncio.create_task(self._background_processor())
            self._processing_tasks.add(task)
            logger.info("背景事件處理器已啟動")

    async def _stop_background_processing(self) -> None:
        """停止背景處理任務."""
        self._is_processing = False

        # 等待所有處理任務完成
        if self._processing_tasks:
            await asyncio.gather(*self._processing_tasks, return_exceptions=True)
            self._processing_tasks.clear()

        logger.info("背景事件處理器已停止")

    async def _background_processor(self) -> None:
        """背景處理器主循環."""
        while self._is_processing:
            try:
                # 處理高優先級事件
                while self._priority_queue and len(self._processing_tasks) < self._max_concurrent_processing:
                    event = self._priority_queue.popleft()
                    task = asyncio.create_task(self._process_event_immediately(event))
                    self._processing_tasks.add(task)

                # 檢查批量處理條件
                should_process_batch = (
                    len(self._event_queue) >= self._batch_size or
                    (self._event_queue and
                     (datetime.now() - self._last_batch_time).total_seconds() >= self._batch_timeout)
                )

                if should_process_batch and len(self._processing_tasks) < self._max_concurrent_processing:
                    # 收集批量事件
                    batch_events = []
                    for _ in range(min(self._batch_size, len(self._event_queue))):
                        if self._event_queue:
                            batch_events.append(self._event_queue.popleft())

                    if batch_events:
                        task = asyncio.create_task(self.process_batch_events(batch_events))
                        self._processing_tasks.add(task)
                        self._last_batch_time = datetime.now()

                # 清理完成的任務
                completed_tasks = {task for task in self._processing_tasks if task.done()}
                for task in completed_tasks:
                    try:
                        await task
                    except Exception as e:
                        logger.error(f"背景處理任務失敗: {e}", exc_info=True)
                    finally:
                        self._processing_tasks.discard(task)

                # 短暫休眠避免過度佔用 CPU
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"背景處理器錯誤: {e}", exc_info=True)
                await asyncio.sleep(1.0)  # 錯誤時較長的休眠

    async def _enqueue_event(self, context: EventTriggerContext) -> None:
        """將事件加入處理隊列.

        Args:
            context: 事件上下文
        """
        if context.priority >= 5:
            self._priority_queue.append(context)
        else:
            self._event_queue.append(context)

    # =============================================================================
    # 快取和統計管理
    # =============================================================================

    async def _update_event_mapping_cache(self) -> None:
        """更新事件到成就類型映射快取."""
        current_time = datetime.now()

        if (self._mapping_cache_time is None or
            current_time - self._mapping_cache_time > self._mapping_cache_ttl):

            # 重建映射快取
            self._event_achievement_mapping = {
                "message_sent": [AchievementType.COUNTER],
                "reaction_added": [AchievementType.COUNTER, AchievementType.CONDITIONAL],
                "voice_joined": [AchievementType.TIME_BASED, AchievementType.MILESTONE],
                "member_joined": [AchievementType.MILESTONE],
                "command_used": [AchievementType.COUNTER, AchievementType.CONDITIONAL],
                "level_up": [AchievementType.MILESTONE, AchievementType.CONDITIONAL],
                "daily_login": [AchievementType.TIME_BASED],
                "achievement_earned": [AchievementType.CONDITIONAL],
            }

            self._mapping_cache_time = current_time
            logger.debug("事件成就映射快取已更新")

    def _update_processing_stats(self, event_count: int, processing_time: float) -> None:
        """更新處理統計.

        Args:
            event_count: 處理的事件數量
            processing_time: 處理時間（毫秒）
        """
        self._stats["events_processed"] += event_count

        # 更新平均處理時間
        current_avg = self._stats["average_processing_time"]
        total_events = self._stats["events_processed"]

        if total_events > 0:
            self._stats["average_processing_time"] = (
                (current_avg * (total_events - event_count) + processing_time) / total_events
            )

    def get_processing_stats(self) -> dict[str, Any]:
        """取得處理統計資訊.

        Returns:
            統計資訊字典
        """
        current_time = datetime.now()
        uptime = (current_time - self._stats["last_reset"]).total_seconds()

        return {
            **self._stats,
            "queue_sizes": {
                "normal": len(self._event_queue),
                "priority": len(self._priority_queue),
                "processing": len(self._processing_tasks)
            },
            "uptime_seconds": uptime,
            "events_per_second": self._stats["events_processed"] / uptime if uptime > 0 else 0
        }

    def reset_stats(self) -> None:
        """重置處理統計."""
        self._stats = {
            "events_processed": 0,
            "events_filtered": 0,
            "achievements_triggered": 0,
            "processing_errors": 0,
            "average_processing_time": 0.0,
            "last_reset": datetime.now()
        }
        logger.info("處理統計已重置")


__all__ = [
    "EventTriggerContext",
    "EventTriggerProcessor",
    "TriggerResult",
]
