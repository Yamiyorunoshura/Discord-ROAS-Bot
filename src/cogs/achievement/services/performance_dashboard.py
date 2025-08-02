"""成就系統監控儀表板.

此模組提供效能監控的儀表板功能，包含：
- 實時效能指標收集和顯示
- 歷史趨勢分析
- 警報管理
- 效能報告生成
- 資源使用監控

根據 Story 5.1 Task 5 和 Task 8 的要求實作。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .achievement_monitor import AchievementPerformanceMonitor
    from .cache_manager import CacheManager
    from .memory_manager import MemoryManager
    from .performance_service import AchievementPerformanceService

logger = logging.getLogger(__name__)


class DashboardTheme(str, Enum):
    """儀表板主題."""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


class ChartType(str, Enum):
    """圖表類型."""
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    GAUGE = "gauge"
    AREA = "area"


@dataclass
class DashboardWidget:
    """儀表板小工具."""

    id: str
    """小工具ID"""

    title: str
    """標題"""

    type: ChartType
    """圖表類型"""

    data: dict[str, Any]
    """資料"""

    config: dict[str, Any] = field(default_factory=dict)
    """配置"""

    position: tuple[int, int] = (0, 0)
    """位置 (x, y)"""

    size: tuple[int, int] = (4, 3)
    """大小 (width, height)"""

    refresh_interval: int = 30
    """重新整理間隔（秒）"""

    last_updated: datetime = field(default_factory=datetime.now)
    """最後更新時間"""


@dataclass
class AlertRule:
    """警報規則."""

    id: str
    """規則ID"""

    name: str
    """規則名稱"""

    metric: str
    """監控指標"""

    operator: str
    """比較操作符 (>, <, >=, <=, ==, !=)"""

    threshold: float
    """閾值"""

    severity: str
    """警報嚴重程度 (info, warning, error, critical)"""

    enabled: bool = True
    """是否啟用"""

    cooldown_minutes: int = 5
    """冷卻時間（分鐘）"""

    last_triggered: datetime | None = None
    """最後觸發時間"""


class PerformanceDashboard:
    """成就系統效能監控儀表板.

    整合所有效能監控功能，提供統一的儀表板介面。
    """

    def __init__(
        self,
        performance_service: AchievementPerformanceService,
        performance_monitor: AchievementPerformanceMonitor | None = None,
        memory_manager: MemoryManager | None = None,
        cache_manager: CacheManager | None = None,
        theme: DashboardTheme = DashboardTheme.DARK
    ):
        """初始化效能儀表板.

        Args:
            performance_service: 效能服務
            performance_monitor: 效能監控器
            memory_manager: 記憶體管理器
            cache_manager: 快取管理器
            theme: 儀表板主題
        """
        self._performance_service = performance_service
        self._performance_monitor = performance_monitor
        self._memory_manager = memory_manager
        self._cache_manager = cache_manager
        self._theme = theme

        # 儀表板配置
        self._widgets: dict[str, DashboardWidget] = {}
        self._alert_rules: dict[str, AlertRule] = {}
        self._dashboard_config = {
            "title": "成就系統效能監控",
            "refresh_interval": 30,
            "auto_refresh": True,
            "theme": theme.value
        }

        # 歷史資料儲存
        self._metrics_history: list[dict[str, Any]] = []
        self._max_history_points = 1000

        # 監控任務
        self._dashboard_task: asyncio.Task | None = None
        self._is_running = False

        # 初始化預設小工具和警報規則
        self._initialize_default_widgets()
        self._initialize_default_alert_rules()

        logger.info("PerformanceDashboard 初始化完成")

    async def __aenter__(self) -> PerformanceDashboard:
        """異步上下文管理器進入."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """異步上下文管理器退出."""
        await self.stop()

    # =============================================================================
    # 儀表板控制
    # =============================================================================

    async def start(self) -> None:
        """啟動儀表板."""
        if self._is_running:
            logger.warning("儀表板已經在運行")
            return

        self._is_running = True
        self._dashboard_task = asyncio.create_task(self._dashboard_loop())

        logger.info("效能儀表板已啟動")

    async def stop(self) -> None:
        """停止儀表板."""
        if not self._is_running:
            return

        self._is_running = False

        if self._dashboard_task and not self._dashboard_task.done():
            self._dashboard_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._dashboard_task

        logger.info("效能儀表板已停止")

    async def _dashboard_loop(self) -> None:
        """儀表板更新循環."""
        while self._is_running:
            try:
                # 收集效能指標
                await self._collect_metrics()

                # 更新小工具資料
                await self._update_widgets()

                # 檢查警報規則
                await self._check_alert_rules()

                # 清理歷史資料
                await self._cleanup_history()

                refresh_interval = self._dashboard_config.get("refresh_interval", 30)
                await asyncio.sleep(refresh_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"儀表板更新循環錯誤: {e}", exc_info=True)
                await asyncio.sleep(10)

    # =============================================================================
    # 指標收集
    # =============================================================================

    async def _collect_metrics(self) -> dict[str, Any]:
        """收集效能指標.

        Returns:
            收集到的指標資料
        """
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "performance": {},
            "memory": {},
            "cache": {},
            "system": {}
        }

        try:
            # 收集效能服務指標
            if self._performance_service:
                performance_report = await self._performance_service.get_performance_report()
                metrics["performance"] = performance_report

            # 收集記憶體指標
            if self._memory_manager:
                memory_stats = self._memory_manager.get_memory_stats()
                metrics["memory"] = memory_stats

            # 收集快取指標
            if self._cache_manager:
                cache_stats = self._cache_manager.get_stats()
                metrics["cache"] = cache_stats

            # 收集系統指標
            if self._performance_monitor:
                system_stats = self._performance_monitor.get_achievement_metrics_summary()
                metrics["system"] = system_stats

            # 儲存到歷史記錄
            self._metrics_history.append(metrics)
            if len(self._metrics_history) > self._max_history_points:
                self._metrics_history = self._metrics_history[-self._max_history_points//2:]

            return metrics

        except Exception as e:
            logger.error(f"收集效能指標失敗: {e}", exc_info=True)
            return metrics

    # =============================================================================
    # 小工具管理
    # =============================================================================

    def _initialize_default_widgets(self) -> None:
        """初始化預設小工具."""
        default_widgets = [
            DashboardWidget(
                id="memory_usage",
                title="記憶體使用量",
                type=ChartType.GAUGE,
                data={},
                position=(0, 0),
                size=(4, 3)
            ),
            DashboardWidget(
                id="cache_hit_rate",
                title="快取命中率",
                type=ChartType.GAUGE,
                data={},
                position=(4, 0),
                size=(4, 3)
            ),
            DashboardWidget(
                id="query_performance",
                title="查詢效能趨勢",
                type=ChartType.LINE,
                data={},
                position=(0, 3),
                size=(8, 4)
            ),
            DashboardWidget(
                id="system_overview",
                title="系統概覽",
                type=ChartType.BAR,
                data={},
                position=(8, 0),
                size=(4, 7)
            ),
            DashboardWidget(
                id="alert_summary",
                title="警報摘要",
                type=ChartType.PIE,
                data={},
                position=(0, 7),
                size=(4, 3)
            ),
            DashboardWidget(
                id="performance_breakdown",
                title="效能分解",
                type=ChartType.AREA,
                data={},
                position=(4, 7),
                size=(4, 3)
            )
        ]

        for widget in default_widgets:
            self._widgets[widget.id] = widget

    async def _update_widgets(self) -> None:
        """更新所有小工具資料."""
        if not self._metrics_history:
            return

        current_metrics = self._metrics_history[-1]

        for widget_id, widget in self._widgets.items():
            try:
                # 檢查是否需要更新
                time_since_update = (datetime.now() - widget.last_updated).total_seconds()
                if time_since_update < widget.refresh_interval:
                    continue

                # 根據小工具類型更新資料
                if widget_id == "memory_usage":
                    await self._update_memory_widget(widget, current_metrics)
                elif widget_id == "cache_hit_rate":
                    await self._update_cache_widget(widget, current_metrics)
                elif widget_id == "query_performance":
                    await self._update_query_performance_widget(widget)
                elif widget_id == "system_overview":
                    await self._update_system_overview_widget(widget, current_metrics)
                elif widget_id == "alert_summary":
                    await self._update_alert_summary_widget(widget)
                elif widget_id == "performance_breakdown":
                    await self._update_performance_breakdown_widget(widget, current_metrics)

                widget.last_updated = datetime.now()

            except Exception as e:
                logger.error(f"更新小工具 {widget_id} 失敗: {e}")

    async def _update_memory_widget(self, widget: DashboardWidget, metrics: dict[str, Any]) -> None:
        """更新記憶體使用量小工具."""
        memory_data = metrics.get("memory", {})
        current = memory_data.get("current", {})

        widget.data = {
            "value": current.get("percent", 0),
            "max": 100,
            "unit": "%",
            "status": self._get_memory_status(current.get("rss_mb", 0)),
            "details": {
                "rss_mb": current.get("rss_mb", 0),
                "vms_mb": current.get("vms_mb", 0),
                "gc_objects": current.get("gc_objects", 0)
            }
        }

    async def _update_cache_widget(self, widget: DashboardWidget, metrics: dict[str, Any]) -> None:
        """更新快取命中率小工具."""
        cache_data = metrics.get("cache", {})
        overall = cache_data.get("overall", {})

        hit_rate = overall.get("hit_rate", 0) * 100

        widget.data = {
            "value": round(hit_rate, 1),
            "max": 100,
            "unit": "%",
            "status": self._get_cache_status(hit_rate),
            "details": {
                "total_hits": overall.get("total_hits", 0),
                "total_misses": overall.get("total_misses", 0),
                "total_requests": overall.get("total_requests", 0)
            }
        }

    async def _update_query_performance_widget(self, widget: DashboardWidget) -> None:
        """更新查詢效能趨勢小工具."""
        # 取得最近30個點的資料
        recent_metrics = self._metrics_history[-30:] if len(self._metrics_history) >= 30 else self._metrics_history

        timestamps = []
        avg_times = []
        slow_queries = []

        for metric in recent_metrics:
            timestamps.append(metric["timestamp"])

            performance = metric.get("performance", {})
            query_stats = performance.get("query_statistics", {})
            avg_times.append(query_stats.get("avg_query_time", 0))
            slow_queries.append(query_stats.get("slow_queries", 0))

        widget.data = {
            "labels": timestamps,
            "datasets": [
                {
                    "label": "平均查詢時間 (ms)",
                    "data": avg_times,
                    "borderColor": "#3b82f6",
                    "backgroundColor": "rgba(59, 130, 246, 0.1)"
                },
                {
                    "label": "慢查詢數量",
                    "data": slow_queries,
                    "borderColor": "#ef4444",
                    "backgroundColor": "rgba(239, 68, 68, 0.1)"
                }
            ]
        }

    async def _update_system_overview_widget(self, widget: DashboardWidget, metrics: dict[str, Any]) -> None:
        """更新系統概覽小工具."""
        performance = metrics.get("performance", {})
        memory = metrics.get("memory", {})
        cache = metrics.get("cache", {})

        widget.data = {
            "labels": ["查詢效能", "記憶體使用", "快取效能", "系統負載"],
            "datasets": [{
                "label": "效能指標",
                "data": [
                    self._calculate_query_score(performance),
                    self._calculate_memory_score(memory),
                    self._calculate_cache_score(cache),
                    self._calculate_system_score(metrics)
                ],
                "backgroundColor": [
                    "#10b981",  # 綠色
                    "#f59e0b",  # 黃色
                    "#3b82f6",  # 藍色
                    "#8b5cf6"   # 紫色
                ]
            }]
        }

    async def _update_alert_summary_widget(self, widget: DashboardWidget) -> None:
        """更新警報摘要小工具."""
        # 統計各種警報類型
        alert_counts = {"info": 0, "warning": 0, "error": 0, "critical": 0}

        # 這裡應該從警報系統取得實際資料
        # 暫時使用模擬資料
        alert_counts["warning"] = 2
        alert_counts["error"] = 1

        widget.data = {
            "labels": ["資訊", "警告", "錯誤", "嚴重"],
            "datasets": [{
                "data": [
                    alert_counts["info"],
                    alert_counts["warning"],
                    alert_counts["error"],
                    alert_counts["critical"]
                ],
                "backgroundColor": [
                    "#6b7280",  # 灰色
                    "#f59e0b",  # 黃色
                    "#ef4444",  # 紅色
                    "#dc2626"   # 深紅色
                ]
            }]
        }

    async def _update_performance_breakdown_widget(self, widget: DashboardWidget, metrics: dict[str, Any]) -> None:
        """更新效能分解小工具."""
        # 取得最近10個點的資料
        recent_metrics = self._metrics_history[-10:] if len(self._metrics_history) >= 10 else self._metrics_history

        timestamps = []
        db_times = []
        cache_times = []
        processing_times = []

        for metric in recent_metrics:
            timestamps.append(metric["timestamp"])

            # 這裡應該有更詳細的效能分解資料
            # 暫時使用模擬資料
            db_times.append(50 + len(metric["timestamp"]) % 30)
            cache_times.append(5 + len(metric["timestamp"]) % 10)
            processing_times.append(20 + len(metric["timestamp"]) % 20)

        widget.data = {
            "labels": timestamps,
            "datasets": [
                {
                    "label": "資料庫時間",
                    "data": db_times,
                    "backgroundColor": "rgba(239, 68, 68, 0.6)"
                },
                {
                    "label": "快取時間",
                    "data": cache_times,
                    "backgroundColor": "rgba(59, 130, 246, 0.6)"
                },
                {
                    "label": "處理時間",
                    "data": processing_times,
                    "backgroundColor": "rgba(16, 185, 129, 0.6)"
                }
            ]
        }

    # =============================================================================
    # 警報規則管理
    # =============================================================================

    def _initialize_default_alert_rules(self) -> None:
        """初始化預設警報規則."""
        default_rules = [
            AlertRule(
                id="memory_high",
                name="記憶體使用過高",
                metric="memory.current.rss_mb",
                operator=">=",
                threshold=80.0,
                severity="warning"
            ),
            AlertRule(
                id="memory_critical",
                name="記憶體使用嚴重",
                metric="memory.current.rss_mb",
                operator=">=",
                threshold=100.0,
                severity="critical"
            ),
            AlertRule(
                id="cache_hit_rate_low",
                name="快取命中率過低",
                metric="cache.overall.hit_rate",
                operator="<",
                threshold=0.7,
                severity="warning"
            ),
            AlertRule(
                id="query_time_high",
                name="查詢時間過長",
                metric="performance.query_statistics.avg_query_time",
                operator=">",
                threshold=300.0,
                severity="warning"
            )
        ]

        for rule in default_rules:
            self._alert_rules[rule.id] = rule

    async def _check_alert_rules(self) -> None:
        """檢查警報規則."""
        if not self._metrics_history:
            return

        current_metrics = self._metrics_history[-1]
        now = datetime.now()

        for rule_id, rule in self._alert_rules.items():
            if not rule.enabled:
                continue

            # 檢查冷卻時間
            if rule.last_triggered:
                time_since_last = (now - rule.last_triggered).total_seconds() / 60
                if time_since_last < rule.cooldown_minutes:
                    continue

            try:
                # 取得指標值
                metric_value = self._get_nested_value(current_metrics, rule.metric)
                if metric_value is None:
                    continue

                # 檢查條件
                if self._evaluate_condition(metric_value, rule.operator, rule.threshold):
                    await self._trigger_alert(rule, metric_value)
                    rule.last_triggered = now

            except Exception as e:
                logger.error(f"檢查警報規則 {rule_id} 失敗: {e}")

    def _get_nested_value(self, data: dict[str, Any], path: str) -> Any:
        """取得巢狀字典的值."""
        keys = path.split(".")
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        return current

    def _evaluate_condition(self, value: float, operator: str, threshold: float) -> bool:
        """評估條件."""
        if operator == ">":
            return value > threshold
        elif operator == "<":
            return value < threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == "==":
            return value == threshold
        elif operator == "!=":
            return value != threshold
        else:
            return False

    async def _trigger_alert(self, rule: AlertRule, current_value: float) -> None:
        """觸發警報."""
        logger.log(
            getattr(logging, rule.severity.upper(), logging.INFO),
            f"警報觸發: {rule.name}",
            extra={
                "rule_id": rule.id,
                "metric": rule.metric,
                "current_value": current_value,
                "threshold": rule.threshold,
                "severity": rule.severity
            }
        )

    # =============================================================================
    # 輔助方法
    # =============================================================================

    def _get_memory_status(self, rss_mb: float) -> str:
        """取得記憶體狀態."""
        if rss_mb >= 100:
            return "critical"
        elif rss_mb >= 80:
            return "warning"
        elif rss_mb >= 50:
            return "info"
        else:
            return "success"

    def _get_cache_status(self, hit_rate: float) -> str:
        """取得快取狀態."""
        if hit_rate >= 80:
            return "success"
        elif hit_rate >= 60:
            return "info"
        elif hit_rate >= 40:
            return "warning"
        else:
            return "critical"

    def _calculate_query_score(self, performance: dict[str, Any]) -> float:
        """計算查詢效能分數."""
        query_stats = performance.get("query_statistics", {})
        avg_time = query_stats.get("avg_query_time", 0)

        if avg_time <= 100:
            return 100
        elif avg_time <= 300:
            return 80
        elif avg_time <= 500:
            return 60
        else:
            return 40

    def _calculate_memory_score(self, memory: dict[str, Any]) -> float:
        """計算記憶體效能分數."""
        current = memory.get("current", {})
        percent = current.get("percent", 0)

        return max(0, 100 - percent)

    def _calculate_cache_score(self, cache: dict[str, Any]) -> float:
        """計算快取效能分數."""
        overall = cache.get("overall", {})
        hit_rate = overall.get("hit_rate", 0)

        return hit_rate * 100

    def _calculate_system_score(self, metrics: dict[str, Any]) -> float:
        """計算系統效能分數."""
        # 綜合評估系統效能
        query_score = self._calculate_query_score(metrics.get("performance", {}))
        memory_score = self._calculate_memory_score(metrics.get("memory", {}))
        cache_score = self._calculate_cache_score(metrics.get("cache", {}))

        return (query_score + memory_score + cache_score) / 3

    async def _cleanup_history(self) -> None:
        """清理歷史資料."""
        # 保留最近的資料點，清理過舊的資料
        if len(self._metrics_history) > self._max_history_points:
            self._metrics_history = self._metrics_history[-self._max_history_points//2:]

    # =============================================================================
    # 公共介面
    # =============================================================================

    def get_dashboard_data(self) -> dict[str, Any]:
        """取得儀表板資料.

        Returns:
            完整的儀表板資料
        """
        return {
            "config": self._dashboard_config,
            "widgets": {
                widget_id: {
                    "id": widget.id,
                    "title": widget.title,
                    "type": widget.type.value,
                    "data": widget.data,
                    "config": widget.config,
                    "position": widget.position,
                    "size": widget.size,
                    "last_updated": widget.last_updated.isoformat()
                }
                for widget_id, widget in self._widgets.items()
            },
            "alerts": {
                rule_id: {
                    "id": rule.id,
                    "name": rule.name,
                    "severity": rule.severity,
                    "enabled": rule.enabled,
                    "last_triggered": rule.last_triggered.isoformat() if rule.last_triggered else None
                }
                for rule_id, rule in self._alert_rules.items()
            },
            "summary": {
                "total_widgets": len(self._widgets),
                "active_alerts": len([r for r in self._alert_rules.values() if r.enabled]),
                "last_update": self._metrics_history[-1]["timestamp"] if self._metrics_history else None,
                "data_points": len(self._metrics_history)
            }
        }

    def add_widget(self, widget: DashboardWidget) -> None:
        """新增小工具."""
        self._widgets[widget.id] = widget
        logger.info(f"小工具已新增: {widget.id}")

    def remove_widget(self, widget_id: str) -> bool:
        """移除小工具."""
        if widget_id in self._widgets:
            del self._widgets[widget_id]
            logger.info(f"小工具已移除: {widget_id}")
            return True
        return False

    def add_alert_rule(self, rule: AlertRule) -> None:
        """新增警報規則."""
        self._alert_rules[rule.id] = rule
        logger.info(f"警報規則已新增: {rule.id}")

    def remove_alert_rule(self, rule_id: str) -> bool:
        """移除警報規則."""
        if rule_id in self._alert_rules:
            del self._alert_rules[rule_id]
            logger.info(f"警報規則已移除: {rule_id}")
            return True
        return False

    async def export_report(self, format: str = "json") -> str:
        """匯出效能報告.

        Args:
            format: 匯出格式 (json, csv)

        Returns:
            匯出的報告資料
        """
        dashboard_data = self.get_dashboard_data()

        if format.lower() == "json":
            return json.dumps(dashboard_data, indent=2, ensure_ascii=False)
        elif format.lower() == "csv":
            # 簡化的 CSV 匯出
            csv_lines = ["timestamp,memory_mb,cache_hit_rate,avg_query_time"]

            for metric in self._metrics_history[-100:]:  # 匯出最近100個點
                timestamp = metric["timestamp"]
                memory_mb = metric.get("memory", {}).get("current", {}).get("rss_mb", 0)
                cache_hit_rate = metric.get("cache", {}).get("overall", {}).get("hit_rate", 0)
                avg_query_time = metric.get("performance", {}).get("query_statistics", {}).get("avg_query_time", 0)

                csv_lines.append(f"{timestamp},{memory_mb},{cache_hit_rate},{avg_query_time}")

            return "\n".join(csv_lines)
        else:
            raise ValueError(f"不支援的匯出格式: {format}")


__all__ = [
    "AlertRule",
    "ChartType",
    "DashboardTheme",
    "DashboardWidget",
    "PerformanceDashboard",
]
