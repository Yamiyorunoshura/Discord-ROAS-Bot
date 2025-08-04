"""成就系統效能監控器.

此模組擴展現有的 PerformanceMonitor,專門監控成就系統的效能指標:
- 查詢執行時間監控
- 資料庫連線狀態追蹤
- 快取效能監控
- 記憶體使用量追蹤
- 自動警報機制

根據 Story 5.1 Task 1.5 和 Task 5 的要求實作.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

from src.core.monitor import PerformanceAlert, PerformanceMonitor

if TYPE_CHECKING:
    from .cache_manager import CacheManager, CacheType

logger = logging.getLogger(__name__)

class MetricType(str, Enum):
    """指標類型."""

    QUERY_TIME = "query_time"
    CACHE_HIT_RATE = "cache_hit_rate"
    MEMORY_USAGE = "memory_usage"
    DATABASE_CONNECTIONS = "database_connections"
    ERROR_RATE = "error_rate"

# 效能監控常數
CRITICAL_CONNECTION_USAGE_THRESHOLD = 0.9  # 90%
WARNING_CONNECTION_USAGE_THRESHOLD = 0.7   # 70%
CRITICAL_RESPONSE_TIME_MS = 500
WARNING_RESPONSE_TIME_MS = 200
CRITICAL_SLOW_QUERY_RATE = 0.3
WARNING_SLOW_QUERY_RATE = 0.1
CRITICAL_ERROR_RATE = 0.1
WARNING_ERROR_RATE = 0.05

# 健康狀態閾值
EXCELLENT_HEALTH_SCORE = 90
GOOD_HEALTH_SCORE = 75
FAIR_HEALTH_SCORE = 60
POOR_HEALTH_SCORE = 40

@dataclass
class AchievementMetric:
    """成就系統效能指標."""

    metric_type: MetricType
    """指標類型"""

    value: float
    """指標值"""

    timestamp: datetime = field(default_factory=datetime.now)
    """記錄時間"""

    context: dict[str, Any] = field(default_factory=dict)
    """上下文資訊"""

    operation: str | None = None
    """操作名稱"""

    user_id: int | None = None
    """相關用戶 ID"""

@dataclass
class QueryMetrics:
    """查詢指標統計."""

    total_queries: int = 0
    slow_queries: int = 0
    failed_queries: int = 0
    avg_response_time: float = 0.0
    max_response_time: float = 0.0
    min_response_time: float = float("inf")
    last_reset: datetime = field(default_factory=datetime.now)

class AchievementPerformanceMonitor(PerformanceMonitor):
    """成就系統效能監控器.

    擴展基礎 PerformanceMonitor,增加成就系統特定的監控功能.
    """

    def __init__(
        self,
        cache_manager: CacheManager | None = None,
        slow_query_threshold: float = 200.0,  # 200ms
        memory_threshold_mb: float = 100.0,
        enable_detailed_logging: bool = True,
    ):
        """初始化成就系統效能監控器.

        Args:
            cache_manager: 快取管理器
            slow_query_threshold: 慢查詢門檻(毫秒)
            memory_threshold_mb: 記憶體使用門檻(MB)
            enable_detailed_logging: 是否啟用詳細日誌
        """
        super().__init__()

        self._cache_manager = cache_manager
        self._slow_query_threshold = slow_query_threshold
        self._memory_threshold_mb = memory_threshold_mb
        self._enable_detailed_logging = enable_detailed_logging

        # 成就系統特定的指標
        self._metrics_history: list[AchievementMetric] = []
        self._query_metrics = QueryMetrics()

        # 效能警報配置
        self._achievement_thresholds = {
            "query_time_warning": 200.0,  # ms
            "query_time_critical": 500.0,  # ms
            "cache_hit_rate_warning": 0.7,  # 70%
            "cache_hit_rate_critical": 0.5,  # 50%
            "memory_usage_warning": 80.0,  # MB
            "memory_usage_critical": 100.0,  # MB
            "error_rate_warning": 0.05,  # 5%
            "error_rate_critical": 0.10,  # 10%
        }

        # 監控任務
        self._monitoring_task: asyncio.Task | None = None
        self._is_monitoring = False

        logger.info(
            "AchievementPerformanceMonitor 初始化完成",
            extra={
                "slow_query_threshold": slow_query_threshold,
                "memory_threshold": memory_threshold_mb,
                "detailed_logging": enable_detailed_logging,
            },
        )

    # =============================================================================
    # 查詢效能監控
    # =============================================================================

    async def track_query_operation(
        self,
        operation: str,
        duration_ms: float,
        success: bool = True,
        user_id: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """追蹤查詢操作效能.

        Args:
            operation: 操作名稱
            duration_ms: 執行時間(毫秒)
            success: 是否成功
            user_id: 相關用戶 ID
            context: 上下文資訊
        """
        # 更新查詢統計
        self._query_metrics.total_queries += 1

        if success:
            # 更新回應時間統計
            if self._query_metrics.total_queries == 1:
                self._query_metrics.avg_response_time = duration_ms
                self._query_metrics.min_response_time = duration_ms
            else:
                # 計算新的平均時間
                total = self._query_metrics.total_queries
                current_avg = self._query_metrics.avg_response_time
                new_avg = ((current_avg * (total - 1)) + duration_ms) / total
                self._query_metrics.avg_response_time = new_avg

            # 更新最大和最小時間
            self._query_metrics.max_response_time = max(
                self._query_metrics.max_response_time, duration_ms
            )
            self._query_metrics.min_response_time = min(
                self._query_metrics.min_response_time, duration_ms
            )

            # 檢查是否為慢查詢
            if duration_ms >= self._slow_query_threshold:
                self._query_metrics.slow_queries += 1

                # 記錄慢查詢警報
                SLOW_QUERY_THRESHOLD = 500
                await self._create_performance_alert(
                    "warning" if duration_ms < SLOW_QUERY_THRESHOLD else "critical",
                    f"慢查詢檢測: {operation} 執行時間 {duration_ms:.1f}ms",
                    MetricType.QUERY_TIME,
                    duration_ms,
                    self._slow_query_threshold,
                )

                if self._enable_detailed_logging:
                    logger.warning(
                        f"慢查詢檢測: {operation}",
                        extra={
                            "operation": operation,
                            "duration_ms": duration_ms,
                            "user_id": user_id,
                            "context": context or {},
                        },
                    )
        else:
            # 查詢失敗
            self._query_metrics.failed_queries += 1

            if self._enable_detailed_logging:
                logger.error(
                    f"查詢失敗: {operation}",
                    extra={
                        "operation": operation,
                        "duration_ms": duration_ms,
                        "user_id": user_id,
                        "context": context or {},
                    },
                )

        # 記錄指標
        metric = AchievementMetric(
            metric_type=MetricType.QUERY_TIME,
            value=duration_ms,
            operation=operation,
            user_id=user_id,
            context=context or {},
        )
        self._metrics_history.append(metric)

        # 限制歷史記錄數量
        MAX_METRICS_HISTORY = 10000
        TRIM_METRICS_TO = 5000
        if len(self._metrics_history) > MAX_METRICS_HISTORY:
            self._metrics_history = self._metrics_history[-TRIM_METRICS_TO:]

    async def track_cache_operation(
        self,
        cache_type: CacheType,
        operation: str,
        hit: bool,
        duration_ms: float | None = None,
    ) -> None:
        """追蹤快取操作效能.

        Args:
            cache_type: 快取類型
            operation: 操作名稱
            hit: 是否命中
            duration_ms: 執行時間(可選)
        """
        # 記錄快取指標
        metric = AchievementMetric(
            metric_type=MetricType.CACHE_HIT_RATE,
            value=1.0 if hit else 0.0,
            operation=f"{cache_type.value}_{operation}",
            context={
                "cache_type": cache_type.value,
                "hit": hit,
                "duration_ms": duration_ms,
            },
        )
        self._metrics_history.append(metric)

        if self._enable_detailed_logging:
            logger.debug(
                f"快取操作: {cache_type.value} {operation}",
                extra={
                    "cache_type": cache_type.value,
                    "operation": operation,
                    "hit": hit,
                    "duration_ms": duration_ms,
                },
            )

    async def track_memory_usage(self, usage_mb: float, context: str = "") -> None:
        """追蹤記憶體使用量.

        Args:
            usage_mb: 記憶體使用量(MB)
            context: 上下文描述
        """
        # 記錄記憶體指標
        metric = AchievementMetric(
            metric_type=MetricType.MEMORY_USAGE,
            value=usage_mb,
            context={"context": context},
        )
        self._metrics_history.append(metric)

        # 檢查記憶體使用警報
        if usage_mb >= self._achievement_thresholds["memory_usage_critical"]:
            await self._create_performance_alert(
                "critical",
                f"記憶體使用量過高: {usage_mb:.1f}MB ({context})",
                MetricType.MEMORY_USAGE,
                usage_mb,
                self._achievement_thresholds["memory_usage_critical"],
            )
        elif usage_mb >= self._achievement_thresholds["memory_usage_warning"]:
            await self._create_performance_alert(
                "warning",
                f"記憶體使用量較高: {usage_mb:.1f}MB ({context})",
                MetricType.MEMORY_USAGE,
                usage_mb,
                self._achievement_thresholds["memory_usage_warning"],
            )

    async def track_database_connections(
        self, active_connections: int, max_connections: int
    ) -> None:
        """追蹤資料庫連線狀態.

        Args:
            active_connections: 活躍連線數
            max_connections: 最大連線數
        """
        connection_usage_rate = active_connections / max(max_connections, 1)

        # 記錄連線指標
        metric = AchievementMetric(
            metric_type=MetricType.DATABASE_CONNECTIONS,
            value=connection_usage_rate,
            context={
                "active_connections": active_connections,
                "max_connections": max_connections,
                "usage_rate": connection_usage_rate,
            },
        )
        self._metrics_history.append(metric)

        # 檢查連線使用率警報
        if connection_usage_rate >= CRITICAL_CONNECTION_USAGE_THRESHOLD:
            await self._create_performance_alert(
                "critical",
                f"資料庫連線使用率過高: {connection_usage_rate:.1%} ({active_connections}/{max_connections})",
                MetricType.DATABASE_CONNECTIONS,
                connection_usage_rate,
                CRITICAL_CONNECTION_USAGE_THRESHOLD,
            )
        elif connection_usage_rate >= WARNING_CONNECTION_USAGE_THRESHOLD:
            await self._create_performance_alert(
                "warning",
                f"資料庫連線使用率較高: {connection_usage_rate:.1%} ({active_connections}/{max_connections})",
                MetricType.DATABASE_CONNECTIONS,
                connection_usage_rate,
                WARNING_CONNECTION_USAGE_THRESHOLD,
            )

    # =============================================================================
    # 監控分析和報告
    # =============================================================================

    def get_achievement_metrics_summary(self, minutes: int = 60) -> dict[str, Any]:
        """取得成就系統指標摘要.

        Args:
            minutes: 時間範圍(分鐘)

        Returns:
            指標摘要資訊
        """
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        recent_metrics = [
            m for m in self._metrics_history if m.timestamp >= cutoff_time
        ]

        if not recent_metrics:
            return {"error": "沒有可用的指標資料"}

        # 按類型分組指標
        metrics_by_type = {}
        for metric in recent_metrics:
            metric_type = metric.metric_type
            if metric_type not in metrics_by_type:
                metrics_by_type[metric_type] = []
            metrics_by_type[metric_type].append(metric)

        summary = {
            "time_range_minutes": minutes,
            "total_metrics": len(recent_metrics),
            "metrics_by_type": {},
        }

        # 分析每種類型的指標
        for metric_type, metrics in metrics_by_type.items():
            values = [m.value for m in metrics]

            if metric_type == MetricType.QUERY_TIME:
                summary["metrics_by_type"][metric_type.value] = {
                    "count": len(values),
                    "avg_ms": sum(values) / len(values),
                    "max_ms": max(values),
                    "min_ms": min(values),
                    "slow_queries": len(
                        [v for v in values if v >= self._slow_query_threshold]
                    ),
                }
            elif metric_type == MetricType.CACHE_HIT_RATE:
                hit_rate = sum(values) / len(values) if values else 0
                summary["metrics_by_type"][metric_type.value] = {
                    "count": len(values),
                    "hit_rate": hit_rate,
                    "hits": sum(values),
                    "total_requests": len(values),
                }
            elif metric_type == MetricType.MEMORY_USAGE:
                summary["metrics_by_type"][metric_type.value] = {
                    "count": len(values),
                    "avg_mb": sum(values) / len(values),
                    "max_mb": max(values),
                    "current_mb": values[-1] if values else 0,
                }
            else:
                summary["metrics_by_type"][metric_type.value] = {
                    "count": len(values),
                    "avg": sum(values) / len(values),
                    "max": max(values),
                    "min": min(values),
                }

        # 添加查詢統計
        summary["query_stats"] = {
            "total_queries": self._query_metrics.total_queries,
            "slow_queries": self._query_metrics.slow_queries,
            "failed_queries": self._query_metrics.failed_queries,
            "avg_response_time": self._query_metrics.avg_response_time,
            "max_response_time": self._query_metrics.max_response_time,
            "min_response_time": self._query_metrics.min_response_time,
            "slow_query_rate": (
                self._query_metrics.slow_queries
                / max(self._query_metrics.total_queries, 1)
            ),
            "error_rate": (
                self._query_metrics.failed_queries
                / max(self._query_metrics.total_queries, 1)
            ),
        }

        if self._cache_manager:
            cache_stats = self._cache_manager.get_stats()
            summary["cache_stats"] = cache_stats

        return summary

    def get_query_performance_report(self) -> dict[str, Any]:
        """取得查詢效能報告."""
        return {
            "query_metrics": {
                "total_queries": self._query_metrics.total_queries,
                "slow_queries": self._query_metrics.slow_queries,
                "failed_queries": self._query_metrics.failed_queries,
                "avg_response_time_ms": round(self._query_metrics.avg_response_time, 2),
                "max_response_time_ms": round(self._query_metrics.max_response_time, 2),
                "min_response_time_ms": round(self._query_metrics.min_response_time, 2),
                "slow_query_rate": round(
                    self._query_metrics.slow_queries
                    / max(self._query_metrics.total_queries, 1),
                    4,
                ),
                "error_rate": round(
                    self._query_metrics.failed_queries
                    / max(self._query_metrics.total_queries, 1),
                    4,
                ),
                "last_reset": self._query_metrics.last_reset.isoformat(),
            },
            "thresholds": {
                "slow_query_threshold_ms": self._slow_query_threshold,
                "memory_threshold_mb": self._memory_threshold_mb,
            },
            "health_status": self._calculate_health_status(),
        }

    def _calculate_health_status(self) -> str:
        """計算系統健康狀態."""
        # 基於多個指標計算整體健康狀態
        slow_query_rate = self._query_metrics.slow_queries / max(
            self._query_metrics.total_queries, 1
        )
        error_rate = self._query_metrics.failed_queries / max(
            self._query_metrics.total_queries, 1
        )
        avg_response_time = self._query_metrics.avg_response_time

        health_score = 100

        # 回應時間影響
        if avg_response_time > CRITICAL_RESPONSE_TIME_MS:
            health_score -= 30
        elif avg_response_time > WARNING_RESPONSE_TIME_MS:
            health_score -= 15

        # 慢查詢率影響
        if slow_query_rate > CRITICAL_SLOW_QUERY_RATE:
            health_score -= 25
        elif slow_query_rate > WARNING_SLOW_QUERY_RATE:
            health_score -= 10

        # 錯誤率影響
        if error_rate > CRITICAL_ERROR_RATE:
            health_score -= 20
        elif error_rate > WARNING_ERROR_RATE:
            health_score -= 10

        # 返回健康狀態
        if health_score >= EXCELLENT_HEALTH_SCORE:
            return "excellent"
        elif health_score >= GOOD_HEALTH_SCORE:
            return "good"
        elif health_score >= FAIR_HEALTH_SCORE:
            return "fair"
        elif health_score >= POOR_HEALTH_SCORE:
            return "poor"
        else:
            return "critical"

    # =============================================================================
    # 警報系統
    # =============================================================================

    async def _create_performance_alert(
        self,
        level: str,
        message: str,
        metric_type: MetricType,
        current_value: float,
        threshold: float,
    ) -> None:
        """建立效能警報."""
        alert = PerformanceAlert(
            level=level,
            message=message,
            timestamp=datetime.now(),
            metric_name=metric_type.value,
            current_value=current_value,
            threshold=threshold,
        )

        # 添加到警報歷史
        self.alerts_history.append(alert)

        # 記錄日誌
        if level == "critical":
            logger.critical(f"成就系統效能警報: {message}")
        else:
            logger.warning(f"成就系統效能警報: {message}")

    # =============================================================================
    # 監控控制
    # =============================================================================

    async def start_achievement_monitoring(self) -> None:
        """啟動成就系統效能監控."""
        if not self._is_monitoring:
            self._is_monitoring = True
            self._monitoring_task = asyncio.create_task(
                self._achievement_monitoring_loop()
            )
            logger.info("成就系統效能監控已啟動")

    async def stop_achievement_monitoring(self) -> None:
        """停止成就系統效能監控."""
        if self._is_monitoring:
            self._is_monitoring = False
            if self._monitoring_task and not self._monitoring_task.done():
                self._monitoring_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._monitoring_task
            logger.info("成就系統效能監控已停止")

    async def _achievement_monitoring_loop(self) -> None:
        """成就系統監控循環."""
        while self._is_monitoring:
            try:
                # 檢查快取效能
                if self._cache_manager:
                    await self._monitor_cache_performance()

                # 檢查錯誤率
                await self._monitor_error_rate()

                await asyncio.sleep(60)  # 每分鐘檢查一次

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"成就系統監控循環錯誤: {e}", exc_info=True)
                await asyncio.sleep(30)

    async def _monitor_cache_performance(self) -> None:
        """監控快取效能."""
        try:
            cache_stats = self._cache_manager.get_stats()
            overall_stats = cache_stats.get("overall", {})
            hit_rate = overall_stats.get("hit_rate", 0)

            # 檢查快取命中率警報
            if hit_rate < self._achievement_thresholds["cache_hit_rate_critical"]:
                await self._create_performance_alert(
                    "critical",
                    f"快取命中率過低: {hit_rate:.1%}",
                    MetricType.CACHE_HIT_RATE,
                    hit_rate,
                    self._achievement_thresholds["cache_hit_rate_critical"],
                )
            elif hit_rate < self._achievement_thresholds["cache_hit_rate_warning"]:
                await self._create_performance_alert(
                    "warning",
                    f"快取命中率較低: {hit_rate:.1%}",
                    MetricType.CACHE_HIT_RATE,
                    hit_rate,
                    self._achievement_thresholds["cache_hit_rate_warning"],
                )

        except Exception as e:
            logger.error(f"快取效能監控錯誤: {e}")

    async def _monitor_error_rate(self) -> None:
        """監控錯誤率."""
        try:
            error_rate = self._query_metrics.failed_queries / max(
                self._query_metrics.total_queries, 1
            )

            # 檢查錯誤率警報
            if error_rate >= self._achievement_thresholds["error_rate_critical"]:
                await self._create_performance_alert(
                    "critical",
                    f"查詢錯誤率過高: {error_rate:.1%}",
                    MetricType.ERROR_RATE,
                    error_rate,
                    self._achievement_thresholds["error_rate_critical"],
                )
            elif error_rate >= self._achievement_thresholds["error_rate_warning"]:
                await self._create_performance_alert(
                    "warning",
                    f"查詢錯誤率較高: {error_rate:.1%}",
                    MetricType.ERROR_RATE,
                    error_rate,
                    self._achievement_thresholds["error_rate_warning"],
                )

        except Exception as e:
            logger.error(f"錯誤率監控錯誤: {e}")

    # =============================================================================
    # 統計重置和管理
    # =============================================================================

    def reset_achievement_metrics(self) -> None:
        """重置成就系統指標."""
        self._metrics_history.clear()
        self._query_metrics = QueryMetrics()
        logger.info("成就系統效能指標已重置")

    def get_metrics_count(self) -> int:
        """取得指標記錄數量."""
        return len(self._metrics_history)

__all__ = [
    "AchievementMetric",
    "AchievementPerformanceMonitor",
    "MetricType",
    "QueryMetrics",
]
