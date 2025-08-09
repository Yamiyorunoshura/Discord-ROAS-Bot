"""成就系統效能分析器.

此模組提供成就系統的效能瓶頸分析,包含:
- 查詢效能分析和基準測試
- 資料庫索引優化建議
- 記憶體使用量分析
- 瓶頸識別和效能報告

根據 Story 5.1 Task 1.1 的要求,分析現有成就查詢的效能瓶頸.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from ..database.models import AchievementType

if TYPE_CHECKING:
    from ..database.repository import AchievementRepository

logger = logging.getLogger(__name__)

# 常數定義
SLOW_QUERY_THRESHOLD_MS = 200  # 慢查詢閾值(毫秒)
CRITICAL_QUERY_THRESHOLD_MS = 500  # 關鍵慢查詢閾值(毫秒)
HIGH_QUERY_THRESHOLD_MS = 300  # 高慢查詢閾值(毫秒)
HIGH_MEMORY_THRESHOLD_MB = 10  # 高記憶體使用閾值(MB)
MEMORY_WARNING_THRESHOLD_MB = 50  # 記憶體警告閾值(MB)
EFFICIENCY_THRESHOLD = 0.1  # 效率閾值
EXCELLENT_RESPONSE_TIME_MS = 100  # 優秀回應時間(毫秒)
GOOD_RESPONSE_TIME_MS = 200  # 良好回應時間(毫秒)
FAIR_RESPONSE_TIME_MS = 300  # 一般回應時間(毫秒)
POOR_RESPONSE_TIME_MS = 500  # 差勁回應時間(毫秒)
EXCELLENT_SLOW_QUERY_RATIO = 0.1  # 優秀慢查詢比例
GOOD_SLOW_QUERY_RATIO = 0.2  # 良好慢查詢比例
FAIR_SLOW_QUERY_RATIO = 0.3  # 一般慢查詢比例
POOR_SLOW_QUERY_RATIO = 0.5  # 差勁慢查詢比例


class QueryType(str, Enum):
    """查詢類型列舉."""

    ACHIEVEMENT_LIST = "achievement_list"
    USER_ACHIEVEMENTS = "user_achievements"
    USER_PROGRESS = "user_progress"
    STATS_QUERY = "stats_query"
    LEADERBOARD = "leaderboard"


@dataclass
class QueryPerformanceMetric:
    """查詢效能指標."""

    query_type: QueryType
    """查詢類型"""

    execution_time_ms: float
    """執行時間(毫秒)"""

    rows_examined: int
    """檢查的行數"""

    rows_returned: int
    """返回的行數"""

    memory_usage_mb: float
    """記憶體使用量(MB)"""

    query_sql: str
    """查詢 SQL"""

    parameters: dict[str, Any] = field(default_factory=dict)
    """查詢參數"""

    timestamp: datetime = field(default_factory=datetime.now)
    """測試時間"""


@dataclass
class PerformanceBottleneck:
    """效能瓶頸."""

    type: str
    """瓶頸類型"""

    severity: str
    """嚴重程度 (low, medium, high, critical)"""

    description: str
    """描述"""

    affected_queries: list[QueryType]
    """影響的查詢類型"""

    recommendations: list[str]
    """優化建議"""

    performance_impact: float
    """效能影響(百分比)"""


@dataclass
class PerformanceBenchmark:
    """效能基準."""

    query_type: QueryType
    baseline_time_ms: float
    target_time_ms: float
    current_time_ms: float
    improvement_percentage: float


class PerformanceAnalyzer:
    """效能分析器.

    提供成就系統的全面效能分析功能.
    """

    def __init__(self, repository: AchievementRepository):
        """初始化效能分析器.

        Args:
            repository: 成就資料存取庫
        """
        self._repository = repository
        self._metrics_history: list[QueryPerformanceMetric] = []
        self._benchmarks: dict[QueryType, PerformanceBenchmark] = {}

        # Performance targets in milliseconds
        self._performance_targets = {
            QueryType.ACHIEVEMENT_LIST: 200,
            QueryType.USER_ACHIEVEMENTS: 150,
            QueryType.USER_PROGRESS: 100,
            QueryType.STATS_QUERY: 300,
            QueryType.LEADERBOARD: 400,
        }

        logger.info("PerformanceAnalyzer 初始化完成")

    async def analyze_all_queries(self) -> dict[str, Any]:
        """分析所有查詢類型的效能.

        Returns:
            完整的效能分析報告
        """
        logger.info("開始全面效能分析")

        analysis_results = {
            "timestamp": datetime.now().isoformat(),
            "query_performance": {},
            "bottlenecks": [],
            "recommendations": [],
            "benchmark_results": {},
            "overall_health": "unknown",
        }

        try:
            # 1. 分析成就列表查詢
            achievement_metrics = await self._analyze_achievement_list_queries()
            analysis_results["query_performance"]["achievement_list"] = (
                achievement_metrics
            )

            # 2. 分析用戶成就查詢
            user_achievement_metrics = await self._analyze_user_achievement_queries()
            analysis_results["query_performance"]["user_achievements"] = (
                user_achievement_metrics
            )

            # 3. 分析用戶進度查詢
            progress_metrics = await self._analyze_progress_queries()
            analysis_results["query_performance"]["user_progress"] = progress_metrics

            # 4. 分析統計查詢
            stats_metrics = await self._analyze_stats_queries()
            analysis_results["query_performance"]["stats"] = stats_metrics

            # 5. 識別效能瓶頸
            bottlenecks = await self._identify_bottlenecks()
            analysis_results["bottlenecks"] = [
                self._bottleneck_to_dict(b) for b in bottlenecks
            ]

            # 6. 生成優化建議
            recommendations = await self._generate_recommendations(bottlenecks)
            analysis_results["recommendations"] = recommendations

            # 7. 計算整體健康度
            overall_health = self._calculate_overall_health()
            analysis_results["overall_health"] = overall_health

            logger.info(f"效能分析完成,整體健康度: {overall_health}")

        except Exception as e:
            logger.error(f"效能分析失敗: {e}", exc_info=True)
            analysis_results["error"] = str(e)

        return analysis_results

    async def _analyze_achievement_list_queries(self) -> dict[str, Any]:
        """分析成就列表查詢效能."""
        logger.debug("分析成就列表查詢效能")

        metrics = []

        # 測試場景 1: 基本成就列表查詢
        start_time = time.perf_counter()
        try:
            achievements = await self._repository.list_achievements(
                active_only=True, limit=50
            )
            execution_time = (time.perf_counter() - start_time) * 1000

            metric = QueryPerformanceMetric(
                query_type=QueryType.ACHIEVEMENT_LIST,
                execution_time_ms=execution_time,
                rows_examined=len(achievements) * 2,  # 估算
                rows_returned=len(achievements),
                memory_usage_mb=len(achievements) * 0.005,  # 估算每個成就 5KB
                query_sql="SELECT * FROM achievements WHERE is_active = 1 LIMIT 50",
                parameters={"active_only": True, "limit": 50},
            )
            metrics.append(metric)
            self._metrics_history.append(metric)

        except Exception as e:
            logger.error(f"基本成就列表查詢測試失敗: {e}")

        # 測試場景 2: 分類篩選查詢
        start_time = time.perf_counter()
        try:
            achievements = await self._repository.list_achievements(
                category_id=1, active_only=True, limit=20
            )
            execution_time = (time.perf_counter() - start_time) * 1000

            metric = QueryPerformanceMetric(
                query_type=QueryType.ACHIEVEMENT_LIST,
                execution_time_ms=execution_time,
                rows_examined=len(achievements) * 3,  # 估算,需要JOIN
                rows_returned=len(achievements),
                memory_usage_mb=len(achievements) * 0.005,
                query_sql="SELECT * FROM achievements WHERE category_id = 1 AND is_active = 1 LIMIT 20",
                parameters={"category_id": 1, "active_only": True, "limit": 20},
            )
            metrics.append(metric)
            self._metrics_history.append(metric)

        except Exception as e:
            logger.error(f"分類篩選查詢測試失敗: {e}")

        # 測試場景 3: 類型篩選查詢
        start_time = time.perf_counter()
        try:
            achievements = await self._repository.list_achievements(
                achievement_type=AchievementType.PROGRESSIVE, active_only=True
            )
            execution_time = (time.perf_counter() - start_time) * 1000

            metric = QueryPerformanceMetric(
                query_type=QueryType.ACHIEVEMENT_LIST,
                execution_time_ms=execution_time,
                rows_examined=len(achievements) * 2,
                rows_returned=len(achievements),
                memory_usage_mb=len(achievements) * 0.005,
                query_sql="SELECT * FROM achievements WHERE type = 'progressive' AND is_active = 1",
                parameters={"achievement_type": "progressive", "active_only": True},
            )
            metrics.append(metric)
            self._metrics_history.append(metric)

        except Exception as e:
            logger.error(f"類型篩選查詢測試失敗: {e}")

        # 計算統計
        if metrics:
            avg_time = sum(m.execution_time_ms for m in metrics) / len(metrics)
            max_time = max(m.execution_time_ms for m in metrics)
            min_time = min(m.execution_time_ms for m in metrics)
            total_memory = sum(m.memory_usage_mb for m in metrics)
        else:
            avg_time = max_time = min_time = total_memory = 0

        return {
            "test_count": len(metrics),
            "average_time_ms": round(avg_time, 2),
            "max_time_ms": round(max_time, 2),
            "min_time_ms": round(min_time, 2),
            "total_memory_mb": round(total_memory, 2),
            "target_time_ms": self._performance_targets[QueryType.ACHIEVEMENT_LIST],
            "meets_target": avg_time
            <= self._performance_targets[QueryType.ACHIEVEMENT_LIST],
            "details": [self._metric_to_dict(m) for m in metrics],
        }

    async def _analyze_user_achievement_queries(self) -> dict[str, Any]:
        """分析用戶成就查詢效能."""
        logger.debug("分析用戶成就查詢效能")

        metrics = []
        test_user_id = 123456  # 測試用戶 ID

        # 測試場景 1: 基本用戶成就查詢
        start_time = time.perf_counter()
        try:
            user_achievements = await self._repository.get_user_achievements(
                test_user_id
            )
            execution_time = (time.perf_counter() - start_time) * 1000

            metric = QueryPerformanceMetric(
                query_type=QueryType.USER_ACHIEVEMENTS,
                execution_time_ms=execution_time,
                rows_examined=len(user_achievements) * 3,  # 需要JOIN achievements表
                rows_returned=len(user_achievements),
                memory_usage_mb=len(user_achievements) * 0.008,  # 包含成就詳情
                query_sql="""SELECT ua.*, a.* FROM user_achievements ua
                           JOIN achievements a ON a.id = ua.achievement_id
                           WHERE ua.user_id = ?""",
                parameters={"user_id": test_user_id},
            )
            metrics.append(metric)
            self._metrics_history.append(metric)

        except Exception as e:
            logger.error(f"基本用戶成就查詢測試失敗: {e}")

        # 測試場景 2: 分類用戶成就查詢
        start_time = time.perf_counter()
        try:
            user_achievements = await self._repository.get_user_achievements(
                test_user_id, category_id=1
            )
            execution_time = (time.perf_counter() - start_time) * 1000

            metric = QueryPerformanceMetric(
                query_type=QueryType.USER_ACHIEVEMENTS,
                execution_time_ms=execution_time,
                rows_examined=len(user_achievements) * 4,  # 複雜JOIN
                rows_returned=len(user_achievements),
                memory_usage_mb=len(user_achievements) * 0.008,
                query_sql="""SELECT ua.*, a.* FROM user_achievements ua
                           JOIN achievements a ON a.id = ua.achievement_id
                           WHERE ua.user_id = ? AND a.category_id = ?""",
                parameters={"user_id": test_user_id, "category_id": 1},
            )
            metrics.append(metric)
            self._metrics_history.append(metric)

        except Exception as e:
            logger.error(f"分類用戶成就查詢測試失敗: {e}")

        # 測試場景 3: 用戶成就統計查詢
        start_time = time.perf_counter()
        try:
            stats = await self._repository.get_user_achievement_stats(test_user_id)
            execution_time = (time.perf_counter() - start_time) * 1000

            metric = QueryPerformanceMetric(
                query_type=QueryType.STATS_QUERY,
                execution_time_ms=execution_time,
                rows_examined=stats.get("total_achievements", 0) * 3,
                rows_returned=1,  # 統計結果
                memory_usage_mb=0.001,  # 統計結果很小
                query_sql="""SELECT COUNT(*), SUM(a.points) FROM user_achievements ua
                           JOIN achievements a ON a.id = ua.achievement_id
                           WHERE ua.user_id = ?""",
                parameters={"user_id": test_user_id},
            )
            metrics.append(metric)
            self._metrics_history.append(metric)

        except Exception as e:
            logger.error(f"用戶成就統計查詢測試失敗: {e}")

        # 計算統計
        if metrics:
            avg_time = sum(m.execution_time_ms for m in metrics) / len(metrics)
            max_time = max(m.execution_time_ms for m in metrics)
            min_time = min(m.execution_time_ms for m in metrics)
            total_memory = sum(m.memory_usage_mb for m in metrics)
        else:
            avg_time = max_time = min_time = total_memory = 0

        return {
            "test_count": len(metrics),
            "average_time_ms": round(avg_time, 2),
            "max_time_ms": round(max_time, 2),
            "min_time_ms": round(min_time, 2),
            "total_memory_mb": round(total_memory, 2),
            "target_time_ms": self._performance_targets[QueryType.USER_ACHIEVEMENTS],
            "meets_target": avg_time
            <= self._performance_targets[QueryType.USER_ACHIEVEMENTS],
            "details": [self._metric_to_dict(m) for m in metrics],
        }

    async def _analyze_progress_queries(self) -> dict[str, Any]:
        """分析用戶進度查詢效能."""
        logger.debug("分析用戶進度查詢效能")

        metrics = []
        test_user_id = 123456
        test_achievement_id = 1

        # 測試場景 1: 單個進度查詢
        start_time = time.perf_counter()
        try:
            progress = await self._repository.get_user_progress(
                test_user_id, test_achievement_id
            )
            execution_time = (time.perf_counter() - start_time) * 1000

            metric = QueryPerformanceMetric(
                query_type=QueryType.USER_PROGRESS,
                execution_time_ms=execution_time,
                rows_examined=1,
                rows_returned=1 if progress else 0,
                memory_usage_mb=0.001,
                query_sql="""SELECT * FROM achievement_progress
                           WHERE user_id = ? AND achievement_id = ?""",
                parameters={
                    "user_id": test_user_id,
                    "achievement_id": test_achievement_id,
                },
            )
            metrics.append(metric)
            self._metrics_history.append(metric)

        except Exception as e:
            logger.error(f"單個進度查詢測試失敗: {e}")

        # 測試場景 2: 用戶所有進度查詢
        start_time = time.perf_counter()
        try:
            progresses = await self._repository.get_user_progresses(test_user_id)
            execution_time = (time.perf_counter() - start_time) * 1000

            metric = QueryPerformanceMetric(
                query_type=QueryType.USER_PROGRESS,
                execution_time_ms=execution_time,
                rows_examined=len(progresses) * 2,
                rows_returned=len(progresses),
                memory_usage_mb=len(progresses) * 0.003,
                query_sql="""SELECT * FROM achievement_progress WHERE user_id = ?
                           ORDER BY last_updated DESC""",
                parameters={"user_id": test_user_id},
            )
            metrics.append(metric)
            self._metrics_history.append(metric)

        except Exception as e:
            logger.error(f"用戶所有進度查詢測試失敗: {e}")

        # 計算統計
        if metrics:
            avg_time = sum(m.execution_time_ms for m in metrics) / len(metrics)
            max_time = max(m.execution_time_ms for m in metrics)
            min_time = min(m.execution_time_ms for m in metrics)
            total_memory = sum(m.memory_usage_mb for m in metrics)
        else:
            avg_time = max_time = min_time = total_memory = 0

        return {
            "test_count": len(metrics),
            "average_time_ms": round(avg_time, 2),
            "max_time_ms": round(max_time, 2),
            "min_time_ms": round(min_time, 2),
            "total_memory_mb": round(total_memory, 2),
            "target_time_ms": self._performance_targets[QueryType.USER_PROGRESS],
            "meets_target": avg_time
            <= self._performance_targets[QueryType.USER_PROGRESS],
            "details": [self._metric_to_dict(m) for m in metrics],
        }

    async def _analyze_stats_queries(self) -> dict[str, Any]:
        """分析統計查詢效能."""
        logger.debug("分析統計查詢效能")

        metrics = []

        # 測試場景 1: 全域統計查詢
        start_time = time.perf_counter()
        try:
            global_stats = await self._repository.get_global_achievement_stats()
            execution_time = (time.perf_counter() - start_time) * 1000

            metric = QueryPerformanceMetric(
                query_type=QueryType.STATS_QUERY,
                execution_time_ms=execution_time,
                rows_examined=global_stats.get("total_achievements", 0),
                rows_returned=4,  # 統計結果項目數
                memory_usage_mb=0.001,
                query_sql="""SELECT COUNT(*) FROM achievements;
                           SELECT COUNT(*) FROM achievements WHERE is_active = 1;
                           SELECT COUNT(*) FROM user_achievements;
                           SELECT COUNT(DISTINCT user_id) FROM user_achievements""",
                parameters={},
            )
            metrics.append(metric)
            self._metrics_history.append(metric)

        except Exception as e:
            logger.error(f"全域統計查詢測試失敗: {e}")

        # 測試場景 2: 熱門成就查詢
        start_time = time.perf_counter()
        try:
            popular_achievements = await self._repository.get_popular_achievements(
                limit=10
            )
            execution_time = (time.perf_counter() - start_time) * 1000

            metric = QueryPerformanceMetric(
                query_type=QueryType.LEADERBOARD,
                execution_time_ms=execution_time,
                rows_examined=len(popular_achievements) * 10,  # 複雜聚合查詢
                rows_returned=len(popular_achievements),
                memory_usage_mb=len(popular_achievements) * 0.005,
                query_sql="""SELECT a.*, COUNT(ua.id) as earned_count
                           FROM achievements a
                           LEFT JOIN user_achievements ua ON ua.achievement_id = a.id
                           WHERE a.is_active = 1
                           GROUP BY a.id
                           ORDER BY earned_count DESC LIMIT 10""",
                parameters={"limit": 10},
            )
            metrics.append(metric)
            self._metrics_history.append(metric)

        except Exception as e:
            logger.error(f"熱門成就查詢測試失敗: {e}")

        # 計算統計
        if metrics:
            avg_time = sum(m.execution_time_ms for m in metrics) / len(metrics)
            max_time = max(m.execution_time_ms for m in metrics)
            min_time = min(m.execution_time_ms for m in metrics)
            total_memory = sum(m.memory_usage_mb for m in metrics)
        else:
            avg_time = max_time = min_time = total_memory = 0

        return {
            "test_count": len(metrics),
            "average_time_ms": round(avg_time, 2),
            "max_time_ms": round(max_time, 2),
            "min_time_ms": round(min_time, 2),
            "total_memory_mb": round(total_memory, 2),
            "target_time_ms": self._performance_targets[QueryType.STATS_QUERY],
            "meets_target": avg_time
            <= self._performance_targets[QueryType.STATS_QUERY],
            "details": [self._metric_to_dict(m) for m in metrics],
        }

    async def _identify_bottlenecks(self) -> list[PerformanceBottleneck]:
        """識別效能瓶頸."""
        logger.debug("識別效能瓶頸")

        bottlenecks = []

        if not self._metrics_history:
            return bottlenecks

        # 分析查詢時間瓶頸
        slow_queries = [
            m
            for m in self._metrics_history
            if m.execution_time_ms > SLOW_QUERY_THRESHOLD_MS
        ]
        if slow_queries:
            affected_types = list({q.query_type for q in slow_queries})
            avg_slow_time = sum(q.execution_time_ms for q in slow_queries) / len(
                slow_queries
            )

            severity = (
                "critical"
                if avg_slow_time > CRITICAL_QUERY_THRESHOLD_MS
                else "high"
                if avg_slow_time > HIGH_QUERY_THRESHOLD_MS
                else "medium"
            )

            bottleneck = PerformanceBottleneck(
                type="slow_queries",
                severity=severity,
                description=f"發現 {len(slow_queries)} 個慢查詢,平均執行時間 {avg_slow_time:.1f}ms",
                affected_queries=affected_types,
                recommendations=[
                    "優化資料庫索引",
                    "實施查詢快取",
                    "考慮分頁查詢",
                    "優化JOIN操作",
                ],
                performance_impact=min(avg_slow_time / 100, 90),  # 最高90%影響
            )
            bottlenecks.append(bottleneck)

        # 分析記憶體使用瓶頸
        high_memory_queries = [
            m
            for m in self._metrics_history
            if m.memory_usage_mb > HIGH_MEMORY_THRESHOLD_MB
        ]
        if high_memory_queries:
            total_memory = sum(q.memory_usage_mb for q in high_memory_queries)

            bottleneck = PerformanceBottleneck(
                type="high_memory_usage",
                severity="medium"
                if total_memory < MEMORY_WARNING_THRESHOLD_MB
                else "high",
                description=f"高記憶體使用查詢總計 {total_memory:.1f}MB",
                affected_queries=list({q.query_type for q in high_memory_queries}),
                recommendations=[
                    "實施結果集限制",
                    "使用分頁查詢",
                    "優化資料結構",
                    "增加記憶體快取",
                ],
                performance_impact=min(total_memory * 2, 70),
            )
            bottlenecks.append(bottleneck)

        # 分析資料庫掃描瓶頸
        high_scan_queries = [
            m for m in self._metrics_history if m.rows_examined > m.rows_returned * 10
        ]
        if high_scan_queries:
            avg_efficiency = sum(
                q.rows_returned / max(q.rows_examined, 1) for q in high_scan_queries
            ) / len(high_scan_queries)

            bottleneck = PerformanceBottleneck(
                type="inefficient_scans",
                severity="high" if avg_efficiency < EFFICIENCY_THRESHOLD else "medium",
                description=f"低效掃描查詢,平均效率 {avg_efficiency:.1%}",
                affected_queries=list({q.query_type for q in high_scan_queries}),
                recommendations=[
                    "添加適當的索引",
                    "優化WHERE條件",
                    "避免SELECT *",
                    "使用覆蓋索引",
                ],
                performance_impact=(1 - avg_efficiency) * 80,
            )
            bottlenecks.append(bottleneck)

        return bottlenecks

    async def _generate_recommendations(
        self, bottlenecks: list[PerformanceBottleneck]
    ) -> list[str]:
        """生成優化建議."""
        recommendations = []

        if not bottlenecks:
            recommendations.append("系統效能良好,無明顯瓶頸")
            return recommendations

        # 按嚴重程度排序瓶頸
        critical_bottlenecks = [b for b in bottlenecks if b.severity == "critical"]
        high_bottlenecks = [b for b in bottlenecks if b.severity == "high"]
        medium_bottlenecks = [b for b in bottlenecks if b.severity == "medium"]

        if critical_bottlenecks:
            recommendations.append("🚨 緊急優化建議:")
            for bottleneck in critical_bottlenecks:
                recommendations.extend([
                    f"  - {rec}" for rec in bottleneck.recommendations
                ])

        if high_bottlenecks:
            recommendations.append("⚠️ 高優先級優化建議:")
            for bottleneck in high_bottlenecks:
                recommendations.extend([
                    f"  - {rec}" for rec in bottleneck.recommendations
                ])

        if medium_bottlenecks:
            recommendations.append("中優先級優化建議:")
            for bottleneck in medium_bottlenecks:
                recommendations.extend([
                    f"  - {rec}" for rec in bottleneck.recommendations
                ])

        # 添加通用建議
        recommendations.extend([
            "",
            "🔧 通用優化建議:",
            "  - 定期更新資料庫統計資訊",
            "  - 監控查詢執行計畫",
            "  - 實施適當的快取策略",
            "  - 考慮讀寫分離架構",
            "  - 定期清理歷史資料",
        ])

        return recommendations

    def _calculate_overall_health(self) -> str:
        """計算整體健康度."""
        if not self._metrics_history:
            return "unknown"

        # 計算各項指標
        avg_time = sum(m.execution_time_ms for m in self._metrics_history) / len(
            self._metrics_history
        )
        slow_query_ratio = len([
            m
            for m in self._metrics_history
            if m.execution_time_ms > SLOW_QUERY_THRESHOLD_MS
        ]) / len(self._metrics_history)

        # 根據指標評估健康度
        if (
            avg_time <= EXCELLENT_RESPONSE_TIME_MS
            and slow_query_ratio <= EXCELLENT_SLOW_QUERY_RATIO
        ):
            return "excellent"
        elif (
            avg_time <= GOOD_RESPONSE_TIME_MS
            and slow_query_ratio <= GOOD_SLOW_QUERY_RATIO
        ):
            return "good"
        elif (
            avg_time <= FAIR_RESPONSE_TIME_MS
            and slow_query_ratio <= FAIR_SLOW_QUERY_RATIO
        ):
            return "fair"
        elif (
            avg_time <= POOR_RESPONSE_TIME_MS
            and slow_query_ratio <= POOR_SLOW_QUERY_RATIO
        ):
            return "poor"
        else:
            return "critical"

    def _metric_to_dict(self, metric: QueryPerformanceMetric) -> dict[str, Any]:
        """將效能指標轉換為字典."""
        return {
            "query_type": metric.query_type.value,
            "execution_time_ms": round(metric.execution_time_ms, 2),
            "rows_examined": metric.rows_examined,
            "rows_returned": metric.rows_returned,
            "memory_usage_mb": round(metric.memory_usage_mb, 3),
            "efficiency": round(metric.rows_returned / max(metric.rows_examined, 1), 3),
            "query_sql": metric.query_sql,
            "parameters": metric.parameters,
            "timestamp": metric.timestamp.isoformat(),
        }

    def _bottleneck_to_dict(self, bottleneck: PerformanceBottleneck) -> dict[str, Any]:
        """將效能瓶頸轉換為字典."""
        return {
            "type": bottleneck.type,
            "severity": bottleneck.severity,
            "description": bottleneck.description,
            "affected_queries": [q.value for q in bottleneck.affected_queries],
            "recommendations": bottleneck.recommendations,
            "performance_impact": round(bottleneck.performance_impact, 1),
        }

    def get_metrics_history(self) -> list[dict[str, Any]]:
        """取得效能指標歷史."""
        return [self._metric_to_dict(m) for m in self._metrics_history]

    def clear_metrics_history(self) -> None:
        """清空效能指標歷史."""
        self._metrics_history.clear()
        logger.info("效能指標歷史已清空")


__all__ = [
    "PerformanceAnalyzer",
    "PerformanceBenchmark",
    "PerformanceBottleneck",
    "QueryPerformanceMetric",
    "QueryType",
]
