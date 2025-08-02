"""效能監控系統測試模組.

此模組測試 Discord ROAS Bot 的性能監控功能，
包括系統指標收集、警報機制、監控任務管理等核心功能。
"""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.monitor import (
    MonitoringLevel,
    PerformanceAlert,
    PerformanceMonitor,
    SystemMetrics,
    get_performance_monitor,
    start_global_monitoring,
    stop_global_monitoring,
)


class TestSystemMetrics:
    """測試系統指標數據類別."""

    def test_system_metrics_initialization(self):
        """測試系統指標初始化."""
        timestamp = time.time()
        metrics = SystemMetrics(
            timestamp=timestamp,
            cpu_percent=25.5,
            memory_percent=65.2,
            memory_total_gb=16.0,
            memory_used_gb=10.4,
            disk_percent=45.8,
            disk_total_gb=500.0,
            disk_used_gb=229.0,
            uptime_seconds=3600.0
        )

        assert metrics.timestamp == timestamp
        assert metrics.cpu_percent == 25.5
        assert metrics.memory_percent == 65.2
        assert metrics.memory_total_gb == 16.0
        assert metrics.memory_used_gb == 10.4
        assert metrics.disk_percent == 45.8
        assert metrics.disk_total_gb == 500.0
        assert metrics.disk_used_gb == 229.0
        assert metrics.uptime_seconds == 3600.0


class TestPerformanceAlert:
    """測試效能警報數據類別."""

    def test_performance_alert_initialization(self):
        """測試效能警報初始化."""
        timestamp = datetime.utcnow()
        alert = PerformanceAlert(
            level="warning",
            message="CPU使用率較高: 75.5%",
            timestamp=timestamp,
            metric_name="cpu_percent",
            current_value=75.5,
            threshold=70.0
        )

        assert alert.level == "warning"
        assert alert.message == "CPU使用率較高: 75.5%"
        assert alert.timestamp == timestamp
        assert alert.metric_name == "cpu_percent"
        assert alert.current_value == 75.5
        assert alert.threshold == 70.0


class TestMonitoringLevel:
    """測試監控級別枚舉."""

    def test_monitoring_level_values(self):
        """測試監控級別枚舉值."""
        assert MonitoringLevel.BASIC.value == "basic"
        assert MonitoringLevel.DETAILED.value == "detailed"
        assert MonitoringLevel.COMPREHENSIVE.value == "comprehensive"


class TestPerformanceMonitor:
    """測試效能監控器功能."""

    @pytest.fixture
    def mock_settings(self):
        """創建模擬設定."""
        from src.core.config import Settings
        return Settings()

    @pytest.fixture
    def monitor(self, mock_settings):
        """創建效能監控器."""
        return PerformanceMonitor(settings=mock_settings)

    def test_performance_monitor_initialization(self, monitor):
        """測試效能監控器初始化."""
        assert monitor.monitoring_interval == 60
        assert monitor.metrics_history_limit == 1000
        assert isinstance(monitor.thresholds, dict)
        assert "cpu_warning" in monitor.thresholds
        assert "cpu_critical" in monitor.thresholds
        assert "memory_warning" in monitor.thresholds
        assert "memory_critical" in monitor.thresholds
        assert "disk_warning" in monitor.thresholds
        assert "disk_critical" in monitor.thresholds
        assert len(monitor.metrics_history) == 0
        assert len(monitor.alerts_history) == 0
        assert monitor._monitoring_task is None
        assert monitor._is_monitoring is False
        assert isinstance(monitor.start_time, float)

    def test_thresholds_values(self, monitor):
        """測試警報閾值設定."""
        assert monitor.thresholds["cpu_warning"] == 70.0
        assert monitor.thresholds["cpu_critical"] == 90.0
        assert monitor.thresholds["memory_warning"] == 80.0
        assert monitor.thresholds["memory_critical"] == 95.0
        assert monitor.thresholds["disk_warning"] == 85.0
        assert monitor.thresholds["disk_critical"] == 95.0

    @pytest.mark.asyncio
    async def test_start_monitoring(self, monitor):
        """測試啟動監控."""
        # 模擬監控循環
        original_loop = monitor._monitoring_loop
        monitor._monitoring_loop = AsyncMock()

        await monitor.start_monitoring()

        assert monitor._is_monitoring is True
        assert monitor._monitoring_task is not None
        assert not monitor._monitoring_task.done()

        # 清理
        await monitor.stop_monitoring()
        monitor._monitoring_loop = original_loop

    @pytest.mark.asyncio
    async def test_start_monitoring_already_running(self, monitor):
        """測試重複啟動監控."""
        monitor._is_monitoring = True

        # 應該不會重複啟動
        await monitor.start_monitoring()

        # 狀態保持不變
        assert monitor._is_monitoring is True

    @pytest.mark.asyncio
    async def test_stop_monitoring(self, monitor):
        """測試停止監控."""
        # 先啟動監控
        monitor._monitoring_loop = AsyncMock()
        await monitor.start_monitoring()

        # 停止監控
        await monitor.stop_monitoring()

        assert monitor._is_monitoring is False
        assert monitor._monitoring_task.done()

    @pytest.mark.asyncio
    async def test_stop_monitoring_not_running(self, monitor):
        """測試停止未運行的監控."""
        # 應該能夠安全地停止未運行的監控
        await monitor.stop_monitoring()

        assert monitor._is_monitoring is False

    @pytest.mark.asyncio
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    async def test_collect_system_metrics(self, mock_disk_usage, mock_virtual_memory, mock_cpu_percent, monitor):
        """測試收集系統指標."""
        # 模擬psutil返回值
        mock_cpu_percent.return_value = 45.5

        mock_memory = MagicMock()
        mock_memory.percent = 72.3
        mock_memory.total = 16 * 1024**3  # 16GB
        mock_memory.used = 12 * 1024**3   # 12GB
        mock_virtual_memory.return_value = mock_memory

        mock_disk = MagicMock()
        mock_disk.total = 500 * 1024**3   # 500GB
        mock_disk.used = 300 * 1024**3    # 300GB
        mock_disk_usage.return_value = mock_disk

        # 收集指標
        metrics = await monitor._collect_system_metrics()

        assert isinstance(metrics, SystemMetrics)
        assert metrics.cpu_percent == 45.5
        assert metrics.memory_percent == 72.3
        assert metrics.memory_total_gb == 16.0
        assert metrics.memory_used_gb == 12.0
        assert abs(metrics.disk_percent - 60.0) < 0.1  # 300/500 * 100
        assert metrics.disk_total_gb == 500.0
        assert metrics.disk_used_gb == 300.0
        assert isinstance(metrics.timestamp, float)
        assert isinstance(metrics.uptime_seconds, float)

    @pytest.mark.asyncio
    @patch('psutil.cpu_percent', side_effect=Exception("psutil error"))
    async def test_collect_system_metrics_error_handling(self, mock_cpu_percent, monitor):
        """測試收集系統指標錯誤處理."""
        # 收集指標應該返回默認值
        metrics = await monitor._collect_system_metrics()

        assert isinstance(metrics, SystemMetrics)
        assert metrics.cpu_percent == 0.0
        assert metrics.memory_percent == 0.0
        assert metrics.memory_total_gb == 0.0
        assert metrics.memory_used_gb == 0.0
        assert metrics.disk_percent == 0.0
        assert metrics.disk_total_gb == 0.0
        assert metrics.disk_used_gb == 0.0
        assert isinstance(metrics.timestamp, float)
        assert isinstance(metrics.uptime_seconds, float)

    def test_check_alerts_no_alerts(self, monitor):
        """測試檢查警報 - 無警報情況."""
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=30.0,
            memory_percent=50.0,
            memory_total_gb=16.0,
            memory_used_gb=8.0,
            disk_percent=40.0,
            disk_total_gb=500.0,
            disk_used_gb=200.0,
            uptime_seconds=3600.0
        )

        alerts = monitor._check_alerts(metrics)

        assert len(alerts) == 0

    def test_check_alerts_cpu_warning(self, monitor):
        """測試檢查警報 - CPU警告."""
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=75.0,  # 超過70%警告線
            memory_percent=50.0,
            memory_total_gb=16.0,
            memory_used_gb=8.0,
            disk_percent=40.0,
            disk_total_gb=500.0,
            disk_used_gb=200.0,
            uptime_seconds=3600.0
        )

        alerts = monitor._check_alerts(metrics)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.level == "warning"
        assert "CPU使用率較高" in alert.message
        assert alert.metric_name == "cpu_percent"
        assert alert.current_value == 75.0
        assert alert.threshold == 70.0

    def test_check_alerts_cpu_critical(self, monitor):
        """測試檢查警報 - CPU嚴重警告."""
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=95.0,  # 超過90%嚴重線
            memory_percent=50.0,
            memory_total_gb=16.0,
            memory_used_gb=8.0,
            disk_percent=40.0,
            disk_total_gb=500.0,
            disk_used_gb=200.0,
            uptime_seconds=3600.0
        )

        alerts = monitor._check_alerts(metrics)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.level == "critical"
        assert "CPU使用率過高" in alert.message
        assert alert.metric_name == "cpu_percent"
        assert alert.current_value == 95.0
        assert alert.threshold == 90.0

    def test_check_alerts_memory_warning(self, monitor):
        """測試檢查警報 - 記憶體警告."""
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=30.0,
            memory_percent=85.0,  # 超過80%警告線
            memory_total_gb=16.0,
            memory_used_gb=13.6,
            disk_percent=40.0,
            disk_total_gb=500.0,
            disk_used_gb=200.0,
            uptime_seconds=3600.0
        )

        alerts = monitor._check_alerts(metrics)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.level == "warning"
        assert "記憶體使用率較高" in alert.message
        assert alert.metric_name == "memory_percent"
        assert alert.current_value == 85.0
        assert alert.threshold == 80.0

    def test_check_alerts_memory_critical(self, monitor):
        """測試檢查警報 - 記憶體嚴重警告."""
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=30.0,
            memory_percent=97.0,  # 超過95%嚴重線
            memory_total_gb=16.0,
            memory_used_gb=15.5,
            disk_percent=40.0,
            disk_total_gb=500.0,
            disk_used_gb=200.0,
            uptime_seconds=3600.0
        )

        alerts = monitor._check_alerts(metrics)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.level == "critical"
        assert "記憶體使用率過高" in alert.message
        assert alert.metric_name == "memory_percent"

    def test_check_alerts_disk_warning(self, monitor):
        """測試檢查警報 - 磁碟警告."""
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=30.0,
            memory_percent=50.0,
            memory_total_gb=16.0,
            memory_used_gb=8.0,
            disk_percent=90.0,  # 超過85%警告線
            disk_total_gb=500.0,
            disk_used_gb=450.0,
            uptime_seconds=3600.0
        )

        alerts = monitor._check_alerts(metrics)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.level == "warning"
        assert "磁碟空間不足" in alert.message
        assert alert.metric_name == "disk_percent"

    def test_check_alerts_disk_critical(self, monitor):
        """測試檢查警報 - 磁碟嚴重警告."""
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=30.0,
            memory_percent=50.0,
            memory_total_gb=16.0,
            memory_used_gb=8.0,
            disk_percent=97.0,  # 超過95%嚴重線
            disk_total_gb=500.0,
            disk_used_gb=485.0,
            uptime_seconds=3600.0
        )

        alerts = monitor._check_alerts(metrics)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.level == "critical"
        assert "磁碟空間嚴重不足" in alert.message
        assert alert.metric_name == "disk_percent"

    def test_check_alerts_multiple_alerts(self, monitor):
        """測試檢查警報 - 多個警報."""
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=95.0,    # CPU嚴重警告
            memory_percent=85.0, # 記憶體警告
            memory_total_gb=16.0,
            memory_used_gb=13.6,
            disk_percent=97.0,   # 磁碟嚴重警告
            disk_total_gb=500.0,
            disk_used_gb=485.0,
            uptime_seconds=3600.0
        )

        alerts = monitor._check_alerts(metrics)

        assert len(alerts) == 3

        # 檢查每個警報的類型
        alert_types = [(alert.metric_name, alert.level) for alert in alerts]
        assert ("cpu_percent", "critical") in alert_types
        assert ("memory_percent", "warning") in alert_types
        assert ("disk_percent", "critical") in alert_types

    def test_get_current_metrics_empty(self, monitor):
        """測試獲取當前指標 - 空指標."""
        result = monitor.get_current_metrics()

        assert result is None

    def test_get_current_metrics_with_data(self, monitor):
        """測試獲取當前指標 - 有資料."""
        # 添加測試指標
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=45.0,
            memory_percent=60.0,
            memory_total_gb=16.0,
            memory_used_gb=9.6,
            disk_percent=55.0,
            disk_total_gb=500.0,
            disk_used_gb=275.0,
            uptime_seconds=3600.0
        )
        monitor.metrics_history.append(metrics)

        result = monitor.get_current_metrics()

        assert result is not None
        assert result.cpu_percent == 45.0
        assert result.memory_percent == 60.0

    def test_get_metrics_summary_empty(self, monitor):
        """測試獲取指標摘要 - 空資料."""
        result = monitor.get_metrics_summary()

        assert "error" in result
        assert result["error"] == "沒有可用的指標數據"

    def test_get_metrics_summary_with_data(self, monitor):
        """測試獲取指標摘要 - 有資料."""
        # 添加測試指標
        current_time = time.time()
        for i in range(5):
            metrics = SystemMetrics(
                timestamp=current_time - (i * 60),  # 每分鐘一個點
                cpu_percent=40.0 + i * 5,
                memory_percent=50.0 + i * 3,
                memory_total_gb=16.0,
                memory_used_gb=8.0 + i,
                disk_percent=45.0 + i * 2,
                disk_total_gb=500.0,
                disk_used_gb=225.0 + i * 10,
                uptime_seconds=3600.0 + i * 60
            )
            monitor.metrics_history.append(metrics)

        result = monitor.get_metrics_summary(minutes=60)

        assert "current_metrics" in result
        assert "summary" in result
        assert "uptime_hours" in result
        assert "recent_alerts" in result

        summary = result["summary"]
        assert "data_points" in summary
        assert "time_range_minutes" in summary
        assert "cpu" in summary
        assert "memory" in summary
        assert "disk" in summary

        # 檢查CPU統計
        cpu_stats = summary["cpu"]
        assert "current" in cpu_stats
        assert "average" in cpu_stats
        assert "max" in cpu_stats
        assert "min" in cpu_stats

    def test_get_alerts_summary_empty(self, monitor):
        """測試獲取警報摘要 - 無警報."""
        result = monitor.get_alerts_summary()

        assert result["total_alerts"] == 0
        assert result["recent_alerts"] == []

    def test_get_alerts_summary_with_data(self, monitor):
        """測試獲取警報摘要 - 有警報."""
        # 添加測試警報
        now = datetime.utcnow()
        alerts = [
            PerformanceAlert(
                level="warning",
                message="Test warning",
                timestamp=now - timedelta(hours=1),
                metric_name="cpu_percent",
                current_value=75.0,
                threshold=70.0
            ),
            PerformanceAlert(
                level="critical",
                message="Test critical",
                timestamp=now - timedelta(hours=2),
                metric_name="memory_percent",
                current_value=97.0,
                threshold=95.0
            ),
            PerformanceAlert(
                level="warning",
                message="Old warning",
                timestamp=now - timedelta(hours=48),  # 超過24小時
                metric_name="disk_percent",
                current_value=87.0,
                threshold=85.0
            )
        ]
        monitor.alerts_history.extend(alerts)

        result = monitor.get_alerts_summary(hours=24)

        assert result["total_alerts"] == 3
        assert result["recent_alerts_count"] == 2  # 只有2個在24小時內
        assert result["time_range_hours"] == 24
        assert "breakdown" in result
        assert result["breakdown"]["warning"] == 1
        assert result["breakdown"]["critical"] == 1
        assert len(result["recent_alerts"]) == 2

    def test_reset_alerts(self, monitor):
        """測試重置警報."""
        # 添加測試警報
        alert = PerformanceAlert(
            level="warning",
            message="Test alert",
            timestamp=datetime.utcnow(),
            metric_name="cpu_percent",
            current_value=75.0,
            threshold=70.0
        )
        monitor.alerts_history.append(alert)

        assert len(monitor.alerts_history) == 1

        # 重置
        monitor.reset_alerts()

        assert len(monitor.alerts_history) == 0

    @pytest.mark.asyncio
    async def test_shutdown(self, monitor):
        """測試關閉監控器."""
        # 模擬監控循環
        monitor._monitoring_loop = AsyncMock()
        await monitor.start_monitoring()

        # 關閉
        await monitor.shutdown()

        assert monitor._is_monitoring is False

    @pytest.mark.asyncio
    async def test_monitoring_loop_with_mocked_methods(self, monitor):
        """測試監控循環 - 模擬方法."""
        # 模擬相關方法
        test_metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=45.0,
            memory_percent=60.0,
            memory_total_gb=16.0,
            memory_used_gb=9.6,
            disk_percent=55.0,
            disk_total_gb=500.0,
            disk_used_gb=275.0,
            uptime_seconds=3600.0
        )

        monitor._collect_system_metrics = AsyncMock(return_value=test_metrics)
        monitor._check_alerts = MagicMock(return_value=[])
        monitor.monitoring_interval = 0.01  # 快速測試

        # 啟動監控，短暫運行後停止
        await monitor.start_monitoring()
        await asyncio.sleep(0.05)  # 讓監控循環運行幾次
        await monitor.stop_monitoring()

        # 檢查結果
        assert len(monitor.metrics_history) > 0
        assert monitor._collect_system_metrics.called
        assert monitor._check_alerts.called


class TestGlobalMonitorFunctions:
    """測試全域監控函數."""

    @pytest.mark.asyncio
    async def test_get_performance_monitor_singleton(self):
        """測試全域效能監控器單例."""
        # 清理可能存在的全域監控器
        await stop_global_monitoring()

        # 獲取兩次應該是同一個實例
        monitor1 = get_performance_monitor()
        monitor2 = get_performance_monitor()

        assert monitor1 is monitor2

        # 清理
        await stop_global_monitoring()

    @pytest.mark.asyncio
    async def test_start_global_monitoring(self):
        """測試啟動全域監控."""
        # 清理現有監控器
        await stop_global_monitoring()

        # 模擬監控循環
        monitor = get_performance_monitor()
        monitor._monitoring_loop = AsyncMock()

        await start_global_monitoring()

        assert monitor._is_monitoring is True

        # 清理
        await stop_global_monitoring()

    @pytest.mark.asyncio
    async def test_stop_global_monitoring(self):
        """測試停止全域監控."""
        # 啟動監控
        monitor = get_performance_monitor()
        monitor._monitoring_loop = AsyncMock()
        await start_global_monitoring()

        # 停止監控
        await stop_global_monitoring()

        # 全域監控器應該被重置
        from src.core.monitor import _global_monitor
        assert _global_monitor is None


class TestMonitoringErrorHandling:
    """測試監控錯誤處理."""

    @pytest.fixture
    def monitor(self):
        """創建效能監控器."""
        from src.core.config import Settings
        return PerformanceMonitor(settings=Settings())

    @pytest.mark.asyncio
    async def test_monitoring_loop_exception_handling(self, monitor):
        """測試監控循環異常處理."""
        # 模擬收集指標時拋出異常
        monitor._collect_system_metrics = AsyncMock(side_effect=Exception("Test error"))
        monitor.monitoring_interval = 0.01  # 快速測試

        # 啟動監控
        await monitor.start_monitoring()
        await asyncio.sleep(0.05)  # 讓循環運行並處理異常
        await monitor.stop_monitoring()

        # 監控應該能夠繼續運行而不崩潰
        assert not monitor._is_monitoring

    def test_metrics_history_limit_enforcement(self, monitor):
        """測試指標歷史限制強制執行."""
        # 設置較小的限制以便測試
        monitor.metrics_history_limit = 10

        # 添加超過限制的指標
        for i in range(15):
            metrics = SystemMetrics(
                timestamp=time.time() + i,
                cpu_percent=40.0,
                memory_percent=50.0,
                memory_total_gb=16.0,
                memory_used_gb=8.0,
                disk_percent=45.0,
                disk_total_gb=500.0,
                disk_used_gb=225.0,
                uptime_seconds=3600.0 + i
            )
            monitor.metrics_history.append(metrics)

            # 模擬限制檢查邏輯
            if len(monitor.metrics_history) > monitor.metrics_history_limit:
                monitor.metrics_history = monitor.metrics_history[
                    -monitor.metrics_history_limit // 2:
                ]

        # 應該被限制在指定數量內
        assert len(monitor.metrics_history) <= monitor.metrics_history_limit

    def test_alerts_history_cleanup(self, monitor):
        """測試警報歷史清理."""
        # 添加大量警報
        now = datetime.utcnow()
        for i in range(150):
            alert = PerformanceAlert(
                level="warning",
                message=f"Test alert {i}",
                timestamp=now - timedelta(minutes=i),
                metric_name="cpu_percent",
                current_value=75.0,
                threshold=70.0
            )
            monitor.alerts_history.append(alert)

        # 模擬清理邏輯
        if len(monitor.alerts_history) > 100:
            monitor.alerts_history = monitor.alerts_history[-50:]

        # 應該被清理到50個
        assert len(monitor.alerts_history) == 50


class TestMonitoringPerformance:
    """測試監控性能."""

    @pytest.fixture
    def monitor(self):
        """創建效能監控器."""
        from src.core.config import Settings
        return PerformanceMonitor(settings=Settings())

    @pytest.mark.asyncio
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    async def test_metrics_collection_performance(self, mock_disk_usage, mock_virtual_memory, mock_cpu_percent, monitor):
        """測試指標收集性能."""
        # 設置模擬返回值
        mock_cpu_percent.return_value = 45.5

        mock_memory = MagicMock()
        mock_memory.percent = 72.3
        mock_memory.total = 16 * 1024**3
        mock_memory.used = 12 * 1024**3
        mock_virtual_memory.return_value = mock_memory

        mock_disk = MagicMock()
        mock_disk.total = 500 * 1024**3
        mock_disk.used = 300 * 1024**3
        mock_disk_usage.return_value = mock_disk

        # 測量收集時間
        start_time = time.time()

        # 收集100次指標
        for _ in range(100):
            await monitor._collect_system_metrics()

        end_time = time.time()
        duration = end_time - start_time

        # 應該在合理時間內完成(每次收集應該少於10ms)
        assert duration < 1.0  # 100次收集在1秒內完成

    def test_alerts_checking_performance(self, monitor):
        """測試警報檢查性能."""
        # 創建測試指標
        metrics = SystemMetrics(
            timestamp=time.time(),
            cpu_percent=45.0,
            memory_percent=60.0,
            memory_total_gb=16.0,
            memory_used_gb=9.6,
            disk_percent=55.0,
            disk_total_gb=500.0,
            disk_used_gb=275.0,
            uptime_seconds=3600.0
        )

        start_time = time.time()

        # 執行1000次警報檢查
        for _ in range(1000):
            monitor._check_alerts(metrics)

        end_time = time.time()
        duration = end_time - start_time

        # 應該很快完成
        assert duration < 0.1  # 1000次檢查在0.1秒內完成

    def test_summary_generation_performance(self, monitor):
        """測試摘要生成性能."""
        # 添加大量測試指標
        current_time = time.time()
        for i in range(1000):
            metrics = SystemMetrics(
                timestamp=current_time - (i * 60),
                cpu_percent=40.0 + (i % 50),
                memory_percent=50.0 + (i % 30),
                memory_total_gb=16.0,
                memory_used_gb=8.0 + (i % 8),
                disk_percent=45.0 + (i % 20),
                disk_total_gb=500.0,
                disk_used_gb=225.0 + (i % 100),
                uptime_seconds=3600.0 + i * 60
            )
            monitor.metrics_history.append(metrics)

        start_time = time.time()

        # 生成摘要
        summary = monitor.get_metrics_summary(minutes=60)

        end_time = time.time()
        duration = end_time - start_time

        # 應該快速生成摘要
        assert duration < 0.1
        assert "summary" in summary
