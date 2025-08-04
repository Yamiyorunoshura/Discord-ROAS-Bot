"""成就系統快取同步管理器.

此模組提供成就系統操作後的快取同步功能,包含:
- 智慧快取失效策略
- 操作影響分析
- 批量快取更新
- 快取一致性保證

確保快取與資料庫的一致性,提供最佳的性能體驗.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from ..constants import DEFAULT_BATCH_SIZE, MIN_BATCH_SIZE

logger = logging.getLogger(__name__)

class CacheEventType(Enum):
    """快取事件類型枚舉."""

    ACHIEVEMENT_GRANTED = "achievement_granted"
    ACHIEVEMENT_REVOKED = "achievement_revoked"
    PROGRESS_UPDATED = "progress_updated"
    USER_DATA_RESET = "user_data_reset"
    BULK_OPERATION = "bulk_operation"
    ACHIEVEMENT_UPDATED = "achievement_updated"
    CATEGORY_UPDATED = "category_updated"

@dataclass
class CacheEvent:
    """快取事件記錄."""

    event_id: str
    event_type: CacheEventType
    user_ids: set[int] = field(default_factory=set)
    achievement_ids: set[int] = field(default_factory=set)
    category_ids: set[int] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class CacheInvalidationPlan:
    """快取失效計劃."""

    plan_id: str
    cache_keys_by_type: dict[str, set[str]] = field(default_factory=dict)
    estimated_impact: int = 0
    priority: int = 1  # 1=highest, 5=lowest
    batch_size: int = 100

class CacheSyncManager:
    """快取同步管理器.

    負責分析操作對快取的影響,並執行智慧的快取失效策略.
    """

    def __init__(self, cache_service=None):
        """初始化快取同步管理器.

        Args:
            cache_service: 快取服務實例
        """
        self.cache_service = cache_service

        # 快取影響規則配置
        self._impact_rules = self._initialize_impact_rules()

        # 統計資料
        self._stats = {
            "events_processed": 0,
            "cache_invalidations": 0,
            "batch_operations": 0,
            "total_keys_invalidated": 0,
        }

        logger.info("CacheSyncManager 初始化完成")

    def _initialize_impact_rules(self) -> dict[CacheEventType, dict[str, Any]]:
        """初始化快取影響規則.

        Returns:
            Dict[CacheEventType, Dict[str, Any]]: 影響規則配置
        """
        return {
            CacheEventType.ACHIEVEMENT_GRANTED: {
                "affected_cache_types": [
                    "user_achievements",
                    "user_progress",
                    "global_stats",
                    "leaderboard",
                ],
                "key_patterns": [
                    "user_achievements:{user_id}",
                    "user_progress:{user_id}",
                    "global_stats:total_achievements",
                    "global_stats:users_with_achievements",
                    "leaderboard:points",
                    "leaderboard:achievement_count",
                ],
                "priority": 1,
                "batch_friendly": True,
            },
            CacheEventType.ACHIEVEMENT_REVOKED: {
                "affected_cache_types": [
                    "user_achievements",
                    "user_progress",
                    "global_stats",
                    "leaderboard",
                ],
                "key_patterns": [
                    "user_achievements:{user_id}",
                    "user_progress:{user_id}",
                    "global_stats:total_achievements",
                    "global_stats:users_with_achievements",
                    "leaderboard:points",
                    "leaderboard:achievement_count",
                ],
                "priority": 1,
                "batch_friendly": True,
            },
            CacheEventType.PROGRESS_UPDATED: {
                "affected_cache_types": [
                    "user_progress",
                    "user_achievements",  # 可能觸發成就解鎖
                ],
                "key_patterns": [
                    "user_progress:{user_id}",
                    "user_progress:{user_id}:{achievement_id}",
                    "user_achievements:{user_id}",  # 預防性失效
                ],
                "priority": 2,
                "batch_friendly": True,
            },
            CacheEventType.USER_DATA_RESET: {
                "affected_cache_types": [
                    "user_achievements",
                    "user_progress",
                    "global_stats",
                    "leaderboard",
                ],
                "key_patterns": [
                    "user_achievements:{user_id}",
                    "user_progress:{user_id}",
                    "user_*:{user_id}",  # 通配符模式
                    "global_stats:*",
                    "leaderboard:*",
                ],
                "priority": 1,
                "batch_friendly": False,  # 影響範圍大,不適合批量
            },
            CacheEventType.BULK_OPERATION: {
                "affected_cache_types": [
                    "user_achievements",
                    "user_progress",
                    "global_stats",
                    "leaderboard",
                ],
                "key_patterns": [
                    "user_achievements:{user_id}",
                    "user_progress:{user_id}",
                    "global_stats:*",
                    "leaderboard:*",
                ],
                "priority": 1,
                "batch_friendly": True,  # 專為批量操作設計
            },
            CacheEventType.ACHIEVEMENT_UPDATED: {
                "affected_cache_types": [
                    "achievement",
                    "user_achievements",  # 可能影響已獲得的成就
                    "global_stats",
                ],
                "key_patterns": [
                    "achievement:{achievement_id}",
                    "achievement:list",
                    "achievement:by_category:{category_id}",
                    "global_stats:achievement_count",
                ],
                "priority": 2,
                "batch_friendly": False,
            },
            CacheEventType.CATEGORY_UPDATED: {
                "affected_cache_types": [
                    "category",
                    "achievement",  # 分類下的成就可能受影響
                ],
                "key_patterns": [
                    "category:{category_id}",
                    "category:list",
                    "achievement:by_category:{category_id}",
                ],
                "priority": 3,
                "batch_friendly": False,
            },
        }

    async def process_cache_event(self, event: CacheEvent) -> CacheInvalidationPlan:
        """處理快取事件.

        Args:
            event: 快取事件

        Returns:
            CacheInvalidationPlan: 快取失效計劃
        """
        try:
            # 分析事件影響
            plan = await self._analyze_cache_impact(event)

            # 執行快取失效
            await self._execute_invalidation_plan(plan)

            self._stats["events_processed"] += 1

            logger.debug(
                "[快取同步]處理快取事件完成",
                extra={
                    "event_id": event.event_id,
                    "event_type": event.event_type.value,
                    "affected_users": len(event.user_ids),
                    "invalidated_keys": plan.estimated_impact,
                },
            )

            return plan

        except Exception as e:
            logger.error(
                f"[快取同步]處理快取事件失敗 {event.event_id}: {e}", exc_info=True
            )
            raise

    async def _analyze_cache_impact(self, event: CacheEvent) -> CacheInvalidationPlan:
        """分析快取影響.

        Args:
            event: 快取事件

        Returns:
            CacheInvalidationPlan: 失效計劃
        """
        plan = CacheInvalidationPlan(plan_id=f"plan_{event.event_id}")

        # 獲取影響規則
        rule = self._impact_rules.get(event.event_type)
        if not rule:
            logger.warning(f"[快取同步]未找到事件類型的影響規則: {event.event_type}")
            return plan

        plan.priority = rule["priority"]

        # 生成需要失效的快取鍵
        for cache_type in rule["affected_cache_types"]:
            cache_keys = self._generate_cache_keys(
                cache_type, rule["key_patterns"], event
            )

            if cache_keys:
                plan.cache_keys_by_type[cache_type] = cache_keys
                plan.estimated_impact += len(cache_keys)

        # 設置批量大小
        if rule.get("batch_friendly", False) and len(event.user_ids) > MIN_BATCH_SIZE:
            plan.batch_size = min(DEFAULT_BATCH_SIZE, len(event.user_ids))
        else:
            plan.batch_size = 1

        logger.debug(
            "[快取同步]快取影響分析完成",
            extra={
                "event_type": event.event_type.value,
                "affected_cache_types": len(plan.cache_keys_by_type),
                "estimated_impact": plan.estimated_impact,
                "priority": plan.priority,
            },
        )

        return plan

    def _generate_cache_keys(
        self, _cache_type: str, key_patterns: list[str], event: CacheEvent
    ) -> set[str]:
        """生成需要失效的快取鍵.

        Args:
            _cache_type: 快取類型(未使用)
            key_patterns: 鍵值模式列表
            event: 快取事件

        Returns:
            Set[str]: 快取鍵集合
        """
        cache_keys = set()

        for pattern in key_patterns:
            # 替換用戶ID
            if "{user_id}" in pattern:
                for user_id in event.user_ids:
                    key = pattern.format(user_id=user_id)
                    cache_keys.add(key)

            # 替換成就ID
            elif "{achievement_id}" in pattern:
                for achievement_id in event.achievement_ids:
                    key = pattern.format(achievement_id=achievement_id)
                    cache_keys.add(key)

                    # 如果還包含用戶ID,需要組合生成
                    if "{user_id}" in key:
                        for user_id in event.user_ids:
                            combined_key = key.format(user_id=user_id)
                            cache_keys.add(combined_key)

            # 替換分類ID
            elif "{category_id}" in pattern:
                for category_id in event.category_ids:
                    key = pattern.format(category_id=category_id)
                    cache_keys.add(key)

            # 通配符模式
            elif "*" in pattern:
                if "{user_id}" in pattern:
                    for user_id in event.user_ids:
                        base_pattern = pattern.replace("{user_id}", str(user_id))
                        cache_keys.add(base_pattern)
                else:
                    cache_keys.add(pattern)

            # 直接模式
            else:
                cache_keys.add(pattern)

        return cache_keys

    async def _execute_invalidation_plan(self, plan: CacheInvalidationPlan) -> None:
        """執行快取失效計劃.

        Args:
            plan: 失效計劃
        """
        if not self.cache_service:
            logger.warning("[快取同步]快取服務未初始化,跳過失效操作")
            return

        total_invalidated = 0

        try:
            for cache_type, cache_keys in plan.cache_keys_by_type.items():
                if not cache_keys:
                    continue

                # 批量處理
                key_list = list(cache_keys)
                for i in range(0, len(key_list), plan.batch_size):
                    batch_keys = key_list[i : i + plan.batch_size]

                    try:
                        await self._invalidate_cache_batch(cache_type, batch_keys)
                        total_invalidated += len(batch_keys)

                    except Exception as e:
                        logger.error(
                            f"[快取同步]批量失效失敗 {cache_type}: {e}",
                            extra={"batch_keys": batch_keys},
                        )
                        # 繼續處理其他批次

            self._stats["cache_invalidations"] += 1
            self._stats["total_keys_invalidated"] += total_invalidated

            if plan.batch_size > 1:
                self._stats["batch_operations"] += 1

            logger.info(
                "[快取同步]快取失效計劃執行完成",
                extra={
                    "plan_id": plan.plan_id,
                    "total_invalidated": total_invalidated,
                    "cache_types": len(plan.cache_keys_by_type),
                },
            )

        except Exception as e:
            logger.error(
                f"[快取同步]執行失效計劃失敗 {plan.plan_id}: {e}", exc_info=True
            )
            raise

    async def _invalidate_cache_batch(
        self, cache_type: str, cache_keys: list[str]
    ) -> None:
        """批量失效快取.

        Args:
            cache_type: 快取類型
            cache_keys: 快取鍵列表
        """
        try:
            # 檢查快取服務是否支援批量失效
            if hasattr(self.cache_service, "invalidate_batch"):
                await self.cache_service.invalidate_batch(cache_type, cache_keys)
            else:
                # 逐個失效
                for cache_key in cache_keys:
                    await self.cache_service.invalidate(cache_type, cache_key)

            logger.debug(
                "[快取同步]批量快取失效完成",
                extra={"cache_type": cache_type, "keys_count": len(cache_keys)},
            )

        except Exception as e:
            logger.error(f"[快取同步]批量快取失效失敗 {cache_type}: {e}")
            raise

    async def create_cache_event(
        self,
        event_type: CacheEventType,
        user_ids: list[int] | None = None,
        achievement_ids: list[int] | None = None,
        category_ids: list[int] | None = None,
        **metadata,
    ) -> CacheEvent:
        """創建快取事件.

        Args:
            event_type: 事件類型
            user_ids: 涉及的用戶ID列表
            achievement_ids: 涉及的成就ID列表
            category_ids: 涉及的分類ID列表
            **metadata: 額外元數據

        Returns:
            CacheEvent: 快取事件
        """
        event = CacheEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            user_ids=set(user_ids or []),
            achievement_ids=set(achievement_ids or []),
            category_ids=set(category_ids or []),
            metadata=metadata,
        )

        return event

    async def invalidate_user_cache(
        self, user_id: int, operation_type: str = "general"
    ) -> None:
        """失效用戶相關快取.

        Args:
            user_id: 用戶ID
            operation_type: 操作類型
        """
        try:
            # 根據操作類型選擇事件類型
            if operation_type == "grant":
                event_type = CacheEventType.ACHIEVEMENT_GRANTED
            elif operation_type == "revoke":
                event_type = CacheEventType.ACHIEVEMENT_REVOKED
            elif operation_type == "progress":
                event_type = CacheEventType.PROGRESS_UPDATED
            elif operation_type == "reset":
                event_type = CacheEventType.USER_DATA_RESET
            else:
                event_type = CacheEventType.ACHIEVEMENT_GRANTED  # 預設

            # 創建並處理事件
            event = await self.create_cache_event(
                event_type=event_type, user_ids=[user_id], operation_type=operation_type
            )

            await self.process_cache_event(event)

        except Exception as e:
            logger.error(f"[快取同步]用戶快取失效失敗 {user_id}: {e}")
            raise

    async def invalidate_bulk_user_cache(
        self, user_ids: list[int], operation_type: str = "bulk"
    ) -> None:
        """批量失效用戶快取.

        Args:
            user_ids: 用戶ID列表
            operation_type: 操作類型
        """
        try:
            event = await self.create_cache_event(
                event_type=CacheEventType.BULK_OPERATION,
                user_ids=user_ids,
                operation_type=operation_type,
                bulk_size=len(user_ids),
            )

            await self.process_cache_event(event)

        except Exception as e:
            logger.error(f"[快取同步]批量用戶快取失效失敗: {e}")
            raise

    async def invalidate_achievement_cache(
        self, achievement_id: int, category_id: int | None = None
    ) -> None:
        """失效成就相關快取.

        Args:
            achievement_id: 成就ID
            category_id: 分類ID
        """
        try:
            event = await self.create_cache_event(
                event_type=CacheEventType.ACHIEVEMENT_UPDATED,
                achievement_ids=[achievement_id],
                category_ids=[category_id] if category_id else None,
            )

            await self.process_cache_event(event)

        except Exception as e:
            logger.error(f"[快取同步]成就快取失效失敗 {achievement_id}: {e}")
            raise

    async def invalidate_global_stats_cache(self) -> None:
        """失效全域統計快取."""
        try:
            if not self.cache_service:
                return

            # 直接失效全域統計相關的快取
            global_cache_keys = ["global_stats:*", "leaderboard:*"]

            for key_pattern in global_cache_keys:
                await self.cache_service.invalidate("global_stats", key_pattern)

            logger.debug("[快取同步]全域統計快取失效完成")

        except Exception as e:
            logger.error(f"[快取同步]全域統計快取失效失敗: {e}")
            raise

    def get_cache_stats(self) -> dict[str, Any]:
        """獲取快取同步統計.

        Returns:
            Dict[str, Any]: 統計資料
        """
        return {**self._stats, "impact_rules_count": len(self._impact_rules)}

    async def get_cache_health(self) -> dict[str, Any]:
        """獲取快取健康狀態.

        Returns:
            Dict[str, Any]: 健康狀態資訊
        """
        health_info = {
            "cache_service_available": self.cache_service is not None,
            "impact_rules_loaded": len(self._impact_rules) > 0,
            "stats": self.get_cache_stats(),
        }

        if self.cache_service:
            try:
                # 嘗試獲取快取服務狀態
                if hasattr(self.cache_service, "get_health"):
                    cache_health = await self.cache_service.get_health()
                    health_info["cache_service_health"] = cache_health
            except Exception as e:
                health_info["cache_service_error"] = str(e)

        return health_info
