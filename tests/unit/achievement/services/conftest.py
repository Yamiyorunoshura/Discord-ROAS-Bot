"""成就系統服務層測試配置.

此模組提供成就系統服務層測試的共用配置和 fixtures，包含：
- 測試資料庫設置
- Mock 物件建立
- 測試資料工廠
- 共用測試工具

遵循測試最佳實踐，提供可重複和可靠的測試環境。
"""

import asyncio
import tempfile
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from src.cogs.achievement.database.models import (
    Achievement,
    AchievementCategory,
    AchievementProgress,
    AchievementType,
    UserAchievement,
)
from src.cogs.achievement.database.repository import AchievementRepository
from src.cogs.achievement.services import (
    AchievementService,
    ProgressTracker,
    TriggerEngine,
)
from src.core.database import DatabasePool


@pytest.fixture(scope="session")
def event_loop():
    """建立事件循環 fixture."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def temp_db_pool() -> AsyncGenerator[DatabasePool, None]:
    """建立臨時資料庫連線池 fixture."""
    # 建立臨時資料庫檔案
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        temp_db_path = Path(tmp_file.name)

    # 建立簡單的測試設定
    from src.core.config import Settings
    test_settings = Settings()

    pool = None
    try:
        # 建立資料庫連線池
        pool = DatabasePool(temp_db_path, test_settings)
        await pool.initialize()

        # 建立測試所需的表格
        await _create_test_tables(pool)

        yield pool

    finally:
        # 清理
        if pool:
            await pool.close_all()
        temp_db_path.unlink(missing_ok=True)


async def _create_test_tables(pool: DatabasePool) -> None:
    """建立測試所需的資料庫表格."""
    async with pool.get_connection() as conn:
        # 建立成就分類表
        await conn.execute("""
            CREATE TABLE achievement_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL,
                display_order INTEGER DEFAULT 0,
                icon_emoji TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 建立成就表
        await conn.execute("""
            CREATE TABLE achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                category_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                criteria TEXT NOT NULL,
                points INTEGER DEFAULT 0,
                badge_url TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES achievement_categories (id)
            )
        """)

        # 建立用戶成就表
        await conn.execute("""
            CREATE TABLE user_achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                achievement_id INTEGER NOT NULL,
                earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notified BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (achievement_id) REFERENCES achievements (id),
                UNIQUE(user_id, achievement_id)
            )
        """)

        # 建立成就進度表
        await conn.execute("""
            CREATE TABLE achievement_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                achievement_id INTEGER NOT NULL,
                current_value REAL DEFAULT 0.0,
                target_value REAL NOT NULL,
                progress_data TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (achievement_id) REFERENCES achievements (id),
                UNIQUE(user_id, achievement_id)
            )
        """)

        await conn.commit()


@pytest_asyncio.fixture
async def repository(temp_db_pool: DatabasePool) -> AchievementRepository:
    """建立成就資料存取庫 fixture."""
    return AchievementRepository(temp_db_pool)


@pytest_asyncio.fixture
async def achievement_service(repository: AchievementRepository) -> AchievementService:
    """建立成就服務 fixture."""
    return AchievementService(
        repository=repository,
        cache_ttl=60,  # 測試時使用短快取時間
        cache_maxsize=100
    )


@pytest_asyncio.fixture
async def progress_tracker(repository: AchievementRepository) -> ProgressTracker:
    """建立進度追蹤器 fixture."""
    return ProgressTracker(repository)


@pytest_asyncio.fixture
async def trigger_engine(
    repository: AchievementRepository,
    progress_tracker: ProgressTracker
) -> TriggerEngine:
    """建立觸發引擎 fixture."""
    return TriggerEngine(repository, progress_tracker)


# =============================================================================
# 測試資料工廠
# =============================================================================

@pytest.fixture
def sample_category() -> AchievementCategory:
    """建立範例成就分類."""
    return AchievementCategory(
        name="social",
        description="社交互動相關成就",
        display_order=1,
        icon_emoji="👥"
    )


@pytest.fixture
def sample_achievement() -> Achievement:
    """建立範例成就."""
    return Achievement(
        name="社交達人",
        description="與其他用戶互動超過 100 次",
        category_id=1,
        type=AchievementType.COUNTER,
        criteria={
            "target_value": 100,
            "counter_field": "social_interactions"
        },
        points=500,
        role_reward="社交專家",
        is_hidden=False
    )


@pytest.fixture
def sample_user_achievement() -> UserAchievement:
    """建立範例用戶成就."""
    return UserAchievement(
        user_id=123456789,
        achievement_id=1,
        earned_at=datetime.now(),
        notified=False
    )


@pytest.fixture
def sample_progress() -> AchievementProgress:
    """建立範例成就進度."""
    return AchievementProgress(
        user_id=123456789,
        achievement_id=1,
        current_value=75.0,
        target_value=100.0,
        progress_data={
            "daily_interactions": [5, 8, 12, 10, 7],
            "streak_days": 5
        }
    )


# =============================================================================
# Mock 物件工廠
# =============================================================================

@pytest.fixture
def mock_repository() -> AsyncMock:
    """建立 Mock Repository."""
    mock = AsyncMock(spec=AchievementRepository)

    # 設定預設的返回值
    mock.get_achievement_by_id.return_value = Achievement(
        id=1,
        name="測試成就",
        description="測試用成就",
        category_id=1,
        type=AchievementType.COUNTER,
        criteria={
            "target_value": 100,
            "counter_field": "test_counter"
        },
        points=100,
        is_active=True,
        role_reward=None,
        is_hidden=False
    )

    mock.get_category_by_id.return_value = AchievementCategory(
        id=1,
        name="test",
        description="測試分類",
        display_order=1
    )

    mock.has_user_achievement.return_value = False

    return mock


@pytest.fixture
def mock_progress_tracker() -> AsyncMock:
    """建立 Mock ProgressTracker."""
    mock = AsyncMock(spec=ProgressTracker)

    mock.update_user_progress.return_value = AchievementProgress(
        id=1,
        user_id=123456789,
        achievement_id=1,
        current_value=50.0,
        target_value=100.0
    )

    return mock


@pytest.fixture
def mock_cache() -> MagicMock:
    """建立 Mock 快取物件."""
    mock = MagicMock()
    mock.keys.return_value = []
    mock.pop.return_value = None
    mock.__contains__ = MagicMock(return_value=False)
    mock.__getitem__ = MagicMock(side_effect=KeyError)
    mock.__setitem__ = MagicMock()
    return mock


# =============================================================================
# 測試工具函數
# =============================================================================

async def create_test_category(
    repository: AchievementRepository,
    name: str = "test_category",
    description: str = "測試分類"
) -> AchievementCategory:
    """建立測試用成就分類."""
    category = AchievementCategory(
        name=name,
        description=description,
        display_order=1,
        icon_emoji="🏆"
    )
    return await repository.create_category(category)


async def create_test_achievement(
    repository: AchievementRepository,
    category_id: int,
    name: str = "test_achievement",
    achievement_type: AchievementType = AchievementType.COUNTER,
    role_reward: str = None,
    is_hidden: bool = False
) -> Achievement:
    """建立測試用成就."""
    achievement = Achievement(
        name=name,
        description="測試用成就",
        category_id=category_id,
        type=achievement_type,
        criteria={
            "target_value": 100,
            "counter_field": "test_counter" if achievement_type == AchievementType.COUNTER else None
        },
        points=100,
        is_active=True,
        role_reward=role_reward,
        is_hidden=is_hidden
    )
    return await repository.create_achievement(achievement)


def create_trigger_context(
    user_id: int = 123456789,
    **kwargs
) -> dict[str, Any]:
    """建立觸發上下文資料."""
    context = {
        "user_id": user_id,
        "timestamp": datetime.now().isoformat()
    }
    context.update(kwargs)
    return context


# =============================================================================
# 測試標記
# =============================================================================

# 為不同類型的測試定義標記
pytest_mark_unit = pytest.mark.unit
pytest_mark_integration = pytest.mark.integration
pytest_mark_database = pytest.mark.database
pytest_mark_slow = pytest.mark.slow
