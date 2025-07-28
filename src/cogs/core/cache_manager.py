"""
🗄️ 多級緩存管理系統
Discord ADR Bot v1.6 - 統一緩存架構

提供企業級的多級緩存功能:
- L1內存緩存(高速訪問)
- L2持久化緩存(數據持久性)
- 智能緩存策略(LRU、TTL、LFU)
- 緩存同步機制
- 完整的監控指標
- 智能緩存預熱
- 性能優化和分析

作者:Discord ADR Bot 架構師
版本:v1.6
"""

import asyncio
import functools
import hashlib
import json
import logging
import pickle
import sqlite3
import threading
import time
import weakref
from abc import ABC, abstractmethod
from collections import OrderedDict, defaultdict, deque
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    TypeVar,
)

# 設置日誌
logger = logging.getLogger(__name__)

# 類型變量
K = TypeVar("K")  # Key type
V = TypeVar("V")  # Value type


class CacheStrategy(Enum):
    """緩存策略枚舉"""

    LRU = "lru"  # 最近最少使用
    LFU = "lfu"  # 最不常用
    TTL = "ttl"  # 基於時間
    FIFO = "fifo"  # 先進先出
    HYBRID = "hybrid"  # 混合策略
    ADAPTIVE = "adaptive"  # 自適應策略


class CacheLevel(Enum):
    """緩存級別枚舉"""

    L1 = 1  # 內存緩存
    L2 = 2  # 持久化緩存
    BOTH = 3  # 兩級緩存


class CacheOperation(Enum):
    """緩存操作枚舉"""

    GET = "get"
    SET = "set"
    DELETE = "delete"
    CLEAR = "clear"
    EXPIRE = "expire"
    PRELOAD = "preload"


class CachePattern(Enum):
    """緩存模式枚舉"""

    READ_THROUGH = "read_through"  # 讀穿透
    WRITE_THROUGH = "write_through"  # 寫穿透
    WRITE_BEHIND = "write_behind"  # 寫回
    CACHE_ASIDE = "cache_aside"  # 旁路緩存


@dataclass
class CacheEntry:
    """緩存條目"""

    key: str
    value: Any
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    ttl: float | None = None
    size: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    hit_count: int = 0
    miss_count: int = 0
    load_time: float = 0.0

    def __post_init__(self):
        if self.size == 0:
            self.size = self._calculate_size()

    def _calculate_size(self) -> int:
        """計算條目大小"""
        try:
            return len(pickle.dumps(self.value))
        except:
            return len(str(self.value).encode("utf-8"))

    def is_expired(self) -> bool:
        """檢查是否過期"""
        if self.ttl is None:
            return False
        return time.time() - self.timestamp > self.ttl

    def touch(self):
        """更新訪問時間"""
        self.last_access = time.time()
        self.access_count += 1
        self.hit_count += 1

    def get_age(self) -> float:
        """獲取條目年齡(秒)"""
        return time.time() - self.timestamp

    def get_idle_time(self) -> float:
        """獲取空閒時間(秒)"""
        return time.time() - self.last_access

    def get_frequency_score(self) -> float:
        """獲取頻率分數"""
        age = self.get_age()
        return self.access_count / (age + 1)  # 避免除零


@dataclass
class CacheStats:
    """緩存統計"""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    expired: int = 0
    total_size: int = 0
    entry_count: int = 0
    preloads: int = 0
    preload_hits: int = 0
    avg_load_time: float = 0.0
    peak_size: int = 0

    @property
    def hit_rate(self) -> float:
        """命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def miss_rate(self) -> float:
        """未命中率"""
        return 1.0 - self.hit_rate

    @property
    def preload_effectiveness(self) -> float:
        """預載入有效性"""
        return self.preload_hits / self.preloads if self.preloads > 0 else 0.0

    def reset(self):
        """重置統計"""
        self.__dict__.update(CacheStats().__dict__)


class CacheAnalyzer:
    """緩存分析器"""

    def __init__(self, max_history: int = 1000):
        self.access_history: deque = deque(maxlen=max_history)
        self.pattern_stats: dict[str, int] = defaultdict(int)
        self.hot_keys: dict[str, int] = defaultdict(int)
        self.cold_keys: set[str] = set()
        self._lock = asyncio.Lock()

    async def record_access(self, key: str, operation: CacheOperation, hit: bool):
        """記錄訪問"""
        async with self._lock:
            access_time = time.time()
            self.access_history.append(
                {
                    "key": key,
                    "operation": operation.value,
                    "hit": hit,
                    "timestamp": access_time,
                }
            )

            # 更新熱點鍵統計
            if hit:
                self.hot_keys[key] += 1
            else:
                self.cold_keys.add(key)

    async def analyze_patterns(self) -> dict[str, Any]:
        """分析訪問模式"""
        async with self._lock:
            if not self.access_history:
                return {"error": "沒有訪問歷史"}

            # 分析最近的訪問模式
            recent_accesses = list(self.access_history)[-100:]  # 最近100次訪問

            # 計算各種指標
            total_accesses = len(recent_accesses)
            hits = sum(1 for access in recent_accesses if access["hit"])
            hit_rate = hits / total_accesses if total_accesses > 0 else 0

            # 熱點鍵分析
            top_hot_keys = sorted(
                self.hot_keys.items(), key=lambda x: x[1], reverse=True
            )[:10]

            # 訪問頻率分析
            key_frequency = defaultdict(int)
            for access in recent_accesses:
                key_frequency[access["key"]] += 1

            return {
                "total_accesses": total_accesses,
                "hit_rate": hit_rate,
                "top_hot_keys": top_hot_keys,
                "unique_keys_accessed": len(key_frequency),
                "cold_keys_count": len(self.cold_keys),
                "avg_accesses_per_key": sum(key_frequency.values()) / len(key_frequency)
                if key_frequency
                else 0,
            }

    async def get_preload_suggestions(self) -> list[str]:
        """獲取預載入建議"""
        async with self._lock:
            # 基於熱點鍵和訪問模式建議預載入
            suggestions = []

            # 高頻訪問但經常錯失的鍵
            for key, count in self.hot_keys.items():
                if count > 5 and key in self.cold_keys:  # 閾值可調整
                    suggestions.append(key)

            return suggestions[:20]  # 限制建議數量


class SmartCacheStrategy:
    """智能緩存策略"""

    def __init__(self, analyzer: CacheAnalyzer):
        self.analyzer = analyzer
        self.strategy_weights = {
            CacheStrategy.LRU: 0.3,
            CacheStrategy.LFU: 0.3,
            CacheStrategy.TTL: 0.2,
            CacheStrategy.ADAPTIVE: 0.2,
        }

    async def should_evict(
        self, entries: dict[str, CacheEntry], max_size: int
    ) -> list[str]:
        """智能選擇需要淘汰的條目"""
        if len(entries) <= max_size:
            return []

        # 獲取分析結果
        await self.analyzer.analyze_patterns()

        # 計算每個條目的淘汰分數
        eviction_scores = {}

        for key, entry in entries.items():
            score = 0.0

            # LRU 分數(年齡)
            age_score = entry.get_age() / 3600  # 標準化到小時
            score += age_score * self.strategy_weights[CacheStrategy.LRU]

            # LFU 分數(頻率的倒數)
            freq_score = 1.0 / (entry.get_frequency_score() + 0.01)  # 避免除零
            score += freq_score * self.strategy_weights[CacheStrategy.LFU]

            # TTL 分數
            if entry.ttl:
                ttl_score = (time.time() - entry.timestamp) / entry.ttl
                score += ttl_score * self.strategy_weights[CacheStrategy.TTL]

            # 自適應分數(基於訪問模式)
            if key in self.analyzer.cold_keys:
                score += 1.0 * self.strategy_weights[CacheStrategy.ADAPTIVE]

            eviction_scores[key] = score

        # 選擇分數最高的條目進行淘汰
        sorted_entries = sorted(
            eviction_scores.items(), key=lambda x: x[1], reverse=True
        )
        evict_count = len(entries) - max_size + 1  # 至少淘汰一個

        return [key for key, _ in sorted_entries[:evict_count]]


class CachePreloader:
    """緩存預載入器"""

    def __init__(self, cache_ref: weakref.ref, analyzer: CacheAnalyzer):
        self.cache_ref = cache_ref
        self.analyzer = analyzer
        self.preload_tasks: set[asyncio.Task] = set()
        self.preload_functions: dict[str, Callable] = {}
        self._lock = asyncio.Lock()

    def register_preload_function(self, pattern: str, func: Callable):
        """註冊預載入函數"""
        self.preload_functions[pattern] = func

    async def start_preloading(self):
        """開始預載入任務"""
        async with self._lock:
            # 獲取預載入建議
            suggestions = await self.analyzer.get_preload_suggestions()

            for key in suggestions:
                # 找到匹配的預載入函數
                for pattern, func in self.preload_functions.items():
                    if pattern in key or key.startswith(pattern):
                        task = asyncio.create_task(self._preload_key(key, func))
                        self.preload_tasks.add(task)
                        task.add_done_callback(self.preload_tasks.discard)
                        break

    async def _preload_key(self, key: str, loader_func: Callable):
        """預載入指定鍵"""
        try:
            cache = self.cache_ref()
            if cache is None:
                return

            # 檢查是否已存在
            if await cache.exists(key):
                return

            # 載入數據
            start_time = time.time()
            data = await loader_func(key)
            load_time = time.time() - start_time

            # 設置到緩存
            if data is not None:
                await cache.set(key, data, level=CacheLevel.BOTH)

                # 記錄預載入統計
                if hasattr(cache, "l1_backend") and hasattr(cache.l1_backend, "stats"):
                    cache.l1_backend.stats.preloads += 1

                logger.debug(f"預載入完成: {key} (耗時: {load_time:.3f}s)")

        except Exception as e:
            logger.error(f"預載入失敗 {key}: {e}")


class CacheBackend(ABC):
    """緩存後端抽象基類"""

    @abstractmethod
    async def get(self, key: str) -> CacheEntry | None:
        """獲取緩存條目"""
        pass

    @abstractmethod
    async def set(self, key: str, entry: CacheEntry) -> bool:
        """設置緩存條目"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """刪除緩存條目"""
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """清空緩存"""
        pass

    @abstractmethod
    async def keys(self) -> list[str]:
        """獲取所有鍵"""
        pass

    @abstractmethod
    async def size(self) -> int:
        """獲取緩存大小"""
        pass


class MemoryCacheBackend(CacheBackend):
    """內存緩存後端(L1)"""

    def __init__(
        self, max_size: int = 1000, strategy: CacheStrategy = CacheStrategy.LRU
    ):
        self.max_size = max_size
        self.strategy = strategy
        self._cache: dict[str, CacheEntry] = {}
        self._access_order: OrderedDict[str, float] = OrderedDict()
        self._lock = asyncio.Lock()
        self.stats = CacheStats()
        self.analyzer = CacheAnalyzer()
        self.smart_strategy = SmartCacheStrategy(self.analyzer)

    async def get(self, key: str) -> CacheEntry | None:
        """獲取緩存條目"""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self.stats.misses += 1
                await self.analyzer.record_access(key, CacheOperation.GET, False)
                return None

            # 檢查過期
            if entry.is_expired():
                await self._remove_entry(key)
                self.stats.misses += 1
                self.stats.expired += 1
                await self.analyzer.record_access(key, CacheOperation.GET, False)
                return None

            # 更新訪問信息
            entry.touch()
            self._update_access_order(key)
            self.stats.hits += 1
            await self.analyzer.record_access(key, CacheOperation.GET, True)

            return entry

    async def set(self, key: str, entry: CacheEntry) -> bool:
        """設置緩存條目"""
        async with self._lock:
            # 檢查是否需要淘汰
            if key not in self._cache and len(self._cache) >= self.max_size:
                await self._evict_entries()

            # 設置條目
            old_entry = self._cache.get(key)
            self._cache[key] = entry
            self._update_access_order(key)

            # 更新統計
            if old_entry is None:
                self.stats.sets += 1
                self.stats.entry_count += 1

            self.stats.total_size = sum(e.size for e in self._cache.values())
            self.stats.peak_size = max(self.stats.peak_size, self.stats.total_size)

            await self.analyzer.record_access(key, CacheOperation.SET, True)

            return True

    async def delete(self, key: str) -> bool:
        """刪除緩存條目"""
        async with self._lock:
            if key in self._cache:
                await self._remove_entry(key)
                self.stats.deletes += 1
                await self.analyzer.record_access(key, CacheOperation.DELETE, True)
                return True
            return False

    async def clear(self) -> bool:
        """清空緩存"""
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self.stats.entry_count = 0
            self.stats.total_size = 0
            return True

    async def keys(self) -> list[str]:
        """獲取所有鍵"""
        async with self._lock:
            return list(self._cache.keys())

    async def size(self) -> int:
        """獲取緩存大小"""
        async with self._lock:
            return len(self._cache)

    def _update_access_order(self, key: str):
        """更新訪問順序"""
        self._access_order[key] = time.time()
        self._access_order.move_to_end(key)

    async def _remove_entry(self, key: str):
        """移除條目"""
        if key in self._cache:
            entry = self._cache.pop(key)
            self._access_order.pop(key, None)
            self.stats.entry_count -= 1
            self.stats.total_size -= entry.size

    async def _evict_entries(self):
        """淘汰條目"""
        if self.strategy == CacheStrategy.ADAPTIVE:
            # 使用智能策略
            keys_to_evict = await self.smart_strategy.should_evict(
                self._cache, self.max_size - 1
            )
            for key in keys_to_evict:
                await self._remove_entry(key)
                self.stats.evictions += 1
        # 使用傳統策略
        elif self.strategy == CacheStrategy.LRU:
            # 移除最近最少使用的
            oldest_key = next(iter(self._access_order))
            await self._remove_entry(oldest_key)
            self.stats.evictions += 1
        elif self.strategy == CacheStrategy.LFU:
            # 移除最不常用的
            min_freq_key = min(
                self._cache.keys(), key=lambda k: self._cache[k].access_count
            )
            await self._remove_entry(min_freq_key)
            self.stats.evictions += 1

    async def get_detailed_stats(self) -> dict[str, Any]:
        """獲取詳細統計"""
        async with self._lock:
            base_stats = {
                "hits": self.stats.hits,
                "misses": self.stats.misses,
                "hit_rate": self.stats.hit_rate,
                "sets": self.stats.sets,
                "deletes": self.stats.deletes,
                "evictions": self.stats.evictions,
                "expired": self.stats.expired,
                "entry_count": self.stats.entry_count,
                "total_size": self.stats.total_size,
                "peak_size": self.stats.peak_size,
                "avg_entry_size": self.stats.total_size / self.stats.entry_count
                if self.stats.entry_count > 0
                else 0,
            }

            # 添加分析結果
            patterns = await self.analyzer.analyze_patterns()
            base_stats.update(patterns)

            return base_stats


class PersistentCacheBackend(CacheBackend):
    """持久化緩存後端(L2)"""

    def __init__(self, db_path: str = "cache.db", max_size: int = 10000):
        self.db_path = db_path
        self.max_size = max_size
        self.stats = CacheStats()
        self._connection_pool: list[sqlite3.Connection] = []
        self._pool_lock = threading.Lock()
        self._lock = asyncio.Lock()
        self._initialize_db()

    def _initialize_db(self):
        """初始化資料庫"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    value BLOB,
                    timestamp REAL,
                    access_count INTEGER,
                    last_access REAL,
                    ttl REAL,
                    size INTEGER,
                    metadata TEXT,
                    hit_count INTEGER DEFAULT 0,
                    load_time REAL DEFAULT 0.0
                )
            """)

            # 添加索引以提升性能
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_last_access ON cache_entries(last_access)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_access_count ON cache_entries(access_count)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_timestamp ON cache_entries(timestamp)"
            )

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"資料庫初始化失敗: {e}")

    def _get_connection(self) -> sqlite3.Connection:
        """獲取資料庫連接"""
        with self._pool_lock:
            if self._connection_pool:
                return self._connection_pool.pop()
            else:
                return sqlite3.connect(self.db_path)

    def _return_connection(self, conn: sqlite3.Connection):
        """歸還資料庫連接"""
        with self._pool_lock:
            if len(self._connection_pool) < 10:  # 限制連接池大小
                self._connection_pool.append(conn)
            else:
                conn.close()

    async def get(self, key: str) -> CacheEntry | None:
        """獲取緩存條目"""
        async with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    "SELECT * FROM cache_entries WHERE key = ?", (key,)
                )
                row = cursor.fetchone()

                if row is None:
                    self.stats.misses += 1
                    return None

                entry = self._row_to_entry(row)

                # 檢查過期
                if entry.is_expired():
                    await self._delete_entry(key, conn)
                    self.stats.misses += 1
                    self.stats.expired += 1
                    return None

                # 更新訪問信息
                entry.touch()
                await self._update_entry(entry, conn)
                self.stats.hits += 1

                return entry

            finally:
                self._return_connection(conn)

    async def set(self, key: str, entry: CacheEntry) -> bool:
        """設置緩存條目"""
        async with self._lock:
            conn = self._get_connection()
            try:
                # 檢查是否需要淘汰
                entry_count = await self._get_entry_count(conn)
                if entry_count >= self.max_size:
                    await self._evict_entries(conn)

                # 序列化數據
                value_blob = pickle.dumps(entry.value)
                metadata_json = json.dumps(entry.metadata)

                # 插入或更新
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cache_entries
                    (key, value, timestamp, access_count, last_access, ttl, size, metadata, hit_count, load_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        entry.key,
                        value_blob,
                        entry.timestamp,
                        entry.access_count,
                        entry.last_access,
                        entry.ttl,
                        entry.size,
                        metadata_json,
                        entry.hit_count,
                        entry.load_time,
                    ),
                )

                conn.commit()
                self.stats.sets += 1

                return True

            except Exception as e:
                logger.error(f"設置緩存條目失敗: {e}")
                return False
            finally:
                self._return_connection(conn)

    async def delete(self, key: str) -> bool:
        """刪除緩存條目"""
        async with self._lock:
            conn = self._get_connection()
            try:
                result = await self._delete_entry(key, conn)
                if result:
                    self.stats.deletes += 1
                return result
            finally:
                self._return_connection(conn)

    async def clear(self) -> bool:
        """清空緩存"""
        async with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("DELETE FROM cache_entries")
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"清空緩存失敗: {e}")
                return False
            finally:
                self._return_connection(conn)

    async def keys(self) -> list[str]:
        """獲取所有鍵"""
        async with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute("SELECT key FROM cache_entries")
                return [row[0] for row in cursor.fetchall()]
            finally:
                self._return_connection(conn)

    async def size(self) -> int:
        """獲取緩存大小"""
        async with self._lock:
            conn = self._get_connection()
            try:
                return await self._get_entry_count(conn)
            finally:
                self._return_connection(conn)

    def _row_to_entry(self, row: tuple) -> CacheEntry:
        """將資料庫行轉換為緩存條目"""
        (
            key,
            value_blob,
            timestamp,
            access_count,
            last_access,
            ttl,
            size,
            metadata_json,
            hit_count,
            load_time,
        ) = row

        try:
            value = pickle.loads(value_blob)
        except (pickle.PickleError, EOFError, ValueError) as e:
            logger.error(f"Failed to deserialize cache value: {e}")
            raise
        metadata = json.loads(metadata_json) if metadata_json else {}

        entry = CacheEntry(
            key=key,
            value=value,
            timestamp=timestamp,
            access_count=access_count,
            last_access=last_access,
            ttl=ttl,
            size=size,
            metadata=metadata,
        )
        entry.hit_count = hit_count or 0
        entry.load_time = load_time or 0.0

        return entry

    async def _delete_entry(self, key: str, conn: sqlite3.Connection) -> bool:
        """刪除條目"""
        cursor = conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
        conn.commit()
        return cursor.rowcount > 0

    async def _update_entry(self, entry: CacheEntry, conn: sqlite3.Connection):
        """更新條目"""
        conn.execute(
            """
            UPDATE cache_entries
            SET access_count = ?, last_access = ?, hit_count = ?
            WHERE key = ?
        """,
            (entry.access_count, entry.last_access, entry.hit_count, entry.key),
        )
        conn.commit()

    async def _get_entry_count(self, conn: sqlite3.Connection) -> int:
        """獲取條目數量"""
        cursor = conn.execute("SELECT COUNT(*) FROM cache_entries")
        return cursor.fetchone()[0]

    async def _evict_entries(self, conn: sqlite3.Connection):
        """淘汰條目"""
        # 移除最舊的條目
        conn.execute(
            """
            DELETE FROM cache_entries
            WHERE key IN (
                SELECT key FROM cache_entries
                ORDER BY last_access ASC
                LIMIT ?
            )
        """,
            (max(1, self.max_size // 10),),
        )  # 一次淘汰10%
        conn.commit()
        self.stats.evictions += conn.total_changes


class MultiLevelCache:
    """多級緩存管理器"""

    def __init__(
        self,
        l1_max_size: int = 1000,
        l2_max_size: int = 10000,
        l1_strategy: CacheStrategy = CacheStrategy.ADAPTIVE,
        default_ttl: float | None = None,
        db_path: str = "cache.db",
        enable_preloading: bool = True,
    ):
        self.l1_backend = MemoryCacheBackend(l1_max_size, l1_strategy)
        self.l2_backend = PersistentCacheBackend(db_path, l2_max_size)
        self.default_ttl = default_ttl
        self.enable_preloading = enable_preloading

        # 創建預載入器
        if enable_preloading:
            self.preloader = CachePreloader(weakref.ref(self), self.l1_backend.analyzer)
        else:
            self.preloader = None

        # 啟動清理任務
        self._cleanup_task = None
        self._start_cleanup_task()

    def _start_cleanup_task(self):
        """啟動清理任務"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        """清理循環"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分鐘清理一次
                await self._cleanup_expired()

                # 觸發預載入
                if self.preloader:
                    await self.preloader.start_preloading()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理任務錯誤: {e}")
                await asyncio.sleep(60)

    async def _cleanup_expired(self):
        """清理過期條目"""
        # 清理 L1 過期條目
        l1_keys = await self.l1_backend.keys()
        for key in l1_keys:
            entry = await self.l1_backend.get(key)
            if entry and entry.is_expired():
                await self.l1_backend.delete(key)

        # 清理 L2 過期條目(通過資料庫查詢)
        # 這裡可以添加更高效的批量清理邏輯

    async def get(self, key: str) -> Any | None:
        """獲取緩存值"""
        # 先從 L1 獲取
        entry = await self.l1_backend.get(key)
        if entry:
            return entry.value

        # 再從 L2 獲取
        entry = await self.l2_backend.get(key)
        if entry:
            # 提升到 L1
            await self.l1_backend.set(key, entry)
            return entry.value

        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: float | None = None,
        level: CacheLevel = CacheLevel.BOTH,
    ) -> bool:
        """設置緩存值"""
        if ttl is None:
            ttl = self.default_ttl

        entry = CacheEntry(key=key, value=value, ttl=ttl, load_time=0.0)

        success = True

        # 根據級別設置緩存
        if level in [CacheLevel.L1, CacheLevel.BOTH]:
            success &= await self.l1_backend.set(key, entry)

        if level in [CacheLevel.L2, CacheLevel.BOTH]:
            success &= await self.l2_backend.set(key, entry)

        return success

    async def delete(self, key: str, level: CacheLevel = CacheLevel.BOTH) -> bool:
        """刪除緩存值"""
        success = True

        if level in [CacheLevel.L1, CacheLevel.BOTH]:
            success &= await self.l1_backend.delete(key)

        if level in [CacheLevel.L2, CacheLevel.BOTH]:
            success &= await self.l2_backend.delete(key)

        return success

    async def clear(self, level: CacheLevel = CacheLevel.BOTH) -> bool:
        """清空緩存"""
        success = True

        if level in [CacheLevel.L1, CacheLevel.BOTH]:
            success &= await self.l1_backend.clear()

        if level in [CacheLevel.L2, CacheLevel.BOTH]:
            success &= await self.l2_backend.clear()

        return success

    async def exists(self, key: str) -> bool:
        """檢查鍵是否存在"""
        return await self.get(key) is not None

    async def expire(self, key: str, ttl: float) -> bool:
        """設置過期時間"""
        # 更新 L1
        entry = await self.l1_backend.get(key)
        if entry:
            entry.ttl = ttl
            entry.timestamp = time.time()
            await self.l1_backend.set(key, entry)

        # 更新 L2
        entry = await self.l2_backend.get(key)
        if entry:
            entry.ttl = ttl
            entry.timestamp = time.time()
            await self.l2_backend.set(key, entry)

        return True

    def get_stats(self) -> dict[str, Any]:
        """獲取統計信息"""
        return {
            "l1": self.l1_backend.stats.__dict__,
            "l2": self.l2_backend.stats.__dict__,
        }

    async def get_detailed_stats(self) -> dict[str, Any]:
        """獲取詳細統計信息"""
        l1_stats = await self.l1_backend.get_detailed_stats()
        l2_stats = self.l2_backend.stats.__dict__

        return {
            "l1": l1_stats,
            "l2": l2_stats,
            "combined": {
                "total_hits": l1_stats["hits"] + l2_stats["hits"],
                "total_misses": l1_stats["misses"] + l2_stats["misses"],
                "combined_hit_rate": (l1_stats["hits"] + l2_stats["hits"])
                / (
                    l1_stats["hits"]
                    + l1_stats["misses"]
                    + l2_stats["hits"]
                    + l2_stats["misses"]
                )
                if (
                    l1_stats["hits"]
                    + l1_stats["misses"]
                    + l2_stats["hits"]
                    + l2_stats["misses"]
                )
                > 0
                else 0,
                "total_entries": l1_stats["entry_count"] + l2_stats["entry_count"],
            },
        }

    def register_preload_function(self, pattern: str, func: Callable):
        """註冊預載入函數"""
        if self.preloader:
            self.preloader.register_preload_function(pattern, func)

    @asynccontextmanager
    async def batch_operation(self):
        """批量操作上下文"""
        # 這裡可以實現批量操作優化
        yield

    async def shutdown(self):
        """關閉緩存管理器"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._cleanup_task

        # 清理連接池
        with self.l2_backend._pool_lock:
            for conn in self.l2_backend._connection_pool:
                conn.close()
            self.l2_backend._connection_pool.clear()


# 全域緩存管理器
_global_cache_manager: MultiLevelCache | None = None


async def get_global_cache_manager() -> MultiLevelCache:
    """獲取全域緩存管理器"""
    global _global_cache_manager
    if _global_cache_manager is None:
        _global_cache_manager = MultiLevelCache()
    return _global_cache_manager


async def dispose_global_cache_manager():
    """釋放全域緩存管理器"""
    global _global_cache_manager
    if _global_cache_manager is not None:
        await _global_cache_manager.shutdown()
        _global_cache_manager = None


# 便捷函數
async def cache_get(key: str) -> Any | None:
    """獲取緩存值"""
    cache = await get_global_cache_manager()
    return await cache.get(key)


async def cache_set(key: str, value: Any, ttl: float | None = None) -> bool:
    """設置緩存值"""
    cache = await get_global_cache_manager()
    return await cache.set(key, value, ttl)


async def cache_delete(key: str) -> bool:
    """刪除緩存值"""
    cache = await get_global_cache_manager()
    return await cache.delete(key)


def cache_key(*args, **kwargs) -> str:
    """生成緩存鍵"""
    # 創建一個唯一的緩存鍵
    key_parts = []

    # 添加位置參數
    for arg in args:
        if hasattr(arg, "__dict__"):
            key_parts.append(f"{type(arg).__name__}:{id(arg)}")
        else:
            key_parts.append(str(arg))

    # 添加關鍵字參數
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}:{v}")

    # 生成哈希
    key_string = ":".join(key_parts)
    return hashlib.sha256(key_string.encode()).hexdigest()


def cached(ttl: float | None = None, key_func: Callable | None = None):
    """緩存裝飾器"""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成緩存鍵
            if key_func:
                cache_key_str = key_func(*args, **kwargs)
            else:
                cache_key_str = f"{func.__name__}:{cache_key(*args, **kwargs)}"

            # 嘗試從緩存獲取
            cached_result = await cache_get(cache_key_str)
            if cached_result is not None:
                return cached_result

            # 執行函數並緩存結果
            start_time = time.time()
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time

            # 設置緩存
            await cache_set(cache_key_str, result, ttl)

            # 記錄性能指標
            logger.debug(f"函數 {func.__name__} 執行耗時: {execution_time:.3f}s")

            return result

        return wrapper

    return decorator
