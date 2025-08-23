import os
import aiosqlite
import logging
import logging.handlers
from typing import Optional, Any, List, Dict, Tuple, Union
from discord.ext import commands
import discord

# === 專案根目錄與資料夾 ===
PROJECT_ROOT = os.environ.get(
    "PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
DBS_DIR = os.path.join(PROJECT_ROOT, "dbs")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(DBS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

def ensure_dbs_path(filename: Optional[str], default_filename: str) -> str:
    """
    保證檔案只會存在於 dbs/ 目錄。
    - filename: 使用者傳入的檔名或路徑
    - default_filename: 預設檔名（不含路徑）
    """
    if not filename:
        return os.path.join(DBS_DIR, default_filename)
    abspath = os.path.abspath(filename)
    # 如果已經在 dbs 內就直接用
    if abspath.startswith(os.path.abspath(DBS_DIR)):
        return abspath
    # 否則無論傳什麼，全部丟進 dbs/
    return os.path.join(DBS_DIR, os.path.basename(filename))

# -------- 日誌設定 --------
log_file = os.path.join(LOGS_DIR, 'database.log')
handler = logging.handlers.RotatingFileHandler(
    log_file, encoding='utf-8', mode='a', maxBytes=5*1024*1024, backupCount=3
)
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger = logging.getLogger('db')
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    logger.addHandler(handler)

class Database(commands.Cog):
    def __init__(self, bot: commands.Bot, db_name: Optional[str] = None, message_db_name: Optional[str] = None):
        self.bot = bot
        self.db_name = ensure_dbs_path(db_name, 'welcome.db')
        self.message_db_name = ensure_dbs_path(message_db_name, 'message.db')
        self.conn: Optional[aiosqlite.Connection] = None
        self.message_conn: Optional[aiosqlite.Connection] = None
        self.ready = False

    async def cog_load(self):
        try:
            await self._init_database()
            setattr(self.bot, "database", self)
            self.ready = True
            logger.info("【資料庫】Database Cog 已就緒，資料庫連線建立完成。")
        except Exception as e:
            logger.error(f"【資料庫】初始化失敗：{e}")

    async def cog_unload(self):
        await self.close()

    async def _init_database(self):
        try:
            self.conn = await aiosqlite.connect(self.db_name)
            await self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.row_factory = aiosqlite.Row

            self.message_conn = await aiosqlite.connect(self.message_db_name)
            await self.message_conn.execute("PRAGMA journal_mode=WAL;")
            self.message_conn.row_factory = aiosqlite.Row

            await self._create_tables()
        except Exception as e:
            logger.error(f"【資料庫】資料庫連線或初始化表格失敗：{e}")

    async def close(self):
        try:
            if self.conn:
                await self.conn.close()
                self.conn = None
            if self.message_conn:
                await self.message_conn.close()
                self.message_conn = None
            logger.info("【資料庫】資料庫連線已關閉。")
        except Exception as e:
            logger.error(f"【資料庫】關閉資料庫時發生錯誤：{e}")

    async def _create_tables(self):
        try:
            assert self.conn is not None
            await self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS welcome_settings (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    title TEXT,
                    description TEXT,
                    image_url TEXT,
                    delete_url TEXT
                );
                CREATE TABLE IF NOT EXISTS welcome_messages (
                    guild_id INTEGER PRIMARY KEY,
                    message TEXT
                );
                CREATE TABLE IF NOT EXISTS text_styles (
                    guild_id INTEGER,
                    type TEXT,
                    x INTEGER,
                    y INTEGER,
                    size INTEGER,
                    color TEXT,
                    opacity INTEGER,
                    font TEXT,
                    PRIMARY KEY (guild_id, type)
                );
                CREATE TABLE IF NOT EXISTS welcome_backgrounds (
                    guild_id INTEGER PRIMARY KEY,
                    image_path TEXT
                );
                CREATE TABLE IF NOT EXISTS settings (
                    setting_name TEXT PRIMARY KEY,
                    setting_value TEXT
                );
                CREATE TABLE IF NOT EXISTS monitored_channels (
                    channel_id INTEGER PRIMARY KEY
                );
                CREATE TABLE IF NOT EXISTS roles (
                    role_id INTEGER PRIMARY KEY,
                    guild_id INTEGER,
                    name TEXT,
                    color TEXT,
                    permissions INTEGER
                );
                CREATE TABLE IF NOT EXISTS channels (
                    channel_id INTEGER PRIMARY KEY,
                    guild_id INTEGER,
                    name TEXT,
                    type TEXT,
                    topic TEXT
                );
            """)
            await self.conn.commit()

            assert self.message_conn is not None
            await self.message_conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    author_id INTEGER NOT NULL,
                    content TEXT,
                    timestamp REAL,
                    attachments TEXT
                )
            """)
            await self.message_conn.commit()
        except Exception as e:
            logger.error(f"【資料庫】建立表格時發生錯誤：{e}")

    # -------- 通用 Query --------
    async def execute(self, query: str, params: Union[Tuple, List]=()):
        try:
            assert self.conn is not None
            async with self.conn.cursor() as c:
                await c.execute(query, params)
                await self.conn.commit()
        except Exception as e:
            logger.error(f"【資料庫】執行 SQL 指令失敗：{e}\n指令內容：{query}\n參數：{params}")

    async def fetchone(self, query: str, params: Union[Tuple, List]=()) -> Optional[aiosqlite.Row]:
        try:
            assert self.conn is not None
            async with self.conn.cursor() as c:
                await c.execute(query, params)
                return await c.fetchone()
        except Exception as e:
            logger.error(f"【資料庫】查詢(單筆)失敗：{e}\n查詢內容：{query}\n參數：{params}")
            return None

    async def fetchall(self, query: str, params: Union[Tuple, List]=()) -> List[aiosqlite.Row]:
        try:
            assert self.conn is not None
            async with self.conn.cursor() as c:
                await c.execute(query, params)
                return list(await c.fetchall())
        except Exception as e:
            logger.error(f"【資料庫】查詢(多筆)失敗：{e}\n查詢內容：{query}\n參數：{params}")
            return []

    # -------- 歡迎訊息 --------
    async def update_welcome_message(self, guild_id: int, channel_id: int, message: str):
        try:
            await self.execute(
                "INSERT OR REPLACE INTO welcome_settings (guild_id, channel_id) VALUES (?, ?)",
                (guild_id, channel_id)
            )
            await self.execute(
                "INSERT OR REPLACE INTO welcome_messages (guild_id, message) VALUES (?, ?)",
                (guild_id, message)
            )
        except Exception as e:
            logger.error(f"【資料庫】更新歡迎訊息失敗：{e}")

    async def get_welcome_message(self, guild_id: int) -> Optional[str]:
        try:
            row = await self.fetchone("SELECT message FROM welcome_messages WHERE guild_id = ?", (guild_id,))
            return row['message'] if row else None
        except Exception as e:
            logger.error(f"【資料庫】取得歡迎訊息失敗：{e}")
            return None

    async def update_welcome_background(self, guild_id: int, image_path: str):
        try:
            await self.execute(
                "INSERT OR REPLACE INTO welcome_backgrounds (guild_id, image_path) VALUES (?, ?)",
                (guild_id, image_path)
            )
        except Exception as e:
            logger.error(f"【資料庫】更新歡迎背景失敗：{e}")

    async def get_welcome_background(self, guild_id: int) -> Optional[str]:
        try:
            row = await self.fetchone("SELECT image_path FROM welcome_backgrounds WHERE guild_id = ?", (guild_id,))
            return row['image_path'] if row else None
        except Exception as e:
            logger.error(f"【資料庫】取得歡迎背景失敗：{e}")
            return None

    async def update_welcome_title(self, guild_id: int, title: str):
        try:
            exist = await self.fetchone("SELECT guild_id FROM welcome_settings WHERE guild_id = ?", (guild_id,))
            if exist:
                await self.execute("UPDATE welcome_settings SET title = ? WHERE guild_id = ?", (title, guild_id))
            else:
                await self.execute("INSERT INTO welcome_settings (guild_id, title) VALUES (?, ?)", (guild_id, title))
        except Exception as e:
            logger.error(f"【資料庫】更新歡迎標題失敗：{e}")

    async def update_welcome_description(self, guild_id: int, description: str):
        try:
            exist = await self.fetchone("SELECT guild_id FROM welcome_settings WHERE guild_id = ?", (guild_id,))
            if exist:
                await self.execute("UPDATE welcome_settings SET description = ? WHERE guild_id = ?", (description, guild_id))
            else:
                await self.execute("INSERT INTO welcome_settings (guild_id, description) VALUES (?, ?)", (guild_id, description))
        except Exception as e:
            logger.error(f"【資料庫】更新歡迎描述失敗：{e}")

    async def get_welcome_settings(self, guild_id: int) -> Optional[Dict[str, Any]]:
        try:
            row = await self.fetchone(
                "SELECT channel_id, title, description, image_url, delete_url FROM welcome_settings WHERE guild_id = ?", (guild_id,)
            )
            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.error(f"【資料庫】取得歡迎設定失敗：{e}")
            return None

    # -------- 文字方塊 --------
    async def update_text_position(self, guild_id: int, text_type: str, x: Optional[int], y: Optional[int]):
        try:
            exist = await self.fetchone(
                "SELECT guild_id FROM text_styles WHERE guild_id = ? AND type = ?", (guild_id, text_type)
            )
            if text_type == "avatar_x":
                if exist:
                    await self.execute(
                        "UPDATE text_styles SET x = ? WHERE guild_id = ? AND type = ?",
                        (x, guild_id, text_type)
                    )
                else:
                    await self.execute(
                        "INSERT INTO text_styles (guild_id, type, x, y) VALUES (?, ?, ?, NULL)",
                        (guild_id, text_type, x)
                    )
            elif text_type == "avatar_y":
                if exist:
                    await self.execute(
                        "UPDATE text_styles SET y = ? WHERE guild_id = ? AND type = ?",
                        (y, guild_id, text_type)
                    )
                else:
                    await self.execute(
                        "INSERT INTO text_styles (guild_id, type, x, y) VALUES (?, ?, NULL, ?)",
                        (guild_id, text_type, y)
                    )
            else:
                if exist:
                    await self.execute(
                        "UPDATE text_styles SET y = ? WHERE guild_id = ? AND type = ?",
                        (y, guild_id, text_type)
                    )
                else:
                    await self.execute(
                        "INSERT INTO text_styles (guild_id, type, x, y) VALUES (?, ?, NULL, ?)",
                        (guild_id, text_type, y)
                    )
        except Exception as e:
            logger.error(f"【資料庫】更新文字方塊座標失敗：{e}")

    async def get_text_position(self, guild_id: int, text_type: str) -> Optional[int]:
        try:
            row = await self.fetchone(
                "SELECT x, y FROM text_styles WHERE guild_id = ? AND type = ?", (guild_id, text_type)
            )
            if row:
                if text_type == "avatar_x":
                    return row['x']
                elif text_type == "avatar_y":
                    return row['y']
                else:
                    return row['y']
            return None
        except Exception as e:
            logger.error(f"【資料庫】取得文字方塊座標失敗：{e}")
            return None

    # -------- 設定 --------
    async def get_setting(self, setting_name: str) -> Optional[str]:
        try:
            row = await self.fetchone("SELECT setting_value FROM settings WHERE setting_name = ?", (setting_name,))
            return row['setting_value'] if row else None
        except Exception as e:
            logger.error(f"【資料庫】取得設定失敗：{e}")
            return None

    async def set_setting(self, setting_name: str, value: str):
        try:
            await self.execute(
                "INSERT OR REPLACE INTO settings (setting_name, setting_value) VALUES (?, ?)",
                (setting_name, value)
            )
        except Exception as e:
            logger.error(f"【資料庫】儲存設定失敗：{e}")

    # -------- 監聽頻道 --------
    async def get_monitored_channels(self) -> List[int]:
        try:
            rows = await self.fetchall("SELECT channel_id FROM monitored_channels")
            return [row['channel_id'] for row in rows]
        except Exception as e:
            logger.error(f"【資料庫】取得監聽頻道失敗：{e}")
            return []

    async def add_monitored_channel(self, channel_id: int):
        try:
            await self.execute(
                "INSERT OR IGNORE INTO monitored_channels (channel_id) VALUES (?)",
                (channel_id,)
            )
        except Exception as e:
            logger.error(f"【資料庫】新增監聽頻道失敗：{e}")

    async def remove_monitored_channel(self, channel_id: int):
        try:
            await self.execute(
                "DELETE FROM monitored_channels WHERE channel_id = ?", (channel_id,)
            )
        except Exception as e:
            logger.error(f"【資料庫】移除監聽頻道失敗：{e}")

    # -------- 訊息資料庫 --------
    async def log_message(self, message_id: int, channel_id: int, guild_id: int, author_id: int, content: str, timestamp: float, attachments: Optional[str] = None):
        try:
            assert self.message_conn is not None
            async with self.message_conn.cursor() as c:
                await c.execute(
                    "INSERT INTO messages (message_id, channel_id, guild_id, author_id, content, timestamp, attachments) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (message_id, channel_id, guild_id, author_id, content, timestamp, attachments)
                )
                await self.message_conn.commit()
        except Exception as e:
            logger.error(f"【資料庫】訊息記錄寫入失敗：{e}")

    # -------- 伺服器資訊同步 --------
    async def get_guild_roles(self, guild_id: int) -> List[aiosqlite.Row]:
        try:
            return await self.fetchall("SELECT role_id, name, color, permissions FROM roles WHERE guild_id = ?", (guild_id,))
        except Exception as e:
            logger.error(f"【資料庫】取得伺服器角色失敗：{e}")
            return []

    async def get_guild_channels(self, guild_id: int) -> List[aiosqlite.Row]:
        try:
            return await self.fetchall("SELECT channel_id, name, type, topic FROM channels WHERE guild_id = ?", (guild_id,))
        except Exception as e:
            logger.error(f"【資料庫】取得伺服器頻道失敗：{e}")
            return []

    async def insert_or_replace_role(self, role: discord.Role):
        try:
            await self.execute(
                "INSERT OR REPLACE INTO roles (role_id, guild_id, name, color, permissions) VALUES (?, ?, ?, ?, ?)",
                (role.id, role.guild.id, role.name, str(role.color), role.permissions.value)
            )
        except Exception as e:
            logger.error(f"【資料庫】角色同步寫入失敗：{e}")

    async def insert_or_replace_channel(self, channel: discord.abc.GuildChannel):
        try:
            topic = getattr(channel, 'topic', None)
            await self.execute(
                "INSERT OR REPLACE INTO channels (channel_id, guild_id, name, type, topic) VALUES (?, ?, ?, ?, ?)",
                (channel.id, channel.guild.id, channel.name, str(channel.type), topic)
            )
        except Exception as e:
            logger.error(f"【資料庫】頻道同步寫入失敗：{e}")

    async def delete_role(self, role_id: int):
        try:
            await self.execute("DELETE FROM roles WHERE role_id = ?", (role_id,))
        except Exception as e:
            logger.error(f"【資料庫】刪除角色時發生錯誤：{e}")

    async def delete_channel(self, channel_id: int):
        try:
            await self.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        except Exception as e:
            logger.error(f"【資料庫】刪除頻道時發生錯誤：{e}")

    async def compare_and_update_guild(self, guild: discord.Guild) -> bool:
        """
        與 Discord 伺服器現有角色、頻道進行同步。
        """
        try:
            db_roles = await self.get_guild_roles(guild.id)
            db_channels = await self.get_guild_channels(guild.id)
            db_roles_dict = {row['role_id']: row for row in db_roles}
            db_channels_dict = {row['channel_id']: row for row in db_channels}

            # 角色同步
            for role in guild.roles:
                db_role = db_roles_dict.get(role.id)
                if not db_role or db_role['name'] != role.name or db_role['color'] != str(role.color) or db_role['permissions'] != role.permissions.value:
                    await self.insert_or_replace_role(role)
            for db_role_id in db_roles_dict:
                if not discord.utils.get(guild.roles, id=db_role_id):
                    await self.delete_role(db_role_id)

            # 頻道同步
            for ch in guild.channels:
                db_ch = db_channels_dict.get(ch.id)
                topic = getattr(ch, 'topic', None)
                if not db_ch or db_ch['name'] != ch.name or db_ch['type'] != str(ch.type) or db_ch['topic'] != topic:
                    await self.insert_or_replace_channel(ch)
            for db_ch_id in db_channels_dict:
                if not discord.utils.get(guild.channels, id=db_ch_id):
                    await self.delete_channel(db_ch_id)

            logger.info(f"【資料庫】伺服器 {guild.id} 資料同步完成")
            return True
        except Exception as e:
            logger.error(f"【資料庫】伺服器 {guild.id} 資料同步失敗：{e}")
            return False

# 關鍵 setup
async def setup(bot: commands.Bot):
    db_cog = Database(bot)
    await bot.add_cog(db_cog)
    await db_cog.cog_load()
    setattr(bot, "database", db_cog)

# 所有資料庫會自動只存在於根目錄 dbs/ 目錄下！