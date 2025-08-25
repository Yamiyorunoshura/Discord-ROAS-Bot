"""
訊息監聽服務
Task ID: 9 - 重構現有模組以符合新架構

提供訊息監聽系統的核心業務邏輯：
- 訊息記錄和儲存
- 訊息搜尋和查詢
- 監聽頻道管理
- 設定管理
"""

import asyncio
import logging
import aiosqlite
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from collections import defaultdict
from contextlib import asynccontextmanager

from core.base_service import BaseService
from core.database_manager import DatabaseManager
from core.exceptions import ServiceError, handle_errors
from .models import MessageRecord, MessageCacheItem, MonitorSettings, SearchQuery, SearchResult, RenderConfig

logger = logging.getLogger('services.message')


class MessageService(BaseService):
    """
    訊息監聽服務
    
    負責處理訊息監聽的所有業務邏輯
    """
    
    def __init__(self, database_manager: DatabaseManager, config: Optional[Dict[str, Any]] = None):
        """
        初始化訊息服務
        
        參數：
            database_manager: 資料庫管理器
            config: 配置參數
        """
        super().__init__("MessageService")
        self.db_manager = database_manager
        self.config = config or {}
        
        # 快取和設定
        self._settings_cache: Dict[str, str] = {}
        self._last_settings_refresh = 0
        self._monitored_channels: List[int] = []
        self._last_channels_refresh = 0
        self._cache_lock = asyncio.Lock()
        
        # 訊息快取（用於批次處理）
        self._message_cache: Dict[int, List[MessageCacheItem]] = defaultdict(list)
        self._cache_timers: Dict[int, asyncio.Task] = {}
        
        # 渲染配置
        self.render_config = RenderConfig(**self.config.get('render', {}))
        
        # 添加資料庫依賴
        self.add_dependency(database_manager, "database")
    
    async def _initialize(self) -> bool:
        """初始化服務"""
        try:
            # 初始化訊息相關資料表
            await self._init_database_tables()
            
            # 載入設定和監聽頻道
            await self.refresh_settings()
            await self.refresh_monitored_channels()
            
            logger.info("訊息服務初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"訊息服務初始化失敗：{e}")
            return False
    
    async def _cleanup(self) -> None:
        """清理資源"""
        try:
            # 取消所有快取定時器
            for timer in self._cache_timers.values():
                if not timer.cancelled():
                    timer.cancel()
            self._cache_timers.clear()
            
            # 處理剩餘的快取訊息
            await self._process_all_cached_messages()
            
            # 清除快取
            async with self._cache_lock:
                self._message_cache.clear()
                self._settings_cache.clear()
                self._monitored_channels.clear()
            
            logger.info("訊息服務已清理")
            
        except Exception as e:
            logger.error(f"清理訊息服務時發生錯誤：{e}")
    
    async def _validate_permissions(self, user_id: int, guild_id: Optional[int], action: str) -> bool:
        """
        訊息服務權限驗證
        
        實作基本的權限邏輯
        """
        # 根據需要實作更複雜的權限邏輯
        return True
    
    async def _init_database_tables(self) -> None:
        """初始化訊息相關的資料表"""
        # 設定表
        await self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS message_settings (
                setting_name TEXT PRIMARY KEY,
                setting_value TEXT
            )
        """)
        
        # 監聽頻道表
        await self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS monitored_channels (
                channel_id INTEGER PRIMARY KEY
            )
        """)
        
        # 訊息記錄表（使用訊息資料庫）
        await self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                content TEXT,
                timestamp REAL,
                attachments TEXT
            )
        """, db_type="message")
        
        # 建立索引以提升查詢效能
        await self.db_manager.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_channel 
            ON messages(channel_id)
        """, db_type="message")
        
        await self.db_manager.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp 
            ON messages(timestamp)
        """, db_type="message")
    
    @handle_errors(log_errors=True)
    async def get_settings(self) -> MonitorSettings:
        """
        獲取監聽設定
        
        返回：
            監聽設定物件
        """
        try:
            await self.refresh_settings()
            
            settings = MonitorSettings(
                enabled=self._settings_cache.get("enabled", "true").lower() == "true",
                log_channel_id=int(self._settings_cache.get("log_channel_id", "0")) or None,
                monitored_channels=self._monitored_channels.copy(),
                record_edits=self._settings_cache.get("record_edits", "true").lower() == "true",
                record_deletes=self._settings_cache.get("record_deletes", "true").lower() == "true",
                retention_days=int(self._settings_cache.get("retention_days", "7")),
                render_mode=self._settings_cache.get("render_mode", "batch")
            )
            
            return settings
            
        except Exception as e:
            logger.error(f"獲取監聽設定失敗：{e}")
            raise ServiceError(
                f"獲取監聽設定失敗：{str(e)}",
                service_name=self.name,
                operation="get_settings"
            )
    
    @handle_errors(log_errors=True)
    async def update_setting(self, key: str, value: str) -> bool:
        """
        更新單一設定
        
        參數：
            key: 設定鍵
            value: 設定值
            
        返回：
            是否更新成功
        """
        try:
            await self.db_manager.execute(
                "INSERT OR REPLACE INTO message_settings (setting_name, setting_value) VALUES (?, ?)",
                (key, value)
            )
            
            # 更新快取
            self._settings_cache[key] = value
            
            # 如果更新了監聽相關設定，重新載入
            if key in ["enabled", "log_channel_id", "record_edits", "record_deletes", "retention_days", "render_mode"]:
                await self.refresh_settings()
            
            logger.info(f"更新訊息設定成功：{key} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"更新訊息設定失敗：{e}")
            raise ServiceError(
                f"更新訊息設定失敗：{str(e)}",
                service_name=self.name,
                operation="update_setting"
            )
    
    @handle_errors(log_errors=True)
    async def add_monitored_channel(self, channel_id: int) -> bool:
        """
        添加監聽頻道
        
        參數：
            channel_id: 頻道 ID
            
        返回：
            是否添加成功
        """
        try:
            await self.db_manager.execute(
                "INSERT OR IGNORE INTO monitored_channels (channel_id) VALUES (?)",
                (channel_id,)
            )
            
            # 更新快取
            if channel_id not in self._monitored_channels:
                self._monitored_channels.append(channel_id)
            
            logger.info(f"添加監聽頻道成功：{channel_id}")
            return True
            
        except Exception as e:
            logger.error(f"添加監聽頻道失敗：{e}")
            raise ServiceError(
                f"添加監聽頻道失敗：{str(e)}",
                service_name=self.name,
                operation="add_monitored_channel"
            )
    
    @handle_errors(log_errors=True)
    async def remove_monitored_channel(self, channel_id: int) -> bool:
        """
        移除監聽頻道
        
        參數：
            channel_id: 頻道 ID
            
        返回：
            是否移除成功
        """
        try:
            await self.db_manager.execute(
                "DELETE FROM monitored_channels WHERE channel_id = ?",
                (channel_id,)
            )
            
            # 更新快取
            if channel_id in self._monitored_channels:
                self._monitored_channels.remove(channel_id)
            
            logger.info(f"移除監聽頻道成功：{channel_id}")
            return True
            
        except Exception as e:
            logger.error(f"移除監聽頻道失敗：{e}")
            raise ServiceError(
                f"移除監聽頻道失敗：{str(e)}",
                service_name=self.name,
                operation="remove_monitored_channel"
            )
    
    @handle_errors(log_errors=True)
    async def save_message(self, message) -> bool:
        """
        儲存訊息記錄
        
        參數：
            message: Discord 訊息物件
            
        返回：
            是否儲存成功
        """
        try:
            # 檢查是否需要監聽此頻道
            if message.channel.id not in self._monitored_channels:
                return False
            
            # 建立訊息記錄
            record = MessageRecord.from_discord_message(message)
            
            # 儲存到資料庫
            await self.db_manager.execute("""
                INSERT OR REPLACE INTO messages 
                (message_id, channel_id, guild_id, author_id, content, timestamp, attachments)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                record.message_id,
                record.channel_id,
                record.guild_id,
                record.author_id,
                record.content,
                record.timestamp,
                record.attachments
            ), db_type="message")
            
            # 添加到快取以進行批次處理
            await self._add_to_cache(message)
            
            logger.debug(f"儲存訊息成功：{message.id}")
            return True
            
        except Exception as e:
            logger.error(f"儲存訊息失敗：{e}")
            return False
    
    @handle_errors(log_errors=True)
    async def search_messages(self, query: SearchQuery) -> SearchResult:
        """
        搜尋訊息
        
        參數：
            query: 搜尋查詢參數
            
        返回：
            搜尋結果
        """
        try:
            # 建構 SQL 查詢
            conditions = []
            params = []
            
            if query.keyword:
                conditions.append("content LIKE ?")
                params.append(f"%{query.keyword}%")
            
            if query.channel_id:
                conditions.append("channel_id = ?")
                params.append(query.channel_id)
            
            if query.author_id:
                conditions.append("author_id = ?")
                params.append(query.author_id)
            
            if query.guild_id:
                conditions.append("guild_id = ?")
                params.append(query.guild_id)
            
            if query.start_time:
                conditions.append("timestamp >= ?")
                params.append(query.start_time.timestamp())
            
            if query.end_time:
                conditions.append("timestamp <= ?")
                params.append(query.end_time.timestamp())
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            # 查詢總數
            count_sql = f"SELECT COUNT(*) as total FROM messages {where_clause}"
            count_result = await self.db_manager.fetchone(count_sql, tuple(params), db_type="message")
            total_count = count_result['total'] if count_result else 0
            
            # 查詢記錄
            sql = f"""
                SELECT * FROM messages {where_clause}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """
            params.extend([query.limit, query.offset])
            
            rows = await self.db_manager.fetchall(sql, tuple(params), db_type="message")
            
            # 轉換為 MessageRecord
            records = []
            for row in rows:
                record = MessageRecord(
                    message_id=row['message_id'],
                    channel_id=row['channel_id'],
                    guild_id=row['guild_id'],
                    author_id=row['author_id'],
                    content=row['content'],
                    timestamp=row['timestamp'],
                    attachments=row['attachments']
                )
                records.append(record)
            
            # 建構結果
            result = SearchResult(
                records=records,
                total_count=total_count,
                has_more=(query.offset + len(records)) < total_count,
                query=query
            )
            
            logger.info(f"搜尋訊息完成：找到 {len(records)} 條記錄，共 {total_count} 條")
            return result
            
        except Exception as e:
            logger.error(f"搜尋訊息失敗：{e}")
            raise ServiceError(
                f"搜尋訊息失敗：{str(e)}",
                service_name=self.name,
                operation="search_messages"
            )
    
    @handle_errors(log_errors=True)
    async def purge_old_messages(self, days: Optional[int] = None) -> int:
        """
        清理舊訊息
        
        參數：
            days: 保留天數，如果不提供則使用設定中的值
            
        返回：
            清理的訊息數量
        """
        try:
            if days is None:
                settings = await self.get_settings()
                days = settings.retention_days
            
            cutoff_time = datetime.now() - timedelta(days=days)
            cutoff_timestamp = cutoff_time.timestamp()
            
            # 先查詢要刪除的數量
            count_result = await self.db_manager.fetchone(
                "SELECT COUNT(*) as count FROM messages WHERE timestamp < ?",
                (cutoff_timestamp,),
                db_type="message"
            )
            delete_count = count_result['count'] if count_result else 0
            
            # 執行刪除
            await self.db_manager.execute(
                "DELETE FROM messages WHERE timestamp < ?",
                (cutoff_timestamp,),
                db_type="message"
            )
            
            logger.info(f"清理舊訊息完成：刪除了 {delete_count} 條記錄")
            return delete_count
            
        except Exception as e:
            logger.error(f"清理舊訊息失敗：{e}")
            raise ServiceError(
                f"清理舊訊息失敗：{str(e)}",
                service_name=self.name,
                operation="purge_old_messages"
            )
    
    async def refresh_settings(self) -> None:
        """重新載入設定快取"""
        try:
            # 避免頻繁重新載入
            current_time = datetime.now().timestamp()
            if current_time - self._last_settings_refresh < 60:  # 1分鐘內不重複載入
                return
            
            async with self._cache_lock:
                rows = await self.db_manager.fetchall(
                    "SELECT setting_name, setting_value FROM message_settings"
                )
                self._settings_cache = {row['setting_name']: row['setting_value'] for row in rows}
                self._last_settings_refresh = current_time
            
            logger.debug("訊息設定快取已更新")
            
        except Exception as e:
            logger.error(f"重新載入設定快取失敗：{e}")
    
    async def refresh_monitored_channels(self) -> None:
        """重新載入監聽頻道快取"""
        try:
            # 避免頻繁重新載入
            current_time = datetime.now().timestamp()
            if current_time - self._last_channels_refresh < 60:  # 1分鐘內不重複載入
                return
            
            async with self._cache_lock:
                rows = await self.db_manager.fetchall(
                    "SELECT channel_id FROM monitored_channels"
                )
                self._monitored_channels = [row['channel_id'] for row in rows]
                self._last_channels_refresh = current_time
            
            logger.debug(f"監聽頻道快取已更新：{len(self._monitored_channels)} 個頻道")
            
        except Exception as e:
            logger.error(f"重新載入監聽頻道快取失敗：{e}")
    
    async def is_channel_monitored(self, channel_id: int) -> bool:
        """檢查頻道是否被監聽"""
        await self.refresh_monitored_channels()
        return channel_id in self._monitored_channels
    
    async def _add_to_cache(self, message) -> None:
        """將訊息添加到快取"""
        try:
            async with self._cache_lock:
                channel_id = message.channel.id
                cache_item = MessageCacheItem(
                    message=message,
                    channel_id=channel_id,
                    cached_at=datetime.now()
                )
                
                self._message_cache[channel_id].append(cache_item)
                
                # 檢查是否需要立即處理
                cache_list = self._message_cache[channel_id]
                if len(cache_list) >= self.render_config.max_cached_messages:
                    await self._process_channel_cache(channel_id)
                else:
                    # 設定定時處理
                    if channel_id not in self._cache_timers:
                        timer = asyncio.create_task(self._cache_timeout_handler(channel_id))
                        self._cache_timers[channel_id] = timer
                        
        except Exception as e:
            logger.error(f"添加訊息到快取失敗：{e}")
    
    async def _cache_timeout_handler(self, channel_id: int) -> None:
        """快取超時處理器"""
        try:
            await asyncio.sleep(self.render_config.max_cache_time)
            await self._process_channel_cache(channel_id)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"快取超時處理失敗：{e}")
    
    async def _process_channel_cache(self, channel_id: int) -> None:
        """處理頻道的快取訊息"""
        try:
            async with self._cache_lock:
                cache_list = self._message_cache.get(channel_id, [])
                if not cache_list:
                    return
                
                # 清除快取和定時器
                self._message_cache[channel_id] = []
                if channel_id in self._cache_timers:
                    timer = self._cache_timers.pop(channel_id)
                    if not timer.cancelled():
                        timer.cancel()
            
            # 圖片渲染功能佔位符
            # 未來版本可以在這裡添加圖片渲染邏輯：
            # - 生成訊息摘要圖片
            # - 渲染聊天記錄縮略圖 
            # - 建立視覺化統計圖表
            # 目前先記錄日誌
            logger.info(f"處理頻道 {channel_id} 的 {len(cache_list)} 條快取訊息")
            
            # 標記為已處理
            for item in cache_list:
                item.processed = True
                
        except Exception as e:
            logger.error(f"處理頻道快取失敗：{e}")
    
    async def _process_all_cached_messages(self) -> None:
        """處理所有快取的訊息"""
        try:
            async with self._cache_lock:
                channel_ids = list(self._message_cache.keys())
            
            for channel_id in channel_ids:
                await self._process_channel_cache(channel_id)
                
        except Exception as e:
            logger.error(f"處理所有快取訊息失敗：{e}")