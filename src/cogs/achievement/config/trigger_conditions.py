"""成就觸發條件配置.

此模組定義成就系統的觸發條件配置，提供：
- 標準化的觸發條件定義
- 條件模板和預設值
- 觸發邏輯配置
- 條件驗證規則

觸發條件遵循以下設計原則：
- 支援多種成就類型的條件定義
- 提供靈活的條件組合機制
- 支援複雜的依賴關係
- 高效的條件評估
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..database.models import AchievementType


@dataclass
class TriggerCondition:
    """觸發條件定義.

    表示單一觸發條件的定義，包含條件類型、參數和評估邏輯。
    """

    condition_type: str
    """條件類型（如 metric_threshold、achievement_dependency）"""

    parameters: dict[str, Any] = field(default_factory=dict)
    """條件參數"""

    description: str = ""
    """條件描述"""


@dataclass
class AchievementTriggerConfig:
    """成就觸發配置.

    定義特定成就的完整觸發配置，包含條件、邏輯和依賴關係。
    """

    achievement_type: AchievementType
    """成就類型"""

    conditions: list[TriggerCondition] = field(default_factory=list)
    """觸發條件列表"""

    logic_operator: str = "AND"
    """條件邏輯運算子（AND/OR）"""

    dependencies: list[int] = field(default_factory=list)
    """依賴的成就 ID 列表"""

    priority: int = 0
    """觸發優先級（數值越高優先級越高）"""


class TriggerConditionTemplates:
    """觸發條件模板.

    提供常用的觸發條件模板，簡化成就配置過程。
    """

    @staticmethod
    def message_count_threshold(target_count: int, time_window: str | None = None) -> TriggerCondition:
        """建立訊息數量閾值條件."""
        parameters = {
            "metric": "message_count",
            "threshold": target_count,
            "operator": ">="
        }

        if time_window:
            parameters["time_window"] = time_window

        return TriggerCondition(
            condition_type="metric_threshold",
            parameters=parameters,
            description=f"發送 {target_count} 則訊息"
        )

    @staticmethod
    def consecutive_days_active(days: int) -> TriggerCondition:
        """建立連續活躍天數條件."""
        return TriggerCondition(
            condition_type="consecutive_activity",
            parameters={
                "activity_type": "daily_active",
                "target_days": days,
                "consecutive": True
            },
            description=f"連續活躍 {days} 天"
        )

    @staticmethod
    def achievement_dependency(achievement_id: int) -> TriggerCondition:
        """建立成就依賴條件."""
        return TriggerCondition(
            condition_type="achievement_dependency",
            parameters={"achievement_id": achievement_id},
            description=f"需要先獲得成就 {achievement_id}"
        )

    @staticmethod
    def time_range_active(start_time: str, end_time: str) -> TriggerCondition:
        """建立時間範圍條件."""
        return TriggerCondition(
            condition_type="time_range",
            parameters={
                "start_time": start_time,
                "end_time": end_time
            },
            description=f"在時間範圍 {start_time} - {end_time} 內"
        )

    @staticmethod
    def guild_role_requirement(role_id: int) -> TriggerCondition:
        """建立伺服器角色要求條件."""
        return TriggerCondition(
            condition_type="guild_role",
            parameters={"role_id": role_id},
            description=f"需要擁有角色 {role_id}"
        )

    @staticmethod
    def channel_activity(channel_id: int, activity_count: int) -> TriggerCondition:
        """建立特定頻道活動條件."""
        return TriggerCondition(
            condition_type="channel_activity",
            parameters={
                "channel_id": channel_id,
                "activity_count": activity_count,
                "operator": ">="
            },
            description=f"在頻道 {channel_id} 中活動 {activity_count} 次"
        )


class DefaultTriggerConfigs:
    """預設觸發配置.

    提供常見成就類型的預設觸發配置模板。
    """

    @staticmethod
    def get_newbie_messenger_config() -> AchievementTriggerConfig:
        """新手訊息員成就配置."""
        return AchievementTriggerConfig(
            achievement_type=AchievementType.COUNTER,
            conditions=[
                TriggerConditionTemplates.message_count_threshold(10)
            ],
            logic_operator="AND",
            priority=1
        )

    @staticmethod
    def get_active_member_config() -> AchievementTriggerConfig:
        """活躍成員成就配置."""
        return AchievementTriggerConfig(
            achievement_type=AchievementType.TIME_BASED,
            conditions=[
                TriggerConditionTemplates.consecutive_days_active(7)
            ],
            logic_operator="AND",
            priority=2
        )

    @staticmethod
    def get_milestone_achiever_config(prerequisite_achievement_id: int) -> AchievementTriggerConfig:
        """里程碑達成者成就配置."""
        return AchievementTriggerConfig(
            achievement_type=AchievementType.CONDITIONAL,
            conditions=[
                TriggerConditionTemplates.achievement_dependency(prerequisite_achievement_id),
                TriggerConditionTemplates.message_count_threshold(100)
            ],
            logic_operator="AND",
            dependencies=[prerequisite_achievement_id],
            priority=3
        )


class TriggerConditionValidator:
    """觸發條件驗證器.

    驗證觸發條件配置的正確性和完整性。
    """

    SUPPORTED_CONDITION_TYPES = {
        "metric_threshold",
        "achievement_dependency",
        "time_range",
        "consecutive_activity",
        "guild_role",
        "channel_activity"
    }

    SUPPORTED_OPERATORS = {">=", ">", "<=", "<", "==", "!="}

    @classmethod
    def validate_condition(cls, condition: TriggerCondition) -> list[str]:
        """驗證單一觸發條件.

        Args:
            condition: 要驗證的條件

        Returns:
            驗證錯誤列表（空列表表示無錯誤）
        """
        errors = []

        # 檢查條件類型
        if condition.condition_type not in cls.SUPPORTED_CONDITION_TYPES:
            errors.append(f"不支援的條件類型: {condition.condition_type}")

        # 根據條件類型檢查必要參數
        if condition.condition_type == "metric_threshold":
            errors.extend(cls._validate_metric_threshold(condition.parameters))
        elif condition.condition_type == "achievement_dependency":
            errors.extend(cls._validate_achievement_dependency(condition.parameters))
        elif condition.condition_type == "time_range":
            errors.extend(cls._validate_time_range(condition.parameters))
        elif condition.condition_type == "consecutive_activity":
            errors.extend(cls._validate_consecutive_activity(condition.parameters))

        return errors

    @classmethod
    def validate_config(cls, config: AchievementTriggerConfig) -> list[str]:
        """驗證完整的觸發配置.

        Args:
            config: 要驗證的配置

        Returns:
            驗證錯誤列表（空列表表示無錯誤）
        """
        errors = []

        # 檢查成就類型
        if not isinstance(config.achievement_type, AchievementType):
            errors.append("無效的成就類型")

        # 檢查邏輯運算子
        if config.logic_operator not in ("AND", "OR"):
            errors.append(f"不支援的邏輯運算子: {config.logic_operator}")

        # 檢查條件
        if not config.conditions:
            errors.append("至少需要一個觸發條件")

        for i, condition in enumerate(config.conditions):
            condition_errors = cls.validate_condition(condition)
            for error in condition_errors:
                errors.append(f"條件 {i + 1}: {error}")

        # 檢查優先級
        if config.priority < 0:
            errors.append("優先級不能為負數")

        return errors

    @classmethod
    def _validate_metric_threshold(cls, params: dict[str, Any]) -> list[str]:
        """驗證指標閾值條件參數."""
        errors = []

        if "metric" not in params:
            errors.append("缺少 metric 參數")

        if "threshold" not in params:
            errors.append("缺少 threshold 參數")

        operator = params.get("operator", ">=")
        if operator not in cls.SUPPORTED_OPERATORS:
            errors.append(f"不支援的運算子: {operator}")

        return errors

    @classmethod
    def _validate_achievement_dependency(cls, params: dict[str, Any]) -> list[str]:
        """驗證成就依賴條件參數."""
        errors = []

        if "achievement_id" not in params:
            errors.append("缺少 achievement_id 參數")

        achievement_id = params.get("achievement_id")
        if not isinstance(achievement_id, int) or achievement_id <= 0:
            errors.append("achievement_id 必須是正整數")

        return errors

    @classmethod
    def _validate_time_range(cls, params: dict[str, Any]) -> list[str]:
        """驗證時間範圍條件參數."""
        errors = []

        if "start_time" not in params and "end_time" not in params:
            errors.append("至少需要 start_time 或 end_time 參數")

        return errors

    @classmethod
    def _validate_consecutive_activity(cls, params: dict[str, Any]) -> list[str]:
        """驗證連續活動條件參數."""
        errors = []

        if "activity_type" not in params:
            errors.append("缺少 activity_type 參數")

        if "target_days" not in params:
            errors.append("缺少 target_days 參數")

        target_days = params.get("target_days")
        if not isinstance(target_days, int) or target_days <= 0:
            errors.append("target_days 必須是正整數")

        return errors


__all__ = [
    "AchievementTriggerConfig",
    "DefaultTriggerConfigs",
    "TriggerCondition",
    "TriggerConditionTemplates",
    "TriggerConditionValidator",
]
