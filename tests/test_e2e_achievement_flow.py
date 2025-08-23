"""
Task T1 - End-to-End Achievement Triggering Test
端對端成就觸發測試

這個測試模擬真實的Discord機器人使用場景：
1. 使用者加入伺服器
2. 發送訊息觸發成就
3. 獲得獎勵
4. 檢查所有系統狀態
"""

import pytest
import asyncio
import sys
import os
import tempfile
import shutil
import json
from datetime import datetime, timedelta

# 確保能找到專案模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.service_startup_manager import get_startup_manager
from services.achievement.models import (
    Achievement, AchievementType, AchievementStatus, AchievementReward, 
    TriggerCondition, TriggerType, RewardType
)
from services.economy.models import AccountType


class TestE2EAchievementFlow:
    """端對端成就流程測試"""
    
    @pytest.fixture(scope="class")
    async def discord_bot_simulation(self):
        """模擬Discord機器人環境"""
        # 設置臨時資料庫
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "bot.db")
        os.environ["DATABASE_PATH"] = db_path
        
        # 初始化所有服務
        startup_manager = await get_startup_manager()
        success = await startup_manager.initialize_all_services()
        assert success, "機器人服務初始化失敗"
        
        # 獲取服務實例
        services = {
            "achievement": startup_manager.service_instances["AchievementService"],
            "economy": startup_manager.service_instances["EconomyService"],
            "role": startup_manager.service_instances["RoleService"],
            "government": startup_manager.service_instances.get("GovernmentService"),
            "startup_manager": startup_manager
        }
        
        # 設置測試伺服器環境
        guild_id = 123456789
        await self._setup_test_guild(services, guild_id)
        
        yield {"services": services, "guild_id": guild_id}
        
        # 清理
        await startup_manager.cleanup_all_services()
        shutil.rmtree(temp_dir, ignore_errors=True)
        if "DATABASE_PATH" in os.environ:
            del os.environ["DATABASE_PATH"]
    
    async def _setup_test_guild(self, services, guild_id):
        """設置測試伺服器環境"""
        achievement_service = services["achievement"]
        
        # 創建多種類型的成就
        achievements = [
            # 新手成就：發送第一條訊息
            {
                "id": "first_message",
                "name": "破冰者",
                "description": "在伺服器中發送第一條訊息",
                "trigger_value": 1,
                "rewards": [
                    {"type": RewardType.CURRENCY, "value": 50},
                    {"type": RewardType.BADGE, "value": "newcomer"}
                ]
            },
            # 活躍成就：發送10條訊息
            {
                "id": "active_chatter",
                "name": "健談者",
                "description": "發送10條訊息",
                "trigger_value": 10,
                "rewards": [
                    {"type": RewardType.CURRENCY, "value": 200},
                    {"type": RewardType.ROLE, "value": "活躍會員"},
                    {"type": RewardType.BADGE, "value": "active_member"}
                ]
            },
            # 里程碑成就：發送100條訊息
            {
                "id": "message_master",
                "name": "訊息大師",
                "description": "發送100條訊息",
                "trigger_value": 100,
                "rewards": [
                    {"type": RewardType.CURRENCY, "value": 1000},
                    {"type": RewardType.ROLE, "value": "資深會員"},
                    {"type": RewardType.BADGE, "value": "veteran"}
                ]
            }
        ]
        
        for achievement_data in achievements:
            await self._create_achievement(achievement_service, guild_id, achievement_data)
    
    async def _create_achievement(self, achievement_service, guild_id, data):
        """創建成就的助手方法"""
        trigger_condition = TriggerCondition(
            trigger_type=TriggerType.MESSAGE_COUNT,
            target_value=data["trigger_value"],
            comparison_operator=">=",
            metadata={"description": data["description"]}
        )
        
        rewards = []
        for reward_data in data["rewards"]:
            reward = AchievementReward(
                reward_type=reward_data["type"],
                value=reward_data["value"],
                metadata={"auto_generated": True}
            )
            rewards.append(reward)
        
        achievement = Achievement(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            achievement_type=AchievementType.MILESTONE,
            guild_id=guild_id,
            trigger_conditions=[trigger_condition],
            rewards=rewards,
            status=AchievementStatus.ACTIVE
        )
        
        return await achievement_service.create_achievement(achievement)
    
    @pytest.mark.asyncio
    async def test_new_user_journey(self, discord_bot_simulation):
        """測試新用戶的完整成就歷程"""
        env = discord_bot_simulation
        services = env["services"]
        guild_id = env["guild_id"]
        user_id = 987654321
        
        achievement_service = services["achievement"]
        economy_service = services["economy"]
        
        # 1. 新用戶加入伺服器，創建經濟帳戶
        try:
            await economy_service.create_account(
                guild_id=guild_id,
                account_type=AccountType.USER,
                user_id=user_id,
                initial_balance=0.0
            )
        except Exception:
            # 帳戶可能已經存在，重置餘額
            try:
                account = await economy_service.get_account(f"user_{user_id}_{guild_id}")
                if account:
                    await economy_service.update_balance(f"user_{user_id}_{guild_id}", 0.0, "測試重置")
            except Exception:
                pass
        
        # 2. 用戶發送第一條訊息 - 應該觸發 "破冰者" 成就
        message_event = {
            "type": "message_sent",
            "user_id": user_id,
            "guild_id": guild_id,
            "message_id": "msg_001",
            "timestamp": datetime.now().isoformat()
        }
        
        triggered = await achievement_service.process_event_triggers(message_event)
        assert "first_message" in triggered, "第一條訊息應該觸發 '破冰者' 成就"
        
        # 檢查成就進度
        progress = await achievement_service.get_user_progress(user_id, "first_message")
        assert progress.completed, "'破冰者' 成就應該已完成"
        
        # 檢查經濟獎勵
        account = await economy_service.get_account(f"user_{user_id}_{guild_id}")
        assert account.balance == 50.0, f"帳戶餘額應該是50，實際是{account.balance}"
        
        # 3. 用戶繼續發送訊息到達10條 - 應該觸發 "健談者" 成就
        for i in range(2, 11):
            message_event["message_id"] = f"msg_{i:03d}"
            triggered = await achievement_service.process_event_triggers(message_event)
        
        # 檢查最新觸發的成就
        assert "active_chatter" in triggered, "第10條訊息應該觸發 '健談者' 成就"
        
        # 檢查成就進度
        progress = await achievement_service.get_user_progress(user_id, "active_chatter")
        assert progress.completed, "'健談者' 成就應該已完成"
        
        # 檢查經濟獎勵（50 + 200 = 250）
        account = await economy_service.get_account(f"user_{user_id}_{guild_id}")
        assert account.balance == 250.0, f"帳戶餘額應該是250，實際是{account.balance}"
        
        # 4. 繼續發送到100條訊息 - 應該觸發 "訊息大師" 成就
        for i in range(11, 101):
            message_event["message_id"] = f"msg_{i:03d}"
            triggered = await achievement_service.process_event_triggers(message_event)
        
        assert "message_master" in triggered, "第100條訊息應該觸發 '訊息大師' 成就"
        
        # 檢查最終帳戶餘額（50 + 200 + 1000 = 1250）
        account = await economy_service.get_account(f"user_{user_id}_{guild_id}")
        assert account.balance == 1250.0, f"最終帳戶餘額應該是1250，實際是{account.balance}"
        
        # 5. 檢查用戶的所有成就
        user_achievements = await achievement_service.get_user_achievements(user_id, guild_id)
        completed_achievements = [a for a in user_achievements if a.completed]
        assert len(completed_achievements) == 3, f"用戶應該完成3個成就，實際完成{len(completed_achievements)}"
        
        # 6. 檢查徽章收集
        db_manager = achievement_service.db_manager
        badges = await db_manager.fetchall(
            "SELECT * FROM user_badges WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        )
        assert len(badges) == 3, f"用戶應該有3個徽章，實際有{len(badges)}"
        
        print(f"\n✅ 新用戶歷程測試完成:")
        print(f"   - 發送訊息數: 100")
        print(f"   - 完成成就數: {len(completed_achievements)}")
        print(f"   - 獲得徽章數: {len(badges)}")
        print(f"   - 最終餘額: {account.balance}")
    
    @pytest.mark.asyncio
    async def test_concurrent_users(self, discord_bot_simulation):
        """測試多用戶並行觸發成就"""
        env = discord_bot_simulation
        services = env["services"]
        guild_id = env["guild_id"]
        
        achievement_service = services["achievement"]
        economy_service = services["economy"]
        
        # 創建10個並行用戶
        user_ids = [1000 + i for i in range(10)]
        
        # 為每個用戶創建經濟帳戶
        for user_id in user_ids:
            try:
                await economy_service.create_account(
                    guild_id=guild_id,
                    account_type=AccountType.USER,
                    user_id=user_id,
                    initial_balance=0.0
                )
            except Exception:
                # 帳戶可能已經存在，重置餘額
                try:
                    account = await economy_service.get_account(f"user_{user_id}_{guild_id}")
                    if account:
                        await economy_service.update_balance(f"user_{user_id}_{guild_id}", 0.0, "測試重置")
                except Exception:
                    pass
        
        # 並行發送訊息
        async def user_activity(user_id):
            for i in range(15):  # 每個用戶發送15條訊息
                message_event = {
                    "type": "message_sent",
                    "user_id": user_id,
                    "guild_id": guild_id,
                    "message_id": f"user_{user_id}_msg_{i}",
                    "timestamp": datetime.now().isoformat()
                }
                await achievement_service.process_event_triggers(message_event)
        
        # 同時執行所有用戶活動
        await asyncio.gather(*[user_activity(user_id) for user_id in user_ids])
        
        # 檢查結果
        total_balance = 0.0
        total_achievements = 0
        
        for user_id in user_ids:
            # 檢查帳戶餘額
            account = await economy_service.get_account(f"user_{user_id}_{guild_id}")
            total_balance += account.balance
            
            # 檢查成就完成情況
            user_achievements = await achievement_service.get_user_achievements(user_id, guild_id)
            completed = [a for a in user_achievements if a.completed]
            total_achievements += len(completed)
            
            # 每個用戶發送15條訊息，應該完成2個成就（破冰者+健談者）
            assert len(completed) == 2, f"用戶{user_id}應該完成2個成就，實際完成{len(completed)}"
            assert account.balance == 250.0, f"用戶{user_id}帳戶餘額應該是250，實際是{account.balance}"
        
        print(f"\n✅ 並行用戶測試完成:")
        print(f"   - 用戶數量: {len(user_ids)}")
        print(f"   - 總成就數: {total_achievements}")
        print(f"   - 總餘額: {total_balance}")
        print(f"   - 平均成就數: {total_achievements / len(user_ids)}")
    
    @pytest.mark.asyncio
    async def test_achievement_system_performance(self, discord_bot_simulation):
        """測試成就系統在高負載下的效能"""
        env = discord_bot_simulation
        services = env["services"]
        guild_id = env["guild_id"]
        
        achievement_service = services["achievement"]
        economy_service = services["economy"]
        
        user_id = 999999
        
        # 創建經濟帳戶
        try:
            await economy_service.create_account(
                guild_id=guild_id,
                account_type=AccountType.USER,
                user_id=user_id,
                initial_balance=0.0
            )
        except Exception:
            # 帳戶可能已經存在，重置餘額
            try:
                account = await economy_service.get_account(f"user_{user_id}_{guild_id}")
                if account:
                    await economy_service.update_balance(f"user_{user_id}_{guild_id}", 0.0, "測試重置")
            except Exception:
                pass
        
        # 測量處理1000個事件的時間
        start_time = datetime.now()
        
        for i in range(1000):
            message_event = {
                "type": "message_sent",
                "user_id": user_id,
                "guild_id": guild_id,
                "message_id": f"perf_test_msg_{i}",
                "timestamp": datetime.now().isoformat()
            }
            await achievement_service.process_event_triggers(message_event)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 檢查效能要求（應該在合理時間內完成）
        events_per_second = 1000 / duration
        
        print(f"\n📊 效能測試結果:")
        print(f"   - 處理1000個事件耗時: {duration:.2f}秒")
        print(f"   - 處理速度: {events_per_second:.2f}事件/秒")
        
        # 基本效能要求：至少能處理10事件/秒
        assert events_per_second >= 10, f"處理速度過慢: {events_per_second:.2f}事件/秒"
        
        # 檢查最終狀態
        account = await economy_service.get_account(f"user_{user_id}_{guild_id}")
        user_achievements = await achievement_service.get_user_achievements(user_id, guild_id)
        completed = [a for a in user_achievements if a.completed]
        
        print(f"   - 完成成就數: {len(completed)}")
        print(f"   - 最終餘額: {account.balance}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])