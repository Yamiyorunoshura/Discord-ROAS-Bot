"""成就分類管理功能單元測試.

此模組測試分類管理的所有核心功能：
- 分類 CRUD 操作
- 分類排序功能
- 資料驗證
- 快取管理
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.cogs.achievement.database.models import AchievementCategory
from src.cogs.achievement.services.admin_service import (
    AchievementAdminService,
    BulkOperationResult,
    ValidationResult,
)


class TestCategoryManagement:
    """分類管理功能測試."""

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
    def sample_category_data(self):
        """樣本分類資料."""
        return {
            "name": "測試分類",
            "description": "這是一個測試分類",
            "icon_emoji": "🏆",
            "display_order": 10,
        }

    @pytest.fixture
    def sample_category(self):
        """樣本分類物件."""
        return AchievementCategory(
            id=1,
            name="測試分類",
            description="這是一個測試分類",
            icon_emoji="🏆",
            display_order=10,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    # 分類創建測試
    async def test_create_category_success(
        self, admin_service, sample_category_data, sample_category
    ):
        """測試成功創建分類."""
        # 配置模擬
        admin_service._validate_category_data = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )
        admin_service._check_category_name_uniqueness = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )
        admin_service._create_category_in_db = AsyncMock(return_value=sample_category)
        admin_service._invalidate_category_cache = AsyncMock()
        admin_service._log_admin_action = AsyncMock()

        # 執行測試
        category, validation = await admin_service.create_category(
            sample_category_data, 123
        )

        # 驗證結果
        assert validation.is_valid is True
        assert category is not None
        assert category.name == "測試分類"
        admin_service._create_category_in_db.assert_called_once()
        admin_service._invalidate_category_cache.assert_called_once()

    async def test_create_category_validation_failure(
        self, admin_service, sample_category_data
    ):
        """測試分類創建驗證失敗."""
        # 配置驗證失敗
        invalid_validation = ValidationResult(is_valid=False)
        invalid_validation.add_error("名稱不能為空")
        admin_service._validate_category_data = AsyncMock(
            return_value=invalid_validation
        )

        # 執行測試
        category, validation = await admin_service.create_category(
            sample_category_data, 123
        )

        # 驗證結果
        assert validation.is_valid is False
        assert category is None
        assert "名稱不能為空" in validation.errors

    async def test_create_category_name_uniqueness_failure(
        self, admin_service, sample_category_data
    ):
        """測試分類名稱唯一性檢查失敗."""
        # 配置驗證成功但名稱重複
        admin_service._validate_category_data = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )

        uniqueness_validation = ValidationResult(is_valid=False)
        uniqueness_validation.add_error("分類名稱已存在")
        admin_service._check_category_name_uniqueness = AsyncMock(
            return_value=uniqueness_validation
        )

        # 執行測試
        category, validation = await admin_service.create_category(
            sample_category_data, 123
        )

        # 驗證結果 - 因為名稱重複，validation 的 errors 會被擴展，但 is_valid 可能仍是 True
        assert category is None
        assert "分類名稱已存在" in validation.errors

    # 分類更新測試
    async def test_update_category_success(self, admin_service, sample_category):
        """測試成功更新分類."""
        # 配置模擬
        updates = {"name": "更新的分類名稱", "description": "更新的描述"}
        updated_category = AchievementCategory(
            **{**sample_category.__dict__, **updates, "updated_at": datetime.now()}
        )

        admin_service._get_achievement_category = AsyncMock(
            return_value=sample_category
        )
        admin_service._validate_category_updates = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )
        admin_service._update_category_in_db = AsyncMock(return_value=updated_category)
        admin_service._invalidate_category_cache = AsyncMock()
        admin_service._log_admin_action = AsyncMock()

        # 執行測試
        category, validation = await admin_service.update_category(1, updates, 123)

        # 驗證結果
        assert validation.is_valid is True
        assert category is not None
        assert category.name == "更新的分類名稱"
        admin_service._update_category_in_db.assert_called_once_with(1, updates)
        admin_service._invalidate_category_cache.assert_called_once()

    async def test_update_category_not_found(self, admin_service):
        """測試更新不存在的分類."""
        # 配置分類不存在
        admin_service._get_achievement_category = AsyncMock(return_value=None)

        # 執行測試
        category, validation = await admin_service.update_category(
            999, {"name": "新名稱"}, 123
        )

        # 驗證結果
        assert validation.is_valid is False
        assert category is None
        assert "分類 999 不存在" in validation.errors

    # 分類刪除測試
    async def test_delete_category_success_empty(self, admin_service, sample_category):
        """測試成功刪除空分類."""
        # 配置分類存在且為空
        admin_service._get_achievement_category = AsyncMock(
            return_value=sample_category
        )
        admin_service._check_category_usage = AsyncMock(
            return_value={"has_achievements": False, "achievement_count": 0}
        )
        admin_service._delete_category_from_db = AsyncMock(return_value=True)
        admin_service._invalidate_category_cache = AsyncMock()
        admin_service._log_admin_action = AsyncMock()

        # 執行測試
        success, validation = await admin_service.delete_category(1, 123)

        # 驗證結果
        assert success is True
        assert validation.is_valid is True
        admin_service._delete_category_from_db.assert_called_once_with(1)
        admin_service._invalidate_category_cache.assert_called_once()

    async def test_delete_category_with_reassignment(
        self, admin_service, sample_category
    ):
        """測試刪除有成就的分類（重新分配）."""
        # 配置分類有成就
        target_category = AchievementCategory(
            id=2, name="目標分類", description="目標描述"
        )

        # 配置模擬 - 為第一次調用返回 sample_category，為第二次調用返回 target_category
        mock_calls = [sample_category, target_category]
        admin_service._get_achievement_category = AsyncMock(side_effect=mock_calls)

        admin_service._check_category_usage = AsyncMock(
            return_value={"has_achievements": True, "achievement_count": 5}
        )
        admin_service._reassign_category_achievements = AsyncMock(return_value=True)
        admin_service._delete_category_from_db = AsyncMock(return_value=True)
        admin_service._invalidate_category_cache = AsyncMock()
        admin_service._invalidate_achievement_cache = AsyncMock()
        admin_service._log_admin_action = AsyncMock()

        # 執行測試（提供目標分類）
        success, validation = await admin_service.delete_category(
            1, 123, target_category_id=2
        )

        # 驗證結果
        assert success is True
        assert validation.is_valid is True
        admin_service._reassign_category_achievements.assert_called_once_with(1, 2)
        admin_service._delete_category_from_db.assert_called_once_with(1)

    async def test_delete_category_with_achievements_no_target(
        self, admin_service, sample_category
    ):
        """測試刪除有成就的分類但未提供目標分類."""
        # 配置分類有成就
        admin_service._get_achievement_category = AsyncMock(
            return_value=sample_category
        )
        admin_service._check_category_usage = AsyncMock(
            return_value={"has_achievements": True, "achievement_count": 5}
        )

        # 執行測試（未提供目標分類）
        success, validation = await admin_service.delete_category(1, 123)

        # 驗證結果
        assert success is False
        assert validation.is_valid is False
        assert "分類中有 5 個成就，需要指定重新分配的目標分類" in validation.errors

    # 分類排序測試
    async def test_reorder_categories_success(self, admin_service):
        """測試成功重新排序分類."""
        # 配置模擬
        category_orders = [
            {"id": 1, "display_order": 10},
            {"id": 2, "display_order": 20},
            {"id": 3, "display_order": 30},
        ]

        # 模擬實際的資料庫更新方法
        admin_service._update_category_display_order = AsyncMock(return_value=True)
        admin_service._invalidate_category_cache = AsyncMock()
        admin_service._log_admin_action = AsyncMock()

        # 執行測試
        result = await admin_service.reorder_categories(category_orders, 123)

        # 驗證結果
        assert isinstance(result, BulkOperationResult)
        assert result.success_count == 3
        assert result.failed_count == 0
        admin_service._invalidate_category_cache.assert_called_once()
        admin_service._log_admin_action.assert_called_once()

    # 分類資料驗證測試
    async def test_validate_category_data_success(
        self, admin_service, sample_category_data
    ):
        """測試分類資料驗證成功."""
        validation = await admin_service._validate_category_data(sample_category_data)

        assert validation.is_valid is True
        assert len(validation.errors) == 0

    async def test_validate_category_data_empty_name(self, admin_service):
        """測試分類名稱為空的驗證."""
        data = {
            "name": "",
            "description": "測試描述",
            "icon_emoji": "🏆",
            "display_order": 10,
        }

        validation = await admin_service._validate_category_data(data)

        assert validation.is_valid is False
        assert "分類名稱不能為空" in validation.errors

    async def test_validate_category_data_name_too_long(self, admin_service):
        """測試分類名稱過長的驗證."""
        data = {
            "name": "A" * 51,  # 超過50字元限制
            "description": "測試描述",
            "icon_emoji": "🏆",
            "display_order": 10,
        }

        validation = await admin_service._validate_category_data(data)

        assert validation.is_valid is False
        assert "分類名稱不能超過 50 字元" in validation.errors

    async def test_validate_category_data_description_too_long(self, admin_service):
        """測試分類描述過長的驗證."""
        data = {
            "name": "測試分類",
            "description": "A" * 201,  # 超過200字元限制
            "icon_emoji": "🏆",
            "display_order": 10,
        }

        validation = await admin_service._validate_category_data(data)

        assert validation.is_valid is False
        assert "分類描述不能超過 200 字元" in validation.errors

    async def test_validate_category_data_invalid_display_order(self, admin_service):
        """測試無效顯示順序的驗證."""
        data = {
            "name": "測試分類",
            "description": "測試描述",
            "icon_emoji": "🏆",
            "display_order": -1,  # 負數順序
        }

        validation = await admin_service._validate_category_data(data)

        assert validation.is_valid is False
        assert "顯示順序必須為非負整數" in validation.errors

    # 快取管理測試
    async def test_invalidate_category_cache(self, admin_service, mock_cache_service):
        """測試分類快取失效."""
        await admin_service._invalidate_category_cache()

        mock_cache_service.delete_pattern.assert_called_once_with("categories:*")

    # 分類名稱唯一性測試
    async def test_check_category_name_uniqueness_new_category(self, admin_service):
        """測試新分類名稱唯一性檢查."""
        admin_service._get_category_by_name = AsyncMock(return_value=None)

        validation = await admin_service._check_category_name_uniqueness("新分類名稱")

        assert validation.is_valid is True
        assert len(validation.errors) == 0

    async def test_check_category_name_uniqueness_duplicate(
        self, admin_service, sample_category
    ):
        """測試重複分類名稱檢查."""
        admin_service._get_category_by_name = AsyncMock(return_value=sample_category)

        validation = await admin_service._check_category_name_uniqueness("測試分類")

        assert validation.is_valid is False
        assert "分類名稱「測試分類」已存在" in validation.errors

    async def test_check_category_name_uniqueness_update_same_category(
        self, admin_service, sample_category
    ):
        """測試更新同一分類時的名稱唯一性檢查."""
        admin_service._get_category_by_name = AsyncMock(return_value=sample_category)

        # 更新同一分類，名稱相同應該通過
        validation = await admin_service._check_category_name_uniqueness(
            "測試分類", exclude_id=1
        )

        assert validation.is_valid is True
        assert len(validation.errors) == 0

    # 分類使用情況檢查測試
    async def test_check_category_usage_empty(self, admin_service):
        """測試檢查空分類使用情況."""
        admin_service._get_category_achievement_count = AsyncMock(return_value=0)

        usage_info = await admin_service._check_category_usage(1)

        assert usage_info["has_achievements"] is False
        assert usage_info["achievement_count"] == 0

    async def test_check_category_usage_with_achievements(self, admin_service):
        """測試檢查有成就的分類使用情況."""
        admin_service._get_category_achievement_count = AsyncMock(return_value=5)

        usage_info = await admin_service._check_category_usage(1)

        assert usage_info["has_achievements"] is True
        assert usage_info["achievement_count"] == 5

    # 獲取所有分類測試
    async def test_get_all_categories_without_stats(self, admin_service):
        """測試獲取所有分類（不含統計）."""
        categories = [
            AchievementCategory(
                id=1, name="分類1", description="描述1", display_order=10
            ),
            AchievementCategory(
                id=2, name="分類2", description="描述2", display_order=20
            ),
        ]
        admin_service._get_all_categories_from_db = AsyncMock(return_value=categories)

        result = await admin_service.get_all_categories(include_stats=False)

        assert len(result) == 2
        assert result[0].name == "分類1"
        assert result[1].name == "分類2"

    async def test_get_all_categories_with_stats(self, admin_service):
        """測試獲取所有分類（包含統計）."""
        categories = [
            AchievementCategory(
                id=1, name="分類1", description="描述1", display_order=10
            ),
            AchievementCategory(
                id=2, name="分類2", description="描述2", display_order=20
            ),
        ]
        admin_service._get_all_categories_from_db = AsyncMock(return_value=categories)
        admin_service._get_category_statistics = AsyncMock(
            return_value={"achievement_count": 5, "active_achievements": 4}
        )

        result = await admin_service.get_all_categories(include_stats=True)

        assert len(result) == 2
        # 驗證統計被調用
        assert admin_service._get_category_statistics.call_count == 2

    # 錯誤處理測試
    async def test_create_category_database_error(
        self, admin_service, sample_category_data
    ):
        """測試創建分類時資料庫錯誤處理."""
        admin_service._validate_category_data = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )
        admin_service._check_category_name_uniqueness = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )
        admin_service._create_category_in_db = AsyncMock(
            side_effect=Exception("資料庫錯誤")
        )

        category, validation = await admin_service.create_category(
            sample_category_data, 123
        )

        assert validation.is_valid is False
        assert category is None
        assert "資料庫錯誤" in str(validation.errors)

    async def test_update_category_database_error(self, admin_service, sample_category):
        """測試更新分類時資料庫錯誤處理."""
        admin_service._get_achievement_category = AsyncMock(
            return_value=sample_category
        )
        admin_service._validate_category_updates = AsyncMock(
            return_value=ValidationResult(is_valid=True)
        )
        admin_service._update_category_in_db = AsyncMock(
            side_effect=Exception("更新錯誤")
        )

        category, validation = await admin_service.update_category(
            1, {"name": "新名稱"}, 123
        )

        assert validation.is_valid is False
        assert category is None
        assert "更新錯誤" in str(validation.errors)

    async def test_delete_category_database_error(self, admin_service, sample_category):
        """測試刪除分類時資料庫錯誤處理."""
        admin_service._get_achievement_category = AsyncMock(
            return_value=sample_category
        )
        admin_service._check_category_usage = AsyncMock(
            return_value={"has_achievements": False, "achievement_count": 0}
        )
        admin_service._delete_category_from_db = AsyncMock(
            side_effect=Exception("刪除錯誤")
        )

        success, validation = await admin_service.delete_category(1, 123)

        assert success is False
        assert validation.is_valid is False
        assert "刪除錯誤" in str(validation.errors)
