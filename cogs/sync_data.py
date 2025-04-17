import discord
from discord.ext import commands, tasks
import sqlite3
import logging
import os

# 設定專案根目錄
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 設定日誌
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
log_dir = os.path.join(PROJECT_ROOT, 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
handler = logging.FileHandler(os.path.join(log_dir, 'sync_data.log'), encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(handler)

class SyncData(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.database
        self.sync_data.start()

    def cog_unload(self):
        self.sync_data.cancel()

    @tasks.loop(hours=24)
    async def sync_data(self):
        """同步伺服器信息"""
        logger.info("開始同步伺服器信息...")
        for guild in self.bot.guilds:
            await self.sync_guild_data(guild)
        logger.info("伺服器信息同步完成。")

    @sync_data.before_loop
    async def before_sync_data(self):
        await self.bot.wait_until_ready()

    async def sync_guild_data(self, guild):
        """同步單個伺服器的信息"""
        guild_id = guild.id

        # 使用 bot.database 執行資料庫操作
        try:
            self.db._execute_query("""
                CREATE TABLE IF NOT EXISTS roles (
                    role_id INTEGER PRIMARY KEY,
                    guild_id INTEGER,
                    name TEXT,
                    color TEXT,
                    permissions INTEGER
                )
            """)
            self.db._execute_query("""
                CREATE TABLE IF NOT EXISTS channels (
                    channel_id INTEGER PRIMARY KEY,
                    guild_id INTEGER,
                    name TEXT,
                    type TEXT,
                    topic TEXT
                )
            """)
            self.db._execute_query("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    guild_id INTEGER,
                    author_id INTEGER,
                    content TEXT,
                    timestamp INTEGER
                )
            """)

            # 獲取並儲存身份組信息
            for role in guild.roles:
                self.db._execute_query(
                    "INSERT OR REPLACE INTO roles (role_id, guild_id, name, color, permissions) VALUES (?, ?, ?, ?, ?)",
                    (role.id, guild_id, role.name, str(role.color), role.permissions.value)
                )
            logger.info(f"伺服器 {guild_id}: 身份組信息已同步。")

            # 獲取並儲存頻道信息
            for channel in guild.text_channels:
                self.db._execute_query(
                    "INSERT OR REPLACE INTO channels (channel_id, guild_id, name, type, topic) VALUES (?, ?, ?, ?, ?)",
                    (channel.id, guild_id, channel.name, "text", channel.topic)
                )
            for channel in guild.voice_channels:
                self.db._execute_query(
                    "INSERT OR REPLACE INTO channels (channel_id, guild_id, name, type, topic) VALUES (?, ?, ?, ?, ?)",
                    (channel.id, guild_id, channel.name, "voice", None)
                )
            logger.info(f"伺服器 {guild_id}: 頻道信息已同步。")

            # 獲取並儲存訊息信息 (只獲取最近 100 條訊息)
            for channel in guild.text_channels:
                try:
                    async for message in channel.history(limit=100):
                        self.db._execute_query(
                            "INSERT OR REPLACE INTO messages (message_id, channel_id, guild_id, author_id, content, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                            (message.id, channel.id, guild_id, message.author.id, message.content, message.created_at.timestamp())
                        )
                    logger.info(f"伺服器 {guild_id}: 頻道 {channel.name} 訊息已同步。")
                except discord.errors.Forbidden:
                    logger.warning(f"伺服器 {guild_id}: 沒有讀取頻道 {channel.name} 訊息的權限。")
                except Exception as e:
                    logger.exception(f"伺服器 {guild_id}: 同步頻道 {channel.name} 訊息時發生錯誤: {e}")

        except Exception as e:
            logger.exception(f"伺服器 {guild_id}: 同步資料時發生錯誤: {e}")

async def setup(bot):
    await bot.add_cog(SyncData(bot))