"""
Discord ROAS Bot - 性能監控系統
按照DESIGN-M001-A整合performance_dashboard功能
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import psutil

from src.core.config import Settings, get_settings
from src.core.logger import get_logger


class MonitoringLevel(Enum):
    """監控級別枚舉"""

    BASIC = "basic"
    DETAILED = "detailed"
    COMPREHENSIVE = "comprehensive"


@dataclass
class SystemMetrics:
    """系統指標"""

    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_total_gb: float
    memory_used_gb: float
    disk_percent: float
    disk_total_gb: float
    disk_used_gb: float
    uptime_seconds: float


@dataclass
class PerformanceAlert:
    """性能警報"""

    level: str  # warning, critical
    message: str
    timestamp: datetime
    metric_name: str
    current_value: float
    threshold: float


class PerformanceMonitor:
    """性能監控器 - 整合自performance_dashboard"""

    def __init__(self, settings: Settings | None = None):
        """初始化性能監控器"""
        self.settings = settings or get_settings()
        self.logger = get_logger("performance_monitor", self.settings)

        # 監控配置
        self.monitoring_interval = 60  # 60秒監控間隔
        self.metrics_history_limit = 1000  # 保留1000個歷史記錄

        # 警報閾值
        self.thresholds = {
            "cpu_warning": 70.0,
            "cpu_critical": 90.0,
            "memory_warning": 80.0,
            "memory_critical": 95.0,
            "disk_warning": 85.0,
            "disk_critical": 95.0,
        }

        # 監控數據存儲
        self.metrics_history: list[SystemMetrics] = []
        self.alerts_history: list[PerformanceAlert] = []

        # 監控任務
        self._monitoring_task: asyncio.Task | None = None
        self._is_monitoring = False

        # 啟動時間
        self.start_time = time.time()

    async def start_monitoring(self) -> None:
        """啟動性能監控"""
        if self._is_monitoring:
            self.logger.warning("性能監控已經在運行")
            return

        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("性能監控已啟動")

    async def stop_monitoring(self) -> None:
        """停止性能監控"""
        if not self._is_monitoring:
            return

        self._is_monitoring = False
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitoring_task

        self.logger.info("性能監控已停止")

    async def _monitoring_loop(self) -> None:
        """監控循環"""
        while self._is_monitoring:
            try:
                # 收集系統指標
                metrics = await self._collect_system_metrics()

                # 存儲指標
                self.metrics_history.append(metrics)

                # 限制歷史記錄數量
                if len(self.metrics_history) > self.metrics_history_limit:
                    self.metrics_history = self.metrics_history[
                        -self.metrics_history_limit // 2 :
                    ]

                # 檢查警報
                alerts = self._check_alerts(metrics)
                if alerts:
                    self.alerts_history.extend(alerts)
                    for alert in alerts:
                        if alert.level == "critical":
                            self.logger.critical(f"性能警報: {alert.message}")
                        else:
                            self.logger.warning(f"性能警報: {alert.message}")

                # 清理舊警報
                if len(self.alerts_history) > 100:
                    self.alerts_history = self.alerts_history[-50:]

                await asyncio.sleep(self.monitoring_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"監控循環發生錯誤: {e}")
                await asyncio.sleep(10)  # 錯誤時短暫休息

    async def _collect_system_metrics(self) -> SystemMetrics:
        """收集系統指標"""
        try:
            # CPU 使用率
            cpu_percent = psutil.cpu_percent(interval=0.1)

            # 記憶體使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_total_gb = memory.total / (1024**3)
            memory_used_gb = memory.used / (1024**3)

            # 磁碟使用率
            disk_usage = psutil.disk_usage("/")
            disk_percent = (disk_usage.used / disk_usage.total) * 100
            disk_total_gb = disk_usage.total / (1024**3)
            disk_used_gb = disk_usage.used / (1024**3)

            # 運行時間
            uptime_seconds = time.time() - self.start_time

            return SystemMetrics(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_total_gb=round(memory_total_gb, 2),
                memory_used_gb=round(memory_used_gb, 2),
                disk_percent=round(disk_percent, 1),
                disk_total_gb=round(disk_total_gb, 2),
                disk_used_gb=round(disk_used_gb, 2),
                uptime_seconds=uptime_seconds,
            )

        except Exception as e:
            self.logger.error(f"收集系統指標失敗: {e}")
            # 返回默認值
            return SystemMetrics(
                timestamp=time.time(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_total_gb=0.0,
                memory_used_gb=0.0,
                disk_percent=0.0,
                disk_total_gb=0.0,
                disk_used_gb=0.0,
                uptime_seconds=time.time() - self.start_time,
            )

    def _check_alerts(self, metrics: SystemMetrics) -> list[PerformanceAlert]:
        """檢查性能警報"""
        alerts = []
        now = datetime.utcnow()

        # CPU 警報
        if metrics.cpu_percent >= self.thresholds["cpu_critical"]:
            alerts.append(
                PerformanceAlert(
                    level="critical",
                    message=f"CPU使用率過高: {metrics.cpu_percent:.1f}%",
                    timestamp=now,
                    metric_name="cpu_percent",
                    current_value=metrics.cpu_percent,
                    threshold=self.thresholds["cpu_critical"],
                )
            )
        elif metrics.cpu_percent >= self.thresholds["cpu_warning"]:
            alerts.append(
                PerformanceAlert(
                    level="warning",
                    message=f"CPU使用率較高: {metrics.cpu_percent:.1f}%",
                    timestamp=now,
                    metric_name="cpu_percent",
                    current_value=metrics.cpu_percent,
                    threshold=self.thresholds["cpu_warning"],
                )
            )

        # 記憶體警報
        if metrics.memory_percent >= self.thresholds["memory_critical"]:
            alerts.append(
                PerformanceAlert(
                    level="critical",
                    message=f"記憶體使用率過高: {metrics.memory_percent:.1f}%",
                    timestamp=now,
                    metric_name="memory_percent",
                    current_value=metrics.memory_percent,
                    threshold=self.thresholds["memory_critical"],
                )
            )
        elif metrics.memory_percent >= self.thresholds["memory_warning"]:
            alerts.append(
                PerformanceAlert(
                    level="warning",
                    message=f"記憶體使用率較高: {metrics.memory_percent:.1f}%",
                    timestamp=now,
                    metric_name="memory_percent",
                    current_value=metrics.memory_percent,
                    threshold=self.thresholds["memory_warning"],
                )
            )

        # 磁碟警報
        if metrics.disk_percent >= self.thresholds["disk_critical"]:
            alerts.append(
                PerformanceAlert(
                    level="critical",
                    message=f"磁碟空間嚴重不足: {metrics.disk_percent:.1f}%",
                    timestamp=now,
                    metric_name="disk_percent",
                    current_value=metrics.disk_percent,
                    threshold=self.thresholds["disk_critical"],
                )
            )
        elif metrics.disk_percent >= self.thresholds["disk_warning"]:
            alerts.append(
                PerformanceAlert(
                    level="warning",
                    message=f"磁碟空間不足: {metrics.disk_percent:.1f}%",
                    timestamp=now,
                    metric_name="disk_percent",
                    current_value=metrics.disk_percent,
                    threshold=self.thresholds["disk_warning"],
                )
            )

        return alerts

    def get_current_metrics(self) -> SystemMetrics | None:
        """獲取當前系統指標"""
        if self.metrics_history:
            return self.metrics_history[-1]
        return None

    def get_metrics_summary(self, minutes: int = 60) -> dict[str, Any]:
        """獲取指標摘要"""
        if not self.metrics_history:
            return {"error": "沒有可用的指標數據"}

        # 獲取指定時間範圍內的指標
        cutoff_time = time.time() - (minutes * 60)
        recent_metrics = [m for m in self.metrics_history if m.timestamp >= cutoff_time]

        if not recent_metrics:
            recent_metrics = self.metrics_history[-10:]  # 至少取最近10條

        # 計算統計值
        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [m.memory_percent for m in recent_metrics]
        disk_values = [m.disk_percent for m in recent_metrics]

        current = recent_metrics[-1] if recent_metrics else None

        return {
            "current_metrics": asdict(current) if current else None,
            "summary": {
                "data_points": len(recent_metrics),
                "time_range_minutes": minutes,
                "cpu": {
                    "current": current.cpu_percent if current else 0,
                    "average": sum(cpu_values) / len(cpu_values) if cpu_values else 0,
                    "max": max(cpu_values) if cpu_values else 0,
                    "min": min(cpu_values) if cpu_values else 0,
                },
                "memory": {
                    "current": current.memory_percent if current else 0,
                    "average": sum(memory_values) / len(memory_values)
                    if memory_values
                    else 0,
                    "max": max(memory_values) if memory_values else 0,
                    "min": min(memory_values) if memory_values else 0,
                    "total_gb": current.memory_total_gb if current else 0,
                },
                "disk": {
                    "current": current.disk_percent if current else 0,
                    "average": sum(disk_values) / len(disk_values)
                    if disk_values
                    else 0,
                    "max": max(disk_values) if disk_values else 0,
                    "min": min(disk_values) if disk_values else 0,
                    "total_gb": current.disk_total_gb if current else 0,
                },
            },
            "uptime_hours": (current.uptime_seconds / 3600) if current else 0,
            "recent_alerts": len(
                [
                    a
                    for a in self.alerts_history
                    if (datetime.utcnow() - a.timestamp).total_seconds() < minutes * 60
                ]
            ),
        }

    def get_alerts_summary(self, hours: int = 24) -> dict[str, Any]:
        """獲取警報摘要"""
        if not self.alerts_history:
            return {"total_alerts": 0, "recent_alerts": []}

        # 獲取指定時間範圍內的警報
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_alerts = [a for a in self.alerts_history if a.timestamp >= cutoff_time]

        # 按級別分類
        warning_alerts = [a for a in recent_alerts if a.level == "warning"]
        critical_alerts = [a for a in recent_alerts if a.level == "critical"]

        return {
            "total_alerts": len(self.alerts_history),
            "recent_alerts_count": len(recent_alerts),
            "time_range_hours": hours,
            "breakdown": {
                "warning": len(warning_alerts),
                "critical": len(critical_alerts),
            },
            "recent_alerts": [
                {
                    "level": a.level,
                    "message": a.message,
                    "timestamp": a.timestamp.isoformat(),
                    "metric_name": a.metric_name,
                    "current_value": a.current_value,
                    "threshold": a.threshold,
                }
                for a in recent_alerts[-10:]  # 最近10個警報
            ],
        }

    def reset_alerts(self) -> None:
        """重置警報歷史"""
        self.alerts_history.clear()
        self.logger.info("性能警報歷史已重置")

    async def shutdown(self) -> None:
        """關閉監控器"""
        await self.stop_monitoring()
        self.logger.info("性能監控器已關閉")


# 全域監控器實例
_global_monitor: PerformanceMonitor | None = None


def get_performance_monitor() -> PerformanceMonitor:
    """獲取全域性能監控器實例"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor


async def start_global_monitoring() -> None:
    """啟動全域性能監控"""
    monitor = get_performance_monitor()
    await monitor.start_monitoring()


async def stop_global_monitoring() -> None:
    """停止全域性能監控"""
    global _global_monitor
    if _global_monitor:
        await _global_monitor.shutdown()
        _global_monitor = None


__all__ = [
    "MonitoringLevel",
    "PerformanceAlert",
    "PerformanceMonitor",
    "SystemMetrics",
    "get_performance_monitor",
    "start_global_monitoring",
    "stop_global_monitoring",
]
