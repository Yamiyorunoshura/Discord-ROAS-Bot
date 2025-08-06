"""
🗄️ 測試資料庫配置模組
提供隔離的測試資料庫環境和相關 fixtures
"""

import tempfile
from pathlib import Path

import aiosqlite


class TestDatabaseManager:
    """測試資料庫管理器"""

    def __init__(self) -> None:
        self.temp_dir: str | None = None
        self.connections: dict[str, aiosqlite.Connection] = {}

    async def setup_test_databases(self) -> dict[str, Path]:
        """
        設置測試資料庫

        Returns:
            資料庫名稱到路徑的映射
        """
        # 創建臨時目錄
        self.temp_dir = tempfile.mkdtemp(prefix="adr_bot_test_")

        # 定義測試資料庫
        databases = {
            "activity": "activity_test.db",
            "message": "message_test.db",
            "welcome": "welcome_test.db",
            "protection": "protection_test.db",
            "sync": "sync_test.db",
            "main": "main_test.db",
        }

        db_paths = {}
        for name, filename in databases.items():
            if self.temp_dir is None:
                raise RuntimeError("Temporary directory not initialized")
            db_path = Path(self.temp_dir) / filename
            db_paths[name] = db_path

            # 創建並初始化資料庫
            conn = await aiosqlite.connect(str(db_path))
            conn.row_factory = aiosqlite.Row
            self.connections[name] = conn

            # 初始化對應的 schema
            await self._initialize_schema(name, conn)

        return db_paths

    async def _initialize_schema(
        self, db_name: str, conn: aiosqlite.Connection
    ) -> None:
        """
        初始化資料庫 schema

        Args:
            db_name: 資料庫名稱
            conn: 資料庫連接
        """
        if db_name == "activity":
            await self._init_activity_schema(conn)
        elif db_name == "message":
            await self._init_message_schema(conn)
        elif db_name == "welcome":
            await self._init_welcome_schema(conn)
        elif db_name == "protection":
            await self._init_protection_schema(conn)
        elif db_name == "sync":
            await self._init_sync_schema(conn)

    async def _init_activity_schema(self, conn: aiosqlite.Connection) -> None:
        """初始化活躍度資料庫 schema"""
        await conn.executescript("""
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
        await conn.commit()

    async def _init_message_schema(self, conn: aiosqlite.Connection) -> None:
        """初始化訊息資料庫 schema"""
        await conn.executescript("""
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
        await conn.commit()

    async def _init_welcome_schema(self, conn: aiosqlite.Connection) -> None:
        """初始化歡迎系統資料庫 schema"""
        await conn.executescript("""
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
        await conn.commit()

    async def _init_protection_schema(self, conn: aiosqlite.Connection) -> None:
        """初始化保護系統資料庫 schema"""
        await conn.executescript("""
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
        """)
        await conn.commit()

    async def _init_sync_schema(self, conn: aiosqlite.Connection) -> None:
        """初始化同步系統資料庫 schema"""
        await conn.executescript("""
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
            CREATE TABLE IF NOT EXISTS members (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                discriminator TEXT,
                joined_at REAL,
                last_updated REAL,
                PRIMARY KEY(user_id, guild_id)
            );
        """)
        await conn.commit()

    async def get_connection(self, db_name: str) -> aiosqlite.Connection:
        """
        獲取資料庫連接

        Args:
            db_name: 資料庫名稱

        Returns:
            資料庫連接
        """
        if db_name not in self.connections:
            raise ValueError(f"未知的資料庫: {db_name}")
        return self.connections[db_name]

    async def cleanup(self) -> None:
        """清理測試資料庫"""
        # 關閉所有連接
        for conn in self.connections.values():
            await conn.close()

        # 清理臨時目錄
        if self.temp_dir and Path(self.temp_dir).exists():
            import shutil

            shutil.rmtree(self.temp_dir)
