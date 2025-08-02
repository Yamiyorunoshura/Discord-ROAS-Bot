"""成就系統效能服務單元測試.

測試 AchievementPerformanceService 的所有效能功能，包括：
- 效能服務初始化和配置
- 快取整合和管理
- 效能監控和分析
- 批量操作優化
- 自動效能調優
- 統計和報告
- 錯誤處理和恢復

使用模擬物件進行快速測試執行。
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from src.cogs.achievement.database.models import (
    Achievement,
    AchievementType,
    UserAchievement,
)
from src.cogs.achievement.services.performance_service import (
    AchievementPerformanceService,
)


@pytest_asyncio.fixture
async def mock_repository():
    """模擬的優化資料存取庫."""
    repository = AsyncMock()
    return repository


@pytest_asyncio.fixture
async def mock_cache_manager():
    """模擬的快取管理器."""
    cache_manager = AsyncMock()
    cache_manager.start = AsyncMock()
    cache_manager.stop = AsyncMock()
    return cache_manager


@pytest_asyncio.fixture
async def mock_performance_monitor():
    """模擬的效能監控器."""
    monitor = AsyncMock()
    monitor.start_achievement_monitoring = AsyncMock()
    monitor.stop_monitoring = AsyncMock()
    return monitor


@pytest_asyncio.fixture
async def mock_performance_analyzer():
    """模擬的效能分析器."""
    analyzer = AsyncMock()
    return analyzer


@pytest_asyncio.fixture
async def performance_service(mock_repository, mock_cache_manager, mock_performance_monitor, mock_performance_analyzer):
    """測試用效能服務."""
    service = AchievementPerformanceService(
        repository=mock_repository,
        cache_manager=mock_cache_manager,
        performance_monitor=mock_performance_monitor,
        performance_analyzer=mock_performance_analyzer,
        enable_auto_optimization=True
    )

    async with service:
        yield service


@pytest_asyncio.fixture
async def sample_achievement():
    """範例成就物件."""
    return Achievement(
        id=1,
        name="測試效能成就",
        description="這是一個測試效能的成就",
        category_id=1,
        type=AchievementType.COUNTER,
        criteria={"target_value": 100},
        points=500,
        is_active=True
    )


@pytest_asyncio.fixture
async def sample_achievements_list():
    """範例成就列表."""
    achievements = []
    for i in range(10):
        achievement = Achievement(
            id=i+1,
            name=f"測試成就 {i+1}",
            description=f"測試成就描述 {i+1}",
            category_id=1,
            type=AchievementType.COUNTER,
            criteria={"target_value": (i+1) * 10},
            points=(i+1) * 100,
            is_active=True
        )
        achievements.append(achievement)
    return achievements


class TestPerformanceServiceInitialization:
    """測試效能服務初始化."""

    @pytest.mark.asyncio
    async def test_service_initialization_with_defaults(self, mock_repository):
        """測試使用預設組件初始化服務."""
        with patch('src.cogs.achievement.services.performance_service.CacheManager') as mock_cache_cls, \
             patch('src.cogs.achievement.services.performance_service.AchievementPerformanceMonitor') as mock_monitor_cls, \
             patch('src.cogs.achievement.services.performance_service.PerformanceAnalyzer') as mock_analyzer_cls:

            service = AchievementPerformanceService(mock_repository)

            # 驗證預設組件建立
            mock_cache_cls.assert_called_once()
            mock_monitor_cls.assert_called_once()
            mock_analyzer_cls.assert_called_once_with(mock_repository)

            # 驗證配置設定
            assert service._enable_auto_optimization is True
            assert service._auto_cache_threshold == 50
            assert service._batch_size == 100

    @pytest.mark.asyncio
    async def test_service_initialization_with_custom_components(self, mock_repository, mock_cache_manager, mock_performance_monitor, mock_performance_analyzer):
        """測試使用自訂組件初始化服務."""
        service = AchievementPerformanceService(
            repository=mock_repository,
            cache_manager=mock_cache_manager,
            performance_monitor=mock_performance_monitor,
            performance_analyzer=mock_performance_analyzer,
            enable_auto_optimization=False
        )

        # 驗證組件指派
        assert service._repository is mock_repository
        assert service._cache_manager is mock_cache_manager
        assert service._performance_monitor is mock_performance_monitor
        assert service._performance_analyzer is mock_performance_analyzer
        assert service._enable_auto_optimization is False

    @pytest.mark.asyncio
    async def test_async_context_manager(self, mock_repository, mock_cache_manager, mock_performance_monitor, mock_performance_analyzer):
        """測試異步上下文管理器."""
        service = AchievementPerformanceService(
            repository=mock_repository,
            cache_manager=mock_cache_manager,
            performance_monitor=mock_performance_monitor,
            performance_analyzer=mock_performance_analyzer
        )

        async with service as ctx_service:
            # 驗證進入時啟動服務
            mock_cache_manager.start.assert_called_once()
            mock_performance_monitor.start_achievement_monitoring.assert_called_once()
            assert ctx_service is service

        # 驗證退出時停止服務
        mock_cache_manager.stop.assert_called_once()
        mock_performance_monitor.stop_monitoring.assert_called_once()


class TestOptimizedDataOperations:
    """測試優化的資料操作."""

    @pytest.mark.asyncio
    async def test_get_achievement_with_cache(self, performance_service, sample_achievement, mock_cache_manager, mock_repository):
        """測試帶快取的成就查詢."""
        achievement_id = 1

        # 模擬快取命中
        mock_cache_manager.get.return_value = sample_achievement

        result = await performance_service.get_achievement_optimized(achievement_id)

        assert result == sample_achievement
        mock_cache_manager.get.assert_called_once()
        mock_repository.get_achievement_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_achievement_cache_miss(self, performance_service, sample_achievement, mock_cache_manager, mock_repository):
        """測試快取未命中時的成就查詢."""
        achievement_id = 1

        # 模擬快取未命中
        mock_cache_manager.get.return_value = None
        mock_repository.get_achievement_by_id.return_value = sample_achievement

        result = await performance_service.get_achievement_optimized(achievement_id)

        assert result == sample_achievement
        mock_cache_manager.get.assert_called_once()
        mock_repository.get_achievement_by_id.assert_called_once_with(achievement_id)
        mock_cache_manager.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_get_achievements(self, performance_service, sample_achievements_list, mock_repository):
        """測試批量獲取成就優化."""
        achievement_ids = [1, 2, 3, 4, 5]
        expected_achievements = sample_achievements_list[:5]

        # 模擬批量查詢
        mock_repository.get_achievements_batch.return_value = expected_achievements

        results = await performance_service.get_achievements_batch_optimized(achievement_ids)

        assert len(results) == 5
        assert results == expected_achievements
        mock_repository.get_achievements_batch.assert_called_once_with(achievement_ids)

    @pytest.mark.asyncio
    async def test_get_user_achievements_with_pagination(self, performance_service, mock_repository):
        """測試帶分頁的用戶成就查詢優化."""
        user_id = 123456789
        page_size = 20
        offset = 0

        expected_achievements = [
            UserAchievement(id=i, user_id=user_id, achievement_id=i, earned_at=datetime.now(), notified=False)
            for i in range(page_size)
        ]

        mock_repository.get_user_achievements_paginated.return_value = expected_achievements

        results = await performance_service.get_user_achievements_optimized(
            user_id=user_id,
            page_size=page_size,
            offset=offset
        )

        assert len(results) == page_size
        mock_repository.get_user_achievements_paginated.assert_called_once_with(
            user_id=user_id,
            limit=page_size,
            offset=offset
        )


class TestPerformanceMonitoring:
    """測試效能監控功能."""

    @pytest.mark.asyncio
    async def test_get_performance_metrics(self, performance_service, mock_performance_monitor):
        """測試取得效能指標."""
        expected_metrics = {
            "cache_hit_rate": 0.85,
            "avg_response_time": 50.2,
            "queries_per_second": 120.5,
            "memory_usage": 0.65
        }

        mock_performance_monitor.get_current_metrics.return_value = expected_metrics

        metrics = await performance_service.get_performance_metrics()

        assert metrics == expected_metrics
        mock_performance_monitor.get_current_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_performance_alert_handling(self, performance_service, mock_performance_monitor):
        """測試效能警報處理."""
        alert_data = {
            "type": "high_response_time",
            "value": 500.0,
            "threshold": 100.0,
            "timestamp": datetime.now()
        }

        # 模擬效能警報
        mock_performance_monitor.get_alerts.return_value = [alert_data]

        alerts = await performance_service.get_performance_alerts()

        assert len(alerts) == 1
        assert alerts[0] == alert_data
        mock_performance_monitor.get_alerts.assert_called_once()

    @pytest.mark.asyncio
    async def test_performance_trend_analysis(self, performance_service, mock_performance_analyzer):
        """測試效能趨勢分析."""
        trend_data = {
            "period": "last_24h",
            "cache_efficiency_trend": "improving",
            "response_time_trend": "stable",
            "throughput_trend": "increasing"
        }

        mock_performance_analyzer.analyze_trends.return_value = trend_data

        trends = await performance_service.analyze_performance_trends(period="last_24h")

        assert trends == trend_data
        mock_performance_analyzer.analyze_trends.assert_called_once_with(period="last_24h")


class TestCacheOptimization:
    """測試快取優化功能."""

    @pytest.mark.asyncio
    async def test_cache_warming(self, performance_service, sample_achievements_list, mock_cache_manager, mock_repository):
        """測試快取預熱."""
        popular_achievement_ids = [1, 2, 3, 4, 5]
        popular_achievements = sample_achievements_list[:5]

        mock_repository.get_popular_achievements.return_value = popular_achievements

        await performance_service.warm_cache()

        # 驗證熱門成就被載入快取
        mock_repository.get_popular_achievements.assert_called_once()
        assert mock_cache_manager.set.call_count == len(popular_achievements)

    @pytest.mark.asyncio
    async def test_cache_invalidation_strategy(self, performance_service, mock_cache_manager):
        """測試快取失效策略."""
        achievement_id = 1

        await performance_service.invalidate_achievement_cache(achievement_id)

        # 驗證相關快取被失效
        mock_cache_manager.invalidate_pattern.assert_called()

    @pytest.mark.asyncio
    async def test_adaptive_cache_sizing(self, performance_service, mock_cache_manager, mock_performance_monitor):
        """測試自適應快取大小調整."""
        # 模擬記憶體使用過高
        mock_performance_monitor.get_memory_usage.return_value = 0.85

        await performance_service.optimize_cache_size()

        # 驗證快取大小被調整
        mock_cache_manager.resize_caches.assert_called()


class TestAutoOptimization:
    """測試自動優化功能."""

    @pytest.mark.asyncio
    async def test_auto_optimization_trigger(self, performance_service, mock_performance_analyzer):
        """測試自動優化觸發."""
        # 模擬效能分析結果建議優化
        optimization_suggestions = [
            {"type": "increase_cache_size", "target": "user_achievements", "value": 2000},
            {"type": "adjust_ttl", "target": "achievements", "value": 600}
        ]

        mock_performance_analyzer.get_optimization_suggestions.return_value = optimization_suggestions

        await performance_service.run_auto_optimization()

        # 驗證優化建議被執行
        mock_performance_analyzer.get_optimization_suggestions.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_optimization_disabled(self, mock_repository):
        """測試停用自動優化時的行為."""
        service = AchievementPerformanceService(
            repository=mock_repository,
            enable_auto_optimization=False
        )

        with patch.object(service, '_apply_optimization') as mock_apply:
            await service.run_auto_optimization()

            # 驗證優化未被執行
            mock_apply.assert_not_called()

    @pytest.mark.asyncio
    async def test_optimization_cooldown(self, performance_service):
        """測試優化冷卻期間."""
        # 設定最近才執行過優化
        performance_service._last_optimization = datetime.now() - timedelta(minutes=5)

        with patch.object(performance_service, '_apply_optimization') as mock_apply:
            await performance_service.run_auto_optimization()

            # 驗證因為冷卻期間而未執行優化
            mock_apply.assert_not_called()


class TestBatchOperations:
    """測試批量操作優化."""

    @pytest.mark.asyncio
    async def test_batch_award_achievements(self, performance_service, mock_repository):
        """測試批量頒發成就優化."""
        award_requests = [
            {"user_id": 123, "achievement_id": 1},
            {"user_id": 124, "achievement_id": 1},
            {"user_id": 125, "achievement_id": 2}
        ]

        await performance_service.batch_award_achievements(award_requests)

        # 驗證使用批量操作
        mock_repository.batch_award_achievements.assert_called_once_with(award_requests)

    @pytest.mark.asyncio
    async def test_batch_update_progress(self, performance_service, mock_repository):
        """測試批量更新進度優化."""
        progress_updates = [
            {"user_id": 123, "achievement_id": 1, "current_value": 50},
            {"user_id": 123, "achievement_id": 2, "current_value": 25},
            {"user_id": 124, "achievement_id": 1, "current_value": 75}
        ]

        await performance_service.batch_update_progress(progress_updates)

        # 驗證使用批量操作
        mock_repository.batch_update_progress.assert_called_once_with(progress_updates)

    @pytest.mark.asyncio
    async def test_batch_operation_chunking(self, performance_service, mock_repository):
        """測試批量操作分塊處理."""
        # 建立大量資料（超過批量大小）
        large_batch = [
            {"user_id": i, "achievement_id": 1, "current_value": 10}
            for i in range(250)  # 超過預設批量大小 100
        ]

        await performance_service.batch_update_progress(large_batch)

        # 驗證被分塊處理
        assert mock_repository.batch_update_progress.call_count >= 3  # 250/100 = 3 chunks


class TestErrorHandlingAndRecovery:
    """測試錯誤處理和恢復功能."""

    @pytest.mark.asyncio
    async def test_cache_failure_fallback(self, performance_service, sample_achievement, mock_cache_manager, mock_repository):
        """測試快取失敗時的回退機制."""
        achievement_id = 1

        # 模擬快取異常
        mock_cache_manager.get.side_effect = Exception("快取服務異常")
        mock_repository.get_achievement_by_id.return_value = sample_achievement

        result = await performance_service.get_achievement_optimized(achievement_id)

        # 驗證回退到資料庫查詢
        assert result == sample_achievement
        mock_repository.get_achievement_by_id.assert_called_once_with(achievement_id)

    @pytest.mark.asyncio
    async def test_performance_monitoring_failure_handling(self, performance_service, mock_performance_monitor):
        """測試效能監控失敗處理."""
        # 模擬監控服務異常
        mock_performance_monitor.get_current_metrics.side_effect = Exception("監控服務異常")

        metrics = await performance_service.get_performance_metrics()

        # 驗證返回預設或空指標
        assert metrics is not None
        assert isinstance(metrics, dict)

    @pytest.mark.asyncio
    async def test_auto_recovery_after_failure(self, performance_service, mock_cache_manager):
        """測試失敗後的自動恢復機制."""
        # 模擬快取服務恢復
        mock_cache_manager.is_healthy.return_value = False

        await performance_service.check_and_recover_services()

        # 驗證嘗試恢復服務
        mock_cache_manager.restart.assert_called_once()

    @pytest.mark.asyncio
    async def test_graceful_degradation(self, performance_service, mock_performance_monitor):
        """測試優雅降級."""
        # 模擬部分服務不可用
        mock_performance_monitor.is_available.return_value = False

        # 服務應該仍然可用，但功能受限
        result = await performance_service.get_service_status()

        assert result["status"] == "degraded"
        assert "monitoring_unavailable" in result["limitations"]


class TestPerformanceReporting:
    """測試效能報告功能."""

    @pytest.mark.asyncio
    async def test_generate_performance_report(self, performance_service, mock_performance_analyzer):
        """測試生成效能報告."""
        expected_report = {
            "report_period": "last_24h",
            "summary": {
                "total_queries": 10000,
                "avg_response_time": 45.2,
                "cache_hit_rate": 0.88
            },
            "recommendations": [
                "增加用戶成就快取大小",
                "優化資料庫查詢索引"
            ]
        }

        mock_performance_analyzer.generate_report.return_value = expected_report

        report = await performance_service.generate_performance_report(period="last_24h")

        assert report == expected_report
        mock_performance_analyzer.generate_report.assert_called_once_with(period="last_24h")

    @pytest.mark.asyncio
    async def test_export_performance_data(self, performance_service, mock_performance_monitor):
        """測試匯出效能資料."""
        export_format = "json"
        time_range = {"start": datetime.now() - timedelta(hours=24), "end": datetime.now()}

        expected_data = {
            "metrics": [
                {"timestamp": "2024-01-01T10:00:00", "response_time": 45.2},
                {"timestamp": "2024-01-01T11:00:00", "response_time": 48.1}
            ]
        }

        mock_performance_monitor.export_data.return_value = expected_data

        data = await performance_service.export_performance_data(
            format=export_format,
            time_range=time_range
        )

        assert data == expected_data
        mock_performance_monitor.export_data.assert_called_once_with(
            format=export_format,
            time_range=time_range
        )


# 測試運行標記
pytestmark = pytest.mark.asyncio
