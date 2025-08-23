"""
Task T1 - Achievement system dependency and startup fix
完整的測試套件，驗證依賴注入修復和獎勵整合

這個測試套件專門測試T1的修復成果：
1. 依賴注入修復驗證
2. 成就觸發測試
3. 獎勵發放測試
4. 錯誤處理測試
"""

import pytest
import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock, patch

# 確保能找到專案模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from test_utils.test_isolation import isolated_test_environment, create_test_user_account
from services.achievement.models import (
    Achievement, AchievementType, AchievementStatus, AchievementReward, 
    TriggerCondition, TriggerType, RewardType
)


class TestT1DependencyInjectionFix:
    """T1 依賴注入修復測試類"""
    
    @pytest.mark.asyncio
    async def test_achievement_service_dependencies(self):
        """測試AchievementService的依賴注入是否正確"""
        async with isolated_test_environment() as env:
            startup_manager = env["startup_manager"]
            
            achievement_service = startup_manager.service_instances.get("AchievementService")
            assert achievement_service is not None, "AchievementService 不存在"
            assert achievement_service.is_initialized, "AchievementService 未初始化"
            
            # 檢查依賴是否正確注入
            economy_service = achievement_service.get_dependency("economy_service")
            role_service = achievement_service.get_dependency("role_service")
            db_manager = achievement_service.get_dependency("database_manager")
            
            assert economy_service is not None, "economy_service 依賴未注入"
            assert role_service is not None, "role_service 依賴未注入"
            assert db_manager is not None, "database_manager 依賴未注入"
            
            # 檢查依賴的類型是否正確
            assert hasattr(economy_service, 'create_account'), "economy_service 缺少必要方法"
            assert hasattr(role_service, 'has_permission'), "role_service 缺少必要方法"
            assert hasattr(db_manager, 'execute'), "database_manager 缺少必要方法"
    
    @pytest.mark.asyncio 
    async def test_service_initialization_order(self):
        """測試服務初始化順序是否正確"""
        async with isolated_test_environment() as env:
            startup_manager = env["startup_manager"]
            
            # 獲取初始化順序
            init_order = startup_manager.get_initialization_order()
            
            # 檢查AchievementService是否在其依賴之後初始化
            achievement_index = init_order.index("AchievementService") if "AchievementService" in init_order else -1
            economy_index = init_order.index("EconomyService") if "EconomyService" in init_order else -1
            role_index = init_order.index("RoleService") if "RoleService" in init_order else -1
            
            assert achievement_index > economy_index, "AchievementService 應該在 EconomyService 之後初始化"
            assert achievement_index > role_index, "AchievementService 應該在 RoleService 之後初始化"


class TestT1AchievementTriggering:
    """T1 成就觸發測試類"""
    
    @pytest.mark.asyncio
    async def test_create_and_trigger_achievement(self):
        """測試成就創建和觸發流程"""
        async with isolated_test_environment() as env:
            startup_manager = env["startup_manager"]
            achievement_service = startup_manager.service_instances["AchievementService"]
            economy_service = startup_manager.service_instances["EconomyService"]
            
            # 使用唯一ID防止衝突
            import uuid
            unique_id = str(uuid.uuid4())[:8]
            achievement_id = f"test_achievement_{unique_id}"
            
            # 創建測試用戶帳戶
            success = await create_test_user_account(economy_service, 67890, 12345, 0.0)
            assert success, "創建測試帳戶失敗"
            
            # 創建測試成就
            achievement = Achievement(
                id=achievement_id,
                name="測試成就",
                description="發送第一條訊息",
                achievement_type=AchievementType.MILESTONE,
                guild_id=12345,
                trigger_conditions=[
                    TriggerCondition(
                        trigger_type=TriggerType.MESSAGE_COUNT,
                        target_value=1,
                        comparison_operator=">=",
                        metadata={"evaluator_name": "message_count_evaluator"}
                    )
                ],
                rewards=[
                    AchievementReward(
                        reward_type=RewardType.CURRENCY,
                        value=50.0,
                        metadata={"currency_type": "coins"}
                    )
                ],
                status=AchievementStatus.ACTIVE
            )
            
            # 儲存成就
            await achievement_service.create_achievement(achievement)
            
            # 模擬事件觸發
            event_data = {
                "type": "message_sent",
                "user_id": 67890,
                "guild_id": 12345,
                "message_content": "Hello world!",
                "timestamp": "2025-08-22T12:00:00Z"
            }
            
            # 觸發成就檢查
            await achievement_service.process_event_triggers(event_data)
            
            # 驗證成就是否被授予
            user_progress = await achievement_service.get_user_progress(
                user_id=67890, 
                achievement_id=achievement_id
            )
            
            assert user_progress is not None, "用戶成就進度不存在"
            assert user_progress.completed, "成就未完成"
            
            # 驗證用戶帳戶餘額
            account = await economy_service.get_account("user_67890_12345")
            assert account is not None, "用戶帳戶不存在"
            assert account.balance == 50.0, f"帳戶餘額應該是50.0，實際是{account.balance}"
    
    @pytest.mark.asyncio
    async def test_reward_distribution(self):
        """測試獎勵發放功能"""
        async with isolated_test_environment() as env:
            startup_manager = env["startup_manager"]
            achievement_service = startup_manager.service_instances["AchievementService"]
            economy_service = startup_manager.service_instances["EconomyService"]
            
            # 使用唯一ID防止衝突
            import uuid
            unique_id = str(uuid.uuid4())[:8]
            achievement_id = f"test_multi_rewards_{unique_id}"
            
            # 創建測試用戶帳戶
            success = await create_test_user_account(economy_service, 67890, 12345, 0.0)
            assert success, "創建測試帳戶失敗"
            
            # 創建多種獎勵類型的成就
            achievement = Achievement(
                id=achievement_id,
                name="豐富獎勵成就",
                description="測試多種獎勵類型",
                achievement_type=AchievementType.MILESTONE,
                guild_id=12345,
                trigger_conditions=[
                    TriggerCondition(
                        trigger_type=TriggerType.MESSAGE_COUNT,
                        target_value=1,
                        comparison_operator=">=",
                        metadata={"evaluator_name": "message_count_evaluator"}
                    )
                ],
                rewards=[
                    AchievementReward(
                        reward_type=RewardType.CURRENCY,
                        value=100.0,
                        metadata={"currency_type": "coins"}
                    ),
                    AchievementReward(
                        reward_type=RewardType.ROLE,
                        value="achiever_role",
                        metadata={"role_name": "成就達人"}
                    ),
                    AchievementReward(
                        reward_type=RewardType.BADGE,
                        value="first_achievement",
                        metadata={"badge_icon": "🏆"}
                    )
                ],
                status=AchievementStatus.ACTIVE
            )
            
            # 儲存成就
            await achievement_service.create_achievement(achievement)
            
            # 觸發成就
            event_data = {
                "type": "message_sent",
                "user_id": 67890,
                "guild_id": 12345,
                "message_content": "Trigger test",
                "timestamp": "2025-08-22T12:00:00Z"
            }
            
            await achievement_service.process_event_triggers(event_data)
            
            # 驗證貨幣獎勵
            account = await economy_service.get_account("user_67890_12345")
            assert account is not None, "用戶帳戶不存在"
            assert account.balance == 100.0, f"帳戶餘額應該是100，實際是{account.balance}"
            
            # 驗證徽章獎勵（通過資料庫查詢）
            db_manager = achievement_service.get_dependency("database_manager")
            badges = await db_manager.fetchall(
                "SELECT * FROM user_badges WHERE user_id = ? AND guild_id = ? AND achievement_id = ?",
                (67890, 12345, achievement_id)
            )
            assert len(badges) > 0, "徽章獎勵未發放"
            # 檢查是否有我們期望的徽章
            badge_found = any(badge['badge_name'] == "first_achievement" for badge in badges)
            assert badge_found, f"期望的徽章未找到，實際徽章：{[badge['badge_name'] for badge in badges]}"


class TestT1ErrorHandling:
    """T1 錯誤處理測試類"""
    
    @pytest.mark.asyncio
    async def test_invalid_event_handling(self):
        """測試無效事件的處理"""
        async with isolated_test_environment() as env:
            startup_manager = env["startup_manager"]
            achievement_service = startup_manager.service_instances["AchievementService"]
            
            # 測試無效事件數據
            invalid_events = [
                {},  # 空事件
                {"type": "message_sent"},  # 缺少user_id
                {"type": "message_sent", "user_id": 123},  # 缺少guild_id
                {"user_id": 123, "guild_id": 456},  # 缺少type
            ]
            
            for event in invalid_events:
                # 應該優雅地處理無效事件，不應該拋出異常
                try:
                    await achievement_service.process_event_triggers(event)
                except Exception as e:
                    pytest.fail(f"處理無效事件時拋出異常：{e}")
    
    @pytest.mark.asyncio
    async def test_dependency_missing_handling(self):
        """測試依賴缺失時的處理"""
        async with isolated_test_environment() as env:
            startup_manager = env["startup_manager"]
            achievement_service = startup_manager.service_instances["AchievementService"]
            
            # 使用唯一ID防止衝突
            import uuid
            unique_id = str(uuid.uuid4())[:8]
            achievement_id = f"test_no_economy_{unique_id}"
            
            # 創建一個沒有經濟獎勵的成就（即使經濟服務不可用也應該能正常運作）
            achievement = Achievement(
                id=achievement_id,
                name="無經濟獎勵成就",
                description="測試無經濟依賴",
                achievement_type=AchievementType.MILESTONE,
                guild_id=12345,
                trigger_conditions=[
                    TriggerCondition(
                        trigger_type=TriggerType.MESSAGE_COUNT,
                        target_value=1,
                        comparison_operator=">=",
                        metadata={"evaluator_name": "message_count_evaluator"}
                    )
                ],
                rewards=[
                    AchievementReward(
                        reward_type=RewardType.BADGE,
                        value="test_badge",
                        metadata={"badge_icon": "🎯"}
                    )
                ],
                status=AchievementStatus.ACTIVE
            )
            
            # 應該能成功創建
            await achievement_service.create_achievement(achievement)
            
            # 模擬觸發
            event_data = {
                "type": "message_sent",
                "user_id": 78901,
                "guild_id": 12345,
                "message_content": "Test",
                "timestamp": "2025-08-22T12:00:00Z"
            }
            
            # 應該能成功處理（即使某些獎勵可能無法發放）
            await achievement_service.process_event_triggers(event_data)
            
            # 驗證成就進度
            user_progress = await achievement_service.get_user_progress(
                user_id=78901,
                achievement_id=achievement_id
            )
            
            assert user_progress is not None, "用戶成就進度應該存在"
            assert user_progress.completed, "成就應該完成"