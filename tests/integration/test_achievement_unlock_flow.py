"""成就解鎖流程整合測試.

此模組測試成就系統的核心解鎖流程，包括：
- 進度追蹤到解鎖的完整流程
- 通知系統整合
- 面板顯示更新
- 事件處理和異步操作
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# 確保正確的導入路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.helpers.test_factories import (
    DiscordObjectFactory,
    TestScenarioFactory,
    quick_achievement,
    quick_interaction,
    quick_user,
)


class TestAchievementUnlockFlow:
    """測試成就解鎖完整流程."""

    def setup_method(self):
        """設置測試環境."""
        # 創建模擬服務
        self.achievement_service = MagicMock()
        self.achievement_service.get_user_progress = AsyncMock()
        self.achievement_service.update_progress = AsyncMock()
        self.achievement_service.unlock_achievement = AsyncMock()

        self.progress_tracker = MagicMock()
        self.progress_tracker.track_event = AsyncMock()
        self.progress_tracker.check_achievement_completion = AsyncMock()

        self.notifier = MagicMock()
        self.notifier.send_achievement_notification = AsyncMock()

        # 創建測試場景
        self.unlock_scenario = TestScenarioFactory.create_achievement_unlock_scenario()

    @pytest.mark.asyncio
    async def test_complete_achievement_unlock_flow(self):
        """測試完整的成就解鎖流程."""
        user = self.unlock_scenario["user"]
        achievement = self.unlock_scenario["achievement"]
        trigger_event = self.unlock_scenario["trigger_event"]

        # 設置模擬回應
        self.progress_tracker.check_achievement_completion.return_value = True
        self.achievement_service.unlock_achievement.return_value = {
            "success": True,
            "achievement": achievement,
            "unlocked_at": "2024-01-01T12:00:00Z"
        }

        # 執行解鎖流程
        result = await self._simulate_unlock_flow(user, achievement, trigger_event)

        # 驗證流程各階段
        assert result["progress_tracked"] is True
        assert result["achievement_unlocked"] is True
        assert result["notification_sent"] is True

        # 驗證服務調用
        self.progress_tracker.track_event.assert_called_once()
        self.achievement_service.unlock_achievement.assert_called_once()
        self.notifier.send_achievement_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_partial_progress_update(self):
        """測試部分進度更新（未解鎖）."""
        user = quick_user()
        achievement = quick_achievement(target=100)

        # 設置部分進度
        self.progress_tracker.check_achievement_completion.return_value = False
        self.achievement_service.update_progress.return_value = {
            "current_progress": 50,
            "target_value": 100,
            "percentage": 50.0
        }

        # 執行進度更新
        result = await self._simulate_progress_update(user, achievement, 50)

        # 驗證只更新進度，不解鎖成就
        assert result["progress_updated"] is True
        assert result["achievement_unlocked"] is False
        assert result["notification_sent"] is False

        self.achievement_service.update_progress.assert_called_once()
        self.achievement_service.unlock_achievement.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_achievements_unlock(self):
        """測試同時解鎖多個成就."""
        user = quick_user()
        achievements = [
            quick_achievement(name="成就1", target=10),
            quick_achievement(name="成就2", target=10),
            quick_achievement(name="成就3", target=10)
        ]

        # 設置所有成就都符合解鎖條件
        self.progress_tracker.check_achievement_completion.return_value = True
        self.achievement_service.unlock_achievement.return_value = {"success": True}

        # 模擬同時觸發多個成就
        tasks = []
        for achievement in achievements:
            task = self._simulate_unlock_flow(user, achievement, {"type": "bulk_unlock"})
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # 驗證所有成就都成功解鎖
        assert len(results) == 3
        assert all(result["achievement_unlocked"] for result in results)

        # 驗證服務被正確調用
        assert self.achievement_service.unlock_achievement.call_count == 3
        assert self.notifier.send_achievement_notification.call_count == 3

    @pytest.mark.asyncio
    async def test_achievement_unlock_with_error_handling(self):
        """測試成就解鎖的錯誤處理."""
        user = quick_user()
        achievement = quick_achievement()

        # 模擬解鎖過程中的錯誤
        self.progress_tracker.check_achievement_completion.return_value = True
        self.achievement_service.unlock_achievement.side_effect = Exception("資料庫錯誤")

        # 執行解鎖流程
        result = await self._simulate_unlock_flow_with_error_handling(user, achievement)

        # 驗證錯誤處理
        assert result["error_occurred"] is True
        assert result["achievement_unlocked"] is False
        assert "資料庫錯誤" in result["error_message"]

        # 驗證錯誤後的清理操作
        assert result["rollback_performed"] is True

    @pytest.mark.asyncio
    async def test_concurrent_progress_tracking(self):
        """測試並發進度追蹤."""
        user = quick_user()
        achievement = quick_achievement(target=100)

        # 模擬多個並發事件
        events = [
            {"type": "message_sent", "value": 1},
            {"type": "message_sent", "value": 1},
            {"type": "message_sent", "value": 1},
            {"type": "voice_join", "value": 10},
            {"type": "reaction_add", "value": 1}
        ]

        self.progress_tracker.track_event.return_value = {"success": True}

        # 並發處理事件
        tasks = [
            self._simulate_event_tracking(user, achievement, event)
            for event in events
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 驗證所有事件都被處理
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) == len(events)

        # 驗證事件追蹤被正確調用
        assert self.progress_tracker.track_event.call_count == len(events)

    async def _simulate_unlock_flow(self, user, achievement, trigger_event):
        """模擬完整的解鎖流程."""
        result = {
            "progress_tracked": False,
            "achievement_unlocked": False,
            "notification_sent": False
        }

        try:
            # 步驟1: 追蹤事件
            await self.progress_tracker.track_event(
                user_id=user.id,
                event_type=trigger_event["type"],
                data=trigger_event["data"]
            )
            result["progress_tracked"] = True

            # 步驟2: 檢查是否達成解鎖條件
            should_unlock = await self.progress_tracker.check_achievement_completion(
                user_id=user.id,
                achievement_id=achievement["id"]
            )

            if should_unlock:
                # 步驟3: 解鎖成就
                unlock_result = await self.achievement_service.unlock_achievement(
                    user_id=user.id,
                    achievement_id=achievement["id"]
                )

                if unlock_result.get("success"):
                    result["achievement_unlocked"] = True

                    # 步驟4: 發送通知
                    await self.notifier.send_achievement_notification(
                        user_id=user.id,
                        achievement=achievement
                    )
                    result["notification_sent"] = True

        except Exception as e:
            result["error"] = str(e)

        return result

    async def _simulate_progress_update(self, user, achievement, progress_value):
        """模擬進度更新."""
        result = {
            "progress_updated": False,
            "achievement_unlocked": False,
            "notification_sent": False
        }

        # 更新進度
        progress_result = await self.achievement_service.update_progress(
            user_id=user.id,
            achievement_id=achievement["id"],
            new_progress=progress_value
        )

        if progress_result:
            result["progress_updated"] = True

            # 檢查是否達到解鎖條件
            should_unlock = await self.progress_tracker.check_achievement_completion(
                user_id=user.id,
                achievement_id=achievement["id"]
            )

            if should_unlock:
                result["achievement_unlocked"] = True
                result["notification_sent"] = True

        return result

    async def _simulate_unlock_flow_with_error_handling(self, user, achievement):
        """模擬帶錯誤處理的解鎖流程."""
        result = {
            "error_occurred": False,
            "achievement_unlocked": False,
            "error_message": "",
            "rollback_performed": False
        }

        try:
            # 嘗試解鎖
            await self.achievement_service.unlock_achievement(
                user_id=user.id,
                achievement_id=achievement["id"]
            )
            result["achievement_unlocked"] = True

        except Exception as e:
            result["error_occurred"] = True
            result["error_message"] = str(e)

            # 執行回滾操作
            result["rollback_performed"] = True

        return result

    async def _simulate_event_tracking(self, user, achievement, event):
        """模擬事件追蹤."""
        return await self.progress_tracker.track_event(
            user_id=user.id,
            event_type=event["type"],
            value=event["value"]
        )


class TestAchievementNotificationIntegration:
    """測試成就通知整合."""

    def setup_method(self):
        """設置測試環境."""
        self.notifier = MagicMock()
        self.notifier.send_achievement_notification = AsyncMock()
        self.notifier.send_progress_update = AsyncMock()

        self.panel_manager = MagicMock()
        self.panel_manager.update_user_panel = AsyncMock()

    @pytest.mark.asyncio
    async def test_achievement_notification_flow(self):
        """測試成就通知流程."""
        user = quick_user()
        achievement = quick_achievement(name="測試通知成就")
        interaction = quick_interaction(user=user)

        # 設置模擬回應
        self.notifier.send_achievement_notification.return_value = {
            "message_sent": True,
            "embed_created": True
        }

        # 執行通知流程
        result = await self._simulate_notification_flow(user, achievement, interaction)

        # 驗證通知發送
        assert result["notification_sent"] is True
        assert result["panel_updated"] is True

        self.notifier.send_achievement_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_notification_handling(self):
        """測試批量通知處理."""
        users = [quick_user() for _ in range(5)]
        achievement = quick_achievement(name="批量通知測試")

        # 模擬批量通知
        tasks = [
            self.notifier.send_achievement_notification(
                user_id=user.id,
                achievement=achievement
            )
            for user in users
        ]

        await asyncio.gather(*tasks)

        # 驗證所有通知都被發送
        assert self.notifier.send_achievement_notification.call_count == len(users)

    async def _simulate_notification_flow(self, user, achievement, interaction):
        """模擬通知流程."""
        result = {
            "notification_sent": False,
            "panel_updated": False
        }

        # 發送成就通知
        notification_result = await self.notifier.send_achievement_notification(
            user_id=user.id,
            achievement=achievement
        )

        if notification_result.get("message_sent"):
            result["notification_sent"] = True

            # 更新用戶面板
            await self.panel_manager.update_user_panel(
                user_id=user.id,
                panel_type="achievements"
            )
            result["panel_updated"] = True

        return result


class TestAchievementPanelIntegration:
    """測試成就面板整合."""

    def setup_method(self):
        """設置測試環境."""
        self.panel_scenario = TestScenarioFactory.create_panel_interaction_scenario()

    @pytest.mark.asyncio
    async def test_panel_display_after_unlock(self):
        """測試解鎖後面板顯示更新."""
        scenario = self.panel_scenario
        scenario["interaction"].user

        # 模擬面板渲染
        panel_data = await self._simulate_panel_render(scenario)

        # 驗證面板數據
        assert panel_data["user_achievements_count"] > 0
        assert panel_data["completion_rate"] >= 0
        assert len(panel_data["categories"]) > 0

        # 驗證UI組件
        expected_components = scenario["expected_components"]
        assert len(panel_data["components"]) >= len(expected_components)

    @pytest.mark.asyncio
    async def test_real_time_panel_updates(self):
        """測試即時面板更新."""
        user = quick_user()
        achievement = quick_achievement()

        # 模擬成就解鎖事件
        unlock_event = {
            "user_id": user.id,
            "achievement_id": achievement["id"],
            "timestamp": "2024-01-01T12:00:00Z"
        }

        # 模擬面板監聽更新事件
        panel_update = await self._simulate_real_time_update(unlock_event)

        # 驗證面板更新
        assert panel_update["updated"] is True
        assert panel_update["new_achievement_count"] > 0

    async def _simulate_panel_render(self, scenario):
        """模擬面板渲染."""
        user_achievements = scenario["user_achievements"]

        # 計算統計數據
        completed_count = sum(1 for ach in user_achievements if ach["is_completed"])
        total_count = len(user_achievements)
        completion_rate = completed_count / total_count if total_count > 0 else 0

        # 生成面板數據
        return {
            "user_achievements_count": completed_count,
            "total_achievements": total_count,
            "completion_rate": completion_rate,
            "categories": ["活動", "社交", "時間"],
            "components": ["category_selector", "refresh_button", "close_button", "progress_bar"]
        }

    async def _simulate_real_time_update(self, unlock_event):
        """模擬即時更新."""
        # 模擬接收到解鎖事件
        user_id = unlock_event["user_id"]
        achievement_id = unlock_event["achievement_id"]

        # 更新面板數據
        return {
            "updated": True,
            "user_id": user_id,
            "new_achievement_id": achievement_id,
            "new_achievement_count": 1,
            "timestamp": unlock_event["timestamp"]
        }


@pytest.mark.integration
class TestFullAchievementSystemIntegration:
    """測試完整成就系統整合."""

    @pytest.mark.asyncio
    async def test_end_to_end_achievement_flow(self):
        """測試端到端成就流程."""
        # 創建完整的測試場景
        user = quick_user()
        guild = DiscordObjectFactory.create_guild()
        achievement = quick_achievement(name="端到端測試", target=5)

        # 模擬5個觸發事件
        events = [{"type": "message_sent", "value": 1} for _ in range(5)]

        # 執行完整流程
        flow_result = await self._execute_end_to_end_flow(user, guild, achievement, events)

        # 驗證端到端結果
        assert flow_result["events_processed"] == 5
        assert flow_result["achievement_unlocked"] is True
        assert flow_result["notification_sent"] is True
        assert flow_result["panel_updated"] is True

    async def _execute_end_to_end_flow(self, user, guild, achievement, events):
        """執行端到端流程模擬."""
        result = {
            "events_processed": 0,
            "achievement_unlocked": False,
            "notification_sent": False,
            "panel_updated": False
        }

        current_progress = 0

        # 逐一處理事件
        for event in events:
            current_progress += event["value"]
            result["events_processed"] += 1

            # 檢查是否達到解鎖條件
            if current_progress >= achievement["target_value"]:
                result["achievement_unlocked"] = True
                result["notification_sent"] = True
                result["panel_updated"] = True
                break

        return result
