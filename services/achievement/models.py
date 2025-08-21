"""
成就系統資料模型
Task ID: 6 - 成就系統核心功能

這個模組定義了成就系統的所有資料模型，包括：
- Achievement: 成就定義
- AchievementProgress: 使用者成就進度
- AchievementReward: 成就獎勵配置
- TriggerCondition: 觸發條件定義
- 相關枚舉類型和驗證函數

符合要求：
- F1: 成就系統資料模型
- 支援JSON格式的彈性配置
- 向前和向後兼容的資料結構
- 完整的資料驗證機制
"""

import json
import re
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from enum import Enum
from dataclasses import dataclass, field

from core.exceptions import ValidationError


# =============================================================================
# 枚舉類型定義
# =============================================================================

class AchievementType(Enum):
    """成就類型"""
    MILESTONE = "milestone"        # 里程碑成就（一次性）
    RECURRING = "recurring"        # 重複成就（可多次完成）
    HIDDEN = "hidden"             # 隱藏成就（不在列表中顯示）
    PROGRESSIVE = "progressive"    # 漸進式成就（多階段）


class TriggerType(Enum):
    """觸發類型"""
    MESSAGE_COUNT = "message_count"        # 訊息數量
    VOICE_TIME = "voice_time"             # 語音時間（秒）
    REACTION_COUNT = "reaction_count"      # 反應數量
    CUSTOM_EVENT = "custom_event"         # 自訂事件
    LOGIN_STREAK = "login_streak"         # 連續登入天數
    COMMAND_USAGE = "command_usage"       # 指令使用次數


class RewardType(Enum):
    """獎勵類型"""
    CURRENCY = "currency"    # 貨幣獎勵
    ROLE = "role"           # 身分組獎勵
    BADGE = "badge"         # 徽章獎勵
    CUSTOM = "custom"       # 自訂獎勵


class AchievementStatus(Enum):
    """成就狀態"""
    ACTIVE = "active"        # 啟用中
    DISABLED = "disabled"    # 已停用
    ARCHIVED = "archived"    # 已封存


# =============================================================================
# 驗證函數
# =============================================================================

def validate_achievement_id(achievement_id: Union[str, int]) -> str:
    """
    驗證成就ID
    
    參數：
        achievement_id: 成就ID
        
    返回：
        標準化的成就ID
        
    異常：
        ValidationError: 當ID格式無效時
    """
    if not achievement_id:
        raise ValidationError(
            "成就ID不能為空",
            field="achievement_id",
            value=achievement_id,
            expected="非空字串"
        )
    
    achievement_id = str(achievement_id).strip()
    
    if len(achievement_id) < 3:
        raise ValidationError(
            "成就ID長度至少為3個字符",
            field="achievement_id",
            value=achievement_id,
            expected="長度 >= 3"
        )
    
    if len(achievement_id) > 100:
        raise ValidationError(
            "成就ID長度不能超過100個字符",
            field="achievement_id",
            value=achievement_id,
            expected="長度 <= 100"
        )
    
    # 檢查字符格式：只允許字母、數字、底線和連字號
    if not re.match(r'^[a-zA-Z0-9_-]+$', achievement_id):
        raise ValidationError(
            "成就ID只能包含字母、數字、底線和連字號",
            field="achievement_id",
            value=achievement_id,
            expected="匹配格式 ^[a-zA-Z0-9_-]+$"
        )
    
    return achievement_id


def validate_user_id(user_id: Union[str, int]) -> int:
    """
    驗證使用者ID
    
    參數：
        user_id: 使用者ID
        
    返回：
        標準化的使用者ID
        
    異常：
        ValidationError: 當ID無效時
    """
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        raise ValidationError(
            "使用者ID必須是有效的整數",
            field="user_id",
            value=user_id,
            expected="整數"
        )
    
    if user_id <= 0:
        raise ValidationError(
            "使用者ID必須大於0",
            field="user_id",
            value=user_id,
            expected="> 0"
        )
    
    # Discord ID 的基本範圍檢查（雖然Discord ID可能更大）
    if user_id > 2**63 - 1:
        raise ValidationError(
            "使用者ID超出有效範圍",
            field="user_id",
            value=user_id,
            expected="<= 2^63 - 1"
        )
    
    return user_id


def validate_guild_id(guild_id: Union[str, int]) -> int:
    """
    驗證伺服器ID
    
    參數：
        guild_id: 伺服器ID
        
    返回：
        標準化的伺服器ID
        
    異常：
        ValidationError: 當ID無效時
    """
    try:
        guild_id = int(guild_id)
    except (ValueError, TypeError):
        raise ValidationError(
            "伺服器ID必須是有效的整數",
            field="guild_id",
            value=guild_id,
            expected="整數"
        )
    
    if guild_id <= 0:
        raise ValidationError(
            "伺服器ID必須大於0",
            field="guild_id",
            value=guild_id,
            expected="> 0"
        )
    
    if guild_id > 2**63 - 1:
        raise ValidationError(
            "伺服器ID超出有效範圍",
            field="guild_id",
            value=guild_id,
            expected="<= 2^63 - 1"
        )
    
    return guild_id


# =============================================================================
# 資料模型類別
# =============================================================================

@dataclass
class TriggerCondition:
    """
    觸發條件定義
    
    定義成就的觸發條件，包括觸發類型、目標值和比較運算符
    """
    trigger_type: Union[TriggerType, str]  # 觸發類型
    target_value: Union[int, float]        # 目標值
    comparison_operator: str               # 比較運算符 (==, !=, >, <, >=, <=)
    metadata: Dict[str, Any] = field(default_factory=dict)  # 額外的配置資料
    
    def validate(self) -> None:
        """
        驗證觸發條件
        
        異常：
            ValidationError: 當資料無效時
        """
        # 驗證比較運算符
        valid_operators = ["==", "!=", ">", "<", ">=", "<="]
        if self.comparison_operator not in valid_operators:
            raise ValidationError(
                f"無效的比較運算符：{self.comparison_operator}",
                field="comparison_operator",
                value=self.comparison_operator,
                expected=f"其中之一：{', '.join(valid_operators)}"
            )
        
        # 驗證目標值
        if not isinstance(self.target_value, (int, float)):
            raise ValidationError(
                "目標值必須是數字",
                field="target_value",
                value=self.target_value,
                expected="int 或 float"
            )
        
        # 驗證觸發類型
        if isinstance(self.trigger_type, str):
            # 允許字串形式的自訂觸發類型
            if not self.trigger_type.strip():
                raise ValidationError(
                    "觸發類型不能為空",
                    field="trigger_type",
                    value=self.trigger_type,
                    expected="非空字串"
                )
        elif not isinstance(self.trigger_type, TriggerType):
            raise ValidationError(
                "觸發類型必須是TriggerType枚舉或字串",
                field="trigger_type",
                value=type(self.trigger_type),
                expected="TriggerType 或 str"
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        trigger_type_value = (
            self.trigger_type.value if isinstance(self.trigger_type, TriggerType)
            else self.trigger_type
        )
        
        return {
            "trigger_type": trigger_type_value,
            "target_value": self.target_value,
            "comparison_operator": self.comparison_operator,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TriggerCondition':
        """從字典建立實例"""
        trigger_type = data["trigger_type"]
        
        # 嘗試轉換為枚舉類型
        try:
            trigger_type = TriggerType(trigger_type)
        except ValueError:
            # 保持字串形式（自訂觸發類型）
            pass
        
        return cls(
            trigger_type=trigger_type,
            target_value=data["target_value"],
            comparison_operator=data["comparison_operator"],
            metadata=data.get("metadata", {})
        )


@dataclass
class AchievementReward:
    """
    成就獎勵定義
    
    定義完成成就時給予的獎勵
    """
    reward_type: Union[RewardType, str]    # 獎勵類型
    value: Union[str, int, float]          # 獎勵值
    metadata: Dict[str, Any] = field(default_factory=dict)  # 額外的獎勵配置
    
    def validate(self) -> None:
        """
        驗證獎勵配置
        
        異常：
            ValidationError: 當資料無效時
        """
        # 根據獎勵類型驗證值
        reward_type_value = (
            self.reward_type.value if isinstance(self.reward_type, RewardType)
            else self.reward_type
        )
        
        if reward_type_value == "currency":
            if not isinstance(self.value, (int, float)):
                raise ValidationError(
                    "貨幣獎勵的值必須是數字",
                    field="value",
                    value=self.value,
                    expected="int 或 float"
                )
            
            if self.value < 0:
                raise ValidationError(
                    "貨幣獎勵不能是負數",
                    field="value",
                    value=self.value,
                    expected=">= 0"
                )
        
        elif reward_type_value == "role":
            if not isinstance(self.value, str):
                raise ValidationError(
                    "身分組獎勵的值必須是字串",
                    field="value",
                    value=self.value,
                    expected="str"
                )
            
            if not self.value.strip():
                raise ValidationError(
                    "身分組名稱不能為空",
                    field="value",
                    value=self.value,
                    expected="非空字串"
                )
        
        elif reward_type_value == "badge":
            if not isinstance(self.value, str):
                raise ValidationError(
                    "徽章獎勵的值必須是字串",
                    field="value",
                    value=self.value,
                    expected="str"
                )
            
            if not self.value.strip():
                raise ValidationError(
                    "徽章名稱不能為空",
                    field="value",
                    value=self.value,
                    expected="非空字串"
                )
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        reward_type_value = (
            self.reward_type.value if isinstance(self.reward_type, RewardType)
            else self.reward_type
        )
        
        return {
            "reward_type": reward_type_value,
            "value": self.value,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AchievementReward':
        """從字典建立實例"""
        reward_type = data["reward_type"]
        
        # 嘗試轉換為枚舉類型
        try:
            reward_type = RewardType(reward_type)
        except ValueError:
            # 保持字串形式（自訂獎勵類型）
            pass
        
        return cls(
            reward_type=reward_type,
            value=data["value"],
            metadata=data.get("metadata", {})
        )


@dataclass
class Achievement:
    """
    成就定義
    
    完整的成就配置，包括觸發條件和獎勵設定
    """
    id: str                                        # 成就唯一ID
    name: str                                      # 成就名稱
    description: str                               # 成就描述
    achievement_type: AchievementType              # 成就類型
    guild_id: int                                  # 所屬伺服器ID
    trigger_conditions: List[TriggerCondition]     # 觸發條件列表
    rewards: List[AchievementReward]              # 獎勵列表
    status: AchievementStatus = AchievementStatus.ACTIVE  # 成就狀態
    metadata: Dict[str, Any] = field(default_factory=dict)  # 額外的成就配置
    created_at: Optional[datetime] = None          # 建立時間
    updated_at: Optional[datetime] = None          # 更新時間
    
    def __post_init__(self):
        """初始化後處理"""
        # 驗證和標準化ID
        self.id = validate_achievement_id(self.id)
        self.guild_id = validate_guild_id(self.guild_id)
        
        # 設定預設時間
        now = datetime.now()
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
    
    def validate(self) -> None:
        """
        驗證成就配置
        
        異常：
            ValidationError: 當配置無效時
        """
        # 驗證基本資料
        if not self.name.strip():
            raise ValidationError(
                "成就名稱不能為空",
                field="name",
                value=self.name,
                expected="非空字串"
            )
        
        if len(self.name) > 200:
            raise ValidationError(
                "成就名稱長度不能超過200個字符",
                field="name",
                value=len(self.name),
                expected="<= 200"
            )
        
        if not self.description.strip():
            raise ValidationError(
                "成就描述不能為空",
                field="description",
                value=self.description,
                expected="非空字串"
            )
        
        if len(self.description) > 1000:
            raise ValidationError(
                "成就描述長度不能超過1000個字符",
                field="description",
                value=len(self.description),
                expected="<= 1000"
            )
        
        # 驗證觸發條件
        if not self.trigger_conditions:
            raise ValidationError(
                "成就必須至少有一個觸發條件",
                field="trigger_conditions",
                value=len(self.trigger_conditions),
                expected=">= 1"
            )
        
        for i, condition in enumerate(self.trigger_conditions):
            try:
                condition.validate()
            except ValidationError as e:
                raise ValidationError(
                    f"觸發條件 {i} 無效：{e.message}",
                    field=f"trigger_conditions[{i}]",
                    value=condition,
                    expected="有效的觸發條件"
                )
        
        # 驗證獎勵
        for i, reward in enumerate(self.rewards):
            try:
                reward.validate()
            except ValidationError as e:
                raise ValidationError(
                    f"獎勵 {i} 無效：{e.message}",
                    field=f"rewards[{i}]",
                    value=reward,
                    expected="有效的獎勵配置"
                )
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "achievement_type": self.achievement_type.value,
            "guild_id": self.guild_id,
            "trigger_conditions": [condition.to_dict() for condition in self.trigger_conditions],
            "rewards": [reward.to_dict() for reward in self.rewards],
            "status": self.status.value,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Achievement':
        """從字典建立實例"""
        # 轉換觸發條件
        trigger_conditions = [
            TriggerCondition.from_dict(condition_data)
            for condition_data in data["trigger_conditions"]
        ]
        
        # 轉換獎勵
        rewards = [
            AchievementReward.from_dict(reward_data)
            for reward_data in data["rewards"]
        ]
        
        # 轉換時間
        created_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"])
        
        updated_at = None
        if data.get("updated_at"):
            updated_at = datetime.fromisoformat(data["updated_at"])
        
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            achievement_type=AchievementType(data["achievement_type"]),
            guild_id=data["guild_id"],
            trigger_conditions=trigger_conditions,
            rewards=rewards,
            status=AchievementStatus(data.get("status", "active")),
            metadata=data.get("metadata", {}),
            created_at=created_at,
            updated_at=updated_at
        )
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Achievement':
        """從資料庫行建立實例"""
        # 解析JSON欄位
        trigger_conditions_data = json.loads(row["trigger_conditions"])
        rewards_data = json.loads(row["rewards"])
        metadata = json.loads(row.get("metadata", "{}"))
        
        trigger_conditions = [
            TriggerCondition.from_dict(condition_data)
            for condition_data in trigger_conditions_data
        ]
        
        rewards = [
            AchievementReward.from_dict(reward_data)
            for reward_data in rewards_data
        ]
        
        # 轉換時間
        created_at = datetime.fromisoformat(row["created_at"])
        updated_at = datetime.fromisoformat(row["updated_at"])
        
        return cls(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            achievement_type=AchievementType(row["achievement_type"]),
            guild_id=row["guild_id"],
            trigger_conditions=trigger_conditions,
            rewards=rewards,
            status=AchievementStatus(row["status"]),
            metadata=metadata,
            created_at=created_at,
            updated_at=updated_at
        )


@dataclass
class AchievementProgress:
    """
    使用者成就進度
    
    追蹤個別使用者對特定成就的完成進度
    """
    id: str                                    # 進度記錄ID
    achievement_id: str                        # 成就ID
    user_id: int                              # 使用者ID
    guild_id: int                             # 伺服器ID
    current_progress: Dict[str, Any]          # 目前進度資料
    completed: bool = False                   # 是否已完成
    completed_at: Optional[datetime] = None   # 完成時間
    last_updated: Optional[datetime] = None   # 最後更新時間
    
    def __post_init__(self):
        """初始化後處理"""
        # 驗證和標準化ID
        self.achievement_id = validate_achievement_id(self.achievement_id)
        self.user_id = validate_user_id(self.user_id)
        self.guild_id = validate_guild_id(self.guild_id)
        
        # 設定預設時間
        if self.last_updated is None:
            self.last_updated = datetime.now()
    
    def validate(self) -> None:
        """
        驗證進度資料
        
        異常：
            ValidationError: 當資料無效時
        """
        # 基本驗證在__post_init__中已完成
        
        if self.current_progress is None:
            raise ValidationError(
                "進度資料不能為None",
                field="current_progress",
                value=self.current_progress,
                expected="Dict[str, Any]"
            )
        
        if not isinstance(self.current_progress, dict):
            raise ValidationError(
                "進度資料必須是字典格式",
                field="current_progress",
                value=type(self.current_progress),
                expected="dict"
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            "id": self.id,
            "achievement_id": self.achievement_id,
            "user_id": self.user_id,
            "guild_id": self.guild_id,
            "current_progress": self.current_progress,
            "completed": self.completed,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AchievementProgress':
        """從字典建立實例"""
        # 轉換時間
        completed_at = None
        if data.get("completed_at"):
            completed_at = datetime.fromisoformat(data["completed_at"])
        
        last_updated = None
        if data.get("last_updated"):
            last_updated = datetime.fromisoformat(data["last_updated"])
        
        return cls(
            id=data["id"],
            achievement_id=data["achievement_id"],
            user_id=data["user_id"],
            guild_id=data["guild_id"],
            current_progress=data["current_progress"],
            completed=data.get("completed", False),
            completed_at=completed_at,
            last_updated=last_updated
        )
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'AchievementProgress':
        """從資料庫行建立實例"""
        # 解析JSON欄位
        current_progress = json.loads(row["current_progress"])
        
        # 轉換時間
        completed_at = None
        if row.get("completed_at"):
            completed_at = datetime.fromisoformat(row["completed_at"])
        
        last_updated = datetime.fromisoformat(row["last_updated"])
        
        return cls(
            id=row["id"],
            achievement_id=row["achievement_id"],
            user_id=row["user_id"],
            guild_id=row["guild_id"],
            current_progress=current_progress,
            completed=bool(row["completed"]),
            completed_at=completed_at,
            last_updated=last_updated
        )
    
    def update_progress(self, new_progress: Dict[str, Any]) -> None:
        """
        更新進度資料
        
        參數：
            new_progress: 新的進度資料
        """
        self.current_progress.update(new_progress)
        self.last_updated = datetime.now()
    
    def mark_completed(self) -> None:
        """標記為已完成"""
        self.completed = True
        self.completed_at = datetime.now()
        self.last_updated = datetime.now()
    
    def get_progress_percentage(self, achievement: Achievement) -> float:
        """
        計算完成百分比（針對數值類型的觸發條件）
        
        參數：
            achievement: 對應的成就配置
            
        返回：
            完成百分比 (0.0 - 1.0)
        """
        if self.completed:
            return 1.0
        
        if not achievement.trigger_conditions:
            return 0.0
        
        # 簡化計算：取第一個數值類型觸發條件
        for condition in achievement.trigger_conditions:
            trigger_type_value = (
                condition.trigger_type.value if isinstance(condition.trigger_type, TriggerType)
                else condition.trigger_type
            )
            
            current_value = self.current_progress.get(trigger_type_value, 0)
            target_value = condition.target_value
            
            if target_value > 0:
                progress_ratio = min(current_value / target_value, 1.0)
                return progress_ratio
        
        return 0.0


# =============================================================================
# 輔助函數
# =============================================================================

def generate_progress_id(user_id: int, achievement_id: str) -> str:
    """
    生成進度記錄ID
    
    參數：
        user_id: 使用者ID
        achievement_id: 成就ID
        
    返回：
        進度記錄ID
    """
    return f"progress_{user_id}_{achievement_id}"


def create_default_progress(achievement_id: str, user_id: int, guild_id: int) -> AchievementProgress:
    """
    創建預設的進度記錄
    
    參數：
        achievement_id: 成就ID
        user_id: 使用者ID
        guild_id: 伺服器ID
        
    返回：
        新的進度記錄
    """
    progress_id = generate_progress_id(user_id, achievement_id)
    
    return AchievementProgress(
        id=progress_id,
        achievement_id=achievement_id,
        user_id=user_id,
        guild_id=guild_id,
        current_progress={},
        completed=False,
        completed_at=None,
        last_updated=datetime.now()
    )