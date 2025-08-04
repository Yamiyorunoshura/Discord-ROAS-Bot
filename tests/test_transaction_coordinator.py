"""成就系統事務協調器測試.

測試事務協調器的核心功能,包含:
- 事務管理和協調
- 快取同步
- 資料完整性驗證
- 錯誤處理和回滾
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.cogs.achievement.services.transaction_coordinator import (
    CoordinatedOperation,
    CoordinatorStatus,
    TransactionCoordinator,
)
from src.cogs.achievement.services.transaction_manager import OperationType
from tests.test_utils import (
    AsyncTestCase,
)


class TestTransactionCoordinator(AsyncTestCase):
    """事務協調器測試類."""

    def setup_method(self):
        """設置測試環境."""
        super().setup_method()

        self.coordinator = TransactionCoordinator(
            achievement_service=self.mock_achievement_service,
            cache_service=self.mock_cache_service,
            enable_validation=True,
        )

    @pytest.mark.asyncio
    async def test_coordinator_initialization(self):
        """測試協調器初始化."""
        assert self.coordinator.status == CoordinatorStatus.READY
        assert self.coordinator.achievement_service == self.mock_achievement_service
        assert self.coordinator.cache_service == self.mock_cache_service
        assert self.coordinator.enable_validation is True

        # 檢查子管理器是否正確初始化
        assert self.coordinator.transaction_manager is not None
        assert self.coordinator.cache_sync_manager is not None
        assert self.coordinator.data_validator is not None

    @pytest.mark.asyncio
    async def test_coordinate_operation_context(self):
        """測試協調操作上下文管理器."""
        async with self.coordinator.coordinate_operation(
            OperationType.GRANT_ACHIEVEMENT,
            user_ids=[self.test_user.id],
            achievement_ids=[1],
            notify=True,
        ) as coord_op:
            # 檢查協調操作對象
            assert isinstance(coord_op, CoordinatedOperation)
            assert coord_op.operation_type == OperationType.GRANT_ACHIEVEMENT
            assert self.test_user.id in coord_op.user_ids
            assert 1 in coord_op.achievement_ids
            assert coord_op.metadata["notify"] is True

            # 檢查協調器狀態
            assert self.coordinator.status == CoordinatorStatus.BUSY

            # 檢查事務已創建
            assert coord_op.transaction is not None

        # 上下文結束後,狀態應該恢復
        assert self.coordinator.status == CoordinatorStatus.READY

    @pytest.mark.asyncio
    async def test_grant_achievement_coordinated(self):
        """測試協調式成就授予."""
        user_id = self.test_user.id
        achievement_id = 1

        # 執行協調式成就授予
        result = await self.coordinator.grant_achievement_coordinated(
            user_id=user_id, achievement_id=achievement_id, notify=True
        )

        # 檢查結果
        assert result["success"] is True
        assert "user_achievement" in result
        assert "operation_id" in result

        # 檢查成就是否已授予
        user_achievements = await self.mock_achievement_service.get_user_achievements(
            user_id
        )
        assert len(user_achievements) == 1
        assert user_achievements[0]["achievement_id"] == achievement_id

        # 檢查統計更新
        stats = self.coordinator.get_coordinator_stats()
        assert stats["coordinator"]["successful_operations"] == 1

    @pytest.mark.asyncio
    async def test_revoke_achievement_coordinated(self):
        """測試協調式成就撤銷."""
        user_id = self.test_user.id
        achievement_id = 1

        # 先授予成就
        await self.mock_achievement_service.grant_user_achievement(
            user_id, achievement_id
        )

        # 執行協調式成就撤銷
        result = await self.coordinator.revoke_achievement_coordinated(
            user_id=user_id, achievement_id=achievement_id, reason="測試撤銷"
        )

        # 檢查結果
        assert result["success"] is True
        assert "revoked_achievement" in result
        assert "operation_id" in result

        # 檢查成就是否已撤銷
        user_achievements = await self.mock_achievement_service.get_user_achievements(
            user_id
        )
        assert len(user_achievements) == 0

    @pytest.mark.asyncio
    async def test_adjust_progress_coordinated(self):
        """測試協調式進度調整."""
        user_id = self.test_user.id
        achievement_id = 1
        new_value = 8.0

        # 執行協調式進度調整
        result = await self.coordinator.adjust_progress_coordinated(
            user_id=user_id, achievement_id=achievement_id, new_value=new_value
        )

        # 檢查結果
        assert result["success"] is True
        assert "updated_progress" in result
        assert result["new_value"] == new_value
        assert "operation_id" in result

        # 檢查進度是否已更新
        user_progress = await self.mock_achievement_service.get_user_progress(user_id)
        assert len(user_progress) == 1
        assert user_progress[0]["current_value"] == new_value

    @pytest.mark.asyncio
    async def test_reset_user_data_coordinated(self):
        """測試協調式用戶資料重置."""
        user_id = self.test_user.id

        # 先添加一些資料
        await self.mock_achievement_service.grant_user_achievement(user_id, 1)
        await self.mock_achievement_service.update_user_progress(user_id, 1, 5.0)

        # 執行協調式用戶資料重置
        result = await self.coordinator.reset_user_data_coordinated(
            user_id=user_id, backup_data=True
        )

        # 檢查結果
        assert result["success"] is True
        assert "reset_result" in result
        assert "backup" in result
        assert "operation_id" in result

        # 檢查資料是否已重置
        user_achievements = await self.mock_achievement_service.get_user_achievements(
            user_id
        )
        user_progress = await self.mock_achievement_service.get_user_progress(user_id)
        assert len(user_achievements) == 0
        assert len(user_progress) == 0

    @pytest.mark.asyncio
    async def test_bulk_operation_coordinated(self):
        """測試協調式批量操作."""
        user_ids = [12345, 12346, 12347]
        achievement_id = 1

        # 執行批量授予操作
        result = await self.coordinator.bulk_operation_coordinated(
            operation_type=OperationType.BULK_GRANT,
            user_ids=user_ids,
            achievement_id=achievement_id,
        )

        # 檢查結果
        assert result["success"] is True
        assert result["total_operations"] == len(user_ids)
        assert result["successful_operations"] == len(user_ids)
        assert result["failed_operations"] == 0
        assert len(result["results"]) == len(user_ids)

        # 檢查每個用戶都獲得了成就
        for user_id in user_ids:
            user_achievements = (
                await self.mock_achievement_service.get_user_achievements(user_id)
            )
            assert len(user_achievements) == 1
            assert user_achievements[0]["achievement_id"] == achievement_id

    @pytest.mark.asyncio
    async def test_duplicate_achievement_error(self):
        """測試重複成就授予錯誤處理."""
        user_id = self.test_user.id
        achievement_id = 1

        # 先授予成就
        await self.mock_achievement_service.grant_user_achievement(
            user_id, achievement_id
        )

        # 嘗試再次授予相同成就
        with pytest.raises(ValueError, match="已經擁有成就"):
            await self.coordinator.grant_achievement_coordinated(
                user_id=user_id, achievement_id=achievement_id
            )

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_achievement_error(self):
        """測試撤銷不存在成就錯誤處理."""
        user_id = self.test_user.id
        achievement_id = 1

        # 嘗試撤銷用戶沒有的成就
        with pytest.raises(ValueError, match="沒有成就"):
            await self.coordinator.revoke_achievement_coordinated(
                user_id=user_id, achievement_id=achievement_id
            )

    @pytest.mark.asyncio
    async def test_coordinator_status_management(self):
        """測試協調器狀態管理."""
        # 初始狀態
        assert self.coordinator.status == CoordinatorStatus.READY

        # 在操作過程中狀態變為忙碌
        async with self.coordinator.coordinate_operation(
            OperationType.GRANT_ACHIEVEMENT, user_ids=[self.test_user.id]
        ):
            assert self.coordinator.status == CoordinatorStatus.BUSY

        # 操作完成後狀態恢復
        assert self.coordinator.status == CoordinatorStatus.READY

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """測試錯誤處理和恢復."""
        # 模擬服務錯誤
        self.mock_achievement_service.grant_user_achievement = AsyncMock(
            side_effect=Exception("模擬錯誤")
        )

        # 嘗試執行操作
        with pytest.raises(Exception, match="模擬錯誤"):
            await self.coordinator.grant_achievement_coordinated(
                user_id=self.test_user.id, achievement_id=1
            )

        # 檢查協調器狀態是否恢復
        assert self.coordinator.status == CoordinatorStatus.READY

        # 檢查錯誤統計
        stats = self.coordinator.get_coordinator_stats()
        assert stats["coordinator"]["failed_operations"] == 1

    @pytest.mark.asyncio
    async def test_health_status(self):
        """測試健康狀態檢查."""
        health = await self.coordinator.get_health_status()

        assert health["coordinator_status"] == CoordinatorStatus.READY.value
        assert health["services_available"]["achievement_service"] is True
        assert health["services_available"]["cache_service"] is True
        assert health["services_available"]["transaction_manager"] is True
        assert health["services_available"]["cache_sync_manager"] is True
        assert health["services_available"]["data_validator"] is True

        assert health["configuration"]["validation_enabled"] is True
        assert "statistics" in health

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """測試並發操作處理."""
        import asyncio

        user_ids = [12345, 12346, 12347]
        achievement_id = 1

        # 創建並發操作任務
        tasks = []
        for user_id in user_ids:
            task = self.coordinator.grant_achievement_coordinated(
                user_id=user_id, achievement_id=achievement_id
            )
            tasks.append(task)

        # 執行並發操作
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 檢查所有操作都成功
        for result in results:
            assert not isinstance(result, Exception)
            assert result["success"] is True

        # 檢查所有用戶都獲得了成就
        for user_id in user_ids:
            user_achievements = (
                await self.mock_achievement_service.get_user_achievements(user_id)
            )
            assert len(user_achievements) == 1


class TestTransactionCoordinatorIntegration(AsyncTestCase):
    """事務協調器整合測試."""

    def setup_method(self):
        """設置測試環境."""
        super().setup_method()

        # 使用真實的服務進行整合測試
        self.coordinator = TransactionCoordinator(
            achievement_service=self.mock_achievement_service,
            cache_service=self.mock_cache_service,
            enable_validation=True,
        )

    @pytest.mark.asyncio
    async def test_complete_workflow(self):
        """測試完整的工作流程."""
        user_id = self.test_user.id
        achievement_id = 1

        # 1. 調整進度
        progress_result = await self.coordinator.adjust_progress_coordinated(
            user_id=user_id, achievement_id=achievement_id, new_value=8.0
        )
        assert progress_result["success"] is True

        # 2. 授予成就
        grant_result = await self.coordinator.grant_achievement_coordinated(
            user_id=user_id, achievement_id=achievement_id
        )
        assert grant_result["success"] is True

        # 3. 檢查最終狀態
        user_achievements = await self.mock_achievement_service.get_user_achievements(
            user_id
        )
        user_progress = await self.mock_achievement_service.get_user_progress(user_id)

        assert len(user_achievements) == 1
        assert len(user_progress) == 1
        assert user_progress[0]["current_value"] == 8.0

        # 4. 重置用戶資料
        reset_result = await self.coordinator.reset_user_data_coordinated(
            user_id=user_id, backup_data=True
        )
        assert reset_result["success"] is True
        assert reset_result["backup"] is not None

        # 5. 檢查重置後狀態
        user_achievements = await self.mock_achievement_service.get_user_achievements(
            user_id
        )
        user_progress = await self.mock_achievement_service.get_user_progress(user_id)

        assert len(user_achievements) == 0
        assert len(user_progress) == 0

    @pytest.mark.asyncio
    async def test_performance_metrics(self):
        """測試效能指標."""
        start_time = datetime.utcnow()

        # 執行多個操作
        user_ids = list(range(12345, 12355))  # 10個用戶
        achievement_id = 1

        for user_id in user_ids:
            await self.coordinator.grant_achievement_coordinated(
                user_id=user_id, achievement_id=achievement_id
            )

        end_time = datetime.utcnow()
        total_duration = (end_time - start_time).total_seconds()

        # 檢查效能統計
        stats = self.coordinator.get_coordinator_stats()
        assert stats["coordinator"]["successful_operations"] == len(user_ids)

        # 平均每個操作應該在合理時間內完成(這裡設為1秒)
        avg_duration = total_duration / len(user_ids)
        assert avg_duration < 1.0, f"平均操作時間過長: {avg_duration}秒"
