"""成就系統資料庫遷移管理模組.

此模組包含成就系統所需的所有資料庫遷移腳本，負責建立和管理：
- achievements 資料表：儲存成就定義
- achievement_categories 資料表：成就分類管理
- user_achievements 資料表：用戶已獲得的成就記錄
- achievement_progress 資料表：用戶成就進度追蹤

遵循現有的資料庫管理模式，使用 SQLite 並支援適當的索引和觸發器。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.database import DatabaseConnection, DatabasePool

logger = logging.getLogger(__name__)


class AchievementMigrations:
    """成就系統資料庫遷移管理器."""

    def __init__(self, pool: DatabasePool):
        """初始化遷移管理器.

        Args:
            pool: 資料庫連線池
        """
        self.pool = pool
        self.logger = logger

    async def run_all_migrations(self) -> None:
        """執行所有遷移腳本.

        按順序執行所有必要的資料庫遷移，確保資料庫結構正確建立。
        """
        migrations = [
            self._create_achievement_categories_table,
            self._create_achievements_table,
            self._create_user_achievements_table,
            self._create_achievement_progress_table,
            self._create_achievement_events_table,
            self._create_notification_preferences_table,
            self._create_global_notification_settings_table,
            self._create_notification_events_table,
            self._create_indexes,
            self._create_triggers,
        ]

        self.logger.info("開始執行成就系統資料庫遷移")

        async with self.pool.get_connection() as conn:
            for migration in migrations:
                try:
                    await migration(conn)
                    self.logger.debug(f"遷移完成: {migration.__name__}")
                except Exception as e:
                    self.logger.error(f"遷移失敗 {migration.__name__}: {e}")
                    raise

        self.logger.info("成就系統資料庫遷移完成")

    async def _create_achievement_categories_table(self, conn: DatabaseConnection) -> None:
        """建立成就分類資料表."""
        sql = """
        CREATE TABLE IF NOT EXISTS achievement_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            display_order INTEGER NOT NULL DEFAULT 0,
            icon_emoji TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        await conn.execute(sql)
        await conn.commit()

        # 插入預設分類資料
        default_categories = [
            ("social", "社交成就", 1, "👥"),
            ("activity", "活躍度成就", 2, "⚡"),
            ("special", "特殊成就", 3, "🌟"),
            ("milestone", "里程碑成就", 4, "🏆"),
        ]

        for category_data in default_categories:
            await conn.execute(
                """
                INSERT OR IGNORE INTO achievement_categories
                (name, description, display_order, icon_emoji)
                VALUES (?, ?, ?, ?)
                """,
                category_data
            )
        await conn.commit()

    async def _create_achievements_table(self, conn: DatabaseConnection) -> None:
        """建立成就資料表."""
        sql = """
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('counter', 'milestone', 'time_based', 'conditional')),
            criteria TEXT NOT NULL,  -- JSON 格式的完成條件
            points INTEGER NOT NULL DEFAULT 0,
            badge_url TEXT,
            role_reward TEXT,  -- 獎勵身分組名稱
            is_hidden BOOLEAN NOT NULL DEFAULT 0,  -- 是否為隱藏成就
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES achievement_categories(id) ON DELETE CASCADE
        )
        """
        await conn.execute(sql)
        await conn.commit()

    async def _create_user_achievements_table(self, conn: DatabaseConnection) -> None:
        """建立用戶成就記錄資料表."""
        sql = """
        CREATE TABLE IF NOT EXISTS user_achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,  -- Discord 用戶 ID
            achievement_id INTEGER NOT NULL,
            earned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            notified BOOLEAN NOT NULL DEFAULT 0,
            FOREIGN KEY (achievement_id) REFERENCES achievements(id) ON DELETE CASCADE,
            UNIQUE(user_id, achievement_id)  -- 防止重複獲得同一成就
        )
        """
        await conn.execute(sql)
        await conn.commit()

    async def _create_achievement_progress_table(self, conn: DatabaseConnection) -> None:
        """建立成就進度追蹤資料表."""
        sql = """
        CREATE TABLE IF NOT EXISTS achievement_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,  -- Discord 用戶 ID
            achievement_id INTEGER NOT NULL,
            current_value REAL NOT NULL DEFAULT 0.0,
            target_value REAL NOT NULL,
            progress_data TEXT,  -- JSON 格式的複雜進度資料
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (achievement_id) REFERENCES achievements(id) ON DELETE CASCADE,
            UNIQUE(user_id, achievement_id)  -- 每個用戶每個成就只有一個進度記錄
        )
        """
        await conn.execute(sql)
        await conn.commit()

    async def _create_achievement_events_table(self, conn: DatabaseConnection) -> None:
        """建立成就事件資料表."""
        sql = """
        CREATE TABLE IF NOT EXISTS achievement_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,  -- Discord 用戶 ID
            guild_id INTEGER NOT NULL,  -- Discord 伺服器 ID
            event_type TEXT NOT NULL,  -- 事件類型 (如 'achievement.message_sent')
            event_data TEXT NOT NULL,  -- JSON 格式的事件詳細資料
            timestamp DATETIME NOT NULL,  -- 事件發生時間
            channel_id INTEGER,  -- 頻道 ID (可選)
            processed BOOLEAN NOT NULL DEFAULT 0,  -- 是否已被處理
            correlation_id TEXT,  -- 事件關聯 ID
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        await conn.execute(sql)
        await conn.commit()

    async def _create_notification_preferences_table(self, conn: DatabaseConnection) -> None:
        """建立用戶通知偏好資料表."""
        sql = """
        CREATE TABLE IF NOT EXISTS notification_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            dm_notifications BOOLEAN NOT NULL DEFAULT 1,
            server_announcements BOOLEAN NOT NULL DEFAULT 1,
            notification_types TEXT DEFAULT '[]',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, guild_id)
        )
        """
        await conn.execute(sql)
        await conn.commit()

    async def _create_global_notification_settings_table(self, conn: DatabaseConnection) -> None:
        """建立全域通知設定資料表."""
        sql = """
        CREATE TABLE IF NOT EXISTS global_notification_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL UNIQUE,
            announcement_channel_id INTEGER,
            announcement_enabled BOOLEAN NOT NULL DEFAULT 0,
            rate_limit_seconds INTEGER NOT NULL DEFAULT 60,
            important_achievements_only BOOLEAN NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        await conn.execute(sql)
        await conn.commit()

    async def _create_notification_events_table(self, conn: DatabaseConnection) -> None:
        """建立通知事件記錄資料表."""
        sql = """
        CREATE TABLE IF NOT EXISTS notification_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            achievement_id INTEGER NOT NULL,
            notification_type TEXT NOT NULL,
            sent_at DATETIME NOT NULL,
            delivery_status TEXT NOT NULL DEFAULT 'pending',
            error_message TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (achievement_id) REFERENCES achievements(id)
        )
        """
        await conn.execute(sql)
        await conn.commit()

    async def _create_indexes(self, conn: DatabaseConnection) -> None:
        """建立效能索引."""
        indexes = [
            # achievements 表索引
            "CREATE INDEX IF NOT EXISTS idx_achievements_category ON achievements(category_id)",
            "CREATE INDEX IF NOT EXISTS idx_achievements_active ON achievements(is_active)",
            "CREATE INDEX IF NOT EXISTS idx_achievements_type ON achievements(type)",

            # user_achievements 表索引
            "CREATE INDEX IF NOT EXISTS idx_user_achievements_user ON user_achievements(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_achievements_achievement ON user_achievements(achievement_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_achievements_earned ON user_achievements(earned_at)",
            "CREATE INDEX IF NOT EXISTS idx_user_achievements_notified ON user_achievements(notified)",

            # achievement_progress 表索引
            "CREATE INDEX IF NOT EXISTS idx_achievement_progress_user ON achievement_progress(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_achievement_progress_achievement ON achievement_progress(achievement_id)",
            "CREATE INDEX IF NOT EXISTS idx_achievement_progress_updated ON achievement_progress(last_updated)",

            # achievement_categories 表索引
            "CREATE INDEX IF NOT EXISTS idx_achievement_categories_order ON achievement_categories(display_order)",

            # achievement_events 表索引
            "CREATE INDEX IF NOT EXISTS idx_achievement_events_user ON achievement_events(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_achievement_events_guild ON achievement_events(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_achievement_events_type ON achievement_events(event_type)",
            "CREATE INDEX IF NOT EXISTS idx_achievement_events_timestamp ON achievement_events(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_achievement_events_processed ON achievement_events(processed)",
            "CREATE INDEX IF NOT EXISTS idx_achievement_events_user_type ON achievement_events(user_id, event_type)",
            "CREATE INDEX IF NOT EXISTS idx_achievement_events_guild_timestamp ON achievement_events(guild_id, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_achievement_events_correlation ON achievement_events(correlation_id)",

            # 通知偏好表索引
            "CREATE INDEX IF NOT EXISTS idx_notification_preferences_user_guild ON notification_preferences(user_id, guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_notification_preferences_guild ON notification_preferences(guild_id)",

            # 全域通知設定表索引
            "CREATE INDEX IF NOT EXISTS idx_global_notification_settings_guild ON global_notification_settings(guild_id)",

            # 通知事件表索引
            "CREATE INDEX IF NOT EXISTS idx_notification_events_user_guild ON notification_events(user_id, guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_notification_events_achievement ON notification_events(achievement_id)",
            "CREATE INDEX IF NOT EXISTS idx_notification_events_sent_at ON notification_events(sent_at)",
            "CREATE INDEX IF NOT EXISTS idx_notification_events_delivery_status ON notification_events(delivery_status)",
            "CREATE INDEX IF NOT EXISTS idx_notification_events_user_sent_at ON notification_events(user_id, sent_at)",

            # Story 5.1 效能優化複合索引
            "CREATE INDEX IF NOT EXISTS idx_user_achievements_user_earned ON user_achievements(user_id, earned_at)",
            "CREATE INDEX IF NOT EXISTS idx_achievement_progress_user_updated ON achievement_progress(user_id, last_updated)",
            "CREATE INDEX IF NOT EXISTS idx_achievements_category_active ON achievements(category_id, is_active)",
            "CREATE INDEX IF NOT EXISTS idx_achievements_type_active ON achievements(type, is_active)",
            "CREATE INDEX IF NOT EXISTS idx_user_achievements_achievement_earned ON user_achievements(achievement_id, earned_at)",
            "CREATE INDEX IF NOT EXISTS idx_achievement_events_user_guild_timestamp ON achievement_events(user_id, guild_id, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_achievement_events_processed_timestamp ON achievement_events(processed, timestamp)",
        ]

        for index_sql in indexes:
            await conn.execute(index_sql)

        await conn.commit()

    async def _create_triggers(self, conn: DatabaseConnection) -> None:
        """建立自動更新時間戳觸發器."""
        triggers = [
            # achievements 表更新觸發器
            """
            CREATE TRIGGER IF NOT EXISTS trg_achievements_updated_at
            AFTER UPDATE ON achievements
            FOR EACH ROW
            BEGIN
                UPDATE achievements SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
            """,

            # achievement_categories 表更新觸發器
            """
            CREATE TRIGGER IF NOT EXISTS trg_achievement_categories_updated_at
            AFTER UPDATE ON achievement_categories
            FOR EACH ROW
            BEGIN
                UPDATE achievement_categories SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
            """,

            # achievement_progress 表更新觸發器
            """
            CREATE TRIGGER IF NOT EXISTS trg_achievement_progress_updated_at
            AFTER UPDATE ON achievement_progress
            FOR EACH ROW
            BEGIN
                UPDATE achievement_progress SET last_updated = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
            """,

            # notification_preferences 表更新觸發器
            """
            CREATE TRIGGER IF NOT EXISTS trg_notification_preferences_updated_at
            AFTER UPDATE ON notification_preferences
            FOR EACH ROW
            BEGIN
                UPDATE notification_preferences SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
            """,

            # global_notification_settings 表更新觸發器
            """
            CREATE TRIGGER IF NOT EXISTS trg_global_notification_settings_updated_at
            AFTER UPDATE ON global_notification_settings
            FOR EACH ROW
            BEGIN
                UPDATE global_notification_settings SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
            """,
        ]

        for trigger_sql in triggers:
            await conn.execute(trigger_sql)

        await conn.commit()

    async def verify_schema(self) -> bool:
        """驗證資料庫 Schema 是否正確建立.

        Returns:
            True 如果所有表格和索引都正確建立，否則 False
        """
        expected_tables = [
            "achievement_categories",
            "achievements",
            "user_achievements",
            "achievement_progress",
            "achievement_events",
            "notification_preferences",
            "global_notification_settings",
            "notification_events"
        ]

        async with self.pool.get_connection() as conn:
            # 檢查表格是否存在
            for table in expected_tables:
                cursor = await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                )
                result = await cursor.fetchone()
                if not result:
                    self.logger.error(f"表格 {table} 不存在")
                    return False

            # 檢查是否有預設分類資料
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM achievement_categories"
            )
            result = await cursor.fetchone()
            if not result or result[0] == 0:
                self.logger.error("achievement_categories 表格沒有預設資料")
                return False

        self.logger.info("資料庫 Schema 驗證通過")
        return True

    async def drop_all_tables(self) -> None:
        """刪除所有成就相關表格（用於測試或重置）.

        WARNING: 這會刪除所有成就資料，僅用於開發和測試環境。
        """
        tables = [
            "notification_events",
            "global_notification_settings",
            "notification_preferences",
            "achievement_events",
            "achievement_progress",
            "user_achievements",
            "achievements",
            "achievement_categories"
        ]

        async with self.pool.get_connection() as conn:
            # 停用外鍵約束以避免刪除順序問題
            await conn.execute("PRAGMA foreign_keys = OFF")

            for table in tables:
                await conn.execute(f"DROP TABLE IF EXISTS {table}")
                self.logger.debug(f"已刪除表格: {table}")

            # 重新啟用外鍵約束
            await conn.execute("PRAGMA foreign_keys = ON")
            await conn.commit()

        self.logger.info("所有成就相關表格已刪除")


async def initialize_achievement_database(pool: DatabasePool) -> None:
    """初始化成就系統資料庫.

    Args:
        pool: 資料庫連線池
    """
    migrations = AchievementMigrations(pool)
    await migrations.run_all_migrations()

    # 驗證 Schema
    if not await migrations.verify_schema():
        raise RuntimeError("成就資料庫 Schema 驗證失敗")


__all__ = [
    "AchievementMigrations",
    "initialize_achievement_database",
]
