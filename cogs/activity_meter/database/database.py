"""
活躍度系統模組資料庫操作類別
- 封裝所有與資料庫相關的操作
- 提供統一的資料存取介面
- 使用專業級連接池管理
"""

import aiosqlite
import asyncio
import logging
import time
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any, Union

from ..config import config
from ...core.database_pool import get_global_pool

logger = logging.getLogger("activity_meter")

class ActivityDatabase:
    """
    活躍度系統資料庫操作類別
    
    功能：
    - 提供非同步資料庫操作
    - 使用專業級連接池管理
    - 完整的錯誤處理
    - 提供所有活躍度系統所需的資料庫操作
    """
    
    def __init__(self):
        """初始化資料庫操作類別"""
        self._pool = None  # 將使用全局連接池
    
    async def _get_pool(self):
        """獲取全局連接池實例"""
        if self._pool is None:
            self._pool = await get_global_pool()
        return self._pool
    
    async def init_db(self) -> None:
        """
        初始化資料庫表結構
        """
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(config.ACTIVITY_DB_PATH) as conn:
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS meter(
                  guild_id INTEGER, user_id INTEGER,
                  score REAL DEFAULT 0, last_msg INTEGER DEFAULT 0,
                  PRIMARY KEY(guild_id, user_id)
                );""")
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS daily(
                  ymd TEXT, guild_id INTEGER, user_id INTEGER,
                  msg_cnt INTEGER DEFAULT 0,
                  PRIMARY KEY(ymd, guild_id, user_id)
                );""")
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS report_channel(
                  guild_id INTEGER PRIMARY KEY,
                  channel_id INTEGER
                );""")
                await conn.commit()
            logger.info("【活躍度】資料庫表結構初始化完成")
        except Exception as e:
            logger.error(f"【活躍度】初始化資料庫表結構失敗: {e}")
            raise
    
    async def close(self) -> None:
        """
        關閉資料庫連接（現在由全局連接池管理）
        """
        # 連接池由全局管理器處理，這裡不需要手動關閉
        logger.info("【活躍度】資料庫連接已由全局連接池管理")
    
    async def get_user_activity(self, guild_id: int, user_id: int) -> Tuple[float, int]:
        """
        獲取用戶的活躍度資訊
        
        Args:
            guild_id: 伺服器 ID
            user_id: 用戶 ID
            
        Returns:
            Tuple[float, int]: (活躍度分數, 最後訊息時間戳)
        """
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(config.ACTIVITY_DB_PATH) as conn:
                cursor = await conn.execute(
                    "SELECT score, last_msg FROM meter WHERE guild_id=? AND user_id=?",
                    (guild_id, user_id)
                )
                row = await cursor.fetchone()
                if row:
                    return row[0], row[1]  # score, last_msg
                return 0.0, 0
        except Exception as e:
            logger.error(f"【活躍度】獲取用戶活躍度失敗: {e}")
            return 0.0, 0
    
    async def update_user_activity(self, guild_id: int, user_id: int, score: float, timestamp: int) -> None:
        """
        更新用戶的活躍度資訊
        
        Args:
            guild_id: 伺服器 ID
            user_id: 用戶 ID
            score: 活躍度分數
            timestamp: 時間戳
        """
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(config.ACTIVITY_DB_PATH) as conn:
                await conn.execute(
                    "INSERT INTO meter VALUES(?,?,?,?) ON CONFLICT DO UPDATE SET score=?, last_msg=?",
                    (guild_id, user_id, score, timestamp, score, timestamp)
                )
                await conn.commit()
        except Exception as e:
            logger.error(f"【活躍度】更新用戶活躍度失敗: {e}")
    
    async def increment_daily_message_count(self, ymd: str, guild_id: int, user_id: int) -> None:
        """
        增加用戶的每日訊息計數
        
        Args:
            ymd: 日期字串 (YYYYMMDD)
            guild_id: 伺服器 ID
            user_id: 用戶 ID
        """
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(config.ACTIVITY_DB_PATH) as conn:
                await conn.execute(
                    "INSERT INTO daily VALUES(?,?,?,1) ON CONFLICT DO UPDATE SET msg_cnt = msg_cnt + 1",
                    (ymd, guild_id, user_id)
                )
                await conn.commit()
        except Exception as e:
            logger.error(f"【活躍度】增加每日訊息計數失敗: {e}")
    
    async def get_daily_rankings(self, ymd: str, guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        獲取每日排行榜
        
        Args:
            ymd: 日期字串 (YYYYMMDD)
            guild_id: 伺服器 ID
            limit: 排行榜數量限制
            
        Returns:
            List[Dict[str, Any]]: 排行榜資料列表
        """
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(config.ACTIVITY_DB_PATH) as conn:
                cursor = await conn.execute(
                    "SELECT user_id, msg_cnt FROM daily WHERE ymd=? AND guild_id=? ORDER BY msg_cnt DESC LIMIT ?",
                    (ymd, guild_id, limit)
                )
                rows = await cursor.fetchall()
                return [{"user_id": row[0], "msg_cnt": row[1]} for row in rows]
        except Exception as e:
            logger.error(f"【活躍度】獲取每日排行榜失敗: {e}")
            return []
    
    async def get_monthly_stats(self, ym: str, guild_id: int) -> Dict[int, int]:
        """
        獲取月度統計資料
        
        Args:
            ym: 月份字串 (YYYYMM)
            guild_id: 伺服器 ID
            
        Returns:
            Dict[int, int]: 用戶 ID 到訊息總數的映射
        """
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(config.ACTIVITY_DB_PATH) as conn:
                cursor = await conn.execute(
                    "SELECT user_id, SUM(msg_cnt) as total FROM daily "
                    "WHERE ymd LIKE ? || '%' AND guild_id=? GROUP BY user_id",
                    (ym, guild_id)
                )
                rows = await cursor.fetchall()
                return {row[0]: row[1] for row in rows}  # user_id: total
        except Exception as e:
            logger.error(f"【活躍度】獲取月度統計失敗: {e}")
            return {}
    
    async def set_report_channel(self, guild_id: int, channel_id: int) -> None:
        """
        設定報告頻道
        
        Args:
            guild_id: 伺服器 ID
            channel_id: 頻道 ID
        """
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(config.ACTIVITY_DB_PATH) as conn:
                await conn.execute(
                    "INSERT INTO report_channel VALUES(?,?) ON CONFLICT DO UPDATE SET channel_id=?",
                    (guild_id, channel_id, channel_id)
                )
                await conn.commit()
        except Exception as e:
            logger.error(f"【活躍度】設定報告頻道失敗: {e}")
    
    async def get_report_channels(self) -> List[Tuple[int, int]]:
        """
        獲取所有報告頻道
        
        Returns:
            List[Tuple[int, int]]: (伺服器 ID, 頻道 ID) 的列表
        """
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(config.ACTIVITY_DB_PATH) as conn:
                cursor = await conn.execute("SELECT guild_id, channel_id FROM report_channel")
                rows = await cursor.fetchall()
                return [(row[0], row[1]) for row in rows]  # guild_id, channel_id
        except Exception as e:
            logger.error(f"【活躍度】獲取報告頻道失敗: {e}")
            return [] 