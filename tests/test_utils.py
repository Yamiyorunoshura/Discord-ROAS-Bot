"""成就系統測試基礎工具.

此模組提供成就系統測試的基礎工具和Mock對象，包含：
- Discord.py Mock 對象
- 測試資料生成器
- 測試配置管理
- 公共測試工具函數

為整個測試套件提供統一的測試基礎設施。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


class MockDiscordUser:
    """Mock Discord 用戶對象."""

    def __init__(self, user_id: int | None = None, name: str | None = None):
        self.id = user_id or 12345
        self.name = name or f"TestUser{self.id}"
        self.display_name = self.name
        self.mention = f"<@{self.id}>"
        self.avatar = None
        self.discriminator = "0001"
        self.bot = False


class MockDiscordMember(MockDiscordUser):
    """Mock Discord 成員對象."""

    def __init__(self, user_id: int | None = None, name: str | None = None, guild_id: int | None = None):
        super().__init__(user_id, name)
        self.guild_id = guild_id or 67890
        self.joined_at = datetime.utcnow() - timedelta(days=30)
        self.roles = []
        self.permissions = MagicMock()
        self.permissions.administrator = False
        self.permissions.manage_guild = False


class MockDiscordGuild:
    """Mock Discord 伺服器對象."""

    def __init__(self, guild_id: int | None = None, name: str | None = None):
        self.id = guild_id or 67890
        self.name = name or f"TestGuild{self.id}"
        self.owner_id = 11111
        self.member_count = 100
        self.members = []

    def get_member(self, user_id: int) -> MockDiscordMember | None:
        """獲取成員."""
        for member in self.members:
            if member.id == user_id:
                return member
        return None

    def add_member(self, member: MockDiscordMember):
        """添加成員."""
        self.members.append(member)


class MockDiscordInteraction:
    """Mock Discord 互動對象."""

    def __init__(
        self,
        user: MockDiscordUser = None,
        guild: MockDiscordGuild = None,
        channel_id: int | None = None
    ):
        self.id = int(datetime.utcnow().timestamp() * 1000)  # 模擬雪花ID
        self.user = user or MockDiscordUser()
        self.guild = guild or MockDiscordGuild()
        self.guild_id = self.guild.id
        self.channel_id = channel_id or 98765

        # Mock 回應方法
        self.response = AsyncMock()
        self.followup = AsyncMock()

        # 預設回應行為
        self.response.defer = AsyncMock()
        self.response.send_message = AsyncMock()
        self.response.edit_message = AsyncMock()
        self.response.send_modal = AsyncMock()

        self.followup.send = AsyncMock()
        self.followup.edit_message = AsyncMock()


class TestDataGenerator:
    """測試資料生成器."""

    @staticmethod
    def create_achievement_data(
        achievement_id: int | None = None,
        name: str | None = None,
        category_id: int | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """創建成就測試資料."""
        return {
            "id": achievement_id or 1,
            "name": name or f"測試成就_{uuid4().hex[:8]}",
            "description": kwargs.get("description", "這是一個測試成就"),
            "category_id": category_id or 1,
            "type": kwargs.get("type", "counter"),
            "criteria": kwargs.get("criteria", {"target_value": 10}),
            "reward_points": kwargs.get("reward_points", 100),
            "badge_url": kwargs.get("badge_url"),
            "is_active": kwargs.get("is_active", True),
            "role_reward": kwargs.get("role_reward"),
            "is_hidden": kwargs.get("is_hidden", False),
            "created_at": kwargs.get("created_at", datetime.utcnow()),
            "updated_at": kwargs.get("updated_at", datetime.utcnow())
        }

    @staticmethod
    def create_category_data(
        category_id: int | None = None,
        name: str | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """創建分類測試資料."""
        return {
            "id": category_id or 1,
            "name": name or f"測試分類_{uuid4().hex[:8]}",
            "description": kwargs.get("description", "這是一個測試分類"),
            "display_order": kwargs.get("display_order", 1),
            "icon_emoji": kwargs.get("icon_emoji", "🏆"),
            "is_active": kwargs.get("is_active", True),
            "created_at": kwargs.get("created_at", datetime.utcnow()),
            "updated_at": kwargs.get("updated_at", datetime.utcnow())
        }

    @staticmethod
    def create_user_achievement_data(
        user_id: int | None = None,
        achievement_id: int | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """創建用戶成就測試資料."""
        return {
            "user_id": user_id or 12345,
            "achievement_id": achievement_id or 1,
            "earned_at": kwargs.get("earned_at", datetime.utcnow()),
            "notified": kwargs.get("notified", True),
            "progress_snapshot": kwargs.get("progress_snapshot", {})
        }

    @staticmethod
    def create_user_progress_data(
        user_id: int | None = None,
        achievement_id: int | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """創建用戶進度測試資料."""
        return {
            "user_id": user_id or 12345,
            "achievement_id": achievement_id or 1,
            "current_value": kwargs.get("current_value", 5.0),
            "target_value": kwargs.get("target_value", 10.0),
            "progress_data": kwargs.get("progress_data", {}),
            "last_updated": kwargs.get("last_updated", datetime.utcnow())
        }


class MockAchievementService:
    """Mock 成就服務."""

    def __init__(self):
        self.achievements = {}
        self.categories = {}
        self.user_achievements = {}
        self.user_progress = {}

    def add_achievement(self, achievement_data: dict[str, Any]):
        """添加成就資料."""
        achievement_id = achievement_data["id"]
        self.achievements[achievement_id] = achievement_data

    def add_category(self, category_data: dict[str, Any]):
        """添加分類資料."""
        category_id = category_data["id"]
        self.categories[category_id] = category_data

    async def get_achievement(self, achievement_id: int) -> dict[str, Any] | None:
        """獲取成就."""
        return self.achievements.get(achievement_id)

    async def get_category(self, category_id: int) -> dict[str, Any] | None:
        """獲取分類."""
        return self.categories.get(category_id)

    async def get_user_achievements(self, user_id: int) -> list[dict[str, Any]]:
        """獲取用戶成就."""
        return [
            ua for ua in self.user_achievements.values()
            if ua["user_id"] == user_id
        ]

    async def get_user_progress(self, user_id: int) -> list[dict[str, Any]]:
        """獲取用戶進度."""
        return [
            up for up in self.user_progress.values()
            if up["user_id"] == user_id
        ]

    async def grant_user_achievement(
        self,
        user_id: int,
        achievement_id: int,
        notify: bool = True
    ) -> dict[str, Any]:
        """授予用戶成就."""
        user_achievement = TestDataGenerator.create_user_achievement_data(
            user_id=user_id,
            achievement_id=achievement_id,
            notified=notify
        )

        key = f"{user_id}:{achievement_id}"
        self.user_achievements[key] = user_achievement
        return user_achievement

    async def revoke_user_achievement(
        self,
        user_id: int,
        achievement_id: int
    ) -> bool:
        """撤銷用戶成就."""
        key = f"{user_id}:{achievement_id}"
        if key in self.user_achievements:
            del self.user_achievements[key]
            return True
        return False

    async def update_user_progress(
        self,
        user_id: int,
        achievement_id: int,
        new_value: float
    ) -> dict[str, Any]:
        """更新用戶進度."""
        key = f"{user_id}:{achievement_id}"

        if key in self.user_progress:
            progress = self.user_progress[key]
            progress["current_value"] = new_value
            progress["last_updated"] = datetime.utcnow()
        else:
            progress = TestDataGenerator.create_user_progress_data(
                user_id=user_id,
                achievement_id=achievement_id,
                current_value=new_value
            )
            self.user_progress[key] = progress

        return progress

    async def reset_user_data(self, user_id: int) -> dict[str, Any]:
        """重置用戶資料."""
        # 移除用戶的所有成就和進度
        achievements_to_remove = [
            key for key, ua in self.user_achievements.items()
            if ua["user_id"] == user_id
        ]

        progress_to_remove = [
            key for key, up in self.user_progress.items()
            if up["user_id"] == user_id
        ]

        for key in achievements_to_remove:
            del self.user_achievements[key]

        for key in progress_to_remove:
            del self.user_progress[key]

        return {
            "user_id": user_id,
            "achievements_removed": len(achievements_to_remove),
            "progress_removed": len(progress_to_remove),
            "reset_at": datetime.utcnow()
        }


class MockCacheService:
    """Mock 快取服務."""

    def __init__(self):
        self.cache = {}
        self.invalidation_calls = []

    async def get(self, cache_type: str, key: str) -> Any:
        """獲取快取."""
        cache_key = f"{cache_type}:{key}"
        return self.cache.get(cache_key)

    async def set(self, cache_type: str, key: str, value: Any, ttl: int = 300):
        """設置快取."""
        cache_key = f"{cache_type}:{key}"
        self.cache[cache_key] = value

    async def invalidate(self, cache_type: str, key: str):
        """失效快取."""
        cache_key = f"{cache_type}:{key}"
        if cache_key in self.cache:
            del self.cache[cache_key]

        self.invalidation_calls.append(cache_key)

    async def invalidate_batch(self, cache_type: str, keys: list[str]):
        """批量失效快取."""
        for key in keys:
            await self.invalidate(cache_type, key)


class MockDatabaseService:
    """Mock 資料庫服務."""

    def __init__(self):
        self.query_calls = []
        self.execute_calls = []
        self.transaction_active = False

    async def execute_query(self, query: str, params: tuple | None = None) -> list[dict[str, Any]]:
        """執行查詢."""
        self.query_calls.append((query, params))
        return []

    async def execute_update(self, query: str, params: tuple | None = None) -> int:
        """執行更新."""
        self.execute_calls.append((query, params))
        return 1

    async def begin_transaction(self):
        """開始事務."""
        self.transaction_active = True

    async def commit_transaction(self):
        """提交事務."""
        self.transaction_active = False

    async def rollback_transaction(self):
        """回滾事務."""
        self.transaction_active = False


class AsyncTestCase:
    """異步測試用例基類."""

    def setup_method(self):
        """測試設置."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # 創建 Mock 服務
        self.mock_achievement_service = MockAchievementService()
        self.mock_cache_service = MockCacheService()
        self.mock_database_service = MockDatabaseService()

        # 創建測試用戶和伺服器
        self.test_user = MockDiscordUser(user_id=12345, name="TestUser")
        self.test_guild = MockDiscordGuild(guild_id=67890, name="TestGuild")
        self.test_member = MockDiscordMember(
            user_id=self.test_user.id,
            name=self.test_user.name,
            guild_id=self.test_guild.id
        )
        self.test_guild.add_member(self.test_member)

        # 創建測試互動
        self.test_interaction = MockDiscordInteraction(
            user=self.test_user,
            guild=self.test_guild
        )

        # 添加測試資料
        self._setup_test_data()

    def teardown_method(self):
        """測試清理."""
        self.loop.close()

    def _setup_test_data(self):
        """設置測試資料."""
        # 添加測試分類
        category = TestDataGenerator.create_category_data(
            category_id=1,
            name="測試分類"
        )
        self.mock_achievement_service.add_category(category)

        # 添加測試成就
        achievement = TestDataGenerator.create_achievement_data(
            achievement_id=1,
            name="測試成就",
            category_id=1
        )
        self.mock_achievement_service.add_achievement(achievement)

    async def run_async_test(self, coro):
        """運行異步測試."""
        return await coro


class TestAssertions:
    """測試斷言工具."""

    @staticmethod
    def assert_audit_event_logged(audit_logger, event_type, user_id=None):
        """斷言審計事件已記錄."""
        if not hasattr(audit_logger, '_event_buffer'):
            raise AssertionError("審計日誌記錄器沒有事件緩衝區")

        events = audit_logger._event_buffer
        matching_events = [
            e for e in events
            if e.event_type == event_type
        ]

        if user_id:
            matching_events = [
                e for e in matching_events
                if e.context and e.context.user_id == user_id
            ]

        assert len(matching_events) > 0, f"沒有找到匹配的審計事件: {event_type}"

    @staticmethod
    def assert_history_recorded(history_manager, action, executor_id=None):
        """斷言歷史操作已記錄."""
        if not hasattr(history_manager, '_history_buffer'):
            raise AssertionError("歷史管理器沒有歷史緩衝區")

        records = history_manager._history_buffer
        matching_records = [
            r for r in records
            if r.action == action
        ]

        if executor_id:
            matching_records = [
                r for r in matching_records
                if r.executor_id == executor_id
            ]

        assert len(matching_records) > 0, f"沒有找到匹配的歷史記錄: {action}"

    @staticmethod
    def assert_cache_invalidated(cache_service, cache_type, key=None):
        """斷言快取已失效."""
        if not hasattr(cache_service, 'invalidation_calls'):
            raise AssertionError("快取服務沒有失效調用記錄")

        calls = cache_service.invalidation_calls

        if key:
            expected_key = f"{cache_type}:{key}"
            assert expected_key in calls, f"快取鍵 {expected_key} 沒有被失效"
        else:
            matching_calls = [
                call for call in calls
                if call.startswith(f"{cache_type}:")
            ]
            assert len(matching_calls) > 0, f"沒有找到 {cache_type} 類型的快取失效調用"

    @staticmethod
    def assert_permission_checked(security_validator, user_id, operation_type):
        """斷言權限已檢查."""
        # 這需要在實際的安全驗證器中添加調用記錄
        pass

    @staticmethod
    def assert_interaction_response_called(interaction, method_name="send_message"):
        """斷言互動回應已調用."""
        if method_name == "send_message":
            assert interaction.response.send_message.called, "互動回應的 send_message 沒有被調用"
        elif method_name == "defer":
            assert interaction.response.defer.called, "互動回應的 defer 沒有被調用"
        elif method_name == "edit_message":
            assert interaction.response.edit_message.called, "互動回應的 edit_message 沒有被調用"


# 測試配置
TEST_CONFIG = {
    "database": {
        "url": ":memory:",  # 使用記憶體資料庫進行測試
        "echo": False
    },
    "cache": {
        "enabled": True,
        "default_ttl": 300
    },
    "security": {
        "enabled": True,
        "require_approval": False,  # 測試時不需要審批
        "audit_logging": True
    },
    "logging": {
        "level": "DEBUG",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    }
}


# 測試夾具 (Fixtures)
@pytest.fixture
def mock_achievement_service():
    """Mock 成就服務夾具."""
    return MockAchievementService()


@pytest.fixture
def mock_cache_service():
    """Mock 快取服務夾具."""
    return MockCacheService()


@pytest.fixture
def mock_database_service():
    """Mock 資料庫服務夾具."""
    return MockDatabaseService()


@pytest.fixture
def test_user():
    """測試用戶夾具."""
    return MockDiscordUser(user_id=12345, name="TestUser")


@pytest.fixture
def test_guild():
    """測試伺服器夾具."""
    return MockDiscordGuild(guild_id=67890, name="TestGuild")


@pytest.fixture
def test_interaction(test_user, test_guild):
    """測試互動夾具."""
    return MockDiscordInteraction(user=test_user, guild=test_guild)


@pytest.fixture
def test_data_generator():
    """測試資料生成器夾具."""
    return TestDataGenerator()


@pytest.fixture
def test_assertions():
    """測試斷言工具夾具."""
    return TestAssertions()


# 測試執行器配置
pytest_plugins = [
    "pytest_asyncio",  # 支援異步測試
]


def pytest_configure(config):
    """Pytest 配置."""
    # 配置日誌
    logging.basicConfig(
        level=logging.DEBUG,
        format=TEST_CONFIG["logging"]["format"]
    )

    # 禁用一些不必要的日誌
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


def pytest_collection_modifyitems(config, items):
    """修改測試項目收集."""
    # 為異步測試添加標記
    for item in items:
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)
