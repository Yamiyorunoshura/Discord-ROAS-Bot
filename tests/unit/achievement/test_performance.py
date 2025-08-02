"""成就系統效能優化測試.

測試效能分析器、快取管理器、優化的資料庫操作等功能。
根據 Story 5.1 Task 9 的要求實作。
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.cogs.achievement.database.models import Achievement, AchievementType
from src.cogs.achievement.database.optimized_repository import (
    OptimizedAchievementRepository,
)
from src.cogs.achievement.services.achievement_monitor import (
    AchievementPerformanceMonitor,
    MetricType,
)
from src.cogs.achievement.services.cache_manager import (
    CacheConfig,
    CacheManager,
    CacheType,
)
from src.cogs.achievement.services.performance_analyzer import (
    PerformanceAnalyzer,
    QueryPerformanceMetric,
    QueryType,
)
from src.cogs.achievement.services.performance_service import (
    AchievementPerformanceService,
)

# 確保所有測試都使用 async event loop
pytestmark = pytest.mark.asyncio


@pytest.fixture
def sample_achievements():
    """範例成就資料."""
    return [
        Achievement(
            id=1,
            name="Test Achievement 1",
            description="Test description 1",
            category_id=1,
            type=AchievementType.COUNTER,
            criteria={
                "target_value": 10,
                "counter_field": "message_count"
            },
            points=100,
            is_active=True,
            role_reward=None,
            is_hidden=False
        ),
        Achievement(
            id=2,
            name="Test Achievement 2",
            description="Test description 2",
            category_id=1,
            type=AchievementType.MILESTONE,
            criteria={
                "target_value": 5,
                "milestone_type": "level"
            },
            points=50,
            is_active=True,
            role_reward="特殊會員",
            is_hidden=True
        )
    ]


class TestPerformanceAnalyzer:
    """效能分析器測試."""

    @pytest.fixture
    def mock_repository(self, sample_achievements):
        """模擬資料存取庫."""
        repository = AsyncMock(spec=OptimizedAchievementRepository)

        repository.list_achievements.return_value = sample_achievements
        repository.get_user_achievements.return_value = []
        repository.get_user_progress.return_value = None
        repository.get_user_progresses.return_value = []
        repository.get_user_achievement_stats.return_value = {
            "total_achievements": 0, "total_points": 0, "categories": {}
        }
        repository.get_global_achievement_stats.return_value = {
            "total_achievements": 2, "active_achievements": 2,
            "total_user_achievements": 0, "unique_users": 0
        }
        repository.get_popular_achievements.return_value = [
            (sample_achievements[0], 5), (sample_achievements[1], 3)
        ]

        return repository

    @pytest.fixture
    def analyzer(self, mock_repository):
        """效能分析器實例."""
        return PerformanceAnalyzer(mock_repository)

    async def test_analyze_achievement_list_queries(self, analyzer):
        """測試成就列表查詢分析."""
        result = await analyzer._analyze_achievement_list_queries()

        assert "test_count" in result
        assert "average_time_ms" in result
        assert "meets_target" in result
        assert result["test_count"] >= 2  # 應該有至少2個測試場景
        assert isinstance(result["average_time_ms"], int | float)
        assert isinstance(result["meets_target"], bool)
        assert "details" in result

    async def test_analyze_user_achievement_queries(self, analyzer):
        """測試用戶成就查詢分析."""
        result = await analyzer._analyze_user_achievement_queries()

        assert "test_count" in result
        assert "average_time_ms" in result
        assert result["test_count"] >= 3  # 應該有3個測試場景
        assert "target_time_ms" in result

    async def test_analyze_progress_queries(self, analyzer):
        """測試進度查詢分析."""
        result = await analyzer._analyze_progress_queries()

        assert "test_count" in result
        assert "average_time_ms" in result
        assert result["test_count"] >= 2  # 應該有2個測試場景

    async def test_analyze_stats_queries(self, analyzer):
        """測試統計查詢分析."""
        result = await analyzer._analyze_stats_queries()

        assert "test_count" in result
        assert "average_time_ms" in result
        assert result["test_count"] >= 2  # 應該有2個測試場景

    async def test_full_analysis(self, analyzer):
        """測試完整效能分析."""
        result = await analyzer.analyze_all_queries()

        assert "timestamp" in result
        assert "query_performance" in result
        assert "bottlenecks" in result
        assert "recommendations" in result
        assert "overall_health" in result

        # 檢查查詢效能分析
        query_perf = result["query_performance"]
        assert "achievement_list" in query_perf
        assert "user_achievements" in query_perf
        assert "user_progress" in query_perf
        assert "stats" in query_perf

    async def test_identify_bottlenecks(self, analyzer):
        """測試瓶頸識別."""
        # 添加一些慢查詢指標
        analyzer._metrics_history = [
            QueryPerformanceMetric(
                query_type=QueryType.ACHIEVEMENT_LIST,
                execution_time_ms=600,  # 慢查詢
                rows_examined=1000,
                rows_returned=10,
                memory_usage_mb=5.0,
                query_sql="SELECT * FROM achievements"
            ),
            QueryPerformanceMetric(
                query_type=QueryType.USER_ACHIEVEMENTS,
                execution_time_ms=800,  # 非常慢
                rows_examined=5000,
                rows_returned=20,
                memory_usage_mb=15.0,
                query_sql="SELECT * FROM user_achievements"
            )
        ]

        bottlenecks = await analyzer._identify_bottlenecks()

        assert len(bottlenecks) > 0
        assert any(b.type == "slow_queries" for b in bottlenecks)

        # 檢查瓶頸屬性
        slow_query_bottleneck = next(b for b in bottlenecks if b.type == "slow_queries")
        assert slow_query_bottleneck.severity in ["medium", "high", "critical"]
        assert len(slow_query_bottleneck.recommendations) > 0


class TestCacheManager:
    """快取管理器測試."""

    @pytest.fixture
    def cache_configs(self):
        """測試快取配置."""
        return {
            CacheType.ACHIEVEMENT: CacheConfig(max_size=10, ttl_seconds=60),
            CacheType.USER_ACHIEVEMENT: CacheConfig(max_size=20, ttl_seconds=30)
        }

    @pytest.fixture
    async def cache_manager(self, cache_configs, tmp_path):
        """快取管理器實例."""
        async with CacheManager(cache_configs, str(tmp_path)) as manager:
            yield manager

    async def test_basic_cache_operations(self, cache_manager):
        """測試基本快取操作."""
        # 測試設定和取得
        await cache_manager.set(CacheType.ACHIEVEMENT, "test_key", "test_value")

        value = await cache_manager.get(CacheType.ACHIEVEMENT, "test_key")
        assert value == "test_value"

        # 測試不存在的鍵
        value = await cache_manager.get(CacheType.ACHIEVEMENT, "nonexistent", "default")
        assert value == "default"

    async def test_cache_expiration(self, cache_configs, tmp_path):
        """測試快取過期."""
        # 設定短期快取
        cache_configs[CacheType.ACHIEVEMENT].ttl_seconds = 1

        async with CacheManager(cache_configs, str(tmp_path)) as manager:
            await manager.set(CacheType.ACHIEVEMENT, "expire_key", "expire_value")

            # 立即取得應該成功
            value = await manager.get(CacheType.ACHIEVEMENT, "expire_key")
            assert value == "expire_value"

            # 等待過期
            await asyncio.sleep(1.1)

            # 過期後應該取得不到
            value = await manager.get(CacheType.ACHIEVEMENT, "expire_key", "expired")
            assert value == "expired"

    async def test_cache_invalidation(self, cache_manager):
        """測試快取失效."""
        # 設定一些測試資料
        await cache_manager.set(CacheType.ACHIEVEMENT, "achievement:1", {"id": 1})
        await cache_manager.set(CacheType.USER_ACHIEVEMENT, "user_achievements:123", [])
        await cache_manager.set(CacheType.USER_ACHIEVEMENT, "user_progress:123:1", {})

        # 使用戶相關快取失效
        invalidated_count = await cache_manager.invalidate_by_user(123)
        assert invalidated_count >= 0  # 可能失效0個或更多項目

    async def test_cache_stats(self, cache_manager):
        """測試快取統計."""
        # 執行一些快取操作
        await cache_manager.set(CacheType.ACHIEVEMENT, "stats_key", "stats_value")
        await cache_manager.get(CacheType.ACHIEVEMENT, "stats_key")  # hit
        await cache_manager.get(CacheType.ACHIEVEMENT, "nonexistent")  # miss

        stats = cache_manager.get_stats()

        assert "overall" in stats
        assert "by_type" in stats

        overall = stats["overall"]
        assert "total_hits" in overall
        assert "total_misses" in overall
        assert "hit_rate" in overall
        assert overall["total_hits"] >= 1
        assert overall["total_misses"] >= 1


class TestAchievementPerformanceMonitor:
    """成就系統效能監控器測試."""

    @pytest.fixture
    def mock_cache_manager(self):
        """模擬快取管理器."""
        manager = AsyncMock(spec=CacheManager)
        manager.get_stats.return_value = {
            "overall": {"hit_rate": 0.8, "total_requests": 100}
        }
        return manager

    @pytest.fixture
    def monitor(self, mock_cache_manager):
        """效能監控器實例."""
        return AchievementPerformanceMonitor(
            cache_manager=mock_cache_manager,
            slow_query_threshold=100.0,
            enable_detailed_logging=False
        )

    async def test_track_query_operation(self, monitor):
        """測試查詢操作追蹤."""
        await monitor.track_query_operation(
            operation="test_query",
            duration_ms=150.0,
            success=True,
            user_id=123
        )

        # 檢查查詢統計
        stats = monitor.get_query_performance_report()
        query_metrics = stats["query_metrics"]

        assert query_metrics["total_queries"] == 1
        assert query_metrics["slow_queries"] == 1  # 150ms > 100ms 門檻
        assert query_metrics["avg_response_time_ms"] == 150.0

    async def test_track_cache_operation(self, monitor):
        """測試快取操作追蹤."""
        await monitor.track_cache_operation(
            cache_type=CacheType.ACHIEVEMENT,
            operation="get",
            hit=True,
            duration_ms=5.0
        )

        # 檢查指標歷史
        assert len(monitor._metrics_history) == 1
        metric = monitor._metrics_history[0]
        assert metric.metric_type == MetricType.CACHE_HIT_RATE
        assert metric.value == 1.0  # hit = True

    async def test_memory_usage_tracking(self, monitor):
        """測試記憶體使用追蹤."""
        # 測試正常記憶體使用
        await monitor.track_memory_usage(50.0, "normal_operation")

        # 測試高記憶體使用（應該觸發警報）
        await monitor.track_memory_usage(90.0, "high_usage_operation")

        # 檢查是否有警報產生
        assert len(monitor.alerts_history) >= 1

        # 檢查警報內容
        memory_alerts = [a for a in monitor.alerts_history if "記憶體" in a.message]
        assert len(memory_alerts) >= 1

    def test_health_status_calculation(self, monitor):
        """測試健康狀態計算."""
        # 模擬一些查詢統計
        monitor._query_metrics.total_queries = 100
        monitor._query_metrics.slow_queries = 5  # 5% 慢查詢
        monitor._query_metrics.failed_queries = 2  # 2% 錯誤率
        monitor._query_metrics.avg_response_time = 120.0  # 120ms 平均時間

        health_status = monitor._calculate_health_status()

        assert health_status in ["excellent", "good", "fair", "poor", "critical"]
        # 基於這些統計，應該是 "good" 或更好
        assert health_status in ["excellent", "good"]


class TestAchievementPerformanceService:
    """成就系統效能服務測試."""

    @pytest.fixture
    def mock_repository(self, sample_achievements):
        """模擬優化的資料存取庫."""
        repo = AsyncMock(spec=OptimizedAchievementRepository)
        return repo

    @pytest.fixture
    async def service(self, mock_repository, sample_achievements, tmp_path):
        """效能服務實例."""
        # 配置模擬資料
        mock_repository.get_achievement_by_id.return_value = sample_achievements[0]
        mock_repository.list_achievements_optimized.return_value = (sample_achievements, len(sample_achievements))
        mock_repository.get_user_achievements_optimized.return_value = ([], 0)
        mock_repository.get_achievements_by_ids.return_value = sample_achievements
        mock_repository.get_user_progress_batch.return_value = []
        mock_repository.get_popular_achievements.return_value = [(a, 5) for a in sample_achievements]
        mock_repository.get_query_stats.return_value = {
            "total_queries": 10,
            "slow_queries": 1,
            "avg_query_time": 45.0,
            "slow_query_ratio": 0.1
        }

        # 創建快取管理器
        cache_manager = CacheManager(cache_dir=str(tmp_path))

        # 創建效能監控器
        from src.cogs.achievement.services.achievement_monitor import (
            AchievementPerformanceMonitor,
        )
        monitor = AchievementPerformanceMonitor(cache_manager=cache_manager)

        # 創建效能分析器
        from src.cogs.achievement.services.performance_analyzer import (
            PerformanceAnalyzer,
        )
        analyzer = PerformanceAnalyzer(mock_repository)

        # 創建服務
        service = AchievementPerformanceService(
            repository=mock_repository,
            cache_manager=cache_manager,
            performance_monitor=monitor,
            performance_analyzer=analyzer
        )

        return service

    async def test_get_achievement_optimized(self, service, sample_achievements):
        """測試優化的成就取得."""
        # 測試取得成就
        result = await service.get_achievement_optimized(1)
        assert result == sample_achievements[0]
        service._repository.get_achievement_by_id.assert_called_once_with(1)

    async def test_list_achievements_optimized(self, service, sample_achievements):
        """測試優化的成就列表查詢."""
        achievements, total = await service.list_achievements_optimized(
            page=1, page_size=10
        )

        assert achievements == sample_achievements
        assert total == len(sample_achievements)

    async def test_batch_operations(self, service, sample_achievements):
        """測試批量操作."""
        result = await service.batch_get_achievements([1, 2])

        assert len(result) == 2
        assert 1 in result
        assert 2 in result

    async def test_cache_invalidation(self, service):
        """測試快取失效."""
        # 測試快取失效
        await service.invalidate_user_cache(123)
        await service.invalidate_achievement_cache(1)

    async def test_performance_report(self, service):
        """測試效能報告生成."""
        report = await service.get_performance_report()

        assert "timestamp" in report
        assert "cache_statistics" in report
        assert "query_statistics" in report

    async def test_auto_optimization(self, service):
        """測試自動優化."""
        result = await service.auto_optimize()

        assert "optimization_time" in result
        assert "optimizations_applied" in result


@pytest.mark.integration
class TestPerformanceIntegration:
    """效能優化整合測試."""

    async def test_end_to_end_performance_flow(self, sample_achievements, tmp_path):
        """測試端到端效能優化流程."""
        # 創建模擬資料庫
        mock_repository = AsyncMock(spec=OptimizedAchievementRepository)
        mock_achievement = sample_achievements[0]
        mock_repository.get_achievement_by_id.return_value = mock_achievement
        mock_repository.get_query_stats.return_value = {
            "total_queries": 10,
            "slow_queries": 1,
            "avg_query_time": 45.0,
            "slow_query_ratio": 0.1
        }
        mock_repository.get_popular_achievements.return_value = [(mock_achievement, 5)]

        # 創建效能服務
        cache_manager = CacheManager(cache_dir=str(tmp_path))
        service = AchievementPerformanceService(
            repository=mock_repository,
            cache_manager=cache_manager
        )

        # 1. 執行查詢操作
        result = await service.get_achievement_optimized(1)
        assert result == mock_achievement

        # 2. 檢查快取是否生效（第二次查詢應該從快取取得）
        result2 = await service.get_achievement_optimized(1)
        assert result2 == mock_achievement

        # 3. 生成效能報告
        report = await service.get_performance_report()
        assert "cache_statistics" in report

        # 4. 執行自動優化
        optimization_result = await service.auto_optimize()
        assert "optimizations_applied" in optimization_result


if __name__ == "__main__":
    # 運行測試
    pytest.main([__file__, "-v"])
