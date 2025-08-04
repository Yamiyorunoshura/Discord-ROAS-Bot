"""測試資料工廠模式.

此模組提供統一的測試資料生成機制,支援:
- 成就系統測試數據生成
- 用戶和伺服器模擬數據
- Discord物件模擬
- 資料庫測試記錄生成
"""

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import discord

# 確保正確的導入路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class DiscordObjectFactory:
    """Discord物件工廠."""

    @staticmethod
    def create_user(
        user_id: int | None = None,
        username: str | None = None,
        discriminator: str | None = None,
        bot: bool = False,
        **kwargs,
    ) -> MagicMock:
        """創建模擬Discord用戶."""
        user = MagicMock(spec=discord.User)
        user.id = user_id or random.randint(100000000000000000, 999999999999999999)
        user.name = username or f"test_user_{random.randint(1000, 9999)}"
        user.discriminator = discriminator or f"{random.randint(1, 9999):04d}"
        user.bot = bot
        user.mention = f"<@{user.id}>"
        user.display_name = user.name
        user.created_at = datetime.utcnow() - timedelta(days=random.randint(30, 365))

        # 設置其他屬性
        for key, value in kwargs.items():
            setattr(user, key, value)

        return user

    @staticmethod
    def create_member(
        user: discord.User = None,
        guild: discord.Guild = None,
        nick: str | None = None,
        roles: list[discord.Role] | None = None,
        **kwargs,
    ) -> MagicMock:
        """創建模擬Discord成員."""
        member = MagicMock(spec=discord.Member)

        if user is None:
            user = DiscordObjectFactory.create_user()

        # 繼承用戶屬性
        member.id = user.id
        member.name = user.name
        member.discriminator = user.discriminator
        member.bot = user.bot
        member.mention = user.mention
        member.created_at = user.created_at

        # 成員特有屬性
        member.nick = nick
        member.display_name = nick or user.name
        member.joined_at = datetime.utcnow() - timedelta(days=random.randint(1, 100))
        member.roles = roles or []
        member.guild = guild

        # 權限相關
        member.guild_permissions = MagicMock()
        member.guild_permissions.administrator = False
        member.guild_permissions.manage_messages = False

        for key, value in kwargs.items():
            setattr(member, key, value)

        return member

    @staticmethod
    def create_guild(
        guild_id: int | None = None,
        name: str | None = None,
        member_count: int | None = None,
        **kwargs,
    ) -> MagicMock:
        """創建模擬Discord伺服器."""
        guild = MagicMock(spec=discord.Guild)
        guild.id = guild_id or random.randint(100000000000000000, 999999999999999999)
        guild.name = name or f"Test Guild {random.randint(1, 100)}"
        guild.member_count = member_count or random.randint(10, 1000)
        guild.created_at = datetime.utcnow() - timedelta(days=random.randint(30, 1000))
        guild.icon = None
        guild.banner = None

        for key, value in kwargs.items():
            setattr(guild, key, value)

        return guild

    @staticmethod
    def create_channel(
        channel_id: int | None = None,
        name: str | None = None,
        guild: discord.Guild = None,
        channel_type: discord.ChannelType = discord.ChannelType.text,
        **kwargs,
    ) -> MagicMock:
        """創建模擬Discord頻道."""
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = channel_id or random.randint(
            100000000000000000, 999999999999999999
        )
        channel.name = name or f"test-channel-{random.randint(1, 100)}"
        channel.guild = guild
        channel.type = channel_type
        channel.mention = f"<#{channel.id}>"
        channel.created_at = datetime.utcnow() - timedelta(days=random.randint(1, 100))

        for key, value in kwargs.items():
            setattr(channel, key, value)

        return channel

    @staticmethod
    def create_interaction(
        user: discord.User = None,
        guild: discord.Guild = None,
        channel: discord.TextChannel = None,
        **kwargs,
    ) -> MagicMock:
        """創建模擬Discord交互."""
        interaction = MagicMock(spec=discord.Interaction)

        interaction.user = user or DiscordObjectFactory.create_user()
        interaction.guild = guild or DiscordObjectFactory.create_guild()
        interaction.channel = channel or DiscordObjectFactory.create_channel(
            guild=interaction.guild
        )
        interaction.guild_id = interaction.guild.id
        interaction.channel_id = interaction.channel.id

        # 響應相關
        interaction.response = MagicMock()
        interaction.followup = MagicMock()
        interaction.response.send_message = MagicMock()
        interaction.followup.send = MagicMock()

        for key, value in kwargs.items():
            setattr(interaction, key, value)

        return interaction


class AchievementDataFactory:
    """成就系統測試數據工廠."""

    @staticmethod
    def create_achievement_data(
        achievement_id: int | None = None,
        name: str | None = None,
        description: str | None = None,
        category_id: int | None = None,
        target_value: int | None = None,
        icon_emoji: str | None = None,
        is_hidden: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        """創建成就測試數據."""
        return {
            "id": achievement_id or random.randint(1, 1000),
            "name": name or f"測試成就 {random.randint(1, 100)}",
            "description": description
            or f"這是一個測試成就的描述 {random.randint(1, 100)}",
            "category_id": category_id or random.randint(1, 10),
            "target_value": target_value or random.randint(10, 1000),
            "icon_emoji": icon_emoji or random.choice(["🏆", "⭐", "🎯", "💎", "🔥"]),
            "role_reward": kwargs.get("role_reward"),
            "is_hidden": is_hidden,
            "created_at": datetime.utcnow() - timedelta(days=random.randint(1, 100)),
            "updated_at": datetime.utcnow() - timedelta(hours=random.randint(1, 24)),
            **kwargs,
        }

    @staticmethod
    def create_user_achievement_data(
        user_id: int | None = None,
        achievement_id: int | None = None,
        current_progress: int | None = None,
        is_completed: bool | None = None,
        completed_at: datetime | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """創建用戶成就進度數據."""
        is_completed = is_completed or random.choice([True, False])

        return {
            "user_id": user_id
            or random.randint(100000000000000000, 999999999999999999),
            "achievement_id": achievement_id or random.randint(1, 100),
            "current_progress": current_progress or random.randint(0, 100),
            "is_completed": is_completed,
            "completed_at": completed_at if is_completed else None,
            "created_at": datetime.utcnow() - timedelta(days=random.randint(1, 30)),
            "updated_at": datetime.utcnow() - timedelta(hours=random.randint(1, 12)),
            **kwargs,
        }

    @staticmethod
    def create_achievement_category_data(
        category_id: int | None = None,
        name: str | None = None,
        description: str | None = None,
        icon_emoji: str | None = None,
        sort_order: int | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """創建成就分類數據."""
        return {
            "id": category_id or random.randint(1, 50),
            "name": name or f"測試分類 {random.randint(1, 20)}",
            "description": description or f"測試分類描述 {random.randint(1, 20)}",
            "icon_emoji": icon_emoji or random.choice(["📚", "🎮", "💬", "⚡", "🌟"]),
            "sort_order": sort_order or random.randint(1, 100),
            "created_at": datetime.utcnow() - timedelta(days=random.randint(1, 50)),
            **kwargs,
        }

    @staticmethod
    def create_multiple_achievements(count: int = 5) -> list[dict[str, Any]]:
        """創建多個成就數據."""
        return [AchievementDataFactory.create_achievement_data() for _ in range(count)]

    @staticmethod
    def create_user_progress_batch(
        user_id: int, achievement_count: int = 10, completion_rate: float = 0.3
    ) -> list[dict[str, Any]]:
        """為用戶創建批量進度數據."""
        achievements = AchievementDataFactory.create_multiple_achievements(
            achievement_count
        )
        progress_data = []

        for achievement in achievements:
            is_completed = random.random() < completion_rate
            progress = AchievementDataFactory.create_user_achievement_data(
                user_id=user_id,
                achievement_id=achievement["id"],
                is_completed=is_completed,
                current_progress=achievement["target_value"]
                if is_completed
                else random.randint(0, achievement["target_value"] - 1),
            )
            progress_data.append(progress)

        return progress_data


class DatabaseTestDataFactory:
    """資料庫測試數據工廠."""

    @staticmethod
    def create_test_database_records(
        table_name: str, count: int = 10, **base_data
    ) -> list[dict[str, Any]]:
        """創建測試資料庫記錄."""
        records = []

        for i in range(count):
            record = {
                "id": i + 1,
                "created_at": datetime.utcnow()
                - timedelta(minutes=random.randint(1, 1440)),
                "updated_at": datetime.utcnow()
                - timedelta(minutes=random.randint(1, 60)),
                **base_data,
            }
            records.append(record)

        return records

    @staticmethod
    def create_activity_meter_data(
        user_id: int | None = None,
        guild_id: int | None = None,
        message_count: int | None = None,
        voice_time: int | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """創建活動度量測試數據."""
        return {
            "user_id": user_id
            or random.randint(100000000000000000, 999999999999999999),
            "guild_id": guild_id
            or random.randint(100000000000000000, 999999999999999999),
            "message_count": message_count or random.randint(0, 1000),
            "voice_time": voice_time or random.randint(0, 7200),  # 秒
            "last_activity": datetime.utcnow() - timedelta(hours=random.randint(1, 24)),
            "activity_score": random.randint(0, 100),
            **kwargs,
        }

    @staticmethod
    def create_message_listener_data(
        message_id: int | None = None,
        user_id: int | None = None,
        channel_id: int | None = None,
        content_length: int | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """創建消息監聽測試數據."""
        return {
            "message_id": message_id
            or random.randint(100000000000000000, 999999999999999999),
            "user_id": user_id
            or random.randint(100000000000000000, 999999999999999999),
            "channel_id": channel_id
            or random.randint(100000000000000000, 999999999999999999),
            "content_length": content_length or random.randint(1, 2000),
            "has_attachment": random.choice([True, False]),
            "timestamp": datetime.utcnow() - timedelta(minutes=random.randint(1, 1440)),
            **kwargs,
        }


class TestScenarioFactory:
    """測試場景工廠."""

    @staticmethod
    def create_achievement_unlock_scenario() -> dict[str, Any]:
        """創建成就解鎖測試場景."""
        user = DiscordObjectFactory.create_user()
        guild = DiscordObjectFactory.create_guild()
        achievement = AchievementDataFactory.create_achievement_data()

        return {
            "user": user,
            "guild": guild,
            "achievement": achievement,
            "trigger_event": {
                "type": "message_sent",
                "data": {
                    "message_count": achievement["target_value"],
                    "timestamp": datetime.utcnow(),
                },
            },
            "expected_result": {
                "achievement_unlocked": True,
                "notification_sent": True,
                "progress_updated": True,
            },
        }

    @staticmethod
    def create_panel_interaction_scenario() -> dict[str, Any]:
        """創建面板交互測試場景."""
        user = DiscordObjectFactory.create_user()
        guild = DiscordObjectFactory.create_guild()
        interaction = DiscordObjectFactory.create_interaction(user=user, guild=guild)

        user_achievements = AchievementDataFactory.create_user_progress_batch(
            user_id=user.id, achievement_count=15, completion_rate=0.4
        )

        return {
            "interaction": interaction,
            "user_achievements": user_achievements,
            "panel_type": "personal_achievements",
            "expected_embeds": 1,
            "expected_components": [
                "category_selector",
                "refresh_button",
                "close_button",
            ],
        }

    @staticmethod
    def create_bulk_operation_scenario() -> dict[str, Any]:
        """創建批量操作測試場景."""
        users = [DiscordObjectFactory.create_user() for _ in range(10)]
        achievement = AchievementDataFactory.create_achievement_data()
        admin_user = DiscordObjectFactory.create_user(username="admin")

        return {
            "admin_user": admin_user,
            "target_users": users,
            "operation": "grant_achievement",
            "achievement": achievement,
            "expected_success_count": len(users),
            "expected_failure_count": 0,
        }

    @staticmethod
    def create_performance_test_scenario() -> dict[str, Any]:
        """創建效能測試場景."""
        return {
            "concurrent_users": 50,
            "operations_per_user": 10,
            "max_response_time": 1.0,  # 秒
            "expected_success_rate": 0.95,
            "test_duration": 30,  # 秒
        }


# 便利函數
def quick_user(user_id: int | None = None, username: str | None = None) -> MagicMock:
    """快速創建測試用戶."""
    return DiscordObjectFactory.create_user(user_id=user_id, username=username)


def quick_guild(guild_id: int | None = None, name: str | None = None) -> MagicMock:
    """快速創建測試伺服器."""
    return DiscordObjectFactory.create_guild(guild_id=guild_id, name=name)


def quick_interaction(
    user: MagicMock | None = None, guild: MagicMock | None = None
) -> MagicMock:
    """快速創建測試交互."""
    return DiscordObjectFactory.create_interaction(user=user, guild=guild)


def quick_achievement(
    name: str | None = None, target: int | None = None
) -> dict[str, Any]:
    """快速創建測試成就."""
    return AchievementDataFactory.create_achievement_data(
        name=name, target_value=target
    )


# 測試數據集
SAMPLE_ACHIEVEMENTS = [
    AchievementDataFactory.create_achievement_data(
        name="初來乍到", description="發送第一條消息", target_value=1, icon_emoji="👋"
    ),
    AchievementDataFactory.create_achievement_data(
        name="健談者", description="發送100條消息", target_value=100, icon_emoji="💬"
    ),
    AchievementDataFactory.create_achievement_data(
        name="超級活躍",
        description="發送1000條消息",
        target_value=1000,
        icon_emoji="🔥",
    ),
]

SAMPLE_CATEGORIES = [
    AchievementDataFactory.create_achievement_category_data(
        name="活動成就", description="與活動參與相關的成就", icon_emoji="🎯"
    ),
    AchievementDataFactory.create_achievement_category_data(
        name="社交成就", description="與社交互動相關的成就", icon_emoji="👥"
    ),
    AchievementDataFactory.create_achievement_category_data(
        name="時間成就", description="與時間積累相關的成就", icon_emoji="⏰"
    ),
]
