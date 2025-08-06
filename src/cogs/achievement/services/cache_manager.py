"""成就系統快取管理器.

此模組提供成就系統的快取管理功能,實作多層快取策略:
- L1 快取:記憶體快取(cachetools TTLCache)
- L2 快取:檔案快取(持久化快取)
- 快取失效和更新策略
- 快取效能監控

根據 Story 5.1 Task 1.4 和 Task 2 的要求實作,支援完善的查詢快取機制.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import pickle
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from cachetools import LRUCache, TTLCache

from ..database.models import Achievement, UserAchievement

logger = logging.getLogger(__name__)


class CacheLevel(str, Enum):
    """快取層級."""

    L1_MEMORY = "l1_memory"
    L2_FILE = "l2_file"


class CacheType(str, Enum):
    """快取類型."""

    ACHIEVEMENT = "achievement"
    ACHIEVEMENT_LIST = "achievement_list"
    USER_ACHIEVEMENT = "user_achievement"
    USER_PROGRESS = "user_progress"
    STATS = "stats"
    LEADERBOARD = "leaderboard"


@dataclass
class CacheConfig:
    """快取配置."""

    max_size: int = 1000
    """最大快取項目數"""

    ttl_seconds: int = 300
    """存活時間(秒)"""

    enable_l2_cache: bool = True
    """是否啟用 L2 檔案快取"""

    l2_cache_path: str | None = None
    """L2 快取檔案路徑"""


@dataclass
class CacheStats:
    """快取統計."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    hit_rate: float = 0.0
    last_reset: datetime = None


class CacheManager:
    """成就系統快取管理器.

    提供多層快取管理和自動失效機制.
    """

    def __init__(
        self,
        cache_configs: dict[CacheType, CacheConfig] | None = None,
        cache_dir: str | None = None,
    ):
        """初始化快取管理器.

        Args:
            cache_configs: 快取配置字典
            cache_dir: 快取目錄路徑
        """
        self._cache_configs = cache_configs or self._get_default_configs()
        self._cache_dir = Path(cache_dir or "./cache/achievement")
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        # L1 記憶體快取
        self._l1_caches: dict[CacheType, TTLCache | LRUCache] = {}
        self._init_l1_caches()

        # L2 檔案快取映射
        self._l2_cache_files: dict[CacheType, Path] = {}
        self._init_l2_cache_files()

        # 快取統計
        self._stats: dict[CacheType, CacheStats] = {}
        self._init_stats()

        # 快取失效追蹤
        self._invalidation_keys: dict[str, set[str]] = {}

        # 背景清理任務
        self._cleanup_task: asyncio.Task | None = None
        self._is_running = False

        logger.info(f"CacheManager 初始化完成,快取目錄: {self._cache_dir}")

    async def __aenter__(self) -> CacheManager:
        """異步上下文管理器進入."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """異步上下文管理器退出."""
        await self.stop()

    # =============================================================================
    # 快取操作介面
    # =============================================================================

    async def get(self, cache_type: CacheType, key: str, default: Any = None) -> Any:
        """從快取取得值.

        Args:
            cache_type: 快取類型
            key: 快取鍵
            default: 預設值

        Returns:
            快取的值或預設值
        """
        # 先嘗試 L1 記憶體快取
        l1_cache = self._l1_caches.get(cache_type)
        if l1_cache and key in l1_cache:
            self._stats[cache_type].hits += 1
            logger.debug(f"L1 快取命中: {cache_type.value}:{key}")
            return l1_cache[key]

        # 嘗試 L2 檔案快取
        config = self._cache_configs[cache_type]
        if config.enable_l2_cache:
            l2_value = await self._get_from_l2_cache(cache_type, key)
            if l2_value is not None:
                # 回填到 L1 快取
                if l1_cache:
                    l1_cache[key] = l2_value
                self._stats[cache_type].hits += 1
                logger.debug(f"L2 快取命中: {cache_type.value}:{key}")
                return l2_value

        # 快取未命中
        self._stats[cache_type].misses += 1
        logger.debug(f"快取未命中: {cache_type.value}:{key}")
        return default

    async def set(
        self, cache_type: CacheType, key: str, value: Any, ttl: int | None = None
    ) -> None:
        """設定快取值.

        Args:
            cache_type: 快取類型
            key: 快取鍵
            value: 快取值
            ttl: 自訂存活時間(覆蓋預設配置)
        """
        # 設定到 L1 記憶體快取
        l1_cache = self._l1_caches.get(cache_type)
        if l1_cache:
            l1_cache[key] = value
            self._stats[cache_type].size = len(l1_cache)

        # 設定到 L2 檔案快取
        config = self._cache_configs[cache_type]
        if config.enable_l2_cache:
            await self._set_to_l2_cache(
                cache_type, key, value, ttl or config.ttl_seconds
            )

        # 記錄失效追蹤
        self._track_invalidation_keys(cache_type, key, value)

        logger.debug(f"快取已設定: {cache_type.value}:{key}")

    async def delete(self, cache_type: CacheType, key: str) -> bool:
        """刪除快取項目.

        Args:
            cache_type: 快取類型
            key: 快取鍵

        Returns:
            是否成功刪除
        """
        deleted = False

        # 從 L1 快取刪除
        l1_cache = self._l1_caches.get(cache_type)
        if l1_cache and key in l1_cache:
            del l1_cache[key]
            self._stats[cache_type].size = len(l1_cache)
            deleted = True

        # 從 L2 快取刪除
        config = self._cache_configs[cache_type]
        if config.enable_l2_cache:
            l2_deleted = await self._delete_from_l2_cache(cache_type, key)
            deleted = deleted or l2_deleted

        if deleted:
            logger.debug(f"快取已刪除: {cache_type.value}:{key}")

        return deleted

    async def clear(self, cache_type: CacheType | None = None) -> None:
        """清空快取.

        Args:
            cache_type: 要清空的快取類型,None 表示清空所有
        """
        if cache_type:
            # 清空特定類型快取
            l1_cache = self._l1_caches.get(cache_type)
            if l1_cache:
                l1_cache.clear()
                self._stats[cache_type].size = 0

            config = self._cache_configs[cache_type]
            if config.enable_l2_cache:
                await self._clear_l2_cache(cache_type)

            logger.info(f"快取已清空: {cache_type.value}")
        else:
            # 清空所有快取
            for cache in self._l1_caches.values():
                cache.clear()

            for config_cache_type in self._cache_configs:
                self._stats[config_cache_type].size = 0
                config = self._cache_configs[config_cache_type]
                if config.enable_l2_cache:
                    await self._clear_l2_cache(config_cache_type)

            logger.info("所有快取已清空")

    # =============================================================================
    # 智慧失效機制
    # =============================================================================

    async def invalidate_by_user(self, user_id: int) -> int:
        """使用戶相關快取失效.

        Args:
            user_id: 用戶 ID

        Returns:
            失效的快取項目數量
        """
        invalidated_count = 0

        # 失效模式
        patterns = [
            f"user:{user_id}:",
            f"user_achievements:{user_id}",
            f"user_progress:{user_id}",
            f"user_stats:{user_id}",
        ]

        for cache_type in [
            CacheType.USER_ACHIEVEMENT,
            CacheType.USER_PROGRESS,
            CacheType.STATS,
        ]:
            if cache_type not in self._cache_configs:
                continue  # 跳過未配置的快取類型
            count = await self._invalidate_by_patterns(cache_type, patterns)
            invalidated_count += count

        logger.info(f"用戶 {user_id} 相關快取已失效: {invalidated_count} 項")
        return invalidated_count

    async def invalidate_by_achievement(self, achievement_id: int) -> int:
        """使成就相關快取失效.

        Args:
            achievement_id: 成就 ID

        Returns:
            失效的快取項目數量
        """
        invalidated_count = 0

        # 失效模式
        patterns = [
            f"achievement:{achievement_id}",
            "achievement_list:",  # 成就列表需要重新載入
            "leaderboard:",  # 排行榜可能受影響
        ]

        for cache_type in [
            CacheType.ACHIEVEMENT,
            CacheType.ACHIEVEMENT_LIST,
            CacheType.LEADERBOARD,
        ]:
            if cache_type not in self._cache_configs:
                continue  # 跳過未配置的快取類型
            count = await self._invalidate_by_patterns(cache_type, patterns)
            invalidated_count += count

        logger.info(f"成就 {achievement_id} 相關快取已失效: {invalidated_count} 項")
        return invalidated_count

    async def invalidate_by_category(self, category_id: int) -> int:
        """使分類相關快取失效.

        Args:
            category_id: 分類 ID

        Returns:
            失效的快取項目數量
        """
        invalidated_count = 0

        # 分類變更影響成就列表和統計
        patterns = [
            f"category:{category_id}:",
            "achievement_list:",
            "stats:",
        ]

        for cache_type in [CacheType.ACHIEVEMENT_LIST, CacheType.STATS]:
            if cache_type not in self._cache_configs:
                continue  # 跳過未配置的快取類型
            count = await self._invalidate_by_patterns(cache_type, patterns)
            invalidated_count += count

        logger.info(f"分類 {category_id} 相關快取已失效: {invalidated_count} 項")
        return invalidated_count

    # =============================================================================
    # 快取預熱
    # =============================================================================

    async def warmup_achievement_cache(self, achievement_ids: list[int]) -> None:
        """預熱成就快取.

        Args:
            achievement_ids: 要預熱的成就 ID 列表
        """
        logger.info(f"開始預熱成就快取: {len(achievement_ids)} 項")

        # 這裡需要與 repository 整合,暫時跳過具體實作
        # 在實際使用時,會透過 service 層調用 repository 載入資料並快取

        logger.info("成就快取預熱完成")

    async def warmup_user_cache(self, user_ids: list[int]) -> None:
        """預熱用戶快取.

        Args:
            user_ids: 要預熱的用戶 ID 列表
        """
        logger.info(f"開始預熱用戶快取: {len(user_ids)} 項")

        # 這裡需要與 repository 整合,暫時跳過具體實作

        logger.info("用戶快取預熱完成")

    # =============================================================================
    # 快取統計和監控
    # =============================================================================

    def get_stats(self, cache_type: CacheType | None = None) -> dict[str, Any]:
        """取得快取統計.

        Args:
            cache_type: 快取類型,None 表示取得所有統計

        Returns:
            快取統計資訊
        """
        if cache_type:
            stats = self._stats[cache_type]
            total_requests = stats.hits + stats.misses
            hit_rate = stats.hits / max(total_requests, 1)

            return {
                "type": cache_type.value,
                "hits": stats.hits,
                "misses": stats.misses,
                "hit_rate": hit_rate,
                "size": stats.size,
                "evictions": stats.evictions,
                "last_reset": stats.last_reset.isoformat()
                if stats.last_reset
                else None,
            }
        else:
            all_stats = {}
            total_hits = total_misses = total_size = 0

            for ct, stats in self._stats.items():
                total_hits += stats.hits
                total_misses += stats.misses
                total_size += stats.size

                total_requests = stats.hits + stats.misses
                hit_rate = stats.hits / max(total_requests, 1)

                all_stats[ct.value] = {
                    "hits": stats.hits,
                    "misses": stats.misses,
                    "hit_rate": hit_rate,
                    "size": stats.size,
                    "evictions": stats.evictions,
                }

            # 總體統計
            total_requests = total_hits + total_misses
            overall_hit_rate = total_hits / max(total_requests, 1)

            return {
                "overall": {
                    "total_hits": total_hits,
                    "total_misses": total_misses,
                    "hit_rate": overall_hit_rate,
                    "total_size": total_size,
                    "total_requests": total_requests,
                },
                "by_type": all_stats,
            }

    def reset_stats(self, cache_type: CacheType | None = None) -> None:
        """重置快取統計.

        Args:
            cache_type: 快取類型,None 表示重置所有統計
        """
        now = datetime.now()

        if cache_type:
            self._stats[cache_type] = CacheStats(last_reset=now)
            logger.info(f"快取統計已重置: {cache_type.value}")
        else:
            for ct in self._stats:
                self._stats[ct] = CacheStats(last_reset=now)
            logger.info("所有快取統計已重置")

    # =============================================================================
    # 生命週期管理
    # =============================================================================

    async def start(self) -> None:
        """啟動快取管理器."""
        if not self._is_running:
            self._is_running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("快取管理器已啟動")

    async def stop(self) -> None:
        """停止快取管理器."""
        if self._is_running:
            self._is_running = False
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._cleanup_task
            logger.info("快取管理器已停止")

    # =============================================================================
    # 內部實作方法
    # =============================================================================

    def _get_default_configs(self) -> dict[CacheType, CacheConfig]:
        """取得預設快取配置."""
        return {
            CacheType.ACHIEVEMENT: CacheConfig(
                max_size=500, ttl_seconds=600, enable_l2_cache=True
            ),
            CacheType.ACHIEVEMENT_LIST: CacheConfig(
                max_size=100, ttl_seconds=300, enable_l2_cache=True
            ),
            CacheType.USER_ACHIEVEMENT: CacheConfig(
                max_size=1000, ttl_seconds=300, enable_l2_cache=True
            ),
            CacheType.USER_PROGRESS: CacheConfig(
                max_size=2000,
                ttl_seconds=180,
                enable_l2_cache=False,  # 進度變化頻繁
            ),
            CacheType.STATS: CacheConfig(
                max_size=200, ttl_seconds=900, enable_l2_cache=True
            ),
            CacheType.LEADERBOARD: CacheConfig(
                max_size=50, ttl_seconds=300, enable_l2_cache=True
            ),
        }

    def _init_l1_caches(self) -> None:
        """初始化 L1 記憶體快取."""
        for cache_type, config in self._cache_configs.items():
            if config.ttl_seconds > 0:
                cache = TTLCache(maxsize=config.max_size, ttl=config.ttl_seconds)
            else:
                cache = LRUCache(maxsize=config.max_size)

            self._l1_caches[cache_type] = cache

        logger.debug("L1 記憶體快取初始化完成")

    def _init_l2_cache_files(self) -> None:
        """初始化 L2 檔案快取路徑."""
        for cache_type in self._cache_configs:
            cache_file = self._cache_dir / f"{cache_type.value}.cache"
            self._l2_cache_files[cache_type] = cache_file

        logger.debug("L2 檔案快取路徑初始化完成")

    def _init_stats(self) -> None:
        """初始化快取統計."""
        for cache_type in self._cache_configs:
            self._stats[cache_type] = CacheStats(last_reset=datetime.now())

    async def _get_from_l2_cache(self, cache_type: CacheType, key: str) -> Any:
        """從 L2 檔案快取取得值."""
        try:
            cache_file = self._l2_cache_files[cache_type]
            if not cache_file.exists():
                return None

            # 載入整個快取檔案
            with cache_file.open("rb") as f:
                cache_data = pickle.load(f)

            # 檢查項目是否存在且未過期
            if key in cache_data:
                item = cache_data[key]
                if item["expires_at"] > time.time():
                    return item["value"]
                else:
                    # 項目已過期,刪除它
                    del cache_data[key]
                    with cache_file.open("wb") as f:
                        pickle.dump(cache_data, f)

            return None

        except Exception as e:
            logger.warning(f"L2 快取讀取失敗 {cache_type.value}:{key}: {e}")
            return None

    async def _set_to_l2_cache(
        self, cache_type: CacheType, key: str, value: Any, ttl_seconds: int
    ) -> None:
        """設定值到 L2 檔案快取."""
        try:
            cache_file = self._l2_cache_files[cache_type]

            # 載入現有快取資料
            cache_data = {}
            if cache_file.exists():
                try:
                    with cache_file.open("rb") as f:
                        cache_data = pickle.load(f)
                except Exception:
                    cache_data = {}

            # 設定新項目
            cache_data[key] = {
                "value": value,
                "expires_at": time.time() + ttl_seconds,
                "created_at": time.time(),
            }

            # 寫回檔案
            with cache_file.open("wb") as f:
                pickle.dump(cache_data, f)

        except Exception as e:
            logger.warning(f"L2 快取寫入失敗 {cache_type.value}:{key}: {e}")

    async def _delete_from_l2_cache(self, cache_type: CacheType, key: str) -> bool:
        """從 L2 檔案快取刪除項目."""
        try:
            cache_file = self._l2_cache_files[cache_type]
            if not cache_file.exists():
                return False

            with cache_file.open("rb") as f:
                cache_data = pickle.load(f)

            if key in cache_data:
                del cache_data[key]
                with cache_file.open("wb") as f:
                    pickle.dump(cache_data, f)
                return True

            return False

        except Exception as e:
            logger.warning(f"L2 快取刪除失敗 {cache_type.value}:{key}: {e}")
            return False

    async def _clear_l2_cache(self, cache_type: CacheType) -> None:
        """清空 L2 檔案快取."""
        try:
            cache_file = self._l2_cache_files[cache_type]
            if cache_file.exists():
                cache_file.unlink()
        except Exception as e:
            logger.warning(f"L2 快取清空失敗 {cache_type.value}: {e}")

    async def _invalidate_by_patterns(
        self, cache_type: CacheType, patterns: list[str]
    ) -> int:
        """根據模式失效快取項目."""
        invalidated_count = 0

        # L1 快取失效
        l1_cache = self._l1_caches.get(cache_type)
        if l1_cache:
            keys_to_remove = []
            for key in l1_cache:
                for pattern in patterns:
                    if pattern in key:
                        keys_to_remove.append(key)
                        break

            for key in keys_to_remove:
                del l1_cache[key]
                invalidated_count += 1

            self._stats[cache_type].size = len(l1_cache)

        # L2 快取失效
        config = self._cache_configs.get(cache_type)
        if config and config.enable_l2_cache:
            l2_count = await self._invalidate_l2_by_patterns(cache_type, patterns)
            invalidated_count += l2_count

        return invalidated_count

    async def _invalidate_l2_by_patterns(
        self, cache_type: CacheType, patterns: list[str]
    ) -> int:
        """根據模式失效 L2 快取項目."""
        try:
            cache_file = self._l2_cache_files[cache_type]
            if not cache_file.exists():
                return 0

            with cache_file.open("rb") as f:
                cache_data = pickle.load(f)

            keys_to_remove = []
            for key in cache_data:
                for pattern in patterns:
                    if pattern in key:
                        keys_to_remove.append(key)
                        break

            for key in keys_to_remove:
                del cache_data[key]

            if keys_to_remove:
                with cache_file.open("wb") as f:
                    pickle.dump(cache_data, f)

            return len(keys_to_remove)

        except Exception as e:
            logger.warning(f"L2 快取模式失效失敗 {cache_type.value}: {e}")
            return 0

    def _track_invalidation_keys(
        self, _cache_type: CacheType, key: str, value: Any
    ) -> None:
        """追蹤快取項目的失效鍵."""
        # 根據值的類型提取失效鍵
        invalidation_keys = set()

        if isinstance(value, Achievement | dict) and hasattr(value, "id"):
            invalidation_keys.add(f"achievement:{value.id}")
            if hasattr(value, "category_id"):
                invalidation_keys.add(f"category:{value.category_id}")

        elif isinstance(value, UserAchievement | dict) and hasattr(value, "user_id"):
            invalidation_keys.add(f"user:{value.user_id}")
            if hasattr(value, "achievement_id"):
                invalidation_keys.add(f"achievement:{value.achievement_id}")

        # 記錄失效追蹤
        self._invalidation_keys[key] = invalidation_keys

    def _generate_cache_key(self, *parts: Any) -> str:
        """生成快取鍵."""
        key_parts = [str(part).replace(":", "_") for part in parts]
        return ":".join(key_parts)

    async def _cleanup_loop(self) -> None:
        """背景清理循環."""
        while self._is_running:
            try:
                await self._cleanup_expired_l2_cache()
                await asyncio.sleep(300)  # 每5分鐘清理一次

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"快取清理循環錯誤: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _cleanup_expired_l2_cache(self) -> None:
        """清理過期的 L2 快取項目."""
        current_time = time.time()
        cleaned_count = 0

        for cache_type, cache_file in self._l2_cache_files.items():
            try:
                if not cache_file.exists():
                    continue

                with cache_file.open("rb") as f:
                    cache_data = pickle.load(f)

                # 找出過期項目
                expired_keys = []
                for key, item in cache_data.items():
                    if item["expires_at"] <= current_time:
                        expired_keys.append(key)

                # 刪除過期項目
                if expired_keys:
                    for key in expired_keys:
                        del cache_data[key]
                        cleaned_count += 1

                    with cache_file.open("wb") as f:
                        pickle.dump(cache_data, f)

            except Exception as e:
                logger.warning(f"L2 快取清理失敗 {cache_type.value}: {e}")

        if cleaned_count > 0:
            logger.debug(f"L2 快取清理完成: {cleaned_count} 項過期項目")


__all__ = [
    "CacheConfig",
    "CacheLevel",
    "CacheManager",
    "CacheStats",
    "CacheType",
]
