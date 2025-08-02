"""成就系統資料模型單元測試.

測試成就系統所有 Pydantic 模型的驗證邏輯、序列化和反序列化功能。

測試涵蓋：
- 模型驗證規則
- 邊界條件測試
- 錯誤處理
- JSON 序列化/反序列化
- 特殊欄位驗證
"""

import json
from datetime import datetime

import pytest

from src.cogs.achievement.database.models import (
    Achievement,
    AchievementCategory,
    AchievementProgress,
    AchievementType,
    UserAchievement,
    create_sample_achievement,
    create_sample_achievement_category,
    create_sample_achievement_progress,
    create_sample_user_achievement,
)


class TestAchievementType:
    """測試 AchievementType 列舉."""

    def test_achievement_type_values(self):
        """測試成就類型的值."""
        assert AchievementType.COUNTER == "counter"
        assert AchievementType.MILESTONE == "milestone"
        assert AchievementType.TIME_BASED == "time_based"
        assert AchievementType.CONDITIONAL == "conditional"

    def test_achievement_type_from_string(self):
        """測試從字串建立成就類型."""
        assert AchievementType("counter") == AchievementType.COUNTER
        assert AchievementType("milestone") == AchievementType.MILESTONE

        # 測試無效值
        with pytest.raises(ValueError):
            AchievementType("invalid_type")


class TestAchievementCategory:
    """測試 AchievementCategory 模型."""

    def test_valid_category_creation(self):
        """測試有效的分類建立."""
        category = AchievementCategory(
            name="social",
            description="社交相關成就",
            display_order=1,
            icon_emoji="👥"
        )

        assert category.name == "social"
        assert category.description == "社交相關成就"
        assert category.display_order == 1
        assert category.icon_emoji == "👥"
        assert category.id is None
        assert category.created_at is None
        assert category.updated_at is None

    def test_category_name_validation(self):
        """測試分類名稱驗證."""
        # 有效名稱
        valid_names = ["social", "activity_meter", "special123"]
        for name in valid_names:
            category = AchievementCategory(name=name, description="test")
            assert category.name == name.lower()

    def test_category_required_fields(self):
        """測試必填欄位驗證."""
        # 缺少 name
        with pytest.raises(ValueError):
            AchievementCategory(description="test")

        # 缺少 description
        with pytest.raises(ValueError):
            AchievementCategory(name="test")

    def test_category_field_length_limits(self):
        """測試欄位長度限制."""
        # name 太長
        with pytest.raises(ValueError):
            AchievementCategory(
                name="a" * 51,  # 超過 50 字元限制
                description="test"
            )

        # description 太長
        with pytest.raises(ValueError):
            AchievementCategory(
                name="test",
                description="a" * 201  # 超過 200 字元限制
            )

    def test_category_display_order_validation(self):
        """測試顯示順序驗證."""
        # 有效的顯示順序
        category = AchievementCategory(name="test", description="test", display_order=5)
        assert category.display_order == 5

        # 負數顯示順序應該被拒絕
        with pytest.raises(ValueError):
            AchievementCategory(name="test", description="test", display_order=-1)

    def test_category_json_serialization(self):
        """測試 JSON 序列化."""
        category = AchievementCategory(
            id=1,
            name="social",
            description="社交成就",
            display_order=1,
            icon_emoji="👥",
            created_at=datetime(2024, 1, 1, 12, 0, 0),
            updated_at=datetime(2024, 1, 2, 12, 0, 0)
        )

        # 測試序列化
        json_data = category.model_dump_json()
        assert isinstance(json_data, str)

        # 測試反序列化
        parsed_data = json.loads(json_data)
        restored_category = AchievementCategory(**parsed_data)
        assert restored_category.name == category.name
        assert restored_category.description == category.description


class TestAchievement:
    """測試 Achievement 模型."""

    def test_valid_achievement_creation(self):
        """測試有效的成就建立."""
        achievement = Achievement(
            name="社交達人",
            description="與其他用戶互動超過 100 次",
            category_id=1,
            type=AchievementType.COUNTER,
            criteria={"target_value": 100, "counter_field": "interactions"},
            points=500,
            role_reward="社交專家",
            is_hidden=False
        )

        assert achievement.name == "社交達人"
        assert achievement.category_id == 1
        assert achievement.type == AchievementType.COUNTER
        assert achievement.criteria["target_value"] == 100
        assert achievement.points == 500
        assert achievement.role_reward == "社交專家"
        assert achievement.is_hidden is False
        assert achievement.is_active is True

    def test_achievement_criteria_validation(self):
        """測試成就條件驗證."""
        # 有效條件（Counter 類型需要 counter_field）
        valid_criteria = {"target_value": 100, "counter_field": "interactions"}
        achievement = Achievement(
            name="test",
            description="test",
            category_id=1,
            type=AchievementType.COUNTER,
            criteria=valid_criteria
        )
        assert achievement.criteria == valid_criteria

        # 缺少 target_value
        with pytest.raises(ValueError, match="成就條件必須包含以下欄位"):
            Achievement(
                name="test",
                description="test",
                category_id=1,
                type=AchievementType.COUNTER,
                criteria={"other_field": 100}
            )

        # target_value 不是數值
        with pytest.raises(ValueError, match="target_value 必須是大於 0 的數值"):
            Achievement(
                name="test",
                description="test",
                category_id=1,
                type=AchievementType.COUNTER,
                criteria={"target_value": "not_a_number"}
            )

        # target_value 不是正數
        with pytest.raises(ValueError, match="target_value 必須是大於 0 的數值"):
            Achievement(
                name="test",
                description="test",
                category_id=1,
                type=AchievementType.COUNTER,
                criteria={"target_value": -10}
            )

    def test_achievement_type_specific_validation(self):
        """測試成就類型特定驗證."""
        base_data = {
            "name": "test",
            "description": "test",
            "category_id": 1,
            "criteria": {"target_value": 100}
        }

        # COUNTER 類型需要 counter_field
        with pytest.raises(ValueError, match="計數器型成就必須指定 counter_field"):
            Achievement(type=AchievementType.COUNTER, **base_data)

        # MILESTONE 類型需要 milestone_type
        with pytest.raises(ValueError, match="里程碑型成就必須指定 milestone_type"):
            Achievement(type=AchievementType.MILESTONE, **base_data)

        # TIME_BASED 類型需要 time_unit
        with pytest.raises(ValueError, match="時間型成就必須指定 time_unit"):
            Achievement(type=AchievementType.TIME_BASED, **base_data)

        # CONDITIONAL 類型需要 conditions
        with pytest.raises(ValueError, match="條件型成就必須指定 conditions 陣列"):
            Achievement(type=AchievementType.CONDITIONAL, **base_data)

    def test_achievement_badge_url_validation(self):
        """測試徽章 URL 驗證."""
        base_data = {
            "name": "test",
            "description": "test",
            "category_id": 1,
            "type": AchievementType.COUNTER,
            "criteria": {"target_value": 100, "counter_field": "test"}
        }

        # 有效的 URL
        valid_urls = [
            "https://example.com/badge.png",
            "http://example.com/badge.png"
        ]
        for url in valid_urls:
            achievement = Achievement(badge_url=url, **base_data)
            assert achievement.badge_url == url

        # 無效的 URL
        with pytest.raises(ValueError, match="徽章 URL 必須以 http:// 或 https:// 開頭"):
            Achievement(badge_url="ftp://example.com/badge.png", **base_data)

    def test_achievement_points_validation(self):
        """測試點數驗證."""
        base_data = {
            "name": "test",
            "description": "test",
            "category_id": 1,
            "type": AchievementType.COUNTER,
            "criteria": {"target_value": 100, "counter_field": "test"}
        }

        # 有效點數
        achievement = Achievement(points=500, **base_data)
        assert achievement.points == 500

        # 負點數
        with pytest.raises(ValueError):
            Achievement(points=-10, **base_data)

        # 過大點數
        with pytest.raises(ValueError):
            Achievement(points=20000, **base_data)

    def test_achievement_criteria_json_methods(self):
        """測試條件 JSON 方法."""
        criteria = {"target_value": 100, "counter_field": "interactions"}
        achievement = Achievement(
            name="test",
            description="test",
            category_id=1,
            type=AchievementType.COUNTER,
            criteria=criteria
        )

        # 測試 JSON 序列化
        json_str = achievement.get_criteria_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed == criteria

        # 測試從 JSON 建立
        restored = Achievement.from_criteria_json(
            json_str,
            name="test",
            description="test",
            category_id=1,
            type=AchievementType.COUNTER
        )
        assert restored.criteria == criteria

    def test_achievement_role_reward_validation(self):
        """測試身分組獎勵欄位驗證."""
        base_data = {
            "name": "test",
            "description": "test",
            "category_id": 1,
            "type": AchievementType.COUNTER,
            "criteria": {"target_value": 100, "counter_field": "test"}
        }

        # 有效的身分組獎勵
        achievement = Achievement(role_reward="VIP會員", **base_data)
        assert achievement.role_reward == "VIP會員"

        # 空值應該被接受
        achievement = Achievement(role_reward=None, **base_data)
        assert achievement.role_reward is None

        # 預設值應該是 None
        achievement = Achievement(**base_data)
        assert achievement.role_reward is None

    def test_achievement_is_hidden_validation(self):
        """測試隱藏成就欄位驗證."""
        base_data = {
            "name": "test",
            "description": "test",
            "category_id": 1,
            "type": AchievementType.COUNTER,
            "criteria": {"target_value": 100, "counter_field": "test"}
        }

        # 明確設定為隱藏
        achievement = Achievement(is_hidden=True, **base_data)
        assert achievement.is_hidden is True

        # 明確設定為不隱藏
        achievement = Achievement(is_hidden=False, **base_data)
        assert achievement.is_hidden is False

        # 預設值應該是 False
        achievement = Achievement(**base_data)
        assert achievement.is_hidden is False

    def test_achievement_with_all_new_fields(self):
        """測試包含所有新欄位的成就建立."""
        achievement = Achievement(
            name="神秘成就",
            description="完成特殊任務的隱藏成就",
            category_id=1,
            type=AchievementType.CONDITIONAL,
            criteria={
                "target_value": 1,
                "conditions": [
                    {"type": "special_event", "value": "completed"}
                ]
            },
            points=1000,
            role_reward="神秘探索者",
            is_hidden=True,
            badge_url="https://example.com/mystery_badge.png"
        )

        assert achievement.name == "神秘成就"
        assert achievement.role_reward == "神秘探索者"
        assert achievement.is_hidden is True
        assert achievement.points == 1000
        assert achievement.badge_url == "https://example.com/mystery_badge.png"


class TestUserAchievement:
    """測試 UserAchievement 模型."""

    def test_valid_user_achievement_creation(self):
        """測試有效的用戶成就建立."""
        user_achievement = UserAchievement(
            user_id=123456789,
            achievement_id=1,
            earned_at=datetime.now(),
            notified=True
        )

        assert user_achievement.user_id == 123456789
        assert user_achievement.achievement_id == 1
        assert user_achievement.notified is True

    def test_user_achievement_id_validation(self):
        """測試 ID 驗證."""
        # 有效 ID
        user_achievement = UserAchievement(user_id=123, achievement_id=456)
        assert user_achievement.user_id == 123
        assert user_achievement.achievement_id == 456

        # 無效 user_id
        with pytest.raises(ValueError, match="Input should be greater than 0"):
            UserAchievement(user_id=-1, achievement_id=1)

        # 無效 achievement_id
        with pytest.raises(ValueError, match="Input should be greater than 0"):
            UserAchievement(user_id=1, achievement_id=0)

    def test_user_achievement_defaults(self):
        """測試預設值."""
        user_achievement = UserAchievement(user_id=123, achievement_id=456)
        assert user_achievement.notified is False
        assert user_achievement.earned_at is None


class TestAchievementProgress:
    """測試 AchievementProgress 模型."""

    def test_valid_progress_creation(self):
        """測試有效的進度建立."""
        progress = AchievementProgress(
            user_id=123456789,
            achievement_id=1,
            current_value=75.0,
            target_value=100.0,
            progress_data={"streak": 5}
        )

        assert progress.user_id == 123456789
        assert progress.current_value == 75.0
        assert progress.target_value == 100.0
        assert progress.progress_data["streak"] == 5

    def test_progress_id_validation(self):
        """測試 ID 驗證."""
        # 無效 user_id
        with pytest.raises(ValueError, match="Input should be greater than 0"):
            AchievementProgress(user_id=-1, achievement_id=1, target_value=100)

        # 無效 achievement_id
        with pytest.raises(ValueError, match="Input should be greater than 0"):
            AchievementProgress(user_id=1, achievement_id=0, target_value=100)

    def test_progress_value_validation(self):
        """測試進度值驗證."""
        # 負的當前值
        with pytest.raises(ValueError, match="Input should be greater than or equal to 0"):
            AchievementProgress(
                user_id=1,
                achievement_id=1,
                current_value=-10,
                target_value=100
            )

        # 負的目標值
        with pytest.raises(ValueError, match="Input should be greater than 0"):
            AchievementProgress(
                user_id=1,
                achievement_id=1,
                current_value=50,
                target_value=-100
            )

    def test_progress_percentage_calculation(self):
        """測試進度百分比計算."""
        # 正常情況
        progress = AchievementProgress(
            user_id=1,
            achievement_id=1,
            current_value=75.0,
            target_value=100.0
        )
        assert progress.progress_percentage == 75.0

        # 完成情況
        progress.current_value = 100.0
        assert progress.progress_percentage == 100.0

        # 超過目標
        progress.current_value = 150.0
        assert progress.progress_percentage == 100.0  # 最大限制在 100%

        # 目標為 0
        progress.target_value = 0
        assert progress.progress_percentage == 100.0

    def test_progress_completion_check(self):
        """測試完成狀態檢查."""
        progress = AchievementProgress(
            user_id=1,
            achievement_id=1,
            current_value=75.0,
            target_value=100.0
        )

        # 未完成
        assert progress.is_completed is False

        # 完成
        progress.current_value = 100.0
        assert progress.is_completed is True

        # 超過完成
        progress.current_value = 150.0
        assert progress.is_completed is True

    def test_progress_data_json_methods(self):
        """測試進度資料 JSON 方法."""
        progress_data = {"daily_count": [5, 8, 12], "streak": 3}
        progress = AchievementProgress(
            user_id=1,
            achievement_id=1,
            target_value=100.0,
            progress_data=progress_data
        )

        # 測試 JSON 序列化
        json_str = progress.get_progress_data_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed == progress_data

        # 測試空資料
        progress.progress_data = None
        assert progress.get_progress_data_json() == "{}"

        # 測試從 JSON 建立
        restored = AchievementProgress.from_progress_data_json(
            json_str,
            user_id=1,
            achievement_id=1,
            target_value=100.0
        )
        assert restored.progress_data == progress_data


class TestSampleFactoryFunctions:
    """測試範例工廠函數."""

    def test_create_sample_achievement_category(self):
        """測試建立範例成就分類."""
        category = create_sample_achievement_category()

        assert isinstance(category, AchievementCategory)
        assert category.name == "social"
        assert category.description == "社交互動相關成就"
        assert category.display_order == 1
        assert category.icon_emoji == "👥"

    def test_create_sample_achievement(self):
        """測試建立範例成就."""
        achievement = create_sample_achievement()

        assert isinstance(achievement, Achievement)
        assert achievement.name == "社交達人"
        assert achievement.type == AchievementType.COUNTER
        assert achievement.category_id == 1
        assert achievement.criteria["target_value"] == 100
        assert achievement.points == 500
        assert achievement.role_reward == "社交專家"
        assert achievement.is_hidden is False

    def test_create_sample_user_achievement(self):
        """測試建立範例用戶成就."""
        user_achievement = create_sample_user_achievement(user_id=999)

        assert isinstance(user_achievement, UserAchievement)
        assert user_achievement.user_id == 999
        assert user_achievement.achievement_id == 1
        assert user_achievement.notified is False

    def test_create_sample_achievement_progress(self):
        """測試建立範例成就進度."""
        progress = create_sample_achievement_progress(user_id=888)

        assert isinstance(progress, AchievementProgress)
        assert progress.user_id == 888
        assert progress.achievement_id == 1
        assert progress.current_value == 75.0
        assert progress.target_value == 100.0
        assert "daily_interactions" in progress.progress_data


class TestModelIntegration:
    """測試模型整合功能."""

    def test_model_from_attributes(self):
        """測試從資料庫結果建立模型."""
        # 模擬資料庫行資料
        db_row = {
            "id": 1,
            "name": "social",
            "description": "社交成就",
            "display_order": 1,
            "icon_emoji": "👥",
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }

        category = AchievementCategory(**db_row)
        assert category.id == 1
        assert category.name == "social"

    def test_model_json_compatibility(self):
        """測試模型 JSON 相容性."""
        achievement = Achievement(
            name="測試成就",
            description="這是測試",
            category_id=1,
            type=AchievementType.COUNTER,
            criteria={"target_value": 100, "counter_field": "test"},
            points=100
        )

        # 序列化為 JSON
        json_data = achievement.model_dump_json()
        assert '"type":"counter"' in json_data

        # 從 JSON 反序列化
        data = json.loads(json_data)
        restored = Achievement(**data)
        assert restored.name == achievement.name
        assert restored.type == achievement.type


# 測試運行標記
pytestmark = pytest.mark.unit
