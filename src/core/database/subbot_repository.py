"""
子機器人資料存取層 (Repository/DAO模式)
Task ID: 3 - 子機器人聊天功能和管理系統開發

這個模組提供專門的子機器人資料存取功能：
- 實現標準CRUD操作
- 提供高效的查詢方法和索引策略
- 集成Token安全加密儲存
- 支援事務管理和資料完整性
- 實現記憶體快取機制
- 與現有資料庫管理器無縫整合
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# 核心依賴
from core.base_service import BaseService
from core.database_manager import DatabaseManager, get_database_manager
from core.security_manager import get_security_manager
from src.core.errors import (
    SubBotError, 
    SubBotCreationError,
    SubBotTokenError,
    SubBotChannelError,
    DatabaseError
)

logger = logging.getLogger('core.database.subbot_repository')


class SubBotStatus(Enum):
    """子機器人狀態枚舉"""
    OFFLINE = "offline"
    ONLINE = "online" 
    CONNECTING = "connecting"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class ChannelType(Enum):
    """頻道類型枚舉"""
    TEXT = "text"
    VOICE = "voice"
    CATEGORY = "category"
    NEWS = "news"
    THREAD = "thread"


@dataclass
class SubBotEntity:
    """子機器人實體類別"""
    id: Optional[int] = None
    bot_id: str = ""
    name: str = ""
    token_hash: str = ""
    target_channels: List[int] = None
    ai_enabled: bool = False
    ai_model: Optional[str] = None
    personality: Optional[str] = None
    rate_limit: int = 10
    status: str = SubBotStatus.OFFLINE.value
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None
    message_count: int = 0
    owner_id: Optional[int] = None
    
    def __post_init__(self):
        if self.target_channels is None:
            self.target_channels = []
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式，適用於資料庫操作"""
        result = asdict(self)
        # 處理特殊欄位
        result['target_channels'] = json.dumps(self.target_channels)
        if self.created_at:
            result['created_at'] = self.created_at.isoformat()
        if self.updated_at:
            result['updated_at'] = self.updated_at.isoformat()
        if self.last_active_at:
            result['last_active_at'] = self.last_active_at.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SubBotEntity':
        """從字典創建實體"""
        # 處理特殊欄位
        if 'target_channels' in data and isinstance(data['target_channels'], str):
            data['target_channels'] = json.loads(data['target_channels'])
        
        # 處理日期時間欄位
        for field in ['created_at', 'updated_at', 'last_active_at']:
            if field in data and isinstance(data[field], str):
                try:
                    data[field] = datetime.fromisoformat(data[field])
                except ValueError:
                    data[field] = None
        
        return cls(**data)


@dataclass
class SubBotChannelEntity:
    """子機器人頻道關聯實體"""
    id: Optional[int] = None
    sub_bot_id: int = 0
    channel_id: int = 0
    channel_type: str = ChannelType.TEXT.value
    permissions: Dict[str, bool] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.permissions is None:
            self.permissions = {
                'send_messages': True,
                'read_messages': True,
                'manage_messages': False
            }
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        result = asdict(self)
        result['permissions'] = json.dumps(self.permissions)
        if self.created_at:
            result['created_at'] = self.created_at.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SubBotChannelEntity':
        """從字典創建實體"""
        if 'permissions' in data and isinstance(data['permissions'], str):
            data['permissions'] = json.loads(data['permissions'])
        
        if 'created_at' in data and isinstance(data['created_at'], str):
            try:
                data['created_at'] = datetime.fromisoformat(data['created_at'])
            except ValueError:
                data['created_at'] = None
        
        return cls(**data)


class SubBotCache:
    """子機器人記憶體快取系統"""
    
    def __init__(self, cache_ttl: int = 300):  # 5分鐘TTL
        """
        初始化快取系統
        
        Args:
            cache_ttl: 快取存活時間（秒）
        """
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._timestamps: Dict[str, datetime] = {}
        self._enabled = True
        
    def get(self, key: str) -> Optional[Any]:
        """獲取快取值"""
        if not self._enabled or key not in self._cache:
            return None
            
        # 檢查是否過期
        if self._is_expired(key):
            self.invalidate(key)
            return None
            
        return self._cache[key]
    
    def set(self, key: str, value: Any) -> None:
        """設置快取值"""
        if not self._enabled:
            return
            
        self._cache[key] = value
        self._timestamps[key] = datetime.now()
    
    def invalidate(self, key: str) -> None:
        """清除特定快取"""
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)
    
    def invalidate_pattern(self, pattern: str) -> None:
        """清除匹配模式的快取"""
        keys_to_remove = [key for key in self._cache.keys() if pattern in key]
        for key in keys_to_remove:
            self.invalidate(key)
    
    def clear(self) -> None:
        """清除所有快取"""
        self._cache.clear()
        self._timestamps.clear()
    
    def _is_expired(self, key: str) -> bool:
        """檢查快取是否過期"""
        if key not in self._timestamps:
            return True
        return (datetime.now() - self._timestamps[key]).total_seconds() > self.cache_ttl
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取快取統計"""
        total_keys = len(self._cache)
        expired_keys = sum(1 for key in self._cache.keys() if self._is_expired(key))
        
        return {
            'enabled': self._enabled,
            'total_keys': total_keys,
            'expired_keys': expired_keys,
            'valid_keys': total_keys - expired_keys,
            'cache_ttl': self.cache_ttl
        }


class SubBotRepository(BaseService):
    """
    子機器人資料存取層
    
    實現完整的CRUD操作，Token安全管理，高效查詢和快取機制
    """
    
    def __init__(self, cache_enabled: bool = True, cache_ttl: int = 300):
        """
        初始化子機器人資料存取層
        
        Args:
            cache_enabled: 是否啟用快取
            cache_ttl: 快取存活時間（秒）
        """
        super().__init__("SubBotRepository")
        
        # 資料庫管理器
        self.db_manager: Optional[DatabaseManager] = None
        
        # 安全管理器
        self.security_manager = get_security_manager()
        
        # 快取系統
        self.cache = SubBotCache(cache_ttl) if cache_enabled else None
        
        # 統計資訊
        self._stats = {
            'queries_executed': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'tokens_encrypted': 0,
            'tokens_decrypted': 0,
            'last_operation': None
        }
    
    async def _initialize(self) -> bool:
        """初始化資料存取層"""
        try:
            # 獲取資料庫管理器
            self.db_manager = await get_database_manager()
            
            # 確認資料表存在
            await self._ensure_tables_exist()
            
            # 創建或更新索引
            await self._create_indexes()
            
            self.logger.info("子機器人資料存取層初始化完成")
            return True
            
        except Exception as e:
            self.logger.error(f"子機器人資料存取層初始化失敗: {e}")
            return False
    
    async def _cleanup(self) -> None:
        """清理資源"""
        try:
            if self.cache:
                self.cache.clear()
            self.logger.info("子機器人資料存取層清理完成")
        except Exception as e:
            self.logger.error(f"清理資料存取層時發生錯誤: {e}")
    
    async def _validate_permissions(
        self, 
        user_id: int, 
        guild_id: Optional[int], 
        action: str
    ) -> bool:
        """驗證資料庫操作權限"""
        # 實作權限檢查邏輯
        return True  # 暫時允許所有操作
    
    async def _ensure_tables_exist(self) -> None:
        """確認必要的資料表存在"""
        try:
            # 檢查sub_bots表
            result = await self.db_manager.fetchone(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sub_bots'"
            )
            if not result:
                raise DatabaseError("sub_bots表不存在，請先執行資料庫遷移")
            
            # 檢查sub_bot_channels表
            result = await self.db_manager.fetchone(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sub_bot_channels'"
            )
            if not result:
                raise DatabaseError("sub_bot_channels表不存在，請先執行資料庫遷移")
                
            self.logger.debug("確認所有必要資料表存在")
            
        except Exception as e:
            self.logger.error(f"檢查資料表存在性時發生錯誤: {e}")
            raise
    
    async def _create_indexes(self) -> None:
        """創建或更新索引以優化查詢效能"""
        try:
            indexes = [
                # sub_bots表索引
                "CREATE INDEX IF NOT EXISTS idx_sub_bots_bot_id ON sub_bots(bot_id)",
                "CREATE INDEX IF NOT EXISTS idx_sub_bots_status ON sub_bots(status)",
                "CREATE INDEX IF NOT EXISTS idx_sub_bots_owner_id ON sub_bots(owner_id)",
                "CREATE INDEX IF NOT EXISTS idx_sub_bots_created_at ON sub_bots(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_sub_bots_ai_enabled ON sub_bots(ai_enabled)",
                
                # sub_bot_channels表索引
                "CREATE INDEX IF NOT EXISTS idx_sub_bot_channels_sub_bot_id ON sub_bot_channels(sub_bot_id)",
                "CREATE INDEX IF NOT EXISTS idx_sub_bot_channels_channel_id ON sub_bot_channels(channel_id)",
                "CREATE INDEX IF NOT EXISTS idx_sub_bot_channels_type ON sub_bot_channels(channel_type)",
                
                # 複合索引
                "CREATE INDEX IF NOT EXISTS idx_sub_bots_status_updated ON sub_bots(status, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_sub_bot_channels_bot_channel ON sub_bot_channels(sub_bot_id, channel_id)",
            ]
            
            for index_sql in indexes:
                await self.db_manager.execute(index_sql)
                
            self.logger.debug("資料庫索引創建完成")
            
        except Exception as e:
            self.logger.warning(f"創建索引時發生錯誤: {e}")
    
    def _update_stats(self, operation: str, cache_hit: bool = False) -> None:
        """更新統計資訊"""
        self._stats['queries_executed'] += 1
        self._stats['last_operation'] = {
            'type': operation,
            'timestamp': datetime.now().isoformat(),
            'cache_hit': cache_hit
        }
        
        if cache_hit:
            self._stats['cache_hits'] += 1
        else:
            self._stats['cache_misses'] += 1
    
    def _get_cache_key(self, operation: str, **kwargs) -> str:
        """生成快取鍵值"""
        key_parts = [f"subbot_{operation}"]
        for k, v in kwargs.items():
            key_parts.append(f"{k}_{v}")
        return ":".join(key_parts)
    
    # ========== 主要CRUD操作 ==========
    
    async def create_subbot(self, subbot: SubBotEntity) -> SubBotEntity:
        """
        創建新的子機器人
        
        Args:
            subbot: 子機器人實體
            
        Returns:
            創建後的子機器人實體（包含ID）
            
        Raises:
            SubBotCreationError: 創建失敗
            SubBotTokenError: Token處理失敗
        """
        try:
            # 驗證bot_id唯一性
            existing = await self.get_subbot_by_bot_id(subbot.bot_id)
            if existing:
                raise SubBotCreationError(
                    bot_id=subbot.bot_id,
                    reason=f"Bot ID {subbot.bot_id} 已存在"
                )
            
            # 加密Token（如果提供）
            if subbot.token_hash and not subbot.token_hash.startswith('encrypted_'):
                subbot.token_hash = await self._encrypt_token(subbot.token_hash)
                self._stats['tokens_encrypted'] += 1
            
            # 設置時間戳
            now = datetime.now()
            subbot.created_at = now
            subbot.updated_at = now
            
            # 插入資料庫
            subbot_dict = subbot.to_dict()
            
            # 移除None或空值的ID欄位
            if 'id' in subbot_dict and subbot_dict['id'] is None:
                del subbot_dict['id']
            
            result = await self.db_manager.execute(
                """INSERT INTO sub_bots 
                   (bot_id, name, token_hash, target_channels, ai_enabled, ai_model, 
                    personality, rate_limit, status, created_at, updated_at, 
                    message_count, owner_id) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    subbot.bot_id,
                    subbot.name,
                    subbot.token_hash,
                    json.dumps(subbot.target_channels),
                    subbot.ai_enabled,
                    subbot.ai_model,
                    subbot.personality,
                    subbot.rate_limit,
                    subbot.status,
                    subbot.created_at.isoformat(),
                    subbot.updated_at.isoformat(),
                    subbot.message_count,
                    subbot.owner_id
                )
            )
            
            # 獲取插入的ID
            created_id = await self._get_last_insert_id()
            subbot.id = created_id
            
            # 清除相關快取
            if self.cache:
                self.cache.invalidate_pattern("subbot_")
            
            self._update_stats('create')
            self.logger.info(f"成功創建子機器人: {subbot.bot_id}")
            
            return subbot
            
        except Exception as e:
            self.logger.error(f"創建子機器人失敗: {e}")
            if isinstance(e, (SubBotCreationError, SubBotTokenError)):
                raise
            raise SubBotCreationError(
                bot_id=subbot.bot_id,
                reason=f"資料庫操作失敗: {str(e)}"
            )
    
    async def get_subbot_by_id(self, subbot_id: int, decrypt_token: bool = False) -> Optional[SubBotEntity]:
        """
        根據資料庫ID獲取子機器人
        
        Args:
            subbot_id: 資料庫ID
            decrypt_token: 是否解密Token
            
        Returns:
            子機器人實體或None
        """
        cache_key = self._get_cache_key("by_id", id=subbot_id, decrypt=decrypt_token)
        
        try:
            # 檢查快取
            if self.cache:
                cached = self.cache.get(cache_key)
                if cached:
                    self._update_stats('get_by_id', cache_hit=True)
                    return SubBotEntity.from_dict(cached)
            
            # 查詢資料庫
            result = await self.db_manager.fetchone(
                "SELECT * FROM sub_bots WHERE id = ?",
                (subbot_id,)
            )
            
            if not result:
                self._update_stats('get_by_id')
                return None
            
            # 轉換為實體
            subbot = SubBotEntity.from_dict(dict(result))
            
            # 解密Token（如果需要）
            if decrypt_token and subbot.token_hash:
                subbot.token_hash = await self._decrypt_token(subbot.token_hash)
                self._stats['tokens_decrypted'] += 1
            
            # 存入快取
            if self.cache:
                self.cache.set(cache_key, subbot.to_dict())
            
            self._update_stats('get_by_id')
            return subbot
            
        except Exception as e:
            self.logger.error(f"根據ID獲取子機器人失敗: {e}")
            return None
    
    async def get_subbot_by_bot_id(self, bot_id: str, decrypt_token: bool = False) -> Optional[SubBotEntity]:
        """
        根據bot_id獲取子機器人
        
        Args:
            bot_id: 子機器人ID
            decrypt_token: 是否解密Token
            
        Returns:
            子機器人實體或None
        """
        cache_key = self._get_cache_key("by_bot_id", bot_id=bot_id, decrypt=decrypt_token)
        
        try:
            # 檢查快取
            if self.cache:
                cached = self.cache.get(cache_key)
                if cached:
                    self._update_stats('get_by_bot_id', cache_hit=True)
                    return SubBotEntity.from_dict(cached)
            
            # 查詢資料庫
            result = await self.db_manager.fetchone(
                "SELECT * FROM sub_bots WHERE bot_id = ?",
                (bot_id,)
            )
            
            if not result:
                self._update_stats('get_by_bot_id')
                return None
            
            # 轉換為實體
            subbot = SubBotEntity.from_dict(dict(result))
            
            # 解密Token（如果需要）
            if decrypt_token and subbot.token_hash:
                subbot.token_hash = await self._decrypt_token(subbot.token_hash)
                self._stats['tokens_decrypted'] += 1
            
            # 存入快取
            if self.cache:
                self.cache.set(cache_key, subbot.to_dict())
            
            self._update_stats('get_by_bot_id')
            return subbot
            
        except Exception as e:
            self.logger.error(f"根據bot_id獲取子機器人失敗: {e}")
            return None
    
    async def update_subbot(self, subbot: SubBotEntity) -> bool:
        """
        更新子機器人資訊
        
        Args:
            subbot: 要更新的子機器人實體
            
        Returns:
            是否更新成功
        """
        try:
            if not subbot.id:
                raise ValueError("子機器人ID不能為空")
            
            # 處理Token加密
            if subbot.token_hash and not subbot.token_hash.startswith('encrypted_'):
                subbot.token_hash = await self._encrypt_token(subbot.token_hash)
                self._stats['tokens_encrypted'] += 1
            
            # 更新時間戳
            subbot.updated_at = datetime.now()
            
            # 執行更新
            await self.db_manager.execute(
                """UPDATE sub_bots SET 
                   name = ?, token_hash = ?, target_channels = ?, ai_enabled = ?, 
                   ai_model = ?, personality = ?, rate_limit = ?, status = ?, 
                   updated_at = ?, last_active_at = ?, message_count = ?, owner_id = ?
                   WHERE id = ?""",
                (
                    subbot.name,
                    subbot.token_hash,
                    json.dumps(subbot.target_channels),
                    subbot.ai_enabled,
                    subbot.ai_model,
                    subbot.personality,
                    subbot.rate_limit,
                    subbot.status,
                    subbot.updated_at.isoformat(),
                    subbot.last_active_at.isoformat() if subbot.last_active_at else None,
                    subbot.message_count,
                    subbot.owner_id,
                    subbot.id
                )
            )
            
            # 清除相關快取
            if self.cache:
                self.cache.invalidate_pattern("subbot_")
            
            self._update_stats('update')
            self.logger.info(f"成功更新子機器人: {subbot.bot_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"更新子機器人失敗: {e}")
            return False
    
    async def delete_subbot(self, bot_id: str) -> bool:
        """
        刪除子機器人（軟刪除或硬刪除）
        
        Args:
            bot_id: 子機器人ID
            
        Returns:
            是否刪除成功
        """
        try:
            # 獲取子機器人資訊
            subbot = await self.get_subbot_by_bot_id(bot_id)
            if not subbot:
                return False  # 不存在，視為成功
            
            # 先刪除相關的頻道配置
            await self.db_manager.execute(
                "DELETE FROM sub_bot_channels WHERE sub_bot_id = ?",
                (subbot.id,)
            )
            
            # 刪除主記錄
            await self.db_manager.execute(
                "DELETE FROM sub_bots WHERE bot_id = ?",
                (bot_id,)
            )
            
            # 清除相關快取
            if self.cache:
                self.cache.invalidate_pattern("subbot_")
            
            self._update_stats('delete')
            self.logger.info(f"成功刪除子機器人: {bot_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"刪除子機器人失敗: {e}")
            return False
    
    # ========== 查詢操作 ==========
    
    async def list_subbots(
        self, 
        status: Optional[str] = None,
        ai_enabled: Optional[bool] = None,
        owner_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        decrypt_tokens: bool = False
    ) -> List[SubBotEntity]:
        """
        列出子機器人（支援多種過濾條件）
        
        Args:
            status: 狀態過濾
            ai_enabled: AI啟用狀態過濾
            owner_id: 擁有者ID過濾
            limit: 限制結果數量
            offset: 偏移量
            decrypt_tokens: 是否解密Token
            
        Returns:
            子機器人列表
        """
        try:
            # 構建查詢條件
            where_conditions = []
            params = []
            
            if status:
                where_conditions.append("status = ?")
                params.append(status)
            
            if ai_enabled is not None:
                where_conditions.append("ai_enabled = ?")
                params.append(ai_enabled)
            
            if owner_id:
                where_conditions.append("owner_id = ?")
                params.append(owner_id)
            
            # 構建SQL
            sql = "SELECT * FROM sub_bots"
            if where_conditions:
                sql += " WHERE " + " AND ".join(where_conditions)
            
            sql += " ORDER BY created_at DESC"
            
            if limit:
                sql += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])
            
            # 執行查詢
            results = await self.db_manager.fetchall(sql, params)
            
            subbots = []
            for result in results:
                subbot = SubBotEntity.from_dict(dict(result))
                
                # 解密Token（如果需要）
                if decrypt_tokens and subbot.token_hash:
                    subbot.token_hash = await self._decrypt_token(subbot.token_hash)
                    self._stats['tokens_decrypted'] += 1
                
                subbots.append(subbot)
            
            self._update_stats('list')
            return subbots
            
        except Exception as e:
            self.logger.error(f"列出子機器人失敗: {e}")
            return []
    
    async def get_subbots_by_channel(self, channel_id: int) -> List[SubBotEntity]:
        """
        根據頻道ID獲取相關的子機器人
        
        Args:
            channel_id: 頻道ID
            
        Returns:
            子機器人列表
        """
        try:
            results = await self.db_manager.fetchall(
                """SELECT sb.* FROM sub_bots sb 
                   INNER JOIN sub_bot_channels sbc ON sb.id = sbc.sub_bot_id 
                   WHERE sbc.channel_id = ? AND sb.status != 'offline'
                   ORDER BY sb.created_at DESC""",
                (channel_id,)
            )
            
            subbots = []
            for result in results:
                subbot = SubBotEntity.from_dict(dict(result))
                subbots.append(subbot)
            
            self._update_stats('get_by_channel')
            return subbots
            
        except Exception as e:
            self.logger.error(f"根據頻道獲取子機器人失敗: {e}")
            return []
    
    async def get_active_subbots(self) -> List[SubBotEntity]:
        """
        獲取所有活躍的子機器人
        
        Returns:
            活躍子機器人列表
        """
        return await self.list_subbots(status=SubBotStatus.ONLINE.value)
    
    async def count_subbots(self, status: Optional[str] = None) -> int:
        """
        統計子機器人數量
        
        Args:
            status: 狀態過濾
            
        Returns:
            數量
        """
        try:
            if status:
                result = await self.db_manager.fetchone(
                    "SELECT COUNT(*) as count FROM sub_bots WHERE status = ?",
                    (status,)
                )
            else:
                result = await self.db_manager.fetchone(
                    "SELECT COUNT(*) as count FROM sub_bots"
                )
            
            return result['count'] if result else 0
            
        except Exception as e:
            self.logger.error(f"統計子機器人數量失敗: {e}")
            return 0
    
    # ========== 頻道管理操作 ==========
    
    async def add_channel_to_subbot(self, subbot_id: int, channel: SubBotChannelEntity) -> bool:
        """
        為子機器人添加頻道配置
        
        Args:
            subbot_id: 子機器人資料庫ID
            channel: 頻道配置
            
        Returns:
            是否添加成功
        """
        try:
            channel.sub_bot_id = subbot_id
            channel.created_at = datetime.now()
            
            # 檢查是否已存在
            existing = await self.db_manager.fetchone(
                "SELECT id FROM sub_bot_channels WHERE sub_bot_id = ? AND channel_id = ?",
                (subbot_id, channel.channel_id)
            )
            
            if existing:
                # 更新現有配置
                await self.db_manager.execute(
                    "UPDATE sub_bot_channels SET channel_type = ?, permissions = ? WHERE id = ?",
                    (
                        channel.channel_type,
                        json.dumps(channel.permissions),
                        existing['id']
                    )
                )
            else:
                # 插入新配置
                await self.db_manager.execute(
                    "INSERT INTO sub_bot_channels (sub_bot_id, channel_id, channel_type, permissions, created_at) VALUES (?, ?, ?, ?, ?)",
                    (
                        channel.sub_bot_id,
                        channel.channel_id,
                        channel.channel_type,
                        json.dumps(channel.permissions),
                        channel.created_at.isoformat()
                    )
                )
            
            # 清除相關快取
            if self.cache:
                self.cache.invalidate_pattern("subbot_")
            
            self._update_stats('add_channel')
            return True
            
        except Exception as e:
            self.logger.error(f"添加頻道配置失敗: {e}")
            return False
    
    async def remove_channel_from_subbot(self, subbot_id: int, channel_id: int) -> bool:
        """
        從子機器人移除頻道配置
        
        Args:
            subbot_id: 子機器人資料庫ID
            channel_id: 頻道ID
            
        Returns:
            是否移除成功
        """
        try:
            await self.db_manager.execute(
                "DELETE FROM sub_bot_channels WHERE sub_bot_id = ? AND channel_id = ?",
                (subbot_id, channel_id)
            )
            
            # 清除相關快取
            if self.cache:
                self.cache.invalidate_pattern("subbot_")
            
            self._update_stats('remove_channel')
            return True
            
        except Exception as e:
            self.logger.error(f"移除頻道配置失敗: {e}")
            return False
    
    async def get_subbot_channels(self, subbot_id: int) -> List[SubBotChannelEntity]:
        """
        獲取子機器人的所有頻道配置
        
        Args:
            subbot_id: 子機器人資料庫ID
            
        Returns:
            頻道配置列表
        """
        try:
            results = await self.db_manager.fetchall(
                "SELECT * FROM sub_bot_channels WHERE sub_bot_id = ? ORDER BY created_at ASC",
                (subbot_id,)
            )
            
            channels = []
            for result in results:
                channel = SubBotChannelEntity.from_dict(dict(result))
                channels.append(channel)
            
            self._update_stats('get_channels')
            return channels
            
        except Exception as e:
            self.logger.error(f"獲取子機器人頻道配置失敗: {e}")
            return []
    
    # ========== 統計和狀態操作 ==========
    
    async def update_subbot_activity(self, bot_id: str, message_count_increment: int = 1) -> bool:
        """
        更新子機器人活動統計
        
        Args:
            bot_id: 子機器人ID
            message_count_increment: 訊息數量增量
            
        Returns:
            是否更新成功
        """
        try:
            now = datetime.now()
            
            await self.db_manager.execute(
                """UPDATE sub_bots SET 
                   message_count = message_count + ?, 
                   last_active_at = ?, 
                   updated_at = ? 
                   WHERE bot_id = ?""",
                (message_count_increment, now.isoformat(), now.isoformat(), bot_id)
            )
            
            # 清除相關快取
            if self.cache:
                self.cache.invalidate_pattern(f"subbot_by_bot_id:bot_id_{bot_id}")
            
            self._update_stats('update_activity')
            return True
            
        except Exception as e:
            self.logger.error(f"更新子機器人活動統計失敗: {e}")
            return False
    
    async def update_subbot_status(self, bot_id: str, status: str, error_message: Optional[str] = None) -> bool:
        """
        更新子機器人狀態
        
        Args:
            bot_id: 子機器人ID
            status: 新狀態
            error_message: 錯誤訊息（如果適用）
            
        Returns:
            是否更新成功
        """
        try:
            now = datetime.now()
            
            # 如果設置為在線狀態，同時更新last_active_at
            if status == SubBotStatus.ONLINE.value:
                await self.db_manager.execute(
                    "UPDATE sub_bots SET status = ?, updated_at = ?, last_active_at = ? WHERE bot_id = ?",
                    (status, now.isoformat(), now.isoformat(), bot_id)
                )
            else:
                await self.db_manager.execute(
                    "UPDATE sub_bots SET status = ?, updated_at = ? WHERE bot_id = ?",
                    (status, now.isoformat(), bot_id)
                )
            
            # 如果有錯誤訊息，可以記錄到日誌或另一個表中
            if error_message:
                self.logger.warning(f"子機器人 {bot_id} 狀態變更為 {status}，錯誤: {error_message}")
            
            # 清除相關快取
            if self.cache:
                self.cache.invalidate_pattern(f"subbot_by_bot_id:bot_id_{bot_id}")
            
            self._update_stats('update_status')
            return True
            
        except Exception as e:
            self.logger.error(f"更新子機器人狀態失敗: {e}")
            return False
    
    async def get_subbots_statistics(self) -> Dict[str, Any]:
        """
        獲取子機器人統計資訊
        
        Returns:
            統計資訊字典
        """
        try:
            stats = {}
            
            # 總數統計
            stats['total_count'] = await self.count_subbots()
            
            # 狀態分布統計
            status_stats = {}
            for status in SubBotStatus:
                count = await self.count_subbots(status.value)
                status_stats[status.value] = count
            stats['status_distribution'] = status_stats
            
            # AI功能統計
            ai_enabled = await self.db_manager.fetchone(
                "SELECT COUNT(*) as count FROM sub_bots WHERE ai_enabled = 1"
            )
            stats['ai_enabled_count'] = ai_enabled['count'] if ai_enabled else 0
            
            # 活動統計
            active_count = await self.db_manager.fetchone(
                "SELECT COUNT(*) as count FROM sub_bots WHERE last_active_at > ?",
                ((datetime.now() - timedelta(hours=24)).isoformat(),)
            )
            stats['active_in_24h'] = active_count['count'] if active_count else 0
            
            # 訊息總數統計
            message_total = await self.db_manager.fetchone(
                "SELECT SUM(message_count) as total FROM sub_bots"
            )
            stats['total_messages'] = message_total['total'] if message_total and message_total['total'] else 0
            
            # 最新創建時間
            latest = await self.db_manager.fetchone(
                "SELECT MAX(created_at) as latest FROM sub_bots"
            )
            stats['latest_created'] = latest['latest'] if latest else None
            
            self._update_stats('get_statistics')
            return stats
            
        except Exception as e:
            self.logger.error(f"獲取統計資訊失敗: {e}")
            return {}
    
    # ========== Token安全管理 ==========
    
    async def _encrypt_token(self, token: str) -> str:
        """
        加密Discord Token
        
        Args:
            token: 原始Token
            
        Returns:
            加密後的Token
        """
        try:
            encrypted = self.security_manager.encrypt_discord_token(token)
            return f"encrypted_{encrypted}"
        except Exception as e:
            self.logger.error(f"Token加密失敗: {e}")
            raise SubBotTokenError(bot_id="未知", token_issue=f"加密失敗: {str(e)}")
    
    async def _decrypt_token(self, encrypted_token: str) -> str:
        """
        解密Discord Token
        
        Args:
            encrypted_token: 加密的Token
            
        Returns:
            原始Token
        """
        try:
            if encrypted_token.startswith('encrypted_'):
                encrypted_token = encrypted_token[10:]  # 移除前綴
            
            return self.security_manager.decrypt_discord_token(encrypted_token)
        except Exception as e:
            self.logger.error(f"Token解密失敗: {e}")
            raise SubBotTokenError(bot_id="未知", token_issue=f"解密失敗: {str(e)}")
    
    async def verify_token_integrity(self, bot_id: str) -> bool:
        """
        驗證Token完整性
        
        Args:
            bot_id: 子機器人ID
            
        Returns:
            Token是否有效
        """
        try:
            subbot = await self.get_subbot_by_bot_id(bot_id, decrypt_token=False)
            if not subbot or not subbot.token_hash:
                return False
            
            # 嘗試解密Token
            try:
                await self._decrypt_token(subbot.token_hash)
                return True
            except:
                return False
                
        except Exception as e:
            self.logger.error(f"驗證Token完整性失敗: {e}")
            return False
    
    # ========== 工具方法 ==========
    
    async def _get_last_insert_id(self) -> int:
        """獲取最後插入的記錄ID"""
        result = await self.db_manager.fetchone("SELECT last_insert_rowid() as id")
        return result['id'] if result else 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """獲取快取統計"""
        if not self.cache:
            return {'enabled': False}
        
        cache_stats = self.cache.get_stats()
        cache_stats.update({
            'repository_stats': self._stats
        })
        
        return cache_stats
    
    def clear_cache(self) -> None:
        """清除所有快取"""
        if self.cache:
            self.cache.clear()
            self.logger.info("子機器人資料存取層快取已清除")
    
    def invalidate_cache_for_bot(self, bot_id: str) -> None:
        """清除特定子機器人的快取"""
        if self.cache:
            self.cache.invalidate_pattern(f"bot_id_{bot_id}")
            self.logger.debug(f"已清除子機器人 {bot_id} 的快取")
    
    async def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        try:
            # 測試資料庫連接
            await self.db_manager.fetchone("SELECT 1")
            
            # 獲取基本統計
            total_count = await self.count_subbots()
            
            return {
                'status': 'healthy',
                'database_connection': 'ok',
                'total_subbots': total_count,
                'cache_enabled': self.cache is not None,
                'last_operation': self._stats.get('last_operation'),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


# 全域實例
_subbot_repository: Optional[SubBotRepository] = None


async def get_subbot_repository() -> SubBotRepository:
    """
    獲取全域子機器人資料存取層實例
    
    Returns:
        子機器人資料存取層實例
    """
    global _subbot_repository
    if not _subbot_repository:
        _subbot_repository = SubBotRepository()
        await _subbot_repository.initialize()
    return _subbot_repository