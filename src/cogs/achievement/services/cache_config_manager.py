"""成就系統快取配置管理器.

此模組實作成就系統的快取配置管理功能,提供:
- 動態配置調整
- 配置驗證和預設值管理
- 配置持久化(未來擴展)
- 配置變更通知機制
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from ..constants import (
    CACHE_SIZE_REDUCTION_THRESHOLD,
    HIGH_HIT_RATE_THRESHOLD,
    HIGH_REQUEST_COUNT_THRESHOLD,
    MIN_HIT_RATE_THRESHOLD,
    MIN_REQUEST_COUNT_FOR_ADJUSTMENT,
    MINIMUM_CACHE_SIZE,
)
from .cache_strategy import AchievementCacheStrategy, CacheConfig

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


@dataclass
class CacheConfigUpdate:
    """快取配置更新資料類別."""

    cache_type: str
    ttl: int | None = None
    maxsize: int | None = None
    enabled: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式."""
        return {
            k: v for k, v in asdict(self).items() if v is not None and k != "cache_type"
        }


class CacheConfigManager:
    """快取配置管理器.

    負責管理快取系統的配置變更、驗證和通知.
    """

    def __init__(self):
        """初始化配置管理器."""
        self._config_listeners: list[Callable[[str, dict[str, Any]], None]] = []
        self._validation_rules: dict[str, dict[str, Any]] = {
            "ttl": {"min": 10, "max": 86400},  # 10秒到1天
            "maxsize": {"min": 10, "max": 10000},  # 10到10000個項目
        }

        logger.info("CacheConfigManager 初始化完成")

    def add_config_listener(
        self, listener: Callable[[str, dict[str, Any]], None]
    ) -> None:
        """新增配置變更監聽器.

        Args:
            listener: 配置變更回調函數,接收 (cache_type, config_updates) 參數
        """
        self._config_listeners.append(listener)
        logger.debug(f"已新增配置監聽器: {listener.__name__}")

    def remove_config_listener(
        self, listener: Callable[[str, dict[str, Any]], None]
    ) -> None:
        """移除配置變更監聽器.

        Args:
            listener: 要移除的監聽器
        """
        if listener in self._config_listeners:
            self._config_listeners.remove(listener)
            logger.debug(f"已移除配置監聽器: {listener.__name__}")

    def validate_config_update(self, update: CacheConfigUpdate) -> tuple[bool, str]:
        """驗證配置更新.

        Args:
            update: 配置更新資料

        Returns:
            (是否有效, 錯誤訊息)
        """
        try:
            # 驗證 TTL
            if update.ttl is not None:
                ttl_rules = self._validation_rules["ttl"]
                if not (ttl_rules["min"] <= update.ttl <= ttl_rules["max"]):
                    return (
                        False,
                        f"TTL 必須在 {ttl_rules['min']}-{ttl_rules['max']} 秒之間",
                    )

            # 驗證快取大小
            if update.maxsize is not None:
                maxsize_rules = self._validation_rules["maxsize"]
                if not (maxsize_rules["min"] <= update.maxsize <= maxsize_rules["max"]):
                    return (
                        False,
                        f"快取大小必須在 {maxsize_rules['min']}-{maxsize_rules['max']} 之間",
                    )

            # 驗證快取類型
            valid_cache_types = [
                "achievement",
                "category",
                "user_achievements",
                "user_progress",
                "global_stats",
                "leaderboard",
            ]
            if update.cache_type not in valid_cache_types:
                return False, f"無效的快取類型: {update.cache_type}"

            return True, ""

        except Exception as e:
            return False, f"配置驗證失敗: {e}"

    def apply_config_update(self, update: CacheConfigUpdate) -> tuple[bool, str]:
        """應用配置更新.

        Args:
            update: 配置更新資料

        Returns:
            (是否成功, 結果訊息)
        """
        # 驗證配置
        is_valid, error_msg = self.validate_config_update(update)
        if not is_valid:
            logger.warning(f"配置更新驗證失敗: {error_msg}")
            return False, error_msg

        try:
            # 準備配置更新字典
            config_updates = update.to_dict()

            # 通知所有監聽器
            for listener in self._config_listeners:
                try:
                    listener(update.cache_type, config_updates)
                except Exception as e:
                    logger.error(
                        f"配置監聽器通知失敗: {listener.__name__}",
                        extra={"error": str(e)},
                        exc_info=True,
                    )

            logger.info(f"配置更新成功: {update.cache_type}", extra=config_updates)

            return True, "配置更新成功"

        except Exception as e:
            error_msg = f"配置更新失敗: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    def get_recommended_config(
        self, cache_type: str, usage_stats: dict[str, Any]
    ) -> CacheConfig:
        """根據使用統計取得建議配置.

        Args:
            cache_type: 快取類型
            usage_stats: 使用統計資料

        Returns:
            建議的快取配置
        """
        # 取得目前配置作為基礎
        current_config = AchievementCacheStrategy.get_config(cache_type)

        # 根據統計資料調整建議
        hit_rate = usage_stats.get("hit_rate", 0)
        usage_rate = usage_stats.get("usage_rate", 0)
        total_requests = usage_stats.get("total_requests", 0)

        recommended_config = CacheConfig(
            ttl=current_config.ttl,
            maxsize=current_config.maxsize,
            enabled=current_config.enabled,
        )

        # 基於命中率調整 TTL
        if (
            hit_rate < MIN_HIT_RATE_THRESHOLD
            and total_requests > MIN_REQUEST_COUNT_FOR_ADJUSTMENT
        ):
            # 命中率低,增加 TTL
            recommended_config.ttl = min(current_config.ttl * 1.5, 1800)
        elif (
            hit_rate > HIGH_HIT_RATE_THRESHOLD
            and total_requests > HIGH_REQUEST_COUNT_THRESHOLD
        ):
            # 命中率高,可以稍微減少 TTL 以保持資料新鮮度
            recommended_config.ttl = max(current_config.ttl * 0.8, 60)

        # 基於使用率調整快取大小
        if usage_rate > HIGH_HIT_RATE_THRESHOLD:
            # 使用率高,增加快取大小
            recommended_config.maxsize = min(current_config.maxsize * 1.5, 5000)
        elif (
            usage_rate < CACHE_SIZE_REDUCTION_THRESHOLD
            and current_config.maxsize > MINIMUM_CACHE_SIZE
        ):
            # 使用率低,減少快取大小以節省記憶體
            recommended_config.maxsize = max(current_config.maxsize * 0.7, 50)

        logger.debug(
            f"產生快取配置建議: {cache_type}",
            extra={
                "current": asdict(current_config),
                "recommended": asdict(recommended_config),
                "stats": usage_stats,
            },
        )

        return recommended_config

    def create_config_update_from_stats(
        self, cache_type: str, usage_stats: dict[str, Any]
    ) -> CacheConfigUpdate:
        """根據統計資料建立配置更新.

        Args:
            cache_type: 快取類型
            usage_stats: 使用統計資料

        Returns:
            配置更新資料
        """
        recommended = self.get_recommended_config(cache_type, usage_stats)

        return CacheConfigUpdate(
            cache_type=cache_type,
            ttl=recommended.ttl,
            maxsize=recommended.maxsize,
            enabled=recommended.enabled,
        )

    def auto_optimize_config(
        self,
        cache_type: str,
        usage_stats: dict[str, Any],
        apply_immediately: bool = False,
    ) -> tuple[bool, str, CacheConfigUpdate]:
        """自動優化快取配置.

        Args:
            cache_type: 快取類型
            usage_stats: 使用統計資料
            apply_immediately: 是否立即應用配置

        Returns:
            (是否成功, 結果訊息, 配置更新資料)
        """
        try:
            # 生成優化建議
            update = self.create_config_update_from_stats(cache_type, usage_stats)

            # 如果需要立即應用
            if apply_immediately:
                success, message = self.apply_config_update(update)
                return success, message, update
            else:
                return True, "配置優化建議已生成", update

        except Exception as e:
            error_msg = f"自動優化配置失敗: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, CacheConfigUpdate(cache_type=cache_type)

    def get_validation_rules(self) -> dict[str, dict[str, Any]]:
        """取得配置驗證規則.

        Returns:
            驗證規則字典
        """
        return self._validation_rules.copy()

    def update_validation_rules(self, rules: dict[str, dict[str, Any]]) -> None:
        """更新配置驗證規則.

        Args:
            rules: 新的驗證規則
        """
        self._validation_rules.update(rules)
        logger.info("配置驗證規則已更新", extra={"updated_rules": list(rules.keys())})


__all__ = [
    "CacheConfigManager",
    "CacheConfigUpdate",
]
