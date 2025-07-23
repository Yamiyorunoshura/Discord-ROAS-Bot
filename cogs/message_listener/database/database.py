"""
訊息監聽系統資料庫操作類別
- 封裝所有與資料庫相關的操作
- 提供統一的資料存取介面
- 使用專業級連接池管理
"""

import aiosqlite
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any, Union

import discord

from ..config.config import MESSAGE_DB_PATH, MESSAGE_RETENTION_DAYS, MAX_SEARCH_RESULTS
from ...core.database_pool import get_global_pool

logger = logging.getLogger("message_listener")

class MessageListenerDB:
    """
    訊息監聽系統資料庫操作類別
    
    功能：
    - 提供非同步資料庫操作
    - 使用專業級連接池管理
    - 完整的錯誤處理
    - 提供所有訊息監聽系統所需的資料庫操作
    """
    
    def __init__(self, db_path: str = MESSAGE_DB_PATH):
        """初始化資料庫操作類別"""
        self.db_path = db_path
        self._pool = None  # 將使用全局連接池
    
    async def _get_pool(self):
        """獲取全局連接池實例"""
        if self._pool is None:
            self._pool = await get_global_pool()
        return self._pool
    
    async def close(self):
        """關閉資料庫連接（現在由全局連接池管理）"""
        # 連接池由全局管理器處理，這裡不需要手動關閉
        logger.info("【訊息監聽】資料庫連接已由全局連接池管理")
    
    async def init_db(self):
        """初始化資料庫結構"""
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        message_id INTEGER PRIMARY KEY,
                        channel_id INTEGER NOT NULL,
                        guild_id INTEGER NOT NULL,
                        author_id INTEGER NOT NULL,
                        content TEXT,
                        timestamp REAL,
                        attachments TEXT,
                        deleted INTEGER DEFAULT 0
                    )
                """)
                
                # 創建索引以提升查詢效能
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON messages (timestamp)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_channel_id ON messages (channel_id)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_guild_id ON messages (guild_id)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_author_id ON messages (author_id)")
                
                # 創建設定表
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        setting_name TEXT PRIMARY KEY,
                        setting_value TEXT
                    )
                """)
                
                # 創建監聽頻道表
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS monitored_channels (
                        channel_id INTEGER PRIMARY KEY
                    )
                """)
                
                await conn.commit()
            logger.info("【訊息監聽】資料庫表格初始化完成")
            
            # 啟動定期清理過期訊息
            asyncio.create_task(self._cleanup_old_messages())
            
        except Exception as exc:
            logger.error(f"【訊息監聽】資料庫初始化失敗: {exc}")
            raise
    
    async def execute(self, query: str, *args):
        """
        執行 SQL 查詢（INSERT、UPDATE、DELETE 等）
        
        Args:
            query: SQL 查詢語句
            *args: 查詢參數
            
        Returns:
            aiosqlite.Cursor: 查詢結果游標
        """
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                cursor = await conn.execute(query, args)
                await conn.commit()
                return cursor
        except Exception as exc:
            logger.error(f"【訊息監聽】執行 SQL 查詢失敗: {exc}")
            raise
    
    async def select(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        執行 SELECT 查詢
        
        Args:
            query: SQL 查詢語句
            params: 查詢參數
            
        Returns:
            List[Dict[str, Any]]: 查詢結果列表
        """
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                cursor = await conn.execute(query, params)
                rows = await cursor.fetchall()
                return [{"message_id": row[0], "channel_id": row[1], "guild_id": row[2], 
                        "author_id": row[3], "content": row[4], "timestamp": row[5], 
                        "attachments": row[6], "deleted": row[7]} for row in rows]
        except Exception as exc:
            logger.error(f"【訊息監聽】執行 SELECT 查詢失敗: {exc}")
            return []
    
    async def save_message(self, message: discord.Message | None):
        """
        儲存訊息到資料庫
        
        Args:
            message: Discord 訊息
        """
        if not message:
            return
            
        try:
            # 準備附件資訊
            attachments_json = None
            if message.attachments:
                attachments_data = []
                for attachment in message.attachments:
                    attachments_data.append({
                        "id": str(attachment.id),
                        "filename": attachment.filename,
                        "url": attachment.url,
                        "size": attachment.size,
                        "content_type": getattr(attachment, "content_type", None)
                    })
                attachments_json = json.dumps(attachments_data)
            
            # 儲存訊息
            await self.execute(
                """
                INSERT OR REPLACE INTO messages 
                (message_id, channel_id, guild_id, author_id, content, timestamp, attachments)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                message.id,
                message.channel.id if message.channel else 0,
                message.guild.id if message.guild else 0,
                message.author.id,
                message.content,
                message.created_at.timestamp(),
                attachments_json
            )
        except Exception as exc:
            logger.error(f"【訊息監聽】儲存訊息失敗: {exc}")
            raise
    
    async def search_messages(
        self, 
        keyword: str | None = None, 
        channel_id: int | None = None,
        hours: int = 24, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        搜尋訊息
        
        Args:
            keyword: 搜尋關鍵字
            channel_id: 頻道 ID
            hours: 搜尋時間範圍（小時）
            limit: 結果數量限制
            
        Returns:
            List[Dict[str, Any]]: 搜尋結果列表
        """
        try:
            # 計算時間範圍
            start_time = (datetime.now() - timedelta(hours=hours)).timestamp()
            
            # 構建查詢條件
            conditions = ["timestamp >= ?", "deleted = 0"]
            params: List[float | int | str] = [start_time]
            
            if keyword:
                conditions.append("content LIKE ?")
                params.append(f"%{keyword}%")
            
            if channel_id:
                conditions.append("channel_id = ?")
                params.append(channel_id)
            
            query = """
                SELECT message_id, channel_id, guild_id, author_id, content, timestamp, attachments, deleted
                FROM messages 
                WHERE {}
                ORDER BY timestamp DESC 
                LIMIT ?
            """.format(' AND '.join(conditions))
            params.append(min(limit, MAX_SEARCH_RESULTS))
            
            return await self.select(query, tuple(params))
            
        except Exception as exc:
            logger.error(f"【訊息監聽】搜尋訊息失敗: {exc}")
            return []
    
    async def purge_old_messages(self, days: int = MESSAGE_RETENTION_DAYS):
        """
        清理過期訊息
        
        Args:
            days: 保留天數
        """
        try:
            cutoff_time = (datetime.now() - timedelta(days=days)).timestamp()
            
            cursor = await self.execute(
                "DELETE FROM messages WHERE timestamp < ?",
                cutoff_time
            )
            
            deleted_count = cursor.rowcount
            logger.info(f"【訊息監聽】清理了 {deleted_count} 條過期訊息")
            
        except Exception as exc:
            logger.error(f"【訊息監聽】清理過期訊息失敗: {exc}")
    
    async def _cleanup_old_messages(self):
        """定期清理過期訊息的背景任務"""
        while True:
            try:
                await asyncio.sleep(86400)  # 每天執行一次
                await self.purge_old_messages()
            except Exception as exc:
                logger.error(f"【訊息監聽】定期清理任務失敗: {exc}")
    
    async def get_setting(self, key: str, default: str = "") -> str:
        """
        獲取設定值
        
        Args:
            key: 設定鍵
            default: 預設值
            
        Returns:
            str: 設定值
        """
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                cursor = await conn.execute(
                    "SELECT setting_value FROM settings WHERE setting_name = ?",
                    (key,)
                )
                row = await cursor.fetchone()
                return row[0] if row else default
        except Exception as exc:
            logger.error(f"【訊息監聽】獲取設定失敗: {exc}")
            return default
    
    async def set_setting(self, key: str, value: str):
        """
        設定設定值
        
        Args:
            key: 設定鍵
            value: 設定值
        """
        try:
            await self.execute(
                "INSERT OR REPLACE INTO settings (setting_name, setting_value) VALUES (?, ?)",
                key, value
            )
        except Exception as exc:
            logger.error(f"【訊息監聽】設定設定值失敗: {exc}")
    
    async def get_monitored_channels(self) -> List[int]:
        """
        獲取監聽的頻道列表
        
        Returns:
            List[int]: 頻道 ID 列表
        """
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                cursor = await conn.execute("SELECT channel_id FROM monitored_channels")
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
        except Exception as exc:
            logger.error(f"【訊息監聽】獲取監聽頻道失敗: {exc}")
            return []
    
    async def add_monitored_channel(self, channel_id: int):
        """
        添加監聽頻道
        
        Args:
            channel_id: 頻道 ID
        """
        try:
            await self.execute(
                "INSERT OR IGNORE INTO monitored_channels (channel_id) VALUES (?)",
                channel_id
            )
        except Exception as exc:
            logger.error(f"【訊息監聽】添加監聽頻道失敗: {exc}")
    
    async def remove_monitored_channel(self, channel_id: int):
        """
        移除監聽頻道
        
        Args:
            channel_id: 頻道 ID
        """
        try:
            await self.execute(
                "DELETE FROM monitored_channels WHERE channel_id = ?",
                channel_id
            )
        except Exception as exc:
            logger.error(f"【訊息監聽】移除監聽頻道失敗: {exc}")
    
    async def clear_monitored_channels(self):
        """清空所有監聽頻道"""
        try:
            await self.execute("DELETE FROM monitored_channels")
        except Exception as exc:
            logger.error(f"【訊息監聽】清空監聽頻道失敗: {exc}") 