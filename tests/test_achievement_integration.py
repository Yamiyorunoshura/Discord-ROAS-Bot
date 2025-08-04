"""成就系統整合測試.

完整的端到端整合測試,涵蓋:
- 完整的成就管理工作流程
- 多組件協作和資料流
- 真實使用場景模擬
- 效能和併發測試
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.cogs.achievement.panel.admin_panel import AdminPanel
from src.cogs.achievement.panel.security_panel import SecureAdminPanel
from src.cogs.achievement.services.audit_logger import AuditEventType, AuditLogger
from src.cogs.achievement.services.history_manager import HistoryAction, HistoryManager
from src.cogs.achievement.services.security_validator import (
    PermissionLevel,
    SecurityValidator,
)
from src.cogs.achievement.services.security_wrapper import SecurityOperationWrapper
from src.cogs.achievement.services.transaction_coordinator import TransactionCoordinator
from tests.test_utils import (
    AsyncTestCase,
)


class IntegrationTestSuite(AsyncTestCase):
    """整合測試套件基類."""

    def setup_method(self):
        """設置完整的測試環境."""
        super().setup_method()

        # 初始化所有核心服務
        self.audit_logger = AuditLogger(
            database_service=self.mock_database_service,
            cache_service=self.mock_cache_service,
        )

        self.security_validator = SecurityValidator(audit_logger=self.audit_logger)

        self.history_manager = HistoryManager(
            database_service=self.mock_database_service,
            cache_service=self.mock_cache_service,
        )

        self.security_wrapper = SecurityOperationWrapper(
            audit_logger=self.audit_logger,
            security_validator=self.security_validator,
            history_manager=self.history_manager,
        )

        self.transaction_coordinator = TransactionCoordinator(
            achievement_service=self.mock_achievement_service,
            cache_service=self.mock_cache_service,
            enable_validation=True,
        )

        # 創建管理面板
        self.mock_bot = MagicMock()
        self.mock_admin_permission_service = MagicMock()
        self.mock_admin_permission_service.check_admin_permission = AsyncMock(
            return_value=MagicMock(allowed=True, reason="test")
        )

        self.admin_panel = AdminPanel(
            bot=self.mock_bot,
            achievement_service=self.mock_achievement_service,
            admin_permission_service=self.mock_admin_permission_service,
            guild_id=self.test_guild.id,
            admin_user_id=self.test_user.id,
        )

        self.secure_admin_panel = SecureAdminPanel(
            bot=self.mock_bot,
            achievement_service=self.mock_achievement_service,
            admin_permission_service=self.mock_admin_permission_service,
            guild_id=self.test_guild.id,
            admin_user_id=self.test_user.id,
        )


class TestCompleteWorkflow(IntegrationTestSuite):
    """完整工作流程測試."""

    @pytest.mark.asyncio
    async def test_complete_achievement_management_workflow(self):
        """測試完整的成就管理工作流程."""
        user_id = self.test_user.id
        achievement_id = 1

        # 1. 授予管理員權限
        await self.security_validator.grant_permission(
            user_id=user_id, permission_level=PermissionLevel.ADMIN, granted_by=11111
        )

        # 2. 啟動管理面板
        self.test_interaction.followup.send = AsyncMock()
        await self.admin_panel.start(self.test_interaction)

        # 驗證面板啟動成功
        assert self.admin_panel.current_state.value == "overview"
        assert self.admin_panel.current_interaction == self.test_interaction

        # 3. 透過協調器調整進度
        progress_result = (
            await self.transaction_coordinator.adjust_progress_coordinated(
                user_id=user_id, achievement_id=achievement_id, new_value=8.0
            )
        )
        assert progress_result["success"] is True

        # 4. 透過協調器授予成就
        grant_result = await self.transaction_coordinator.grant_achievement_coordinated(
            user_id=user_id, achievement_id=achievement_id, notify=True
        )
        assert grant_result["success"] is True

        # 5. 驗證審計事件記錄
        audit_events = await self.audit_logger.query_events(
            from_time=datetime.utcnow() - timedelta(minutes=5)
        )
        assert len(audit_events) > 0

        # 查找成就授予事件
        grant_events = [
            e
            for e in audit_events
            if e.event_type == AuditEventType.ACHIEVEMENT_GRANTED
        ]
        assert len(grant_events) > 0

        # 6. 驗證操作歷史記錄
        history_records = await self.history_manager.query_history(
            from_time=datetime.utcnow() - timedelta(minutes=5)
        )
        assert len(history_records) > 0

        # 查找授予記錄
        grant_records = [
            r
            for r in history_records
            if r.action == HistoryAction.GRANT and r.executor_id == user_id
        ]
        assert len(grant_records) > 0

        # 7. 驗證快取狀態
        assert len(self.mock_cache_service.invalidation_calls) > 0

        # 8. 驗證最終資料狀態
        user_achievements = await self.mock_achievement_service.get_user_achievements(
            user_id
        )
        user_progress = await self.mock_achievement_service.get_user_progress(user_id)

        assert len(user_achievements) == 1
        assert user_achievements[0]["achievement_id"] == achievement_id
        assert len(user_progress) == 1
        assert user_progress[0]["current_value"] == 8.0

    @pytest.mark.asyncio
    async def test_secure_operation_workflow(self):
        """測試安全操作工作流程."""
        user_id = self.test_user.id

        # 初始化安全面板
        await self.secure_admin_panel.initialize_security_services()

        # 授予權限
        await self.security_validator.grant_permission(
            user_id=user_id, permission_level=PermissionLevel.ELEVATED, granted_by=11111
        )

        # 模擬安全操作(使用裝飾器)
        from src.cogs.achievement.services.security_wrapper import (
            secure_grant_achievement,
        )

        class TestOperationTarget:
            def __init__(self, security_wrapper, achievement_service):
                self.security_wrapper = security_wrapper
                self.achievement_service = achievement_service

            @secure_grant_achievement
            async def grant_achievement_secure(
                self, interaction, user_id, achievement_id
            ):
                """安全的成就授予操作."""
                result = await self.achievement_service.grant_user_achievement(
                    user_id, achievement_id, notify=True
                )
                return {
                    "success": True,
                    "user_achievement": result,
                    "target_type": "user",
                    "target_id": user_id,
                    "affected_users": [user_id],
                    "affected_achievements": [achievement_id],
                }

        # 創建測試目標
        test_target = TestOperationTarget(
            self.security_wrapper, self.mock_achievement_service
        )

        # 執行安全操作
        result = await test_target.grant_achievement_secure(
            self.test_interaction, user_id=user_id, achievement_id=1
        )

        # 驗證操作結果
        assert result["success"] is True
        assert "user_achievement" in result

        # 驗證安全記錄
        audit_events = self.audit_logger._event_buffer
        security_events = [
            e
            for e in audit_events
            if e.event_type == AuditEventType.ACHIEVEMENT_GRANTED
        ]
        assert len(security_events) > 0

        history_records = self.history_manager._history_buffer
        grant_records = [r for r in history_records if r.action == HistoryAction.GRANT]
        assert len(grant_records) > 0

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self):
        """測試錯誤恢復工作流程."""
        user_id = self.test_user.id
        achievement_id = 1

        # 模擬服務錯誤
        original_grant_method = self.mock_achievement_service.grant_user_achievement
        self.mock_achievement_service.grant_user_achievement = AsyncMock(
            side_effect=Exception("模擬服務錯誤")
        )

        # 嘗試執行操作(應該失敗)
        with pytest.raises(Exception, match="模擬服務錯誤"):
            await self.transaction_coordinator.grant_achievement_coordinated(
                user_id=user_id, achievement_id=achievement_id
            )

        # 檢查協調器狀態是否正確恢復
        assert self.transaction_coordinator.status.value == "ready"

        # 檢查錯誤統計
        stats = self.transaction_coordinator.get_coordinator_stats()
        assert stats["coordinator"]["failed_operations"] == 1

        # 恢復服務並重試
        self.mock_achievement_service.grant_user_achievement = original_grant_method

        # 重新執行操作(應該成功)
        result = await self.transaction_coordinator.grant_achievement_coordinated(
            user_id=user_id, achievement_id=achievement_id
        )

        assert result["success"] is True

        # 檢查統計更新
        stats = self.transaction_coordinator.get_coordinator_stats()
        assert stats["coordinator"]["successful_operations"] == 1


class TestConcurrencyAndPerformance(IntegrationTestSuite):
    """併發和效能測試."""

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """測試併發操作處理."""
        user_ids = list(range(12345, 12355))  # 10個用戶
        achievement_id = 1

        # 創建併發任務
        tasks = []
        for user_id in user_ids:
            task = self.transaction_coordinator.grant_achievement_coordinated(
                user_id=user_id, achievement_id=achievement_id
            )
            tasks.append(task)

        # 執行併發操作
        start_time = datetime.utcnow()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = datetime.utcnow()

        # 檢查所有操作都成功
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) == len(user_ids)

        # 檢查效能(應該在合理時間內完成)
        total_time = (end_time - start_time).total_seconds()
        assert total_time < 5.0, f"併發操作時間過長: {total_time}秒"

        # 檢查所有用戶都獲得了成就
        for user_id in user_ids:
            user_achievements = (
                await self.mock_achievement_service.get_user_achievements(user_id)
            )
            assert len(user_achievements) == 1
            assert user_achievements[0]["achievement_id"] == achievement_id

    @pytest.mark.asyncio
    async def test_bulk_operations_performance(self):
        """測試批量操作效能."""
        user_ids = list(range(12345, 12395))  # 50個用戶
        achievement_id = 1

        start_time = datetime.utcnow()

        # 執行批量操作
        result = await self.transaction_coordinator.bulk_operation_coordinated(
            operation_type="bulk_grant",
            user_ids=user_ids,
            achievement_id=achievement_id,
        )

        end_time = datetime.utcnow()

        # 檢查結果
        assert result["success"] is True
        assert result["total_operations"] == len(user_ids)
        assert result["successful_operations"] == len(user_ids)
        assert result["failed_operations"] == 0

        # 檢查效能
        total_time = (end_time - start_time).total_seconds()
        avg_time_per_user = total_time / len(user_ids)
        assert avg_time_per_user < 0.1, f"每用戶平均處理時間過長: {avg_time_per_user}秒"

        # 檢查所有用戶都獲得了成就
        for user_id in user_ids:
            user_achievements = (
                await self.mock_achievement_service.get_user_achievements(user_id)
            )
            assert len(user_achievements) == 1

    @pytest.mark.asyncio
    async def test_cache_performance(self):
        """測試快取效能."""
        user_id = self.test_user.id
        cache_key = f"user:{user_id}"

        # 測試快取寫入效能
        start_time = datetime.utcnow()
        for i in range(100):
            await self.mock_cache_service.set("test", f"{cache_key}_{i}", {"data": i})
        end_time = datetime.utcnow()

        write_time = (end_time - start_time).total_seconds()
        assert write_time < 1.0, f"快取寫入時間過長: {write_time}秒"

        # 測試快取讀取效能
        start_time = datetime.utcnow()
        for i in range(100):
            result = await self.mock_cache_service.get("test", f"{cache_key}_{i}")
            assert result is not None
        end_time = datetime.utcnow()

        read_time = (end_time - start_time).total_seconds()
        assert read_time < 0.5, f"快取讀取時間過長: {read_time}秒"


class TestDataConsistency(IntegrationTestSuite):
    """資料一致性測試."""

    @pytest.mark.asyncio
    async def test_transaction_consistency(self):
        """測試事務一致性."""
        user_id = self.test_user.id
        achievement_id = 1

        # 在事務中執行多個操作
        async with self.transaction_coordinator.coordinate_operation(
            "complex_operation", user_ids=[user_id], achievement_ids=[achievement_id]
        ) as coord_op:
            # 調整進度
            await self.mock_achievement_service.update_user_progress(
                user_id, achievement_id, 10.0
            )

            # 授予成就
            await self.mock_achievement_service.grant_user_achievement(
                user_id, achievement_id
            )

            # 檢查事務狀態
            assert coord_op.transaction is not None

        # 檢查最終狀態一致性
        user_achievements = await self.mock_achievement_service.get_user_achievements(
            user_id
        )
        user_progress = await self.mock_achievement_service.get_user_progress(user_id)

        assert len(user_achievements) == 1
        assert len(user_progress) == 1
        assert user_progress[0]["current_value"] == 10.0

    @pytest.mark.asyncio
    async def test_cache_consistency(self):
        """測試快取一致性."""
        user_id = self.test_user.id
        achievement_id = 1

        # 設置初始快取
        await self.mock_cache_service.set("user_achievements", str(user_id), [])

        # 執行操作(應該使快取失效)
        await self.transaction_coordinator.grant_achievement_coordinated(
            user_id=user_id, achievement_id=achievement_id
        )

        # 檢查快取是否被正確失效
        cache_key = f"user_achievements:{user_id}"
        assert cache_key in self.mock_cache_service.invalidation_calls

        # 檢查新的快取狀態
        cached_achievements = await self.mock_cache_service.get(
            "user_achievements", str(user_id)
        )
        # 因為快取已失效,應該返回 None
        assert cached_achievements is None


class TestSecurityIntegration(IntegrationTestSuite):
    """安全整合測試."""

    @pytest.mark.asyncio
    async def test_complete_security_workflow(self):
        """測試完整的安全工作流程."""
        admin_id = 11111

        # 1. 授予管理員權限
        await self.security_validator.grant_permission(
            user_id=admin_id,
            permission_level=PermissionLevel.ADMIN,
            granted_by=admin_id,
        )

        # 2. 啟動安全面板
        self.test_interaction.followup.send = AsyncMock()
        await self.secure_admin_panel.start(self.test_interaction)

        # 3. 檢查權限
        permission_result = await self.security_validator.check_permission(
            user_id=admin_id,
            operation_type="grant_achievement",
            context={"guild_id": self.test_guild.id},
        )
        assert permission_result["allowed"] is True

        # 4. 執行安全操作
        from src.cogs.achievement.services.audit_logger import AuditContext

        context = AuditContext(user_id=admin_id, guild_id=self.test_guild.id)

        audit_event = await self.audit_logger.log_event(
            event_type=AuditEventType.ACHIEVEMENT_GRANTED,
            context=context,
            operation_name="secure_grant_test",
            success=True,
            metadata={"security_validated": True},
        )

        # 5. 記錄操作歷史
        history_record = await self.history_manager.record_operation(
            action=HistoryAction.GRANT,
            category="user_achievement",
            operation_name="secure_grant_test",
            executor_id=admin_id,
            success=True,
        )

        # 6. 驗證安全記錄
        assert audit_event.success is True
        assert history_record.success is True

        # 7. 檢查統計
        security_stats = await self.security_validator.get_security_statistics()
        assert security_stats["permission_checks"] == 1

        audit_stats = await self.audit_logger.get_audit_statistics()
        assert audit_stats["events_logged"] >= 1

    @pytest.mark.asyncio
    async def test_security_violation_handling(self):
        """測試安全違規處理."""
        user_id = self.test_user.id  # 沒有特殊權限的用戶

        # 嘗試執行需要高權限的操作
        permission_result = await self.security_validator.check_permission(
            user_id=user_id,
            operation_type="reset_user_data",
            context={"guild_id": self.test_guild.id},
        )

        # 應該被拒絕
        assert permission_result["allowed"] is False

        # 記錄安全違規
        from src.cogs.achievement.services.audit_logger import (
            AuditContext,
            AuditSeverity,
        )

        context = AuditContext(user_id=user_id, guild_id=self.test_guild.id)

        violation_event = await self.audit_logger.log_event(
            event_type=AuditEventType.SECURITY_VIOLATION,
            context=context,
            operation_name="unauthorized_reset_attempt",
            severity=AuditSeverity.WARNING,
            success=False,
            error_message="權限不足",
            risk_level="high",
        )

        # 檢查違規記錄
        assert violation_event.event_type == AuditEventType.SECURITY_VIOLATION
        assert violation_event.success is False
        assert violation_event.severity == AuditSeverity.WARNING

        # 檢查統計更新
        audit_stats = await self.audit_logger.get_audit_statistics()
        assert audit_stats["security_violations"] >= 1


class TestSystemHealth(IntegrationTestSuite):
    """系統健康測試."""

    @pytest.mark.asyncio
    async def test_system_health_check(self):
        """測試系統健康檢查."""
        # 檢查協調器健康狀態
        health = await self.transaction_coordinator.get_health_status()

        assert health["coordinator_status"] == "ready"
        assert health["services_available"]["achievement_service"] is True
        assert health["services_available"]["cache_service"] is True
        assert health["services_available"]["transaction_manager"] is True
        assert health["services_available"]["cache_sync_manager"] is True
        assert health["services_available"]["data_validator"] is True

        # 檢查安全組件健康狀態
        security_stats = await self.security_validator.get_security_statistics()
        assert "tokens_generated" in security_stats
        assert "permission_checks" in security_stats

        audit_stats = await self.audit_logger.get_audit_statistics()
        assert "events_logged" in audit_stats
        assert "buffer_size" in audit_stats

    @pytest.mark.asyncio
    async def test_resource_cleanup(self):
        """測試資源清理."""
        # 執行一些操作來產生資源
        user_id = self.test_user.id

        for i in range(10):
            await self.transaction_coordinator.grant_achievement_coordinated(
                user_id=user_id + i, achievement_id=1
            )

        # 檢查緩衝區狀態
        audit_buffer_size = len(self.audit_logger._event_buffer)
        history_buffer_size = len(self.history_manager._history_buffer)

        assert audit_buffer_size > 0
        assert history_buffer_size > 0

        # 模擬清理操作(在實際實現中會有自動清理機制)
        # 這裡只是驗證資源使用在合理範圍內
        assert audit_buffer_size < 100
        assert history_buffer_size < 100


# 測試配置和夾具
@pytest.fixture
def integration_test_suite():
    """整合測試套件夾具."""
    return IntegrationTestSuite()


# 測試標記
pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
