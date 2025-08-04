"""
反可執行檔案保護模組資料庫操作模組
封裝所有與資料庫相關的操作
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any

import aiosqlite

# 使用統一的核心模組
from src.cogs.core.error_handler import create_error_handler
from src.cogs.core.logger import setup_module_logger
from src.core.config import get_settings

# 設置模組日誌記錄器
logger = setup_module_logger("anti_executable.database")
error_handler = create_error_handler("anti_executable.database", logger)

class AntiExecutableDatabase:
    """反可執行檔案保護資料庫管理器"""

    def __init__(self, cog):
        """
        初始化資料庫管理器

        Args:
            cog: 反可執行檔案保護 Cog 實例
        """
        self.cog = cog

        # 使用配置系統獲取正確的資料庫路徑
        settings = get_settings()
        db_path = settings.database.sqlite_path / "anti_executable.db"

        # 確保資料庫目錄存在
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.db_path = str(db_path)
        self._lock = asyncio.Lock()

    async def init_db(self):
        """初始化資料庫表格"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 配置表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS config (
                        guild_id INTEGER,
                        key TEXT,
                        value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (guild_id, key)
                    )
                """)

                # 統計表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS stats (
                        guild_id INTEGER,
                        stat_type TEXT,
                        count INTEGER DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (guild_id, stat_type)
                    )
                """)

                # 操作日誌表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS action_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER,
                        user_id INTEGER,
                        action TEXT,
                        details TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # 檔案檢測記錄表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS file_detections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER,
                        user_id INTEGER,
                        filename TEXT,
                        file_extension TEXT,
                        risk_level TEXT,
                        action_taken TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # 索引
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_action_logs_guild_time
                    ON action_logs(guild_id, timestamp)
                """)

                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_file_detections_guild_time
                    ON file_detections(guild_id, timestamp)
                """)

                await db.commit()
                logger.info("[反可執行檔案]資料庫初始化完成")

        except Exception as exc:
            error_handler.log_error(exc, "資料庫初始化", "DATABASE_INIT_ERROR")
            raise

    # ───────── 配置管理 ─────────
    async def get_config(self, guild_id: int, key: str, default: str = "") -> str:
        """
        獲取配置值

        Args:
            guild_id: 伺服器 ID
            key: 配置鍵
            default: 預設值

        Returns:
            str: 配置值
        """
        try:
            async with self._lock, aiosqlite.connect(self.db_path) as db, db.execute(
                "SELECT value FROM config WHERE guild_id = ? AND key = ?",
                (guild_id, key),
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else default

        except Exception as exc:
            error_handler.log_error(
                exc, f"獲取配置 - {guild_id}:{key}", "CONFIG_GET_ERROR"
            )
            return default

    async def set_config(self, guild_id: int, key: str, value: str):
        """
        設置配置值

        Args:
            guild_id: 伺服器 ID
            key: 配置鍵
            value: 配置值
        """
        try:
            async with self._lock, aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                        INSERT OR REPLACE INTO config (guild_id, key, value, updated_at)
                        VALUES (?, ?, ?, ?)
                    """,
                    (guild_id, key, value, datetime.now()),
                )
                await db.commit()

        except Exception as exc:
            error_handler.log_error(
                exc, f"設置配置 - {guild_id}:{key}", "CONFIG_SET_ERROR"
            )

    async def get_all_config(self, guild_id: int) -> dict[str, str]:
        """
        獲取伺服器所有配置

        Args:
            guild_id: 伺服器 ID

        Returns:
            Dict[str, str]: 配置字典
        """
        try:
            async with self._lock, aiosqlite.connect(self.db_path) as db, db.execute(
                "SELECT key, value FROM config WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return {row[0]: row[1] for row in rows}

        except Exception as exc:
            error_handler.log_error(
                exc, f"獲取所有配置 - {guild_id}", "CONFIG_GET_ALL_ERROR"
            )
            return {}

    # ───────── 統計管理 ─────────
    async def add_stat(self, guild_id: int, stat_type: str, count: int = 1):
        """
        添加統計資料

        Args:
            guild_id: 伺服器 ID
            stat_type: 統計類型
            count: 數量
        """
        try:
            async with self._lock, aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO stats (guild_id, stat_type, count, last_updated)
                    VALUES (?, ?, COALESCE((SELECT count FROM stats WHERE guild_id = ? AND stat_type = ?), 0) + ?, ?)
                """,
                    (
                        guild_id,
                        stat_type,
                        guild_id,
                        stat_type,
                        count,
                        datetime.now(),
                    ),
                )
                await db.commit()

        except Exception as exc:
            error_handler.log_error(
                exc, f"添加統計 - {guild_id}:{stat_type}", "STATS_ADD_ERROR"
            )

    async def get_stats(self, guild_id: int) -> dict[str, int]:
        """
        獲取統計資料

        Args:
            guild_id: 伺服器 ID

        Returns:
            Dict[str, int]: 統計資料
        """
        try:
            async with self._lock, aiosqlite.connect(self.db_path) as db, db.execute(
                "SELECT stat_type, count FROM stats WHERE guild_id = ?",
                (guild_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return {row[0]: row[1] for row in rows}

        except Exception as exc:
            error_handler.log_error(exc, f"獲取統計 - {guild_id}", "STATS_GET_ERROR")
            return {}

    async def reset_stats(self, guild_id: int):
        """
        重置統計資料

        Args:
            guild_id: 伺服器 ID
        """
        try:
            async with self._lock, aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM stats WHERE guild_id = ?", (guild_id,))
                await db.commit()

        except Exception as exc:
            error_handler.log_error(exc, f"重置統計 - {guild_id}", "STATS_RESET_ERROR")

    # ───────── 操作日誌 ─────────
    async def add_action_log(
        self, guild_id: int, user_id: int, action: str, details: str = ""
    ):
        """
        添加操作日誌

        Args:
            guild_id: 伺服器 ID
            user_id: 用戶 ID
            action: 操作類型
            details: 詳細資訊
        """
        try:
            async with self._lock, aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO action_logs (guild_id, user_id, action, details, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (guild_id, user_id, action, details, datetime.now()),
                )
                await db.commit()

        except Exception as exc:
            error_handler.log_error(
                exc, f"添加操作日誌 - {guild_id}:{user_id}", "ACTION_LOG_ADD_ERROR"
            )

    async def get_action_logs(
        self, guild_id: int, limit: int = 100
    ) -> list[dict[str, Any]]:
        """
        獲取操作日誌

        Args:
            guild_id: 伺服器 ID
            limit: 限制數量

        Returns:
            List[Dict[str, Any]]: 操作日誌列表
        """
        try:
            async with self._lock, aiosqlite.connect(self.db_path) as db, db.execute(
                """
                    SELECT user_id, action, details, timestamp
                    FROM action_logs
                    WHERE guild_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """,
                (guild_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "user_id": row[0],
                        "action": row[1],
                        "details": row[2],
                        "timestamp": row[3],
                    }
                        for row in rows
                    ]

        except Exception as exc:
            error_handler.log_error(
                exc, f"獲取操作日誌 - {guild_id}", "ACTION_LOG_GET_ERROR"
            )
            return []

    async def cleanup_action_logs(self, guild_id: int, days: int = 30):
        """
        清理過期的操作日誌

        Args:
            guild_id: 伺服器 ID,0 表示所有伺服器
            days: 保留天數
        """
        try:
            async with self._lock, aiosqlite.connect(self.db_path) as db:
                cutoff_date = datetime.now() - timedelta(days=days)

                if guild_id == 0:
                    # 清理所有伺服器
                    await db.execute(
                        "DELETE FROM action_logs WHERE timestamp < ?",
                        (cutoff_date,),
                    )
                else:
                    # 清理特定伺服器
                    await db.execute(
                        "DELETE FROM action_logs WHERE guild_id = ? AND timestamp < ?",
                        (guild_id, cutoff_date),
                    )

                await db.commit()

        except Exception as exc:
            error_handler.log_error(
                exc, f"清理操作日誌 - {guild_id}", "ACTION_LOG_CLEANUP_ERROR"
            )

    # ───────── 檔案檢測記錄 ─────────
    async def add_file_detection(
        self,
        guild_id: int,
        user_id: int,
        filename: str,
        file_extension: str,
        risk_level: str,
        action_taken: str,
    ):
        """
        添加檔案檢測記錄

        Args:
            guild_id: 伺服器 ID
            user_id: 用戶 ID
            filename: 檔案名稱
            file_extension: 檔案副檔名
            risk_level: 風險等級
            action_taken: 採取的行動
        """
        try:
            async with self._lock, aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO file_detections (guild_id, user_id, filename, file_extension, risk_level, action_taken, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        guild_id,
                        user_id,
                        filename,
                        file_extension,
                        risk_level,
                        action_taken,
                        datetime.now(),
                    ),
                )
                await db.commit()

        except Exception as exc:
            error_handler.log_error(
                exc,
                f"添加檔案檢測記錄 - {guild_id}:{user_id}",
                "FILE_DETECTION_ADD_ERROR",
            )

    async def get_file_detections(
        self, guild_id: int, limit: int = 100
    ) -> list[dict[str, Any]]:
        """
        獲取檔案檢測記錄

        Args:
            guild_id: 伺服器 ID
            limit: 限制數量

        Returns:
            List[Dict[str, Any]]: 檔案檢測記錄列表
        """
        try:
            async with self._lock, aiosqlite.connect(self.db_path) as db, db.execute(
                """
                SELECT user_id, filename, file_extension, risk_level, action_taken, timestamp
                FROM file_detections
                WHERE guild_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (guild_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                            {
                                "user_id": row[0],
                                "filename": row[1],
                                "file_extension": row[2],
                                "risk_level": row[3],
                                "action_taken": row[4],
                                "timestamp": row[5],
                            }
                            for row in rows
                        ]

        except Exception as exc:
            error_handler.log_error(
                exc, f"獲取檔案檢測記錄 - {guild_id}", "FILE_DETECTION_GET_ERROR"
            )
            return []

    async def get_detection_stats(
        self, guild_id: int, days: int = 30
    ) -> dict[str, Any]:
        """
        獲取檔案檢測統計

        Args:
            guild_id: 伺服器 ID
            days: 統計天數

        Returns:
            Dict[str, Any]: 統計資料
        """
        try:
            async with self._lock, aiosqlite.connect(self.db_path) as db:
                cutoff_date = datetime.now() - timedelta(days=days)

                # 總檢測次數
                async with db.execute(
                    """
                        SELECT COUNT(*) FROM file_detections
                        WHERE guild_id = ? AND timestamp >= ?
                    """,
                    (guild_id, cutoff_date),
                ) as cursor:
                    total_detections = (await cursor.fetchone())[0]

                # 風險等級統計
                async with db.execute(
                    """
                        SELECT risk_level, COUNT(*) FROM file_detections
                        WHERE guild_id = ? AND timestamp >= ?
                        GROUP BY risk_level
                    """,
                    (guild_id, cutoff_date),
                ) as cursor:
                    risk_stats = {row[0]: row[1] for row in await cursor.fetchall()}

                # 檔案類型統計
                async with db.execute(
                    """
                        SELECT file_extension, COUNT(*) FROM file_detections
                        WHERE guild_id = ? AND timestamp >= ?
                        GROUP BY file_extension
                        ORDER BY COUNT(*) DESC
                        LIMIT 10
                    """,
                    (guild_id, cutoff_date),
                ) as cursor:
                    extension_stats = {
                        row[0]: row[1] for row in await cursor.fetchall()
                    }

                # 行動統計
                async with db.execute(
                    """
                        SELECT action_taken, COUNT(*) FROM file_detections
                        WHERE guild_id = ? AND timestamp >= ?
                        GROUP BY action_taken
                    """,
                    (guild_id, cutoff_date),
                ) as cursor:
                    action_stats = {row[0]: row[1] for row in await cursor.fetchall()}

                return {
                    "total_detections": total_detections,
                    "risk_stats": risk_stats,
                    "extension_stats": extension_stats,
                    "action_stats": action_stats,
                    "period_days": days,
                }

        except Exception as exc:
            error_handler.log_error(
                exc, f"獲取檢測統計 - {guild_id}", "DETECTION_STATS_ERROR"
            )
            return {}

    async def cleanup_file_detections(self, guild_id: int, days: int = 90):
        """
        清理過期的檔案檢測記錄

        Args:
            guild_id: 伺服器 ID,0 表示所有伺服器
            days: 保留天數
        """
        try:
            async with self._lock, aiosqlite.connect(self.db_path) as db:
                cutoff_date = datetime.now() - timedelta(days=days)

                if guild_id == 0:
                    # 清理所有伺服器
                    await db.execute(
                        "DELETE FROM file_detections WHERE timestamp < ?",
                        (cutoff_date,),
                    )
                else:
                    # 清理特定伺服器
                    await db.execute(
                        "DELETE FROM file_detections WHERE guild_id = ? AND timestamp < ?",
                        (guild_id, cutoff_date),
                    )

                await db.commit()

        except Exception as exc:
            error_handler.log_error(
                exc, f"清理檔案檢測記錄 - {guild_id}", "FILE_DETECTION_CLEANUP_ERROR"
            )

    # ───────── 資料維護 ─────────
    async def vacuum_database(self):
        """優化資料庫"""
        try:
            async with self._lock, aiosqlite.connect(self.db_path) as db:
                await db.execute("VACUUM")
                await db.commit()
                logger.info("[反可執行檔案]資料庫優化完成")

        except Exception as exc:
            error_handler.log_error(exc, "資料庫優化", "DATABASE_VACUUM_ERROR")

    async def get_database_info(self) -> dict[str, Any]:
        """
        獲取資料庫資訊

        Returns:
            Dict[str, Any]: 資料庫資訊
        """
        try:
            async with self._lock, aiosqlite.connect(self.db_path) as db:
                # 獲取表格資訊
                info = {}

                for table in ["config", "stats", "action_logs", "file_detections"]:
                    async with db.execute("SELECT COUNT(*) FROM " + table) as cursor:
                        count = (await cursor.fetchone())[0]
                        info[f"{table}_count"] = count

                # 獲取資料庫大小
                async with db.execute("PRAGMA page_size") as cursor:
                    page_size = (await cursor.fetchone())[0]

                async with db.execute("PRAGMA page_count") as cursor:
                    page_count = (await cursor.fetchone())[0]

                info["database_size"] = page_size * page_count

                return info

        except Exception as exc:
            error_handler.log_error(exc, "獲取資料庫資訊", "DATABASE_INFO_ERROR")
            return {}
