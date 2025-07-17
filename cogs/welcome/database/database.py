"""
歡迎系統資料庫模組

此模組包含所有與資料庫相關的操作，封裝為 WelcomeDB 類別
使用專業級連接池管理
"""

import aiosqlite
import contextlib
import logging
from typing import Dict, Any, Optional

from config import WELCOME_DB_PATH
from ..config.config import DEFAULT_SETTINGS
from ...core.database_pool import get_global_pool

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
                
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS welcome_backgrounds (
                        guild_id INTEGER PRIMARY KEY,
                        image_path TEXT
                    )
                """)
                await conn.commit()
            
        except Exception as exc:
            logger.error("資料庫初始化失敗，請檢查檔案權限或路徑。", exc_info=True)

    async def get_settings(self, guild_id: int) -> Dict[str, Any]:
        """
        取得伺服器的歡迎訊息設定
        
        Args:
            guild_id: Discord 伺服器 ID
            
        Returns:
            Dict[str, Any]: 設定值字典
        """
        await self.init_db()
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                cursor = await conn.execute("SELECT * FROM welcome_settings WHERE guild_id=?", (guild_id,))
                row = await cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    db_settings = dict(zip(columns, row))
                    merged = DEFAULT_SETTINGS.copy()
                    merged.update({k: v for k, v in db_settings.items() if v is not None})
                    return merged
        except Exception as exc:
            logger.error("讀取資料庫設定失敗", exc_info=True)
        return DEFAULT_SETTINGS.copy()

    async def update_setting(self, guild_id: int, key: str, value: Any) -> None:
        """
        更新單一設定值
        
        Args:
            guild_id: Discord 伺服器 ID
            key: 設定鍵名
            value: 設定值
        """
        await self.init_db()
        try:
            if not await self.exists(guild_id):
                await self.insert_defaults(guild_id)
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                await conn.execute(f"UPDATE welcome_settings SET {key}=? WHERE guild_id=?", (value, guild_id))
                await conn.commit()
        except Exception as exc:
            logger.error(f"更新設定失敗（欄位: {key}）", exc_info=True)

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
                cursor = await conn.execute("SELECT 1 FROM welcome_settings WHERE guild_id=?", (guild_id,))
                return await cursor.fetchone() is not None
        except Exception as exc:
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
                await conn.execute("""
                    INSERT OR IGNORE INTO welcome_settings
                    (guild_id, channel_id, title, description, message, avatar_x, avatar_y,
                     title_y, description_y, title_font_size, desc_font_size, avatar_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
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
                ))
                await conn.commit()
        except Exception as exc:
            logger.error("寫入預設設定失敗", exc_info=True)

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
                    (guild_id, image_path)
                )
                await conn.commit()
        except Exception as exc:
            logger.error("更新背景圖片失敗", exc_info=True)
            
    async def get_background_path(self, guild_id: int) -> Optional[str]:
        """
        取得伺服器的背景圖片路徑
        
        Args:
            guild_id: Discord 伺服器 ID
            
        Returns:
            Optional[str]: 背景圖片路徑，若無則為 None
        """
        await self.init_db()
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                cursor = await conn.execute("SELECT image_path FROM welcome_backgrounds WHERE guild_id=?", (guild_id,))
                row = await cursor.fetchone()
                return row[0] if row else None
        except Exception as exc:
            logger.error("取得背景圖片路徑失敗", exc_info=True)
            return None

    async def close(self):
        """關閉資料庫連接（現在由全局連接池管理）"""
        # 連接池由全局管理器處理，這裡不需要手動關閉
        logger.info("【歡迎系統】資料庫連接已由全局連接池管理") 