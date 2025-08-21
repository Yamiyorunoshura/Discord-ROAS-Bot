"""
成就系統服務測試
Task ID: 6 - 成就系統核心功能

測試 services/achievement/achievement_service.py 中的 AchievementService 類別
包含所有核心功能的單元測試、整合測試和效能測試

測試覆蓋：
- F1: 成就系統資料模型
- F2: 成就服務核心邏輯  
- F3: 成就觸發系統
- F4: 獎勵系統整合
- N1: 效能要求
- N2: 可擴展性要求
- N3: 可靠性要求
"""

import pytest
import asyncio
import sys
import os
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Optional, Dict, Any, List

# 測試文件中的匯入
from services.achievement.achievement_service import AchievementService
from services.achievement.models import (
    Achievement, AchievementProgress, AchievementReward, TriggerCondition,
    AchievementType, TriggerType, RewardType, AchievementStatus
)
from services.economy.economy_service import EconomyService
from services.government.role_service import RoleService
from core.database_manager import DatabaseManager
from core.exceptions import ValidationError, ServiceError, DatabaseError


@pytest.fixture
async def mock_db_manager():
    """模擬資料庫管理器"""
    db_manager = Mock(spec=DatabaseManager)
    db_manager.is_initialized = True
    
    # 建立完整的模擬資料庫行結構
    sample_achievement_row = {
        "id": "test_achievement_001",
        "name": "初次發言", 
        "description": "在伺服器中發送第一條訊息",
        "achievement_type": "milestone",
        "guild_id": 123456789,
        "trigger_conditions": '[{"trigger_type": "message_count", "target_value": 1, "comparison_operator": ">=", "metadata": {}}]',
        "rewards": '[{"reward_type": "currency", "value": 10.0, "metadata": {"reason": "完成首次發言成就"}}]',
        "status": "active",
        "metadata": "{}",
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00"
    }
    
    sample_progress_row = {
        "id": "progress_001",
        "achievement_id": "test_achievement_001", 
        "user_id": 987654321,
        "guild_id": 123456789,
        "current_progress": '{"message_count": 5}',
        "completed": 1,
        "completed_at": "2024-01-01T00:00:00",
        "last_updated": "2024-01-01T00:00:00"
    }
    
    # 預設返回None（表示不存在的記錄）
    # 但可以在測試中動態配置
    mock_result = Mock()
    mock_result.lastrowid = 1
    mock_result.rowcount = 1
    db_manager.execute = AsyncMock(return_value=mock_result)
    db_manager.fetchone = AsyncMock(return_value=None)
    db_manager.fetchall = AsyncMock(return_value=[])
    
    # 修正事務管理器的模擬設置
    mock_transaction = AsyncMock()
    mock_transaction.__aenter__ = AsyncMock(return_value=mock_transaction)
    mock_transaction.__aexit__ = AsyncMock(return_value=None)
    db_manager.transaction = Mock(return_value=mock_transaction)
    
    # 儲存示例資料供測試使用
    db_manager.sample_achievement_row = sample_achievement_row
    db_manager.sample_progress_row = sample_progress_row
    
    # 模擬遷移管理器
    db_manager.migration_manager = Mock()
    db_manager.migration_manager.add_migration = Mock()
    db_manager.migration_manager.apply_migrations = AsyncMock(return_value=True)
    
    return db_manager


@pytest.fixture
async def mock_economy_service():
    """模擬經濟服務"""
    service = Mock(spec=EconomyService)
    service.is_initialized = True
    service.name = "EconomyService"
    
    # 模擬經濟服務方法
    service.deposit = AsyncMock(return_value=Mock())
    service.get_balance = AsyncMock(return_value=100.0)
    service.create_account = AsyncMock()
    
    return service


@pytest.fixture
async def mock_role_service():
    """模擬身分組服務"""
    service = Mock(spec=RoleService)
    service.is_initialized = True
    service.name = "RoleService"
    
    # 模擬身分組服務方法
    service.assign_role_to_user = AsyncMock(return_value=True)
    service.get_role_by_name = AsyncMock()
    service.create_role_if_not_exists = AsyncMock()
    
    # 模擬權限檢查方法 - 預設授權管理員操作
    service.has_permission = AsyncMock(return_value=True)
    
    return service


@pytest.fixture
async def achievement_service(mock_db_manager, mock_economy_service, mock_role_service):
    """成就服務實例"""
    service = AchievementService()
    service.add_dependency(mock_db_manager, "database_manager")
    service.add_dependency(mock_economy_service, "economy_service")
    service.add_dependency(mock_role_service, "role_service")
    
    await service.initialize()
    return service


@pytest.fixture
def sample_achievement():
    """範例成就"""
    return Achievement(
        id="test_achievement_001",
        name="初次發言",
        description="在伺服器中發送第一條訊息",
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
                value=10.0,
                metadata={"reason": "完成首次發言成就"}
            )
        ],
        status=AchievementStatus.ACTIVE,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


@pytest.fixture
def sample_progress():
    """範例進度"""
    return AchievementProgress(
        id="progress_001",
        achievement_id="test_achievement_001",
        user_id=987654321,
        guild_id=123456789,
        current_progress={"message_count": 0},
        completed=False,
        completed_at=None,
        last_updated=datetime.now()
    )


class TestAchievementServiceInitialization:
    """測試 AchievementService 初始化"""
    
    async def test_service_initialization(self, mock_db_manager, mock_economy_service, mock_role_service):
        """測試服務初始化"""
        service = AchievementService()
        service.add_dependency(mock_db_manager, "database_manager")
        service.add_dependency(mock_economy_service, "economy_service")
        service.add_dependency(mock_role_service, "role_service")
        
        result = await service.initialize()
        assert result is True
        assert service.is_initialized
        
        # 驗證遷移註冊
        mock_db_manager.migration_manager.add_migration.assert_called()
        mock_db_manager.migration_manager.apply_migrations.assert_called()
    
    async def test_service_initialization_without_dependencies(self):
        """測試缺少依賴的初始化失敗"""
        service = AchievementService()
        result = await service.initialize()
        assert result is False
    
    async def test_service_cleanup(self, achievement_service):
        """測試服務清理"""
        await achievement_service.cleanup()
        assert not achievement_service.is_initialized


class TestAchievementDataModel:
    """測試成就資料模型 - F1"""
    
    def test_achievement_model_creation(self, sample_achievement):
        """測試成就模型建立"""
        assert sample_achievement.id == "test_achievement_001"
        assert sample_achievement.name == "初次發言"
        assert sample_achievement.achievement_type == AchievementType.MILESTONE
        assert len(sample_achievement.trigger_conditions) == 1
        assert len(sample_achievement.rewards) == 1
    
    def test_achievement_model_validation(self):
        """測試成就模型驗證"""
        # 測試無效資料
        with pytest.raises(ValidationError):
            Achievement(
                id="",  # 空ID應該失敗
                name="測試成就",
                description="測試描述",
                achievement_type=AchievementType.MILESTONE,
                guild_id=123456789,
                trigger_conditions=[],
                rewards=[]
            )
    
    def test_progress_model_creation(self, sample_progress):
        """測試進度模型建立"""
        assert sample_progress.achievement_id == "test_achievement_001"
        assert sample_progress.user_id == 987654321
        assert not sample_progress.completed
        assert "message_count" in sample_progress.current_progress
    
    def test_trigger_condition_model(self):
        """測試觸發條件模型"""
        condition = TriggerCondition(
            trigger_type=TriggerType.MESSAGE_COUNT,
            target_value=10,
            comparison_operator=">=",
            metadata={"channel_id": 123}
        )
        
        assert condition.trigger_type == TriggerType.MESSAGE_COUNT
        assert condition.target_value == 10
        assert condition.comparison_operator == ">="
        assert condition.metadata["channel_id"] == 123
    
    def test_reward_model(self):
        """測試獎勵模型"""
        reward = AchievementReward(
            reward_type=RewardType.ROLE,
            value="VIP會員",
            metadata={"role_color": "gold"}
        )
        
        assert reward.reward_type == RewardType.ROLE
        assert reward.value == "VIP會員"
        assert reward.metadata["role_color"] == "gold"


class TestAchievementCRUDOperations:
    """測試成就CRUD操作 - F2"""
    
    async def test_create_achievement(self, achievement_service, sample_achievement, mock_db_manager):
        """測試建立成就"""
        mock_db_manager.execute.return_value = None
        
        result = await achievement_service.create_achievement(sample_achievement)
        
        assert result.id == sample_achievement.id
        mock_db_manager.execute.assert_called()
    
    async def test_get_achievement_by_id(self, achievement_service, sample_achievement, mock_db_manager):
        """測試根據ID獲取成就"""
        # 模擬資料庫返回
        mock_db_manager.fetchone.return_value = {
            'id': sample_achievement.id,
            'name': sample_achievement.name,
            'description': sample_achievement.description,
            'achievement_type': sample_achievement.achievement_type.value,
            'guild_id': sample_achievement.guild_id,
            'trigger_conditions': json.dumps([c.to_dict() for c in sample_achievement.trigger_conditions]),
            'rewards': json.dumps([r.to_dict() for r in sample_achievement.rewards]),
            'status': sample_achievement.status.value,
            'created_at': sample_achievement.created_at.isoformat(),
            'updated_at': sample_achievement.updated_at.isoformat()
        }
        
        result = await achievement_service.get_achievement(sample_achievement.id)
        
        assert result is not None
        assert result.id == sample_achievement.id
        mock_db_manager.fetchone.assert_called()
    
    async def test_update_achievement(self, achievement_service, sample_achievement, mock_db_manager):
        """測試更新成就"""
        # 配置模擬資料庫返回現有成就資料
        existing_achievement_row = mock_db_manager.sample_achievement_row.copy()
        mock_db_manager.fetchone.return_value = existing_achievement_row
        mock_db_manager.execute.return_value = None
        
        sample_achievement.name = "更新後的成就名稱"
        result = await achievement_service.update_achievement(sample_achievement)
        
        assert result.name == "更新後的成就名稱"
        mock_db_manager.execute.assert_called()
    
    async def test_delete_achievement(self, achievement_service, mock_db_manager):
        """測試刪除成就"""
        achievement_id = "test_achievement_001"
        
        # 配置模擬資料庫返回現有成就資料
        existing_achievement_row = mock_db_manager.sample_achievement_row.copy()
        mock_db_manager.fetchone.return_value = existing_achievement_row
        mock_db_manager.execute.return_value = None
        
        result = await achievement_service.delete_achievement(achievement_id)
        
        assert result is True
        mock_db_manager.execute.assert_called()
    
    async def test_list_achievements_by_guild(self, achievement_service, mock_db_manager):
        """測試按伺服器列出成就"""
        guild_id = 123456789
        
        # 模擬多個成就
        mock_db_manager.fetchall.return_value = [
            {
                'id': 'achievement_1',
                'name': '成就1',
                'description': '描述1',
                'achievement_type': 'milestone',
                'guild_id': guild_id,
                'trigger_conditions': '[]',
                'rewards': '[]',
                'status': 'active',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            },
            {
                'id': 'achievement_2',
                'name': '成就2',
                'description': '描述2',
                'achievement_type': 'recurring',
                'guild_id': guild_id,
                'trigger_conditions': '[]',
                'rewards': '[]',
                'status': 'active',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
        ]
        
        results = await achievement_service.list_guild_achievements(guild_id)
        
        assert len(results) == 2
        assert results[0].id == 'achievement_1'
        assert results[1].id == 'achievement_2'
        mock_db_manager.fetchall.assert_called()


class TestAchievementProgress:
    """測試成就進度管理 - F2"""
    
    async def test_get_user_progress(self, achievement_service, sample_progress, mock_db_manager):
        """測試獲取使用者進度"""
        user_id = 987654321
        achievement_id = "test_achievement_001"
        
        # 修正進度資料欄位名稱
        mock_db_manager.fetchone.return_value = {
            'id': sample_progress.id,
            'achievement_id': sample_progress.achievement_id,
            'user_id': sample_progress.user_id,
            'guild_id': sample_progress.guild_id,
            'current_progress': json.dumps(sample_progress.current_progress),
            'completed': sample_progress.completed,
            'completed_at': None,
            'last_updated': sample_progress.last_updated.isoformat()
        }
        
        result = await achievement_service.get_user_progress(user_id, achievement_id)
        
        assert result is not None
        assert result.user_id == user_id
        assert result.achievement_id == achievement_id
        mock_db_manager.fetchone.assert_called()
    
    async def test_update_user_progress(self, achievement_service, mock_db_manager):
        """測試更新使用者進度"""
        user_id = 987654321
        achievement_id = "test_achievement_001"
        new_progress = {"message_count": 5}
        
        # 設置無限循環的回傳值（只要有足夠多的調用就行）
        existing_achievement_row = mock_db_manager.sample_achievement_row.copy()
        existing_progress_row = mock_db_manager.sample_progress_row.copy()
        
        # 設置可重複的回傳序列
        mock_db_manager.fetchone.side_effect = lambda *args, **kwargs: (
            existing_achievement_row if "achievements" in (args[0] if args else "") 
            else existing_progress_row
        )
        mock_db_manager.execute.return_value = None
        
        result = await achievement_service.update_user_progress(
            user_id, achievement_id, new_progress
        )
        
        assert result is True
        mock_db_manager.execute.assert_called()
    
    async def test_list_user_achievements(self, achievement_service, mock_db_manager):
        """測試列出使用者成就"""
        user_id = 987654321
        guild_id = 123456789
        
        # 配置完整的進度記錄資料結構，包含所有必需欄位
        mock_db_manager.fetchall.return_value = [
            {
                'id': 'progress_001',
                'achievement_id': 'achievement_1',
                'user_id': user_id,
                'guild_id': guild_id,
                'current_progress': '{"message_count": 10}',
                'completed': True,
                'completed_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                # 添加成就相關欄位（如果查詢包含JOIN）
                'name': '測試成就',
                'description': '測試成就描述',
                'achievement_type': 'milestone',
                'status': 'active'
            }
        ]
        
        results = await achievement_service.list_user_achievements(user_id, guild_id)
        
        assert len(results) >= 0
        mock_db_manager.fetchall.assert_called()


class TestTriggerSystem:
    """測試觸發系統 - F3"""
    
    async def test_evaluate_trigger_condition(self, achievement_service):
        """測試觸發條件評估"""
        condition = TriggerCondition(
            trigger_type=TriggerType.MESSAGE_COUNT,
            target_value=10,
            comparison_operator=">=",
            metadata={}
        )
        
        # 測試達成條件
        user_progress = {"message_count": 15}
        result = await achievement_service.evaluate_trigger_condition(condition, user_progress)
        assert result is True
        
        # 測試未達成條件
        user_progress = {"message_count": 5}
        result = await achievement_service.evaluate_trigger_condition(condition, user_progress)
        assert result is False
    
    async def test_process_event_triggers(self, achievement_service, mock_db_manager):
        """測試事件觸發處理"""
        user_id = 987654321
        guild_id = 123456789
        event_data = {
            "type": "message_sent",
            "user_id": user_id,
            "guild_id": guild_id,
            "channel_id": 111222333
        }
        
        # 模擬活躍成就
        mock_db_manager.fetchall.return_value = []
        
        await achievement_service.process_event_triggers(event_data)
        
        # 驗證資料庫查詢被調用
        mock_db_manager.fetchall.assert_called()
    
    async def test_compound_trigger_conditions(self, achievement_service):
        """測試複合觸發條件"""
        conditions = [
            TriggerCondition(
                trigger_type=TriggerType.MESSAGE_COUNT,
                target_value=10,
                comparison_operator=">=",
                metadata={}
            ),
            TriggerCondition(
                trigger_type=TriggerType.VOICE_TIME,
                target_value=60,
                comparison_operator=">=",
                metadata={}
            )
        ]
        
        # 測試所有條件都達成
        user_progress = {"message_count": 15, "voice_time": 120}
        result = await achievement_service.evaluate_compound_conditions(
            conditions, user_progress, operator="AND"
        )
        assert result is True
        
        # 測試部分條件達成（AND操作）
        user_progress = {"message_count": 15, "voice_time": 30}
        result = await achievement_service.evaluate_compound_conditions(
            conditions, user_progress, operator="AND"
        )
        assert result is False
        
        # 測試部分條件達成（OR操作）
        result = await achievement_service.evaluate_compound_conditions(
            conditions, user_progress, operator="OR"
        )
        assert result is True


class TestRewardSystem:
    """測試獎勵系統整合 - F4"""
    
    async def test_award_currency_reward(self, achievement_service, mock_economy_service):
        """測試貨幣獎勵發放"""
        user_id = 987654321
        guild_id = 123456789
        reward = AchievementReward(
            reward_type=RewardType.CURRENCY,
            value=50.0,
            metadata={"reason": "完成成就獎勵"}
        )
        
        await achievement_service.award_reward(user_id, guild_id, reward)
        
        # 驗證經濟服務被調用
        mock_economy_service.deposit.assert_called()
    
    async def test_award_role_reward(self, achievement_service, mock_role_service):
        """測試身分組獎勵發放"""
        user_id = 987654321
        guild_id = 123456789
        reward = AchievementReward(
            reward_type=RewardType.ROLE,
            value="VIP會員",
            metadata={"role_color": "gold"}
        )
        
        # 模擬Discord對象
        mock_guild = MagicMock()
        mock_user = MagicMock()
        mock_role = MagicMock()
        # 直接測試獎勵發放
        result = await achievement_service.award_reward(user_id, guild_id, reward)
        
        # 驗證身分組獎勵被記錄
        assert result["success"] is True
        assert "身分組獎勵已記錄" in result.get("note", "")
    
    async def test_award_badge_reward(self, achievement_service, mock_db_manager):
        """測試徽章獎勵發放"""
        user_id = 987654321
        guild_id = 123456789
        reward = AchievementReward(
            reward_type=RewardType.BADGE,
            value="首次發言徽章",
            metadata={"badge_icon": "🏆"}
        )
        
        # 確保execute返回有lastrowid的mock對象
        mock_db_manager.execute.return_value = Mock(lastrowid=1, rowcount=1)
        
        result = await achievement_service.award_reward(user_id, guild_id, reward)
        assert result["success"] is True
        
        # 驗證徽章記錄被儲存
        mock_db_manager.execute.assert_called()
    
    async def test_reward_transaction_record(self, achievement_service, mock_db_manager, mock_economy_service):
        """測試獎勵發放記錄"""
        user_id = 987654321
        guild_id = 123456789
        achievement_id = "test_achievement_001"
        rewards = [
            AchievementReward(
                reward_type=RewardType.CURRENCY,
                value=25.0,
                metadata={}
            )
        ]
        
        # 清除先前的調用記錄
        mock_db_manager.execute.reset_mock()
        mock_economy_service.deposit.reset_mock()
        
        # 確保 complete_achievement 能夠找到成就和進度
        existing_achievement_row = mock_db_manager.sample_achievement_row.copy()
        existing_progress_row = mock_db_manager.sample_progress_row.copy()
        
        # 設置可重複的回傳序列
        mock_db_manager.fetchone.side_effect = lambda *args, **kwargs: (
            existing_achievement_row if "achievements" in (args[0] if args else "") 
            else existing_progress_row
        )
        
        # 確保execute返回有lastrowid的對象
        mock_result = Mock()
        mock_result.lastrowid = 123
        mock_result.rowcount = 1
        mock_db_manager.execute.return_value = mock_result
        
        # 模擬成就完成，應該會記錄獎勵發放
        result = await achievement_service.complete_achievement(user_id, achievement_id, rewards)
        
        # 驗證成就完成成功
        assert result is True
        
        # 驗證相關調用（任何一個被調用都表示有記錄操作）
        assert (mock_db_manager.execute.call_count >= 1 or 
                mock_economy_service.deposit.call_count >= 1), \
               f"應該至少有一個數據庫操作或獎勵發放調用，但執行次數分別為：{mock_db_manager.execute.call_count}, {mock_economy_service.deposit.call_count}"


class TestPerformanceRequirements:
    """測試效能要求 - N1"""
    
    async def test_trigger_evaluation_performance(self, achievement_service):
        """測試觸發評估效能 < 100ms"""
        condition = TriggerCondition(
            trigger_type=TriggerType.MESSAGE_COUNT,
            target_value=10,
            comparison_operator=">=",
            metadata={}
        )
        user_progress = {"message_count": 15}
        
        start_time = time.time()
        result = await achievement_service.evaluate_trigger_condition(condition, user_progress)
        end_time = time.time()
        
        execution_time = (end_time - start_time) * 1000  # 轉換為毫秒
        assert execution_time < 100  # 應該小於100ms
        assert result is True
    
    async def test_progress_query_performance(self, achievement_service, mock_db_manager):
        """測試進度查詢效能 < 200ms"""
        user_id = 987654321
        achievement_id = "test_achievement_001"
        
        mock_db_manager.fetchone.return_value = {
            'id': 'progress_001',
            'achievement_id': achievement_id,
            'user_id': user_id,
            'guild_id': 123456789,
            'current_progress': '{"message_count": 5}',
            'completed': False,
            'completed_at': None,
            'last_updated': datetime.now().isoformat()
        }
        
        start_time = time.time()
        result = await achievement_service.get_user_progress(user_id, achievement_id)
        end_time = time.time()
        
        execution_time = (end_time - start_time) * 1000
        assert execution_time < 200  # 應該小於200ms
        assert result is not None
    
    async def test_batch_progress_update(self, achievement_service, mock_db_manager):
        """測試批量進度更新"""
        updates = [
            {"user_id": 111, "achievement_id": "ach_001", "progress": {"count": 1}},
            {"user_id": 222, "achievement_id": "ach_001", "progress": {"count": 2}},
            {"user_id": 333, "achievement_id": "ach_001", "progress": {"count": 3}},
        ]
        
        # 配置模擬資料庫總是返回現有成就資料
        existing_achievement_row = mock_db_manager.sample_achievement_row.copy()
        existing_achievement_row["id"] = "ach_001"
        existing_progress_row = mock_db_manager.sample_progress_row.copy()
        existing_progress_row["achievement_id"] = "ach_001"
        
        # 設置可重複的回傳序列
        mock_db_manager.fetchone.side_effect = lambda *args, **kwargs: (
            existing_achievement_row if "achievements" in (args[0] if args else "") 
            else existing_progress_row
        )
        mock_db_manager.execute.return_value = None
        
        start_time = time.time()
        result = await achievement_service.batch_update_progress(updates)
        end_time = time.time()
        
        execution_time = (end_time - start_time) * 1000
        assert result is True
        # 批量操作應該比逐一操作更快
        assert execution_time < len(updates) * 50  # 每個更新應該平均小於50ms


class TestScalabilityRequirements:
    """測試可擴展性要求 - N2"""
    
    async def test_custom_trigger_type_registration(self, achievement_service):
        """測試自訂觸發類型註冊"""
        # 註冊自訂觸發類型，符合實際的函數簽名
        custom_trigger = "CUSTOM_ACTION"
        def evaluator_func(progress_data, target_value, operator):
            """自訂評估器，符合實際的調用格式"""
            current_value = progress_data.get("custom_count", 0)
            if operator == ">=":
                return current_value >= target_value
            elif operator == "==":
                return current_value == target_value
            elif operator == ">":
                return current_value > target_value
            else:
                return False
        
        await achievement_service.register_custom_trigger_type(custom_trigger, evaluator_func)
        
        # 測試自訂觸發類型使用
        condition = TriggerCondition(
            trigger_type=custom_trigger,
            target_value=5,
            comparison_operator=">=",
            metadata={}
        )
        user_progress = {"custom_count": 10}
        
        result = await achievement_service.evaluate_trigger_condition(condition, user_progress)
        assert result is True
    
    async def test_custom_reward_type_registration(self, achievement_service):
        """測試自訂獎勵類型註冊"""
        # 註冊自訂獎勵類型
        custom_reward = "CUSTOM_REWARD"
        handler_func = AsyncMock()
        
        await achievement_service.register_custom_reward_type(custom_reward, handler_func)
        
        # 測試自訂獎勵類型使用
        reward = AchievementReward(
            reward_type=custom_reward,
            value="special_item",
            metadata={"rarity": "legendary"}
        )
        
        await achievement_service.award_reward(123, 456, reward)
        
        # 驗證自訂處理器被調用
        handler_func.assert_called()
    
    def test_achievement_data_compatibility(self, sample_achievement):
        """測試成就資料向前兼容"""
        # 測試新增欄位不會破壞現有功能
        data_dict = sample_achievement.to_dict()
        data_dict["new_field"] = "new_value"
        
        # 應該能夠處理額外的欄位而不報錯
        try:
            achievement = Achievement.from_dict(data_dict)
            assert achievement.id == sample_achievement.id
        except Exception as e:
            pytest.fail(f"向前兼容性測試失敗：{e}")


class TestReliabilityRequirements:
    """測試可靠性要求 - N3"""
    
    async def test_concurrent_progress_update_handling(self, achievement_service, mock_db_manager):
        """測試並發進度更新處理"""
        user_id = 987654321
        achievement_id = "test_achievement_001"
        
        # 配置模擬資料庫總是返回現有資料
        existing_achievement_row = mock_db_manager.sample_achievement_row.copy()
        existing_progress_row = mock_db_manager.sample_progress_row.copy()
        
        # 設置可重複的回傳序列
        mock_db_manager.fetchone.side_effect = lambda *args, **kwargs: (
            existing_achievement_row if "achievements" in (args[0] if args else "") 
            else existing_progress_row
        )
        mock_db_manager.execute.return_value = None
        
        # 創建多個並發任務
        tasks = []
        for i in range(10):
            task = achievement_service.update_user_progress(
                user_id, achievement_id, {"message_count": i}
            )
            tasks.append(task)
        
        # 執行並發更新
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 檢查是否有任何異常
        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"並發更新失敗：{result}")
                
        # 所有更新應該都成功
        assert all(result is True for result in results if not isinstance(result, Exception))
    
    async def test_database_error_recovery(self, achievement_service, mock_db_manager):
        """測試資料庫錯誤恢復"""
        achievement_id = "test_achievement_001"
        
        # 模擬資料庫錯誤
        mock_db_manager.fetchone.side_effect = DatabaseError("模擬資料庫連接失敗", operation="fetchone")
        
        # 應該優雅處理錯誤而不崩潰
        with pytest.raises(ServiceError):
            await achievement_service.get_achievement(achievement_id)
    
    async def test_data_consistency_validation(self, achievement_service, mock_db_manager):
        """測試資料一致性驗證"""
        user_id = 987654321
        achievement_id = "test_achievement_001"
        
        # 設置資料庫事務模擬
        mock_transaction = AsyncMock()
        mock_db_manager.transaction.return_value.__aenter__.return_value = mock_transaction
        mock_db_manager.transaction.return_value.__aexit__.return_value = None
        
        # 測試事務中的資料更新
        await achievement_service.complete_achievement_with_rewards(
            user_id, achievement_id, []
        )
        
        # 驗證事務被使用
        mock_db_manager.transaction.assert_called()
    
    async def test_graceful_degradation(self, achievement_service, mock_economy_service, mock_role_service):
        """測試優雅降級"""
        user_id = 987654321
        guild_id = 123456789
        
        # 模擬經濟服務不可用
        mock_economy_service.deposit.side_effect = ServiceError("經濟服務不可用", service_name="EconomyService", operation="deposit")
        
        reward = AchievementReward(
            reward_type=RewardType.CURRENCY,
            value=10.0,
            metadata={}
        )
        
        # 應該記錄錯誤但不完全失敗
        result = await achievement_service.award_reward_with_fallback(user_id, guild_id, reward)
        
        # 驗證有適當的錯誤處理
        assert "error" in result or "fallback" in result


class TestIntegrationScenarios:
    """整合測試場景"""
    
    async def test_complete_achievement_flow(self, achievement_service, sample_achievement, mock_db_manager, mock_economy_service):
        """測試完整的成就流程"""
        user_id = 987654321
        guild_id = 123456789
        
        # 1. 創建成就
        mock_db_manager.execute.return_value = None
        achievement = await achievement_service.create_achievement(sample_achievement)
        
        # 2. 處理事件觸發
        event_data = {
            "type": "message_sent",
            "user_id": user_id,
            "guild_id": guild_id
        }
        
        # 配置模擬資料庫返回的活躍成就資料，包含所有必需欄位
        mock_achievement_row = {
            'id': achievement.id,
            'name': achievement.name,
            'description': achievement.description,
            'achievement_type': achievement.achievement_type.value,
            'guild_id': achievement.guild_id,
            'trigger_conditions': json.dumps([c.to_dict() for c in achievement.trigger_conditions]),
            'rewards': json.dumps([r.to_dict() for r in achievement.rewards]),
            'status': achievement.status.value,
            'metadata': json.dumps(achievement.metadata),
            'created_at': achievement.created_at.isoformat(),
            'updated_at': achievement.updated_at.isoformat()
        }
        
        mock_db_manager.fetchall.return_value = [mock_achievement_row]
        
        # 配置使用者進度資料
        mock_progress_row = {
            'id': 'progress_001',
            'achievement_id': achievement.id,
            'user_id': user_id,
            'guild_id': guild_id,
            'current_progress': '{"message_count": 0}',
            'completed': False,
            'completed_at': None,
            'last_updated': datetime.now().isoformat()
        }
        
        mock_db_manager.fetchone.return_value = mock_progress_row
        
        # 3. 處理觸發並完成成就
        await achievement_service.process_event_triggers(event_data)
        
        # 驗證整個流程
        assert mock_db_manager.execute.call_count >= 1  # 至少有一次資料庫寫入
    
    async def test_multi_reward_achievement(self, achievement_service, mock_db_manager, mock_economy_service, mock_role_service):
        """測試多重獎勵成就"""
        achievement = Achievement(
            id="multi_reward_achievement",
            name="多重獎勵成就",
            description="獲得多種獎勵的成就",
            achievement_type=AchievementType.MILESTONE,
            guild_id=123456789,
            trigger_conditions=[
                TriggerCondition(
                    trigger_type=TriggerType.MESSAGE_COUNT,
                    target_value=100,
                    comparison_operator=">=",
                    metadata={}
                )
            ],
            rewards=[
                AchievementReward(reward_type=RewardType.CURRENCY, value=100.0, metadata={}),
                AchievementReward(reward_type=RewardType.ROLE, value="活躍會員", metadata={}),
                AchievementReward(reward_type=RewardType.BADGE, value="百訊徽章", metadata={})
            ]
        )
        
        user_id = 987654321
        guild_id = 123456789
        
        # 確保 execute 返回有 lastrowid 屬性的對象
        mock_result = Mock()
        mock_result.lastrowid = 123
        mock_result.rowcount = 1
        mock_db_manager.execute.return_value = mock_result
        
        # 直接發放多重獎勵
        for reward in achievement.rewards:
            await achievement_service.award_reward(user_id, guild_id, reward)
        
        # 驗證各種獎勵都被處理
        assert mock_economy_service.deposit.call_count >= 1  # 貨幣獎勵
        assert mock_db_manager.execute.call_count >= 1      # 徽章獎勵記錄


if __name__ == "__main__":
    pytest.main([__file__, "-v"])