"""
dpytest 測試環境配置
Task ID: T5 - Discord testing: dpytest and random interactions

這個模組提供 dpytest 測試的基礎配置和 fixture。
確保測試環境隔離和一致性。
"""

import pytest
import discord
import discord.ext.test as dpytest
import asyncio
import tempfile
import os
from pathlib import Path
import logging

# 抑制 discord.py 的調試輸出
logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('discord.http').setLevel(logging.WARNING)


@pytest.fixture(scope="function")
async def bot():
    """提供測試機器人實例"""
    # 配置 intents
    intents = discord.Intents.default()
    intents.message_content = True
    
    # 建立機器人
    test_bot = discord.ext.commands.Bot(
        command_prefix="!",
        intents=intents
    )
    
    # 設置事件循環
    test_bot.loop = asyncio.get_event_loop()
    
    # 添加測試命令
    @test_bot.command()
    async def ping(ctx):
        await ctx.send("pong")
    
    # 設置 dpytest - 直接用字符串列表指定成員名稱
    dpytest.configure(test_bot, guilds=1, text_channels=1, members=["TestUser"])
    
    yield test_bot
    
    # 清理
    await dpytest.empty_queue()


@pytest.fixture(scope="function") 
def guild(bot):
    """提供測試公會"""
    return bot.guilds[0]


@pytest.fixture(scope="function") 
def channel(guild):
    """提供測試頻道"""
    return guild.text_channels[0]


@pytest.fixture(scope="function")
def member(guild):
    """提供測試成員"""
    # 如果公會沒有成員，創建一個
    if not guild.members or len(guild.members) == 0:
        # 手動建立一個測試成員
        import discord.ext.test as dpytest
        test_member = dpytest.backend.make_user("TestUser", guild)
        guild._members[test_member.id] = test_member
        return test_member
    
    # 獲取第一個非機器人成員，如果沒有就用第一個
    members = [m for m in guild.members if not m.bot]
    return members[0] if members else guild.members[0]


@pytest.fixture(scope="function")
def temp_db_path():
    """提供臨時資料庫路徑，確保測試隔離"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = Path(tmp_file.name)
    
    yield db_path
    
    # 清理臨時檔案
    if db_path.exists():
        os.unlink(db_path)


@pytest.fixture(scope="function")
def mock_panel_config():
    """提供模擬的面板配置"""
    return {
        "achievement_panel": {
            "enabled": True,
            "max_achievements_per_page": 5,
            "auto_refresh": True
        },
        "terminal_panel": {
            "enabled": True,
            "admin_only": True,
            "command_timeout": 30
        }
    }


# 測試會話配置
@pytest.fixture(scope="session", autouse=True)
def configure_test_environment():
    """自動配置測試環境"""
    # 設定測試環境變數
    os.environ["TESTING"] = "true"
    os.environ["LOG_LEVEL"] = "WARNING"
    
    # 確保測試目錄存在
    test_dirs = ["logs", "test_reports", "tests/dpytest"]
    for dir_name in test_dirs:
        Path(dir_name).mkdir(parents=True, exist_ok=True)
    
    yield
    
    # 清理
    if "TESTING" in os.environ:
        del os.environ["TESTING"]


class DpytestHelper:
    """dpytest 測試輔助類"""
    
    def __init__(self):
        self.message_queue = []
        self.sent_messages = []
    
    async def send_message(self, channel, content: str, user=None):
        """發送測試訊息"""
        import discord.ext.test as dpytest
        message = dpytest.backend.make_message(content, user, channel)
        self.sent_messages.append(message)
        return message
    
    async def send_command(self, channel, command: str, user=None):
        """發送測試命令"""
        command_text = f"!{command}" if not command.startswith("!") else command
        return await self.send_message(channel, command_text, user)
    
    async def add_reaction(self, message, emoji: str, user):
        """添加反應"""
        import discord.ext.test as dpytest
        dpytest.backend.add_reaction(message, emoji, user)
    
    async def assert_message_sent(self, content: str, timeout: float = 5.0):
        """驗證訊息已發送"""
        import discord.ext.test as dpytest
        import asyncio
        try:
            response = await asyncio.wait_for(dpytest.get_message(), timeout=timeout)
            assert content.lower() in response.content.lower(), f"Expected '{content}' in '{response.content}'"
        except asyncio.TimeoutError:
            raise AssertionError(f"No message containing '{content}' received within {timeout}s")
    
    async def wait_for_message(self, timeout: float = 2.0):
        """等待下一個訊息"""
        import discord.ext.test as dpytest
        import asyncio
        try:
            return await asyncio.wait_for(dpytest.get_message(), timeout=timeout)
        except asyncio.TimeoutError:
            raise AssertionError(f"No message received within {timeout}s")


@pytest.fixture(scope="function")
def dpytest_helper():
    """提供dpytest測試輔助工具"""
    return DpytestHelper()


@pytest.fixture(scope="function")
def test_channel(guild):
    """提供測試頻道（別名）"""
    return guild.text_channels[0]


@pytest.fixture(scope="function")
def test_user(guild):
    """提供測試用戶（別名）"""
    # 如果公會沒有成員，創建一個
    if not guild.members or len(guild.members) == 0:
        # 手動建立一個測試成員
        import discord.ext.test as dpytest
        test_member = dpytest.backend.make_user("TestUser", guild)
        guild._members[test_member.id] = test_member
        return test_member
    
    # 獲取第一個非機器人成員，如果沒有就用第一個
    members = [m for m in guild.members if not m.bot]
    return members[0] if members else guild.members[0]


@pytest.fixture(scope="function")
def test_guild(bot):
    """提供測試公會（別名）"""
    return bot.guilds[0]


# 測試標記
pytest_plugins = ["pytest_asyncio"]