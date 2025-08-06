"""成就系統資料模型定義.

此模組定義了成就系統的所有 Pydantic 資料模型, 提供:
- 資料驗證和序列化
- 型別安全保證
- JSON 序列化支援
- 完整的型別提示

包含的模型:
- AchievementType: 成就類型列舉
- AchievementCategory: 成就分類模型
- Achievement: 成就定義模型
- UserAchievement: 用戶成就獲得記錄模型
- AchievementProgress: 成就進度追蹤模型
- AchievementEventData: 成就事件資料模型
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, Field, field_validator, model_validator

# 常數定義
MAX_RATE_LIMIT_SECONDS = 3600  # 最大頻率限制時間(1小時)


class AchievementType(str, Enum):
    """成就類型列舉.

    定義四種基本的成就類型:
    - COUNTER: 計數器型成就(如發送訊息數量)
    - MILESTONE: 里程碑型成就(如達到特定等級)
    - TIME_BASED: 時間型成就(如連續登入天數)
    - CONDITIONAL: 條件型成就(如完成特定任務)
    """

    COUNTER = "counter"
    MILESTONE = "milestone"
    TIME_BASED = "time_based"
    CONDITIONAL = "conditional"


class AchievementCategory(BaseModel):
    """成就分類資料模型.

    表示成就的分類資訊, 用於組織和管理不同類型的成就.
    支援無限層級的分類階層結構.

    Attributes:
        id: 分類唯一識別碼
        name: 分類名稱(唯一)
        description: 分類描述
        parent_id: 父分類 ID(None 表示根分類)
        level: 分類層級(從 0 開始)
        display_order: UI 顯示順序
        icon_emoji: 分類圖示表情符號
        is_expanded: 是否展開子分類(UI 狀態)
        created_at: 建立時間
        updated_at: 最後更新時間
    """

    id: int | None = Field(None, description="分類唯一識別碼")
    name: str = Field(..., min_length=1, max_length=50, description="分類名稱")
    description: str = Field(..., min_length=1, max_length=200, description="分類描述")
    parent_id: int | None = Field(None, description="父分類 ID(None 表示根分類)")
    level: int = Field(default=0, ge=0, le=10, description="分類層級(最多 10 層)")
    display_order: int = Field(default=0, ge=0, description="UI 顯示順序")
    icon_emoji: str | None = Field(None, max_length=10, description="分類圖示表情符號")
    is_expanded: bool = Field(default=False, description="是否展開子分類(UI 狀態)")
    created_at: datetime | None = Field(None, description="建立時間")
    updated_at: datetime | None = Field(None, description="最後更新時間")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """驗證分類名稱格式."""
        if not v.strip():
            raise ValueError("分類名稱不能為空")
        return v.strip()

    @field_validator("parent_id")
    @classmethod
    def validate_parent_id(cls, v: int | None) -> int | None:
        """驗證父分類 ID."""
        if v is not None and v <= 0:
            raise ValueError("父分類 ID 必須是正數")
        return v

    @model_validator(mode="after")
    def validate_parent_consistency(self) -> AchievementCategory:
        """驗證父子關係一致性."""
        if self.parent_id is not None and self.parent_id == self.id:
            raise ValueError("分類不能以自己作為父分類")

        # 根分類(parent_id=None)的層級必須是 0
        if self.parent_id is None and self.level != 0:
            self.level = 0

        return self

    @property
    def is_root(self) -> bool:
        """檢查是否為根分類."""
        return self.parent_id is None

    @property
    def full_path(self) -> str:
        """取得分類的完整路徑(需要配合服務層使用)."""
        return self.name  # 基本實作, 完整路徑需要服務層構建

    def get_indent_display_name(self) -> str:
        """取得帶縮排的顯示名稱."""
        indent = "　" * self.level  # 使用全形空格縮排
        return (
            f"{indent}{self.icon_emoji} {self.name}"
            if self.icon_emoji
            else f"{indent}{self.name}"
        )

    class Config:
        """Pydantic 模型配置."""

        from_attributes = True
        json_encoders: ClassVar[dict[type, Any]] = {
            datetime: lambda v: v.isoformat() if v else None
        }


class Achievement(BaseModel):
    """成就定義資料模型.

    表示單一成就的完整定義, 包含成就的所有屬性和完成條件.

    Attributes:
        id: 成就唯一識別碼
        name: 成就顯示名稱
        description: 成就描述
        category_id: 所屬分類 ID
        type: 成就類型
        criteria: 成就完成條件(JSON 格式)
        points: 完成獎勵點數
        badge_url: 徽章圖片 URL
        is_active: 成就是否啟用
        created_at: 建立時間
        updated_at: 最後更新時間
    """

    id: int | None = Field(None, description="成就唯一識別碼")
    name: str = Field(..., min_length=1, max_length=100, description="成就顯示名稱")
    description: str = Field(..., min_length=1, max_length=500, description="成就描述")
    category_id: int = Field(..., gt=0, description="所屬分類 ID")
    type: AchievementType = Field(..., description="成就類型")
    criteria: dict[str, Any] = Field(..., description="成就完成條件")
    points: int = Field(default=0, ge=0, le=10000, description="完成獎勵點數")
    badge_url: str | None = Field(None, max_length=500, description="徽章圖片 URL")
    role_reward: str | None = Field(None, description="成就獎勵身分組名稱")
    is_hidden: bool = Field(default=False, description="是否為隱藏成就")
    is_active: bool = Field(default=True, description="成就是否啟用")
    created_at: datetime | None = Field(None, description="建立時間")
    updated_at: datetime | None = Field(None, description="最後更新時間")

    @field_validator("criteria")
    @classmethod
    def validate_criteria(cls, v: dict[str, Any]) -> dict[str, Any]:
        """驗證成就完成條件格式."""
        if not isinstance(v, dict):
            raise ValueError("成就條件必須是字典格式")

        # 基本條件驗證
        required_fields = {"target_value"}
        if not required_fields.issubset(v.keys()):
            raise ValueError(f"成就條件必須包含以下欄位: {required_fields}")

        # 驗證目標值
        target_value = v.get("target_value")
        if not isinstance(target_value, int | float) or target_value <= 0:
            raise ValueError("target_value 必須是大於 0 的數值")

        return v

    @field_validator("badge_url")
    @classmethod
    def validate_badge_url(cls, v: str | None) -> str | None:
        """驗證徽章 URL 格式."""
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("徽章 URL 必須以 http:// 或 https:// 開頭")
        return v

    @model_validator(mode="after")
    def validate_type_criteria_consistency(self) -> Achievement:
        """驗證成就類型與條件的一致性."""
        type_specific_validations = {
            AchievementType.COUNTER: self._validate_counter_criteria,
            AchievementType.MILESTONE: self._validate_milestone_criteria,
            AchievementType.TIME_BASED: self._validate_time_based_criteria,
            AchievementType.CONDITIONAL: self._validate_conditional_criteria,
        }

        validator = type_specific_validations.get(self.type)
        if validator:
            validator()

        return self

    def _validate_counter_criteria(self) -> None:
        """驗證計數器型成就條件."""
        criteria = self.criteria
        if "counter_field" not in criteria:
            raise ValueError("計數器型成就必須指定 counter_field")

    def _validate_milestone_criteria(self) -> None:
        """驗證里程碑型成就條件."""
        criteria = self.criteria
        if "milestone_type" not in criteria:
            raise ValueError("里程碑型成就必須指定 milestone_type")

    def _validate_time_based_criteria(self) -> None:
        """驗證時間型成就條件."""
        criteria = self.criteria
        if "time_unit" not in criteria:
            raise ValueError("時間型成就必須指定 time_unit(如 'days', 'hours')")

    def _validate_conditional_criteria(self) -> None:
        """驗證條件型成就條件."""
        criteria = self.criteria
        if "conditions" not in criteria:
            raise ValueError("條件型成就必須指定 conditions 陣列")

    def get_criteria_json(self) -> str:
        """取得 JSON 格式的條件字串."""
        return json.dumps(self.criteria, ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_criteria_json(cls, criteria_json: str, **kwargs: Any) -> Achievement:
        """從 JSON 字串建立成就物件."""
        criteria = json.loads(criteria_json)
        return cls(criteria=criteria, **kwargs)

    class Config:
        """Pydantic 模型配置."""

        from_attributes = True
        json_encoders: ClassVar[dict[type, Any]] = {
            datetime: lambda v: v.isoformat() if v else None,
            AchievementType: lambda v: v.value,
        }


class UserAchievement(BaseModel):
    """用戶成就獲得記錄資料模型.

    表示用戶已獲得的成就記錄, 用於追蹤用戶的成就獲得狀況.

    Attributes:
        id: 記錄唯一識別碼
        user_id: Discord 用戶 ID
        achievement_id: 成就 ID 參考
        earned_at: 獲得時間
        notified: 是否已通知用戶
    """

    id: int | None = Field(None, description="記錄唯一識別碼")
    user_id: int = Field(..., gt=0, description="Discord 用戶 ID")
    achievement_id: int = Field(..., gt=0, description="成就 ID 參考")
    earned_at: datetime | None = Field(None, description="獲得時間")
    notified: bool = Field(default=False, description="是否已通知用戶")

    @field_validator("user_id", "achievement_id")
    @classmethod
    def validate_positive_ids(cls, v: int) -> int:
        """驗證 ID 為正數."""
        if v <= 0:
            raise ValueError("ID 必須是正數")
        return v

    class Config:
        """Pydantic 模型配置."""

        from_attributes = True
        json_encoders: ClassVar[dict[type, Any]] = {
            datetime: lambda v: v.isoformat() if v else None
        }


class AchievementProgress(BaseModel):
    """成就進度追蹤資料模型.

    表示用戶對特定成就的進度狀況, 支援複雜的進度追蹤機制.

    Attributes:
        id: 進度記錄唯一識別碼
        user_id: Discord 用戶 ID
        achievement_id: 成就 ID 參考
        current_value: 當前進度值
        target_value: 目標值
        progress_data: 複雜進度追蹤資料(JSON 格式)
        last_updated: 最後更新時間
    """

    id: int | None = Field(None, description="進度記錄唯一識別碼")
    user_id: int = Field(..., gt=0, description="Discord 用戶 ID")
    achievement_id: int = Field(..., gt=0, description="成就 ID 參考")
    current_value: float = Field(default=0.0, ge=0, description="當前進度值")
    target_value: float = Field(..., gt=0, description="目標值")
    progress_data: dict[str, Any] | None = Field(None, description="複雜進度追蹤資料")
    last_updated: datetime | None = Field(None, description="最後更新時間")

    @field_validator("user_id", "achievement_id")
    @classmethod
    def validate_positive_ids(cls, v: int) -> int:
        """驗證 ID 為正數."""
        if v <= 0:
            raise ValueError("ID 必須是正數")
        return v

    @field_validator("current_value", "target_value")
    @classmethod
    def validate_progress_values(cls, v: float) -> float:
        """驗證進度值為非負數."""
        if v < 0:
            raise ValueError("進度值不能是負數")
        return v

    @model_validator(mode="after")
    def validate_progress_consistency(self) -> AchievementProgress:
        """驗證進度值的一致性."""
        if self.current_value > self.target_value:
            # 允許超過目標值, 但記錄警告
            pass
        return self

    @property
    def progress_percentage(self) -> float:
        """計算進度百分比."""
        if self.target_value == 0:
            return 100.0
        return min((self.current_value / self.target_value) * 100, 100.0)

    @property
    def is_completed(self) -> bool:
        """檢查是否已完成."""
        return self.current_value >= self.target_value

    def get_progress_data_json(self) -> str:
        """取得 JSON 格式的進度資料字串."""
        if self.progress_data is None:
            return "{}"
        return json.dumps(self.progress_data, ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_progress_data_json(
        cls, progress_data_json: str, **kwargs: Any
    ) -> AchievementProgress:
        """從 JSON 字串建立進度物件."""
        progress_data = json.loads(progress_data_json) if progress_data_json else None
        return cls(progress_data=progress_data, **kwargs)

    class Config:
        """Pydantic 模型配置."""

        from_attributes = True
        json_encoders: ClassVar[dict[type, Any]] = {
            datetime: lambda v: v.isoformat() if v else None
        }


class AchievementEventData(BaseModel):
    """成就事件資料模型.

    表示與成就相關的事件資料, 用於事件追蹤和成就觸發.

    Attributes:
        id: 事件記錄唯一識別碼
        user_id: Discord 用戶 ID
        guild_id: Discord 伺服器 ID
        event_type: 事件類型
        event_data: 事件詳細資料(JSON 格式)
        timestamp: 事件發生時間
        channel_id: 頻道 ID(如適用)
        processed: 是否已被處理標記
        correlation_id: 事件關聯 ID(用於追蹤相關事件)
    """

    id: int | None = Field(None, description="事件記錄唯一識別碼")
    user_id: int = Field(..., gt=0, description="Discord 用戶 ID")
    guild_id: int = Field(..., gt=0, description="Discord 伺服器 ID")
    event_type: str = Field(..., min_length=1, max_length=100, description="事件類型")
    event_data: dict[str, Any] = Field(..., description="事件詳細資料")
    timestamp: datetime = Field(..., description="事件發生時間")
    channel_id: int | None = Field(None, description="頻道 ID")
    processed: bool = Field(default=False, description="是否已被處理")
    correlation_id: str | None = Field(None, max_length=100, description="事件關聯 ID")

    @field_validator("user_id", "guild_id")
    @classmethod
    def validate_positive_ids(cls, v: int) -> int:
        """驗證 ID 為正數."""
        if v <= 0:
            raise ValueError("ID 必須是正數")
        return v

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        """驗證事件類型格式."""
        if not v.startswith("achievement."):
            raise ValueError("事件類型必須以 'achievement.' 開頭")
        return v

    @field_validator("event_data")
    @classmethod
    def validate_event_data(cls, v: dict[str, Any]) -> dict[str, Any]:
        """驗證事件資料格式."""
        if not isinstance(v, dict):
            raise ValueError("事件資料必須是字典格式")

        # 檢查必要欄位
        if "is_bot" not in v:
            v["is_bot"] = False

        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        """驗證時間戳不能是未來時間."""
        # 允許 5 分鐘的時間差異以處理時區和系統時間差異
        future_threshold = datetime.now() + timedelta(minutes=5)
        if v > future_threshold:
            raise ValueError("事件時間戳不能是未來時間")
        return v

    def get_event_data_json(self) -> str:
        """取得 JSON 格式的事件資料字串."""
        return json.dumps(self.event_data, ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_event_data_json(
        cls, event_data_json: str, **kwargs: Any
    ) -> AchievementEventData:
        """從 JSON 字串建立事件物件."""
        event_data = json.loads(event_data_json)
        return cls(event_data=event_data, **kwargs)

    def is_achievement_relevant(self) -> bool:
        """檢查事件是否與成就相關."""
        # 檢查事件類型
        if not self.event_type.startswith("achievement."):
            return False

        if self.event_data.get("is_bot", False):
            return False

        # 檢查必要的模型欄位(這些是模型的頂層屬性, 不在 event_data 中)
        return not (not self.user_id or not self.guild_id)

    def get_standardized_data(self) -> dict[str, Any]:
        """取得標準化的事件資料."""
        standardized = {
            "user_id": self.user_id,
            "guild_id": self.guild_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "processed": self.processed,
        }

        # 添加可選欄位
        if self.channel_id:
            standardized["channel_id"] = self.channel_id

        if self.correlation_id:
            standardized["correlation_id"] = self.correlation_id

        # 合併事件特定資料
        standardized.update(self.event_data)

        return standardized

    class Config:
        """Pydantic 模型配置."""

        from_attributes = True
        json_encoders: ClassVar[dict[type, Any]] = {
            datetime: lambda v: v.isoformat() if v else None
        }


# 用於快速建立測試資料的工廠函數
def create_sample_achievement_category() -> AchievementCategory:
    """建立範例成就分類資料."""
    return AchievementCategory(
        name="social", description="社交互動相關成就", display_order=1, icon_emoji="👥"
    )


def create_sample_achievement() -> Achievement:
    """建立範例成就資料."""
    return Achievement(
        name="社交達人",
        description="與其他用戶互動超過 100 次",
        category_id=1,
        type=AchievementType.COUNTER,
        criteria={"target_value": 100, "counter_field": "social_interactions"},
        points=500,
        role_reward="社交專家",
        is_hidden=False,
    )


def create_sample_user_achievement(user_id: int = 123456789) -> UserAchievement:
    """建立範例用戶成就記錄."""
    return UserAchievement(
        user_id=user_id, achievement_id=1, earned_at=datetime.now(), notified=False
    )


def create_sample_achievement_progress(user_id: int = 123456789) -> AchievementProgress:
    """建立範例成就進度記錄."""
    return AchievementProgress(
        user_id=user_id,
        achievement_id=1,
        current_value=75.0,
        target_value=100.0,
        progress_data={"daily_interactions": [5, 8, 12, 10, 7], "streak_days": 5},
    )


class NotificationPreference(BaseModel):
    """用戶通知偏好資料模型.

    表示用戶的成就通知偏好設定.

    Attributes:
        id: 偏好設定唯一識別碼
        user_id: Discord 用戶 ID
        guild_id: Discord 伺服器 ID
        dm_notifications: 是否啟用私訊通知
        server_announcements: 是否啟用伺服器公告
        notification_types: 允許的通知類型列表
        created_at: 建立時間
        updated_at: 最後更新時間
    """

    id: int | None = Field(None, description="偏好設定唯一識別碼")
    user_id: int = Field(..., gt=0, description="Discord 用戶 ID")
    guild_id: int = Field(..., gt=0, description="Discord 伺服器 ID")
    dm_notifications: bool = Field(default=True, description="是否啟用私訊通知")
    server_announcements: bool = Field(default=True, description="是否啟用伺服器公告")
    notification_types: list[str] = Field(
        default_factory=list, description="允許的通知類型列表"
    )
    created_at: datetime | None = Field(None, description="建立時間")
    updated_at: datetime | None = Field(None, description="最後更新時間")

    @field_validator("user_id", "guild_id")
    @classmethod
    def validate_positive_ids(cls, v: int) -> int:
        """驗證 ID 為正數."""
        if v <= 0:
            raise ValueError("ID 必須是正數")
        return v

    @field_validator("notification_types")
    @classmethod
    def validate_notification_types(cls, v: list[str]) -> list[str]:
        """驗證通知類型列表."""
        if not isinstance(v, list):
            raise ValueError("通知類型必須是列表格式")

        valid_types = {
            "counter",
            "milestone",
            "time_based",
            "conditional",
            "rare",
            "epic",
            "legendary",
            "all",
        }

        for notification_type in v:
            if notification_type not in valid_types:
                raise ValueError(f"無效的通知類型: {notification_type}")

        return v

    class Config:
        """Pydantic 模型配置."""

        from_attributes = True
        json_encoders: ClassVar[dict[type, Any]] = {
            datetime: lambda v: v.isoformat() if v else None
        }


class GlobalNotificationSettings(BaseModel):
    """全域通知設定資料模型.

    表示伺服器層級的通知設定.

    Attributes:
        id: 設定唯一識別碼
        guild_id: Discord 伺服器 ID
        announcement_channel_id: 公告頻道 ID
        announcement_enabled: 是否啟用公告功能
        rate_limit_seconds: 通知頻率限制(秒)
        important_achievements_only: 是否僅通知重要成就
        created_at: 建立時間
        updated_at: 最後更新時間
    """

    id: int | None = Field(None, description="設定唯一識別碼")
    guild_id: int = Field(..., gt=0, description="Discord 伺服器 ID")
    announcement_channel_id: int | None = Field(None, description="公告頻道 ID")
    announcement_enabled: bool = Field(default=False, description="是否啟用公告功能")
    rate_limit_seconds: int = Field(
        default=60, ge=0, le=MAX_RATE_LIMIT_SECONDS, description="通知頻率限制(秒)"
    )
    important_achievements_only: bool = Field(
        default=False, description="是否僅通知重要成就"
    )
    created_at: datetime | None = Field(None, description="建立時間")
    updated_at: datetime | None = Field(None, description="最後更新時間")

    @field_validator("guild_id")
    @classmethod
    def validate_guild_id(cls, v: int) -> int:
        """驗證伺服器 ID."""
        if v <= 0:
            raise ValueError("伺服器 ID 必須是正數")
        return v

    @field_validator("rate_limit_seconds")
    @classmethod
    def validate_rate_limit(cls, v: int) -> int:
        """驗證頻率限制."""
        if v < 0:
            raise ValueError("頻率限制不能是負數")
        if v > MAX_RATE_LIMIT_SECONDS:
            raise ValueError("頻率限制不能超過 1 小時")
        return v

    class Config:
        """Pydantic 模型配置."""

        from_attributes = True
        json_encoders: ClassVar[dict[type, Any]] = {
            datetime: lambda v: v.isoformat() if v else None
        }


class NotificationEvent(BaseModel):
    """通知事件資料模型.

    表示成就通知的事件記錄.

    Attributes:
        id: 事件唯一識別碼
        user_id: Discord 用戶 ID
        guild_id: Discord 伺服器 ID
        achievement_id: 成就 ID
        notification_type: 通知類型
        sent_at: 發送時間
        delivery_status: 遞送狀態
        error_message: 錯誤訊息(如有)
        retry_count: 重試次數
    """

    id: int | None = Field(None, description="事件唯一識別碼")
    user_id: int = Field(..., gt=0, description="Discord 用戶 ID")
    guild_id: int = Field(..., gt=0, description="Discord 伺服器 ID")
    achievement_id: int = Field(..., gt=0, description="成就 ID")
    notification_type: str = Field(..., description="通知類型")
    sent_at: datetime = Field(..., description="發送時間")
    delivery_status: str = Field(default="pending", description="遞送狀態")
    error_message: str | None = Field(None, description="錯誤訊息")
    retry_count: int = Field(default=0, ge=0, description="重試次數")

    @field_validator("user_id", "guild_id", "achievement_id")
    @classmethod
    def validate_positive_ids(cls, v: int) -> int:
        """驗證 ID 為正數."""
        if v <= 0:
            raise ValueError("ID 必須是正數")
        return v

    @field_validator("notification_type")
    @classmethod
    def validate_notification_type(cls, v: str) -> str:
        """驗證通知類型."""
        valid_types = {"dm", "announcement", "both"}
        if v not in valid_types:
            raise ValueError(f"無效的通知類型: {v}")
        return v

    @field_validator("delivery_status")
    @classmethod
    def validate_delivery_status(cls, v: str) -> str:
        """驗證遞送狀態."""
        valid_statuses = {"pending", "sent", "failed", "retry"}
        if v not in valid_statuses:
            raise ValueError(f"無效的遞送狀態: {v}")
        return v

    class Config:
        """Pydantic 模型配置."""

        from_attributes = True
        json_encoders: ClassVar[dict[type, Any]] = {
            datetime: lambda v: v.isoformat() if v else None
        }


def create_sample_notification_preference(
    user_id: int = 123456789, guild_id: int = 987654321
) -> NotificationPreference:
    """建立範例通知偏好記錄."""
    return NotificationPreference(
        user_id=user_id,
        guild_id=guild_id,
        dm_notifications=True,
        server_announcements=False,
        notification_types=["milestone", "rare"],
    )


def create_sample_global_notification_settings(
    guild_id: int = 987654321,
) -> GlobalNotificationSettings:
    """建立範例全域通知設定."""
    return GlobalNotificationSettings(
        guild_id=guild_id,
        announcement_channel_id=555666777,
        announcement_enabled=True,
        rate_limit_seconds=300,
        important_achievements_only=True,
    )


__all__ = [
    "Achievement",
    "AchievementCategory",
    "AchievementEventData",
    "AchievementProgress",
    "AchievementType",
    "GlobalNotificationSettings",
    "NotificationEvent",
    "NotificationPreference",
    "UserAchievement",
    "create_sample_achievement",
    "create_sample_achievement_category",
    "create_sample_achievement_progress",
    "create_sample_global_notification_settings",
    "create_sample_notification_preference",
    "create_sample_user_achievement",
]
