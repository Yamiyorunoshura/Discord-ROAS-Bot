"""成就系統快取策略配置.

此模組提供成就系統的快取策略和配置，包含：
- TTL 快取配置
- 快取鍵值管理
- 快取無效化策略
- 效能優化配置

遵循快取最佳實踐，提供高效能的資料存取。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """快取配置類別."""
    ttl: int  # 存活時間（秒）
    maxsize: int  # 最大條目數
    enabled: bool = True  # 是否啟用快取


class AchievementCacheStrategy:
    """成就系統快取策略.

    定義成就系統各種資料的快取策略和配置。
    """

    # 預設快取配置
    DEFAULT_CONFIGS = {
        "achievement": CacheConfig(ttl=600, maxsize=500),  # 成就資料快取 10 分鐘
        "category": CacheConfig(ttl=1800, maxsize=100),    # 分類資料快取 30 分鐘
        "user_achievements": CacheConfig(ttl=300, maxsize=1000),  # 用戶成就快取 5 分鐘
        "user_progress": CacheConfig(ttl=60, maxsize=2000),  # 用戶進度快取 1 分鐘
        "global_stats": CacheConfig(ttl=900, maxsize=50),   # 全域統計快取 15 分鐘
        "leaderboard": CacheConfig(ttl=300, maxsize=100),   # 排行榜快取 5 分鐘
    }

    @classmethod
    def get_config(cls, cache_type: str) -> CacheConfig:
        """取得特定類型的快取配置.

        Args:
            cache_type: 快取類型

        Returns:
            快取配置物件
        """
        return cls.DEFAULT_CONFIGS.get(
            cache_type,
            CacheConfig(ttl=300, maxsize=100)  # 預設配置
        )

    @classmethod
    def get_cache_key(cls, cache_type: str, *args: Any) -> str:
        """生成標準化的快取鍵值.

        Args:
            cache_type: 快取類型
            *args: 快取參數

        Returns:
            標準化的快取鍵值
        """
        from .cache_key_standard import CacheKeyStandard, CacheKeyType

        try:
            # 將 cache_type 轉換為 CacheKeyType
            key_type = CacheKeyType(cache_type)

            # 根據參數數量和類型推斷參數名稱
            kwargs = cls._build_kwargs_from_args(cache_type, args)

            return CacheKeyStandard.generate_cache_key(key_type, **kwargs)

        except (ValueError, TypeError):
            # 回退到原始方法
            return f"achievement:{cache_type}:" + ":".join(str(arg) for arg in args)

    @classmethod
    def _build_kwargs_from_args(cls, cache_type: str, args: tuple[Any, ...]) -> dict[str, Any]:
        """根據快取類型和參數構建關鍵字參數.

        Args:
            cache_type: 快取類型
            args: 位置參數

        Returns:
            關鍵字參數字典
        """
        kwargs = {}

        if cache_type == "achievement" and len(args) >= 1:
            kwargs["achievement_id"] = args[0]
        elif cache_type == "category" and len(args) >= 1:
            kwargs["category_id"] = args[0]
        elif cache_type == "categories" and len(args) >= 1:
            kwargs["active_only"] = args[0]
        elif cache_type == "achievements":
            if len(args) >= 1 and args[0] is not None:
                kwargs["category_id"] = args[0]
            if len(args) >= 2 and args[1] is not None:
                kwargs["type"] = str(args[1])
            if len(args) >= 3:
                kwargs["active"] = args[2]
            if len(args) >= 4 and args[3] is not None:
                kwargs["limit"] = args[3]
            if len(args) >= 5:
                kwargs["offset"] = args[4]
        elif cache_type == "user_achievements":
            if len(args) >= 1:
                kwargs["user_id"] = args[0]
            if len(args) >= 2 and args[1] is not None:
                kwargs["category_id"] = args[1]
            if len(args) >= 3 and args[2] is not None:
                kwargs["limit"] = args[2]
        elif cache_type == "user_progress":
            if len(args) >= 1:
                kwargs["user_id"] = args[0]
            if len(args) >= 2 and args[1] is not None:
                kwargs["achievement_id"] = args[1]
        elif cache_type == "user_stats" and len(args) >= 1:
            kwargs["user_id"] = args[0]
        elif cache_type == "leaderboard":
            if len(args) >= 1:
                kwargs["type"] = args[0]
            if len(args) >= 2:
                kwargs["limit"] = args[1]
        elif cache_type == "popular_achievements" and len(args) >= 1:
            kwargs["limit"] = args[0]

        return kwargs

    @classmethod
    def get_invalidation_patterns(cls, operation_type: str, **kwargs) -> list[str]:
        """取得需要無效化的快取模式.

        Args:
            operation_type: 操作類型（create, update, delete）
            **kwargs: 操作相關參數

        Returns:
            需要無效化的快取模式列表
        """
        from .cache_key_standard import CacheKeyStandard

        try:
            # 使用標準化的無效化模式
            return CacheKeyStandard.get_invalidation_patterns_for_operation(
                operation_type, **kwargs
            )
        except Exception as e:
            logger.warning(f"使用標準化無效化模式失敗，回退到原始模式: {e}")

            # 回退到原始實現
            patterns = []

            if operation_type in ["create_achievement", "update_achievement", "delete_achievement"]:
                patterns.extend([
                    "achievement:",
                    "achievements:",
                    "global_stats",
                    "popular_achievements"
                ])

                # 如果有分類 ID，也無效化分類相關快取
                if "category_id" in kwargs:
                    patterns.append(f"category:{kwargs['category_id']}")

            elif operation_type in ["create_category", "update_category", "delete_category"]:
                patterns.extend([
                    "category:",
                    "categories:"
                ])

            elif operation_type in ["award_achievement", "update_progress"]:
                user_id = kwargs.get("user_id")
                if user_id:
                    patterns.extend([
                        f"user_achievements:{user_id}",
                        f"user_progress:{user_id}",
                        f"user_stats:{user_id}",
                        "global_stats",
                        "leaderboard"
                    ])

            return patterns


class CacheInvalidationManager:
    """快取無效化管理器.

    負責管理快取的無效化邏輯和策略。
    """

    def __init__(self):
        """初始化快取無效化管理器."""
        self._invalidation_history: list[dict[str, Any]] = []

    def invalidate_patterns(self, cache: Any, patterns: list[str]) -> int:
        """根據模式無效化快取項目.

        Args:
            cache: 快取物件
            patterns: 無效化模式列表

        Returns:
            無效化的項目數量
        """
        if not patterns:
            return 0

        keys_to_remove = []

        # 尋找匹配的快取鍵值
        for key in cache:
            if any(pattern in key for pattern in patterns):
                keys_to_remove.append(key)

        # 移除匹配的項目
        removed_count = 0
        for key in keys_to_remove:
            if cache.pop(key, None) is not None:
                removed_count += 1

        # 記錄無效化歷史
        if removed_count > 0:
            self._invalidation_history.append({
                "timestamp": logger.name,  # 使用 logger 名稱作為時間戳
                "patterns": patterns,
                "removed_count": removed_count,
                "removed_keys": keys_to_remove
            })

            logger.debug(
                "快取無效化完成",
                extra={
                    "patterns": patterns,
                    "removed_count": removed_count
                }
            )

        return removed_count

    def get_invalidation_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """取得快取無效化歷史.

        Args:
            limit: 返回的最大記錄數

        Returns:
            無效化歷史記錄列表
        """
        return self._invalidation_history[-limit:]

    def clear_invalidation_history(self) -> None:
        """清除無效化歷史記錄."""
        self._invalidation_history.clear()


class PerformanceOptimizer:
    """效能優化器.

    提供快取效能監控和優化建議。
    """

    def __init__(self):
        """初始化效能優化器."""
        self._hit_counts: dict[str, int] = {}
        self._miss_counts: dict[str, int] = {}

    def record_cache_hit(self, cache_type: str) -> None:
        """記錄快取命中.

        Args:
            cache_type: 快取類型
        """
        self._hit_counts[cache_type] = self._hit_counts.get(cache_type, 0) + 1

    def record_cache_miss(self, cache_type: str) -> None:
        """記錄快取未命中.

        Args:
            cache_type: 快取類型
        """
        self._miss_counts[cache_type] = self._miss_counts.get(cache_type, 0) + 1

    def get_cache_statistics(self) -> dict[str, dict[str, Any]]:
        """取得快取統計資料.

        Returns:
            快取統計資料字典
        """
        stats = {}

        all_cache_types = set(self._hit_counts.keys()) | set(self._miss_counts.keys())

        for cache_type in all_cache_types:
            hits = self._hit_counts.get(cache_type, 0)
            misses = self._miss_counts.get(cache_type, 0)
            total = hits + misses

            hit_rate = (hits / total * 100) if total > 0 else 0.0

            stats[cache_type] = {
                "hits": hits,
                "misses": misses,
                "total_requests": total,
                "hit_rate": round(hit_rate, 2),
                "efficiency": "excellent" if hit_rate >= 80 else
                            "good" if hit_rate >= 60 else
                            "fair" if hit_rate >= 40 else "poor"
            }

        return stats

    def get_optimization_suggestions(self) -> list[dict[str, Any]]:
        """取得效能優化建議.

        Returns:
            優化建議列表
        """
        suggestions = []
        stats = self.get_cache_statistics()

        for cache_type, stat in stats.items():
            hit_rate = stat["hit_rate"]
            total_requests = stat["total_requests"]

            if hit_rate < 40 and total_requests > 100:
                suggestions.append({
                    "cache_type": cache_type,
                    "issue": "low_hit_rate",
                    "current_hit_rate": hit_rate,
                    "suggestion": f"考慮增加 {cache_type} 快取的 TTL 或調整快取策略",
                    "priority": "high" if hit_rate < 20 else "medium"
                })

            if total_requests > 1000 and hit_rate > 90:
                suggestions.append({
                    "cache_type": cache_type,
                    "issue": "over_caching",
                    "current_hit_rate": hit_rate,
                    "suggestion": f"{cache_type} 快取效率很高，可以考慮增加快取大小以支援更多資料",
                    "priority": "low"
                })

        return suggestions

    def reset_statistics(self) -> None:
        """重置統計資料."""
        self._hit_counts.clear()
        self._miss_counts.clear()


__all__ = [
    "AchievementCacheStrategy",
    "CacheConfig",
    "CacheInvalidationManager",
    "PerformanceOptimizer",
]
