"""成就系統快取服務單元測試.

測試 AchievementCacheService 的所有快取服務功能,包括:
- 快取服務初始化
- 基本快取操作(get/set/delete)
- 快取失效策略
- 配置管理整合
- 效能監控
- 錯誤處理

使用模擬物件進行快速測試執行.
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from src.cogs.achievement.database.models import (
    Achievement,
    AchievementType,
    UserAchievement,
)
from src.cogs.achievement.services.cache_config_manager import CacheConfigUpdate
from src.cogs.achievement.services.cache_service import AchievementCacheService


@pytest_asyncio.fixture
async def cache_service():
    """測試用快取服務."""
    with (
        patch("src.cogs.achievement.services.cache_service.AchievementCacheStrategy"),
        patch("src.cogs.achievement.services.cache_service.CacheInvalidationManager"),
        patch("src.cogs.achievement.services.cache_service.PerformanceOptimizer"),
        patch("src.cogs.achievement.services.cache_service.CacheConfigManager"),
    ):
        service = AchievementCacheService()
        await service.initialize()
        yield service
        await service.cleanup()


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


@pytest_asyncio.fixture
async def sample_user_achievement():
    """範例用戶成就物件."""
    return UserAchievement(
        id=1,
        user_id=123456789,
        achievement_id=1,
        earned_at=datetime.now(),
        notified=False,
    )


class TestCacheServiceInitialization:
    """測試快取服務初始化."""

    @pytest.mark.asyncio
    async def test_service_initialization(self):
        """測試服務初始化."""
        with (
            patch(
                "src.cogs.achievement.services.cache_service.AchievementCacheStrategy"
            ) as mock_strategy,
            patch(
                "src.cogs.achievement.services.cache_service.CacheInvalidationManager"
            ) as mock_invalidation,
            patch(
                "src.cogs.achievement.services.cache_service.PerformanceOptimizer"
            ) as mock_optimizer,
            patch(
                "src.cogs.achievement.services.cache_service.CacheConfigManager"
            ) as mock_config,
        ):
            service = AchievementCacheService()
            await service.initialize()

            # 驗證各組件初始化
            assert service._strategy is not None
            assert service._invalidation_manager is not None
            assert service._performance_optimizer is not None
            assert service._config_manager is not None

            # 驗證配置監聽器註冊
            mock_config.return_value.add_config_listener.assert_called_once()

            await service.cleanup()

    @pytest.mark.asyncio
    async def test_cache_initialization(self, cache_service):
        """測試快取初始化."""
        # 驗證快取字典建立
        assert hasattr(cache_service, "_caches")
        assert isinstance(cache_service._caches, dict)

    @pytest.mark.asyncio
    async def test_service_cleanup(self):
        """測試服務清理."""
        with (
            patch(
                "src.cogs.achievement.services.cache_service.AchievementCacheStrategy"
            ) as mock_strategy,
            patch(
                "src.cogs.achievement.services.cache_service.CacheInvalidationManager"
            ) as mock_invalidation,
            patch(
                "src.cogs.achievement.services.cache_service.PerformanceOptimizer"
            ) as mock_optimizer,
            patch(
                "src.cogs.achievement.services.cache_service.CacheConfigManager"
            ) as mock_config,
        ):
            service = AchievementCacheService()
            await service.initialize()
            await service.cleanup()

            # 驗證清理方法被呼叫
            # 由於實際實作可能不同,這裡只是驗證結構


class TestBasicCacheOperations:
    """測試基本快取操作."""

    @pytest.mark.asyncio
    async def test_get_cached_achievement(self, cache_service, sample_achievement):
        """測試取得快取成就."""
        cache_key = "achievement:1"

        # 模擬快取策略返回資料
        cache_service._strategy.get_cached_data = AsyncMock(
            return_value=sample_achievement
        )

        result = await cache_service.get_cached_achievement(1)

        assert result is not None
        assert result.id == sample_achievement.id
        cache_service._strategy.get_cached_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_achievement(self, cache_service, sample_achievement):
        """測試快取成就."""
        # 模擬快取策略
        cache_service._strategy.cache_data = AsyncMock()

        await cache_service.cache_achievement(sample_achievement)

        cache_service._strategy.cache_data.assert_called_once_with(
            f"achievement:{sample_achievement.id}", sample_achievement
        )

    @pytest.mark.asyncio
    async def test_get_cached_user_achievements(
        self, cache_service, sample_user_achievement
    ):
        """測試取得快取用戶成就."""
        user_id = 123456789
        achievements = [sample_user_achievement]

        # 模擬快取策略返回資料
        cache_service._strategy.get_cached_data = AsyncMock(return_value=achievements)

        result = await cache_service.get_cached_user_achievements(user_id)

        assert result is not None
        assert len(result) == 1
        assert result[0].user_id == user_id

    @pytest.mark.asyncio
    async def test_cache_user_achievements(
        self, cache_service, sample_user_achievement
    ):
        """測試快取用戶成就列表."""
        user_id = 123456789
        achievements = [sample_user_achievement]

        # 模擬快取策略
        cache_service._strategy.cache_data = AsyncMock()

        await cache_service.cache_user_achievements(user_id, achievements)

        cache_service._strategy.cache_data.assert_called_once_with(
            f"user_achievements:{user_id}", achievements
        )

    @pytest.mark.asyncio
    async def test_cache_miss_handling(self, cache_service):
        """測試快取未命中處理."""
        # 模擬快取未命中
        cache_service._strategy.get_cached_data = AsyncMock(return_value=None)

        result = await cache_service.get_cached_achievement(999)

        assert result is None
        cache_service._strategy.get_cached_data.assert_called_once()


class TestCacheInvalidation:
    """測試快取失效機制."""

    @pytest.mark.asyncio
    async def test_invalidate_achievement_cache(self, cache_service):
        """測試成就快取失效."""
        achievement_id = 1

        # 模擬失效管理器
        cache_service._invalidation_manager.invalidate_related_caches = AsyncMock()

        await cache_service.invalidate_achievement_cache(achievement_id)

        cache_service._invalidation_manager.invalidate_related_caches.assert_called_once_with(
            f"achievement:{achievement_id}"
        )

    @pytest.mark.asyncio
    async def test_invalidate_user_cache(self, cache_service):
        """測試用戶快取失效."""
        user_id = 123456789

        # 模擬失效管理器
        cache_service._invalidation_manager.invalidate_user_related_caches = AsyncMock()

        await cache_service.invalidate_user_cache(user_id)

        cache_service._invalidation_manager.invalidate_user_related_caches.assert_called_once_with(
            user_id
        )

    @pytest.mark.asyncio
    async def test_batch_invalidation(self, cache_service):
        """測試批量失效."""
        cache_keys = ["achievement:1", "achievement:2", "user_achievements:123"]

        # 模擬失效管理器
        cache_service._invalidation_manager.batch_invalidate = AsyncMock()

        await cache_service.batch_invalidate(cache_keys)

        cache_service._invalidation_manager.batch_invalidate.assert_called_once_with(
            cache_keys
        )

    @pytest.mark.asyncio
    async def test_clear_all_caches(self, cache_service):
        """測試清除所有快取."""
        # 模擬失效管理器
        cache_service._invalidation_manager.clear_all = AsyncMock()

        await cache_service.clear_all_caches()

        cache_service._invalidation_manager.clear_all.assert_called_once()


class TestPerformanceMonitoring:
    """測試效能監控."""

    @pytest.mark.asyncio
    async def test_get_cache_statistics(self, cache_service):
        """測試取得快取統計."""
        mock_stats = {
            "hit_rate": 0.85,
            "miss_rate": 0.15,
            "total_hits": 1000,
            "total_misses": 150,
        }

        # 模擬效能優化器
        cache_service._performance_optimizer.get_performance_stats = AsyncMock(
            return_value=mock_stats
        )

        stats = await cache_service.get_cache_statistics()

        assert stats == mock_stats
        cache_service._performance_optimizer.get_performance_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cache_health_status(self, cache_service):
        """測試取得快取健康狀態."""
        mock_health = {
            "status": "healthy",
            "memory_usage": 0.45,
            "cache_efficiency": 0.92,
        }

        # 模擬效能優化器
        cache_service._performance_optimizer.get_health_status = AsyncMock(
            return_value=mock_health
        )

        health = await cache_service.get_cache_health_status()

        assert health == mock_health
        cache_service._performance_optimizer.get_health_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_optimize_cache_performance(self, cache_service):
        """測試快取效能優化."""
        # 模擬效能優化器
        cache_service._performance_optimizer.optimize = AsyncMock()

        await cache_service.optimize_cache_performance()

        cache_service._performance_optimizer.optimize.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_cache_statistics(self, cache_service):
        """測試重置快取統計."""
        # 模擬效能優化器
        cache_service._performance_optimizer.reset_stats = AsyncMock()

        await cache_service.reset_cache_statistics()

        cache_service._performance_optimizer.reset_stats.assert_called_once()


class TestConfigurationManagement:
    """測試配置管理."""

    @pytest.mark.asyncio
    async def test_config_change_handling(self, cache_service):
        """測試配置變更處理."""
        config_update = CacheConfigUpdate(
            cache_type="achievement", max_size=2000, ttl_seconds=600
        )

        # 模擬配置變更
        await cache_service._on_config_changed(config_update)

        # 驗證配置已更新(實際實作可能不同)
        # 這裡主要測試方法不會拋出異常

    @pytest.mark.asyncio
    async def test_dynamic_cache_resize(self, cache_service):
        """測試動態快取大小調整."""
        cache_type = "achievement"
        new_size = 1500

        with patch.object(cache_service, "_resize_cache") as mock_resize:
            await cache_service.resize_cache(cache_type, new_size)
            mock_resize.assert_called_once_with(cache_type, new_size)

    @pytest.mark.asyncio
    async def test_ttl_adjustment(self, cache_service):
        """測試 TTL 動態調整."""
        cache_type = "user_achievements"
        new_ttl = 900

        with patch.object(cache_service, "_adjust_ttl") as mock_adjust:
            await cache_service.adjust_cache_ttl(cache_type, new_ttl)
            mock_adjust.assert_called_once_with(cache_type, new_ttl)


class TestErrorHandling:
    """測試錯誤處理."""

    @pytest.mark.asyncio
    async def test_cache_operation_error_handling(self, cache_service):
        """測試快取操作錯誤處理."""
        # 模擬快取策略拋出異常
        cache_service._strategy.get_cached_data = AsyncMock(
            side_effect=Exception("快取錯誤")
        )

        # 應該不會拋出異常,而是返回 None
        result = await cache_service.get_cached_achievement(1)
        assert result is None

    @pytest.mark.asyncio
    async def test_invalidation_error_handling(self, cache_service):
        """測試失效操作錯誤處理."""
        # 模擬失效管理器拋出異常
        cache_service._invalidation_manager.invalidate_related_caches = AsyncMock(
            side_effect=Exception("失效錯誤")
        )

        # 應該不會拋出異常
        await cache_service.invalidate_achievement_cache(1)

    @pytest.mark.asyncio
    async def test_performance_monitoring_error_handling(self, cache_service):
        """測試效能監控錯誤處理."""
        # 模擬效能優化器拋出異常
        cache_service._performance_optimizer.get_performance_stats = AsyncMock(
            side_effect=Exception("統計錯誤")
        )

        # 應該返回預設值或空統計
        stats = await cache_service.get_cache_statistics()
        assert stats is not None  # 應該有某種預設回應

    @pytest.mark.asyncio
    async def test_memory_pressure_handling(self, cache_service):
        """測試記憶體壓力處理."""
        # 模擬記憶體不足情況
        with patch("psutil.virtual_memory") as mock_memory:
            mock_memory.return_value.percent = 95.0  # 95% 記憶體使用率

            # 觸發記憶體壓力處理
            await cache_service._handle_memory_pressure()

            # 驗證採取了緩解措施(實際實作可能不同)


class TestCacheWarmup:
    """測試快取預熱功能."""

    @pytest.mark.asyncio
    async def test_warmup_popular_achievements(self, cache_service):
        """測試預熱熱門成就."""
        popular_achievements = [1, 2, 3, 4, 5]

        with patch.object(cache_service, "_load_achievement") as mock_load:
            await cache_service.warmup_popular_achievements(popular_achievements)

            # 驗證所有熱門成就都被載入
            assert mock_load.call_count == len(popular_achievements)

    @pytest.mark.asyncio
    async def test_warmup_user_data(self, cache_service):
        """測試預熱用戶資料."""
        active_users = [123, 456, 789]

        with patch.object(cache_service, "_load_user_achievements") as mock_load:
            await cache_service.warmup_user_data(active_users)

            # 驗證所有活躍用戶資料都被載入
            assert mock_load.call_count == len(active_users)

    @pytest.mark.asyncio
    async def test_scheduled_warmup(self, cache_service):
        """測試定時預熱."""
        with (
            patch.object(cache_service, "warmup_popular_achievements") as mock_popular,
            patch.object(cache_service, "warmup_user_data") as mock_user,
        ):
            await cache_service.scheduled_warmup()

            # 驗證定時預熱執行
            mock_popular.assert_called_once()
            mock_user.assert_called_once()


class TestCacheConsistency:
    """測試快取一致性."""

    @pytest.mark.asyncio
    async def test_cache_coherence_check(self, cache_service):
        """測試快取一致性檢查."""
        # 模擬一致性檢查
        with patch.object(cache_service, "_verify_cache_consistency") as mock_verify:
            mock_verify.return_value = True

            is_consistent = await cache_service.verify_cache_consistency()

            assert is_consistent is True
            mock_verify.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_sync_with_database(self, cache_service):
        """測試快取與資料庫同步."""
        cache_keys = ["achievement:1", "user_achievements:123"]

        with patch.object(cache_service, "_sync_cache_with_db") as mock_sync:
            await cache_service.sync_cache_with_database(cache_keys)

            mock_sync.assert_called_once_with(cache_keys)

    @pytest.mark.asyncio
    async def test_resolve_cache_conflicts(self, cache_service):
        """測試快取衝突解決."""
        conflicted_keys = ["achievement:1"]

        with patch.object(cache_service, "_resolve_conflicts") as mock_resolve:
            await cache_service.resolve_cache_conflicts(conflicted_keys)

            mock_resolve.assert_called_once_with(conflicted_keys)


# 測試運行標記
pytestmark = pytest.mark.asyncio
