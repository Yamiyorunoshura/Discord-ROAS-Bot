"""整合的成就系統效能服務.

此模組整合所有效能優化功能，提供統一的服務介面：
- 整合快取管理、效能監控、批量操作
- 提供高級的效能優化策略
- 統一的服務介面
- 自動效能調優

根據 Story 5.1 所有 Task 的要求實作統一的效能服務。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .achievement_monitor import AchievementPerformanceMonitor
from .cache_manager import CacheManager, CacheType
from .performance_analyzer import PerformanceAnalyzer

if TYPE_CHECKING:
    from ..database.models import (
        Achievement,
        AchievementProgress,
        AchievementType,
        UserAchievement,
    )
    from ..database.optimized_repository import OptimizedAchievementRepository

logger = logging.getLogger(__name__)


class AchievementPerformanceService:
    """成就系統整合效能服務.

    整合快取、監控、分析等功能，提供統一的高效能服務介面。
    """

    def __init__(
        self,
        repository: OptimizedAchievementRepository,
        cache_manager: CacheManager | None = None,
        performance_monitor: AchievementPerformanceMonitor | None = None,
        performance_analyzer: PerformanceAnalyzer | None = None,
        enable_auto_optimization: bool = True
    ):
        """初始化效能服務.

        Args:
            repository: 優化的資料存取庫
            cache_manager: 快取管理器
            performance_monitor: 效能監控器
            performance_analyzer: 效能分析器
            enable_auto_optimization: 是否啟用自動優化
        """
        self._repository = repository
        self._cache_manager = cache_manager or CacheManager()
        self._performance_monitor = performance_monitor or AchievementPerformanceMonitor(
            cache_manager=self._cache_manager
        )
        self._performance_analyzer = performance_analyzer or PerformanceAnalyzer(repository)
        self._enable_auto_optimization = enable_auto_optimization

        # 效能配置
        self._auto_cache_threshold = 50  # 自動快取的查詢頻率門檻
        self._preload_popular_achievements = True
        self._batch_size = 100

        # 統計追蹤
        self._operation_counts: dict[str, int] = {}
        self._last_optimization = datetime.now()

        logger.info("AchievementPerformanceService 初始化完成")

    async def __aenter__(self) -> AchievementPerformanceService:
        """異步上下文管理器進入."""
        await self._cache_manager.start()
        await self._performance_monitor.start_achievement_monitoring()

        if self._preload_popular_achievements:
            await self._preload_popular_data()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """異步上下文管理器退出."""
        await self._cache_manager.stop()
        await self._performance_monitor.stop_achievement_monitoring()

    # =============================================================================
    # 高效能成就查詢介面
    # =============================================================================

    async def get_achievement_optimized(self, achievement_id: int) -> Achievement | None:
        """高效能取得成就（含快取和監控）.

        Args:
            achievement_id: 成就 ID

        Returns:
            成就物件或 None
        """
        operation_start = datetime.now()
        operation_name = "get_achievement_optimized"

        try:
            # 嘗試從快取取得
            cache_key = f"achievement:{achievement_id}"
            cached_achievement = await self._cache_manager.get(
                CacheType.ACHIEVEMENT, cache_key
            )

            if cached_achievement:
                await self._performance_monitor.track_cache_operation(
                    CacheType.ACHIEVEMENT, "get", hit=True
                )
                await self._track_operation_success(operation_name, operation_start)
                return cached_achievement

            # 快取未命中，從資料庫載入
            await self._performance_monitor.track_cache_operation(
                CacheType.ACHIEVEMENT, "get", hit=False
            )

            achievement = await self._repository.get_achievement_by_id(achievement_id)

            # 快取結果
            if achievement:
                await self._cache_manager.set(
                    CacheType.ACHIEVEMENT, cache_key, achievement
                )

            await self._track_operation_success(operation_name, operation_start)
            return achievement

        except Exception as e:
            await self._track_operation_failure(operation_name, operation_start, str(e))
            raise

    async def list_achievements_optimized(
        self,
        category_id: int | None = None,
        achievement_type: AchievementType | None = None,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 20,
        use_cache: bool = True
    ) -> tuple[list[Achievement], int]:
        """高效能成就列表查詢.

        Args:
            category_id: 篩選特定分類
            achievement_type: 篩選特定類型
            active_only: 是否只取得啟用的成就
            page: 頁數
            page_size: 每頁大小
            use_cache: 是否使用快取

        Returns:
            (成就列表, 總數量) 的元組
        """
        operation_start = datetime.now()
        operation_name = "list_achievements_optimized"

        try:
            # 生成快取鍵
            cache_key = f"achievement_list:{category_id}:{achievement_type}:{active_only}:{page}:{page_size}"

            # 嘗試從快取取得
            if use_cache:
                cached_result = await self._cache_manager.get(
                    CacheType.ACHIEVEMENT_LIST, cache_key
                )

                if cached_result:
                    await self._performance_monitor.track_cache_operation(
                        CacheType.ACHIEVEMENT_LIST, "get", hit=True
                    )
                    await self._track_operation_success(operation_name, operation_start)
                    return cached_result

                await self._performance_monitor.track_cache_operation(
                    CacheType.ACHIEVEMENT_LIST, "get", hit=False
                )

            # 執行優化查詢
            achievements, total_count = await self._repository.list_achievements_optimized(
                category_id=category_id,
                achievement_type=achievement_type,
                active_only=active_only,
                page=page,
                page_size=page_size
            )

            result = (achievements, total_count)

            # 快取結果
            if use_cache:
                await self._cache_manager.set(
                    CacheType.ACHIEVEMENT_LIST, cache_key, result, ttl=300  # 5分鐘
                )

            await self._track_operation_success(operation_name, operation_start)
            return result

        except Exception as e:
            await self._track_operation_failure(operation_name, operation_start, str(e))
            raise

    async def get_user_achievements_optimized(
        self,
        user_id: int,
        category_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
        use_cache: bool = True
    ) -> tuple[list[tuple[UserAchievement, Achievement]], int]:
        """高效能用戶成就查詢.

        Args:
            user_id: 用戶 ID
            category_id: 篩選特定分類
            page: 頁數
            page_size: 每頁大小
            use_cache: 是否使用快取

        Returns:
            ((用戶成就記錄, 成就詳情) 的元組列表, 總數量)
        """
        operation_start = datetime.now()
        operation_name = "get_user_achievements_optimized"

        try:
            # 生成快取鍵
            cache_key = f"user_achievements:{user_id}:{category_id}:{page}:{page_size}"

            # 嘗試從快取取得
            if use_cache:
                cached_result = await self._cache_manager.get(
                    CacheType.USER_ACHIEVEMENT, cache_key
                )

                if cached_result:
                    await self._performance_monitor.track_cache_operation(
                        CacheType.USER_ACHIEVEMENT, "get", hit=True
                    )
                    await self._track_operation_success(operation_name, operation_start, user_id)
                    return cached_result

                await self._performance_monitor.track_cache_operation(
                    CacheType.USER_ACHIEVEMENT, "get", hit=False
                )

            # 執行優化查詢
            user_achievements, total_count = await self._repository.get_user_achievements_optimized(
                user_id=user_id,
                category_id=category_id,
                page=page,
                page_size=page_size
            )

            result = (user_achievements, total_count)

            # 快取結果
            if use_cache:
                await self._cache_manager.set(
                    CacheType.USER_ACHIEVEMENT, cache_key, result, ttl=300  # 5分鐘
                )

            await self._track_operation_success(operation_name, operation_start, user_id)
            return result

        except Exception as e:
            await self._track_operation_failure(operation_name, operation_start, str(e), user_id)
            raise

    async def get_user_progress_optimized(
        self,
        user_id: int,
        achievement_id: int,
        use_cache: bool = True
    ) -> AchievementProgress | None:
        """高效能用戶進度查詢.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID
            use_cache: 是否使用快取

        Returns:
            進度物件或 None
        """
        operation_start = datetime.now()
        operation_name = "get_user_progress_optimized"

        try:
            # 短期快取（進度資料變化頻繁）
            cache_key = f"user_progress:{user_id}:{achievement_id}"

            if use_cache:
                cached_progress = await self._cache_manager.get(
                    CacheType.USER_PROGRESS, cache_key
                )

                if cached_progress:
                    await self._performance_monitor.track_cache_operation(
                        CacheType.USER_PROGRESS, "get", hit=True
                    )
                    await self._track_operation_success(operation_name, operation_start, user_id)
                    return cached_progress

                await self._performance_monitor.track_cache_operation(
                    CacheType.USER_PROGRESS, "get", hit=False
                )

            # 從資料庫載入
            progress = await self._repository.get_user_progress(user_id, achievement_id)

            # 短期快取（3分鐘）
            if use_cache and progress:
                await self._cache_manager.set(
                    CacheType.USER_PROGRESS, cache_key, progress, ttl=180
                )

            await self._track_operation_success(operation_name, operation_start, user_id)
            return progress

        except Exception as e:
            await self._track_operation_failure(operation_name, operation_start, str(e), user_id)
            raise

    # =============================================================================
    # 批量操作介面
    # =============================================================================

    async def batch_get_achievements(self, achievement_ids: list[int]) -> dict[int, Achievement]:
        """批量取得成就.

        Args:
            achievement_ids: 成就 ID 列表

        Returns:
            成就 ID 到成就物件的映射
        """
        operation_start = datetime.now()
        operation_name = "batch_get_achievements"

        try:
            if not achievement_ids:
                return {}

            # 檢查快取中已存在的成就
            cached_achievements = {}
            missing_ids = []

            for achievement_id in achievement_ids:
                cache_key = f"achievement:{achievement_id}"
                cached = await self._cache_manager.get(CacheType.ACHIEVEMENT, cache_key)

                if cached:
                    cached_achievements[achievement_id] = cached
                else:
                    missing_ids.append(achievement_id)

            # 批量載入缺失的成就
            loaded_achievements = {}
            if missing_ids:
                achievements = await self._repository.get_achievements_by_ids(missing_ids)

                for achievement in achievements:
                    loaded_achievements[achievement.id] = achievement
                    # 快取新載入的成就
                    cache_key = f"achievement:{achievement.id}"
                    await self._cache_manager.set(
                        CacheType.ACHIEVEMENT, cache_key, achievement
                    )

            # 合併結果
            result = {**cached_achievements, **loaded_achievements}

            await self._track_operation_success(operation_name, operation_start)

            logger.debug(
                f"批量取得成就: 請求 {len(achievement_ids)} 項，"
                f"快取命中 {len(cached_achievements)} 項，"
                f"資料庫載入 {len(loaded_achievements)} 項"
            )

            return result

        except Exception as e:
            await self._track_operation_failure(operation_name, operation_start, str(e))
            raise

    async def batch_get_user_progress(
        self,
        user_ids: list[int],
        achievement_ids: list[int] | None = None
    ) -> dict[tuple[int, int], AchievementProgress]:
        """批量取得用戶進度.

        Args:
            user_ids: 用戶 ID 列表
            achievement_ids: 成就 ID 列表（可選）

        Returns:
            (用戶ID, 成就ID) 到進度物件的映射
        """
        operation_start = datetime.now()
        operation_name = "batch_get_user_progress"

        try:
            if not user_ids:
                return {}

            # 執行批量查詢
            progresses = await self._repository.get_user_progress_batch(
                user_ids, achievement_ids
            )

            # 轉換為映射並快取
            result = {}
            for progress in progresses:
                key = (progress.user_id, progress.achievement_id)
                result[key] = progress

                # 快取進度資料（短期）
                cache_key = f"user_progress:{progress.user_id}:{progress.achievement_id}"
                await self._cache_manager.set(
                    CacheType.USER_PROGRESS, cache_key, progress, ttl=180
                )

            await self._track_operation_success(operation_name, operation_start)

            logger.debug(f"批量取得用戶進度: {len(user_ids)} 個用戶，{len(result)} 項進度")

            return result

        except Exception as e:
            await self._track_operation_failure(operation_name, operation_start, str(e))
            raise

    # =============================================================================
    # 快取失效管理
    # =============================================================================

    async def invalidate_user_cache(self, user_id: int) -> None:
        """使用戶相關快取失效.

        Args:
            user_id: 用戶 ID
        """
        try:
            invalidated_count = await self._cache_manager.invalidate_by_user(user_id)
            logger.info(f"用戶 {user_id} 快取失效: {invalidated_count} 項")

        except Exception as e:
            logger.error(f"用戶快取失效失敗 {user_id}: {e}")

    async def invalidate_achievement_cache(self, achievement_id: int) -> None:
        """使成就相關快取失效.

        Args:
            achievement_id: 成就 ID
        """
        try:
            invalidated_count = await self._cache_manager.invalidate_by_achievement(achievement_id)
            logger.info(f"成就 {achievement_id} 快取失效: {invalidated_count} 項")

        except Exception as e:
            logger.error(f"成就快取失效失敗 {achievement_id}: {e}")

    async def invalidate_category_cache(self, category_id: int) -> None:
        """使分類相關快取失效.

        Args:
            category_id: 分類 ID
        """
        try:
            invalidated_count = await self._cache_manager.invalidate_by_category(category_id)
            logger.info(f"分類 {category_id} 快取失效: {invalidated_count} 項")

        except Exception as e:
            logger.error(f"分類快取失效失敗 {category_id}: {e}")

    # =============================================================================
    # 效能分析和報告
    # =============================================================================

    async def get_performance_report(self) -> dict[str, Any]:
        """取得完整的效能報告.

        Returns:
            效能報告字典
        """
        try:
            # 取得各組件的統計
            cache_stats = self._cache_manager.get_stats()
            monitor_stats = self._performance_monitor.get_achievement_metrics_summary()
            query_stats = self._repository.get_query_stats()

            return {
                "timestamp": datetime.now().isoformat(),
                "cache_statistics": cache_stats,
                "monitoring_statistics": monitor_stats,
                "query_statistics": query_stats,
                "operation_counts": self._operation_counts,
                "performance_summary": {
                    "total_operations": sum(self._operation_counts.values()),
                    "last_optimization": self._last_optimization.isoformat(),
                    "auto_optimization_enabled": self._enable_auto_optimization
                }
            }

        except Exception as e:
            logger.error(f"生成效能報告失敗: {e}")
            return {"error": str(e)}

    async def analyze_performance(self) -> dict[str, Any]:
        """執行效能分析.

        Returns:
            效能分析報告
        """
        try:
            return await self._performance_analyzer.analyze_all_queries()

        except Exception as e:
            logger.error(f"效能分析失敗: {e}")
            return {"error": str(e)}

    # =============================================================================
    # 自動優化機制
    # =============================================================================

    async def auto_optimize(self) -> dict[str, Any]:
        """執行自動優化.

        Returns:
            優化結果報告
        """
        if not self._enable_auto_optimization:
            return {"message": "自動優化已停用"}

        optimization_start = datetime.now()
        optimizations = []

        try:
            # 1. 分析快取效能
            cache_stats = self._cache_manager.get_stats()
            overall_stats = cache_stats.get("overall", {})
            hit_rate = overall_stats.get("hit_rate", 0)

            if hit_rate < 0.6:  # 命中率低於60%
                # 預載熱門資料
                await self._preload_popular_data()
                optimizations.append("預載熱門資料以提升快取命中率")

            # 2. 分析查詢效能
            query_stats = self._repository.get_query_stats()
            slow_query_ratio = query_stats.get("slow_query_ratio", 0)

            if slow_query_ratio > 0.2:  # 慢查詢比例超過20%
                # 建議增加索引或優化查詢
                optimizations.append("檢測到高慢查詢比例，建議檢查資料庫索引")

            # 3. 記憶體使用優化
            # 清理過期快取
            await self._cache_manager.clear()
            optimizations.append("清理過期快取以減少記憶體使用")

            self._last_optimization = datetime.now()

            return {
                "optimization_time": optimization_start.isoformat(),
                "duration_seconds": (datetime.now() - optimization_start).total_seconds(),
                "optimizations_applied": optimizations,
                "cache_hit_rate": hit_rate,
                "slow_query_ratio": slow_query_ratio
            }

        except Exception as e:
            logger.error(f"自動優化失敗: {e}")
            return {"error": str(e)}

    # =============================================================================
    # 內部工具方法
    # =============================================================================

    async def _preload_popular_data(self) -> None:
        """預載熱門資料."""
        try:
            # 預載前10個熱門成就
            popular_achievements = await self._repository.get_popular_achievements(limit=10)

            for achievement, _ in popular_achievements:
                cache_key = f"achievement:{achievement.id}"
                await self._cache_manager.set(
                    CacheType.ACHIEVEMENT, cache_key, achievement
                )

            logger.info(f"預載了 {len(popular_achievements)} 個熱門成就")

        except Exception as e:
            logger.warning(f"預載熱門資料失敗: {e}")

    async def _track_operation_success(
        self,
        operation: str,
        start_time: datetime,
        user_id: int | None = None
    ) -> None:
        """追蹤操作成功."""
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        # 更新操作計數
        self._operation_counts[operation] = self._operation_counts.get(operation, 0) + 1

        # 記錄效能監控
        await self._performance_monitor.track_query_operation(
            operation=operation,
            duration_ms=duration_ms,
            success=True,
            user_id=user_id
        )

    async def _track_operation_failure(
        self,
        operation: str,
        start_time: datetime,
        error: str,
        user_id: int | None = None
    ) -> None:
        """追蹤操作失敗."""
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        # 記錄效能監控
        await self._performance_monitor.track_query_operation(
            operation=operation,
            duration_ms=duration_ms,
            success=False,
            user_id=user_id,
            context={"error": error}
        )

        logger.error(f"操作失敗: {operation}，錯誤: {error}")


__all__ = [
    "AchievementPerformanceService",
]
