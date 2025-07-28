"""
多級緩存管理系統測試
Discord ADR Bot v1.6 - 緩存架構測試

測試覆蓋:
- 緩存條目和統計
- 內存緩存後端(L1)
- 持久化緩存後端(L2)
- 多級緩存管理器
- 緩存策略和淘汰
- 便利函數和裝飾器

作者:Discord ADR Bot 測試工程師
版本:v1.6
"""

import asyncio
import builtins
import contextlib
import os
import tempfile
import time

import pytest
import pytest_asyncio

from src.core.container import (
    CacheEntry,
    CacheLevel,
    CacheStats,
    CacheStrategy,
    MemoryCacheBackend,
    MultiLevelCache,
    PersistentCacheBackend,
    cache_delete,
    cache_get,
    cache_key,
    cache_set,
    cached,
    dispose_global_cache_manager,
    get_global_cache_manager,
)


class TestCacheEntry:
    """緩存條目測試"""

    def test_cache_entry_creation(self):
        """測試緩存條目創建"""
        entry = CacheEntry(key="test_key", value="test_value", ttl=3600)

        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.ttl == 3600
        assert entry.access_count == 0
        assert entry.size > 0
        assert not entry.is_expired()

    def test_cache_entry_expiry(self):
        """測試緩存條目過期"""
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            ttl=0.1,  # 0.1秒過期
        )

        assert not entry.is_expired()

        time.sleep(0.2)
        assert entry.is_expired()

    def test_cache_entry_touch(self):
        """測試緩存條目訪問更新"""
        entry = CacheEntry(key="test", value="value")

        initial_access = entry.last_access
        initial_count = entry.access_count

        time.sleep(0.01)
        entry.touch()

        assert entry.last_access > initial_access
        assert entry.access_count == initial_count + 1

    def test_cache_entry_size_calculation(self):
        """測試緩存條目大小計算"""
        small_entry = CacheEntry(key="small", value="x")
        large_entry = CacheEntry(key="large", value="x" * 1000)

        assert small_entry.size > 0
        assert large_entry.size > small_entry.size


class TestCacheStats:
    """緩存統計測試"""

    def test_cache_stats_creation(self):
        """測試緩存統計創建"""
        stats = CacheStats()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.hit_rate == 0.0
        assert stats.miss_rate == 1.0

    def test_cache_stats_hit_rate(self):
        """測試緩存命中率計算"""
        stats = CacheStats(hits=7, misses=3)

        assert stats.hit_rate == 0.7
        assert abs(stats.miss_rate - 0.3) < 0.0001  # 使用浮點數比較


class TestMemoryCacheBackend:
    """內存緩存後端測試"""

    @pytest_asyncio.fixture
    async def memory_cache(self):
        """創建內存緩存實例"""
        return MemoryCacheBackend(max_size=3, strategy=CacheStrategy.LRU)

    @pytest.mark.asyncio
    async def test_set_and_get(self, memory_cache):
        """測試設置和獲取"""
        entry = CacheEntry(key="test", value="value")

        # 設置緩存
        result = await memory_cache.set("test", entry)
        assert result is True

        # 獲取緩存
        retrieved = await memory_cache.get("test")
        assert retrieved is not None
        assert retrieved.value == "value"
        assert memory_cache.stats.hits == 1

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, memory_cache):
        """測試獲取不存在的條目"""
        result = await memory_cache.get("nonexistent")

        assert result is None
        assert memory_cache.stats.misses == 1

    @pytest.mark.asyncio
    async def test_delete(self, memory_cache):
        """測試刪除條目"""
        entry = CacheEntry(key="test", value="value")
        await memory_cache.set("test", entry)

        # 刪除條目
        result = await memory_cache.delete("test")
        assert result is True

        # 驗證已刪除
        retrieved = await memory_cache.get("test")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_clear(self, memory_cache):
        """測試清空緩存"""
        entry1 = CacheEntry(key="test1", value="value1")
        entry2 = CacheEntry(key="test2", value="value2")

        await memory_cache.set("test1", entry1)
        await memory_cache.set("test2", entry2)

        # 清空緩存
        result = await memory_cache.clear()
        assert result is True

        # 驗證已清空
        assert await memory_cache.get("test1") is None
        assert await memory_cache.get("test2") is None

    @pytest.mark.asyncio
    async def test_lru_eviction(self, memory_cache):
        """測試LRU淘汰策略"""
        # 填滿緩存
        for i in range(3):
            entry = CacheEntry(key=f"key{i}", value=f"value{i}")
            await memory_cache.set(f"key{i}", entry)

        # 訪問第一個條目,使其成為最近使用
        await memory_cache.get("key0")

        new_entry = CacheEntry(key="new_key", value="new_value")
        await memory_cache.set("new_key", new_entry)

        # 驗證淘汰結果
        assert await memory_cache.get("key0") is not None  # 最近訪問,保留
        assert await memory_cache.get("key1") is None  # 最久未使用,被淘汰
        assert await memory_cache.get("key2") is not None  # 保留
        assert await memory_cache.get("new_key") is not None  # 新條目

    @pytest.mark.asyncio
    async def test_expired_entry(self, memory_cache):
        """測試過期條目處理"""
        entry = CacheEntry(key="test", value="value", ttl=0.1)
        await memory_cache.set("test", entry)

        # 立即獲取應該成功
        result = await memory_cache.get("test")
        assert result is not None

        # 等待過期
        await asyncio.sleep(0.2)

        # 過期後獲取應該返回None
        result = await memory_cache.get("test")
        assert result is None
        assert memory_cache.stats.expired > 0


class TestPersistentCacheBackend:
    """持久化緩存後端測試"""

    @pytest_asyncio.fixture
    async def persistent_cache(self):
        """創建持久化緩存實例"""
        # 使用臨時文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_file.close()

        cache = PersistentCacheBackend(db_path=temp_file.name, max_size=5)
        yield cache

        # 清理
        with contextlib.suppress(builtins.BaseException):
            os.unlink(temp_file.name)

    @pytest.mark.asyncio
    async def test_set_and_get(self, persistent_cache):
        """測試設置和獲取"""
        entry = CacheEntry(key="test", value={"data": "test"})

        # 設置緩存
        result = await persistent_cache.set("test", entry)
        assert result is True

        # 獲取緩存
        retrieved = await persistent_cache.get("test")
        assert retrieved is not None
        assert retrieved.value == {"data": "test"}

    @pytest.mark.asyncio
    async def test_persistence(self, persistent_cache):
        """測試數據持久性"""
        entry = CacheEntry(key="persistent", value="data")
        await persistent_cache.set("persistent", entry)

        new_cache = PersistentCacheBackend(db_path=persistent_cache.db_path, max_size=5)

        # 數據應該仍然存在
        retrieved = await new_cache.get("persistent")
        assert retrieved is not None
        assert retrieved.value == "data"

    @pytest.mark.asyncio
    async def test_delete(self, persistent_cache):
        """測試刪除條目"""
        entry = CacheEntry(key="test", value="value")
        await persistent_cache.set("test", entry)

        # 刪除條目
        result = await persistent_cache.delete("test")
        assert result is True

        # 驗證已刪除
        retrieved = await persistent_cache.get("test")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_clear(self, persistent_cache):
        """測試清空緩存"""
        entry1 = CacheEntry(key="test1", value="value1")
        entry2 = CacheEntry(key="test2", value="value2")

        await persistent_cache.set("test1", entry1)
        await persistent_cache.set("test2", entry2)

        # 清空緩存
        result = await persistent_cache.clear()
        assert result is True

        # 驗證已清空
        assert await persistent_cache.get("test1") is None
        assert await persistent_cache.get("test2") is None

    @pytest.mark.asyncio
    async def test_keys(self, persistent_cache):
        """測試獲取所有鍵"""
        entry1 = CacheEntry(key="key1", value="value1")
        entry2 = CacheEntry(key="key2", value="value2")

        await persistent_cache.set("key1", entry1)
        await persistent_cache.set("key2", entry2)

        keys = await persistent_cache.keys()
        assert set(keys) == {"key1", "key2"}


class TestMultiLevelCache:
    """多級緩存管理器測試"""

    @pytest_asyncio.fixture
    async def multi_cache(self):
        """創建多級緩存實例"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_file.close()

        cache = MultiLevelCache(
            l1_max_size=2, l2_max_size=5, default_ttl=3600, db_path=temp_file.name
        )

        yield cache

        await cache.shutdown()
        with contextlib.suppress(builtins.BaseException):
            os.unlink(temp_file.name)

    @pytest.mark.asyncio
    async def test_set_and_get(self, multi_cache):
        """測試設置和獲取"""
        # 設置緩存
        result = await multi_cache.set("test", "value")
        assert result is True

        # 獲取緩存
        retrieved = await multi_cache.get("test")
        assert retrieved == "value"

    @pytest.mark.asyncio
    async def test_l1_to_l2_promotion(self, multi_cache):
        """測試L1到L2的數據提升"""
        # 在L2設置數據
        await multi_cache.set("test", "value", level=CacheLevel.L2)

        retrieved = await multi_cache.get("test")
        assert retrieved == "value"

        # 驗證L1中現在有這個數據
        l1_entry = await multi_cache.l1_cache.get("test")
        assert l1_entry is not None
        assert l1_entry.value == "value"

    @pytest.mark.asyncio
    async def test_delete_both_levels(self, multi_cache):
        """測試刪除兩級緩存"""
        await multi_cache.set("test", "value")

        # 刪除緩存
        result = await multi_cache.delete("test")
        assert result is True

        # 驗證兩級緩存都已刪除
        assert await multi_cache.get("test") is None
        assert await multi_cache.l1_cache.get("test") is None
        assert await multi_cache.l2_cache.get("test") is None

    @pytest.mark.asyncio
    async def test_clear_both_levels(self, multi_cache):
        """測試清空兩級緩存"""
        await multi_cache.set("test1", "value1")
        await multi_cache.set("test2", "value2")

        # 清空緩存
        result = await multi_cache.clear()
        assert result is True

        # 驗證兩級緩存都已清空
        assert await multi_cache.get("test1") is None
        assert await multi_cache.get("test2") is None

    @pytest.mark.asyncio
    async def test_exists(self, multi_cache):
        """測試檢查鍵是否存在"""
        await multi_cache.set("existing", "value")

        assert await multi_cache.exists("existing") is True
        assert await multi_cache.exists("nonexistent") is False

    @pytest.mark.asyncio
    async def test_expire(self, multi_cache):
        """測試設置過期時間"""
        await multi_cache.set("test", "value")

        # 設置過期時間
        result = await multi_cache.expire("test", 0.1)
        assert result is True

        # 等待過期
        await asyncio.sleep(0.2)

        # 驗證已過期
        assert await multi_cache.get("test") is None

    @pytest.mark.asyncio
    async def test_get_stats(self, multi_cache):
        """測試獲取統計信息"""
        await multi_cache.set("test", "value")
        await multi_cache.get("test")

        stats = multi_cache.get_stats()

        assert "L1" in stats
        assert "L2" in stats
        assert stats["L1"].hits > 0
        assert stats["L2"].sets > 0

    @pytest.mark.asyncio
    async def test_batch_operation(self, multi_cache):
        """測試批量操作"""
        async with multi_cache.batch_operation() as cache:
            await cache.set("batch1", "value1")
            await cache.set("batch2", "value2")

            assert await cache.get("batch1") == "value1"
            assert await cache.get("batch2") == "value2"


class TestConvenienceFunctions:
    """便利函數測試"""

    @pytest_asyncio.fixture(autouse=True)
    async def setup_and_cleanup(self):
        """設置和清理測試環境"""
        # 清理全局緩存管理器
        await dispose_global_cache_manager()

        # 清理可能存在的緩存文件

        cache_files = ["data/cache.db", "cache.db"]
        for cache_file in cache_files:
            try:
                if os.path.exists(cache_file):
                    os.unlink(cache_file)
            except:
                pass

        yield

        # 測試後清理
        await dispose_global_cache_manager()

    @pytest.mark.asyncio
    async def test_cache_key_generation(self):
        """測試緩存鍵生成"""
        key1 = cache_key("func", "arg1", "arg2", param="value")
        key2 = cache_key("func", "arg1", "arg2", param="value")
        key3 = cache_key("func", "arg1", "arg3", param="value")

        assert key1 == key2  # 相同參數應該生成相同鍵
        assert key1 != key3  # 不同參數應該生成不同鍵

    @pytest.mark.asyncio
    async def test_global_cache_functions(self):
        """測試全局緩存函數"""
        # 設置緩存
        result = await cache_set("global_test", "global_value")
        assert result is True

        # 獲取緩存
        retrieved = await cache_get("global_test")
        assert retrieved == "global_value"

        # 刪除緩存
        result = await cache_delete("global_test")
        assert result is True

        # 驗證已刪除
        retrieved = await cache_get("global_test")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_cached_decorator(self):
        """測試緩存裝飾器"""
        call_count = 0

        @cached(ttl=3600)
        async def expensive_function(x, y):
            nonlocal call_count
            call_count += 1
            return x + y

        # 第一次調用
        result1 = await expensive_function(1, 2)
        assert result1 == 3
        assert call_count == 1

        result2 = await expensive_function(1, 2)
        assert result2 == 3
        assert call_count == 1  # 沒有再次調用函數

        # 不同參數的調用
        result3 = await expensive_function(2, 3)
        assert result3 == 5
        assert call_count == 2  # 調用了函數

    @pytest.mark.asyncio
    async def test_cached_decorator_with_custom_key(self):
        """測試帶自定義鍵的緩存裝飾器"""
        call_count = 0

        def custom_key_func(x, y):
            return f"custom:{x}:{y}"

        @cached(ttl=3600, key_func=custom_key_func)
        async def function_with_custom_key(x, y):
            nonlocal call_count
            call_count += 1
            return x * y

        # 調用函數
        result = await function_with_custom_key(3, 4)
        assert result == 12
        assert call_count == 1

        # 驗證使用了自定義鍵
        cached_value = await cache_get("custom:3:4")
        assert cached_value == 12


class TestGlobalCacheManager:
    """全局緩存管理器測試"""

    @pytest.mark.asyncio
    async def test_get_global_cache_manager(self):
        """測試獲取全局緩存管理器"""
        manager1 = await get_global_cache_manager()
        manager2 = await get_global_cache_manager()

        # 應該返回同一個實例
        assert manager1 is manager2

    @pytest.mark.asyncio
    async def test_global_cache_isolation(self):
        """測試全局緩存隔離"""
        # 使用全局緩存
        await cache_set("global_isolation_test", "global_value")

        # 創建獨立的緩存實例
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_file.close()

        independent_cache = MultiLevelCache(db_path=temp_file.name)

        try:
            # 獨立緩存不應該有全局緩存的數據
            result = await independent_cache.get("global_isolation_test")
            assert result is None

            # 設置獨立緩存的數據
            await independent_cache.set("independent_test", "independent_value")

            # 全局緩存不應該有獨立緩存的數據
            global_result = await cache_get("independent_test")
            assert global_result is None

        finally:
            await independent_cache.shutdown()
            with contextlib.suppress(builtins.BaseException):
                os.unlink(temp_file.name)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
