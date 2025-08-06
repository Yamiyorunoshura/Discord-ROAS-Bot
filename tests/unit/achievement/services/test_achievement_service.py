"""AchievementService 單元測試.

此模組測試成就服務的核心功能,包含:
- CRUD 操作測試
- 業務規則驗證測試
- 快取行為測試
- 錯誤處理測試

遵循 AAA 模式(Arrange, Act, Assert)和測試最佳實踐.
"""

from unittest.mock import patch

import pytest

from src.cogs.achievement.database.models import (
    Achievement,
    AchievementCategory,
    AchievementType,
)
from src.cogs.achievement.services.achievement_service import AchievementService
from tests.unit.achievement.services.conftest import (
    create_test_achievement,
    create_test_category,
    pytest_mark_unit,
)


@pytest_mark_unit
class TestAchievementService:
    """AchievementService 單元測試類別."""

    # ==========================================================================
    # 初始化和配置測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_service_initialization(self, mock_repository):
        """測試服務初始化."""
        # Arrange & Act
        service = AchievementService(
            repository=mock_repository
        )

        # Assert
        assert service._repository == mock_repository
        assert service._cache_service is not None

    @pytest.mark.asyncio
    async def test_service_context_manager(self, mock_repository):
        """測試服務上下文管理器."""
        # Arrange
        service = AchievementService(mock_repository)

        # Act & Assert
        async with service as ctx_service:
            assert ctx_service is service
            assert len(service._cache) == 0

    # ==========================================================================
    # 成就分類 CRUD 操作測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_create_category_success(self, achievement_service, repository):
        """測試成功建立成就分類."""
        # Arrange
        category = AchievementCategory(
            name="test_social",
            description="測試社交分類",
            display_order=1,
            icon_emoji="👥",
        )

        # Act
        created_category = await achievement_service.create_category(category)

        # Assert
        assert created_category.id is not None
        assert created_category.name == "test_social"
        assert created_category.description == "測試社交分類"

    @pytest.mark.asyncio
    async def test_create_category_duplicate_name(
        self, achievement_service, repository
    ):
        """測試建立重複名稱的分類時拋出錯誤."""
        # Arrange
        category1 = AchievementCategory(name="duplicate", description="第一個分類")
        category2 = AchievementCategory(name="duplicate", description="第二個分類")

        await achievement_service.create_category(category1)

        # Act & Assert
        with pytest.raises(ValueError, match="分類名稱 'duplicate' 已存在"):
            await achievement_service.create_category(category2)

    @pytest.mark.asyncio
    async def test_get_category_by_id_cached(self, achievement_service, repository):
        """測試取得分類時的快取行為."""
        # Arrange
        category = await create_test_category(repository, "cache_test")

        # Act - 第一次呼叫
        result1 = await achievement_service.get_category_by_id(category.id)

        # Act - 第二次呼叫(應從快取取得)
        result2 = await achievement_service.get_category_by_id(category.id)

        # Assert
        assert result1.id == category.id
        assert result2.id == category.id
        assert result1 is result2  # 應該是相同的物件實例(來自快取)

    @pytest.mark.asyncio
    async def test_list_categories_cached(self, achievement_service, repository):
        """測試取得分類列表的快取行為."""
        # Arrange
        await create_test_category(repository, "cat1")
        await create_test_category(repository, "cat2")

        # Act - 第一次呼叫
        result1 = await achievement_service.list_categories()

        # Act - 第二次呼叫(應從快取取得)
        result2 = await achievement_service.list_categories()

        # Assert
        assert len(result1) == 2
        assert len(result2) == 2
        # 快取應該返回相同的結果
        assert [cat.name for cat in result1] == [cat.name for cat in result2]

    @pytest.mark.asyncio
    async def test_update_category_invalidates_cache(
        self, achievement_service, repository
    ):
        """測試更新分類時無效化快取."""
        # Arrange
        category = await create_test_category(repository, "update_test")

        # 先取得一次以建立快取
        await achievement_service.get_category_by_id(category.id)

        # Act - 更新分類
        updated_category = await achievement_service.update_category(
            category.id, {"description": "更新後的描述"}
        )

        # Assert
        assert updated_category.description == "更新後的描述"

        # 驗證快取已被無效化(重新從資料庫取得)
        fresh_category = await achievement_service.get_category_by_id(category.id)
        assert fresh_category.description == "更新後的描述"

    @pytest.mark.asyncio
    async def test_delete_category_with_achievements_fails(
        self, achievement_service, repository
    ):
        """測試刪除有成就的分類時失敗."""
        # Arrange
        category = await create_test_category(repository, "delete_test")
        await create_test_achievement(repository, category.id, "test_achievement")

        # Act & Assert
        with pytest.raises(ValueError, match="下還有.*個成就,無法刪除"):
            await achievement_service.delete_category(category.id)

    # ==========================================================================
    # 成就 CRUD 操作測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_create_achievement_success(self, achievement_service, repository):
        """測試成功建立成就."""
        # Arrange
        category = await create_test_category(repository, "achievement_cat")
        achievement = Achievement(
            name="測試成就",
            description="這是一個測試成就",
            category_id=category.id,
            type=AchievementType.COUNTER,
            criteria={"target_value": 50, "counter_field": "messages"},
            points=100,
            role_reward="測試專家",
            is_hidden=False,
        )

        # Act
        created_achievement = await achievement_service.create_achievement(achievement)

        # Assert
        assert created_achievement.id is not None
        assert created_achievement.name == "測試成就"
        assert created_achievement.category_id == category.id
        assert created_achievement.points == 100
        assert created_achievement.role_reward == "測試專家"
        assert created_achievement.is_hidden is False

    @pytest.mark.asyncio
    async def test_create_achievement_invalid_category(self, achievement_service):
        """測試建立成就時分類不存在的錯誤."""
        # Arrange
        achievement = Achievement(
            name="無效成就",
            description="分類不存在的成就",
            category_id=999,  # 不存在的分類 ID
            type=AchievementType.COUNTER,
            criteria={"target_value": 50},
            points=100,
            role_reward=None,
            is_hidden=False,
        )

        # Act & Assert
        with pytest.raises(ValueError, match="分類 999 不存在"):
            await achievement_service.create_achievement(achievement)

    @pytest.mark.asyncio
    async def test_create_achievement_duplicate_name_in_category(
        self, achievement_service, repository
    ):
        """測試在同一分類中建立重複名稱成就的錯誤."""
        # Arrange
        category = await create_test_category(repository, "dup_cat")

        achievement1 = Achievement(
            name="重複成就",
            description="第一個成就",
            category_id=category.id,
            type=AchievementType.COUNTER,
            criteria={"target_value": 50},
            points=100,
            role_reward=None,
            is_hidden=False,
        )

        achievement2 = Achievement(
            name="重複成就",
            description="第二個成就",
            category_id=category.id,
            type=AchievementType.COUNTER,
            criteria={"target_value": 100},
            points=200,
            role_reward="重複專家",
            is_hidden=True,
        )

        await achievement_service.create_achievement(achievement1)

        # Act & Assert
        with pytest.raises(ValueError, match="分類內成就名稱 '重複成就' 已存在"):
            await achievement_service.create_achievement(achievement2)

    @pytest.mark.asyncio
    async def test_list_achievements_with_filters(
        self, achievement_service, repository
    ):
        """測試帶篩選條件的成就列表查詢."""
        # Arrange
        category1 = await create_test_category(repository, "cat1")
        category2 = await create_test_category(repository, "cat2")

        # 建立不同類型的成就
        await create_test_achievement(
            repository, category1.id, "counter1", AchievementType.COUNTER
        )
        await create_test_achievement(
            repository, category1.id, "milestone1", AchievementType.MILESTONE
        )
        await create_test_achievement(
            repository, category2.id, "counter2", AchievementType.COUNTER
        )

        # Act - 按分類篩選
        cat1_achievements = await achievement_service.list_achievements(
            category_id=category1.id
        )

        # Act - 按類型篩選
        counter_achievements = await achievement_service.list_achievements(
            achievement_type=AchievementType.COUNTER
        )

        # Assert
        assert len(cat1_achievements) == 2
        assert all(a.category_id == category1.id for a in cat1_achievements)

        assert len(counter_achievements) == 2
        assert all(a.type == AchievementType.COUNTER for a in counter_achievements)

    # ==========================================================================
    # 用戶成就操作測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_award_achievement_to_user_success(
        self, achievement_service, repository
    ):
        """測試成功為用戶頒發成就."""
        # Arrange
        category = await create_test_category(repository, "award_cat")
        achievement = await create_test_achievement(
            repository, category.id, "award_test"
        )
        user_id = 123456789

        # Act
        user_achievement = await achievement_service.award_achievement_to_user(
            user_id, achievement.id
        )

        # Assert
        assert user_achievement.user_id == user_id
        assert user_achievement.achievement_id == achievement.id
        assert user_achievement.earned_at is not None

    @pytest.mark.asyncio
    async def test_award_achievement_nonexistent_achievement(self, achievement_service):
        """測試頒發不存在的成就時失敗."""
        # Arrange
        user_id = 123456789
        nonexistent_achievement_id = 999

        # Act & Assert
        with pytest.raises(ValueError, match="成就 999 不存在"):
            await achievement_service.award_achievement_to_user(
                user_id, nonexistent_achievement_id
            )

    @pytest.mark.asyncio
    async def test_award_achievement_inactive_achievement(
        self, achievement_service, repository
    ):
        """測試頒發未啟用的成就時失敗."""
        # Arrange
        category = await create_test_category(repository, "inactive_cat")
        achievement = await create_test_achievement(
            repository, category.id, "inactive_test"
        )

        # 停用成就
        await achievement_service.update_achievement(
            achievement.id, {"is_active": False}
        )

        user_id = 123456789

        # Act & Assert
        with pytest.raises(ValueError, match=f"成就 {achievement.id} 未啟用"):
            await achievement_service.award_achievement_to_user(user_id, achievement.id)

    @pytest.mark.asyncio
    async def test_get_user_achievements(self, achievement_service, repository):
        """測試取得用戶成就列表."""
        # Arrange
        category = await create_test_category(repository, "user_cat")
        achievement1 = await create_test_achievement(
            repository, category.id, "user_ach1"
        )
        achievement2 = await create_test_achievement(
            repository, category.id, "user_ach2"
        )

        user_id = 123456789

        # 頒發成就
        await achievement_service.award_achievement_to_user(user_id, achievement1.id)
        await achievement_service.award_achievement_to_user(user_id, achievement2.id)

        # Act
        user_achievements = await achievement_service.get_user_achievements(user_id)

        # Assert
        assert len(user_achievements) == 2
        achievement_ids = [ua[1].id for ua in user_achievements]
        assert achievement1.id in achievement_ids
        assert achievement2.id in achievement_ids

    @pytest.mark.asyncio
    async def test_get_user_achievement_stats(self, achievement_service, repository):
        """測試取得用戶成就統計."""
        # Arrange
        category = await create_test_category(repository, "stats_cat")
        achievement = await create_test_achievement(
            repository, category.id, "stats_ach"
        )
        user_id = 123456789

        # 頒發成就
        await achievement_service.award_achievement_to_user(user_id, achievement.id)

        # Act
        stats = await achievement_service.get_user_achievement_stats(user_id)

        # Assert
        assert stats["total_achievements"] == 1
        assert stats["total_points"] == 100  # 預設 100 點數

    # ==========================================================================
    # 批量操作測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_batch_create_achievements_success(
        self, achievement_service, repository
    ):
        """測試批量建立成就成功."""
        # Arrange
        category = await create_test_category(repository, "batch_cat")

        achievements = [
            Achievement(
                name=f"批量成就 {i}",
                description=f"批量建立的成就 {i}",
                category_id=category.id,
                type=AchievementType.COUNTER,
                criteria={"target_value": i * 10},
                points=i * 50,
                role_reward=f"批量專家 {i}" if i % 2 == 0 else None,
                is_hidden=i == 3,
            )
            for i in range(1, 4)
        ]

        # Act
        created_achievements = await achievement_service.batch_create_achievements(
            achievements
        )

        # Assert
        assert len(created_achievements) == 3
        for i, achievement in enumerate(created_achievements, 1):
            assert achievement.name == f"批量成就 {i}"
            assert achievement.points == i * 50

    @pytest.mark.asyncio
    async def test_batch_create_achievements_partial_failure(
        self, achievement_service, repository
    ):
        """測試批量建立成就時部分失敗的情況."""
        # Arrange
        category = await create_test_category(repository, "partial_cat")

        # 建立一些成就,其中一個會因為重複名稱失敗
        achievements = [
            Achievement(
                name="批量成就 1",
                description="第一個成就",
                category_id=category.id,
                type=AchievementType.COUNTER,
                criteria={"target_value": 10},
                points=50,
                role_reward=None,
                is_hidden=False,
            ),
            Achievement(
                name="批量成就 1",  # 重複名稱
                description="重複名稱的成就",
                category_id=category.id,
                type=AchievementType.COUNTER,
                criteria={"target_value": 20},
                points=100,
                role_reward="重複專家",
                is_hidden=True,
            ),
            Achievement(
                name="批量成就 2",
                description="第二個成就",
                category_id=category.id,
                type=AchievementType.COUNTER,
                criteria={"target_value": 30},
                points=150,
                role_reward="批量大師",
                is_hidden=False,
            ),
        ]

        # Act
        created_achievements = await achievement_service.batch_create_achievements(
            achievements
        )

        # Assert - 應該建立了 2 個成就(第 1 個和第 3 個)
        assert len(created_achievements) == 2
        created_names = {a.name for a in created_achievements}
        assert "批量成就 1" in created_names
        assert "批量成就 2" in created_names

    # ==========================================================================
    # 統計和報表測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_get_global_achievement_stats(self, achievement_service, repository):
        """測試取得全域成就統計."""
        # Arrange
        category = await create_test_category(repository, "global_cat")
        achievement = await create_test_achievement(
            repository, category.id, "global_ach"
        )
        user_id = 123456789

        # 頒發成就
        await achievement_service.award_achievement_to_user(user_id, achievement.id)

        # Act
        stats = await achievement_service.get_global_achievement_stats()

        # Assert
        assert stats["total_achievements"] >= 1
        assert stats["active_achievements"] >= 1
        assert stats["total_user_achievements"] >= 1
        assert stats["unique_users"] >= 1

    @pytest.mark.asyncio
    async def test_get_popular_achievements(self, achievement_service, repository):
        """測試取得熱門成就列表."""
        # Arrange
        category = await create_test_category(repository, "popular_cat")
        achievement1 = await create_test_achievement(
            repository, category.id, "popular1"
        )
        achievement2 = await create_test_achievement(
            repository, category.id, "popular2"
        )

        # 讓第一個成就更受歡迎
        for user_id in [111, 222, 333]:
            await achievement_service.award_achievement_to_user(
                user_id, achievement1.id
            )

        await achievement_service.award_achievement_to_user(444, achievement2.id)

        # Act
        popular_achievements = await achievement_service.get_popular_achievements(
            limit=2
        )

        # Assert
        assert len(popular_achievements) == 2
        # 第一個應該是最受歡迎的
        assert popular_achievements[0][0].id == achievement1.id
        assert popular_achievements[0][1] == 3  # 3 個用戶獲得
        assert popular_achievements[1][0].id == achievement2.id
        assert popular_achievements[1][1] == 1  # 1 個用戶獲得

    # ==========================================================================
    # 錯誤處理和邊界情況測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_service_handles_repository_errors(self, mock_repository):
        """測試服務正確處理 Repository 錯誤."""
        # Arrange
        mock_repository.get_category_by_id.side_effect = Exception("資料庫連線失敗")
        service = AchievementService(mock_repository)

        # Act & Assert
        with pytest.raises(Exception, match="資料庫連線失敗"):
            await service.get_category_by_id(1)

    @pytest.mark.asyncio
    async def test_cache_error_fallback(self, achievement_service, repository):
        """測試快取錯誤時的降級處理."""
        # Arrange
        category = await create_test_category(repository, "cache_error_cat")

        # 模擬快取錯誤
        with patch.object(
            achievement_service._cache,
            "__contains__",
            side_effect=Exception("快取錯誤"),
        ):
            # Act - 即使快取出錯,應該仍能從資料庫取得資料
            result = await achievement_service.get_category_by_id(category.id)

            # Assert
            assert result is not None
            assert result.id == category.id
