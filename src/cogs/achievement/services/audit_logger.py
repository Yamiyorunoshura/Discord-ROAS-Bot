"""成就系統審計日誌系統.

此模組提供成就系統的審計日誌功能,包含:
- 操作日誌記錄
- 安全事件追蹤
- 審計報告生成
- 合規性監控

確保所有管理操作都有完整的審計軌跡,滿足安全合規要求.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

from ..constants import MAX_FAILED_OPERATIONS, NON_WORK_HOURS_END, NON_WORK_HOURS_START

logger = logging.getLogger(__name__)

class AuditEventType(Enum):
    """審計事件類型枚舉."""

    # 成就管理操作
    ACHIEVEMENT_GRANTED = "achievement_granted"
    ACHIEVEMENT_REVOKED = "achievement_revoked"
    PROGRESS_ADJUSTED = "progress_adjusted"
    USER_DATA_RESET = "user_data_reset"

    # 批量操作
    BULK_GRANT = "bulk_grant"
    BULK_REVOKE = "bulk_revoke"
    BULK_RESET = "bulk_reset"

    # 系統操作
    ADMIN_LOGIN = "admin_login"
    PERMISSION_CHECK = "permission_check"
    SECURITY_VIOLATION = "security_violation"
    DATA_EXPORT = "data_export"
    CONFIG_CHANGE = "config_change"

    # 查詢操作
    USER_LOOKUP = "user_lookup"
    DATA_ACCESS = "data_access"
    REPORT_GENERATED = "report_generated"

class AuditSeverity(Enum):
    """審計嚴重性等級."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AuditStatus(Enum):
    """審計狀態."""

    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    CANCELLED = "cancelled"

@dataclass
class AuditContext:
    """審計上下文資訊."""

    user_id: int
    guild_id: int
    channel_id: int | None = None
    interaction_id: str | None = None
    session_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None

@dataclass
class AuditEvent:
    """審計事件記錄."""

    event_id: str = field(default_factory=lambda: str(uuid4()))
    event_type: AuditEventType = AuditEventType.USER_LOOKUP
    severity: AuditSeverity = AuditSeverity.INFO
    status: AuditStatus = AuditStatus.SUCCESS

    # 上下文資訊
    context: AuditContext | None = None

    # 操作詳情
    operation_name: str = ""
    target_type: str = ""  # user, achievement, category, etc.
    target_id: int | str | None = None
    target_ids: list[int | str] = field(default_factory=list)

    # 操作資料
    old_values: dict[str, Any] = field(default_factory=dict)
    new_values: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    # 時間戳記
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # 結果資訊
    success: bool = True
    error_message: str | None = None
    duration_ms: float | None = None

    # 安全相關
    risk_level: str = "low"  # low, medium, high, critical
    requires_approval: bool = False
    approved_by: int | None = None
    approval_timestamp: datetime | None = None

@dataclass
class AuditQuery:
    """審計查詢參數."""

    event_types: list[AuditEventType] | None = None
    severity_levels: list[AuditSeverity] | None = None
    user_ids: list[int] | None = None
    target_types: list[str] | None = None
    target_ids: list[int | str] | None = None

    start_time: datetime | None = None
    end_time: datetime | None = None

    risk_levels: list[str] | None = None
    success_only: bool | None = None

    limit: int = 100
    offset: int = 0

    sort_by: str = "timestamp"
    sort_order: str = "desc"  # asc, desc

@dataclass
class AuditReport:
    """審計報告."""

    report_id: str = field(default_factory=lambda: str(uuid4()))
    report_type: str = ""
    generated_at: datetime = field(default_factory=datetime.utcnow)
    generated_by: int = 0

    query_params: AuditQuery | None = None
    events: list[AuditEvent] = field(default_factory=list)

    # 統計資料
    total_events: int = 0
    events_by_type: dict[str, int] = field(default_factory=dict)
    events_by_severity: dict[str, int] = field(default_factory=dict)
    events_by_status: dict[str, int] = field(default_factory=dict)

    # 安全分析
    security_issues: list[dict[str, Any]] = field(default_factory=list)
    risk_analysis: dict[str, Any] = field(default_factory=dict)

    # 趨勢分析
    timeline_data: list[dict[str, Any]] = field(default_factory=list)

    duration_ms: float | None = None

class AuditLogger:
    """審計日誌記錄器.

    負責記錄、查詢和分析審計事件.
    """

    def __init__(self, database_service=None, cache_service=None):
        """初始化審計日誌記錄器.

        Args:
            database_service: 資料庫服務實例
            cache_service: 快取服務實例
        """
        self.database_service = database_service
        self.cache_service = cache_service

        # In-memory event buffer for high-frequency writes
        self._event_buffer: list[AuditEvent] = []
        self._buffer_size = 100

        # 統計資料
        self._stats = {
            "events_logged": 0,
            "events_queried": 0,
            "reports_generated": 0,
            "security_violations": 0,
            "buffer_flushes": 0,
        }

        # 風險評估規則
        self._risk_rules = self._initialize_risk_rules()

        logger.info("AuditLogger 初始化完成")

    def _initialize_risk_rules(self) -> dict[str, dict[str, Any]]:
        """初始化風險評估規則.

        Returns:
            Dict[str, Dict[str, Any]]: 風險評估規則
        """
        return {
            # 高風險操作
            "bulk_operations": {
                "risk_level": "high",
                "requires_approval": True,
                "threshold": 10,  # 超過10個目標視為高風險
                "description": "批量操作涉及多個用戶",
            },
            "data_reset": {
                "risk_level": "critical",
                "requires_approval": True,
                "description": "用戶資料重置操作",
            },
            "permission_escalation": {
                "risk_level": "critical",
                "requires_approval": True,
                "description": "權限提升操作",
            },
            # 中風險操作
            "manual_adjustment": {
                "risk_level": "medium",
                "requires_approval": False,
                "description": "手動調整成就進度",
            },
            "achievement_revoke": {
                "risk_level": "medium",
                "requires_approval": False,
                "description": "撤銷用戶成就",
            },
            # 異常模式檢測
            "rapid_operations": {
                "risk_level": "medium",
                "threshold": 50,  # 每分鐘超過50次操作
                "time_window": 60,  # 秒
                "description": "短時間內大量操作",
            },
            "off_hours_access": {
                "risk_level": "medium",
                "time_range": [(22, 6)],  # 22:00-06:00
                "description": "非工作時間訪問",
            },
        }

    async def log_event(
        self,
        event_type: AuditEventType,
        context: AuditContext,
        operation_name: str = "",
        target_type: str = "",
        target_id: int | str | None = None,
        target_ids: list[int | str] | None = None,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs,
    ) -> AuditEvent:
        """記錄審計事件.

        Args:
            event_type: 事件類型
            context: 審計上下文
            operation_name: 操作名稱
            target_type: 目標類型
            target_id: 目標ID
            target_ids: 目標ID列表
            old_values: 操作前的值
            new_values: 操作後的值
            metadata: 額外元數據
            **kwargs: 額外參數

        Returns:
            AuditEvent: 審計事件記錄
        """
        event = AuditEvent(
            event_type=event_type,
            context=context,
            operation_name=operation_name,
            target_type=target_type,
            target_id=target_id,
            target_ids=target_ids or [],
            old_values=old_values or {},
            new_values=new_values or {},
            metadata=metadata or {},
        )

        # 設置其他屬性
        for key, value in kwargs.items():
            if hasattr(event, key):
                setattr(event, key, value)

        # 風險評估
        await self._assess_risk(event)

        # 添加到緩衝區
        self._event_buffer.append(event)
        self._stats["events_logged"] += 1

        # 檢查是否需要刷新緩衝區
        if len(self._event_buffer) >= self._buffer_size:
            await self._flush_buffer()

        # 記錄高風險事件
        if event.risk_level in ["high", "critical"]:
            await self._handle_high_risk_event(event)

        logger.debug(
            "[審計日誌]記錄事件",
            extra={
                "event_id": event.event_id,
                "event_type": event_type.value,
                "user_id": context.user_id,
                "operation": operation_name,
                "risk_level": event.risk_level,
            },
        )

        return event

    async def _assess_risk(self, event: AuditEvent) -> None:
        """評估事件風險等級.

        Args:
            event: 審計事件
        """
        risk_level = "low"
        requires_approval = False

        try:
            # 檢查操作類型風險
            if event.event_type in [
                AuditEventType.BULK_RESET,
                AuditEventType.USER_DATA_RESET,
            ]:
                risk_level = "critical"
                requires_approval = True

            elif event.event_type in [
                AuditEventType.BULK_GRANT,
                AuditEventType.BULK_REVOKE,
                AuditEventType.ACHIEVEMENT_REVOKED,
            ]:
                # 檢查批量操作規模
                target_count = len(event.target_ids) if event.target_ids else 1
                if target_count >= self._risk_rules["bulk_operations"]["threshold"]:
                    risk_level = "high"
                    requires_approval = True
                else:
                    risk_level = "medium"

            elif event.event_type == AuditEventType.PROGRESS_ADJUSTED:
                risk_level = "medium"

            # 檢查異常模式
            if event.context:
                # 檢查非工作時間訪問
                current_hour = datetime.utcnow().hour
                if current_hour >= NON_WORK_HOURS_START or current_hour <= NON_WORK_HOURS_END:
                    if risk_level == "low":
                        risk_level = "medium"
                    event.metadata["off_hours_access"] = True

                # 檢查快速操作模式
                rapid_ops = await self._check_rapid_operations(event.context.user_id)
                if rapid_ops:
                    if risk_level in ["low", "medium"]:
                        risk_level = "medium"
                    event.metadata["rapid_operations"] = rapid_ops

            event.risk_level = risk_level
            event.requires_approval = requires_approval

        except Exception as e:
            logger.error(f"[審計日誌]風險評估失敗: {e}")
            event.risk_level = "medium"  # 預設為中風險

    async def _check_rapid_operations(self, user_id: int) -> bool:
        """檢查是否存在快速操作模式.

        Args:
            user_id: 用戶ID

        Returns:
            bool: 是否存在快速操作
        """
        try:
            # 檢查最近1分鐘內的操作次數
            recent_threshold = datetime.utcnow() - timedelta(minutes=1)
            recent_ops = [
                event
                for event in self._event_buffer
                if (
                    event.context
                    and event.context.user_id == user_id
                    and event.timestamp >= recent_threshold
                )
            ]

            rapid_threshold = self._risk_rules["rapid_operations"]["threshold"]
            return len(recent_ops) >= rapid_threshold

        except Exception as e:
            logger.error(f"[審計日誌]快速操作檢查失敗: {e}")
            return False

    async def _handle_high_risk_event(self, event: AuditEvent) -> None:
        """處理高風險事件.

        Args:
            event: 審計事件
        """
        try:
            # 立即記錄到持久化存儲
            if self.database_service:
                await self._persist_event(event)

            # 觸發安全警告
            await self._trigger_security_alert(event)

            # 更新統計
            self._stats["security_violations"] += 1

            logger.warning(
                "[審計日誌]高風險事件檢測",
                extra={
                    "event_id": event.event_id,
                    "risk_level": event.risk_level,
                    "user_id": event.context.user_id if event.context else None,
                    "operation": event.operation_name,
                },
            )

        except Exception as e:
            logger.error(f"[審計日誌]高風險事件處理失敗: {e}")

    async def _trigger_security_alert(self, event: AuditEvent) -> None:
        """觸發安全警告.

        Args:
            event: 審計事件
        """
        # 這裡可以實現各種警告機制:
        # - 發送通知到管理員頻道
        # - 記錄到安全日誌
        # - 觸發外部監控系統

        alert_data = {
            "event_id": event.event_id,
            "alert_type": "security_violation",
            "risk_level": event.risk_level,
            "user_id": event.context.user_id if event.context else None,
            "operation": event.operation_name,
            "timestamp": event.timestamp.isoformat(),
            "details": event.metadata,
        }

        logger.warning(f"[安全警告]{alert_data}")

    async def _flush_buffer(self) -> None:
        """刷新事件緩衝區到持久化存儲."""
        if not self._event_buffer:
            return

        try:
            if self.database_service:
                # 批量持久化事件
                for event in self._event_buffer:
                    await self._persist_event(event)

            self._stats["buffer_flushes"] += 1
            buffer_size = len(self._event_buffer)
            self._event_buffer.clear()

            logger.debug(f"[審計日誌]緩衝區刷新完成,處理 {buffer_size} 個事件")

        except Exception as e:
            logger.error(f"[審計日誌]緩衝區刷新失敗: {e}")

    async def _persist_event(self, event: AuditEvent) -> None:
        """持久化單個事件.

        Args:
            event: 審計事件
        """
        try:
            # 這裡實現實際的資料庫存儲邏輯
            # 例如:INSERT INTO audit_events (...)
            pass

        except Exception as e:
            logger.error(f"[審計日誌]事件持久化失敗 {event.event_id}: {e}")

    async def query_events(self, query: AuditQuery) -> list[AuditEvent]:
        """查詢審計事件.

        Args:
            query: 查詢參數

        Returns:
            List[AuditEvent]: 審計事件列表
        """
        try:
            self._stats["events_queried"] += 1

            # 先從緩衝區查詢
            buffer_results = self._query_buffer(query)

            # 再從資料庫查詢
            db_results = []
            if self.database_service:
                db_results = await self._query_database(query)

            # 合併結果並去重
            all_results = buffer_results + db_results
            unique_results = {event.event_id: event for event in all_results}

            # 排序和分頁
            sorted_events = sorted(
                unique_results.values(),
                key=lambda e: getattr(e, query.sort_by, e.timestamp),
                reverse=query.sort_order == "desc",
            )

            return sorted_events[query.offset : query.offset + query.limit]

        except Exception as e:
            logger.error(f"[審計日誌]事件查詢失敗: {e}")
            return []

    def _query_buffer(self, query: AuditQuery) -> list[AuditEvent]:
        """查詢緩衝區中的事件.

        Args:
            query: 查詢參數

        Returns:
            List[AuditEvent]: 匹配的事件列表
        """
        results = []

        for event in self._event_buffer:
            if self._matches_query(event, query):
                results.append(event)

        return results

    async def _query_database(self, query: AuditQuery) -> list[AuditEvent]:  # noqa: ARG002
        """從資料庫查詢事件.

        Args:
            query: 查詢參數

        Returns:
            List[AuditEvent]: 匹配的事件列表
        """
        # TODO: 實現實際的資料庫查詢邏輯
        return []

    def _matches_query(self, event: AuditEvent, query: AuditQuery) -> bool:
        """檢查事件是否匹配查詢條件.

        Args:
            event: 審計事件
            query: 查詢參數

        Returns:
            bool: 是否匹配
        """
        # 組合所有條件檢查
        conditions = [
            # 檢查事件類型
            not query.event_types or event.event_type in query.event_types,
            # 檢查嚴重性等級
            not query.severity_levels or event.severity in query.severity_levels,
            # 檢查用戶ID
            not query.user_ids or (event.context and event.context.user_id in query.user_ids),
            # 檢查目標類型
            not query.target_types or event.target_type in query.target_types,
            # 檢查目標ID
            not query.target_ids or (
                event.target_id in query.target_ids or
                any(tid in query.target_ids for tid in event.target_ids)
            ),
            # 檢查時間範圍
            not query.start_time or event.timestamp >= query.start_time,
            not query.end_time or event.timestamp <= query.end_time,
            # 檢查風險等級
            not query.risk_levels or event.risk_level in query.risk_levels,
            # 檢查成功狀態
            query.success_only is None or event.success == query.success_only
        ]

        return all(conditions)

    async def generate_report(
        self, report_type: str, query: AuditQuery, generated_by: int
    ) -> AuditReport:
        """生成審計報告.

        Args:
            report_type: 報告類型
            query: 查詢參數
            generated_by: 報告生成者ID

        Returns:
            AuditReport: 審計報告
        """
        start_time = datetime.utcnow()

        try:
            # 查詢事件
            events = await self.query_events(query)

            # 創建報告
            report = AuditReport(
                report_type=report_type,
                generated_by=generated_by,
                query_params=query,
                events=events,
            )

            # 生成統計資料
            await self._generate_report_statistics(report)

            # 生成安全分析
            await self._generate_security_analysis(report)

            # 生成趨勢分析
            await self._generate_timeline_analysis(report)

            # 計算執行時間
            end_time = datetime.utcnow()
            report.duration_ms = (end_time - start_time).total_seconds() * 1000

            self._stats["reports_generated"] += 1

            logger.info(
                "[審計日誌]報告生成完成",
                extra={
                    "report_id": report.report_id,
                    "report_type": report_type,
                    "events_count": len(events),
                    "duration_ms": report.duration_ms,
                },
            )

            return report

        except Exception as e:
            logger.error(f"[審計日誌]報告生成失敗: {e}")
            raise

    async def _generate_report_statistics(self, report: AuditReport) -> None:
        """生成報告統計資料.

        Args:
            report: 審計報告
        """
        report.total_events = len(report.events)

        # 按類型統計
        for event in report.events:
            event_type = event.event_type.value
            report.events_by_type[event_type] = (
                report.events_by_type.get(event_type, 0) + 1
            )

        # 按嚴重性統計
        for event in report.events:
            severity = event.severity.value
            report.events_by_severity[severity] = (
                report.events_by_severity.get(severity, 0) + 1
            )

        # 按狀態統計
        for event in report.events:
            status = event.status.value
            report.events_by_status[status] = report.events_by_status.get(status, 0) + 1

    async def _generate_security_analysis(self, report: AuditReport) -> None:
        """生成安全分析.

        Args:
            report: 審計報告
        """
        security_issues = []

        # 分析高風險事件
        high_risk_events = [
            e for e in report.events if e.risk_level in ["high", "critical"]
        ]
        if high_risk_events:
            security_issues.append(
                {
                    "type": "high_risk_operations",
                    "count": len(high_risk_events),
                    "description": f"檢測到 {len(high_risk_events)} 個高風險操作",
                    "severity": "warning",
                }
            )

        # 分析失敗操作
        failed_events = [e for e in report.events if not e.success]
        if len(failed_events) > MAX_FAILED_OPERATIONS:  # 超過失敗操作限制
            security_issues.append(
                {
                    "type": "high_failure_rate",
                    "count": len(failed_events),
                    "description": f"操作失敗率過高: {len(failed_events)}/{len(report.events)}",
                    "severity": "warning",
                }
            )

        # 分析異常模式
        user_activities = {}
        for event in report.events:
            if event.context:
                user_id = event.context.user_id
                user_activities[user_id] = user_activities.get(user_id, 0) + 1

        # 檢查異常活躍用戶
        avg_activity = (
            sum(user_activities.values()) / len(user_activities)
            if user_activities
            else 0
        )
        for user_id, activity_count in user_activities.items():
            if activity_count > avg_activity * 3:  # 超過平均值3倍
                security_issues.append(
                    {
                        "type": "unusual_user_activity",
                        "user_id": user_id,
                        "count": activity_count,
                        "description": f"用戶 {user_id} 活動異常頻繁 ({activity_count} 次操作)",
                        "severity": "info",
                    }
                )

        report.security_issues = security_issues

        # 風險分析摘要
        report.risk_analysis = {
            "total_high_risk": len(high_risk_events),
            "failure_rate": len(failed_events) / len(report.events)
            if report.events
            else 0,
            "unique_users": len(user_activities),
            "most_active_user": max(user_activities.items(), key=lambda x: x[1])
            if user_activities
            else None,
        }

    async def _generate_timeline_analysis(self, report: AuditReport) -> None:
        """生成時間線分析.

        Args:
            report: 審計報告
        """
        timeline_data = []

        # 按小時分組事件
        hourly_events = {}
        for event in report.events:
            hour_key = event.timestamp.strftime("%Y-%m-%d %H:00")
            if hour_key not in hourly_events:
                hourly_events[hour_key] = {
                    "timestamp": hour_key,
                    "total": 0,
                    "by_type": {},
                    "by_severity": {},
                    "high_risk": 0,
                }

            hourly_data = hourly_events[hour_key]
            hourly_data["total"] += 1

            # 按類型統計
            event_type = event.event_type.value
            hourly_data["by_type"][event_type] = (
                hourly_data["by_type"].get(event_type, 0) + 1
            )

            # 按嚴重性統計
            severity = event.severity.value
            hourly_data["by_severity"][severity] = (
                hourly_data["by_severity"].get(severity, 0) + 1
            )

            # 高風險事件統計
            if event.risk_level in ["high", "critical"]:
                hourly_data["high_risk"] += 1

        # 轉換為列表並排序
        timeline_data = sorted(hourly_events.values(), key=lambda x: x["timestamp"])
        report.timeline_data = timeline_data

    async def get_audit_statistics(self) -> dict[str, Any]:
        """獲取審計統計資料.

        Returns:
            Dict[str, Any]: 統計資料
        """
        return {
            **self._stats,
            "buffer_size": len(self._event_buffer),
            "buffer_capacity": self._buffer_size,
            "risk_rules_count": len(self._risk_rules),
        }

    async def cleanup_old_events(self, retention_days: int = 90) -> int:
        """清理舊的審計事件.

        Args:
            retention_days: 保留天數

        Returns:
            int: 清理的事件數量
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

            # 清理緩衝區中的舊事件
            buffer_before = len(self._event_buffer)
            self._event_buffer = [
                event for event in self._event_buffer if event.timestamp >= cutoff_date
            ]
            buffer_cleaned = buffer_before - len(self._event_buffer)

            # 清理資料庫中的舊事件
            db_cleaned = 0
            if self.database_service:
                # 這裡實現資料庫清理邏輯
                pass

            total_cleaned = buffer_cleaned + db_cleaned

            logger.info(
                "[審計日誌]舊事件清理完成",
                extra={
                    "retention_days": retention_days,
                    "cutoff_date": cutoff_date.isoformat(),
                    "cleaned_count": total_cleaned,
                },
            )

            return total_cleaned

        except Exception as e:
            logger.error(f"[審計日誌]舊事件清理失敗: {e}")
            return 0

    async def __aenter__(self):
        """異步上下文管理器入口."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """異步上下文管理器出口."""
        # 刷新緩衝區
        await self._flush_buffer()
