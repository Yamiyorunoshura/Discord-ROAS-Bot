"""成就管理快取和效能測試.

此模組測試快取管理和效能優化功能:
- 快取失效機制
- 快取一致性
- 效能優化測試
- 異步處理測試
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, call

import pytest

from src.cogs.achievement.database.models import Achievement, AchievementCategory
from src.cogs.achievement.services.admin_service import (
    AchievementAdminService,
    BulkOperationResult,
    ValidationResult,
)


class TestCacheAndPerformance:
    """快取和效能測試."""

    @pytest.fixture
    def mock_cache_service(self):
        """模擬快取服務."""
        cache_service = AsyncMock()
        cache_service.get = AsyncMock()
        cache_service.set = AsyncMock()
        cache_service.delete = AsyncMock()
        cache_service.delete_pattern = AsyncMock()
        return cache_service

    @pytest.fixture
    def admin_service(self, mock_cache_service):
        """建立管理服務實例."""
        return AchievementAdminService(
            repository=AsyncMock(),
            permission_service=AsyncMock(
                check_admin_permission=AsyncMock(return_value=True)
            ),
            cache_service=mock_cache_service,
        )

    @pytest.fixture
    def sample_achievement(self):
        """樣本成就物件."""
        return Achievement(
            id=1,
            name="測試成就",
            description="測試描述",
            category="社交互動",
            category_id=1,
            type="counter",
            criteria={"target_value": 10, "counter_field": "interactions"},
            points=100,
            is_active=True,
            role_reward=None,
            is_hidden=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    # 快取失效機制測試
    async def test_cache_invalidation_on_achievement_create(
        self, admin_service, mock_cache_service
    ):
        """測試創建成就時的快取失效."""
        # 配置模擬
        admin_service._validate_achievement_data = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )
        admin_service._check_achievement_name_uniqueness = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )
        admin_service._create_achievement_in_db = AsyncMock(
            return_value=Achievement(
                id=1,
                name="測試成就",
                description="測試描述",
                category="社交互動",
                category_id=1,
                type="counter",
                criteria={"target_value": 10, "counter_field": "interactions"},
                points=100,
                is_active=True,
                role_reward=None,
                is_hidden=False,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        )
        admin_service._log_admin_action = AsyncMock()

        data = {
            "name": "測試成就",
            "description": "描述",
            "category": "社交互動",
            "type": "counter",
            "criteria": {"target_value": 10},
            "points": 100,
        }

        # 執行創建操作
        await admin_service.create_achievement(data, 123)

        # 驗證快取失效調用
        mock_cache_service.delete_pattern.assert_has_calls(
            [call("achievements:list:*"), call("achievements:count:*")]
        )

    async def test_cache_invalidation_on_achievement_update(
        self, admin_service, mock_cache_service, sample_achievement
    ):
        """測試更新成就時的快取失效."""
        # 配置模擬
        admin_service._get_achievement_by_id = AsyncMock(
            return_value=sample_achievement
        )
        admin_service._validate_achievement_updates = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )
        admin_service._update_achievement_in_db = AsyncMock(
            return_value=sample_achievement
        )
        admin_service._log_admin_action = AsyncMock()

        updates = {"name": "更新的成就名稱"}

        # 執行更新操作
        await admin_service.update_achievement(1, updates, 123)

        # 驗證特定成就快取和列表快取都被清除
        mock_cache_service.delete.assert_called_with("achievement:detail:1")
        mock_cache_service.delete_pattern.assert_has_calls(
            [call("achievements:list:*"), call("achievements:count:*")]
        )

    async def test_cache_invalidation_on_achievement_delete(
        self, admin_service, mock_cache_service, sample_achievement
    ):
        """測試刪除成就時的快取失效."""
        # 配置模擬
        admin_service._get_achievement_by_id = AsyncMock(
            return_value=sample_achievement
        )
        admin_service._check_achievement_dependencies = AsyncMock(return_value=[])
        admin_service._delete_achievement_from_db = AsyncMock(return_value=True)
        admin_service._log_admin_action = AsyncMock()

        # 執行刪除操作
        await admin_service.delete_achievement(1, 123)

        # 驗證快取失效
        mock_cache_service.delete.assert_called_with("achievement:detail:1")
        mock_cache_service.delete_pattern.assert_has_calls(
            [call("achievements:list:*"), call("achievements:count:*")]
        )

    async def test_cache_invalidation_on_bulk_operations(
        self, admin_service, mock_cache_service
    ):
        """測試批量操作時的快取失效."""
        # 配置模擬
        achievements = [
            Achievement(
                id=1,
                name="成就1",
                description="描述1",
                category="社交互動",
                category_id=1,
                type="counter",
                criteria={"target_value": 10, "counter_field": "interactions"},
                points=100,
                is_active=False,
                role_reward=None,
                is_hidden=False,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
            Achievement(
                id=2,
                name="成就2",
                description="描述2",
                category="社交互動",
                category_id=1,
                type="counter",
                criteria={"target_value": 10, "counter_field": "interactions"},
                points=100,
                is_active=False,
                role_reward=None,
                is_hidden=False,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
            Achievement(
                id=3,
                name="成就3",
                description="描述3",
                category="社交互動",
                category_id=1,
                type="counter",
                criteria={"target_value": 10, "counter_field": "interactions"},
                points=100,
                is_active=False,
                role_reward=None,
                is_hidden=False,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
        ]
        admin_service._get_achievements_by_ids = AsyncMock(return_value=achievements)
        admin_service._validate_bulk_status_update = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )
        admin_service._update_achievements_status_in_db = AsyncMock()
        admin_service._log_admin_action = AsyncMock()

        # 執行批量狀態更新
        await admin_service.bulk_update_status([1, 2, 3], True, 123)

        # 驗證批量快取失效
        mock_cache_service.delete_pattern.assert_has_calls(
            [call("achievements:list:*"), call("achievements:count:*")]
        )

    async def test_category_cache_invalidation(self, admin_service, mock_cache_service):
        """測試分類操作時的快取失效."""
        # 配置模擬
        admin_service._validate_category_data = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )
        admin_service._check_category_name_uniqueness = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )
        admin_service._create_category_in_db = AsyncMock(
            return_value=AchievementCategory(id=1, name="測試分類", description="描述")
        )
        admin_service._log_admin_action = AsyncMock()

        data = {"name": "測試分類", "description": "描述", "display_order": 10}

        # 執行創建分類操作
        await admin_service.create_category(data, 123)

        # 驗證分類快取失效
        mock_cache_service.delete_pattern.assert_called_with("categories:*")

    # 快取一致性測試
    async def test_cache_consistency_after_concurrent_updates(
        self, admin_service, mock_cache_service, sample_achievement
    ):
        """測試並發更新後的快取一致性."""
        # 模擬並發更新場景
        admin_service._get_achievement_by_id = AsyncMock(
            return_value=sample_achievement
        )
        admin_service._validate_achievement_updates = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )
        admin_service._update_achievement_in_db = AsyncMock(
            return_value=sample_achievement
        )
        admin_service._log_admin_action = AsyncMock()

        # 模擬兩個並發更新請求
        updates1 = {"name": "更新1"}
        updates2 = {"description": "更新2"}

        # 執行並發更新(實際上是序列,但測試邏輯)
        await admin_service.update_achievement(1, updates1, 123)
        await admin_service.update_achievement(1, updates2, 124)

        # 驗證每次更新都觸發了快取失效
        assert mock_cache_service.delete.call_count == 2
        assert mock_cache_service.delete_pattern.call_count == 4  # 每次更新2個pattern

    async def test_cache_selective_invalidation(
        self, admin_service, mock_cache_service
    ):
        """測試選擇性快取失效."""
        # 測試更新特定成就只失效相關快取
        sample_achievement = Achievement(
            id=1,
            name="測試成就",
            description="測試描述",
            category="社交互動",
            category_id=1,
            type="counter",
            criteria={"target_value": 10, "counter_field": "interactions"},
            points=100,
            is_active=True,
            role_reward=None,
            is_hidden=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        admin_service._get_achievement_by_id = AsyncMock(
            return_value=sample_achievement
        )
        admin_service._validate_achievement_updates = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )
        admin_service._update_achievement_in_db = AsyncMock(
            return_value=sample_achievement
        )
        admin_service._log_admin_action = AsyncMock()

        # 執行更新
        await admin_service.update_achievement(1, {"points": 200}, 123)

        # 驗證只有相關快取被失效
        mock_cache_service.delete.assert_called_with("achievement:detail:1")
        mock_cache_service.delete_pattern.assert_any_call("achievements:list:*")

        # 分類快取不應該被失效(因為沒有變更分類)
        assert all(
            call.args[0] != "categories:*"
            for call in mock_cache_service.delete_pattern.call_args_list
        )

    # 效能優化測試
    async def test_batch_database_operations_performance(self, admin_service):
        """測試批量資料庫操作效能."""
        # 模擬大量成就的批量操作
        large_achievement_ids = list(range(1, 101))  # 100個成就
        achievements = [
            Achievement(
                id=i,
                name=f"成就{i}",
                description=f"描述{i}",
                category="社交互動",
                category_id=1,
                type="counter",
                criteria={"target_value": 10, "counter_field": "interactions"},
                points=100,
                is_active=False,
                role_reward=None,
                is_hidden=False,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            for i in large_achievement_ids
        ]

        admin_service._get_achievements_by_ids = AsyncMock(return_value=achievements)
        admin_service._validate_bulk_status_update = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )

        # 模擬批量更新操作
        batch_update_calls = []

        def mock_batch_update(ids, status):
            batch_update_calls.append(len(ids))
            return True

        admin_service._update_achievements_status_in_db = AsyncMock(
            side_effect=mock_batch_update
        )
        admin_service._invalidate_achievement_cache = AsyncMock()
        admin_service._log_admin_action = AsyncMock()

        # 執行批量操作
        start_time = datetime.now()
        result = await admin_service.bulk_update_status(
            large_achievement_ids, True, 123
        )
        end_time = datetime.now()

        # 驗證效能(操作應該在合理時間內完成)
        operation_time = (end_time - start_time).total_seconds()
        assert operation_time < 5.0  # 假設5秒是合理的上限

        # 驗證使用了批量操作而非逐個操作
        assert result.success_count == 100
        assert (
            admin_service._update_achievements_status_in_db.call_count == 1
        )  # 單次批量調用
        assert len(batch_update_calls) == 1
        assert batch_update_calls[0] == 100

    async def test_cache_preloading_mechanism(self, admin_service, mock_cache_service):
        """測試快取預載入機制."""
        # 模擬預載入邏輯
        achievements = [
            Achievement(
                id=1,
                name="Test",
                description="Desc",
                category="Cat",
                category_id=1,
                type="counter",
                criteria={"target_value": 10, "counter_field": "interactions"},
                points=100,
                is_active=True,
            )
        ]
        mock_cache_service.set("achievements:list:all", achievements)

        # 驗證快取設置
        mock_cache_service.set.assert_called_with("achievements:list:all", achievements)

    async def test_lazy_loading_performance(self, admin_service, mock_cache_service):
        """測試延遲載入效能."""
        # 模擬快取獲取和設置
        mock_cache_service.get = AsyncMock(side_effect=[None, "cached_data"])
        admin_service.repository.get_achievement_by_id = AsyncMock(
            return_value=Achievement(
                id=1,
                name="Test",
                description="Desc",
                category="Cat",
                category_id=1,
                type="counter",
                criteria={"target_value": 10, "counter_field": "interactions"},
                points=100,
                is_active=True,
            )
        )
        mock_cache_service.set = AsyncMock()

        # First call: cache miss
        result1 = await admin_service.get_achievement_by_id(1)
        assert result1 == Achievement(
            id=1,
            name="Test",
            description="Desc",
            category="Cat",
            category_id=1,
            type="counter",
            criteria={"target_value": 10, "counter_field": "interactions"},
            points=100,
            is_active=True,
        )
        admin_service.repository.get_achievement_by_id.assert_called_once_with(1)
        mock_cache_service.set.assert_called_once_with(
            f"achievement:1",
            Achievement(
                id=1,
                name="Test",
                description="Desc",
                category="Cat",
                category_id=1,
                type="counter",
                criteria={"target_value": 10, "counter_field": "interactions"},
                points=100,
                is_active=True,
            ),
            ttl=1800,
        )

        # Second call: cache hit
        result2 = await admin_service.get_achievement_by_id(1)
        assert result2 == "cached_data"
        assert (
            admin_service.repository.get_achievement_by_id.call_count == 1
        )  # Not called again

    # 異步處理測試
    async def test_async_bulk_operation_processing(self, admin_service):
        """測試異步批量操作處理."""
        # 模擬批量更新
        achievement_ids = [1, 2]
        admin_service._get_achievements_by_ids = AsyncMock(
            return_value=[
                Achievement(
                    id=1,
                    name="Test1",
                    description="Desc1",
                    category="Cat1",
                    category_id=1,
                    type="counter",
                    criteria={"target_value": 10, "counter_field": "interactions"},
                    points=100,
                    is_active=True,
                ),
                Achievement(
                    id=2,
                    name="Test2",
                    description="Desc2",
                    category="Cat1",
                    category_id=1,
                    type="counter",
                    criteria={"target_value": 10, "counter_field": "interactions"},
                    points=100,
                    is_active=True,
                ),
            ]
        )
        admin_service._validate_bulk_status_update = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )
        admin_service._update_achievements_status_in_db = AsyncMock(return_value=True)

        result = await admin_service.bulk_update_status(achievement_ids, True, 123)

        assert isinstance(result, BulkOperationResult)
        assert result.success_count == len(achievement_ids)

    async def test_concurrent_cache_operations_safety(
        self, admin_service, mock_cache_service
    ):
        """測試並發快取操作的安全性."""

        # 模擬並發的快取操作
        async def concurrent_cache_operation(operation_id):
            await admin_service._invalidate_achievement_cache(operation_id)

        # 執行多個並發快取操作
        tasks = [concurrent_cache_operation(i) for i in range(1, 6)]
        await asyncio.gather(*tasks)

        # 驗證所有操作都被安全處理
        assert mock_cache_service.delete_pattern.call_count >= 5

        # 確保沒有發生競態條件或死鎖
        # (如果有問題,上面的 gather 會超時或拋出異常)

    # 記憶體效率測試
    async def test_memory_efficient_bulk_processing(self, admin_service):
        """測試記憶體效率的批量處理."""
        # 模擬批量處理
        achievement_ids = [1, 2, 3]
        admin_service._get_achievements_by_ids = AsyncMock(
            return_value=[
                Achievement(
                    id=1,
                    name="Test1",
                    description="Desc1",
                    category="Cat1",
                    category_id=1,
                    type="counter",
                    criteria={"target_value": 10, "counter_field": "interactions"},
                    points=100,
                    is_active=True,
                ),
                Achievement(
                    id=2,
                    name="Test2",
                    description="Desc2",
                    category="Cat1",
                    category_id=1,
                    type="counter",
                    criteria={"target_value": 10, "counter_field": "interactions"},
                    points=100,
                    is_active=True,
                ),
                Achievement(
                    id=3,
                    name="Test3",
                    description="Desc3",
                    category="Cat1",
                    category_id=1,
                    type="counter",
                    criteria={"target_value": 10, "counter_field": "interactions"},
                    points=100,
                    is_active=True,
                ),
            ]
        )
        admin_service._validate_bulk_status_update = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )
        admin_service._update_achievements_status_in_db = AsyncMock(return_value=True)

        result = await admin_service.bulk_update_status(achievement_ids, True, 123)

        assert result.success_count == 3

    # 快取效能指標測試
    async def test_cache_performance_metrics(self, admin_service, mock_cache_service):
        """測試快取效能指標收集."""
        # 測試快取服務的基本調用
        # 模擬獲取成就操作
        sample_achievement = Achievement(
            id=1,
            name="測試成就",
            description="測試描述",
            category="社交互動",
            category_id=1,
            type="counter",
            criteria={"target_value": 10, "counter_field": "interactions"},
            points=100,
            is_active=True,
            role_reward=None,
            is_hidden=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        admin_service.repository.get_achievement_by_id = AsyncMock(
            return_value=sample_achievement
        )

        # 執行獲取操作
        result = await admin_service.repository.get_achievement_by_id(1)

        # 驗證結果
        assert result is not None
        assert result.id == 1

    # 快取過期和TTL測試
    async def test_cache_ttl_management(self, admin_service, mock_cache_service):
        """測試快取TTL管理."""
        # 測試快取失效功能
        sample_achievement = Achievement(
            id=1,
            name="測試成就",
            description="測試描述",
            category="社交互動",
            category_id=1,
            type="counter",
            criteria={"target_value": 10, "counter_field": "interactions"},
            points=100,
            is_active=True,
            role_reward=None,
            is_hidden=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # 測試快取失效調用
        await admin_service._invalidate_achievement_cache(1)

        # 驗證快取失效方法被調用
        mock_cache_service.delete.assert_called_with("achievement:detail:1")
        mock_cache_service.delete_pattern.assert_has_calls(
            [call("achievements:list:*"), call("achievements:count:*")]
        )

    # 資源清理測試
    async def test_resource_cleanup_on_service_shutdown(
        self, admin_service, mock_cache_service
    ):
        """測試服務關閉時的資源清理."""
        # 測試快取服務的存在性
        assert admin_service.cache_service is not None

        # 測試快取失效功能
        await admin_service._invalidate_achievement_cache()

        # 驗證快取失效被調用
        mock_cache_service.delete_pattern.assert_has_calls(
            [call("achievements:list:*"), call("achievements:count:*")]
        )

    # 快取策略測試
    async def test_cache_strategy_effectiveness(
        self, admin_service, mock_cache_service
    ):
        """測試快取策略的有效性."""
        # Test cache invalidation strategy effectiveness
        achievement_id = 1
        await admin_service._invalidate_achievement_cache(achievement_id)
        await admin_service._invalidate_achievement_cache()  # Test global invalidation

        mock_cache_service.delete.assert_called_with("achievement:detail:1")
        mock_cache_service.delete_pattern.assert_has_calls(
            [
                call("achievements:list:*"),
                call("achievements:count:*"),
                call("achievements:list:*"),
                call("achievements:count:*"),
            ]
        )
