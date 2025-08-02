"""成就系統資料庫模組."""

from .migrations import AchievementMigrations, initialize_achievement_database
from .models import (
    Achievement,
    AchievementCategory,
    AchievementProgress,
    AchievementType,
    UserAchievement,
    create_sample_achievement,
    create_sample_achievement_category,
    create_sample_achievement_progress,
    create_sample_user_achievement,
)
from .repository import AchievementRepository

__all__ = [
    # 模型
    "Achievement",
    "AchievementCategory",
    # 遷移
    "AchievementMigrations",
    "AchievementProgress",
    # 資料存取層
    "AchievementRepository",
    "AchievementType",
    "UserAchievement",
    # 範例工廠函數
    "create_sample_achievement",
    "create_sample_achievement_category",
    "create_sample_achievement_progress",
    "create_sample_user_achievement",
    "initialize_achievement_database",
]
