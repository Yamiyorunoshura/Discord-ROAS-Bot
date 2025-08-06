"""
反惡意連結保護模組資料庫管理
- 封裝所有資料庫操作
- 提供配置管理功能
- 支援黑名單快取和更新
- 統計和日誌記錄
"""

import datetime as dt
import logging
from typing import TYPE_CHECKING, Any

import aiosqlite

from src.core.config import get_settings

if TYPE_CHECKING:
    from ..main.main import AntiLink


class AntiLinkDatabase:
    """
    反惡意連結資料庫管理器

    負責處理所有與資料庫相關的操作,包括:
    - 配置管理
    - 黑名單快取
    - 統計記錄
    - 操作日誌
    """

    def __init__(self, cog: "AntiLink"):
        """
        初始化資料庫管理器

        Args:
            cog: AntiLink 模組實例
        """
        self.cog = cog
        self.logger = logging.getLogger("anti_link.database")

        # 使用配置系統獲取正確的資料庫路徑
        settings = get_settings()
        db_path = settings.database.sqlite_path / "anti_link.db"

        # 確保資料庫目錄存在
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._db_path = str(db_path)

    def _get_db_path(self) -> str:
        """獲取資料庫路徑"""
        return self._db_path

    async def init_db(self):
        """初始化資料庫表格"""
        try:
            async with aiosqlite.connect(self._get_db_path()) as db:
                # 創建配置表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS config (
                        guild_id INTEGER,
                        key TEXT,
                        value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (guild_id, key)
                    )
                """)

                # 創建黑名單快取表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS blacklist_cache (
                        domain TEXT PRIMARY KEY,
                        source TEXT,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # 創建統計表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS stats (
                        guild_id INTEGER,
                        stat_type TEXT,
                        count INTEGER DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (guild_id, stat_type)
                    )
                """)

                # 創建操作日誌表
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

                # 創建索引
                await db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_config_guild ON config(guild_id)"
                )
                await db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_stats_guild ON stats(guild_id)"
                )
                await db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_logs_guild ON action_logs(guild_id)"
                )
                await db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON action_logs(timestamp)"
                )

                await db.commit()
                self.logger.info("[反惡意連結]資料庫初始化完成")

        except Exception as exc:
            self.logger.error(f"[反惡意連結]資料庫初始化失敗: {exc}")
            raise

    # ───────── 配置管理 ─────────
    async def get_config(
        self, guild_id: int, key: str, default: str | None = None
    ) -> str | None:
        """
        取得配置值

        Args:
            guild_id: 伺服器 ID
            key: 配置鍵
            default: 預設值

        Returns:
            str | None: 配置值
        """
        try:
            async with (
                aiosqlite.connect(self._get_db_path()) as db,
                db.execute(
                    "SELECT value FROM config WHERE guild_id = ? AND key = ?",
                    (guild_id, key),
                ) as cursor,
            ):
                row = await cursor.fetchone()
                return row[0] if row else default

        except Exception as exc:
            self.logger.error(f"[反惡意連結]取得配置失敗 {guild_id}.{key}: {exc}")
            return default

    async def set_config(self, guild_id: int, key: str, value: str):
        """
        設定配置值

        Args:
            guild_id: 伺服器 ID
            key: 配置鍵
            value: 配置值
        """
        try:
            async with aiosqlite.connect(self._get_db_path()) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO config (guild_id, key, value, updated_at)
                    VALUES (?, ?, ?, ?)
                """,
                    (guild_id, key, value, dt.datetime.now()),
                )
                await db.commit()

        except Exception as exc:
            self.logger.error(f"[反惡意連結]設定配置失敗 {guild_id}.{key}: {exc}")
            raise

    async def get_all_config(self, guild_id: int) -> dict[str, str]:
        """
        取得伺服器所有配置

        Args:
            guild_id: 伺服器 ID

        Returns:
            Dict[str, str]: 配置字典
        """
        try:
            async with (
                aiosqlite.connect(self._get_db_path()) as db,
                db.execute(
                    "SELECT key, value FROM config WHERE guild_id = ?", (guild_id,)
                ) as cursor,
            ):
                rows = await cursor.fetchall()
                return {row[0]: row[1] for row in rows}

        except Exception as exc:
            self.logger.error(f"[反惡意連結]取得所有配置失敗 {guild_id}: {exc}")
            return {}

    # ───────── 黑名單管理 ─────────
    async def update_blacklist_cache(self, domains: set[str], source: str):
        """
        更新黑名單快取

        Args:
            domains: 網域集合
            source: 來源名稱
        """
        try:
            async with aiosqlite.connect(self._get_db_path()) as db:
                now = dt.datetime.now()

                # 批次插入或更新
                for domain in domains:
                    await db.execute(
                        """
                        INSERT OR REPLACE INTO blacklist_cache
                        (domain, source, added_at, last_seen)
                        VALUES (?, ?,
                            COALESCE((SELECT added_at FROM blacklist_cache WHERE domain = ?), ?),
                            ?)
                    """,
                        (domain, source, domain, now, now),
                    )

                await db.commit()
                self.logger.info(
                    f"[反惡意連結]更新黑名單快取: {len(domains)} 個網域來自 {source}"
                )

        except Exception as exc:
            self.logger.error(f"[反惡意連結]更新黑名單快取失敗: {exc}")
            raise

    async def get_blacklist_cache(self, source: str | None = None) -> set[str]:
        """
        取得黑名單快取

        Args:
            source: 來源過濾(可選)

        Returns:
            Set[str]: 黑名單網域集合
        """
        try:
            async with aiosqlite.connect(self._get_db_path()) as db:
                if source:
                    async with db.execute(
                        "SELECT domain FROM blacklist_cache WHERE source = ?", (source,)
                    ) as cursor:
                        rows = await cursor.fetchall()
                else:
                    async with db.execute(
                        "SELECT domain FROM blacklist_cache"
                    ) as cursor:
                        rows = await cursor.fetchall()

                return {row[0] for row in rows}

        except Exception as exc:
            self.logger.error(f"[反惡意連結]取得黑名單快取失敗: {exc}")
            return set()

    async def cleanup_blacklist_cache(self, days: int = 30):
        """
        清理過期的黑名單快取

        Args:
            days: 保留天數
        """
        try:
            async with aiosqlite.connect(self._get_db_path()) as db:
                cutoff_date = dt.datetime.now() - dt.timedelta(days=days)

                result = await db.execute(
                    "DELETE FROM blacklist_cache WHERE last_seen < ?", (cutoff_date,)
                )

                await db.commit()
                self.logger.info(
                    f"[反惡意連結]清理黑名單快取: 刪除 {result.rowcount} 個過期項目"
                )

        except Exception as exc:
            self.logger.error(f"[反惡意連結]清理黑名單快取失敗: {exc}")

    # ───────── 統計管理 ─────────
    async def add_stat(self, guild_id: int, stat_type: str, count: int = 1):
        """
        添加統計資料

        Args:
            guild_id: 伺服器 ID
            stat_type: 統計類型
            count: 增加數量
        """
        try:
            async with aiosqlite.connect(self._get_db_path()) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO stats (guild_id, stat_type, count, last_updated)
                    VALUES (?, ?,
                        COALESCE((SELECT count FROM stats WHERE guild_id = ? AND stat_type = ?), 0) + ?,
                        ?)
                """,
                    (
                        guild_id,
                        stat_type,
                        guild_id,
                        stat_type,
                        count,
                        dt.datetime.now(),
                    ),
                )

                await db.commit()

        except Exception as exc:
            self.logger.error(f"[反惡意連結]添加統計失敗: {exc}")

    async def get_stats(self, guild_id: int) -> dict[str, int]:
        """
        取得統計資料

        Args:
            guild_id: 伺服器 ID

        Returns:
            Dict[str, int]: 統計資料字典
        """
        try:
            async with (
                aiosqlite.connect(self._get_db_path()) as db,
                db.execute(
                    "SELECT stat_type, count FROM stats WHERE guild_id = ?", (guild_id,)
                ) as cursor,
            ):
                rows = await cursor.fetchall()
                return {row[0]: row[1] for row in rows}

        except Exception as exc:
            self.logger.error(f"[反惡意連結]取得統計失敗: {exc}")
            return {}

    async def reset_stats(self, guild_id: int):
        """
        重置統計資料

        Args:
            guild_id: 伺服器 ID
        """
        try:
            async with aiosqlite.connect(self._get_db_path()) as db:
                await db.execute("DELETE FROM stats WHERE guild_id = ?", (guild_id,))
                await db.commit()

        except Exception as exc:
            self.logger.error(f"[反惡意連結]重置統計失敗: {exc}")

    # ───────── 操作日誌 ─────────
    async def add_action_log(
        self, guild_id: int, user_id: int, action: str, details: str
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
            async with aiosqlite.connect(self._get_db_path()) as db:
                await db.execute(
                    """
                    INSERT INTO action_logs (guild_id, user_id, action, details, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (guild_id, user_id, action, details, dt.datetime.now()),
                )

                await db.commit()

        except Exception as exc:
            self.logger.error(f"[反惡意連結]添加操作日誌失敗: {exc}")

    async def get_action_logs(
        self, guild_id: int, limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        取得操作日誌

        Args:
            guild_id: 伺服器 ID
            limit: 限制數量

        Returns:
            List[Dict[str, Any]]: 操作日誌列表
        """
        try:
            async with (
                aiosqlite.connect(self._get_db_path()) as db,
                db.execute(
                    """
                SELECT user_id, action, details, timestamp
                FROM action_logs
                WHERE guild_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                    (guild_id, limit),
                ) as cursor,
            ):
                rows = await cursor.fetchall()

                logs = []
                for row in rows:
                    logs.append({
                        "user_id": row[0],
                        "action": row[1],
                        "details": row[2],
                        "timestamp": row[3],
                    })

                    return logs

        except Exception as exc:
            self.logger.error(f"[反惡意連結]取得操作日誌失敗: {exc}")
            return []

    async def cleanup_action_logs(self, guild_id: int, days: int = 30):
        """
        清理過期的操作日誌

        Args:
            guild_id: 伺服器 ID
            days: 保留天數
        """
        try:
            async with aiosqlite.connect(self._get_db_path()) as db:
                cutoff_date = dt.datetime.now() - dt.timedelta(days=days)

                result = await db.execute(
                    "DELETE FROM action_logs WHERE guild_id = ? AND timestamp < ?",
                    (guild_id, cutoff_date),
                )

                await db.commit()
                self.logger.info(
                    f"[反惡意連結]清理操作日誌: 刪除 {result.rowcount} 個過期項目"
                )

        except Exception as exc:
            self.logger.error(f"[反惡意連結]清理操作日誌失敗: {exc}")
