"""成就批量操作功能單元測試.

此模組測試批量操作的所有核心功能：
- 批量狀態變更
- 批量刪除
- 批量分類變更
- 依賴關係分析
- 進度追蹤
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.cogs.achievement.database.models import Achievement
from src.cogs.achievement.services.admin_service import (
    AchievementAdminService,
    BulkOperationResult,
    ValidationResult,
)


class TestBulkOperations:
    """批量操作功能測試."""

    @pytest.fixture
    def mock_repository(self):
        """模擬資料庫倉庫."""
        repository = AsyncMock()
        return repository

    @pytest.fixture
    def mock_permission_service(self):
        """模擬權限服務."""
        permission_service = AsyncMock()
        permission_service.check_admin_permission.return_value = True
        return permission_service

    @pytest.fixture
    def mock_cache_service(self):
        """模擬快取服務."""
        cache_service = AsyncMock()
        return cache_service

    @pytest.fixture
    def admin_service(
        self, mock_repository, mock_permission_service, mock_cache_service
    ):
        """建立管理服務實例."""
        return AchievementAdminService(
            repository=mock_repository,
            permission_service=mock_permission_service,
            cache_service=mock_cache_service,
        )

    @pytest.fixture
    def sample_achievements(self):
        """樣本成就列表."""
        return [
            Achievement(
                id=1,
                name="成就1",
                description="描述1",
                category="社交互動",
                type="counter",
                criteria={"target_value": 10},
                points=100,
                is_active=True,
                role_reward=None,
                is_hidden=False,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
            Achievement(
                id=2,
                name="成就2",
                description="描述2",
                category="活躍度",
                type="milestone",
                criteria={"target": 50},
                points=200,
                is_active=False,
                role_reward="VIP會員",
                is_hidden=True,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
            Achievement(
                id=3,
                name="成就3",
                description="描述3",
                category="社交互動",
                type="time_based",
                criteria={"duration": 3600},
                points=150,
                is_active=True,
                role_reward=None,
                is_hidden=False,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
        ]

    # 批量狀態變更測試
    async def test_bulk_update_status_success(self, admin_service, sample_achievements):
        """測試成功批量更新狀態."""
        achievement_ids = [1, 2, 3]

        # 配置模擬
        admin_service._get_achievements_by_ids = AsyncMock(
            return_value=sample_achievements
        )
        admin_service._validate_bulk_status_update = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )
        admin_service._update_achievements_status_in_db = AsyncMock()
        admin_service._invalidate_achievement_cache = AsyncMock()
        admin_service._log_admin_action = AsyncMock()

        # 執行測試
        result = await admin_service.bulk_update_status(achievement_ids, True, 123)

        # 驗證結果
        assert isinstance(result, BulkOperationResult)
        assert result.success_count == 3
        assert result.failed_count == 0
        assert len(result.affected_achievements) == 3
        admin_service._update_achievements_status_in_db.assert_called_once_with(
            achievement_ids, True
        )
        admin_service._invalidate_achievement_cache.assert_called_once()

    async def test_bulk_update_status_partial_success(
        self, admin_service, sample_achievements
    ):
        """測試批量更新狀態部分成功."""
        achievement_ids = [1, 2, 999]  # 999 不存在
        existing_achievements = sample_achievements[:2]  # 只有前兩個存在

        # 配置模擬
        admin_service._get_achievements_by_ids = AsyncMock(
            return_value=existing_achievements
        )
        admin_service._validate_bulk_status_update = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )
        admin_service._update_achievements_status_in_db = AsyncMock()
        admin_service._invalidate_achievement_cache = AsyncMock()
        admin_service._log_admin_action = AsyncMock()

        # 執行測試
        result = await admin_service.bulk_update_status(achievement_ids, False, 123)

        # 驗證結果
        assert result.success_count == 2
        assert result.failed_count == 1
        assert len(result.affected_achievements) == 2
        assert "成就 999 不存在" in result.errors

    async def test_bulk_update_status_no_changes_needed(self, admin_service):
        """測試批量更新狀態時無需變更."""
        # 所有成就都已經是目標狀態
        achievements = [
            Achievement(id=1, name="成就1", is_active=True, role_reward=None, is_hidden=False),
            Achievement(id=2, name="成就2", is_active=True, role_reward=None, is_hidden=False),
        ]

        admin_service._get_achievements_by_ids = AsyncMock(return_value=achievements)
        admin_service._validate_bulk_status_update = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )

        # 執行測試 - 嘗試啟用已啟用的成就
        result = await admin_service.bulk_update_status([1, 2], True, 123)

        # 驗證結果 - 應該跳過無需變更的成就
        assert result.success_count == 0
        assert result.failed_count == 0
        assert "無需變更" in str(result.details)

    # 批量刪除測試
    async def test_bulk_delete_success(self, admin_service, sample_achievements):
        """測試成功批量刪除."""
        achievement_ids = [1, 2, 3]

        # 配置模擬
        admin_service._get_achievements_by_ids = AsyncMock(
            return_value=sample_achievements
        )
        admin_service._analyze_bulk_delete_dependencies = AsyncMock(
            return_value={
                "safe_to_delete": achievement_ids,
                "dependencies": {},
                "warnings": [],
            }
        )
        admin_service._delete_achievements_from_db = AsyncMock()
        admin_service._invalidate_achievement_cache = AsyncMock()
        admin_service._log_admin_action = AsyncMock()

        # 執行測試
        result = await admin_service.bulk_delete(achievement_ids, 123)

        # 驗證結果
        assert result.success_count == 3
        assert result.failed_count == 0
        assert len(result.affected_achievements) == 3
        admin_service._delete_achievements_from_db.assert_called_once_with(
            achievement_ids
        )

    async def test_bulk_delete_with_dependencies(
        self, admin_service, sample_achievements
    ):
        """測試批量刪除有依賴關係的成就."""
        achievement_ids = [1, 2, 3]

        # 配置依賴關係分析
        admin_service._get_achievements_by_ids = AsyncMock(
            return_value=sample_achievements
        )
        admin_service._analyze_bulk_delete_dependencies = AsyncMock(
            return_value={
                "safe_to_delete": [2, 3],  # 只有部分可以安全刪除
                "dependencies": {
                    1: ["prerequisite_achievement_4"]  # 成就1有依賴
                },
                "warnings": ["成就1有依賴關係，無法刪除"],
            }
        )

        # 執行測試（非強制模式）
        result = await admin_service.bulk_delete(achievement_ids, 123, force=False)

        # 驗證結果
        assert result.success_count == 2  # 只刪除了2個
        assert result.failed_count == 1  # 1個因依賴失敗
        assert "依賴關係" in result.errors[0]

    async def test_bulk_delete_force_mode(self, admin_service, sample_achievements):
        """測試強制批量刪除模式."""
        achievement_ids = [1, 2, 3]

        # 配置模擬
        admin_service._get_achievements_by_ids = AsyncMock(
            return_value=sample_achievements
        )
        admin_service._analyze_bulk_delete_dependencies = AsyncMock(
            return_value={
                "safe_to_delete": [2, 3],
                "dependencies": {1: ["prerequisite_achievement_4"]},
                "warnings": ["成就1有依賴關係"],
            }
        )
        admin_service._force_delete_achievements_from_db = AsyncMock()
        admin_service._invalidate_achievement_cache = AsyncMock()
        admin_service._log_admin_action = AsyncMock()

        # 執行測試（強制模式）
        result = await admin_service.bulk_delete(achievement_ids, 123, force=True)

        # 驗證結果
        assert result.success_count == 3  # 強制模式全部刪除
        assert result.failed_count == 0
        admin_service._force_delete_achievements_from_db.assert_called_once_with(
            achievement_ids
        )

    # 批量分類變更測試
    async def test_bulk_update_category_success(
        self, admin_service, sample_achievements
    ):
        """測試成功批量變更分類."""
        achievement_ids = [1, 2, 3]
        target_category = "成長里程"

        # 配置模擬
        admin_service._get_achievements_by_ids = AsyncMock(
            return_value=sample_achievements
        )
        admin_service._validate_category_exists = AsyncMock(return_value=True)
        admin_service._update_achievements_category_in_db = AsyncMock()
        admin_service._invalidate_achievement_cache = AsyncMock()
        admin_service._invalidate_category_cache = AsyncMock()
        admin_service._log_admin_action = AsyncMock()

        # 執行測試
        result = await admin_service.bulk_update_category(
            achievement_ids, target_category, 123
        )

        # 驗證結果
        assert result.success_count == 3
        assert result.failed_count == 0
        assert len(result.affected_achievements) == 3
        admin_service._update_achievements_category_in_db.assert_called_once_with(
            achievement_ids, target_category
        )
        admin_service._invalidate_achievement_cache.assert_called_once()
        admin_service._invalidate_category_cache.assert_called_once()

    async def test_bulk_update_category_invalid_target(
        self, admin_service, sample_achievements
    ):
        """測試批量變更到無效分類."""
        achievement_ids = [1, 2, 3]
        invalid_category = "不存在的分類"

        # 配置無效分類
        admin_service._get_achievements_by_ids = AsyncMock(
            return_value=sample_achievements
        )
        admin_service._validate_category_exists = AsyncMock(return_value=False)

        # 執行測試
        result = await admin_service.bulk_update_category(
            achievement_ids, invalid_category, 123
        )

        # 驗證結果
        assert result.success_count == 0
        assert result.failed_count == 3
        assert f"目標分類「{invalid_category}」不存在" in result.errors[0]

    async def test_bulk_update_category_skip_same_category(self, admin_service):
        """測試批量變更分類時智能跳過已在目標分類的成就."""
        # 成就1和3已經在目標分類，只有成就2需要變更
        achievements = [
            Achievement(id=1, name="成就1", category="目標分類", role_reward=None, is_hidden=False),
            Achievement(id=2, name="成就2", category="其他分類", role_reward=None, is_hidden=False),
            Achievement(id=3, name="成就3", category="目標分類", role_reward=None, is_hidden=False),
        ]

        admin_service._get_achievements_by_ids = AsyncMock(return_value=achievements)
        admin_service._validate_category_exists = AsyncMock(return_value=True)
        admin_service._update_achievements_category_in_db = AsyncMock()
        admin_service._invalidate_achievement_cache = AsyncMock()
        admin_service._invalidate_category_cache = AsyncMock()
        admin_service._log_admin_action = AsyncMock()

        # 執行測試
        result = await admin_service.bulk_update_category([1, 2, 3], "目標分類", 123)

        # 驗證結果
        assert result.success_count == 1  # 只變更了成就2
        assert result.failed_count == 0
        assert "智能跳過" in str(result.details)
        # 只應該更新成就2
        admin_service._update_achievements_category_in_db.assert_called_once_with(
            [2], "目標分類"
        )

    # 依賴關係分析測試
    async def test_analyze_bulk_delete_dependencies_no_dependencies(
        self, admin_service
    ):
        """測試分析批量刪除無依賴關係的情況."""
        achievement_ids = [1, 2, 3]

        # 配置無依賴關係
        admin_service._check_achievement_dependencies = AsyncMock(return_value=[])

        # 執行測試
        analysis = await admin_service._analyze_bulk_delete_dependencies(
            achievement_ids
        )

        # 驗證結果
        assert analysis["safe_to_delete"] == achievement_ids
        assert len(analysis["dependencies"]) == 0
        assert len(analysis["warnings"]) == 0

    async def test_analyze_bulk_delete_dependencies_with_dependencies(
        self, admin_service
    ):
        """測試分析批量刪除有依賴關係的情況."""
        achievement_ids = [1, 2, 3]

        # 配置依賴關係
        def mock_check_dependencies(achievement_id):
            if achievement_id == 1:
                return [{"id": 4, "name": "依賴成就4"}]
            elif achievement_id == 2:
                return [{"id": 5, "name": "依賴成就5"}, {"id": 6, "name": "依賴成就6"}]
            return []

        admin_service._check_achievement_dependencies = AsyncMock(
            side_effect=mock_check_dependencies
        )

        # 執行測試
        analysis = await admin_service._analyze_bulk_delete_dependencies(
            achievement_ids
        )

        # 驗證結果
        assert analysis["safe_to_delete"] == [3]  # 只有成就3無依賴
        assert 1 in analysis["dependencies"]
        assert 2 in analysis["dependencies"]
        assert len(analysis["dependencies"][1]) == 1
        assert len(analysis["dependencies"][2]) == 2
        assert len(analysis["warnings"]) == 2

    # 權限檢查測試
    async def test_bulk_operations_permission_denied(
        self, admin_service, mock_permission_service
    ):
        """測試批量操作權限被拒絕."""
        # 配置權限檢查失敗
        mock_permission_service.check_admin_permission.return_value = False

        # 執行測試
        result = await admin_service.bulk_update_status([1, 2, 3], True, 123)

        # 驗證結果
        assert result.success_count == 0
        assert result.failed_count == 3
        assert "權限不足" in result.errors[0]

    # 錯誤處理測試
    async def test_bulk_update_status_database_error(
        self, admin_service, sample_achievements
    ):
        """測試批量狀態更新時資料庫錯誤處理."""
        achievement_ids = [1, 2, 3]

        admin_service._get_achievements_by_ids = AsyncMock(
            return_value=sample_achievements
        )
        admin_service._validate_bulk_status_update = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )
        admin_service._update_achievements_status_in_db = AsyncMock(
            side_effect=Exception("資料庫連接失敗")
        )

        # 執行測試
        result = await admin_service.bulk_update_status(achievement_ids, True, 123)

        # 驗證結果
        assert result.success_count == 0
        assert result.failed_count == 3
        assert "資料庫連接失敗" in result.errors[0]

    async def test_bulk_delete_database_error(self, admin_service, sample_achievements):
        """測試批量刪除時資料庫錯誤處理."""
        achievement_ids = [1, 2, 3]

        admin_service._get_achievements_by_ids = AsyncMock(
            return_value=sample_achievements
        )
        admin_service._analyze_bulk_delete_dependencies = AsyncMock(
            return_value={
                "safe_to_delete": achievement_ids,
                "dependencies": {},
                "warnings": [],
            }
        )
        admin_service._delete_achievements_from_db = AsyncMock(
            side_effect=Exception("刪除操作失敗")
        )

        # 執行測試
        result = await admin_service.bulk_delete(achievement_ids, 123)

        # 驗證結果
        assert result.success_count == 0
        assert result.failed_count == 3
        assert "刪除操作失敗" in result.errors[0]

    # 進度追蹤測試
    async def test_bulk_operation_progress_tracking(
        self, admin_service, sample_achievements
    ):
        """測試批量操作進度追蹤功能."""
        achievement_ids = [1, 2, 3, 4, 5]  # 較多成就用於測試進度

        # 模擬逐個處理的過程
        processed_achievements = []

        def mock_process_achievement(achievement_id):
            processed_achievements.append(achievement_id)
            return True

        admin_service._get_achievements_by_ids = AsyncMock(
            return_value=sample_achievements[:3]
        )
        admin_service._validate_bulk_status_update = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )

        # 模擬分批處理
        admin_service._update_achievements_status_in_db = AsyncMock(
            side_effect=lambda ids, status: [
                mock_process_achievement(aid) for aid in ids
            ]
        )
        admin_service._invalidate_achievement_cache = AsyncMock()
        admin_service._log_admin_action = AsyncMock()

        # 執行測試
        result = await admin_service.bulk_update_status(achievement_ids[:3], True, 123)

        # 驗證結果包含進度資訊
        assert result.success_count == 3
        assert result.total_count == 3
        assert result.success_rate == 100.0

    # 批量操作結果類別測試
    async def test_bulk_operation_result_methods(self):
        """測試BulkOperationResult類別的方法."""
        result = BulkOperationResult()

        # 測試添加成功結果
        achievement = Achievement(id=1, name="測試成就", role_reward=None, is_hidden=False)
        result.add_success(achievement, "成功訊息")

        assert result.success_count == 1
        assert result.failed_count == 0
        assert len(result.affected_achievements) == 1
        assert "success_1" in result.details

        # 測試添加錯誤結果
        result.add_error("錯誤訊息")

        assert result.success_count == 1
        assert result.failed_count == 1
        assert "錯誤訊息" in result.errors

        # 測試計算屬性
        assert result.total_count == 2
        assert result.success_rate == 50.0

    # 驗證結果類別測試
    async def test_validation_result_methods(self):
        """測試ValidationResult類別的方法."""
        validation = ValidationResult(is_valid=True)

        # 添加錯誤應該使 is_valid 變為 False
        validation.add_error("測試錯誤")

        assert validation.is_valid is False
        assert "測試錯誤" in validation.errors

        # 添加警告不應影響 is_valid
        validation = ValidationResult(is_valid=True)
        validation.add_warning("測試警告")

        assert validation.is_valid is True
        assert "測試警告" in validation.warnings

    # 批量操作統計測試
    async def test_bulk_operation_statistics(self, admin_service):
        """測試批量操作統計收集."""
        # 模擬混合結果：部分成功，部分失敗
        achievements = [
            Achievement(id=1, name="成就1", is_active=False, role_reward=None, is_hidden=False),
            Achievement(id=2, name="成就2", is_active=False, role_reward=None, is_hidden=False),
            Achievement(id=3, name="成就3", is_active=True, role_reward=None, is_hidden=False),  # 已啟用，無需變更
        ]

        admin_service._get_achievements_by_ids = AsyncMock(return_value=achievements)
        admin_service._validate_bulk_status_update = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )

        # 模擬部分操作失敗
        def mock_update_status(ids, status):
            # 假設第一個成就更新失敗
            if 1 in ids:
                raise Exception("成就1更新失敗")
            return True

        admin_service._update_achievements_status_in_db = AsyncMock(
            side_effect=mock_update_status
        )
        admin_service._invalidate_achievement_cache = AsyncMock()
        admin_service._log_admin_action = AsyncMock()

        # 執行測試
        result = await admin_service.bulk_update_status([1, 2, 3], True, 123)

        # 驗證統計資訊
        assert result.total_count > 0
        assert 0 <= result.success_rate <= 100
        assert len(result.errors) > 0 or result.failed_count > 0
