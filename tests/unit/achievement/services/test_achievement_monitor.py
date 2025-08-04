"""成就系統效能監控器單元測試.

測試 AchievementPerformanceMonitor 的所有監控功能,包括:
- 效能指標收集和追蹤
- 查詢時間監控
- 快取效能監控
- 記憶體使用量追蹤
- 警報機制
- 資料庫連線監控
- 統計報告生成

使用模擬物件進行快速測試執行.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from src.cogs.achievement.services.achievement_monitor import (
    AchievementMetric,
    AchievementPerformanceMonitor,
    MetricType,
)


@pytest_asyncio.fixture
async def mock_cache_manager():
    """模擬的快取管理器."""
    cache_manager = AsyncMock()
    cache_manager.get_stats.return_value = {
        "hits": 1000,
        "misses": 200,
        "hit_rate": 0.83,
        "size": 500,
    }
    return cache_manager


@pytest_asyncio.fixture
async def performance_monitor(mock_cache_manager):
    """測試用效能監控器."""
    with patch("src.core.monitor.PerformanceMonitor"):
        monitor = AchievementPerformanceMonitor(
            cache_manager=mock_cache_manager,
            alert_thresholds={
                MetricType.QUERY_TIME: 100.0,
                MetricType.CACHE_HIT_RATE: 0.7,
                MetricType.MEMORY_USAGE: 0.8,
            },
        )
        await monitor.initialize()
        yield monitor
        await monitor.cleanup()


@pytest_asyncio.fixture
async def sample_metric():
    """範例效能指標."""
    return AchievementMetric(
        metric_type=MetricType.QUERY_TIME,
        value=45.2,
        operation="get_achievement",
        user_id=123456789,
        context={"achievement_id": 1},
    )


class TestMonitorInitialization:
    """測試監控器初始化."""

    @pytest.mark.asyncio
    async def test_monitor_initialization_with_defaults(self):
        """測試使用預設配置初始化監控器."""
        with patch("src.core.monitor.PerformanceMonitor") as mock_base:
            monitor = AchievementPerformanceMonitor()
            await monitor.initialize()

            # 驗證基礎監控器初始化
            mock_base.assert_called_once()

            # 驗證預設配置
            assert monitor._collection_interval == 60.0
            assert len(monitor._alert_thresholds) > 0

            await monitor.cleanup()

    @pytest.mark.asyncio
    async def test_monitor_initialization_with_custom_config(self, mock_cache_manager):
        """測試使用自訂配置初始化監控器."""
        custom_thresholds = {MetricType.QUERY_TIME: 50.0, MetricType.MEMORY_USAGE: 0.9}

        with patch("src.core.monitor.PerformanceMonitor"):
            monitor = AchievementPerformanceMonitor(
                cache_manager=mock_cache_manager,
                alert_thresholds=custom_thresholds,
                collection_interval=30.0,
            )
            await monitor.initialize()

            assert monitor._cache_manager is mock_cache_manager
            assert monitor._alert_thresholds == custom_thresholds
            assert monitor._collection_interval == 30.0

            await monitor.cleanup()

    @pytest.mark.asyncio
    async def test_monitor_start_stop(self, performance_monitor):
        """測試監控器啟動和停止."""
        await performance_monitor.start_achievement_monitoring()

        # 驗證監控狀態
        assert performance_monitor._monitoring_active is True

        await performance_monitor.stop_monitoring()

        # 驗證停止狀態
        assert performance_monitor._monitoring_active is False


class TestMetricCollection:
    """測試指標收集功能."""

    @pytest.mark.asyncio
    async def test_record_query_time(self, performance_monitor):
        """測試記錄查詢時間."""
        operation = "get_user_achievements"
        query_time = 75.5
        context = {"user_id": 123456789, "limit": 10}

        await performance_monitor.record_query_time(operation, query_time, context)

        # 驗證指標被記錄
        metrics = performance_monitor._get_recent_metrics(MetricType.QUERY_TIME)
        assert len(metrics) == 1
        assert metrics[0].value == query_time
        assert metrics[0].operation == operation
        assert metrics[0].context == context

    @pytest.mark.asyncio
    async def test_record_cache_performance(
        self, performance_monitor, mock_cache_manager
    ):
        """測試記錄快取效能."""
        await performance_monitor.record_cache_performance()

        # 驗證快取統計被收集
        mock_cache_manager.get_stats.assert_called()

        # 驗證快取指標被記錄
        hit_rate_metrics = performance_monitor._get_recent_metrics(
            MetricType.CACHE_HIT_RATE
        )
        assert len(hit_rate_metrics) >= 1

    @pytest.mark.asyncio
    async def test_record_memory_usage(self, performance_monitor):
        """測試記錄記憶體使用量."""
        with patch("psutil.virtual_memory") as mock_memory:
            mock_memory.return_value.percent = 65.5

            await performance_monitor.record_memory_usage()

            # 驗證記憶體指標被記錄
            memory_metrics = performance_monitor._get_recent_metrics(
                MetricType.MEMORY_USAGE
            )
            assert len(memory_metrics) == 1
            assert memory_metrics[0].value == 0.655  # 轉換為比例

    @pytest.mark.asyncio
    async def test_record_database_connections(self, performance_monitor):
        """測試記錄資料庫連線狀態."""
        with patch.object(
            performance_monitor, "_get_db_connection_count", return_value=15
        ):
            await performance_monitor.record_database_connections()

            # 驗證資料庫連線指標被記錄
            db_metrics = performance_monitor._get_recent_metrics(
                MetricType.DATABASE_CONNECTIONS
            )
            assert len(db_metrics) == 1
            assert db_metrics[0].value == 15

    @pytest.mark.asyncio
    async def test_record_error_rate(self, performance_monitor):
        """測試記錄錯誤率."""
        # 記錄一些操作和錯誤
        await performance_monitor.record_operation_result(
            "get_achievement", success=True
        )
        await performance_monitor.record_operation_result(
            "get_achievement", success=True
        )
        await performance_monitor.record_operation_result(
            "get_achievement", success=False
        )

        await performance_monitor.record_error_rate()

        # 驗證錯誤率指標被記錄
        error_metrics = performance_monitor._get_recent_metrics(MetricType.ERROR_RATE)
        assert len(error_metrics) >= 1


class TestPerformanceTracking:
    """測試效能追蹤功能."""

    @pytest.mark.asyncio
    async def test_query_timing_context_manager(self, performance_monitor):
        """測試查詢計時上下文管理器."""
        operation = "test_operation"
        context = {"test": "data"}

        async with performance_monitor.time_query(operation, context):
            # 模擬一些工作
            await asyncio.sleep(0.01)

        # 驗證時間被記錄
        metrics = performance_monitor._get_recent_metrics(MetricType.QUERY_TIME)
        assert len(metrics) >= 1

        recorded_metric = metrics[-1]
        assert recorded_metric.operation == operation
        assert recorded_metric.context == context
        assert recorded_metric.value > 0

    @pytest.mark.asyncio
    async def test_operation_success_tracking(self, performance_monitor):
        """測試操作成功率追蹤."""
        operation = "award_achievement"

        # 記錄多個操作結果
        for i in range(10):
            success = i < 8  # 80% 成功率
            await performance_monitor.record_operation_result(operation, success)

        # 取得操作統計
        stats = performance_monitor.get_operation_stats(operation)

        assert stats["total_operations"] == 10
        assert stats["successful_operations"] == 8
        assert stats["success_rate"] == 0.8

    @pytest.mark.asyncio
    async def test_performance_trend_analysis(self, performance_monitor):
        """測試效能趨勢分析."""
        # 記錄一系列查詢時間
        base_time = datetime.now() - timedelta(hours=1)

        for i in range(10):
            metric = AchievementMetric(
                metric_type=MetricType.QUERY_TIME,
                value=50.0 + i * 5,  # 遞增的查詢時間
                timestamp=base_time + timedelta(minutes=i * 6),
                operation="get_achievement",
            )
            performance_monitor._record_metric(metric)

        # 分析趨勢
        trend = performance_monitor.analyze_trend(
            MetricType.QUERY_TIME, time_window=timedelta(hours=1)
        )

        assert trend["direction"] == "increasing"
        assert trend["slope"] > 0


class TestAlertSystem:
    """測試警報系統."""

    @pytest.mark.asyncio
    async def test_query_time_alert(self, performance_monitor):
        """測試查詢時間警報."""
        # 記錄超過門檻的查詢時間
        slow_query_time = 150.0  # 超過預設門檻 100.0

        await performance_monitor.record_query_time(
            "slow_operation", slow_query_time, {"query": "complex_join"}
        )

        # 檢查警報
        alerts = performance_monitor.get_active_alerts()

        # 驗證產生了查詢時間警報
        query_alerts = [a for a in alerts if a.metric_type == MetricType.QUERY_TIME]
        assert len(query_alerts) >= 1
        assert query_alerts[0].severity == "warning"

    @pytest.mark.asyncio
    async def test_cache_hit_rate_alert(self, performance_monitor, mock_cache_manager):
        """測試快取命中率警報."""
        # 模擬低快取命中率
        mock_cache_manager.get_stats.return_value = {
            "hits": 600,
            "misses": 400,
            "hit_rate": 0.6,  # 低於門檻 0.7
            "size": 1000,
        }

        await performance_monitor.record_cache_performance()

        # 檢查警報
        alerts = performance_monitor.get_active_alerts()

        # 驗證產生了快取命中率警報
        cache_alerts = [a for a in alerts if a.metric_type == MetricType.CACHE_HIT_RATE]
        assert len(cache_alerts) >= 1

    @pytest.mark.asyncio
    async def test_memory_usage_alert(self, performance_monitor):
        """測試記憶體使用量警報."""
        with patch("psutil.virtual_memory") as mock_memory:
            mock_memory.return_value.percent = 85.0  # 超過門檻 80%

            await performance_monitor.record_memory_usage()

            # 檢查警報
            alerts = performance_monitor.get_active_alerts()

            # 驗證產生了記憶體使用量警報
            memory_alerts = [
                a for a in alerts if a.metric_type == MetricType.MEMORY_USAGE
            ]
            assert len(memory_alerts) >= 1
            assert memory_alerts[0].severity == "warning"

    @pytest.mark.asyncio
    async def test_alert_resolution(self, performance_monitor):
        """測試警報解決機制."""
        # 先觸發警報
        await performance_monitor.record_query_time("slow_op", 150.0)
        initial_alerts = performance_monitor.get_active_alerts()
        assert len(initial_alerts) >= 1

        # 記錄正常的查詢時間
        for _ in range(5):
            await performance_monitor.record_query_time("normal_op", 50.0)

        # 檢查警報是否解決
        await performance_monitor.check_alert_resolution()
        current_alerts = performance_monitor.get_active_alerts()

        # 驗證警報數量減少
        assert len(current_alerts) < len(initial_alerts)

    @pytest.mark.asyncio
    async def test_alert_escalation(self, performance_monitor):
        """測試警報升級機制."""
        # 持續記錄高查詢時間
        for _ in range(10):
            await performance_monitor.record_query_time("critical_slow_op", 200.0)

        alerts = performance_monitor.get_active_alerts()

        # 檢查是否有警報被升級為嚴重
        critical_alerts = [a for a in alerts if a.severity == "critical"]
        assert len(critical_alerts) >= 1


class TestStatisticsAndReporting:
    """測試統計和報告功能."""

    @pytest.mark.asyncio
    async def test_get_performance_summary(self, performance_monitor):
        """測試取得效能摘要."""
        # 記錄一些測試資料
        await performance_monitor.record_query_time("op1", 45.0)
        await performance_monitor.record_query_time("op2", 55.0)
        await performance_monitor.record_cache_performance()

        summary = performance_monitor.get_performance_summary()

        assert "avg_query_time" in summary
        assert "cache_hit_rate" in summary
        assert "total_operations" in summary
        assert "alert_count" in summary

    @pytest.mark.asyncio
    async def test_get_metrics_by_timeframe(self, performance_monitor):
        """測試按時間範圍取得指標."""
        # 記錄不同時間的指標
        now = datetime.now()

        # 1小時前的指標
        old_metric = AchievementMetric(
            metric_type=MetricType.QUERY_TIME,
            value=100.0,
            timestamp=now - timedelta(hours=1),
        )
        performance_monitor._record_metric(old_metric)

        # 最近的指標
        recent_metric = AchievementMetric(
            metric_type=MetricType.QUERY_TIME,
            value=50.0,
            timestamp=now - timedelta(minutes=5),
        )
        performance_monitor._record_metric(recent_metric)

        # 取得最近30分鐘的指標
        recent_metrics = performance_monitor.get_metrics_by_timeframe(
            MetricType.QUERY_TIME, timedelta(minutes=30)
        )

        assert len(recent_metrics) == 1
        assert recent_metrics[0].value == 50.0

    @pytest.mark.asyncio
    async def test_generate_performance_report(self, performance_monitor):
        """測試生成效能報告."""
        # 記錄測試資料
        await performance_monitor.record_query_time("test_op", 45.0)
        await performance_monitor.record_cache_performance()
        await performance_monitor.record_memory_usage()

        report = performance_monitor.generate_performance_report(
            time_period=timedelta(hours=1)
        )

        assert "report_generated_at" in report
        assert "time_period" in report
        assert "metrics_summary" in report
        assert "alerts_summary" in report
        assert "recommendations" in report

    @pytest.mark.asyncio
    async def test_export_metrics_data(self, performance_monitor):
        """測試匯出指標資料."""
        # 記錄測試資料
        for i in range(5):
            await performance_monitor.record_query_time(f"op_{i}", 45.0 + i * 5)

        exported_data = performance_monitor.export_metrics_data(
            metrics=[MetricType.QUERY_TIME],
            format="json",
            time_range=timedelta(hours=1),
        )

        assert "metrics" in exported_data
        assert len(exported_data["metrics"]) == 5
        assert "export_info" in exported_data


class TestErrorHandling:
    """測試錯誤處理."""

    @pytest.mark.asyncio
    async def test_metric_collection_error_handling(self, performance_monitor):
        """測試指標收集錯誤處理."""
        # 模擬記憶體監控失敗
        with patch("psutil.virtual_memory", side_effect=Exception("監控服務異常")):
            # 不應該拋出異常
            await performance_monitor.record_memory_usage()

            # 監控應該仍然運作
            assert performance_monitor._monitoring_active is True

    @pytest.mark.asyncio
    async def test_alert_system_error_handling(self, performance_monitor):
        """測試警報系統錯誤處理."""
        # 模擬警報處理失敗
        with patch.object(
            performance_monitor, "_send_alert", side_effect=Exception("警報發送失敗")
        ):
            # 記錄觸發警報的指標
            await performance_monitor.record_query_time("error_op", 200.0)

            # 不應該影響正常監控
            assert performance_monitor._monitoring_active is True

    @pytest.mark.asyncio
    async def test_cache_monitoring_failure_fallback(
        self, performance_monitor, mock_cache_manager
    ):
        """測試快取監控失敗時的回退機制."""
        # 模擬快取管理器異常
        mock_cache_manager.get_stats.side_effect = Exception("快取服務異常")

        await performance_monitor.record_cache_performance()

        # 驗證沒有拋出異常,並記錄了錯誤狀態
        error_metrics = performance_monitor._get_recent_metrics(MetricType.ERROR_RATE)
        # 可能會記錄快取監控錯誤


class TestPerformanceOptimization:
    """測試效能優化建議."""

    @pytest.mark.asyncio
    async def test_get_optimization_recommendations(self, performance_monitor):
        """測試取得優化建議."""
        # 記錄一些效能問題
        for _ in range(5):
            await performance_monitor.record_query_time("slow_query", 150.0)

        with patch("psutil.virtual_memory") as mock_memory:
            mock_memory.return_value.percent = 85.0
            await performance_monitor.record_memory_usage()

        recommendations = performance_monitor.get_optimization_recommendations()

        assert len(recommendations) > 0
        assert any("query" in rec.lower() for rec in recommendations)
        assert any("memory" in rec.lower() for rec in recommendations)

    @pytest.mark.asyncio
    async def test_performance_health_check(self, performance_monitor):
        """測試效能健康檢查."""
        # 記錄正常效能資料
        await performance_monitor.record_query_time("normal_op", 45.0)
        await performance_monitor.record_cache_performance()

        health_status = performance_monitor.get_health_status()

        assert "overall_health" in health_status
        assert "component_health" in health_status
        assert health_status["overall_health"] in ["healthy", "warning", "critical"]

    @pytest.mark.asyncio
    async def test_automated_performance_tuning(self, performance_monitor):
        """測試自動效能調優."""
        # 模擬需要調優的情況
        for _ in range(10):
            await performance_monitor.record_query_time("repeated_slow_query", 120.0)

        tuning_actions = await performance_monitor.suggest_automated_tuning()

        assert len(tuning_actions) > 0
        assert any(action["type"] == "cache_optimization" for action in tuning_actions)


# 測試運行標記
pytestmark = pytest.mark.asyncio
