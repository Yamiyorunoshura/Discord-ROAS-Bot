"""
資料同步模組快取服務 - 重構版本

提供同步狀態管理和快取功能
採用依賴注入模式設計
"""

import asyncio
import datetime as dt
from threading import Lock
from typing import Protocol


# ────────────────────────────
# 服務接口定義
# ────────────────────────────
class ISyncDataCache(Protocol):
    """資料同步快取服務接口"""

    def is_syncing(self, guild_id: int) -> bool:
        """檢查是否正在同步中"""
        ...

    def mark_syncing(self, guild_id: int) -> None:
        """標記為同步中"""
        ...

    def clear_sync_mark(self, guild_id: int) -> None:
        """清除同步標記"""
        ...

    def get_last_sync_time(self, guild_id: int) -> dt.datetime | None:
        """取得最後同步時間"""
        ...

    def set_last_sync_time(self, guild_id: int, sync_time: dt.datetime) -> None:
        """設定最後同步時間"""
        ...

    def get_sync_lock(self, guild_id: int) -> asyncio.Lock:
        """取得同步鎖"""
        ...

    def clear_all(self) -> None:
        """清除所有快取"""
        ...

class SyncDataCacheService:
    """資料同步快取服務實現"""

    def __init__(self, min_sync_interval: int = 300):
        """
        初始化快取服務

        Args:
            min_sync_interval: 最小同步間隔(秒)
        """
        self._min_sync_interval = min_sync_interval
        self._sync_cache: dict[int, dt.datetime] = {}
        self._sync_locks: dict[int, asyncio.Lock] = {}
        self._thread_lock = Lock()  # 用於線程安全的鎖管理

    def is_syncing(self, guild_id: int) -> bool:
        """
        檢查是否正在同步中

        Args:
            guild_id: 伺服器 ID

        Returns:
            bool: 是否正在同步中
        """
        if guild_id not in self._sync_cache:
            return False

        last_sync = self._sync_cache[guild_id]
        time_diff = (dt.datetime.utcnow() - last_sync).total_seconds()

        # 如果在最小間隔內有同步過,則認為正在同步中
        return time_diff < self._min_sync_interval

    def mark_syncing(self, guild_id: int) -> None:
        """
        標記為同步中

        Args:
            guild_id: 伺服器 ID
        """
        self._sync_cache[guild_id] = dt.datetime.utcnow()

    def clear_sync_mark(self, guild_id: int) -> None:
        """
        清除同步標記

        Args:
            guild_id: 伺服器 ID
        """
        self._sync_cache.pop(guild_id, None)

    def get_last_sync_time(self, guild_id: int) -> dt.datetime | None:
        """
        取得最後同步時間

        Args:
            guild_id: 伺服器 ID

        Returns:
            Optional[dt.datetime]: 最後同步時間
        """
        return self._sync_cache.get(guild_id)

    def set_last_sync_time(self, guild_id: int, sync_time: dt.datetime) -> None:
        """
        設定最後同步時間

        Args:
            guild_id: 伺服器 ID
            sync_time: 同步時間
        """
        self._sync_cache[guild_id] = sync_time

    def get_sync_lock(self, guild_id: int) -> asyncio.Lock:
        """
        取得同步鎖(線程安全)

        Args:
            guild_id: 伺服器 ID

        Returns:
            asyncio.Lock: 同步鎖
        """
        with self._thread_lock:
            if guild_id not in self._sync_locks:
                self._sync_locks[guild_id] = asyncio.Lock()
            return self._sync_locks[guild_id]

    def clear_all(self) -> None:
        """清除所有快取"""
        with self._thread_lock:
            self._sync_cache.clear()
            # 清理未使用的鎖
            locked_locks = []
            for guild_id, lock in self._sync_locks.items():
                if lock.locked():
                    locked_locks.append(guild_id)

            # 保留正在使用的鎖
            self._sync_locks = {
                guild_id: lock
                for guild_id, lock in self._sync_locks.items()
                if guild_id in locked_locks
            }

    def get_cache_stats(self) -> dict[str, int]:
        """
        取得快取統計資訊

        Returns:
            Dict[str, int]: 快取統計
        """
        with self._thread_lock:
            return {
                "cached_guilds": len(self._sync_cache),
                "active_locks": len(self._sync_locks),
                "locked_count": sum(
                    1 for lock in self._sync_locks.values() if lock.locked()
                ),
            }
