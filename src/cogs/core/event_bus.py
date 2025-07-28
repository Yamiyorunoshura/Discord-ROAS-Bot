"""
🚌 事件總線系統
Discord ADR Bot v1.6 - 統一事件管理架構

提供企業級的事件驅動功能:
- 事件發布/訂閱機制
- 事件過濾和路由
- 事件持久化和重放
- 事件優先級管理
- 異步事件處理
- 事件批處理優化
- 智能事件路由
- 性能監控和分析

作者:Discord ADR Bot 架構師
版本:v1.6
"""

import asyncio
import json
import logging
import statistics
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    TypeVar,
)

# 設置日誌
logger = logging.getLogger(__name__)

# 類型變量
T = TypeVar("T")
EventHandler = Callable[["Event"], Awaitable[None]]


class EventPriority(Enum):
    """事件優先級枚舉"""

    CRITICAL = 0  # 關鍵事件,最高優先級
    HIGH = 1  # 高優先級事件
    NORMAL = 2  # 普通優先級事件
    LOW = 3  # 低優先級事件
    BACKGROUND = 4  # 背景事件,最低優先級


class EventStatus(Enum):
    """事件狀態枚舉"""

    PENDING = "pending"  # 待處理
    PROCESSING = "processing"  # 處理中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 處理失敗
    CANCELLED = "cancelled"  # 已取消
    BATCHED = "batched"  # 已批處理


class EventProcessingMode(Enum):
    """事件處理模式枚舉"""

    IMMEDIATE = "immediate"  # 立即處理
    BATCHED = "batched"  # 批處理
    SCHEDULED = "scheduled"  # 定時處理
    ADAPTIVE = "adaptive"  # 自適應處理


@dataclass
class Event:
    """事件基礎類別"""

    event_type: str
    data: dict[str, Any] = field(default_factory=dict)
    source: str | None = None
    target: str | None = None
    priority: EventPriority = EventPriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    event_id: str | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    processing_mode: EventProcessingMode = EventProcessingMode.IMMEDIATE
    batch_key: str | None = None  # 批處理鍵
    retry_count: int = 0
    max_retries: int = 3

    def __post_init__(self):
        if self.event_id is None:
            self.event_id = f"{self.event_type}_{int(self.timestamp * 1000000)}"

        # 自動生成批處理鍵
        if (
            self.batch_key is None
            and self.processing_mode == EventProcessingMode.BATCHED
        ):
            self.batch_key = f"{self.event_type}_{self.source or 'default'}"

    def __lt__(self, other):
        """用於優先級隊列排序"""
        return self.priority.value < other.priority.value

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式"""
        return {
            "event_type": self.event_type,
            "data": self.data,
            "source": self.source,
            "target": self.target,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
            "event_id": self.event_id,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
            "processing_mode": self.processing_mode.value,
            "batch_key": self.batch_key,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """從字典創建事件"""
        return cls(
            event_type=data["event_type"],
            data=data.get("data", {}),
            source=data.get("source"),
            target=data.get("target"),
            priority=EventPriority(data.get("priority", EventPriority.NORMAL.value)),
            timestamp=data.get("timestamp", time.time()),
            event_id=data.get("event_id"),
            correlation_id=data.get("correlation_id"),
            metadata=data.get("metadata", {}),
            processing_mode=EventProcessingMode(
                data.get("processing_mode", EventProcessingMode.IMMEDIATE.value)
            ),
            batch_key=data.get("batch_key"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
        )

    def can_retry(self) -> bool:
        """檢查是否可以重試"""
        return self.retry_count < self.max_retries

    def increment_retry(self):
        """增加重試次數"""
        self.retry_count += 1

    def get_size(self) -> int:
        """估算事件大小(字節)"""
        try:
            return len(json.dumps(self.to_dict()).encode("utf-8"))
        except:
            return len(str(self.data).encode("utf-8"))


@dataclass
class EventBatch:
    """事件批次"""

    batch_key: str
    events: list[Event] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    max_size: int = 100
    max_wait_time: float = 1.0  # 最大等待時間(秒)

    def add_event(self, event: Event) -> bool:
        """添加事件到批次"""
        if len(self.events) >= self.max_size:
            return False

        event.processing_mode = EventProcessingMode.BATCHED
        self.events.append(event)
        return True

    def is_ready(self) -> bool:
        """檢查批次是否準備好處理"""
        return (
            len(self.events) >= self.max_size
            or time.time() - self.created_at >= self.max_wait_time
        )

    def get_total_size(self) -> int:
        """獲取批次總大小"""
        return sum(event.get_size() for event in self.events)


@dataclass
class EventSubscription:
    """事件訂閱描述符"""

    handler: EventHandler
    event_types: set[str]
    filters: list[Callable[["Event"], bool]] = field(default_factory=list)
    priority: EventPriority = EventPriority.NORMAL
    max_retries: int = 3
    retry_delay: float = 1.0
    enabled: bool = True
    subscriber_id: str | None = None
    processing_mode: EventProcessingMode = EventProcessingMode.IMMEDIATE
    batch_size: int = 10
    max_batch_wait: float = 1.0

    def matches(self, event: Event) -> bool:
        """檢查事件是否匹配此訂閱"""
        # 檢查事件類型
        if event.event_type not in self.event_types and "*" not in self.event_types:
            return False

        # 檢查過濾器
        for filter_func in self.filters:
            try:
                if not filter_func(event):
                    return False
            except Exception as e:
                logger.warning(f"【事件總線】過濾器執行失敗: {e}")
                return False

        return True


class EventMetrics:
    """事件指標收集器"""

    def __init__(self):
        self.total_events_published = 0
        self.total_events_processed = 0
        self.total_events_failed = 0
        self.total_processing_time = 0.0
        self.events_by_type: dict[str, int] = defaultdict(int)
        self.events_by_priority: dict[str, int] = defaultdict(int)
        self.processing_times: deque[float] = deque(maxlen=1000)
        self.error_count = 0
        self.batch_count = 0
        self.batch_sizes: deque[int] = deque(maxlen=100)
        self.created_at = time.time()
        self._lock = asyncio.Lock()

    async def record_event_published(self, event: Event):
        """記錄事件發布"""
        async with self._lock:
            self.total_events_published += 1
            self.events_by_type[event.event_type] += 1
            self.events_by_priority[event.priority.name] += 1

    async def record_event_processed(
        self, event: Event, processing_time: float, success: bool = True
    ):
        """記錄事件處理"""
        async with self._lock:
            if success:
                self.total_events_processed += 1
                self.total_processing_time += processing_time
                self.processing_times.append(processing_time)
            else:
                self.total_events_failed += 1
                self.error_count += 1

    async def record_batch_processed(self, batch: EventBatch, processing_time: float):
        """記錄批次處理"""
        async with self._lock:
            self.batch_count += 1
            self.batch_sizes.append(len(batch.events))

            # 記錄批次中每個事件的處理
            for event in batch.events:
                await self.record_event_processed(
                    event, processing_time / len(batch.events)
                )

    async def get_metrics_summary(self) -> dict[str, Any]:
        """獲取指標摘要"""
        async with self._lock:
            uptime = time.time() - self.created_at
            avg_processing_time = (
                statistics.mean(self.processing_times) if self.processing_times else 0.0
            )
            avg_batch_size = (
                statistics.mean(self.batch_sizes) if self.batch_sizes else 0.0
            )

            return {
                "uptime_seconds": uptime,
                "total_events_published": self.total_events_published,
                "total_events_processed": self.total_events_processed,
                "total_events_failed": self.total_events_failed,
                "success_rate": (
                    self.total_events_processed
                    / (self.total_events_processed + self.total_events_failed)
                    if (self.total_events_processed + self.total_events_failed) > 0
                    else 1.0
                ),
                "avg_processing_time_ms": avg_processing_time * 1000,
                "events_per_second": self.total_events_published / uptime
                if uptime > 0
                else 0.0,
                "events_by_type": dict(self.events_by_type),
                "events_by_priority": dict(self.events_by_priority),
                "batch_count": self.batch_count,
                "avg_batch_size": avg_batch_size,
                "error_rate": self.error_count / self.total_events_published
                if self.total_events_published > 0
                else 0.0,
            }


class EventRouter:
    """智能事件路由器"""

    def __init__(self):
        self.routing_rules: list[Callable[[Event], list[str]]] = []
        self.performance_cache: dict[str, float] = {}
        self._lock = asyncio.Lock()

    def add_routing_rule(self, rule: Callable[[Event], list[str]]):
        """添加路由規則"""
        self.routing_rules.append(rule)

    async def route_event(
        self, event: Event, subscriptions: dict[str, EventSubscription]
    ) -> list[str]:
        """路由事件到合適的訂閱者"""
        async with self._lock:
            matched_subscribers = []

            # 應用路由規則
            for rule in self.routing_rules:
                try:
                    rule_results = rule(event)
                    matched_subscribers.extend(rule_results)
                except Exception as e:
                    logger.warning(f"【事件總線】路由規則執行失敗: {e}")

            # 如果沒有路由規則匹配,使用默認匹配
            if not matched_subscribers:
                for subscriber_id, subscription in subscriptions.items():
                    if subscription.enabled and subscription.matches(event):
                        matched_subscribers.append(subscriber_id)

            # 根據性能緩存排序訂閱者
            matched_subscribers.sort(
                key=lambda sub_id: self.performance_cache.get(sub_id, 0.0)
            )

            return matched_subscribers

    async def update_performance(self, subscriber_id: str, processing_time: float):
        """更新訂閱者性能指標"""
        async with self._lock:
            # 使用指數移動平均更新性能指標
            if subscriber_id in self.performance_cache:
                self.performance_cache[subscriber_id] = (
                    0.7 * self.performance_cache[subscriber_id] + 0.3 * processing_time
                )
            else:
                self.performance_cache[subscriber_id] = processing_time


class EventCompressor:
    """事件壓縮器"""

    def __init__(self):
        self.compression_rules: dict[str, Callable[[list[Event]], list[Event]]] = {}

    def register_compression_rule(
        self, event_type: str, rule: Callable[[list[Event]], list[Event]]
    ):
        """註冊壓縮規則"""
        self.compression_rules[event_type] = rule

    async def compress_events(self, events: list[Event]) -> list[Event]:
        """壓縮事件列表"""
        if not events:
            return events

        # 按事件類型分組
        events_by_type = defaultdict(list)
        for event in events:
            events_by_type[event.event_type].append(event)

        compressed_events = []

        # 對每種事件類型應用壓縮規則
        for event_type, type_events in events_by_type.items():
            if event_type in self.compression_rules:
                try:
                    compressed = self.compression_rules[event_type](type_events)
                    compressed_events.extend(compressed)
                except Exception as e:
                    logger.warning(f"【事件總線】事件壓縮失敗 {event_type}: {e}")
                    compressed_events.extend(type_events)
            else:
                compressed_events.extend(type_events)

        return compressed_events


class EventFilter:
    """事件過濾器工具類別"""

    @staticmethod
    def by_source(source: str) -> Callable[["Event"], bool]:
        """按來源過濾"""
        return lambda event: event.source == source

    @staticmethod
    def by_target(target: str) -> Callable[["Event"], bool]:
        """按目標過濾"""
        return lambda event: event.target == target

    @staticmethod
    def by_priority(min_priority: EventPriority) -> Callable[["Event"], bool]:
        """按優先級過濾"""
        return lambda event: event.priority.value <= min_priority.value

    @staticmethod
    def by_data_key(key: str, value: Any = None) -> Callable[["Event"], bool]:
        """按數據鍵過濾"""
        if value is None:
            return lambda event: key in event.data
        else:
            return lambda event: event.data.get(key) == value

    @staticmethod
    def by_time_range(start_time: float, end_time: float) -> Callable[["Event"], bool]:
        """按時間範圍過濾"""
        return lambda event: start_time <= event.timestamp <= end_time

    @staticmethod
    def by_correlation_id(correlation_id: str) -> Callable[["Event"], bool]:
        """按關聯ID過濾"""
        return lambda event: event.correlation_id == correlation_id


class EventPersistence(ABC):
    """事件持久化抽象基類"""

    @abstractmethod
    async def save_event(self, event: Event) -> bool:
        """保存事件"""
        pass

    @abstractmethod
    async def load_events(
        self,
        event_type: str | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """加載事件"""
        pass

    @abstractmethod
    async def delete_events(self, event_ids: list[str]) -> int:
        """刪除事件"""
        pass

    @abstractmethod
    async def save_batch(self, batch: EventBatch) -> bool:
        """保存事件批次"""
        pass


class MemoryEventPersistence(EventPersistence):
    """內存事件持久化實現"""

    def __init__(self, max_events: int = 10000):
        self.events: list[Event] = []
        self.batches: list[EventBatch] = []
        self.max_events = max_events
        self._lock = asyncio.Lock()

    async def save_event(self, event: Event) -> bool:
        """保存事件到內存"""
        async with self._lock:
            self.events.append(event)

            # 如果超過最大數量,移除最舊的事件
            if len(self.events) > self.max_events:
                self.events = self.events[-self.max_events :]

            return True

    async def save_batch(self, batch: EventBatch) -> bool:
        """保存事件批次"""
        async with self._lock:
            self.batches.append(batch)

            # 保存批次中的所有事件
            for event in batch.events:
                await self.save_event(event)

            return True

    async def load_events(
        self,
        event_type: str | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """從內存加載事件"""
        async with self._lock:
            filtered_events = []

            for event in self.events:
                # 應用過濾條件
                if event_type and event.event_type != event_type:
                    continue
                if start_time and event.timestamp < start_time:
                    continue
                if end_time and event.timestamp > end_time:
                    continue

                filtered_events.append(event)

                if len(filtered_events) >= limit:
                    break

            return filtered_events

    async def delete_events(self, event_ids: list[str]) -> int:
        """從內存刪除事件"""
        async with self._lock:
            deleted_count = 0
            self.events = [
                event
                for event in self.events
                if event.event_id not in event_ids
                or (deleted_count := deleted_count + 1, False)[1]
            ]
            return deleted_count


class EventBus:
    """高性能事件總線"""

    def __init__(self, persistence: EventPersistence | None = None):
        self._subscriptions: dict[str, EventSubscription] = {}
        self._event_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._batch_queues: dict[str, EventBatch] = {}
        self._processing_tasks: set[asyncio.Task] = set()
        self._batch_tasks: set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._batch_lock = asyncio.Lock()

        # 組件初始化
        self.persistence = persistence or MemoryEventPersistence()
        self.metrics = EventMetrics()
        self.router = EventRouter()
        self.compressor = EventCompressor()

        # 配置參數
        self.max_workers = 10
        self.batch_processing_interval = 0.1  # 100ms
        self.enable_compression = True
        self.enable_batch_processing = True

        # 性能監控
        self._processing_times: deque[float] = deque(maxlen=1000)
        self._error_counts: dict[str, int] = defaultdict(int)

        # 自動設置壓縮規則
        self._setup_default_compression_rules()

    def _setup_default_compression_rules(self):
        """設置默認壓縮規則"""

        # 合併相同類型的狀態更新事件
        def merge_status_updates(events: list[Event]) -> list[Event]:
            if len(events) <= 1:
                return events

            # 保留最新的狀態更新
            latest_event = max(events, key=lambda e: e.timestamp)
            return [latest_event]

        self.compressor.register_compression_rule("status_update", merge_status_updates)
        self.compressor.register_compression_rule("heartbeat", merge_status_updates)

        # 合併計數器事件
        def merge_counter_events(events: list[Event]) -> list[Event]:
            if len(events) <= 1:
                return events

            total_count = sum(event.data.get("count", 1) for event in events)
            merged_event = events[-1]  # 使用最新事件作為基礎
            merged_event.data["count"] = total_count
            return [merged_event]

        self.compressor.register_compression_rule(
            "counter_increment", merge_counter_events
        )

    async def initialize(self):
        """初始化事件總線"""
        # 啟動處理工作者
        for _i in range(self.max_workers):
            task = asyncio.create_task(self._process_events())
            self._processing_tasks.add(task)
            task.add_done_callback(self._processing_tasks.discard)

        # 啟動批處理任務
        if self.enable_batch_processing:
            batch_task = asyncio.create_task(self._process_batches())
            self._batch_tasks.add(batch_task)
            batch_task.add_done_callback(self._batch_tasks.discard)

        logger.info("【事件總線】事件總線已初始化")

    async def shutdown(self):
        """關閉事件總線"""
        logger.info("【事件總線】正在關閉事件總線...")

        # 設置關閉信號
        self._shutdown_event.set()

        # 等待所有任務完成
        all_tasks = self._processing_tasks | self._batch_tasks
        if all_tasks:
            await asyncio.gather(*all_tasks, return_exceptions=True)

        logger.info("【事件總線】事件總線已關閉")

    def subscribe(
        self,
        event_types: list[str],
        handler: EventHandler,
        filters: list[Callable[["Event | None"], bool]] | None = None,
        priority: EventPriority = EventPriority.NORMAL,
        max_retries: int = 3,
        subscriber_id: str | None = None,
        processing_mode: EventProcessingMode = EventProcessingMode.IMMEDIATE,
        batch_size: int = 10,
    ) -> str:
        """訂閱事件"""
        if isinstance(event_types, str):
            event_types = [event_types]

        if subscriber_id is None:
            subscriber_id = f"sub_{int(time.time() * 1000000)}_{id(handler)}"

        subscription = EventSubscription(
            handler=handler,
            event_types=set(event_types),
            filters=filters or [],
            priority=priority,
            max_retries=max_retries,
            subscriber_id=subscriber_id,
            processing_mode=processing_mode,
            batch_size=batch_size,
        )

        self._subscriptions[subscriber_id] = subscription

        logger.debug(f"【事件總線】新訂閱: {subscriber_id} -> {event_types}")
        return subscriber_id

    def unsubscribe(self, subscriber_id: str) -> bool:
        """取消訂閱"""
        if subscriber_id in self._subscriptions:
            del self._subscriptions[subscriber_id]
            logger.debug(f"【事件總線】取消訂閱: {subscriber_id}")
            return True
        return False

    async def publish(self, event: Event, persist: bool = True) -> bool:
        """發布事件"""
        try:
            # 記錄指標
            await self.metrics.record_event_published(event)

            # 持久化事件
            if persist:
                await self.persistence.save_event(event)

            # 根據處理模式路由事件
            if (
                event.processing_mode == EventProcessingMode.BATCHED
                and self.enable_batch_processing
            ):
                await self._add_to_batch(event)
            else:
                # 立即處理
                await self._event_queue.put((event.priority.value, time.time(), event))

            return True

        except Exception as e:
            logger.error(f"【事件總線】發布事件失敗: {e}")
            return False

    async def publish_batch(self, events: list[Event], persist: bool = True) -> bool:
        """批量發布事件"""
        try:
            # 壓縮事件(如果啟用)
            if self.enable_compression and len(events) > 1:
                events = await self.compressor.compress_events(events)

            # 發布每個事件
            for event in events:
                await self.publish(event, persist)

            return True

        except Exception as e:
            logger.error(f"【事件總線】批量發布事件失敗: {e}")
            return False

    async def publish_sync(self, event: Event) -> list[Any]:
        """同步發布事件並等待所有處理完成"""
        results = []

        # 獲取匹配的訂閱者
        matched_subscribers = await self.router.route_event(event, self._subscriptions)

        # 同步執行所有處理器
        for subscriber_id in matched_subscribers:
            subscription = self._subscriptions.get(subscriber_id)
            if subscription and subscription.enabled:
                try:
                    start_time = time.time()
                    result = await subscription.handler(event)
                    processing_time = time.time() - start_time

                    results.append(result)

                    # 更新性能指標
                    await self.router.update_performance(subscriber_id, processing_time)
                    await self.metrics.record_event_processed(
                        event, processing_time, True
                    )

                except Exception as e:
                    logger.error(f"【事件總線】同步處理事件失敗 {subscriber_id}: {e}")
                    results.append(e)
                    await self.metrics.record_event_processed(event, 0, False)

        return results

    async def _add_to_batch(self, event: Event):
        """添加事件到批處理隊列"""
        async with self._batch_lock:
            batch_key = event.batch_key or f"{event.event_type}_default"

            if batch_key not in self._batch_queues:
                self._batch_queues[batch_key] = EventBatch(
                    batch_key=batch_key,
                    max_size=10,  # 可配置
                    max_wait_time=1.0,  # 可配置
                )

            batch = self._batch_queues[batch_key]
            if not batch.add_event(event):
                # 批次已滿,處理當前批次並創建新批次
                await self._process_batch(batch)

                # 創建新批次
                new_batch = EventBatch(
                    batch_key=batch_key, max_size=10, max_wait_time=1.0
                )
                new_batch.add_event(event)
                self._batch_queues[batch_key] = new_batch

    async def _process_batches(self):
        """批處理任務循環"""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.batch_processing_interval)

                async with self._batch_lock:
                    ready_batches = []

                    for batch_key, batch in list(self._batch_queues.items()):
                        if batch.is_ready():
                            ready_batches.append(batch)
                            del self._batch_queues[batch_key]

                # 處理準備好的批次
                for batch in ready_batches:
                    await self._process_batch(batch)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"【事件總線】批處理循環錯誤: {e}")
                await asyncio.sleep(1)

    async def _process_batch(self, batch: EventBatch):
        """處理事件批次"""
        try:
            start_time = time.time()

            # 持久化批次
            await self.persistence.save_batch(batch)

            # 獲取批次中所有事件的匹配訂閱者
            all_subscribers = set()
            for event in batch.events:
                subscribers = await self.router.route_event(event, self._subscriptions)
                all_subscribers.update(subscribers)

            # 為每個訂閱者處理批次
            for subscriber_id in all_subscribers:
                subscription = self._subscriptions.get(subscriber_id)
                if not subscription or not subscription.enabled:
                    continue

                # 過濾出該訂閱者關心的事件
                relevant_events = [
                    event for event in batch.events if subscription.matches(event)
                ]

                if relevant_events:
                    await self._execute_batch_handler(subscription, relevant_events)

            processing_time = time.time() - start_time
            await self.metrics.record_batch_processed(batch, processing_time)

            logger.debug(
                f"【事件總線】批次處理完成: {batch.batch_key} ({len(batch.events)} 事件)"
            )

        except Exception as e:
            logger.error(f"【事件總線】批次處理失敗: {e}")

    async def _execute_batch_handler(
        self, subscription: EventSubscription, events: list[Event]
    ):
        """執行批次處理器"""
        try:
            # 如果處理器支持批次處理,傳遞事件列表
            if hasattr(subscription.handler, "__annotations__"):
                sig = subscription.handler.__annotations__
                if "events" in sig or len(sig) > 1:
                    # 支持批次處理 - 但目前的處理器只接受單個事件,所以逐個處理
                    for event in events:
                        await subscription.handler(event)
                    return

            # 否則逐個處理事件
            for event in events:
                await subscription.handler(event)

        except Exception as e:
            logger.error(
                f"【事件總線】批次處理器執行失敗 {subscription.subscriber_id}: {e}"
            )

    async def _process_events(self):
        """事件處理工作者循環"""
        while not self._shutdown_event.is_set():
            try:
                # 從隊列獲取事件(帶超時)
                try:
                    priority, enqueue_time, event = await asyncio.wait_for(
                        self._event_queue.get(), timeout=1.0
                    )
                except TimeoutError:
                    continue

                await self._handle_event(event)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"【事件總線】事件處理工作者錯誤: {e}")
                await asyncio.sleep(0.1)

    async def _handle_event(self, event: Event):
        """處理單個事件"""
        try:
            # 獲取匹配的訂閱者
            matched_subscribers = await self.router.route_event(
                event, self._subscriptions
            )

            # 並發執行所有匹配的處理器
            tasks = []
            for subscriber_id in matched_subscribers:
                subscription = self._subscriptions.get(subscriber_id)
                if subscription and subscription.enabled:
                    task = asyncio.create_task(
                        self._execute_handler(event, subscription)
                    )
                    tasks.append(task)

            # 等待所有處理器完成
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"【事件總線】處理事件失敗 {event.event_id}: {e}")

    async def _execute_handler(self, event: Event, subscription: EventSubscription):
        """執行事件處理器"""
        retry_count = 0

        while retry_count <= subscription.max_retries:
            try:
                start_time = time.time()

                # 執行處理器
                await subscription.handler(event)

                processing_time = time.time() - start_time

                # 更新性能指標
                if subscription.subscriber_id:
                    await self.router.update_performance(
                        subscription.subscriber_id, processing_time
                    )
                await self.metrics.record_event_processed(event, processing_time, True)

                return  # 成功,退出重試循環

            except Exception as e:
                retry_count += 1
                processing_time = time.time() - start_time

                await self.metrics.record_event_processed(event, processing_time, False)

                if retry_count <= subscription.max_retries:
                    logger.warning(
                        f"【事件總線】處理器執行失敗,重試 {retry_count}/{subscription.max_retries}: "
                        f"{subscription.subscriber_id} - {e}"
                    )
                    await asyncio.sleep(subscription.retry_delay * retry_count)
                else:
                    logger.error(
                        f"【事件總線】處理器執行失敗,已達最大重試次數: "
                        f"{subscription.subscriber_id} - {e}"
                    )

    async def get_event_history(
        self, event_type: str | None = None, limit: int = 100
    ) -> list[Event]:
        """獲取事件歷史"""
        return await self.persistence.load_events(event_type=event_type, limit=limit)

    async def replay_events(
        self,
        event_type: str | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> int:
        """重放事件"""
        events = await self.persistence.load_events(
            event_type=event_type, start_time=start_time, end_time=end_time, limit=1000
        )

        replayed_count = 0
        for event in events:
            # 創建重放事件副本
            replay_event = Event(
                event_type=f"replay_{event.event_type}",
                data=event.data,
                source=event.source,
                target=event.target,
                priority=event.priority,
                correlation_id=event.correlation_id,
                metadata={**event.metadata, "original_event_id": event.event_id},
            )

            await self.publish(replay_event, persist=False)
            replayed_count += 1

        return replayed_count

    def get_metrics(self) -> dict[str, Any]:
        """獲取事件總線指標"""
        return {
            "subscriptions_count": len(self._subscriptions),
            "queue_size": self._event_queue.qsize(),
            "batch_queues_count": len(self._batch_queues),
            "processing_workers": len(self._processing_tasks),
            "batch_workers": len(self._batch_tasks),
        }

    async def get_detailed_metrics(self) -> dict[str, Any]:
        """獲取詳細指標"""
        basic_metrics = self.get_metrics()
        performance_metrics = await self.metrics.get_metrics_summary()

        return {
            **basic_metrics,
            **performance_metrics,
            "router_performance": self.router.performance_cache.copy(),
            "active_batches": {
                batch_key: {
                    "events_count": len(batch.events),
                    "created_at": batch.created_at,
                    "total_size": batch.get_total_size(),
                }
                for batch_key, batch in self._batch_queues.items()
            },
        }

    @asynccontextmanager
    async def event_scope(self, scope_name: str):
        """事件作用域上下文管理器"""
        scope_events = []

        async def scope_handler(event: Event):
            scope_events.append(event)

        # 訂閱所有事件
        subscription_id = self.subscribe(
            event_types=["*"],
            handler=scope_handler,
            subscriber_id=f"scope_{scope_name}_{int(time.time())}",
        )

        try:
            yield scope_events
        finally:
            self.unsubscribe(subscription_id)


# 全域事件總線實例
_global_event_bus: EventBus | None = None
_bus_lock = asyncio.Lock()


async def get_global_event_bus() -> EventBus:
    """獲取全域事件總線"""
    global _global_event_bus

    async with _bus_lock:
        if _global_event_bus is None:
            _global_event_bus = EventBus()
            await _global_event_bus.initialize()

    return _global_event_bus


async def dispose_global_event_bus():
    """釋放全域事件總線"""
    global _global_event_bus

    async with _bus_lock:
        if _global_event_bus is not None:
            await _global_event_bus.shutdown()
            _global_event_bus = None


# 便捷函數
async def publish_event(
    event_type: str,
    data: dict[str, Any | None] | None = None,
    source: str | None = None,
    target: str | None = None,
    priority: EventPriority = EventPriority.NORMAL,
    processing_mode: EventProcessingMode = EventProcessingMode.IMMEDIATE,
) -> bool:
    """發布事件的便捷函數"""
    event = Event(
        event_type=event_type,
        data=data or {},
        source=source,
        target=target,
        priority=priority,
        processing_mode=processing_mode,
    )

    bus = await get_global_event_bus()
    return await bus.publish(event)


async def publish_batch_events(events_data: list[dict[str, Any]]) -> bool:
    """批量發布事件的便捷函數"""
    events = [Event.from_dict(event_data) for event_data in events_data]

    bus = await get_global_event_bus()
    return await bus.publish_batch(events)


def event_handler(
    event_types: list[str],
    filters: list[Callable[["Event | None"], bool]] | None = None,
    priority: EventPriority = EventPriority.NORMAL,
    processing_mode: EventProcessingMode = EventProcessingMode.IMMEDIATE,
):
    """事件處理器裝飾器"""

    def decorator(func: EventHandler):
        async def wrapper():
            bus = await get_global_event_bus()
            return bus.subscribe(
                event_types=event_types,
                handler=func,
                filters=filters,
                priority=priority,
                processing_mode=processing_mode,
            )

        # 自動註冊處理器
        asyncio.create_task(wrapper())
        return func

    return decorator
