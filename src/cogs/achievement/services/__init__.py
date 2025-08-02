"""成就系統服務層模組.

此模組提供成就系統的業務邏輯服務, 包含:
- AchievementService: 成就核心業務邏輯
- AchievementCacheService: 成就快取管理服務
- ProgressTracker: 成就進度追蹤服務
- TriggerEngine: 成就觸發檢查引擎

所有服務遵循以下設計原則:
- 使用 Repository Pattern 進行資料存取
- 支援依賴注入和容器化管理
- 提供完整的錯誤處理和日誌記錄
- 支援快取策略和效能優化
"""

from .achievement_service import AchievementService
from .cache_config_manager import CacheConfigManager, CacheConfigUpdate
from .cache_key_standard import CacheKeyPattern, CacheKeyStandard, CacheKeyType
from .cache_service import AchievementCacheService
from .progress_tracker import ProgressTracker
from .trigger_engine import TriggerEngine

__all__ = [
    "AchievementCacheService",
    "AchievementService",
    "CacheConfigManager",
    "CacheConfigUpdate",
    "CacheKeyPattern",
    "CacheKeyStandard",
    "CacheKeyType",
    "ProgressTracker",
    "TriggerEngine",
]
