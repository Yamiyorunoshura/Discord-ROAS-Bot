"""
🧪 Discord ADR Bot v1.6 測試配置文件
- 提供測試所需的 fixtures
- 配置測試環境
- 模擬 Discord 物件
- 支援效能測試和錯誤處理測試
"""

import asyncio
import os
import re
import time
from collections.abc import AsyncGenerator, Generator
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import aiosqlite
import discord
import psutil
import pytest
import pytest_asyncio
from discord.ext import commands

# ═══════════════════════════════════════════════════════════════════════════════════════════
# 🎯 測試環境配置
# ═══════════════════════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """🔄 創建事件循環用於測試"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """🌍 設置測試環境變數"""
    monkeypatch.setenv("PROJECT_ROOT", "/tmp/test_project")
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("TESTING", "true")

    # 創建測試目錄
    test_dirs = [
        "/tmp/test_project/data",
        "/tmp/test_project/logs",
        "/tmp/test_project/dbs",
    ]
    for dir_path in test_dirs:
        os.makedirs(dir_path, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 🎮 Discord 物件模擬 Fixtures
# ═══════════════════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_guild() -> discord.Guild:
    """🏰 模擬 Discord 伺服器"""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 12345
    guild.name = "測試伺服器"
    guild.member_count = 100
    guild.created_at = datetime.utcnow()
    guild.owner_id = 11111
    guild.get_member.return_value = None
    guild.get_channel.return_value = None
    guild.get_role.return_value = None
    guild.channels = []
    guild.roles = []
    guild.members = []
    guild.me = MagicMock(spec=discord.Member)
    guild.me.guild_permissions = discord.Permissions.all()
    return guild


@pytest.fixture
def mock_user() -> discord.User:
    """👤 模擬 Discord 用戶"""
    user = MagicMock(spec=discord.User)
    user.id = 67890
    user.name = "測試用戶"
    user.display_name = "測試用戶"
    user.discriminator = "0001"
    user.bot = False
    user.created_at = datetime.utcnow()
    user.display_avatar = MagicMock()
    user.display_avatar.url = "https://cdn.discordapp.com/avatars/67890/avatar.png"
    user.mention = f"<@{user.id}>"
    return user


@pytest.fixture
def mock_member(mock_guild: discord.Guild, mock_user: discord.User) -> discord.Member:
    """👥 模擬 Discord 成員"""
    member = MagicMock(spec=discord.Member)
    member.id = mock_user.id
    member.name = mock_user.name
    member.display_name = mock_user.display_name
    member.discriminator = mock_user.discriminator
    member.bot = False
    member.guild = mock_guild
    member.joined_at = datetime.utcnow()
    member.created_at = mock_user.created_at
    member.display_avatar = mock_user.display_avatar
    member.mention = mock_user.mention

    # 權限設定
    member.guild_permissions = MagicMock(spec=discord.Permissions)
    member.guild_permissions.administrator = False
    member.guild_permissions.manage_guild = False
    member.guild_permissions.manage_messages = False
    member.guild_permissions.manage_channels = False
    member.guild_permissions.manage_roles = False

    # 超時功能
    member.timeout = AsyncMock()
    member.edit = AsyncMock()

    return member


@pytest.fixture
def mock_admin_member(
    mock_guild: discord.Guild, mock_user: discord.User
) -> discord.Member:
    """👑 模擬管理員成員"""
    member = MagicMock(spec=discord.Member)
    member.id = mock_user.id + 1
    member.name = "管理員"
    member.display_name = "管理員"
    member.discriminator = "0002"
    member.bot = False
    member.guild = mock_guild
    member.joined_at = datetime.utcnow()
    member.created_at = datetime.utcnow()

    # 管理員權限
    member.guild_permissions = MagicMock(spec=discord.Permissions)
    member.guild_permissions.administrator = True
    member.guild_permissions.manage_guild = True
    member.guild_permissions.manage_messages = True
    member.guild_permissions.manage_channels = True
    member.guild_permissions.manage_roles = True

    return member


@pytest.fixture
def mock_channel(mock_guild: discord.Guild) -> discord.TextChannel:
    """📝 模擬 Discord 文字頻道"""
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 98765
    channel.name = "測試頻道"
    channel.guild = mock_guild
    channel.type = discord.ChannelType.text
    channel.position = 0
    channel.topic = "測試頻道主題"
    channel.created_at = datetime.utcnow()
    channel.send = AsyncMock()
    channel.edit = AsyncMock()
    channel.delete = AsyncMock()
    channel.mention = f"<#{channel.id}>"

    # 權限覆蓋
    channel.permissions_for = MagicMock(return_value=discord.Permissions.all())

    return channel


@pytest.fixture
def mock_voice_channel(mock_guild: discord.Guild) -> discord.VoiceChannel:
    """🔊 模擬 Discord 語音頻道"""
    channel = MagicMock(spec=discord.VoiceChannel)
    channel.id = 98766
    channel.name = "測試語音頻道"
    channel.guild = mock_guild
    channel.type = discord.ChannelType.voice
    channel.position = 1
    channel.user_limit = 10
    channel.bitrate = 64000
    channel.created_at = datetime.utcnow()
    channel.edit = AsyncMock()
    channel.delete = AsyncMock()

    return channel


@pytest.fixture
def mock_role(mock_guild: discord.Guild) -> discord.Role:
    """🏷️ 模擬 Discord 角色"""
    role = MagicMock(spec=discord.Role)
    role.id = 55555
    role.name = "測試角色"
    role.guild = mock_guild
    role.position = 1
    role.permissions = discord.Permissions.none()
    role.color = discord.Color.blue()
    role.hoist = False
    role.mentionable = True
    role.created_at = datetime.utcnow()
    role.mention = f"<@&{role.id}>"
    role.edit = AsyncMock()
    role.delete = AsyncMock()

    return role


@pytest.fixture
def mock_message(
    mock_guild: discord.Guild,
    mock_member: discord.Member,
    mock_channel: discord.TextChannel,
) -> discord.Message:
    """💬 模擬 Discord 訊息"""
    message = MagicMock(spec=discord.Message)
    message.id = 123456789
    message.content = "測試訊息內容"
    message.author = mock_member
    message.guild = mock_guild
    message.channel = mock_channel
    message.created_at = datetime.utcnow()
    message.edited_at = None
    message.attachments = []
    message.stickers = []
    message.embeds = []
    message.mentions = []
    message.channel_mentions = []
    message.role_mentions = []
    message.reference = None
    message.type = discord.MessageType.default

    # 訊息操作
    message.edit = AsyncMock()
    message.delete = AsyncMock()
    message.add_reaction = AsyncMock()
    message.remove_reaction = AsyncMock()
    message.pin = AsyncMock()
    message.unpin = AsyncMock()
    message.reply = AsyncMock()

    return message


@pytest.fixture
def mock_attachment() -> discord.Attachment:
    """📎 模擬 Discord 附件"""
    attachment = MagicMock(spec=discord.Attachment)
    attachment.id = 987654321
    attachment.filename = "test_file.txt"
    attachment.size = 1024
    attachment.url = "https://cdn.discordapp.com/attachments/123/456/test_file.txt"
    attachment.proxy_url = attachment.url
    attachment.content_type = "text/plain"
    attachment.read = AsyncMock(return_value=b"test content")

    return attachment


@pytest.fixture
def mock_interaction(
    mock_guild: discord.Guild, mock_member: discord.Member
) -> discord.Interaction:
    """⚡ 模擬 Discord 互動"""
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.guild = mock_guild
    interaction.user = mock_member
    interaction.guild_id = mock_guild.id
    interaction.channel_id = 98765
    interaction.id = 111222333
    interaction.token = "test_token"
    interaction.type = discord.InteractionType.application_command

    # 響應方法
    interaction.response = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.is_done.return_value = False

    # 跟進方法
    interaction.followup = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.followup.edit_message = AsyncMock()

    return interaction


@pytest.fixture
def mock_bot() -> commands.Bot:
    """🤖 模擬 Discord Bot"""
    bot = MagicMock(spec=commands.Bot)
    bot.user = MagicMock(spec=discord.ClientUser)
    bot.user.id = 11111
    bot.user.name = "測試機器人"
    bot.user.discriminator = "0000"
    bot.user.bot = True

    # Bot 方法
    bot.add_cog = AsyncMock()
    bot.remove_cog = AsyncMock()
    bot.load_extension = AsyncMock()
    bot.unload_extension = AsyncMock()
    bot.get_guild = MagicMock()
    bot.get_channel = MagicMock()
    bot.get_user = MagicMock()
    bot.fetch_user = AsyncMock()
    bot.fetch_guild = AsyncMock()
    bot.fetch_channel = AsyncMock()

    # 事件循環
    bot.loop = (
        asyncio.get_running_loop()
        if asyncio.get_event_loop_policy().get_event_loop().is_running()
        else asyncio.new_event_loop()
    )

    return bot


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 🗄️ 資料庫測試 Fixtures
# ═══════════════════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def test_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """🗄️ 提供記憶體資料庫用於測試"""
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row

    try:
        yield db
    finally:
        await db.close()


@pytest_asyncio.fixture
async def activity_test_db(test_db: aiosqlite.Connection) -> aiosqlite.Connection:
    """📊 設置活躍度系統測試資料庫"""
    await test_db.executescript("""
        CREATE TABLE IF NOT EXISTS meter(
          guild_id INTEGER, user_id INTEGER,
          score REAL DEFAULT 0, last_msg INTEGER DEFAULT 0,
          PRIMARY KEY(guild_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS daily(
          ymd TEXT, guild_id INTEGER, user_id INTEGER,
          msg_cnt INTEGER DEFAULT 0,
          PRIMARY KEY(ymd, guild_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS report_channel(
          guild_id INTEGER PRIMARY KEY,
          channel_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS settings(
          guild_id INTEGER PRIMARY KEY,
          enabled INTEGER DEFAULT 1,
          auto_report INTEGER DEFAULT 0,
          report_time TEXT DEFAULT '09:00'
        );
    """)
    await test_db.commit()
    return test_db


@pytest_asyncio.fixture
async def message_listener_test_db(
    test_db: aiosqlite.Connection,
) -> aiosqlite.Connection:
    """💬 設置訊息監聽系統測試資料庫"""
    await test_db.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY,
            channel_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            content TEXT,
            timestamp REAL,
            attachments TEXT,
            stickers TEXT,
            deleted INTEGER DEFAULT 0,
            edited_at REAL,
            reference_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS settings (
            setting_name TEXT PRIMARY KEY,
            setting_value TEXT
        );
        CREATE TABLE IF NOT EXISTS monitored_channels (
            channel_id INTEGER PRIMARY KEY,
            guild_id INTEGER NOT NULL,
            webhook_url TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_id);
        CREATE INDEX IF NOT EXISTS idx_messages_author ON messages(author_id);
        CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
    """)
    await test_db.commit()
    return test_db


@pytest_asyncio.fixture
async def welcome_test_db(test_db: aiosqlite.Connection) -> aiosqlite.Connection:
    """👋 設置歡迎系統測試資料庫"""
    await test_db.executescript("""
        CREATE TABLE IF NOT EXISTS welcome_config (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0,
            channel_id INTEGER,
            message TEXT,
            background_url TEXT,
            font_color TEXT DEFAULT '#FFFFFF',
            background_color TEXT DEFAULT '#000000'
        );
        CREATE TABLE IF NOT EXISTS welcome_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            message_id INTEGER,
            timestamp REAL,
            success INTEGER DEFAULT 1
        );
    """)
    await test_db.commit()
    return test_db


@pytest_asyncio.fixture
async def protection_test_db(test_db: aiosqlite.Connection) -> aiosqlite.Connection:
    """🛡️ 設置保護系統測試資料庫"""
    await test_db.executescript("""
        -- 反垃圾訊息
        CREATE TABLE IF NOT EXISTS spam_settings (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0,
            max_messages INTEGER DEFAULT 5,
            time_window INTEGER DEFAULT 10,
            mute_duration INTEGER DEFAULT 300,
            delete_messages INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS spam_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            message_id INTEGER,
            timestamp REAL,
            action TEXT
        );

        -- 反惡意連結
        CREATE TABLE IF NOT EXISTS link_settings (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0,
            action TEXT DEFAULT 'delete',
            notify_admins INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS link_whitelist (
            guild_id INTEGER NOT NULL,
            domain TEXT NOT NULL,
            added_by INTEGER,
            added_at REAL,
            PRIMARY KEY(guild_id, domain)
        );
        CREATE TABLE IF NOT EXISTS link_blacklist (
            guild_id INTEGER NOT NULL,
            domain TEXT NOT NULL,
            added_by INTEGER,
            added_at REAL,
            PRIMARY KEY(guild_id, domain)
        );

        -- 反可執行檔案
        CREATE TABLE IF NOT EXISTS executable_settings (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0,
            action TEXT DEFAULT 'delete',
            scan_content INTEGER DEFAULT 1,
            max_file_size INTEGER DEFAULT 10485760
        );
        CREATE TABLE IF NOT EXISTS executable_whitelist (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            added_by INTEGER,
            added_at REAL,
            PRIMARY KEY(guild_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS detection_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            filename TEXT,
            detection_type TEXT,
            threat_level TEXT,
            action_taken TEXT,
            timestamp REAL
        );
    """)
    await test_db.commit()
    return test_db


@pytest_asyncio.fixture
async def sync_test_db(test_db: aiosqlite.Connection) -> aiosqlite.Connection:
    """🔄 設置同步系統測試資料庫"""
    await test_db.executescript("""
        CREATE TABLE IF NOT EXISTS guilds (
            guild_id INTEGER PRIMARY KEY,
            guild_name TEXT NOT NULL,
            owner_id INTEGER,
            member_count INTEGER,
            channel_count INTEGER,
            role_count INTEGER,
            created_at REAL,
            last_updated REAL
        );
        CREATE TABLE IF NOT EXISTS channels (
            channel_id INTEGER PRIMARY KEY,
            guild_id INTEGER NOT NULL,
            channel_name TEXT NOT NULL,
            channel_type TEXT,
            position INTEGER,
            topic TEXT,
            created_at REAL,
            last_updated REAL
        );
        CREATE TABLE IF NOT EXISTS roles (
            role_id INTEGER PRIMARY KEY,
            guild_id INTEGER NOT NULL,
            role_name TEXT NOT NULL,
            permissions INTEGER,
            position INTEGER,
            color INTEGER,
            hoist INTEGER,
            mentionable INTEGER,
            created_at REAL,
            last_updated REAL
        );
        CREATE TABLE IF NOT EXISTS members (
            user_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            discriminator TEXT,
            joined_at REAL,
            last_updated REAL,
            PRIMARY KEY(user_id, guild_id)
        );
        CREATE TABLE IF NOT EXISTS sync_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            sync_type TEXT NOT NULL,
            changes_count INTEGER,
            success INTEGER,
            error_message TEXT,
            timestamp REAL
        );
    """)
    await test_db.commit()
    return test_db


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 🔧 測試工具函數
# ═══════════════════════════════════════════════════════════════════════════════════════════


def assert_tracking_id_format(tracking_id: str) -> None:
    """✅ 驗證追蹤碼格式"""

    pattern = r"TRACKING_ID-[A-Z_]+\d{3}-\d{6}"
    assert re.match(pattern, tracking_id), f"追蹤碼格式不正確: {tracking_id}"


def assert_discord_id_valid(discord_id: int) -> None:
    """✅ 驗證 Discord ID 格式"""
    assert isinstance(discord_id, int), "Discord ID 必須是整數"
    assert discord_id > 0, "Discord ID 必須大於 0"
    assert len(str(discord_id)) >= 17, "Discord ID 長度不足"


def assert_timestamp_valid(timestamp: float) -> None:
    """✅ 驗證時間戳格式"""
    assert isinstance(timestamp, int | float), "時間戳必須是數字"
    assert timestamp > 0, "時間戳必須大於 0"
    # 檢查是否為合理的時間範圍(2020-2030年)
    assert 1577836800 <= timestamp <= 1893456000, "時間戳不在合理範圍內"


def assert_embed_valid(embed: discord.Embed) -> None:
    """✅ 驗證 Discord Embed 格式"""
    assert isinstance(embed, discord.Embed), "必須是 Discord Embed 對象"
    assert len(embed.title or "") <= 256, "標題長度不能超過 256 字符"
    assert len(embed.description or "") <= 4096, "描述長度不能超過 4096 字符"
    assert len(embed.fields) <= 25, "欄位數量不能超過 25 個"

    for field in embed.fields:
        assert len(field.name) <= 256, "欄位名稱長度不能超過 256 字符"
        assert len(field.value) <= 1024, "欄位值長度不能超過 1024 字符"


async def assert_async_no_exception(coro) -> Any:
    """✅ 驗證異步函數不拋出異常"""
    try:
        result = await coro
        return result
    except Exception as e:
        pytest.fail(f"異步函數拋出了異常: {e}")


def assert_performance_acceptable(execution_time: float, max_time: float) -> None:
    """⚡ 驗證執行時間在可接受範圍內"""
    assert execution_time <= max_time, (
        f"執行時間 {execution_time:.3f}s 超過限制 {max_time:.3f}s"
    )


def assert_memory_usage_acceptable(memory_usage: int, max_memory: int) -> None:
    """🧠 驗證記憶體使用量在可接受範圍內"""
    assert memory_usage <= max_memory, (
        f"記憶體使用量 {memory_usage} bytes 超過限制 {max_memory} bytes"
    )


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 📊 效能測試支援
# ═══════════════════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def performance_timer():
    """⏱️ 效能計時器"""

    class PerformanceTimer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = time.perf_counter()

        def stop(self):
            self.end_time = time.perf_counter()

        @property
        def elapsed(self) -> float:
            if self.start_time is None or self.end_time is None:
                return 0.0
            return self.end_time - self.start_time

    return PerformanceTimer()


@pytest.fixture
def memory_monitor():
    """🧠 記憶體監控器"""

    class MemoryMonitor:
        def __init__(self):
            self.process = psutil.Process(os.getpid())
            self.initial_memory = self.process.memory_info().rss

        def get_current_usage(self) -> int:
            return self.process.memory_info().rss

        def get_memory_increase(self) -> int:
            return self.get_current_usage() - self.initial_memory

    return MemoryMonitor()


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 🎭 Mock 管理器
# ═══════════════════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_manager():
    """🎭 統一的 Mock 管理器"""

    class MockManager:
        def __init__(self):
            self.patches = []

        def patch_async(self, target: str, return_value=None, side_effect=None):
            """創建異步 Mock"""
            mock = AsyncMock(return_value=return_value, side_effect=side_effect)
            patcher = patch(target, mock)
            self.patches.append(patcher)
            return patcher.start()

        def patch_sync(self, target: str, return_value=None, side_effect=None):
            """創建同步 Mock"""
            mock = MagicMock(return_value=return_value, side_effect=side_effect)
            patcher = patch(target, mock)
            self.patches.append(patcher)
            return patcher.start()

        def cleanup(self):
            """清理所有 Mock"""
            for patcher in self.patches:
                patcher.stop()
            self.patches.clear()

    manager = MockManager()
    yield manager
    manager.cleanup()


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 🧪 測試資料生成器
# ═══════════════════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def test_data_generator():
    """🧪 測試資料生成器"""

    class TestDataGenerator:
        @staticmethod
        def generate_guild_data(count: int = 1) -> list[dict[str, Any]]:
            """生成測試伺服器資料"""
            return [
                {
                    "guild_id": 12345 + i,
                    "guild_name": f"測試伺服器 {i + 1}",
                    "member_count": 100 + i * 10,
                    "channel_count": 5 + i,
                    "role_count": 3 + i,
                    "created_at": time.time() - (i * 86400),
                }
                for i in range(count)
            ]

        @staticmethod
        def generate_user_data(count: int = 1) -> list[dict[str, Any]]:
            """生成測試用戶資料"""
            return [
                {
                    "user_id": 67890 + i,
                    "username": f"用戶{i + 1}",
                    "discriminator": f"{i + 1:04d}",
                    "bot": False,
                    "created_at": time.time() - (i * 86400),
                }
                for i in range(count)
            ]

        @staticmethod
        def generate_message_data(count: int = 1) -> list[dict[str, Any]]:
            """生成測試訊息資料"""
            return [
                {
                    "message_id": 123456789 + i,
                    "channel_id": 98765,
                    "guild_id": 12345,
                    "author_id": 67890,
                    "content": f"測試訊息 {i + 1}",
                    "timestamp": time.time() - (i * 60),
                    "attachments": "[]",
                    "stickers": "[]",
                    "deleted": 0,
                }
                for i in range(count)
            ]

    return TestDataGenerator()


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 🔒 安全測試支援
# ═══════════════════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def security_tester():
    """🔒 安全測試工具"""

    class SecurityTester:
        @staticmethod
        def generate_malicious_inputs() -> list[str]:
            """生成惡意輸入測試資料"""
            return [
                "'; DROP TABLE users; --",  # SQL 注入
                "<script>alert('XSS')</script>",  # XSS 攻擊
                "../../etc/passwd",  # 路徑遍歷
                "A" * 10000,  # 超長字符串
                "\x00\x01\x02",  # 二進制字符
                "🔥" * 1000,  # 大量 Unicode
                "",  # 空字符串
                None,  # None 值
            ]

        @staticmethod
        def generate_large_data(size_mb: int = 1) -> bytes:
            """生成大量資料"""
            return b"A" * (size_mb * 1024 * 1024)

        @staticmethod
        def simulate_network_error():
            """模擬網路錯誤"""

            return aiohttp.ClientError("模擬網路錯誤")

    return SecurityTester()


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 📋 測試標記配置
# ═══════════════════════════════════════════════════════════════════════════════════════════


# 註冊自定義標記
def pytest_configure(config):
    """配置 pytest 標記"""
    config.addinivalue_line("markers", "slow: 標記為慢速測試")
    config.addinivalue_line("markers", "integration: 標記為整合測試")
    config.addinivalue_line("markers", "performance: 標記為效能測試")
    config.addinivalue_line("markers", "security: 標記為安全測試")
    config.addinivalue_line("markers", "database: 標記為資料庫測試")
    config.addinivalue_line("markers", "network: 標記為網路測試")
    config.addinivalue_line("markers", "timeout: 標記為超時測試")
