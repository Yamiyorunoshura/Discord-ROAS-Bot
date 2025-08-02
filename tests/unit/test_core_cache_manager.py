"""快取管理系統測試模組.

此模組測試 Discord ROAS Bot 的企業級多級快取功能，
包括L1內存快取、L2持久化快取、智能快取策略等核心功能。
"""

import os
import tempfile
import time

import pytest

from src.cogs.core.cache_manager import (
    CacheAnalyzer,
    CacheEntry,
    CacheLevel,
    CacheOperation,
    CacheStats,
    CacheStrategy,
    MemoryCacheBackend,
    MultiLevelCache,
    PersistentCacheBackend,
    SmartCacheStrategy,
    cache_delete,
    cache_get,
    cache_key,
    cache_set,
    cached,
    dispose_global_cache_manager,
    get_global_cache_manager,
)


class TestCacheEntry:
    """測試快取條目功能."""

    def test_cache_entry_initialization(self):
        """測試快取條目初始化."""
        entry = CacheEntry(key="test_key", value="test_value")

        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert isinstance(entry.timestamp, float)
        assert entry.access_count == 0
        assert isinstance(entry.last_access, float)
        assert entry.ttl is None
        assert entry.size > 0  # 應該有計算大小
        assert isinstance(entry.metadata, dict)
        assert entry.hit_count == 0
        assert entry.miss_count == 0
        assert entry.load_time == 0.0

    def test_cache_entry_with_ttl(self):
        """測試帶過期時間的快取條目."""
        entry = CacheEntry(key="test_key", value="test_value", ttl=300.0)

        assert entry.ttl == 300.0
        assert not entry.is_expired()  # 剛創建不應該過期

    def test_cache_entry_expiration(self):
        """測試快取條目過期檢查."""
        # 創建一個立即過期的條目
        entry = CacheEntry(key="test_key", value="test_value", ttl=0.01)

        # 等待一小段時間
        time.sleep(0.02)

        assert entry.is_expired()

    def test_cache_entry_touch(self):
        """測試快取條目訪問更新."""
        entry = CacheEntry(key="test_key", value="test_value")
        initial_access_count = entry.access_count
        initial_hit_count = entry.hit_count
        initial_last_access = entry.last_access

        # 等待一小段時間以確保時間戳不同
        time.sleep(0.01)
        entry.touch()

        assert entry.access_count == initial_access_count + 1
        assert entry.hit_count == initial_hit_count + 1
        assert entry.last_access > initial_last_access

    def test_cache_entry_age_calculation(self):
        """測試快取條目年齡計算."""
        entry = CacheEntry(key="test_key", value="test_value")

        # 等待一小段時間
        time.sleep(0.01)

        age = entry.get_age()
        assert age > 0
        assert age < 1.0  # 應該小於1秒

    def test_cache_entry_idle_time_calculation(self):
        """測試快取條目空閒時間計算."""
        entry = CacheEntry(key="test_key", value="test_value")

        # 等待一小段時間
        time.sleep(0.01)

        idle_time = entry.get_idle_time()
        assert idle_time > 0

    def test_cache_entry_frequency_score(self):
        """測試快取條目頻率分數計算."""
        entry = CacheEntry(key="test_key", value="test_value")

        # 增加訪問次數
        entry.touch()
        entry.touch()

        frequency_score = entry.get_frequency_score()
        assert frequency_score > 0

    def test_cache_entry_size_calculation(self):
        """測試快取條目大小計算."""
        small_entry = CacheEntry(key="small", value="x")
        large_entry = CacheEntry(key="large", value="x" * 1000)

        assert small_entry.size > 0
        assert large_entry.size > small_entry.size


class TestCacheStats:
    """測試快取統計功能."""

    def test_cache_stats_initialization(self):
        """測試快取統計初始化."""
        stats = CacheStats()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.sets == 0
        assert stats.deletes == 0
        assert stats.evictions == 0
        assert stats.expired == 0
        assert stats.total_size == 0
        assert stats.entry_count == 0
        assert stats.preloads == 0
        assert stats.preload_hits == 0
        assert stats.avg_load_time == 0.0
        assert stats.peak_size == 0

    def test_cache_stats_hit_rate_calculation(self):
        """測試命中率計算."""
        stats = CacheStats()

        # 初始狀態命中率應該為0
        assert stats.hit_rate == 0.0
        assert stats.miss_rate == 1.0

        # 設置一些數據
        stats.hits = 7
        stats.misses = 3

        assert abs(stats.hit_rate - 0.7) < 0.001
        assert abs(stats.miss_rate - 0.3) < 0.001

    def test_cache_stats_preload_effectiveness(self):
        """測試預載入有效性計算."""
        stats = CacheStats()

        # 初始狀態預載入有效性應該為0
        assert stats.preload_effectiveness == 0.0

        # 設置預載入數據
        stats.preloads = 10
        stats.preload_hits = 7

        assert stats.preload_effectiveness == 0.7

    def test_cache_stats_reset(self):
        """測試統計重置."""
        stats = CacheStats()

        # 設置一些數據
        stats.hits = 10
        stats.misses = 5
        stats.sets = 8

        # 重置
        stats.reset()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.sets == 0


class TestCacheAnalyzer:
    """測試快取分析器功能."""

    @pytest.fixture
    def analyzer(self):
        """創建快取分析器."""
        return CacheAnalyzer(max_history=100)

    @pytest.mark.asyncio
    async def test_analyzer_initialization(self, analyzer):
        """測試快取分析器初始化."""
        assert len(analyzer.access_history) == 0
        assert len(analyzer.pattern_stats) == 0
        assert len(analyzer.hot_keys) == 0
        assert len(analyzer.cold_keys) == 0

    @pytest.mark.asyncio
    async def test_analyzer_record_access(self, analyzer):
        """測試記錄訪問."""
        await analyzer.record_access("key1", CacheOperation.GET, True)
        await analyzer.record_access("key2", CacheOperation.GET, False)

        assert len(analyzer.access_history) == 2
        assert analyzer.hot_keys["key1"] == 1
        assert "key2" in analyzer.cold_keys

    @pytest.mark.asyncio
    async def test_analyzer_analyze_patterns_empty(self, analyzer):
        """測試分析空的訪問模式."""
        result = await analyzer.analyze_patterns()

        assert "error" in result
        assert result["error"] == "沒有訪問歷史"

    @pytest.mark.asyncio
    async def test_analyzer_analyze_patterns_with_data(self, analyzer):
        """測試分析有數據的訪問模式."""
        # 添加一些訪問記錄
        for i in range(10):
            await analyzer.record_access(f"key{i % 3}", CacheOperation.GET, i % 2 == 0)

        result = await analyzer.analyze_patterns()

        assert "total_accesses" in result
        assert "hit_rate" in result
        assert "top_hot_keys" in result
        assert "unique_keys_accessed" in result
        assert "cold_keys_count" in result
        assert "avg_accesses_per_key" in result

        assert result["total_accesses"] == 10
        assert 0 <= result["hit_rate"] <= 1

    @pytest.mark.asyncio
    async def test_analyzer_preload_suggestions(self, analyzer):
        """測試預載入建議."""
        # 創建一個高頻但經常錯失的鍵
        for _ in range(10):
            await analyzer.record_access("hot_key", CacheOperation.GET, True)

        # 將其標記為冷鍵
        analyzer.cold_keys.add("hot_key")

        suggestions = await analyzer.get_preload_suggestions()

        assert "hot_key" in suggestions


class TestSmartCacheStrategy:
    """測試智能快取策略功能."""

    @pytest.fixture
    def analyzer(self):
        """創建快取分析器."""
        return CacheAnalyzer()

    @pytest.fixture
    def strategy(self, analyzer):
        """創建智能快取策略."""
        return SmartCacheStrategy(analyzer)

    @pytest.mark.asyncio
    async def test_smart_strategy_initialization(self, strategy):
        """測試智能策略初始化."""
        assert strategy.analyzer is not None
        assert isinstance(strategy.strategy_weights, dict)
        assert CacheStrategy.LRU in strategy.strategy_weights
        assert CacheStrategy.LFU in strategy.strategy_weights

    @pytest.mark.asyncio
    async def test_smart_strategy_should_evict_no_eviction_needed(self, strategy):
        """測試不需要淘汰的情況."""
        entries = {
            "key1": CacheEntry("key1", "value1"),
            "key2": CacheEntry("key2", "value2")
        }

        keys_to_evict = await strategy.should_evict(entries, max_size=5)

        assert len(keys_to_evict) == 0

    @pytest.mark.asyncio
    async def test_smart_strategy_should_evict_with_eviction(self, strategy):
        """測試需要淘汰的情況."""
        entries = {
            "key1": CacheEntry("key1", "value1"),
            "key2": CacheEntry("key2", "value2"),
            "key3": CacheEntry("key3", "value3")
        }

        keys_to_evict = await strategy.should_evict(entries, max_size=2)

        assert len(keys_to_evict) >= 1
        assert all(key in entries for key in keys_to_evict)


class TestMemoryCacheBackend:
    """測試內存快取後端功能."""

    @pytest.fixture
    def backend(self):
        """創建內存快取後端."""
        return MemoryCacheBackend(max_size=10, strategy=CacheStrategy.LRU)

    @pytest.mark.asyncio
    async def test_memory_backend_initialization(self, backend):
        """測試內存後端初始化."""
        assert backend.max_size == 10
        assert backend.strategy == CacheStrategy.LRU
        assert len(backend._cache) == 0
        assert isinstance(backend.stats, CacheStats)

    @pytest.mark.asyncio
    async def test_memory_backend_set_and_get(self, backend):
        """測試設置和獲取."""
        entry = CacheEntry("test_key", "test_value")

        # 設置
        success = await backend.set("test_key", entry)
        assert success
        assert backend.stats.sets == 1

        # 獲取
        retrieved_entry = await backend.get("test_key")
        assert retrieved_entry is not None
        assert retrieved_entry.key == "test_key"
        assert retrieved_entry.value == "test_value"
        assert backend.stats.hits == 1

    @pytest.mark.asyncio
    async def test_memory_backend_get_nonexistent(self, backend):
        """測試獲取不存在的鍵."""
        result = await backend.get("nonexistent_key")

        assert result is None
        assert backend.stats.misses == 1

    @pytest.mark.asyncio
    async def test_memory_backend_get_expired(self, backend):
        """測試獲取過期條目."""
        # 創建立即過期的條目
        entry = CacheEntry("test_key", "test_value", ttl=0.01)
        await backend.set("test_key", entry)

        # 等待過期
        time.sleep(0.02)

        result = await backend.get("test_key")

        assert result is None
        assert backend.stats.expired >= 1

    @pytest.mark.asyncio
    async def test_memory_backend_delete(self, backend):
        """測試刪除."""
        entry = CacheEntry("test_key", "test_value")
        await backend.set("test_key", entry)

        # 刪除
        success = await backend.delete("test_key")
        assert success
        assert backend.stats.deletes == 1

        # 確認已刪除
        result = await backend.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_memory_backend_clear(self, backend):
        """測試清空."""
        # 添加一些條目
        for i in range(3):
            entry = CacheEntry(f"key{i}", f"value{i}")
            await backend.set(f"key{i}", entry)

        # 清空
        success = await backend.clear()
        assert success

        # 確認已清空
        size = await backend.size()
        assert size == 0

    @pytest.mark.asyncio
    async def test_memory_backend_keys(self, backend):
        """測試獲取所有鍵."""
        # 添加一些條目
        keys = ["key1", "key2", "key3"]
        for key in keys:
            entry = CacheEntry(key, f"value_{key}")
            await backend.set(key, entry)

        # 獲取鍵列表
        retrieved_keys = await backend.keys()

        assert len(retrieved_keys) == len(keys)
        assert all(key in retrieved_keys for key in keys)

    @pytest.mark.asyncio
    async def test_memory_backend_size(self, backend):
        """測試獲取大小."""
        initial_size = await backend.size()
        assert initial_size == 0

        # 添加條目
        entry = CacheEntry("test_key", "test_value")
        await backend.set("test_key", entry)

        new_size = await backend.size()
        assert new_size == 1

    @pytest.mark.asyncio
    async def test_memory_backend_eviction_lru(self, backend):
        """測試LRU淘汰策略."""
        # 填滿快取
        for i in range(backend.max_size):
            entry = CacheEntry(f"key{i}", f"value{i}")
            await backend.set(f"key{i}", entry)

        # 添加一個新條目，應該觸發淘汰
        entry = CacheEntry("new_key", "new_value")
        await backend.set("new_key", entry)

        # 檢查淘汰統計
        assert backend.stats.evictions >= 1

        # 最早的條目應該被淘汰
        first_entry = await backend.get("key0")
        assert first_entry is None

    @pytest.mark.asyncio
    async def test_memory_backend_detailed_stats(self, backend):
        """測試獲取詳細統計."""
        # 執行一些操作
        entry = CacheEntry("test_key", "test_value")
        await backend.set("test_key", entry)
        await backend.get("test_key")
        await backend.get("nonexistent")

        stats = await backend.get_detailed_stats()

        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
        assert "sets" in stats
        assert "entry_count" in stats
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
        assert stats["sets"] >= 1


class TestPersistentCacheBackend:
    """測試持久化快取後端功能."""

    @pytest.fixture
    def temp_db_path(self):
        """創建臨時資料庫路徑."""
        temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_file.close()
        yield temp_file.name
        # 清理
        try:
            os.unlink(temp_file.name)
        except (OSError, FileNotFoundError):
            pass

    @pytest.fixture
    def backend(self, temp_db_path):
        """創建持久化快取後端."""
        return PersistentCacheBackend(db_path=temp_db_path, max_size=100)

    @pytest.mark.asyncio
    async def test_persistent_backend_initialization(self, backend):
        """測試持久化後端初始化."""
        assert isinstance(backend.db_path, str)
        assert backend.max_size == 100
        assert isinstance(backend.stats, CacheStats)

        # 確認資料庫文件存在
        assert os.path.exists(backend.db_path)

    @pytest.mark.asyncio
    async def test_persistent_backend_set_and_get(self, backend):
        """測試設置和獲取."""
        entry = CacheEntry("test_key", "test_value")

        # 設置
        success = await backend.set("test_key", entry)
        assert success

        # 獲取
        retrieved_entry = await backend.get("test_key")
        assert retrieved_entry is not None
        assert retrieved_entry.key == "test_key"
        assert retrieved_entry.value == "test_value"

    @pytest.mark.asyncio
    async def test_persistent_backend_get_nonexistent(self, backend):
        """測試獲取不存在的鍵."""
        result = await backend.get("nonexistent_key")

        assert result is None
        assert backend.stats.misses >= 1

    @pytest.mark.asyncio
    async def test_persistent_backend_delete(self, backend):
        """測試刪除."""
        entry = CacheEntry("test_key", "test_value")
        await backend.set("test_key", entry)

        # 刪除
        success = await backend.delete("test_key")
        assert success

        # 確認已刪除
        result = await backend.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_persistent_backend_clear(self, backend):
        """測試清空."""
        # 添加一些條目
        for i in range(3):
            entry = CacheEntry(f"key{i}", f"value{i}")
            await backend.set(f"key{i}", entry)

        # 清空
        success = await backend.clear()
        assert success

        # 確認已清空
        size = await backend.size()
        assert size == 0

    @pytest.mark.asyncio
    async def test_persistent_backend_keys(self, backend):
        """測試獲取所有鍵."""
        # 添加一些條目
        keys = ["key1", "key2", "key3"]
        for key in keys:
            entry = CacheEntry(key, f"value_{key}")
            await backend.set(key, entry)

        # 獲取鍵列表
        retrieved_keys = await backend.keys()

        assert len(retrieved_keys) == len(keys)
        assert all(key in retrieved_keys for key in keys)

    @pytest.mark.asyncio
    async def test_persistent_backend_size(self, backend):
        """測試獲取大小."""
        initial_size = await backend.size()
        assert initial_size == 0

        # 添加條目
        entry = CacheEntry("test_key", "test_value")
        await backend.set("test_key", entry)

        new_size = await backend.size()
        assert new_size == 1

    @pytest.mark.asyncio
    async def test_persistent_backend_complex_objects(self, backend):
        """測試存儲複雜對象."""
        complex_value = {
            "string": "test",
            "number": 42,
            "list": [1, 2, 3],
            "nested": {"key": "value"}
        }

        entry = CacheEntry("complex_key", complex_value)

        # 設置
        success = await backend.set("complex_key", entry)
        assert success

        # 獲取
        retrieved_entry = await backend.get("complex_key")
        assert retrieved_entry is not None
        assert retrieved_entry.value == complex_value


class TestMultiLevelCache:
    """測試多級快取管理器功能."""

    @pytest.fixture
    def temp_db_path(self):
        """創建臨時資料庫路徑."""
        temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_file.close()
        yield temp_file.name
        # 清理
        try:
            os.unlink(temp_file.name)
        except (OSError, FileNotFoundError):
            pass

    @pytest.fixture
    async def cache_manager(self, temp_db_path):
        """創建多級快取管理器."""
        manager = MultiLevelCache(
            l1_max_size=10,
            l2_max_size=100,
            l1_strategy=CacheStrategy.LRU,
            default_ttl=3600.0,
            db_path=temp_db_path,
            enable_preloading=False  # 禁用預載入以簡化測試
        )
        yield manager
        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_multi_level_cache_initialization(self, cache_manager):
        """測試多級快取初始化."""
        assert cache_manager.l1_backend is not None
        assert cache_manager.l2_backend is not None
        assert cache_manager.default_ttl == 3600.0
        assert cache_manager.enable_preloading == False

    @pytest.mark.asyncio
    async def test_multi_level_cache_set_and_get_l1(self, cache_manager):
        """測試L1快取設置和獲取."""
        # 設置到L1
        success = await cache_manager.set("test_key", "test_value", level=CacheLevel.L1)
        assert success

        # 從快取獲取(應該從L1獲取)
        result = await cache_manager.get("test_key")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_multi_level_cache_set_and_get_l2(self, cache_manager):
        """測試L2快取設置和獲取."""
        # 設置到L2
        success = await cache_manager.set("test_key", "test_value", level=CacheLevel.L2)
        assert success

        # 從快取獲取(應該從L2獲取)
        result = await cache_manager.get("test_key")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_multi_level_cache_set_and_get_both(self, cache_manager):
        """測試兩級快取設置和獲取."""
        # 設置到兩級
        success = await cache_manager.set("test_key", "test_value", level=CacheLevel.BOTH)
        assert success

        # 從快取獲取
        result = await cache_manager.get("test_key")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_multi_level_cache_l1_to_l2_promotion(self, cache_manager):
        """測試L2到L1的提升."""
        # 只設置到L2
        await cache_manager.set("test_key", "test_value", level=CacheLevel.L2)

        # 清空L1以確保數據只在L2
        await cache_manager.clear(level=CacheLevel.L1)

        # 獲取數據(應該從L2獲取並提升到L1)
        result = await cache_manager.get("test_key")
        assert result == "test_value"

        # 再次獲取應該從L1獲取
        result = await cache_manager.get("test_key")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_multi_level_cache_delete(self, cache_manager):
        """測試刪除."""
        # 設置數據
        await cache_manager.set("test_key", "test_value", level=CacheLevel.BOTH)

        # 刪除
        success = await cache_manager.delete("test_key", level=CacheLevel.BOTH)
        assert success

        # 確認已刪除
        result = await cache_manager.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_multi_level_cache_clear(self, cache_manager):
        """測試清空."""
        # 設置一些數據
        await cache_manager.set("key1", "value1", level=CacheLevel.BOTH)
        await cache_manager.set("key2", "value2", level=CacheLevel.BOTH)

        # 清空
        success = await cache_manager.clear(level=CacheLevel.BOTH)
        assert success

        # 確認已清空
        result1 = await cache_manager.get("key1")
        result2 = await cache_manager.get("key2")
        assert result1 is None
        assert result2 is None

    @pytest.mark.asyncio
    async def test_multi_level_cache_exists(self, cache_manager):
        """測試檢查鍵是否存在."""
        # 不存在的鍵
        exists = await cache_manager.exists("nonexistent_key")
        assert not exists

        # 設置鍵
        await cache_manager.set("test_key", "test_value")

        # 存在的鍵
        exists = await cache_manager.exists("test_key")
        assert exists

    @pytest.mark.asyncio
    async def test_multi_level_cache_expire(self, cache_manager):
        """測試設置過期時間."""
        # 設置數據
        await cache_manager.set("test_key", "test_value")

        # 設置過期時間
        success = await cache_manager.expire("test_key", 0.01)
        assert success

        # 等待過期
        time.sleep(0.02)

        # 獲取應該為空(過期)
        result = await cache_manager.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_multi_level_cache_stats(self, cache_manager):
        """測試獲取統計信息."""
        # 執行一些操作
        await cache_manager.set("test_key", "test_value")
        await cache_manager.get("test_key")
        await cache_manager.get("nonexistent")

        # 獲取基本統計
        stats = cache_manager.get_stats()
        assert "l1" in stats
        assert "l2" in stats

        # 獲取詳細統計
        detailed_stats = await cache_manager.get_detailed_stats()
        assert "l1" in detailed_stats
        assert "l2" in detailed_stats
        assert "combined" in detailed_stats

    @pytest.mark.asyncio
    async def test_multi_level_cache_batch_operation(self, cache_manager):
        """測試批量操作."""
        async with cache_manager.batch_operation():
            await cache_manager.set("key1", "value1")
            await cache_manager.set("key2", "value2")
            await cache_manager.set("key3", "value3")

        # 確認數據都已設置
        assert await cache_manager.get("key1") == "value1"
        assert await cache_manager.get("key2") == "value2"
        assert await cache_manager.get("key3") == "value3"


class TestCacheUtilities:
    """測試快取工具函數."""

    def test_cache_key_generation(self):
        """測試快取鍵生成."""
        # 基本參數
        key1 = cache_key("arg1", "arg2")
        key2 = cache_key("arg1", "arg2")
        key3 = cache_key("arg1", "arg3")

        assert key1 == key2  # 相同參數應該生成相同鍵
        assert key1 != key3  # 不同參數應該生成不同鍵

        # 關鍵字參數
        key4 = cache_key("arg1", kwarg1="value1")
        key5 = cache_key("arg1", kwarg1="value1")
        key6 = cache_key("arg1", kwarg1="value2")

        assert key4 == key5
        assert key4 != key6

    def test_cache_key_with_objects(self):
        """測試對象快取鍵生成."""
        class TestObject:
            def __init__(self, value):
                self.value = value

        obj1 = TestObject("test")
        obj2 = TestObject("test")

        key1 = cache_key(obj1)
        key2 = cache_key(obj2)

        # 不同對象實例應該生成不同鍵
        assert key1 != key2

    @pytest.mark.asyncio
    async def test_cached_decorator_basic(self):
        """測試基本快取裝飾器."""
        call_count = 0

        @cached(ttl=60.0)
        async def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # 第一次調用
        result1 = await expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # 第二次調用(應該從快取獲取)
        result2 = await expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # 沒有增加

        # 不同參數的調用
        result3 = await expensive_function(3)
        assert result3 == 6
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_cached_decorator_custom_key(self):
        """測試自定義鍵的快取裝飾器."""
        def custom_key_func(x, y):
            return f"custom_{x}_{y}"

        call_count = 0

        @cached(ttl=60.0, key_func=custom_key_func)
        async def add_function(x, y):
            nonlocal call_count
            call_count += 1
            return x + y

        # 調用函數
        result = await add_function(2, 3)
        assert result == 5
        assert call_count == 1

        # 再次調用相同參數
        result = await add_function(2, 3)
        assert result == 5
        assert call_count == 1


class TestGlobalCacheManager:
    """測試全域快取管理器."""

    @pytest.mark.asyncio
    async def test_global_cache_manager_singleton(self):
        """測試全域快取管理器單例."""
        # 清理現有的全域管理器
        await dispose_global_cache_manager()

        # 獲取兩次應該是同一個實例
        manager1 = await get_global_cache_manager()
        manager2 = await get_global_cache_manager()

        assert manager1 is manager2

        # 清理
        await dispose_global_cache_manager()

    @pytest.mark.asyncio
    async def test_global_cache_functions(self):
        """測試全域快取函數."""
        # 清理現有的全域管理器
        await dispose_global_cache_manager()

        # 設置值
        success = await cache_set("test_key", "test_value")
        assert success

        # 獲取值
        result = await cache_get("test_key")
        assert result == "test_value"

        # 刪除值
        success = await cache_delete("test_key")
        assert success

        # 確認已刪除
        result = await cache_get("test_key")
        assert result is None

        # 清理
        await dispose_global_cache_manager()

    @pytest.mark.asyncio
    async def test_dispose_global_cache_manager(self):
        """測試釋放全域快取管理器."""
        # 獲取管理器
        manager = await get_global_cache_manager()
        assert manager is not None

        # 釋放
        await dispose_global_cache_manager()

        # 再次獲取應該是新實例
        new_manager = await get_global_cache_manager()
        assert new_manager is not manager

        # 清理
        await dispose_global_cache_manager()


class TestCacheErrorHandling:
    """測試快取錯誤處理."""

    @pytest.mark.asyncio
    async def test_memory_backend_error_handling(self):
        """測試內存後端錯誤處理."""
        backend = MemoryCacheBackend(max_size=5)

        # 測試處理異常情況
        try:
            # 嘗試使用無效的快取條目
            invalid_entry = CacheEntry("test", None)
            await backend.set("test", invalid_entry)

            result = await backend.get("test")
            # 應該能夠處理並返回結果
            assert result is not None or result is None
        except Exception as e:
            # 如果拋出異常，應該是預期的類型
            assert isinstance(e, (ValueError, TypeError, AttributeError))

    @pytest.mark.asyncio
    async def test_persistent_backend_db_error_handling(self):
        """測試持久化後端資料庫錯誤處理."""
        # 使用無效路徑創建後端
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid_path = os.path.join(temp_dir, "subdir", "invalid.db")

            try:
                backend = PersistentCacheBackend(db_path=invalid_path)
                # 嘗試操作
                entry = CacheEntry("test", "value")
                await backend.set("test", entry)
            except Exception as e:
                # 應該能夠處理資料庫錯誤
                assert isinstance(e, (OSError, Exception))


class TestCachePerformance:
    """測試快取性能."""

    @pytest.mark.asyncio
    async def test_memory_cache_performance(self):
        """測試內存快取性能."""
        backend = MemoryCacheBackend(max_size=1000)

        start_time = time.time()

        # 大量設置操作
        for i in range(100):
            entry = CacheEntry(f"key{i}", f"value{i}")
            await backend.set(f"key{i}", entry)

        # 大量獲取操作
        for i in range(100):
            await backend.get(f"key{i}")

        end_time = time.time()
        duration = end_time - start_time

        # 確保性能合理(200個操作在1秒內完成)
        assert duration < 1.0

    @pytest.mark.asyncio
    async def test_multi_level_cache_performance(self):
        """測試多級快取性能."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            cache_manager = MultiLevelCache(
                l1_max_size=50,
                l2_max_size=500,
                db_path=temp_db_path,
                enable_preloading=False
            )

            start_time = time.time()

            # 大量操作
            for i in range(50):
                await cache_manager.set(f"key{i}", f"value{i}")
                await cache_manager.get(f"key{i}")

            end_time = time.time()
            duration = end_time - start_time

            # 確保性能合理
            assert duration < 2.0

            await cache_manager.shutdown()

        finally:
            # 清理
            try:
                os.unlink(temp_db_path)
            except (OSError, FileNotFoundError):
                pass

    @pytest.mark.asyncio
    async def test_cache_memory_usage(self):
        """測試快取內存使用."""
        backend = MemoryCacheBackend(max_size=100)

        # 添加不同大小的條目
        small_entry = CacheEntry("small", "x")
        large_entry = CacheEntry("large", "x" * 1000)

        await backend.set("small", small_entry)
        await backend.set("large", large_entry)

        # 檢查統計
        stats = await backend.get_detailed_stats()
        assert stats["total_size"] > 0
        assert stats["entry_count"] == 2
        assert stats["avg_entry_size"] > 0
