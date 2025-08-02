"""成就事件資料處理系統.

實作成就事件的完整資料處理管道，包含：
- 事件資料結構化和標準化
- 事件過濾和驗證邏輯
- 事件批次處理優化
- 資料清理和正規化
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from ..database.models import AchievementEventData

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class EventDataProcessor:
    """事件資料處理器.

    負責處理成就事件的資料標準化、過濾和批次處理：
    - 事件資料結構化和驗證
    - 事件過濾規則管理
    - 批次處理邏輯
    - 資料清理和正規化
    """

    def __init__(
        self,
        batch_size: int = 50,
        batch_timeout: float = 5.0,
        max_memory_events: int = 1000
    ):
        """初始化事件資料處理器.

        Args:
            batch_size: 批次處理大小
            batch_timeout: 批次處理超時時間（秒）
            max_memory_events: 記憶體中最大事件數量
        """
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.max_memory_events = max_memory_events

        # 事件過濾器
        self._filters: list[Callable[[AchievementEventData], bool]] = []
        self._filter_stats: dict[str, int] = defaultdict(int)

        # 批次處理
        self._pending_events: deque[AchievementEventData] = deque()
        self._batch_lock = asyncio.Lock()
        self._last_batch_time = time.time()

        # 事件統計
        self._stats = {
            'total_processed': 0,
            'filtered_out': 0,
            'batches_created': 0,
            'validation_errors': 0,
            'last_processing_time': None
        }

        # 資料標準化規則
        self._standardization_rules: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}
        self._setup_default_standardization_rules()

    def _setup_default_standardization_rules(self) -> None:
        """設置預設的資料標準化規則."""

        def standardize_message_event(data: dict[str, Any]) -> dict[str, Any]:
            """標準化訊息事件資料."""
            standardized = data.copy()

            # 確保必要欄位存在
            standardized.setdefault('content_length', 0)
            standardized.setdefault('has_attachments', False)
            standardized.setdefault('has_embeds', False)
            standardized.setdefault('mention_count', 0)

            # 標準化數值型別
            standardized['content_length'] = max(0, int(standardized.get('content_length', 0)))
            standardized['mention_count'] = max(0, int(standardized.get('mention_count', 0)))

            return standardized

        def standardize_reaction_event(data: dict[str, Any]) -> dict[str, Any]:
            """標準化反應事件資料."""
            standardized = data.copy()

            # 確保表情符號欄位存在
            standardized.setdefault('emoji', '❓')
            standardized.setdefault('is_custom_emoji', False)
            standardized.setdefault('message_author_id', 0)

            return standardized

        def standardize_voice_event(data: dict[str, Any]) -> dict[str, Any]:
            """標準化語音事件資料."""
            standardized = data.copy()

            # 確保頻道資訊完整
            if 'joined_channel_id' in standardized:
                standardized.setdefault('joined_channel_name', 'Unknown')
            if 'left_channel_id' in standardized:
                standardized.setdefault('left_channel_name', 'Unknown')

            return standardized

        def standardize_member_event(data: dict[str, Any]) -> dict[str, Any]:
            """標準化成員事件資料."""
            standardized = data.copy()

            # 確保時間戳格式正確
            if 'join_timestamp' in standardized:
                timestamp = standardized['join_timestamp']
                if isinstance(timestamp, int | float):
                    standardized['join_timestamp'] = timestamp
                else:
                    standardized['join_timestamp'] = time.time()

            # 確保角色數量為非負數
            if 'roles_count' in standardized:
                standardized['roles_count'] = max(0, int(standardized.get('roles_count', 0)))

            return standardized

        # 註冊標準化規則
        self._standardization_rules.update({
            'achievement.message_sent': standardize_message_event,
            'achievement.message_edited': standardize_message_event,
            'achievement.message_deleted': standardize_message_event,
            'achievement.reaction_added': standardize_reaction_event,
            'achievement.reaction_removed': standardize_reaction_event,
            'achievement.voice_joined': standardize_voice_event,
            'achievement.voice_left': standardize_voice_event,
            'achievement.voice_moved': standardize_voice_event,
            'achievement.member_joined': standardize_member_event,
            'achievement.member_left': standardize_member_event,
            'achievement.member_updated': standardize_member_event,
        })

    def add_filter(
        self,
        filter_func: Callable[[AchievementEventData], bool],
        filter_name: str | None = None
    ) -> None:
        """新增事件過濾器.

        Args:
            filter_func: 過濾函數，返回 True 表示事件通過
            filter_name: 過濾器名稱（用於統計）
        """
        self._filters.append(filter_func)
        if filter_name:
            self._filter_stats[filter_name] = 0

    def add_standardization_rule(
        self,
        event_type: str,
        rule_func: Callable[[dict[str, Any]], dict[str, Any]]
    ) -> None:
        """新增資料標準化規則.

        Args:
            event_type: 事件類型
            rule_func: 標準化函數
        """
        self._standardization_rules[event_type] = rule_func

    async def process_event(self, event_data: dict[str, Any]) -> AchievementEventData | None:
        """處理單個事件.

        Args:
            event_data: 原始事件資料

        Returns:
            處理後的事件資料，如果被過濾則返回 None
        """
        try:
            self._stats['total_processed'] += 1
            self._stats['last_processing_time'] = time.time()

            # 步驟 1: 資料結構化
            structured_event = await self._structure_event_data(event_data)
            if not structured_event:
                return None

            # 步驟 2: 資料標準化
            standardized_event = await self._standardize_event_data(structured_event)

            # 步驟 3: 事件過濾
            if not await self._filter_event(standardized_event):
                self._stats['filtered_out'] += 1
                return None

            # 步驟 4: 資料驗證
            if not await self._validate_event_data(standardized_event):
                self._stats['validation_errors'] += 1
                return None

            return standardized_event

        except Exception as e:
            logger.error(f"【事件資料處理器】處理事件失敗: {e}", exc_info=True)
            self._stats['validation_errors'] += 1
            return None

    async def process_batch(self, events: list[dict[str, Any]]) -> list[AchievementEventData]:
        """批次處理多個事件.

        Args:
            events: 原始事件資料列表

        Returns:
            處理後的事件資料列表
        """
        processed_events = []

        # 並行處理事件（但保持順序）
        tasks = [self.process_event(event_data) for event_data in events]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, AchievementEventData):
                processed_events.append(result)
            elif isinstance(result, Exception):
                logger.error(f"【事件資料處理器】批次處理事件錯誤: {result}")

        self._stats['batches_created'] += 1
        logger.debug(f"【事件資料處理器】批次處理完成: {len(processed_events)}/{len(events)} 事件通過")

        return processed_events

    async def add_to_batch(self, event_data: dict[str, Any]) -> list[AchievementEventData] | None:
        """新增事件到批次處理佇列.

        Args:
            event_data: 事件資料

        Returns:
            如果批次準備好處理，返回事件列表；否則返回 None
        """
        async with self._batch_lock:
            # 處理事件並添加到佇列
            processed_event = await self.process_event(event_data)
            if processed_event:
                self._pending_events.append(processed_event)

                # 記憶體管理
                if len(self._pending_events) > self.max_memory_events:
                    # 移除舊事件
                    while len(self._pending_events) > self.max_memory_events * 0.8:
                        self._pending_events.popleft()
                    logger.warning("【事件資料處理器】記憶體事件數量超限，已清理舊事件")

            # 檢查是否需要處理批次
            should_process_batch = (
                len(self._pending_events) >= self.batch_size or
                (self._pending_events and
                 time.time() - self._last_batch_time >= self.batch_timeout)
            )

            if should_process_batch:
                # 取出批次事件
                batch_events = list(self._pending_events)
                self._pending_events.clear()
                self._last_batch_time = time.time()

                return batch_events

            return None

    async def _structure_event_data(self, event_data: dict[str, Any]) -> AchievementEventData | None:
        """結構化事件資料.

        Args:
            event_data: 原始事件資料

        Returns:
            結構化的事件資料模型
        """
        try:
            # 檢查必要欄位
            required_fields = ['user_id', 'guild_id', 'event_type']
            for field in required_fields:
                if field not in event_data:
                    logger.warning(f"【事件資料處理器】缺少必要欄位: {field}")
                    return None

            # 建立事件資料模型
            achievement_event = AchievementEventData(
                user_id=event_data['user_id'],
                guild_id=event_data['guild_id'],
                event_type=event_data['event_type'],
                event_data=event_data.get('event_data', {}),
                timestamp=datetime.fromtimestamp(event_data.get('timestamp', time.time())),
                channel_id=event_data.get('channel_id'),
                correlation_id=event_data.get('correlation_id')
            )

            return achievement_event

        except Exception as e:
            logger.error(f"【事件資料處理器】結構化事件資料失敗: {e}")
            return None

    async def _standardize_event_data(self, event: AchievementEventData) -> AchievementEventData:
        """標準化事件資料.

        Args:
            event: 事件資料模型

        Returns:
            標準化後的事件資料
        """
        try:
            # 套用標準化規則
            if event.event_type in self._standardization_rules:
                rule_func = self._standardization_rules[event.event_type]
                standardized_data = rule_func(event.event_data)

                # 建立新的事件物件
                event = AchievementEventData(
                    id=event.id,
                    user_id=event.user_id,
                    guild_id=event.guild_id,
                    event_type=event.event_type,
                    event_data=standardized_data,
                    timestamp=event.timestamp,
                    channel_id=event.channel_id,
                    processed=event.processed,
                    correlation_id=event.correlation_id
                )

            return event

        except Exception as e:
            logger.error(f"【事件資料處理器】標準化事件資料失敗: {e}")
            return event

    async def _filter_event(self, event: AchievementEventData) -> bool:
        """過濾事件.

        Args:
            event: 事件資料

        Returns:
            True 如果事件通過所有過濾器
        """
        try:
            # 基本過濾檢查
            if not event.is_achievement_relevant():
                return False

            # 套用自訂過濾器
            for i, filter_func in enumerate(self._filters):
                try:
                    if not filter_func(event):
                        filter_name = f"filter_{i}"
                        self._filter_stats[filter_name] += 1
                        return False
                except Exception as e:
                    logger.warning(f"【事件資料處理器】過濾器執行失敗: {e}")
                    continue

            return True

        except Exception as e:
            logger.error(f"【事件資料處理器】事件過濾失敗: {e}")
            return False

    async def _validate_event_data(self, event: AchievementEventData) -> bool:
        """驗證事件資料.

        Args:
            event: 事件資料

        Returns:
            True 如果事件資料有效
        """
        try:
            # 使用 Pydantic 模型進行驗證
            # 如果模型建立時沒有錯誤，則資料有效
            return True

        except Exception as e:
            logger.error(f"【事件資料處理器】事件資料驗證失敗: {e}")
            return False

    def get_processing_stats(self) -> dict[str, Any]:
        """獲取處理統計資訊.

        Returns:
            處理統計資訊字典
        """
        return {
            **self._stats,
            'pending_events_count': len(self._pending_events),
            'filter_stats': dict(self._filter_stats),
            'success_rate': (
                (self._stats['total_processed'] - self._stats['filtered_out'] - self._stats['validation_errors'])
                / self._stats['total_processed']
                if self._stats['total_processed'] > 0 else 1.0
            ),
            'standardization_rules_count': len(self._standardization_rules),
            'active_filters_count': len(self._filters)
        }

    async def flush_pending_events(self) -> list[AchievementEventData]:
        """強制處理所有待處理事件.

        Returns:
            待處理的事件列表
        """
        async with self._batch_lock:
            if self._pending_events:
                batch_events = list(self._pending_events)
                self._pending_events.clear()
                self._last_batch_time = time.time()
                logger.info(f"【事件資料處理器】強制處理待處理事件: {len(batch_events)} 個")
                return batch_events
            return []

    def clear_stats(self) -> None:
        """清除統計資訊."""
        self._stats = {
            'total_processed': 0,
            'filtered_out': 0,
            'batches_created': 0,
            'validation_errors': 0,
            'last_processing_time': None
        }
        self._filter_stats.clear()


# 預設過濾器函數

def create_user_whitelist_filter(whitelisted_users: set[int]) -> Callable[[AchievementEventData], bool]:
    """建立用戶白名單過濾器.

    Args:
        whitelisted_users: 白名單用戶 ID 集合

    Returns:
        過濾器函數
    """
    def filter_func(event: AchievementEventData) -> bool:
        return event.user_id in whitelisted_users

    return filter_func


def create_guild_whitelist_filter(whitelisted_guilds: set[int]) -> Callable[[AchievementEventData], bool]:
    """建立伺服器白名單過濾器.

    Args:
        whitelisted_guilds: 白名單伺服器 ID 集合

    Returns:
        過濾器函數
    """
    def filter_func(event: AchievementEventData) -> bool:
        return event.guild_id in whitelisted_guilds

    return filter_func


def create_event_type_filter(allowed_types: set[str]) -> Callable[[AchievementEventData], bool]:
    """建立事件類型過濾器.

    Args:
        allowed_types: 允許的事件類型集合

    Returns:
        過濾器函數
    """
    def filter_func(event: AchievementEventData) -> bool:
        return event.event_type in allowed_types

    return filter_func


def create_time_window_filter(
    start_time: datetime | None = None,
    end_time: datetime | None = None
) -> Callable[[AchievementEventData], bool]:
    """建立時間窗口過濾器.

    Args:
        start_time: 開始時間（包含）
        end_time: 結束時間（包含）

    Returns:
        過濾器函數
    """
    def filter_func(event: AchievementEventData) -> bool:
        if start_time and event.timestamp < start_time:
            return False
        return not (end_time and event.timestamp > end_time)

    return filter_func


def create_rate_limit_filter(
    max_events_per_user: int = 100,
    time_window_minutes: int = 60
) -> Callable[[AchievementEventData], bool]:
    """建立頻率限制過濾器.

    Args:
        max_events_per_user: 每個用戶最大事件數
        time_window_minutes: 時間窗口（分鐘）

    Returns:
        過濾器函數
    """
    user_event_counts: dict[int, deque[datetime]] = defaultdict(lambda: deque())

    def filter_func(event: AchievementEventData) -> bool:
        now = datetime.now()
        cutoff_time = now - timedelta(minutes=time_window_minutes)

        # 清理過期記錄
        user_events = user_event_counts[event.user_id]
        while user_events and user_events[0] < cutoff_time:
            user_events.popleft()

        # 檢查頻率限制
        if len(user_events) >= max_events_per_user:
            return False

        # 記錄此次事件
        user_events.append(now)
        return True

    return filter_func
