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
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any, Union

from ..config import config
from ...core.database_pool import get_global_pool

logger = logging.getLogger("activity_meter")

# Phase 3: 錯誤處理體系
class ActivityMeterError(Exception):
    """活躍度系統錯誤基類（底層專用）"""
    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(f"[{error_code}] {message}")

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
        self._settings_cache = {}
        self._cache_time = {}
    
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
            raise ActivityMeterError("E101", f"資料庫初始化失敗: {e}")
    
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
            raise ActivityMeterError("E102", f"查詢用戶活躍度失敗: {e}")
    
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
            raise ActivityMeterError("E102", f"更新用戶活躍度失敗: {e}")
    
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
            raise ActivityMeterError("E102", f"每日訊息計數失敗: {e}")
    
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
            raise ActivityMeterError("E102", f"查詢每日排行榜失敗: {e}")
    
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
            raise ActivityMeterError("E102", f"查詢月度統計失敗: {e}")
    
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
            raise ActivityMeterError("E102", f"設定報告頻道失敗: {e}")
    
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
            raise ActivityMeterError("E102", f"查詢報告頻道失敗: {e}")
    
    # PRD v1.71 新增方法
    async def get_monthly_top_users(self, limit: int = 3) -> List[Tuple[int, float, int]]:
        """獲取過去一個月平均活躍度最高的用戶"""
        try:
            # 計算過去一個月的時間範圍
            now = datetime.now()
            month_ago = now - timedelta(days=30)
            
            pool = await self._get_pool()
            async with pool.get_connection_context(config.ACTIVITY_DB_PATH) as conn:
                cursor = await conn.execute("""
                SELECT user_id, AVG(score) as avg_score, COUNT(*) as message_count
                FROM meter
                WHERE last_msg >= ?
                GROUP BY user_id
                HAVING COUNT(*) >= 1
                ORDER BY avg_score DESC
                LIMIT ?
                """, (int(month_ago.timestamp()), limit))
                results = await cursor.fetchall()
                
            return [(user_id, avg_score, message_count) for user_id, avg_score, message_count in results]
            
        except Exception as e:
            logger.error(f"【活躍度】獲取月度排行榜失敗: {e}")
            raise ActivityMeterError("E102", f"查詢月度排行榜失敗: {e}")
    
    async def get_monthly_message_count(self) -> int:
        """獲取本月訊息總量"""
        try:
            now = datetime.now()
            start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            pool = await self._get_pool()
            async with pool.get_connection_context(config.ACTIVITY_DB_PATH) as conn:
                cursor = await conn.execute("""
                SELECT COUNT(*) as message_count
                FROM meter
                WHERE last_msg >= ?
                """, (int(start_of_month.timestamp()),))
                result = await cursor.fetchone()
                
            return result[0] if result else 0
            
        except Exception as e:
            logger.error(f"【活躍度】獲取本月訊息總量失敗: {e}")
            raise ActivityMeterError("E102", f"查詢本月訊息總量失敗: {e}")
    
    async def get_last_month_message_count(self) -> int:
        """獲取上個月訊息總量"""
        try:
            now = datetime.now()
            start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            start_of_last_month = (start_of_month - timedelta(days=1)).replace(day=1)
            
            pool = await self._get_pool()
            async with pool.get_connection_context(config.ACTIVITY_DB_PATH) as conn:
                cursor = await conn.execute("""
                SELECT COUNT(*) as message_count
                FROM meter
                WHERE last_msg >= ? AND last_msg < ?
                """, (int(start_of_last_month.timestamp()), int(start_of_month.timestamp())))
                result = await cursor.fetchone()
                
            return result[0] if result else 0
            
        except Exception as e:
            logger.error(f"【活躍度】獲取上個月訊息總量失敗: {e}")
            raise ActivityMeterError("E102", f"查詢上個月訊息總量失敗: {e}")
    
    async def save_progress_style(self, guild_id: int, style: str) -> None:
        """保存進度條風格設定"""
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(config.ACTIVITY_DB_PATH) as conn:
                # 確保設定表存在
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS activity_meter_settings (
                    guild_id INTEGER PRIMARY KEY,
                    progress_style TEXT DEFAULT 'classic',
                    announcement_channel INTEGER,
                    announcement_time INTEGER DEFAULT 21
                )
                """)
                
                await conn.execute("""
                INSERT INTO activity_meter_settings (guild_id, progress_style)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET progress_style = ?
                """, (guild_id, style, style))
                await conn.commit()
                
        except Exception as e:
            logger.error(f"【活躍度】保存進度條風格失敗: {e}")
            raise ActivityMeterError("E402", f"保存進度條風格失敗: {e}")
    
    async def save_announcement_time(self, guild_id: int, hour: int) -> None:
        """保存公告時間設定"""
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(config.ACTIVITY_DB_PATH) as conn:
                # 確保設定表存在
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS activity_meter_settings (
                    guild_id INTEGER PRIMARY KEY,
                    progress_style TEXT DEFAULT 'classic',
                    announcement_channel INTEGER,
                    announcement_time INTEGER DEFAULT 21
                )
                """)
                
                await conn.execute("""
                INSERT INTO activity_meter_settings (guild_id, announcement_time)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET announcement_time = ?
                """, (guild_id, hour, hour))
                await conn.commit()
                
        except Exception as e:
            logger.error(f"【活躍度】保存公告時間失敗: {e}")
            raise ActivityMeterError("E402", f"保存公告時間失敗: {e}")
    
    async def load_settings(self, guild_id: int) -> dict:
        """從數據庫載入設定"""
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(config.ACTIVITY_DB_PATH) as conn:
                # 確保設定表存在
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS activity_meter_settings (
                    guild_id INTEGER PRIMARY KEY,
                    progress_style TEXT DEFAULT 'classic',
                    announcement_channel INTEGER,
                    announcement_time INTEGER DEFAULT 21
                )
                """)
                
                cursor = await conn.execute("""
                SELECT progress_style, announcement_channel, announcement_time
                FROM activity_meter_settings
                WHERE guild_id = ?
                """, (guild_id,))
                result = await cursor.fetchone()
                
            if result:
                return {
                    'progress_style': result[0],
                    'announcement_channel': result[1],
                    'announcement_time': result[2]
                }
            else:
                return {
                    'progress_style': 'classic',
                    'announcement_channel': None,
                    'announcement_time': 21
                }
                
        except Exception as e:
            logger.error(f"【活躍度】載入設定失敗: {e}")
            raise ActivityMeterError("E401", f"載入設定失敗: {e}")
    
    async def get_progress_style(self, guild_id: int) -> str:
        """獲取進度條風格設定"""
        try:
            settings = await self.load_settings(guild_id)
            return settings.get('progress_style', 'classic')
        except Exception as e:
            logger.error(f"【活躍度】獲取進度條風格失敗: {e}")
            raise ActivityMeterError("E401", f"獲取進度條風格失敗: {e}")
    
    async def save_all_settings(self, guild_id: int, progress_style: str, announcement_channel: int = None, announcement_time: int = 21) -> None:
        """一次性保存所有設定"""
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(config.ACTIVITY_DB_PATH) as conn:
                # 確保設定表存在
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS activity_meter_settings (
                    guild_id INTEGER PRIMARY KEY,
                    progress_style TEXT DEFAULT 'classic',
                    announcement_channel INTEGER,
                    announcement_time INTEGER DEFAULT 21
                )
                """)
                
                await conn.execute("""
                INSERT INTO activity_meter_settings (guild_id, progress_style, announcement_channel, announcement_time)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                progress_style = excluded.progress_style,
                announcement_channel = excluded.announcement_channel,
                announcement_time = excluded.announcement_time
                """, (guild_id, progress_style, announcement_channel, announcement_time))
                await conn.commit()
                
        except Exception as e:
            logger.error(f"【活躍度】保存所有設定失敗: {e}")
            raise ActivityMeterError("E402", f"保存所有設定失敗: {e}")
    
    async def refresh_settings_cache(self):
        """刷新設定緩存"""
        self._settings_cache = {}
        self._cache_time = {}
        logger.info("【活躍度】設定緩存已刷新")
    
    async def get_latest_settings(self, guild_id: int) -> dict:
        """獲取最新設定（強制刷新）"""
        cache_key = f"settings_{guild_id}"
        current_time = time.time()
        
        # 檢查緩存是否過期
        if (cache_key not in self._cache_time or 
            current_time - self._cache_time[cache_key] > 30):  # 30秒過期
            # 強制從數據庫重新載入
            settings = await self._load_settings_from_db(guild_id)
            self._settings_cache[cache_key] = settings
            self._cache_time[cache_key] = current_time
            logger.info(f"【活躍度】已重新載入 guild {guild_id} 的設定")
        
        return self._settings_cache[cache_key]
    
    async def _load_settings_from_db(self, guild_id: int) -> dict:
        """從數據庫載入設定"""
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(config.ACTIVITY_DB_PATH) as conn:
                # 確保設定表存在
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS activity_meter_settings (
                    guild_id INTEGER PRIMARY KEY,
                    progress_style TEXT DEFAULT 'classic',
                    announcement_channel INTEGER,
                    announcement_time INTEGER DEFAULT 21
                )
                """)
                
                cursor = await conn.execute("""
                SELECT progress_style, announcement_channel, announcement_time
                FROM activity_meter_settings
                WHERE guild_id = ?
                """, (guild_id,))
                result = await cursor.fetchone()
                
            if result:
                return {
                    'progress_style': result[0],
                    'announcement_channel': result[1],
                    'announcement_time': result[2]
                }
            else:
                return {
                    'progress_style': 'classic',
                    'announcement_channel': None,
                    'announcement_time': 21
                }
                
        except Exception as e:
            logger.error(f"【活躍度】從數據庫載入設定失敗: {e}")
            raise ActivityMeterError("E401", f"從數據庫載入設定失敗: {e}")
    
    async def save_announcement_channel(self, guild_id: int, channel_id: int) -> None:
        """保存公告頻道設定"""
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(config.ACTIVITY_DB_PATH) as conn:
                # 確保設定表存在
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS activity_meter_settings (
                    guild_id INTEGER PRIMARY KEY,
                    progress_style TEXT DEFAULT 'classic',
                    announcement_channel INTEGER,
                    announcement_time INTEGER DEFAULT 21
                )
                """)
                
                await conn.execute("""
                INSERT INTO activity_meter_settings (guild_id, announcement_channel)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET announcement_channel = ?
                """, (guild_id, channel_id, channel_id))
                await conn.commit()
                
                # 刷新緩存
                await self.refresh_settings_cache()
                
        except Exception as e:
            logger.error(f"【活躍度】保存公告頻道失敗: {e}")
            raise ActivityMeterError("E402", f"保存公告頻道失敗: {e}")
    
    async def get_announcement_time(self, guild_id: int) -> str:
        """
        獲取公告時間設定
        
        Args:
            guild_id: 伺服器ID
            
        Returns:
            str: 時間字符串 (HH:MM格式)
            
        Raises:
            ActivityMeterError: 數據庫查詢失敗時拋出
        """
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(config.ACTIVITY_DB_PATH) as conn:
                # 確保設定表存在
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS activity_meter_settings (
                    guild_id INTEGER PRIMARY KEY,
                    progress_style TEXT DEFAULT 'classic',
                    announcement_channel INTEGER,
                    announcement_time INTEGER DEFAULT 21
                )
                """)
                
                cursor = await conn.execute("""
                SELECT announcement_time 
                FROM activity_meter_settings 
                WHERE guild_id = ?
                """, (guild_id,))
                result = await cursor.fetchone()
                
                if result:
                    # 將小時轉換為HH:MM格式
                    hour = result[0]
                    return f"{hour:02d}:00"
                else:
                    # 返回預設時間
                    return "09:00"
                    
        except Exception as e:
            logger.error(f"【活躍度】獲取公告時間失敗: {e}")
            raise ActivityMeterError("E102", f"獲取公告時間失敗: {e}")
    
    async def update_announcement_time(self, guild_id: int, time_str: str) -> None:
        """
        更新公告時間設定
        
        Args:
            guild_id: 伺服器ID
            time_str: 時間字符串 (HH:MM格式)
            
        Raises:
            ActivityMeterError: 數據庫更新失敗時拋出
        """
        try:
            # 驗證時間格式
            if not self._validate_time_format(time_str):
                raise ValueError("時間格式錯誤，請使用 HH:MM 格式")
            
            # 解析時間
            hour = int(time_str.split(':')[0])
            
            pool = await self._get_pool()
            async with pool.get_connection_context(config.ACTIVITY_DB_PATH) as conn:
                # 確保設定表存在
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS activity_meter_settings (
                    guild_id INTEGER PRIMARY KEY,
                    progress_style TEXT DEFAULT 'classic',
                    announcement_channel INTEGER,
                    announcement_time INTEGER DEFAULT 21
                )
                """)
                
                await conn.execute("""
                INSERT INTO activity_meter_settings (guild_id, announcement_time)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET announcement_time = ?
                """, (guild_id, hour, hour))
                await conn.commit()
                
                # 刷新緩存
                await self.refresh_settings_cache()
                
        except Exception as e:
            logger.error(f"【活躍度】更新公告時間失敗: {e}")
            raise ActivityMeterError("E102", f"更新公告時間失敗: {e}")
    
    def _validate_time_format(self, time_str: str) -> bool:
        """
        驗證時間格式
        
        Args:
            time_str: 時間字符串
            
        Returns:
            bool: 格式是否正確
        """
        import re
        # 檢查格式
        pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
        if not re.match(pattern, time_str):
            return False
        
        # 解析時間
        try:
            hour, minute = map(int, time_str.split(':'))
            return 0 <= hour <= 23 and 0 <= minute <= 59
        except:
            return False 