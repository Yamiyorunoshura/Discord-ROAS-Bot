"""成就系統效能優化和快取整合.

此模組提供成就系統的效能優化功能，包含：
- 智慧快取管理和策略
- 批量資料庫操作優化
- 異步任務隊列處理
- 效能監控和統計
- 記憶體使用優化

效能優化遵循以下設計原則：
- 多層次快取策略減少資料庫存取
- 批量操作優化減少 I/O 開銷
- 異步非阻塞處理提升併發效能
- 智慧預載和快取失效機制
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from cachetools import LRUCache, TTLCache

if TYPE_CHECKING:
    from ..database.models import Achievement, AchievementProgress, UserAchievement
    from ..database.repository import AchievementRepository

logger = logging.getLogger(__name__)


class CacheType(str, Enum):
    """快取類型列舉."""
    ACHIEVEMENT = "achievement"
    USER_ACHIEVEMENT = "user_achievement"
    PROGRESS = "progress"
    TRIGGER_RESULT = "trigger_result"
    USER_STATS = "user_stats"


@dataclass
class CacheConfig:
    """快取配置.

    定義不同類型快取的配置參數。
    """

    max_size: int = 1000
    """最大快取項目數"""

    ttl: int = 300  # 5分鐘
    """存活時間（秒）"""

    enable_compression: bool = False
    """是否啟用壓縮"""

    auto_refresh: bool = True
    """是否自動重新整理"""


@dataclass
class BatchOperation:
    """批量操作.

    封裝批量資料庫操作的資訊。
    """

    operation_type: str
    """操作類型（select, insert, update, delete）"""

    table: str
    """目標表"""

    data: list[dict[str, Any]]
    """操作資料"""

    priority: int = 0
    """優先級"""

    created_at: datetime = field(default_factory=datetime.now)
    """創建時間"""


class PerformanceOptimizer:
    """效能優化器.

    提供成就系統的全面效能優化功能，包含：
    - 多層次智慧快取管理
    - 批量資料庫操作調度
    - 異步任務隊列處理
    - 效能監控和分析
    """

    def __init__(
        self,
        repository: AchievementRepository,
        cache_configs: dict[CacheType, CacheConfig] | None = None,
        batch_size: int = 100,
        batch_timeout: float = 5.0,
        enable_monitoring: bool = True
    ):
        """初始化效能優化器.

        Args:
            repository: 成就資料存取庫
            cache_configs: 快取配置字典
            batch_size: 批量處理大小
            batch_timeout: 批量處理超時
            enable_monitoring: 是否啟用監控
        """
        self._repository = repository
        self._batch_size = batch_size
        self._batch_timeout = batch_timeout
        self._enable_monitoring = enable_monitoring

        # 初始化快取配置
        self._cache_configs = cache_configs or self._get_default_cache_configs()

        # 建立多層快取
        self._caches: dict[CacheType, TTLCache | LRUCache] = {}
        self._init_caches()

        # 批量操作隊列
        self._batch_queues: dict[str, list[BatchOperation]] = {}
        self._batch_locks: dict[str, asyncio.Lock] = {}
        self._batch_timers: dict[str, datetime] = {}

        # 效能監控
        self._stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "batch_operations": 0,
            "database_queries": 0,
            "average_response_time": 0.0,
            "memory_usage": 0,
            "last_reset": datetime.now()
        }

        # 背景任務
        self._background_tasks: set[asyncio.Task] = set()
        self._is_running = False

        logger.info(
            "PerformanceOptimizer 初始化完成",
            extra={
                "cache_types": list(self._cache_configs.keys()),
                "batch_size": batch_size,
                "monitoring_enabled": enable_monitoring
            }
        )

    async def __aenter__(self) -> PerformanceOptimizer:
        """異步上下文管理器進入."""
        await self._start_background_tasks()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """異步上下文管理器退出."""
        await self._stop_background_tasks()

    # =============================================================================
    # 快取管理功能
    # =============================================================================

    async def get_cached_achievement(self, achievement_id: int) -> Achievement | None:
        """從快取取得成就資料.

        Args:
            achievement_id: 成就 ID

        Returns:
            成就物件或 None
        """
        cache_key = f"achievement:{achievement_id}"

        # 嘗試從快取取得
        cached = self._get_from_cache(CacheType.ACHIEVEMENT, cache_key)
        if cached is not None:
            self._stats["cache_hits"] += 1
            return cached

        # 快取未命中，從資料庫載入
        self._stats["cache_misses"] += 1
        achievement = await self._repository.get_achievement_by_id(achievement_id)

        if achievement:
            self._set_cache(CacheType.ACHIEVEMENT, cache_key, achievement)

        return achievement

    async def get_cached_user_achievements(
        self,
        user_id: int,
        use_batch: bool = True
    ) -> list[UserAchievement]:
        """從快取取得用戶成就列表.

        Args:
            user_id: 用戶 ID
            use_batch: 是否使用批量載入

        Returns:
            用戶成就列表
        """
        cache_key = f"user_achievements:{user_id}"

        # 嘗試從快取取得
        cached = self._get_from_cache(CacheType.USER_ACHIEVEMENT, cache_key)
        if cached is not None:
            self._stats["cache_hits"] += 1
            return cached

        # 快取未命中，從資料庫載入
        self._stats["cache_misses"] += 1

        if use_batch:
            # 使用批量載入
            achievements = await self._batch_load_user_achievements([user_id])
            return achievements.get(user_id, [])
        else:
            # 直接載入
            achievements = await self._repository.get_user_achievements(user_id)
            self._set_cache(CacheType.USER_ACHIEVEMENT, cache_key, achievements)
            return achievements

    async def get_cached_user_progress(
        self,
        user_id: int,
        achievement_id: int
    ) -> AchievementProgress | None:
        """從快取取得用戶進度.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID

        Returns:
            進度物件或 None
        """
        cache_key = f"progress:{user_id}:{achievement_id}"

        # 嘗試從快取取得
        cached = self._get_from_cache(CacheType.PROGRESS, cache_key)
        if cached is not None:
            self._stats["cache_hits"] += 1
            return cached

        # 快取未命中，從資料庫載入
        self._stats["cache_misses"] += 1
        progress = await self._repository.get_user_progress(user_id, achievement_id)

        if progress:
            self._set_cache(CacheType.PROGRESS, cache_key, progress)

        return progress

    async def cache_trigger_result(
        self,
        user_id: int,
        achievement_id: int,
        trigger_context: dict[str, Any],
        result: tuple[bool, str]
    ) -> None:
        """快取觸發檢查結果.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID
            trigger_context: 觸發上下文
            result: 觸發結果
        """
        # 生成上下文的雜湊作為快取鍵的一部分
        context_hash = self._hash_dict(trigger_context)
        cache_key = f"trigger:{user_id}:{achievement_id}:{context_hash}"

        self._set_cache(CacheType.TRIGGER_RESULT, cache_key, result)

    async def get_cached_trigger_result(
        self,
        user_id: int,
        achievement_id: int,
        trigger_context: dict[str, Any]
    ) -> tuple[bool, str] | None:
        """取得快取的觸發檢查結果.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID
            trigger_context: 觸發上下文

        Returns:
            觸發結果或 None
        """
        context_hash = self._hash_dict(trigger_context)
        cache_key = f"trigger:{user_id}:{achievement_id}:{context_hash}"

        cached = self._get_from_cache(CacheType.TRIGGER_RESULT, cache_key)
        if cached is not None:
            self._stats["cache_hits"] += 1
            return cached

        self._stats["cache_misses"] += 1
        return None

    def invalidate_user_cache(self, user_id: int) -> None:
        """使用戶相關快取失效.

        Args:
            user_id: 用戶 ID
        """
        patterns_to_clear = [
            f"user_achievements:{user_id}",
            f"progress:{user_id}:",
            f"trigger:{user_id}:",
            f"user_stats:{user_id}"
        ]

        for cache_type in self._caches:
            cache = self._caches[cache_type]
            keys_to_remove = []

            for key in cache:
                for pattern in patterns_to_clear:
                    if pattern in key:
                        keys_to_remove.append(key)
                        break

            for key in keys_to_remove:
                cache.pop(key, None)

        logger.debug(f"已清除用戶 {user_id} 的相關快取")

    def invalidate_achievement_cache(self, achievement_id: int) -> None:
        """使成就相關快取失效.

        Args:
            achievement_id: 成就 ID
        """
        patterns_to_clear = [
            f"achievement:{achievement_id}",
            f"progress:.*:{achievement_id}",
            f"trigger:.*:{achievement_id}:"
        ]

        for cache_type in self._caches:
            cache = self._caches[cache_type]
            keys_to_remove = []

            for key in cache:
                for _pattern in patterns_to_clear:
                    if str(achievement_id) in key:
                        keys_to_remove.append(key)
                        break

            for key in keys_to_remove:
                cache.pop(key, None)

        logger.debug(f"已清除成就 {achievement_id} 的相關快取")

    # =============================================================================
    # 批量操作優化
    # =============================================================================

    async def batch_load_achievements(
        self,
        achievement_ids: list[int]
    ) -> dict[int, Achievement]:
        """批量載入成就資料.

        Args:
            achievement_ids: 成就 ID 列表

        Returns:
            成就 ID 到成就物件的映射
        """
        if not achievement_ids:
            return {}

        # 檢查快取，找出需要從資料庫載入的 ID
        cached_achievements = {}
        missing_ids = []

        for achievement_id in achievement_ids:
            cache_key = f"achievement:{achievement_id}"
            cached = self._get_from_cache(CacheType.ACHIEVEMENT, cache_key)

            if cached is not None:
                cached_achievements[achievement_id] = cached
                self._stats["cache_hits"] += 1
            else:
                missing_ids.append(achievement_id)
                self._stats["cache_misses"] += 1

        # 批量載入缺失的成就
        loaded_achievements = {}
        if missing_ids:
            achievements = await self._repository.get_achievements_by_ids(missing_ids)

            for achievement in achievements:
                loaded_achievements[achievement.id] = achievement
                # 更新快取
                cache_key = f"achievement:{achievement.id}"
                self._set_cache(CacheType.ACHIEVEMENT, cache_key, achievement)

        # 合併結果
        result = {**cached_achievements, **loaded_achievements}

        logger.debug(
            "批量載入成就完成",
            extra={
                "requested": len(achievement_ids),
                "from_cache": len(cached_achievements),
                "from_db": len(loaded_achievements)
            }
        )

        return result

    async def _batch_load_user_achievements(
        self,
        user_ids: list[int]
    ) -> dict[int, list[UserAchievement]]:
        """批量載入用戶成就.

        Args:
            user_ids: 用戶 ID 列表

        Returns:
            用戶 ID 到成就列表的映射
        """
        if not user_ids:
            return {}

        # 批量查詢資料庫
        all_achievements = await self._repository.get_user_achievements_batch(user_ids)

        # 按用戶分組
        user_achievements = {}
        for user_id in user_ids:
            user_achievements[user_id] = []

        for achievement in all_achievements:
            user_id = achievement.user_id
            if user_id in user_achievements:
                user_achievements[user_id].append(achievement)

        # 更新快取
        for user_id, achievements in user_achievements.items():
            cache_key = f"user_achievements:{user_id}"
            self._set_cache(CacheType.USER_ACHIEVEMENT, cache_key, achievements)

        return user_achievements

    async def batch_update_progress(
        self,
        progress_updates: list[dict[str, Any]]
    ) -> None:
        """批量更新進度資料.

        Args:
            progress_updates: 進度更新列表
        """
        if not progress_updates:
            return

        # 添加到批量操作隊列
        operation = BatchOperation(
            operation_type="update",
            table="achievement_progress",
            data=progress_updates,
            priority=1
        )

        await self._enqueue_batch_operation(operation)

    async def batch_award_achievements(
        self,
        award_data: list[dict[str, Any]]
    ) -> None:
        """批量頒發成就.

        Args:
            award_data: 頒發資料列表
        """
        if not award_data:
            return

        # 添加到批量操作隊列
        operation = BatchOperation(
            operation_type="insert",
            table="user_achievements",
            data=award_data,
            priority=2
        )

        await self._enqueue_batch_operation(operation)

    # =============================================================================
    # 內部實作方法
    # =============================================================================

    def _get_default_cache_configs(self) -> dict[CacheType, CacheConfig]:
        """取得預設快取配置."""
        return {
            CacheType.ACHIEVEMENT: CacheConfig(max_size=500, ttl=600),  # 10分鐘
            CacheType.USER_ACHIEVEMENT: CacheConfig(max_size=1000, ttl=300),  # 5分鐘
            CacheType.PROGRESS: CacheConfig(max_size=2000, ttl=180),  # 3分鐘
            CacheType.TRIGGER_RESULT: CacheConfig(max_size=5000, ttl=60),  # 1分鐘
            CacheType.USER_STATS: CacheConfig(max_size=1000, ttl=900),  # 15分鐘
        }

    def _init_caches(self) -> None:
        """初始化快取."""
        for cache_type, config in self._cache_configs.items():
            if config.ttl > 0:
                cache = TTLCache(maxsize=config.max_size, ttl=config.ttl)
            else:
                cache = LRUCache(maxsize=config.max_size)

            self._caches[cache_type] = cache

        logger.debug("快取系統初始化完成")

    def _get_from_cache(self, cache_type: CacheType, key: str) -> Any:
        """從快取取得值."""
        cache = self._caches.get(cache_type)
        if cache is None:
            return None

        return cache.get(key)

    def _set_cache(self, cache_type: CacheType, key: str, value: Any) -> None:
        """設定快取值."""
        cache = self._caches.get(cache_type)
        if cache is not None:
            cache[key] = value

    def _hash_dict(self, data: dict[str, Any]) -> str:
        """生成字典的雜湊值."""
        # 將字典轉為 JSON 並排序鍵以確保一致性
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.md5(json_str.encode()).hexdigest()[:8]

    async def _enqueue_batch_operation(self, operation: BatchOperation) -> None:
        """將操作加入批量隊列."""
        queue_key = f"{operation.table}:{operation.operation_type}"

        # 取得或創建隊列鎖
        if queue_key not in self._batch_locks:
            self._batch_locks[queue_key] = asyncio.Lock()

        async with self._batch_locks[queue_key]:
            # 初始化隊列
            if queue_key not in self._batch_queues:
                self._batch_queues[queue_key] = []
                self._batch_timers[queue_key] = datetime.now()

            # 添加操作到隊列
            self._batch_queues[queue_key].append(operation)

            # 檢查是否達到批量處理條件
            queue = self._batch_queues[queue_key]
            time_elapsed = (datetime.now() - self._batch_timers[queue_key]).total_seconds()

            if len(queue) >= self._batch_size or time_elapsed >= self._batch_timeout:
                # 處理批量操作
                operations_to_process = queue.copy()
                self._batch_queues[queue_key] = []
                self._batch_timers[queue_key] = datetime.now()

                # 異步處理批量操作
                task = asyncio.create_task(
                    self._process_batch_operations(queue_key, operations_to_process)
                )
                self._background_tasks.add(task)

    async def _process_batch_operations(
        self,
        queue_key: str,
        operations: list[BatchOperation]
    ) -> None:
        """處理批量操作."""
        try:
            start_time = datetime.now()

            if not operations:
                return

            # 按操作類型分組
            grouped_operations = {}
            for op in operations:
                key = f"{op.table}:{op.operation_type}"
                if key not in grouped_operations:
                    grouped_operations[key] = []
                grouped_operations[key].extend(op.data)

            # 執行批量操作
            for op_key, data in grouped_operations.items():
                table, operation_type = op_key.split(":", 1)

                if operation_type == "insert":
                    await self._repository.batch_insert(table, data)
                elif operation_type == "update":
                    await self._repository.batch_update(table, data)
                elif operation_type == "delete":
                    await self._repository.batch_delete(table, data)

            # 更新統計
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            self._stats["batch_operations"] += len(operations)

            logger.info(
                "批量操作處理完成",
                extra={
                    "queue_key": queue_key,
                    "operation_count": len(operations),
                    "processing_time_ms": processing_time
                }
            )

        except Exception as e:
            logger.error(
                "批量操作處理失敗",
                extra={
                    "queue_key": queue_key,
                    "operation_count": len(operations),
                    "error": str(e)
                },
                exc_info=True
            )
        finally:
            # 清理背景任務
            current_task = asyncio.current_task()
            if current_task in self._background_tasks:
                self._background_tasks.discard(current_task)

    async def _start_background_tasks(self) -> None:
        """啟動背景任務."""
        if not self._is_running:
            self._is_running = True

            # 啟動快取清理任務
            cleanup_task = asyncio.create_task(self._cache_cleanup_loop())
            self._background_tasks.add(cleanup_task)

            # 啟動效能監控任務
            if self._enable_monitoring:
                monitor_task = asyncio.create_task(self._performance_monitor_loop())
                self._background_tasks.add(monitor_task)

            logger.info("效能優化器背景任務已啟動")

    async def _stop_background_tasks(self) -> None:
        """停止背景任務."""
        self._is_running = False

        # 處理剩餘的批量操作
        for queue_key, operations in self._batch_queues.items():
            if operations:
                await self._process_batch_operations(queue_key, operations)

        # 等待背景任務完成
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()

        logger.info("效能優化器背景任務已停止")

    async def _cache_cleanup_loop(self) -> None:
        """快取清理循環."""
        while self._is_running:
            try:
                # 檢查快取大小和記憶體使用
                total_cache_size = sum(len(cache) for cache in self._caches.values())

                if total_cache_size > 10000:  # 如果快取項目過多
                    # 清理最少使用的快取項目
                    for _cache_type, cache in self._caches.items():
                        if isinstance(cache, LRUCache) and len(cache) > cache.maxsize * 0.8:
                            # 清理 20% 的項目
                            items_to_remove = int(len(cache) * 0.2)
                            for _ in range(items_to_remove):
                                cache.popitem(last=False)

                # 記錄快取統計
                if self._enable_monitoring:
                    self._stats["memory_usage"] = total_cache_size

                await asyncio.sleep(60)  # 每分鐘檢查一次

            except Exception as e:
                logger.error(f"快取清理循環錯誤: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _performance_monitor_loop(self) -> None:
        """效能監控循環."""
        while self._is_running:
            try:
                # 計算快取命中率
                total_cache_requests = self._stats["cache_hits"] + self._stats["cache_misses"]
                hit_rate = (
                    self._stats["cache_hits"] / total_cache_requests
                    if total_cache_requests > 0 else 0
                )

                # 記錄效能統計
                logger.info(
                    "效能統計",
                    extra={
                        "cache_hit_rate": f"{hit_rate:.2%}",
                        "cache_size": sum(len(cache) for cache in self._caches.values()),
                        "batch_operations": self._stats["batch_operations"],
                        "background_tasks": len(self._background_tasks)
                    }
                )

                await asyncio.sleep(300)  # 每5分鐘記錄一次

            except Exception as e:
                logger.error(f"效能監控循環錯誤: {e}", exc_info=True)
                await asyncio.sleep(300)

    # =============================================================================
    # 公共統計和管理介面
    # =============================================================================

    def get_cache_stats(self) -> dict[str, Any]:
        """取得快取統計資訊."""
        stats = {}

        for cache_type, cache in self._caches.items():
            stats[cache_type.value] = {
                "size": len(cache),
                "max_size": cache.maxsize,
                "usage_rate": len(cache) / cache.maxsize if cache.maxsize > 0 else 0
            }

        total_requests = self._stats["cache_hits"] + self._stats["cache_misses"]
        hit_rate = self._stats["cache_hits"] / total_requests if total_requests > 0 else 0

        stats["overall"] = {
            "hit_rate": hit_rate,
            "total_requests": total_requests,
            "batch_operations": self._stats["batch_operations"]
        }

        return stats

    def clear_all_caches(self) -> None:
        """清空所有快取."""
        for cache in self._caches.values():
            cache.clear()

        logger.info("所有快取已清空")

    def get_performance_stats(self) -> dict[str, Any]:
        """取得效能統計資訊."""
        return self._stats.copy()


__all__ = [
    "BatchOperation",
    "CacheConfig",
    "CacheType",
    "PerformanceOptimizer",
]
