"""
核心錯誤處理系統
Task ID: 1 - 建立核心架構基礎

這個模組提供了分層的錯誤處理架構，包含：
- 錯誤類別層次結構
- 全域錯誤處理裝飾器  
- 錯誤記錄和報告機制
- 使用者友善的錯誤訊息轉換
- 錯誤恢復和降級策略
"""
import asyncio
import logging
import functools
import traceback
from typing import Optional, Dict, Any, Callable, Union
from enum import Enum
import discord
from discord.ext import commands

# 設定日誌記錄器
logger = logging.getLogger('core.exceptions')


class ErrorSeverity(Enum):
    """錯誤嚴重性等級"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """錯誤類別"""
    SYSTEM = "system"
    DATABASE = "database"
    DISCORD = "discord"
    PERMISSION = "permission"
    VALIDATION = "validation"
    BUSINESS = "business"


class BotError(Exception):
    """
    機器人錯誤基礎類別
    
    所有自定義錯誤的基礎類別，提供統一的錯誤處理介面
    """
    
    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        user_message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = True
    ):
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.category = category
        self.user_message = user_message or self._get_default_user_message()
        self.details = details or {}
        self.recoverable = recoverable
        
    def _get_default_user_message(self) -> str:
        """獲取預設的使用者友善錯誤訊息"""
        return "發生了一個錯誤，請稍後再試或聯絡管理員。"
    
    def to_dict(self) -> Dict[str, Any]:
        """將錯誤轉換為字典格式，便於記錄和報告"""
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "severity": self.severity.value,
            "category": self.category.value,
            "user_message": self.user_message,
            "details": self.details,
            "recoverable": self.recoverable
        }


class ServiceError(BotError):
    """
    服務層錯誤
    
    當服務層（業務邏輯）發生錯誤時拋出
    """
    
    def __init__(
        self,
        message: str,
        service_name: str,
        operation: str,
        **kwargs
    ):
        # 先設定 service_name 屬性，然後調用父類
        self.service_name = service_name
        self.operation = operation
        
        # 確保 category 設定正確
        kwargs.setdefault('category', ErrorCategory.BUSINESS)
        
        super().__init__(
            message,
            **kwargs
        )
        
        # 更新詳情
        self.details.update({
            "service_name": service_name,
            "operation": operation
        })
    
    def _get_default_user_message(self) -> str:
        return f"服務 {self.service_name} 暫時無法使用，請稍後再試。"


class ServiceInitializationError(ServiceError):
    """服務初始化錯誤"""
    
    def __init__(self, service_name: str, reason: str, **kwargs):
        # 移除可能導致衝突的參數
        kwargs.pop('category', None)
        kwargs.setdefault('severity', ErrorSeverity.HIGH)
        kwargs.setdefault('recoverable', False)
        
        super().__init__(
            f"服務 {service_name} 初始化失敗：{reason}",
            service_name=service_name,
            operation="initialize",
            **kwargs
        )
        self.reason = reason


class ServicePermissionError(ServiceError):
    """服務權限錯誤"""
    
    def __init__(self, service_name: str, user_id: int, action: str, **kwargs):
        # 先設定屬性
        self.user_id = user_id
        self.action = action
        
        # 移除可能導致衝突的參數
        kwargs.pop('category', None)
        
        super().__init__(
            f"使用者 {user_id} 沒有權限在服務 {service_name} 執行 {action}",
            service_name=service_name,
            operation=action,
            category=ErrorCategory.PERMISSION,
            **kwargs
        )
        
        # 更新詳情
        self.details.update({
            "user_id": user_id,
            "action": action
        })
    
    def _get_default_user_message(self) -> str:
        return "您沒有執行此操作的權限。"


class DatabaseError(BotError):
    """
    資料庫錯誤
    
    當資料庫操作失敗時拋出
    """
    
    def __init__(
        self,
        message: str,
        operation: str,
        table: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.DATABASE,
            **kwargs
        )
        self.operation = operation
        self.table = table
        self.details.update({
            "operation": operation,
            "table": table
        })
    
    def _get_default_user_message(self) -> str:
        return "資料庫暫時無法使用，請稍後再試。"


class DatabaseConnectionError(DatabaseError):
    """資料庫連線錯誤"""
    
    def __init__(self, db_name: str, reason: str, **kwargs):
        super().__init__(
            f"無法連線到資料庫 {db_name}：{reason}",
            operation="connect",
            severity=ErrorSeverity.CRITICAL,
            recoverable=False,
            **kwargs
        )
        self.db_name = db_name
        self.details["db_name"] = db_name


class DatabaseQueryError(DatabaseError):
    """資料庫查詢錯誤"""
    
    def __init__(self, query: str, error: str, table: Optional[str] = None, **kwargs):
        super().__init__(
            f"資料庫查詢失敗：{error}",
            operation="query",
            table=table,
            **kwargs
        )
        self.query = query
        self.error = error
        self.details.update({
            "query": query,
            "error": error
        })


class DiscordError(BotError):
    """
    Discord API 錯誤
    
    當 Discord API 操作失敗時拋出
    """
    
    def __init__(
        self,
        message: str,
        discord_error: Optional[discord.DiscordException] = None,
        **kwargs
    ):
        super().__init__(
            message,
            category=ErrorCategory.DISCORD,
            **kwargs
        )
        self.discord_error = discord_error
        if discord_error:
            self.details["discord_error"] = str(discord_error)
    
    def _get_default_user_message(self) -> str:
        return "Discord 服務暫時無法使用，請稍後再試。"


class ValidationError(BotError):
    """
    輸入驗證錯誤
    
    當使用者輸入不符合要求時拋出
    """
    
    def __init__(
        self,
        message: str,
        field: str,
        value: Any,
        expected: str,
        **kwargs
    ):
        # 先設置屬性
        self.field = field
        self.value = value
        self.expected = expected
        
        super().__init__(
            message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            **kwargs
        )
        
        self.details.update({
            "field": field,
            "value": str(value),
            "expected": expected
        })
    
    def _get_default_user_message(self) -> str:
        return f"輸入格式錯誤：{self.field} 應該是 {self.expected}"


# 錯誤處理裝飾器
def handle_errors(
    log_errors: bool = True,
    return_user_message: bool = False,
    default_return_value: Any = None
):
    """
    全域錯誤處理裝飾器
    
    參數：
        log_errors: 是否記錄錯誤到日誌
        return_user_message: 是否返回使用者友善的錯誤訊息
        default_return_value: 發生錯誤時的預設返回值
    """
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except BotError as e:
                    if log_errors:
                        logger.error(f"BotError in {func.__name__}: {e.to_dict()}")
                    
                    if return_user_message:
                        return e.user_message
                    elif default_return_value is not None:
                        return default_return_value
                    else:
                        raise
                        
                except Exception as e:
                    if log_errors:
                        logger.exception(f"Unexpected error in {func.__name__}: {str(e)}")
                    
                    # 將意外錯誤包裝為 BotError
                    bot_error = BotError(
                        f"Unexpected error in {func.__name__}: {str(e)}",
                        severity=ErrorSeverity.HIGH,
                        details={
                            "function": func.__name__,
                            "original_error": str(e),
                            "traceback": traceback.format_exc()
                        }
                    )
                    
                    if return_user_message:
                        return bot_error.user_message
                    elif default_return_value is not None:
                        return default_return_value
                    else:
                        raise bot_error
                        
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except BotError as e:
                    if log_errors:
                        logger.error(f"BotError in {func.__name__}: {e.to_dict()}")
                    
                    if return_user_message:
                        return e.user_message
                    elif default_return_value is not None:
                        return default_return_value
                    else:
                        raise
                        
                except Exception as e:
                    if log_errors:
                        logger.exception(f"Unexpected error in {func.__name__}: {str(e)}")
                    
                    # 將意外錯誤包裝為 BotError
                    bot_error = BotError(
                        f"Unexpected error in {func.__name__}: {str(e)}",
                        severity=ErrorSeverity.HIGH,
                        details={
                            "function": func.__name__,
                            "original_error": str(e),
                            "traceback": traceback.format_exc()
                        }
                    )
                    
                    if return_user_message:
                        return bot_error.user_message
                    elif default_return_value is not None:
                        return default_return_value
                    else:
                        raise bot_error
                        
            return sync_wrapper
    return decorator


def discord_error_handler(
    send_to_user: bool = True,
    ephemeral: bool = True
):
    """
    Discord 互動專用的錯誤處理裝飾器
    
    參數：
        send_to_user: 是否向使用者發送錯誤訊息
        ephemeral: 錯誤訊息是否為私人訊息
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            try:
                await func(self, interaction, *args, **kwargs)
            except BotError as e:
                logger.error(f"BotError in Discord interaction {func.__name__}: {e.to_dict()}")
                
                if send_to_user:
                    try:
                        if interaction.response.is_done():
                            await interaction.followup.send(
                                e.user_message,
                                ephemeral=ephemeral
                            )
                        else:
                            await interaction.response.send_message(
                                e.user_message,
                                ephemeral=ephemeral
                            )
                    except Exception as send_error:
                        logger.error(f"Failed to send error message to user: {send_error}")
                        
            except Exception as e:
                logger.exception(f"Unexpected error in Discord interaction {func.__name__}: {str(e)}")
                
                error_message = "發生了一個意外錯誤，請稍後再試或聯絡管理員。"
                
                if send_to_user:
                    try:
                        if interaction.response.is_done():
                            await interaction.followup.send(
                                error_message,
                                ephemeral=ephemeral
                            )
                        else:
                            await interaction.response.send_message(
                                error_message,
                                ephemeral=ephemeral
                            )
                    except Exception as send_error:
                        logger.error(f"Failed to send error message to user: {send_error}")
                        
        return wrapper
    return decorator


class ErrorReporter:
    """
    錯誤報告器
    
    提供錯誤記錄、統計和報告功能
    """
    
    def __init__(self):
        self.error_counts: Dict[str, int] = {}
        self.recent_errors: list = []
        self.max_recent_errors = 100
    
    def report_error(self, error: BotError, context: Optional[Dict[str, Any]] = None):
        """
        報告錯誤
        
        參數：
            error: 要報告的錯誤
            context: 額外的上下文信息
        """
        error_type = error.__class__.__name__
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        error_record = {
            "timestamp": discord.utils.utcnow().isoformat(),
            "error": error.to_dict(),
            "context": context or {}
        }
        
        self.recent_errors.append(error_record)
        
        # 保持最近錯誤記錄的數量限制
        if len(self.recent_errors) > self.max_recent_errors:
            self.recent_errors.pop(0)
        
        # 記錄到日誌
        logger.error(f"Error reported: {error.to_dict()}")
        
        # 如果是嚴重錯誤，額外記錄
        if error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            logger.critical(f"Critical error reported: {error.to_dict()}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """獲取錯誤統計信息"""
        total_errors = sum(self.error_counts.values())
        
        return {
            "total_errors": total_errors,
            "error_counts": self.error_counts.copy(),
            "recent_errors_count": len(self.recent_errors),
            "most_common_error": max(self.error_counts.items(), key=lambda x: x[1]) if self.error_counts else None
        }
    
    def clear_statistics(self):
        """清除錯誤統計"""
        self.error_counts.clear()
        self.recent_errors.clear()


# 全域錯誤報告器實例
error_reporter = ErrorReporter()


# 錯誤恢復策略
class ErrorRecoveryStrategy:
    """錯誤恢復策略基礎類別"""
    
    async def can_recover(self, error: BotError) -> bool:
        """檢查是否可以恢復"""
        return error.recoverable
    
    async def recover(self, error: BotError, context: Optional[Dict[str, Any]] = None) -> bool:
        """嘗試恢復錯誤"""
        raise NotImplementedError("Subclasses must implement recover method")


class DatabaseRecoveryStrategy(ErrorRecoveryStrategy):
    """資料庫錯誤恢復策略"""
    
    async def can_recover(self, error: BotError) -> bool:
        return isinstance(error, DatabaseError) and error.recoverable
    
    async def recover(self, error: BotError, context: Optional[Dict[str, Any]] = None) -> bool:
        """嘗試重新連線資料庫"""
        if isinstance(error, DatabaseConnectionError):
            try:
                # 這裡會在 DatabaseManager 實作後完善
                logger.info(f"Attempting to recover from database connection error: {error.db_name}")
                return True
            except Exception as e:
                logger.error(f"Database recovery failed: {e}")
                return False
        return False


class ServiceRecoveryStrategy(ErrorRecoveryStrategy):
    """服務錯誤恢復策略"""
    
    async def can_recover(self, error: BotError) -> bool:
        return isinstance(error, ServiceError) and error.recoverable
    
    async def recover(self, error: BotError, context: Optional[Dict[str, Any]] = None) -> bool:
        """嘗試重新初始化服務"""
        if isinstance(error, ServiceInitializationError):
            try:
                logger.info(f"Attempting to recover service: {error.service_name}")
                # 這裡會在 BaseService 實作後完善
                return True
            except Exception as e:
                logger.error(f"Service recovery failed: {e}")
                return False
        return False


class ErrorRecoveryManager:
    """錯誤恢復管理器"""
    
    def __init__(self):
        self.strategies = [
            DatabaseRecoveryStrategy(),
            ServiceRecoveryStrategy()
        ]
    
    async def attempt_recovery(self, error: BotError, context: Optional[Dict[str, Any]] = None) -> bool:
        """嘗試恢復錯誤"""
        for strategy in self.strategies:
            if await strategy.can_recover(error):
                try:
                    if await strategy.recover(error, context):
                        logger.info(f"Successfully recovered from error: {error.__class__.__name__}")
                        return True
                except Exception as e:
                    logger.error(f"Recovery strategy failed: {e}")
        
        logger.warning(f"No recovery strategy available for error: {error.__class__.__name__}")
        return False


# 全域錯誤恢復管理器實例
error_recovery_manager = ErrorRecoveryManager()