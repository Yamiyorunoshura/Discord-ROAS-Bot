"""成就系統操作歷史管理器.

此模組提供成就系統的操作歷史管理功能,包含:
- 操作歷史記錄和查詢
- 歷史資料分析和報告
- 操作追蹤和監控
- 歷史資料展示和導出

提供完整的操作可追溯性和歷史資料分析能力.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

# 常數定義
MAX_CHANGES_DISPLAY = 3  # 顯示變更的最大欄位數量

class HistoryAction(Enum):
    """歷史操作動作枚舉."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    GRANT = "grant"
    REVOKE = "revoke"
    RESET = "reset"
    ADJUST = "adjust"
    APPROVE = "approve"
    REJECT = "reject"

class HistoryCategory(Enum):
    """歷史分類枚舉."""

    ACHIEVEMENT = "achievement"
    USER_ACHIEVEMENT = "user_achievement"
    PROGRESS = "progress"
    USER_DATA = "user_data"
    PERMISSION = "permission"
    SYSTEM = "system"
    SECURITY = "security"

@dataclass
class HistoryRecord:
    """歷史記錄."""

    record_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # 操作資訊
    action: HistoryAction = HistoryAction.UPDATE
    category: HistoryCategory = HistoryCategory.USER_ACHIEVEMENT
    operation_name: str = ""

    # 執行者資訊
    executor_id: int = 0
    executor_name: str = ""
    executor_role: str = ""

    # 目標資訊
    target_type: str = ""
    target_id: int | str = ""
    target_name: str = ""

    # 資料變更
    old_values: dict[str, Any] = field(default_factory=dict)
    new_values: dict[str, Any] = field(default_factory=dict)
    changes_summary: str = ""

    # 上下文資訊
    guild_id: int = 0
    channel_id: int | None = None
    interaction_id: str | None = None
    session_id: str | None = None

    # 操作結果
    success: bool = True
    error_message: str | None = None
    duration_ms: float | None = None

    # 影響範圍
    affected_users: list[int] = field(default_factory=list)
    affected_achievements: list[int] = field(default_factory=list)

    # 額外資訊
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    # 風險等級
    risk_level: str = "low"
    requires_attention: bool = False

@dataclass
class HistoryQuery:
    """歷史查詢參數."""

    # 時間範圍
    start_time: datetime | None = None
    end_time: datetime | None = None

    # 操作篩選
    actions: list[HistoryAction] | None = None
    categories: list[HistoryCategory] | None = None
    operation_names: list[str] | None = None

    # 執行者篩選
    executor_ids: list[int] | None = None
    executor_roles: list[str] | None = None

    # 目標篩選
    target_types: list[str] | None = None
    target_ids: list[int | str] | None = None

    # 結果篩選
    success_only: bool | None = None
    risk_levels: list[str] | None = None

    # 搜尋關鍵字
    search_keywords: list[str] | None = None

    # 分頁和排序
    limit: int = 50
    offset: int = 0
    sort_by: str = "timestamp"
    sort_order: str = "desc"  # asc, desc

    # 聚合選項
    group_by: str | None = None  # action, category, executor_id, etc.
    include_statistics: bool = False

@dataclass
class HistoryAnalysis:
    """歷史分析結果."""

    analysis_id: str = field(default_factory=lambda: str(uuid4()))
    generated_at: datetime = field(default_factory=datetime.utcnow)

    # 查詢參數
    query_params: HistoryQuery | None = None
    total_records: int = 0
    analyzed_period: tuple[datetime, datetime] | None = None

    # 操作統計
    operations_by_action: dict[str, int] = field(default_factory=dict)
    operations_by_category: dict[str, int] = field(default_factory=dict)
    operations_by_executor: dict[int, int] = field(default_factory=dict)
    operations_by_risk_level: dict[str, int] = field(default_factory=dict)

    # 成功率統計
    success_rate: float = 0.0
    failed_operations: int = 0

    # 時間分析
    operations_by_hour: dict[int, int] = field(default_factory=dict)
    operations_by_day: dict[str, int] = field(default_factory=dict)
    operations_by_month: dict[str, int] = field(default_factory=dict)

    # 趨勢分析
    trending_operations: list[dict[str, Any]] = field(default_factory=list)
    peak_activity_periods: list[dict[str, Any]] = field(default_factory=list)

    # 用戶活動分析
    most_active_executors: list[dict[str, Any]] = field(default_factory=list)
    most_affected_users: list[dict[str, Any]] = field(default_factory=list)

    # 風險分析
    high_risk_operations: list[HistoryRecord] = field(default_factory=list)
    security_incidents: list[dict[str, Any]] = field(default_factory=list)

    # 效能分析
    average_operation_duration: float = 0.0
    slowest_operations: list[dict[str, Any]] = field(default_factory=list)

class HistoryManager:
    """操作歷史管理器.

    負責記錄、查詢和分析系統操作歷史.
    """

    def __init__(self, database_service: Any = None, cache_service: Any = None) -> None:
        """初始化歷史管理器.

        Args:
            database_service: 資料庫服務實例
            cache_service: 快取服務實例
        """
        self.database_service = database_service
        self.cache_service = cache_service

        # 記憶體中的歷史記錄緩衝區
        self._history_buffer: list[HistoryRecord] = []
        self._buffer_size = 200

        # 統計資料
        self._stats = {
            "records_created": 0,
            "queries_executed": 0,
            "analyses_generated": 0,
            "buffer_flushes": 0,
            "export_operations": 0,
        }

        logger.info("HistoryManager 初始化完成")

    async def record_operation(
        self,
        action: HistoryAction,
        category: HistoryCategory,
        operation_name: str,
        executor_id: int,
        target_type: str = "",
        target_id: int | str = "",
        target_name: str = "",
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
        guild_id: int = 0,
        channel_id: int | None = None,
        affected_users: list[int] | None = None,
        affected_achievements: list[int] | None = None,
        success: bool = True,
        error_message: str | None = None,
        duration_ms: float | None = None,
        risk_level: str = "low",
        **metadata: Any,
    ) -> HistoryRecord:
        """記錄操作歷史.

        Args:
            action: 操作動作
            category: 操作分類
            operation_name: 操作名稱
            executor_id: 執行者ID
            target_type: 目標類型
            target_id: 目標ID
            target_name: 目標名稱
            old_values: 操作前的值
            new_values: 操作後的值
            guild_id: 伺服器ID
            channel_id: 頻道ID
            affected_users: 受影響的用戶列表
            affected_achievements: 受影響的成就列表
            success: 操作是否成功
            error_message: 錯誤訊息
            duration_ms: 操作耗時
            risk_level: 風險等級
            **metadata: 額外元資料

        Returns:
            HistoryRecord: 歷史記錄
        """
        # 生成變更摘要
        changes_summary = self._generate_changes_summary(
            old_values or {}, new_values or {}
        )

        # 生成標籤
        tags = self._generate_tags(action, category, operation_name, risk_level)

        record = HistoryRecord(
            action=action,
            category=category,
            operation_name=operation_name,
            executor_id=executor_id,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            old_values=old_values or {},
            new_values=new_values or {},
            changes_summary=changes_summary,
            guild_id=guild_id,
            channel_id=channel_id,
            affected_users=affected_users or [],
            affected_achievements=affected_achievements or [],
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
            risk_level=risk_level,
            requires_attention=risk_level in ["high", "critical"] or not success,
            metadata=metadata,
            tags=tags,
        )

        # 添加到緩衝區
        self._history_buffer.append(record)
        self._stats["records_created"] += 1

        # 檢查是否需要刷新緩衝區
        if len(self._history_buffer) >= self._buffer_size:
            await self._flush_buffer()

        logger.debug(
            "[歷史管理]記錄操作歷史",
            extra={
                "record_id": record.record_id,
                "action": action.value,
                "category": category.value,
                "operation": operation_name,
                "executor_id": executor_id,
                "success": success,
                "risk_level": risk_level,
            },
        )

        return record

    def _generate_changes_summary(
        self, old_values: dict[str, Any], new_values: dict[str, Any]
    ) -> str:
        """生成變更摘要.

        Args:
            old_values: 舊值
            new_values: 新值

        Returns:
            str: 變更摘要
        """
        if not old_values and not new_values:
            return "無資料變更"

        if not old_values:
            return f"新增資料: {len(new_values)} 個欄位"

        if not new_values:
            return f"刪除資料: {len(old_values)} 個欄位"

        changes = []
        all_keys = set(old_values.keys()) | set(new_values.keys())

        for key in all_keys:
            old_val = old_values.get(key)
            new_val = new_values.get(key)

            if key not in old_values:
                changes.append(f"新增 {key}")
            elif key not in new_values:
                changes.append(f"移除 {key}")
            elif old_val != new_val:
                changes.append(f"修改 {key}")

        if not changes:
            return "無實際變更"

        return (
            f"變更 {len(changes)} 個欄位: "
            + ", ".join(changes[:MAX_CHANGES_DISPLAY])
            + ("..." if len(changes) > MAX_CHANGES_DISPLAY else "")
        )

    def _generate_tags(
        self,
        action: HistoryAction,
        category: HistoryCategory,
        operation_name: str,
        risk_level: str,
    ) -> list[str]:
        """生成操作標籤.

        Args:
            action: 操作動作
            category: 操作分類
            operation_name: 操作名稱
            risk_level: 風險等級

        Returns:
            List[str]: 標籤列表
        """
        tags = [action.value, category.value]

        # 添加風險等級標籤
        if risk_level in ["high", "critical"]:
            tags.append(f"risk_{risk_level}")

        # 添加操作類型標籤
        if "bulk" in operation_name.lower():
            tags.append("bulk_operation")

        if "reset" in operation_name.lower():
            tags.append("destructive")

        if "grant" in operation_name.lower() or "award" in operation_name.lower():
            tags.append("grant_operation")

        if "revoke" in operation_name.lower():
            tags.append("revoke_operation")

        return tags

    async def _flush_buffer(self) -> None:
        """刷新歷史記錄緩衝區到持久化存儲."""
        if not self._history_buffer:
            return

        try:
            if self.database_service:
                # 批量持久化記錄
                for record in self._history_buffer:
                    await self._persist_record(record)

            self._stats["buffer_flushes"] += 1
            buffer_size = len(self._history_buffer)
            self._history_buffer.clear()

            logger.debug(f"[歷史管理]緩衝區刷新完成,處理 {buffer_size} 條記錄")

        except Exception as e:
            logger.error(f"[歷史管理]緩衝區刷新失敗: {e}")

    async def _persist_record(self, record: HistoryRecord) -> None:
        """持久化單條歷史記錄.

        Args:
            record: 歷史記錄
        """
        try:
            # 這裡實現實際的資料庫存儲邏輯
            # 例如:INSERT INTO history_records (...)
            pass

        except Exception as e:
            logger.error(f"[歷史管理]記錄持久化失敗 {record.record_id}: {e}")

    async def query_history(self, query: HistoryQuery) -> list[HistoryRecord]:
        """查詢操作歷史.

        Args:
            query: 查詢參數

        Returns:
            List[HistoryRecord]: 歷史記錄列表
        """
        try:
            self._stats["queries_executed"] += 1

            # 先從緩衝區查詢
            buffer_results = self._query_buffer(query)

            # 再從資料庫查詢
            db_results = []
            if self.database_service:
                db_results = await self._query_database(query)

            # 合併結果並去重
            all_results = buffer_results + db_results
            unique_results = {record.record_id: record for record in all_results}

            # 排序和分頁
            sorted_records = sorted(
                unique_results.values(),
                key=lambda r: getattr(r, query.sort_by, r.timestamp),
                reverse=query.sort_order == "desc",
            )

            return sorted_records[query.offset : query.offset + query.limit]

        except Exception as e:
            logger.error(f"[歷史管理]歷史查詢失敗: {e}")
            return []

    def _query_buffer(self, query: HistoryQuery) -> list[HistoryRecord]:
        """查詢緩衝區中的記錄.

        Args:
            query: 查詢參數

        Returns:
            List[HistoryRecord]: 匹配的記錄列表
        """
        results = []

        for record in self._history_buffer:
            if self._matches_query(record, query):
                results.append(record)

        return results

    async def _query_database(self, query: HistoryQuery) -> list[HistoryRecord]:  # noqa: ARG002
        """從資料庫查詢記錄.

        Args:
            query: 查詢參數

        Returns:
            List[HistoryRecord]: 匹配的記錄列表
        """
        # 這裡實現實際的資料庫查詢邏輯
        return []

    def _matches_query(self, record: HistoryRecord, query: HistoryQuery) -> bool:
        """檢查記錄是否匹配查詢條件.

        Args:
            record: 歷史記錄
            query: 查詢參數

        Returns:
            bool: 是否匹配
        """
        # 基本條件檢查
        conditions = [
            # 檢查時間範圍
            not query.start_time or record.timestamp >= query.start_time,
            not query.end_time or record.timestamp <= query.end_time,
            # 檢查操作動作
            not query.actions or record.action in query.actions,
            # 檢查操作分類
            not query.categories or record.category in query.categories,
            # 檢查操作名稱
            not query.operation_names or record.operation_name in query.operation_names,
            # 檢查執行者
            not query.executor_ids or record.executor_id in query.executor_ids,
            # 檢查目標類型
            not query.target_types or record.target_type in query.target_types,
            # 檢查目標ID
            not query.target_ids or record.target_id in query.target_ids,
            # 檢查成功狀態
            query.success_only is None or record.success == query.success_only,
            # 檢查風險等級
            not query.risk_levels or record.risk_level in query.risk_levels,
        ]

        # 如果基本條件不滿足,直接返回 False
        if not all(conditions):
            return False

        # 檢查搜尋關鍵字
        if query.search_keywords:
            searchable_text = " ".join(
                [
                    record.operation_name,
                    record.target_name,
                    record.changes_summary,
                    record.error_message or "",
                    " ".join(record.tags),
                ]
            ).lower()

            return all(
                keyword.lower() in searchable_text
                for keyword in query.search_keywords
            )

        return True

    async def analyze_history(self, query: HistoryQuery) -> HistoryAnalysis:
        """分析操作歷史.

        Args:
            query: 查詢參數

        Returns:
            HistoryAnalysis: 分析結果
        """
        try:
            start_time = datetime.utcnow()

            # 查詢相關記錄
            records = await self.query_history(query)

            analysis = HistoryAnalysis(query_params=query, total_records=len(records))

            if records:
                analysis.analyzed_period = (
                    min(r.timestamp for r in records),
                    max(r.timestamp for r in records),
                )

            # 操作統計
            self._analyze_operations(records, analysis)

            # 成功率統計
            self._analyze_success_rate(records, analysis)

            # 時間分析
            self._analyze_time_patterns(records, analysis)

            # 趨勢分析
            self._analyze_trends(records, analysis)

            # 用戶活動分析
            self._analyze_user_activity(records, analysis)

            # 風險分析
            self._analyze_risks(records, analysis)

            # 效能分析
            self._analyze_performance(records, analysis)

            self._stats["analyses_generated"] += 1

            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds() * 1000

            logger.info(
                "[歷史管理]歷史分析完成",
                extra={
                    "analysis_id": analysis.analysis_id,
                    "records_analyzed": len(records),
                    "duration_ms": duration,
                },
            )

            return analysis

        except Exception as e:
            logger.error(f"[歷史管理]歷史分析失敗: {e}")
            raise

    def _analyze_operations(
        self, records: list[HistoryRecord], analysis: HistoryAnalysis
    ) -> None:
        """分析操作統計.

        Args:
            records: 歷史記錄列表
            analysis: 分析結果
        """
        for record in records:
            # 按動作統計
            action = record.action.value
            analysis.operations_by_action[action] = (
                analysis.operations_by_action.get(action, 0) + 1
            )

            # 按分類統計
            category = record.category.value
            analysis.operations_by_category[category] = (
                analysis.operations_by_category.get(category, 0) + 1
            )

            # 按執行者統計
            executor = record.executor_id
            analysis.operations_by_executor[executor] = (
                analysis.operations_by_executor.get(executor, 0) + 1
            )

            # 按風險等級統計
            risk_level = record.risk_level
            analysis.operations_by_risk_level[risk_level] = (
                analysis.operations_by_risk_level.get(risk_level, 0) + 1
            )

    def _analyze_success_rate(
        self, records: list[HistoryRecord], analysis: HistoryAnalysis
    ) -> None:
        """分析成功率.

        Args:
            records: 歷史記錄列表
            analysis: 分析結果
        """
        if not records:
            return

        successful_ops = sum(1 for r in records if r.success)
        analysis.success_rate = (successful_ops / len(records)) * 100
        analysis.failed_operations = len(records) - successful_ops

    def _analyze_time_patterns(
        self, records: list[HistoryRecord], analysis: HistoryAnalysis
    ) -> None:
        """分析時間模式.

        Args:
            records: 歷史記錄列表
            analysis: 分析結果
        """
        for record in records:
            timestamp = record.timestamp

            # 按小時統計
            hour = timestamp.hour
            analysis.operations_by_hour[hour] = (
                analysis.operations_by_hour.get(hour, 0) + 1
            )

            # 按日期統計
            day = timestamp.strftime("%Y-%m-%d")
            analysis.operations_by_day[day] = analysis.operations_by_day.get(day, 0) + 1

            # 按月份統計
            month = timestamp.strftime("%Y-%m")
            analysis.operations_by_month[month] = (
                analysis.operations_by_month.get(month, 0) + 1
            )

    def _analyze_trends(
        self, records: list[HistoryRecord], analysis: HistoryAnalysis
    ) -> None:
        """分析趨勢.

        Args:
            records: 歷史記錄列表
            analysis: 分析結果
        """
        # 找出最頻繁的操作
        operation_counts: dict[str, int] = {}
        for record in records:
            op_name = record.operation_name
            operation_counts[op_name] = operation_counts.get(op_name, 0) + 1

        # 排序並取前5名
        top_operations = sorted(
            operation_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]

        for op_name, count in top_operations:
            analysis.trending_operations.append(
                {
                    "operation": op_name,
                    "count": count,
                    "percentage": (count / len(records)) * 100,
                }
            )

        # 找出活動高峰期
        hourly_activity = analysis.operations_by_hour
        if hourly_activity:
            avg_activity = sum(hourly_activity.values()) / len(hourly_activity)

            for hour, count in hourly_activity.items():
                if count > avg_activity * 1.5:  # 超過平均值1.5倍
                    analysis.peak_activity_periods.append(
                        {
                            "hour": hour,
                            "count": count,
                            "above_average": count - avg_activity,
                        }
                    )

    def _analyze_user_activity(
        self, records: list[HistoryRecord], analysis: HistoryAnalysis
    ) -> None:
        """分析用戶活動.

        Args:
            records: 歷史記錄列表
            analysis: 分析結果
        """
        # 最活躍的執行者
        executor_activity = analysis.operations_by_executor
        top_executors = sorted(
            executor_activity.items(), key=lambda x: x[1], reverse=True
        )[:10]

        for executor_id, count in top_executors:
            analysis.most_active_executors.append(
                {
                    "executor_id": executor_id,
                    "operations_count": count,
                    "percentage": (count / len(records)) * 100,
                }
            )

        # 最受影響的用戶
        affected_users_count: dict[int, int] = {}
        for record in records:
            for user_id in record.affected_users:
                affected_users_count[user_id] = affected_users_count.get(user_id, 0) + 1

        top_affected = sorted(
            affected_users_count.items(), key=lambda x: x[1], reverse=True
        )[:10]

        for user_id, count in top_affected:
            analysis.most_affected_users.append(
                {"user_id": user_id, "affected_operations": count}
            )

    def _analyze_risks(
        self, records: list[HistoryRecord], analysis: HistoryAnalysis
    ) -> None:
        """分析風險.

        Args:
            records: 歷史記錄列表
            analysis: 分析結果
        """
        # 高風險操作
        high_risk_records = [r for r in records if r.risk_level in ["high", "critical"]]
        analysis.high_risk_operations = high_risk_records[:20]  # 取前20個

        # 安全事件
        security_incidents = []

        # 檢查失敗的高風險操作
        for record in high_risk_records:
            if not record.success:
                security_incidents.append(
                    {
                        "type": "high_risk_failure",
                        "record_id": record.record_id,
                        "timestamp": record.timestamp.isoformat(),
                        "operation": record.operation_name,
                        "executor_id": record.executor_id,
                        "error": record.error_message,
                    }
                )

        # 檢查異常活動模式
        executor_activity = analysis.operations_by_executor
        avg_activity = (
            sum(executor_activity.values()) / len(executor_activity)
            if executor_activity
            else 0
        )

        for executor_id, activity_count in executor_activity.items():
            if activity_count > avg_activity * 3:  # 超過平均值3倍
                security_incidents.append(
                    {
                        "type": "unusual_activity",
                        "executor_id": executor_id,
                        "activity_count": activity_count,
                        "above_average": activity_count - avg_activity,
                        "description": "用戶活動異常頻繁",
                    }
                )

        analysis.security_incidents = security_incidents

    def _analyze_performance(
        self, records: list[HistoryRecord], analysis: HistoryAnalysis
    ) -> None:
        """分析效能.

        Args:
            records: 歷史記錄列表
            analysis: 分析結果
        """
        # 有效能資料的記錄
        performance_records = [r for r in records if r.duration_ms is not None]

        if not performance_records:
            return

        # 平均操作時間
        total_duration = sum(r.duration_ms for r in performance_records)
        analysis.average_operation_duration = total_duration / len(performance_records)

        # 最慢的操作
        slowest_records = sorted(
            performance_records, key=lambda r: r.duration_ms, reverse=True
        )[:10]

        for record in slowest_records:
            analysis.slowest_operations.append(
                {
                    "record_id": record.record_id,
                    "operation": record.operation_name,
                    "duration_ms": record.duration_ms,
                    "timestamp": record.timestamp.isoformat(),
                    "executor_id": record.executor_id,
                }
            )

    async def export_history(
        self, query: HistoryQuery, format: str = "json", include_analysis: bool = False
    ) -> dict[str, Any]:
        """導出歷史資料.

        Args:
            query: 查詢參數
            format: 導出格式 (json, csv, xlsx)
            include_analysis: 是否包含分析結果

        Returns:
            Dict[str, Any]: 導出結果
        """
        try:
            self._stats["export_operations"] += 1

            # 查詢歷史記錄
            records = await self.query_history(query)

            export_data = {
                "export_id": str(uuid4()),
                "generated_at": datetime.utcnow().isoformat(),
                "format": format,
                "query_params": query.__dict__,
                "total_records": len(records),
                "records": [],
            }

            # 轉換記錄格式
            for record in records:
                export_data["records"].append(self._serialize_record(record))

            # 包含分析結果
            if include_analysis:
                analysis = await self.analyze_history(query)
                export_data["analysis"] = self._serialize_analysis(analysis)

            logger.info(
                "[歷史管理]歷史資料導出完成",
                extra={
                    "export_id": export_data["export_id"],
                    "format": format,
                    "records_count": len(records),
                    "include_analysis": include_analysis,
                },
            )

            return export_data

        except Exception as e:
            logger.error(f"[歷史管理]歷史資料導出失敗: {e}")
            raise

    def _serialize_record(self, record: HistoryRecord) -> dict[str, Any]:
        """序列化歷史記錄.

        Args:
            record: 歷史記錄

        Returns:
            Dict[str, Any]: 序列化後的記錄
        """
        return {
            "record_id": record.record_id,
            "timestamp": record.timestamp.isoformat(),
            "action": record.action.value,
            "category": record.category.value,
            "operation_name": record.operation_name,
            "executor_id": record.executor_id,
            "executor_name": record.executor_name,
            "executor_role": record.executor_role,
            "target_type": record.target_type,
            "target_id": record.target_id,
            "target_name": record.target_name,
            "old_values": record.old_values,
            "new_values": record.new_values,
            "changes_summary": record.changes_summary,
            "guild_id": record.guild_id,
            "channel_id": record.channel_id,
            "success": record.success,
            "error_message": record.error_message,
            "duration_ms": record.duration_ms,
            "affected_users": record.affected_users,
            "affected_achievements": record.affected_achievements,
            "risk_level": record.risk_level,
            "requires_attention": record.requires_attention,
            "tags": record.tags,
            "metadata": record.metadata,
        }

    def _serialize_analysis(self, analysis: HistoryAnalysis) -> dict[str, Any]:
        """序列化分析結果.

        Args:
            analysis: 分析結果

        Returns:
            Dict[str, Any]: 序列化後的分析結果
        """
        return {
            "analysis_id": analysis.analysis_id,
            "generated_at": analysis.generated_at.isoformat(),
            "total_records": analysis.total_records,
            "analyzed_period": [
                analysis.analyzed_period[0].isoformat()
                if analysis.analyzed_period
                else None,
                analysis.analyzed_period[1].isoformat()
                if analysis.analyzed_period
                else None,
            ],
            "operations_by_action": analysis.operations_by_action,
            "operations_by_category": analysis.operations_by_category,
            "operations_by_executor": {
                str(k): v for k, v in analysis.operations_by_executor.items()
            },
            "operations_by_risk_level": analysis.operations_by_risk_level,
            "success_rate": analysis.success_rate,
            "failed_operations": analysis.failed_operations,
            "operations_by_hour": {
                str(k): v for k, v in analysis.operations_by_hour.items()
            },
            "operations_by_day": analysis.operations_by_day,
            "operations_by_month": analysis.operations_by_month,
            "trending_operations": analysis.trending_operations,
            "peak_activity_periods": analysis.peak_activity_periods,
            "most_active_executors": analysis.most_active_executors,
            "most_affected_users": analysis.most_affected_users,
            "high_risk_operations": [
                self._serialize_record(r) for r in analysis.high_risk_operations
            ],
            "security_incidents": analysis.security_incidents,
            "average_operation_duration": analysis.average_operation_duration,
            "slowest_operations": analysis.slowest_operations,
        }

    async def get_history_statistics(self) -> dict[str, Any]:
        """獲取歷史管理統計資料.

        Returns:
            Dict[str, Any]: 統計資料
        """
        # 清理過期項目
        await self._cleanup_old_records()

        return {
            **self._stats,
            "buffer_size": len(self._history_buffer),
            "buffer_capacity": self._buffer_size,
        }

    async def _cleanup_old_records(self, retention_days: int = 365) -> int:
        """清理舊的歷史記錄.

        Args:
            retention_days: 保留天數

        Returns:
            int: 清理的記錄數量
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

            # 清理緩衝區中的舊記錄
            buffer_before = len(self._history_buffer)
            self._history_buffer = [
                record
                for record in self._history_buffer
                if record.timestamp >= cutoff_date
            ]
            buffer_cleaned = buffer_before - len(self._history_buffer)

            # 清理資料庫中的舊記錄
            db_cleaned = 0
            if self.database_service:
                # 這裡實現資料庫清理邏輯
                pass

            total_cleaned = buffer_cleaned + db_cleaned

            if total_cleaned > 0:
                logger.info(
                    "[歷史管理]舊記錄清理完成",
                    extra={
                        "retention_days": retention_days,
                        "cutoff_date": cutoff_date.isoformat(),
                        "cleaned_count": total_cleaned,
                    },
                )

            return total_cleaned

        except Exception as e:
            logger.error(f"[歷史管理]舊記錄清理失敗: {e}")
            return 0

    async def __aenter__(self):
        """異步上下文管理器入口."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """異步上下文管理器出口."""
        # 刷新緩衝區
        await self._flush_buffer()
