"""
¯ ActivityCache - æ´»èºåº¦ç³»çµ±ç·©å­æ¨¡å¡
- æä¾é«æçç·©å­æ©å¶
- æ¯æ´TTLåLRUç­ç¥
- å¯¦ç¾ç·©å­çµ±è¨åç£æ§
- æ¯æ´æ¨¡å¼å¹éçç·©å­æ¸ç
"""

import logging
import re
import time
from collections import OrderedDict
from typing import Any

logger = logging.getLogger("activity_cache")


class CacheEntry:
    """ç·©å­æ¢ç®"""

    def __init__(self, key: str, value: Any, ttl: int = 300):
        """
        åå§åç·©å­æ¢ç®

        Args:
            key: ç·©å­éµ
            value: ç·©å­å¼
            ttl: çå­æé(ç§)
        """
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
        self.access_count = 0
        self.last_accessed = time.time()

    def is_expired(self) -> bool:
        """æª¢æ¥æ¯å¦éæ"""
        return time.time() - self.created_at > self.ttl

    def access(self):
        """è¨éè¨ªå"""
        self.access_count += 1
        self.last_accessed = time.time()

    def get_age(self) -> float:
        """ç²åå¹´é½¡(ç§)"""
        return time.time() - self.created_at


class ActivityCache:
    """
    æ´»èºåº¦ç³»çµ±ç·©å­
    - æä¾é«æçç·©å­æ©å¶
    - æ¯æ´TTLåLRUç­ç¥
    - å¯¦ç¾ç·©å­çµ±è¨åç£æ§
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        åå§åç·©å­

        Args:
            max_size: æå¤§ç·©å­æ¢ç®æ¸
            default_ttl: é è¨­TTL(ç§)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()

        # çµ±è¨æ¸æ
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expirations = 0

        logger.info(
            f"ActivityCache åå§åæå (max_size={max_size}, default_ttl={default_ttl})"
        )

    def get(self, key: str) -> Any | None:
        """
        ç²åç·©å­å¼

        Args:
            key: ç·©å­éµ

        Returns:
            Any | None: ç·©å­å¼,å¦æä¸å­å¨æéæåè¿åNone
        """
        if key not in self.cache:
            self.misses += 1
            return None

        entry = self.cache[key]

        # æª¢æ¥æ¯å¦éæ
        if entry.is_expired():
            del self.cache[key]
            self.expirations += 1
            self.misses += 1
            return None

        # è¨éè¨ªå
        entry.access()
        self.hits += 1

        self.cache.move_to_end(key)

        return entry.value

    def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """
        è¨­ç½®ç·©å­å¼

        Args:
            key: ç·©å­éµ
            value: ç·©å­å¼
            ttl: çå­æé(ç§),Noneè¡¨ç¤ºä½¿ç¨é è¨­å¼

        Returns:
            bool: è¨­ç½®æ¯å¦æå
        """
        try:
            # å¦æéµå·²å­å¨,åç§»é¤
            if key in self.cache:
                del self.cache[key]

            # æª¢æ¥ç·©å­å¤§å°
            if len(self.cache) >= self.max_size:
                self._evict_lru()

            # åµå»ºæ°çç·©å­æ¢ç®
            entry = CacheEntry(key, value, ttl or self.default_ttl)
            self.cache[key] = entry

            return True

        except Exception as e:
            logger.error(f"è¨­ç½®ç·©å­å¤±æ: {key}, é¯èª¤: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        åªé¤ç·©å­å¼

        Args:
            key: ç·©å­éµ

        Returns:
            bool: åªé¤æ¯å¦æå
        """
        try:
            if key in self.cache:
                del self.cache[key]
                return True
            return False

        except Exception as e:
            logger.error(f"åªé¤ç·©å­å¤±æ: {key}, é¯èª¤: {e}")
            return False

    def clear(self, pattern: str | None = None):
        """
        æ¸é¤ç·©å­

        Args:
            pattern: ç·©å­æ¨¡å¼å¹é,Noneè¡¨ç¤ºæ¸é¤ææ
        """
        try:
            if pattern is None:
                # æ¸é¤ææç·©å­
                self.cache.clear()
                logger.info("ææç·©å­å·²æ¸é¤")
            else:
                # æ ¹ææ¨¡å¼æ¸é¤ç·©å­
                keys_to_delete = []
                for key in self.cache:
                    if re.match(pattern, key):
                        keys_to_delete.append(key)

                for key in keys_to_delete:
                    del self.cache[key]

                logger.info(
                    f"æ ¹ææ¨¡å¼ '{pattern}' æ¸é¤äº {len(keys_to_delete)} åç·©å­"
                )

        except Exception as e:
            logger.error(f"æ¸é¤ç·©å­å¤±æ: {e}")

    def _evict_lru(self):
        """é©éæè¿æå°ä½¿ç¨çç·©å­æ¢ç®"""
        if not self.cache:
            return

        # ç§»é¤æèçæ¢ç®
        oldest_key = next(iter(self.cache))
        del self.cache[oldest_key]
        self.evictions += 1

    def cleanup_expired(self) -> int:
        """
        æ¸çéæçç·©å­æ¢ç®

        Returns:
            int: æ¸ççæ¢ç®æ¸é
        """
        expired_keys = []
        for key, entry in self.cache.items():
            if entry.is_expired():
                expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]
            self.expirations += 1

        if expired_keys:
            logger.info(f"ð§¹ æ¸çäº {len(expired_keys)} åéæç·©å­")

        return len(expired_keys)

    def get_stats(self) -> dict[str, Any]:
        """
        ç²åç·©å­çµ±è¨

        Returns:
            Dict[str, Any]: ç·©å­çµ±è¨æ¸æ
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
        ç²åç·©å­è©³ç´°ä¿¡æ¯

        Returns:
            Dict[str, Any]: ç·©å­è©³ç´°ä¿¡æ¯
        """
        cache_info = []
        for key, entry in self.cache.items():
            cache_info.append({
                "key": key,
                "age": entry.get_age(),
                "ttl": entry.ttl,
                "access_count": entry.access_count,
                "last_accessed": entry.last_accessed,
                "is_expired": entry.is_expired(),
            })

        return {"entries": cache_info, "stats": self.get_stats()}

    def set_max_size(self, max_size: int):
        """
        è¨­ç½®æå¤§ç·©å­å¤§å°

        Args:
            max_size: æ°çæå¤§å¤§å°
        """
        self.max_size = max_size

        # å¦æç¶åå¤§å°è¶éæ°çæå¤§å¼,é²è¡æ¸ç
        while len(self.cache) > self.max_size:
            self._evict_lru()

        logger.info(f"ç·©å­æå¤§å¤§å°å·²æ´æ°: {max_size}")

    def set_default_ttl(self, ttl: int):
        """
        è¨­ç½®é è¨­TTL

        Args:
            ttl: æ°çé è¨­TTL(ç§)
        """
        self.default_ttl = ttl
        logger.info(f"é è¨­TTLå·²æ´æ°: {ttl}ç§")

    def get_memory_usage(self) -> dict[str, Any]:
        """
        ç²åè¨æ¶é«ä½¿ç¨ææ³

        Returns:
            Dict[str, Any]: è¨æ¶é«ä½¿ç¨æ¸æ
        """
        # ç°¡åçè¨æ¶é«ä½¿ç¨ä¼°ç®
        total_size = 0
        for key, entry in self.cache.items():
            # ä¼°ç®æ¯åæ¢ç®çå¤§å°
            total_size += len(str(key)) + len(str(entry.value)) + 100  # é¡å¤éé·

        return {
            "estimated_size_bytes": total_size,
            "estimated_size_mb": total_size / (1024 * 1024),
            "entries_count": len(self.cache),
        }
