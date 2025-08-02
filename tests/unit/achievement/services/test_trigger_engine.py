"""TriggerEngine 單元測試.

此模組測試觸發引擎的核心功能，包含：
- 成就觸發條件檢查測試
- 自動觸發機制測試
- 事件處理測試
- 批量觸發檢查測試

遵循 AAA 模式（Arrange, Act, Assert）和測試最佳實踐。
"""

from datetime import datetime, timedelta

import pytest

from src.cogs.achievement.database.models import (
    Achievement,
    AchievementType,
)
from src.cogs.achievement.services.trigger_engine import TriggerEngine
from tests.unit.achievement.services.conftest import (
    create_test_achievement,
    create_test_category,
    create_trigger_context,
    pytest_mark_unit,
)


@pytest_mark_unit
class TestTriggerEngine:
    """TriggerEngine 單元測試類別."""

    # ==========================================================================
    # 初始化和配置測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_engine_initialization(self, mock_repository, mock_progress_tracker):
        """測試觸發引擎初始化."""
        # Arrange & Act
        engine = TriggerEngine(mock_repository, mock_progress_tracker)

        # Assert
        assert engine._repository == mock_repository
        assert engine._progress_tracker == mock_progress_tracker

    @pytest.mark.asyncio
    async def test_engine_context_manager(self, mock_repository, mock_progress_tracker):
        """測試觸發引擎上下文管理器."""
        # Arrange
        engine = TriggerEngine(mock_repository, mock_progress_tracker)

        # Act & Assert
        async with engine as ctx_engine:
            assert ctx_engine is engine

    # ==========================================================================
    # 成就觸發條件檢查測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_check_achievement_trigger_already_earned(self, trigger_engine, repository):
        """測試檢查已獲得成就的觸發條件."""
        # Arrange
        category = await create_test_category(repository, "earned_cat")
        achievement = await create_test_achievement(repository, category.id, "earned_ach")
        user_id = 123456789

        # 先頒發成就
        await repository.award_achievement(user_id, achievement.id)

        # Act
        should_trigger, reason = await trigger_engine.check_achievement_trigger(
            user_id=user_id,
            achievement_id=achievement.id,
            trigger_context=create_trigger_context()
        )

        # Assert
        assert should_trigger is False
        assert "用戶已獲得此成就" in reason

    @pytest.mark.asyncio
    async def test_check_achievement_trigger_inactive(self, trigger_engine, repository):
        """測試檢查未啟用成就的觸發條件."""
        # Arrange
        category = await create_test_category(repository, "inactive_trigger_cat")
        achievement = await create_test_achievement(repository, category.id, "inactive_trigger")

        # 停用成就
        await repository.update_achievement(achievement.id, {"is_active": False})

        user_id = 123456789

        # Act
        should_trigger, reason = await trigger_engine.check_achievement_trigger(
            user_id=user_id,
            achievement_id=achievement.id,
            trigger_context=create_trigger_context()
        )

        # Assert
        assert should_trigger is False
        assert "成就未啟用" in reason

    @pytest.mark.asyncio
    async def test_check_counter_trigger_success(self, trigger_engine, repository):
        """測試計數型成就觸發條件檢查成功."""
        # Arrange
        category = await create_test_category(repository, "counter_trigger_cat")
        achievement = Achievement(
            name="計數觸發測試",
            description="計數型成就觸發測試",
            category_id=category.id,
            type=AchievementType.COUNTER,
            criteria={"target_value": 50, "counter_field": "messages"},
            points=100,
            role_reward=None,
            is_hidden=False
        )
        achievement = await repository.create_achievement(achievement)

        user_id = 123456789

        # 設定進度達到目標值
        await repository.update_progress(
            user_id=user_id,
            achievement_id=achievement.id,
            current_value=50.0
        )

        # Act
        should_trigger, reason = await trigger_engine.check_achievement_trigger(
            user_id=user_id,
            achievement_id=achievement.id,
            trigger_context=create_trigger_context()
        )

        # Assert
        assert should_trigger is True
        assert "計數達到目標值 50" in reason

    @pytest.mark.asyncio
    async def test_check_counter_trigger_not_reached(self, trigger_engine, repository):
        """測試計數型成就觸發條件未達成."""
        # Arrange
        category = await create_test_category(repository, "counter_not_reached_cat")
        achievement = Achievement(
            name="計數未達成測試",
            description="計數型成就未達成測試",
            category_id=category.id,
            type=AchievementType.COUNTER,
            criteria={"target_value": 100, "counter_field": "messages"},
            points=100,
            role_reward=None,
            is_hidden=False
        )
        achievement = await repository.create_achievement(achievement)

        user_id = 123456789

        # 設定進度未達到目標值
        await repository.update_progress(
            user_id=user_id,
            achievement_id=achievement.id,
            current_value=30.0
        )

        # Act
        should_trigger, reason = await trigger_engine.check_achievement_trigger(
            user_id=user_id,
            achievement_id=achievement.id,
            trigger_context=create_trigger_context()
        )

        # Assert
        assert should_trigger is False
        assert "計數尚未達到目標值 (30.0/100)" in reason

    @pytest.mark.asyncio
    async def test_check_milestone_trigger_success(self, trigger_engine, repository):
        """測試里程碑型成就觸發條件檢查成功."""
        # Arrange
        category = await create_test_category(repository, "milestone_trigger_cat")
        achievement = Achievement(
            name="里程碑觸發測試",
            description="里程碑型成就觸發測試",
            category_id=category.id,
            type=AchievementType.MILESTONE,
            criteria={"target_value": 25, "milestone_type": "level"},
            points=200,
            role_reward="里程碑達人",
            is_hidden=False
        )
        achievement = await repository.create_achievement(achievement)

        user_id = 123456789

        # 設定觸發上下文，包含達到的里程碑值
        trigger_context = create_trigger_context(user_id=user_id, level=30)

        # Act
        should_trigger, reason = await trigger_engine.check_achievement_trigger(
            user_id=user_id,
            achievement_id=achievement.id,
            trigger_context=trigger_context
        )

        # Assert
        assert should_trigger is True
        assert "里程碑達到 level: 30" in reason

    @pytest.mark.asyncio
    async def test_check_time_based_trigger_success(self, trigger_engine, repository):
        """測試時間型成就觸發條件檢查成功."""
        # Arrange
        category = await create_test_category(repository, "time_trigger_cat")
        achievement = Achievement(
            name="時間觸發測試",
            description="時間型成就觸發測試",
            category_id=category.id,
            type=AchievementType.TIME_BASED,
            criteria={"target_value": 7, "time_unit": "days"},
            points=300,
            role_reward="時間管理大師",
            is_hidden=True
        )
        achievement = await repository.create_achievement(achievement)

        user_id = 123456789

        # 設定 7 天連續的進度資料
        today = datetime.now().date()
        streak_dates = [
            (today - timedelta(days=i)).isoformat()
            for i in range(6, -1, -1)  # 7 天連續
        ]

        await repository.update_progress(
            user_id=user_id,
            achievement_id=achievement.id,
            current_value=7.0,
            progress_data={"streak_dates": streak_dates}
        )

        # Act
        should_trigger, reason = await trigger_engine.check_achievement_trigger(
            user_id=user_id,
            achievement_id=achievement.id,
            trigger_context=create_trigger_context()
        )

        # Assert
        assert should_trigger is True
        assert "連續 7 天達到目標" in reason

    @pytest.mark.asyncio
    async def test_check_conditional_trigger_all_conditions_met(self, trigger_engine, repository):
        """測試條件型成就所有條件滿足的觸發檢查."""
        # Arrange
        category = await create_test_category(repository, "conditional_trigger_cat")
        achievement = Achievement(
            name="條件觸發測試",
            description="條件型成就觸發測試",
            category_id=category.id,
            type=AchievementType.CONDITIONAL,
            criteria={
                "target_value": 2,
                "require_all": True,
                "conditions": [
                    {"type": "metric_threshold", "metric": "level", "threshold": 10},
                    {"type": "metric_threshold", "metric": "messages", "threshold": 50}
                ]
            },
            points=400
        )
        achievement = await repository.create_achievement(achievement)

        user_id = 123456789

        # 設定觸發上下文，滿足所有條件
        trigger_context = create_trigger_context(user_id=user_id, level=15, messages=60)

        # Act
        should_trigger, reason = await trigger_engine.check_achievement_trigger(
            user_id=user_id,
            achievement_id=achievement.id,
            trigger_context=trigger_context
        )

        # Assert
        assert should_trigger is True
        assert "滿足所有條件" in reason

    @pytest.mark.asyncio
    async def test_check_conditional_trigger_partial_conditions(self, trigger_engine, repository):
        """測試條件型成就部分條件滿足的觸發檢查."""
        # Arrange
        category = await create_test_category(repository, "partial_conditional_cat")
        achievement = Achievement(
            name="部分條件測試",
            description="部分條件滿足測試",
            category_id=category.id,
            type=AchievementType.CONDITIONAL,
            criteria={
                "target_value": 2,
                "require_all": True,
                "conditions": [
                    {"type": "metric_threshold", "metric": "level", "threshold": 10},
                    {"type": "metric_threshold", "metric": "messages", "threshold": 100}
                ]
            },
            points=400
        )
        achievement = await repository.create_achievement(achievement)

        user_id = 123456789

        # 設定觸發上下文，只滿足部分條件
        trigger_context = create_trigger_context(user_id=user_id, level=15, messages=30)

        # Act
        should_trigger, reason = await trigger_engine.check_achievement_trigger(
            user_id=user_id,
            achievement_id=achievement.id,
            trigger_context=trigger_context
        )

        # Assert
        assert should_trigger is False
        assert "未滿足條件" in reason

    # ==========================================================================
    # 單一條件評估測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_evaluate_metric_threshold_condition(self, trigger_engine):
        """測試指標閾值條件評估."""
        # Arrange
        condition = {
            "type": "metric_threshold",
            "metric": "score",
            "threshold": 80,
            "operator": ">="
        }
        trigger_context = {"score": 85}

        # Act
        is_satisfied, reason = await trigger_engine._evaluate_single_condition(
            user_id=123456789,
            condition=condition,
            trigger_context=trigger_context
        )

        # Assert
        assert is_satisfied is True
        assert "score >= 80 (實際: 85)" in reason

    @pytest.mark.asyncio
    async def test_evaluate_achievement_dependency_condition(self, trigger_engine, repository):
        """測試成就依賴條件評估."""
        # Arrange
        category = await create_test_category(repository, "dependency_cat")
        prerequisite_achievement = await create_test_achievement(repository, category.id, "prerequisite")

        user_id = 123456789

        # 先頒發依賴的成就
        await repository.award_achievement(user_id, prerequisite_achievement.id)

        condition = {
            "type": "achievement_dependency",
            "achievement_id": prerequisite_achievement.id
        }

        # Act
        is_satisfied, reason = await trigger_engine._evaluate_single_condition(
            user_id=user_id,
            condition=condition,
            trigger_context={}
        )

        # Assert
        assert is_satisfied is True
        assert f"已獲得依賴成就 {prerequisite_achievement.id}" in reason

    @pytest.mark.asyncio
    async def test_evaluate_time_range_condition(self, trigger_engine):
        """測試時間範圍條件評估."""
        # Arrange
        now = datetime.now()
        start_time = (now - timedelta(hours=1)).isoformat()
        end_time = (now + timedelta(hours=1)).isoformat()

        condition = {
            "type": "time_range",
            "start_time": start_time,
            "end_time": end_time
        }

        # Act
        is_satisfied, reason = await trigger_engine._evaluate_single_condition(
            user_id=123456789,
            condition=condition,
            trigger_context={}
        )

        # Assert
        assert is_satisfied is True
        assert "在時間範圍內" in reason

    # ==========================================================================
    # 自動觸發機制測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_process_automatic_triggers_success(self, trigger_engine, repository):
        """測試自動觸發處理成功."""
        # Arrange
        category = await create_test_category(repository, "auto_trigger_cat")
        achievement = Achievement(
            name="自動觸發測試",
            description="自動觸發成就測試",
            category_id=category.id,
            type=AchievementType.COUNTER,
            criteria={"target_value": 1, "counter_field": "messages"},
            points=100
        )
        achievement = await repository.create_achievement(achievement)

        user_id = 123456789

        # 設定進度達到目標值
        await repository.update_progress(
            user_id=user_id,
            achievement_id=achievement.id,
            current_value=1.0
        )

        # Act
        newly_earned = await trigger_engine.process_automatic_triggers(
            user_id=user_id,
            trigger_event="message_sent",
            event_data=create_trigger_context(user_id=user_id, messages=1)
        )

        # Assert
        assert len(newly_earned) == 1
        assert newly_earned[0].achievement_id == achievement.id

    @pytest.mark.asyncio
    async def test_process_automatic_triggers_no_eligible_achievements(
        self,
        trigger_engine,
        repository
    ):
        """測試自動觸發處理無符合條件的成就."""
        # Arrange
        category = await create_test_category(repository, "no_eligible_cat")
        achievement = Achievement(
            name="不符合條件測試",
            description="不符合觸發條件的成就",
            category_id=category.id,
            type=AchievementType.COUNTER,
            criteria={"target_value": 100, "counter_field": "messages"},
            points=100
        )
        achievement = await repository.create_achievement(achievement)

        user_id = 123456789

        # 設定進度未達到目標值
        await repository.update_progress(
            user_id=user_id,
            achievement_id=achievement.id,
            current_value=10.0
        )

        # Act
        newly_earned = await trigger_engine.process_automatic_triggers(
            user_id=user_id,
            trigger_event="message_sent",
            event_data=create_trigger_context(user_id=user_id, messages=10)
        )

        # Assert
        assert len(newly_earned) == 0

    @pytest.mark.asyncio
    async def test_filter_achievements_by_event(self, trigger_engine, repository):
        """測試根據事件過濾成就."""
        # Arrange
        category = await create_test_category(repository, "filter_cat")

        counter_achievement = await create_test_achievement(
            repository, category.id, "counter", AchievementType.COUNTER
        )
        milestone_achievement = await create_test_achievement(
            repository, category.id, "milestone", AchievementType.MILESTONE
        )
        time_achievement = await create_test_achievement(
            repository, category.id, "time", AchievementType.TIME_BASED
        )

        all_achievements = [counter_achievement, milestone_achievement, time_achievement]

        # Act - 過濾訊息發送事件相關的成就（應該只有計數型）
        message_achievements = trigger_engine._filter_achievements_by_event(
            all_achievements, "message_sent"
        )

        # Act - 過濾每日登入事件相關的成就（應該只有時間型）
        login_achievements = trigger_engine._filter_achievements_by_event(
            all_achievements, "daily_login"
        )

        # Assert
        assert len(message_achievements) == 1
        assert message_achievements[0].type == AchievementType.COUNTER

        assert len(login_achievements) == 1
        assert login_achievements[0].type == AchievementType.TIME_BASED

    # ==========================================================================
    # 批量觸發檢查測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_batch_check_triggers_for_users(self, trigger_engine, repository):
        """測試批量用戶觸發檢查."""
        # Arrange
        category = await create_test_category(repository, "batch_trigger_cat")
        achievement = Achievement(
            name="批量觸發測試",
            description="批量觸發檢查測試",
            category_id=category.id,
            type=AchievementType.COUNTER,
            criteria={"target_value": 5, "counter_field": "actions"},
            points=100
        )
        achievement = await repository.create_achievement(achievement)

        user_ids = [111, 222, 333]

        # 為用戶設定不同的進度
        await repository.update_progress(111, achievement.id, 5.0)  # 達到目標
        await repository.update_progress(222, achievement.id, 3.0)  # 未達到目標
        await repository.update_progress(333, achievement.id, 8.0)  # 超過目標

        # Act
        results = await trigger_engine.batch_check_triggers_for_users(
            user_ids=user_ids,
            trigger_event="interaction",
            event_data=create_trigger_context(actions=1)
        )

        # Assert
        assert len(results) == 3
        assert len(results[111]) == 1  # 應該獲得成就
        assert len(results[222]) == 0  # 不應該獲得成就
        assert len(results[333]) == 1  # 應該獲得成就

    # ==========================================================================
    # 觸發事件處理測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_handle_trigger_event_success(self, trigger_engine, repository, progress_tracker):
        """測試處理觸發事件成功."""
        # Arrange
        category = await create_test_category(repository, "event_handler_cat")
        achievement = await create_test_achievement(
            repository, category.id, "event_handler", AchievementType.COUNTER
        )

        user_id = 123456789
        event_data = create_trigger_context(user_id=user_id, messages=1)

        # Act
        await trigger_engine.handle_trigger_event("message_sent", event_data)

        # Assert - 驗證進度已被更新（通過檢查是否有進度記錄）
        progress = await repository.get_user_progress(user_id, achievement.id)
        assert progress is not None
        assert progress.current_value > 0

    @pytest.mark.asyncio
    async def test_handle_trigger_event_missing_user_id(self, trigger_engine):
        """測試處理缺少用戶 ID 的觸發事件."""
        # Arrange
        event_data = {"action": "test"}  # 沒有 user_id

        # Act & Assert - 應該不會拋出異常，但會記錄警告
        await trigger_engine.handle_trigger_event("test_event", event_data)

    @pytest.mark.asyncio
    async def test_calculate_progress_increment(self, trigger_engine, repository):
        """測試進度增量計算."""
        # Arrange
        category = await create_test_category(repository, "increment_cat")

        counter_achievement = Achievement(
            name="計數增量測試",
            description="計數型成就增量測試",
            category_id=category.id,
            type=AchievementType.COUNTER,
            criteria={"target_value": 10},
            points=100
        )

        milestone_achievement = Achievement(
            name="里程碑增量測試",
            description="里程碑型成就增量測試",
            category_id=category.id,
            type=AchievementType.MILESTONE,
            criteria={"target_value": 50, "milestone_type": "exp"},
            points=200
        )

        # Act
        counter_increment = trigger_engine._calculate_progress_increment(
            counter_achievement, "message_sent", {}
        )

        milestone_increment = trigger_engine._calculate_progress_increment(
            milestone_achievement, "level_up", {"exp": 25}
        )

        # Assert
        assert counter_increment == 1.0  # 計數型成就每次增加 1
        assert milestone_increment == 25.0  # 里程碑型成就根據事件資料增加
