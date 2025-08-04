"""成就系統快取服務.

此模組實作成就系統的快取管理功能,整合 AchievementCacheStrategy 和 cachetools,
提供高效能的資料快取和智慧無效化機制.

功能包含:
- 多層快取架構管理
- 智慧快取無效化
- 效能監控和優化
- 動態配置調整
"""

from __future__ import annotations

import logging
from typing import Any, TypeVar

from cachetools import TTLCache

from ..constants import CRITICAL_USAGE_RATE, WARNING_USAGE_RATE
from .cache_config_manager import CacheConfigManager, CacheConfigUpdate
from .cache_strategy import (
    AchievementCacheStrategy,
    CacheInvalidationManager,
    PerformanceOptimizer,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

class AchievementCacheService:
    """成就系統快取服務.

    整合 AchievementCacheStrategy 提供完整的快取管理功能.
    """

    def __init__(self):
        """初始化快取服務."""
        self._caches: dict[str, TTLCache] = {}
        self._strategy = AchievementCacheStrategy()
        self._invalidation_manager = CacheInvalidationManager()
        self._performance_optimizer = PerformanceOptimizer()
        self._config_manager = CacheConfigManager()

        # 註冊配置變更監聽器
        self._config_manager.add_config_listener(self._on_config_changed)

        # 初始化各種類型的快取
        self._initialize_caches()

        logger.info("AchievementCacheService 初始化完成")

    def _initialize_caches(self) -> None:
        """根據策略配置初始化所有快取."""
        cache_types = [
            "achievement",
            "category",
            "user_achievements",
            "user_progress",
            "global_stats",
            "leaderboard",
        ]

        initialized_count = 0
        failed_count = 0

        for cache_type in cache_types:
            try:
                config = self._strategy.get_config(cache_type)
                if config.enabled:
                    self._caches[cache_type] = TTLCache(
                        maxsize=config.maxsize, ttl=config.ttl
                    )
                    initialized_count += 1
                    logger.debug(
                        f"快取初始化完成: {cache_type}",
                        extra={"maxsize": config.maxsize, "ttl": config.ttl},
                    )
                else:
                    logger.debug(f"快取已禁用,跳過初始化: {cache_type}")
            except Exception as e:
                failed_count += 1
                logger.error(
                    f"快取初始化失敗: {cache_type}",
                    extra={"error": str(e)},
                    exc_info=True,
                )

        logger.info(
            f"快取初始化完成 - 成功: {initialized_count}, 失敗: {failed_count}",
            extra={
                "initialized_caches": list(self._caches.keys()),
                "total_types": len(cache_types),
            },
        )

    def reinitialize_cache(self, cache_type: str) -> bool:
        """重新初始化特定快取.

        Args:
            cache_type: 快取類型

        Returns:
            True 如果重新初始化成功
        """
        try:
            # 清除現有快取
            if cache_type in self._caches:
                del self._caches[cache_type]

            # 重新初始化
            config = self._strategy.get_config(cache_type)
            if config.enabled:
                self._caches[cache_type] = TTLCache(
                    maxsize=config.maxsize, ttl=config.ttl
                )
                logger.info(f"快取重新初始化成功: {cache_type}")
                return True
            else:
                logger.info(f"快取已禁用,無法重新初始化: {cache_type}")
                return False

        except Exception as e:
            logger.error(
                f"快取重新初始化失敗: {cache_type}",
                extra={"error": str(e)},
                exc_info=True,
            )
            return False

    def get_cache_health_status(self) -> dict[str, dict[str, Any]]:
        """取得快取健康狀態.

        Returns:
            包含所有快取健康狀態的字典
        """
        health_status = {}

        for cache_type, cache in self._caches.items():
            try:
                config = self._strategy.get_config(cache_type)
                current_size = len(cache)
                usage_rate = (current_size / config.maxsize) * 100

                # 判斷健康狀態
                status = "healthy"
                issues = []

                if usage_rate > CRITICAL_USAGE_RATE:
                    status = "critical"
                    issues.append("快取使用率過高")
                elif usage_rate > WARNING_USAGE_RATE:
                    status = "warning"
                    issues.append("快取使用率偏高")

                # 檢查快取是否過期或無效
                try:
                    # 嘗試存取快取來檢查是否正常運作
                    test_key = f"health_check_{cache_type}"
                    cache[test_key] = "test"
                    cache.pop(test_key, None)
                except Exception:
                    status = "error"
                    issues.append("快取存取失敗")

                health_status[cache_type] = {
                    "status": status,
                    "current_size": current_size,
                    "max_size": config.maxsize,
                    "usage_rate": round(usage_rate, 2),
                    "ttl": config.ttl,
                    "enabled": config.enabled,
                    "issues": issues,
                }

            except Exception as e:
                health_status[cache_type] = {
                    "status": "error",
                    "error": str(e),
                    "enabled": False,
                }

        return health_status

    def _on_config_changed(
        self, cache_type: str, config_updates: dict[str, Any]
    ) -> None:
        """配置變更事件處理器.

        Args:
            cache_type: 快取類型
            config_updates: 配置更新項目
        """
        try:
            self.update_cache_config(cache_type, **config_updates)
            logger.info(f"配置變更已應用: {cache_type}", extra=config_updates)
        except Exception as e:
            logger.error(
                f"配置變更應用失敗: {cache_type}",
                extra={"error": str(e), "config_updates": config_updates},
                exc_info=True,
            )

    def get_cache_key(self, cache_type: str, *args: Any) -> str:
        """生成標準化的快取鍵值.

        Args:
            cache_type: 快取類型
            *args: 快取參數

        Returns:
            標準化的快取鍵值
        """
        return self._strategy.get_cache_key(cache_type, *args)

    def get(self, cache_type: str, key: str) -> Any | None:
        """從快取中取得資料.

        Args:
            cache_type: 快取類型
            key: 快取鍵值

        Returns:
            快取的資料或 None
        """
        cache = self._caches.get(cache_type)
        if cache is None:
            self._performance_optimizer.record_cache_miss(cache_type)
            return None

        result = cache.get(key)
        if result is not None:
            self._performance_optimizer.record_cache_hit(cache_type)
            logger.debug(f"快取命中: {cache_type}:{key}")
        else:
            self._performance_optimizer.record_cache_miss(cache_type)
            logger.debug(f"快取未命中: {cache_type}:{key}")

        return result

    def set(self, cache_type: str, key: str, value: Any) -> bool:
        """設定快取資料.

        Args:
            cache_type: 快取類型
            key: 快取鍵值
            value: 要快取的資料

        Returns:
            True 如果設定成功,False 如果快取類型不存在
        """
        cache = self._caches.get(cache_type)
        if cache is not None:
            cache[key] = value
            logger.debug(f"快取設定: {cache_type}:{key}")
            return True
        else:
            logger.warning(f"快取類型不存在: {cache_type}")
            return False

    def invalidate_by_operation(self, operation_type: str, **kwargs) -> int:
        """根據操作類型無效化相關快取.

        Args:
            operation_type: 操作類型
            **kwargs: 操作相關參數

        Returns:
            無效化的項目總數
        """
        patterns = self._strategy.get_invalidation_patterns(operation_type, **kwargs)
        if not patterns:
            return 0

        total_removed = 0
        for _cache_type, cache in self._caches.items():
            removed = self._invalidation_manager.invalidate_patterns(cache, patterns)
            total_removed += removed

        logger.info(
            f"快取無效化完成: {operation_type}",
            extra={
                "patterns": patterns,
                "total_removed": total_removed,
                "kwargs": kwargs,
            },
        )

        return total_removed

    def invalidate_by_patterns(self, cache_type: str, patterns: list[str]) -> int:
        """根據模式無效化特定快取.

        Args:
            cache_type: 快取類型
            patterns: 無效化模式列表

        Returns:
            無效化的項目數量
        """
        cache = self._caches.get(cache_type)
        if cache is None:
            return 0

        return self._invalidation_manager.invalidate_patterns(cache, patterns)

    def clear_cache(self, cache_type: str) -> None:
        """清除特定類型的快取.

        Args:
            cache_type: 快取類型
        """
        cache = self._caches.get(cache_type)
        if cache is not None:
            cache.clear()
            logger.info(f"快取已清除: {cache_type}")

    def clear_all_caches(self) -> None:
        """清除所有快取."""
        for _cache_type, cache in self._caches.items():
            cache.clear()
        logger.info("所有快取已清除")

    def get_cache_statistics(self) -> dict[str, dict[str, Any]]:
        """取得快取統計資料.

        Returns:
            包含所有快取統計的字典
        """
        perf_stats = self._performance_optimizer.get_cache_statistics()

        # 增加快取大小和配置資訊
        stats = {}
        for cache_type, cache in self._caches.items():
            config = self._strategy.get_config(cache_type)
            cache_stats = perf_stats.get(cache_type, {})

            stats[cache_type] = {
                **cache_stats,
                "current_size": len(cache),
                "max_size": config.maxsize,
                "ttl": config.ttl,
                "usage_rate": round(len(cache) / config.maxsize * 100, 2),
                "enabled": config.enabled,
            }

        return stats

    def get_optimization_suggestions(self) -> list[dict[str, Any]]:
        """取得快取優化建議.

        Returns:
            優化建議列表
        """
        suggestions = self._performance_optimizer.get_optimization_suggestions()

        # 增加基於快取使用率的建議
        stats = self.get_cache_statistics()
        for cache_type, stat in stats.items():
            usage_rate = stat.get("usage_rate", 0)

            if usage_rate > CRITICAL_USAGE_RATE:
                suggestions.append(
                    {
                        "cache_type": cache_type,
                        "issue": "high_usage_rate",
                        "current_usage_rate": usage_rate,
                        "suggestion": f"{cache_type} 快取使用率過高 ({usage_rate}%),建議增加快取大小",
                        "priority": "medium",
                    }
                )

        return suggestions

    def get_invalidation_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """取得快取無效化歷史.

        Args:
            limit: 返回的最大記錄數

        Returns:
            無效化歷史記錄列表
        """
        return self._invalidation_manager.get_invalidation_history(limit)

    def update_cache_config(self, cache_type: str, **config_updates) -> bool:
        """動態更新快取配置.

        Args:
            cache_type: 快取類型
            **config_updates: 配置更新項目

        Returns:
            True 如果更新成功
        """
        try:
            current_config = self._strategy.get_config(cache_type)

            # 創建新的快取配置
            ttl = config_updates.get("ttl", current_config.ttl)
            maxsize = config_updates.get("maxsize", current_config.maxsize)
            enabled = config_updates.get("enabled", current_config.enabled)

            if enabled:
                # 備份現有資料
                old_cache = self._caches.get(cache_type)
                old_data = dict(old_cache) if old_cache else {}

                # 創建新快取
                new_cache = TTLCache(maxsize=maxsize, ttl=ttl)

                # 遷移可能的資料
                for key, value in old_data.items():
                    if len(new_cache) < maxsize:
                        new_cache[key] = value

                self._caches[cache_type] = new_cache
            # 禁用快取
            elif cache_type in self._caches:
                del self._caches[cache_type]

            logger.info(f"快取配置更新成功: {cache_type}", extra=config_updates)
            return True

        except Exception as e:
            logger.error(
                f"快取配置更新失敗: {cache_type}",
                extra={"error": str(e), "config_updates": config_updates},
                exc_info=True,
            )
            return False

    def apply_config_update(self, update: CacheConfigUpdate) -> bool:
        """應用快取配置更新.

        Args:
            update: 配置更新資料

        Returns:
            True 如果更新成功
        """
        success, message = self._config_manager.apply_config_update(update)
        if not success:
            logger.warning(f"配置更新失敗: {message}")
        return success

    def get_config_recommendations(self) -> dict[str, CacheConfigUpdate]:
        """取得所有快取類型的配置建議.

        Returns:
            包含配置建議的字典
        """
        recommendations = {}
        stats = self.get_cache_statistics()

        for cache_type, cache_stats in stats.items():
            try:
                update = self._config_manager.create_config_update_from_stats(
                    cache_type, cache_stats
                )
                recommendations[cache_type] = update
            except Exception as e:
                logger.error(
                    f"產生配置建議失敗: {cache_type}",
                    extra={"error": str(e)},
                    exc_info=True,
                )

        return recommendations

    def auto_optimize_all_caches(
        self, apply_immediately: bool = False
    ) -> dict[str, tuple[bool, str]]:
        """自動優化所有快取配置.

        Args:
            apply_immediately: 是否立即應用配置

        Returns:
            每個快取類型的優化結果
        """
        results = {}
        stats = self.get_cache_statistics()

        for cache_type, cache_stats in stats.items():
            try:
                success, message, update = self._config_manager.auto_optimize_config(
                    cache_type, cache_stats, apply_immediately
                )
                results[cache_type] = (success, message)

                if success and not apply_immediately:
                    logger.info(
                        f"配置優化建議: {cache_type}",
                        extra={"update": update.to_dict()},
                    )

            except Exception as e:
                error_msg = f"自動優化失敗: {e}"
                results[cache_type] = (False, error_msg)
                logger.error(
                    f"自動優化配置失敗: {cache_type}",
                    extra={"error": str(e)},
                    exc_info=True,
                )

        return results

    async def __aenter__(self) -> AchievementCacheService:
        """異步上下文管理器進入."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """異步上下文管理器退出."""
        logger.info("開始快取服務清理...")

        try:
            # 記錄清理前的狀態
            cache_stats = self.get_cache_statistics()
            total_items = sum(
                stat.get("current_size", 0) for stat in cache_stats.values()
            )

            # 清理快取
            self.clear_all_caches()

            # 重置效能統計
            self._performance_optimizer.reset_statistics()

            # 清理無效化歷史
            self._invalidation_manager.clear_invalidation_history()

            # 移除配置監聽器
            if hasattr(self, "_config_manager"):
                try:
                    self._config_manager.remove_config_listener(self._on_config_changed)
                except Exception as e:
                    logger.warning(f"移除配置監聽器失敗: {e}")

            logger.info(
                "快取服務清理完成",
                extra={
                    "cleared_cache_types": len(cache_stats),
                    "cleared_items": total_items,
                    "exception_occurred": exc_type is not None,
                },
            )

        except Exception as cleanup_error:
            logger.error(
                "快取服務清理過程中發生錯誤",
                extra={"error": str(cleanup_error)},
                exc_info=True,
            )

    def graceful_shutdown(self) -> dict[str, Any]:
        """優雅關閉快取服務.

        Returns:
            關閉統計資料
        """
        logger.info("開始優雅關閉快取服務...")

        # 收集關閉前統計
        shutdown_stats = {
            "cache_statistics": self.get_cache_statistics(),
            "performance_stats": self._performance_optimizer.get_cache_statistics(),
            "invalidation_history": self._invalidation_manager.get_invalidation_history(
                10
            ),
            "health_status": self.get_cache_health_status(),
        }

        # Store critical data if needed
        critical_issues = []
        for cache_type, health in shutdown_stats["health_status"].items():
            if health.get("status") in ["critical", "error"]:
                critical_issues.append(
                    {
                        "cache_type": cache_type,
                        "status": health.get("status"),
                        "issues": health.get("issues", []),
                    }
                )

        shutdown_stats["critical_issues"] = critical_issues

        # 執行清理
        try:
            self.clear_all_caches()
            self._performance_optimizer.reset_statistics()
            self._invalidation_manager.clear_invalidation_history()

            shutdown_stats["cleanup_success"] = True
            logger.info("快取服務優雅關閉完成")

        except Exception as e:
            shutdown_stats["cleanup_success"] = False
            shutdown_stats["cleanup_error"] = str(e)
            logger.error(f"快取服務關閉清理失敗: {e}", exc_info=True)

        return shutdown_stats

__all__ = [
    "AchievementCacheService",
]
