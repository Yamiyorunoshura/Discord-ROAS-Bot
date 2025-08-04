"""成就系統安全組件測試.

測試安全系統的核心功能,包含:
- 審計日誌記錄和查詢
- 權限驗證和管理
- 操作歷史追蹤
- 安全挑戰和審批
"""

from datetime import datetime

import pytest

from src.cogs.achievement.services.audit_logger import (
    AuditContext,
    AuditEvent,
    AuditEventType,
    AuditLogger,
    AuditQuery,
    AuditSeverity,
)
from src.cogs.achievement.services.history_manager import (
    HistoryAction,
    HistoryCategory,
    HistoryManager,
    HistoryQuery,
    HistoryRecord,
)
from src.cogs.achievement.services.security_validator import (
    AuthenticationMethod,
    PermissionLevel,
    SecurityValidator,
)
from tests.test_utils import (
    AsyncTestCase,
)


class TestAuditLogger(AsyncTestCase):
    """審計日誌記錄器測試類."""

    def setup_method(self):
        """設置測試環境."""
        super().setup_method()

        self.audit_logger = AuditLogger(
            database_service=self.mock_database_service,
            cache_service=self.mock_cache_service,
        )

    @pytest.mark.asyncio
    async def test_audit_logger_initialization(self):
        """測試審計日誌記錄器初始化."""
        assert self.audit_logger.database_service == self.mock_database_service
        assert self.audit_logger.cache_service == self.mock_cache_service
        assert len(self.audit_logger._event_buffer) == 0
        assert self.audit_logger._buffer_size == 100
        assert len(self.audit_logger._risk_rules) > 0

    @pytest.mark.asyncio
    async def test_log_event(self):
        """測試記錄審計事件."""
        context = AuditContext(
            user_id=self.test_user.id,
            guild_id=self.test_guild.id,
            interaction_id="test_interaction",
        )

        event = await self.audit_logger.log_event(
            event_type=AuditEventType.ACHIEVEMENT_GRANTED,
            context=context,
            operation_name="test_grant_achievement",
            target_type="user",
            target_id=self.test_user.id,
            old_values={},
            new_values={"achievement_id": 1},
            metadata={"test": True},
        )

        # 檢查事件屬性
        assert isinstance(event, AuditEvent)
        assert event.event_type == AuditEventType.ACHIEVEMENT_GRANTED
        assert event.context.user_id == self.test_user.id
        assert event.operation_name == "test_grant_achievement"
        assert event.success is True
        assert event.metadata["test"] is True

        # 檢查事件已添加到緩衝區
        assert len(self.audit_logger._event_buffer) == 1
        assert self.audit_logger._stats["events_logged"] == 1

    @pytest.mark.asyncio
    async def test_risk_assessment(self):
        """測試風險評估."""
        context = AuditContext(user_id=self.test_user.id, guild_id=self.test_guild.id)

        # 測試低風險操作
        low_risk_event = await self.audit_logger.log_event(
            event_type=AuditEventType.ACHIEVEMENT_GRANTED,
            context=context,
            operation_name="grant_single_achievement",
        )
        assert low_risk_event.risk_level == "low"
        assert low_risk_event.requires_approval is False

        # 測試高風險操作
        high_risk_event = await self.audit_logger.log_event(
            event_type=AuditEventType.USER_DATA_RESET,
            context=context,
            operation_name="reset_user_data",
        )
        assert high_risk_event.risk_level == "critical"
        assert high_risk_event.requires_approval is True

    @pytest.mark.asyncio
    async def test_query_events(self):
        """測試查詢審計事件."""
        context = AuditContext(user_id=self.test_user.id, guild_id=self.test_guild.id)

        # 創建多個測試事件
        await self.audit_logger.log_event(
            event_type=AuditEventType.ACHIEVEMENT_GRANTED,
            context=context,
            operation_name="grant_1",
        )
        await self.audit_logger.log_event(
            event_type=AuditEventType.ACHIEVEMENT_REVOKED,
            context=context,
            operation_name="revoke_1",
        )
        await self.audit_logger.log_event(
            event_type=AuditEventType.PROGRESS_UPDATED,
            context=context,
            operation_name="progress_1",
        )

        # 查詢所有事件
        all_events = await self.audit_logger.query_events(AuditQuery(limit=10))
        assert len(all_events) == 3

        # 按事件類型查詢
        grant_events = await self.audit_logger.query_events(
            AuditQuery(event_types=[AuditEventType.ACHIEVEMENT_GRANTED])
        )
        assert len(grant_events) == 1
        assert grant_events[0].event_type == AuditEventType.ACHIEVEMENT_GRANTED

        # 按用戶ID查詢
        user_events = await self.audit_logger.query_events(
            AuditQuery(user_ids=[self.test_user.id])
        )
        assert len(user_events) == 3

    @pytest.mark.asyncio
    async def test_generate_report(self):
        """測試生成審計報告."""
        context = AuditContext(user_id=self.test_user.id, guild_id=self.test_guild.id)

        # 創建測試事件
        for i in range(5):
            await self.audit_logger.log_event(
                event_type=AuditEventType.ACHIEVEMENT_GRANTED,
                context=context,
                operation_name=f"grant_{i}",
                success=i % 2 == 0,  # 一半成功,一半失敗
            )

        # 生成報告
        report = await self.audit_logger.generate_report(
            report_type="test_report",
            query=AuditQuery(limit=10),
            generated_by=self.test_user.id,
        )

        # 檢查報告
        assert report.report_type == "test_report"
        assert report.generated_by == self.test_user.id
        assert report.total_events == 5
        assert len(report.events) == 5
        assert "achievement_granted" in report.events_by_type
        assert report.events_by_type["achievement_granted"] == 5

        # 檢查統計資料
        assert report.summary["total_issues"] >= 0
        assert self.audit_logger._stats["reports_generated"] == 1

    @pytest.mark.asyncio
    async def test_buffer_management(self):
        """測試緩衝區管理."""
        context = AuditContext(user_id=self.test_user.id, guild_id=self.test_guild.id)

        # 填滿緩衝區
        initial_buffer_size = self.audit_logger._buffer_size
        self.audit_logger._buffer_size = 3  # 設置小的緩衝區大小用於測試

        # 記錄超過緩衝區大小的事件
        for i in range(5):
            await self.audit_logger.log_event(
                event_type=AuditEventType.ACHIEVEMENT_GRANTED,
                context=context,
                operation_name=f"test_{i}",
            )

        # 檢查緩衝區是否被刷新
        assert len(self.audit_logger._event_buffer) < 5
        assert self.audit_logger._stats["buffer_flushes"] > 0

        # 恢復原始緩衝區大小
        self.audit_logger._buffer_size = initial_buffer_size


class TestSecurityValidator(AsyncTestCase):
    """安全驗證器測試類."""

    def setup_method(self):
        """設置測試環境."""
        super().setup_method()

        self.security_validator = SecurityValidator()

    @pytest.mark.asyncio
    async def test_security_validator_initialization(self):
        """測試安全驗證器初始化."""
        assert len(self.security_validator._security_tokens) == 0
        assert len(self.security_validator._permission_grants) == 0
        assert len(self.security_validator._security_challenges) == 0
        assert len(self.security_validator._operation_approvals) == 0
        assert len(self.security_validator._risk_rules) > 0

    @pytest.mark.asyncio
    async def test_permission_management(self):
        """測試權限管理."""
        user_id = self.test_user.id

        # 授予權限
        grant = await self.security_validator.grant_permission(
            user_id=user_id,
            permission_level=PermissionLevel.ADMIN,
            granted_by=11111,
            expires_in_hours=24,
        )

        assert grant.user_id == user_id
        assert grant.permission_level == PermissionLevel.ADMIN
        assert grant.granted_by == 11111
        assert grant.expires_at is not None

        # 檢查權限
        user_permission = await self.security_validator._get_user_permission(user_id)
        assert user_permission == PermissionLevel.ADMIN

        # 撤銷權限
        success = await self.security_validator.revoke_permission(
            grant_id=grant.grant_id, revoked_by=11111, reason="測試撤銷"
        )
        assert success is True

        # 檢查權限是否被撤銷
        user_permission = await self.security_validator._get_user_permission(user_id)
        assert user_permission == PermissionLevel.BASIC

    @pytest.mark.asyncio
    async def test_permission_check(self):
        """測試權限檢查."""
        user_id = self.test_user.id

        # 授予管理員權限
        await self.security_validator.grant_permission(
            user_id=user_id, permission_level=PermissionLevel.ADMIN, granted_by=11111
        )

        # 檢查高權限操作
        result = await self.security_validator.check_permission(
            user_id=user_id,
            operation_type="grant_achievement",
            context={"guild_id": self.test_guild.id},
        )

        assert result["allowed"] is True
        assert result["user_permission"] == PermissionLevel.ADMIN.value

        # 檢查超級管理員權限的操作
        result = await self.security_validator.check_permission(
            user_id=user_id,
            operation_type="bulk_reset",
            context={"guild_id": self.test_guild.id},
        )

        assert result["allowed"] is False
        assert result["reason"] == "insufficient_permission"

    @pytest.mark.asyncio
    async def test_security_token_management(self):
        """測試安全令牌管理."""
        user_id = self.test_user.id
        operation_type = "grant_achievement"

        # 生成安全令牌
        token = await self.security_validator.generate_security_token(
            user_id=user_id, operation_type=operation_type, expires_in_minutes=15
        )

        assert token.user_id == user_id
        assert token.operation_type == operation_type
        assert token.used is False
        assert token.expires_at > datetime.utcnow()

        # 驗證令牌
        validation_result = await self.security_validator.validate_security_token(
            token_value=token.token_value,
            user_id=user_id,
            operation_type=operation_type,
        )

        assert validation_result["valid"] is True
        assert validation_result["token"] == token
        assert token.used is True  # 令牌應該被標記為已使用

        # 再次驗證已使用的令牌
        validation_result = await self.security_validator.validate_security_token(
            token_value=token.token_value,
            user_id=user_id,
            operation_type=operation_type,
        )

        assert validation_result["valid"] is False
        assert validation_result["reason"] == "token_already_used"

    @pytest.mark.asyncio
    async def test_security_challenge(self):
        """測試安全挑戰."""
        user_id = self.test_user.id
        operation_type = "revoke_achievement"

        # 創建安全挑戰
        challenge = await self.security_validator.create_security_challenge(
            user_id=user_id,
            operation_type=operation_type,
            challenge_type=AuthenticationMethod.TOKEN,
        )

        assert challenge.user_id == user_id
        assert challenge.operation_type == operation_type
        assert challenge.challenge_type == AuthenticationMethod.TOKEN
        assert challenge.attempts == 0
        assert challenge.solved is False

        # 從挑戰數據中提取正確答案(這是測試環境的簡化)
        challenge_code = challenge.challenge_data.split(": ")[1]

        # 解決挑戰
        result = await self.security_validator.solve_security_challenge(
            challenge_id=challenge.challenge_id,
            response=challenge_code,
            user_id=user_id,
        )

        assert result["success"] is True
        assert "token" in result
        assert "expires_at" in result
        assert challenge.solved is True

    @pytest.mark.asyncio
    async def test_operation_approval(self):
        """測試操作審批."""
        user_id = self.test_user.id
        approver_id = 11111

        # 授予審批者管理員權限
        await self.security_validator.grant_permission(
            user_id=approver_id,
            permission_level=PermissionLevel.ADMIN,
            granted_by=approver_id,
        )

        # 請求操作審批
        approval = await self.security_validator.request_operation_approval(
            requested_by=user_id,
            operation_type="user_data_reset",
            operation_details={"user_id": user_id},
            context={"guild_id": self.test_guild.id},
        )

        assert approval.requested_by == user_id
        assert approval.operation_type == "user_data_reset"
        assert approval.status == "pending"
        assert approval.required_approvers == 1

        # 審批操作
        approval_result = await self.security_validator.approve_operation(
            approval_id=approval.approval_id, approver_id=approver_id, notes="測試審批"
        )

        assert approval_result["success"] is True
        assert approval_result["status"] == "approved"
        assert "token" in approval_result
        assert approval.status == "approved"
        assert approver_id in approval.current_approvers

    @pytest.mark.asyncio
    async def test_security_statistics(self):
        """測試安全統計."""
        user_id = self.test_user.id

        # 執行一些安全操作
        await self.security_validator.generate_security_token(user_id, "test_op")
        await self.security_validator.create_security_challenge(user_id, "test_op")
        await self.security_validator.check_permission(user_id, "test_op", {})

        # 獲取統計
        stats = await self.security_validator.get_security_statistics()

        assert stats["tokens_generated"] == 1
        assert stats["challenges_created"] == 1
        assert stats["permission_checks"] == 1
        assert stats["active_tokens"] == 1
        assert stats["active_challenges"] == 1


class TestHistoryManager(AsyncTestCase):
    """歷史管理器測試類."""

    def setup_method(self):
        """設置測試環境."""
        super().setup_method()

        self.history_manager = HistoryManager(
            database_service=self.mock_database_service,
            cache_service=self.mock_cache_service,
        )

    @pytest.mark.asyncio
    async def test_history_manager_initialization(self):
        """測試歷史管理器初始化."""
        assert self.history_manager.database_service == self.mock_database_service
        assert self.history_manager.cache_service == self.mock_cache_service
        assert len(self.history_manager._history_buffer) == 0
        assert self.history_manager._buffer_size == 200

    @pytest.mark.asyncio
    async def test_record_operation(self):
        """測試記錄操作歷史."""
        record = await self.history_manager.record_operation(
            action=HistoryAction.GRANT,
            category=HistoryCategory.USER_ACHIEVEMENT,
            operation_name="grant_achievement",
            executor_id=self.test_user.id,
            target_type="user",
            target_id=12346,
            target_name="TargetUser",
            old_values={},
            new_values={"achievement_id": 1},
            guild_id=self.test_guild.id,
            affected_users=[12346],
            affected_achievements=[1],
            success=True,
            risk_level="low",
        )

        # 檢查記錄屬性
        assert isinstance(record, HistoryRecord)
        assert record.action == HistoryAction.GRANT
        assert record.category == HistoryCategory.USER_ACHIEVEMENT
        assert record.executor_id == self.test_user.id
        assert record.target_id == 12346
        assert record.success is True
        assert record.risk_level == "low"

        # 檢查記錄已添加到緩衝區
        assert len(self.history_manager._history_buffer) == 1
        assert self.history_manager._stats["records_created"] == 1

    @pytest.mark.asyncio
    async def test_query_history(self):
        """測試查詢操作歷史."""
        # 創建多個測試記錄
        await self.history_manager.record_operation(
            action=HistoryAction.GRANT,
            category=HistoryCategory.USER_ACHIEVEMENT,
            operation_name="grant_1",
            executor_id=self.test_user.id,
            success=True,
        )
        await self.history_manager.record_operation(
            action=HistoryAction.REVOKE,
            category=HistoryCategory.USER_ACHIEVEMENT,
            operation_name="revoke_1",
            executor_id=self.test_user.id,
            success=False,
        )
        await self.history_manager.record_operation(
            action=HistoryAction.RESET,
            category=HistoryCategory.USER_DATA,
            operation_name="reset_1",
            executor_id=11111,
            success=True,
        )

        # 查詢所有記錄
        all_records = await self.history_manager.query_history(HistoryQuery(limit=10))
        assert len(all_records) == 3

        # 按動作查詢
        grant_records = await self.history_manager.query_history(
            HistoryQuery(actions=[HistoryAction.GRANT])
        )
        assert len(grant_records) == 1
        assert grant_records[0].action == HistoryAction.GRANT

        # 按執行者查詢
        user_records = await self.history_manager.query_history(
            HistoryQuery(executor_ids=[self.test_user.id])
        )
        assert len(user_records) == 2

        # 按成功狀態查詢
        failed_records = await self.history_manager.query_history(
            HistoryQuery(success_only=False)
        )
        # 這應該包含所有記錄
        assert len(failed_records) == 3

        success_records = await self.history_manager.query_history(
            HistoryQuery(success_only=True)
        )
        assert len(success_records) == 2

    @pytest.mark.asyncio
    async def test_analyze_history(self):
        """測試歷史分析."""
        # 創建測試記錄
        for i in range(10):
            await self.history_manager.record_operation(
                action=HistoryAction.GRANT if i % 2 == 0 else HistoryAction.REVOKE,
                category=HistoryCategory.USER_ACHIEVEMENT,
                operation_name=f"operation_{i}",
                executor_id=self.test_user.id if i < 7 else 11111,
                affected_users=[12346 + i],
                success=i % 3 != 0,  # 約2/3成功率
                duration_ms=100 + i * 10,
            )

        # 分析歷史
        analysis = await self.history_manager.analyze_history(HistoryQuery(limit=20))

        # 檢查分析結果
        assert analysis.total_records == 10
        assert analysis.success_rate > 0
        assert len(analysis.operations_by_action) > 0
        assert len(analysis.operations_by_executor) > 0

        # 檢查操作統計
        assert "grant" in analysis.operations_by_action
        assert "revoke" in analysis.operations_by_action
        assert self.test_user.id in analysis.operations_by_executor
        assert 11111 in analysis.operations_by_executor

        # 檢查成功率
        expected_success_rate = (7 / 10) * 100  # 7個成功操作
        assert abs(analysis.success_rate - expected_success_rate) < 1

        # 檢查活躍執行者
        assert len(analysis.most_active_executors) > 0
        most_active = analysis.most_active_executors[0]
        assert most_active["executor_id"] == self.test_user.id
        assert most_active["operations_count"] == 7

    @pytest.mark.asyncio
    async def test_export_history(self):
        """測試歷史資料導出."""
        # 創建測試記錄
        for i in range(3):
            await self.history_manager.record_operation(
                action=HistoryAction.GRANT,
                category=HistoryCategory.USER_ACHIEVEMENT,
                operation_name=f"export_test_{i}",
                executor_id=self.test_user.id,
            )

        # 導出歷史資料
        export_data = await self.history_manager.export_history(
            query=HistoryQuery(limit=10), format="json", include_analysis=True
        )

        # 檢查導出資料
        assert "export_id" in export_data
        assert export_data["format"] == "json"
        assert export_data["total_records"] == 3
        assert len(export_data["records"]) == 3
        assert "analysis" in export_data

        # 檢查統計更新
        assert self.history_manager._stats["export_operations"] == 1

    @pytest.mark.asyncio
    async def test_buffer_management(self):
        """測試緩衝區管理."""
        # 設置小的緩衝區大小用於測試
        original_size = self.history_manager._buffer_size
        self.history_manager._buffer_size = 3

        # 記錄超過緩衝區大小的操作
        for i in range(5):
            await self.history_manager.record_operation(
                action=HistoryAction.GRANT,
                category=HistoryCategory.USER_ACHIEVEMENT,
                operation_name=f"buffer_test_{i}",
                executor_id=self.test_user.id,
            )

        # 檢查緩衝區是否被刷新
        assert len(self.history_manager._history_buffer) < 5
        assert self.history_manager._stats["buffer_flushes"] > 0

        # 恢復原始緩衝區大小
        self.history_manager._buffer_size = original_size


class TestSecurityIntegration(AsyncTestCase):
    """安全系統整合測試."""

    def setup_method(self):
        """設置測試環境."""
        super().setup_method()

        self.audit_logger = AuditLogger(
            database_service=self.mock_database_service,
            cache_service=self.mock_cache_service,
        )

        self.security_validator = SecurityValidator(audit_logger=self.audit_logger)

        self.history_manager = HistoryManager(
            database_service=self.mock_database_service,
            cache_service=self.mock_cache_service,
        )

    @pytest.mark.asyncio
    async def test_complete_security_workflow(self):
        """測試完整的安全工作流程."""
        user_id = self.test_user.id
        context = AuditContext(user_id=user_id, guild_id=self.test_guild.id)

        # 1. 授予用戶權限
        await self.security_validator.grant_permission(
            user_id=user_id, permission_level=PermissionLevel.ELEVATED, granted_by=11111
        )

        # 2. 檢查權限
        permission_result = await self.security_validator.check_permission(
            user_id=user_id,
            operation_type="revoke_achievement",
            context={"guild_id": self.test_guild.id},
        )
        assert permission_result["allowed"] is True

        # 3. 記錄審計事件
        audit_event = await self.audit_logger.log_event(
            event_type=AuditEventType.ACHIEVEMENT_REVOKED,
            context=context,
            operation_name="revoke_achievement_secure",
            target_type="user",
            target_id=12346,
            metadata={"security_validated": True},
        )
        assert audit_event.success is True

        # 4. 記錄操作歷史
        history_record = await self.history_manager.record_operation(
            action=HistoryAction.REVOKE,
            category=HistoryCategory.USER_ACHIEVEMENT,
            operation_name="revoke_achievement_secure",
            executor_id=user_id,
            target_type="user",
            target_id=12346,
            success=True,
            risk_level="medium",
        )
        assert history_record.success is True

        # 5. 驗證所有系統都有記錄
        audit_events = await self.audit_logger.query_events(
            AuditQuery(user_ids=[user_id])
        )
        assert len(audit_events) >= 1

        history_records = await self.history_manager.query_history(
            HistoryQuery(executor_ids=[user_id])
        )
        assert len(history_records) == 1

        security_stats = await self.security_validator.get_security_statistics()
        assert security_stats["permission_checks"] == 1

    @pytest.mark.asyncio
    async def test_security_violation_handling(self):
        """測試安全違規處理."""
        user_id = self.test_user.id
        context = AuditContext(user_id=user_id, guild_id=self.test_guild.id)

        # 嘗試未授權操作
        permission_result = await self.security_validator.check_permission(
            user_id=user_id,
            operation_type="bulk_reset",
            context={"guild_id": self.test_guild.id},
        )
        assert permission_result["allowed"] is False

        # 記錄安全違規
        violation_event = await self.audit_logger.log_event(
            event_type=AuditEventType.SECURITY_VIOLATION,
            context=context,
            operation_name="unauthorized_bulk_reset",
            severity=AuditSeverity.WARNING,
            success=False,
            error_message="權限不足",
            risk_level="high",
        )

        assert violation_event.event_type == AuditEventType.SECURITY_VIOLATION
        assert violation_event.success is False
        assert violation_event.risk_level == "high"

        # 檢查安全統計
        audit_stats = await self.audit_logger.get_audit_statistics()
        assert audit_stats["security_violations"] >= 1
