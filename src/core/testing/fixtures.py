"""
🧪 共用測試 Fixtures
提供所有測試模組使用的基礎 fixtures
"""

from collections.abc import AsyncGenerator

import discord
import dpytest
import pytest_asyncio
from discord.ext import commands

from src.core.testing.dpytest_config import DpytestConfig, cleanup_test_environment


@pytest_asyncio.fixture
async def test_bot() -> AsyncGenerator[commands.Bot, None]:
    """
    提供已配置的測試機器人

    Returns:
        配置好的 Discord.py 機器人實例
    """
    # 創建機器人實例
    intents = discord.Intents.all()
    bot = commands.Bot(command_prefix="!", intents=intents)

    try:
        # 配置 dpytest
        await DpytestConfig.configure_bot(
            bot, num_guilds=2, num_members=10, num_channels=5, num_roles=3
        )

        yield bot

    finally:
        # 清理測試環境
        await cleanup_test_environment()


@pytest_asyncio.fixture
async def test_guild(test_bot: commands.Bot) -> discord.Guild:
    """
    提供測試伺服器

    Args:
        test_bot: 測試機器人實例

    Returns:
        測試伺服器對象
    """
    guilds = list(test_bot.guilds)
    return guilds[0] if guilds else await DpytestConfig.create_test_guild()


@pytest_asyncio.fixture
async def test_channel(test_guild: discord.Guild) -> discord.TextChannel:
    """
    提供測試文字頻道

    Args:
        test_guild: 測試伺服器

    Returns:
        測試文字頻道
    """
    channels = [ch for ch in test_guild.channels if isinstance(ch, discord.TextChannel)]
    return (
        channels[0]
        if channels
        else dpytest.backend.make_text_channel("測試頻道", test_guild)
    )


@pytest_asyncio.fixture
async def test_user(test_guild: discord.Guild) -> discord.User:
    """
    提供測試用戶

    Args:
        test_guild: 測試伺服器

    Returns:
        測試用戶對象
    """
    return await DpytestConfig.create_test_user("測試用戶", discriminator="0001")


@pytest_asyncio.fixture
async def test_member(
    test_user: discord.User, test_guild: discord.Guild
) -> discord.Member:
    """
    提供測試成員

    Args:
        test_user: 測試用戶
        test_guild: 測試伺服器

    Returns:
        測試成員對象
    """
    members = list(test_guild.members)
    return (
        members[0]
        if members
        else await DpytestConfig.create_test_member(test_user, test_guild)
    )


@pytest_asyncio.fixture
async def test_admin_member(test_guild: discord.Guild) -> discord.Member:
    """
    提供管理員測試成員

    Args:
        test_guild: 測試伺服器

    Returns:
        具有管理員權限的測試成員
    """
    admin_user = await DpytestConfig.create_test_user("管理員", discriminator="0002")
    admin_member = await DpytestConfig.create_test_member(admin_user, test_guild)

    # 設定管理員權限
    admin_role = discord.utils.get(test_guild.roles, name="Administrator")
    if not admin_role:
        admin_role = dpytest.backend.make_role(
            "Administrator", test_guild, permissions=discord.Permissions.all()
        )

    admin_member._roles.add(admin_role.id)
    return admin_member
