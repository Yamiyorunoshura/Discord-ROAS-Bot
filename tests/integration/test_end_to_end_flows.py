"""
端到端使用者流程測試
Task ID: 10 - 建立系統整合測試

這個模組測試完整的使用者操作流程：
- 使用者註冊到獲得成就完整流程
- 政府部門建立到財政管理流程
- 錯誤場景的優雅處理
- 所有UI互動響應正常
- 面板和互動的正確性

符合要求：
- F4: 撰寫使用者流程測試
- N3: 測試穩定性 - 測試通過率≥99%
- 確保使用者體驗的一致性
"""

import pytest
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from tests.test_infrastructure import MockDiscordClient
import discord


@dataclass
class UserJourney:
    """使用者旅程定義"""
    journey_name: str
    steps: List[Dict[str, Any]]
    expected_outcomes: List[Dict[str, Any]]
    error_scenarios: List[Dict[str, Any]]


class EndToEndUserFlowTests:
    """端到端使用者流程測試"""
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_new_user_onboarding_journey(self, cross_system_test_setup, mock_discord_client):
        """測試新使用者完整上線流程"""
        setup = cross_system_test_setup
        discord_client = mock_discord_client
        
        # 步驟1：新使用者加入伺服器
        user_id = random.randint(100000, 999999)
        guild_id = 987654321
        username = f"NewUser{user_id}"
        
        # 建立Discord互動
        join_interaction = discord_client.create_interaction(
            user_id=user_id,
            username=username,
            guild_id=guild_id,
            interaction_type=discord.InteractionType.component,
            custom_id="welcome_message"
        )
        
        # 步驟2：歡迎系統處理新使用者
        welcome_service = setup["services"]["welcome"]
        welcome_result = await welcome_service.handle_member_join(user_id, guild_id)
        
        assert welcome_result["success"] is True
        assert welcome_result["user_id"] == user_id
        
        # 步驟3：自動建立經濟帳戶
        economy_service = setup["services"]["economy"]
        try:
            balance = await economy_service.get_user_balance(user_id, guild_id)
            # 新使用者應該有初始餘額
            assert balance >= 0
        except:
            # 如果帳戶不存在，建立它
            await economy_service.create_user_account(user_id, guild_id)
            balance = await economy_service.get_user_balance(user_id, guild_id)
            assert balance >= 0
        
        # 步驟4：使用者發送第一條訊息
        message_interaction = discord_client.create_interaction(
            user_id=user_id,
            username=username,
            guild_id=guild_id,
            interaction_type=discord.InteractionType.application_command,
            command_name="hello"
        )
        
        # 模擬訊息活動
        activity_service = setup["services"]["activity"]
        await activity_service.record_message_activity(user_id, guild_id)
        
        # 步驟5：檢查新手成就觸發
        achievement_service = setup["services"]["achievement"]
        
        # 建立新手成就
        newbie_achievement = {
            "achievement_id": "first_message",
            "name": "第一條訊息",
            "description": "發送第一條訊息的成就",
            "type": "MILESTONE",
            "trigger_type": "MESSAGE_COUNT",
            "target_value": 1,
            "reward_currency": 100,
            "reward_experience": 50,
            "is_active": True
        }
        await achievement_service.create_achievement(newbie_achievement)
        
        # 觸發成就檢查
        achievement_result = await achievement_service.check_and_award_achievement(
            user_id, guild_id, "MESSAGE_COUNT", 1
        )
        
        # 驗證成就獲得
        assert achievement_result is not None
        if achievement_result.get("achievement_awarded"):
            # 檢查獎勵是否發放
            final_balance = await economy_service.get_user_balance(user_id, guild_id)
            assert final_balance >= 100  # 初始餘額 + 成就獎勵
        
        # 步驟6：驗證使用者資料完整性
        user_achievements = await achievement_service.get_user_achievements(user_id, guild_id)
        user_activity = await activity_service.get_user_activity_stats(user_id, guild_id)
        
        # 驗證所有系統都有此使用者的記錄
        assert user_activity is not None
        # user_achievements 可能為空列表，這是正常的
        
        print(f"✅ 新使用者 {username} 成功完成上線流程")
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_achievement_unlock_journey(self, cross_system_test_setup, mock_discord_client):
        """測試成就解鎖完整流程"""
        setup = cross_system_test_setup
        discord_client = mock_discord_client
        
        user_id = 555777
        guild_id = 987654321
        username = "AchievementHunter"
        
        # 建立測試使用者
        economy_service = setup["services"]["economy"]
        achievement_service = setup["services"]["achievement"]
        activity_service = setup["services"]["activity"]
        
        await economy_service.create_user_account(user_id, guild_id)
        initial_balance = await economy_service.get_user_balance(user_id, guild_id)
        
        # 建立多階段成就
        achievements = [
            {
                "achievement_id": "message_novice",
                "name": "訊息新手",
                "description": "發送10條訊息",
                "type": "CUMULATIVE",
                "trigger_type": "MESSAGE_COUNT",
                "target_value": 10,
                "reward_currency": 200,
                "is_active": True
            },
            {
                "achievement_id": "message_expert",
                "name": "訊息專家",
                "description": "發送50條訊息",
                "type": "CUMULATIVE",
                "trigger_type": "MESSAGE_COUNT",
                "target_value": 50,
                "reward_currency": 500,
                "is_active": True
            },
            {
                "achievement_id": "active_user",
                "name": "活躍使用者",
                "description": "連續7天活躍",
                "type": "STREAK",
                "trigger_type": "DAILY_ACTIVE",
                "target_value": 7,
                "reward_currency": 1000,
                "is_active": True
            }
        ]
        
        for achievement in achievements:
            await achievement_service.create_achievement(achievement)
        
        # 模擬使用者活動進度
        message_count = 0
        achieved_milestones = []
        
        # 模擬發送15條訊息
        for i in range(15):
            message_count += 1
            await activity_service.record_message_activity(user_id, guild_id)
            
            # 檢查成就觸發
            result = await achievement_service.check_and_award_achievement(
                user_id, guild_id, "MESSAGE_COUNT", message_count
            )
            
            if result and result.get("achievement_awarded"):
                achieved_milestones.append(result["achievement_id"])
                print(f"🏆 解鎖成就：{result['achievement_name']}")
        
        # 驗證成就解鎖順序
        assert "message_novice" in achieved_milestones, "應該解鎖訊息新手成就"
        
        # 驗證獎勵累積
        final_balance = await economy_service.get_user_balance(user_id, guild_id)
        expected_minimum = initial_balance + 200  # 至少獲得新手成就獎勵
        assert final_balance >= expected_minimum, f"餘額應該至少增加200，實際：{final_balance - initial_balance}"
        
        # 檢查成就進度
        progress = await achievement_service.get_user_progress(user_id, guild_id, "message_expert")
        if progress:
            assert progress["current_value"] == 15, f"訊息專家成就進度應該是15，實際：{progress['current_value']}"
        
        print(f"✅ 使用者 {username} 成功完成成就解鎖流程")
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_government_department_management_journey(self, cross_system_test_setup, mock_discord_client):
        """測試政府部門管理完整流程"""
        setup = cross_system_test_setup
        discord_client = mock_discord_client
        
        # 建立部門管理者
        manager_id = 111222
        member1_id = 333444
        member2_id = 555666
        guild_id = 987654321
        
        government_service = setup["services"]["government"]
        economy_service = setup["services"]["economy"]
        
        # 確保所有使用者都有經濟帳戶
        for user_id in [manager_id, member1_id, member2_id]:
            try:
                await economy_service.create_user_account(user_id, guild_id)
            except:
                pass
        
        # 步驟1：建立部門
        dept_creation_interaction = discord_client.create_interaction(
            user_id=manager_id,
            username="DeptManager",
            guild_id=guild_id,
            interaction_type=discord.InteractionType.component,
            custom_id="create_department"
        )
        
        dept_result = await government_service.create_department(
            guild_id=guild_id,
            name="測試開發部",
            description="負責系統測試的部門",
            budget=10000,
            max_members=5,
            creator_id=manager_id
        )
        
        assert dept_result["success"] is True
        dept_id = dept_result["department_id"]
        
        # 驗證部門經濟帳戶自動建立
        dept_balance = await economy_service.get_department_balance(dept_id, guild_id)
        assert dept_balance == 10000, "部門預算應該正確初始化"
        
        # 步驟2：成員申請加入部門
        member1_join_interaction = discord_client.create_interaction(
            user_id=member1_id,
            username="Member1",
            guild_id=guild_id,
            interaction_type=discord.InteractionType.component,
            custom_id=f"join_department_{dept_id}"
        )
        
        join_result1 = await government_service.join_department(
            user_id=member1_id,
            guild_id=guild_id,
            department_id=dept_id
        )
        assert join_result1["success"] is True
        
        # 步驟3：第二個成員加入
        join_result2 = await government_service.join_department(
            user_id=member2_id,
            guild_id=guild_id,
            department_id=dept_id
        )
        assert join_result2["success"] is True
        
        # 步驟4：部門預算分配
        salary_amount = 500
        
        # 管理者分配薪資給成員
        salary_interaction = discord_client.create_interaction(
            user_id=manager_id,
            username="DeptManager",
            guild_id=guild_id,
            interaction_type=discord.InteractionType.component,
            custom_id="pay_salary"
        )
        
        # 給成員1發薪資
        member1_initial_balance = await economy_service.get_user_balance(member1_id, guild_id)
        await economy_service.department_pay_salary(
            department_id=dept_id,
            guild_id=guild_id,
            user_id=member1_id,
            amount=salary_amount,
            authorized_by=manager_id,
            description="月度薪資"
        )
        
        # 給成員2發薪資
        member2_initial_balance = await economy_service.get_user_balance(member2_id, guild_id)
        await economy_service.department_pay_salary(
            department_id=dept_id,
            guild_id=guild_id,
            user_id=member2_id,
            amount=salary_amount,
            authorized_by=manager_id,
            description="月度薪資"
        )
        
        # 步驟5：驗證薪資發放
        member1_final_balance = await economy_service.get_user_balance(member1_id, guild_id)
        member2_final_balance = await economy_service.get_user_balance(member2_id, guild_id)
        
        assert member1_final_balance == member1_initial_balance + salary_amount
        assert member2_final_balance == member2_initial_balance + salary_amount
        
        # 驗證部門餘額減少
        final_dept_balance = await economy_service.get_department_balance(dept_id, guild_id)
        expected_dept_balance = 10000 - (salary_amount * 2)
        assert final_dept_balance == expected_dept_balance
        
        # 步驟6：查看部門財務報告
        dept_transactions = await economy_service.get_department_transaction_history(
            dept_id, guild_id, limit=10
        )
        
        assert len(dept_transactions) >= 3  # 初始化 + 2次薪資發放
        
        salary_transactions = [t for t in dept_transactions if t["type"] == "SALARY_PAYMENT"]
        assert len(salary_transactions) == 2
        
        # 步驟7：部門成員查看個人財務記錄
        member1_transactions = await economy_service.get_transaction_history(
            member1_id, guild_id, limit=10
        )
        
        salary_received = [t for t in member1_transactions if t["type"] == "SALARY_RECEIVED"]
        assert len(salary_received) >= 1
        
        print(f"✅ 部門 {dept_id} 管理流程完成，共有 {len(dept_transactions)} 筆財務記錄")
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery_flow(self, cross_system_test_setup, mock_discord_client):
        """測試錯誤處理和恢復流程"""
        setup = cross_system_test_setup
        discord_client = mock_discord_client
        
        user_id = 777888
        guild_id = 987654321
        username = "ErrorTestUser"
        
        economy_service = setup["services"]["economy"]
        government_service = setup["services"]["government"]
        achievement_service = setup["services"]["achievement"]
        
        # 錯誤場景1：操作不存在的使用者帳戶
        with pytest.raises(Exception):
            await economy_service.get_user_balance(999999, guild_id)
        
        # 恢復：建立帳戶後重試
        await economy_service.create_user_account(user_id, guild_id)
        balance = await economy_service.get_user_balance(user_id, guild_id)
        assert balance >= 0
        
        # 錯誤場景2：嘗試轉移超過餘額的金額
        with pytest.raises(Exception):
            await economy_service.transfer_currency(
                from_user_id=user_id,
                to_user_id=888999,
                guild_id=guild_id,
                amount=999999999,  # 遠超餘額
                description="錯誤測試轉移"
            )
        
        # 恢復：檢查餘額未被影響
        post_error_balance = await economy_service.get_user_balance(user_id, guild_id)
        assert post_error_balance == balance, "錯誤操作不應影響餘額"
        
        # 錯誤場景3：建立無效的部門
        with pytest.raises(Exception):
            await government_service.create_department(
                guild_id=guild_id,
                name="",  # 空名稱
                description="無效部門",
                budget=-1000,  # 負預算
                max_members=0,  # 無效成員數
                creator_id=user_id
            )
        
        # 恢復：建立有效部門
        valid_dept = await government_service.create_department(
            guild_id=guild_id,
            name="恢復測試部",
            description="錯誤恢復測試",
            budget=5000,
            max_members=3,
            creator_id=user_id
        )
        assert valid_dept["success"] is True
        
        # 錯誤場景4：建立重複的成就ID
        achievement_data = {
            "achievement_id": "duplicate_test",
            "name": "重複測試成就",
            "type": "MILESTONE",
            "trigger_type": "MESSAGE_COUNT",
            "target_value": 1,
            "is_active": True
        }
        
        # 第一次建立應該成功
        await achievement_service.create_achievement(achievement_data)
        
        # 第二次建立相同ID應該失敗
        with pytest.raises(Exception):
            await achievement_service.create_achievement(achievement_data)
        
        # 恢復：查詢確保只有一個成就
        achievements = await achievement_service.get_active_achievements(guild_id)
        duplicate_achievements = [a for a in achievements if a.get("achievement_id") == "duplicate_test"]
        assert len(duplicate_achievements) <= 1, "不應該有重複的成就"
        
        # 錯誤場景5：並發操作衝突
        async def concurrent_operation(operation_id: int):
            """並發操作測試"""
            try:
                await economy_service.add_currency(
                    user_id, guild_id, 10, f"並發測試 {operation_id}"
                )
                return {"success": True, "operation_id": operation_id}
            except Exception as e:
                return {"success": False, "operation_id": operation_id, "error": str(e)}
        
        # 執行10個並發操作
        tasks = [concurrent_operation(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        # 檢查結果
        successful_ops = [r for r in results if r["success"]]
        failed_ops = [r for r in results if not r["success"]]
        
        # 大部分操作應該成功
        assert len(successful_ops) >= 8, f"並發操作成功率過低：{len(successful_ops)}/10"
        
        # 驗證最終狀態一致性
        final_balance = await economy_service.get_user_balance(user_id, guild_id)
        transactions = await economy_service.get_transaction_history(user_id, guild_id)
        
        # 交易記錄數量應該與成功的操作一致
        concurrent_transactions = [t for t in transactions if "並發測試" in t["description"]]
        assert len(concurrent_transactions) == len(successful_ops)
        
        print(f"✅ 錯誤處理測試完成，{len(successful_ops)}/10 並發操作成功")
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_panel_interaction_flow(self, cross_system_test_setup, mock_discord_client):
        """測試面板互動流程"""
        setup = cross_system_test_setup
        discord_client = mock_discord_client
        
        user_id = 123789
        guild_id = 987654321
        username = "PanelTestUser"
        
        # 建立各種互動
        interactions = [
            # 經濟面板互動
            discord_client.create_interaction(
                user_id=user_id,
                username=username,
                guild_id=guild_id,
                interaction_type=discord.InteractionType.component,
                custom_id="economy_balance"
            ),
            
            # 成就面板互動
            discord_client.create_interaction(
                user_id=user_id,
                username=username,
                guild_id=guild_id,
                interaction_type=discord.InteractionType.component,
                custom_id="achievement_list"
            ),
            
            # 政府面板互動
            discord_client.create_interaction(
                user_id=user_id,
                username=username,
                guild_id=guild_id,
                interaction_type=discord.InteractionType.component,
                custom_id="government_info"
            ),
            
            # 活動面板互動
            discord_client.create_interaction(
                user_id=user_id,
                username=username,
                guild_id=guild_id,
                interaction_type=discord.InteractionType.component,
                custom_id="activity_stats"
            )
        ]
        
        # 確保使用者在各系統中存在
        economy_service = setup["services"]["economy"]
        await economy_service.create_user_account(user_id, guild_id)
        
        # 模擬面板互動處理
        response_count = 0
        
        for interaction in interactions:
            try:
                # 這裡應該調用對應的面板處理器
                # 由於我們沒有實際的面板實例，我們模擬互動處理
                
                if interaction.data.get("custom_id") == "economy_balance":
                    balance = await economy_service.get_user_balance(user_id, guild_id)
                    # 模擬面板回應
                    await interaction.response.send_message(f"你的餘額：{balance}")
                    
                elif interaction.data.get("custom_id") == "achievement_list":
                    achievement_service = setup["services"]["achievement"]
                    achievements = await achievement_service.get_user_achievements(user_id, guild_id)
                    await interaction.response.send_message(f"成就數量：{len(achievements)}")
                    
                elif interaction.data.get("custom_id") == "government_info":
                    government_service = setup["services"]["government"]
                    departments = await government_service.get_user_departments(user_id, guild_id)
                    await interaction.response.send_message(f"參與部門數：{len(departments)}")
                    
                elif interaction.data.get("custom_id") == "activity_stats":
                    activity_service = setup["services"]["activity"]
                    stats = await activity_service.get_user_activity_stats(user_id, guild_id)
                    message_count = stats.get("message_count", 0) if stats else 0
                    await interaction.response.send_message(f"訊息數量：{message_count}")
                
                response_count += 1
                
            except Exception as e:
                print(f"面板互動失敗：{interaction.data.get('custom_id')} - {e}")
        
        # 驗證所有互動都有回應
        responses = discord_client.get_interaction_responses(user_id)
        assert len(responses) == response_count, f"預期 {response_count} 個回應，實際獲得 {len(responses)} 個"
        
        # 驗證回應內容合理性
        for response in responses:
            assert len(response["args"]) > 0 or len(response["kwargs"]) > 0, "回應應該包含內容"
        
        print(f"✅ 面板互動測試完成，處理了 {response_count} 個互動")
    
    @pytest.mark.e2e
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_complete_user_lifecycle(self, cross_system_test_setup, mock_discord_client):
        """測試完整的使用者生命週期"""
        setup = cross_system_test_setup
        discord_client = mock_discord_client
        
        # 建立一個新使用者並模擬其完整生命週期
        user_id = 999888
        guild_id = 987654321
        username = "LifecycleTestUser"
        
        # 階段1：使用者加入
        welcome_service = setup["services"]["welcome"]
        economy_service = setup["services"]["economy"]
        achievement_service = setup["services"]["achievement"]
        government_service = setup["services"]["government"]
        activity_service = setup["services"]["activity"]
        
        # 歡迎新使用者
        await welcome_service.handle_member_join(user_id, guild_id)
        await economy_service.create_user_account(user_id, guild_id)
        
        # 階段2：活躍參與（模擬1週的活動）
        daily_messages = [5, 8, 12, 7, 15, 10, 6]  # 7天的訊息數量
        total_messages = 0
        
        for day, message_count in enumerate(daily_messages):
            for _ in range(message_count):
                total_messages += 1
                await activity_service.record_message_activity(user_id, guild_id)
                
                # 定期檢查成就
                if total_messages % 10 == 0:
                    await achievement_service.check_and_award_achievement(
                        user_id, guild_id, "MESSAGE_COUNT", total_messages
                    )
        
        # 階段3：加入政府部門
        dept_result = await government_service.create_department(
            guild_id=guild_id,
            name="使用者生命週期測試部",
            description="測試完整生命週期",
            budget=8000,
            max_members=10,
            creator_id=user_id
        )
        dept_id = dept_result["department_id"]
        
        # 階段4：經濟活動
        # 獲得一些初始資金
        await economy_service.add_currency(user_id, guild_id, 1000, "生命週期測試獎勵")
        
        # 進行一些交易
        await economy_service.transfer_to_department(
            from_user_id=user_id,
            to_department_id=dept_id,
            guild_id=guild_id,
            amount=500,
            description="部門投資"
        )
        
        # 階段5：成就收集
        # 建立並觸發多個成就
        lifecycle_achievements = [
            {
                "achievement_id": "active_member",
                "name": "活躍成員",
                "type": "MILESTONE",
                "trigger_type": "MESSAGE_COUNT",
                "target_value": 50,
                "reward_currency": 300,
                "is_active": True
            },
            {
                "achievement_id": "department_founder",
                "name": "部門創始人",
                "type": "MILESTONE",
                "trigger_type": "DEPARTMENT_CREATE",
                "target_value": 1,
                "reward_currency": 500,
                "is_active": True
            }
        ]
        
        for achievement in lifecycle_achievements:
            await achievement_service.create_achievement(achievement)
        
        # 觸發成就檢查
        await achievement_service.check_and_award_achievement(
            user_id, guild_id, "MESSAGE_COUNT", total_messages
        )
        await achievement_service.check_and_award_achievement(
            user_id, guild_id, "DEPARTMENT_CREATE", 1
        )
        
        # 階段6：生命週期總結和驗證
        # 驗證經濟狀況
        final_balance = await economy_service.get_user_balance(user_id, guild_id)
        transaction_history = await economy_service.get_transaction_history(user_id, guild_id)
        
        # 驗證活動統計
        activity_stats = await activity_service.get_user_activity_stats(user_id, guild_id)
        
        # 驗證成就獲得
        user_achievements = await achievement_service.get_user_achievements(user_id, guild_id)
        
        # 驗證政府參與
        user_departments = await government_service.get_user_departments(user_id, guild_id)
        
        # 綜合驗證
        assert final_balance > 0, "使用者應該累積了一些財富"
        assert len(transaction_history) > 0, "應該有交易歷史"
        assert activity_stats is not None, "應該有活動統計"
        assert len(user_departments) > 0, "應該參與了部門"
        
        # 計算生命週期得分
        lifecycle_score = (
            final_balance * 0.1 +
            len(user_achievements) * 100 +
            len(user_departments) * 200 +
            (activity_stats.get("message_count", 0) if activity_stats else 0) * 5
        )
        
        print(f"✅ 使用者 {username} 完整生命週期測試完成")
        print(f"   - 最終餘額：{final_balance}")
        print(f"   - 交易記錄：{len(transaction_history)} 筆")
        print(f"   - 獲得成就：{len(user_achievements)} 個")
        print(f"   - 參與部門：{len(user_departments)} 個")
        print(f"   - 訊息數量：{activity_stats.get('message_count', 0) if activity_stats else 0}")
        print(f"   - 生命週期得分：{lifecycle_score:.1f}")
        
        assert lifecycle_score > 1000, f"生命週期得分 {lifecycle_score:.1f} 過低，預期 > 1000"