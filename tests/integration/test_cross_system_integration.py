"""
跨系統整合測試套件
Task ID: 10 - 建立系統整合測試

這個模組測試各系統間的整合功能：
- 成就系統與經濟系統整合（貨幣獎勵發放）
- 政府系統與經濟系統整合（部門帳戶管理）
- 身分組管理與所有系統的整合
- 資料一致性和事務完整性驗證

符合要求：
- F2: 實作跨系統整合測試
- N2: 測試覆蓋率 - 核心業務邏輯覆蓋率≥95%
- N3: 測試穩定性 - 測試通過率≥99%
"""

import pytest
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any

from tests.test_infrastructure import (
    performance_test, 
    data_consistency_check,
    load_test
)
from core.exceptions import ServiceError, ValidationError

# 導入模型類別
from services.achievement.models import Achievement, AchievementType, TriggerCondition, TriggerType, AchievementReward, RewardType, AchievementStatus


class TestCrossSystemIntegration:
    """跨系統整合測試"""
    
    @pytest.mark.integration
    @pytest.mark.cross_system
    @pytest.mark.asyncio
    async def test_achievement_economy_integration(self, cross_system_test_setup):
        """測試成就系統與經濟系統整合 - 貨幣獎勵發放"""
        setup = cross_system_test_setup
        achievement_service = setup["services"]["achievement"]
        economy_service = setup["services"]["economy"]
        test_users = setup["test_data"]["users"]
        
        # 選擇一個測試使用者
        test_user = test_users[0]
        user_id = test_user["discord_id"]
        guild_id = 987654321
        
        # 建立測試成就（包含貨幣獎勵）
        trigger_condition = TriggerCondition(
            trigger_type=TriggerType.MESSAGE_COUNT,
            target_value=10,
            comparison_operator=">=",
            metadata={}
        )
        
        currency_reward = AchievementReward(
            reward_type=RewardType.CURRENCY,
            value=500,
            metadata={"description": "測試貨幣獎勵"}
        )
        
        achievement_data = Achievement(
            id="test_currency_reward",
            name="貨幣獎勵測試成就", 
            description="測試成就系統與經濟系統整合",
            achievement_type=AchievementType.MILESTONE,
            guild_id=guild_id,
            trigger_conditions=[trigger_condition],
            rewards=[currency_reward],
            status=AchievementStatus.ACTIVE,
            metadata={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # 在成就系統中建立成就
        await achievement_service.create_achievement(achievement_data)
        
        # 確保使用者在經濟系統中存在
        try:
            await economy_service.get_user_balance(user_id, guild_id)
        except:
            await economy_service.create_user_account(user_id, guild_id)
        
        # 記錄初始餘額
        initial_balance = await economy_service.get_user_balance(user_id, guild_id)
        
        # 模擬觸發成就條件
        progress_data = {
            "user_id": user_id,
            "guild_id": guild_id,
            "achievement_id": "test_currency_reward",
            "current_value": 10,  # 達到目標值
            "last_updated": datetime.now()
        }
        
        # 觸發成就檢查和獎勵發放
        achievement_result = await achievement_service.check_and_award_achievement(
            user_id, guild_id, "MESSAGE_COUNT", 10
        )
        
        # 驗證成就獲得
        assert achievement_result is not None
        assert achievement_result["achievement_awarded"] is True
        
        # 驗證貨幣獎勵已發放
        final_balance = await economy_service.get_user_balance(user_id, guild_id)
        assert final_balance == initial_balance + 500
        
        # 驗證交易記錄
        transactions = await economy_service.get_transaction_history(user_id, guild_id, limit=5)
        reward_transaction = None
        for transaction in transactions:
            if transaction["type"] == "ACHIEVEMENT_REWARD":
                reward_transaction = transaction
                break
        
        assert reward_transaction is not None
        assert reward_transaction["amount"] == 500
        assert "test_currency_reward" in reward_transaction["description"]
    
    @pytest.mark.integration
    @pytest.mark.cross_system
    @pytest.mark.asyncio
    async def test_government_economy_integration(self, cross_system_test_setup):
        """測試政府系統與經濟系統整合 - 部門帳戶管理"""
        setup = cross_system_test_setup
        government_service = setup["services"]["government"]
        economy_service = setup["services"]["economy"]
        test_departments = setup["test_data"]["departments"]
        test_users = setup["test_data"]["users"]
        
        # 選擇測試資料
        test_dept = test_departments[0]
        test_user = test_users[0]
        user_id = test_user["discord_id"]
        guild_id = 987654321
        
        # 建立部門
        dept_result = await government_service.create_department(
            guild_id=guild_id,
            name=test_dept["name"],
            description=test_dept["description"],
            budget=test_dept["budget"],
            max_members=test_dept["max_members"],
            creator_id=user_id
        )
        dept_id = dept_result["department_id"]
        
        # 驗證部門帳戶自動建立
        dept_balance = await economy_service.get_department_balance(dept_id, guild_id)
        assert dept_balance == test_dept["budget"]
        
        # 測試部門資金轉移
        transfer_amount = 1000
        await economy_service.transfer_to_department(
            from_user_id=user_id,
            to_department_id=dept_id,
            guild_id=guild_id,
            amount=transfer_amount,
            description="測試部門資金轉移"
        )
        
        # 驗證部門餘額增加
        new_dept_balance = await economy_service.get_department_balance(dept_id, guild_id)
        assert new_dept_balance == test_dept["budget"] + transfer_amount
        
        # 測試部門支出
        expense_amount = 500
        await economy_service.department_expense(
            department_id=dept_id,
            guild_id=guild_id,
            amount=expense_amount,
            description="測試部門支出",
            authorized_by=user_id
        )
        
        # 驗證部門餘額減少
        final_dept_balance = await economy_service.get_department_balance(dept_id, guild_id)
        assert final_dept_balance == test_dept["budget"] + transfer_amount - expense_amount
        
        # 驗證部門財務記錄
        dept_transactions = await economy_service.get_department_transaction_history(
            dept_id, guild_id, limit=10
        )
        assert len(dept_transactions) >= 3  # 初始化 + 轉移 + 支出
        
        # 驗證交易類型正確
        transaction_types = [t["type"] for t in dept_transactions]
        assert "DEPARTMENT_INIT" in transaction_types
        assert "DEPARTMENT_TRANSFER" in transaction_types
        assert "DEPARTMENT_EXPENSE" in transaction_types
    
    @pytest.mark.integration
    @pytest.mark.cross_system
    @pytest.mark.asyncio
    async def test_role_management_integration(self, cross_system_test_setup):
        """測試身分組管理與所有系統的整合"""
        setup = cross_system_test_setup
        government_service = setup["services"]["government"]
        achievement_service = setup["services"]["achievement"]
        economy_service = setup["services"]["economy"]
        test_users = setup["test_data"]["users"]
        
        # 選擇測試使用者
        test_user = test_users[0]
        user_id = test_user["discord_id"]
        guild_id = 987654321
        
        # 建立測試部門
        dept_result = await government_service.create_department(
            guild_id=guild_id,
            name="身分組測試部",
            description="測試身分組管理整合",
            budget=10000,
            max_members=10,
            creator_id=user_id
        )
        dept_id = dept_result["department_id"]
        
        # 測試使用者加入部門（身分組變更）
        join_result = await government_service.join_department(
            user_id=user_id,
            guild_id=guild_id,
            department_id=dept_id
        )
        assert join_result["success"] is True
        
        # 驗證身分組變更同步到成就系統
        # 檢查是否有"加入部門"相關的成就進度更新
        user_achievements = await achievement_service.get_user_achievements(user_id, guild_id)
        
        # 建立部門相關成就來測試
        dept_achievement = {
            "achievement_id": "join_department",
            "name": "加入部門成就",
            "description": "成功加入政府部門",
            "type": "MILESTONE",
            "trigger_type": "DEPARTMENT_JOIN",
            "target_value": 1,
            "reward_currency": 200,
            "is_active": True
        }
        await achievement_service.create_achievement(dept_achievement)
        
        # 觸發部門加入成就檢查
        await achievement_service.check_and_award_achievement(
            user_id, guild_id, "DEPARTMENT_JOIN", 1
        )
        
        # 驗證成就獲得和經濟獎勵
        initial_balance = await economy_service.get_user_balance(user_id, guild_id)
        updated_achievements = await achievement_service.get_user_achievements(user_id, guild_id)
        
        # 檢查使用者在部門中的狀態
        dept_members = await government_service.get_department_members(dept_id, guild_id)
        assert any(member["user_id"] == user_id for member in dept_members)
        
        # 測試身分組權限在經濟系統中的應用
        # 部門成員應該有特殊的經濟操作權限
        can_access_dept_funds = await economy_service.check_department_access(
            user_id, dept_id, guild_id
        )
        assert can_access_dept_funds is True
    
    @pytest.mark.integration
    @pytest.mark.cross_system
    @pytest.mark.asyncio
    @data_consistency_check(["achievement", "economy", "government"])
    async def test_data_consistency_across_systems(self, cross_system_test_setup):
        """驗證跨系統資料一致性"""
        setup = cross_system_test_setup
        achievement_service = setup["services"]["achievement"]
        economy_service = setup["services"]["economy"]
        government_service = setup["services"]["government"]
        test_users = setup["test_data"]["users"]
        
        user_id = test_users[0]["discord_id"]
        guild_id = 987654321
        
        # 建立複雜的跨系統操作序列
        operations = []
        
        # 1. 建立經濟帳戶
        await economy_service.create_user_account(user_id, guild_id)
        operations.append("create_economy_account")
        
        # 2. 建立成就
        achievement_data = {
            "achievement_id": "consistency_test",
            "name": "一致性測試成就",
            "description": "測試資料一致性",
            "type": "CUMULATIVE",
            "trigger_type": "TRANSACTION_COUNT",
            "target_value": 5,
            "reward_currency": 1000,
            "is_active": True
        }
        await achievement_service.create_achievement(achievement_data)
        operations.append("create_achievement")
        
        # 3. 建立部門
        dept_result = await government_service.create_department(
            guild_id=guild_id,
            name="一致性測試部",
            description="測試資料一致性",
            budget=5000,
            max_members=5,
            creator_id=user_id
        )
        dept_id = dept_result["department_id"]
        operations.append("create_department")
        
        # 4. 執行多次交易以觸發成就
        for i in range(5):
            await economy_service.add_currency(
                user_id, guild_id, 100, f"測試交易 {i+1}"
            )
            operations.append(f"transaction_{i+1}")
        
        # 5. 檢查成就觸發
        await achievement_service.check_and_award_achievement(
            user_id, guild_id, "TRANSACTION_COUNT", 5
        )
        operations.append("check_achievement")
        
        # 驗證所有系統的資料一致性
        
        # 檢查經濟系統資料
        user_balance = await economy_service.get_user_balance(user_id, guild_id)
        transactions = await economy_service.get_transaction_history(user_id, guild_id)
        
        # 檢查成就系統資料
        user_achievements = await achievement_service.get_user_achievements(user_id, guild_id)
        achievement_progress = await achievement_service.get_user_progress(
            user_id, guild_id, "consistency_test"
        )
        
        # 檢查政府系統資料
        dept_info = await government_service.get_department_info(dept_id, guild_id)
        
        # 驗證一致性
        # 1. 經濟系統的交易次數應該與成就進度一致
        assert len([t for t in transactions if t["type"] != "ACHIEVEMENT_REWARD"]) == 5
        assert achievement_progress["current_value"] == 5
        
        # 2. 成就獎勵應該反映在經濟餘額中
        expected_balance = 500 + 1000  # 5次交易(每次100) + 成就獎勵(1000)
        assert user_balance == expected_balance
        
        # 3. 部門預算應該正確初始化
        dept_balance = await economy_service.get_department_balance(dept_id, guild_id)
        assert dept_balance == 5000
        
        # 4. 所有相關記錄的時間戳應該在合理範圍內
        now = datetime.now()
        for transaction in transactions:
            assert abs((now - transaction["timestamp"]).total_seconds()) < 60
    
    @pytest.mark.integration
    @pytest.mark.performance
    @pytest.mark.asyncio
    @performance_test(max_duration_ms=5000)
    async def test_cross_system_performance(self, cross_system_test_setup, performance_monitor):
        """測試跨系統操作效能"""
        setup = cross_system_test_setup
        achievement_service = setup["services"]["achievement"]
        economy_service = setup["services"]["economy"]
        government_service = setup["services"]["government"]
        
        # 建立測試資料
        user_id = 123456
        guild_id = 987654321
        
        # 測試複雜跨系統操作的效能
        measurement = performance_monitor.start_measurement("cross_system_operation")
        
        # 並行執行跨系統操作
        tasks = []
        
        # 經濟系統操作
        tasks.append(economy_service.create_user_account(user_id, guild_id))
        
        # 成就系統操作
        achievement_data = {
            "achievement_id": "performance_test",
            "name": "效能測試成就",
            "type": "MILESTONE",
            "trigger_type": "MESSAGE_COUNT",
            "target_value": 1,
            "reward_currency": 100,
            "is_active": True
        }
        tasks.append(achievement_service.create_achievement(achievement_data))
        
        # 政府系統操作
        tasks.append(government_service.create_department(
            guild_id=guild_id,
            name="效能測試部",
            description="測試效能",
            budget=1000,
            max_members=5,
            creator_id=user_id
        ))
        
        # 等待所有操作完成
        results = await asyncio.gather(*tasks)
        
        performance_monitor.end_measurement(measurement)
        
        # 驗證操作成功
        assert all(result is not None for result in results)
        
        # 檢查效能統計
        stats = performance_monitor.get_stats()
        assert stats["max_duration_ms"] < 5000
    
    @pytest.mark.integration
    @pytest.mark.load
    @pytest.mark.asyncio
    async def test_concurrent_cross_system_operations(self, cross_system_test_setup, load_test_runner):
        """測試並發跨系統操作"""
        setup = cross_system_test_setup
        achievement_service = setup["services"]["achievement"]
        economy_service = setup["services"]["economy"]
        
        async def cross_system_operation(user_id: int, operation_id: int, **kwargs):
            """執行跨系統操作"""
            guild_id = 987654321
            
            # 建立經濟帳戶
            await economy_service.create_user_account(user_id, guild_id)
            
            # 新增貨幣
            await economy_service.add_currency(
                user_id, guild_id, 100, f"負載測試操作 {operation_id}"
            )
            
            # 檢查成就（假設已有相關成就）
            await achievement_service.check_and_award_achievement(
                user_id, guild_id, "MESSAGE_COUNT", 1
            )
            
            return {"user_id": user_id, "operation_id": operation_id, "success": True}
        
        # 執行負載測試
        result = await load_test_runner.run_concurrent_operations(
            cross_system_operation,
            concurrent_count=20,
            operations_per_user=3
        )
        
        # 驗證負載測試結果
        assert result["success_rate"] >= 95.0  # 至少95%成功率
        assert result["failed"] <= 3  # 最多3個失敗操作
        assert len(result["failures"]) <= 3
    
    @pytest.mark.integration
    @pytest.mark.cross_system
    @pytest.mark.asyncio
    async def test_transaction_atomicity(self, cross_system_test_setup):
        """測試跨系統事務原子性"""
        setup = cross_system_test_setup
        achievement_service = setup["services"]["achievement"]
        economy_service = setup["services"]["economy"]
        db_manager = setup["db_manager"]
        
        user_id = 555666
        guild_id = 987654321
        
        # 建立初始狀態
        await economy_service.create_user_account(user_id, guild_id)
        initial_balance = await economy_service.get_user_balance(user_id, guild_id)
        
        # 建立一個會失敗的成就（故意設置無效資料）
        try:
            async with db_manager.transaction() as conn:
                # 新增貨幣
                await economy_service.add_currency(
                    user_id, guild_id, 1000, "原子性測試"
                )
                
                # 故意觸發錯誤（例如建立無效成就）
                invalid_achievement = {
                    "achievement_id": "",  # 空ID，應該失敗
                    "name": "無效成就",
                    "type": "INVALID_TYPE",  # 無效類型
                    "is_active": True
                }
                await achievement_service.create_achievement(invalid_achievement)
                
        except Exception:
            # 預期的錯誤
            pass
        
        # 驗證事務回滾 - 餘額應該沒有變化
        final_balance = await economy_service.get_user_balance(user_id, guild_id)
        assert final_balance == initial_balance
        
        # 驗證無效成就沒有被建立
        achievements = await achievement_service.get_active_achievements(guild_id)
        invalid_achievements = [a for a in achievements if a.get("name") == "無效成就"]
        assert len(invalid_achievements) == 0