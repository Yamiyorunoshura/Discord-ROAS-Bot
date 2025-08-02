"""成就系統 Repository 單元測試.

測試 AchievementRepository 的所有資料存取功能，包括：
- CRUD 操作
- 複雜查詢
- 成就進度管理
- 統計功能
- 錯誤處理

使用記憶體內 SQLite 進行快速測試執行。
"""


import pytest
import pytest_asyncio

from src.cogs.achievement.database import (
    Achievement,
    AchievementCategory,
    AchievementProgress,
    AchievementRepository,
    AchievementType,
    UserAchievement,
    initialize_achievement_database,
)
from src.core.config import Settings
from src.core.database import DatabasePool


@pytest_asyncio.fixture
async def test_settings():
    """測試用設定."""
    settings = Settings()
    # 使用記憶體內資料庫進行測試
    settings.database.sqlite_path = ":memory:"
    return settings


@pytest_asyncio.fixture
async def test_pool(test_settings):
    """測試用資料庫連線池."""
    # 使用臨時檔案而非記憶體資料庫，因為需要 Path 物件
    import tempfile
    from pathlib import Path
    temp_file = Path(tempfile.mktemp(suffix='.db'))

    pool = DatabasePool(temp_file, test_settings)
    await pool.initialize()

    # 初始化成就資料庫結構
    await initialize_achievement_database(pool)

    yield pool

    # 清理
    await pool.close_all()

    # 清理臨時檔案
    if temp_file.exists():
        temp_file.unlink()


@pytest_asyncio.fixture
async def repository(test_pool):
    """測試用 Repository."""
    return AchievementRepository(test_pool)


@pytest_asyncio.fixture
async def sample_category(repository):
    """建立範例分類."""
    category = AchievementCategory(
        name="test_social",
        description="測試社交分類",
        display_order=1,
        icon_emoji="👥"
    )
    return await repository.create_category(category)


@pytest_asyncio.fixture
async def sample_achievement(repository, sample_category):
    """建立範例成就."""
    achievement = Achievement(
        name="測試成就",
        description="這是一個測試成就",
        category_id=sample_category.id,
        type=AchievementType.COUNTER,
        criteria={"target_value": 100, "counter_field": "interactions"},
        points=500,
        role_reward=None,
        is_hidden=False
    )
    return await repository.create_achievement(achievement)


class TestAchievementCategoryOperations:
    """測試成就分類操作."""

    @pytest.mark.asyncio
    async def test_create_category(self, repository):
        """測試建立分類."""
        category = AchievementCategory(
            name="test_social",  # 使用不同的名稱避免與預設分類衝突
            description="社交成就分類",
            display_order=10,  # 使用不同的順序避免衝突
            icon_emoji="👥"
        )

        created = await repository.create_category(category)

        assert created.id is not None
        assert created.name == "test_social"
        assert created.description == "社交成就分類"
        assert created.display_order == 10
        assert created.icon_emoji == "👥"
        assert created.created_at is not None

    @pytest.mark.asyncio
    async def test_get_category_by_id(self, repository, sample_category):
        """測試根據 ID 取得分類."""
        found = await repository.get_category_by_id(sample_category.id)

        assert found is not None
        assert found.id == sample_category.id
        assert found.name == sample_category.name

    @pytest.mark.asyncio
    async def test_get_category_by_id_not_found(self, repository):
        """測試取得不存在的分類."""
        found = await repository.get_category_by_id(99999)
        assert found is None

    @pytest.mark.asyncio
    async def test_get_category_by_name(self, repository, sample_category):
        """測試根據名稱取得分類."""
        found = await repository.get_category_by_name(sample_category.name)

        assert found is not None
        assert found.name == sample_category.name

    @pytest.mark.asyncio
    async def test_list_categories(self, repository):
        """測試列出所有分類."""
        # 建立多個分類（使用不與預設資料衝突的名稱）
        categories_data = [
            ("test_social", "社交", 10, "👥"),
            ("test_activity", "活躍", 11, "⚡"),
            ("test_special", "特殊", 12, "🌟")
        ]

        for name, desc, order, emoji in categories_data:
            category = AchievementCategory(
                name=name,
                description=desc,
                display_order=order,
                icon_emoji=emoji
            )
            await repository.create_category(category)

        # 取得列表
        categories = await repository.list_categories()

        # 驗證結果（包含預設的 4 個分類 + 新建的 3 個）
        assert len(categories) >= 3

        # 驗證排序（按 display_order）
        orders = [cat.display_order for cat in categories]
        assert orders == sorted(orders)

    @pytest.mark.asyncio
    async def test_update_category(self, repository, sample_category):
        """測試更新分類."""
        updates = {
            "description": "更新後的描述",
            "display_order": 99
        }

        success = await repository.update_category(sample_category.id, updates)
        assert success is True

        # 驗證更新
        updated = await repository.get_category_by_id(sample_category.id)
        assert updated.description == "更新後的描述"
        assert updated.display_order == 99

    @pytest.mark.asyncio
    async def test_delete_category(self, repository, sample_category):
        """測試刪除分類."""
        success = await repository.delete_category(sample_category.id)
        assert success is True

        # 驗證刪除
        found = await repository.get_category_by_id(sample_category.id)
        assert found is None


class TestAchievementOperations:
    """測試成就操作."""

    @pytest.mark.asyncio
    async def test_create_achievement(self, repository, sample_category):
        """測試建立成就."""
        achievement = Achievement(
            name="社交達人",
            description="與其他用戶互動超過 100 次",
            category_id=sample_category.id,
            type=AchievementType.COUNTER,
            criteria={"target_value": 100, "counter_field": "interactions"},
            points=500,
            badge_url="https://example.com/badge.png",
            role_reward=None,
            is_hidden=False
        )

        created = await repository.create_achievement(achievement)

        assert created.id is not None
        assert created.name == "社交達人"
        assert created.category_id == sample_category.id
        assert created.type == AchievementType.COUNTER
        assert created.criteria["target_value"] == 100
        assert created.points == 500
        assert created.is_active is True

    @pytest.mark.asyncio
    async def test_get_achievement_by_id(self, repository, sample_achievement):
        """測試根據 ID 取得成就."""
        found = await repository.get_achievement_by_id(sample_achievement.id)

        assert found is not None
        assert found.id == sample_achievement.id
        assert found.name == sample_achievement.name
        assert isinstance(found.type, AchievementType)
        assert isinstance(found.criteria, dict)

    @pytest.mark.asyncio
    async def test_list_achievements_basic(self, repository, sample_achievement):
        """測試基本成就列表查詢."""
        achievements = await repository.list_achievements()

        assert len(achievements) >= 1
        assert any(a.id == sample_achievement.id for a in achievements)

    @pytest.mark.asyncio
    async def test_list_achievements_with_filters(self, repository, sample_category):
        """測試帶篩選條件的成就列表查詢."""
        # 建立不同類型的成就
        achievements_data = [
            ("計數器成就", AchievementType.COUNTER, {"target_value": 100, "counter_field": "test"}),
            ("里程碑成就", AchievementType.MILESTONE, {"target_value": 50, "milestone_type": "level"}),
            ("時間成就", AchievementType.TIME_BASED, {"target_value": 7, "time_unit": "days"}),
        ]

        created_achievements = []
        for name, achv_type, criteria in achievements_data:
            achievement = Achievement(
                name=name,
                description=f"測試{name}",
                category_id=sample_category.id,
                type=achv_type,
                criteria=criteria,
                points=100,
                role_reward=None,
                is_hidden=False
            )
            created = await repository.create_achievement(achievement)
            created_achievements.append(created)

        # 按分類篩選
        category_achievements = await repository.list_achievements(category_id=sample_category.id)
        assert len(category_achievements) >= 3
        assert all(a.category_id == sample_category.id for a in category_achievements)

        # 按類型篩選
        counter_achievements = await repository.list_achievements(
            achievement_type=AchievementType.COUNTER
        )
        assert len(counter_achievements) >= 1
        assert all(a.type == AchievementType.COUNTER for a in counter_achievements)

        # 測試分頁
        limited_achievements = await repository.list_achievements(limit=2, offset=0)
        assert len(limited_achievements) <= 2

    @pytest.mark.asyncio
    async def test_update_achievement(self, repository, sample_achievement):
        """測試更新成就."""
        updates = {
            "name": "更新後的成就名稱",
            "points": 1000,
            "is_active": False
        }

        success = await repository.update_achievement(sample_achievement.id, updates)
        assert success is True

        # 驗證更新
        updated = await repository.get_achievement_by_id(sample_achievement.id)
        assert updated.name == "更新後的成就名稱"
        assert updated.points == 1000
        assert updated.is_active is False

    @pytest.mark.asyncio
    async def test_delete_achievement(self, repository, sample_achievement):
        """測試刪除成就."""
        success = await repository.delete_achievement(sample_achievement.id)
        assert success is True

        # 驗證刪除
        found = await repository.get_achievement_by_id(sample_achievement.id)
        assert found is None


class TestUserAchievementOperations:
    """測試用戶成就操作."""

    @pytest.mark.asyncio
    async def test_award_achievement(self, repository, sample_achievement):
        """測試頒發成就."""
        user_id = 123456789

        user_achievement = await repository.award_achievement(user_id, sample_achievement.id)

        assert user_achievement.id is not None
        assert user_achievement.user_id == user_id
        assert user_achievement.achievement_id == sample_achievement.id
        assert user_achievement.earned_at is not None
        assert user_achievement.notified is False

    @pytest.mark.asyncio
    async def test_award_achievement_duplicate(self, repository, sample_achievement):
        """測試重複頒發成就（應該失敗）."""
        user_id = 123456789

        # 第一次頒發
        await repository.award_achievement(user_id, sample_achievement.id)

        # 第二次頒發應該失敗
        with pytest.raises(ValueError, match="已經獲得成就"):
            await repository.award_achievement(user_id, sample_achievement.id)

    @pytest.mark.asyncio
    async def test_has_user_achievement(self, repository, sample_achievement):
        """測試檢查用戶是否已獲得成就."""
        user_id = 123456789

        # 初始狀態
        assert await repository.has_user_achievement(user_id, sample_achievement.id) is False

        # 頒發成就後
        await repository.award_achievement(user_id, sample_achievement.id)
        assert await repository.has_user_achievement(user_id, sample_achievement.id) is True

    @pytest.mark.asyncio
    async def test_get_user_achievements(self, repository, sample_category):
        """測試取得用戶成就列表."""
        user_id = 123456789

        # 建立多個成就
        achievements = []
        for i in range(3):
            achievement = Achievement(
                name=f"成就 {i+1}",
                description=f"測試成就 {i+1}",
                category_id=sample_category.id,
                type=AchievementType.COUNTER,
                criteria={"target_value": (i+1) * 10, "counter_field": "test"},
                points=(i+1) * 100
            )
            created = await repository.create_achievement(achievement)
            achievements.append(created)

            # 頒發成就給用戶
            await repository.award_achievement(user_id, created.id)

        # 取得用戶成就列表
        user_achievements = await repository.get_user_achievements(user_id)

        assert len(user_achievements) == 3

        for user_achievement, achievement in user_achievements:
            assert isinstance(user_achievement, UserAchievement)
            assert isinstance(achievement, Achievement)
            assert user_achievement.user_id == user_id
            assert achievement.id == user_achievement.achievement_id

    @pytest.mark.asyncio
    async def test_mark_achievement_notified(self, repository, sample_achievement):
        """測試標記成就通知已發送."""
        user_id = 123456789

        # 頒發成就
        user_achievement = await repository.award_achievement(user_id, sample_achievement.id)

        # 標記為已通知 - 使用 user_id 和 achievement_id
        success = await repository.mark_achievement_notified(user_id, sample_achievement.id)
        assert success is True

        # 驗證狀態
        user_achievements = await repository.get_user_achievements(user_id)
        user_achievement_record, _ = user_achievements[0]
        assert user_achievement_record.notified is True

    @pytest.mark.asyncio
    async def test_get_user_achievement_stats(self, repository, sample_category):
        """測試取得用戶成就統計."""
        user_id = 123456789

        # 建立並頒發多個成就
        total_points = 0
        for i in range(3):
            points = (i + 1) * 100
            total_points += points

            achievement = Achievement(
                name=f"成就 {i+1}",
                description=f"測試成就 {i+1}",
                category_id=sample_category.id,
                type=AchievementType.COUNTER,
                criteria={"target_value": 10, "counter_field": "test"},
                points=points
            )
            created = await repository.create_achievement(achievement)
            await repository.award_achievement(user_id, created.id)

        # 取得統計
        stats = await repository.get_user_achievement_stats(user_id)

        assert stats["total_achievements"] == 3
        assert stats["total_points"] == total_points
        assert isinstance(stats["categories"], dict)


class TestAchievementProgressOperations:
    """測試成就進度操作."""

    @pytest.mark.asyncio
    async def test_update_progress_new_record(self, repository, sample_achievement):
        """測試更新進度（建立新記錄）."""
        user_id = 123456789
        current_value = 50.0
        progress_data = {"daily_count": [5, 10, 15]}

        progress = await repository.update_progress(
            user_id,
            sample_achievement.id,
            current_value,
            progress_data
        )

        assert progress.user_id == user_id
        assert progress.achievement_id == sample_achievement.id
        assert progress.current_value == current_value
        assert progress.target_value == 100.0  # 從成就條件取得
        assert progress.progress_data == progress_data

    @pytest.mark.asyncio
    async def test_update_progress_existing_record(self, repository, sample_achievement):
        """測試更新進度（更新現有記錄）."""
        user_id = 123456789

        # 第一次更新
        await repository.update_progress(user_id, sample_achievement.id, 50.0)

        # 第二次更新
        new_progress_data = {"streak": 5}
        progress = await repository.update_progress(
            user_id,
            sample_achievement.id,
            75.0,
            new_progress_data
        )

        assert progress.current_value == 75.0
        assert progress.progress_data == new_progress_data

    @pytest.mark.asyncio
    async def test_update_progress_auto_award_achievement(self, repository, sample_achievement):
        """測試進度達到目標時自動頒發成就."""
        user_id = 123456789

        # 更新進度到目標值
        await repository.update_progress(user_id, sample_achievement.id, 100.0)

        # 檢查是否自動獲得成就
        has_achievement = await repository.has_user_achievement(user_id, sample_achievement.id)
        assert has_achievement is True

    @pytest.mark.asyncio
    async def test_get_user_progress(self, repository, sample_achievement):
        """測試取得用戶進度."""
        user_id = 123456789

        # 建立進度記錄
        await repository.update_progress(user_id, sample_achievement.id, 60.0)

        # 取得進度
        progress = await repository.get_user_progress(user_id, sample_achievement.id)

        assert progress is not None
        assert progress.current_value == 60.0
        assert progress.progress_percentage == 60.0
        assert progress.is_completed is False

    @pytest.mark.asyncio
    async def test_get_user_progresses(self, repository, sample_category):
        """測試取得用戶所有進度."""
        user_id = 123456789

        # 建立多個成就和進度
        for i in range(3):
            achievement = Achievement(
                name=f"進度成就 {i+1}",
                description=f"測試進度成就 {i+1}",
                category_id=sample_category.id,
                type=AchievementType.COUNTER,
                criteria={"target_value": 100, "counter_field": "test"},
                points=100
            )
            created = await repository.create_achievement(achievement)
            await repository.update_progress(user_id, created.id, (i + 1) * 20.0)

        # 取得所有進度
        progresses = await repository.get_user_progresses(user_id)

        assert len(progresses) == 3
        for progress in progresses:
            assert isinstance(progress, AchievementProgress)
            assert progress.user_id == user_id

    @pytest.mark.asyncio
    async def test_delete_user_progress(self, repository, sample_achievement):
        """測試刪除用戶進度."""
        user_id = 123456789

        # 建立進度記錄
        await repository.update_progress(user_id, sample_achievement.id, 30.0)

        # 刪除進度
        success = await repository.delete_user_progress(user_id, sample_achievement.id)
        assert success is True

        # 驗證刪除
        progress = await repository.get_user_progress(user_id, sample_achievement.id)
        assert progress is None


class TestStatisticsAndReports:
    """測試統計和報表功能."""

    @pytest.mark.asyncio
    async def test_get_global_achievement_stats(self, repository, sample_category):
        """測試取得全域成就統計."""
        # 建立一些測試資料
        user_ids = [111, 222, 333]

        for i in range(3):
            achievement = Achievement(
                name=f"統計成就 {i+1}",
                description=f"統計測試成就 {i+1}",
                category_id=sample_category.id,
                type=AchievementType.COUNTER,
                criteria={"target_value": 100, "counter_field": "test"},
                points=100,
                is_active=(i < 2)  # 前兩個啟用，第三個不啟用
            )
            created = await repository.create_achievement(achievement)

            # 為不同用戶頒發成就
            for user_id in user_ids[:i+1]:  # 遞增的獲得人數
                await repository.award_achievement(user_id, created.id)

        # 取得統計
        stats = await repository.get_global_achievement_stats()

        assert stats["total_achievements"] >= 3
        assert stats["active_achievements"] >= 2
        assert stats["total_user_achievements"] >= 6  # 1+2+3
        assert stats["unique_users"] >= 3

    @pytest.mark.asyncio
    async def test_get_popular_achievements(self, repository, sample_category):
        """測試取得最受歡迎的成就."""
        # 建立成就並模擬不同的獲得人數
        achievements_data = [
            ("熱門成就 1", 5),  # 5 個用戶獲得
            ("熱門成就 2", 3),  # 3 個用戶獲得
            ("熱門成就 3", 8),  # 8 個用戶獲得
        ]

        created_achievements = []
        for name, user_count in achievements_data:
            achievement = Achievement(
                name=name,
                description=f"測試{name}",
                category_id=sample_category.id,
                type=AchievementType.COUNTER,
                criteria={"target_value": 100, "counter_field": "test"},
                points=100
            )
            created = await repository.create_achievement(achievement)
            created_achievements.append(created)

            # 為指定數量的用戶頒發成就
            for user_id in range(1000, 1000 + user_count):
                await repository.award_achievement(user_id, created.id)

        # 取得熱門成就
        popular = await repository.get_popular_achievements(limit=5)

        assert len(popular) >= 3

        # 驗證排序（按獲得人數降序）
        earned_counts = [count for _, count in popular]
        assert earned_counts == sorted(earned_counts, reverse=True)

        # 驗證最受歡迎的成就
        top_achievement, top_count = popular[0]
        assert top_achievement.name == "熱門成就 3"
        assert top_count == 8


class TestErrorHandling:
    """測試錯誤處理."""

    @pytest.mark.asyncio
    async def test_update_progress_nonexistent_achievement(self, repository):
        """測試更新不存在成就的進度."""
        user_id = 123456789
        nonexistent_achievement_id = 99999

        with pytest.raises(ValueError, match="成就 .* 不存在"):
            await repository.update_progress(user_id, nonexistent_achievement_id, 50.0)

    @pytest.mark.asyncio
    async def test_award_nonexistent_achievement(self, repository):
        """測試頒發不存在的成就."""
        user_id = 123456789
        nonexistent_achievement_id = 99999

        # 這個測試需要檢查資料庫外鍵約束
        # 由於使用 SQLite，外鍵約束會阻止插入無效的 achievement_id
        with pytest.raises(Exception):  # 可能是 DatabaseError 或其他資料庫相關錯誤
            await repository.award_achievement(user_id, nonexistent_achievement_id)

    @pytest.mark.asyncio
    async def test_update_category_nonexistent(self, repository):
        """測試更新不存在的分類."""
        nonexistent_category_id = 99999
        updates = {"name": "不存在的分類"}

        success = await repository.update_category(nonexistent_category_id, updates)
        assert success is False  # 沒有記錄被更新

    @pytest.mark.asyncio
    async def test_delete_nonexistent_records(self, repository):
        """測試刪除不存在的記錄."""
        # 刪除不存在的分類
        success = await repository.delete_category(99999)
        assert success is False

        # 刪除不存在的成就
        success = await repository.delete_achievement(99999)
        assert success is False

        # 刪除不存在的進度
        success = await repository.delete_user_progress(99999, 99999)
        assert success is False


# 測試運行標記
pytestmark = pytest.mark.asyncio
