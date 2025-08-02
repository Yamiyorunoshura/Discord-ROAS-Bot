"""
歡迎系統資料庫模組

此模組包含所有與資料庫相關的操作,封裝為 WelcomeDB 類別
使用專業級連接池管理
"""

import logging
from typing import Any

# 使用統一配置系統獲取路徑
from src.core.config import get_settings

# 獲取配置實例
_settings = get_settings()
WELCOME_DB_PATH = str(_settings.get_database_path("welcome"))

from ...core.database_pool import get_global_pool
from ..config.config import DEFAULT_SETTINGS

logger = logging.getLogger("welcome")


class WelcomeDB:
    """歡迎訊息資料庫管理類別"""

    def __init__(self, db_path: str = WELCOME_DB_PATH):
        """
        初始化資料庫管理類別

        Args:
            db_path: 資料庫檔案路徑
        """
        self.db_path = db_path
        self._pool = None  # 將使用全局連接池

    async def _get_pool(self):
        """獲取全局連接池實例"""
        if self._pool is None:
            self._pool = await get_global_pool()
        return self._pool

    async def init_db(self) -> None:
        """初始化資料庫結構"""
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS welcome_settings (
                        guild_id INTEGER PRIMARY KEY,
                        channel_id INTEGER,
                        title TEXT,
                        description TEXT,
                        message TEXT,
                        avatar_x INTEGER,
                        avatar_y INTEGER,
                        title_y INTEGER,
                        description_y INTEGER,
                        title_font_size INTEGER,
                        desc_font_size INTEGER,
                        avatar_size INTEGER
                    )
                """)
                await conn.commit()
                logger.info("【歡迎系統】資料庫表結構初始化完成")
        except Exception as exc:
            logger.error(f"【歡迎系統】資料庫初始化失敗: {exc}", exc_info=True)
            raise

    async def exists(self, guild_id: int) -> bool:
        """
        檢查伺服器設定是否存在

        Args:
            guild_id: Discord 伺服器 ID

        Returns:
            bool: 是否存在設定
        """
        await self.init_db()
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                cursor = await conn.execute(
                    "SELECT 1 FROM welcome_settings WHERE guild_id=?", (guild_id,)
                )
                return await cursor.fetchone() is not None
        except Exception:
            logger.error("檢查資料庫紀錄存在失敗", exc_info=True)
            return False

    async def insert_defaults(self, guild_id: int) -> None:
        """
        插入預設設定

        Args:
            guild_id: Discord 伺服器 ID
        """
        defaults = DEFAULT_SETTINGS.copy()
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                await conn.execute(
                    """
                    INSERT OR IGNORE INTO welcome_settings
                    (guild_id, channel_id, title, description, message, avatar_x, avatar_y,
                     title_y, description_y, title_font_size, desc_font_size, avatar_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        guild_id,
                        defaults["channel_id"],
                        defaults["title"],
                        defaults["description"],
                        defaults["message"],
                        defaults["avatar_x"],
                        defaults["avatar_y"],
                        defaults["title_y"],
                        defaults["description_y"],
                        defaults["title_font_size"],
                        defaults["desc_font_size"],
                        defaults["avatar_size"],
                    ),
                )
                await conn.commit()
        except Exception:
            logger.error("寫入預設設定失敗", exc_info=True)

    async def get_settings(self, guild_id: int) -> dict[str, Any]:
        """
        獲取伺服器設定

        Args:
            guild_id: Discord 伺服器 ID

        Returns:
            Dict[str, Any]: 設定字典
        """
        await self.init_db()
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                cursor = await conn.execute(
                    """
                    SELECT channel_id, title, description, message, avatar_x, avatar_y,
                           title_y, description_y, title_font_size, desc_font_size, avatar_size
                    FROM welcome_settings WHERE guild_id=?
                """,
                    (guild_id,),
                )
                row = await cursor.fetchone()

                if row:
                    return {
                        "channel_id": row[0],
                        "title": row[1],
                        "description": row[2],
                        "message": row[3],
                        "avatar_x": row[4],
                        "avatar_y": row[5],
                        "title_y": row[6],
                        "description_y": row[7],
                        "title_font_size": row[8],
                        "desc_font_size": row[9],
                        "avatar_size": row[10],
                    }
                else:
                    # 如果沒有設定,插入預設值並返回
                    await self.insert_defaults(guild_id)
                    return DEFAULT_SETTINGS.copy()
        except Exception:
            logger.error("獲取設定失敗", exc_info=True)
            return DEFAULT_SETTINGS.copy()

    async def update_setting(self, guild_id: int, key: str, value: Any) -> None:
        """
        更新特定設定

        Args:
            guild_id: Discord 伺服器 ID
            key: 設定鍵名
            value: 設定值
        """
        await self.init_db()
        # 確保記錄存在
        if not await self.exists(guild_id):
            await self.insert_defaults(guild_id)

        # 驗證key是否為有效的列名
        valid_keys = {
            "channel_id",
            "title",
            "description",
            "message",
            "avatar_x",
            "avatar_y",
            "title_y",
            "description_y",
            "title_font_size",
            "desc_font_size",
            "avatar_size",
        }
        if key not in valid_keys:
            raise ValueError(f"Invalid setting key: {key}")

        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                await conn.execute(
                    f"UPDATE welcome_settings SET {key}=? WHERE guild_id=?",
                    (value, guild_id),
                )
                await conn.commit()
        except Exception:
            logger.error(f"更新設定失敗(欄位: {key})", exc_info=True)

    async def update_welcome_background(self, guild_id: int, image_path: str) -> None:
        """
        更新歡迎背景圖片

        Args:
            guild_id: Discord 伺服器 ID
            image_path: 圖片檔案路徑
        """
        await self.init_db()
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                await conn.execute(
                    "INSERT OR REPLACE INTO welcome_backgrounds (guild_id, image_path) VALUES (?, ?)",
                    (guild_id, image_path),
                )
                await conn.commit()
        except Exception:
            logger.error("更新背景圖片失敗", exc_info=True)

    async def get_background_path(self, guild_id: int) -> str | None:
        """
        取得伺服器的背景圖片路徑

        Args:
            guild_id: Discord 伺服器 ID

        Returns:
            str | None: 背景圖片路徑,若無則為 None
        """
        await self.init_db()
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                cursor = await conn.execute(
                    "SELECT image_path FROM welcome_backgrounds WHERE guild_id=?",
                    (guild_id,),
                )
                row = await cursor.fetchone()
                return row[0] if row else None
        except Exception:
            logger.error("取得背景圖片路徑失敗", exc_info=True)
            return None

    async def close(self):
        """關閉資料庫連接(現在由全局連接池管理)"""
        # 連接池由全局管理器處理,這裡不需要手動關閉
        logger.info("【歡迎系統】資料庫連接已由全局連接池管理")
