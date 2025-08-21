"""
成就系統資料模型測試
Task ID: 6 - 成就系統核心功能

測試 services/achievement/models.py 中的所有資料模型
包含模型建立、驗證、序列化和資料轉換的測試

測試覆蓋：
- Achievement 成就模型
- AchievementProgress 進度模型
- AchievementReward 獎勵模型
- TriggerCondition 觸發條件模型
- 所有枚舉類型
- 資料驗證邏輯
- JSON序列化/反序列化
"""

import pytest
import json
from datetime import datetime
from typing import Dict, Any

from services.achievement.models import (
    Achievement, AchievementProgress, AchievementReward, TriggerCondition,
    AchievementType, TriggerType, RewardType, AchievementStatus,
    validate_achievement_id, validate_user_id, validate_guild_id
)
from core.exceptions import ValidationError


class TestEnumerations:
    """測試枚舉類型"""
    
    def test_achievement_type_enum(self):
        """測試成就類型枚舉"""
        assert AchievementType.MILESTONE.value == "milestone"
        assert AchievementType.RECURRING.value == "recurring"
        assert AchievementType.HIDDEN.value == "hidden"
        assert AchievementType.PROGRESSIVE.value == "progressive"
    
    def test_trigger_type_enum(self):
        """測試觸發類型枚舉"""
        assert TriggerType.MESSAGE_COUNT.value == "message_count"
        assert TriggerType.VOICE_TIME.value == "voice_time"
        assert TriggerType.REACTION_COUNT.value == "reaction_count"
        assert TriggerType.CUSTOM_EVENT.value == "custom_event"
    
    def test_reward_type_enum(self):
        """測試獎勵類型枚舉"""
        assert RewardType.CURRENCY.value == "currency"
        assert RewardType.ROLE.value == "role"
        assert RewardType.BADGE.value == "badge"
        assert RewardType.CUSTOM.value == "custom"
    
    def test_achievement_status_enum(self):
        """測試成就狀態枚舉"""
        assert AchievementStatus.ACTIVE.value == "active"
        assert AchievementStatus.DISABLED.value == "disabled"
        assert AchievementStatus.ARCHIVED.value == "archived"


class TestValidationFunctions:
    """測試驗證函數"""
    
    def test_validate_achievement_id(self):
        """測試成就ID驗證"""
        # 有效ID
        assert validate_achievement_id("valid_achievement_123") == "valid_achievement_123"
        assert validate_achievement_id("ACHIEVEMENT_001") == "ACHIEVEMENT_001"
        
        # 無效ID
        with pytest.raises(ValidationError):
            validate_achievement_id("")  # 空字串
        
        with pytest.raises(ValidationError):
            validate_achievement_id("a")  # 太短
        
        with pytest.raises(ValidationError):
            validate_achievement_id("invalid id with spaces")  # 包含空格
        
        with pytest.raises(ValidationError):
            validate_achievement_id("invalid@id")  # 包含特殊字符
    
    def test_validate_user_id(self):
        """測試使用者ID驗證"""
        # 有效ID
        assert validate_user_id(123456789) == 123456789
        assert validate_user_id("987654321") == 987654321
        
        # 無效ID
        with pytest.raises(ValidationError):
            validate_user_id(0)  # 零值
        
        with pytest.raises(ValidationError):
            validate_user_id(-1)  # 負值
        
        with pytest.raises(ValidationError):
            validate_user_id("invalid")  # 非數字字串
    
    def test_validate_guild_id(self):
        """測試伺服器ID驗證"""
        # 有效ID
        assert validate_guild_id(123456789) == 123456789
        assert validate_guild_id("987654321") == 987654321
        
        # 無效ID
        with pytest.raises(ValidationError):
            validate_guild_id(0)
        
        with pytest.raises(ValidationError):
            validate_guild_id(-1)
        
        with pytest.raises(ValidationError):
            validate_guild_id("not_a_number")


class TestTriggerConditionModel:
    """測試觸發條件模型"""
    
    def test_trigger_condition_creation(self):
        """測試觸發條件建立"""
        condition = TriggerCondition(
            trigger_type=TriggerType.MESSAGE_COUNT,
            target_value=10,
            comparison_operator=">=",
            metadata={"channel_id": 123456789}
        )
        
        assert condition.trigger_type == TriggerType.MESSAGE_COUNT
        assert condition.target_value == 10
        assert condition.comparison_operator == ">="
        assert condition.metadata["channel_id"] == 123456789
    
    def test_trigger_condition_validation(self):
        """測試觸發條件驗證"""
        # 有效的比較運算符
        valid_operators = ["==", "!=", ">", "<", ">=", "<="]
        for op in valid_operators:
            condition = TriggerCondition(
                trigger_type=TriggerType.MESSAGE_COUNT,
                target_value=10,
                comparison_operator=op,
                metadata={}
            )
            condition.validate()  # 不應該拋出異常
        
        # 無效的比較運算符
        with pytest.raises(ValidationError):
            condition = TriggerCondition(
                trigger_type=TriggerType.MESSAGE_COUNT,
                target_value=10,
                comparison_operator="invalid",
                metadata={}
            )
            condition.validate()
    
    def test_trigger_condition_serialization(self):
        """測試觸發條件序列化"""
        condition = TriggerCondition(
            trigger_type=TriggerType.VOICE_TIME,
            target_value=300,
            comparison_operator=">=",
            metadata={"channel_type": "voice"}
        )
        
        # 轉換為字典
        data_dict = condition.to_dict()
        assert data_dict["trigger_type"] == "voice_time"
        assert data_dict["target_value"] == 300
        assert data_dict["comparison_operator"] == ">="
        assert data_dict["metadata"]["channel_type"] == "voice"
        
        # 從字典重建
        rebuilt_condition = TriggerCondition.from_dict(data_dict)
        assert rebuilt_condition.trigger_type == condition.trigger_type
        assert rebuilt_condition.target_value == condition.target_value
        assert rebuilt_condition.comparison_operator == condition.comparison_operator
        assert rebuilt_condition.metadata == condition.metadata


class TestAchievementRewardModel:
    """測試成就獎勵模型"""
    
    def test_reward_creation(self):
        """測試獎勵建立"""
        reward = AchievementReward(
            reward_type=RewardType.CURRENCY,
            value=50.0,
            metadata={"reason": "完成成就"}
        )
        
        assert reward.reward_type == RewardType.CURRENCY
        assert reward.value == 50.0
        assert reward.metadata["reason"] == "完成成就"
    
    def test_reward_validation(self):
        """測試獎勵驗證"""
        # 貨幣獎勵必須是數字
        reward = AchievementReward(
            reward_type=RewardType.CURRENCY,
            value=100.0,
            metadata={}
        )
        reward.validate()  # 不應該拋出異常
        
        # 身分組獎勵必須是字串
        reward = AchievementReward(
            reward_type=RewardType.ROLE,
            value="VIP會員",
            metadata={}
        )
        reward.validate()  # 不應該拋出異常
        
        # 無效的貨幣值
        with pytest.raises(ValidationError):
            reward = AchievementReward(
                reward_type=RewardType.CURRENCY,
                value=-10.0,  # 負數
                metadata={}
            )
            reward.validate()
    
    def test_reward_serialization(self):
        """測試獎勵序列化"""
        reward = AchievementReward(
            reward_type=RewardType.BADGE,
            value="活躍徽章",
            metadata={"badge_icon": "🏆", "rarity": "common"}
        )
        
        # 轉換為字典
        data_dict = reward.to_dict()
        assert data_dict["reward_type"] == "badge"
        assert data_dict["value"] == "活躍徽章"
        assert data_dict["metadata"]["badge_icon"] == "🏆"
        
        # 從字典重建
        rebuilt_reward = AchievementReward.from_dict(data_dict)
        assert rebuilt_reward.reward_type == reward.reward_type
        assert rebuilt_reward.value == reward.value
        assert rebuilt_reward.metadata == reward.metadata


class TestAchievementModel:
    """測試成就模型"""
    
    def test_achievement_creation(self):
        """測試成就建立"""
        trigger_conditions = [
            TriggerCondition(
                trigger_type=TriggerType.MESSAGE_COUNT,
                target_value=10,
                comparison_operator=">=",
                metadata={}
            )
        ]
        
        rewards = [
            AchievementReward(
                reward_type=RewardType.CURRENCY,
                value=25.0,
                metadata={}
            )
        ]
        
        achievement = Achievement(
            id="test_achievement_001",
            name="測試成就",
            description="這是一個測試成就",
            achievement_type=AchievementType.MILESTONE,
            guild_id=123456789,
            trigger_conditions=trigger_conditions,
            rewards=rewards,
            status=AchievementStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        assert achievement.id == "test_achievement_001"
        assert achievement.name == "測試成就"
        assert achievement.achievement_type == AchievementType.MILESTONE
        assert len(achievement.trigger_conditions) == 1
        assert len(achievement.rewards) == 1
    
    def test_achievement_validation(self):
        """測試成就驗證"""
        # 無效的成就ID
        with pytest.raises(ValidationError):
            Achievement(
                id="",  # 空ID
                name="測試成就",
                description="測試描述",
                achievement_type=AchievementType.MILESTONE,
                guild_id=123456789,
                trigger_conditions=[],
                rewards=[]
            )
        
        # 無效的伺服器ID
        with pytest.raises(ValidationError):
            Achievement(
                id="valid_achievement_001",
                name="測試成就",
                description="測試描述",
                achievement_type=AchievementType.MILESTONE,
                guild_id=0,  # 無效的伺服器ID
                trigger_conditions=[],
                rewards=[]
            )
        
        # 缺少觸發條件
        with pytest.raises(ValidationError):
            achievement = Achievement(
                id="valid_achievement_001",
                name="測試成就",
                description="測試描述",
                achievement_type=AchievementType.MILESTONE,
                guild_id=123456789,
                trigger_conditions=[],  # 空的觸發條件
                rewards=[]
            )
            achievement.validate()
    
    def test_achievement_serialization(self):
        """測試成就序列化"""
        trigger_condition = TriggerCondition(
            trigger_type=TriggerType.MESSAGE_COUNT,
            target_value=5,
            comparison_operator=">=",
            metadata={}
        )
        
        reward = AchievementReward(
            reward_type=RewardType.CURRENCY,
            value=10.0,
            metadata={}
        )
        
        achievement = Achievement(
            id="serialization_test",
            name="序列化測試",
            description="測試序列化功能",
            achievement_type=AchievementType.MILESTONE,
            guild_id=123456789,
            trigger_conditions=[trigger_condition],
            rewards=[reward],
            status=AchievementStatus.ACTIVE,
            created_at=datetime(2023, 1, 1, 12, 0, 0),
            updated_at=datetime(2023, 1, 1, 12, 0, 0)
        )
        
        # 轉換為字典
        data_dict = achievement.to_dict()
        assert data_dict["id"] == "serialization_test"
        assert data_dict["name"] == "序列化測試"
        assert data_dict["achievement_type"] == "milestone"
        assert len(data_dict["trigger_conditions"]) == 1
        assert len(data_dict["rewards"]) == 1
        
        # 從字典重建
        rebuilt_achievement = Achievement.from_dict(data_dict)
        assert rebuilt_achievement.id == achievement.id
        assert rebuilt_achievement.name == achievement.name
        assert rebuilt_achievement.achievement_type == achievement.achievement_type
        assert len(rebuilt_achievement.trigger_conditions) == 1
        assert len(rebuilt_achievement.rewards) == 1
    
    def test_achievement_database_conversion(self):
        """測試成就資料庫轉換"""
        achievement = Achievement(
            id="db_test_001",
            name="資料庫測試",
            description="測試資料庫轉換",
            achievement_type=AchievementType.MILESTONE,
            guild_id=123456789,
            trigger_conditions=[
                TriggerCondition(
                    trigger_type=TriggerType.MESSAGE_COUNT,
                    target_value=1,
                    comparison_operator=">=",
                    metadata={}
                )
            ],
            rewards=[
                AchievementReward(
                    reward_type=RewardType.CURRENCY,
                    value=5.0,
                    metadata={}
                )
            ],
            status=AchievementStatus.ACTIVE,
            created_at=datetime(2023, 1, 1, 12, 0, 0),
            updated_at=datetime(2023, 1, 1, 12, 0, 0)
        )
        
        # 轉換為資料庫行格式
        db_row = {
            'id': achievement.id,
            'name': achievement.name,
            'description': achievement.description,
            'achievement_type': achievement.achievement_type.value,
            'guild_id': achievement.guild_id,
            'trigger_conditions': json.dumps([c.to_dict() for c in achievement.trigger_conditions]),
            'rewards': json.dumps([r.to_dict() for r in achievement.rewards]),
            'status': achievement.status.value,
            'created_at': achievement.created_at.isoformat(),
            'updated_at': achievement.updated_at.isoformat()
        }
        
        # 從資料庫行重建
        rebuilt_achievement = Achievement.from_db_row(db_row)
        assert rebuilt_achievement.id == achievement.id
        assert rebuilt_achievement.name == achievement.name
        assert rebuilt_achievement.achievement_type == achievement.achievement_type
        assert len(rebuilt_achievement.trigger_conditions) == 1
        assert len(rebuilt_achievement.rewards) == 1


class TestAchievementProgressModel:
    """測試成就進度模型"""
    
    def test_progress_creation(self):
        """測試進度建立"""
        progress = AchievementProgress(
            id="progress_001",
            achievement_id="achievement_001",
            user_id=987654321,
            guild_id=123456789,
            current_progress={"message_count": 5, "voice_time": 300},
            completed=False,
            completed_at=None,
            last_updated=datetime.now()
        )
        
        assert progress.achievement_id == "achievement_001"
        assert progress.user_id == 987654321
        assert progress.current_progress["message_count"] == 5
        assert not progress.completed
    
    def test_progress_validation(self):
        """測試進度驗證"""
        # 無效的使用者ID
        with pytest.raises(ValidationError):
            AchievementProgress(
                id="progress_001",
                achievement_id="achievement_001",
                user_id=0,  # 無效ID
                guild_id=123456789,
                current_progress={},
                completed=False,
                completed_at=None,
                last_updated=datetime.now()
            )
        
        # 無效的成就ID
        with pytest.raises(ValidationError):
            AchievementProgress(
                id="progress_001",
                achievement_id="",  # 空成就ID
                user_id=987654321,
                guild_id=123456789,
                current_progress={},
                completed=False,
                completed_at=None,
                last_updated=datetime.now()
            )
    
    def test_progress_serialization(self):
        """測試進度序列化"""
        progress = AchievementProgress(
            id="progress_002",
            achievement_id="achievement_002",
            user_id=987654321,
            guild_id=123456789,
            current_progress={"message_count": 15, "reactions_given": 3},
            completed=True,
            completed_at=datetime(2023, 1, 15, 14, 30, 0),
            last_updated=datetime(2023, 1, 15, 14, 30, 0)
        )
        
        # 轉換為字典
        data_dict = progress.to_dict()
        assert data_dict["achievement_id"] == "achievement_002"
        assert data_dict["user_id"] == 987654321
        assert data_dict["completed"] is True
        
        # 從字典重建
        rebuilt_progress = AchievementProgress.from_dict(data_dict)
        assert rebuilt_progress.achievement_id == progress.achievement_id
        assert rebuilt_progress.user_id == progress.user_id
        assert rebuilt_progress.completed == progress.completed
    
    def test_progress_database_conversion(self):
        """測試進度資料庫轉換"""
        progress = AchievementProgress(
            id="db_progress_001",
            achievement_id="db_achievement_001",
            user_id=987654321,
            guild_id=123456789,
            current_progress={"step": 1, "total_steps": 5},
            completed=False,
            completed_at=None,
            last_updated=datetime(2023, 1, 1, 12, 0, 0)
        )
        
        # 轉換為資料庫行格式
        db_row = {
            'id': progress.id,
            'achievement_id': progress.achievement_id,
            'user_id': progress.user_id,
            'guild_id': progress.guild_id,
            'current_progress': json.dumps(progress.current_progress),
            'completed': progress.completed,
            'completed_at': progress.completed_at.isoformat() if progress.completed_at else None,
            'last_updated': progress.last_updated.isoformat()
        }
        
        # 從資料庫行重建
        rebuilt_progress = AchievementProgress.from_db_row(db_row)
        assert rebuilt_progress.achievement_id == progress.achievement_id
        assert rebuilt_progress.user_id == progress.user_id
        assert rebuilt_progress.current_progress == progress.current_progress
        assert rebuilt_progress.completed == progress.completed


class TestComplexScenarios:
    """測試複雜場景"""
    
    def test_multi_condition_achievement(self):
        """測試多條件成就"""
        conditions = [
            TriggerCondition(
                trigger_type=TriggerType.MESSAGE_COUNT,
                target_value=50,
                comparison_operator=">=",
                metadata={}
            ),
            TriggerCondition(
                trigger_type=TriggerType.VOICE_TIME,
                target_value=3600,  # 1小時
                comparison_operator=">=",
                metadata={}
            ),
            TriggerCondition(
                trigger_type=TriggerType.REACTION_COUNT,
                target_value=20,
                comparison_operator=">=",
                metadata={}
            )
        ]
        
        rewards = [
            AchievementReward(
                reward_type=RewardType.CURRENCY,
                value=100.0,
                metadata={}
            ),
            AchievementReward(
                reward_type=RewardType.ROLE,
                value="活躍會員",
                metadata={}
            )
        ]
        
        achievement = Achievement(
            id="multi_condition_achievement",
            name="全方位活躍成就",
            description="需要在訊息、語音和反應方面都達到要求",
            achievement_type=AchievementType.MILESTONE,
            guild_id=123456789,
            trigger_conditions=conditions,
            rewards=rewards,
            status=AchievementStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # 驗證成就建立
        assert len(achievement.trigger_conditions) == 3
        assert len(achievement.rewards) == 2
        achievement.validate()  # 不應該拋出異常
    
    def test_progressive_achievement_with_metadata(self):
        """測試帶有元資料的漸進式成就"""
        achievement = Achievement(
            id="progressive_achievement_001",
            name="訊息大師",
            description="根據發送的訊息數量獲得不同等級的獎勵",
            achievement_type=AchievementType.PROGRESSIVE,
            guild_id=123456789,
            trigger_conditions=[
                TriggerCondition(
                    trigger_type=TriggerType.MESSAGE_COUNT,
                    target_value=1000,
                    comparison_operator=">=",
                    metadata={"level": 3, "tier": "master"}
                )
            ],
            rewards=[
                AchievementReward(
                    reward_type=RewardType.CURRENCY,
                    value=500.0,
                    metadata={"bonus_multiplier": 2.0}
                ),
                AchievementReward(
                    reward_type=RewardType.BADGE,
                    value="訊息大師徽章",
                    metadata={"badge_tier": "gold", "special_effect": "glitter"}
                )
            ],
            status=AchievementStatus.ACTIVE,
            metadata={
                "progression_levels": [10, 50, 100, 500, 1000],
                "category": "communication",
                "difficulty": "hard"
            },
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # 測試序列化包含所有元資料
        data_dict = achievement.to_dict()
        assert "progression_levels" in data_dict["metadata"]
        assert data_dict["trigger_conditions"][0]["metadata"]["level"] == 3
        assert data_dict["rewards"][0]["metadata"]["bonus_multiplier"] == 2.0
        
        # 測試反序列化
        rebuilt_achievement = Achievement.from_dict(data_dict)
        assert rebuilt_achievement.metadata["category"] == "communication"
        assert rebuilt_achievement.trigger_conditions[0].metadata["tier"] == "master"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])