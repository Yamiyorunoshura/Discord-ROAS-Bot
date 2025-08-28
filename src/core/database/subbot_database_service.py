"""
子機器人資料庫整合服務
Task ID: 3 - 子機器人聊天功能和管理系統開發

這個模組提供完整的資料庫整合功能：
- 整合Repository/DAO與現有資料庫管理器
- 統一事務管理和連接池
- 自動查詢優化和索引管理
- 完整的錯誤處理和重試機制
- 資料庫監控和效能統計
- 支援異步操作和批次處理
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from contextlib import asynccontextmanager
from dataclasses import asdict

# 核心依賴
from core.base_service import BaseService
from core.database_manager import DatabaseManager, get_database_manager

# 新的資料庫組件
from .subbot_repository import SubBotRepository, SubBotEntity, SubBotChannelEntity, get_subbot_repository
from .query_optimizer import QueryOptimizer, get_query_optimizer
from ..security.subbot_token_manager import SubBotTokenManager, get_token_manager, TokenEncryptionLevel

# 錯誤處理
from src.core.errors import (
    SubBotError,
    SubBotCreationError,
    SubBotTokenError,
    SubBotChannelError,
    DatabaseError
)

logger = logging.getLogger('core.database.subbot_database_service')


class TransactionManager:
    """事務管理器"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.active_transactions: Dict[str, Any] = {}
    
    @asynccontextmanager
    async def transaction(self, isolation_level: str = "DEFERRED"):
        """
        事務上下文管理器
        
        Args:
            isolation_level: 事務隔離級別
        """
        transaction_id = f"txn_{datetime.now().timestamp()}"
        
        try:
            # 開始事務
            async with self.db_manager.transaction() as conn:
                self.active_transactions[transaction_id] = {
                    'connection': conn,
                    'start_time': datetime.now(),
                    'isolation_level': isolation_level
                }
                
                yield conn
                
        except Exception as e:
            logger.error(f"事務 {transaction_id} 失敗: {e}")
            raise
        finally:
            # 清理事務記錄
            self.active_transactions.pop(transaction_id, None)
    
    def get_active_transaction_count(self) -> int:
        """獲取活躍事務數量"""
        return len(self.active_transactions)
    
    def get_transaction_stats(self) -> Dict[str, Any]:
        """獲取事務統計"""
        if not self.active_transactions:
            return {'active_count': 0, 'avg_duration': 0.0}
        
        now = datetime.now()
        durations = [
            (now - txn['start_time']).total_seconds()
            for txn in self.active_transactions.values()
        ]
        
        return {
            'active_count': len(self.active_transactions),
            'avg_duration': sum(durations) / len(durations),
            'max_duration': max(durations) if durations else 0.0,
            'min_duration': min(durations) if durations else 0.0
        }


class QueryExecutor:
    """查詢執行器 - 整合優化器和統計"""
    
    def __init__(self, db_manager: DatabaseManager, optimizer: QueryOptimizer):
        self.db_manager = db_manager
        self.optimizer = optimizer
        self.execution_stats = {
            'total_queries': 0,
            'optimized_queries': 0,
            'cached_queries': 0,
            'failed_queries': 0,
            'total_time': 0.0
        }
    
    async def execute_query(
        self,
        sql: str,
        params: Optional[Tuple] = None,
        optimize: bool = True,
        db_type: str = "main"
    ) -> None:
        """
        執行優化的查詢
        
        Args:
            sql: SQL語句
            params: 查詢參數
            optimize: 是否啟用優化
            db_type: 資料庫類型
        """
        start_time = datetime.now()
        
        try:
            # 查詢優化
            if optimize:
                optimization_result = await self.optimizer.optimize_query(sql)
                if optimization_result.get('optimized', False):
                    sql = optimization_result['optimized_sql']
                    self.execution_stats['optimized_queries'] += 1
            
            # 執行查詢
            await self.db_manager.execute(sql, params or (), db_type)
            
            # 記錄執行時間
            execution_time = (datetime.now() - start_time).total_seconds()
            self.execution_stats['total_time'] += execution_time
            
            # 分析查詢效能
            await self.optimizer.analyze_query(sql, params, execution_time)
            
        except Exception as e:
            self.execution_stats['failed_queries'] += 1
            logger.error(f"查詢執行失敗: {e}")
            raise
        finally:
            self.execution_stats['total_queries'] += 1
    
    async def fetch_query(
        self,
        sql: str,
        params: Optional[Tuple] = None,
        fetch_one: bool = False,
        optimize: bool = True,
        db_type: str = "main"
    ) -> Union[Dict[str, Any], List[Dict[str, Any]], None]:
        """
        執行查詢並返回結果
        
        Args:
            sql: SQL語句
            params: 查詢參數
            fetch_one: 是否只返回一行
            optimize: 是否啟用優化
            db_type: 資料庫類型
            
        Returns:
            查詢結果
        """
        start_time = datetime.now()
        
        try:
            # 查詢優化
            if optimize:
                optimization_result = await self.optimizer.optimize_query(sql)
                if optimization_result.get('optimized', False):
                    sql = optimization_result['optimized_sql']
                    self.execution_stats['optimized_queries'] += 1
            
            # 執行查詢
            if fetch_one:
                result = await self.db_manager.fetchone(sql, params or (), db_type)
            else:
                result = await self.db_manager.fetchall(sql, params or (), db_type)
            
            # 記錄執行時間
            execution_time = (datetime.now() - start_time).total_seconds()
            self.execution_stats['total_time'] += execution_time
            
            # 分析查詢效能
            rows_count = 1 if fetch_one and result else len(result) if result else 0
            await self.optimizer.analyze_query(sql, params, execution_time)
            
            return result
            
        except Exception as e:
            self.execution_stats['failed_queries'] += 1
            logger.error(f"查詢執行失敗: {e}")
            raise
        finally:
            self.execution_stats['total_queries'] += 1
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """獲取執行統計"""
        stats = self.execution_stats.copy()
        if stats['total_queries'] > 0:
            stats['avg_execution_time'] = stats['total_time'] / stats['total_queries']
            stats['optimization_rate'] = stats['optimized_queries'] / stats['total_queries'] * 100
            stats['failure_rate'] = stats['failed_queries'] / stats['total_queries'] * 100
        else:
            stats['avg_execution_time'] = 0.0
            stats['optimization_rate'] = 0.0
            stats['failure_rate'] = 0.0
        
        return stats


class RetryHandler:
    """重試處理器"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    async def execute_with_retry(self, operation, *args, **kwargs):
        """
        帶重試的執行操作
        
        Args:
            operation: 要執行的異步操作
            *args: 位置參數
            **kwargs: 關鍵字參數
            
        Returns:
            操作結果
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await operation(*args, **kwargs)
            
            except Exception as e:
                last_exception = e
                
                # 判斷是否應該重試
                if attempt == self.max_retries or not self._should_retry(e):
                    break
                
                # 計算延遲時間（指數退避）
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                
                logger.warning(f"操作失敗，{delay}秒後重試 (嘗試 {attempt + 1}/{self.max_retries + 1}): {e}")
                await asyncio.sleep(delay)
        
        # 重試結束後仍然失敗
        raise last_exception
    
    def _should_retry(self, exception: Exception) -> bool:
        """判斷異常是否應該重試"""
        # 資料庫鎖定、連接問題等可以重試
        retry_exceptions = (
            DatabaseError,
            asyncio.TimeoutError,
            ConnectionError
        )
        
        # 業務邏輯錯誤不應該重試
        no_retry_exceptions = (
            SubBotCreationError,
            SubBotTokenError,
            SubBotChannelError
        )
        
        if isinstance(exception, no_retry_exceptions):
            return False
        
        if isinstance(exception, retry_exceptions):
            return True
        
        # 檢查SQLite特定錯誤
        error_msg = str(exception).lower()
        if any(keyword in error_msg for keyword in ['database is locked', 'connection', 'timeout']):
            return True
        
        return False


class SubBotDatabaseService(BaseService):
    """
    子機器人資料庫整合服務
    
    整合所有資料庫相關組件，提供統一的高級API
    """
    
    def __init__(
        self,
        enable_query_optimization: bool = True,
        enable_token_encryption: bool = True,
        encryption_level: TokenEncryptionLevel = TokenEncryptionLevel.STANDARD,
        enable_caching: bool = True,
        cache_ttl: int = 300,
        max_retries: int = 3
    ):
        """
        初始化資料庫服務
        
        Args:
            enable_query_optimization: 是否啟用查詢優化
            enable_token_encryption: 是否啟用Token加密
            encryption_level: Token加密等級
            enable_caching: 是否啟用快取
            cache_ttl: 快取存活時間（秒）
            max_retries: 最大重試次數
        """
        super().__init__("SubBotDatabaseService")
        
        # 組件配置
        self.enable_query_optimization = enable_query_optimization
        self.enable_token_encryption = enable_token_encryption
        self.encryption_level = encryption_level
        self.enable_caching = enable_caching
        self.cache_ttl = cache_ttl
        
        # 核心組件
        self.db_manager: Optional[DatabaseManager] = None
        self.repository: Optional[SubBotRepository] = None
        self.query_optimizer: Optional[QueryOptimizer] = None
        self.token_manager: Optional[SubBotTokenManager] = None
        
        # 輔助組件
        self.transaction_manager: Optional[TransactionManager] = None
        self.query_executor: Optional[QueryExecutor] = None
        self.retry_handler = RetryHandler(max_retries=max_retries)
        
        # 統計資訊
        self._service_stats = {
            'operations_count': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'retries_performed': 0,
            'cache_usage': {
                'hits': 0,
                'misses': 0,
                'evictions': 0
            },
            'last_operation_time': None
        }
    
    async def _initialize(self) -> bool:
        """初始化資料庫服務"""
        try:
            self.logger.info("子機器人資料庫服務初始化中...")
            
            # 初始化資料庫管理器
            self.db_manager = await get_database_manager()
            self.add_dependency(self.db_manager, "database_manager")
            
            # 初始化Repository
            self.repository = SubBotRepository(
                cache_enabled=self.enable_caching,
                cache_ttl=self.cache_ttl
            )
            await self.repository.initialize()
            self.repository.add_dependency(self.db_manager, "database_manager")
            
            # 初始化查詢優化器（如果啟用）
            if self.enable_query_optimization:
                self.query_optimizer = await get_query_optimizer()
                self.query_optimizer.add_dependency(self.db_manager, "database_manager")
                
                # 創建查詢執行器
                self.query_executor = QueryExecutor(self.db_manager, self.query_optimizer)
            
            # 初始化Token管理器（如果啟用）
            if self.enable_token_encryption:
                self.token_manager = get_token_manager(self.encryption_level)
                await self.token_manager.initialize()
            
            # 初始化事務管理器
            self.transaction_manager = TransactionManager(self.db_manager)
            
            self.logger.info("子機器人資料庫服務初始化完成")
            return True
            
        except Exception as e:
            self.logger.error(f"資料庫服務初始化失敗: {e}")
            return False
    
    async def _cleanup(self) -> None:
        """清理資源"""
        try:
            if self.repository:
                await self.repository.cleanup()
            
            if self.query_optimizer:
                await self.query_optimizer.cleanup()
            
            if self.token_manager:
                await self.token_manager.cleanup()
            
            self.logger.info("子機器人資料庫服務清理完成")
        except Exception as e:
            self.logger.error(f"清理資料庫服務時發生錯誤: {e}")
    
    async def _validate_permissions(self, user_id: int, guild_id: Optional[int], action: str) -> bool:
        """驗證權限"""
        # 資料庫操作通常需要管理員權限
        return True  # 暫時允許所有操作
    
    # ========== 高級API方法 ==========
    
    async def create_subbot(
        self,
        name: str,
        token: str,
        owner_id: int,
        channel_ids: Optional[List[int]] = None,
        ai_enabled: bool = False,
        ai_model: Optional[str] = None,
        personality: Optional[str] = None,
        rate_limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        創建子機器人（完整流程）
        
        Args:
            name: 子機器人名稱
            token: Discord Bot Token
            owner_id: 擁有者ID
            channel_ids: 頻道ID列表
            ai_enabled: 是否啟用AI功能
            ai_model: AI模型名稱
            personality: AI人格設定
            rate_limit: 速率限制
            
        Returns:
            創建結果
        """
        operation_start = datetime.now()
        
        try:
            self._service_stats['operations_count'] += 1
            
            # 使用事務確保一致性
            async with self.transaction_manager.transaction():
                # 生成唯一的bot_id
                bot_id = f"subbot_{int(datetime.now().timestamp())}_{hash(name) % 10000:04d}"
                
                # 處理Token加密
                encrypted_token = ""
                token_metadata = ""
                
                if self.enable_token_encryption and self.token_manager:
                    encrypted_token, token_metadata = await self.retry_handler.execute_with_retry(
                        self.token_manager.encrypt_discord_token,
                        token, bot_id
                    )
                else:
                    encrypted_token = token
                
                # 創建SubBot實體
                subbot = SubBotEntity(
                    bot_id=bot_id,
                    name=name,
                    token_hash=encrypted_token,
                    target_channels=channel_ids or [],
                    ai_enabled=ai_enabled,
                    ai_model=ai_model,
                    personality=personality,
                    rate_limit=rate_limit or 10,
                    owner_id=owner_id
                )
                
                # 保存到資料庫
                created_subbot = await self.retry_handler.execute_with_retry(
                    self.repository.create_subbot,
                    subbot
                )
                
                # 如果有頻道配置，創建頻道關聯
                if channel_ids and created_subbot.id:
                    for channel_id in channel_ids:
                        channel_entity = SubBotChannelEntity(
                            sub_bot_id=created_subbot.id,
                            channel_id=channel_id,
                            channel_type="text",
                            permissions={
                                'send_messages': True,
                                'read_messages': True,
                                'manage_messages': False
                            }
                        )
                        
                        await self.retry_handler.execute_with_retry(
                            self.repository.add_channel_to_subbot,
                            created_subbot.id, channel_entity
                        )
                
                # 更新統計
                self._service_stats['successful_operations'] += 1
                self._service_stats['last_operation_time'] = datetime.now()
                
                self.logger.info(f"成功創建子機器人: {bot_id}")
                
                return {
                    'success': True,
                    'subbot': {
                        'id': created_subbot.id,
                        'bot_id': created_subbot.bot_id,
                        'name': created_subbot.name,
                        'owner_id': created_subbot.owner_id,
                        'ai_enabled': created_subbot.ai_enabled,
                        'status': created_subbot.status,
                        'created_at': created_subbot.created_at.isoformat() if created_subbot.created_at else None
                    },
                    'channels_configured': len(channel_ids) if channel_ids else 0,
                    'token_encrypted': self.enable_token_encryption,
                    'encryption_level': self.encryption_level.value if self.enable_token_encryption else None,
                    'execution_time': (datetime.now() - operation_start).total_seconds()
                }
                
        except Exception as e:
            self._service_stats['failed_operations'] += 1
            self.logger.error(f"創建子機器人失敗: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__,
                'execution_time': (datetime.now() - operation_start).total_seconds()
            }
    
    async def get_subbot(self, bot_id: str, include_token: bool = False) -> Optional[Dict[str, Any]]:
        """
        獲取子機器人詳細資訊
        
        Args:
            bot_id: 子機器人ID
            include_token: 是否包含解密的Token
            
        Returns:
            子機器人資訊
        """
        try:
            # 從Repository獲取資料
            subbot = await self.retry_handler.execute_with_retry(
                self.repository.get_subbot_by_bot_id,
                bot_id, False  # 不在Repository層解密
            )
            
            if not subbot:
                return None
            
            # 轉換為字典
            result = {
                'id': subbot.id,
                'bot_id': subbot.bot_id,
                'name': subbot.name,
                'owner_id': subbot.owner_id,
                'target_channels': subbot.target_channels,
                'ai_enabled': subbot.ai_enabled,
                'ai_model': subbot.ai_model,
                'personality': subbot.personality,
                'rate_limit': subbot.rate_limit,
                'status': subbot.status,
                'created_at': subbot.created_at.isoformat() if subbot.created_at else None,
                'updated_at': subbot.updated_at.isoformat() if subbot.updated_at else None,
                'last_active_at': subbot.last_active_at.isoformat() if subbot.last_active_at else None,
                'message_count': subbot.message_count
            }
            
            # 如果需要Token且啟用加密
            if include_token and self.enable_token_encryption and self.token_manager:
                try:
                    # 這裡需要Token元資料，實際實現中應該從資料庫獲取
                    # 暫時模擬處理
                    token_info = self.token_manager.get_token_info(bot_id)
                    if token_info:
                        result['token_info'] = token_info
                    else:
                        result['token_available'] = False
                except Exception as e:
                    self.logger.warning(f"獲取Token資訊失敗: {e}")
                    result['token_error'] = str(e)
            
            # 獲取頻道配置
            if subbot.id:
                channels = await self.retry_handler.execute_with_retry(
                    self.repository.get_subbot_channels,
                    subbot.id
                )
                result['channels'] = [
                    {
                        'id': ch.id,
                        'channel_id': ch.channel_id,
                        'channel_type': ch.channel_type,
                        'permissions': ch.permissions,
                        'created_at': ch.created_at.isoformat() if ch.created_at else None
                    }
                    for ch in channels
                ]
            
            return result
            
        except Exception as e:
            self.logger.error(f"獲取子機器人失敗: {e}")
            return None
    
    async def update_subbot(self, bot_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新子機器人資訊
        
        Args:
            bot_id: 子機器人ID
            updates: 要更新的欄位
            
        Returns:
            是否更新成功
        """
        try:
            # 獲取現有資料
            subbot = await self.repository.get_subbot_by_bot_id(bot_id)
            if not subbot:
                return False
            
            # 應用更新
            for key, value in updates.items():
                if hasattr(subbot, key):
                    setattr(subbot, key, value)
            
            # 處理Token更新（如果包含）
            if 'token' in updates and self.enable_token_encryption and self.token_manager:
                encrypted_token, token_metadata = await self.retry_handler.execute_with_retry(
                    self.token_manager.encrypt_discord_token,
                    updates['token'], bot_id
                )
                subbot.token_hash = encrypted_token
            
            # 執行更新
            success = await self.retry_handler.execute_with_retry(
                self.repository.update_subbot,
                subbot
            )
            
            if success:
                self.logger.info(f"成功更新子機器人: {bot_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"更新子機器人失敗: {e}")
            return False
    
    async def delete_subbot(self, bot_id: str) -> bool:
        """
        刪除子機器人
        
        Args:
            bot_id: 子機器人ID
            
        Returns:
            是否刪除成功
        """
        try:
            async with self.transaction_manager.transaction():
                # 執行刪除
                success = await self.retry_handler.execute_with_retry(
                    self.repository.delete_subbot,
                    bot_id
                )
                
                if success:
                    self.logger.info(f"成功刪除子機器人: {bot_id}")
                
                return success
                
        except Exception as e:
            self.logger.error(f"刪除子機器人失敗: {e}")
            return False
    
    async def list_subbots(
        self,
        status: Optional[str] = None,
        owner_id: Optional[int] = None,
        ai_enabled: Optional[bool] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        列出子機器人
        
        Args:
            status: 狀態過濾
            owner_id: 擁有者ID過濾
            ai_enabled: AI啟用狀態過濾
            limit: 結果限制
            offset: 偏移量
            
        Returns:
            子機器人列表
        """
        try:
            subbots = await self.retry_handler.execute_with_retry(
                self.repository.list_subbots,
                status, ai_enabled, owner_id, limit, offset, False
            )
            
            result = []
            for subbot in subbots:
                result.append({
                    'id': subbot.id,
                    'bot_id': subbot.bot_id,
                    'name': subbot.name,
                    'owner_id': subbot.owner_id,
                    'status': subbot.status,
                    'ai_enabled': subbot.ai_enabled,
                    'ai_model': subbot.ai_model,
                    'created_at': subbot.created_at.isoformat() if subbot.created_at else None,
                    'last_active_at': subbot.last_active_at.isoformat() if subbot.last_active_at else None,
                    'message_count': subbot.message_count
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"列出子機器人失敗: {e}")
            return []
    
    async def update_activity(self, bot_id: str, message_count_increment: int = 1) -> bool:
        """
        更新子機器人活動統計
        
        Args:
            bot_id: 子機器人ID
            message_count_increment: 訊息數量增量
            
        Returns:
            是否更新成功
        """
        try:
            return await self.retry_handler.execute_with_retry(
                self.repository.update_subbot_activity,
                bot_id, message_count_increment
            )
        except Exception as e:
            self.logger.error(f"更新活動統計失敗: {e}")
            return False
    
    async def update_status(self, bot_id: str, status: str) -> bool:
        """
        更新子機器人狀態
        
        Args:
            bot_id: 子機器人ID
            status: 新狀態
            
        Returns:
            是否更新成功
        """
        try:
            return await self.retry_handler.execute_with_retry(
                self.repository.update_subbot_status,
                bot_id, status
            )
        except Exception as e:
            self.logger.error(f"更新狀態失敗: {e}")
            return False
    
    # ========== 批次操作 ==========
    
    async def batch_update_status(self, status_updates: List[Tuple[str, str]]) -> Dict[str, Any]:
        """
        批次更新狀態
        
        Args:
            status_updates: (bot_id, status) 元組列表
            
        Returns:
            批次更新結果
        """
        results = {
            'success_count': 0,
            'failed_count': 0,
            'results': []
        }
        
        for bot_id, status in status_updates:
            try:
                success = await self.update_status(bot_id, status)
                results['results'].append({
                    'bot_id': bot_id,
                    'status': status,
                    'success': success
                })
                
                if success:
                    results['success_count'] += 1
                else:
                    results['failed_count'] += 1
                    
            except Exception as e:
                results['results'].append({
                    'bot_id': bot_id,
                    'status': status,
                    'success': False,
                    'error': str(e)
                })
                results['failed_count'] += 1
        
        return results
    
    # ========== 統計和監控 ==========
    
    async def get_statistics(self) -> Dict[str, Any]:
        """獲取完整統計資訊"""
        try:
            stats = {}
            
            # Repository統計
            if self.repository:
                repo_stats = await self.repository.get_subbots_statistics()
                stats['repository'] = repo_stats
                
                cache_stats = self.repository.get_cache_stats()
                stats['cache'] = cache_stats
            
            # 查詢優化器統計
            if self.query_optimizer:
                query_stats = self.query_optimizer.get_query_statistics()
                stats['query_optimizer'] = query_stats
            
            # 查詢執行器統計
            if self.query_executor:
                execution_stats = self.query_executor.get_execution_stats()
                stats['query_executor'] = execution_stats
            
            # Token管理器統計
            if self.token_manager:
                token_stats = self.token_manager.get_statistics()
                stats['token_manager'] = token_stats
            
            # 事務管理器統計
            if self.transaction_manager:
                txn_stats = self.transaction_manager.get_transaction_stats()
                stats['transaction_manager'] = txn_stats
            
            # 服務層統計
            stats['service'] = self._service_stats.copy()
            
            return stats
            
        except Exception as e:
            self.logger.error(f"獲取統計失敗: {e}")
            return {'error': str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        try:
            health_status = {
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'components': {}
            }
            
            # 檢查Repository
            if self.repository:
                repo_health = await self.repository.health_check()
                health_status['components']['repository'] = repo_health
            
            # 檢查資料庫連接
            if self.db_manager:
                try:
                    await self.db_manager.fetchone("SELECT 1")
                    health_status['components']['database'] = {'status': 'healthy'}
                except Exception as e:
                    health_status['components']['database'] = {'status': 'unhealthy', 'error': str(e)}
                    health_status['status'] = 'degraded'
            
            # 檢查Token管理器
            if self.token_manager:
                token_stats = self.token_manager.get_statistics()
                health_status['components']['token_manager'] = {
                    'status': 'healthy',
                    'encryption_level': token_stats.get('encryption_level'),
                    'total_tokens': token_stats.get('total_tokens', 0)
                }
            
            return health_status
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    # ========== 維護操作 ==========
    
    async def optimize_database(self) -> Dict[str, Any]:
        """執行資料庫優化"""
        try:
            result = {
                'success': True,
                'operations': []
            }
            
            # 創建推薦的索引
            if self.query_optimizer:
                index_result = await self.query_optimizer.create_recommended_indexes()
                result['operations'].append({
                    'operation': 'create_indexes',
                    'result': index_result
                })
            
            # 執行VACUUM
            if self.db_manager:
                await self.db_manager.execute("VACUUM")
                result['operations'].append({
                    'operation': 'vacuum',
                    'result': {'success': True}
                })
            
            # 分析表統計
            if self.db_manager:
                await self.db_manager.execute("ANALYZE")
                result['operations'].append({
                    'operation': 'analyze',
                    'result': {'success': True}
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"資料庫優化失敗: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def clear_cache(self) -> bool:
        """清除快取"""
        try:
            if self.repository:
                self.repository.clear_cache()
            return True
        except Exception as e:
            self.logger.error(f"清除快取失敗: {e}")
            return False


# 全域實例
_subbot_db_service: Optional[SubBotDatabaseService] = None


async def get_subbot_database_service() -> SubBotDatabaseService:
    """
    獲取全域子機器人資料庫服務實例
    
    Returns:
        資料庫服務實例
    """
    global _subbot_db_service
    if _subbot_db_service is None:
        _subbot_db_service = SubBotDatabaseService()
        await _subbot_db_service.initialize()
    return _subbot_db_service