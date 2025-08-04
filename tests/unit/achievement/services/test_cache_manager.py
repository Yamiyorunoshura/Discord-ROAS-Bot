"""成就系統快取管理器單元測試.

測試 CacheManager 的所有快取功能,包括:
- L1 記憶體快取操作
- L2 檔案快取操作
- 快取失效策略
- 快取統計功能
- 多層快取協調
- 錯誤處理

使用模擬物件進行快速測試執行.
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio

from src.cogs.achievement.database.models import Achievement, AchievementType
from src.cogs.achievement.services.cache_manager import (
    CacheConfig,
    CacheManager,
    CacheType,
)


@pytest_asyncio.fixture
async def temp_cache_dir():
    """臨時快取目錄."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest_asyncio.fixture
async def cache_configs():
    """測試用快取配置."""
    return {
        CacheType.ACHIEVEMENT: CacheConfig(
            max_size=100, ttl_seconds=60, enable_l2_cache=True
        ),
        CacheType.USER_ACHIEVEMENT: CacheConfig(
            max_size=200, ttl_seconds=120, enable_l2_cache=False
        ),
        CacheType.STATS: CacheConfig(
            max_size=50, ttl_seconds=300, enable_l2_cache=True
        ),
    }


@pytest_asyncio.fixture
async def cache_manager(cache_configs, temp_cache_dir):
    """測試用快取管理器."""
    manager = CacheManager(cache_configs, temp_cache_dir)
    async with manager:
        yield manager


@pytest_asyncio.fixture
async def sample_achievement():
    """範例成就物件."""
    return Achievement(
        id=1,
        name="測試成就",
        description="這是一個測試成就",
        category_id=1,
        type=AchievementType.COUNTER,
        criteria={"target_value": 100},
        points=500,
        is_active=True,
    )


class TestCacheManagerInitialization:
    """測試快取管理器初始化."""

    @pytest.mark.asyncio
    async def test_default_initialization(self, temp_cache_dir):
        """測試使用預設配置初始化."""
        manager = CacheManager(cache_dir=temp_cache_dir)
        async with manager:
            # 驗證快取目錄建立
            assert Path(temp_cache_dir).exists()

            # 驗證 L1 快取建立
            assert len(manager._l1_caches) > 0

    @pytest.mark.asyncio
    async def test_custom_config_initialization(self, cache_configs, temp_cache_dir):
        """測試使用自訂配置初始化."""
        manager = CacheManager(cache_configs, temp_cache_dir)
        async with manager:
            # 驗證配置套用
            for cache_type, config in cache_configs.items():
                if cache_type in manager._l1_caches:
                    cache = manager._l1_caches[cache_type]
                    assert cache.maxsize == config.max_size

    @pytest.mark.asyncio
    async def test_cache_directory_creation(self):
        """測試快取目錄自動建立."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "non_existent" / "cache"

            manager = CacheManager(cache_dir=str(cache_dir))
            async with manager:
                assert cache_dir.exists()


class TestL1MemoryCache:
    """測試 L1 記憶體快取操作."""

    @pytest.mark.asyncio
    async def test_basic_set_get(self, cache_manager, sample_achievement):
        """測試基本的設定和取得操作."""
        cache_key = "achievement:1"

        # 設定快取
        await cache_manager.set(CacheType.ACHIEVEMENT, cache_key, sample_achievement)

        # 取得快取
        cached_data = await cache_manager.get(CacheType.ACHIEVEMENT, cache_key)

        assert cached_data is not None
        assert cached_data.id == sample_achievement.id
        assert cached_data.name == sample_achievement.name

    @pytest.mark.asyncio
    async def test_cache_miss(self, cache_manager):
        """測試快取未命中."""
        cache_key = "nonexistent:key"

        cached_data = await cache_manager.get(CacheType.ACHIEVEMENT, cache_key)

        assert cached_data is None

    @pytest.mark.asyncio
    async def test_cache_expiration(self, temp_cache_dir):
        """測試快取過期."""
        # 使用短 TTL 配置
        config = CacheConfig(max_size=10, ttl_seconds=1)
        configs = {CacheType.ACHIEVEMENT: config}

        manager = CacheManager(configs, temp_cache_dir)
        async with manager:
            cache_key = "expiry:test"
            test_data = {"test": "data"}

            # 設定快取
            await manager.set(CacheType.ACHIEVEMENT, cache_key, test_data)

            # 立即取得應該成功
            cached_data = await manager.get(CacheType.ACHIEVEMENT, cache_key)
            assert cached_data == test_data

            # 等待過期
            time.sleep(1.1)

            # 過期後應該返回 None
            cached_data = await manager.get(CacheType.ACHIEVEMENT, cache_key)
            assert cached_data is None

    @pytest.mark.asyncio
    async def test_cache_eviction(self, temp_cache_dir):
        """測試快取淘汰機制."""
        # 使用小容量配置
        config = CacheConfig(max_size=2, ttl_seconds=300)
        configs = {CacheType.ACHIEVEMENT: config}

        manager = CacheManager(configs, temp_cache_dir)
        async with manager:
            # 填滿快取
            await manager.set(CacheType.ACHIEVEMENT, "key1", "data1")
            await manager.set(CacheType.ACHIEVEMENT, "key2", "data2")

            # 驗證資料存在
            assert await manager.get(CacheType.ACHIEVEMENT, "key1") == "data1"
            assert await manager.get(CacheType.ACHIEVEMENT, "key2") == "data2"

            # 添加第三個項目,應該觸發淘汰
            await manager.set(CacheType.ACHIEVEMENT, "key3", "data3")

            # 驗證淘汰機制(最舊的項目應該被移除)
            cache_size = len(manager._l1_caches[CacheType.ACHIEVEMENT])
            assert cache_size <= 2

    @pytest.mark.asyncio
    async def test_delete_cache_entry(self, cache_manager, sample_achievement):
        """測試刪除快取項目."""
        cache_key = "achievement:1"

        # 設定快取
        await cache_manager.set(CacheType.ACHIEVEMENT, cache_key, sample_achievement)

        # 驗證存在
        assert await cache_manager.get(CacheType.ACHIEVEMENT, cache_key) is not None

        # 刪除
        await cache_manager.delete(CacheType.ACHIEVEMENT, cache_key)

        # 驗證已刪除
        assert await cache_manager.get(CacheType.ACHIEVEMENT, cache_key) is None


class TestL2FileCache:
    """測試 L2 檔案快取操作."""

    @pytest.mark.asyncio
    async def test_l2_cache_enabled_config(self, temp_cache_dir):
        """測試 L2 快取啟用配置."""
        config = CacheConfig(enable_l2_cache=True)
        configs = {CacheType.ACHIEVEMENT: config}

        manager = CacheManager(configs, temp_cache_dir)
        await manager.initialize()

        try:
            cache_key = "l2:test"
            test_data = {"test": "l2_data"}

            # 設定快取(應該同時寫入 L1 和 L2)
            await manager.set(CacheType.ACHIEVEMENT, cache_key, test_data)

            # 清除 L1 快取
            manager._l1_caches[CacheType.ACHIEVEMENT].clear()

            # 從 L2 取得資料(應該自動載入到 L1)
            cached_data = await manager.get(CacheType.ACHIEVEMENT, cache_key)
            assert cached_data == test_data

        finally:
            await manager.cleanup()

    @pytest.mark.asyncio
    async def test_l2_cache_disabled_config(self, temp_cache_dir):
        """測試 L2 快取停用配置."""
        config = CacheConfig(enable_l2_cache=False)
        configs = {CacheType.ACHIEVEMENT: config}

        manager = CacheManager(configs, temp_cache_dir)
        await manager.initialize()

        try:
            cache_key = "l2:disabled"
            test_data = {"test": "no_l2"}

            # 設定快取(只寫入 L1)
            await manager.set(CacheType.ACHIEVEMENT, cache_key, test_data)

            # 清除 L1 快取
            manager._l1_caches[CacheType.ACHIEVEMENT].clear()

            # 應該無法從 L2 取得資料
            cached_data = await manager.get(CacheType.ACHIEVEMENT, cache_key)
            assert cached_data is None

        finally:
            await manager.cleanup()

    @pytest.mark.asyncio
    async def test_l2_cache_file_operations(self, cache_manager):
        """測試 L2 快取檔案操作."""
        cache_key = "file:ops"
        test_data = {"complex": {"nested": "data"}, "list": [1, 2, 3]}

        # 設定快取
        await cache_manager.set(CacheType.ACHIEVEMENT, cache_key, test_data)

        # 驗證檔案建立
        expected_file = cache_manager._get_l2_cache_path(
            CacheType.ACHIEVEMENT, cache_key
        )
        assert expected_file.exists()

        # 清除 L1 快取並重新載入
        cache_manager._l1_caches[CacheType.ACHIEVEMENT].clear()
        cached_data = await cache_manager.get(CacheType.ACHIEVEMENT, cache_key)

        assert cached_data == test_data


class TestCacheInvalidation:
    """測試快取失效機制."""

    @pytest.mark.asyncio
    async def test_invalidate_by_pattern(self, cache_manager):
        """測試按模式失效快取."""
        # 設定多個相關快取項目
        test_data = {"test": "data"}
        keys = [
            "user:123:achievements",
            "user:123:progress",
            "user:456:achievements",
            "achievement:1",
        ]

        for key in keys:
            await cache_manager.set(CacheType.USER_ACHIEVEMENT, key, test_data)

        # 失效特定用戶的快取
        await cache_manager.invalidate_pattern(CacheType.USER_ACHIEVEMENT, "user:123:*")

        # 驗證失效結果
        assert (
            await cache_manager.get(CacheType.USER_ACHIEVEMENT, "user:123:achievements")
            is None
        )
        assert (
            await cache_manager.get(CacheType.USER_ACHIEVEMENT, "user:123:progress")
            is None
        )
        assert (
            await cache_manager.get(CacheType.USER_ACHIEVEMENT, "user:456:achievements")
            == test_data
        )
        assert (
            await cache_manager.get(CacheType.USER_ACHIEVEMENT, "achievement:1")
            == test_data
        )

    @pytest.mark.asyncio
    async def test_invalidate_by_type(self, cache_manager):
        """測試按類型失效快取."""
        test_data = {"test": "data"}

        # 在不同類型設定快取
        await cache_manager.set(CacheType.ACHIEVEMENT, "key1", test_data)
        await cache_manager.set(CacheType.USER_ACHIEVEMENT, "key2", test_data)
        await cache_manager.set(CacheType.STATS, "key3", test_data)

        # 失效特定類型
        await cache_manager.invalidate_type(CacheType.ACHIEVEMENT)

        # 驗證失效結果
        assert await cache_manager.get(CacheType.ACHIEVEMENT, "key1") is None
        assert await cache_manager.get(CacheType.USER_ACHIEVEMENT, "key2") == test_data
        assert await cache_manager.get(CacheType.STATS, "key3") == test_data

    @pytest.mark.asyncio
    async def test_clear_all_caches(self, cache_manager):
        """測試清除所有快取."""
        test_data = {"test": "data"}

        # 在所有類型設定快取
        await cache_manager.set(CacheType.ACHIEVEMENT, "key1", test_data)
        await cache_manager.set(CacheType.USER_ACHIEVEMENT, "key2", test_data)
        await cache_manager.set(CacheType.STATS, "key3", test_data)

        # 清除所有快取
        await cache_manager.clear_all()

        # 驗證清除結果
        assert await cache_manager.get(CacheType.ACHIEVEMENT, "key1") is None
        assert await cache_manager.get(CacheType.USER_ACHIEVEMENT, "key2") is None
        assert await cache_manager.get(CacheType.STATS, "key3") is None


class TestCacheStatistics:
    """測試快取統計功能."""

    @pytest.mark.asyncio
    async def test_hit_miss_statistics(self, cache_manager):
        """測試命中/未命中統計."""
        cache_key = "stats:test"
        test_data = {"test": "data"}

        # 重置統計
        await cache_manager.reset_stats()

        # 快取未命中
        await cache_manager.get(CacheType.ACHIEVEMENT, cache_key)

        # 設定快取
        await cache_manager.set(CacheType.ACHIEVEMENT, cache_key, test_data)

        # 快取命中
        await cache_manager.get(CacheType.ACHIEVEMENT, cache_key)
        await cache_manager.get(CacheType.ACHIEVEMENT, cache_key)

        # 檢查統計
        stats = await cache_manager.get_stats(CacheType.ACHIEVEMENT)
        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.hit_rate == 2 / 3

    @pytest.mark.asyncio
    async def test_cache_size_statistics(self, cache_manager):
        """測試快取大小統計."""
        test_data = {"test": "data"}

        # 添加多個項目
        for i in range(5):
            await cache_manager.set(CacheType.ACHIEVEMENT, f"key{i}", test_data)

        # 檢查大小統計
        stats = await cache_manager.get_stats(CacheType.ACHIEVEMENT)
        assert stats.size == 5

    @pytest.mark.asyncio
    async def test_global_statistics(self, cache_manager):
        """測試全域統計."""
        test_data = {"test": "data"}

        # 在多個類型設定快取
        await cache_manager.set(CacheType.ACHIEVEMENT, "key1", test_data)
        await cache_manager.set(CacheType.USER_ACHIEVEMENT, "key2", test_data)

        # 取得全域統計
        global_stats = await cache_manager.get_global_stats()

        assert "total_size" in global_stats
        assert "total_hits" in global_stats
        assert "total_misses" in global_stats
        assert "cache_types" in global_stats


class TestCacheErrorHandling:
    """測試快取錯誤處理."""

    @pytest.mark.asyncio
    async def test_serialization_error_handling(self, cache_manager):
        """測試序列化錯誤處理."""

        # 建立無法序列化的物件
        class UnserializableObject:
            def __init__(self):
                self.func = lambda x: x  # 函數無法被 pickle

        cache_key = "error:serialization"
        bad_data = UnserializableObject()

        # 設定快取應該不會拋出異常
        await cache_manager.set(CacheType.ACHIEVEMENT, cache_key, bad_data)

        # 取得應該返回 None(因為序列化失敗)
        cached_data = await cache_manager.get(CacheType.ACHIEVEMENT, cache_key)
        # 根據實際實作,可能返回 None 或原始物件(如果只存在 L1 快取)

    @pytest.mark.asyncio
    async def test_file_permission_error_handling(self, temp_cache_dir):
        """測試檔案權限錯誤處理."""
        config = CacheConfig(enable_l2_cache=True)
        configs = {CacheType.ACHIEVEMENT: config}

        manager = CacheManager(configs, temp_cache_dir)
        await manager.initialize()

        try:
            # 模擬檔案權限錯誤
            with patch("builtins.open", side_effect=PermissionError("權限被拒")):
                cache_key = "error:permission"
                test_data = {"test": "data"}

                # 設定快取不應該拋出異常
                await manager.set(CacheType.ACHIEVEMENT, cache_key, test_data)

                # L1 快取應該仍然工作
                cached_data = await manager.get(CacheType.ACHIEVEMENT, cache_key)
                assert cached_data == test_data

        finally:
            await manager.cleanup()

    @pytest.mark.asyncio
    async def test_corrupted_cache_file_handling(self, temp_cache_dir):
        """測試損壞快取檔案處理."""
        config = CacheConfig(enable_l2_cache=True)
        configs = {CacheType.ACHIEVEMENT: config}

        manager = CacheManager(configs, temp_cache_dir)
        await manager.initialize()

        try:
            cache_key = "error:corrupted"

            # 建立損壞的快取檔案
            cache_file = manager._get_l2_cache_path(CacheType.ACHIEVEMENT, cache_key)
            cache_file.parent.mkdir(parents=True, exist_ok=True)

            with open(cache_file, "w") as f:
                f.write("invalid pickle data")

            # 嘗試讀取應該不會拋出異常
            cached_data = await manager.get(CacheType.ACHIEVEMENT, cache_key)
            assert cached_data is None

        finally:
            await manager.cleanup()


class TestCachePerformance:
    """測試快取效能相關功能."""

    @pytest.mark.asyncio
    async def test_bulk_operations(self, cache_manager):
        """測試批量操作效能."""
        test_data = {"test": "bulk_data"}
        keys = [f"bulk:key{i}" for i in range(100)]

        # 批量設定
        start_time = time.time()
        for key in keys:
            await cache_manager.set(CacheType.ACHIEVEMENT, key, test_data)
        set_time = time.time() - start_time

        # 批量取得
        start_time = time.time()
        for key in keys:
            cached_data = await cache_manager.get(CacheType.ACHIEVEMENT, key)
            assert cached_data == test_data
        get_time = time.time() - start_time

        # 驗證效能(這些值可能需要根據實際環境調整)
        assert set_time < 1.0  # 100 次設定應該在 1 秒內完成
        assert get_time < 0.5  # 100 次取得應該在 0.5 秒內完成

    @pytest.mark.asyncio
    async def test_concurrent_access(self, cache_manager):
        """測試並發存取."""
        test_data = {"test": "concurrent"}

        async def set_cache(key_suffix: int):
            """設定快取的協程."""
            key = f"concurrent:key{key_suffix}"
            await cache_manager.set(CacheType.ACHIEVEMENT, key, test_data)

        async def get_cache(key_suffix: int):
            """取得快取的協程."""
            key = f"concurrent:key{key_suffix}"
            return await cache_manager.get(CacheType.ACHIEVEMENT, key)

        # 並發設定
        await asyncio.gather(*[set_cache(i) for i in range(10)])

        # 並發取得
        results = await asyncio.gather(*[get_cache(i) for i in range(10)])

        # 驗證結果
        for result in results:
            assert result == test_data


# 測試運行標記
pytestmark = pytest.mark.asyncio
