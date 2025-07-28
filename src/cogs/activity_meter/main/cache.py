"""
🎯 ActivityCache - 活躍度系統緩存模塊
- 提供高效的緩存機制
- 支援TTL和LRU策略
- 實現緩存統計和監控
- 支援模式匹配的緩存清理
"""

import logging
import re
import time
from collections import OrderedDict
from typing import Any

logger = logging.getLogger("activity_cache")


class CacheEntry:
    """緩存條目"""

    def __init__(self, key: str, value: Any, ttl: int = 300):
        """
        初始化緩存條目

        Args:
            key: 緩存鍵
            value: 緩存值
            ttl: 生存時間(秒)
        """
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
        self.access_count = 0
        self.last_accessed = time.time()

    def is_expired(self) -> bool:
        """檢查是否過期"""
        return time.time() - self.created_at > self.ttl

    def access(self):
        """記錄訪問"""
        self.access_count += 1
        self.last_accessed = time.time()

    def get_age(self) -> float:
        """獲取年齡(秒)"""
        return time.time() - self.created_at


class ActivityCache:
    """
    活躍度系統緩存
    - 提供高效的緩存機制
    - 支援TTL和LRU策略
    - 實現緩存統計和監控
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        初始化緩存

        Args:
            max_size: 最大緩存條目數
            default_ttl: 預設TTL(秒)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()

        # 統計數據
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expirations = 0

        logger.info(
            f"✅ ActivityCache 初始化成功 (max_size={max_size}, default_ttl={default_ttl})"
        )

    def get(self, key: str) -> Any | None:
        """
        獲取緩存值

        Args:
            key: 緩存鍵

        Returns:
            Any | None: 緩存值,如果不存在或過期則返回None
        """
        if key not in self.cache:
            self.misses += 1
            return None

        entry = self.cache[key]

        # 檢查是否過期
        if entry.is_expired():
            del self.cache[key]
            self.expirations += 1
            self.misses += 1
            return None

        # 記錄訪問
        entry.access()
        self.hits += 1

        # 移動到末尾(LRU)
        self.cache.move_to_end(key)

        return entry.value

    def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """
        設置緩存值

        Args:
            key: 緩存鍵
            value: 緩存值
            ttl: 生存時間(秒),None表示使用預設值

        Returns:
            bool: 設置是否成功
        """
        try:
            # 如果鍵已存在,先移除
            if key in self.cache:
                del self.cache[key]

            # 檢查緩存大小
            if len(self.cache) >= self.max_size:
                self._evict_lru()

            # 創建新的緩存條目
            entry = CacheEntry(key, value, ttl or self.default_ttl)
            self.cache[key] = entry

            return True

        except Exception as e:
            logger.error(f"❌ 設置緩存失敗: {key}, 錯誤: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        刪除緩存值

        Args:
            key: 緩存鍵

        Returns:
            bool: 刪除是否成功
        """
        try:
            if key in self.cache:
                del self.cache[key]
                return True
            return False

        except Exception as e:
            logger.error(f"❌ 刪除緩存失敗: {key}, 錯誤: {e}")
            return False

    def clear(self, pattern: str | None = None):
        """
        清除緩存

        Args:
            pattern: 緩存模式匹配,None表示清除所有
        """
        try:
            if pattern is None:
                # 清除所有緩存
                self.cache.clear()
                logger.info("✅ 所有緩存已清除")
            else:
                # 根據模式清除緩存
                keys_to_delete = []
                for key in self.cache:
                    if re.match(pattern, key):
                        keys_to_delete.append(key)

                for key in keys_to_delete:
                    del self.cache[key]

                logger.info(
                    f"✅ 根據模式 '{pattern}' 清除了 {len(keys_to_delete)} 個緩存"
                )

        except Exception as e:
            logger.error(f"❌ 清除緩存失敗: {e}")

    def _evict_lru(self):
        """驅逐最近最少使用的緩存條目"""
        if not self.cache:
            return

        # 移除最舊的條目
        oldest_key = next(iter(self.cache))
        del self.cache[oldest_key]
        self.evictions += 1

    def cleanup_expired(self) -> int:
        """
        清理過期的緩存條目

        Returns:
            int: 清理的條目數量
        """
        expired_keys = []
        for key, entry in self.cache.items():
            if entry.is_expired():
                expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]
            self.expirations += 1

        if expired_keys:
            logger.info(f"🧹 清理了 {len(expired_keys)} 個過期緩存")

        return len(expired_keys)

    def get_stats(self) -> dict[str, Any]:
        """
        獲取緩存統計

        Returns:
            Dict[str, Any]: 緩存統計數據
        """
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "total_requests": total_requests,
        }

    def get_cache_info(self) -> dict[str, Any]:
        """
        獲取緩存詳細信息

        Returns:
            Dict[str, Any]: 緩存詳細信息
        """
        cache_info = []
        for key, entry in self.cache.items():
            cache_info.append(
                {
                    "key": key,
                    "age": entry.get_age(),
                    "ttl": entry.ttl,
                    "access_count": entry.access_count,
                    "last_accessed": entry.last_accessed,
                    "is_expired": entry.is_expired(),
                }
            )

        return {"entries": cache_info, "stats": self.get_stats()}

    def set_max_size(self, max_size: int):
        """
        設置最大緩存大小

        Args:
            max_size: 新的最大大小
        """
        self.max_size = max_size

        # 如果當前大小超過新的最大值,進行清理
        while len(self.cache) > self.max_size:
            self._evict_lru()

        logger.info(f"✅ 緩存最大大小已更新: {max_size}")

    def set_default_ttl(self, ttl: int):
        """
        設置預設TTL

        Args:
            ttl: 新的預設TTL(秒)
        """
        self.default_ttl = ttl
        logger.info(f"✅ 預設TTL已更新: {ttl}秒")

    def get_memory_usage(self) -> dict[str, Any]:
        """
        獲取記憶體使用情況

        Returns:
            Dict[str, Any]: 記憶體使用數據
        """
        # 簡化的記憶體使用估算
        total_size = 0
        for key, entry in self.cache.items():
            # 估算每個條目的大小
            total_size += len(str(key)) + len(str(entry.value)) + 100  # 額外開銷

        return {
            "estimated_size_bytes": total_size,
            "estimated_size_mb": total_size / (1024 * 1024),
            "entries_count": len(self.cache),
        }
