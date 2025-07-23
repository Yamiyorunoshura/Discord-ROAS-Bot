"""
資料同步模組資料庫操作
- 封裝同步相關的資料庫操作
- 提供角色和頻道資料的存取介面
- 使用專業級連接池管理
"""

import asyncio
import logging
import aiosqlite
import os
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

import discord

from ...core.database_pool import get_global_pool

logger = logging.getLogger("sync_data")

# 資料庫路徑配置
PROJECT_ROOT = os.environ.get(
    "PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)
DBS_DIR = os.path.join(PROJECT_ROOT, "dbs")
os.makedirs(DBS_DIR, exist_ok=True)

class SyncDataDatabase:
    """
    資料同步模組資料庫操作類
    
    功能：
    - 角色資料同步
    - 頻道資料同步
    - 同步記錄管理
    - 資料驗證和清理
    - 使用專業級連接池管理
    """
    
    def __init__(self, bot):
        """
        初始化資料庫操作類
        
        Args:
            bot: Discord 機器人實例
        """
        self.bot = bot
        self.db_path = os.path.join(DBS_DIR, "sync_data.db")
        self._pool = None  # 將使用全局連接池
    
    async def _get_pool(self):
        """獲取全局連接池實例"""
        if self._pool is None:
            self._pool = await get_global_pool()
        return self._pool
    
    async def init_db(self):
        """初始化資料庫表格"""
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                # 創建角色表
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS roles (
                        role_id INTEGER PRIMARY KEY,
                        guild_id INTEGER,
                        name TEXT,
                        color TEXT,
                        permissions INTEGER,
                        position INTEGER,
                        mentionable INTEGER,
                        hoist INTEGER,
                        managed INTEGER
                    )
                """)
                
                # 創建頻道表
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS channels (
                        channel_id INTEGER PRIMARY KEY,
                        guild_id INTEGER,
                        name TEXT,
                        type TEXT,
                        topic TEXT,
                        position INTEGER,
                        category_id INTEGER
                    )
                """)
                
                # 創建同步記錄表
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS sync_data_log(
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER,
                        sync_type TEXT,
                        status TEXT,
                        roles_affected INTEGER DEFAULT 0,
                        channels_affected INTEGER DEFAULT 0,
                        error_message TEXT,
                        start_time TIMESTAMP,
                        end_time TIMESTAMP,
                        duration REAL
                    )
                """)
                
                await conn.commit()
            logger.info("【資料同步】資料庫初始化完成")
            
        except Exception as exc:
            logger.error(f"【資料同步】資料庫初始化失敗: {exc}")
            raise
    
    async def close(self):
        """關閉資料庫連接（現在由全局連接池管理）"""
        # 連接池由全局管理器處理，這裡不需要手動關閉
        logger.info("【資料同步】資料庫連接已由全局連接池管理")
    
    async def execute(self, query: str, params: tuple = ()):
        """
        執行 SQL 指令
        
        Args:
            query: SQL 查詢語句
            params: 參數
        """
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                await conn.execute(query, params)
                await conn.commit()
        except Exception as exc:
            logger.error(f"【資料同步】執行 SQL 指令失敗：{exc}")
            raise
    
    async def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """
        查詢單筆資料
        
        Args:
            query: SQL 查詢語句
            params: 參數
            
        Returns:
            Optional[Dict[str, Any]]: 查詢結果
        """
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                cursor = await conn.execute(query, params)
                row = await cursor.fetchone()
                if row:
                    return dict(zip([desc[0] for desc in cursor.description], row))
                return None
        except Exception as exc:
            logger.error(f"【資料同步】查詢單筆資料失敗：{exc}")
            return None
    
    async def fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        查詢多筆資料
        
        Args:
            query: SQL 查詢語句
            params: 參數
            
        Returns:
            List[Dict[str, Any]]: 查詢結果列表
        """
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                cursor = await conn.execute(query, params)
                rows = await cursor.fetchall()
                if rows:
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
                return []
        except Exception as exc:
            logger.error(f"【資料同步】查詢多筆資料失敗：{exc}")
            return []
    
    async def fetchval(self, query: str, params: tuple = ()) -> Optional[Any]:
        """
        查詢單個值
        
        Args:
            query: SQL 查詢語句
            params: 參數
            
        Returns:
            Optional[Any]: 查詢結果
        """
        try:
            pool = await self._get_pool()
            async with pool.get_connection_context(self.db_path) as conn:
                cursor = await conn.execute(query, params)
                row = await cursor.fetchone()
                return row[0] if row else None
        except Exception as exc:
            logger.error(f"【資料同步】查詢單個值失敗：{exc}")
            return None
    
    async def get_guild_roles(self, guild_id: int) -> List[Dict[str, Any]]:
        """
        獲取伺服器角色資料
        
        Args:
            guild_id: 伺服器 ID
            
        Returns:
            List[Dict[str, Any]]: 角色資料列表
        """
        try:
            return await self.fetchall(
                "SELECT * FROM roles WHERE guild_id = ? ORDER BY position ASC",
                (guild_id,)
            )
        except Exception as exc:
            logger.error(f"【資料同步】獲取伺服器角色失敗：{exc}")
            return []
    
    async def insert_or_replace_role(self, role: discord.Role):
        """
        插入或更新角色資料
        
        Args:
            role: Discord 角色物件
        """
        try:
            await self.execute(
                """
                INSERT OR REPLACE INTO roles 
                (role_id, guild_id, name, color, permissions, position, mentionable, hoist, managed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    role.id,
                    role.guild.id,
                    role.name,
                    str(role.color),
                    role.permissions.value,
                    role.position,
                    int(role.mentionable),
                    int(role.hoist),
                    int(role.managed)
                )
            )
        except Exception as exc:
            logger.error(f"【資料同步】插入角色資料失敗：{exc}")
            raise
    
    async def delete_role(self, role_id: int):
        """
        刪除角色資料
        
        Args:
            role_id: 角色 ID
        """
        try:
            await self.execute("DELETE FROM roles WHERE role_id = ?", (role_id,))
        except Exception as exc:
            logger.error(f"【資料同步】刪除角色資料失敗：{exc}")
            raise
    
    async def get_guild_channels(self, guild_id: int) -> List[Dict[str, Any]]:
        """
        獲取伺服器頻道資料
        
        Args:
            guild_id: 伺服器 ID
            
        Returns:
            List[Dict[str, Any]]: 頻道資料列表
        """
        try:
            return await self.fetchall(
                "SELECT * FROM channels WHERE guild_id = ? ORDER BY position",
                (guild_id,)
            )
        except Exception as exc:
            logger.error(f"【資料同步】獲取伺服器頻道失敗：{exc}")
            return []
    
    async def insert_or_replace_channel(self, channel: discord.abc.GuildChannel):
        """
        插入或更新頻道資料
        
        Args:
            channel: Discord 頻道物件
        """
        try:
            await self.execute(
                """
                INSERT OR REPLACE INTO channels 
                (channel_id, guild_id, name, type, topic, position, category_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    channel.id,
                    channel.guild.id,
                    channel.name,
                    str(channel.type),
                    getattr(channel, 'topic', None),
                    channel.position,
                    channel.category_id if hasattr(channel, 'category_id') else None
                )
            )
        except Exception as exc:
            logger.error(f"【資料同步】插入頻道資料失敗：{exc}")
            raise
    
    async def delete_channel(self, channel_id: int):
        """
        刪除頻道資料
        
        Args:
            channel_id: 頻道 ID
        """
        try:
            await self.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        except Exception as exc:
            logger.error(f"【資料同步】刪除頻道資料失敗：{exc}")
            raise
    
    async def log_sync_result(self, guild_id: int, sync_type: str, status: str, 
                             roles_affected: int = 0, channels_affected: int = 0,
                             error_message: str = "", start_time: Optional[datetime] = None,
                             end_time: Optional[datetime] = None, duration: float = 0.0):
        """
        記錄同步結果
        
        Args:
            guild_id: 伺服器 ID
            sync_type: 同步類型
            status: 同步狀態
            roles_affected: 影響的角色數量
            channels_affected: 影響的頻道數量
            error_message: 錯誤訊息
            start_time: 開始時間
            end_time: 結束時間
            duration: 持續時間
        """
        try:
            await self.execute(
                """
                INSERT INTO sync_data_log 
                (guild_id, sync_type, status, roles_affected, channels_affected, 
                 error_message, start_time, end_time, duration)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    sync_type,
                    status,
                    roles_affected,
                    channels_affected,
                    error_message,
                    start_time,
                    end_time,
                    duration
                )
            )
        except Exception as exc:
            logger.error(f"【資料同步】記錄同步結果失敗：{exc}")
            raise
    
    async def get_sync_history(self, guild_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        獲取同步歷史記錄
        
        Args:
            guild_id: 伺服器 ID
            limit: 限制筆數
            
        Returns:
            List[Dict[str, Any]]: 同步歷史記錄列表
        """
        try:
            return await self.fetchall(
                """
                SELECT * FROM sync_data_log 
                WHERE guild_id = ? 
                ORDER BY start_time DESC 
                LIMIT ?
                """,
                (guild_id, limit)
            )
        except Exception as exc:
            logger.error(f"【資料同步】獲取同步歷史失敗：{exc}")
            return []
    
    async def cleanup_old_logs(self, days: int = 30):
        """
        清理舊的同步記錄
        
        Args:
            days: 保留天數
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            await self.execute(
                "DELETE FROM sync_data_log WHERE start_time < ?",
                (cutoff_date,)
            )
        except Exception as exc:
            logger.error(f"【資料同步】清理舊記錄失敗：{exc}")
            raise
    
    async def validate_data_integrity(self, guild_id: int) -> Dict[str, Any]:
        """
        驗證資料完整性
        
        Args:
            guild_id: 伺服器 ID
            
        Returns:
            Dict[str, Any]: 驗證結果
        """
        try:
            result = {
                "guild_id": guild_id,
                "roles_count": 0,
                "channels_count": 0,
                "last_sync": None,
                "integrity_check": True
            }
            
            # 統計角色數量
            result["roles_count"] = await self.fetchval(
                "SELECT COUNT(*) FROM roles WHERE guild_id = ?",
                (guild_id,)
            ) or 0
            
            # 統計頻道數量
            result["channels_count"] = await self.fetchval(
                "SELECT COUNT(*) FROM channels WHERE guild_id = ?",
                (guild_id,)
            ) or 0
            
            # 獲取最後同步時間
            last_sync = await self.fetchone(
                "SELECT start_time FROM sync_data_log WHERE guild_id = ? ORDER BY start_time DESC LIMIT 1",
                (guild_id,)
            )
            if last_sync:
                result["last_sync"] = last_sync.get("start_time")
            
            return result
            
        except Exception as exc:
            logger.error(f"【資料同步】驗證資料完整性失敗：{exc}")
            return {
                "guild_id": guild_id,
                "roles_count": 0,
                "channels_count": 0,
                "last_sync": None,
                "integrity_check": False,
                "error": str(exc)
            }
            
    async def get_last_sync_record(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """
        獲取最後一次同步記錄
        
        Args:
            guild_id: 伺服器 ID
            
        Returns:
            Optional[Dict[str, Any]]: 最後同步記錄，如果沒有則返回 None
        """
        try:
            records = await self.fetchall(
                """
                SELECT * FROM sync_data_log 
                WHERE guild_id = ? 
                ORDER BY start_time DESC 
                LIMIT 1
                """,
                (guild_id,)
            )
            return records[0] if records else None
        except Exception as exc:
            logger.error(f"【資料同步】獲取最後同步記錄失敗：{exc}")
            return None
