"""TriggerEngine 增強功能測試.

此模組測試 TriggerEngine 的增強功能,包含:
- 複雜計數型成就觸發邏輯測試
- 多階段里程碑成就測試
- 事件驅動觸發系統測試
- 效能優化功能測試

測試遵循 AAA 模式和現代測試最佳實踐.
"""

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.cogs.achievement.config.trigger_conditions import (
    AchievementTriggerConfig,
    TriggerCondition,
    TriggerConditionValidator,
)
from src.cogs.achievement.database.models import (
    Achievement,
    AchievementProgress,
    AchievementType,
    UserAchievement,
)
from src.cogs.achievement.services.trigger_engine import TriggerEngine


@pytest.mark.unit
class TestTriggerEngineEnhanced:
    """TriggerEngine 增強功能測試類別."""

    # ==========================================================================
    # 複雜計數型成就測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_counter_trigger_with_time_window(
        self, mock_repository, mock_progress_tracker
    ):
        """測試帶時間窗口的計數型成就觸發."""
        # Arrange
        engine = TriggerEngine(mock_repository, mock_progress_tracker)

        achievement = create_test_achievement(
            achievement_id=1,
            achievement_type=AchievementType.COUNTER,
            criteria={
                "target_value": 10,
                "counter_field": "message_count",
                "time_window": "7d",
            },
            name="Test Counter Achievement",
        )

        # 模擬時間窗口內的進度資料
        mock_progress = Mock()
        mock_progress.progress_data = {
            "windowed_events": [
                {"timestamp": datetime.now().isoformat(), "message_count": 5},
                {
                    "timestamp": (datetime.now() - timedelta(days=2)).isoformat(),
                    "message_count": 6,
                },
            ]
        }
        mock_repository.get_user_progress.return_value = mock_progress
        mock_repository.has_user_achievement.return_value = False

        trigger_context = {"message_count": 1, "event_type": "message_sent"}

        # Act
        result, reason = await engine._check_counter_trigger(
            user_id=123,
            achievement=achievement,
            criteria=achievement.criteria,
            trigger_context=trigger_context,
        )

        # Assert
        assert result is True
        assert "時間窗口內計數達到目標值" in reason
        mock_repository.get_user_progress.assert_called_once_with(123, 1)

    @pytest.mark.asyncio
    async def test_counter_trigger_compound_conditions(
        self, mock_repository, mock_progress_tracker
    ):
        """測試複合條件計數型成就觸發."""
        # Arrange
        engine = TriggerEngine(mock_repository, mock_progress_tracker)

        achievement = create_test_achievement(
            achievement_id=2,
            achievement_type=AchievementType.COUNTER,
            criteria={
                "conditions": [
                    {"field": "message_count", "target_value": 50, "operator": ">="},
                    {"field": "reaction_count", "target_value": 20, "operator": ">="},
                ],
                "logic_operator": "AND",
                "target_value": 1,  # 添加必要的 target_value
            },
            name="Complex Counter Achievement",
        )

        # 模擬進度資料
        mock_progress = Mock()
        mock_progress.current_value = 60.0
        mock_repository.get_user_progress.return_value = mock_progress
        mock_repository.has_user_achievement.return_value = False

        trigger_context = {
            "message_count": 60,
            "reaction_count": 25,
            "event_type": "message_sent",
        }

        # Act
        result, reason = await engine._check_counter_trigger(
            user_id=123,
            achievement=achievement,
            criteria=achievement.criteria,
            trigger_context=trigger_context,
        )

        # Assert
        assert result is True
        assert "滿足所有複合條件" in reason

    @pytest.mark.asyncio
    async def test_parse_time_window(self, mock_repository, mock_progress_tracker):
        """測試時間窗口解析功能."""
        # Arrange
        engine = TriggerEngine(mock_repository, mock_progress_tracker)

        # Act & Assert
        assert engine._parse_time_window("7d") == 7 * 24 * 3600
        assert engine._parse_time_window("24h") == 24 * 3600
        assert engine._parse_time_window("30m") == 30 * 60
        assert engine._parse_time_window("invalid") == 0

    # ==========================================================================
    # 多階段里程碑成就測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_multi_stage_milestone_trigger(
        self, mock_repository, mock_progress_tracker
    ):
        """測試多階段里程碑成就觸發."""
        # Arrange
        engine = TriggerEngine(mock_repository, mock_progress_tracker)

        achievement = create_test_achievement(
            achievement_id=3,
            achievement_type=AchievementType.MILESTONE,
            criteria={
                "milestone_type": "multi_stage",
                "stages": [
                    {
                        "condition": {
                            "type": "metric",
                            "metric": "level",
                            "threshold": 5,
                        }
                    },
                    {
                        "condition": {
                            "type": "metric",
                            "metric": "level",
                            "threshold": 10,
                        }
                    },
                    {
                        "condition": {
                            "type": "metric",
                            "metric": "level",
                            "threshold": 20,
                        }
                    },
                ],
                "target_value": 3,  # 三個階段
            },
            name="Multi-Stage Milestone",
        )

        # 模擬當前階段為 2(最後階段)
        mock_progress = Mock()
        mock_progress.progress_data = {"current_stage": 2}
        mock_repository.get_user_progress.return_value = mock_progress
        mock_repository.has_user_achievement.return_value = False

        trigger_context = {"level": 20, "event_type": "level_up"}

        # Act
        result, reason = await engine._check_milestone_trigger(
            user_id=123,
            achievement=achievement,
            criteria=achievement.criteria,
            trigger_context=trigger_context,
        )

        # Assert
        assert result is True
        assert "完成最終階段" in reason

    @pytest.mark.asyncio
    async def test_event_triggered_milestone(
        self, mock_repository, mock_progress_tracker
    ):
        """測試事件觸發里程碑成就."""
        # Arrange
        engine = TriggerEngine(mock_repository, mock_progress_tracker)

        achievement = create_test_achievement(
            achievement_id=4,
            achievement_type=AchievementType.MILESTONE,
            criteria={
                "milestone_type": "event_triggered",
                "required_events": ["message_sent", "reaction_added", "voice_joined"],
                "event_sequence": True,
                "target_value": 3,  # 三個事件
            },
            name="Event Sequence Milestone",
        )

        # 模擬事件歷史
        mock_progress = Mock()
        mock_progress.progress_data = {
            "event_history": [
                {"event_type": "message_sent", "timestamp": "2023-01-01T10:00:00"},
                {"event_type": "reaction_added", "timestamp": "2023-01-01T10:01:00"},
            ]
        }
        mock_repository.get_user_progress.return_value = mock_progress
        mock_repository.has_user_achievement.return_value = False

        trigger_context = {"event_type": "voice_joined"}

        # Act
        result, reason = await engine._check_milestone_trigger(
            user_id=123,
            achievement=achievement,
            criteria=achievement.criteria,
            trigger_context=trigger_context,
        )

        # Assert
        assert result is True
        assert "事件序列完成" in reason

    # ==========================================================================
    # 時間型成就增強測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_time_based_trigger_enhanced(
        self, mock_repository, mock_progress_tracker
    ):
        """測試增強的時間型成就觸發."""
        # Arrange
        engine = TriggerEngine(mock_repository, mock_progress_tracker)

        achievement = create_test_achievement(
            achievement_id=5,
            achievement_type=AchievementType.TIME_BASED,
            criteria={"target_value": 7, "time_unit": "days"},
            name="Consecutive Days Achievement",
        )

        # 模擬7天連續活動的進度資料
        today = datetime.now()
        streak_dates = [
            (today - timedelta(days=i)).date().isoformat() for i in range(7)
        ]

        mock_progress = Mock()
        mock_progress.progress_data = {"streak_dates": streak_dates}
        mock_repository.get_user_progress.return_value = mock_progress
        mock_repository.has_user_achievement.return_value = False

        trigger_context = {"event_type": "daily_login"}

        # Act
        result, reason = await engine._check_time_based_trigger(
            user_id=123,
            achievement=achievement,
            criteria=achievement.criteria,
            trigger_context=trigger_context,
        )

        # Assert
        assert result is True
        assert "連續 7 天達到目標" in reason

    # ==========================================================================
    # 條件型成就增強測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_conditional_trigger_enhanced(
        self, mock_repository, mock_progress_tracker
    ):
        """測試增強的條件型成就觸發."""
        # Arrange
        engine = TriggerEngine(mock_repository, mock_progress_tracker)

        achievement = create_test_achievement(
            achievement_id=6,
            achievement_type=AchievementType.CONDITIONAL,
            criteria={
                "conditions": [
                    {
                        "type": "metric_threshold",
                        "metric": "message_count",
                        "threshold": 100,
                        "operator": ">=",
                    },
                    {"type": "achievement_dependency", "achievement_id": 1},
                    {
                        "type": "time_range",
                        "start_time": "2023-01-01T00:00:00",
                        "end_time": "2023-12-31T23:59:59",
                    },
                ],
                "require_all": True,
                "target_value": 1,  # 條件型成就的目標
            },
            name="Complex Conditional Achievement",
        )

        # 模擬滿足所有條件
        mock_repository.has_user_achievement.return_value = True  # 有依賴成就

        trigger_context = {"message_count": 150, "event_type": "message_sent"}

        # Mock 時間範圍條件
        with patch(
            "src.cogs.achievement.services.trigger_engine.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = datetime(2023, 6, 15, 12, 0, 0)
            mock_datetime.fromisoformat = datetime.fromisoformat

            # Act
            result, reason = await engine._check_conditional_trigger(
                user_id=123,
                achievement=achievement,
                criteria=achievement.criteria,
                trigger_context=trigger_context,
            )

        # Assert
        assert result is True
        assert "滿足所有條件" in reason

    # ==========================================================================
    # 自動觸發機制測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_process_automatic_triggers(
        self, mock_repository, mock_progress_tracker
    ):
        """測試自動觸發處理機制."""
        # Arrange
        engine = TriggerEngine(mock_repository, mock_progress_tracker)

        # 模擬啟用的成就
        test_achievements = [
            create_test_achievement(
                achievement_id=1,
                achievement_type=AchievementType.COUNTER,
                criteria={"target_value": 1, "counter_field": "message_count"},
                name="Message Achievement",
            ),
            create_test_achievement(
                achievement_id=2,
                achievement_type=AchievementType.COUNTER,
                criteria={"target_value": 1, "counter_field": "reaction_count"},
                name="Reaction Achievement",
            ),
        ]

        mock_repository.list_achievements.return_value = test_achievements
        mock_repository.has_user_achievement.return_value = False

        # 模擬進度資料
        mock_progress = Mock()
        mock_progress.current_value = 1.0
        mock_repository.get_user_progress.return_value = mock_progress

        # 模擬成就頒發
        mock_user_achievement = UserAchievement(
            id=1, user_id=123, achievement_id=1, earned_at=datetime.now()
        )
        mock_repository.award_achievement.return_value = mock_user_achievement

        event_data = {"message_count": 1, "user_id": 123, "event_type": "message_sent"}

        # Act
        newly_earned = await engine.process_automatic_triggers(
            user_id=123, trigger_event="message_sent", event_data=event_data
        )

        # Assert
        assert len(newly_earned) == 1
        assert newly_earned[0].achievement_id == 1
        mock_repository.award_achievement.assert_called_once_with(123, 1)

    # ==========================================================================
    # 批量處理測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_batch_check_triggers_for_users(
        self, mock_repository, mock_progress_tracker
    ):
        """測試批量用戶觸發檢查."""
        # Arrange
        engine = TriggerEngine(mock_repository, mock_progress_tracker)

        # 模擬批量處理返回值
        mock_user_achievement = UserAchievement(
            id=1, user_id=123, achievement_id=1, earned_at=datetime.now()
        )

        with patch.object(engine, "process_automatic_triggers") as mock_process:
            mock_process.return_value = [mock_user_achievement]

            # Act
            results = await engine.batch_check_triggers_for_users(
                user_ids=[123, 456, 789],
                trigger_event="message_sent",
                event_data={"message_count": 1},
            )

        # Assert
        assert len(results) == 3
        assert 123 in results
        assert len(results[123]) == 1
        assert mock_process.call_count == 3

    # ==========================================================================
    # 錯誤處理測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_trigger_check_with_invalid_achievement(
        self, mock_repository, mock_progress_tracker
    ):
        """測試無效成就的觸發檢查錯誤處理."""
        # Arrange
        engine = TriggerEngine(mock_repository, mock_progress_tracker)
        mock_repository.get_achievement_by_id.return_value = None

        trigger_context = {"event_type": "test"}

        # Act & Assert
        with pytest.raises(ValueError, match="成就 999 不存在"):
            await engine.check_achievement_trigger(
                user_id=123, achievement_id=999, trigger_context=trigger_context
            )

    @pytest.mark.asyncio
    async def test_trigger_check_with_inactive_achievement(
        self, mock_repository, mock_progress_tracker
    ):
        """測試未啟用成就的觸發檢查."""
        # Arrange
        engine = TriggerEngine(mock_repository, mock_progress_tracker)

        inactive_achievement = create_test_achievement(
            achievement_id=1,
            achievement_type=AchievementType.COUNTER,
            criteria={"target_value": 10},
            is_active=False,
            name="Inactive Achievement",
        )

        mock_repository.has_user_achievement.return_value = False
        mock_repository.get_achievement_by_id.return_value = inactive_achievement

        trigger_context = {"event_type": "test"}

        # Act
        result, reason = await engine.check_achievement_trigger(
            user_id=123, achievement_id=1, trigger_context=trigger_context
        )

        # Assert
        assert result is False
        assert reason == "成就未啟用"

    # ==========================================================================
    # 效能測試
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_trigger_check_performance(
        self, mock_repository, mock_progress_tracker
    ):
        """測試觸發檢查效能."""
        # Arrange
        engine = TriggerEngine(mock_repository, mock_progress_tracker)

        achievement = create_test_achievement(
            achievement_id=1,
            achievement_type=AchievementType.COUNTER,
            criteria={"target_value": 1, "counter_field": "message_count"},
            name="Performance Test Achievement",
        )

        mock_repository.has_user_achievement.return_value = False
        mock_repository.get_achievement_by_id.return_value = achievement

        mock_progress = Mock()
        mock_progress.current_value = 1.0
        mock_repository.get_user_progress.return_value = mock_progress

        trigger_context = {"message_count": 1, "event_type": "message_sent"}

        # Act
        start_time = datetime.now()

        # 執行多次觸發檢查
        for _ in range(100):
            await engine.check_achievement_trigger(
                user_id=123, achievement_id=1, trigger_context=trigger_context
            )

        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds() * 1000

        # Assert - 每次觸發檢查應該在 50ms 內完成
        average_time = total_time / 100
        assert average_time < 50.0, f"平均觸發檢查時間 {average_time}ms 超過 50ms 限制"


@pytest.mark.unit
class TestTriggerConditions:
    """觸發條件配置測試類別."""

    def test_trigger_condition_creation(self):
        """測試觸發條件創建."""
        # Arrange & Act
        condition = TriggerCondition(
            condition_type="metric_threshold",
            parameters={"metric": "message_count", "threshold": 100},
            description="發送100則訊息",
        )

        # Assert
        assert condition.condition_type == "metric_threshold"
        assert condition.parameters["threshold"] == 100
        assert "100則訊息" in condition.description

    def test_trigger_condition_validator(self):
        """測試觸發條件驗證器."""
        # Arrange
        valid_condition = TriggerCondition(
            condition_type="metric_threshold",
            parameters={"metric": "message_count", "threshold": 100, "operator": ">="},
        )

        invalid_condition = TriggerCondition(
            condition_type="metric_threshold",
            parameters={"threshold": 100},  # 缺少 metric
        )

        # Act
        valid_errors = TriggerConditionValidator.validate_condition(valid_condition)
        invalid_errors = TriggerConditionValidator.validate_condition(invalid_condition)

        # Assert
        assert len(valid_errors) == 0
        assert len(invalid_errors) > 0
        assert "缺少 metric 參數" in invalid_errors[0]

    def test_achievement_trigger_config_validation(self):
        """測試成就觸發配置驗證."""
        # Arrange
        condition = TriggerCondition(
            condition_type="metric_threshold",
            parameters={"metric": "message_count", "threshold": 100, "operator": ">="},
        )

        valid_config = AchievementTriggerConfig(
            achievement_type=AchievementType.COUNTER,
            conditions=[condition],
            logic_operator="AND",
        )

        invalid_config = AchievementTriggerConfig(
            achievement_type=AchievementType.COUNTER,
            conditions=[],  # 空條件列表
            logic_operator="INVALID",  # 無效邏輯運算子
        )

        # Act
        valid_errors = TriggerConditionValidator.validate_config(valid_config)
        invalid_errors = TriggerConditionValidator.validate_config(invalid_config)

        # Assert
        assert len(valid_errors) == 0
        assert len(invalid_errors) >= 2  # 至少有兩個錯誤
        assert any("至少需要一個觸發條件" in error for error in invalid_errors)
        assert any("不支援的邏輯運算子" in error for error in invalid_errors)


# ==========================================================================
# 測試輔助函數和 Fixtures
# ==========================================================================


@pytest.fixture
def mock_repository():
    """模擬資料庫存取庫."""
    repository = AsyncMock()
    repository.has_user_achievement.return_value = False
    repository.get_achievement_by_id.return_value = None
    repository.get_user_progress.return_value = None
    return repository


@pytest.fixture
def mock_progress_tracker():
    """模擬進度追蹤器."""
    tracker = AsyncMock()
    return tracker


def create_test_achievement(
    achievement_id: int,
    achievement_type: AchievementType,
    criteria: dict[str, Any],
    is_active: bool = True,
    name: str | None = None,
) -> Achievement:
    """創建測試用成就物件."""
    # 確保 criteria 包含必要的 target_value
    if "target_value" not in criteria:
        criteria["target_value"] = 1

    return Achievement(
        id=achievement_id,
        name=name or f"Test Achievement {achievement_id}",
        description=f"Test description for achievement {achievement_id}",
        category_id=1,  # 使用預設分類 ID
        type=achievement_type,
        criteria=criteria,
        is_active=is_active,
        points=100,
    )


def create_test_progress(
    user_id: int,
    achievement_id: int,
    current_value: float = 0.0,
    progress_data: dict[str, Any] | None = None,
) -> AchievementProgress:
    """創建測試用進度物件."""
    return AchievementProgress(
        id=1,
        user_id=user_id,
        achievement_id=achievement_id,
        current_value=current_value,
        progress_data=progress_data or {},
        last_updated=datetime.now(),
    )
